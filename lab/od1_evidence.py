"""OD-1 evidence on lab captures: how many fx-0.1 rows does the proposed 1.5 K keep-alive expiry change?

python -m lab.od1_evidence
Each recorded lab capture is decoded once and extracted twice, with and without expiry; rows are compared feature by feature.
Lab captures only; T3.5 holds the MQTTset evidence. Nothing here changes a model or a frozen result.
"""
import json
import time
from collections import Counter
from pathlib import Path

from ids.decoder import decode_pcap
from ids.features import FEATURE_IDS, extract_features

ROOT = Path(__file__).resolve().parents[1]
LAB = Path.home() / "edgewatch-data" / "lab"




def main():
    from ids.training import BENIGN_RUNS, LAB_RUNS, RUN_PORTS
    ports = {}
    for campaign in ("campaign1", "campaign2"):
        ports.update({(campaign, r): p for r, p in {**LAB_RUNS, **(BENIGN_RUNS if campaign == "campaign1" else {})}.items()})
    for campaign, runs in RUN_PORTS.items():
        ports.update({(campaign, r): p for r, p in runs.items()})
    ports[("campaign1", "stealth")] = 18843
    ports[("campaign7", "ben_smart_home")] = 18848
    out, totals = [], Counter()
    for (campaign, run), port in sorted(ports.items()):
        capture = LAB / campaign / run / "capture.pcap"
        if not capture.exists():
            continue
        events = list(decode_pcap(capture, Counter(), broker_port=port))
        base = list(extract_features(events, broker_port=port))
        expiring = list(extract_features(events, broker_port=port, keepalive_expiry=1.5))
        changed = Counter()
        rows_changed = 0
        for a, b in zip(base, expiring):
            assert (a.window_start_ns, a.source_key) == (b.window_start_ns, b.source_key)
            diff = [f for f, x, y in zip(FEATURE_IDS, a.features, b.features) if x != y]
            rows_changed += bool(diff)
            changed.update(diff)
        entry = {"run": f"{campaign}/{run}", "rows": len(base), "rows_changed": rows_changed, "features_changed": dict(changed), "row_count_equal": len(base) == len(expiring)}
        out.append(entry)
        totals["rows"] += len(base)
        totals["rows_changed"] += rows_changed
        print(entry, flush=True)
    body = {"experiment": "ENG-OD1-expiry", "run_date": time.strftime("%Y-%m-%d"), "proposal": "fx-0.1 plus 1.5 K keep-alive expiry (OD-1)", "runs": out, "totals": dict(totals),
            "note": "Lab captures on Windows loopback. A missed FIN or RST is rare on loopback, so zero changes here do not show the expiry is harmless on a lossy network; they show it does not disturb these runs."}
    folder = ROOT / "results" / "ENG-OD1-expiry"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "metrics.json").write_text(json.dumps(body, indent=1))
    print(json.dumps(body["totals"]))


if __name__ == "__main__":
    main()
