# Edge Watch: handoff to Codex (2026-11-09)

Working rules are in [AGENTS.md](AGENTS.md). Everything below was checked against the repository and the running machine on 2026-11-09. Anything not verified is marked as such.

## 1. What this is

A **software-only college IoT security demo**. Virtual smart-home devices talk MQTT to a local Mosquitto broker. A passive IDS captures that traffic on Windows loopback, classifies 5-second windows with a decision tree (`ew-dt12-lab-v6`), and raises alerts. A React dashboard lets a user build a home, control devices, run bounded attacks, and watch the IDS respond.

There is no hardware and no cloud. It is not real-world validated: all traffic is simulated on one PC, and the UI says so.

## 2. Architecture

```
Smart Home devices (lab/devices.py, one MQTT client each)  ┐
Wokwi ESP32 → RFC2217 serial :4000 → serial bridge          ├→ Mosquitto (home hub, 127.0.0.1/::1:18840) ─┐
Attack lab (lab/run.py, attacks.py, bounded, loopback)      ┘                                             │
dumpcap on \Device\NPF_Loopback "tcp port 18840" → ids.service (decode → features F01–F26 → model → alerts) │
  → SQLite event store (~/edgewatch-data/run/events.sqlite) → FastAPI + WebSocket :8000 → React dashboard   │
Telemetry reader (lab/home.py Bridge) → ~/edgewatch-data/home/telemetry.json → /api/home ←─────────────────┘
```

| Path | Contents |
|---|---|
| `src/ids/` | IDS: `decoder`, `features`, `pipeline`, `detector`, `alerts`, `store`, `service`; also `baselines` and `training` (offline). **Do not change detection behaviour.** |
| `lab/` | `devices.py` (9 device state machines plus host), `home.py` (hub: broker, ACL, telemetry reader, serial bridge, `send_command`), `run.py`, `attacks.py`, `benign.py`, `gateway.py`, `wire.py` (raw MQTT client), `safety.py`, `e2e.py`, `e2e_cc.py` |
| `dashboard/api/` | `app.py` (all endpoints), `simulation.py` (bounded lab runs, hub detection) |
| `dashboard/web/src/` | `main.tsx` (shell, hash routes), `smarthome.tsx` (floor plan, inspector, device controls), `demo.tsx` (Attack Simulator), `alerts.tsx`, `overview.tsx` (status, incidents, chart), `devices.ts` (catalogue, placement), `home.tsx`, `store.ts`, `ui.tsx`, `styles.css` |
| `simulators/wokwi-smart-home/` | PlatformIO ESP32 firmware (DHT22 GPIO15, PIR GPIO13, LED GPIO26). Env `esp32dev` is the serial protocol (default); env `esp32dev-wifi` is direct MQTT and needs Wokwi's paid gateway (unverified) |
| `scripts/` | `start-edgewatch.ps1`, `stop-edgewatch.ps1`, `start-wokwi-home.ps1`, `stop-wokwi-home.ps1` |
| `docs/implementation/INSTALL_AND_OPERATE.md` | Operator guide. §7 covers Wokwi, §8 the Smart Home, devices and attacks |
| `docs/AUTONOMOUS_EXECUTION_LOG.md` | Dated checkpoints (history) |

## 3. Functionality (implemented and verified)

**Navigation:** Smart Home · Attack Simulator · Alerts (hash routes `#/home`, `#/attack`, `#/alerts?source=<key>`). Advanced (detector comparison, research results, diagnostics) was **removed**; old `#/advanced/...` links open Smart Home.

**Smart Home:**
- Floor plan with 7 rooms and drag-and-drop from the palette (pointer events), plus a **+** button and keyboard support (arrows move, Enter selects, Delete removes).
- Inspector edits name, type, room and backing.
- Layout is saved through `PUT /api/home/layout` to `~/edgewatch-data/home/layout.json`: at most 24 devices, local only.
- Device ids are never reused.

**Nine devices.** Each software device is its own MQTT client from its own address `127.0.4.x`, with topics `edgewatch/devices/<id>/{state,status,event,command}`:

