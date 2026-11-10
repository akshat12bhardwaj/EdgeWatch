"""Opt-in multi-Wokwi serial bridges; attaches to the existing home broker.

python -m lab.controllers --config simulators/controllers.example.json
No broker or simulator is started/stopped here. Firmware telemetry, never Python
device models, supplies these devices. Each bridge binds a distinct loopback IP.
"""
import argparse
import ipaddress
import json
import math
import re
import select
import socket
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

from . import home, wire
from .devices import atomic_write

ROLES = {"environment": {"climate", "thermostat"}, "access": {"motion", "door", "lock"}, "lighting": {"light", "plug"}, "safety": {"smoke", "camera"}}
MAX_LINE, MAX_PER_S = 512, 20
SILENT_S = 25  # the firmware reports every 3 s; this long without a valid line means the simulated board is not running


class SerialLost(Exception):
    """The RFC2217 link itself failed. Kept apart from MQTT errors so a hub restart never reopens the serial port."""


def _serial(call, *args):
    try:
        return call(*args)
    except (OSError, ValueError) as error:
        raise SerialLost(f"{type(error).__name__}: {error}") from error


def load_config(path):
    config = json.loads(Path(path).read_text())
    if not isinstance(config, list) or not 1 <= len(config) <= 4:
        raise ValueError("configure one to four controllers")
    ids, ips, urls = set(), set(), set()
    for row in config:
        cid, source, url = row.get("id"), row.get("source_ip"), row.get("serial")
        if cid not in ROLES or cid in ids:
            raise ValueError("unknown or duplicate controller id")
        address = ipaddress.ip_address(source)
        parsed = urlparse(url)
        if address.version != 4 or not address.is_loopback or not str(address).startswith("127.0.3.") or source in ips or source in home.DEVICES or source == "127.0.3.4":
            raise ValueError("controller source must be a distinct unused 127.0.3.x address")
        if parsed.scheme != "rfc2217" or parsed.hostname not in ("localhost", "127.0.0.1", "::1") or not parsed.port or parsed.username or parsed.password or parsed.query or url in urls:
            raise ValueError("controller serial must be a distinct local RFC2217 URL")
        ids.add(cid); ips.add(source); urls.add(url)
    return config


def parse_line(line, controller):
    if len(line) > MAX_LINE or not line.startswith(b"EW2 "):
        return None
    try:
        _, channel, text = line.decode("ascii").strip().split(" ", 2)
        data = json.loads(text)
        if channel not in ROLES[controller] or not isinstance(data, dict):
            return None
        # Only known state fields are copied; identity and time are host metadata.
        rules = {
            "climate": {"temperature": (-40, 80), "humidity": (0, 100)},
            "thermostat": {"current": (-40, 80), "target": (10, 30), "mode": ("heating", "cooling", "idle")},
            "motion": {"motion": bool}, "door": {"open": bool}, "lock": {"locked": bool},
            "light": {"on": bool}, "plug": {"on": bool, "power_w": (0, 60), "energy_wh": (0, 1000000), "appliance_w": (60, 60)},
            "smoke": {"level": (0, 100), "threshold": (10, 50), "alarm": bool},
            "camera": {"monitoring": bool, "motion_events": (0, 1000000)},
        }[channel]
        out = {}
        for key, rule in rules.items():
            value = data[key]
            if rule is bool:
                if type(value) is not bool: return None
            elif isinstance(rule[0], str):
                if value not in rule: return None
            elif type(value) not in (int, float) or not math.isfinite(value) or not rule[0] <= value <= rule[1]:
                return None
            out[key] = value
        ack = data.get("ack")
        if ack is not None:
            if not isinstance(ack, str) or not re.fullmatch(r"[a-f0-9]{8}", ack): return None
            out["ack"] = ack
        return channel, out
    except (ValueError, UnicodeDecodeError, KeyError, TypeError):
        return None


