"""Layout migration and truthful controller routing, using isolated API state."""
from fastapi.testclient import TestClient
from dashboard.api.app import create_app


def device(kind="climate", controller="environment", **extra):
    return {"id": "sensor1", "name": "Sensor", "type": kind, "source": "wokwi",
            "room": "living", "x": 150, "y": 120, "controller": controller, **extra}


def test_controller_layout_survives_new_api_instance(tmp_path):
    options = dict(data_dir=tmp_path, web_dist=tmp_path / "absent")
    layout = {"devices": [device(), device("lock", "access", id="lock1")]}
    with TestClient(create_app(**options), base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as c:
        assert c.put("/api/home/layout", json=layout).status_code == 200
    with TestClient(create_app(**options), base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as c:
        assert c.get("/api/home/layout").json()["devices"] == layout["devices"]
        assert c.post("/api/home/devices/sensor1/command", json={"room_temperature": 25}).status_code == 422
        assert c.post("/api/home/devices/lock1/command", json={"attempt": "correct"}).status_code == 422
        assert c.post("/api/home/devices/lock1/command", json={"locked": True}).status_code == 409  # no hub


def test_controller_slots_are_unique_and_match_firmware(tmp_path):
    with TestClient(create_app(data_dir=tmp_path), base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as c:
        for devices in ([device(), device(id="sensor2")], [device("lock")], [device(source="software")]):
            assert c.put("/api/home/layout", json={"devices": devices}).status_code == 422
        legacy = device("light", None)
        assert c.put("/api/home/layout", json={"devices": [legacy]}).status_code == 200
        got = c.get("/api/home/layout").json()["devices"][0]
        assert (got["x"], got["y"], got["source"], got["controller"]) == (150, 120, "wokwi", None)
