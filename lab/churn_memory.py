"""Does IDS memory plateau under sustained connection churn? (SG-09 follow-up to ENG-P2-soak-v2.)

python -m lab.churn_memory [--connections 200000]
Feeds synthetic loopback churn (one client, ephemeral ports reused like Windows, 49152-65535) through the real decoder,
extractor, alert engine and a SQLite store, one connection per 10 ms of capture time, and samples traced Python memory.
Ranking-only, in-process; RSS includes the interpreter and imports, so it is reported separately.
"""
import argparse
import json
import platform
import struct
import tempfile
import time
import tracemalloc
from collections import Counter
from pathlib import Path

import psutil

from ids.decoder import decode_packets
from ids.pipeline import pseudonymizer
from ids.service import Pipeline
from ids.store import EventStore

ROOT = Path(__file__).resolve().parents[1]
CLIENT, BROKER = bytes([127, 0, 5, 1]), bytes([127, 0, 0, 1])
SYN, ACK, FIN, PSH = 2, 16, 1, 8


def frame(t_ns, src, dst, sport, dport, seq, flags, data=b""):
    tcp = struct.pack(">HHIIBBHHH", sport, dport, seq & 0xFFFFFFFF, 1, 0x50, flags, 8192, 0, 0) + data
    ip = struct.pack(">BBHHHBBH4s4s", 0x45, 0, 20 + len(tcp), 1, 0, 64, 6, 0, src, dst) + tcp
    return t_ns, 1, b"\x02" * 6 + b"\x04" * 6 + b"\x08\x00" + ip


def mstr(b):
    return struct.pack(">H", len(b)) + b


CONNECT = bytes([0x10]) + bytes([len(b := mstr(b"MQTT") + bytes([4, 0xC2]) + struct.pack(">H", 60) + mstr(b"c") + mstr(b"u") + mstr(b"p"))]) + b
CONNACK = bytes([0x20, 2, 0, 0])


def churn(n, start_ns):
    for i in range(n):
        port, t = 49152 + i % 16384, start_ns + i * 10_000_000
        yield frame(t, CLIENT, BROKER, port, 1883, 1000, SYN)
        yield frame(t + 1, BROKER, CLIENT, 1883, port, 9000, SYN | ACK)
        yield frame(t + 2, CLIENT, BROKER, port, 1883, 1001, PSH | ACK, CONNECT)
        yield frame(t + 3, BROKER, CLIENT, 1883, port, 9001, PSH | ACK, CONNACK)
        yield frame(t + 4, CLIENT, BROKER, port, 1883, 1001 + len(CONNECT), FIN | ACK)
        yield frame(t + 5, BROKER, CLIENT, 1883, port, 9005, FIN | ACK)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--connections", type=int, default=200_000)
    args = parser.parse_args()
    me = psutil.Process()
    samples = []
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        store = EventStore(Path(tmp) / "e.sqlite", "churn", "replay")
        pipeline = Pipeline(store, None, 5, 1883, pseudonymizer(), clock=time.time)
        stats = Counter()
        tracemalloc.start()
        every = args.connections // 10
        for i, event in enumerate(decode_packets(churn(args.connections, 10 ** 18), stats, broker_port=1883)):
            pipeline.handle_event(event)
            if (i + 1) % (every * 2) == 0:  # two events with MQTT or flags per connection reach here on average
                samples.append({"events": i + 1, "traced_mib": round(tracemalloc.get_traced_memory()[0] / 2 ** 20, 2), "rss_mb": round(me.memory_info().rss / 2 ** 20, 1),
                                "decoder_streams_peak": stats["streams_peak"], "tracked_f22": pipeline.aggregator.open_connections, "alert_sources": len(pipeline.engine.sources)})
        pipeline.finish()
        tracemalloc.stop()
        store.db.close()
    later = [s["traced_mib"] for s in samples[len(samples) // 2:]]
    body = {"experiment": "ENG-P4-churn-memory", "run_date": time.strftime("%Y-%m-%d"), "device": f"development laptop ({platform.processor()}), not a gateway",
            "connections": args.connections, "samples": samples, "second_half_traced_growth_mib": round(max(later) - min(later), 2) if later else None,
            "note": "Synthetic churn through the real in-process pipeline without a model; ephemeral ports reused as on Windows. Traced memory is Python allocations only."}
    out = ROOT / "results" / "ENG-P4-churn-memory"
    out.mkdir(parents=True, exist_ok=True)
    (out / "metrics.json").write_text(json.dumps(body, indent=1))
    print(json.dumps({k: body[k] for k in ("connections", "second_half_traced_growth_mib")}), *samples, sep="\n")


if __name__ == "__main__":
    main()
