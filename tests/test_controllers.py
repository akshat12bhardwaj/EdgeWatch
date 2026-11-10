"""Bridge engineering tests; fixtures are not evidence of Wokwi runtime operation."""
import json
import threading
import time
from pathlib import Path

import pytest

from lab import controllers, home, wire


@pytest.mark.parametrize("line,role,expected", [
    (b'EW2 climate {"temperature":22.5,"humidity":45}\n', "environment", ("climate", {"temperature":22.5,"humidity":45})),
    (b'EW2 lock {"locked":false,"ack":"abcd1234"}\n', "access", ("lock", {"locked":False,"ack":"abcd1234"})),
    (b'EW2 door {"open":true}\n', "access", ("door", {"open":True})),
])
def test_firmware_state_contract(line, role, expected):
    assert controllers.parse_line(line, role) == expected


@pytest.mark.parametrize("line", [
    b'EW2 climate {"temperature":NaN,"humidity":45}',
    b'EW2 climate {"temperature":true,"humidity":45}',
    b'EW2 climate {"temperature":22,"humidity":101}',
    b'EW2 thermostat {"current":22,"target":21,"mode":"pretend"}',
    b'EW2 climate {}', b'EW2 lock {"locked":true}', b'EW2 '+b'x'*600,
    b'EW2 climate {"temperature":22,"humidity":45,"ack":"not-an-ack"}',
])
def test_rejects_invalid_wrong_controller_and_unbounded_telemetry(line):
    assert controllers.parse_line(line, "environment") is None


def test_supported_commands_require_firmware_ack_identifier_and_exact_fields():
    assert controllers.command_line("lock", b'{"locked":false,"cmd_id":"abcd1234"}') == b'EW2 lock locked 0 abcd1234\n'
    assert controllers.command_line("thermostat", b'{"target":23.5,"cmd_id":"abcd1234"}') == b'EW2 thermostat target 23.5 abcd1234\n'
    for channel, payload in [("lock", b'{"locked":1,"cmd_id":"abcd1234"}'), ("motion", b'{"trigger":true,"cmd_id":"abcd1234"}'), ("lock", b'{"locked":true}'), ("lock", b'{"locked":true,"cmd_id":"abcd1234","extra":1}'), ("thermostat", b'{"target":31,"cmd_id":"abcd1234"}')]:
        assert controllers.command_line(channel, payload) is None


def test_config_requires_distinct_local_serial_and_real_loopback_sources(tmp_path):
    path = tmp_path / "config.json"
    config = [{"id":"environment","serial":"rfc2217://localhost:4002","source_ip":"127.0.3.11"},{"id":"access","serial":"rfc2217://localhost:4001","source_ip":"127.0.3.12"}]
    path.write_text(json.dumps(config))
    assert controllers.load_config(path) == config
    for field,value in [("source_ip","192.168.1.2"),("source_ip","127.0.3.10"),("source_ip","127.0.3.4"),("source_ip","127.0.3.11"),("serial","rfc2217://example.com:4001"),("serial","rfc2217://localhost:4002")]:
        bad=json.loads(json.dumps(config));bad[1][field]=value;path.write_text(json.dumps(bad))
        with pytest.raises(ValueError): controllers.load_config(path)


def test_mapping_only_routes_matching_controller_and_channel(tmp_path):
    path=tmp_path/'layout.json'
    path.write_text(json.dumps({"devices":[{"id":"lock1","type":"lock","controller":"access","source":"wokwi"},{"id":"climate1","type":"climate","controller":"environment","source":"wokwi"},{"id":"fake","type":"camera","controller":"access","source":"wokwi"}]}))
    bridge=controllers.ControllerBridge({"id":"access"},1,(),path,lambda:None)
    assert bridge.mappings()=={"lock1":"lock"}
    observer=home.Bridge(1,(),tmp_path/'out.json',layout=path)
    assert 'lock1' in observer.wanted()


def test_publish_preserves_only_device_report_ack_no_host_generated_ack(tmp_path):
    class Client:
        def __init__(self): self.messages=[]
        def publish(self,*args,**kwargs): self.messages.append((args,kwargs))
    client=Client()
    bridge=controllers.ControllerBridge({"id":"access"},1,(),tmp_path/'layout.json',lambda:None)
    bridge.publish_state(client,'lock1','lock',{"locked":False})
    state=json.loads(client.messages[0][0][1]);assert 'ack' not in state and state['controller']=='access'
    bridge.publish_state(client,'lock1','lock',{"locked":True,"ack":"abcd1234"})
    assert json.loads(client.messages[2][0][1])['ack']=='abcd1234'


def test_bridge_reconnect_wait_is_interruptible(tmp_path):
    attempts=[]
    bridge=controllers.ControllerBridge({"id":"access"},1,(),tmp_path/'layout.json',lambda:None,log=lambda _:None)
    def fail(stop): attempts.append(1);raise OSError('absent')
    bridge.session=fail
    stop=threading.Event();thread=threading.Thread(target=bridge.run,args=(stop,));thread.start()
    for _ in range(100):
        if attempts: break
        time.sleep(.005)
    stop.set();thread.join(1)
    assert attempts==[1] and not thread.is_alive()


