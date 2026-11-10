"""Virtual smart home for Wokwi: a persistent broker on the IDS port plus a read-only telemetry bridge.

python -m lab.home init  --port 18840            # credentials, broker config and the firmware's secrets.h (idempotent)
python -m lab.home serve --port 18840 [--devices <run dir>/devices.json] [--serial rfc2217://localhost:4000]

The broker outlives lab runs, so the Wokwi ESP32 stays connected while `lab.run --attach` adds traffic and attacks.
An ACL lets only the ESP32's account publish sensor topics, so no lab client can spoof what the dashboard shows.
The bridge keeps only validated latest values in telemetry.json, outside the IDS store; detection never reads it.
"""
import argparse
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import gateway, wire
from .devices import atomic_write


def listening(port, seconds=10):
    """Wait for the broker from Edge Watch's own probe address, so the check is never attributed to the Wokwi gateway's 127.0.0.1."""
    deadline = time.monotonic() + seconds
    while True:
        with socket.socket() as s:
            s.bind((PROBE_SOURCE, 0))
            s.settimeout(0.5)
            if not s.connect_ex(("127.0.0.1", port)):
                return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.2)

ROOT = Path(__file__).resolve().parents[1]
HOME = Path(os.environ.get("EDGEWATCH_DATA", Path.home() / "edgewatch-data")) / "home"
FIRMWARE = ROOT / "simulators" / "wokwi-smart-home"
PREFIX = "edgewatch/home/"
DEVICE_USER, BRIDGE_USER, HOST_USER = "wokwi-home", "edgewatch-bridge", "edgewatch-devices"
DEVICES_PREFIX = "edgewatch/devices/"  # the Smart Home builder's software devices (lab/devices.py)
BRIDGE_SOURCE, CONTROL_SOURCE, PROBE_SOURCE, SERIAL_SOURCE = "127.0.3.1", "127.0.3.2", "127.0.3.3", "127.0.3.10"
# The Wokwi Private IoT Gateway reaches the broker from this machine's loopback; the lab never uses 127.0.0.1 or ::1.
# On the free path the serial bridge publishes for the ESP32 from SERIAL_SOURCE: the IDS sees the bridge's MQTT, not the ESP32's WiFi.
DEVICES = {"127.0.0.1": "wokwi_esp32", "::1": "wokwi_esp32", SERIAL_SOURCE: "wokwi_serial", BRIDGE_SOURCE: "edgewatch_bridge", CONTROL_SOURCE: "edgewatch_bridge", PROBE_SOURCE: "edgewatch_bridge"}
# Serial protocol (mirrored in simulators/wokwi-smart-home/src/main.cpp): "EW1 <field> <value>\n", 115200 baud.
SERIAL_FIELDS = {"temperature": "temperature", "humidity": "humidity", "motion": "motion", "light": "light/state", "status": "device/status"}
MAX_LINE, MAX_PER_S = 64, 20  # the firmware sends a few lines per 10 s; anything faster is dropped, never queued
# Exact topics, no wildcard: a "#" subscription is itself an indicator the IDS rightly flags.
TELEMETRY_TOPICS = ("temperature", "humidity", "motion", "light/state", "device/status")
ACL = f"""user {DEVICE_USER}
topic write {PREFIX}temperature
topic write {PREFIX}humidity
topic write {PREFIX}motion
topic write {PREFIX}light/state
topic write {PREFIX}device/status
topic read {PREFIX}light/set
user {HOST_USER}
topic write {DEVICES_PREFIX}+/state
topic write {DEVICES_PREFIX}+/status
topic write {DEVICES_PREFIX}+/event
topic read {DEVICES_PREFIX}+/command
user {BRIDGE_USER}
topic read {PREFIX}#
topic write {PREFIX}light/set
topic read {DEVICES_PREFIX}#
topic write {DEVICES_PREFIX}+/command
user {gateway.LAB_USER}
topic deny {PREFIX}#
topic deny {DEVICES_PREFIX}#
topic readwrite #
"""


