"""Cost of the live IDS by scenario, against a no-IDS baseline. Development-machine figures: this is not E3/E4 and says nothing about a Raspberry Pi.

python -m lab.perf --model <bundle> --seconds 60 --out results/ENG-P1

Loss is measured directly: the generator knows how many PUBLISH it sent, and the IDS reports how many it saw.
"""
import argparse
import json
import os
import platform
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import psutil

from . import attacks, benign, gateway, run as lab_run, wire

PORT = 18880
ROOT = Path(__file__).resolve().parents[1]


class Sent:
    def __init__(self):
        self.lock, self.publish, self.connect = threading.Lock(), 0, 0

    def add(self, publish=0, connect=0):
        with self.lock:
            self.publish += publish
            self.connect += connect


def rate_publisher(source, stop, broker, cred, rate, sent, batch=50):
    c = wire.Client(source, broker)
    c.login(f"load{source}", *cred)
    started, n = time.monotonic(), 0
    payload = wire.publish("load/topic", bytes(64))
    while not stop.is_set():
        c.send(payload * batch)
        n += batch
        sent.add(publish=batch)
        delay = started + n / rate - time.monotonic()
        if delay > 0:
            time.sleep(delay)
    c.close()


def churner(source, stop, broker, cred, rate, sent):
    started, n = time.monotonic(), 0
    while not stop.is_set():
        try:
            c = wire.Client(source, broker)
            c.login(f"ch{n}", *cred)
            sent.add(connect=1)
            c.close()
        except OSError:
            pass
        n += 1
        delay = started + n / rate - time.monotonic()
        if delay > 0:
            time.sleep(delay)


def long_lived(stop, broker, cred, count=500):
    held = []
    for i in range(count):
        c = wire.Client(f"127.0.3.{i % 200 + 1}", broker)
        c.login(f"ll{i}", *cred, keepalive=600)
        held.append(c)
    while not stop.wait(30):
        for c in held:
            c.send(wire.PINGREQ)
    for c in held:
        c.close()


def scenario_load(name, stop, broker, cred, sent):
    threads = []
    def spawn(target, *args):
        t = threading.Thread(target=target, args=args, daemon=True)
        t.start()
        threads.append(t)
    if name == "idle_broker":
        pass
    elif name == "benign_12_clients":
        threads += benign.start(benign.BASE_MIX, stop, broker, cred)[0]
    elif name == "multi_clients_60":
        threads += benign.start(("steady",) * 60, stop, broker, cred)[0]
    elif name.startswith("rate_"):
        total = int(name.split("_")[1])
        for i in range(4):
            spawn(rate_publisher, f"127.0.4.{i + 1}", stop, broker, cred, total / 4, sent)
    elif name == "connection_churn_100_per_s":
        spawn(churner, "127.0.5.1", stop, broker, cred, 100, sent)
    elif name == "long_lived_500":
        spawn(long_lived, stop, broker, cred)
    elif name == "attack_mix":
        threads += benign.start(benign.BASE_MIX, stop, broker, cred)[0]
        for i, family in enumerate(("flood_publish", "bruteforce", "flood_connect", "malformed", "lowrate")):
            spawn(attacks.run_family, family, f"127.0.6.{i + 1}", MEASURE_S, broker, cred)
    return threads


MEASURE_S = 60


def sampler(processes, stop, samples):
    for p in processes.values():
        if p:
            try:
                p.cpu_percent()
            except psutil.Error:
                pass
    while not stop.wait(1):
        row = {}
        for name, process in processes.items():
            if process is None:
                continue
            try:
                row[f"{name}_cpu"] = process.cpu_percent()
                row[f"{name}_rss"] = process.memory_info().rss / 1048576
            except psutil.Error:
                pass
        samples.append(row)


def stat(samples, key, f):
    values = [s[key] for s in samples if key in s]
    return round(f(values), 2) if values else None


def percentile(values, p):
    values = sorted(values)
    return values[min(len(values) - 1, int(p * len(values)))] if values else None


def db_size(db):
    """The WAL holds recent writes, so the main file alone understates a short run."""
    return sum(p.stat().st_size for p in (db, db.with_name(db.name + "-wal")) if p.exists())