def command_line(channel, payload):
    """Only firmware-supported commands; ack is emitted by the firmware after actuation."""
    if len(payload) > MAX_LINE: return None
    try:
        data = json.loads(payload)
        cmd = data.get("cmd_id", "")
        if not isinstance(cmd, str) or not re.fullmatch(r"[a-f0-9]{8}", cmd): return None
        if channel == "thermostat" and set(data) == {"target", "cmd_id"} and type(data["target"]) in (int, float) and 10 <= data["target"] <= 30:
            return f"EW2 thermostat target {data['target']:.1f} {cmd}\n".encode()
        if channel == "lock" and set(data) == {"locked", "cmd_id"} and type(data["locked"]) is bool:
            return f"EW2 lock locked {int(data['locked'])} {cmd}\n".encode()
        fields = {"light": {"on": bool}, "plug": {"on": bool}, "smoke": {"smoke": bool, "reset": bool, "threshold": (10, 50)}, "camera": {"monitoring": bool, "simulate_motion": bool}}
        for field, rule in fields.get(channel, {}).items():
            if set(data) != {field, "cmd_id"}: continue
            value = data[field]
            if rule is bool and type(value) is bool:
                return f"EW2 {channel} {field} {int(value)} {cmd}\n".encode()
            if rule is not bool and type(value) in (int, float) and rule[0] <= value <= rule[1]:
                return f"EW2 {channel} {field} {value:.1f} {cmd}\n".encode()
    except (ValueError, TypeError, AttributeError):
        pass
    return None


def receive_bounded(client):
    """Read one small MQTT packet; refuse malformed lengths before allocating a body."""
    head, size, shift = client._read_exact(1)[0], 0, 0
    for _ in range(4):
        value = client._read_exact(1)[0]
        size |= (value & 127) << shift
        if size > 4096: raise ValueError("controller MQTT packet exceeds limit")
        if not value & 128: return head, client._read_exact(size) if size else b""
        shift += 7
    raise ValueError("malformed MQTT length")


