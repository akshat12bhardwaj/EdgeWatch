"""Wokwi smart home: topic contract, telemetry validation, the bridge, ACL isolation, light control and attach-mode lab runs.

The broker tests start a real Mosquitto on an isolated loopback port (18961) and stand in for the ESP32 with a raw client
using the firmware's account and topics. They test Edge Watch's side of the contract, not the Wokwi simulator.
"""
import json
import shutil
import socket
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from lab import benign, gateway, home, run as lab_run, wire  # noqa: E402

PORT = 18961
BROKER_MISSING = not Path(gateway.find("mosquitto", "sbin")).exists() and not shutil.which("mosquitto")


def test_topics_and_serial_protocol_match_the_firmware():
    source = (ROOT / "simulators" / "wokwi-smart-home" / "src" / "main.cpp").read_text()
    assert r'"EW1 %s %s\n"' in source and 'strncmp(line, "EW1 light ", 10)' in source
    for field in home.SERIAL_FIELDS:
        assert f'"{field}"' in source
    assert '"edgewatch/home/light/set"' in source and '"edgewatch/home/device/status"' in source
    for topic in ("temperature", "humidity", "motion", "light/state", "device/status"):
        assert f"topic write {home.PREFIX}{topic}" in home.ACL


@pytest.mark.parametrize("topic,payload,expected", [
    ("temperature", b"22.5", ("temperature", 22.5)), ("humidity", b" 45 ", ("humidity", 45.0)),
    ("motion", b"1", ("motion", True)), ("motion", b"0", ("motion", False)),
    ("light/state", b"on", ("light", True)), ("light/state", b"OFF", ("light", False)),
    ("device/status", b"online", ("status", "online")), ("device/status", b"offline", ("status", "offline")),
])
def test_valid_telemetry_is_parsed(topic, payload, expected):
    assert home.parse(home.PREFIX + topic, payload) == expected


@pytest.mark.parametrize("topic,payload", [
    ("temperature", b"nan-ish"), ("temperature", b"120"), ("temperature", b"-41"), ("humidity", b"101"), ("humidity", b"\xff"),
    ("motion", b"yes"), ("light/state", b"dim"), ("device/status", b"rebooting"), ("light/set", b"ON"), ("other", b"1"),
])
def test_invalid_telemetry_is_rejected_not_coerced(topic, payload):
    assert home.parse(home.PREFIX + topic, payload) is None
    assert home.parse("sensor/x/" + topic, b"1") is None


def test_bridge_keeps_latest_valid_values_and_counts_rejects(tmp_path):
    clock = iter([100, 101, 102, 103, 104]).__next__
    bridge = home.Bridge(1, ("u", "p"), tmp_path / "t.json", clock=clock)
    assert bridge.handle(home.PREFIX + "temperature", b"21.0") and bridge.handle(home.PREFIX + "temperature", b"21.5")
    assert not bridge.handle(home.PREFIX + "temperature", b"999") and not bridge.handle(home.PREFIX + "light/set", b"ON")
    bridge.write()
    body = json.loads((tmp_path / "t.json").read_text())
    assert body["values"]["temperature"] == {"value": 21.5, "ts": 101} and body["rejected"] == 1


def test_publish_parts_reads_a_qos0_publish():
    packet = wire.publish(home.PREFIX + "motion", b"1")
    assert home.publish_parts(packet[2:]) == (home.PREFIX + "motion", b"1")


def test_wokwi_sources_are_not_lab_sources():
    assert {"127.0.0.1", "::1"} <= set(home.DEVICES) and home.DEVICES["127.0.0.1"] == "wokwi_esp32"
    assert all(not s.startswith(("127.0.1.", "127.0.2.")) for s in home.DEVICES)  # lab benign and attack ranges
    assert benign.SCENARIOS["wokwi_only"] == ()


