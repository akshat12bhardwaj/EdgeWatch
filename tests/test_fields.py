"""TShark adapter tests. Fixtures copy the -T ek shape seen from tshark 4.6.9 (T3); no capture files are read."""
import dataclasses
import hashlib
import hmac
import json
import logging
import shutil
import struct
import subprocess
import sys
import textwrap
import time
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ids import (FeatureAggregator, MqttMessage, PacketEvent, TSharkError, TSharkOutputError, extract_features,  # noqa: E402
                 parse_ek_lines, read_pcap)
from ids import fields  # noqa: E402

CLIENT, BROKER = "192.0.2.1", "192.0.2.9"
SENTINELS = ("SENTINEL-USER", "SENTINEL-PASS", "SENTINEL-CLIENT", "SENTINEL-TOPIC", "SENTINEL-PAYLOAD", "SENTINEL-TEXT")


def layers(t="100.000000000", up=True, **extra):
    src, dst, sport, dport = (CLIENT, BROKER, "5000", "1883") if up else (BROKER, CLIENT, "1883", "5000")
    base = {"frame_time_epoch": [t], "ip_src": [src], "ip_dst": [dst], "tcp_srcport": [sport], "tcp_dstport": [dport],
            "tcp_len": ["0"], "tcp_flags_syn": ["False"], "tcp_flags_ack": ["True"], "tcp_flags_fin": ["False"],
            "tcp_flags_reset": ["False"]}
    return {**base, **extra}


def ek(*frames):
    lines = []
    for frame in frames:
        lines.append(b'{"index":{"_index":"packets-2020-06-22","_type":"doc"}}\r\n')
        lines.append(json.dumps({"timestamp": "100000", "layers": frame}).encode() + b"\r\n")
    return lines


def parse(*frames, stats=None):
    return list(parse_ek_lines(ek(*frames), stats))


def leaks(*objects):
    """Sentinels found in anything printable. Returns only the sentinels, so a failure cannot print other content."""
    items = [i for o in objects for i in (o if isinstance(o, list) else [o])]
    text = "".join(repr(i) + (repr(dataclasses.asdict(i)) if dataclasses.is_dataclass(i) else "") for i in items)
    return [s for s in SENTINELS if s in text]


def publish(*names, up=True, t="100.0"):
    """A frame with one QoS 0 PUBLISH per topic."""
    sizes = [str(len(n.encode())) for n in names]
    return layers(t, up=up, mqtt_hdrflags=["0x30"] * len(names), mqtt_len=[str(int(n) + 3) for n in sizes],
                  mqtt_topic=list(names), mqtt_topic_len=sizes)


def subscribe(*filters, t="100.0"):
    """A frame with one SUBSCRIBE holding all these filters."""
    sizes = [len(n.encode()) for n in filters]
    return layers(t, mqtt_hdrflags=["0x82"], mqtt_len=[str(2 + sum(3 + n for n in sizes))],
                  mqtt_topic=list(filters), mqtt_topic_len=[str(n) for n in sizes])


def features_of(*frames):
    row, = extract_features(parse(*frames))
    return row.as_dict()


def test_one_packet_with_one_message():
    event, = parse(layers(tcp_len=["14"], mqtt_hdrflags=["0x10"], mqtt_len=["12"], mqtt_kalive=["60"]))
    assert event == PacketEvent(100_000_000_000, CLIENT, BROKER, 5000, 1883, tcp_len=14, ack=True,
                                mqtt=(MqttMessage(1, 12, keepalive=60),))


@pytest.mark.parametrize("text, expected", [
    ("1592812177.370831000", 1592812177370831000),
    ("1592812177.999999999", 1592812177999999999),  # a float would round this up
    ("100", 100_000_000_000),
    ("100.5", 100_500_000_000),
])
def test_timestamps_become_exact_integer_nanoseconds(text, expected):
    assert parse(layers(t=text))[0].ts_ns == expected


def test_all_flags_are_read_and_ipv6_is_accepted():
    frame = layers(tcp_flags_syn=["True"], tcp_flags_ack=["False"], tcp_flags_fin=["True"], tcp_flags_reset=["True"])
    event, = parse(frame)
    assert (event.syn, event.ack, event.fin, event.rst) == (True, False, True, True)
    del frame["ip_src"], frame["ip_dst"]
    event, = parse({**frame, "ipv6_src": ["2001:db8::1"], "ipv6_dst": ["2001:db8::9"]})
    assert (event.src, event.dst) == ("2001:db8::1", "2001:db8::9")


