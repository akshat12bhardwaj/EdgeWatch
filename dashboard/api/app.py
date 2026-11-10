"""Edge Watch API: reads the event store and pushes new events over a WebSocket. Runs and restarts independently of the IDS and the broker.

EDGEWATCH_DB=<events.sqlite> uvicorn dashboard.api.app:app --host 127.0.0.1 --port 8000
Control requests need EDGEWATCH_API_TOKEN when it is set. It must be set before binding to anything but loopback.
"""
import asyncio
import hmac
import ipaddress
import json
import os
import sys
import subprocess
import secrets
import re
import sqlite3
import psutil
import threading
import time
from pathlib import Path
from typing import Literal, Optional
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from ids.store import connect
from lab.home import send_command, send_light

from .simulation import SimulationController, SimulationRequest, kill_tree
from .history import install_history

ROOT = Path(__file__).resolve().parents[2]
WEB_DIST = ROOT / "dashboard" / "web" / "dist"
POLL_S = 0.25
BATCH = 500
STALE_S = 15
LOCAL_HOSTS = ["127.0.0.1", "localhost", "[::1]", "::1"]


def is_loopback(host):
    try:
        return host == "localhost" or ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def device_summary(placed, reports, controllers, telemetry, now):
    """The one count every page shows: configured layout devices only (never broker, IDS, attacker or telemetry reader), each online only while it reports."""
    online = []
    for d in placed:
        r, c = reports.get(d.get("id")) or {}, controllers.get(d.get("controller")) if d.get("controller") else None
        fresh = r.get("status") == "online" and now - (r.get("ts") or 0) <= 30
        if d.get("controller"):
            fresh = fresh and bool(c and c.get("mqtt_connected") and c.get("last_message") and now - c["last_message"] <= 30)
        elif d.get("source") == "wokwi":  # legacy single board: live only while the hub bridge has fresh values from it
            v = telemetry.get("values", {})
            fresh = bool(telemetry.get("bridge_connected")) and (v.get("status") or {}).get("value") == "online" and now - max([x.get("ts") or 0 for x in v.values()] or [0]) <= 30
        if fresh:
            online.append(d["id"])
    wokwi = sum(d.get("source") == "wokwi" for d in placed)
    return {"total": len(placed), "online": len(online), "online_ids": online, "wokwi": wokwi, "software": len(placed) - wokwi,
            "wokwi_online": sum(d.get("source") == "wokwi" and d["id"] in online for d in placed)}


