"""Offline pipeline tests on invented captures."""
import json
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ids import FEATURE_IDS, WindowRow  # noqa: E402
from ids import pipeline  # noqa: E402


def write_capture(path):
    topic = b"SECRET-TOPIC"
    data = bytes([0x30, 2 + len(topic)]) + struct.pack(">H", len(topic)) + topic
    out = struct.pack("<IHHiIII", 0xa1b2c3d4, 2, 4, 0, 0, 65535, 1)
    for i in range(20):
        tcp = struct.pack(">HHIIBBHHH", 5000, 1883, 1000 + i * len(data), 1, 0x50, 0x18, 8192, 0, 0) + data
        ip = struct.pack(">BBHHHBBH4s4s", 0x45, 0, 20 + len(tcp), 0, 0, 64, 6, 0, bytes([192, 0, 2, 1]), bytes([192, 0, 2, 9]))
        frame = b"\x02" * 6 + b"\x04" * 6 + b"\x08\x00" + ip + tcp
        out += struct.pack("<IIII", 100 + i, 0, len(frame), len(frame)) + frame
    path.write_bytes(out)
    return path


def row(**changes):
    values = dict(window_start_ns=0, source_key="s", features=tuple(1.0 if i not in (19, 20) else 0.5 for i in range(26)))
    return WindowRow(**{**values, **changes})


def test_valid_row_passes():
    assert pipeline.validate_row(row())


@pytest.mark.parametrize("bad", [
    row(features=(1.0,) * 25),
    row(features=(float("nan"),) + (0.0,) * 25),
    row(features=(-1.0,) + (0.0,) * 25),
    row(features=(0.0,) * 19 + (1.5,) + (0.0,) * 6),
    row(extractor_version="fx-9"),
])
def test_invalid_rows_are_refused(bad):
    with pytest.raises(pipeline.SchemaError):
        pipeline.validate_row(bad)


def test_pseudonyms_are_stable_in_a_run_and_differ_across_runs():
    a, b = pipeline.pseudonymizer(), pipeline.pseudonymizer()
    assert a("192.0.2.1") == a("192.0.2.1") != b("192.0.2.1")
    assert a("192.0.2.1") != a("192.0.2.2") and "192.0.2.1" not in a("192.0.2.1")


def test_run_writes_a_table_and_report_without_raw_identities(tmp_path):
    capture = write_capture(tmp_path / "c.pcap")
    report = pipeline.run(capture, tmp_path / "out")
    import pandas as pd
    table = pd.read_parquet(tmp_path / "out" / "rows_w5.parquet")
    assert report["rows"] == len(table) == 4 and list(table.columns[3:]) == list(FEATURE_IDS)
    assert report["decoder"]["frames"] == 20 and report["sources_pseudonymous"] and "D-01" in report["status"]
    everything = table.to_csv() + (tmp_path / "out" / "diagnostics_w5.json").read_text()
    assert "192.0.2" not in everything and "SECRET" not in everything


def test_run_is_reproducible_with_raw_sources(tmp_path):
    capture = write_capture(tmp_path / "c.pcap")
    a = pipeline.run(capture, tmp_path / "a", raw_sources=True)
    b = pipeline.run(capture, tmp_path / "b", raw_sources=True)
    assert a["rows_digest"] == b["rows_digest"] is not None
