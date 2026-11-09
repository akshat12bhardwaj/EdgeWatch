"""Feature extractor tests. Expected values are worked out by hand from synthetic events; no capture files are read."""
import dataclasses
import json
import math
import os
import statistics
import subprocess
import sys
import tracemalloc
from pathlib import Path
from random import Random

import pytest

SRC = str(Path(__file__).resolve().parents[1] / "src")
sys.path.insert(0, SRC)

from ids import EXTRACTOR_VERSION, FEATURE_IDS, FeatureAggregator, MqttMessage, PacketEvent, extract_features  # noqa: E402

BROKER, A, C = "10.0.0.9", "10.0.0.1", "10.0.0.2"
SEC = 1_000_000_000


def ns(seconds):
    return round(seconds * SEC)


def up(t, src=A, port=5000, **kw):
    return PacketEvent(ns(t), src, BROKER, port, 1883, **kw)


def down(t, dst=A, port=5000, **kw):
    return PacketEvent(ns(t), BROKER, dst, 1883, port, **kw)


def msg(msg_type, length=0, **kw):
    return MqttMessage(msg_type, length, **kw)


def rows(events, **options):
    return list(extract_features(events, **options))


def one(events, key=A, start_s=None, **options):
    found = [r for r in rows(events, **options)
             if r.source_key == key and (start_s is None or r.window_start_ns == ns(start_s))]
    assert len(found) == 1, found
    return found[0].as_dict()


def scenario():
    """Window [100, 105) with client A on two connections and client C publishing once."""
    return [
        up(100.0, syn=True),
        down(100.2, syn=True, ack=True),
        up(100.5, tcp_len=14, ack=True, mqtt=(msg(1, 12, keepalive=60),)),
        down(100.7, tcp_len=4, ack=True, mqtt=(msg(2, 2, connack_code=5),)),
        up(102.0, port=5001, syn=True),
        down(102.2, port=5001, rst=True),
        up(103.0, tcp_len=40, ack=True, mqtt=(
            msg(3, 20, qos=1, retain=True, topics=("t/a",)),
            msg(3, 10, topics=("t/b",)),
            msg(8, 8, topics=("t/#",)),
        )),
        down(103.5, tcp_len=100, ack=True, mqtt=(msg(3, 50, qos=2, retain=True, topics=("other",)),)),
        up(104.5, tcp_len=6, ack=True, fin=True, malformed=True, mqtt=(msg(12), msg(14))),
        up(101.0, src=C, port=6000, tcp_len=9, ack=True, mqtt=(msg(3, 7, topics=("t/a",)),)),
    ]


def sorted_scenario():
    return sorted(scenario(), key=lambda e: e.ts_ns)


def test_every_feature_has_its_worked_out_value():
    f = one(sorted_scenario())
    gaps = [0.5, 1.5, 1.0, 1.5]  # 100.0, 100.5, 102.0, 103.0, 104.5
    lengths = [12, 20, 10, 8, 0, 0]
    expected = {
        "F01": 5, "F02": 60, "F03": 2,
        "F04": 1,  # the broker's RST counts for its client
        "F05": 1, "F06": 2,
        "F09": 1, "F10": 1, "F11": 1.0, "F12": 2, "F13": 1, "F14": 1, "F15": 1,
        "F18": 20,
        "F19": 3,  # t/a, t/b, t/# and not the broker's delivery on "other"
        "F20": 0.5, "F21": 0.5, "F22": 60, "F23": 1, "F24": 1,
        "F25": 7,  # A's 6 messages plus C's 1; broker-to-client messages excluded
        "F26": 2,
    }
    assert {k: f[k] for k in expected} == expected
    assert f["F07"] == pytest.approx(1.125)
    assert f["F08"] == pytest.approx(math.sqrt(0.171875))  # population variance of the gaps
    assert f["F08"] == pytest.approx(statistics.pstdev(gaps))
    assert f["F16"] == pytest.approx(50 / 6)
    assert f["F17"] == pytest.approx(statistics.pstdev(lengths))


def test_all_26_features_exist_in_order():
    r = rows(sorted_scenario())[0]
    assert FEATURE_IDS == tuple(f"F{i:02d}" for i in range(1, 27))
    assert len(r.features) == 26 and r.extractor_version == EXTRACTOR_VERSION == "fx-0.1"