def run_scenario(name, model, with_ids=True, seconds=60):
    global MEASURE_S
    MEASURE_S = seconds
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        folder = Path(folder)
        broker_process, cred = gateway.start_broker(folder / "broker", PORT)
        broker = ("127.0.0.1", PORT)
        ids = None
        db = folder / "events.sqlite"
        try:
            if not lab_run.wait_for_port(PORT):
                raise RuntimeError("broker did not start")
            processes = {"broker": psutil.Process(broker_process.pid)}
            if with_ids:
                env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
                ids = subprocess.Popen([sys.executable, "-m", "ids.service", "--db", str(db), "--port", str(PORT), "--model", str(model)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                launcher = psutil.Process(ids.pid)  # a venv python.exe is a launcher, so measure the real interpreter beneath it
                deadline = time.monotonic() + 30
                capture = None
                while capture is None and time.monotonic() < deadline:
                    capture = next((c for c in launcher.children(recursive=True) if "dumpcap" in c.name().lower()), None)
                    time.sleep(0.2)
                processes["capture"] = capture
                processes["ids"] = capture.parent() if capture else launcher
                time.sleep(3)  # dumpcap has no ready signal, so allow for opening the adapter and compiling its filter
            stop, sample_stop, sent, samples = threading.Event(), threading.Event(), Sent(), []
            threads = scenario_load(name, stop, broker, cred, sent)
            sample_thread = threading.Thread(target=sampler, args=(processes, sample_stop, samples), daemon=True)
            sample_thread.start()
            started = time.monotonic()
            time.sleep(seconds)
            stop.set()
            sample_stop.set()
            elapsed = time.monotonic() - started
            for t in threads:
                t.join(timeout=5)
            time.sleep(8)  # let the last windows close, including the live lag
            out = {"scenario": name, "with_ids": with_ids, "seconds": seconds, "sent_publish": sent.publish, "sent_connect": sent.connect, "target_publish_per_s": sent.publish / elapsed,
                   "broker_cpu_pct_of_core_mean": stat(samples, "broker_cpu", lambda v: sum(v) / len(v)), "broker_rss_mb_peak": stat(samples, "broker_rss", max), "broker_alive": broker_process.poll() is None}
            if with_ids:
                out |= {"ids_cpu_pct_of_core_mean": stat(samples, "ids_cpu", lambda v: sum(v) / len(v)), "ids_cpu_pct_of_core_peak": stat(samples, "ids_cpu", max), "ids_rss_mb_peak": stat(samples, "ids_rss", max), "ids_rss_mb_first": samples[0].get("ids_rss") if samples else None, "ids_rss_mb_last": samples[-1].get("ids_rss") if samples else None,
                        "capture_cpu_pct_of_core_mean": stat(samples, "capture_cpu", lambda v: sum(v) / len(v)), "capture_rss_mb_peak": stat(samples, "capture_rss", max)}
                with sqlite3.connect(db, timeout=5) as c:
                    windows = [json.loads(r[0]) for r in c.execute("SELECT body FROM events WHERE event_type='window'")]
                    resources = [json.loads(r[0]) for r in c.execute("SELECT body FROM events WHERE event_type='resource'")]
                    alerts = c.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
                seen_publish = sum(w["features"]["F12"] for w in windows)
                seen_connect = sum(w["features"]["F09"] for w in windows)
                stages = {k: [w["stage_latency_ms"][k] for w in windows] for k in ("window_close_to_features", "inference", "alert_build", "processing_total")}
                out |= {"windows": len(windows), "alerts": alerts, "seen_publish": seen_publish, "seen_connect": seen_connect, "mqtt_msgs_per_s": max((r["mqtt_msgs_per_s"] for r in resources), default=0),
                        "publish_loss_fraction": (sent.publish - seen_publish) / sent.publish if sent.publish else None, "connect_loss_fraction": (sent.connect - seen_connect) / sent.connect if sent.connect else None,
                        "inference_ms_p50": percentile(stages["inference"], 0.5), "inference_ms_p95": percentile(stages["inference"], 0.95), "alert_build_ms_p95": percentile(stages["alert_build"], 0.95),
                        "processing_total_ms_p50": percentile(stages["processing_total"], 0.5), "processing_total_ms_p95": percentile(stages["processing_total"], 0.95), "db_bytes": db_size(db),
                        "db_bytes_per_window": db_size(db) / max(len(windows), 1), "tcp_gaps": resources[-1]["tcp_gaps_total"] if resources else None, "late_events": resources[-1].get("late_events_total") if resources else None, "tracked_f22_end": resources[-1]["tracked_f22_connections"] if resources else None, "capture_dropped": None}
            return out
        finally:
            if ids:
                # Kills its dumpcap child too, so a measurement cannot leak a capture into the next scenario.
                for child in psutil.Process(ids.pid).children(recursive=True) if ids.poll() is None else []:
                    child.terminate()
                ids.terminate()
                ids.wait(timeout=10)
            gateway.stop(broker_process)
            time.sleep(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--out", default=str(ROOT / "results" / "ENG-P1"))
    parser.add_argument("--no-baseline", action="store_true")
    parser.add_argument("--scenarios", default="idle_broker,benign_12_clients,multi_clients_60,long_lived_500,connection_churn_100_per_s,attack_mix,rate_1000,rate_5000,rate_20000,rate_50000")
    args = parser.parse_args()
    results = []
    for name in args.scenarios.split(","):
        result = run_scenario(name, args.model, with_ids=True, seconds=args.seconds)
        if not args.no_baseline:
            result["broker_cpu_no_ids_pct_of_core"] = run_scenario(name, args.model, with_ids=False, seconds=args.seconds)["broker_cpu_pct_of_core_mean"]
        results.append(result)
        print(json.dumps(result), flush=True)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "metrics.json").write_text(json.dumps({"experiment": "ENG-P1", "run_date": time.strftime("%Y-%m-%d"), "device": f"development laptop, Windows loopback, {platform.processor()}, {psutil.cpu_count()} logical CPUs; generator on the same machine",
                                                  "note": f"Single-run, {args.seconds} s, generator on the same host. Ranking only: this is not E3/E4 and not a gateway result. CPU is percent of one core.", "scenarios": results}, indent=1))


if __name__ == "__main__":
    main()
