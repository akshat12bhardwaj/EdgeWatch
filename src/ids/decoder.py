"""Bounded byte-level capture decoder: an evaluation alternative to fields.py (T3.3), yielding the same PacketEvent.

Record reading, network parsing, and stream reassembly come from the D-01 parser (d01_stream.py, d01_inspect.py), with
limits added. Standard library only. MQTT 3.1.1, plus the MQTT 5 framing features need. Nothing here keeps or reports payloads, credentials, or client IDs.
"""
import ipaddress
import secrets
import struct
from collections import Counter
from typing import Iterable, Iterator, Optional

from .features import CONNACK, CONNECT, PUBLISH, SUBSCRIBE, MqttMessage, PacketEvent
from .fields import _token

MAX_STREAMS = 65_536  # least recently used goes first; each direction of a connection is one stream
MAX_STREAM_BYTES = 1 << 20  # per direction: partial message plus out-of-order data
MAX_TOTAL_BYTES = 64 << 20  # across all streams, so the worst case is not MAX_STREAMS x MAX_STREAM_BYTES
MAX_OUT_OF_ORDER_SEGMENTS = 256  # from D-01
IDLE_NS = 3600 * 10 ** 9  # from D-01
FILTER_OVERHEAD = 3  # SUBSCRIBE: 2-byte length plus QoS byte per filter
MAX_FRAGMENTED_DATAGRAMS = 1024  # oldest goes first; a datagram holds at most 64 KiB, so this caps fragment memory
FRAGMENT_TIMEOUT_NS = 60 * 10 ** 9  # RFC 8200 section 4.5
_IPV6_SKIPPED = {0, 43, 60}  # hop-by-hop, routing, destination options: (length + 1) x 8 bytes
AUTH = 15

# From D-01: the flags MQTT 3.1.1 requires, by type. Absent types (0, 15) and PUBLISH QoS 3 are invalid here, unlike tshark.
REQUIRED_FLAGS = {1: 0, 2: 0, 4: 0, 5: 0, 6: 2, 7: 0, 8: 2, 9: 0, 10: 2, 11: 0, 12: 0, 13: 0, 14: 0}
_PCAP_MAGIC = {b"\xd4\xc3\xb2\xa1": ("<", 1000), b"\xa1\xb2\xc3\xd4": (">", 1000),
               b"\x4d\x3c\xb2\xa1": ("<", 1), b"\xa1\xb2\x3c\x4d": (">", 1)}
_PCAPNG = b"\x0a\x0d\x0d\x0a"


class DecoderError(RuntimeError):
    """The capture file is invalid or cut short. Messages never quote its contents."""


def _pcap_records(f, head) -> Iterator[tuple[int, int, bytes]]:
    endian, multiplier = _PCAP_MAGIC[head]
    rest = f.read(20)
    if len(rest) < 20:
        raise DecoderError("capture header is cut short")
    link = struct.unpack(endian + "HHiIII", rest)[5]
    number = 0
    while True:
        header = f.read(16)
        if not header:
            return
        number += 1
        if len(header) < 16:
            raise DecoderError(f"capture is cut short at record {number}")
        seconds, fraction, captured, _ = struct.unpack(endian + "IIII", header)
        if captured > 16 << 20:
            raise DecoderError(f"implausible length at record {number}")
        body = f.read(captured)
        if len(body) < captured:
            raise DecoderError(f"capture is cut short at record {number}")
        yield seconds * 1_000_000_000 + fraction * multiplier, link, body


