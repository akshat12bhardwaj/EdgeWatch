"""Offline pipeline: capture file -> decoder -> FeatureAggregator -> validated rows plus a diagnostics report.

python -m ids.pipeline <capture> <out dir> [--window 5] [--port 1883] [--raw-sources]

Outputs are engineering tables, not research feature tables: labels and the evaluation protocol stay open (D-01). Keep them outside Git.
"""
import argparse
import hashlib
import hmac
import json
import math
import secrets
from collections import Counter
from pathlib import Path
from typing import Callable, Iterable, Iterator, Optional

from .decoder import decode_pcap
from .features import EXTRACTOR_VERSION, FEATURE_IDS, FeatureAggregator, WindowRow

_FRACTIONS = (FEATURE_IDS.index("F20"), FEATURE_IDS.index("F21"))


class SchemaError(ValueError):
    """A row breaks the feature contract. Messages name the feature, never a source."""


def validate_row(row: WindowRow) -> WindowRow:
    if row.extractor_version != EXTRACTOR_VERSION:
        raise SchemaError("wrong extractor version")
    if len(row.features) != len(FEATURE_IDS):
        raise SchemaError("wrong feature count")
    for name, value in zip(FEATURE_IDS, row.features):
        if not math.isfinite(value) or value < 0:
            raise SchemaError(f"{name} is not a finite non-negative number")
    for i in _FRACTIONS:
        if row.features[i] > 1:
            raise SchemaError(f"{FEATURE_IDS[i]} is above 1")
    return row


def pseudonymizer(key: Optional[bytes] = None) -> Callable[[str], str]:
    """Run-scoped source pseudonym: stable inside a run, unlinkable across runs, and not reversible without the key."""
    key = key or secrets.token_bytes(32)
    return lambda source: "src-" + hmac.digest(key, source.encode(), "sha256").hex()[:12]


def rows_from_capture(path, stats: Optional[Counter] = None, window_s=5, broker_port=1883, source_key=None,
                      aggregator_stats: Optional[Counter] = None) -> Iterator[WindowRow]:
    aggregator = FeatureAggregator(window_s=window_s, broker_port=broker_port, source_key=source_key or pseudonymizer())
    for event in decode_pcap(path, stats, broker_port=broker_port):
        yield from map(validate_row, aggregator.push(event))
    yield from map(validate_row, aggregator.finish())
    if aggregator_stats is not None:
        aggregator_stats.update(aggregator.stats)


def digest_rows(rows: Iterable[WindowRow]) -> str:
    """Independent of source pseudonyms' key material only if sources are raw; use with stable keys when comparing runs."""
    h = hashlib.sha256()
    for r in rows:
        h.update(repr((r.window_start_ns, r.source_key, r.features, r.complete)).encode())
    return h.hexdigest()


# Diagnostics an operator needs to judge a table. Only counters; decoder stats never hold packet contents.
DIAGNOSTIC_KEYS = ("frames", "events", "mqtt_messages", "malformed_frames", "non_tcp_frames", "bad_metadata_frames", "truncated_tcp_frames",
                   "unsupported_link_frames", "ip_fragments", "ip_datagrams_reassembled", "ip_fragment_overlaps", "ip_fragments_expired",
                   "ip_fragments_invalid", "tcp_retransmitted_segments", "tcp_out_of_order_segments", "tcp_sequence_gaps", "partial_messages_discarded",
                   "oversized_messages_skipped", "invalid_fixed_header_events", "topic_mismatch_messages", "streams_evicted_limit", "streams_evicted_bytes",
                   "streams_evicted_idle")


def run(capture, out_dir, window_s=5, broker_port=1883, raw_sources=False):
    import pandas as pd  # offline only: the live path must not pay for pandas
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stats, aggregator_stats = Counter(), Counter()
    key = str if raw_sources else pseudonymizer()
    rows = list(rows_from_capture(capture, stats, window_s, broker_port, key, aggregator_stats))
    table = pd.DataFrame([r.features for r in rows], columns=FEATURE_IDS)
    table.insert(0, "window_start_ns", [r.window_start_ns for r in rows])
    table.insert(1, "source_key", [r.source_key for r in rows])
    table.insert(2, "complete", [r.complete for r in rows])
    name = f"rows_w{window_s}.parquet"
    table.to_parquet(out_dir / name, index=False)
    diagnostics = {"capture_name": Path(capture).name, "window_s": window_s, "extractor_version": EXTRACTOR_VERSION, "adapter": "decoder",
                   "rows": len(rows), "rows_digest": digest_rows(rows) if raw_sources else None,
                   "sources_pseudonymous": not raw_sources, "decoder": {k: stats[k] for k in DIAGNOSTIC_KEYS}, "extractor": dict(aggregator_stats),
                   "status": "engineering table; D-01 open, not a research feature table"}
    (out_dir / f"diagnostics_w{window_s}.json").write_text(json.dumps(diagnostics, indent=1))
    return diagnostics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("capture")
    parser.add_argument("out")
    parser.add_argument("--window", type=int, default=5)
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--raw-sources", action="store_true", help="only for lab captures, whose addresses are invented loopback ones")
    args = parser.parse_args()
    print(json.dumps(run(args.capture, args.out, args.window, args.port, args.raw_sources), indent=1))


if __name__ == "__main__":
    main()