def test_multiple_messages_keep_their_position_and_values():
    event, = parse(layers(
        mqtt_hdrflags=["0x30", "0x10", "0x3b", "0x82", "0x34", "0xc0"], mqtt_len=["7", "12", "9", "5", "6", "0"],
        mqtt_kalive=["300"]))
    assert event.mqtt == (
        MqttMessage(3, 7),
        MqttMessage(1, 12, keepalive=300),
        MqttMessage(3, 9, qos=1, retain=True),  # 0x3b: DUP set, QoS 1, retain set
        MqttMessage(8, 5),                      # SUBSCRIBE's fixed bits are not QoS
        MqttMessage(3, 6, qos=2),
        MqttMessage(12, 0),
    )


def test_each_connect_and_connack_gets_its_own_value():
    up, down = parse(layers(mqtt_hdrflags=["0x10", "0x10"], mqtt_len=["12", "12"], mqtt_kalive=["1", "2"]),
                     layers(up=False, mqtt_hdrflags=["0x20", "0x20"], mqtt_len=["2", "2"], mqtt_conack_val=["5", "0"]))
    assert [m.keepalive for m in up.mqtt] == [1, 2]
    assert [m.connack_code for m in down.mqtt] == [5, 0]


def test_flood_sized_frame_keeps_every_message():
    event, = parse(layers(mqtt_hdrflags=["0x30"] * 2048, mqtt_len=["15"] * 2048))
    assert len(event.mqtt) == 2048


def test_tcp_without_mqtt_is_kept():
    event, = parse(layers(tcp_flags_syn=["True"], tcp_flags_ack=["False"]))
    assert event.syn and event.mqtt == ()


def test_broker_replies_stay_from_broker_and_reach_only_the_reply_features():
    down = layers("100.1", up=False, tcp_len=["4"], mqtt_hdrflags=["0x20"], mqtt_len=["2"], mqtt_conack_val=["5"])
    events = parse(layers(mqtt_hdrflags=["0x10"], mqtt_len=["12"], mqtt_kalive=["60"]), down)
    assert (events[1].src, events[1].sport, events[1].dst, events[1].dport) == (BROKER, 1883, CLIENT, 5000)
    row, = extract_features(events)
    assert row.source_key == CLIENT
    f = row.as_dict()
    assert (f["F01"], f["F02"], f["F09"], f["F10"], f["F25"]) == (1, 0, 1, 1, 1)


def test_message_split_across_segments_counts_only_in_the_completing_frame():
    # tshark reports nothing on the first segment and the whole message on the one that finishes it.
    first = layers("104.9", tcp_len=["2"])
    second = layers("105.1", tcp_len=["30"], mqtt_hdrflags=["0x10"], mqtt_len=["30"], mqtt_kalive=["10"])
    a, b = extract_features(parse(first, second))
    assert (a.as_dict()["F09"], a.as_dict()["F02"]) == (0, 2)
    assert (b.as_dict()["F09"], b.as_dict()["F18"]) == (1, 30)


def test_missing_optional_tcp_fields_use_defaults_and_are_counted():
    frame = layers()
    del frame["tcp_len"], frame["tcp_flags_ack"]
    stats = Counter()
    event, = parse(frame, stats=stats)
    assert (event.tcp_len, event.ack) == (0, False)
    assert stats["missing_tcp_field_frames"] == 2


def test_non_tcp_frames_are_skipped_and_counted():
    stats = Counter()
    assert parse({"frame_time_epoch": ["1.0"], "ip_src": [CLIENT], "ip_dst": [BROKER]}, stats=stats) == []
    assert (stats["frames"], stats["non_tcp_frames"], stats["events"]) == (1, 1, 0)


@pytest.mark.parametrize("change", [
    {"frame_time_epoch": ["not-a-time"]},
    {"frame_time_epoch": ["-1.5"]},
    {"frame_time_epoch": ["1.0", "2.0"]},
    {"frame_time_epoch": []},
    {"tcp_srcport": ["70000"]},
    {"tcp_dstport": ["abc"]},
    {"tcp_dstport": 1883},
    {"tcp_len": ["-1"]},
    {"tcp_flags_syn": ["maybe"]},
    {"ip_src": []},
    {"ip_src": [CLIENT, BROKER]},  # an ICMP error quoting a TCP packet: direction would be a guess
])
def test_malformed_packet_metadata_drops_only_that_frame(change):
    stats = Counter()
    events = parse(layers(**change), layers(), stats=stats)
    assert len(events) == 1 and stats["bad_metadata_frames"] == 1