def _pcapng_records(f, head) -> Iterator[tuple[int, int, bytes]]:
    endian, interfaces, raw, number = "<", [], head, 0
    try:
        while True:
            raw = raw or f.read(4)
            if not raw:
                return
            number += 1
            size = f.read(4)
            if len(raw) < 4 or len(size) < 4:
                raise DecoderError(f"capture is cut short at block {number}")
            if raw == _PCAPNG:
                order = f.read(4)
                endian = "<" if order == b"\x4d\x3c\x2b\x1a" else ">"
                interfaces = []
                length = struct.unpack(endian + "I", size)[0]
                if not 28 <= length <= 32 << 20 or length % 4:
                    raise DecoderError(f"bad length at block {number}")
                body = order + f.read(length - 16)
            else:
                length = struct.unpack(endian + "I", size)[0]
                if not 12 <= length <= 32 << 20 or length % 4:
                    raise DecoderError(f"bad length at block {number}")
                body = f.read(length - 12)
            tail = f.read(4)
            if len(tail) < 4 or struct.unpack(endian + "I", tail)[0] != length:
                raise DecoderError(f"bad trailer at block {number}")
            kind = struct.unpack(endian + "I", raw)[0]
            if kind == 1:
                link, _, _ = struct.unpack(endian + "HHI", body[:8])
                resolution, p = 1000, 8
                while p + 4 <= len(body):
                    code, size_ = struct.unpack(endian + "HH", body[p:p + 4])
                    if code == 0:
                        break
                    if code == 9 and size_ == 1:
                        value = body[p + 4]
                        resolution = 10 ** 9 / 2 ** (value & 0x7f) if value & 0x80 else 10 ** (9 - value)
                    p += 4 + size_ + (-size_ % 4)
                interfaces.append((link, resolution))
            elif kind == 6:
                index, high, low, captured, _ = struct.unpack(endian + "IIIII", body[:20])
                link, resolution = interfaces[index]
                yield int(((high << 32) | low) * resolution), link, body[20:20 + captured]
            raw = b""
    except (IndexError, struct.error):
        raise DecoderError(f"invalid block {number}") from None


def read_stream(f) -> Iterator[tuple[int, int, bytes]]:
    """Yield (timestamp ns, link type, frame) one at a time from an open binary file or pipe."""
    head = f.read(4)
    if head in _PCAP_MAGIC:
        yield from _pcap_records(f, head)
    elif head == _PCAPNG:
        yield from _pcapng_records(f, head)
    else:
        raise DecoderError("not a pcap or pcapng file")


def read_records(path) -> Iterator[tuple[int, int, bytes]]:
    """Yield (timestamp ns, link type, frame) one at a time from a pcap or pcapng file."""
    with open(path, "rb") as f:
        yield from read_stream(f)


def _network(link, f):
    """(src, dst, protocol, L4 bytes, fragment, declared L4 length), or the name of a stats key if it is not usable.

    fragment is None, or (datagram id, byte offset, more follow) for a piece reassembled by _Fragments.
    """
    if link == 1:
        if len(f) < 14:
            return "bad_metadata_frames"
        ethertype, p = int.from_bytes(f[12:14]), 14
        while ethertype in (0x8100, 0x88a8) and len(f) >= p + 4:
            ethertype, p = int.from_bytes(f[p + 2:p + 4]), p + 4
    elif link == 113:
        if len(f) < 16:
            return "bad_metadata_frames"
        ethertype, p = int.from_bytes(f[14:16]), 16
    elif link == 276:
        if len(f) < 20:
            return "bad_metadata_frames"
        ethertype, p = int.from_bytes(f[:2]), 20
    elif link == 101:
        ethertype, p = 0x0800 if f[:1] and f[0] >> 4 == 4 else 0x86dd, 0
    elif link == 0:
        ethertype, p = 0x0800 if len(f) > 4 and f[4] >> 4 == 4 else 0x86dd, 4
    else:
        return "unsupported_link_frames"
    if ethertype == 0x0800:
        if len(f) < p + 20:
            return "bad_metadata_frames"
        header = (f[p] & 15) * 4
        total = int.from_bytes(f[p + 2:p + 4])
        if header < 20 or total < header:
            return "bad_metadata_frames"
        word = int.from_bytes(f[p + 6:p + 8])
        fragment = (int.from_bytes(f[p + 4:p + 6]), (word & 0x1fff) * 8, bool(word & 0x2000)) if word & 0x3fff else None
        return ("%d.%d.%d.%d" % tuple(f[p + 12:p + 16]), "%d.%d.%d.%d" % tuple(f[p + 16:p + 20]), f[p + 9],
                f[p + header:p + total], fragment, total - header)
    if ethertype == 0x86dd:
        if len(f) < p + 40:
            return "bad_metadata_frames"
        total = int.from_bytes(f[p + 4:p + 6])
        next_header, at, end, fragment = f[p + 6], p + 40, p + 40 + total, None
        while next_header in _IPV6_SKIPPED or next_header == 44:
            if len(f) < at + 8 or at + 8 > end:
                return "bad_metadata_frames"
            if next_header == 44:
                word = int.from_bytes(f[at + 2:at + 4])
                fragment = (int.from_bytes(f[at + 4:at + 8]), word & 0xfff8, bool(word & 1)) if word & 0xfff9 else None
                size = 8
            else:
                size = (f[at + 1] + 1) * 8
            next_header, at = f[at], at + size
        if at > end:
            return "bad_metadata_frames"
        return (str(ipaddress.IPv6Address(f[p + 8:p + 24])), str(ipaddress.IPv6Address(f[p + 24:p + 40])), next_header,
                f[at:end], fragment, end - at)
    return "non_tcp_frames"


