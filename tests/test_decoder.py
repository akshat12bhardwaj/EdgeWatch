"""Byte-level decoder tests. All packets are invented; no capture files are read."""
import dataclasses
import hashlib
import hmac
import json
import logging
import struct
import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ids import FeatureAggregator, MqttMessage, PacketEvent, extract_features, read_pcap  # noqa: E402
from ids import decoder, fields  # noqa: E402
from ids.decoder import DecoderError, decode_packets, decode_pcap, read_records  # noqa: E402

CLIENT, BROKER = bytes([192, 0, 2, 1]), bytes([192, 0, 2, 9])
CLIENT_S, BROKER_S = "192.0.2.1", "192.0.2.9"
SENTINELS = ("SENTINEL-TOPIC", "SENTINEL-USER", "SENTINEL-PASS", "SENTINEL-CLIENT", "SENTINEL-PAYLOAD")
SYN, ACK, FIN, RST, PSH = 2, 16, 1, 4, 8


def ipv4(payload, src=CLIENT, dst=BROKER, proto=6, frag=0, total=None):
    return struct.pack(">BBHHHBBH4s4s", 0x45, 0, 20 + len(payload) if total is None else total, 1, frag, 64, proto, 0, src, dst) + payload


def tcp(seq=1000, flags=PSH | ACK, data=b"", sport=5000, dport=1883):
    return struct.pack(">HHIIBBHHH", sport, dport, seq & 0xffffffff, 1, 0x50, flags, 8192, 0, 0) + data


def eth(ip_packet, ethertype=0x0800):
    return b"\x02" * 6 + b"\x04" * 6 + struct.pack(">H", ethertype) + ip_packet


def up(seq=1000, data=b"", flags=PSH | ACK, sport=5000, t=100):
    return t * 10 ** 9, 1, eth(ipv4(tcp(seq, flags, data, sport, 1883)))


def down(seq=9000, data=b"", flags=PSH | ACK, sport=5000, t=100):
    return t * 10 ** 9, 1, eth(ipv4(tcp(seq, flags, data, 1883, sport), BROKER, CLIENT))


def mstr(text):
    return struct.pack(">H", len(text)) + text


def varint(n):
    out = b""
    while True:
        n, digit = n >> 7, n & 127
        out += bytes([digit | (128 if n else 0)])
        if not n:
            return out


def msg(header, body=b""):
    return bytes([header]) + varint(len(body)) + body


def publish(topic=b"t/a", qos=0, retain=False, payload=b"x"):
    return msg(0x30 | qos << 1 | retain, mstr(topic) + (b"\0\1" if qos else b"") + payload)


def subscribe(*filters):
    return msg(0x82, b"\0\1" + b"".join(mstr(f) + b"\0" for f in filters))


def unsubscribe(*filters):
    return msg(0xa2, b"\0\2" + b"".join(mstr(f) for f in filters))


def connect(keepalive=60, client=b"SENTINEL-CLIENT", user=b"SENTINEL-USER", password=b"SENTINEL-PASS"):
    return msg(0x10, mstr(b"MQTT") + b"\x04\xc2" + struct.pack(">H", keepalive) + mstr(client) + mstr(user) + mstr(password))


def decode(*packets, stats=None, **options):
    return list(decode_packets(packets, stats, **options))


def types(events):
    return [[m.msg_type for m in e.mqtt] for e in events]


def leaks(*objects):
    items = [i for o in objects for i in (o if isinstance(o, list) else [o])]
    text = "".join(repr(i) + (repr(dataclasses.asdict(i)) if dataclasses.is_dataclass(i) else "") for i in items)
    return [s for s in SENTINELS if s in text]


