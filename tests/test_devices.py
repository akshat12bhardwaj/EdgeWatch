"""Smart Home software devices (lab/devices.py): each model's behaviour, then all nine types live on a real Mosquitto
(isolated port 18961) with the telemetry reader, commands acknowledged over MQTT, removal, reconnection and recovery."""
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from lab import devices, gateway, home, wire  # noqa: E402
from test_home import BROKER_MISSING, PORT, home_broker, wait_for  # noqa: E402,F401  (fixture)


def run(model, seconds, step=1.0):
    events = []
    for _ in range(int(seconds / step)):
        events += model.tick(step, 0)[1]
    return events


def test_light_door_and_camera_apply_only_valid_commands():
    light = devices.Light()
    assert light.apply({"on": True}, 0)[0] and light.state["on"] and not light.apply({"on": "yes"}, 0)[0]
    door = devices.Door()
    changed, events = door.apply({"open": True}, 5)
    assert changed and door.state == {"open": True, "changed": 5} and events == [{"event": "opened"}]
    cam = devices.Camera()
    assert cam.apply({"simulate_motion": True}, 1)[1] == [{"event": "motion"}] and cam.state["motion_events"] == 1
    cam.apply({"monitoring": False}, 2)
    assert cam.apply({"simulate_motion": True}, 3)[1] == [] and cam.state["motion_events"] == 1  # paused: no events


def test_motion_clears_by_itself_after_its_interval():
    m = devices.Motion()
    m.apply({"clear_after_s": 3}, 0)
    assert m.apply({"trigger": True}, 0)[1] == [{"event": "motion"}] and m.state["motion"]
    run(m, 2)
    assert m.state["motion"]
    run(m, 2)
    assert not m.state["motion"]
    assert m.apply({"clear_after_s": 1000}, 0) == (False, [])  # out of range


def test_lock_keeps_lock_state_and_access_attempts_apart():
    lock = devices.Lock()
    lock.apply({"attempt": "wrong"}, 1)
    lock.apply({"attempt": "wrong"}, 2)
    assert lock.state["locked"] and lock.state["failed_attempts"] == 2 and lock.state["last_attempt"]["result"] == "rejected"
    _, events = lock.apply({"attempt": "correct"}, 3)
    assert not lock.state["locked"] and lock.state["failed_attempts"] == 0 and events[-1]["result"] == "accepted"
    assert lock.apply({"locked": True}, 4)[1] == [{"event": "locked"}]


def test_plug_power_and_energy_are_deterministic():
    plug = devices.Plug()
    plug.apply({"appliance_w": 1200}, 0)
    assert plug.state["power_w"] == 0.4
    plug.apply({"on": True}, 0)
    run(plug, 36)
    assert plug.state["power_w"] == 1200 and abs(plug.state["energy_wh"] - 12.0) < 0.05  # 1.2 kW for 36 s


def test_thermostat_heats_to_target_then_idles():
    t = devices.Thermostat({"current": 18.0})
    t.apply({"target": 20}, 0)
    assert t.state["mode"] == "heating"
    run(t, 30)
    assert t.state["mode"] == "heating" and 19.4 < t.state["current"] < 19.6
    run(t, 20)
    assert t.state["mode"] == "idle" and 19.7 <= t.state["current"] <= 20.3
    t.apply({"target": 15}, 0)
    assert t.state["mode"] == "cooling" and t.apply({"target": 99}, 0) == (False, [])


def test_smoke_alarm_latches_at_threshold_until_reset():
    s = devices.Smoke()
    s.apply({"threshold": 40}, 0)
    s.apply({"smoke": True}, 0)
    events = run(s, 6)
    assert s.state["alarm"] and s.state["level"] >= 40 and [e["event"] for e in events] == ["alarm"]
    assert s.apply({"reset": True}, 0)[1] == [{"event": "reset"}] and s.state == {"level": 0.0, "threshold": 40, "alarm": False, "smoke": False}


def test_climate_follows_room_conditions_gradually():
    c = devices.Climate()
    c.apply({"room_temperature": 25, "room_humidity": 60}, 0)
    run(c, 5)
    assert c.state["temperature"] == 22.0 and c.state["humidity"] == 50.0
    run(c, 30)
    assert c.state["temperature"] == 25 and c.state["humidity"] == 60


def test_atomic_write_survives_a_reader_holding_the_file(tmp_path):
    # Regression: on Windows the API reading telemetry.json made replace() fail, and the uncaught error killed the reader thread.
    target = tmp_path / "telemetry.json"
    target.write_text("old")
    held = open(target)  # an open handle blocks replacement on Windows
    threading.Timer(0.08, held.close).start()
    assert devices.atomic_write(target, "new") and target.read_text() == "new"
    held = open(target)
    try:
        result = devices.atomic_write(target, "newer", tries=3)  # still held: must not raise
        assert result is (sys.platform != "win32")
    finally:
        held.close()


def test_host_forgets_state_of_devices_no_longer_in_the_layout(tmp_path):
    # Regression: a removed device's saved state stayed on disk and a new device with a reused id inherited it.
    (tmp_path / "device-state.json").write_text(json.dumps({"gone": {"room_temperature": 27}}))
    (tmp_path / "layout.json").write_text(json.dumps({"devices": []}))
    host = devices.DeviceHost(1, ("u", "p"), tmp_path / "layout.json", tmp_path, None, log=lambda *_: None)
    host.reconcile()
    assert host.saved == {} and host._dirty


def test_saved_state_survives_only_for_known_fields():
    assert devices.Light({"on": True, "evil": 1}).state == {"on": True}


