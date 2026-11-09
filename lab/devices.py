"""Virtual smart-home devices for the Smart Home builder: one MQTT client and one state machine per placed software device.

Topics, under edgewatch/devices/<id>/:
  state    retained JSON on every change and as periodic telemetry: {"id","type","seq","updated","ack", ...fields}
  status   retained "online" / "offline"; "offline" is also each client's last will, so a crash is visible too
  event    JSON, not retained: things that happen (camera motion, smoke alarm, lock access attempt)
  command  JSON from the dashboard: {"cmd_id": "...", <field>: <value>}. The device applies what it accepts and echoes
           cmd_id as "ack" in its next state, so a command counts as done only when the device says so.
These are software simulations: watts, smoke level and room temperature come from small deterministic models, not sensors.
The host follows the saved layout: devices start when placed, stop and clear their retained topics when removed.
"""
import json
import socket
import threading
import time
from pathlib import Path

from . import wire

PREFIX = "edgewatch/devices/"
TYPES = ("light", "motion", "climate", "door", "lock", "camera", "plug", "thermostat", "smoke")
MAX_COMMAND = 512


def atomic_write(path, text, tries=10):
    """Write via a temp file and replace. On Windows a reader holding the file makes replace fail with PermissionError
    for a moment: retry briefly, and if it still fails return False instead of raising. The next write replaces it."""
    path = Path(path)
    temp = path.with_name(path.name + ".tmp")
    for _ in range(tries):
        try:
            temp.write_text(text)
            temp.replace(path)
            return True
        except PermissionError:
            time.sleep(0.02)
        except OSError:
            return False
    return False


def _num(cmd, key, low, high):
    v = cmd.get(key)
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and low <= v <= high else None


class Model:
    period = 15.0  # periodic telemetry, seconds

    def __init__(self, state=None):
        self.state = {**self.initial(), **{k: v for k, v in (state or {}).items() if k in self.initial()}}

    def initial(self):
        return {}

    def apply(self, cmd, now):
        """Apply what is valid in cmd. Returns (changed, events)."""
        return False, []

    def tick(self, dt, now):
        return False, []


class Light(Model):
    def initial(self):
        return {"on": False}

    def apply(self, cmd, now):
        if isinstance(cmd.get("on"), bool) and cmd["on"] != self.state["on"]:
            self.state["on"] = cmd["on"]
            return True, []
        return False, []


class Motion(Model):
    def initial(self):
        return {"motion": False, "clear_after_s": 10}

    def apply(self, cmd, now):
        changed = False
        if (n := _num(cmd, "clear_after_s", 2, 300)) is not None:
            self.state["clear_after_s"], changed = int(n), True
        if cmd.get("trigger") is True:
            self.state["motion"], self._left, changed = True, self.state["clear_after_s"], True
            return changed, [{"event": "motion"}]
        return changed, []

    def tick(self, dt, now):
        if self.state["motion"]:
            self._left = getattr(self, "_left", self.state["clear_after_s"]) - dt
            if self._left <= 0:
                self.state["motion"] = False
                return True, []
        return False, []


class Climate(Model):
    """Readings follow the room conditions set from the dashboard, a little at a time, like a real sensor settling."""
    period = 10.0

    def initial(self):
        return {"temperature": 21.0, "humidity": 45.0, "room_temperature": 21.0, "room_humidity": 45.0}

    def apply(self, cmd, now):
        changed = False
        if (t := _num(cmd, "room_temperature", -10, 50)) is not None:
            self.state["room_temperature"], changed = round(t, 1), True
        if (h := _num(cmd, "room_humidity", 0, 100)) is not None:
            self.state["room_humidity"], changed = round(h, 1), True
        return changed, []

    def tick(self, dt, now):
        s = self.state
        shown = lambda: (round(s["temperature"], 1), round(s["humidity"]))
        before = shown()
        step = lambda cur, goal, rate: round(cur + max(-rate * dt, min(rate * dt, goal - cur)), 2)
        s["temperature"], s["humidity"] = step(s["temperature"], s["room_temperature"], 0.2), step(s["humidity"], s["room_humidity"], 1.0)
        return shown() != before, []  # publish when the reading changes at the precision it is shown


