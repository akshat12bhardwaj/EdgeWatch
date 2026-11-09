"""ENG-P3: state bounds and per-stage throughput on this machine (SG-09). Deterministic inputs; ranking-only numbers.

python -m lab.bench [--capture <pcap>] [--model <bundle>]
(a) F22 open-connection state with and without the OD-1 hard limit, under up to 300,000 never-closed connections.
(b) Per-source alert state under source churn, with and without pruning.
(c) Decode, feature and inference cost per stage on a real recorded lab capture.
"""
import argparse
import gc
import json
import platform
import time
import tracemalloc
from collections import Counter
from pathlib import Path

from ids.alerts import AlertEngine
from ids.decoder import decode_pcap
from ids.detector import Detector
from ids.features import FeatureAggregator, MqttMessage, PacketEvent, extract_features

ROOT = Path(__file__).resolve().parents[1]
DATA = Path.home() / "edgewatch-data"


def held(n):
    for i in range(n):
        src = f"10.{i >> 16 & 255}.{i >> 8 & 255}.{i & 255}"
        yield PacketEvent(i * 1000, src, "10.255.0.1", 6000, 1883, syn=True)
        yield PacketEvent(i * 1000 + 500, src, "10.255.0.1", 6000, 1883, mqtt=(MqttMessage(1, 12, keepalive=65535),))


def f22_state(n, cap):
    gc.collect()
    tracemalloc.start()
    agg = FeatureAggregator(max_open_connections=cap)
    for e in held(n):
        agg.push(e)
    agg.advance(10 ** 15)
    current = tracemalloc.get_traced_memory()[0]
    tracemalloc.stop()
    return {"connections_offered": n, "cap": cap, "tracked": agg.open_connections, "evicted": agg.stats["evicted_connections"], "retained_mib": round(current / 2 ** 20, 2)}


def churn_state(sources, prune):
    engine = AlertEngine(0.5)
    w = 5 * 10 ** 9
    for i in range(sources):
        if prune:
            engine.prune(i * w)
        engine.observe(f"s{i}", i * w, str(i), (0.0,) * 26, None, None)
    return {"sources_seen": sources, "prune": prune, "sources_tracked": len(engine.sources)}


def stages(capture, port, model):
    stats = Counter()
    detector = Detector(model)  # loaded outside the timed stages
    detector.score((0.0,) * 26)
    t0 = time.perf_counter()
    events = list(decode_pcap(capture, stats, broker_port=port))
    t1 = time.perf_counter()
    rows = list(extract_features(events, broker_port=port, max_open_connections=65_536))
    t2 = time.perf_counter()
    scored = [detector.score(r.features) for r in rows]
    t3 = time.perf_counter()
    engine = AlertEngine(detector.tau)
    for r, (cls, score) in zip(rows, scored):
        engine.observe(r.source_key, r.window_start_ns, "w", r.features, cls, score)
    t4 = time.perf_counter()
    # E7 analogue: evidence is built only when an alert opens, so its cost is per alert, not per window.
    flagged = [(r, cls) for r, (cls, score) in zip(rows, scored) if score >= detector.tau and cls != "benign"] or [(r, scored[0][0]) for r in rows[:50]]
    t5 = time.perf_counter()
    for r, cls in flagged:
        detector.explain(r.features, cls)
    explain_us = (time.perf_counter() - t5) / len(flagged) * 1e6
    return {"capture": str(capture.relative_to(DATA)) if DATA in capture.parents else capture.name, "frames": stats["frames"], "events": len(events), "mqtt_messages": sum(len(e.mqtt) for e in events), "windows": len(rows),
            "decode_events_per_s": round(len(events) / (t1 - t0)), "decode_us_per_event": round((t1 - t0) / len(events) * 1e6, 2),
            "features_us_per_event": round((t2 - t1) / len(events) * 1e6, 2), "inference_us_per_window": round((t3 - t2) / len(rows) * 1e6, 1),
            "alert_policy_us_per_window": round((t4 - t3) / len(rows) * 1e6, 1), "end_to_end_offline_events_per_s": round(len(events) / (t4 - t0)),
            "evidence_us_per_alert": round(explain_us, 1), "evidence_samples": len(flagged)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", default=str(DATA / "lab" / "campaign6" / "ep_s2" / "capture.pcap"))
    parser.add_argument("--port", type=int, default=18842)
    parser.add_argument("--model", default=str(DATA / "models" / "ew-dt12-lab-v6"))
    args = parser.parse_args()
    body = {"experiment": "ENG-P3-bounds", "run_date": time.strftime("%Y-%m-%d"), "device": f"development laptop ({platform.processor()}), not a gateway", "python": platform.python_version(),
            "note": "Single run, synthetic inputs for (a) and (b), a recorded lab capture for (c). Offline, one thread, ranking only; live capture adds dumpcap and a 1 s lag.",
            "f22_state": [f22_state(n, cap) for n in (10_000, 100_000, 300_000) for cap in (None, 65_536)],
            "alert_state_under_churn": [churn_state(20_000, p) for p in (False, True)],
            "stages": stages(Path(args.capture), args.port, args.model)}
    out = ROOT / "results" / "ENG-P3-bounds"
    out.mkdir(parents=True, exist_ok=True)
    (out / "metrics.json").write_text(json.dumps(body, indent=1))
    print(json.dumps(body, indent=1))


if __name__ == "__main__":
    main()
