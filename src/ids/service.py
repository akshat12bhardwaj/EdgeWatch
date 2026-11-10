"""The IDS process: capture -> decoder -> FeatureAggregator -> model -> alerts -> event store. Passive and independent of the broker.

python -m ids.service --db <events.sqlite> --model <bundle dir> --port 1883 --capture "\\Device\\NPF_Loopback"
python -m ids.service --db <events.sqlite> --model <bundle dir> --replay <capture.pcap> --speed 10

It never opens a connection to the broker and never writes to the network. Stopping it, or any failure here, cannot affect the broker.
"""
import argparse
import json
import logging
import os
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Optional

import psutil

from .alerts import AlertEngine, ground_truth_status
from .decoder import decode_packets, read_records, read_stream
from .detector import Detector, ModelRefused
from .features import EXTRACTOR_VERSION, FEATURE_IDS, FeatureAggregator
from .pipeline import pseudonymizer, validate_row
from .store import EventStore

log = logging.getLogger("edgewatch.ids")
DEFAULT_DUMPCAP = r"C:\Program Files\Wireshark\dumpcap.exe"
TIMER_S = 0.25
# The timer must trail capture: packets still in dumpcap's pipe carry older timestamps, and the extractor drops anything behind its watermark.
LIVE_LAG_NS = 1_000_000_000
F01, F25, F12 = FEATURE_IDS.index("F01"), FEATURE_IDS.index("F25"), FEATURE_IDS.index("F12")
SERVICE_VERSION = "0.1.0"
MAX_F22_CONNECTIONS = 65_536  # OD-1 hard limit; F22 is exactly fx-0.1 below it, and evictions are counted
DISPLAY_RETENTION_S = 600  # per-source dashboard state is forgotten after this much silence


def dumpcap_command(interface, port, dumpcap=None):
    """Full snap length and pcap on stdout. The filter only sees MQTT, so nothing else on the host is read."""
    return [dumpcap or os.environ.get("DUMPCAP_PATH") or shutil.which("dumpcap") or DEFAULT_DUMPCAP, "-i", interface, "-f", f"tcp port {port}", "-P", "-w", "-", "-q"]


def tie_to_this_process(process):
    """Windows: the capture dies with the IDS, even on a hard kill. On Linux dumpcap gets SIGPIPE at its next packet, or use systemd's cgroup."""
    if os.name != "nt":
        return
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
    kernel.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)

    class Limits(ctypes.Structure):
        _fields_ = [("a", ctypes.c_int64), ("b", ctypes.c_int64), ("LimitFlags", wintypes.DWORD), ("c", ctypes.c_size_t), ("d", ctypes.c_size_t), ("e", wintypes.DWORD), ("f", ctypes.c_size_t), ("g", wintypes.DWORD), ("h", wintypes.DWORD)]

    class Extended(ctypes.Structure):
        _fields_ = [("basic", Limits), ("io", ctypes.c_uint64 * 6), ("x", ctypes.c_size_t * 4)]

    global _job
    if _job is None:
        _job = kernel.CreateJobObjectW(None, None)
        info = Extended()
        info.basic.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        kernel.SetInformationJobObject(_job, 9, ctypes.byref(info), ctypes.sizeof(info))
    handle = kernel.OpenProcess(0x0101, False, process.pid)  # PROCESS_TERMINATE | PROCESS_SET_QUOTA
    kernel.AssignProcessToJobObject(_job, handle)
    kernel.CloseHandle(wintypes.HANDLE(handle))


_job = None