def _message(msg_type, flags, length, body, key, stats):
    """One complete message, and whether its structure is broken. Reads only what features need; never the CONNECT payload."""
    if msg_type == CONNECT:
        if len(body) >= 2 and len(body) >= 6 + (name := int.from_bytes(body[:2])):
            if body[2:2 + name] in (b"MQTT", b"MQIsdp"):
                return MqttMessage(msg_type, length, keepalive=int.from_bytes(body[4 + name:6 + name])), False
            stats["connect_unknown_protocol"] += 1
            return MqttMessage(msg_type, length), False
        return MqttMessage(msg_type, length), True
    if msg_type == CONNACK:
        return MqttMessage(msg_type, length, connack_code=body[1] if len(body) >= 2 else None), len(body) < 2
    if msg_type == PUBLISH:
        qos, retain = (flags >> 1) & 3, bool(flags & 1)
        if len(body) >= 2 and len(body) >= 2 + (size := int.from_bytes(body[:2])) + (2 if qos else 0):
            # surrogateescape keeps invalid UTF-8 distinct, where tshark's text collapses it to U+FFFD
            topics = (_token(body[2:2 + size].decode("utf-8", "surrogateescape"), key),) if size else ()
            return MqttMessage(msg_type, length, qos=qos, retain=retain, topics=topics), False
        stats["topic_mismatch_messages"] += 1
        return MqttMessage(msg_type, length, qos=qos, retain=retain), True
    if msg_type == SUBSCRIBE:
        p, filters = 2, []
        while p + FILTER_OVERHEAD <= len(body):
            size = int.from_bytes(body[p:p + 2])
            if p + FILTER_OVERHEAD + size > len(body):
                break
            if size:
                filters.append(body[p + 2:p + 2 + size])
            p += FILTER_OVERHEAD + size
        if p != len(body) or len(body) < 2:  # includes MQTT 5, whose properties do not fit this layout
            stats["topic_mismatch_messages"] += 1
            return MqttMessage(msg_type, length), True
        return MqttMessage(msg_type, length, topics=tuple(_token(t.decode("utf-8", "surrogateescape"), key) for t in filters)), False
    return MqttMessage(msg_type, length), False


def _without_properties(body):
    """An MQTT 5 SUBSCRIBE body with its properties removed, or unchanged if they do not fit, which _message then flags."""
    size, multiplier, p = 0, 1, 2
    while p < len(body):
        byte = body[p]
        size += (byte & 127) * multiplier
        multiplier *= 128
        p += 1
        if not byte & 128:
            return body[:2] + body[p + size:] if p + size <= len(body) else body
        if p > 5:
            break
    return body


class _Fragments:
    """Bounded IP reassembly. Overlapping pieces drop the datagram, as RFC 5722 requires, so overlaps cannot rewrite data."""

    def __init__(self, stats, max_datagrams=MAX_FRAGMENTED_DATAGRAMS, timeout_ns=FRAGMENT_TIMEOUT_NS):
        self.stats, self.max, self.timeout = stats, max_datagrams, timeout_ns
        self.held = {}  # key -> [first seen ns, {offset: bytes}, total length or None]; insertion order is oldest first

    def add(self, key, offset, more, data, ts_ns) -> Optional[bytes]:
        while self.held:
            oldest = next(iter(self.held))
            if len(self.held) < self.max and ts_ns - self.held[oldest][0] <= self.timeout:
                break
            del self.held[oldest]
            self.stats["ip_fragments_expired"] += 1
        if offset + len(data) > 65535 or (more and len(data) % 8):
            self.stats["ip_fragments_invalid"] += 1
            self.held.pop(key, None)
            return None
        entry = self.held.setdefault(key, [ts_ns, {}, None])
        pieces = entry[1]
        if any(offset < o + len(d) and o < offset + len(data) for o, d in pieces.items()):
            self.stats["ip_fragment_overlaps"] += 1
            del self.held[key]
            return None
        pieces[offset] = data
        if not more:
            entry[2] = offset + len(data)
        if entry[2] is None or sum(map(len, pieces.values())) != entry[2]:
            return None
        del self.held[key]
        self.stats["ip_datagrams_reassembled"] += 1
        return b"".join(pieces[o] for o in sorted(pieces))


