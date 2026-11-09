"""Command-center end-to-end check (SG-08): the documented start script, a dashboard-triggered simulation, the store, API,
WebSocket and the dashboard in headless Chrome, failure cases, stop and restart. Writes only what it observed.

python -m lab.e2e_cc --shots <dir>          # about 6 minutes; Windows loopback only
"""
import argparse
import json
import os
import platform
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import psutil
from websockets.sync.client import connect as ws_connect

from .e2e import CHROME, Browser  # noqa: F401  (Browser drives Chrome over CDP)

ROOT = Path(__file__).resolve().parents[1]
MQTT, API = 18860, 8010
PS = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"]


def http(path, data=None, method=None):
    request = urllib.request.Request(f"http://127.0.0.1:{API}{path}", data=json.dumps(data).encode() if data is not None else None, headers={"Content-Type": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"null")


def script(name, *args):
    # A file, not a pipe: the services the script starts inherit its output handle, so a pipe never reaches EOF and run() hangs.
    with tempfile.TemporaryFile("w+", encoding="utf-8", errors="replace") as log:
        try:
            code = subprocess.run([*PS, str(ROOT / "scripts" / name), *args], stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, timeout=180).returncode
        except subprocess.TimeoutExpired:
            code = -1
        log.seek(0)
        return code, log.read()


def ours():
    """Project processes still alive: anything bound to our ports, or python/dumpcap/mosquitto naming them."""
    found = []
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            line = " ".join(p.info["cmdline"] or [])
        except psutil.Error:
            continue
        if any(k in line for k in (f"tcp port {MQTT}", f"--port {MQTT}", f"--port {API}", "lab.run", "ids.service", "dashboard.api")) and "e2e_cc" not in line:
            found.append({"pid": p.info["pid"], "name": p.info["name"]})
    return found


def wait(predicate, seconds, step=1.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(step)
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--shots", required=True)
    parser.add_argument("--out", default=str(ROOT / "results" / "ENG-E2E-CC"))
    args = parser.parse_args()
    shots = Path(args.shots)
    shots.mkdir(parents=True, exist_ok=True)
    checks, notes = {}, {}

    # Failure case first: a missing model gives an actionable error and starts nothing.
    code, text = script("start-edgewatch.ps1", "-Mode", "dashboard", "-MqttPort", str(MQTT), "-ApiPort", str(API), "-Model", "no-such-model")
    checks["missing_model_refused_with_message"] = code != 0 and "did not load" in text and not ours()

    started = time.time()
    code, text = script("start-edgewatch.ps1", "-Mode", "dashboard", "-MqttPort", str(MQTT), "-ApiPort", str(API))
    checks["clean_start"] = code == 0
    notes["start_output"] = text.strip().splitlines()[-6:]
    if code != 0:
        raise SystemExit(text)
    browser = None
    try:
        code, text = script("start-edgewatch.ps1", "-Mode", "dashboard", "-MqttPort", str(MQTT), "-ApiPort", str(API))
        checks["second_start_refused"] = code != 0 and "already running" in text
        health = wait(lambda: (lambda h: h if h[1]["status"] == "ok" else None)(http("/api/health")), 30)
        checks["health_ok_before_traffic"] = bool(health)
        run_id = health[1]["run"]["run_id"] if health else None

        browser = Browser(f"http://127.0.0.1:{API}/")
        time.sleep(4)
        socket = ws_connect(f"ws://127.0.0.1:{API}/ws/events")

        body = {"benign": "smart_home", "families": ["bruteforce", "flood_publish", "malformed"], "episodes": 1, "attack_s": 30, "calm_s": 15, "rate_factor": 1.0, "seed": 7}
        status, sim = http("/api/simulation/start", body)
        checks["simulation_started"] = status == 200
        notes["simulation"] = sim
        checks["duplicate_start_refused_409"] = http("/api/simulation/start", body)[0] == 409
        checks["off_limits_request_refused_422"] = http("/api/simulation/start", {**body, "rate_factor": 3})[0] == 422

        ws_events, shot_taken = [], False
        sim_started = time.monotonic()
        while time.monotonic() < sim_started + sim.get("planned_s", 155) + 40:
            try:
                ws_events += json.loads(socket.recv(timeout=2))
            except TimeoutError:
                pass
            if not shot_taken and time.monotonic() - sim_started > 90:
                shot_taken = True
                browser.shot(shots / "live_during_attack_1920.png")
        status_now = http("/api/simulation")[1]
        checks["simulation_finished_by_itself"] = status_now["running"] is None and status_now["history"] and status_now["history"][0]["exit_code"] == 0
        kinds = {}
        for e in ws_events:
            kinds[e["event_type"]] = kinds.get(e["event_type"], 0) + 1
        notes["websocket_events_by_type"] = kinds
        windows = [e for e in ws_events if e["event_type"] == "window"]
        alerts = {e["alert_id"]: e for e in ws_events if e["event_type"] == "alert"}
        markers = [e for e in ws_events if e["event_type"] == "run_marker"]
        checks["packets_decoded_to_windows"] = len(windows) > 20
        checks["features_present"] = all(len(w["features"]) == 26 for w in windows)
        checks["predictions_present"] = all(w["prediction"] is not None and w["score"] is not None for w in windows)
        checks["ground_truth_announced"] = sum(m["marker"] == "scheduled_attack" for m in markers) == 3
        checks["scenario_devices_announced"] = any(m["marker"] == "scenario_devices" and len(m.get("devices", {})) == 12 for m in markers)
        model_alerts = [a for a in alerts.values() if a["kind"] == "model"]
        matched = {a["predicted_class"] for a in model_alerts if a["status"] == "matches_scheduled_attack"}
        notes["alerts"] = [{k: a[k] for k in ("predicted_class", "severity", "status", "score")} for a in model_alerts]
        checks["each_family_alerted_and_matched"] = {"bruteforce", "flood", "malformed"} <= matched
        checks["no_alert_without_scheduled_attack"] = all(a["status"] != "no_scheduled_attack" for a in model_alerts)
        truth_windows = [w for w in windows if w["ground_truth"] is not None]
        notes["benign_windows_flagged"] = sum(w["ground_truth"] == "benign" and w["state"] != "normal" for w in truth_windows)
        notes["benign_windows"] = sum(w["ground_truth"] == "benign" for w in truth_windows)
        stored = http(f"/api/alerts?run_id={run_id}&limit=100")[1]
        checks["alerts_persisted_in_store"] = {a["alert_id"] for a in stored} >= set(alerts)
        delays = [(a["first_seen"] - (a["start_ns"] / 1e9)) for a in model_alerts]
        notes["alert_first_seen_minus_first_window_start_s"] = sorted(round(d, 1) for d in delays)

        # The dashboard shows the same events: KPI alert count equals the stream's, and the device labels are drawn.
        dom_alerts = browser.js("document.querySelector('[data-metric=alerts] b')?.textContent")
        checks["dashboard_alert_count_matches_stream"] = dom_alerts == str(len(alerts))
        checks["dashboard_device_labels_drawn"] = (browser.js("document.querySelectorAll('.node-dev').length") or 0) >= 10
        browser.shot(shots / "live_after_1920.png")
        for tab in ("attack", "alerts"):
            browser.js(f"location.hash = '/{tab}'")  # deep links: #/home, #/attack, #/alerts
            time.sleep(2)
            if tab == "alerts":
                checks["investigate_lists_alerts"] = (browser.js("document.querySelectorAll('.alert-list .alert-row').length") or 0) >= len(alerts)
            browser.shot(shots / f"{tab.replace('/', '_')}_1920.png")

        # Phone width: the page must not be wider than the screen.
        widths = {}
        for tab in ("home", "attack", "alerts"):
            browser.call("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=1, mobile=True)
            browser.js(f"location.hash = '/{tab}'")
            time.sleep(1.5)
            widths[tab] = browser.js("[document.documentElement.scrollWidth, window.innerWidth]")
            browser.shot(shots / f"{tab.replace('/', '_')}_390.png")
        notes["phone_scroll_vs_inner_width"] = widths
        checks["no_horizontal_overflow_at_390px"] = all(w and w[0] <= w[1] for w in widths.values())

        # Rapid start and stop: the whole lab tree (runner, broker, capture) goes away.
        status, quick = http("/api/simulation/start", {"benign": "base", "families": [], "seconds": 60})
        time.sleep(6)
        lab_pid = quick.get("pid")
        tree = [c.pid for c in psutil.Process(lab_pid).children(recursive=True)] if lab_pid and psutil.pid_exists(lab_pid) else []
        stop_status, stopped = http("/api/simulation/stop", {})
        time.sleep(2)
        checks["rapid_stop_kills_lab_tree"] = status == 200 and stopped == {"stopped": True} and not any(psutil.pid_exists(p) for p in [lab_pid, *tree])
        notes["lab_tree_size_at_stop"] = len(tree) + 1

        # Frontend connection loss: kill the API only; the IDS keeps writing, and the dashboard says it is disconnected.
        api_pid = next(p["pid"] for p in json.loads((Path(os.environ.get("EDGEWATCH_DATA", Path.home() / "edgewatch-data")) / "run" / "edgewatch-pids.json").read_text(encoding="utf-8-sig"))["processes"] if p["name"] == "api")
        browser.call("Emulation.setDeviceMetricsOverride", width=1920, height=1080, deviceScaleFactor=1, mobile=False)
        browser.js("location.hash = '/overview'")
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(api_pid)], capture_output=True)
        time.sleep(5)
        checks["dashboard_shows_disconnect"] = bool(browser.js("!!document.querySelector('.disconnect')"))
        browser.shot(shots / "api_lost_1920.png")
        ids_alive = any("ids.service" in " ".join(p.info["cmdline"] or []) for p in psutil.process_iter(["cmdline"]))
        checks["ids_survives_api_loss"] = ids_alive
        socket.close()
    finally:
        if browser:
            browser.close()
        code, text = script("stop-edgewatch.ps1")
        checks["stop_script_ok"] = code == 0
        time.sleep(3)
        notes["left_after_stop"] = ours()
        checks["no_orphans_after_stop"] = not notes["left_after_stop"]

    # Restart: a repeat start works and earlier alerts are still readable.
    code, text = script("start-edgewatch.ps1", "-Mode", "dashboard", "-MqttPort", str(MQTT), "-ApiPort", str(API))
    checks["repeat_start"] = code == 0
    if code == 0:
        h = wait(lambda: (lambda r: r if r[1]["status"] == "ok" else None)(http("/api/health")), 30)
        checks["recovered_health_ok"] = bool(h)
        checks["earlier_alerts_still_readable"] = len(http(f"/api/alerts?run_id={run_id}")[1]) >= len(alerts)
        script("stop-edgewatch.ps1")
        time.sleep(3)
        checks["no_orphans_after_second_stop"] = not ours()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    # Written only here, after every step, and atomically: a crashed or killed run leaves the previous file untouched,
    # and run_started identifies which run a file belongs to.
    body = {"experiment": "ENG-E2E-CC", "run_date": time.strftime("%Y-%m-%d"), "run_started_epoch": round(started), "completed": True, "device": f"development laptop ({platform.processor()}), not a gateway", "duration_s": round(time.time() - started),
            "status": "engineering check on Windows loopback with simulated clients; not a physical network", "checks": checks, "all_passed": all(checks.values()), "observations": notes}
    temp = out / "metrics.json.tmp"
    temp.write_text(json.dumps(body, indent=1))
    temp.replace(out / "metrics.json")
    print(json.dumps({"all_passed": body["all_passed"], "failed": [k for k, v in checks.items() if not v]}, indent=1))


if __name__ == "__main__":
    main()