class Pipeline:
    """Everything after the decoder. Thread-safe, because the live timer and the capture thread both advance windows."""

    def __init__(self, store: EventStore, detector: Optional[Detector], window_s, port, source_key, schedule_path=None, clock=time.time, max_f22_connections=MAX_F22_CONNECTIONS):
        self.store, self.detector, self.window_s, self.clock = store, detector, window_s, clock
        self.window_ns = window_s * 10 ** 9
        self.key = source_key
        self.aggregator = FeatureAggregator(window_s=window_s, broker_port=port, source_key=source_key, max_open_connections=max_f22_connections)
        self._pruned_at = None
        tau = detector.tau if detector else 1.0
        self.engine = AlertEngine(tau, window_s=window_s, explain=detector.explain if detector else None, clock=lambda: self.clock())
        self.lock = threading.Lock()
        self.counters = Counter()
        self.model_errors = 0
        self.source_rates, self.source_state, self.last_seen = {}, {}, {}
        self.schedule_path = Path(schedule_path) if schedule_path else None
        self._schedule, self._schedule_mtime, self._announced, self._devices_mtime = None, None, set(), None
        self.stage_samples = []

    def schedule(self):
        """The runner's ground truth, re-read when it changes. Sources are pseudonymized here, so they never reach the store raw."""
        if self.schedule_path is None or not self.schedule_path.exists():
            return None
        try:
            mtime = self.schedule_path.stat().st_mtime
            if mtime != self._schedule_mtime:
                entries = json.loads(self.schedule_path.read_text())
                self._schedule = [{"source_key": self.key(e["source"]), "family": e["family"], "episode": e["episode"], "start_ns": int(e["start_epoch"] * 10 ** 9), "end_ns": int(e["end_epoch"] * 10 ** 9)} for e in entries]
                self._schedule_mtime = mtime
                for entry in self._schedule:
                    # A later simulation restarts episode numbers, so the start time is part of the identity.
                    if (entry["episode"], entry["start_ns"]) not in self._announced:
                        self._announced.add((entry["episode"], entry["start_ns"]))
                        self.store.write("run_marker", entry["start_ns"] / 1e9, {"marker": "scheduled_attack", **entry, "label": "scheduled attack (ground truth from runner)"})
        except (OSError, ValueError, KeyError, TypeError):
            self.counters["schedule_read_errors"] += 1
        self._read_devices()
        return self._schedule

    def _read_devices(self):
        """Scenario device profiles from the runner, pseudonymized like sources. Topology metadata only; never used for detection."""
        path = self.schedule_path.with_name("devices.json")
        try:
            mtime = path.stat().st_mtime
            if mtime == self._devices_mtime:
                return
            self._devices_mtime = mtime
            devices = {self.key(source): str(profile) for source, profile in json.loads(path.read_text()).items()}
            self.store.write("run_marker", time.time(), {"marker": "scenario_devices", "devices": devices, "label": "simulated device profiles from the lab runner"})
        except FileNotFoundError:
            return
        except (OSError, ValueError, AttributeError):
            self.counters["schedule_read_errors"] += 1

    def handle_event(self, event):
        with self.lock:
            self.counters["packets"] += 1
            self.counters["mqtt_messages"] += len(event.mqtt)
            rows = self.aggregator.push(event)
            for row in rows:
                self.handle_row(row)

    def tick(self, now_ns):
        with self.lock:
            for row in self.aggregator.advance(now_ns - LIVE_LAG_NS):
                self.handle_row(row)

    def finish(self):
        with self.lock:
            for row in self.aggregator.finish():
                self.handle_row(row)

    def handle_row(self, row):
        features_done = time.perf_counter_ns()
        wall_features = self.clock()
        try:
            validate_row(row)
        except ValueError:
            self.counters["invalid_rows"] += 1
            return
        predicted, score = None, None
        if self.detector:
            try:
                predicted, score = self.detector.score(row.features)
            except Exception as error:  # a broken model must never stop monitoring
                self.model_errors += 1
                log.warning("model failed on a window: %s", type(error).__name__)
        inference_done = time.perf_counter_ns()
        window_id = uuid.uuid4().hex
        try:
            state, alerts = self.engine.observe(row.source_key, row.window_start_ns, window_id, row.features, predicted, score)
        except Exception as error:
            self.model_errors += 1
            log.warning("alert evaluation failed: %s", type(error).__name__)
            state, alerts = "normal", []
        alert_done = time.perf_counter_ns()
        window_end = (row.window_start_ns + self.window_ns) / 1e9
        self._prune(row.window_start_ns)
        stage = {"window_close_to_features": max(wall_features - window_end, 0) * 1000, "inference": (inference_done - features_done) / 1e6,
                 "alert_build": (alert_done - inference_done) / 1e6, "processing_total": max(self.clock() - window_end, 0) * 1000}
        self.stage_samples.append(stage)
        del self.stage_samples[:-1000]
        self.source_rates[row.source_key] = (row.features[F12] + row.features[FEATURE_IDS.index("F09")]) / self.window_s
        self.source_state[row.source_key] = {"state": state, "score": score, "predicted": predicted if state != "normal" else "benign", "window": row.window_start_ns / 1e9}
        self.last_seen[row.source_key] = window_end
        ground_truth = None
        schedule = self.schedule()
        if schedule is not None:
            ground_truth = next((e["family"] for e in schedule if e["source_key"] == row.source_key and row.window_start_ns < e["end_ns"] and e["start_ns"] < row.window_start_ns + self.window_ns), "benign")
        self.store.write("window", window_end, {"window_id": window_id, "window_start": row.window_start_ns / 1e9, "window_end": window_end, "source_key": row.source_key,
                                                 "features": row.as_dict(), "complete": row.complete, "prediction": predicted, "score": score, "state": state, "model_id": self.detector.model_id if self.detector else None,
                                                 "extractor_version": row.extractor_version, "ground_truth": ground_truth, "stage_latency_ms": stage})
        self.counters["windows"] += 1
        for alert in alerts:
            alert = {k: v for k, v in alert.items() if k != "update"}
            status = ground_truth_status(alert, schedule, self.window_ns)
            self.store.write("alert", alert["start_ns"] / 1e9, {**alert, "status": status, "model_id": self.detector.model_id if self.detector else None, "extractor_version": row.extractor_version})
            self.counters["alerts"] += 1


    def _prune(self, window_start_ns):
        """Once per window: bounds per-source state under source churn. Alert pruning is exact; display state is cosmetic."""
        if self._pruned_at == window_start_ns:
            return
        self._pruned_at = window_start_ns
        self.engine.prune(window_start_ns)
        horizon = window_start_ns / 1e9 - DISPLAY_RETENTION_S
        for key in [k for k, t in self.last_seen.items() if t < horizon]:
            for table in (self.last_seen, self.source_rates, self.source_state):
                table.pop(key, None)


