"""Dashboard-triggered lab runs: bounded, loopback-only, one at a time. Starts `python -m lab.run` with an argument list (no shell).

The lab runner keeps its own safety checks (allow-list, rate caps). This layer adds request validation, a total-duration cap,
a single-run lock, and cleanup of the whole process tree. Ground truth goes to the file the IDS already reads (--schedule),
so alerts are matched against the runner's schedule, never against the IDS's own predictions.
"""
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Literal, Optional

import psutil
from pydantic import BaseModel, ConfigDict, Field, field_validator

from lab.attacks import FAMILIES
from lab.benign import PROFILES, SCENARIOS
from lab.run import TRAINED_FAMILIES

ROOT = Path(__file__).resolve().parents[2]
MAX_TOTAL_S = 600
LEAD_S = 20
FAMILY_TEXT = {"flood_connect": "T1 connection flood / churn", "flood_publish": "T2 publish flood", "lowrate": "T3 slow hold (SlowITe-style)", "malformed": "T4 malformed packets",
               "bruteforce": "T5 password guessing (disposable lab account)", "wildcard": "T6 wildcard subscribe (rule indicator, untrained)", "topic_probe": "T7 topic probing (untrained)"}
BENIGN_CHOICES = tuple(s for s in SCENARIOS if s != "new_device")
Family = Literal[tuple(FAMILIES)]  # type: ignore[valid-type]
Benign = Literal[BENIGN_CHOICES]  # type: ignore[valid-type]


class SimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    benign: Benign = "base"
    families: list[Family] = Field(default_factory=list, max_length=len(FAMILIES))
    episodes: int = Field(1, ge=1, le=3)
    attack_s: int = Field(30, ge=10, le=120)
    calm_s: int = Field(15, ge=5, le=60)
    rate_factor: float = Field(1.0, gt=0.04, le=1.0)
    seconds: int = Field(120, ge=30, le=MAX_TOTAL_S)  # benign-only runs
    seed: int = Field(0, ge=0, le=1_000_000)
    # Smart Home layout devices as profile@device-id; profiles are lab traffic patterns, ids link sources back to the layout.
    mix: list[str] = Field(default_factory=list, max_length=24)

    @field_validator("mix")
    @classmethod
    def known_profiles(cls, mix):
        for item in mix:
            profile, _, device = item.partition("@")
            if profile not in PROFILES or not re.fullmatch(r"[A-Za-z0-9-]{1,12}", device):
                raise ValueError(f"unknown device profile or id: {item[:40]}")
        return mix

    def total_s(self):
        if not self.families:
            return self.seconds
        return LEAD_S + self.episodes * len(set(self.families)) * (self.attack_s + self.calm_s)


def port_in_use(port):
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