def parse(topic, payload):
    """(field, value) for a valid telemetry message, else None. Ranges are the DHT22's; anything else is rejected, not coerced."""
    try:
        text = payload.decode("ascii").strip()
    except UnicodeDecodeError:
        return None
    name = topic[len(PREFIX):] if topic.startswith(PREFIX) else None
    try:
        if name in ("temperature", "humidity"):
            value = float(text)
            low, high = (-40, 80) if name == "temperature" else (0, 100)
            return (name, round(value, 1)) if low <= value <= high else None
    except ValueError:
        return None
    if name == "motion" and text in ("0", "1"):
        return "motion", text == "1"
    if name == "light/state" and text.upper() in ("ON", "OFF"):
        return "light", text.upper() == "ON"
    if name == "device/status" and text in ("online", "offline"):
        return "status", text
    return None


def publish_parts(body):
    """Topic and payload of a QoS 0 PUBLISH body (the bridge subscribes at QoS 0, so nothing else is delivered)."""
    n = int.from_bytes(body[:2], "big")
    return body[2:2 + n].decode("utf-8", "replace"), body[2 + n:]


def init(port):
    """Create (once) the accounts, and (always) the config for this port. Returns the state written to home-broker.json."""
    HOME.mkdir(parents=True, exist_ok=True)
    cred_file = HOME / "credentials.json"
    cred = json.loads(cred_file.read_text()) if cred_file.exists() else {}
    for user in (DEVICE_USER, BRIDGE_USER, gateway.LAB_USER, HOST_USER):  # accounts added in later versions are created on upgrade
        cred.setdefault(user, secrets.token_hex(12))
    cred_file.write_text(json.dumps(cred))
    passwd = HOME / "home.passwd"
    passwd.unlink(missing_ok=True)
    for i, (user, password) in enumerate(cred.items()):
        subprocess.run([gateway.find("mosquitto_passwd", "bin"), *(["-c"] if i == 0 else []), "-b", str(passwd), user, password], check=True, capture_output=True)
    (HOME / "home.acl").write_text(ACL)
    # Loopback only, both families: the gateway's choice of 127.0.0.1 or ::1 is not documented, and the IDS decodes both.
    (HOME / "mosquitto.conf").write_text(f"per_listener_settings false\nlistener {port} 127.0.0.1\nlistener {port} ::1\nallow_anonymous false\n"
                                         f"password_file {passwd.as_posix()}\nacl_file {(HOME / 'home.acl').as_posix()}\npersistence false\n"
                                         f"log_dest file {(HOME / 'mosquitto.log').as_posix()}\nlog_type error\nlog_type warning\nlog_type notice\n")
    secrets_h = FIRMWARE / "include" / "secrets.h"
    text = (FIRMWARE / "include" / "secrets.example.h").read_text().replace("18840", str(port)).replace("set-by-lab-home-init", cred[DEVICE_USER])
    if not secrets_h.exists() or secrets_h.read_text() != text:
        secrets_h.write_text(text)  # git-ignored; the firmware must be rebuilt after this changes
    state = {"port": port, "lab": [gateway.LAB_USER, cred[gateway.LAB_USER]], "bridge": [BRIDGE_USER, cred[BRIDGE_USER]], "host": [HOST_USER, cred[HOST_USER]], "devices": DEVICES, "telemetry": str(HOME / "telemetry.json")}
    (HOME / "home-broker.json").write_text(json.dumps(state, indent=1))
    return state


