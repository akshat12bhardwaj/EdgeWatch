"""TShark adapter: runs tshark on a capture file and yields PacketEvent, with no feature or window logic.

Settings and field meanings were validated in T2; docs/architecture/FEATURE_SPECIFICATION.md section 8 has the limits.
Topic strings exist only while one frame is decoded: section 8.1 has the privacy boundary.
"""
import hmac
import json
import os
import re
import secrets
import shutil
import subprocess
import threading
from collections import Counter, deque
from itertools import repeat
from typing import Iterable, Iterator, Optional

from .features import CONNACK, CONNECT, PUBLISH, SUBSCRIBE, MqttMessage, PacketEvent

DEFAULT_TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
# Never add usernames, passwords, client IDs, or payloads here: what is not requested cannot leak.
# mqtt.topic is the one exception: _topic_tokens is its only reader, and no raw value may leave that function.
FIELDS =("frame.time_epoch", "ip.src", "ip.dst", "ipv6.src", "ipv6.dst", "tcp.srcport", "tcp.dstport", "tcp.len",
          "tcp.flags.syn", "tcp.flags.ack", "tcp.flags.fin", "tcp.flags.reset",
          "mqtt.hdrflags", "mqtt.len", "mqtt.kalive", "mqtt.conack.val", "mqtt.topic", "mqtt.topic_len",
          "_ws.malformed.expert")
# All three are needed: T2 lost 458 real PUBLISH on capture_1w with out-of-order off. Never add -2 or -M (T2 section 5).
PREFERENCES = ("tcp.desegment_tcp_streams:TRUE", "tcp.analyze_sequence_numbers:TRUE", "tcp.reassemble_out_of_order:TRUE")

_EPOCH = re.compile(r"([0-9]+)(?:\.([0-9]{1,9}))?")
_BOOLEANS = {"True": True, "False": False, "1": True, "0": False}
UNSUBSCRIBE = 10


class TSharkError(RuntimeError):
    """tshark could not start or exited with an error."""


class TSharkOutputError(TSharkError):
    """tshark's output was invalid or cut short. Messages never quote the output."""


def _one(layers, key) -> str:
    values = layers.get(key, ())
    if len(values) != 1:  # more than one means an embedded packet, such as an ICMP error quoting TCP
        raise ValueError(key)
    return values[0]


def _epoch_ns(text: str) -> int:
    match = _EPOCH.fullmatch(text)
    if not match:
        raise ValueError("frame_time_epoch")
    return int(match[1]) * 1_000_000_000 + int((match[2] or "").ljust(9, "0"))


def _port(layers, key) -> int:
    port = int(_one(layers, key))
    if not 0 <= port <= 65535:
        raise ValueError(key)
    return port


def _address(layers, family_v4, family_v6) -> str:
    return _one({"a": [*layers.get(family_v4, ()), *layers.get(family_v6, ())]}, "a")


def _optional(layers, key, default, stats):
    if key not in layers:
        stats["missing_tcp_field_frames"] += 1
        return default
    return _one(layers, key)


def _flag(layers, key, stats) -> bool:
    return _BOOLEANS[_optional(layers, key, "False", stats)]


def _aligned(layers, key, expected, stats) -> Iterator[Optional[int]]:
    """Values for the messages that carry this field, or None for all of them if the count disagrees: never guess."""
    try:
        values = layers.get(key, ())
        if len(values) == expected:
            return iter([int(v) for v in values])
    except (TypeError, ValueError):
        pass
    stats[f"{key}_mismatch_frames"] += 1
    return repeat(None)


def _token(topic: str, key: bytes) -> str:
    """HMAC-SHA256 of a topic. A trailing # is the wildcard flag, in the form F24 in features.py already reads.

    Hex digests never contain # or +, so nothing else can match. The flag depends only on the string, so equal strings
    give equal tokens and different strings different ones, and F19 counts what it would count on the strings.
    """
    # surrogatepass: JSON can decode to a lone surrogate, and a UnicodeEncodeError would carry the whole string
    digest = hmac.digest(key, topic.encode("utf-8", "surrogatepass"), "sha256").hex()
    # shortcut: the flag shares the topics field to keep MqttMessage and T1 unchanged, use a typed field if another adapter appears
    return digest + "#" if "#" in topic or "+" in topic else digest