class _Stream:
    """One direction of a connection. From D-01's Stream, with byte limits and skipping of oversized messages."""
    __slots__ = ("key", "stats", "expected", "buf", "ooo", "ooo_bytes", "skip", "last_ns", "bad", "out", "limit", "v5")

    def __init__(self, key, stats, limit):
        self.key, self.stats, self.limit = key, stats, limit
        self.expected, self.buf, self.ooo, self.ooo_bytes, self.skip = None, bytearray(), {}, 0, 0
        self.last_ns, self.bad, self.out, self.v5 = 0, False, [], False

    def size(self):
        return len(self.buf) + self.ooo_bytes

    def syn(self, seq):
        self.close()
        self.expected = (seq + 1) & 0xffffffff

    def add(self, seq, data):
        stats = self.stats
        if self.expected is None:
            self.expected = seq
            stats["streams_without_syn"] += 1
        delta = ((seq - self.expected + 2 ** 31) & 0xffffffff) - 2 ** 31
        if delta < 0:
            if delta + len(data) <= 0:
                stats["tcp_retransmitted_segments"] += 1
                return
            data = data[-delta:]
            stats["tcp_partial_overlaps"] += 1
        elif delta > 0:
            self.ooo_bytes += len(data) - len(self.ooo.get(seq, b""))
            self.ooo[seq] = data
            stats["tcp_out_of_order_segments"] += 1
            if len(self.ooo) > MAX_OUT_OF_ORDER_SEGMENTS or self.size() > self.limit:
                self._skip_gap()
            self._drain()
            return
        self._accept(data)
        self._drain()

    def _drain(self):
        while self.expected in self.ooo:
            data = self.ooo.pop(self.expected)
            self.ooo_bytes -= len(data)
            self._accept(data)

    def _skip_gap(self):
        self.stats["tcp_sequence_gaps"] += 1
        self._discard_partial()
        self.expected = min(self.ooo, key=lambda s: (s - self.expected) & 0xffffffff)

    def _discard_partial(self):
        if self.buf or self.skip:
            self.stats["partial_messages_discarded"] += 1
            self.stats["partial_bytes_discarded"] += len(self.buf)
        self.buf.clear()
        self.skip = 0

    def _accept(self, data):
        self.expected = (self.expected + len(data)) & 0xffffffff
        if self.skip:
            used = min(self.skip, len(data))
            self.skip -= used
            data = data[used:]
        self.buf += data
        self._parse()

    def _parse(self):
        b, stats = self.buf, self.stats
        while b:
            msg_type, flags = b[0] >> 4, b[0] & 15
            if msg_type == PUBLISH:
                valid = (flags >> 1) & 3 != 3
            else:
                valid = REQUIRED_FLAGS.get(msg_type) == flags or (self.v5 and msg_type == AUTH and flags == 0)
            length, multiplier, i = 0, 1, 1
            while True:
                if i >= len(b):
                    return
                byte = b[i]
                length += (byte & 127) * multiplier
                multiplier *= 128
                i += 1
                if not byte & 128:
                    break
                if i > 4:
                    self._invalid()
                    return
            if not valid:
                # Its framing is still read, so one bad header cannot hide the valid messages after it in the stream.
                if len(b) < i + length:
                    self._invalid()
                    return
                stats["invalid_fixed_header_events"] += 1
                stats["invalid_bytes_discarded"] += i + length
                self.bad = True
                del b[:i + length]
                continue
            if len(b) < i + length:
                if i + length > self.limit:  # clearing alone would parse the rest of its payload as messages
                    stats["oversized_messages_skipped"] += 1
                    self.skip = i + length - len(b)
                    b.clear()
                return
            body = bytes(b[i:i + length])
            if msg_type == CONNECT and len(body) >= 3:
                self.v5 = body[2 + int.from_bytes(body[:2]):3 + int.from_bytes(body[:2])] == b"\x05"
            elif msg_type == SUBSCRIBE and self.v5:
                body = _without_properties(body)
            message, broken = _message(msg_type, flags, length, body, self.key, stats)
            self.bad |= broken
            self.out.append(message)
            del b[:i + length]

    def _invalid(self):
        self.stats["invalid_fixed_header_events"] += 1
        self.stats["invalid_bytes_discarded"] += len(self.buf)
        self.bad = True
        self.buf.clear()

    def close(self):
        self.v5 = False
        if self.ooo:
            self.stats["tcp_sequence_gaps_at_close"] += 1
        self._discard_partial()
        self.expected, self.ooo, self.ooo_bytes = None, {}, 0


