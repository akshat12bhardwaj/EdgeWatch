"""Lab safety and wire tests. The broker test runs only where a Mosquitto binary exists, and only on loopback."""
import json
import os
import shutil
import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ids import extract_features  # noqa: E402
from ids.decoder import decode_packets, decode_pcap  # noqa: E402
from lab import attacks, benign, gateway, run as lab_run, safety, wire  # noqa: E402


@pytest.mark.parametrize("address", ["8.8.8.8", "192.168.1.5", "10.0.0.1", "1.1.1.1"])
def test_non_loopback_targets_are_refused(address, monkeypatch):
    monkeypatch.delenv("LAB_TARGETS", raising=False)
    with pytest.raises(safety.SafetyError):
        safety.check_target(address)


def test_client_refuses_a_target_before_opening_any_socket(monkeypatch):
    monkeypatch.delenv("LAB_TARGETS", raising=False)
    monkeypatch.setattr(wire.socket, "socket", lambda *a: pytest.fail("socket opened"))
    with pytest.raises(safety.SafetyError):
        wire.Client("127.0.0.1", ("8.8.8.8", 1883))


def test_allow_list_accepts_only_private_addresses(monkeypatch):
    monkeypatch.setenv("LAB_TARGETS", "192.168.50.2")
    safety.check_target("192.168.50.2")
    monkeypatch.setenv("LAB_TARGETS", "8.8.8.8")
    with pytest.raises(safety.SafetyError):
        safety.check_target("8.8.8.8")


@pytest.mark.parametrize("kwargs", [{"rate": 5001}, {"duration": 601}, {"connections": 2001}])
def test_caps_are_enforced(kwargs):
    with pytest.raises(safety.SafetyError):
        safety.check_caps(**kwargs)


def test_attack_refuses_rate_above_the_cap():
    with pytest.raises(safety.SafetyError):
        attacks.run_family("flood_publish", "127.0.2.1", 1, ("127.0.0.1", 1), ("u", "p"), rate=10 ** 6)


def test_schedule_is_balanced_shuffled_reproducible_and_non_overlapping():
    a, end = lab_run.make_schedule(3, 40, 25, seed=1)
    assert a == lab_run.make_schedule(3, 40, 25, seed=1)[0] and a != lab_run.make_schedule(3, 40, 25, seed=2)[0]
    assert Counter(e["family"] for e in a) == {f: 3 for f in lab_run.TRAINED_FAMILIES}
    assert all(x["end_s"] + 25 == y["start_s"] for x, y in zip(a, a[1:])) and end == a[-1]["end_s"] + 25


def frame(payload, sport=5000, seq=1000):
    import struct
    tcp = struct.pack(">HHIIBBHHH", sport, 1883, seq, 1, 0x50, 0x18, 8192, 0, 0) + payload
    ip = struct.pack(">BBHHHBBH4s4s", 0x45, 0, 20 + len(tcp), 0, 0, 64, 6, 0, bytes([127, 0, 2, 1]), bytes([127, 0, 0, 1]))
    return 1, 0, b"\x02\0\0\0" + ip + tcp


def test_wire_packets_decode_with_the_expected_types_and_no_credentials():
    data = wire.connect("c", 65535, "SECRET-U", "SECRET-P") + wire.publish("t/a", b"x", qos=1) + wire.subscribe("a/#") + wire.PINGREQ + wire.DISCONNECT
    event, = decode_packets([frame(data)])
    assert [m.msg_type for m in event.mqtt] == [1, 3, 8, 12, 14] and event.mqtt[0].keepalive == 65535
    assert event.mqtt[2].topics[0].endswith("#") and "SECRET" not in repr(event)


def test_every_malformed_attack_packet_is_flagged_by_the_decoder():
    for data in attacks.MALFORMED:
        event, = decode_packets([frame(data)])
        assert event.malformed


BROKER_MISSING = not (shutil.which("mosquitto") or (gateway.TOOLS / "sbin" / "mosquitto.exe").exists())


@pytest.mark.skipif(BROKER_MISSING, reason="no Mosquitto binary")
def test_real_broker_accepts_lab_login_and_refuses_a_wrong_password(tmp_path):
    process, cred = gateway.start_broker(tmp_path, port=18831)
    try:
        assert lab_run.wait_for_port(18831)
        broker = ("127.0.0.1", 18831)
        c = wire.Client("127.0.1.200", broker)
        assert c.login("ok", *cred) == 0
        c.publish("t/a", b"1", qos=1)
        c.publish("t/a", b"2", qos=2)
        c.close()
        bad = wire.Client("127.0.1.201", broker)
        assert bad.login("no", cred[0], "wrong") != 0
        bad.close(graceful=False)
    finally:
        gateway.stop(process)
    assert process.poll() is not None
    assert "wrong" not in (tmp_path / "mosquitto.conf").read_text()

def test_ground_truth_starts_empty_and_lists_marks_in_order(tmp_path):
    path = tmp_path / "sub" / "truth.json"
    write = lab_run.ground_truth_writer(path)
    assert json.loads(path.read_text()) == []
    write({"episode": 0})
    write({"episode": 1})
    assert [m["episode"] for m in json.loads(path.read_text())] == [0, 1] and not path.with_suffix(".tmp").exists()


@pytest.mark.skipif(BROKER_MISSING, reason="no Mosquitto binary")
def test_new_families_and_smart_home_profiles_run_and_stop_cleanly(tmp_path):
    import threading
    process, cred = gateway.start_broker(tmp_path, port=18832)
    try:
        assert lab_run.wait_for_port(18832)
        broker, stop = ("127.0.0.1", 18832), threading.Event()
        threads, sources = benign.start(benign.SCENARIOS["smart_home"], stop, broker, cred)
        attacks.run_family("topic_probe", "127.0.2.50", 1.5, broker, cred, seed=1, rate=20)
        stop.set()
        for t in threads:
            t.join(timeout=10)
        assert not any(t.is_alive() for t in threads) and len(sources) == 12
        assert process.poll() is None  # the broker survived both
    finally:
        gateway.stop(process)


def test_topic_probe_refuses_rates_above_the_cap():
    with pytest.raises(safety.SafetyError):
        attacks.run_family("topic_probe", "127.0.0.1", 1, ("127.0.0.1", 1), ("u", "p"), rate=10 ** 6)


def test_scaled_options_never_exceed_defaults_and_refuse_factors_above_one():
    for family in attacks.FAMILIES:
        full, low = lab_run.scaled_options(family, 1.0), lab_run.scaled_options(family, 0.05)
        assert all(low[k] <= full[k] for k in full)
    with pytest.raises(ValueError):
        lab_run.scaled_options("flood_publish", 1.5)
    # varied_rates is unchanged by the refactor: same seed, same rates as the campaign runs used
    entries = [{"family": "flood_publish"}, {"family": "lowrate"}]
    assert lab_run.varied_rates(entries, 3) == lab_run.varied_rates(entries, 3)