def test_other_source_has_its_own_counts_and_shared_context():
    f = one(sorted_scenario(), key=C)
    assert (f["F01"], f["F02"], f["F12"], f["F19"], f["F25"], f["F26"]) == (1, 9, 1, 1, 7, 2)
    assert (f["F07"], f["F08"], f["F16"], f["F17"], f["F18"]) == (5.0, 0.0, 7.0, 0.0, 7)  # F07 = W under 2 packets


@pytest.mark.parametrize("w, t, start", [(5, 105.0, 105), (5, 104.999999999, 100), (1, 3.0, 3), (10, 20.0, 20)])
def test_event_at_exact_boundary_belongs_to_the_new_window(w, t, start):
    event = PacketEvent(round(t * SEC), A, BROKER, 5000, 1883)
    assert [r.window_start_ns for r in rows([event], window_s=w)] == [start * SEC]


def test_unsupported_window_and_grace_are_rejected():
    with pytest.raises(ValueError):
        FeatureAggregator(window_s=2)
    with pytest.raises(ValueError):
        FeatureAggregator(window_s=1, grace_ns=SEC)


def test_broker_to_client_traffic_counts_only_where_defined():
    f = one([
        up(1.0),
        down(1.1, tcp_len=50, syn=True, ack=True, fin=True, mqtt=(
            msg(1, 9, keepalive=99), msg(2, 2, connack_code=4), msg(3, 11, qos=1, retain=True, topics=("x",)),
            msg(8, 5, topics=("#",)), msg(12), msg(14),
        ), malformed=True),
    ])
    assert f["F01"] == 1 and f["F02"] == 0 and f["F03"] == 0 and f["F05"] == 0  # from-broker bytes and flags ignored
    assert f["F10"] == 1  # the one feature defined on broker replies, besides F04
    assert [f[k] for k in ("F09", "F12", "F13", "F14", "F15", "F19", "F20", "F21", "F22", "F23", "F24", "F25")] == [0] * 12


def test_multiple_messages_in_one_frame_count_individually():
    f = one([up(1.0, mqtt=tuple(msg(3, 5, topics=("t",)) for _ in range(2048)))])
    assert (f["F01"], f["F12"], f["F25"], f["F19"], f["F16"], f["F18"]) == (1, 2048, 2048, 1, 5.0, 5)


def test_message_completed_across_frames_counts_in_the_completing_frames_window():
    all_rows = rows([up(4.9, tcp_len=2), up(5.1, tcp_len=30, mqtt=(msg(1, 30, keepalive=10),))])
    first, second = all_rows[0].as_dict(), all_rows[1].as_dict()
    assert first["F09"] == 0 and first["F25"] == 0 and first["F02"] == 2
    assert second["F09"] == 1 and second["F25"] == 1 and second["F18"] == 30


def test_reversal_of_38_microseconds_gives_the_same_rows_as_sorted_input():
    base = [up(4.99999, mqtt=(msg(3, 1),)), up(5.0, mqtt=(msg(3, 2),)), up(5.00002, mqtt=(msg(3, 3),))]
    out_of_order = [base[1], base[0], base[2]]  # crosses the window boundary, reversed by 10 us
    just_within = [up(7.000038), up(7.0)]
    assert rows(out_of_order) == rows(base)
    assert rows(just_within) == rows(list(reversed(just_within)))
    assert rows(just_within)[0].as_dict()["F07"] == pytest.approx(38e-6)  # never a negative gap


def test_event_older_than_the_grace_period_is_dropped_and_counted():
    agg = FeatureAggregator()
    assert agg.push(up(10.0)) == []
    agg.push(up(9.5))
    assert agg.stats["late_events"] == 1
    assert [r.as_dict()["F01"] for r in agg.finish()] == [1]


def test_f22_carries_across_windows_and_expires_on_fin():
    events = [
        up(1.0, mqtt=(msg(1, 10, keepalive=300),)),
        up(6.0),            # carried
        up(11.0, fin=True),  # still open during this window
        up(16.0),            # expired
    ]
    assert [r.as_dict()["F22"] for r in rows(events)] == [300, 300, 300, 0]