@pytest.fixture
def home_broker(tmp_path, monkeypatch):
    firmware = tmp_path / "fw"
    (firmware / "include").mkdir(parents=True)
    shutil.copy(ROOT / "simulators" / "wokwi-smart-home" / "include" / "secrets.example.h", firmware / "include")
    monkeypatch.setattr(home, "HOME", tmp_path / "home")
    monkeypatch.setattr(home, "FIRMWARE", firmware)
    state = home.init(PORT)
    import subprocess
    broker = subprocess.Popen([gateway.find("mosquitto", "sbin"), "-c", str(home.HOME / "mosquitto.conf")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert lab_run.wait_for_port(PORT), (home.HOME / "mosquitto.log").read_text() if (home.HOME / "mosquitto.log").exists() else "no log"
    yield state
    gateway.stop(broker)


def device(state, source="127.0.0.1"):
    """Stands in for the ESP32: its account, its topics."""
    cred = json.loads((home.HOME / "credentials.json").read_text())
    c = wire.Client(source, ("127.0.0.1", PORT), timeout=5)
    assert c.login("wokwi-esp32-home", home.DEVICE_USER, cred[home.DEVICE_USER]) == 0
    return c


def wait_for(predicate, seconds=5):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


@pytest.mark.integration
@pytest.mark.skipif(BROKER_MISSING, reason="no Mosquitto binary")
def test_init_writes_firmware_secrets_for_the_port(home_broker):
    text = (home.FIRMWARE / "include" / "secrets.h").read_text()
    cred = json.loads((home.HOME / "credentials.json").read_text())
    assert f"EW_MQTT_PORT {PORT}" in text and cred[home.DEVICE_USER] in text and "host.wokwi.internal" in text
    assert home.init(PORT)["bridge"] == home_broker["bridge"]  # idempotent: credentials survive a second init


@pytest.mark.integration
@pytest.mark.skipif(BROKER_MISSING, reason="no Mosquitto binary")
def test_bridge_sees_device_telemetry_but_not_spoofed_lab_publishes(home_broker):
    bridge, stop = home.Bridge(PORT, home_broker["bridge"], Path(home_broker["telemetry"])), threading.Event()
    threading.Thread(target=bridge.run, args=(stop,), daemon=True).start()
    try:
        assert wait_for(lambda: bridge.connected)
        esp = device(home_broker)
        esp.publish(home.PREFIX + "device/status", b"online", retain=True)
        esp.publish(home.PREFIX + "temperature", b"22.5")
        assert wait_for(lambda: bridge.values.get("temperature", {}).get("value") == 22.5)
        lab = wire.Client("127.0.2.77", ("127.0.0.1", PORT))
        assert lab.login("attacker", *home_broker["lab"]) == 0
        lab.publish(home.PREFIX + "temperature", b"30.0", qos=1)  # the ACL drops it; Mosquitto still acks
        lab.close()
        esp.publish(home.PREFIX + "humidity", b"40.0")
        assert wait_for(lambda: "humidity" in bridge.values)
        assert bridge.values["temperature"]["value"] == 22.5 and bridge.values["status"]["value"] == "online"
        esp.close()
        on_disk = json.loads(Path(home_broker["telemetry"]).read_text())
        assert on_disk["bridge_connected"] and on_disk["values"]["humidity"]["value"] == 40.0
    finally:
        stop.set()


@pytest.mark.integration
@pytest.mark.skipif(BROKER_MISSING, reason="no Mosquitto binary")
def test_light_command_reaches_the_device_and_only_the_bridge_may_send_it(home_broker):
    esp = device(home_broker)
    esp.send(wire.subscribe(home.PREFIX + "light/set", qos=0))
    esp.receive()  # SUBACK
    assert home.send_light(PORT, home_broker["bridge"], True)
    head, body = esp.receive()
    assert head >> 4 == 3 and home.publish_parts(body) == (home.PREFIX + "light/set", b"ON")
    lab = wire.Client("127.0.2.78", ("127.0.0.1", PORT))
    lab.login("attacker", *home_broker["lab"])
    lab.publish(home.PREFIX + "light/set", b"OFF")
    lab.close()
    esp.sock.settimeout(1)
    with pytest.raises(socket.timeout):
        esp.receive()  # the lab account cannot switch the light
    esp.close()


@pytest.mark.integration
@pytest.mark.skipif(BROKER_MISSING, reason="no Mosquitto binary")
def test_attached_lab_run_shares_the_broker_and_leaves_it_running(home_broker, tmp_path):
    esp = device(home_broker)
    written = {}
    marks, sources = lab_run.run(tmp_path / "lab", [], 3, ("steady",), PORT, capture=False, scenario="attach-test", attach=home_broker, on_devices=written.update)
    assert len(sources) == 1 and lab_run.wait_for_port(PORT, 1)
    assert json.loads((tmp_path / "lab" / "manifest.json").read_text())["broker_alive_at_end"]
    esp.publish(home.PREFIX + "motion", b"1")  # the ESP32's session survived the lab run
    esp.close()


@pytest.mark.integration
@pytest.mark.skipif(BROKER_MISSING, reason="no Mosquitto binary")
def test_broker_also_listens_on_ipv6_loopback(home_broker):
    try:
        with socket.create_connection(("::1", PORT), timeout=2):
            pass
    except OSError as error:
        pytest.skip(f"no IPv6 loopback here: {error}")


def test_edge_watch_own_clients_never_look_like_the_device_or_an_indicator():
    # A "#" subscription is what the IDS's wildcard rule flags; probes must not come from the gateway's 127.0.0.1.
    assert all("#" not in t and "+" not in t for t in home.TELEMETRY_TOPICS)
    assert home.DEVICES[home.PROBE_SOURCE] == "edgewatch_bridge" and not home.PROBE_SOURCE.startswith("127.0.0.")
    assert set(home.TELEMETRY_TOPICS) == {"temperature", "humidity", "motion", "light/state", "device/status"}


# Serial bridge (free Wokwi path) -----------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("line,expected", [
    (b"EW1 temperature 22.5\n", (home.PREFIX + "temperature", b"22.5")), (b"EW1 motion 1\r\n", (home.PREFIX + "motion", b"1")),
    (b"EW1 light OFF\n", (home.PREFIX + "light/state", b"OFF")), (b"EW1 status online\n", (home.PREFIX + "device/status", b"online")),
])
def test_valid_serial_lines_map_to_topics(line, expected):
    assert home.parse_line(line) == expected