class Monitor(threading.Thread):
    """1 Hz resource and topology events. Temperature is reported only where the platform has a sensor, never as zero."""

    def __init__(self, pipeline, stats, capture_process=None, stop=None, broker_name="mosquitto", interval=1.0, enabled=lambda: True):
        super().__init__(daemon=True)
        self.pipeline, self.stats, self.capture, self.stop_event, self.broker_name, self.interval, self.enabled = pipeline, stats, capture_process, stop, broker_name, interval, enabled
        self.me = psutil.Process()
        self.broker = None
        self.child = None
        self.me.cpu_percent()

    def _find_broker(self):
        if self.broker and self.broker.is_running():
            return self.broker
        for process in psutil.process_iter(["name"]):
            if self.broker_name in (process.info["name"] or "").lower():
                self.broker = process
                process.cpu_percent()
                return process
        self.broker = None
        return None

    def _temperature(self):
        reader = getattr(psutil, "sensors_temperatures", None)
        sensors = reader() if reader else {}
        for entries in sensors.values():
            if entries:
                return entries[0].current
        return None

    def run(self):
        last = dict(self.pipeline.counters)
        last_t = time.monotonic()
        while not self.stop_event.wait(self.interval):
            try:
                now, elapsed = time.monotonic(), None
                elapsed, last_t = now - last_t, now
                counters = dict(self.pipeline.counters)
                rate = {k: (counters.get(k, 0) - last.get(k, 0)) / elapsed for k in ("packets", "mqtt_messages", "windows")}
                last = counters
                broker = self._find_broker()
                body = {"ids_cpu_pct": self.me.cpu_percent() / psutil.cpu_count(), "ids_rss_mb": self.me.memory_info().rss / 1048576, "capture_cpu_pct": None, "capture_rss_mb": None,
                        "broker_running": broker is not None, "broker_cpu_pct": broker.cpu_percent() / psutil.cpu_count() if broker else None, "broker_rss_mb": broker.memory_info().rss / 1048576 if broker else None,
                        "soc_temp_c": self._temperature(), "throttled": None, "pkts_per_s": rate["packets"], "mqtt_msgs_per_s": rate["mqtt_messages"], "windows_per_s": rate["windows"], "capture_drops_total": None,
                        "tcp_gaps_total": self.stats["tcp_sequence_gaps"], "late_events_total": self.pipeline.aggregator.stats["late_events"], "malformed_frames_total": self.stats["malformed_frames"], "tracked_f22_connections": self.pipeline.aggregator.open_connections, "evicted_f22_connections": self.pipeline.aggregator.stats["evicted_connections"], "tracked_sources": len(self.pipeline.engine.sources),
                        "decoder_streams": self.stats["streams_peak"], "model_errors": self.pipeline.model_errors, "store_write_errors": self.pipeline.store.write_errors, "model_loaded": self.pipeline.detector is not None,
                        "ids_enabled": self.enabled(), "total_cpus": psutil.cpu_count()}
                if self.capture and self.capture() is not None:
                    try:
                        process = self.child if self.child and self.child.pid == self.capture().pid else psutil.Process(self.capture().pid)
                        if process is not self.child:
                            self.child = process
                            process.cpu_percent()
                        body["capture_cpu_pct"] = process.cpu_percent() / psutil.cpu_count()
                        body["capture_rss_mb"] = process.memory_info().rss / 1048576
                    except psutil.Error:
                        pass
                self.pipeline.store.write("resource", time.time(), body)
                now_wall = time.time()
                silent_after = 3 * self.pipeline.window_s
                self.pipeline.store.write("topology", now_wall, {"nodes": [{"source_key": k, "msgs_per_s": self.pipeline.source_rates.get(k, 0), **self.pipeline.source_state.get(k, {}), "silent": now_wall - self.pipeline.last_seen.get(k, now_wall) > silent_after}
                                                                          for k in list(self.pipeline.source_state)[-200:]]})
            except psutil.Error:
                continue
            except Exception as error:  # one bad tick must not end resource/topology reporting for the rest of the run
                print(f"monitor: {type(error).__name__}: {error}", file=sys.stderr, flush=True)