class Door(Model):
    def initial(self):
        return {"open": False, "changed": None}

    def apply(self, cmd, now):
        if isinstance(cmd.get("open"), bool) and cmd["open"] != self.state["open"]:
            self.state["open"], self.state["changed"] = cmd["open"], now
            return True, [{"event": "opened" if cmd["open"] else "closed"}]
        return False, []


class Lock(Model):
    """A simulated keypad: "correct"/"wrong" stand for an entered code. No real authentication is implemented."""

    def initial(self):
        return {"locked": True, "failed_attempts": 0, "last_attempt": None}

    def apply(self, cmd, now):
        changed, events = False, []
        if isinstance(cmd.get("locked"), bool) and cmd["locked"] != self.state["locked"]:
            self.state["locked"], changed = cmd["locked"], True
            events.append({"event": "locked" if cmd["locked"] else "unlocked"})
        if cmd.get("attempt") in ("correct", "wrong"):
            ok = cmd["attempt"] == "correct"
            self.state["last_attempt"] = {"result": "accepted" if ok else "rejected", "at": now}
            self.state["failed_attempts"] = 0 if ok else self.state["failed_attempts"] + 1
            if ok:
                self.state["locked"] = False
            events.append({"event": "access", "result": "accepted" if ok else "rejected"})
            changed = True
        return changed, events


class Camera(Model):
    """Status and motion events only: there is no video."""

    def initial(self):
        return {"monitoring": True, "last_motion": None, "motion_events": 0}

    def apply(self, cmd, now):
        changed, events = False, []
        if isinstance(cmd.get("monitoring"), bool) and cmd["monitoring"] != self.state["monitoring"]:
            self.state["monitoring"], changed = cmd["monitoring"], True
        if cmd.get("simulate_motion") is True and self.state["monitoring"]:
            self.state["last_motion"], self.state["motion_events"], changed = now, self.state["motion_events"] + 1, True
            events.append({"event": "motion"})
        return changed, events


class Plug(Model):
    """Simulated load: the set appliance wattage while on, 0.4 W standby while off, integrated into watt-hours."""
    period = 10.0

    def initial(self):
        return {"on": False, "appliance_w": 60.0, "power_w": 0.4, "energy_wh": 0.0}

    def apply(self, cmd, now):
        changed = False
        if isinstance(cmd.get("on"), bool) and cmd["on"] != self.state["on"]:
            self.state["on"], changed = cmd["on"], True
        if (w := _num(cmd, "appliance_w", 1, 3000)) is not None:
            self.state["appliance_w"], changed = round(w, 1), True
        if changed:
            self.state["power_w"] = self.state["appliance_w"] if self.state["on"] else 0.4
        return changed, []

    def tick(self, dt, now):
        self.state["energy_wh"] = round(self.state["energy_wh"] + self.state["power_w"] * dt / 3600, 4)
        return False, []


class Thermostat(Model):
    """Heats or cools at 0.05 °C/s towards the target, idle within ±0.3 °C."""
    period = 5.0

    def initial(self):
        return {"current": 20.0, "target": 21.0, "mode": "idle"}

    def apply(self, cmd, now):
        if (t := _num(cmd, "target", 10, 30)) is not None:
            self.state["target"] = round(t * 2) / 2
            return self._mode(), []
        return False, []

    def _mode(self):
        s = self.state
        s["mode"] ="heating" if s["current"] < s["target"] - 0.3 else "cooling" if s["current"] > s["target"] + 0.3 else "idle"
        return True

    def tick(self, dt, now):
        s, before = self.state, self.state["mode"]
        if s["mode"] != "idle":
            s["current"] = round(s["current"] + (0.05 if s["mode"] == "heating" else -0.05) * dt, 2)
        self._mode()
        return s["mode"] != before, []