def test_f22_expires_on_rst_from_either_side_and_keeps_other_connections():
    events = [
        up(1.0, mqtt=(msg(1, 10, keepalive=100),)),
        up(1.5, port=5001, mqtt=(msg(1, 10, keepalive=40),)),
        down(2.0, rst=True),
        up(6.0),
        down(7.0, port=5001, rst=True),
        up(11.0),
    ]
    assert [r.as_dict()["F22"] for r in rows(events)] == [100, 40, 0]


def test_f22_is_not_carried_through_a_reused_port_and_is_zero_when_unknown():
    events = [up(1.0, mqtt=(msg(1, 10, keepalive=100),)), up(6.0, syn=True), up(11.0)]
    # The old connection is open at the start of [5, 10) until the SYN replaces it, so it ends after that window.
    assert [r.as_dict()["F22"] for r in rows(events)] == [100, 100, 0]
    assert rows([up(1.0)])[0].as_dict()["F22"] == 0  # connection opened before capture


# T3.4: F22 state lifecycle. Hand-worked values; the state assertions read the aggregator's private map on purpose.

def state_after(events, **options):
    agg = FeatureAggregator(**options)
    out = [r for e in events for r in agg.push(e)]
    agg.advance(events[-1].ts_ns + 2_000_000)
    return agg, out


def test_clients_without_open_connections_leave_no_entry():
    agg, _ = state_after([up(1.0), up(1.1, src=C, port=6000), down(1.2, dst="10.0.0.3")])
    assert agg._open == {}


def test_entry_is_removed_on_fin_and_on_rst_from_either_side():
    for closing in (up(2.0, fin=True), up(2.0, rst=True), down(2.0, fin=True), down(2.0, rst=True)):
        agg, _ = state_after([up(1.0, mqtt=(msg(1, 10, keepalive=60),)), closing])
        assert agg._open == {}, closing


def test_active_connection_and_its_keepalive_are_retained_across_windows():
    agg, _ = state_after([up(1.0, mqtt=(msg(1, 10, keepalive=60),)), up(6.0), up(16.0)])
    assert agg._open == {A: {(5000, BROKER): 60}}


def test_entry_stays_until_the_last_connection_of_a_client_closes():
    agg, _ = state_after([up(1.0, mqtt=(msg(1, 10, keepalive=100),)), up(1.5, port=5001, mqtt=(msg(1, 10, keepalive=40),)), up(2.0, fin=True)])
    assert agg._open == {A: {(5001, BROKER): 40}}
    agg, _ = state_after([up(1.0, mqtt=(msg(1, 10, keepalive=100),)), up(1.5, port=5001, mqtt=(msg(1, 10, keepalive=40),)), up(2.0, fin=True), up(2.5, port=5001, rst=True)])
    assert agg._open == {}


def test_clients_keep_separate_entries():
    agg, _ = state_after([up(1.0, mqtt=(msg(1, 10, keepalive=100),)), up(1.5, src=C, port=6000, mqtt=(msg(1, 10, keepalive=40),)), up(2.0, fin=True)])
    assert agg._open == {C: {(6000, BROKER): 40}}


def test_keepalive_zero_connection_is_kept_as_open_state():
    agg, _ = state_after([up(1.0, mqtt=(msg(1, 10, keepalive=0),))])
    assert agg._open == {A: {(5000, BROKER): 0}}


def test_reused_tuple_keeps_one_entry_and_the_newest_keepalive():
    agg, out = state_after([up(1.0, mqtt=(msg(1, 10, keepalive=100),)), up(6.0, syn=True), up(6.1, mqtt=(msg(1, 10, keepalive=40),)), up(11.0)])
    assert agg._open == {A: {(5000, BROKER): 40}}
    assert [r.as_dict()["F22"] for r in out] == [100, 100]  # the old connection was open during [5, 10)


def test_syn_on_a_reused_port_without_a_new_connect_leaves_no_entry():
    agg, _ = state_after([up(1.0, mqtt=(msg(1, 10, keepalive=100),)), up(6.0, syn=True)])
    assert agg._open == {}


def test_idle_connection_is_not_expired_and_still_gives_f22_when_the_client_returns():
    # Production has no idle limit: one week of silence on the connection does not end it.
    week = 7 * 86400
    events = [up(1.0, mqtt=(msg(1, 10, keepalive=300),)), up(week, port=5001)]
    assert [r.as_dict()["F22"] for r in rows(events)] == [300, 300]


