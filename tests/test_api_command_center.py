"""API additions for the command center (SG-07) and its guards (SG-10): search, runs, simulation control, replay comparison."""
import json
import time

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from dashboard.api.app import create_app
from ids.store import EventStore


@pytest.fixture
def store(tmp_path):
    store = EventStore(tmp_path / "e.sqlite", "run1", "live")
    store.write("run_marker", time.time(), {"marker": "run_start", "scenario": "s", "model_id": "m"})
    yield store
    store.db.close()  # the store has no close(); leaving it open leaks a connection into later tests


def client(path, tmp_path, remote=None, **options):
    options.setdefault("data_dir", tmp_path / "data")
    app = create_app(db_path=path, web_dist=tmp_path / "no-web", **options)
    return TestClient(app, base_url="http://127.0.0.1", client=(remote or "127.0.0.1", 50000))


def test_foreign_host_header_is_refused(store, tmp_path):
    c = client(store.path, tmp_path)
    assert c.get("/api/health").status_code == 200
    assert c.get("/api/health", headers={"host": "attacker.example"}).status_code == 400


def test_websocket_from_a_foreign_origin_is_refused(store, tmp_path):
    c = client(store.path, tmp_path)
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect("ws://127.0.0.1/ws/events", headers={"origin": "http://evil.example"}) as ws:
            ws.receive_text()
    with c.websocket_connect("ws://127.0.0.1/ws/events", headers={"origin": "http://127.0.0.1:8000"}):
        pass


def test_alert_search_filters_and_runs(store, tmp_path):
    for i, (sev, kind, cls) in enumerate((("high", "model", "flood"), ("low", "rule", "wildcard_subscribe"), ("medium", "model", "bruteforce"))):
        store.write("alert", 100 + i, {"alert_id": f"a{i}", "source_key": "s", "kind": kind, "predicted_class": cls, "score": 0.9, "severity": sev, "start_ns": 0, "last_window_ns": 0,
                                       "duration_s": 10, "window_ids": [], "evidence": [], "status": "no_scheduled_attack", "first_seen": 0})
    c = client(store.path, tmp_path)
    assert [a["alert_id"] for a in c.get("/api/alerts?severity=high").json()] == ["a0"]
    assert [a["alert_id"] for a in c.get("/api/alerts?kind=rule").json()] == ["a1"]
    assert [a["alert_id"] for a in c.get("/api/alerts?predicted_class=bruteforce").json()] == ["a2"]
    assert c.get("/api/alerts?severity=bogus").status_code == 422
    runs = c.get("/api/runs").json()
    assert runs[0]["run_id"] == "run1" and runs[0]["alerts"] == 3 and runs[0]["provenance"] == "live"


def test_simulation_is_unavailable_without_ids_settings(store, tmp_path):
    c = client(store.path, tmp_path)
    status = c.get("/api/simulation").json()
    assert status["available"] is False and "EDGEWATCH_MQTT_PORT" in status["reason"]
    assert c.post("/api/simulation/start", json={"families": ["bruteforce"]}).status_code == 503


@pytest.mark.parametrize("body", [{"families": ["nmap"]}, {"rate_factor": 2}, {"episodes": 50}, {"families": ["bruteforce"], "shell": "x"}, {"attack_s": 100000}, {"benign": "../x"}])
def test_simulation_requests_outside_the_limits_are_rejected(store, tmp_path, body):
    c = client(store.path, tmp_path, mqtt_port=18899, schedule=str(tmp_path / "gt.json"))
    assert c.post("/api/simulation/start", json=body).status_code == 422


def test_simulation_total_duration_is_capped(store, tmp_path):
    c = client(store.path, tmp_path, mqtt_port=18899, schedule=str(tmp_path / "gt.json"))
    body = {"families": ["flood_connect", "flood_publish", "lowrate", "malformed", "bruteforce", "wildcard", "topic_probe"], "episodes": 3, "attack_s": 120, "calm_s": 60}
    r = c.post("/api/simulation/start", json=body)
    assert r.status_code == 422 and "limit" in r.json()["detail"]


def test_simulation_control_is_refused_from_another_machine(store, tmp_path):
    c = client(store.path, tmp_path, remote="192.168.1.50", mqtt_port=18899, schedule=str(tmp_path / "gt.json"))
    assert c.post("/api/simulation/start", json={"families": ["bruteforce"]}).status_code == 403
    assert c.post("/api/simulation/stop").status_code == 403


def test_simulation_needs_the_token_when_set(store, tmp_path):
    c = client(store.path, tmp_path, mqtt_port=18899, schedule=str(tmp_path / "gt.json"), token="t0k")
    assert c.post("/api/simulation/stop").status_code == 401
    assert c.post("/api/simulation/stop", headers={"Authorization": "Bearer t0k"}).json() == {"stopped": False}


# Wokwi virtual smart home -------------------------------------------------------------------------------------------------------------
def test_home_is_unconfigured_without_lab_home_state(store, tmp_path):
    c = client(store.path, tmp_path, data_dir=tmp_path / "data", mqtt_port=18840, schedule=str(tmp_path / "truth.json"))
    assert c.get("/api/home").json() == {"configured": False}
    assert c.post("/api/home/light", json={"on": True}).status_code == 409


