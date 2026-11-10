import time

import pytest
from fastapi.testclient import TestClient

from dashboard.api.app import create_app
from ids.store import EventStore


@pytest.fixture
def history(tmp_path):
    path = tmp_path / "events.sqlite"
    stores = []
    for run in ("old", "other", "current"):
        s = EventStore(path, run, "live")
        stores.append(s)
        s.write("run_marker", time.time(), {"marker": "run_start"})
        s.write("alert", time.time(), {"alert_id": run, "source_key": "source", "severity": "high"})
        s.write("window", time.time(), {"window_id": run})
    stores[-1].set_control("enabled", "true")
    yield path, stores
    for s in stores:
        s.db.close()


def client(path, **kwargs):
    return TestClient(create_app(db_path=path, data_dir=path.parent, token="test-token"), base_url="http://127.0.0.1", client=kwargs.get("address", ("127.0.0.1", 50000)))


def clear(c, scope="all", run=None, **kwargs):
    return c.post("/api/alerts/history/clear", json={"scope": scope, "run_id": run, "confirmation": "CLEAR ALERT HISTORY"}, headers={"Authorization": "Bearer test-token", **kwargs})


def test_clear_all_sessions_keeps_detection_and_other_data(history):
    path, stores = history
    db = stores[-1].db
    with client(path) as c:
        assert {a["alert_id"] for a in c.get("/api/alerts").json()} == {"old", "other", "current"}
        assert c.get("/api/health").json()["alerts_total"] == 3
        r = clear(c)
        assert r.status_code == 200
        assert sorted(r.json()["deleted_alert_ids"]) == ["current", "old", "other"]
        assert (r.json()["deleted_events"], r.json()["remaining_alerts"]) == (3, 0)
        assert c.get("/api/alerts").json() == []
        assert c.get("/api/health").json()["alerts_total"] == 0
    assert db.execute("SELECT COUNT(*) FROM alerts").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM events WHERE event_type='alert'").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM events WHERE event_type IN ('window','run_marker')").fetchone()[0] == 6
    assert stores[-1].control("enabled") == "true"
    with client(path) as c:  # a restarted API reads the same store: nothing comes back
        assert c.get("/api/alerts").json() == []
    assert stores[-1].write("alert", time.time(), {"alert_id": "new", "source_key": "s", "severity": "high"})
    with client(path) as c:
        assert [a["alert_id"] for a in c.get("/api/alerts").json()] == ["new"]
        assert c.get("/api/health").json()["alerts_total"] == 1


def test_single_session_scope_still_exact(history):
    path, _ = history
    with client(path) as c:
        assert clear(c, "run", "old").json()["deleted_alert_ids"] == ["old"]
        assert {a["alert_id"] for a in c.get("/api/alerts").json()} == {"other", "current"}


def test_guard_confirmation_origin_and_remote(history):
    path, _ = history
    with client(path) as c:
        assert c.post("/api/alerts/history/clear", json={}).status_code == 401
        assert c.post("/api/alerts/history/clear", json={"scope": "all", "confirmation": "yes"}, headers={"Authorization": "Bearer test-token"}).status_code == 422
        assert clear(c, Origin="https://foreign.example").status_code == 403
        assert clear(c, Origin="https://127.0.0.1").status_code == 403
        assert clear(c, "run", None).status_code == 422
        assert clear(c, "all", "old").status_code == 422
    with client(path, address=("192.168.1.20", 50000)) as c:
        assert clear(c).status_code == 403


def test_missing_store_not_created(tmp_path):
    path = tmp_path / "missing.sqlite"
    with client(path) as c:
        assert clear(c).status_code == 503
    assert not path.exists()