def test_cleanup_at_a_window_boundary_keeps_f22_in_the_window_where_the_connection_ended():
    events = [up(4.9, mqtt=(msg(1, 10, keepalive=300),)), up(5.0, fin=True), up(10.0)]
    assert [r.as_dict()["F22"] for r in rows(events)] == [300, 300, 0]


def test_closing_a_connection_before_a_new_client_row_does_not_change_other_clients():
    events = [up(1.0, mqtt=(msg(1, 10, keepalive=300),)), up(1.5, src=C, port=6000, mqtt=(msg(1, 10, keepalive=9),)), up(2.0, rst=True), up(6.0), up(6.1, src=C, port=6000)]
    assert [(r.source_key, r.as_dict()["F22"]) for r in rows(events)] == [(A, 300), (C, 9), (A, 0), (C, 9)]


def churn(count, closed=True, clients=True):
    """New connections with a CONNECT, closed with FIN or left open; each on a new client or all on one."""
    for i in range(count):
        src = f"10.{i >> 16 & 255}.{i >> 8 & 255}.{i & 255}" if clients else A
        yield up(i * 0.001, src=src, port=1024 + i % 60000, mqtt=(msg(1, 10, keepalive=60),))
        if closed:
            yield up(i * 0.001 + 0.0005, src=src, port=1024 + i % 60000, fin=True)


def retained_bytes(events):
    agg = FeatureAggregator(window_s=1)
    tracemalloc.start()
    for e in events:
        agg.push(e)
    agg.advance(10 ** 15)
    size = tracemalloc.get_traced_memory()[0]
    tracemalloc.stop()
    return size, agg


def test_closed_connection_churn_retains_no_state_and_memory_does_not_grow_with_it():
    small, agg = retained_bytes(churn(2000))
    assert agg._open == {}
    large, agg = retained_bytes(churn(20000))
    assert agg._open == {}
    assert large < small + 50_000  # ten times the clients; about 300 bytes each would add over 5 MB


def test_unclosed_connections_are_retained_because_f22_still_needs_them():
    agg = FeatureAggregator(window_s=1)
    for e in churn(1000, closed=False):
        agg.push(e)
    agg.advance(10 ** 15)
    assert len(agg._open) == 1000 and sum(map(len, agg._open.values())) == 1000


def test_cleanup_changes_no_output_against_a_map_that_keeps_empty_entries():
    class KeepsEmpty(FeatureAggregator):
        """The behaviour before T3.4: every client seen keeps an entry for ever."""
        def _apply(self, e):
            client = e.src if e.dport == self._port else e.dst
            seen = self.__dict__.setdefault("seen", set())
            seen.add(client)
            result = super()._apply(e)
            for c in seen:
                self._open.setdefault(c, {})
            return result

    random = Random(4)
    events, t = [], 1.0
    for _ in range(3000):
        t += random.random() * 0.2
        src, port = random.choice((A, C, "10.0.0.3")), random.choice((5000, 5001, 5002))
        choice = random.random()
        kw = {"mqtt": (msg(1, 10, keepalive=random.choice((0, 30, 60, 300))),)} if choice < 0.2 else {"fin": True} if choice < 0.3 else {"rst": True} if choice < 0.35 else {"syn": True} if choice < 0.4 else {}
        events.append(up(t, src=src, port=port, **kw) if random.random() < 0.8 else down(t, dst=src, port=port, **{k: v for k, v in kw.items() if k != "mqtt"}))
    for w in (1, 5, 10):
        keeps = KeepsEmpty(window_s=w)
        now = FeatureAggregator(window_s=w)
        a = [r for e in events for r in keeps.push(e)] + keeps.finish()
        b = [r for e in events for r in now.push(e)] + now.finish()
        assert a == b and len(a) > 0


def test_no_row_for_a_source_without_a_to_broker_packet():
    assert rows([down(1.0, mqtt=(msg(2, 2, connack_code=5),))]) == []
    silent = [up(1.0), down(6.0), up(11.0)]
    agg = FeatureAggregator()
    out = [r for e in silent for r in agg.push(e)] + agg.finish()
    assert [r.window_start_ns for r in out] == [0, 10 * SEC]
    assert agg.stats["reply_only_windows"] == 1


