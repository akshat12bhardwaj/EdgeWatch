# Edge Watch maintenance handoff (2026-11-10)

Read [AGENTS.md](AGENTS.md) before work. Current public documentation starts at
[README.md](README.md) and [docs/README.md](docs/README.md). This replaces accumulated
historical checkpoints; previous tracked versions remain in Git history.

## Current application

Software-only college demo: three pages, **Smart Home**, **Attack Simulator** and
**Alerts**. No Advanced/research/diagnostic section. No new feature work or research
experiments are requested.

- Smart Home: seven-room Three.js cutaway, saved placement, nine device types,
  independent software MQTT devices, four optional Wokwi ESP32 controller backings.
  Device list/inspector provide keyboard and graphics-failure alternatives.
- Right-side controls contain hub start/stop, palette, device list and inspector.
  Network communication uses measured IDS samples and new device/security events.
  Missing data stays unavailable. Network sources are not logical device counts.
- Device totals use the saved layout and fresh reports; Wokwi devices also require
  a fresh controller. Commands complete only on device acknowledgement. Smoke
  safety alarms stay separate from security alerts. No camera video exists.
- Attack Simulator uses actual run status and scheduled-source IDS events. It
  allows ten seconds after traffic ends before reporting a missed detection.
  Result links reference actual alert IDs, never invented records.
- Clear Alert History requires explicit consent and deletes all sessions' alerts,
  including current-session alerts, transactionally. Other telemetry is preserved.
- Controller bridges separate serial/MQTT reconnection, retain serial sessions
  during broker outages, and use bounded reconnect backoff. Firmware silence
  stays visible; paused simulator tabs need the user's attention in VS Code.
- The store serializes capture/monitor use of its SQLite connection; monitoring
  logs per-tick errors and continues. No detector features/thresholds changed.

## Commands and service ownership

From the repository root:

```powershell
.\scripts\start-smart-home.ps1
.venv\Scripts\python.exe -m lab.startup status
# Only after your demo; stops the launcher's verified owned processes:
.venv\Scripts\python.exe -m lab.startup stop
```

Default dashboard: http://127.0.0.1:8020; MQTT: 18840. Startup shares data, store
and attack schedule; preserves compatible services; starts no automatic attacks.
See [Setup](docs/SETUP.md) for dependencies and the separately supplied frozen model.

The owner has active services. Do not assume old PIDs or restart any component.
Use status/process inspection before acting. Reserve API 8000/8020, MQTT 18840,
Wokwi 4000–4004 and any other active listeners. Use isolated ports for tests.
`lab/e2e_cc.py` and the older stop script can interfere with a user stack: do not
run them while it is active. Do not launch attacks against it for documentation work.

Runtime files normally live at `$HOME/edgewatch-data`: `home/` holds credentials,
layout/state/telemetry and controller snapshots; `run/` holds the event DB, startup
records and logs. Never stage these files. A dashboard-started hub is an API child.

## Verification and known limits

Publication checks on 2026-11-10: 56 focused Python tests, 471 non-integration
tests, 482 full-suite tests (including 11 integration), 54 frontend tests,
TypeScript/production build, Python compilation and all five serial firmware
builds passed. Local and immutable-history Markdown file/anchor checks passed.
Dependency consistency passed. No live-stack restart or destructive E2E was run.

Use the [README test commands](README.md#verification), focused checks first.
Integration tests use isolated ports and temporary stores. Compile-check modified
Python before any authorized restart. Firmware builds do not reload running Wokwi
simulators. Keep simulator tabs visible to avoid stale reports.

The trained demo cannot run from a clone without the owner's unchanged
`ew-dt12-lab-v6` bundle. No public download is supplied. Model/dataset/evidence
directories remain external and protected. Never retrain or tune detection to
improve results. Historical attached attack runs include missed detections.

Earlier hybrid browser verification passed 18/19 checks; one long fake-firmware
remapping harness stalled and failed its 25-second timing check. A focused probe
passed and the device recovered. This is historical evidence, not a claim that
the full browser harness was rerun for publication. Avoid destructive live E2E.

Existing advisories: large lazy 3D build chunk and Starlette/httpx deprecation.
Linux deployment examples and paid Wokwi WiFi gateway remain unverified and are
not the supported local demo route.

## Protected files and publication

Preserve frozen models, `constraints-model.txt`, `results/`, external raw/reference/
engineering/reports evidence and `docs/DECISIONS.md`. Detection logic/features/
thresholds remain frozen. Preserve original attribution and unresolved decisions.

The owner explicitly authorized the November 2026 documentation cleanup and normal
commit/push to `https://github.com/akshat12bhardwaj/EdgeWatch.git`. This authorization
does not allow force pushes, history replacement or deleting remote branches.
Future publication work still follows AGENTS.md and requires owner authorization.