class Bridge:
    """Subscribes to the home topics and keeps the latest valid value of each, with its arrival time.

    Software devices: exact per-device subscriptions that follow the saved layout (no wildcards), so it never looks like a
    "listen to everything" client. Their states come from lab/devices.py over MQTT, never from the host's memory.
    """
    MAX_EVENTS = 8

    def __init__(self, port, cred, out, clock=time.time, layout=None, source=BRIDGE_SOURCE, client_id="edgewatch-telemetry-bridge"):
        self.port, self.cred, self.out, self.clock = port, cred, Path(out), clock
        self.layout = Path(layout) if layout else None
        self.values, self.devices, self.rejected, self.connected = {}, {}, 0, False
        self.source, self.client_id = source, client_id

    def handle(self, topic, payload):
        if topic.startswith(DEVICES_PREFIX):
            return self.handle_device(topic, payload)
        parsed = parse(topic, payload)
        if parsed is None:
            if not topic.endswith("/set"):  # commands are not telemetry
                self.rejected += 1
            return False
        self.values[parsed[0]] = {"value": parsed[1], "ts": self.clock()}
        return True

    def handle_device(self, topic, payload):
        device_id, _, leaf = topic[len(DEVICES_PREFIX):].partition("/")
        entry = self.devices.setdefault(device_id, {"state": None, "status": None, "events": [], "ts": None})
        if not payload:  # cleared retained topic: the device was removed
            entry[leaf if leaf in ("state", "status") else "events"] = None if leaf != "event" else []
            return True
        try:
            body = payload.decode("ascii") if leaf == "status" else json.loads(payload) if len(payload) <= 2048 else None
        except (UnicodeDecodeError, ValueError):
            body = None
        if leaf == "status" and body in ("online", "offline"):
            entry["status"] = body
        elif leaf == "state" and isinstance(body, dict) and body.get("id") == device_id:
            entry["state"], entry["ts"] = body, self.clock()
        elif leaf == "event" and isinstance(body, dict) and body.get("id") == device_id:
            entry["events"] = [body, *entry["events"]][: self.MAX_EVENTS]
        else:
            self.rejected += 1
            return False
        return True

    def wanted(self):
        try:
            layout = json.loads(self.layout.read_text()) if self.layout else {}
        except (OSError, ValueError):
            return None
        return {d["id"] for d in layout.get("devices", []) if (d.get("source") == "software" or d.get("source") == "wokwi" and d.get("controller") in ("environment", "access", "lighting", "safety")) and re.fullmatch(r"[A-Za-z0-9-]{1,12}", d.get("id", ""))}

    def write(self):
        body = {"updated": self.clock(), "port": self.port, "bridge_connected": self.connected, "rejected": self.rejected, "values": self.values, "devices": self.devices}
        atomic_write(self.out, json.dumps(body))  # never raises: a failed snapshot must not stop the reader

    def run(self, stop):
        while not stop.is_set():
            c = None
            try:
                c = wire.Client(self.source, ("127.0.0.1", self.port), timeout=1)
                if c.login(self.client_id, *self.cred, keepalive=60):
                    raise ConnectionError("bridge login refused")
                pid = 1
                for topic in TELEMETRY_TOPICS:
                    c.send(wire.subscribe(PREFIX + topic, packet_id=pid))
                    pid += 1
                subscribed = set()
                self.connected = True
                self.write()
                last_ping = time.monotonic()
                while not stop.is_set():
                    want = self.wanted()
                    if want is not None and want != subscribed:
                        for device_id in want - subscribed:
                            for leaf in ("state", "status", "event"):
                                c.send(wire.subscribe(f"{DEVICES_PREFIX}{device_id}/{leaf}", packet_id=pid))
                                pid = pid % 65000 + 1
                        for device_id in subscribed - want:
                            for leaf in ("state", "status", "event"):
                                c.send(wire.unsubscribe(f"{DEVICES_PREFIX}{device_id}/{leaf}", packet_id=pid))
                                pid = pid % 65000 + 1
                            self.devices.pop(device_id, None)
                        subscribed = want
                        self.write()
                    try:
                        head, body = c.receive()
                    except socket.timeout:
                        if time.monotonic() - last_ping >= 30:
                            c.send(wire.PINGREQ)  # keep the session alive, like any idle subscriber
                            last_ping = time.monotonic()
                        continue
                    if head >> 4 == 3 and self.handle(*publish_parts(body)):
                        self.write()
                c.close()
            except OSError:
                if c:
                    c.close(graceful=False)  # the session failed: release the socket now, not at garbage collection
            self.connected = False
            self.write()
            stop.wait(2)


def send_command(port, cred, device_id, command):
    """Publish one command to a software device as the bridge account. Returns True when the broker accepted it.
    The device's next state (with "ack" = cmd_id) is the only evidence that it acted."""
    c = wire.Client(CONTROL_SOURCE, ("127.0.0.1", port))
    try:
        if c.login("edgewatch-device-control", *cred):
            return False
        c.publish(f"{DEVICES_PREFIX}{device_id}/command", json.dumps(command).encode(), qos=1)
        return True
    finally:
        c.close()


def send_light(port, cred, on):
    """Publish one light command as the bridge account, from its own source address. Returns True when the broker accepted it."""
    c = wire.Client(CONTROL_SOURCE, ("127.0.0.1", port))
    try:
        if c.login("edgewatch-light-control", *cred):
            return False
        c.publish(PREFIX + "light/set", b"ON" if on else b"OFF", qos=1)
        return True
    finally:
        c.close()


