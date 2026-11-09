"""Real broker, real loopback capture, real IDS process. Skipped where Mosquitto or dumpcap is missing. Windows loopback only."""
import json
import os
import shutil
import signal
import sqlite3
from contextlib import closing  # sqlite3's own context manager commits but never closes: use both
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil
import pytest

from dashboard.api.__main__ import check_bind
from ids.service import DEFAULT_DUMPCAP
from lab import attacks, gateway, run as lab_run, wire

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.integration
AVAILABLE = (shutil.which("mosquitto") or (gateway.TOOLS / "sbin" / "mosquitto.exe").exists()) and (shutil.which("dumpcap") or Path(DEFAULT_DUMPCAP).exists())
PORT = 18870


def test_api_refuses_to_bind_beyond_loopback_without_a_token():
    check_bind("127.0.0.1", None)
    check_bind("192.168.1.2", "token")
    with pytest.raises(SystemExit):
        check_bind("192.168.1.2", None)


def start_ids(db, *extra):
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    return subprocess.Popen([sys.executable, "-m", "ids.service", "--db", str(db), "--port", str(PORT), "--window", "1", *extra], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0)


def wait_rows(db, sql, minimum, seconds=25):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            with closing(sqlite3.connect(db, timeout=2)) as c, c:
                value = c.execute(sql).fetchone()[0]
            if value >= minimum:
                return value
        except sqlite3.Error:
            pass
        time.sleep(0.2)
    return None


def stop_process(process):
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


@pytest.mark.skipif(not AVAILABLE, reason="no Mosquitto or dumpcap")
def test_broker_keeps_serving_through_ids_start_pause_kill_and_restart(tmp_path):
    db = tmp_path / "events.sqlite"
    broker, cred = gateway.start_broker(tmp_path / "broker", PORT)
    ids = None
    stop = threading.Event()
    delivered = []

    def publisher():
        while not stop.is_set():
            try:
                c = wire.Client("127.0.1.60", ("127.0.0.1", PORT))
                assert c.login("itest", *cred) == 0
                while not stop.is_set():
                    c.publish("itest/a", b"1", qos=1)  # the acknowledgement proves the broker handled it
                    delivered.append(time.monotonic())
                    time.sleep(0.05)
                c.close()
            except OSError:
                time.sleep(0.2)

    try:
        assert lab_run.wait_for_port(PORT)
        thread = threading.Thread(target=publisher, daemon=True)
        thread.start()
        ids = start_ids(db)
        assert wait_rows(db, "SELECT COUNT(*) FROM events WHERE event_type='window'", 2), "IDS saw no live traffic"

        # Pause through the control row: capture stops, the broker and IDS process stay up.
        with closing(sqlite3.connect(db, timeout=5)) as c, c:
            c.execute("INSERT OR REPLACE INTO control(key, value) VALUES ('enabled','false')")
        time.sleep(3)
        with closing(sqlite3.connect(db, timeout=5)) as c, c:
            before = c.execute("SELECT COUNT(*) FROM events WHERE event_type='window'").fetchone()[0]
        count_before = len(delivered)
        time.sleep(3)
        with closing(sqlite3.connect(db, timeout=5)) as c, c:
            after = c.execute("SELECT COUNT(*) FROM events WHERE event_type='window'").fetchone()[0]
        assert after == before and len(delivered) > count_before and ids.poll() is None and broker.poll() is None
        with closing(sqlite3.connect(db, timeout=5)) as c, c:
            c.execute("INSERT OR REPLACE INTO control(key, value) VALUES ('enabled','true')")
        assert wait_rows(db, "SELECT COUNT(*) FROM events WHERE event_type='window'", after + 2), "capture did not resume"

        # Kill the IDS hard: the broker must not notice, and the store must stay readable.
        capture = next(c for c in psutil.Process(ids.pid).children(recursive=True) if "dumpcap" in c.name().lower())  # recursive: a venv python.exe is a launcher
        ids.kill()
        ids.wait()
        psutil.wait_procs([capture], timeout=5)
        assert not capture.is_running(), "a hard kill left dumpcap running"
        count_before = len(delivered)
        time.sleep(2)
        assert len(delivered) > count_before and broker.poll() is None
        with closing(sqlite3.connect(db, timeout=5)) as c, c:
            assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            windows = c.execute("SELECT COUNT(*) FROM events WHERE event_type='window'").fetchone()[0]

        # Restart with a model path that does not exist: it runs without inference, and its pseudonyms come from a new key.
        ids = start_ids(db, "--model", str(tmp_path / "no-such-model"))
        assert wait_rows(db, "SELECT COUNT(*) FROM events WHERE event_type='window'", windows + 2), "restart lost monitoring"
        with closing(sqlite3.connect(db, timeout=5)) as c, c:
            bodies = [json.loads(r[0]) for r in c.execute("SELECT body FROM events ORDER BY id DESC LIMIT 200")]
            dump = "\n".join(c.iterdump())
        assert any(b["event_type"] == "window" and b["prediction"] is None for b in bodies)
        assert {b["provenance"] for b in bodies} == {"live"}
        assert "127.0.1.60" not in dump and "itest" not in dump and cred[1] not in dump
    finally:
        stop.set()
        if ids:
            stop_process(ids)
        gateway.stop(broker)