| Device | Behaviour | Controls |
|---|---|---|
| light | on/off | On, Off |
| motion | motion, then clear after 5–60 s | Trigger, clear-after |
| climate | reading moves towards the set room temperature/humidity | Room sliders |
| door | open/closed, last change | Open, Close |
| lock | locked/unlocked; simulated keypad (not real auth) | Lock, Unlock, Correct/Wrong code |
| camera | monitoring on/off, motion events (no video) | Pause/Start, Simulate motion |
| plug | on/off, simulated W and Wh | On, Off, appliance |
| thermostat | ±0.05 °C/s towards target | Target ±0.5 |
| smoke | level, threshold, latched alarm. A **safety** alarm, kept separate from IDS alerts | Simulate smoke, Reset, threshold |

How the devices behave:
- **Commands:** `POST /api/home/devices/{id}/command` validates per type. The UI marks a command done **only** when the device's next state echoes `ack == cmd_id`.
- **Last will:** each device's last will sets its status to `offline`.
- **Persistence:** device state persists in `home/device-state.json`.
- **Access control:** the ACL denies the lab/attack account access to `edgewatch/devices/#` and `edgewatch/home/#`.

**Hub:** Smart Home → Home panel → **Start hub** (`POST /api/home/start`) runs `python -m lab.home serve --port 18840 --serial rfc2217://localhost:4000 --devices <run dir>/devices.json` as a **child of the API**. `start-wokwi-home.ps1` starts the same hub independently.

