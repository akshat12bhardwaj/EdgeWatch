# Edge Watch

A software-only college IoT security demo: virtual smart-home devices communicate
over a local MQTT broker, a passive IDS observes loopback traffic, and a React
dashboard presents **Smart Home**, **Attack Simulator**, and **Alerts**.

Sensor values from software devices are simulated. Device commands complete only
after a device acknowledgement. Smoke safety alarms are separate from IDS alerts.
Edge Watch observes traffic and raises alerts; it does not prevent attacks.
Detection has not been validated on physical devices or real-world deployments.

## Source layout

- `src/ids/`: packet decoding, features, inference, alerts, persistence, and offline tools.
- `lab/`: MQTT devices, local broker integration, bounded attack simulator, serial bridge, and test tools.
- `dashboard/`: FastAPI/WebSocket API and React dashboard, including the npm lockfile.
- `simulators/wokwi-smart-home/`: ESP32 firmware, circuit, PlatformIO and Wokwi configuration.
- `scripts/`, `deploy/`: Windows launch helpers and historical Linux deployment examples.
- `tests/`, `docs/`: automated checks, operating instructions, architecture and project history.

## Setup and reproducibility

Use Python 3.11 or newer and a Node.js version compatible with the checked-in
frontend dependencies. Mosquitto and Wireshark's dumpcap/tshark are required for
live MQTT capture; install these separately. On Windows, loopback capture also
requires Npcap. Wokwi's free integration uses VS Code and an RFC2217 serial bridge;
PlatformIO builds the firmware. The optional WiFi gateway path is paid and unverified.

From the repository root in PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[offline,dev,wokwi]" -c constraints-model.txt
Push-Location dashboard/web
npm ci
npm test
npm run build
Pop-Location
.venv\Scripts\python.exe -m pytest -q -m "not integration"
```

**A fresh clone does not contain the frozen model, datasets, captures, runtime
credentials, or research evidence.** The default launch script requires the
separately provisioned `ew-dt12-lab-v6` bundle under
`$HOME/edgewatch-data/models/`. No public model download is provided here.
Without that bundle, the source and tests are available, but the complete trained
IDS demo cannot be reproduced from this repository alone. Do not retrain merely
to substitute a missing bundle. The IDS supports operation without inference;
see the operator guide for its manual command.

Read [CODEX_HANDOFF.md](CODEX_HANDOFF.md) for the current demo state and
[INSTALL_AND_OPERATE.md](docs/implementation/INSTALL_AND_OPERATE.md) for operation.
Older quick-start, presentation and phase documents describe historical UI and
research workflows. Their commands are not all appropriate for the current demo.
The `deploy/` examples are not the local demo configuration: in particular,
`mosquitto-edgewatch.conf` listens on all interfaces. Do not use it for this
loopback-only demo or expose the API/broker publicly.

Keep runtime files under `$HOME/edgewatch-data` (or `EDGEWATCH_DATA`), outside
the checkout. Generate local Wokwi credentials with the existing home setup;
`include/secrets.example.h` contains placeholders, while `include/secrets.h`
is ignored. Keep attacks on loopback, rate-capped, and at most 600 seconds.

## Validation and safe operation

The full Python suite requires local capture and broker tools:

```powershell
.venv\Scripts\python.exe -m pytest -q
```

Tests use isolated ports. Do not restart an existing demo to run checks.
Do not run `lab/e2e_cc.py` while user services are running: it can stop them.
When running `lab.e2e`, always supply `--out` pointing to a scratch directory;
its default writes into protected research results.

This publication preserves the existing Git history. Research artifacts and
frozen models remain local and unchanged; their absence is intentional.