def test_non_object_layers_are_counted():
    stats = Counter()
    assert list(parse_ek_lines([b'{"layers":[1]}\n'], stats)) == [] and stats["bad_metadata_frames"] == 1


@pytest.mark.parametrize("change", [
    {"mqtt_hdrflags": ["0x30", "0x30"], "mqtt_len": ["1"]},
    {"mqtt_len": ["1"]},
    {"mqtt_hdrflags": ["junk"], "mqtt_len": ["1"]},
    {"mqtt_hdrflags": ["0x130"], "mqtt_len": ["1"]},
    {"mqtt_hdrflags": ["0x30"], "mqtt_len": ["-1"]},
])
def test_message_count_mismatch_keeps_the_packet_but_never_guesses_messages(change):
    stats = Counter()
    event, = parse(layers(tcp_len=["9"], **change), stats=stats)
    assert event.tcp_len == 9 and event.mqtt == () and stats["mqtt_mismatch_frames"] == 1


@pytest.mark.parametrize("values", [[], ["1", "2", "3"], ["junk", "2"]])
def test_keepalive_mismatch_keeps_messages_without_assigning_values(values):
    stats = Counter()
    event, = parse(layers(mqtt_hdrflags=["0x10", "0x10"], mqtt_len=["1", "1"], mqtt_kalive=values), stats=stats)
    assert [m.keepalive for m in event.mqtt] == [None, None] and stats["mqtt_kalive_mismatch_frames"] == 1


def test_connack_mismatch_keeps_messages_without_assigning_values():
    stats = Counter()
    event, = parse(layers(up=False, mqtt_hdrflags=["0x20"], mqtt_len=["1"]), stats=stats)
    assert event.mqtt[0].connack_code is None and stats["mqtt_conack_val_mismatch_frames"] == 1


def test_qos_and_retain_come_from_hdrflags_not_from_separate_lists():
    event, = parse(layers(mqtt_hdrflags=["0x30", "0x33"], mqtt_len=["1", "1"], mqtt_qos=["2", "0"], mqtt_retain=["True", "False"]))
    assert [(m.qos, m.retain) for m in event.mqtt] == [(0, False), (1, True)]


def test_qos_3_and_reserved_types_pass_through_and_are_counted():
    stats = Counter()
    event, = parse(layers(mqtt_hdrflags=["0x36", "0x00", "0xf0"], mqtt_len=["5", "2", "2"]), stats=stats)
    assert [m.qos for m in event.mqtt] == [3, 0, 0] and stats["reserved_messages"] == 2
    f = next(extract_features([event])).as_dict()
    assert (f["F12"], f["F20"], f["F25"]) == (1, 1.0, 3)  # no typed count for reserved messages


def test_malformed_flag_comes_only_from_the_validated_field():
    stats = Counter()
    bad, expert_only, clean = parse(layers(_ws_malformed_expert=["1"]), layers(_ws_expert_group=["33554432"]), layers(), stats=stats)
    assert (bad.malformed, expert_only.malformed, clean.malformed) == (True, False, False)
    assert stats["malformed_frames"] == 1


def test_invalid_json_raises_without_quoting_the_line():
    with pytest.raises(TSharkOutputError) as caught:
        list(parse_ek_lines([b'{"layers": SENTINEL-TOPIC\n']))
    assert "line 1" in str(caught.value) and "SENTINEL" not in str(caught.value)
    assert caught.value.__cause__ is None and caught.value.__suppress_context__


def test_invalid_utf8_and_non_object_json_raise():
    for line in (b'\xff\xfe\n', b'[1]\n'):
        with pytest.raises(TSharkOutputError):
            list(parse_ek_lines([line]))


