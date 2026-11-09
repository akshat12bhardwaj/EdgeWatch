"""IDS service: replay path on an invented capture, model failure, provenance, and a real broker-and-capture path where available."""
import json
import shutil
import sqlite3
import struct
import subprocess
import sys
import threading
import time
from collections import Counter
from pathlib import Path

import pytest

from ids import FEATURE_IDS
from ids.detector import ModelRefused
from ids.pipeline import pseudonymizer
from ids.service import Pipeline, build_parser, dumpcap_command, load_detector, run_replay
from ids.store import EventStore, connect
from ids.features import MqttMessage, PacketEvent

SECRET = b"SECRET-TOPIC-VALUE"


def write_capture(path, seconds=30, rate=4):
    data = bytes([0x30, 2 + len(SECRET)]) + struct.pack(">H", len(SECRET)) + SECRET
    out = struct.pack("<IHHiIII", 0xa1b2c3d4, 2, 4, 0, 0, 65535, 1)
    seq = 1000
    for i in range(seconds * rate):
        tcp = struct.pack(">HHIIBBHHH", 5000, 1883, seq, 1, 0x50, 0x18, 8192, 0, 0) + data
        seq += len(data)
        ip = struct.pack(">BBHHHBBH4s4s", 0x45, 0, 20 + len(tcp), 0, 0, 64, 6, 0, bytes([192, 168, 7, 7]), bytes([192, 0, 2, 9]))
        frame = b"\x02" * 6 + b"\x04" * 6 + b"\x08\x00" + ip + tcp
        out += struct.pack("<IIII", 1000 + i // rate, (i % rate) * 1000, len(frame), len(frame)) + frame
    path.write_bytes(out)
    return path


class AlwaysAttack:
    model_id, tau = "fake", 0.5

    def score(self, features):
        return "flood", 0.95

    def explain(self, features, predicted_class):
        return [{"feature": "F12", "value": features[11], "baseline_p50": 1.0, "contribution": 0.4}]


class Broken(AlwaysAttack):
    def score(self, features):
        raise ValueError("model broke")



@pytest.fixture(autouse=True)
def _close_stores(monkeypatch):
    """Close every EventStore a test opens (directly or through replay()), so no connection is left to the garbage collector."""
    made, real = [], EventStore.__init__

    def init(self, *args, **kwargs):
        real(self, *args, **kwargs)
        made.append(self)
    monkeypatch.setattr(EventStore, "__init__", init)
    yield
    for store in made:
        store.db.close()

def replay(tmp_path, detector, **overrides):
    args = build_parser().parse_args(["--db", str(tmp_path / "e.sqlite"), "--replay", str(write_capture(tmp_path / "c.pcap"))])
    for k, v in overrides.items():
        setattr(args, k, v)
    store = EventStore(args.db, "run1", "replay")
    pipeline, stats = run_replay(args, store, detector, pseudonymizer())
    return store, pipeline, stats


def rows(store, kind):
    return [json.loads(r["body"]) for r in store.db.execute("SELECT body FROM events WHERE event_type=? ORDER BY id", (kind,))]


def test_replay_writes_windows_and_alerts_with_replay_provenance(tmp_path):
    store, pipeline, _ = replay(tmp_path, AlwaysAttack())
    windows, alerts = rows(store, "window"), rows(store, "alert")
    assert len(windows) == 6 and windows[0]["features"]["F12"] == 20 and alerts
    assert {e["provenance"] for e in windows + alerts} == {"replay"} and windows[0]["extractor_version"] == "fx-0.1"
    assert alerts[0]["status"] == "unverified_prediction" and alerts[0]["evidence"][0]["feature"] == "F12" and alerts[0]["model_id"] == "fake"
    assert [w["state"] for w in windows[:3]] == ["suspicious", "alert", "alert"]


def test_no_raw_identity_or_topic_reaches_the_store(tmp_path):
    store, _, _ = replay(tmp_path, AlwaysAttack())
    dump = "\n".join(store.db.iterdump())
    assert "192.168.7.7" not in dump and SECRET.decode() not in dump


def test_broken_model_never_stops_monitoring(tmp_path):
    store, pipeline, _ = replay(tmp_path, Broken())
    windows = rows(store, "window")
    assert len(windows) == 6 and pipeline.model_errors == 6 and windows[0]["prediction"] is None and not rows(store, "alert")


def test_missing_model_runs_in_feature_only_mode(tmp_path):
    assert load_detector(str(tmp_path / "no-model")) is None and load_detector(None) is None
    store, pipeline, _ = replay(tmp_path, None)
    windows = rows(store, "window")
    assert len(windows) == 6 and windows[0]["model_id"] is None and windows[0]["state"] == "normal"


def test_store_failure_does_not_stop_the_pipeline(tmp_path):
    store = EventStore(tmp_path / "e.sqlite", "r", "live")
    store.db.close()
    pipeline = Pipeline(store, AlwaysAttack(), 5, 1883, pseudonymizer())
    for t in range(0, 30):
        pipeline.handle_event(PacketEvent(t * 10 ** 9, "10.0.0.1", "10.0.0.2", 5000, 1883, mqtt=(MqttMessage(3, 5),)))
    pipeline.finish()
    assert pipeline.counters["windows"] == 6 and store.write_errors >= 6


def test_schedule_marks_status_and_never_stores_raw_source(tmp_path):
    key = pseudonymizer()
    schedule = tmp_path / "schedule.json"
    schedule.write_text(json.dumps([{"source": "10.0.0.1", "family": "flood", "episode": 0, "start_epoch": 0, "end_epoch": 100}]))
    store = EventStore(tmp_path / "e.sqlite", "r", "live")
    pipeline = Pipeline(store, AlwaysAttack(), 5, 1883, key, schedule)
    for t in range(0, 20):
        pipeline.handle_event(PacketEvent(t * 10 ** 9, "10.0.0.1", "10.0.0.2", 5000, 1883, mqtt=(MqttMessage(3, 5),)))
    pipeline.finish()
    alert = rows(store, "alert")[0]
    marker = rows(store, "run_marker")[0]
    assert alert["status"] == "matches_scheduled_attack" and rows(store, "window")[0]["ground_truth"] == "flood"
    assert marker["source_key"] == key("10.0.0.1") and "10.0.0.1" not in "\n".join(store.db.iterdump())


def test_corrupt_schedule_is_counted_not_fatal(tmp_path):
    schedule = tmp_path / "schedule.json"
    schedule.write_text("{not json")
    store = EventStore(tmp_path / "e.sqlite", "r", "live")
    pipeline = Pipeline(store, AlwaysAttack(), 5, 1883, pseudonymizer(), schedule)
    assert pipeline.schedule() is None and pipeline.counters["schedule_read_errors"] == 1


def test_capture_command_is_read_only_and_filtered_to_the_mqtt_port():
    command = dumpcap_command("eth0", 1883, "dumpcap")
    assert command[command.index("-f") + 1] == "tcp port 1883" and command[command.index("-w") + 1] == "-"


def test_service_module_has_no_way_to_write_to_the_network():
    source = (Path(__file__).resolve().parents[1] / "src" / "ids" / "service.py").read_text()
    assert "import socket" not in source and ".send(" not in source and "connect(" not in source.replace("connect(path", "")


def test_live_timer_trails_capture_so_packets_in_the_pipe_are_not_dropped(tmp_path):
    store = EventStore(tmp_path / "e.sqlite", "r", "live")
    pipeline = Pipeline(store, AlwaysAttack(), 5, 1883, pseudonymizer())
    now = 1000 * 10 ** 9
    pipeline.tick(now)
    in_transit = PacketEvent(now - 500_000_000, "10.0.0.1", "10.0.0.2", 5000, 1883, mqtt=(MqttMessage(3, 5),))
    pipeline.handle_event(in_transit)
    pipeline.finish()
    assert pipeline.aggregator.stats["late_events"] == 0
    assert rows(store, "window")[0]["features"]["F12"] == 1

def test_devices_and_repeated_episode_numbers_are_announced_pseudonymized(tmp_path):
    key = pseudonymizer()
    schedule = tmp_path / "ground_truth.json"
    (tmp_path / "devices.json").write_text(json.dumps({"127.0.1.10": "temp_humidity"}))
    schedule.write_text(json.dumps([{"source": "127.0.2.10", "family": "bruteforce", "episode": 0, "start_epoch": 0, "end_epoch": 50}]))
    store = EventStore(tmp_path / "e.sqlite", "r", "live")
    pipeline = Pipeline(store, AlwaysAttack(), 5, 1883, key, schedule)
    pipeline.schedule()
    import os
    schedule.write_text(json.dumps([{"source": "127.0.2.10", "family": "flood_publish", "episode": 0, "start_epoch": 100, "end_epoch": 150}]))
    os.utime(schedule, (time.time() + 5, time.time() + 5))
    pipeline.schedule()
    markers = rows(store, "run_marker")
    assert [m["family"] for m in markers if m["marker"] == "scheduled_attack"] == ["bruteforce", "flood_publish"]
    devices = [m for m in markers if m["marker"] == "scenario_devices"]
    assert devices[0]["devices"] == {key("127.0.1.10"): "temp_humidity"}
    assert "127.0.1.10" not in "\n".join(store.db.iterdump())


def test_per_source_state_is_bounded_under_source_churn(tmp_path):
    store = EventStore(tmp_path / "e.sqlite", "r", "live")
    pipeline = Pipeline(store, AlwaysAttack(), 5, 1883, pseudonymizer())
    for t in range(0, 1500, 5):  # 300 windows, a new client each window, as with connection churn from many hosts
        pipeline.handle_event(PacketEvent(t * 10 ** 9, f"10.9.{t // 250}.{t % 250}", "10.0.0.2", 5000, 1883, mqtt=(MqttMessage(3, 5),)))
    pipeline.finish()
    assert len(pipeline.engine.sources) <= 15  # suppression (60 s) plus one window, 5 s apart
    assert len(pipeline.last_seen) <= 125  # 600 s display retention