class Smoke(Model):
    """Smoke level rises while a simulated source burns and the alarm latches at the threshold until reset."""
    period = 10.0

    def initial(self):
        return {"level": 0.0, "threshold": 30, "alarm": False, "smoke": False}

    def apply(self, cmd, now):
        changed = False
        if (n := _num(cmd, "threshold", 5, 95)) is not None:
            self.state["threshold"], changed = int(n), True
        if cmd.get("smoke") is True and not self.state["smoke"]:
            self.state["smoke"], changed = True, True
        if cmd.get("reset") is True:
            self.state.update(smoke=False, level=0.0, alarm=False)
            return True, [{"event": "reset"}]
        return changed, []

    def tick(self, dt, now):
        s, before = self.state, (self.state["level"], self.state["alarm"])
        s["level"] = round(min(85.0, s["level"] + 8 * dt) if s["smoke"] else max(0.0, s["level"] - 4 * dt), 1)
        events = []
        if s["level"] >= s["threshold"] and not s["alarm"]:
            s["alarm"] = True
            events.append({"event": "alarm", "level": s["level"]})
        return (s["level"], s["alarm"]) != before, events


MODELS = {"light": Light, "motion": Motion, "climate": Climate, "door": Door, "lock": Lock, "camera": Camera, "plug": Plug, "thermostat": Thermostat, "smoke": Smoke}


class DeviceClient(threading.Thread):
    """One device: its own MQTT session from its own loopback address. Reconnects with a 2 s pause; stops on request."""

    def __init__(self, device_id, dtype, source, port, cred, state=None, on_state=None, clock=time.time):
        super().__init__(daemon=True, name=f"device-{device_id}")
        self.id, self.type, self.source, self.port, self.cred, self.clock = device_id, dtype, source, port, cred, clock
        self.model = MODELS[dtype](state)
        self.on_state = on_state or (lambda *_: None)
        self.stop_event, self.remove, self.seq, self.ack, self.connected = threading.Event(), False, 0, None, False
        self.topic = lambda leaf: f"{PREFIX}{device_id}/{leaf}"

    def stop(self, remove=False):
        self.remove = remove
        self.stop_event.set()

    def _publish(self, c, leaf, payload, retain=False):
        c.publish(self.topic(leaf), payload if isinstance(payload, bytes) else json.dumps(payload).encode(), retain=retain)

    def _state(self, c):
        self.seq += 1
        body = {"id": self.id, "type": self.type, "seq": self.seq, "updated": self.clock(), "ack": self.ack, **self.model.state}
        self._publish(c, "state", body, retain=True)
        self.on_state(self.id, self.model.state)
        return time.monotonic()

    def run(self):
        while not self.stop_event.is_set():
            c = None
            try:
                c = wire.Client(self.source, ("127.0.0.1", self.port), timeout=1)
                if c.login(f"ew-{self.id}", *self.cred, keepalive=60, will=(self.topic("status"), b"offline", True)):
                    raise ConnectionError("device login refused")
                c.send(wire.subscribe(self.topic("command")))
                self._publish(c, "status", b"online", retain=True)
                self.connected = True
                last_pub = self._state(c)
                last_tick = last_ping = time.monotonic()
                while not self.stop_event.is_set():
                    changed, events = False, []
                    try:
                        head, body = c.receive()
                        if head >> 4 == 3:
                            n = int.from_bytes(body[:2], "big")
                            topic, payload = body[2:2 + n].decode("utf-8", "replace"), body[2 + n:]
                            cmd = json.loads(payload) if topic == self.topic("command") and len(payload) <= MAX_COMMAND else None
                            if isinstance(cmd, dict):
                                changed, events = self.model.apply(cmd, self.clock())
                                self.ack, changed = str(cmd.get("cmd_id", ""))[:16] or None, True  # acknowledged, even if nothing changed
                    except (socket.timeout, ValueError):
                        pass
                    now = time.monotonic()
                    if now - last_tick >= 1:
                        tick_changed, tick_events = self.model.tick(now - last_tick, self.clock())
                        changed, events, last_tick = changed or tick_changed, events + tick_events, now
                    for e in events:
                        self._publish(c, "event", {**e, "id": self.id, "at": self.clock()})
                    if changed or now - last_pub >= self.model.period:
                        last_pub = last_ping = self._state(c)
                    elif now - last_ping >= 30:
                        c.send(wire.PINGREQ)
                        last_ping = now
                if self.remove:  # removed from the home: clear what the broker retains for it
                    self._publish(c, "state", b"", retain=True)
                    self._publish(c, "status", b"", retain=True)
                else:
                    self._publish(c, "status", b"offline", retain=True)
                c.close()
            except OSError:
                if c:
                    c.close(graceful=False)  # the session failed: release the socket now, not at garbage collection
            self.connected = False
            self.stop_event.wait(2)


