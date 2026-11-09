# Edge Watch: Windows Quick Start

Every command here was run on Windows 11 with Python 3.13.7, Node 26.8.1, Wireshark 4.6.9, Npcap 1.88 and Mosquitto 2.0.15. Paste them into **Windows PowerShell**. Paths use `$HOME`, which here is `C:\Users\aksha_q43exq6`.

**Dashboard:** http://127.0.0.1:8000/

**How it fits together:** the lab runner starts its own Mosquitto broker and clients, so you never start a broker yourself. The API serves the dashboard, so there is no separate frontend process. The IDS watches packets on the MQTT port and never connects to the broker. Start order: API, then IDS, then lab.

## A. First-time setup

Run once. Safe to repeat.

```powershell
cd "$HOME\OneDrive\Documents\IOT project"
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[offline,dev]" -c constraints-model.txt
python -m pip check

cd dashboard\web
npm ci
npm run build
cd ..\..
```

**Keep `-c constraints-model.txt`.** The models were saved with scikit-learn 1.8.0, and the IDS refuses a model from any other version. Without it, pip installs a newer one and the IDS runs with inference off.

## B. Every later start

### Easiest: one command

```powershell
cd "$HOME\OneDrive\Documents\IOT project"
powershell -ExecutionPolicy Bypass -File .\scripts\start-edgewatch.ps1
```

Then open http://127.0.0.1:8000/. This is the demo: about 6 minutes of benign traffic with 5 scheduled attack families. The processes run hidden, so you can close this terminal.

| To run | Command |
|---|---|
| Benign traffic only, 30 minutes | `powershell -ExecutionPolicy Bypass -File .\scripts\start-edgewatch.ps1 -Mode benign -Seconds 1800` |
| Dashboard and IDS, no traffic yet: start simulations from the **Simulate** tab, or read earlier runs | `powershell -ExecutionPolicy Bypass -File .\scripts\start-edgewatch.ps1 -Mode dashboard` |
| Stop everything | `powershell -ExecutionPolicy Bypass -File .\scripts\stop-edgewatch.ps1` |

The script checks prerequisites, loads the model first, refuses to start twice or on a busy port, and reports failures with the log.

**Dashboard tabs.** *Live*: overview, topology, detection feed, timeline, analytics, pipeline and resources. *Simulate*: pick benign devices, attack families, episodes, duration and a rate fraction, then Start/Stop; the run goes to 127.0.0.1 on the IDS's port only, at most 600 s, and alerts are matched against the runner's schedule. In demo mode the lab already holds the port, so Simulate waits until it ends. *Investigate*: search and filter stored alerts and open one. *Compare*: re-score the windows already recorded in a run with several models and the rule and rate baselines; marked REPLAY COMPARISON. *Research*: result files only.

### Or: three terminals, to watch each part

**Terminal 1: API and dashboard.** Keep open.

```powershell
cd "$HOME\OneDrive\Documents\IOT project"
$env:EDGEWATCH_DB = "$HOME\edgewatch-data\run\events.sqlite"
$env:EDGEWATCH_MODEL = "$HOME\edgewatch-data\models\ew-dt12-lab-v6"
.\.venv\Scripts\python.exe -m dashboard.api
```

**Terminal 2: IDS.** Keep open. Start it before the lab, and leave it a few seconds.

```powershell
cd "$HOME\OneDrive\Documents\IOT project"
.\.venv\Scripts\python.exe -m ids.service --db "$HOME\edgewatch-data\run\events.sqlite" --model "$HOME\edgewatch-data\models\ew-dt12-lab-v6" --port 18840 --schedule "$HOME\edgewatch-data\run\manual\ground_truth.json" --scenario manual
```

**Terminal 3: lab, including broker and clients.** It ends by itself. Benign first, if you want a clean start:

```powershell
cd "$HOME\OneDrive\Documents\IOT project"
.\.venv\Scripts\python.exe -m lab.run --out "$HOME\edgewatch-data\lab\live\$(Get-Date -Format yyyyMMdd-HHmmss)" --port 18840 --plan benign --scenario base --seconds 300 --ground-truth "$HOME\edgewatch-data\run\manual\ground_truth.json"
```

Or the attack demo:

```powershell
cd "$HOME\OneDrive\Documents\IOT project"
.\.venv\Scripts\python.exe -m lab.run --out "$HOME\edgewatch-data\lab\live\$(Get-Date -Format yyyyMMdd-HHmmss)" --port 18840 --plan episodes --episodes 1 --scenario base --ground-truth "$HOME\edgewatch-data\run\manual\ground_truth.json"
```

Run only one lab at a time on a port.

**Browser:** http://127.0.0.1:8000/. `R` opens the research view, `Esc` closes a drawer, and clicking an alert opens its evidence.

## C. Shutdown

**Script start:** `powershell -ExecutionPolicy Bypass -File .\scripts\stop-edgewatch.ps1`. It stops only the processes it started and deletes no run data. The lab is stopped abruptly, so that run has no `manifest.json`. Let a run finish if you want one.

**Terminals:** press **Ctrl+C** in Terminal 3, then 2, then 1. The lab stops its own broker and capture. The order does not matter for safety, because the parts are independent.

**Check that nothing is left:**

```powershell
Get-Process mosquitto,dumpcap -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'ids.service|lab.run|dashboard.api' } | Select-Object ProcessId,CommandLine
```

Stop a leftover by its PID, after checking that it is the one you mean: `Stop-Process -Id 12345`.