def _topic_tokens(layers, types, lengths, key, stats) -> list[tuple[str, ...]]:
    """Tokens per message, or none for the whole frame if the fields do not fit the messages: never guess.

    mqtt.topic has one value per PUBLISH topic, SUBSCRIBE filter, and UNSUBSCRIBE filter, in message order. A zero-length
    one has a mqtt.topic_len but no mqtt.topic. Nothing raised or counted here may quote these values.
    """
    topics, sizes = layers.get("mqtt_topic", []), layers.get("mqtt_topic_len", [])
    if not topics and not sizes and not {PUBLISH, SUBSCRIBE, UNSUBSCRIBE} & set(types):
        return [()] * len(types)
    try:
        if not (isinstance(topics, list) and isinstance(sizes, list) and all(isinstance(t, str) for t in topics)):
            raise ValueError
        sizes = [int(n) for n in sizes]
        if any(n < 0 for n in sizes) or sum(n > 0 for n in sizes) != len(topics):
            raise ValueError
        spans, end = [], 0
        for msg_type, length in zip(types, lengths):
            start = end
            if msg_type == PUBLISH:
                end += 1
                if 2 + sizes[start] > length:
                    raise ValueError
            elif msg_type in (SUBSCRIBE, UNSUBSCRIBE):  # packet ID, then per filter: length, text, SUBSCRIBE's QoS byte
                walked, overhead = 2, 3 if msg_type == SUBSCRIBE else 2
                while walked < length:
                    walked += overhead + sizes[end]
                    end += 1
                if walked != length:
                    raise ValueError
            spans.append((start, end))
        if end != len(sizes):
            raise ValueError
    except (IndexError, OverflowError, TypeError, ValueError):
        stats["topic_mismatch_frames"] += 1
        return [()] * len(types)
    names = iter(topics)
    tokens = [_token(next(names), key) if n else None for n in sizes]
    return [tuple(t for t in tokens[start:end] if t) if msg_type != UNSUBSCRIBE else ()  # F19 and F24 ignore UNSUBSCRIBE
            for msg_type, (start, end) in zip(types, spans)]


def _messages(layers, stats, key) -> tuple[MqttMessage, ...]:
    headers, lengths = layers.get("mqtt_hdrflags", ()), layers.get("mqtt_len", ())
    try:
        if len(headers) != len(lengths):
            raise ValueError
        headers = [int(h, 0) for h in headers]  # the one source of type, QoS, and retain (T2 section 6)
        lengths = [int(n) for n in lengths]
        if any(not 0 <= h <= 255 for h in headers) or any(n < 0 for n in lengths):
            raise ValueError
    except (TypeError, ValueError):
        stats["mqtt_mismatch_frames"] += 1
        return ()
    if not headers:
        return ()
    types = [h >> 4 for h in headers]
    keepalives = _aligned(layers, "mqtt_kalive", types.count(CONNECT), stats)
    codes = _aligned(layers, "mqtt_conack_val", types.count(CONNACK), stats)
    tokens = _topic_tokens(layers, types, lengths, key, stats)
    messages = []
    for header, msg_type, length, topics in zip(headers, types, lengths, tokens):
        stats["reserved_messages"] += msg_type in (0, 15)  # passed on: they count in F16-F18 and F25, not as a type
        is_publish = msg_type == PUBLISH  # other types use these bits differently, such as SUBSCRIBE's fixed 0x82
        messages.append(MqttMessage(msg_type, length,
                                    qos=(header >> 1) & 3 if is_publish else 0,
                                    retain=bool(header & 1) if is_publish else False,
                                    keepalive=next(keepalives) if msg_type == CONNECT else None,
                                    connack_code=next(codes) if msg_type == CONNACK else None,
                                    topics=topics))
    return tuple(messages)