def decode_packets(packets: Iterable[tuple[int, int, bytes]], stats: Optional[Counter] = None, broker_port=1883,
                   max_streams=MAX_STREAMS, max_stream_bytes=MAX_STREAM_BYTES, max_total_bytes=MAX_TOTAL_BYTES,
                   idle_ns=IDLE_NS) -> Iterator[PacketEvent]:
    """Decode (timestamp ns, link type, frame) tuples in arrival order. One call is one run, with its own topic key."""
    stats = Counter() if stats is None else stats
    key = secrets.token_bytes(32)
    streams: dict[tuple, _Stream] = {}  # insertion order is least recently used first
    fragments = _Fragments(stats)
    total = 0

    def evict(stream_key, counter):
        nonlocal total
        stream = streams.pop(stream_key)
        total -= stream.size()
        stream.close()
        stats[counter] += 1

    for ts_ns, link, frame in packets:
        stats["frames"] += 1
        parsed = _network(link, frame)
        if isinstance(parsed, str):
            stats[parsed] += 1
            continue
        src, dst, protocol, segment, fragment, declared = parsed
        if protocol != 6:
            stats["non_tcp_frames"] += 1
            continue
        if fragment:
            stats["ip_fragments"] += 1
            datagram_id, offset, more = fragment
            segment = fragments.add((src, dst, datagram_id), offset, more, segment, ts_ns)
            if segment is None:
                continue  # the event belongs to the frame that completes the datagram
            declared = len(segment)
        if len(segment) < 20:
            stats["bad_metadata_frames"] += 1
            continue
        sport, dport, seq = struct.unpack("!HHI", segment[:8])
        header, flags = (segment[12] >> 4) * 4, segment[13]
        if header < 20 or declared < header:
            stats["bad_metadata_frames"] += 1
            continue
        data = segment[header:]
        if len(data) < declared - header:
            stats["truncated_tcp_frames"] += 1
        syn, ack, fin, rst = bool(flags & 2), bool(flags & 16), bool(flags & 1), bool(flags & 4)
        messages, malformed = (), False
        if broker_port in (sport, dport) and (syn or data or rst):
            stream_key = (src, sport, dst, dport)
            stream = streams.pop(stream_key, None)
            if stream is None and (syn or data):
                stream = _Stream(key, stats, max_stream_bytes)
                stats["streams_opened"] += 1
                reverse = streams.get((dst, dport, src, sport))
                stream.v5 = bool(reverse and reverse.v5)
            if stream is not None:
                before = stream.size()
                if syn:
                    stream.syn(seq)
                if data:
                    stream.add((seq + syn) & 0xffffffff, data)  # a SYN uses one sequence number before its data
                messages, malformed = tuple(stream.out), stream.bad
                stream.out, stream.bad = [], False
                if stream.v5 and (reverse := streams.get((dst, dport, src, sport))):
                    reverse.v5 = True
                if rst:
                    stream.close()
                    stats["streams_closed_rst"] += 1
                    total -= before
                else:
                    stream.last_ns = ts_ns
                    streams[stream_key] = stream
                    total += stream.size() - before
                    stats["stream_bytes_peak"] = max(stats["stream_bytes_peak"], stream.size())
                    stats["streams_peak"] = max(stats["streams_peak"], len(streams))
                    stats["total_bytes_peak"] = max(stats["total_bytes_peak"], total)
                while streams:
                    oldest = next(iter(streams))
                    if len(streams) > max_streams:
                        evict(oldest, "streams_evicted_limit")
                    elif total > max_total_bytes:
                        evict(oldest, "streams_evicted_bytes")
                    elif ts_ns - streams[oldest].last_ns > idle_ns:
                        evict(oldest, "streams_evicted_idle")
                    else:
                        break
        stats["malformed_frames"] += malformed
        stats["mqtt_messages"] += len(messages)
        stats["events"] += 1
        yield PacketEvent(ts_ns, src, dst, sport, dport, tcp_len=declared - header, syn=syn, ack=ack, fin=fin, rst=rst,
                          mqtt=messages, malformed=malformed)
    stats["streams_open_at_end"] += len(streams)
    for stream in streams.values():
        stream.close()


def decode_pcap(path, stats: Optional[Counter] = None, **limits) -> Iterator[PacketEvent]:
    """Yield a capture file's events, holding one record at a time plus bounded stream state."""
    return decode_packets(read_records(path), stats, **limits)