def write_pcap(path, packets, cut=0):
    data = struct.pack("<IHHiIII", 0xa1b2c3d4, 2, 4, 0, 0, 65535, 1)
    for i, (t, _, frame) in enumerate(packets):
        data += struct.pack("<IIII", t // 10 ** 9, i, len(frame), len(frame)) + frame
    path.write_bytes(data[:-cut] if cut else data)
    return path


def write_pcapng(path, packets):
    def block(kind, body):
        return struct.pack("<II", kind, 12 + len(body)) + body + struct.pack("<I", 12 + len(body))
    data = block(0x0a0d0d0a, struct.pack("<IHHq", 0x1a2b3c4d, 1, 0, -1)) + block(1, struct.pack("<HHI", 1, 0, 65535))
    for t, _, frame in packets:
        micro = t // 1000
        data += block(6, struct.pack("<IIIII", 0, micro >> 32, micro & 0xffffffff, len(frame), len(frame)) + frame + b"\0" * (-len(frame) % 4))
    path.write_bytes(data)
    return path


# Link, IP, and TCP parsing

def test_ethernet_ipv4_tcp_fields_and_padding():
    frame = eth(ipv4(tcp(flags=SYN | ACK | FIN | RST, data=b""))) + b"\0" * 6  # Ethernet padding is not TCP data
    event, = decode((123 * 10 ** 9, 1, frame))
    assert event == PacketEvent(123 * 10 ** 9, CLIENT_S, BROKER_S, 5000, 1883, tcp_len=0, syn=True, ack=True, fin=True, rst=True)


def test_vlan_tag_is_skipped():
    frame = eth(struct.pack(">HH", 7, 0x0800) + ipv4(tcp()), 0x8100)
    assert decode((1, 1, frame))[0].src == CLIENT_S


def test_ipv6_is_parsed_and_its_addresses_are_canonical():
    segment = tcp(data=publish())
    ip6 = struct.pack(">IHBB", 6 << 28, len(segment), 6, 64) + bytes.fromhex("20010db8" + "0" * 23 + "1") + bytes.fromhex("20010db8" + "0" * 23 + "9") + segment
    event, = decode((1, 1, eth(ip6, 0x86dd)))
    assert (event.src, event.dst) == ("2001:db8::1", "2001:db8::9") and event.mqtt[0].msg_type == 3


def ipv6(headers_and_payload, first_header):
    return struct.pack(">IHBB", 6 << 28, len(headers_and_payload), first_header, 64) + b"\1" * 16 + b"\2" * 16 + headers_and_payload


@pytest.mark.parametrize("first, extension", [
    (0, bytes([6, 0]) + bytes(6)),  # hop-by-hop
    (60, bytes([6, 1]) + bytes(14)),  # destination options, 16 bytes
    (43, bytes([60, 0]) + bytes(6) + bytes([6, 0]) + bytes(6)),  # routing, then destination options
])
def test_ipv6_extension_headers_are_walked_to_tcp(first, extension):
    event, = decode((1, 1, eth(ipv6(extension + tcp(data=publish()), first), 0x86dd)))
    assert [m.msg_type for m in event.mqtt] == [3] and event.tcp_len == len(publish())


def test_ipv6_extension_header_running_past_the_packet_is_counted():
    stats = Counter()
    assert decode((1, 1, eth(ipv6(bytes([6, 200]) + bytes(6), 0), 0x86dd)), stats=stats) == [] and stats["bad_metadata_frames"] == 1


def test_ipv6_atomic_fragment_is_plain_tcp():
    event, = decode((1, 1, eth(ipv6(bytes([6, 0, 0, 0, 0, 0, 0, 9]) + tcp(data=publish()), 44), 0x86dd)))
    assert [m.msg_type for m in event.mqtt] == [3]


def fragments_v4(segment, cut, ident_frag_first=0x2000):
    return (eth(ipv4(segment[:cut], frag=ident_frag_first)), eth(ipv4(segment[cut:], frag=cut // 8)))


def test_ipv4_fragments_are_reassembled_on_the_completing_frame_in_either_order():
    segment = tcp(data=publish(payload=b"x" * 60))
    first, last = fragments_v4(segment, 16)
    for order in ((first, last), (last, first)):
        stats = Counter()
        event, = decode(*[(5, 1, f) for f in order], stats=stats)
        assert [m.msg_type for m in event.mqtt] == [3] and event.tcp_len == len(segment) - 20
        assert stats["ip_fragments"] == 2 and stats["ip_datagrams_reassembled"] == 1


def test_ipv6_fragments_are_reassembled():
    segment = tcp(data=publish(payload=b"x" * 60))
    pieces = [bytes([6, 0, 0, 1, 0, 0, 0, 9]) + segment[:16], bytes([6, 0, 0, 16, 0, 0, 0, 9]) + segment[16:]]
    event, = decode(*[(5, 1, eth(ipv6(p, 44), 0x86dd)) for p in pieces])
    assert [m.msg_type for m in event.mqtt] == [3]


def test_overlapping_fragments_drop_the_datagram_so_they_cannot_rewrite_data():
    segment = tcp(data=publish(payload=b"x" * 60))
    first, last = fragments_v4(segment, 16)
    overlap = eth(ipv4(segment[8:24], frag=0x2000 | 1))
    stats = Counter()
    assert decode((5, 1, first), (5, 1, overlap), (5, 1, last), stats=stats) == []
    assert stats["ip_fragment_overlaps"] == 1 and stats["ip_datagrams_reassembled"] == 0


def test_fragment_memory_is_limited_by_count_and_by_time():
    stats = Counter()
    pool = decoder._Fragments(stats, max_datagrams=2, timeout_ns=100)
    for i in range(5):
        assert pool.add(("a", "b", i), 0, True, b"x" * 8, 0) is None
    assert len(pool.held) == 2 and stats["ip_fragments_expired"] == 3
    pool.add(("a", "b", 99), 0, True, b"x" * 8, 1000)
    assert list(pool.held) == [("a", "b", 99)]


def test_fragment_past_the_ip_limit_or_with_an_unaligned_middle_is_rejected():
    stats = Counter()
    pool = decoder._Fragments(stats)
    assert pool.add(("a", "b", 1), 65528, False, b"x" * 16, 0) is None
    assert pool.add(("a", "b", 2), 0, True, b"x" * 7, 0) is None
    assert stats["ip_fragments_invalid"] == 2 and not pool.held


@pytest.mark.parametrize("link, prefix", [
    (0, b"\x02\0\0\0"),  # null/loopback, which Npcap's loopback adapter uses
    (101, b""),  # raw IP
    (113, bytes(14) + b"\x08\x00"),  # Linux cooked
    (276, b"\x08\x00" + bytes(18)),  # Linux cooked v2
])
def test_each_supported_link_type_reaches_mqtt(link, prefix):
    event, = decode((1, link, prefix + ipv4(tcp(data=publish()))))
    assert [m.msg_type for m in event.mqtt] == [3] and event.src == CLIENT_S


def test_tcp_options_are_skipped_by_the_header_length():
    segment = struct.pack(">HHIIBBHHH", 5000, 1883, 1000, 1, 0x80, PSH | ACK, 8192, 0, 0) + b"\1" * 12 + publish()
    event, = decode((1, 1, eth(ipv4(segment))))
    assert event.tcp_len == len(publish()) and event.mqtt[0].msg_type == 3


@pytest.mark.parametrize("frame, key", [
    (b"\0" * 5, "bad_metadata_frames"),
    (eth(b"\x45"), "bad_metadata_frames"),
    (eth(ipv4(b"short")), "bad_metadata_frames"),
    (eth(ipv4(tcp()[:12] + b"\x10" + tcp()[13:])), "bad_metadata_frames"),  # TCP header length of 4
    (eth(ipv4(tcp(), total=10)), "bad_metadata_frames"),
    (eth(b"\0" * 28, 0x0806), "non_tcp_frames"),
    (eth(ipv4(b"\0" * 8, proto=17)), "non_tcp_frames"),
    (eth(ipv4(tcp(), frag=0x2000)), "ip_fragments"),
    (eth(ipv4(tcp(), frag=5)), "ip_fragments"),
])
def test_unusable_frames_are_counted_and_skipped(frame, key):
    stats = Counter()
    assert decode((1, 1, frame), up(), stats=stats)[0].sport == 5000 and stats[key] == 1 and stats["events"] == 1


def test_unsupported_link_type_is_counted():
    stats = Counter()
    assert decode((1, 999, b"\0" * 60), stats=stats) == [] and stats["unsupported_link_frames"] == 1


def test_frames_on_other_ports_become_events_without_mqtt():
    event, = decode((1, 1, eth(ipv4(tcp(data=publish(), dport=80)))))
    assert event.dport == 80 and event.mqtt == ()


def test_truncated_capture_keeps_the_declared_tcp_length_and_counts_it():
    ip = ipv4(tcp(data=b"\x30\x05abc"), total=20 + 20 + 100)
    stats = Counter()
    event, = decode((1, 1, eth(ip)), stats=stats)
    assert event.tcp_len == 100 and stats["truncated_tcp_frames"] == 1


# TCP reconstruction

def test_message_split_across_segments_belongs_to_the_completing_frame():
    p = publish()
    assert types(decode(up(1000, p[:2]), up(1002, p[2:]))) == [[], [3]]


def test_one_segment_with_a_whole_message_and_part_of_the_next():
    p, q = publish(b"a"), publish(b"b")
    assert types(decode(up(1000, p + q[:2]), up(1000 + len(p) + 2, q[2:]))) == [[3], [3]]


def test_multiple_messages_in_one_segment():
    data = publish(b"a") + msg(0xc0) + publish(b"b")
    assert types(decode(up(1000, data))) == [[3, 12, 3]]


def test_exact_retransmission_is_not_counted_twice():
    p = publish()
    stats = Counter()
    assert types(decode(up(1000, p), up(1000, p), stats=stats)) == [[3], []]
    assert stats["tcp_retransmitted_segments"] == 1


def test_partial_overlap_keeps_only_new_bytes():
    p = publish()
    stats = Counter()
    events = decode(up(1000, p[:4]), up(1002, p[2:]), up(1000 + len(p), msg(0xc0)), stats=stats)
    assert types(events) == [[], [3], [12]] and stats["tcp_partial_overlaps"] == 1  # leftover bytes would break the PINGREQ


def test_out_of_order_segments_are_held_until_the_gap_fills():
    p, q = publish(b"a"), publish(b"b")
    stats = Counter()
    events = decode(up(2000, p), up(2000 + len(p) + len(q), q), up(2000 + len(p), q), stats=stats)
    assert types(events) == [[3], [], [3, 3]] and stats["tcp_out_of_order_segments"] == 1


def test_retransmission_after_a_syn_reset_and_zero_length_frame_ahead_of_data():
    p = publish()
    events = decode(up(999, flags=SYN), up(1000), up(1000 + 2 * len(p)), up(1000, p), up(1000 + len(p), p))
    assert types(events) == [[], [], [], [3], [3]]  # the capture_1w pattern: empty frames carry no sequence state


def test_sequence_numbers_wrap():
    p = publish()
    start = 2 ** 32 - 2
    stats = Counter()
    events = decode(up(start, p[:2]), up(0, p[2:]), up(start, p[:2]), stats=stats)  # the old sequence number is behind, not far ahead
    assert types(events) == [[], [3], []] and stats["tcp_retransmitted_segments"] == 1


def test_syn_data_starts_after_the_syn_sequence_number():
    assert types(decode(up(999, publish(), flags=SYN))) == [[3]]


def test_directions_are_reassembled_separately():
    p = publish()
    events = decode(up(1000, p[:2]), down(9000, msg(0x20, b"\0\5")), up(1002, p[2:]))
    assert types(events) == [[], [2], [3]] and events[1].mqtt[0].connack_code == 5


def test_tuple_reuse_after_a_new_syn_discards_the_old_partial_message():
    p = publish()
    stats = Counter()
    events = decode(up(999, flags=SYN), up(1000, p[:3]), up(4999, flags=SYN), up(5000, p), stats=stats)
    assert types(events) == [[], [], [], [3]] and stats["partial_messages_discarded"] == 1


def test_fin_keeps_state_so_late_retransmissions_are_still_recognised():
    p = publish()
    stats = Counter()
    events = decode(up(999, flags=SYN), up(1000, p), up(1000 + len(p), flags=FIN | ACK), up(1000, p), stats=stats)
    assert types(events) == [[], [3], [], []] and stats["tcp_retransmitted_segments"] == 1


def test_rst_ends_the_stream_and_discards_its_partial_message():
    p = publish()
    stats = Counter()
    events = decode(up(1000, p[:3]), up(1003, flags=RST), stats=stats)
    assert types(events) == [[], []] and stats["partial_messages_discarded"] == 1 and stats["streams_closed_rst"] == 1


def test_incomplete_stream_at_end_of_capture_is_counted_without_inventing_a_message():
    stats = Counter()
    assert types(decode(up(1000, publish()[:3]), stats=stats)) == [[]]
    assert stats["streams_open_at_end"] == 1 and stats["partial_messages_discarded"] == 1


# Limits

def test_oversized_message_is_skipped_without_parsing_its_payload_as_messages():
    payload = publish(payload=bytes([0xc0, 0]) * 3000)  # the payload looks like PINGREQs
    stats = Counter()
    chunks = [payload[i:i + 1000] for i in range(0, len(payload), 1000)]
    packets = [up(1000 + i * 1000, c) for i, c in enumerate(chunks)] + [up(1000 + len(payload), msg(0xc0))]
    events = decode(*packets, stats=stats, max_stream_bytes=1024)
    assert [t for e in types(events) for t in e] == [12]
    assert stats["oversized_messages_skipped"] == 1 and stats["stream_bytes_peak"] <= 1024


def test_out_of_order_bytes_cannot_exceed_the_stream_limit():
    stats = Counter()
    packets = [up(1000), *(up(2000 + i * 2000, b"\x30" * 500) for i in range(50))]
    decode(*packets, stats=stats, max_stream_bytes=1024)
    assert stats["tcp_sequence_gaps"] >= 1 and stats["stream_bytes_peak"] <= 1024 + 500


def test_out_of_order_segment_count_is_limited_and_a_gap_loses_only_the_partial_message():
    stats = Counter()
    p = msg(0xc0)
    packets = [up(1000, publish()[:3]), *(up(2000 + i * 10, p) for i in range(decoder.MAX_OUT_OF_ORDER_SEGMENTS + 1))]
    decode(*packets, stats=stats)
    assert stats["tcp_sequence_gaps"] >= 1 and stats["partial_messages_discarded"] == 1


def test_stream_count_is_limited_by_evicting_the_least_recently_used():
    stats = Counter()
    decode(*(up(1000, b"\x30", sport=2000 + i) for i in range(50)), stats=stats, max_streams=10)
    assert stats["streams_peak"] <= 11 and stats["streams_evicted_limit"] == 40


def test_total_buffered_bytes_are_limited_across_streams():
    stats = Counter()
    partial = publish(payload=b"x" * 2000)[:1000]
    decode(*(up(1000, partial, sport=2000 + i) for i in range(50)), stats=stats, max_total_bytes=4000)
    assert stats["streams_evicted_bytes"] > 0 and stats["partial_messages_discarded"] > 0


def test_idle_stream_is_evicted_by_capture_time_and_active_ones_are_not():
    stats = Counter()
    p = publish()
    events = decode(up(1000, p, t=0), up(1000, p, sport=6000, t=0), up(1000 + len(p), p, t=3000), up(1000, p, sport=7000, t=3601), stats=stats)
    assert types(events)[-1] == [3] and stats["streams_evicted_idle"] == 1


# MQTT parsing

@pytest.mark.parametrize("header, msg_type, body", [
    (0x10, 1, mstr(b"MQTT") + b"\x04\x02\x00\x3c" + mstr(b"c")), (0x20, 2, b"\0\0"), (0x30, 3, mstr(b"t")),
    (0x40, 4, b"\0\1"), (0x50, 5, b"\0\1"), (0x62, 6, b"\0\1"), (0x70, 7, b"\0\1"), (0x82, 8, b"\0\1" + mstr(b"f") + b"\0"),
    (0x90, 9, b"\0\1\0"), (0xa2, 10, b"\0\1" + mstr(b"f")), (0xb0, 11, b"\0\1"), (0xc0, 12, b""), (0xd0, 13, b""), (0xe0, 14, b""),
])
def test_every_mqtt_3_1_1_type_is_decoded(header, msg_type, body):
    event, = decode(up(1000, msg(header, body)))
    assert event.mqtt[0].msg_type == msg_type and event.mqtt[0].length == len(body) and event.malformed is False


@pytest.mark.parametrize("n", [0, 127, 128, 16383, 16384, 300000])
def test_remaining_length_variable_encoding(n):
    data = bytes([0xd0]) + varint(n) + b"\0" * n
    chunks = [data[i:i + 60000] for i in range(0, len(data), 60000)]
    events = decode(*(up(1000 + i * 60000, c) for i, c in enumerate(chunks)))
    assert events[-1].mqtt[0].length == n and all(not e.mqtt for e in events[:-1])


def test_remaining_length_of_five_bytes_is_invalid_and_flagged():
    stats = Counter()
    event, = decode(up(1000, bytes([0x30, 0xff, 0xff, 0xff, 0xff, 0xff, 1])), stats=stats)
    assert event.mqtt == () and event.malformed and stats["invalid_fixed_header_events"] == 1


@pytest.mark.parametrize("data", [bytes([0x00, 0]), bytes([0xf0, 0]), bytes([0x36, 3]) + mstr(b"t"), bytes([0x80, 0]), b"GET / HTTP/1.1"])
def test_invalid_fixed_headers_follow_d01_and_are_flagged(data):
    stats = Counter()
    event, = decode(up(1000, data), stats=stats)
    assert event.mqtt == () and event.malformed and stats["invalid_fixed_header_events"] == 1


@pytest.mark.parametrize("qos", [0, 1, 2])
@pytest.mark.parametrize("retain", [False, True])
def test_qos_and_retain(qos, retain):
    m = decode(up(1000, publish(qos=qos, retain=retain)))[0].mqtt[0]
    assert (m.qos, m.retain) == (qos, retain)


def test_keepalive_and_connack_codes():
    events = decode(up(1000, connect(300)), down(9000, msg(0x20, b"\0\5")))
    assert events[0].mqtt[0].keepalive == 300 and events[1].mqtt[0].connack_code == 5


@pytest.mark.parametrize("data", [
    msg(0x10, b"\xff\xffMQ"), msg(0x10, b"\0\4MQTT"), msg(0x20, b"\0"), msg(0x30, b"\xff\xffa"), msg(0x32, mstr(b"t")),
    msg(0x82, b"\0\1\xff\xffa"), msg(0x82, b"\0"),
])
def test_structurally_broken_messages_are_kept_without_values_and_flagged(data):
    event, = decode(up(1000, data))
    m = event.mqtt[0]
    assert event.malformed and m.topics == () and m.keepalive is None and m.connack_code is None


def test_unknown_protocol_name_gives_no_keepalive_and_is_not_flagged():
    stats = Counter()
    event, = decode(up(1000, msg(0x10, mstr(b"XXXX") + b"\x04\x02\x00\x3c" + mstr(b"c"))), stats=stats)
    assert event.mqtt[0].keepalive is None and not event.malformed and stats["connect_unknown_protocol"] == 1


def test_mqtt_5_subscribe_is_counted_not_guessed():
    stats = Counter()
    event, = decode(up(1000, msg(0x82, b"\0\1\0" + mstr(b"a/#") + b"\0")), stats=stats)
    assert event.mqtt[0].topics == () and stats["topic_mismatch_messages"] == 1


def test_auth_without_an_mqtt_5_connect_is_invalid():
    assert decode(up(1000, msg(0xf0)))[0].mqtt == ()


CONNECT_5 = msg(0x10, mstr(b"MQTT") + b"\x05\x02\x00\x3c\x00" + mstr(b"c"))


def test_mqtt_5_subscribe_after_a_level_5_connect_is_tokenized_and_not_flagged():
    stats = Counter()
    sub = msg(0x82, b"\0\1\0" + mstr(b"a/#") + b"\0")
    connected, subscribed = decode(up(1000, CONNECT_5), up(1000 + len(CONNECT_5), sub), stats=stats)
    assert connected.mqtt[0].keepalive == 60 and not subscribed.malformed
    assert subscribed.mqtt[0].topics[0].endswith("#") and stats["topic_mismatch_messages"] == 0


def test_mqtt_5_subscribe_properties_are_skipped():
    sub = msg(0x82, b"\0\1\x02\x0b\x01" + mstr(b"a") + b"\0")
    _, subscribed = decode(up(1000, CONNECT_5), up(1000 + len(CONNECT_5), sub))
    assert not subscribed.malformed and len(subscribed.mqtt[0].topics) == 1


def test_mqtt_5_auth_is_a_message_in_both_directions():
    syn_ack = down(8999, flags=SYN | ACK)
    events = decode(syn_ack, up(1000, CONNECT_5), up(1000 + len(CONNECT_5), msg(0xf0, b"\x18\0")), down(9000, msg(0xf0, b"\x18\0")))
    assert [types([e]) for e in events[2:]] == [[[15]], [[15]]] and not any(e.malformed for e in events)


def test_mqtt_5_state_ends_with_the_connection():
    sub = msg(0x82, b"\0\1\0" + mstr(b"a") + b"\0")
    events = decode(up(1000, CONNECT_5), up(5000, flags=SYN), up(5001, sub))
    assert events[2].malformed


def test_invalid_header_does_not_hide_valid_messages_after_it():
    stats = Counter()
    event, = decode(up(1000, msg(0xf0) + publish() + msg(0x36, mstr(b"a")) + publish()), stats=stats)
    assert types([event]) == [[3, 3]] and event.malformed and stats["invalid_fixed_header_events"] == 2


def test_invalid_header_with_an_unfinished_body_discards_only_that_buffer():
    event, after = decode(up(1000, b"\xf0\x7fgarbage"), up(1009, publish()))
    assert event.malformed and types([after]) == [[3]]


def test_unsubscribe_and_empty_publish_topic_give_no_tokens():
    event, = decode(up(1000, unsubscribe(b"a", b"b") + publish(b"")))
    assert [m.topics for m in event.mqtt] == [(), ()]


# Topics

def test_multiple_filters_wildcards_and_f19_f24_through_the_shared_extractor():
    frame = up(1000, subscribe(b"a/+", b"b/#", b"c") + publish(b"c") + publish(b"d/#"))
    f = next(extract_features(decode(frame))).as_dict()
    assert (f["F13"], f["F12"], f["F19"], f["F24"]) == (1, 2, 4, 1)


def test_repeated_topics_share_a_token_and_runs_differ():
    first = decode(up(1000, publish(b"a") + publish(b"a") + publish(b"b")))[0].mqtt
    second = decode(up(1000, publish(b"a")))[0].mqtt
    assert first[0].topics == first[1].topics != first[2].topics and first[0].topics != second[0].topics


def test_token_matches_the_shared_hmac_and_invalid_utf8_stays_distinct(monkeypatch):
    key = bytes(range(32))
    monkeypatch.setattr(decoder.secrets, "token_bytes", lambda n: key)
    event, = decode(up(1000, publish(b"t/a") + msg(0x30, b"\0\2\xff\xfe") + msg(0x30, b"\0\2\xff\xfd")))
    assert event.mqtt[0].topics == (hmac.new(key, b"t/a", hashlib.sha256).hexdigest(),)
    assert event.mqtt[1].topics != event.mqtt[2].topics


# Privacy

def test_sentinels_never_reach_events_rows_stats_logs_or_console(caplog, capsys):
    caplog.set_level(logging.DEBUG)
    stats = Counter()
    data = connect() + publish(b"SENTINEL-TOPIC", payload=b"SENTINEL-PAYLOAD") + subscribe(b"SENTINEL-TOPIC/#") + unsubscribe(b"SENTINEL-TOPIC")
    events = decode(up(1000, data), up(5000, data), up(9000, data[:30]), down(9000, data), stats=stats)
    aggregator = FeatureAggregator()
    rows = [r for e in events for r in aggregator.push(e)] + aggregator.finish()
    captured = capsys.readouterr()
    assert rows and leaks(events, rows, dict(stats), json.dumps([dataclasses.asdict(r) for r in rows]), caplog.text, captured.out, captured.err) == []


def test_invalid_frames_never_put_their_bytes_in_errors_or_stats(tmp_path):
    stats = Counter()
    decode(up(1000, b"SENTINEL-PAYLOAD"), (1, 1, b"SENTINEL-TOPIC"), (1, 1, eth(ipv4(b"SENTINEL-TOPIC"))), stats=stats)
    assert leaks(dict(stats)) == []
    bad = tmp_path / "x.pcap"
    bad.write_bytes(b"SENTINEL-TOPIC")
    with pytest.raises(DecoderError) as caught:
        list(read_records(bad))
    assert "SENT" not in str(caught.value) + repr(caught.value)  # the reader has seen only the first 4 bytes


def test_key_is_not_exposed_in_events_or_stats(monkeypatch):
    monkeypatch.setattr(decoder.secrets, "token_bytes", lambda n: b"K" * 32)
    stats = Counter()
    event, = decode(up(1000, publish(b"SENTINEL-TOPIC")), stats=stats)
    assert "KKKK" not in repr(dict(stats)) + repr(event)


def test_message_has_no_fields_for_sensitive_data():
    assert {f.name for f in dataclasses.fields(MqttMessage)}.isdisjoint({"payload", "client_id", "username", "password"})


# Files and determinism

def test_pcap_and_pcapng_decode_alike_and_incrementally(tmp_path):
    packets = [up(1000, publish(), t=100), up(1000 + len(publish()), publish(), t=101)]
    classic = write_pcap(tmp_path / "a.pcap", packets)
    events = list(decode_pcap(classic))
    assert len(events) == 2 and events[0].ts_ns == 100_000_000_000 + 0 * 1000
    next_ = list(decode_pcap(write_pcapng(tmp_path / "a.pcapng", packets)))
    assert types(next_) == [[3], [3]] and next_[1].ts_ns == 101 * 10 ** 9


def test_reader_is_lazy(tmp_path):
    path = write_pcap(tmp_path / "a.pcap", [up(1000, publish())] * 5)
    records = read_records(path)
    next(records)
    assert records.gi_frame is not None  # still suspended with the file open, not a list read up front
    records.close()


def test_events_before_a_cut_short_file_are_delivered_then_it_raises(tmp_path):
    path = write_pcap(tmp_path / "a.pcap", [up(1000, publish()), up(2000, publish())], cut=3)
    got = []
    with pytest.raises(DecoderError, match="cut short"):
        for event in decode_pcap(path):
            got.append(event)
    assert len(got) == 1


def test_output_is_deterministic_apart_from_the_run_key():
    data = [up(1000 + i * 100, publish(bytes([97 + i % 3]))) for i in range(50)]
    assert [r.features for r in extract_features(decode(*data))] == [r.features for r in extract_features(decode(*data))]


# The reference adapter on the same invented file

@pytest.mark.skipif(not Path(fields.DEFAULT_TSHARK).exists(), reason="tshark is not installed")
def test_events_match_tshark_on_an_invented_capture(tmp_path):
    a, b = publish(b"a/b"), publish(b"c", qos=1, retain=True)
    con = connect(30)
    s = subscribe(b"x/#", b"y")
    packets = [up(999, flags=SYN), down(8999, flags=SYN | ACK), up(1000, con[:5]), up(1005, con[5:]), down(9000, msg(0x20, b"\0\0")),
               up(1000 + len(con), a + s + b[:2]), up(1000 + len(con) + len(a + s) + 2, b[2:]),
               up(1000 + len(con), a + s + b[:2]),  # retransmission
               up(1000 + len(con + a + s + b) + 2, msg(0xc0)), up(1000 + len(con + a + s + b), msg(0xc0)),  # out of order
               up(1000 + len(con + a + s + b) + 4, unsubscribe(b"x/#") + msg(0xe0)), down(9004, flags=FIN | ACK)]
    packets = [(100 * 10 ** 9 + i * 1000, link, frame) for i, (_, link, frame) in enumerate(packets)]
    path = tmp_path / "invented.pcap"
    data = struct.pack("<IHHiIII", 0xa1b2c3d4, 2, 4, 0, 0, 65535, 1)
    for t, _, frame in packets:
        data += struct.pack("<IIII", t // 10 ** 9, t % 10 ** 9 // 1000, len(frame), len(frame)) + frame
    path.write_bytes(data)

    def shape(events):
        seen = {}
        return [(e.ts_ns, e.src, e.dst, e.sport, e.dport, e.tcp_len, e.syn, e.ack, e.fin, e.rst,
                 [(m.msg_type, m.length, m.qos, m.retain, m.keepalive, m.connack_code,
                   [seen.setdefault(t, len(seen)) for t in m.topics], [t.endswith("#") for t in m.topics]) for m in e.mqtt]) for e in events]
    assert shape(decode_pcap(path)) == shape(read_pcap(path, tshark=fields.DEFAULT_TSHARK))


def test_random_and_mutated_frames_never_crash_the_decoder():
    """Fuzz: garbage link frames, and valid frames with random byte flips, must be counted, not raised."""
    import random
    rng = random.Random(7)
    good = [up(1000 + i * 40, publish(b"t/%d" % i), t=100 + i) for i in range(50)]
    records = []
    for i in range(3000):
        t = 200 * 10 ** 9 + i * 1000
        if i % 3 == 0:
            records.append((t, 1, bytes(rng.randrange(256) for _ in range(rng.randrange(0, 120)))))
        else:
            frame = bytearray(rng.choice(good)[2])
            for _ in range(rng.randrange(1, 6)):
                frame[rng.randrange(len(frame))] = rng.randrange(256)
            records.append((t, 1, bytes(frame[:rng.randrange(1, len(frame) + 1)])))
    stats = Counter()
    events = list(decode_packets(good + records, stats))
    assert len(events) >= len(good)
    rows = list(extract_features(events))
    assert rows  # the extractor accepts whatever the decoder emits