class DeviceHost:
    """Runs a DeviceClient for every software device in the saved layout, and keeps the IDS's device labels in step."""

    def __init__(self, port, cred, layout_path, home_dir, devices_file=None, log=print):
        self.port, self.cred, self.layout_path, self.home = port, cred, Path(layout_path), Path(home_dir)
        self.devices_file, self.log = Path(devices_file) if devices_file else None, log
        self.clients: dict[str, DeviceClient] = {}
        self.addresses = self._load("device-addresses.json")
        self.saved = self._load("device-state.json")
        self._dirty, self._lock = False, threading.Lock()

    def _load(self, name):
        try:
            return json.loads((self.home / name).read_text())
        except (OSError, ValueError):
            return {}

    def _write(self, name, data):
        return atomic_write(self.home / name, json.dumps(data))

    def remember(self, device_id, state):
        with self._lock:
            self.saved[device_id] = dict(state)
            self._dirty = True

    def address(self, device_id):
        """A stable loopback address per device, so the IDS sees each device as its own source across restarts."""
        if device_id not in self.addresses:
            used = set(self.addresses.values())
            self.addresses[device_id] = next(f"127.0.4.{n}" for n in range(10, 250) if f"127.0.4.{n}" not in used)
            self._write("device-addresses.json", self.addresses)
        return self.addresses[device_id]

    def wanted(self):
        try:
            layout = json.loads(self.layout_path.read_text())
        except (OSError, ValueError):
            return None  # unreadable: keep what runs rather than stop everything
        return {d["id"]: d["type"] for d in layout.get("devices", []) if d.get("source") == "software" and d.get("type") in MODELS}

    def reconcile(self):
        want = self.wanted()
        if want is None:
            return
        for device_id, client in list(self.clients.items()):
            if want.get(device_id) != client.type:
                client.stop(remove=True)
                client.join(timeout=5)
                del self.clients[device_id]
                if device_id not in want:
                    self.saved.pop(device_id, None)
                    self._dirty = True
                self.log(f"devices: stopped {device_id} ({client.type})")
        with self._lock:  # removed while the hub was stopped, or before this host ran: forget it on disk too
            for gone in [i for i in self.saved if i not in want]:
                del self.saved[gone]
                self._dirty = True
        for device_id, dtype in want.items():
            if device_id not in self.clients:
                saved = self.saved.get(device_id) if self.saved.get(device_id, {}).keys() <= set(MODELS[dtype]().state) else None
                client = DeviceClient(device_id, dtype, self.address(device_id), self.port, self.cred, saved, self.remember)
                client.start()
                self.clients[device_id] = client
                self.log(f"devices: started {device_id} ({dtype}) from {client.source}")
        if self.devices_file:
            try:
                known = json.loads(self.devices_file.read_text())
            except (OSError, ValueError):
                known = {}
            labels = {self.addresses[i]: f"{c.type}@{i}" for i, c in self.clients.items()}
            if any(known.get(k) != v for k, v in labels.items()):
                atomic_write(self.devices_file, json.dumps({**known, **labels}))

    def run(self, stop):
        while not stop.is_set():
            self.reconcile()
            with self._lock:
                if self._dirty and self._write("device-state.json", self.saved):  # device state survives a hub restart
                    self._dirty = False
            stop.wait(1)
        for client in self.clients.values():
            client.stop()
        for client in self.clients.values():
            client.join(timeout=5)
