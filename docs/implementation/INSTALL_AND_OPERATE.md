# Install and Operate

**For day-to-day use on Windows, follow [WINDOWS_QUICK_START.md](WINDOWS_QUICK_START.md).**

**Verified:** Windows 11, Python 3.13, Node 26, Wireshark 4.6.9 with Npcap, Mosquitto 2.0.15 from conda-forge, all on loopback. **Not verified:** the Linux and Raspberry Pi steps in section 5.

## 1. Install (Windows development machine)

```powershell
python -m pip install -e ".[offline,dev]" -c constraints-model.txt   # the constraints match the saved models
conda create -y -p $HOME\edgewatch-data\tools\mosquitto -c conda-forge --override-channels mosquitto
winget install WiresharkFoundation.Wireshark        # with Npcap; loopback capture needs no admin rights after install
cd dashboard\web; npm install; npm run build; cd ..\..
```

Raw data, tables, models and lab runs live in `%USERPROFILE%\edgewatch-data`, or wherever `EDGEWATCH_DATA` points. Never put them in Git or OneDrive.

## 2. Test

```powershell
python -m pytest tests -m "not integration"   # unit and API tests
python -m pytest tests -m integration          # real broker, real capture, real IDS process
cd dashboard\web; npm test; npm run build
```

## 3. Run the whole system

Run each in its own terminal, with `$env:PYTHONPATH="src;."` set in each.

```powershell
# Broker, benign clients, and a scheduled attack run on a lab port
python -m lab.run --out $HOME\edgewatch-data\lab\demo --plan episodes --episodes 1 --port 18840

# IDS. Leave out --model to run without inference
python -m ids.service --db $HOME\edgewatch-data\run\events.sqlite --model $HOME\edgewatch-data\models\<model id> --port 18840

# API and dashboard, at http://127.0.0.1:8000
$env:EDGEWATCH_DB="$HOME\edgewatch-data\run\events.sqlite"; $env:EDGEWATCH_MODEL="$HOME\edgewatch-data\models\<model id>"
python -m dashboard.api
```

A bounded lab run from the command line, the same thing the Security Demo page starts (loopback only; families from `lab.attacks.FAMILIES`):

```powershell
python -m lab.run --out <dir> --port 18840 --plan episodes --families bruteforce,topic_probe --episodes 1 --attack-s 30 --calm-s 15 --rate-factor 0.5 --ground-truth <run dir>\ground_truth.json
python -m lab.run --out <dir> --port 18840 --plan benign --scenario smart_home --seconds 300
```

The API enables the Security Demo page only when `EDGEWATCH_MQTT_PORT` and `EDGEWATCH_SCHEDULE` are set (the start script sets them). Simulation control is refused from any non-loopback client, and needs `EDGEWATCH_API_TOKEN` too when that is set. Requests with a foreign `Host` header are refused; list extra names in `EDGEWATCH_ALLOWED_HOSTS` when exposing the API.

Replay a recorded capture, shown as `REPLAY`:

```powershell
python -m ids.service --db $HOME\edgewatch-data\run\replay.sqlite --model <bundle> --replay <capture.pcap> --port 18840 --speed 10
```

The whole chain with a real browser, writing `results/ENG-E2E/metrics.json`:

```powershell
python -m lab.e2e --model <bundle> --shots <folder>
```

## 4. Reproduce the results

```powershell
python -m ids.pipeline <capture> <out dir> [--raw-sources]   # engineering table and diagnostics
python -m ids.training dq-mqttset                            # leakage checks; needs tables for all 6 captures
python -m ids.training mqttset                               # ENG-M1
python -m ids.training lab-tables --campaign campaign2
python -m ids.training lab-select --campaign campaign2       # ENG-L1
python -m ids.training lab-final --campaign campaign2 --kind <k> --params "<json>" --features without_F25_F26 --model-id <id>   # ENG-L2
python -m ids.training lab-stealth --campaign campaign2 --model-id <id> --port 18844   # ENG-L3
python -m ids.training lab-transfer --campaign campaign2     # ENG-X1
python -m lab.perf --model <bundle>                          # ENG-P1
python -m ids.training lab-compare --campaign campaign6      # ENG-C1: v6 tree vs LR, RF, rule and rate baselines on identical held-out runs
python -m ids.training lab-splits --campaign campaign6       # ENG-R1: random vs episode-grouped vs run-held-out splits on dev runs
python -m lab.bench                                          # ENG-P3: state bounds and per-stage cost
python -m lab.e2e_cc --shots <folder>                        # ENG-E2E-CC: start script, Simulate API, WebSocket, browser, failures, stop, restart
```