def test_home_reports_bridge_values_but_not_running_without_its_process(store, tmp_path):
    data = tmp_path / "data"
    (data / "home").mkdir(parents=True)
    (data / "home" / "telemetry.json").write_text(json.dumps({"bridge_connected": True, "rejected": 2, "values": {"temperature": {"value": 22.5, "ts": 1}}}))
    (data / "home" / "home-broker.json").write_text(json.dumps({"port": 18840, "serve_pid": 0, "telemetry": str(data / "home" / "telemetry.json")}))
    c = client(store.path, tmp_path, data_dir=data, mqtt_port=18840, schedule=str(tmp_path / "truth.json"))
    body = c.get("/api/home").json()
    assert body["configured"] and not body["running"] and not body["bridge_connected"]  # a stale file alone never reads as connected
    assert body["values"]["temperature"]["value"] == 22.5 and body["rejected"] == 2
    assert c.get("/api/simulation").json()["home_broker"] is False


def test_home_light_control_is_loopback_only_and_validated(store, tmp_path):
    remote = client(store.path, tmp_path, remote="10.0.0.5", data_dir=tmp_path / "data", mqtt_port=18840, schedule=str(tmp_path / "t.json"), allowed_hosts=["127.0.0.1", "testserver"])
    assert remote.post("/api/home/light", json={"on": True}).status_code == 403
    local = client(store.path, tmp_path, data_dir=tmp_path / "data", mqtt_port=18840, schedule=str(tmp_path / "t.json"))
    assert local.post("/api/home/light", json={"on": "maybe", "extra": 1}).status_code == 422


def test_wokwi_only_demo_needs_the_home_broker(store, tmp_path):
    c = client(store.path, tmp_path, data_dir=tmp_path / "data", mqtt_port=18840, schedule=str(tmp_path / "truth.json"))
    r = c.post("/api/simulation/start", json={"benign": "wokwi_only", "families": ["bruteforce"]})
    assert r.status_code == 409 and "smart-home broker" in r.json()["detail"]


# Smart Home layout ----------------------------------------------------------------------------------------------------------------------
def _device(i, **extra):
    return {"id": f"d{i}", "name": f"Device {i}", "type": "light", "room": "living", "x": 100 + i, "y": 100, **extra}


def test_layout_round_trips_and_starts_empty(store, tmp_path):
    c = client(store.path, tmp_path, data_dir=tmp_path / "data")
    assert c.get("/api/home/layout").json() == {"devices": [], "saved": False}
    layout = {"devices": [_device(1), _device(2, type="climate", source="wokwi", room="kitchen")]}
    assert c.put("/api/home/layout", json=layout).json() == {"saved": True, "devices": 2}
    body = c.get("/api/home/layout").json()
    assert body["saved"] and [d["id"] for d in body["devices"]] == ["d1", "d2"] and body["devices"][0]["source"] == "software"


@pytest.mark.parametrize("bad", [
    {"devices": [_device(1, type="toaster")]}, {"devices": [_device(1, room="moon")]}, {"devices": [_device(1, x=5000)]},
    {"devices": [_device(1, id="../x")]}, {"devices": [_device(1, name="")]}, {"devices": [_device(1), _device(1)]},
    {"devices": [_device(1, source="wokwi", type="camera")]},  # the Wokwi board has no camera
    {"devices": [_device(1, source="wokwi"), _device(2, source="wokwi")]},  # and only one LED
    {"devices": [_device(i) for i in range(25)]}, {"devices": [], "extra": 1},
])
def test_layout_rejects_invalid_or_dishonest_devices(store, tmp_path, bad):
    assert client(store.path, tmp_path, data_dir=tmp_path / "data").put("/api/home/layout", json=bad).status_code == 422


def test_layout_writes_are_loopback_only(store, tmp_path):
    remote = client(store.path, tmp_path, remote="10.0.0.5", data_dir=tmp_path / "data", allowed_hosts=["127.0.0.1", "testserver"])
    assert remote.put("/api/home/layout", json={"devices": []}).status_code == 403


def test_device_commands_are_validated_per_type_before_reaching_mqtt(store, tmp_path):
    c = client(store.path, tmp_path, data_dir=tmp_path / "data", mqtt_port=18840, schedule=str(tmp_path / "t.json"))
    c.put("/api/home/layout", json={"devices": [_device(1, type="thermostat"), _device(2, type="light", source="wokwi")]})
    cmd = lambda i, body: c.post(f"/api/home/devices/{i}/command", json=body).status_code
    assert cmd("d9", {"target": 21}) == 404  # not placed
    assert cmd("d2", {"on": True}) == 404  # Wokwi-backed: controlled through the ESP32, not the device host
    assert cmd("../x", {"target": 21}) in (404, 422)
    for bad in ({"target": 99}, {"target": "hot"}, {"on": True}, {}, {"target": 21, "a": 1, "b": 2, "c": 3}):
        assert cmd("d1", bad) == 422, bad
    assert cmd("d1", {"target": 21.5}) == 409  # valid, but the hub is not running


def test_home_hub_start_needs_the_lab_configuration(store, tmp_path):
    c = client(store.path, tmp_path, data_dir=tmp_path / "data")
    assert c.post("/api/home/start").status_code == 503
    assert c.post("/api/home/stop").json() == {"stopped": False}
    remote = client(store.path, tmp_path, remote="10.0.0.5", data_dir=tmp_path / "data", allowed_hosts=["127.0.0.1", "testserver"])
    assert remote.post("/api/home/start").status_code == 403 and remote.post("/api/home/devices/d1/command", json={"on": True}).status_code == 403


def test_simulation_mix_accepts_layout_devices_and_rejects_unknown_profiles(store, tmp_path):
    c = client(store.path, tmp_path, data_dir=tmp_path / "data", mqtt_port=18840, schedule=str(tmp_path / "t.json"))
    for mix in (["toaster@d1"], ["light@../x"], ["light"], [f"light@d{i}" for i in range(25)]):
        assert c.post("/api/simulation/start", json={"benign": "layout", "mix": mix}).status_code == 422
