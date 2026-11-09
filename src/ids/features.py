"""Shared windowed feature extractor (offline and live). Standard library only.

Semantics are defined in docs/architecture/FEATURE_SPECIFICATION.md, section 7.
Input adapters decode packets into PacketEvent; this module never touches a parser or capture tool.
"""
from collections import Counter
from dataclasses import dataclass, field
from heapq import heappop, heappush
from math import sqrt
from typing import Iterable, Iterator, Optional

EXTRACTOR_VERSION = "fx-0.1"
FEATURE_IDS = tuple(f"F{i:02d}" for i in range(1, 27))
SUPPORTED_WINDOWS_S = (1, 5, 10)
DEFAULT_GRACE_NS = 1_000_000  # 1 ms: covers the largest reversal measured in MQTTset (38 microseconds)

CONNECT, CONNACK, PUBLISH, SUBSCRIBE, PINGREQ, DISCONNECT = 1, 2, 3, 8, 12, 14


@dataclass(frozen=True, slots=True)
class MqttMessage:
    """One complete MQTT message. There are deliberately no payload, client-ID, or credential fields."""
    msg_type: int
    length: int  # MQTT remaining length, as in mqtt.len
    qos: int = 0
    retain: bool = False
    keepalive: Optional[int] = None  # CONNECT only
    connack_code: Optional[int] = None  # CONNACK only
    topics: tuple[str, ...] = field(default=(), repr=False)  # PUBLISH topic or SUBSCRIBE filters, as adapter tokens (fields.py); counted, never emitted


@dataclass(frozen=True, slots=True)
class PacketEvent:
    """One captured frame. Messages belong to the frame that completes them."""
    ts_ns: int
    src: str
    dst: str
    sport: int
    dport: int
    tcp_len: int = 0
    syn: bool = False
    ack: bool = False
    fin: bool = False
    rst: bool = False
    mqtt: tuple[MqttMessage, ...] = ()
    # shortcut: False also means "the input parser cannot tell", so F23 is only valid from an adapter that sets it; tshark adapter is T3
    malformed: bool = False


@dataclass(frozen=True, slots=True)
class WindowRow:
    window_start_ns: int
    source_key: str  # grouping key only, never part of features
    features: tuple[float, ...]  # F01..F26, in FEATURE_IDS order
    extractor_version: str = EXTRACTOR_VERSION
    complete: bool = True  # False if the stream started or ended inside this window; not a feature

    def as_dict(self) -> dict[str, float]:
        return dict(zip(FEATURE_IDS, self.features))


class _Moments:
    """Running mean and population standard deviation, so window state stays small under floods."""
    __slots__ = ("n", "mean", "m2")

    def __init__(self):
        self.n, self.mean, self.m2 = 0, 0.0, 0.0

    def add(self, x):
        self.n += 1
        delta = x - self.mean
        self.mean += delta / self.n
        self.m2 += delta * (x - self.mean)

    def std(self):
        return sqrt(self.m2 / self.n) if self.n > 1 else 0.0


class _SourceWindow:
    __slots__ = ("pkts", "bytes", "syn", "rst", "fin", "ports", "last_ts", "iat", "connect", "refused", "publish",
                 "subscribe", "pingreq", "disconnect", "lens", "len_max", "topics", "qos_gt0", "retain", "keepalive",
                 "malformed", "wildcard")

    def __init__(self):
        self.pkts = self.bytes = self.syn = self.rst = self.fin = 0
        self.connect = self.refused = self.publish = self.subscribe = self.pingreq = self.disconnect = 0
        self.len_max = self.qos_gt0 = self.retain = self.keepalive = self.malformed = self.wildcard = 0
        self.ports, self.topics = set(), set()
        self.last_ts = None
        self.iat, self.lens = _Moments(), _Moments()