class SimulationController:
    def __init__(self, port: Optional[int], schedule: Optional[str], data_dir: Path):
        self.port, self.schedule, self.data_dir = port, Path(schedule) if schedule else None, data_dir
        self.process: Optional[subprocess.Popen] = None
        self.current: Optional[dict] = None
        self.history: list[dict] = []
        self.lock = threading.Lock()

    def home(self):
        """The lab.home state when its broker is the one on our port: runs then attach to it instead of starting their own."""
        path = self.data_dir / "home" / "home-broker.json"
        try:
            state = json.loads(path.read_text())
        except (OSError, ValueError):
            return None
        if state.get("port") != self.port or not self.port:
            return None
        try:  # the listener must be lab.home's broker, not a per-run lab broker that happens to use the same port
            serving = "lab.home" in " ".join(psutil.Process(int(state.get("serve_pid", 0))).cmdline())
        except (psutil.Error, ValueError):
            serving = False
        # No connect-probe: lab.home exits when its broker dies, and a probe from 127.0.0.1 would be counted as the Wokwi gateway's traffic.
        return path if serving else None

    def unavailable_reason(self):
        if not self.port or not self.schedule:
            return "Simulation needs EDGEWATCH_MQTT_PORT and EDGEWATCH_SCHEDULE, which start-edgewatch.ps1 sets for the IDS it starts."
        return None

    def _reap(self):
        if self.process is not None and self.process.poll() is not None:
            self.current = {**self.current, "running": False, "exit_code": self.process.returncode, "ended": time.time()}
            self.history = [self.current, *self.history][:10]
            self.process, self.current = None, None

    def status(self):
        with self.lock:
            self._reap()
            return {"available": self.unavailable_reason() is None, "reason": self.unavailable_reason(), "port": self.port, "running": self.current,
                    "history": self.history, "families": [{"id": f, "text": FAMILY_TEXT.get(f, f), "trained": f in TRAINED_FAMILIES} for f in FAMILIES],
                    "benign": list(BENIGN_CHOICES), "home_broker": self.home() is not None, "limits": {"max_total_s": MAX_TOTAL_S, "episodes": [1, 3], "attack_s": [10, 120], "calm_s": [5, 60], "rate_factor": [0.05, 1.0], "target": "127.0.0.1 only"}}

    def start(self, request: SimulationRequest):
        with self.lock:
            self._reap()
            if self.unavailable_reason():
                return 503, self.unavailable_reason()
            if self.process is not None:
                return 409, "a simulation is already running; stop it first"
            total = request.total_s()
            if total > MAX_TOTAL_S:
                return 422, f"planned run is {total} s; the limit is {MAX_TOTAL_S} s"
            home = self.home()
            if request.benign == "wokwi_only" and not home:
                return 409, "the Wokwi smart-home broker is not running; start it with scripts/start-wokwi-home.ps1"
            if not home and port_in_use(self.port):
                return 409, f"port {self.port} already has a broker (for example the demo lab); wait for it to finish"
            stamp = time.strftime("%Y%m%d-%H%M%S")
            out = self.data_dir / "lab" / "live" / f"{stamp}-sim"
            command = [sys.executable, "-m", "lab.run", "--out", str(out), "--port", str(self.port), "--ground-truth", str(self.schedule), "--scenario", request.benign, "--seed", str(request.seed)]
            if home:
                command += ["--attach", str(home)]
            if request.mix:
                command += ["--mix", ",".join(request.mix)]
            if request.families:
                command += ["--plan", "episodes", "--families", ",".join(dict.fromkeys(request.families)), "--episodes", str(request.episodes), "--attack-s", str(request.attack_s),
                            "--calm-s", str(request.calm_s), "--rate-factor", str(request.rate_factor), "--lead-s", str(LEAD_S)]
            else:
                command += ["--plan", "benign", "--seconds", str(request.seconds)]
            env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(ROOT / "src"), str(ROOT)]), "PYTHONUNBUFFERED": "1"}
            env.pop("LAB_TARGETS", None)  # dashboard runs are loopback only, whatever the shell allows
            out.mkdir(parents=True, exist_ok=True)
            log = open(out / "runner.log", "wb")
            try:
                self.process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
            finally:
                log.close()
            try:
                from ids.service import tie_to_this_process
                tie_to_this_process(self.process)  # Windows: the lab and its broker die with the API, even on a hard kill
            except OSError:
                pass
            self.current = {"running": True, "pid": self.process.pid, "started": time.time(), "planned_s": total, "ends_by": time.time() + total + 15, "request": request.model_dump(), "out_dir": out.name}
            return 200, self.current

    def stop(self):
        with self.lock:
            self._reap()
            if self.process is None:
                return False
            self.current = {**self.current, "stopped_by_user": True}  # so a stop is never reported as a failure
            kill_tree(self.process.pid)
            self.process.wait(timeout=10)
            self._reap()
            return True

    def watchdog(self):
        """Hard stop if a run outlives its plan, so nothing triggered from the dashboard can run unbounded."""
        with self.lock:
            overdue = self.process is not None and self.current and time.time() > self.current["ends_by"] + 30
        if overdue:
            self.stop()


def kill_tree(pid):
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
    except psutil.NoSuchProcess:
        return
    for p in [*children, parent]:
        try:
            p.kill()
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs([*children, parent], timeout=5)