def run_live(args, store, detector, key):
    """Runs capture while enabled and restarts it if it dies. The control row flips state without touching the broker."""
    stop = threading.Event()
    pipeline = Pipeline(store, detector, args.window, args.port, key, args.schedule)
    stats = Counter()
    current = {"process": None}
    enabled = lambda: store.control("enabled", "true") == "true"
    monitor = Monitor(pipeline, stats, lambda: current["process"], stop, enabled=enabled)
    monitor.start()

    def request_stop(*_):
        stop.set()
        if current["process"]:
            current["process"].terminate()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    def timer():
        while not stop.wait(TIMER_S):
            pipeline.tick(time.time_ns())

    threading.Thread(target=timer, daemon=True).start()
    backoff = 1
    store.write("run_marker", time.time(), {"marker": "run_start", "scenario": args.scenario, "extractor_version": EXTRACTOR_VERSION, "service_version": SERVICE_VERSION,
                                             "model_id": detector.model_id if detector else None, "adapter": "decoder", "window_s": args.window})
    while not stop.is_set():
        if not enabled():
            stop.wait(1)
            continue
        command = dumpcap_command(args.capture, args.port, args.dumpcap)
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except OSError as error:
            log.error("cannot start capture: %s", error.strerror)
            stop.wait(backoff)
            backoff = min(backoff * 2, 30)
            continue
        tie_to_this_process(process)
        current["process"] = process
        reader_done = threading.Event()

        def watcher():
            # Disabling must stop capture promptly even when no packet arrives to wake the reader.
            while not stop.is_set() and not reader_done.is_set():
                if not enabled():
                    process.terminate()
                    return
                stop.wait(0.5)

        threading.Thread(target=watcher, daemon=True).start()
        started = time.monotonic()
        try:
            for event in decode_packets(read_stream(process.stdout), stats, broker_port=args.port):
                pipeline.handle_event(event)
        except Exception as error:  # a bad record ends this capture run, and the loop below starts a new one
            log.warning("capture stream ended: %s", type(error).__name__)
        reader_done.set()
        if process.poll() is None:
            process.terminate()
        process.wait()
        current["process"] = None
        if time.monotonic() - started > 30:
            backoff = 1
        if not stop.is_set() and enabled():
            pipeline.counters["capture_restarts"] += 1
            stop.wait(backoff)
            backoff = min(backoff * 2, 30)
    pipeline.finish()
    store.write("run_marker", time.time(), {"marker": "run_stop"})