@pytest.mark.parametrize("line", [b"EW1 temperature 999\n", b"EW1 temperature\n", b"EW2 motion 1\n", b"EW1 door open\n", b"EW1 motion 1 extra\n",
                                  b"Edge Watch virtual smart home starting\n", b"\xff\xfe\n", b"EW1 humidity " + b"9" * 80 + b"\n"])
def test_invalid_serial_lines_are_rejected(line):
    assert home.parse_line(line) is None


def test_serial_bridge_announces_online_rate_limits_and_maps_commands():
    t = [0.0]
    out = []
    b = home.SerialBridge("x", 1, ("u", "p"), clock=lambda: t[0], log=lambda *_: None)
    assert b.handle_line(b"EW1 temperature 21.0\n", lambda *a: out.append(a))
    assert out[0] == (home.PREFIX + "device/status", b"online", True) and out[1] == (home.PREFIX + "temperature", b"21.0", False)
    for _ in range(home.MAX_PER_S + 5):
        b.handle_line(b"EW1 motion 1\n", lambda *a: None)
    assert b.stats["dropped"] == 6  # 1 + 25 lines in one second, 20 allowed
    t[0] = 2.0
    assert b.handle_line(b"EW1 motion 0\n", lambda *a: None)
    assert not b.handle_line(b"EW1 motion maybe\n", lambda *a: None) and b.stats["rejected"] == 1
    assert home.SerialBridge.command_line(b"on") == b"EW1 light ON\n" and home.SerialBridge.command_line(b"0") == b"EW1 light OFF\n"
    assert home.SerialBridge.command_line(b"EW1 light ON\nEW1 reboot") is None


class ScriptedSerial:
    """Stands in for Wokwi's RFC2217 port in this test only: lines the firmware would print, and a record of what is written."""

    def __init__(self, lines):
        self.lines, self.written, self.closed = list(lines), [], False

    def readline(self, size):
        if self.lines:  # like pyserial: an over-long line comes back in size-limited pieces
            line = self.lines.pop(0)
            if len(line) > size:
                self.lines.insert(0, line[size:])
            return line[:size]
        time.sleep(0.05)
        return b""

    def write(self, data):
        self.written.append(data)

    def close(self):
        self.closed = True