`edgewatch-data/scripts/lab_campaign2.ps1` holds the exact lab commands. Run IDs and lab traffic are not byte-identical between runs, because they are real timed traffic. Only one run may use a given port, since each capture filters on its port.

## 5. Gateway (Linux, Raspberry Pi): unverified

No Raspberry Pi was available, so **none of this has been run.** Treat it as a checklist to test.

```bash
sudo useradd -r edgewatch
sudo mkdir -p /opt/edgewatch /var/lib/edgewatch/models /etc/edgewatch
sudo apt install mosquitto tshark     # tshark brings dumpcap
sudo setcap cap_net_raw,cap_net_admin+eip "$(command -v dumpcap)"
python3 -m venv /opt/edgewatch/.venv && /opt/edgewatch/.venv/bin/pip install /opt/edgewatch
sudo cp deploy/mosquitto-edgewatch.conf /etc/mosquitto/conf.d/
sudo cp deploy/edgewatch-*.service /etc/systemd/system/ && sudo systemctl daemon-reload
sudo systemctl enable --now edgewatch-ids edgewatch-api
```

**Must be checked on the device:**
- A model bundle refuses another scikit-learn version, so retrain on the gateway's version, or pin it. This is by design (ADR-11).
- `eth0` is the right interface in `edgewatch-ids.service`.
- CPU, RSS, and latency: nothing measured here applies.
- `MemoryMax=512M` restarts the IDS if F22 state grows, resetting state as if capture had started there.
- Interface offload settings, which can change F01, F07 and F08 (T2).

To expose the API beyond loopback, set `EDGEWATCH_API_TOKEN` in `/etc/edgewatch/api.env`. It refuses to start otherwise.

## 6. Health and troubleshooting

`GET /api/health` gives `status` (`ok`, `idle`, `disabled`, `no_store`), `ids`, `broker_running`, `model_loaded`, and provenance.

| Symptom | Likely cause | Check |
|---|---|---|
| `no_store` | IDS never started, or a different `EDGEWATCH_DB` | Paths match |
| "inference off" in P1 | Model missing or refused | IDS log says why, including version mismatch |
| No windows, IDS running | Wrong interface or port | `dumpcap -D`; `--port` matches the broker |
| Broker "not seen" | Process is not named `mosquitto`, or another broker | Display only; it does not affect the broker |
| `ids.pipeline` shows `tcp_sequence_gaps` | Packets lost in capture | Lower load; compare with generator counts |
| Red "Provenance unknown" bar | Mixed events in one view | Use separate stores for live and replay |
| Lab client refused | A second broker on that port | One run per port |

**Stop order does not matter.** The broker, IDS and API are independent.

## 7. Wokwi virtual smart home (optional)

One simulated ESP32 in Wokwi for VS Code publishes real sensor readings over MQTT to a broker on the port the IDS captures. The Python lab still provides every attack. Nothing here changes the IDS, its features or the model.

**Default path (free, verified 2026-11-09):** Wokwi ESP32 firmware → UART → Wokwi's RFC2217 serial server on `localhost:4000` (`rfc2217ServerPort` in `wokwi.toml`) → `lab.home` serial bridge → MQTT on the home broker `127.0.0.1:18840` → loopback capture → IDS → dashboard.

**Here the ESP32 does not speak MQTT.** It prints structured serial lines, and the serial bridge publishes them, using the device's broker account, from its own address (`127.0.3.10`, labelled "Wokwi ESP32 (serial bridge)"). Edge Watch analyses the bridge's MQTT session; it does not see the simulated ESP32's WiFi packets. Light commands go the other way: dashboard → `light/set` → bridge → serial → firmware → LED.