def test_f11_is_not_clamped_when_connack_arrives_without_a_connect():
    f = one([up(1.0), down(1.1, mqtt=(msg(2, 2, connack_code=5), msg(2, 2, connack_code=5), msg(2, 2, connack_code=0)))])
    assert (f["F09"], f["F10"], f["F11"]) == (0, 2, 2.0)


def test_f25_f26_are_per_window_and_count_active_sources_only():
    events = [up(1.0, mqtt=(msg(3),)), up(1.5, src=C, port=6000), down(2.0, dst="10.0.0.3", mqtt=(msg(3),)), up(6.0)]
    out = rows(events)
    assert [(r.source_key, r.as_dict()["F25"], r.as_dict()["F26"]) for r in out] == [(A, 1, 2), (C, 1, 2), (A, 0, 1)]


def test_traffic_not_on_the_broker_port_is_ignored():
    agg = FeatureAggregator()
    agg.push(PacketEvent(ns(1), A, BROKER, 5000, 80))
    assert agg.finish() == [] and agg.stats["ignored_events"] == 1


def test_batch_and_incremental_paths_match():
    events = sorted_scenario() + [up(106.0, mqtt=(msg(3, 1),)), up(112.0)]
    agg = FeatureAggregator()
    incremental = []
    for e in events:
        incremental += agg.push(e)
    incremental += agg.finish()
    assert incremental == rows(events)


def test_live_timer_closes_a_window_with_the_same_features_as_batch():
    events = [up(1.0, mqtt=(msg(3, 4),))]
    agg = FeatureAggregator()
    assert agg.push(events[0]) == []
    assert agg.advance(ns(4.9)) == []
    closed = agg.advance(ns(5.0) + 1_000_000)  # window end plus grace
    assert [r.features for r in closed] == [r.features for r in rows(events)]
    assert agg.finish() == []


def test_empty_input_and_end_of_stream_flags():
    assert rows([]) == []
    assert FeatureAggregator().finish() == []
    events = [up(1.0), up(6.0), up(11.0)]
    assert [r.complete for r in rows(events)] == [False, True, False]  # stream starts and ends inside windows
    with pytest.raises(RuntimeError):
        agg = FeatureAggregator()
        agg.finish()
        agg.push(events[0])


def test_no_sensitive_text_reaches_rows_or_event_repr():
    secret = "SENTINEL-TOPIC"
    event = up(1.0, mqtt=(msg(3, 5, topics=(secret,)), msg(8, 5, topics=(secret + "/#",))))
    assert secret not in repr(event)
    row = rows([event])[0]
    assert secret not in repr(row) and secret not in json.dumps(dataclasses.asdict(row))
    assert {f.name for f in dataclasses.fields(MqttMessage)}.isdisjoint({"payload", "client_id", "username", "password"})
    assert all(isinstance(v, (int, float)) for v in row.features)


def test_source_key_is_excluded_from_features_and_can_be_pseudonymised():
    row = rows([up(1.0)], source_key=lambda ip: "dev-07")[0]
    assert row.source_key == "dev-07" and A not in repr(row)
    assert set(row.as_dict()) == set(FEATURE_IDS)
    assert "source_key" not in row.as_dict()
    assert rows([up(1.0)], source_key=lambda ip: "x")[0].features == rows([up(1.0)])[0].features


def test_rows_in_a_window_are_ordered_by_source_key_not_arrival():
    out = rows([up(1.0, src=C, port=6000), up(1.5, src=A)])
    assert [r.source_key for r in out] == [A, C]


def test_repeated_runs_and_different_hash_seeds_give_identical_output():
    assert rows(sorted_scenario()) == rows(sorted_scenario())
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]);"
        "from ids import *;"
        "m = lambda t: MqttMessage(3, 1, topics=(t,));"
        "e = [PacketEvent(10**9 + i, f'10.0.0.{i % 5}', 'b', 5000 + i, 1883, mqtt=(m(f't{i}'),)) for i in range(50)];"
        "print([(r.source_key, r.features) for r in extract_features(e)])"
    )
    outputs = {
        subprocess.run([sys.executable, "-c", code, SRC], env={**os.environ, "PYTHONHASHSEED": seed},
                       capture_output=True, text=True, check=True).stdout
        for seed in ("1", "2", "3")
    }
    assert len(outputs) == 1 and outputs.pop().startswith("[('10.0.0.0'")