@pytest.mark.parametrize("cut", [
    lambda lines: lines[:-1],                         # ends after an index line
    lambda lines: lines[:-1] + [lines[-1][:20]],      # ends inside a document
    lambda lines: lines[:-1] + [lines[-1].rstrip()],  # complete JSON, no line end
])
def test_truncated_stream_is_an_error_after_earlier_frames_are_delivered(cut):
    got = []
    with pytest.raises(TSharkOutputError, match="cut short|invalid"):
        for event in parse_ek_lines(cut(ek(layers(), layers()))):
            got.append(event)
    assert len(got) == 1


def test_nothing_sensitive_can_leave_the_adapter():
    assert not {"mqtt.username", "mqtt.passwd", "mqtt.clientid", "mqtt.msg", "mqtt.msg_text", "mqtt.willtopic"} & set(fields.FIELDS)
    command = " ".join(fields._command("x.pcap", "tshark"))
    assert "passwd" not in command and "clientid" not in command and "username" not in command and "mqtt.msg" not in command
    hostile = layers(mqtt_hdrflags=["0x10", "0x30"], mqtt_len=["1", "16"], mqtt_kalive=["1"], mqtt_username=[SENTINELS[0]],
                     mqtt_passwd=[SENTINELS[1]], mqtt_clientid=[SENTINELS[2]], mqtt_topic=[SENTINELS[3]], mqtt_topic_len=["14"],
                     mqtt_msg=[SENTINELS[4]], mqtt_msg_text=[SENTINELS[5]])
    stats = Counter()
    event, = parse(hostile, stats=stats)
    assert len(event.mqtt[1].topics) == 1  # the topic was used, as a token
    assert leaks(event, stats, list(extract_features([event]))) == []


# T3.1: topics. All names here are invented; no capture is read.

def test_repeated_topic_has_one_token_and_different_topics_differ_within_a_run():
    same_a, same_b, other = parse(publish("t/a"), publish("t/a", t="100.1"), publish("t/b", t="100.2"))
    assert same_a.mqtt[0].topics == same_b.mqtt[0].topics != other.mqtt[0].topics
    assert len(same_a.mqtt[0].topics[0]) == 64


def test_runs_use_different_keys_but_give_equal_features():
    frames = (publish("t/a", "t/b"), subscribe("t/a", "s/#", t="100.5"))
    first, second = parse(*frames), parse(*frames)
    assert first[0].mqtt[0].topics != second[0].mqtt[0].topics
    assert [r.features for r in extract_features(first)] == [r.features for r in extract_features(second)]


def test_token_is_keyed_hmac_sha256_from_a_secure_random_32_byte_key(monkeypatch):
    key = bytes(range(32))
    calls = []
    monkeypatch.setattr(fields.secrets, "token_bytes", lambda n: calls.append(n) or key)
    event, = parse(publish("t/a"))
    assert calls == [32]
    assert event.mqtt[0].topics == (hmac.new(key, b"t/a", hashlib.sha256).hexdigest(),)
    assert event.mqtt[0].topics != (hashlib.sha256(b"t/a").hexdigest(),)


def test_key_is_not_exposed_in_events_stats_or_errors(monkeypatch):
    key = b"K" * 32
    monkeypatch.setattr(fields.secrets, "token_bytes", lambda n: key)
    stats = Counter()
    event, = parse(publish("t/a"), stats=stats)
    with pytest.raises(TSharkOutputError) as caught:
        list(parse_ek_lines(ek(publish("t/a")) + [b"not json\n"], stats))
    text = repr(event) + repr(dataclasses.asdict(event)) + repr(stats) + str(caught.value)
    assert ("KKKK" in text, key.hex() in text) == (False, False)


@pytest.mark.parametrize("name, wildcard", [
    ("a/+/c", True), ("+", True), ("a/#", True), ("#", True),
    ("a/b/c", False), ("", False),
    ("a+b", True), ("a#b", True),  # invalid MQTT filters, but fx-0.1 says "contains", and F24 keeps that
])
def test_wildcard_detection_on_subscribe_filters(name, wildcard):
    assert features_of(subscribe(name))["F24"] == int(wildcard)


def test_wildcard_flag_holds_nothing_about_which_wildcard_and_keeps_a_token():
    plus, hash_, plain = parse(subscribe("a/+"), subscribe("a/#", t="100.1"), subscribe("a/b", t="100.2"))
    assert plus.mqtt[0].topics[0].endswith("#") and hash_.mqtt[0].topics[0].endswith("#")
    assert len(plus.mqtt[0].topics[0]) == 65 and "+" not in plus.mqtt[0].topics[0]
    assert len(plain.mqtt[0].topics[0]) == 64