def test_mqtt_length_refused_before_reading_a_large_body():
    class Client:
        def __init__(self, data): self.data=data;self.reads=[]
        def _read_exact(self,n):
            self.reads.append(n);out,self.data=self.data[:n],self.data[n:];return out
    client=Client(b'\x30\xff\xff\x7f')
    with pytest.raises(ValueError): controllers.receive_bounded(client)
    assert all(n==1 for n in client.reads)
    client=Client(b'\x30\x03abc')
    assert controllers.receive_bounded(client)==(0x30,b'abc')


@pytest.mark.parametrize("kind,state,command", [
    ("light", {"on":True}, {"on":False}),
    ("plug", {"on":True,"power_w":60,"energy_wh":.1,"appliance_w":60}, {"on":False}),
    ("smoke", {"level":30,"threshold":20,"alarm":True}, {"reset":True}),
    ("camera", {"monitoring":True,"motion_events":3}, {"monitoring":False}),
])
def test_lighting_safety_state_and_command_contract(kind,state,command):
    role="lighting" if kind in ("light","plug") else "safety"
    assert controllers.parse_line(b'EW2 '+kind.encode()+b' '+json.dumps(state).encode(),role)==(kind,state)
    command['cmd_id']='abcd1234'
    assert controllers.command_line(kind,json.dumps(command).encode()) is not None


class FakeSerial:
    def __init__(self, lines): self.lines, self.closed, self.opened = list(lines), False, 1
    def readline(self, n): return self.lines.pop(0) if self.lines else b""
    def write(self, data): pass
    def close(self): self.closed = True


def _fake_mqtt(monkeypatch, failures):
    """An MQTT client whose first `failures` sessions die mid-stream, like a hub restart."""
    import socket as socketlib
    sessions = []
    class Client:
        def __init__(self, *args, **kwargs):
            self.sock, self.peer = socketlib.socketpair()
            self.published = []; sessions.append(self)
        def login(self, *args, **kwargs): return 0
        def send(self, data):
            if len(sessions) <= failures and len(self.published) >= 1: raise ConnectionResetError("broker restarted")
        def publish(self, topic, payload, retain=False):
            self.published.append((topic, payload)); self.send(b"")
        def close(self, graceful=True): self.sock.close(); self.peer.close()
    monkeypatch.setattr(controllers.wire, "Client", Client)
    monkeypatch.setattr(controllers.select, "select", lambda r, w, x, t: ([], [], []))
    return sessions


def _layout(tmp_path):
    path = tmp_path / "layout.json"
    path.write_text(json.dumps({"devices": [{"id": "t1", "type": "climate", "source": "wokwi", "controller": "environment"}]}))
    return path


def test_broker_restart_reconnects_mqtt_without_reopening_serial(tmp_path, monkeypatch):
    sessions = _fake_mqtt(monkeypatch, failures=1)
    opened = []
    def open_serial(url):
        opened.append(url); return FakeSerial([b'EW2 climate {"temperature":21.5,"humidity":40}\n'] * 50)
    bridge = controllers.ControllerBridge({"id": "environment", "serial": "rfc2217://x", "source_ip": "127.0.0.1"}, 1, ("u", "p"), _layout(tmp_path), lambda: None, open_serial, log=lambda _: None)
    stop = threading.Event(); thread = threading.Thread(target=bridge.run, args=(stop,)); thread.start()
    for _ in range(400):
        if len(sessions) >= 2 and any(t.endswith("/state") for t, _ in sessions[1].published): break
        time.sleep(.01)
    stop.set(); thread.join(5)
    assert len(sessions) >= 2 and opened == ["rfc2217://x"]  # MQTT came back on the same serial session
    assert "MQTT ConnectionResetError" in bridge.stats["last_error"]


def test_silent_firmware_marks_devices_offline_but_keeps_serial_open(tmp_path, monkeypatch):
    sessions = _fake_mqtt(monkeypatch, failures=0)
    monkeypatch.setattr(controllers, "SILENT_S", 0.2)
    ser = FakeSerial([b'EW2 climate {"temperature":21.5,"humidity":40}\n'])
    bridge = controllers.ControllerBridge({"id": "environment", "serial": "x", "source_ip": "127.0.0.1"}, 1, ("u", "p"), _layout(tmp_path), lambda: None, lambda url: ser, log=lambda _: None)
    stop = threading.Event(); thread = threading.Thread(target=bridge.run, args=(stop,)); thread.start()
    for _ in range(300):
        if sessions and sessions[0].published[-1:] == [(home.DEVICES_PREFIX + "t1/status", b"offline")] and not bridge.stats["firmware_reporting"] and bridge.stats["forwarded"]: break
        time.sleep(.01)
    silent = (bridge.stats["firmware_reporting"], ser.closed, len(sessions))
    stop.set(); thread.join(5)
    assert silent == (False, False, 1)  # offline shown honestly; no serial reopen, no MQTT churn


def test_unexpected_error_in_one_controller_does_not_end_its_thread(tmp_path):
    calls = []
    bridge = controllers.ControllerBridge({"id": "access"}, 1, (), tmp_path / "layout.json", lambda: None, log=lambda _: None)
    def boom(stop): calls.append(1); raise AttributeError("pyserial internals")
    bridge.session = boom
    stop = threading.Event(); thread = threading.Thread(target=bridge.run, args=(stop,)); thread.start()
    time.sleep(.1)
    alive = thread.is_alive()
    stop.set(); thread.join(2)
    assert calls and alive and "AttributeError" in bridge.stats["last_error"]
