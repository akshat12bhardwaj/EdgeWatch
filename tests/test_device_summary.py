"""One device count for every page: configured layout devices, online only while reporting."""
from dashboard.api.app import device_summary

NOW = 1000.0


def dev(i, source="software", controller=None, kind="light", name=None):
    return {"id": i, "name": name or i, "type": kind, "source": source, "controller": controller}


def rep(ts=NOW - 2, status="online"):
    return {"status": status, "ts": ts, "state": {}}


CTRL = {"lighting": {"mqtt_connected": True, "last_message": NOW - 1}, "access": {"mqtt_connected": True, "last_message": NOW - 1}}
LAYOUT = [dev("s1"), dev("s2", kind="motion"), dev("w1", "wokwi", "lighting"), dev("w2", "wokwi", "access", "motion")]
REPORTS = {d["id"]: rep() for d in LAYOUT}


def test_all_reporting():
    s = device_summary(LAYOUT, REPORTS, CTRL, {}, NOW)
    assert (s["total"], s["online"], s["wokwi"], s["software"], s["wokwi_online"]) == (4, 4, 2, 2, 2)


def test_add_remove_rename():
    added = device_summary(LAYOUT + [dev("s3")], REPORTS, CTRL, {}, NOW)
    assert (added["total"], added["online"]) == (5, 4)  # not online until it reports
    assert device_summary(LAYOUT[1:], REPORTS, CTRL, {}, NOW)["total"] == 3  # stale report of a removed id is not counted
    renamed = [dict(LAYOUT[0], name="Desk lamp")] + LAYOUT[1:]
    assert device_summary(renamed, REPORTS, CTRL, {}, NOW)["online_ids"] == ["s1", "s2", "w1", "w2"]


def test_hub_stopped_counts_nothing_online():
    s = device_summary(LAYOUT, {}, {}, {}, NOW)  # the API passes no reports when the hub is not running
    assert (s["total"], s["online"]) == (4, 0)


def test_wokwi_disconnect_affects_only_its_controller():
    ctrl = {**CTRL, "access": {"mqtt_connected": True, "last_message": NOW - 60}}
    s = device_summary(LAYOUT, REPORTS, ctrl, {}, NOW)
    assert s["online_ids"] == ["s1", "s2", "w1"] and s["wokwi_online"] == 1
    assert device_summary(LAYOUT, REPORTS, {**CTRL, "lighting": {"mqtt_connected": False, "last_message": NOW}}, {}, NOW)["online_ids"] == ["s1", "s2", "w2"]


def test_software_stop_and_mqtt_reconnect():
    stale = {**REPORTS, "s2": rep(NOW - 31)}
    assert device_summary(LAYOUT, stale, CTRL, {}, NOW)["online"] == 3
    assert device_summary(LAYOUT, {**REPORTS, "s2": rep(status="offline")}, CTRL, {}, NOW)["online"] == 3
    assert device_summary(LAYOUT, REPORTS, CTRL, {}, NOW)["online"] == 4  # reconnected: fresh report again


def test_unknown_reports_never_become_devices():
    s = device_summary(LAYOUT, {**REPORTS, "ghost": rep(), "edgewatch_bridge": rep()}, CTRL, {}, NOW)
    assert (s["total"], s["online"]) == (4, 4)


def test_legacy_board_needs_fresh_bridge_values():
    legacy = [dev("l1", "wokwi", None, "climate")]
    live = {"bridge_connected": True, "values": {"status": {"value": "online", "ts": NOW - 5}, "temperature": {"value": 22, "ts": NOW - 2}}}
    assert device_summary(legacy, {}, {}, live, NOW)["online"] == 1
    assert device_summary(legacy, {}, {}, {**live, "bridge_connected": False}, NOW)["online"] == 0
    assert device_summary(legacy, {}, {}, {}, NOW)["online"] == 0