@pytest.mark.integration
@pytest.mark.skipif(BROKER_MISSING, reason="no Mosquitto binary")
def test_serial_bridge_end_to_end_through_the_broker(home_broker):
    cred = (home.DEVICE_USER, json.loads((home.HOME / "credentials.json").read_text())[home.DEVICE_USER])
    reader, stop = home.Bridge(PORT, home_broker["bridge"], Path(home_broker["telemetry"])), threading.Event()
    threading.Thread(target=reader.run, args=(stop,), daemon=True).start()
    lines = [b"Edge Watch virtual smart home starting\n", b"EW1 status online\n", b"EW1 light OFF\n", b"EW1 temperature 23.4\n",
             b"EW1 humi", b"dity 51.0\n",  # split by a read timeout, as happens on a real serial link
             b"x" * 200 + b"\n", b"EW1 motion 1\n"]
    port_ = ScriptedSerial(lines)
    bridge = home.SerialBridge("scripted", PORT, cred, open_serial=lambda url: port_, log=lambda *_: None)
    session_stop = threading.Event()
    worker = threading.Thread(target=bridge.session, args=(session_stop,), daemon=True)
    try:
        assert wait_for(lambda: reader.connected)
        worker.start()
        assert wait_for(lambda: reader.values.get("motion", {}).get("value") is True)
        assert reader.values["temperature"]["value"] == 23.4 and reader.values["status"]["value"] == "online" and reader.values["light"]["value"] is False
        assert reader.values["humidity"]["value"] == 51.0  # reassembled from two reads
        assert bridge.stats["rejected"] == 1  # the over-long line
        assert home.send_light(PORT, home_broker["bridge"], True)
        assert wait_for(lambda: b"EW1 light ON\n" in port_.written)
    finally:
        session_stop.set()
        worker.join(timeout=5)
    assert wait_for(lambda: reader.values["status"]["value"] == "offline") and port_.closed
    stop.set()


@pytest.mark.integration
@pytest.mark.skipif(BROKER_MISSING, reason="no Mosquitto binary")
def test_layout_mix_labels_each_source_with_its_device_id(tmp_path):
    import subprocess
    truth = tmp_path / "truth.json"
    code = subprocess.run([sys.executable, "-m", "lab.run", "--out", str(tmp_path / "lab"), "--port", "18962", "--plan", "benign", "--seconds", "3",
                           "--scenario", "layout", "--mix", "light@d1,door@d7,bursty@cam2", "--ground-truth", str(truth)],
                          cwd=ROOT, env={**__import__("os").environ, "PYTHONPATH": f"{ROOT / 'src'}{__import__('os').pathsep}{ROOT}"}, timeout=60).returncode
    assert code == 0
    assert sorted(json.loads((tmp_path / "devices.json").read_text()).values()) == ["bursty@cam2", "door@d7", "light@d1"]


@pytest.mark.integration
@pytest.mark.skipif(BROKER_MISSING, reason="no Mosquitto binary")
def test_layout_mix_with_the_wokwi_hub_attached_keeps_both_labels(home_broker, tmp_path):
    # Regression: labelling once ran over the merged hub + lab map and crashed every attached run with an IndexError.
    import subprocess
    state_file = home.HOME / "home-broker.json"
    truth = tmp_path / "truth.json"
    result = subprocess.run([sys.executable, "-m", "lab.run", "--out", str(tmp_path / "lab"), "--port", str(PORT), "--plan", "benign", "--seconds", "3",
                             "--scenario", "layout", "--mix", "light@d1,bursty@d2", "--attach", str(state_file), "--ground-truth", str(truth)],
                            cwd=ROOT, env={**__import__("os").environ, "PYTHONPATH": f"{ROOT / 'src'}{__import__('os').pathsep}{ROOT}"}, timeout=60, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-800:]
    labels = json.loads((tmp_path / "devices.json").read_text())
    assert {"light@d1", "bursty@d2", "wokwi_serial", "wokwi_esp32"} <= set(labels.values())
    assert lab_run.wait_for_port(PORT, 1)  # the shared broker is still up
