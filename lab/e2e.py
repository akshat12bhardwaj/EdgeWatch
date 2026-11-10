"""End-to-end check: clients -> Mosquitto -> dumpcap -> IDS -> store -> API/WebSocket -> dashboard in a real headless browser.

python -m lab.e2e --model <bundle> --out results/ENG-E2E --shots <dir>
Writes what it actually observed. Windows loopback, simulated clients; not a physical network.
"""
import argparse
import base64
import json
import os
import platform
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

from websockets.sync.client import connect as ws_connect

from . import benign, gateway, run as lab_run

ROOT = Path(__file__).resolve().parents[1]
PORT, API = 18871, 8012
CDP = 9333
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def http(path, data=None):
    request = urllib.request.Request(f"http://127.0.0.1:{API}{path}", data=json.dumps(data).encode() if data else None, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=5) as r:
        return json.load(r)


class Browser:
    def __init__(self, url):
        self.profile = tempfile.mkdtemp()
        self.process = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", f"--remote-debugging-port={CDP}", "--remote-allow-origins=*", f"--user-data-dir={self.profile}", "--window-size=1920,1080", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        target = None
        for _ in range(50):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{CDP}/json", timeout=2) as r:
                    target = next(t for t in json.load(r) if t["type"] == "page")
                break
            except (OSError, StopIteration):
                time.sleep(0.2)
        if target is None:
            self.process.kill()
            raise RuntimeError(f"headless Chrome gave no page on CDP port {CDP}")
        self.ws = ws_connect(target["webSocketDebuggerUrl"], max_size=None, open_timeout=10)
        self.n = 0

    def call(self, method, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            message = json.loads(self.ws.recv(timeout=30))
            if message.get("id") == self.n:
                return message.get("result", {})

    def js(self, expression):
        return self.call("Runtime.evaluate", expression=expression, returnByValue=True).get("result", {}).get("value")

    def shot(self, path):
        Path(path).write_bytes(base64.b64decode(self.call("Page.captureScreenshot", format="png")["data"]))

    def close(self):
        try:
            self.ws.close()
        finally:
            # Chrome's renderers and GPU process are children; kill the whole tree so the CDP port and profile are released.
            import psutil
            try:
                tree = psutil.Process(self.process.pid).children(recursive=True)
            except psutil.NoSuchProcess:
                tree = []
            for p in [*tree, self.process]:
                try:
                    p.kill()
                except (psutil.NoSuchProcess, OSError):
                    pass
            psutil.wait_procs([p for p in tree], timeout=10)
            self.process.wait(timeout=10)
            shutil.rmtree(self.profile, ignore_errors=True)


def scan_privacy(db_path, cred):
    with sqlite3.connect(db_path, timeout=5) as c:
        dump = "\n".join(c.iterdump())
    needles = {"lab_password": cred[1], "lab_username": cred[0], "topic_prefix_sensor": "sensor/", "topic_flood": "flood/", "client_id_steady": "steady0", "client_id_cf": '"cf0"', "ipv4_127_0_1": "127.0.1.", "ipv4_127_0_2": "127.0.2."}
    return {name: needle in dump for name, needle in needles.items()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--out", default=str(ROOT / "results" / "ENG-E2E"))
    parser.add_argument("--shots", required=True)
    args = parser.parse_args()
    shots = Path(args.shots)
    shots.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp())
    db = work / "events.sqlite"
    schedule_file = work / "ground_truth.json"
    env = {**os.environ, "PYTHONPATH": f"{ROOT / 'src'}{os.pathsep}{ROOT}", "EDGEWATCH_DB": str(db), "EDGEWATCH_MODEL": str(args.model)}
    obs = {"checks": {}}
    marks = []

    def on_marker(mark):
        marks.append(mark)
        temp = schedule_file.with_suffix(".tmp")
        temp.write_text(json.dumps(marks))
        temp.replace(schedule_file)  # atomic, so the IDS never reads half a file

    ids = subprocess.Popen([sys.executable, "-m", "ids.service", "--db", str(db), "--port", str(PORT), "--model", str(args.model), "--schedule", str(schedule_file), "--scenario", "e2e-benign-then-attacks"], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    api = subprocess.Popen([sys.executable, "-m", "dashboard.api", "--port", str(API)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(5)
    browser = None
    schedule, seconds = lab_run.make_schedule(1, 30, 20, seed=11, lead_s=45)
    done = {}

    def run_lab():
        done["marks"], done["sources"] = lab_run.run(work / "lab", schedule, seconds, benign.BASE_MIX, PORT, capture=False, scenario="e2e", on_marker=on_marker, on_credentials=lambda cred: done.update(password=cred[1]))

    runner = threading.Thread(target=run_lab, daemon=True)
    runner.start()
    try:
        time.sleep(8)
        browser = Browser(f"http://127.0.0.1:{API}/")
        time.sleep(4)
        browser.shot(shots / "1_start.png")
        points = "(document.querySelector('.line-a')?.getAttribute('points') || '').split(' ').length"
        rows_before = browser.js(points)
        # Benign phase before the first attack. Stored count of alerts here is the false-alert check for this run.
        time.sleep(30)
        before_attack = http("/api/alerts")
        rows_after = browser.js(points)
        obs["checks"]["timeline_grew_without_reload"] = {"points_at_start": rows_before, "points_later": rows_after, "pass": rows_after > rows_before}
        obs["checks"]["no_alerts_in_benign_phase"] = {"alerts": len(before_attack), "pass": len(before_attack) == 0}
        obs["checks"]["clear_state_shown"] = {"pass": browser.js("document.querySelector('.clear')?.textContent") == "No alerts in this monitoring session"}
        browser.shot(shots / "2_benign.png")

        # Wait for the first alert to reach the page with no reload.
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline and not browser.js("document.querySelectorAll('.alert-row').length"):
            time.sleep(0.5)
        obs["checks"]["alert_reached_dashboard_without_reload"] = {"pass": bool(browser.js("document.querySelectorAll('.alert-row').length"))}
        browser.shot(shots / "3_attack.png")
        browser.js("document.querySelector('.alert-row').click()")
        time.sleep(1.5)
        drawer = browser.js("document.querySelector('.drawer')?.innerText") or ""
        obs["checks"]["drawer_opens_with_evidence"] = {"pass": "what the model weighted" in drawer.lower() and "not proof of malicious intent" in drawer and browser.js("document.querySelectorAll('.evidence tbody tr').length") > 0}
        browser.shot(shots / "4_drawer.png")
        browser.js("document.dispatchEvent(new KeyboardEvent('keydown', {key:'Escape', bubbles:true})); window.dispatchEvent(new KeyboardEvent('keydown', {key:'Escape'}))")
        time.sleep(0.5)
        obs["checks"]["escape_closes_drawer"] = {"pass": not browser.js("!!document.querySelector('.drawer')")}

        # Pause through the API while traffic runs: the broker must stay up.
        http("/api/control", {"action": "disable"})
        time.sleep(4)
        paused = http("/api/health")
        with sqlite3.connect(db, timeout=5) as c:
            count_a = c.execute("SELECT COUNT(*) FROM events WHERE event_type='window'").fetchone()[0]
        time.sleep(7)
        with sqlite3.connect(db, timeout=5) as c:
            count_b = c.execute("SELECT COUNT(*) FROM events WHERE event_type='window'").fetchone()[0]
        http("/api/control", {"action": "enable"})
        broker_alive_paused = lab_run.wait_for_port(PORT, 2)
        obs["checks"]["pause_stops_windows_not_broker"] = {"windows_during_pause": count_b - count_a, "ids_enabled_reported": paused["ids_enabled"], "pass": count_b - count_a <= 1 and broker_alive_paused and not paused["ids_enabled"]}

        # Kill and restart the API mid-run: the IDS must not care, and the page must reconnect.
        api.kill()
        api.wait()
        time.sleep(3)
        disconnected = browser.js("!!document.querySelector('.disconnect')")
        browser.shot(shots / "5_disconnected.png")
        with sqlite3.connect(db, timeout=5) as c:
            count_c = c.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        time.sleep(4)
        with sqlite3.connect(db, timeout=5) as c:
            count_d = c.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        api2 = subprocess.Popen([sys.executable, "-m", "dashboard.api", "--port", str(API)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(6)
        reconnected = not browser.js("!!document.querySelector('.disconnect')")
        obs["checks"]["api_restart_tolerated"] = {"disconnect_banner_shown": disconnected, "ids_kept_writing": count_d > count_c, "page_reconnected": reconnected, "pass": disconnected and count_d > count_c and reconnected}

        runner.join(timeout=seconds + 60)
        time.sleep(8)
        browser.shot(shots / "6_end.png")
        time.sleep(1.5)
        # The dashboard has three sections; an old #/advanced link lands on Smart Home instead of a broken page.
        tabs = browser.js("[...document.querySelectorAll('nav .tab')].map(t => t.textContent)") or []
        browser.js("location.hash = '/advanced/research'")
        time.sleep(1.5)
        obs["checks"]["three_sections_and_old_links_safe"] = {"tabs": tabs, "pass": tabs == ["Smart Home", "Attack Simulator", "Alerts"] and browser.js("!!document.querySelector('.floor-card')") and not browser.js("!!document.querySelector('.research')")}
        browser.shot(shots / "7_old_link.png")
        whole = (browser.js("document.body.innerText") or "").lower()
        obs["checks"]["no_forbidden_words_in_page"] = {"pass": not re.search(r"confirmed|blocked|neutrali[sz]ed", whole)}

        alerts = http("/api/alerts?limit=1000")
        model_alerts = [a for a in alerts if a["kind"] == "model"]
        pseudonyms = {}
        with sqlite3.connect(db, timeout=5) as c:
            markers = [json.loads(r[0]) for r in c.execute("SELECT body FROM events WHERE event_type='run_marker' AND body LIKE '%scheduled_attack%'")]
        by_family = {}
        for m in markers:
            hit = [a for a in model_alerts if a["source_key"] == m["source_key"] and a["start_ns"] < m["end_ns"] + 5e9 and a["last_window_ns"] + 5e9 > m["start_ns"]]
            first = min((a["first_seen"] for a in hit), default=None)
            by_family[m["family"]] = {"alerted": bool(hit), "classes": sorted({a["predicted_class"] for a in hit}), "statuses": sorted({a["status"] for a in hit}), "wall_seconds_from_scheduled_start_to_alert": first - m["start_ns"] / 1e9 if first else None}
        false = [a for a in model_alerts if a["status"] == "no_scheduled_attack"]
        obs["by_family"] = by_family
        obs["alerts_total"], obs["alerts_no_scheduled_attack"] = len(model_alerts), len(false)
        obs["checks"]["all_scheduled_attacks_alerted_or_explained"] = {"missed": [k for k, v in by_family.items() if not v["alerted"]], "pass": all(v["alerted"] for v in by_family.values())}
        privacy = scan_privacy(db, (gateway.LAB_USER, done["password"]))
        obs["privacy_strings_found_in_store"] = privacy
        obs["checks"]["privacy_scan_clean"] = {"pass": not any(privacy.values())}
        status = http("/api/health")
        obs["checks"]["broker_seen_running"] = {"pass": bool(status.get("broker_running")) or bool(done.get("marks"))}
        api2.terminate()
    finally:
        if browser:
            browser.close()
        ids.terminate()
        try:
            ids.wait(timeout=10)
        except subprocess.TimeoutExpired:
            ids.kill()
        if api.poll() is None:
            api.terminate()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((work / "lab" / "manifest.json").read_text())
    obs["broker_alive_at_end"] = manifest["broker_alive_at_end"]
    obs["checks"]["broker_alive_at_end"] = {"pass": manifest["broker_alive_at_end"]}
    obs |= {"experiment": "ENG-E2E", "run_date": time.strftime("%Y-%m-%d"), "device": f"development laptop, Windows loopback, {platform.processor()}", "note": "One run. Simulated clients on loopback, not a physical network or a Raspberry Pi.", "all_passed": all(c["pass"] for c in obs["checks"].values())}
    (out / "metrics.json").write_text(json.dumps(obs, indent=1))
    print(json.dumps(obs, indent=1))


if __name__ == "__main__":
    main()
