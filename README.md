# Edge Watch

A software-only college IoT cybersecurity project. Build an interactive 3D smart
home, control virtual devices, run bounded local attack simulations, and inspect
alerts from a passive MQTT intrusion detection system (IDS).

## Features

- **Smart Home:** seven-room 3D house, saved layouts, device placement, camera
  controls, accessible device list and acknowledged device commands.
- **Nine device types:** light, motion, climate, door, lock, camera, plug,
  thermostat and smoke. Use software devices or four virtual Wokwi ESP32
  controllers connected through serial-to-MQTT bridges.
- **Network monitoring:** measured MQTT activity, network sources and a live feed.
- **Attack Simulator:** rate-capped local scenarios, progress flow and honest
  detected, missed, stopped or failed outcomes.
- **Alerts:** history, filters, evidence and explicit consent before clearing
  stored alerts. Smoke safety alarms are separate from IDS security alerts.

Commands complete only after device acknowledgement. Software readings, power
consumption, camera events and other modeled behavior are simulations. No camera
video exists. Edge Watch observes and alerts; it does not prevent attacks or
guarantee detection. No physical deployment or real-world validation is claimed.

## Technology

Python 3.11+, FastAPI, WebSockets, SQLite, scikit-learn, Mosquitto, Wireshark/Npcap,
React, TypeScript, Vite, Three.js and React Three Fiber. Virtual ESP32 firmware
uses Arduino/PlatformIO and Wokwi for VS Code.

## Quick start (Windows PowerShell)

Install Python, Node.js compatible with the locked frontend packages, Mosquitto,
Wireshark with Npcap, and optionally VS Code with Wokwi and PlatformIO. From the
repository root:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[offline,dev,wokwi]" -c constraints-model.txt
Push-Location dashboard/web
npm ci
npm run build
Pop-Location
# Requires the separately supplied frozen model described below:
.\scripts\start-smart-home.ps1
```

Open [the local dashboard](http://127.0.0.1:8020). Startup coordinates the IDS,
home broker, API and bridges; no attack starts automatically. Software devices
need no Wokwi simulator. See [Setup](docs/SETUP.md), [User guide](docs/USER_GUIDE.md),
[Architecture](docs/ARCHITECTURE.md) and [Troubleshooting](docs/TROUBLESHOOTING.md).

## Limits and reproducibility

**The frozen `ew-dt12-lab-v6` model bundle is supplied separately** under
`$HOME/edgewatch-data/models/ew-dt12-lab-v6` (or the `EDGEWATCH_DATA` equivalent).
There is no public model download. A fresh clone supports source inspection and
tests, but cannot reproduce the complete trained IDS demo without this bundle.
Keep `constraints-model.txt`; do not retrain to replace a missing model.

Wokwi sensors on one controller share one packet-level source. Keep simulator
tabs visible so firmware continues reporting. All services and attack traffic
stay local; attacks are bounded to at most 600 seconds and rate-capped.

Models, datasets, captures, databases, runtime credentials and research evidence
are intentionally excluded. Runtime files normally live in `$HOME/edgewatch-data`,
outside the checkout. The `deploy/` Linux examples are historical and unverified
for this demo; do not use them to expose the broker or API.

## Project structure

- `dashboard/`: FastAPI API and three-page React frontend.
- `lab/`: software devices, broker, bridges, startup and bounded attack lab.
- `src/ids/`: capture, features, frozen-model inference and event store.
- `simulators/wokwi-{environment,access,lighting,safety}/`: four ESP32 projects;
  `wokwi-smart-home/` retains the legacy board.
- `scripts/`: Windows helpers; `tests/`: Python unit and integration checks.
- `docs/`: [current guides and preserved references](docs/README.md).
- [AGENTS.md](AGENTS.md) and [CODEX_HANDOFF.md](CODEX_HANDOFF.md): contributor
  rules and current maintenance context.

## Verification

```powershell
.venv\Scripts\python.exe -m pytest -q -m "not integration"
Push-Location dashboard/web
npm test
npm run build
Pop-Location
.venv\Scripts\python.exe -m pytest -q
```

The build includes TypeScript checks. Integration tests need local broker/capture
tools and use isolated ports. Never run `lab/e2e_cc.py` against a running user
stack. If running `lab.e2e`, always pass `--out` to a scratch folder.
