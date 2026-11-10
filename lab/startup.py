"""Start the local smart-home stack without replacing running services.

python -m lab.startup start --api-port 8020
python -m lab.startup status
python -m lab.startup stop   # only processes this launcher recorded, never adopted ones
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

import psutil

from . import home
from .devices import atomic_write

ROOT = Path(__file__).resolve().parents[1]
MODULES = {"ids": "ids.service", "home": "lab.home", "api": "dashboard.api", "controllers": "lab.controllers"}


def process_matches(record):
    try:
        p = psutil.Process(record["pid"])
        args = p.cmdline()
        return abs(p.create_time() - record["created"]) < .1 and any(args[i:i+2] == ["-m", MODULES[record["name"]]] for i in range(len(args)-1))
    except (psutil.Error, KeyError):
        return False


def listening(port):
    """Inspect listener ownership without injecting probe traffic into MQTT capture."""
    return any(c.status == psutil.CONN_LISTEN and c.laddr.port == port for c in psutil.net_connections(kind="tcp"))


def service(module, port=None):
    for p in psutil.process_iter(["pid", "cmdline", "create_time"]):
        args = p.info["cmdline"] or []
        if not any(args[i:i+2] == ["-m", module] for i in range(len(args)-1)): continue
        if port is not None and option(args, "--port") != str(port): continue
        return p
    return None


def option(args, key):
    try: return args[args.index(key)+1]
    except (ValueError, IndexError): return None


def http(port, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=2) as response:
        return json.load(response)


def wait_for(check, seconds=30, process=None):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        if process and process.poll() is not None: raise RuntimeError("a newly started component exited; see its log")
        try:
            if check(): return
        except (OSError, ValueError): pass
        time.sleep(.4)
    raise RuntimeError("component readiness timed out; see startup logs")


def stop_records(records):
    for record in reversed(records):
        if not process_matches(record): continue
        try:
            p = psutil.Process(record["pid"])
            children = p.children(recursive=True)
            for child in reversed(children):
                try: child.terminate()
                except psutil.Error: pass
            p.terminate()
            _, remaining = psutil.wait_procs([*children, p], timeout=5)
            for child in remaining:
                try: child.kill()
                except psutil.Error: pass
        except psutil.Error: pass


def launch_stack(data, api_port, mqtt_port, model, controllers=True):
    data = Path(data).resolve()
    state_file = data / "run" / "home-stack.json"
    try: saved = json.loads(state_file.read_text())
    except (OSError, ValueError): saved = {}
    owned = [r for r in saved.get("processes", []) if process_matches(r)]
    started = []
    # Prefer the active IDS's schedule: API attacks must write exactly what that IDS reads.
    ids = service("ids.service", mqtt_port)
    if ids:
        schedule = option(ids.cmdline(), "--schedule")
        if not schedule: raise RuntimeError("existing IDS has no attack schedule; leave it running and coordinate a restart")
        schedule = Path(schedule)
        run_dir = schedule.parent
        active_db = option(ids.cmdline(), "--db")
        if not active_db or Path(active_db).resolve() != (data / "run/events.sqlite").resolve():
            raise RuntimeError("existing IDS uses another event store; leave it running and select the matching EDGEWATCH_DATA")
    else:
        run_dir = data / "run" / ("home-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
        schedule = run_dir / "ground_truth.json"
    run_dir.mkdir(parents=True, exist_ok=True)
    if not schedule.exists(): atomic_write(schedule, "[]")
    env = {**os.environ, "EDGEWATCH_DATA": str(data), "EDGEWATCH_DB": str(data / "run" / "events.sqlite"), "EDGEWATCH_MODEL": str(data / "models" / model),
           "EDGEWATCH_MQTT_PORT": str(mqtt_port), "EDGEWATCH_SCHEDULE": str(schedule), "PYTHONUNBUFFERED": "1"}
    result = {"run_dir": str(run_dir), "api_port": api_port, "mqtt_port": mqtt_port, "schedule": str(schedule), "processes": owned}
    def save(): atomic_write(state_file, json.dumps(result, indent=2))
    def start(name, arguments):
        with (run_dir / f"{name}.out.log").open("ab") as stdout, (run_dir / f"{name}.err.log").open("ab") as stderr:
            kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
            p = subprocess.Popen([sys.executable, "-m", MODULES[name], *arguments], cwd=ROOT, env=env, stdout=stdout, stderr=stderr, **kwargs)
        record = {"name": name, "pid": p.pid, "created": psutil.Process(p.pid).create_time()}
        started.append(record); owned.append(record); save()
        print(f"Started {name} (PID {p.pid})", flush=True)
        return p
    try:
        # Capture precedes home/device traffic. The frozen detector is loaded unchanged.
        if ids is None:
            if not (ROOT / "dashboard/web/dist/index.html").exists(): raise RuntimeError("build the dashboard first: cd dashboard/web; npm ci; npm run build")
            checked = subprocess.run([sys.executable, "-c", "import sys; from ids.detector import Detector; Detector(sys.argv[1])", env["EDGEWATCH_MODEL"]], cwd=ROOT, env=env, capture_output=True)
            if checked.returncode: raise RuntimeError("frozen model did not load; install dependencies using constraints-model.txt; no retraining")
            p = start("ids", ["--db", env["EDGEWATCH_DB"], "--model", env["EDGEWATCH_MODEL"], "--port", str(mqtt_port), "--schedule", str(schedule), "--scenario", "smart-home"])
            def capture_ready():
                return any("dumpcap" in " ".join(q.info["cmdline"] or []).lower() and f"tcp port {mqtt_port}" in " ".join(q.info["cmdline"] or []) for q in psutil.process_iter(["cmdline"]))
            wait_for(capture_ready, process=p)
        if not listening(mqtt_port):
            p = start("home", ["serve", "--port", str(mqtt_port), "--devices", str(run_dir / "devices.json"), "--serial", "rfc2217://localhost:4000"])
            wait_for(lambda: listening(mqtt_port), process=p)
        else:
            try: hub = json.loads((data / "home/home-broker.json").read_text())
            except (OSError, ValueError): hub = {}
            if hub.get("port") != mqtt_port or not service("lab.home", mqtt_port):
                raise RuntimeError("MQTT port belongs to another service; it was left untouched")
            print("Using the existing home broker", flush=True)
        api = service("dashboard.api", api_port)
        if listening(api_port):
            if not api: raise RuntimeError("API port belongs to another service; choose an unused --api-port")
            info = http(api_port, "/api/simulation")
            active_schedule = api.environ().get("EDGEWATCH_SCHEDULE")
            if info.get("port") != mqtt_port or not info.get("available") or not active_schedule or Path(active_schedule).resolve() != schedule.resolve():
                raise RuntimeError("existing API has incompatible attack settings; choose an unused --api-port (it was not restarted)")
        else:
            p = start("api", ["--port", str(api_port)])
            wait_for(lambda: http(api_port, "/api/simulation").get("available"), process=p)
        if controllers and service("lab.controllers") is None:
            p = start("controllers", ["--config", str(ROOT / "simulators/controllers.example.json"), "--devices", str(run_dir / "devices.json")])
            def bridges_started():
                snapshot = json.loads((data / "home/controllers-state.json").read_text())
                return time.time() - snapshot.get("updated", 0) < 5 and len(snapshot.get("controllers", {})) == 4
            wait_for(bridges_started, process=p)
        save()
        print(f"Dashboard: http://127.0.0.1:{api_port}/", flush=True)
        print("Attack lab configured; no attack starts automatically.", flush=True)
        print("Wokwi: open each simulators/wokwi-{environment,access,lighting,safety} folder in its own VS Code window; F1 > Wokwi: Start Simulator. Keep its simulator tab visible.", flush=True)
        print("Controllers remain unavailable until genuine firmware messages arrive.", flush=True)
        return result
    except Exception:
        stop_records(started)
        result["processes"] = [r for r in owned if r not in started]
        save()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "status", "stop"))
    parser.add_argument("--api-port", type=int, default=8020)
    parser.add_argument("--mqtt-port", type=int, default=18840)
    parser.add_argument("--model", default="ew-dt12-lab-v6")
    parser.add_argument("--no-controllers", action="store_true")
    args = parser.parse_args()
    data = Path(os.environ.get("EDGEWATCH_DATA", Path.home() / "edgewatch-data"))
    if args.action == "start":
        launch_stack(data, args.api_port, args.mqtt_port, args.model, not args.no_controllers)
    else:
        try: saved = json.loads((data / "run/home-stack.json").read_text())
        except (OSError, ValueError): saved = {}
        if args.action == "stop": stop_records(saved.get("processes", []))
        print(json.dumps({**saved, "processes": [{**r, "running": process_matches(r)} for r in saved.get("processes", [])]}, indent=2))


if __name__ == "__main__":
    main()
