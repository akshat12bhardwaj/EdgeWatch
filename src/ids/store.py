"""SQLite event store shared by the IDS (writer) and the API (reader). WAL lets them run and restart independently."""
import json
import threading
import sqlite3
import time
from pathlib import Path

SCHEMA_VERSION = "1.0"
DEFAULT_MAX_EVENTS = 500_000  # about a week of 1 Hz resource plus window rows for a dozen sources; alerts are never pruned by this
EVENT_TYPES = ("window", "alert", "resource", "topology", "run_marker")
PROVENANCE = ("live", "replay", "synthetic")
DDL = """
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL, ts REAL NOT NULL, run_id TEXT NOT NULL,
                                   provenance TEXT NOT NULL, body TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS events_type_id ON events(event_type, id);
CREATE TABLE IF NOT EXISTS alerts (alert_id TEXT PRIMARY KEY, ts REAL NOT NULL, run_id TEXT NOT NULL, source_key TEXT NOT NULL, severity TEXT NOT NULL,
                                   provenance TEXT NOT NULL, body TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS alerts_ts ON alerts(ts);
CREATE TABLE IF NOT EXISTS control (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def connect(path, read_only=False):
    path = Path(path)
    if read_only:
        db = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=5, check_same_thread=False)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(path, timeout=5, check_same_thread=False)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=NORMAL")  # survives a process crash; a power cut can lose the last commits, not corrupt the file
        db.executescript(DDL)
    db.row_factory = sqlite3.Row
    return db


class EventStore:
    """Writes never raise into the capture path: a database failure is counted and reported, and detection continues."""

    def __init__(self, path, run_id, provenance, traffic_source="mixed", max_events=DEFAULT_MAX_EVENTS):
        if provenance not in PROVENANCE:
            raise ValueError("provenance must be live, replay or synthetic")
        self.path, self.run_id, self.provenance, self.traffic_source, self.max_events = path, run_id, provenance, traffic_source, max_events
        self.db = connect(path)
        self.write_errors = 0
        self._since_prune = 0
        # The capture thread and the 1 Hz Monitor share this connection; unserialized use raised SystemError and killed the Monitor.
        self._lock = threading.RLock()

    def envelope(self, event_type, ts, body):
        if event_type not in EVENT_TYPES:
            raise ValueError("unknown event type")
        return {"event_type": event_type, "ts": ts, "run_id": self.run_id, "provenance": self.provenance, "traffic_source": self.traffic_source,
                "schema_version": SCHEMA_VERSION, **body}

    def write(self, event_type, ts, body):
        event = self.envelope(event_type, ts, body)
        try:
            with self._lock, self.db:
                self.db.execute("INSERT INTO events(event_type, ts, run_id, provenance, body) VALUES (?,?,?,?,?)",
                                (event_type, ts, self.run_id, self.provenance, json.dumps(event, separators=(",", ":"))))
                if event_type == "alert":
                    self.db.execute("INSERT OR REPLACE INTO alerts(alert_id, ts, run_id, source_key, severity, provenance, body) VALUES (?,?,?,?,?,?,?)",
                                    (event["alert_id"], ts, self.run_id, event["source_key"], event["severity"], self.provenance, json.dumps(event, separators=(",", ":"))))
            self._since_prune += 1
            if self._since_prune >= 5000:
                self.prune()
            return event
        except (sqlite3.Error, SystemError):
            self.write_errors += 1
            return None

    def prune(self):
        self._since_prune = 0
        with self._lock, self.db:
            self.db.execute("DELETE FROM events WHERE id <= (SELECT MAX(id) FROM events) - ?", (self.max_events,))

    def control(self, key, default=None):
        try:
            with self._lock:
                row = self.db.execute("SELECT value FROM control WHERE key=?", (key,)).fetchone()
            return row["value"] if row else default
        except sqlite3.Error:
            self.write_errors += 1
            return default

    def set_control(self, key, value):
        try:
            with self._lock, self.db:
                self.db.execute("INSERT OR REPLACE INTO control(key, value) VALUES (?,?)", (key, value))
        except sqlite3.Error:
            self.write_errors += 1


def now():
    return time.time()