def run_replay(args, store, detector, key):
    """Replays a recorded capture through the same code path. Provenance is fixed to replay when the store is created."""
    pipeline = Pipeline(store, detector, args.window, args.port, key, args.schedule, clock=None)
    last_ns = None
    replay_now = {"t": 0.0}
    pipeline.clock = lambda: replay_now["t"]
    stats = Counter()
    store.write("run_marker", time.time(), {"marker": "run_start", "scenario": args.scenario, "extractor_version": EXTRACTOR_VERSION, "model_id": detector.model_id if detector else None,
                                             "adapter": "decoder", "window_s": args.window})
    for event in decode_packets(read_records(args.replay), stats, broker_port=args.port):
        if last_ns is not None and args.speed:
            time.sleep(max(event.ts_ns - last_ns, 0) / 1e9 / args.speed)
        last_ns = event.ts_ns
        replay_now["t"] = event.ts_ns / 1e9
        pipeline.handle_event(event)
    pipeline.finish()
    store.write("run_marker", time.time(), {"marker": "run_stop"})
    return pipeline, stats


def load_detector(path):
    if not path:
        return None
    try:
        return Detector(path)
    except ModelRefused as error:
        log.error("running without inference: %s", error)
        return None


def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--model")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--window", type=int, default=5, choices=(1, 5, 10))
    parser.add_argument("--capture", default=r"\Device\NPF_Loopback")
    parser.add_argument("--dumpcap")
    parser.add_argument("--replay")
    parser.add_argument("--speed", type=float, default=0, help="replay speed; 0 means as fast as possible")
    parser.add_argument("--schedule", help="JSON ground truth from the lab runner")
    parser.add_argument("--scenario", default="unspecified")
    parser.add_argument("--traffic-source", default="mixed")
    return parser


def main():
    args = build_parser().parse_args()
    logging.basicConfig(level=logging.INFO, format='{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}')
    provenance = "replay" if args.replay else "live"  # set here only, so a replay can never report itself as live
    store = EventStore(args.db, uuid.uuid4().hex[:12], provenance, args.traffic_source)
    detector = load_detector(args.model)
    key = pseudonymizer(secrets.token_bytes(32))
    if args.replay:
        run_replay(args, store, detector, key)
    else:
        run_live(args, store, detector, key)


if __name__ == "__main__":
    main()