def create_app(db_path=None, token=None, web_dist=WEB_DIST, data_dir=None, mqtt_port=None, schedule=None, allowed_hosts=None):
    app = FastAPI(title="Edge Watch", docs_url="/api/docs", openapi_url="/api/openapi.json")
    data_dir = Path(data_dir or os.environ.get("EDGEWATCH_DATA", Path.home() / "edgewatch-data"))
    db_path = Path(db_path or os.environ.get("EDGEWATCH_DB", data_dir / "run" / "events.sqlite"))
    token = token if token is not None else os.environ.get("EDGEWATCH_API_TOKEN")
    # DNS rebinding: a web page cannot reach this API through a hostname it controls. Exposed deployments list their own names.
    hosts = allowed_hosts or [h.strip() for h in os.environ.get("EDGEWATCH_ALLOWED_HOSTS", "").split(",") if h.strip()] or LOCAL_HOSTS
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)
    port_env = mqtt_port or os.environ.get("EDGEWATCH_MQTT_PORT")
    simulation = SimulationController(int(port_env) if port_env else None, schedule or os.environ.get("EDGEWATCH_SCHEDULE"), data_dir)
    app.state.simulation = simulation

    def watchdog():
        while True:
            time.sleep(5)
            simulation.watchdog()

    threading.Thread(target=watchdog, daemon=True).start()

    def reader():
        """A fresh read-only connection, so a missing, locked or recreated database is an answer, not a crash."""
        if not db_path.exists():
            return None
        try:
            return connect(db_path, read_only=True)
        except sqlite3.Error:
            return None

    def query(sql, args=()):
        db = reader()
        if db is None:
            return None
        try:
            return db.execute(sql, args).fetchall()
        except sqlite3.Error:
            return None
        finally:
            db.close()

    def latest_run():
        rows = query("SELECT body FROM events WHERE event_type='run_marker' AND body LIKE '%\"run_start\"%' ORDER BY id DESC LIMIT 1")
        return json.loads(rows[0]["body"]) if rows else None

    def rows_for(event_type, limit, since=None, run_id=None):
        sql, args = "SELECT id, body FROM events WHERE event_type=?", [event_type]
        if since is not None:
            sql += " AND ts>=?"
            args.append(since)
        if run_id:
            sql += " AND run_id=?"
            args.append(run_id)
        rows = query(sql + " ORDER BY id DESC LIMIT ?", (*args, limit))
        return None if rows is None else [{**json.loads(r["body"]), "id": r["id"]} for r in reversed(rows)]

    def require_token(authorization: Optional[str] = Header(default=None)):
        if token and not hmac.compare_digest(authorization or "", f"Bearer {token}"):
            raise HTTPException(401, "control token required")

    def require_local(request: Request, authorization: Optional[str] = Header(default=None)):
        """Simulation starts traffic, so it is loopback only, always, and needs the token too when one is set."""
        if not request.client or not is_loopback(request.client.host):
            raise HTTPException(403, "simulation control is only accepted from this machine")
        require_token(authorization)

    install_history(app, db_path, require_local)

    @app.get("/api/health")
    def health():
        rows = query("SELECT MAX(ts) AS t FROM events")
        if rows is None:
            return {"status": "no_store", "store": "missing or unreadable", "ids": "unknown", "run": None, "provenance": None}
        last = rows[0]["t"]
        run = latest_run()
        controls = query("SELECT value FROM control WHERE key='enabled'") or []
        enabled = not controls or controls[0]["value"] == "true"
        resources = rows_for("resource", 1)
        age = time.time() - last if last else None
        running = bool(resources) and time.time() - resources[-1]["ts"] < STALE_S
        status = "ok" if running and enabled else ("disabled" if not enabled else "idle")
        total = query("SELECT COUNT(*) AS n FROM alerts") or [{"n": None}]
        return {"alerts_total": total[0]["n"], "status": status, "store": "ok", "ids": "running" if running else "stopped", "ids_enabled": enabled, "last_event_age_s": age, "run": run,
                "provenance": run["provenance"] if run else None, "model_loaded": resources[-1].get("model_loaded") if resources else None,
                "broker_running": bool(simulation.port and any(c.status == psutil.CONN_LISTEN and c.laddr.port == simulation.port for c in psutil.net_connections(kind="tcp")))}

    @app.get("/api/alerts")
    def alerts(limit: int = Query(100, ge=1, le=1000), run_id: Optional[str] = None, source: Optional[str] = None,
               severity: Optional[Literal["low", "medium", "high"]] = None, kind: Optional[Literal["model", "rule"]] = None,
               status: Optional[Literal["unverified_prediction", "matches_scheduled_attack", "no_scheduled_attack"]] = None,
               predicted_class: Optional[str] = Query(None, max_length=40), since: Optional[float] = None, until: Optional[float] = None):
        sql, args = "SELECT body FROM alerts WHERE 1=1", []
        for column, value in (("run_id", run_id), ("source_key", source), ("severity", severity), ("status", status)):
            if value:
                sql += f" AND {column}=?"  # column names are fixed literals; only values come from the request, and they are bound
                args.append(value)
        if since is not None:
            sql += " AND ts>=?"
            args.append(since)
        if until is not None:
            sql += " AND ts<=?"
            args.append(until)
        rows = query(sql + " ORDER BY ts DESC", tuple(args))
        out = [] if rows is None else [json.loads(r["body"]) for r in rows]
        return [a for a in out if (not kind or a.get("kind") == kind) and (not predicted_class or a.get("predicted_class") == predicted_class)][:limit]

    @app.get("/api/runs")
    def runs(limit: int = Query(50, ge=1, le=500)):
        """Runs in this store, newest first, with provenance, so history and replay comparison can pick one."""
        rows = query("SELECT run_id, provenance, MIN(ts) AS started, MAX(ts) AS last, SUM(event_type='window') AS windows FROM events GROUP BY run_id, provenance ORDER BY started DESC LIMIT ?", (limit,))
        if rows is None:
            return []
        out = []
        for r in rows:
            start = query("SELECT body FROM events WHERE run_id=? AND event_type='run_marker' AND body LIKE ? LIMIT 1", (r["run_id"], '%"run_start"%')) or []
            alerts_n = query("SELECT COUNT(*) AS n FROM alerts WHERE run_id=?", (r["run_id"],)) or [{"n": None}]
            marker = json.loads(start[0]["body"]) if start else {}
            out.append({"run_id": r["run_id"], "provenance": r["provenance"], "started": r["started"], "last": r["last"], "windows": r["windows"], "alerts": alerts_n[0]["n"],
                        "scenario": marker.get("scenario"), "model_id": marker.get("model_id")})
        return out

    @app.get("/api/alerts/{alert_id}")
    def alert(alert_id: str):
        rows = query("SELECT body FROM alerts WHERE alert_id=?", (alert_id,))
        if not rows:
            raise HTTPException(404, "no such alert")
        body = json.loads(rows[0]["body"])
        history = query("SELECT body FROM events WHERE event_type='window' AND run_id=? AND ts<=? AND body LIKE ? ORDER BY id DESC LIMIT 12",
                        (body["run_id"], body["last_window_ns"] / 1e9 + 5, f'%"source_key":"{body["source_key"]}"%')) or []
        return {**body, "history": [json.loads(r["body"]) for r in reversed(history)]}

    @app.get("/api/windows")
    def windows(limit: int = Query(200, ge=1, le=2000), run_id: Optional[str] = None):
        return rows_for("window", limit, run_id=run_id) or []

    @app.get("/api/traffic")
    def traffic(seconds: int = Query(300, ge=10, le=86400), run_id: Optional[str] = None):
        since = time.time() - seconds
        items = rows_for("resource", 1800, since, run_id) or []
        return [{"ts": r["ts"], "mqtt_msgs_per_s": r["mqtt_msgs_per_s"], "pkts_per_s": r["pkts_per_s"]} for r in items]

    @app.get("/api/resources")
    def resources(seconds: int = Query(300, ge=10, le=86400), run_id: Optional[str] = None):
        return rows_for("resource", 1800, time.time() - seconds, run_id) or []

    @app.get("/api/markers")
    def markers(limit: int = Query(200, ge=1, le=2000), run_id: Optional[str] = None):
        return rows_for("run_marker", limit, run_id=run_id) or []

    @app.get("/api/topology")
    def topology():
        items = rows_for("topology", 1)
        return items[-1] if items else {"nodes": []}

    class Control(BaseModel):
        model_config = ConfigDict(extra="forbid")
        action: Literal["enable", "disable"]

    @app.post("/api/control", dependencies=[Depends(require_token)])
    def control(request: Control):
        """Only pauses the IDS's capture. Nothing here can reach the broker or any traffic."""
        if not db_path.exists():
            raise HTTPException(503, "event store is not available")
        try:
            db = connect(db_path)
            with db:
                db.execute("INSERT OR REPLACE INTO control(key, value) VALUES ('enabled', ?)", ("true" if request.action == "enable" else "false",))
            db.close()
        except sqlite3.Error:
            raise HTTPException(503, "event store is not writable") from None
        return {"enabled": request.action == "enable"}

    @app.get("/api/simulation")
    def simulation_status():
        return simulation.status()

    @app.post("/api/simulation/start", dependencies=[Depends(require_local)])
    def simulation_start(request: SimulationRequest):
        code, body = simulation.start(request)
        if code != 200:
            raise HTTPException(code, body)
        return body

    @app.post("/api/simulation/stop", dependencies=[Depends(require_local)])
    def simulation_stop():
        return {"stopped": simulation.stop()}

    class Light(BaseModel):
        model_config = ConfigDict(extra="forbid")
        on: bool

    @app.get("/api/home")
    def home():
        """Latest Wokwi smart-home telemetry from lab.home's bridge. Read from its own file: never from, or into, the IDS store."""
        try:
            state = json.loads((data_dir / "home" / "home-broker.json").read_text())
        except (OSError, ValueError):
            return {"configured": False}
        try:
            telemetry = json.loads(Path(state["telemetry"]).read_text())
        except (OSError, ValueError, KeyError):
            telemetry = {}
        running = simulation.home() is not None
        device_reports = dict(telemetry.get("devices", {})) if running else {}
        try:
            observed = json.loads((data_dir / "home" / "controllers-telemetry.json").read_text())
            if running and observed.get("bridge_connected") and time.time() - observed.get("updated", 0) < 30:
                placed = json.loads(layout_path.read_text()).get("devices", [])
                mapped = {d["id"] for d in placed if d.get("source") == "wokwi" and d.get("controller")}
                device_reports.update({k: v for k, v in observed.get("devices", {}).items() if k in mapped})
        except (OSError, ValueError, TypeError):
            pass
        try:
            controller_state = json.loads((data_dir / "home" / "controllers-state.json").read_text())
            controllers = controller_state.get("controllers", {}) if time.time() - controller_state.get("updated", 0) < 10 else {}
        except (OSError, ValueError, TypeError):
            controllers = {}
        try:
            placed = json.loads(layout_path.read_text()).get("devices", [])
        except (OSError, ValueError, AttributeError):
            placed = []
        return {"summary": device_summary(placed, device_reports, controllers, telemetry if running else {}, time.time()), "configured": True, "running": running, "controllers": controllers, "transport": "serial" if state.get("serial_url") else "gateway", "port": state.get("port"), "monitored_port": simulation.port, "now": time.time(),
                "bridge_connected": running and bool(telemetry.get("bridge_connected")), "rejected": telemetry.get("rejected", 0), "values": telemetry.get("values", {}),
                "devices": device_reports}

    @app.post("/api/home/light", dependencies=[Depends(require_local)])
    def home_light(request: Light):
        """Publishes one command on edgewatch/home/light/set. The ESP32 reports the result on light/state; this does not assume it."""
        path = simulation.home()
        if path is None:
            raise HTTPException(409, "the Wokwi smart-home broker is not running on the monitored port")
        state = json.loads(path.read_text())
        try:
            sent = send_light(state["port"], state["bridge"], request.on)
        except OSError:
            sent = False
        if not sent:
            raise HTTPException(502, "the home broker refused the command")
        return {"sent": True}

    class LayoutDevice(BaseModel):
        model_config = ConfigDict(extra="forbid")
        id: str = Field(pattern=r"^[A-Za-z0-9-]{1,12}$")
        name: str = Field(min_length=1, max_length=40)
        type: Literal["light", "motion", "climate", "door", "lock", "camera", "plug", "thermostat", "smoke"]
        room: Literal["living", "kitchen", "bedroom", "entrance", "office", "bathroom", "garage"]
        x: float = Field(ge=0, le=1100)
        y: float = Field(ge=0, le=640)
        source: Literal["software", "wokwi"] = "software"
        controller: Optional[Literal["environment", "access", "lighting", "safety"]] = None

    class Layout(BaseModel):
        model_config = ConfigDict(extra="forbid")
        devices: list[LayoutDevice] = Field(default_factory=list, max_length=24)

        @field_validator("devices")
        @classmethod
        def honest_sources(cls, devices):
            # One Wokwi ESP32 has one DHT22, one PIR and one LED: each can back at most one placed device of its kind.
            wokwi = [d.type for d in devices if d.source == "wokwi" and not d.controller]
            if any(t not in ("climate", "motion", "light") for t in wokwi) or len(wokwi) != len(set(wokwi)):
                raise ValueError("only one climate sensor, motion sensor and smart light can be Wokwi-backed")
            roles = {"environment": {"climate", "thermostat"}, "access": {"motion", "door", "lock"}, "lighting": {"light", "plug"}, "safety": {"smoke", "camera"}}
            slots = []
            for d in devices:
                if d.controller:
                    if d.source != "wokwi" or d.type not in roles[d.controller]:
                        raise ValueError("device is not supported by this controller")
                    slots.append((d.controller, d.type))
            if len(slots) != len(set(slots)):
                raise ValueError("each controller sensor can back only one placed device")
            if len({d.id for d in devices}) != len(devices):
                raise ValueError("device ids must be unique")
            return devices

    layout_path = data_dir / "home" / "layout.json"

    # Smart Home device commands. Fields and ranges per type; the device validates again and its next state is the proof.
    COMMANDS = {"light": {"on": bool}, "motion": {"trigger": bool, "clear_after_s": (2, 300)}, "climate": {"room_temperature": (-10, 50), "room_humidity": (0, 100)},
                "door": {"open": bool}, "lock": {"locked": bool, "attempt": ("correct", "wrong")}, "camera": {"monitoring": bool, "simulate_motion": bool},
                "plug": {"on": bool, "appliance_w": (1, 3000)}, "thermostat": {"target": (10, 30)}, "smoke": {"smoke": bool, "reset": bool, "threshold": (5, 95)}}

    def valid_command(kind, body):
        rules = COMMANDS.get(kind, {})
        if not body or len(body) > 3:
            return False
        for key, value in body.items():
            rule = rules.get(key)
            if rule is bool:
                ok = isinstance(value, bool)
            elif isinstance(rule, tuple) and isinstance(rule[0], str):
                ok = value in rule
            elif isinstance(rule, tuple):
                ok = isinstance(value, (int, float)) and not isinstance(value, bool) and rule[0] <= value <= rule[1]
            else:
                ok = False
            if not ok:
                return False
        return True

    @app.post("/api/home/devices/{device_id}/command", dependencies=[Depends(require_local)])
    def device_command(device_id: str, body: dict):
        if not re.fullmatch(r"[A-Za-z0-9-]{1,12}", device_id):
            raise HTTPException(422, "invalid device id")
        try:
            placed = next((d for d in json.loads(layout_path.read_text())["devices"] if d["id"] == device_id), None)
        except (OSError, ValueError, KeyError):
            placed = None
        if placed is None or (placed.get("source") != "software" and not placed.get("controller")):
            raise HTTPException(404, "no software device with that id in the saved layout")
        if placed.get("controller"):
            firmware_fields = {"thermostat": {"target"}, "lock": {"locked"}, "light": {"on"}, "plug": {"on"}, "smoke": {"smoke", "reset", "threshold"}, "camera": {"monitoring", "simulate_motion"}}
            if len(body) != 1 or not set(body) <= firmware_fields.get(placed["type"], set()) or ("threshold" in body and (type(body["threshold"]) not in (int, float) or not 10 <= body["threshold"] <= 50)):
                raise HTTPException(422, "adjust this sensor in its Wokwi simulator")
        if not valid_command(placed["type"], body):
            raise HTTPException(422, f"not a valid {placed['type']} command")
        path = simulation.home()
        if path is None:
            raise HTTPException(409, "the smart-home hub is not running")
        cmd_id = secrets.token_hex(4)
        try:
            sent = send_command(json.loads(path.read_text())["port"], json.loads(path.read_text())["bridge"], device_id, {**body, "cmd_id": cmd_id})
        except OSError:
            sent = False
        if not sent:
            raise HTTPException(502, "the hub refused the command")
        return {"sent": True, "cmd_id": cmd_id}

    hub = {"process": None}

    @app.post("/api/home/start", dependencies=[Depends(require_local)])
    def home_start():
        """Starts the smart-home hub (broker, device host, telemetry reader, Wokwi serial bridge) on the IDS's port."""
        if simulation.home() is not None:
            raise HTTPException(409, "the smart-home hub is already running")
        if not simulation.port or not simulation.schedule:
            raise HTTPException(503, simulation.unavailable_reason())
        if simulation.status()["running"]:
            raise HTTPException(409, "a lab run is using the port; wait for it to finish")
        from .simulation import port_in_use
        if port_in_use(simulation.port):
            raise HTTPException(409, f"port {simulation.port} already has a broker; wait for it to finish")
        env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(ROOT / "src"), str(ROOT)]), "PYTHONUNBUFFERED": "1", "EDGEWATCH_DATA": str(data_dir)}
        (data_dir / "home").mkdir(parents=True, exist_ok=True)
        log = open(data_dir / "home" / "serve.out.log", "ab")  # append: earlier sessions stay readable for troubleshooting
        log.write(("--- hub started from the dashboard " + time.strftime("%Y-%m-%d %H:%M:%S") + "\n").encode())
        log.flush()
        try:
            process = subprocess.Popen([sys.executable, "-m", "lab.home", "serve", "--port", str(simulation.port), "--serial", "rfc2217://localhost:4000",
                                        "--devices", str(simulation.schedule.with_name("devices.json"))], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        finally:
            log.close()
        try:
            from ids.service import tie_to_this_process
            tie_to_this_process(process)  # Windows: the hub dies with the API, even on a hard kill
        except OSError:
            pass
        hub["process"] = process
        for _ in range(40):
            if simulation.home() is not None:
                return {"started": True, "pid": process.pid}
            if process.poll() is not None:
                break
            time.sleep(0.25)
        raise HTTPException(500, "the smart-home hub did not start; see home/serve.out.log")

    @app.post("/api/home/stop", dependencies=[Depends(require_local)])
    def home_stop():
        path = simulation.home()
        if path is None:
            return {"stopped": False}
        pid = json.loads(path.read_text()).get("serve_pid")
        kill_tree(int(pid))  # simulation.home() has checked that this PID is lab.home's
        return {"stopped": True}

    @app.get("/api/home/layout")
    def get_layout():
        """The Smart Home floor plan: where the user placed which device. Metadata only; never read by detection."""
        try:
            return {**Layout.model_validate_json(layout_path.read_text()).model_dump(), "saved": True}
        except (OSError, ValueError):
            return {"devices": [], "saved": False}

    @app.put("/api/home/layout", dependencies=[Depends(require_local)])
    def put_layout(layout: Layout):
        layout_path.parent.mkdir(parents=True, exist_ok=True)
        temp = layout_path.with_suffix(".tmp")
        temp.write_text(layout.model_dump_json())
        temp.replace(layout_path)
        return {"saved": True, "devices": len(layout.devices)}

    @app.websocket("/ws/events")
    async def events(socket: WebSocket, after: Optional[int] = None):
        # Browsers send Origin on WebSockets and CORS does not apply to them, so a foreign page is refused here.
        origin = urlparse(socket.headers.get("origin") or "").hostname
        if origin and not is_loopback(origin) and origin not in hosts:
            await socket.close(code=1008)
            return
        await socket.accept()
        last = after
        try:
            while True:
                if last is None:
                    rows = query("SELECT MAX(id) AS m FROM events")
                    last = (rows[0]["m"] or 0) if rows else None
                else:
                    rows = query("SELECT id, body FROM events WHERE id>? ORDER BY id LIMIT ?", (last, BATCH))
                    if rows is not None and not rows:
                        newest = query("SELECT MAX(id) AS m FROM events")
                        if newest and (newest[0]["m"] or 0) < last:  # the store was recreated
                            last = 0
                    elif rows:
                        last = rows[-1]["id"]
                        await socket.send_text("[" + ",".join(r["body"][:-1] + f',"id":{r["id"]}}}' for r in rows) + "]")
                await asyncio.sleep(POLL_S)
        except (WebSocketDisconnect, RuntimeError):
            return

    if Path(web_dist).exists():
        app.mount("/assets", StaticFiles(directory=Path(web_dist) / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def page(path: str):
            if path.startswith(("api/", "ws/")):
                raise HTTPException(404, "not found")
            return FileResponse(Path(web_dist) / "index.html")

    return app


app = create_app()