**Gateway path (paid, not verified):** firmware env `esp32dev-wifi` connects over Wokwi WiFi to `host.wokwi.internal:18840` through the Private IoT Gateway. The IDS then sees the gateway's connection from `127.0.0.1`, labelled "Wokwi ESP32 smart home". Start the helper with `-Gateway` to use it.

### Prerequisites

| Item | Where | Notes |
|---|---|---|
| Wokwi for VS Code | extension `wokwi.wokwi-vscode` | F1 → “Wokwi: Request a new License” on first use (free account) |
| RFC2217 serial server | `rfc2217ServerPort = 4000` in `wokwi.toml` | Worked on this machine's Wokwi license, with no paid gateway (verified 2026-11-09) |
| pyserial | `.venv\Scripts\python.exe -m pip install pyserial` (extra `edgewatch[wokwi]`) | RFC2217 client for the serial bridge |
| Private IoT Gateway | F1 → “Enable Private Wokwi IoT Gateway” | Only for the `-Gateway` path. Wokwi documents it as **paid plans only** |
| PlatformIO | extension `platformio.platformio-ide` | The first build downloads the Arduino-ESP32 framework (about 4 min) |
| Edge Watch | `start-edgewatch.ps1 -Mode dashboard` | The home broker must run on the IDS's port |

### Files