def parse_line(line):
    """(topic, payload) for one valid serial line from the firmware, else None. Validation is the same as for MQTT telemetry."""
    if len(line) > MAX_LINE:
        return None
    try:
        parts = line.decode("ascii").strip().split(" ")
    except UnicodeDecodeError:
        return None
    if len(parts) != 3 or parts[0] != "EW1" or parts[1] not in SERIAL_FIELDS:
        return None
    topic, payload = PREFIX + SERIAL_FIELDS[parts[1]], parts[2].encode()
    return (topic, payload) if parse(topic, payload) else None


class SerialBridge:
    """Wokwi ESP32 serial (RFC2217) -> MQTT as the device's account, and light/set back to the serial port.

    MQTT is connected only while the serial link is open, so Edge Watch sees a device session only while Wokwi runs.
    """

    def __init__(self, url, port, cred, open_serial=None, clock=time.monotonic, log=print):
        self.url, self.port, self.cred, self.clock, self.log = url, port, cred, clock, log
        self.open_serial = open_serial
        self.stats = {"forwarded": 0, "rejected": 0, "dropped": 0, "commands": 0}
        self._window, self._count, self.online = 0.0, 0, False

    def allow(self):
        now = self.clock()
        if now - self._window >= 1:
            self._window, self._count = now, 0
        self._count += 1
        return self._count <= MAX_PER_S

    def handle_line(self, line, publish):
        """Validate one line and publish it. Returns True when forwarded."""
        parsed = parse_line(line)
        if parsed is None:
            if line.startswith(b"EW1"):
                self.stats["rejected"] += 1
            elif self.stats.setdefault("device_log", 0) < 50:  # the firmware's own log lines, bounded, for troubleshooting
                self.stats["device_log"] += 1
                self.log(f"device: {line.decode('ascii', 'replace').strip()}")
            return False
        if not self.allow():
            self.stats["dropped"] += 1
            return False
        topic, payload = parsed
        if not self.online and topic != PREFIX + "device/status":
            publish(PREFIX + "device/status", b"online", True)  # the device is talking, whether or not we saw its boot line
            self.online = True
        retained = topic in (PREFIX + "device/status", PREFIX + "light/state")
        publish(topic, payload, retained)
        self.online = self.online or payload == b"online"
        self.stats["forwarded"] += 1
        return True

    @staticmethod
    def command_line(payload):
        """The serial line for a light/set payload, or None. The firmware validates again; this only refuses obvious junk."""
        text = payload.decode("ascii", "replace").strip().upper()
        return f"EW1 light {'ON' if text in ('ON', '1') else 'OFF'}\n".encode() if text in ("ON", "OFF", "1", "0") else None

    def _commands(self, client, ser, stop, lock):
        """Reads the MQTT side: light/set -> serial; pings while idle."""
        while not stop.is_set():
            try:
                head, body = client.receive()
            except socket.timeout:
                with lock:
                    client.send(wire.PINGREQ)
                continue
            except OSError:
                stop.set()
                return
            if head >> 4 == 3:
                topic, payload = publish_parts(body)
                line = self.command_line(payload) if topic == PREFIX + "light/set" else None
                if line:
                    ser.write(line)
                    self.stats["commands"] += 1
                    self.log(f"serial bridge: light command -> {line.decode().strip()}")

    def session(self, stop):
        """One serial + MQTT session. Returns when either side closes."""
        import serial  # optional dependency: pip install edgewatch[wokwi]
        opener = self.open_serial or (lambda url: serial.serial_for_url(url, baudrate=115200, timeout=1))
        ser = opener(self.url)
        self.log(f"serial bridge: connected to {self.url}")
        client = wire.Client(SERIAL_SOURCE, ("127.0.0.1", self.port), timeout=30)
        lock, ended = threading.Lock(), threading.Event()
        try:
            if client.login("wokwi-esp32-serial-bridge", *self.cred, keepalive=60):
                raise ConnectionError("broker refused the device account")
            client.send(wire.subscribe(PREFIX + "light/set"))

            def publish(topic, payload, retained):
                with lock:
                    client.publish(topic, payload, retain=retained)

            threading.Thread(target=self._commands, args=(client, ser, ended, lock), daemon=True).start()
            pending, discarding = b"", False
            while not stop.is_set() and not ended.is_set():
                chunk = ser.readline(MAX_LINE + 1)  # a timeout can split a line; pending joins the pieces, bounded
                if not chunk:
                    continue
                if discarding:  # the rest of an over-long line
                    discarding = not chunk.endswith(b"\n")
                    continue
                pending += chunk
                if len(pending) > MAX_LINE:
                    self.stats["rejected"] += 1
                    pending, discarding = b"", not chunk.endswith(b"\n")
                elif pending.endswith(b"\n"):
                    self.handle_line(pending, publish)
                    pending = b""
        finally:
            ended.set()
            if self.online:
                try:
                    with lock:
                        client.publish(PREFIX + "device/status", b"offline", retain=True)
                except OSError:
                    pass
            self.online = False
            client.close()
            ser.close()
            self.log(f"serial bridge: session ended {self.stats}")

    def run(self, stop):
        waiting = False
        while not stop.is_set():
            try:
                self.session(stop)
                waiting = False
            except Exception as error:  # serial server absent (simulator stopped) or link lost: retry, bounded
                if not waiting:
                    self.log(f"serial bridge: waiting for the Wokwi serial server at {self.url} ({type(error).__name__})")
                    waiting = True
            stop.wait(2)


