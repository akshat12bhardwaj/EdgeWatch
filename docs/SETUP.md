# Windows setup

Run from the repository root in PowerShell. Runtime data belongs outside the
checkout and OneDrive, normally `$HOME/edgewatch-data`. Set `EDGEWATCH_DATA`
consistently in every terminal if using another location. Preserve existing services.

## Prerequisites

- Python 3.11+; this machine uses Python 3.13.
- Node.js/npm compatible with the lockfile's package engines; this machine uses
  Node 26. `npm ci` reports engine incompatibilities.
- Mosquitto and `mosquitto_passwd` on `PATH`. The existing fallback searches
  `$HOME/edgewatch-data/tools/mosquitto/Library/{sbin,bin}`.
- Wireshark dumpcap and Npcap with loopback capture support. The IDS checks
  `DUMPCAP_PATH`, then `PATH`, then `C:\Program Files\Wireshark\dumpcap.exe`.
  Offline tools also use tshark.
- Optional: VS Code, Wokwi extension with activated license, and PlatformIO.
  Serial integration requires no paid IoT gateway.

Use normal installers for prerequisites. No WSL, physical hardware or cloud is required.

## Python and dashboard

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[offline,dev,wokwi]" -c constraints-model.txt
.venv\Scripts\python.exe -m pip check
Push-Location dashboard/web
npm ci
npm run build
Pop-Location
```

The API serves the built dashboard; no separate Vite server is needed. Preserve
the npm lockfile and model constraints. Arbitrary scikit-learn upgrades can
disable inference for the frozen bundle.

## Required model

Obtain the existing trusted `ew-dt12-lab-v6` directory from the project owner and
place the complete unchanged bundle at `$HOME/edgewatch-data/models/ew-dt12-lab-v6`
or `<EDGEWATCH_DATA>/models/ew-dt12-lab-v6`. No public download or replacement
training procedure is provided. Model deserialization executes code: use trusted
bundles only. Without it, unit tests remain available but coordinated startup
refuses the complete IDS demo. Do not modify frozen models or constraints.

## Broker and startup

```powershell
.\scripts\start-smart-home.ps1
.venv\Scripts\python.exe -m lab.startup status
```

Open [Smart Home](http://127.0.0.1:8020/#/home). Defaults: API `8020`, MQTT `18840`.
Startup checks the model, starts capture, generates broker credentials/ACL/config,
and starts missing services with shared store/schedule settings. No attack begins
automatically. Compatible existing services are reused; incompatible/busy ports
cause an error without replacing their owner. `-ApiPort` and `-MqttPort` select
other ports on a fresh stack.

`lab.home` generates `home/mosquitto.conf`, password files and `credentials.json`
under the data directory: loopback-only IPv4/IPv6, no anonymous access. The lab
account cannot publish protected device telemetry. Do not copy the historical
`deploy/mosquitto-edgewatch.conf`, which listens beyond loopback. Never start a
second broker on the same port or publish runtime credentials.

## Wokwi and PlatformIO (optional)

Build the four projects with the installed PlatformIO executable:

```powershell
foreach ($role in @('environment', 'access', 'lighting', 'safety')) {
    & "$HOME/.platformio/penv/Scripts/pio.exe" run -d "simulators/wokwi-$role" -e esp32dev
    if ($LASTEXITCODE -ne 0) { throw "Firmware build failed for $role" }
}
```

Open each folder in its own VS Code window, run **Wokwi: Start Simulator**, and
keep every simulator tab visible. Hidden/paused tabs may stop reporting. Each
`wokwi.toml` uses `.pio/build/esp32dev/firmware.bin` and `.elf`. Access, environment,
lighting and safety use RFC2217 ports `4001`, `4002`, `4003`, `4004`, matching
`simulators/controllers.example.json`.

Coordinated startup already starts the bridges. For separate foreground operation
against an existing hub:

```powershell
.\scripts\start-wokwi-controllers.ps1
# Or compile all four before attaching:
# .\scripts\start-wokwi-controllers.ps1 -Build
```

Avoid duplicate runners. Ctrl+C stops this wrapper's bridges only. Select each
device's named controller in the inspector; one firmware channel backs one device.
Devices become online only after genuine firmware reports. Firmware prints serial
messages; Python publishes MQTT on its behalf.

The original `simulators/wokwi-smart-home` uses port `4000`; build it with the
same command using that folder. Serial `esp32dev` needs no WiFi credentials.
The optional `esp32dev-wifi`/paid gateway path is unverified and unnecessary.
Home initialization generates ignored `include/secrets.h`; the tracked
`include/secrets.example.h` is a placeholder template.

## Shutdown

**Stop hub** stops home devices/broker while API/IDS may continue. After your demo:

```powershell
.venv\Scripts\python.exe -m lab.startup stop
```

This stops only recorded processes whose identities still match; adopted services
remain alone. Stop Wokwi using its toolbar. Do not use older stop/E2E helpers
against another user's stack. Restarting an API can end its dashboard-started hub.

## Checks

Use [README verification commands](../README.md#verification). Integration tests
need broker/capture tools and isolated ports. Start no new research campaigns.
See [Troubleshooting](TROUBLESHOOTING.md).