- `simulators/wokwi-smart-home/`: `platformio.ini` (env `esp32dev`: serial protocol, the default; env `esp32dev-wifi`: direct MQTT), `src/main.cpp`, `diagram.json` (ESP32 DevKit-C v4, DHT22 on GPIO 15, PIR on GPIO 13, LED with 220 Ω on GPIO 26), `wokwi.toml` (`.pio/build/esp32dev/firmware.bin`/`.elf`, `rfc2217ServerPort = 4000`), `include/secrets.example.h`. `include/secrets.h` is generated and git-ignored.
- `lab/home.py`: `init` (accounts, ACL, broker config, `secrets.h`) and `serve` (broker, telemetry reader, and with `--serial` the RFC2217 serial bridge). State lives in `%USERPROFILE%\edgewatch-data\home\`.
- `scripts/start-wokwi-home.ps1`, `scripts/stop-wokwi-home.ps1`.

### Topics

| Topic | Direction | Payload | When |
|---|---|---|---|
| `edgewatch/home/temperature` | ESP32 → | `22.5` (°C, −40 to 80) | every 10 s |
| `edgewatch/home/humidity` | ESP32 → | `45.0` (%RH, 0 to 100) | every 10 s |
| `edgewatch/home/motion` | ESP32 → | `1` / `0` | on PIR change |
| `edgewatch/home/light/state` | ESP32 → | `ON` / `OFF`, retained | after each change |
| `edgewatch/home/device/status` | ESP32 → | `online` retained; `offline` as last will | on connect and on loss |
| `edgewatch/home/light/set` | → ESP32 | `ON` / `OFF` / `1` / `0`; anything else is ignored | dashboard button |

**Broker security:** loopback listeners only, no anonymous access, and three accounts with random passwords generated once per install (`home\credentials.json`, outside Git). The ACL allows only `wokwi-home` to publish sensor topics, only `edgewatch-bridge` to send `light/set`, and denies `labclient` (all lab traffic and attacks) everything under `edgewatch/home/`. A lab attack therefore cannot fake what the dashboard shows. The bridge keeps only validated latest values in `home\telemetry.json`; nothing goes into the IDS store, and detection never reads it.

**Lab runs:** while the home broker is serving, Security Demo runs (and `lab.run --attach <home-broker.json>`) use it instead of starting their own broker. `wokwi_only` is a lab scenario with no Python devices, so the ESP32 is the only normal device.

**Serial protocol** (115200 baud, one line each): from the device, `EW1 temperature 22.5`, `EW1 humidity 45.0`, `EW1 motion 1|0`, `EW1 light ON|OFF`, `EW1 status online`; to the device, `EW1 light ON|OFF`. The bridge validates every line the same way as MQTT telemetry, and also enforces lines of at most 64 bytes (longer ones are dropped whole) and at most 20 lines/s (the excess is dropped, never queued). It publishes `device/status online` when the device starts talking and `offline` when the serial link closes, and reconnects every 2 s while the simulator is stopped. Lines that aren't protocol, such as the ESP32's boot log, are logged to `home\serve.out.log` (at most 50 per session).

### Start and stop (verified commands)

```powershell
.\scripts\start-edgewatch.ps1 -Mode dashboard   # IDS + API, MQTT port 18840, http://127.0.0.1:8000/
.\scripts\start-wokwi-home.ps1                  # home broker + bridge; builds the firmware when secrets.h is newer
# Manual, in VS Code: open simulators\wokwi-smart-home as the folder, then F1 > "Wokwi: Start Simulator"
# Evidence: %USERPROFILE%\edgewatch-data\home\serve.out.log says "serial bridge: connected to rfc2217://localhost:4000"
.\scripts\stop-wokwi-home.ps1                   # hub only; Edge Watch keeps running
.\scripts\stop-edgewatch.ps1
```

The start helper refuses a second instance, a busy port, a still-running startup-demo lab, and an IDS on another port. It prints the manual VS Code steps.

### Demonstration

1. Smart Home → the Home panel shows the Wokwi ESP32 as Connected, and Wokwi-backed devices on the floor plan show “Connected” and live readings. In Wokwi, click the DHT22 or PIR to change values; the dashboard follows within about 2 s.
2. Turn the smart light on from the card. The LED changes in Wokwi, and the card updates only when the ESP32 reports `light/state`.
3. Attack Simulator → choose an attack → Start attack. Your layout's software devices run as normal traffic next to the Wokwi ESP32. The steps light up from real IDS events; a missed attack shows as missed.
4. The smart-home readings keep updating during the attack. The alert opens with a plain-English explanation.

### Troubleshooting

| Symptom (serial path) | Cause and fix |
|---|---|
| Log stays at "waiting for the Wokwi serial server" | The simulator isn't running, or `wokwi.toml` lacks `rfc2217ServerPort = 4000`. Start it in VS Code |
| The simulation stopped after the hub restarted | Wokwi ended the run when its serial client disconnected (observed). Restart the simulator after restarting the hub |
| Card shows "Hub not running" after an upgrade | Restart the API so `/api/home` is loaded |

| Symptom | Cause and fix |
|---|---|
| Serial: `MQTT: ... failed, state -2` | The gateway cannot reach the broker. Enable the Private IoT Gateway (paid plan), check that `start-wokwi-home.ps1` is running, and check the port in `secrets.h` |
| Serial: `failed, state 5` | Not authorised: `secrets.h` is older than the credentials. Rerun `start-wokwi-home.ps1` (it rebuilds), then restart the simulator |
| Card shows “Hub not running” | Start `start-wokwi-home.ps1`. If you just upgraded, restart the API so `/api/home` exists |
| Card warns about a different port | The hub and the IDS use different ports; restart one with matching `-MqttPort` |
| `#error include/secrets.h is missing` | Run `python -m lab.home init --port 18840` (or the start helper) |
| Demo says the port already has a broker | The startup demo's own lab broker is running; wait for it, or use `-Mode dashboard` |

### End-to-end evidence (2026-11-09, serial path, live stack)

- Wokwi's RFC2217 server listened on `localhost:4000`, owned by VS Code. The bridge received the ESP32's own ROM boot lines and `Edge Watch virtual smart home starting`.
- Readings reached the dashboard through MQTT: 22.5 °C and 45 % (the DHT22 values set in `diagram.json`), motion, light state, `online`.
- Light: 5 of 5 commands in the instrumented session came back confirmed by the firmware's own `light` report (about 0.3 s each), and the LED was seen lit in Wokwi.
- PIR: two clicks in Wokwi produced `motion 1` then `motion 0` about 5 s later, twice, all of it through bridge, MQTT and reader. One earlier command, sent before diagnostic logging existed, was not applied; the cause is unexplained.
- IDS: the serial-bridge source had 34 windows (CONNECT, PUBLISH and SUBSCRIBE counted), all `normal`, with 0 alerts.
- Attack: a Security Demo in `wokwi_only` mode with 30 s of publish flooding was alerted after 11.3 s (1/1 matched, 0 missed). The device kept publishing during the attack, its windows stayed `normal`, and the only alert was on the lab attacker's source.

