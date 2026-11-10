"""Startup ownership/readiness checks without launching or stopping user services."""
import json
from types import SimpleNamespace

import psutil
import pytest

from lab import startup


def test_option_and_service_identity_require_exact_module_arguments(monkeypatch):
    processes = [SimpleNamespace(info={"cmdline":["python","-c","text -m ids.service --port 18840"]}),
                 SimpleNamespace(info={"cmdline":["python","-m","ids.service","--port","18840"]})]
    monkeypatch.setattr(psutil,"process_iter",lambda attrs:processes)
    assert startup.service("ids.service",18840) is processes[1]
    assert startup.service("ids.service",18841) is None
    assert startup.option(["--port"],"--port") is None


def test_stale_or_recycled_pid_is_never_owned(monkeypatch):
    class Process:
        def create_time(self):return 20
        def cmdline(self):return ["python","-m","dashboard.api","--port","8020"]
    monkeypatch.setattr(psutil,"Process",lambda pid:Process())
    assert not startup.process_matches({"pid":1,"name":"api","created":10})
    assert startup.process_matches({"pid":1,"name":"api","created":20})
    assert not startup.process_matches({"pid":1,"name":"home","created":20})


def test_readiness_uses_current_listener_not_probe_or_old_pid(monkeypatch):
    monkeypatch.setattr(psutil,"net_connections",lambda **kwargs:[SimpleNamespace(status=psutil.CONN_ESTABLISHED,laddr=SimpleNamespace(port=18840))])
    assert not startup.listening(18840)
    monkeypatch.setattr(psutil,"net_connections",lambda **kwargs:[SimpleNamespace(status=psutil.CONN_LISTEN,laddr=SimpleNamespace(port=18840))])
    assert startup.listening(18840)


def test_start_refuses_existing_ids_without_shared_schedule_before_any_launch(tmp_path,monkeypatch):
    monkeypatch.setattr(startup,"service",lambda *args:SimpleNamespace(cmdline=lambda:["python","-m","ids.service","--port","18840"]))
    with pytest.raises(RuntimeError,match="no attack schedule"):
        startup.launch_stack(tmp_path,8020,18840,"test")
    assert not (tmp_path/'run/home-stack.json').exists()


def test_cleanup_skips_unowned_process_records(monkeypatch):
    monkeypatch.setattr(startup,"process_matches",lambda record:False)
    monkeypatch.setattr(psutil,"Process",lambda pid:pytest.fail("must not touch stale or unowned PID"))
    startup.stop_records([{"pid":1,"name":"api","created":0}])