def test_wildcard_text_in_a_publish_topic_does_not_count_for_f24():
    f = features_of(publish("a/#", "b/+"))
    assert (f["F12"], f["F19"], f["F24"]) == (2, 2, 0)


def test_same_string_published_and_subscribed_counts_once_in_f19():
    f = features_of(publish("a/b", "a/#"), subscribe("a/b", "a/#", t="100.1"))
    assert (f["F19"], f["F24"]) == (2, 1)


def test_multiple_filters_in_one_subscribe_count_once_for_f24_and_each_for_f19():
    event, = parse(subscribe("a/+", "b/#", "c/d"))
    assert len(event.mqtt) == 1 and len(event.mqtt[0].topics) == 3
    f = next(extract_features([event])).as_dict()
    assert (f["F13"], f["F19"], f["F24"]) == (1, 3, 1)


def test_multiple_messages_in_one_frame_get_their_own_topics_without_double_counting():
    # 3.1.1 layout: PUBLISH a, SUBSCRIBE b/# + c, PUBLISH QoS 1 d, UNSUBSCRIBE e, SUBSCRIBE f, PINGREQ
    frame = layers(mqtt_hdrflags=["0x30", "0x82", "0x32", "0xa2", "0x82", "0xc0"], mqtt_len=["4", "12", "6", "5", "6", "0"],
                   mqtt_topic=["a", "b/#", "c", "d", "e", "f"], mqtt_topic_len=["1", "3", "1", "1", "1", "1"])
    stats = Counter()
    event, = parse(frame, stats=stats)
    assert [len(m.topics) for m in event.mqtt] == [1, 2, 1, 0, 1, 0]
    assert stats["topic_mismatch_frames"] == 0
    f = next(extract_features([event])).as_dict()
    assert (f["F19"], f["F24"], f["F25"]) == (5, 1, 6)  # e is not a PUBLISH or SUBSCRIBE; a wildcard SUBSCRIBE counts once


def test_flood_frame_with_repeated_topic_keeps_every_message_and_one_distinct_topic():
    f = features_of(publish(*["t"] * 2048))
    assert (f["F12"], f["F19"]) == (2048, 1)


def test_direction_and_window_boundaries_are_preserved():
    down = publish("from/broker", up=False, t="100.1")
    assert features_of(publish("t/a"), down)["F19"] == 1  # the broker's delivery is not the source's topic
    a, b = extract_features(parse(publish("t/a", t="104.9"), publish("t/a", t="105.1")))
    assert (a.as_dict()["F19"], b.as_dict()["F19"]) == (1, 1)  # the set does not persist across windows


def test_zero_length_topic_has_a_length_but_no_text_and_gives_no_token():
    # Seen from tshark 4.6.9: mqtt_topic_len is ["0"] and mqtt_topic is absent.
    empty = layers(mqtt_hdrflags=["0x30", "0x30"], mqtt_len=["3", "4"], mqtt_topic=["a"], mqtt_topic_len=["0", "1"])
    stats = Counter()
    event, = parse(empty, stats=stats)
    assert [len(m.topics) for m in event.mqtt] == [0, 1] and stats["topic_mismatch_frames"] == 0


def test_topic_length_is_used_to_walk_and_is_not_retained():
    assert {f.name for f in dataclasses.fields(MqttMessage)} == {"msg_type", "length", "qos", "retain", "keepalive",
                                                                 "connack_code", "topics"}
    wide = "é/" * 3  # topic_len counts bytes, not characters
    assert len(parse(subscribe(wide))[0].mqtt[0].topics) == 1