### Tests

`tests/test_home.py` uses a real Mosquitto on isolated port 18961, with a raw client standing in for the ESP32. It covers the topic contract against `main.cpp`, validation, ACL isolation, light control, attach-mode lab runs and the IPv6 listener. `tests/test_api_command_center.py` covers `/api/home` and `/api/home/light`, and `dashboard/web/src/home.test.ts` covers connectivity status. These test Edge Watch's side; Wokwi's side is verified only by a real simulator run (see the execution log).

### Limits

- The IDS identifies sources by address. Every connection the gateway makes appears as one loopback source, so two simulated ESP32s would share one source.
- On the free path the IDS observes the bridge's MQTT traffic for the device, not the device's own network behaviour; detection results describe that session.
- Wokwi's free plan has no Private IoT Gateway, so direct ESP32 MQTT (`-Gateway`) needs a paid plan; only the serial path was verified.
- `wokwi-cli` runs on Wokwi's servers and is not documented to support `host.wokwi.internal`; there is no headless end-to-end run.
- The ESP32 traffic was never in the model's training data, so a false alert on it is possible. It would appear as an alert with “No simulated attack was scheduled”.


## 8. Smart Home builder and Attack Simulator

The dashboard opens on **Smart Home**: a floor plan with seven rooms, the smart-home hub (the MQTT broker) and Edge Watch in the network closet. The other pages are **Attack Simulator** and **Alerts**. The old `#/overview` and `#/demo` links redirect, and any other old link (such as `#/advanced/...`) opens Smart Home. The Advanced section (detector comparison, research results, diagnostics) was removed on 2026-11-09; the IDS, models, training code and `results/` files are unchanged and stay usable from the command line.

### Building a home

- Drag a device from the palette into a room, or press **+** to add it to the selected device's room (the living room if none is selected). Drops outside the house are refused. Positions snap to a grid and avoid other devices and the hub.
- Drag a placed device to move it, including into another room. With a device focused, the arrow keys move it, Enter selects it and Delete removes it.
- The inspector edits name, type, room and what simulates the device. **Remove device** deletes it.
- **Start with a sample home** places 9 devices. When the Wokwi hub is set up, the sample backs its temperature sensor, motion sensor and light with the Wokwi ESP32.
- The layout is saved through `PUT /api/home/layout` (loopback only, validated, at most 24 devices) to `%USERPROFILE%\edgewatch-data\home\layout.json`, outside the IDS store. It survives reloads and restarts.

### Devices

Every placed device is one of two kinds:

- **Software device.** It runs in the smart-home hub's device host (`lab/devices.py`) as its own MQTT client, with its own stable loopback address (`127.0.4.x`), so Edge Watch's IDS sees it as a separate source. A small deterministic state machine drives it, and watts, smoke level and room temperature are labelled simulated.
- **Wokwi device.** Only a light, motion sensor or temperature sensor can be Wokwi-backed, using the ESP32's LED, PIR or DHT22, at most one of each. Its readings come from the ESP32 through the serial bridge, and only while it is reporting.

**Topics** for software devices, under `edgewatch/devices/<id>/`:
- `state`: retained JSON on every change and as periodic telemetry. Fields: `id`, `type`, `seq`, `updated`, `ack`, plus the type's own fields.
- `status`: retained `online`/`offline`. `offline` is also the client's last will, so a crashed device shows as offline.
- `event`: camera motion, smoke alarm, lock access attempt, door opened or closed.
- `command`: from the dashboard, as `{"cmd_id": ..., <field>: <value>}`.

**How a command is confirmed.** The API validates each command per type before publishing it. The dashboard counts a command as done only when the device's next `state` echoes its `cmd_id` as `ack`, and shows "no confirmation" after 8 s otherwise.

**Access control.** The broker ACL lets only the device host publish device state, and only the dashboard's bridge account send commands. The lab (attack) account is denied `edgewatch/devices/#`, so an attack cannot fake device state.