def serve(port, devices_file=None, serial_url=None):
    state = init(port)
    if listening(port, 0):
        raise SystemExit(f"port {port} already has a listener; stop it first")
    broker = subprocess.Popen([gateway.find("mosquitto", "sbin"), "-c", str(HOME / "mosquitto.conf")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        from ids.service import tie_to_this_process
        tie_to_this_process(broker)  # Windows: the broker dies with this process, even on a hard kill
    except (ImportError, OSError):
        pass
    try:
        if not listening(port):
            raise SystemExit("home broker did not start; see " + str(HOME / "mosquitto.log"))
        (HOME / "home-broker.json").write_text(json.dumps({**state, "serve_pid": os.getpid(), "serial_url": serial_url}, indent=1))
        if devices_file:  # lets the IDS label the Wokwi gateway's connection before any lab run; earlier lab labels are kept
            path = Path(devices_file)
            try:
                known = json.loads(path.read_text())
            except (OSError, ValueError):
                known = {}
            atomic_write(path, json.dumps({**known, **DEVICES}))
        print(f"home broker on 127.0.0.1:{port} and [::1]:{port}; telemetry -> {state['telemetry']}", flush=True)
        stop = threading.Event()
        bridge = Bridge(port, state["bridge"], state["telemetry"], layout=HOME / "layout.json")
        threading.Thread(target=bridge.run, args=(stop,), daemon=True).start()
        from .devices import DeviceHost  # the Smart Home builder's software devices follow the saved layout
        host = DeviceHost(port, state["host"], HOME / "layout.json", HOME, devices_file, log=lambda text: print(text, flush=True))
        threading.Thread(target=host.run, args=(stop,), daemon=True).start()
        if serial_url:
            device_cred = (DEVICE_USER, json.loads((HOME / "credentials.json").read_text())[DEVICE_USER])
            log = lambda text: print(text, flush=True)
            threading.Thread(target=SerialBridge(serial_url, port, device_cred, log=log).run, args=(stop,), daemon=True).start()
        while broker.poll() is None:
            time.sleep(1)
        raise SystemExit("home broker exited")
    finally:
        stop_flag = locals().get("stop")
        if stop_flag:
            stop_flag.set()
        gateway.stop(broker)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("init", "serve"))
    parser.add_argument("--port", type=int, default=18840)
    parser.add_argument("--devices", help="devices.json next to the IDS's --schedule file")
    parser.add_argument("--serial", help="Wokwi RFC2217 serial URL, e.g. rfc2217://localhost:4000 (free path; needs pyserial)")
    args = parser.parse_args()
    if args.action == "init":
        state = init(args.port)
        print(f"ready: {HOME / 'home-broker.json'}; firmware secrets for port {state['port']} in {FIRMWARE / 'include' / 'secrets.h'}")
    else:
        serve(args.port, args.devices, args.serial)


if __name__ == "__main__":
    sys.exit(main())