## D. Troubleshooting

Run these from the repository folder.

```powershell
# Versions
python --version; node --version; npm --version
.\.venv\Scripts\python.exe --version

# Mosquitto, and capture
& "$HOME\edgewatch-data\tools\mosquitto\Library\sbin\mosquitto.exe" -h | Select-Object -First 1
& "C:\Program Files\Wireshark\tshark.exe" --version | Select-Object -First 1
& "C:\Program Files\Wireshark\dumpcap.exe" -D | Select-String Loopback

# Are the ports in use? No output means free.
Get-NetTCPConnection -LocalPort 18840 -State Listen -ErrorAction SilentlyContinue
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue

# API health
Invoke-RestMethod http://127.0.0.1:8000/api/health | ConvertTo-Json -Depth 3

# Python dependencies, and whether the model loads
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pip list | Select-String "scikit-learn|numpy|joblib|scipy"
.\.venv\Scripts\python.exe -c "from ids.detector import Detector; import pathlib; d = Detector(pathlib.Path.home() / 'edgewatch-data/models/ew-dt12-lab-v6'); print('loaded', d.model_id)"

# Logs from the newest script start. Each part has .out.log and .err.log.
$run = Get-ChildItem "$HOME\edgewatch-data\run" -Directory | Where-Object Name -match '^\d{8}-' | Sort-Object Name | Select-Object -Last 1
Get-ChildItem $run.FullName
Get-Content "$($run.FullName)\ids.err.log" -Tail 20
Get-Content "$($run.FullName)\api.err.log" -Tail 20
Get-Content "$($run.FullName)\lab.err.log" -Tail 20

# Broker log from the newest lab run
$lab = Get-ChildItem "$HOME\edgewatch-data\lab\live" -Directory | Sort-Object LastWriteTime | Select-Object -Last 1
Get-Content "$($lab.FullName)\broker\mosquitto.log" -Tail 20

# Database: integrity, and events per run
.\.venv\Scripts\python.exe -c "import sqlite3,pathlib; c=sqlite3.connect(pathlib.Path.home()/'edgewatch-data/run/events.sqlite'); print(c.execute('pragma integrity_check').fetchone()); print(c.execute('select run_id,event_type,count(*) from events group by 1,2').fetchall()[-10:])"

# Tests
.\.venv\Scripts\python.exe -m pytest tests -m "not integration"
.\.venv\Scripts\python.exe -m pytest tests -m integration
```

**Restart the system:**

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\stop-edgewatch.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\start-edgewatch.ps1
```

| Symptom | What it means | Fix |
|---|---|---|
| `/api/health` says `no_store` | The IDS has never created the store | Start the IDS, using the same `EDGEWATCH_DB` path |
| `disabled`, or the start script says "started no capture" | **The Pause IDS button's setting is saved in the store and survives restarts** | Resume, below |
| `idle` with `ids: stopped` | No IDS is writing | Start the IDS |
| P1 shows "none: inference off" | Model missing or refused | Run the model check above. Reinstall using `constraints-model.txt` |
| Broker "not seen" with `status: ok` | The lab has finished, and its broker with it. **Normal after a demo** | Start another lab |
| No windows, but the lab is running | IDS and lab are on different ports | Use `--port 18840` on both |
| "Edge Watch looks already running" | Earlier processes are alive | Run the stop script |
| Lab client errors | Another broker holds the port | Check port 18840 |
| Dashboard 404 or blank | No build existed when the API started | Build, then restart the API |

**Resume a paused IDS** (API running):

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/control -ContentType application/json -Body '{"action":"enable"}'
```

## E. Operational notes

- **Which terminal stays open:** none with the scripts. With three terminals, all three, though Terminal 3 ends by itself when the lab finishes.
- **Broker:** always managed by the lab runner. It stops when the lab ends, so after a demo the dashboard rightly shows "not seen" and traffic stops. The API and IDS keep running.
- **Model:** loaded automatically from `--model` when the IDS starts. Changing it needs an IDS restart. `EDGEWATCH_MODEL` only tells the API which model card to show. **Keep both on the same model.**
- **Frontend rebuild:** no restart needed after a rebuild; just refresh the page. Restart the API only if `dist` did not exist when it started.
- **Generated data:** all under `$HOME\edgewatch-data`, none in the repository except small `results\` summaries.

| Path | Holds |
|---|---|
| `run\events.sqlite` | Events and alerts from every run. The dashboard shows the newest run |
| `run\<timestamp>\` | Logs and ground truth from one script start |
| `lab\live\<timestamp>\` | One lab run: `capture.pcap` (raw packets), schedule, manifest, broker log and that run's random credentials |
| `models\` | Model bundles |

- **Disk:** each demo adds tens of MB of capture. Nothing is removed automatically except old events past 500,000 in the store. Delete old `lab\live` folders yourself if you need space.
- **Localhost only:** the API and broker bind to `127.0.0.1`. The API refuses other addresses unless `EDGEWATCH_API_TOKEN` is set. Attack scripts refuse non-loopback targets.
- **Safe to repeat:** section A, all of section D, the stop script, `npm run build`, and the start script, which refuses to double-start. Lab commands make a new folder each time.
- **What running it proves:** the software works on this laptop, and the bundled model raises alerts on this project's own simulated attacks. **It does not prove real-world detection,** and no result here is a research result or a Raspberry Pi measurement. See `docs/reports/FINAL_TECHNICAL_REPORT.md`.
