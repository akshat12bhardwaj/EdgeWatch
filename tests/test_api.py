"""API tests against a real SQLite store. No mocks: an empty, missing or broken store must give honest answers."""
import json
import time

import pytest
from fastapi.testclient import TestClient

from dashboard.api.app import create_app
from ids.store import EventStore


@pytest.fixture
def store(tmp_path):
    store = EventStore(tmp_path / "e.sqlite", "run1", "live")
    store.write("run_marker", time.time(), {"marker": "run_start", "scenario": "s", "model_id": "m"})
    yield store
    store.db.close()  # the store has no close(); leaving it open leaks a connection into later tests


def client(path, tmp_path, **options):
    options.setdefault("data_dir", tmp_path / "data")
    return TestClient(create_app(db_path=path, web_dist=tmp_path / "no-web", **options), base_url="http://127.0.0.1", client=("127.0.0.1", 50000))


def test_missing_store_is_reported_not_raised(tmp_path):
    c = client(tmp_path / "absent.sqlite", tmp_path)
    assert c.get("/api/health").json()["status"] == "no_store"
    assert c.get("/api/alerts").json() == [] and c.get("/api/traffic").json() == [] and c.get("/api/topology").json() == {"nodes": []}
    assert c.post("/api/control", json={"action": "disable"}).status_code == 503


def test_corrupt_store_is_reported_not_raised(tmp_path):
    path = tmp_path / "bad.sqlite"
    path.write_bytes(b"this is not a database at all" * 100)
    c = client(path, tmp_path)
    assert c.get("/api/health").json()["status"] == "no_store" and c.get("/api/alerts").json() == []


def test_health_reflects_a_running_ids_and_provenance(store, tmp_path):
    store.write("resource", time.time(), {"model_loaded": True, "broker_running": True, "pkts_per_s": 1, "mqtt_msgs_per_s": 1})
    body = client(store.path, tmp_path).get("/api/health").json()
    assert body["status"] == "ok" and body["provenance"] == "live" and body["model_loaded"]
    assert body["broker_running"] is False  # no configured MQTT port; old resource rows are not live connectivity


def test_health_checks_current_mqtt_listener_instead_of_stale_resource(store, tmp_path, monkeypatch):
    from types import SimpleNamespace
    import psutil
    store.write("resource", time.time(), {"model_loaded": True, "broker_running": True})
    c = client(store.path, tmp_path, mqtt_port=18979)
    monkeypatch.setattr(psutil, "net_connections", lambda **kwargs: [])
    body = c.get("/api/health").json()
    assert body["broker_running"] is False and body["ids"] == "running" and body["provenance"] == "live"
    listener = SimpleNamespace(status=psutil.CONN_LISTEN, laddr=SimpleNamespace(port=18979))
    monkeypatch.setattr(psutil, "net_connections", lambda **kwargs: [listener])
    assert c.get("/api/health").json()["broker_running"] is True


def test_health_reports_a_stopped_ids(store, tmp_path):
    store.write("resource", time.time() - 100, {})
    assert client(store.path, tmp_path).get("/api/health").json()["ids"] == "stopped"


def test_alert_list_filter_detail_and_history(store, tmp_path):
    t = time.time()
    store.write("window", t, {"window_id": "w", "source_key": "src-a", "features": {"F01": 3}})
    store.write("alert", t, {"alert_id": "a1", "source_key": "src-a", "severity": "high", "last_window_ns": int(t * 1e9), "predicted_class": "flood"})
    store.write("alert", t, {"alert_id": "a2", "source_key": "src-b", "severity": "low", "last_window_ns": int(t * 1e9), "predicted_class": "x"})
    c = client(store.path, tmp_path)
    assert len(c.get("/api/alerts").json()) == 2 and [a["alert_id"] for a in c.get("/api/alerts", params={"source": "src-a"}).json()] == ["a1"]
    detail = c.get("/api/alerts/a1").json()
    assert detail["history"][0]["window_id"] == "w" and c.get("/api/alerts/none").status_code == 404


def test_query_parameter_cannot_inject_sql(store, tmp_path):
    store.write("alert", time.time(), {"alert_id": "a1", "source_key": "src-a", "severity": "high"})
    c = client(store.path, tmp_path)
    assert c.get("/api/alerts", params={"source": "x' OR '1'='1"}).json() == []


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 100000}, {"limit": "many"}])
def test_invalid_limits_are_rejected(store, tmp_path, params):
    assert client(store.path, tmp_path).get("/api/alerts", params=params).status_code == 422


@pytest.mark.parametrize("body", [{"action": "stop-broker"}, {"action": "enable", "extra": 1}, {}, {"action": None}])
def test_invalid_control_requests_are_rejected_and_change_nothing(store, tmp_path, body):
    c = client(store.path, tmp_path)
    assert c.post("/api/control", json=body).status_code == 422
    assert store.control("enabled") is None


def test_control_flips_only_the_ids_flag(store, tmp_path):
    c = client(store.path, tmp_path)
    assert c.post("/api/control", json={"action": "disable"}).json() == {"enabled": False}
    assert store.control("enabled") == "false" and c.get("/api/health").json()["ids_enabled"] is False
    c.post("/api/control", json={"action": "enable"})
    assert store.control("enabled") == "true"


def test_control_token_is_enforced_and_never_echoed(store, tmp_path):
    c = client(store.path, tmp_path, token="s3cret-token")
    denied = c.post("/api/control", json={"action": "disable"})
    assert denied.status_code == 401 and "s3cret" not in denied.text and store.control("enabled") is None
    assert c.post("/api/control", json={"action": "disable"}, headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert c.post("/api/control", json={"action": "disable"}, headers={"Authorization": "Bearer s3cret-token"}).status_code == 200
    assert "s3cret" not in c.get("/api/health").text


def test_websocket_pushes_only_new_events_in_order_with_ids(store, tmp_path):
    with client(store.path, tmp_path).websocket_connect("ws://127.0.0.1/ws/events?after=0") as socket:
        first = json.loads(socket.receive_text())
        assert first[0]["marker"] == "run_start" and first[0]["id"] == 1
        store.write("window", time.time(), {"window_id": "w", "source_key": "s"})
        second = json.loads(socket.receive_text())
        assert second[0]["window_id"] == "w" and second[0]["id"] == 2 and second[0]["provenance"] == "live"


def test_websocket_stays_up_when_the_store_appears_later(tmp_path):
    path = tmp_path / "later.sqlite"
    with client(path, tmp_path).websocket_connect("ws://127.0.0.1/ws/events?after=0") as socket:
        store = EventStore(path, "r", "replay")
        store.write("window", time.time(), {"window_id": "late", "source_key": "s"})
        assert json.loads(socket.receive_text())[0]["window_id"] == "late"
        store.db.close()