@pytest.mark.parametrize("change", [
    {"mqtt_topic": []},                                  # text missing
    {"mqtt_topic_len": []},                              # length missing
    {"mqtt_topic": ["SENTINEL-TOPIC", "x"]},             # too many
    {"mqtt_topic_len": ["14", "1"]},                     # too many
    {"mqtt_topic_len": ["junk"]},
    {"mqtt_topic_len": ["-14"]},
    {"mqtt_topic_len": [None]},
    {"mqtt_topic_len": [float("inf")]},
    {"mqtt_topic_len": ["99999"]},                       # longer than the message
    {"mqtt_topic": "SENTINEL-TOPIC"},                    # not a list
    {"mqtt_topic": [14]},                                # not text
    {"mqtt_topic": [{"x": "SENTINEL-TOPIC"}]},
    {"mqtt_topic_len": "14"},
    {"mqtt_topic": "S"},                                 # a one-character string would iterate like a one-item list
    {"mqtt_topic_len": "7"},
])
def test_malformed_topic_metadata_keeps_the_message_without_tokens_or_leaks(change):
    frame = {**publish("SENTINEL-TOPIC"), **change}
    stats = Counter()
    event, = parse(frame, stats=stats)
    assert event.mqtt[0].msg_type == 3 and event.mqtt[0].topics == () and stats["topic_mismatch_frames"] == 1
    assert leaks(event, stats) == []


def test_publish_without_any_topic_fields_gives_zero_not_a_guess():
    stats = Counter()
    event, = parse(layers(mqtt_hdrflags=["0x30"], mqtt_len=["5"]), stats=stats)
    assert next(extract_features([event])).as_dict()["F19"] == 0 and stats["topic_mismatch_frames"] == 1


@pytest.mark.parametrize("length", ["3", "6", "9", "11"])
def test_subscribe_walk_that_does_not_end_exactly_drops_the_frames_topics(length):
    frame = layers(mqtt_hdrflags=["0x30", "0x82"], mqtt_len=["4", length], mqtt_topic=["a", "b", "c"],
                   mqtt_topic_len=["1", "1", "1"])
    stats = Counter()
    event, = parse(frame, stats=stats)
    assert all(m.topics == () for m in event.mqtt) and stats["topic_mismatch_frames"] == 1


def test_frames_without_topic_messages_are_not_counted_as_mismatches_but_stray_topics_are():
    stats = Counter()
    parse(layers(mqtt_hdrflags=["0x10"], mqtt_len=["1"], mqtt_kalive=["1"]), stats=stats)
    assert stats["topic_mismatch_frames"] == 0
    event, = parse(layers(mqtt_hdrflags=["0xc0"], mqtt_len=["0"], mqtt_topic=["SENTINEL-TOPIC"], mqtt_topic_len=["14"]), stats=stats)
    assert stats["topic_mismatch_frames"] == 1 and leaks(event, stats) == []


def test_lone_surrogate_cannot_raise_an_error_holding_the_topic():
    # json.dumps writes \ud800 and json.loads returns a lone surrogate, which a strict encode would reject
    stats = Counter()
    frame = layers(mqtt_hdrflags=["0x30"], mqtt_len=["20"], mqtt_topic=["SENTINEL-TOPIC\ud800"], mqtt_topic_len=["17"])
    event, = parse(frame, stats=stats)
    assert len(event.mqtt[0].topics) == 1 and leaks(event, stats) == []


def test_sentinel_topics_do_not_reach_events_rows_stats_logs_or_console(caplog, capsys):
    caplog.set_level(logging.DEBUG)
    stats = Counter()
    events = parse(publish("SENTINEL-TOPIC", "SENTINEL-TOPIC/2"), subscribe("SENTINEL-TOPIC/#", t="100.1"),
                   publish("SENTINEL-TOPIC", up=False, t="100.2"), stats=stats)
    aggregator = FeatureAggregator()
    rows = [r for e in events for r in aggregator.push(e)] + aggregator.finish()
    records = json.dumps([dataclasses.asdict(r) for r in rows])
    captured = capsys.readouterr()
    assert rows and leaks(events, rows, stats, dict(aggregator.stats), records, caplog.text, captured.out, captured.err) == []
    assert all(isinstance(v, (int, float)) for r in rows for v in r.features)


def test_generator_holds_no_raw_topic_while_the_consumer_has_the_event():
    events = parse_ek_lines(iter(ek(publish("SENTINEL-TOPIC"))))
    next(events)
    assert leaks(list(events.gi_frame.f_locals.values())) == []


def test_invalid_json_exception_keeps_no_reference_to_the_line():
    with pytest.raises(TSharkOutputError) as caught:
        list(parse_ek_lines([b'{"layers":{"mqtt_topic":["SENTINEL-TOPIC"]\n']))
    assert leaks(str(caught.value), repr(caught.value)) == []
    assert caught.value.__cause__ is None and caught.value.__context__ is None