**Wokwi (free path, verified):**
- The firmware prints lines like `EW1 <field> <value>`, and Wokwi for VS Code serves the serial port over RFC2217 (`rfc2217ServerPort = 4000` in `wokwi.toml`).
- The serial bridge publishes those readings to MQTT as the device's account, from `127.0.3.10`. **The ESP32 itself does not speak MQTT here**, and the IDS sees the bridge's session.
- Verified: DHT22 readings, PIR changes and LED control (confirmed by the firmware's own state).
- One board, so at most one Wokwi-backed light, motion sensor and temperature sensor.

**Attack Simulator:**
- 7 attacks (two marked "Not trained"), aimed at the hub. Traffic comes from separate lab clients `127.0.2.x`, drawn outside the house.
- Each run is bounded at 600 s maximum and loopback only.
- If the hub is running, the lab **attaches** to it (`lab.run --attach`); otherwise it starts its own broker.
- The progress steps advance only from IDS events; a missed attack is shown as missed.

## 4. Commands (verified)

PowerShell, from the repo root:

```powershell
.\scripts\start-edgewatch.ps1 -Mode dashboard   # API http://127.0.0.1:8000 + IDS on MQTT port 18840 (refuses if already running)
# then Smart Home → Start hub   (or: .\scripts\start-wokwi-home.ps1 ; stop with .\scripts\stop-wokwi-home.ps1)
# Wokwi (manual, VS Code): open simulators\wokwi-smart-home → F1 → "Wokwi: Start Simulator"
.\scripts\stop-edgewatch.ps1                    # stops only what start-edgewatch.ps1 recorded

.venv\Scripts\python.exe -m pytest -q -m "not integration"   # 426 pass, ~13 s: run this first
.venv\Scripts\python.exe -m pytest -q                        # 437 pass, ~65 s; integration tests need Mosquitto + dumpcap
cd dashboard\web; npm test; npm run build                    # 30 pass; build runs tsc --noEmit first
.venv\Scripts\python.exe -m lab.e2e --model "$HOME\edgewatch-data\models\ew-dt12-lab-v6" --out <scratch dir> --shots <scratch dir>
cd simulators\wokwi-smart-home; & "$HOME\.platformio\penv\Scripts\pio.exe" run -e esp32dev
```

Details for the commands above:
- `start-edgewatch.ps1 -Mode dashboard` was verified by `lab.e2e_cc` (31/31) earlier on 2026-11-09, before the UI redesign. The dashboard's Start hub button and the Wokwi scripts were verified later.
- `lab.e2e` is self-contained: ports 8012, 18871 and CDP 9333, about 5 min. **Always pass `--out`.** The default writes into the protected `results/ENG-E2E`.
- Tests bind isolated ports 18831, 18832, 18870, 18899, 18961 and 18962.

## 5. Running now (do not stop, restart or reuse)

| Process | PID | Port | Started by |
|---|---|---|---|
| `python -m dashboard.api --port 8000` | 29432 (child 30052) | 127.0.0.1:8000 | Claude, with the start script's environment; recorded in `~/edgewatch-data/run/edgewatch-pids.json` |
| `python -m ids.service ... --port 18840` | 32988 (child 24460) | captures loopback tcp 18840 | user's `start-edgewatch.ps1` at 13:34 (run dir `run/20261109-133420`) |
| Smart-home hub `python -m lab.home serve --port 18840 --serial ... --devices ...` | 40556 (child 40332, mosquitto 44040) | 127.0.0.1 / ::1 : 18840 | dashboard Start hub, 20:29; **a child of the API (30052), so it stops if the API restarts** |
| VS Code (Wokwi simulator, RFC2217) | 26864 | [::]:4000 | user |

Other runtime state:
- At 20:36 the hub reported the Wokwi ESP32 online and 9 of 9 software devices online.
- The hub writes `~/edgewatch-data/home/serve.out.log`. It is not in the PID file (it's dashboard-started); stop it with Smart Home → Stop hub (`POST /api/home/stop`).
- The `lab` PID 30676 in the PID file is stale.
- Shared data dir `~/edgewatch-data`: `run/events.sqlite` (live store, which already holds demo and test alerts), `home/` (credentials, layout, device state, logs), `models/`, `lab/`.
- Avoid ports 8000, 18840 and 4000 for tests. `lab/e2e_cc.py` **stops the running stack** (shared PID file), so don't run it while the user's services are up.

## 6. Latest verification (2026-11-09)

- **Python:** 437 passed. Strict `-W error::ResourceWarning` also passes, and 0 sqlite connections are left unclosed. The 1 remaining warning is the starlette/httpx deprecation from a dependency.
- **Frontend:** 30 passed; `tsc` clean; build OK.
- **`lab.e2e`:** 14/14, including the three-sections/old-link check.
- **Live checks** (one-off browser scripts, not in the repo):
  - 19/19 nine-device UI flow: controls confirmed by acks, removal, refresh, hub-restart recovery, IDS saw every device as normal.
  - Attack with the Wokwi board plus 9 devices online: Message flooding alerted after 8.7 s, the only alert was on the attacker, and devices stayed online and normal.
- **Not re-verified:** `lab/e2e_cc.py` (selectors updated after the redesign, never re-run), and the paid `esp32dev-wifi` path.

## 7. Known issues and limits

- A hub started from the dashboard dies when the API restarts. Its Wokwi serial session then ends, and the simulator may need restarting in VS Code.
- The IDS identifies sources by IP: all Wokwi traffic is one source (the bridge). Software devices' values are simulated and labelled as such.
- On phones the floor plan pans; dragging devices needs a mouse (use **+** and the inspector instead).
- Some docs (`docs/CHATGPT_PROJECT_HANDOVER.md`, `docs/presentation/*`, phase docs) describe earlier designs. Two carry a status note; treat them as history.
- `lab/e2e_cc.py`'s process detection matches any `dashboard.api` or `ids.service`, so it needs a machine with no other Edge Watch running.
- No pending feature work was requested at handoff.

## 8. Protected (do not modify or delete)

- `~/edgewatch-data/models/*`: the frozen bundles `ew-dt12-lab-v6` (deployed) and v1–v5, plus `constraints-model.txt` (pinned versions needed to load them).
- `results/` (53 experiment folders, `metrics.json` evidence) and `~/edgewatch-data/{raw,reference,engineering,reports}` (datasets and evidence).
- `src/ids/` detection logic, features and thresholds; `docs/DECISIONS.md` (open decisions such as D-01 need owner approval).
- Live data: `~/edgewatch-data/run/events.sqlite` and `home/credentials.json`.

## 9. Git

- Branch `docs/phase-00-baseline` (main branch: `main`). Last commit `4be5493`. **Nothing from this work is committed.**
- Modified (tracked): `.gitignore` and 9 docs files.
- Untracked: `dashboard/`, `lab/`, `src/`, `tests/`, `scripts/`, `simulators/`, `deploy/`, `results/`, `pyproject.toml`, `constraints-model.txt`, several docs, `CODEX_HANDOFF.md` and `AGENTS.md`.
- `simulators/wokwi-smart-home/.gitignore` excludes `.pio/`, `include/secrets.h` and `build.log`.
- Do not stage, commit or push without the owner's approval.