def _event(layers, stats, key) -> Optional[PacketEvent]:
    if not isinstance(layers, dict):
        stats["bad_metadata_frames"] += 1
        return None
    if "tcp_srcport" not in layers and "tcp_dstport" not in layers:
        stats["non_tcp_frames"] += 1
        return None
    try:
        event = PacketEvent(_epoch_ns(_one(layers, "frame_time_epoch")),
                            _address(layers, "ip_src", "ipv6_src"), _address(layers, "ip_dst", "ipv6_dst"),
                            _port(layers, "tcp_srcport"), _port(layers, "tcp_dstport"),
                            tcp_len=int(_optional(layers, "tcp_len", "0", stats)),
                            syn=_flag(layers, "tcp_flags_syn", stats), ack=_flag(layers, "tcp_flags_ack", stats),
                            fin=_flag(layers, "tcp_flags_fin", stats), rst=_flag(layers, "tcp_flags_reset", stats),
                            mqtt=_messages(layers, stats, key),
                            # Means a dissector exception only; reserved types and QoS 3 dissect cleanly (T2 section 7).
                            malformed="_ws_malformed_expert" in layers)
        if event.tcp_len < 0:
            raise ValueError("tcp_len")
    except (KeyError, TypeError, ValueError):
        stats["bad_metadata_frames"] += 1
        return None
    stats["malformed_frames"] += event.malformed
    stats["mqtt_messages"] += len(event.mqtt)
    return event


def parse_ek_lines(lines: Iterable[bytes], stats: Optional[Counter] = None) -> Iterator[PacketEvent]:
    """Decode tshark -T ek lines one at a time. Only the fields read below can reach a PacketEvent.

    One call is one run: its random key lives only here, so tokens compare within a run and never across runs.
    """
    stats = Counter() if stats is None else stats
    key = secrets.token_bytes(32)
    number, awaiting_document = 0, False
    for number, line in enumerate(lines, 1):
        if not line.endswith(b"\n"):
            raise TSharkOutputError(f"tshark output was cut short at line {number}")
        try:
            document = json.loads(line)
        except ValueError:
            document = None  # raised below, not here: the JSON error holds the raw line and would stay as __context__
        if document is None:
            raise TSharkOutputError(f"invalid JSON from tshark at line {number}") from None
        if not isinstance(document, dict):
            raise TSharkOutputError(f"unexpected JSON from tshark at line {number}")
        if "index" in document:
            awaiting_document = True
        if "layers" in document:
            awaiting_document = False
            stats["frames"] += 1
            event = _event(document["layers"], stats, key)
            del line, document  # raw topics must not stay referenced while this generator waits on its consumer
            if event is not None:
                stats["events"] += 1
                yield event
    if awaiting_document:
        raise TSharkOutputError(f"tshark output was cut short after line {number}")


def _command(pcap, tshark=None) -> list[str]:
    command = [tshark or os.environ.get("TSHARK_PATH") or shutil.which("tshark") or DEFAULT_TSHARK, "-n", "-T", "ek", "-l"]
    for preference in PREFERENCES:
        command += ["-o", preference]
    for name in FIELDS:
        command += ["-e", name]
    return command + ["-r", str(pcap)]


def _failure(returncode, stderr_tail, reader) -> TSharkError:
    reader.join(timeout=5)
    detail = " | ".join(stderr_tail) or "no error text"
    return TSharkError(f"tshark exited with code {returncode}: {detail}")


def _stop(process, reader):
    process.stdout.close()
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    reader.join(timeout=5)
    process.stderr.close()


def read_pcap(pcap, tshark=None, stats: Optional[Counter] = None) -> Iterator[PacketEvent]:
    """Yield a capture's events as tshark produces them, holding one frame at a time.

    Pass a Counter as stats for diagnostics. Closing the generator early stops tshark without raising.
    tshark's path comes from the argument, then TSHARK_PATH, then PATH, then the default Windows install.
    """
    # shortcut: offline files only, live capture adds -i and -f once it is tested (T2 section 8)
    # shortcut: tshark memory grows with frames and has no safe bound, so this is not Raspberry Pi ready, see section 8
    try:
        process = subprocess.Popen(_command(pcap, tshark), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as error:
        raise TSharkError(f"cannot start tshark: {error.strerror or error}") from None
    stderr_tail = deque(maxlen=20)  # undrained stderr could block tshark; kept short because reports may quote it

    def drain():
        for line in process.stderr:
            stderr_tail.append(line.decode(errors="replace").strip())

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    try:
        try:
            yield from parse_ek_lines(process.stdout, stats)
        except TSharkOutputError:
            try:
                returncode = process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                raise TSharkOutputError("tshark sent invalid output and was stopped") from None
            if returncode:  # a dead tshark explains cut-short output better than the parser can
                raise _failure(returncode, stderr_tail, reader) from None
            raise
        returncode = process.wait()
        if returncode:
            raise _failure(returncode, stderr_tail, reader)
    finally:
        _stop(process, reader)