| Device | Behaviour | Dashboard controls |
|---|---|---|
| Smart light | on/off | On, Off |
| Motion sensor | motion, then clear after 5–60 s | Trigger motion, clear-after time |
| Temperature sensor | reading moves towards the set room conditions (0.2 °C/s); telemetry every 10 s | Room temperature and humidity |
| Door sensor | open/closed, with the time of the last change; events | Open, Close |
| Smart lock | locked/unlocked; simulated keypad attempts with a failed-attempt count. No real authentication | Lock, Unlock, Correct code, Wrong code |
| Camera | monitoring on/off; motion events while monitoring. No video | Start or pause monitoring, Simulate motion |
| Smart plug | on/off; appliance load as simulated W, 0.4 W standby, energy in Wh | On, Off, appliance (60–2000 W) |
| Thermostat | heats or cools at 0.05 °C/s towards the target, idle within ±0.3 °C | Target ± 0.5 °C (10–30) |
| Smoke sensor | simulated level rises while smoke is present; the alarm latches at the threshold until reset | Simulate smoke, Reset, threshold |

**On the floor plan.** The tile's border shows Edge Watch's verdict on the device's traffic. The tile's fill and icon show the device's own state: a light glowing, a door open, a lock unlocked, a thermostat heating or cooling, a camera's monitoring dot, and a plug's watts. A smoke alarm is drawn as an orange safety ring with a separate banner, labelled as a device safety alarm and not an Edge Watch security alert.

**Lifecycle.** The device host follows the saved layout once a second:
- Adding a device starts its client.
- Removing a device stops it and clears its retained topics. Ids are never reused, so a new device cannot inherit a removed one's state or history.
- Clients reconnect every 2 s if the broker goes away.
- Each device's last state is saved to `home/device-state.json` and restored when the hub restarts.

**Running the hub.** Smart Home → Home panel → **Start hub**. This starts the broker, device host, telemetry reader and Wokwi serial bridge on the IDS's port, as a child of the API. `.\scripts\start-wokwi-home.ps1` still starts the same hub on its own.

### Attacks

The Attack Simulator runs against the hub while your devices keep working (verified 2026-11-09: Wokwi plus 9 software devices stayed online and normal; a light switched mid-attack was confirmed; Message flooding was alerted after 8.7 s, with the only alert on the attacker). It offers Message flooding, Repeated login attempts, Malformed messages, Suspicious connection activity, Low-rate connection hold, Topic exploration and Listening to every device (the last two are marked "Not trained").
- **Target:** MQTT devices all talk through one hub, so the attacks aim at the hub, and the page says so. The traffic always comes from a separate simulated attacker, never from your devices.
- **During the run:** the progress steps (normal activity → attack begins → suspicious traffic → alert raised, or a missed attack) light up only from real events. The results show time to detect.
- **Failed runs:** a run that ends with an error is shown as failed, with its log folder; a run you stop is shown as stopped by you.

### Simulation and real hardware

The UI (Smart Home → "Simulation and real hardware") and this guide use the same wording:

> This project is simulation-based, but the same MQTT communication flow, smart-device behaviour, monitoring pipeline and attack-detection logic could be applied to a hardware-based IoT deployment. The simulation reproduces the operational behaviour without requiring physical hardware. It has not been validated on physical devices, and it does not model radio, power or hardware timing.

This is a claim about conceptual equivalence of the deployment, not a measured equivalence. No hardware result exists.

### Verified (2026-11-09, live stack, headless Chrome with trusted mouse and keyboard input)

- **Builder, 13/13 checks:**
  - adding devices: palette drop into a room, a second room, a refused drop outside the house, and the + button
  - moving and editing: dragging to the kitchen, arrow-key move, renaming
  - removing: the Remove button and the Delete key, after which the onboarding returns
  - the sample home, the layout surviving a reload, and no runtime errors
- **Live run:**
  - Run the home started 6 software devices, each linked to its own source and classified normal, with the Wokwi ESP32 live alongside (22.5 °C · 45 %). Stop worked.
  - Message flooding from the Attack Simulator was alerted after 8.2 s (1/1 matched, 0 missed). The attacker was drawn in its alert state, and all 9 home devices stayed normal.
- **Bug found by this run and fixed:** attach mode plus a device mix crashed every run (IndexError in device labelling). It now has a regression test.
- **No horizontal overflow** on Smart Home, Attack Simulator, Alerts or Diagnostics at 390, 768 and 1366 px.