def _held(n, t=0.0):
    """n clients each opening one connection with a keep-alive and never closing it, like a slow-hold attack."""
    return [up(t + i * 1e-4, src=f"10.1.{i // 250}.{i % 250}", port=6000, syn=True) for i in range(n)] + \
        [up(t + 0.5 + i * 1e-4, src=f"10.1.{i // 250}.{i % 250}", port=6000, mqtt=(msg(1, 12, keepalive=600),)) for i in range(n)]


def test_open_connection_cap_bounds_f22_state_and_counts_evictions():
    agg = FeatureAggregator(max_open_connections=100)
    for e in _held(1000):
        agg.push(e)
    agg.advance(ns(20))
    assert agg.open_connections == 100
    assert agg.stats["evicted_connections"] == 900
    assert sum(map(len, agg._open.values())) == 100


def test_open_connection_cap_is_exact_below_the_limit():
    events = _held(50) + [up(12, src="10.1.0.0", port=6000, mqtt=(msg(12),))]  # a later window carries F22 for a held connection
    assert rows(events) == rows(events, max_open_connections=50)
    assert one(events, key="10.1.0.0", start_s=10)["F22"] == 600


def test_unbounded_by_default_for_offline_tables():
    agg = FeatureAggregator()
    for e in _held(500):
        agg.push(e)
    agg.advance(ns(20))
    assert agg.open_connections == 500 and agg.stats["evicted_connections"] == 0


def _silent_then_other_connection(keepalive, later_s):
    """Connection 1 sends CONNECT at 0 and is then silent with no FIN; at later_s the same client uses connection 2."""
    return [up(0, port=6001, syn=True), up(0.1, port=6001, mqtt=(msg(1, 12, keepalive=keepalive),)),
            up(later_s, port=6002, syn=True), up(later_s + 0.1, port=6002, mqtt=(msg(12),))]


def test_keepalive_expiry_drops_a_silent_connection_only_after_its_deadline():
    # K=10, so the deadline is 0.1 + 15 = 15.1 s. Window [10,15) is before it; window [20,25) is after it.
    assert one(_silent_then_other_connection(10, 12), start_s=10, keepalive_expiry=1.5)["F22"] == 10
    assert one(_silent_then_other_connection(10, 21), start_s=20, keepalive_expiry=1.5)["F22"] == 0
    assert one(_silent_then_other_connection(10, 21), start_s=20)["F22"] == 10  # fx-0.1 keeps it


def test_keepalive_expiry_never_expires_keepalive_zero_and_labels_its_rows():
    events = _silent_then_other_connection(0, 500)
    assert one(events, start_s=500, keepalive_expiry=1.5)["F22"] == 0  # K=0 contributes 0 either way
    held = _silent_then_other_connection(0, 500)
    agg = FeatureAggregator(keepalive_expiry=1.5)
    for e in held:
        agg.push(e)
    agg.finish()
    assert agg.stats["expired_keepalive"] == 0
    rows_ = rows(_silent_then_other_connection(10, 21), keepalive_expiry=1.5)
    assert {r.extractor_version for r in rows_} == {"fx-0.1+ka1.5"}
    from ids.pipeline import SchemaError, validate_row
    with pytest.raises(SchemaError):
        validate_row(rows_[0])  # an fx-0.1 model can never receive these rows


def test_keepalive_expiry_bounds_state_under_silent_holds():
    agg = FeatureAggregator(keepalive_expiry=1.5)
    for e in _held(1000):  # every hold declares K=600
        agg.push(e)
    agg.advance(ns(2000))
    agg.push(up(2000, src="10.200.0.1", port=7000, syn=True))  # a later packet closes the windows past the deadline
    agg.advance(ns(2010))
    assert agg.open_connections == 0 and agg.stats["expired_keepalive"] == 1000


def test_keepalive_expiry_rejects_non_positive_factors():
    with pytest.raises(ValueError):
        FeatureAggregator(keepalive_expiry=0)