class ControllerBridge:
    def __init__(self, config, port, cred, layout, snapshot, open_serial=None, log=print):
        self.config, self.port, self.cred = config, port, cred
        self.layout, self.snapshot, self.open_serial, self.log = Path(layout), snapshot, open_serial, log
        self.stats = {"serial_connected": False, "mqtt_connected": False, "forwarded": 0, "rejected": 0, "dropped": 0, "commands": 0, "last_message": None, "firmware_reporting": False, "last_error": None}
        self.values, self.seq, self.reported = {}, 0, 0.0

    def mappings(self):
        try:
            devices = json.loads(self.layout.read_text()).get("devices", [])
        except (OSError, ValueError):
            return {}
        out = {}
        for d in devices:
            if d.get("source") == "wokwi" and d.get("controller") == self.config["id"] and d.get("type") in ROLES[self.config["id"]] and re.fullmatch(r"[A-Za-z0-9-]{1,12}", d.get("id", "")):
                out[d["id"]] = d["type"]
        return out

    def publish_state(self, client, device_id, channel, state):
        self.seq += 1
        data = {**state, "id": device_id, "type": channel, "seq": self.seq, "updated": time.time(), "controller": self.config["id"], "transport": "wokwi-serial"}
        client.publish(home.DEVICES_PREFIX + device_id + "/state", json.dumps(data).encode(), retain=True)
        client.publish(home.DEVICES_PREFIX + device_id + "/status", b"online", retain=True)

    def session(self, stop):
        """One serial connection, kept open while MQTT reconnects inside it. Reopening an RFC2217 port re-sends DTR/RTS,
        which an ESP32 can treat as a reset, so the port is reopened only when the link itself fails."""
        import serial
        opener = self.open_serial or (lambda url: serial.serial_for_url(url, baudrate=115200, timeout=.15))
        ser = _serial(opener, self.config["serial"])
        self.stats["serial_connected"], self.reported = True, time.monotonic()
        try:
            while not stop.is_set():
                try:
                    self.mqtt_session(ser, stop)
                except (OSError, ValueError) as error:
                    self.stats["last_error"] = f"MQTT {type(error).__name__}: {error}"[:160]
                    self.log(f"controller {self.config['id']}: MQTT {type(error).__name__}; serial kept open, retrying")
                    stop.wait(2)
        finally:
            _close(ser)
            self.stats["serial_connected"] = self.stats["firmware_reporting"] = False
            self.snapshot()

    def mqtt_session(self, ser, stop):
        client, mapped = None, {}
        try:
            client = wire.Client(self.config["source_ip"], ("127.0.0.1", self.port), timeout=1)
            if client.login("wokwi-" + self.config["id"], *self.cred, keepalive=30):
                raise ConnectionError("controller MQTT login refused")
            self.stats["mqtt_connected"] = True
            self.values = {}  # never restore stale state after a reconnect
            pending, discard, count = b"", False, 0
            window = last_ping = time.monotonic()
            self.log(f"controller {self.config['id']}: serial and MQTT connected, awaiting firmware")
            while not stop.is_set():
                now = time.monotonic()
                want = self.mappings()
                if want != mapped:
                    for did in set(mapped) - set(want):
                        client.send(wire.unsubscribe(home.DEVICES_PREFIX + did + "/command"))
                        client.publish(home.DEVICES_PREFIX + did + "/status", b"offline", retain=True)
                    for did in set(want) - set(mapped):
                        client.send(wire.subscribe(home.DEVICES_PREFIX + did + "/command"))
                        client.publish(home.DEVICES_PREFIX + did + "/status", b"offline", retain=True)
                    mapped = want
                chunk = _serial(ser.readline, MAX_LINE + 1)
                if chunk:
                    if discard:
                        discard = not chunk.endswith(b"\n")
                    else:
                        pending += chunk
                        if len(pending) > MAX_LINE:
                            self.stats["rejected"] += 1
                            pending, discard = b"", not chunk.endswith(b"\n")
                        elif pending.endswith(b"\n"):
                            protocol = pending.startswith(b"EW2")
                            parsed = parse_line(pending, self.config["id"])
                            if not protocol and self.stats.setdefault("device_logs", 0) < 10:
                                self.stats["device_logs"] += 1
                                self.log(f"controller {self.config['id']} device: {pending.decode('ascii', 'replace').strip()}")
                            pending = b""
                            if now - window >= 1: window, count = now, 0
                            count += int(protocol)
                            if count > MAX_PER_S:
                                self.stats["dropped"] += 1
                            elif parsed:
                                channel, state = parsed
                                self.values[channel] = state
                                self.reported = now
                                if not self.stats["firmware_reporting"]:
                                    self.stats["firmware_reporting"] = True
                                    self.log(f"controller {self.config['id']}: firmware reporting")
                                self.stats["last_message"] = time.time()
                                for did, kind in mapped.items():
                                    if channel == kind: self.publish_state(client, did, channel, state)
                                self.stats["forwarded"] += 1
                            elif protocol: self.stats["rejected"] += 1
                if select.select([client.sock], [], [], 0)[0]:
                    head, body = receive_bounded(client)
                    if head >> 4 == 3:
                        topic, payload = home.publish_parts(body)
                        did = topic.removeprefix(home.DEVICES_PREFIX).removesuffix("/command")
                        line = command_line(mapped.get(did), payload) if topic == home.DEVICES_PREFIX + did + "/command" else None
                        if line:
                            _serial(ser.write, line)
                            self.stats["commands"] += 1
                if now - last_ping >= 10:
                    client.send(wire.PINGREQ); last_ping = now
                if self.stats["firmware_reporting"] and now - self.reported > SILENT_S:
                    # Silent board: show its devices offline but keep the port open; the next valid line brings them back.
                    self.stats["firmware_reporting"] = False
                    self.log(f"controller {self.config['id']}: no firmware telemetry for {SILENT_S} s; is its Wokwi simulator running in VS Code?")
                    for did in mapped:
                        client.publish(home.DEVICES_PREFIX + did + "/status", b"offline", retain=True)
                self.snapshot()
        finally:
            if client:
                for did in mapped:
                    try: client.publish(home.DEVICES_PREFIX + did + "/status", b"offline", retain=True)
                    except OSError: pass
                client.close()
            self.stats["mqtt_connected"] = False
            self.snapshot()

    def run(self, stop):
        """Bounded reconnection: 2 s doubling to 30 s. Any failure stays inside this controller; the others, the hub and software devices continue."""
        backoff = 2
        while not stop.is_set():
            started = time.monotonic()
            try:
                self.session(stop)
            except Exception as error:
                self.stats["last_error"] = f"{type(error).__name__}: {error}"[:160]
                self.log(f"controller {self.config['id']}: waiting ({self.stats['last_error']}); retry in {backoff} s")
            backoff = 2 if time.monotonic() - started > 60 else min(30, backoff * 2)
            stop.wait(backoff)