# Live, on a real broker ---------------------------------------------------------------------------------------------------------------
LAYOUT = [("l1", "light"), ("l2", "light"), ("m1", "motion"), ("c1", "climate"), ("d1", "door"), ("k1", "lock"), ("v1", "camera"), ("p1", "plug"), ("t1", "thermostat"), ("s1", "smoke")]


def write_layout(entries):
    body = {"devices": [{"id": i, "name": i, "type": t, "room": "living", "x": 100, "y": 100, "source": "software"} for i, t in entries]}
    (home.HOME / "layout.json").write_text(json.dumps(body))


@pytest.mark.integration
@pytest.mark.skipif(BROKER_MISSING, reason="no Mosquitto binary")
def test_all_nine_devices_live_commands_removal_and_recovery(home_broker, tmp_path):
    write_layout(LAYOUT)
    labels = tmp_path / "devices.json"
    stop = threading.Event()
    reader = home.Bridge(PORT, home_broker["bridge"], Path(home_broker["telemetry"]), layout=home.HOME / "layout.json")
    host = devices.DeviceHost(PORT, home_broker["host"], home.HOME / "layout.json", home.HOME, labels, log=lambda *_: None)
    threading.Thread(target=reader.run, args=(stop,), daemon=True).start()
    threading.Thread(target=host.run, args=(stop,), daemon=True).start()
    state = lambda i: (reader.devices.get(i) or {}).get("state") or {}

    def command(device_id, body):
        cmd_id = f"c{time.monotonic_ns() % 10 ** 8}"
        assert home.send_command(PORT, home_broker["bridge"], device_id, {**body, "cmd_id": cmd_id})
        assert wait_for(lambda: state(device_id).get("ack") == cmd_id, 6), (device_id, body, state(device_id))
        return state(device_id)

    try:
        # Creation and MQTT connection: every device online with its own state, from its own address.
        assert wait_for(lambda: all(state(i).get("type") == t and reader.devices[i]["status"] == "online" for i, t in LAYOUT), 10)
        assert len({host.clients[i].source for i, _ in LAYOUT}) == len(LAYOUT)
        assert {v for v in json.loads(labels.read_text()).values()} == {f"{t}@{i}" for i, t in LAYOUT}
        # Controls, each acknowledged by the device's own next state.
        assert command("l1", {"on": True})["on"] and not state("l2")["on"]  # two lights, independent
        assert command("d1", {"open": True})["open"]
        assert not command("k1", {"attempt": "correct"})["locked"] and command("k1", {"locked": True})["locked"]
        assert command("v1", {"simulate_motion": True})["motion_events"] == 1 and reader.devices["v1"]["events"][0]["event"] == "motion"
        assert command("p1", {"on": True, "appliance_w": 100})["power_w"] == 100
        assert command("t1", {"target": 25})["mode"] == "heating"
        assert command("m1", {"clear_after_s": 2, "trigger": True})["motion"]
        assert wait_for(lambda: state("m1")["motion"] is False, 6)  # clears by itself
        command("s1", {"threshold": 10, "smoke": True})
        assert wait_for(lambda: state("s1").get("alarm") is True, 6) and any(e["event"] == "alarm" for e in reader.devices["s1"]["events"])
        assert command("s1", {"reset": True})["level"] == 0
        command("c1", {"room_temperature": 23})
        assert wait_for(lambda: state("c1")["temperature"] >= 21.4, 6)
        # The lab (attack) account cannot command a device: the ACL drops it, so no ack and no change.
        lab = wire.Client("127.0.2.90", ("127.0.0.1", PORT))
        lab.login("attacker", *home_broker["lab"])
        lab.publish(f"{devices.PREFIX}d1/command", json.dumps({"open": False, "cmd_id": "evil"}).encode(), qos=1)
        lab.close()
        time.sleep(1.5)
        assert state("d1")["open"] and state("d1")["ack"] != "evil"
        # Removal stops the client and clears its retained topics.
        write_layout([e for e in LAYOUT if e[0] != "l2"])
        assert wait_for(lambda: "l2" not in host.clients and "l2" not in reader.devices, 8)
        probe = wire.Client("127.0.3.50", ("127.0.0.1", PORT), timeout=1.5)
        probe.login("probe", *home_broker["bridge"])
        probe.send(wire.subscribe(f"{devices.PREFIX}l2/state"))
        probe.receive()  # SUBACK
        with pytest.raises(OSError):  # nothing retained for a removed device
            probe.receive()
        probe.close()
        # Reconnection: the broker goes away and comes back; every device returns.
        broker_pids = [p for p in __import__("psutil").process_iter(["name", "cmdline"]) if p.info["name"] and "mosquitto" in p.info["name"].lower() and str(home.HOME) in " ".join(p.info["cmdline"] or [])]
        for p in broker_pids:
            p.kill()
        time.sleep(1)
        broker = subprocess.Popen([gateway.find("mosquitto", "sbin"), "-c", str(home.HOME / "mosquitto.conf")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            assert wait_for(lambda: all(c.connected for c in host.clients.values()), 15)
            assert wait_for(lambda: state("l1").get("on") is True and reader.devices["l1"]["status"] == "online", 10)
        finally:
            stop.set()
            time.sleep(3)
            # Recovery: a new host restores each device's last state from disk.
            again = devices.DeviceHost(PORT, home_broker["host"], home.HOME / "layout.json", home.HOME, None, log=lambda *_: None)
            again.reconcile()
            try:
                assert again.clients["l1"].model.state["on"] is True and again.clients["p1"].model.state["appliance_w"] == 100
                assert again.clients["l1"].source == host.clients["l1"].source  # same identity after restart
            finally:
                for c in again.clients.values():
                    c.stop()
                broker.kill()
                broker.wait()
    finally:
        stop.set()