def test_process_failure_after_topics_never_quotes_them_and_writes_no_files(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    fake_tshark(monkeypatch, f"""
        import sys
        sys.stdout.buffer.write({b"".join(ek(publish("SENTINEL-TOPIC")))!r} + b'{{"layers": SENTINEL-TOPIC\\n')
        sys.stdout.buffer.flush()
    """)
    stats = Counter()
    got = []
    with pytest.raises(TSharkOutputError) as caught:
        for event in read_pcap("x", stats=stats):
            got.append(event)
    assert len(got) == 1 and leaks(got, stats, str(caught.value)) == []
    assert list(tmp_path.iterdir()) == []


TSHARK = shutil.which("tshark") or (fields.DEFAULT_TSHARK if Path(fields.DEFAULT_TSHARK).exists() else None)


def mqtt_string(text):
    return struct.pack(">H", len(text)) + text


def mqtt_message(header, body):
    assert len(body) < 128
    return bytes([header, len(body)]) + body


def write_pcap(path, payloads):
    """One TCP frame per payload, from a new client port each, so that tshark decodes each on its own."""
    with open(path, "wb") as out:
        out.write(struct.pack("<IHHiIII", 0xa1b2c3d4, 2, 4, 0, 0, 65535, 1))
        for i, payload in enumerate(payloads):
            tcp = struct.pack(">HHIIBBHHH", 5000 + i, 1883, 1000, 1, 0x50, 0x18, 8192, 0, 0)
            ip = struct.pack(">BBHHHBBH4s4s", 0x45, 0, 40 + len(payload), i + 1, 0, 64, 6, 0, bytes([192, 0, 2, 1]), bytes([192, 0, 2, 9]))
            frame = b"\x02" * 6 + b"\x04" * 6 + b"\x08\x00" + ip + tcp + payload
            out.write(struct.pack("<IIII", 100, i, len(frame), len(frame)) + frame)


@pytest.mark.skipif(TSHARK is None, reason="tshark is not installed")
def test_real_tshark_alignment_on_an_invented_capture(tmp_path):
    secret = b"SENTINEL-TOPIC"
    publish_one = mqtt_message(0x30, mqtt_string(secret) + b"x")
    subscribe_two = mqtt_message(0x82, b"\x00\x01" + mqtt_string(secret + b"/+") + b"\x00" + mqtt_string(b"plain") + b"\x01")
    publish_qos1 = mqtt_message(0x32, mqtt_string(b"second") + b"\x00\x01x")
    unsubscribe = mqtt_message(0xa2, b"\x00\x02" + mqtt_string(b"gone/#") + mqtt_string(b"gone/x"))
    will = mqtt_message(0x10, mqtt_string(b"MQTT") + b"\x04\x06\x00\x3c" + mqtt_string(b"cid") + mqtt_string(secret + b"/will") + mqtt_string(b"bye"))
    empty = mqtt_message(0x30, mqtt_string(b"") + b"x")
    pcap = tmp_path / "invented.pcap"
    write_pcap(pcap, [publish_one + subscribe_two + publish_qos1 + unsubscribe + publish_one, will, empty])
    stats = Counter()
    events = list(read_pcap(pcap, tshark=TSHARK, stats=stats))
    assert [[len(m.topics) for m in e.mqtt] for e in events] == [[1, 2, 1, 0, 1], [0], [0]]
    assert events[0].mqtt[0].topics == events[0].mqtt[4].topics
    assert stats["topic_mismatch_frames"] == 0
    f = next(extract_features(events)).as_dict()
    assert (f["F12"], f["F13"], f["F19"], f["F24"]) == (4, 1, 4, 1)
    assert leaks(events, stats, list(extract_features(events))) == []


def test_output_is_deterministic_and_fields_are_in_a_fixed_order():
    frames = [layers(str(100 + i), mqtt_hdrflags=["0x30"], mqtt_len=[str(i)]) for i in range(20)]
    assert parse(*frames) == parse(*frames)
    assert fields._command("x.pcap", "t") == fields._command("x.pcap", "t")


def test_command_uses_exactly_the_validated_settings():
    command = fields._command("x.pcap", "t")
    assert command[:5] == ["t", "-n", "-T", "ek", "-l"] and command[-2:] == ["-r", "x.pcap"]
    assert [command[i + 1] for i, a in enumerate(command) if a == "-o"] == [
        "tcp.desegment_tcp_streams:TRUE", "tcp.analyze_sequence_numbers:TRUE", "tcp.reassemble_out_of_order:TRUE"]
    assert "-2" not in command and "-M" not in command


def test_tshark_path_prefers_argument_then_environment(monkeypatch):
    monkeypatch.setenv("TSHARK_PATH", "from-env")
    assert fields._command("x", "from-arg")[0] == "from-arg"
    assert fields._command("x")[0] == "from-env"


# Process tests run a real child process standing in for tshark.

def fake_tshark(monkeypatch, body):
    script = textwrap.dedent(body)
    monkeypatch.setattr(fields, "_command", lambda pcap, tshark=None: [sys.executable, "-c", script])


PRINT_TWO_FRAMES = f"""
    import sys
    sys.stdout.buffer.write({b"".join(ek(layers(), layers()))!r})
    sys.stdout.buffer.flush()
"""


def test_successful_process_yields_events_and_exits_cleanly(monkeypatch):
    fake_tshark(monkeypatch, PRINT_TWO_FRAMES)
    stats = Counter()
    assert len(list(read_pcap("x", stats=stats))) == 2 and stats["events"] == 2


def test_missing_executable_is_a_clear_error():
    with pytest.raises(TSharkError, match="cannot start tshark"):
        list(read_pcap("x", tshark=str(Path(__file__).parent / "no-such-tshark.exe")))


def test_non_zero_exit_reports_code_and_stderr(monkeypatch):
    fake_tshark(monkeypatch, """
        import sys
        sys.stderr.write("tshark: The file does not exist.\\n")
        sys.exit(2)
    """)
    with pytest.raises(TSharkError, match=r"code 2.*does not exist"):
        list(read_pcap("x"))


def test_failure_after_output_delivers_events_then_raises(monkeypatch):
    fake_tshark(monkeypatch, PRINT_TWO_FRAMES + "\n    sys.exit(3)\n")
    got = []
    with pytest.raises(TSharkError, match="code 3"):
        for event in read_pcap("x"):
            got.append(event)
    assert len(got) == 2


def test_early_process_death_mid_line_reports_the_exit_not_the_parse(monkeypatch):
    fake_tshark(monkeypatch, """
        import os, sys
        sys.stdout.buffer.write(b'{"index":{}}\\n{"layers":{"frame')
        sys.stdout.buffer.flush()
        os._exit(9)
    """)
    with pytest.raises(TSharkError, match="code 9") as caught:
        list(read_pcap("x"))
    assert not isinstance(caught.value, TSharkOutputError)


def test_clean_exit_with_cut_short_output_is_still_an_error(monkeypatch):
    fake_tshark(monkeypatch, r"""
        import sys
        sys.stdout.buffer.write(b'{"index":{}}\n')
    """)
    with pytest.raises(TSharkOutputError, match="cut short"):
        list(read_pcap("x"))


def test_invalid_json_stops_a_process_that_keeps_running(monkeypatch):
    fake_tshark(monkeypatch, r"""
        import sys, time
        sys.stdout.buffer.write(b'not json\n')
        sys.stdout.buffer.flush()
        time.sleep(60)
    """)
    started = time.monotonic()
    with pytest.raises(TSharkOutputError, match="invalid"):
        list(read_pcap("x"))
    assert time.monotonic() - started < 30


def test_closing_the_generator_stops_tshark_without_raising(monkeypatch):
    processes = []
    real_popen = subprocess.Popen

    def recording_popen(*args, **kwargs):
        processes.append(real_popen(*args, **kwargs))
        return processes[-1]

    monkeypatch.setattr(subprocess, "Popen", recording_popen)
    fake_tshark(monkeypatch, PRINT_TWO_FRAMES + "\n    import time; time.sleep(60)\n")
    events = read_pcap("x")
    next(events)
    assert processes[0].poll() is None
    events.close()
    assert processes[0].poll() is not None and processes[0].stdout.closed and processes[0].stderr.closed


def test_a_full_stderr_pipe_cannot_block_tshark(monkeypatch):
    fake_tshark(monkeypatch, PRINT_TWO_FRAMES + """
    for _ in range(50000):
        sys.stderr.write("warning line that fills the pipe\\n")
    """)
    assert len(list(read_pcap("x"))) == 2