def _close(ser):
    try:
        ser.close()
    except Exception:  # closing a dead RFC2217 link can raise; the port is released either way
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--layout", type=Path, help="default: the home layout; use a scratch layout for isolated verification")
    parser.add_argument("--out-dir", type=Path, help="default: the home runtime directory; never use results/")
    parser.add_argument("--devices", type=Path, help="optional IDS device-label map; records real bridge source IPs, shared per controller")
    args = parser.parse_args()
    config = load_config(args.config)
    # A local ownership socket prevents duplicate runners from taking each other's
    # MQTT sessions or competing for the same simulated serial ports.
    with socket.socket() as owner:
        try:
            owner.bind(("127.0.0.1", 18964))
        except OSError:
            raise SystemExit("another controller runner owns local port 18964")
        run_controllers(args, config)


def run_controllers(args, config):
    state = json.loads((home.HOME / "home-broker.json").read_text())
    layout, out = args.layout or home.HOME / "layout.json", args.out_dir or home.HOME
    protected = {"results", "models", "raw", "reference", "engineering", "reports"}
    if protected.intersection(p.lower() for p in out.resolve().parts):
        raise ValueError("controller snapshots must not write into protected artifacts")
    out.mkdir(parents=True, exist_ok=True)
    if args.devices:
        if protected.intersection(p.lower() for p in args.devices.resolve().parts):
            raise ValueError("device labels must not write into protected artifacts")
        known = json.loads(args.devices.read_text()) if args.devices.exists() else {}
        known.update({row["source_ip"]: "wokwi_" + row["id"] for row in config})
        atomic_write(args.devices, json.dumps(known))
    # Reuse existing local accounts and ACL; no changes to the running broker.
    cred = state["host"]
    stop, lock, bridges = threading.Event(), threading.Lock(), []
    def snapshot():
        with lock:
            body = {"updated": time.time(), "controllers": {b.config["id"]: {**b.stats, "source_ip": b.config["source_ip"], "serial": b.config["serial"]} for b in bridges}}
            atomic_write(out / "controllers-state.json", json.dumps(body))
    bridges.extend(ControllerBridge(c, state["port"], cred, layout, snapshot) for c in config)
    observer = home.Bridge(state["port"], state["bridge"], out / "controllers-telemetry.json", layout=layout, source="127.0.3.4", client_id="edgewatch-controller-observer")
    def resilient(run, name):
        def loop():  # a crashed thread restarts; previously one dead thread ended the whole runner and all four controllers
            while not stop.is_set():
                try:
                    run(stop)
                except Exception as error:
                    print(f"{name}: {type(error).__name__}: {error}; restarting", flush=True)
                    stop.wait(2)
        return loop
    threads = [threading.Thread(target=resilient(b.run, getattr(b, "config", {}).get("id", "observer")), daemon=True) for b in [*bridges, observer]]
    for t in threads: t.start()
    try:
        while all(t.is_alive() for t in threads): stop.wait(1)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        for t in threads: t.join(5)
        snapshot()


if __name__ == "__main__":
    main()