class FeatureAggregator:
    """Streaming tumbling-window aggregator.

    push() takes one event, advance() closes windows from a live timer, and finish() ends the stream. Each returns
    the rows that became final, ordered by window then source key.
    """

    def __init__(self, window_s=5, broker_port=1883, grace_ns=DEFAULT_GRACE_NS, source_key=str, max_open_connections=None, keepalive_expiry=None):
        if window_s not in SUPPORTED_WINDOWS_S:
            raise ValueError(f"window_s must be one of {SUPPORTED_WINDOWS_S}, got {window_s!r}")
        self._w_ns = window_s * 1_000_000_000
        if not 0 <= grace_ns < self._w_ns:
            raise ValueError("grace_ns must be at least 0 and shorter than the window")
        self._window_s, self._port, self._grace, self._key = window_s, broker_port, grace_ns, source_key
        self._heap, self._seq = [], 0
        self._newest = self._watermark = None
        self._index = None  # index of the open window
        self._sources: dict[str, _SourceWindow] = {}
        self._messages = 0  # F25 for the open window
        # A connection whose FIN or RST was never captured stays open until stream end. max_open_connections bounds that state
        # (OD-1 hard limit): below it F22 is exactly fx-0.1; above it the oldest client's oldest connection is dropped and counted.
        # None keeps the original unbounded behaviour, which offline tables use.
        self._open: dict[str, dict[tuple, int]] = {}  # client -> connection -> keep-alive, for F22; clients with none have no entry
        self._open_total, self._max_open = 0, max_open_connections
        # Proposed OD-1 expiry, opt-in: a connection silent from the client for longer than keepalive_expiry x K is dropped from
        # F22 state, as an MQTT broker must drop it after 1.5 K. It changes F22 only when a FIN or RST was missed, so rows carry
        # their own extractor version and validate_row refuses them for fx-0.1 models. K = 0 never expires.
        if keepalive_expiry is not None and keepalive_expiry <= 0:
            raise ValueError("keepalive_expiry must be positive")
        self._expiry = keepalive_expiry
        self._last: dict[tuple, int] = {}  # (client, connection) -> last client packet, only when expiry is on
        self.version = EXTRACTOR_VERSION if keepalive_expiry is None else f"{EXTRACTOR_VERSION}+ka{keepalive_expiry:g}"
        self._seen_first_window = self._finished = False
        self.stats = Counter()  # ignored_events, late_events, reply_only_windows

    def push(self, event: PacketEvent) -> list[WindowRow]:
        if self._finished:
            raise RuntimeError("push() after finish()")
        if self._port not in (event.sport, event.dport):
            self.stats["ignored_events"] += 1
            return []
        if self._watermark is not None and event.ts_ns < self._watermark:
            self.stats["late_events"] += 1  # the window it belongs to may already be final
            return []
        heappush(self._heap, (event.ts_ns, self._seq, event))
        self._seq += 1
        self._newest = event.ts_ns if self._newest is None else max(self._newest, event.ts_ns)
        return self._release(self._newest - self._grace)

    def advance(self, now_ns: int) -> list[WindowRow]:
        """Close windows when no packet arrives to do so. Uses the same clock as event timestamps."""
        self._newest = now_ns if self._newest is None else max(self._newest, now_ns)
        return self._release(self._newest - self._grace)

    def finish(self) -> list[WindowRow]:
        self._finished = True
        rows = []
        while self._heap:
            rows += self._apply(heappop(self._heap)[2])
        rows += self._close(final=True)
        return rows

    def _release(self, limit: int) -> list[WindowRow]:
        rows = []
        while self._heap and self._heap[0][0] <= limit:
            rows += self._apply(heappop(self._heap)[2])
        self._watermark = limit
        if self._index is not None and (self._index + 1) * self._w_ns <= limit:
            rows += self._close()
        return rows

    def _apply(self, e: PacketEvent) -> list[WindowRow]:
        index = e.ts_ns // self._w_ns
        rows = self._close() if self._index is not None and index > self._index else []
        self._index = index

        to_broker = e.dport == self._port
        client, port, broker = (e.src, e.sport, e.dst) if to_broker else (e.dst, e.dport, e.src)
        conn = (port, broker)
        s = self._sources.setdefault(client, _SourceWindow())
        open_conns = self._open.get(client) or {}
        before = len(open_conns)

        if to_broker:
            s.pkts += 1
            s.bytes += e.tcp_len
            s.ports.add(e.sport)
            s.malformed += e.malformed
            if s.last_ts is not None:
                s.iat.add((e.ts_ns - s.last_ts) / 1e9)
            s.last_ts = e.ts_ns
            if e.syn and not e.ack:
                s.syn += 1
                self._expire(s, open_conns, conn)  # port reuse: a new SYN ends any earlier connection on this port
            s.fin += e.fin
        s.rst += e.rst

        for m in e.mqtt:
            if to_broker:
                self._count_to_broker(s, open_conns, conn, m)
            elif m.msg_type == CONNACK and m.connack_code not in (None, 0):
                s.refused += 1

        if e.fin or e.rst:
            self._expire(s, open_conns, conn)
        if self._expiry is not None and to_broker and conn in open_conns:
            self._last[(client, conn)] = e.ts_ns
        # Only clients with an open connection get an entry: _row reads a missing client and an empty one alike.
        if open_conns:
            self._open[client] = open_conns
        else:
            self._open.pop(client, None)
        self._open_total += len(open_conns) - before
        if self._max_open is not None:
            self._evict_open()
        return rows

    def _evict_open(self):
        while self._open_total > self._max_open:
            client = next(iter(self._open))
            conns = self._open[client]
            conns.pop(next(iter(conns)))
            if not conns:
                del self._open[client]
            self._open_total -= 1
            self.stats["evicted_connections"] += 1

    @property
    def open_connections(self) -> int:
        return self._open_total

    def _count_to_broker(self, s, open_conns, conn, m):
        self._messages += 1
        s.lens.add(m.length)
        s.len_max = max(s.len_max, m.length)
        if m.msg_type == CONNECT:
            s.connect += 1
            if m.keepalive is not None:
                open_conns[conn] = m.keepalive
                s.keepalive = max(s.keepalive, m.keepalive)
        elif m.msg_type == PUBLISH:
            s.publish += 1
            s.qos_gt0 += m.qos > 0
            s.retain += bool(m.retain)
            s.topics.update(m.topics)
        elif m.msg_type == SUBSCRIBE:
            s.subscribe += 1
            s.topics.update(m.topics)
            s.wildcard += any("#" in t or "+" in t for t in m.topics)
        elif m.msg_type == PINGREQ:
            s.pingreq += 1
        elif m.msg_type == DISCONNECT:
            s.disconnect += 1

    @staticmethod
    def _expire(s, open_conns, conn):
        # A connection open at any point in this window still counts towards this window's F22.
        kept = open_conns.pop(conn, None)
        if kept is not None:
            s.keepalive = max(s.keepalive, kept)

    def _close(self, final=False) -> list[WindowRow]:
        if self._index is None:
            return []
        complete = self._seen_first_window and not final
        self._seen_first_window = True
        if self._expiry is not None:
            self._expire_silent(self._index * self._w_ns)
        active = {c: s for c, s in self._sources.items() if s.pkts}
        self.stats["reply_only_windows"] += len(self._sources) - len(active)
        rows = [self._row(c, s, len(active), complete) for c, s in active.items()]
        rows.sort(key=lambda r: r.source_key)
        self._sources, self._messages, self._index = {}, 0, None
        return rows

    def _expire_silent(self, window_start_ns):
        """Drop connections whose keep-alive deadline passed before this window began, so they were open at no point in it."""
        for key, last in list(self._last.items()):
            client, conn = key
            conns = self._open.get(client)
            if not conns or conn not in conns:
                del self._last[key]  # closed, replaced, or evicted already
                continue
            keepalive = conns[conn]
            if keepalive and last + self._expiry * keepalive * 1_000_000_000 < window_start_ns:
                del conns[conn], self._last[key]
                if not conns:
                    del self._open[client]
                self._open_total -= 1
                self.stats["expired_keepalive"] += 1

    def _row(self, client, s, active_sources, complete) -> WindowRow:
        carried = max(self._open.get(client, {}).values(), default=0)
        features = (
            s.pkts,                                                  # F01
            s.bytes,                                                 # F02
            s.syn,                                                   # F03
            s.rst,                                                   # F04
            s.fin,                                                   # F05
            len(s.ports),                                            # F06
            s.iat.mean if s.iat.n else float(self._window_s),        # F07
            s.iat.std(),                                             # F08
            s.connect,                                               # F09
            s.refused,                                               # F10
            s.refused / max(s.connect, 1),                           # F11
            s.publish,                                               # F12
            s.subscribe,                                             # F13
            s.pingreq,                                               # F14
            s.disconnect,                                            # F15
            s.lens.mean,                                             # F16
            s.lens.std(),                                            # F17
            s.len_max,                                               # F18
            len(s.topics),                                           # F19
            s.qos_gt0 / s.publish if s.publish else 0.0,             # F20
            s.retain / s.publish if s.publish else 0.0,              # F21
            max(s.keepalive, carried),                               # F22
            s.malformed,                                             # F23
            s.wildcard,                                              # F24
            self._messages,                                          # F25
            active_sources,                                          # F26
        )
        return WindowRow(self._index * self._w_ns, self._key(client), features, self.version, complete=complete)


def extract_features(events: Iterable[PacketEvent], **options) -> Iterator[WindowRow]:
    """Yield rows for a whole event stream, using the same code path as live operation."""
    aggregator = FeatureAggregator(**options)
    for event in events:
        yield from aggregator.push(event)
    yield from aggregator.finish()
