# Troubleshooting

From the repository root, use
`.venv\Scripts\python.exe -m lab.startup status`. Inspect the current launch's
`run/home-*/{ids,home,api,controllers}.{out,err}.log` and `home/serve.out.log` /
`home/mosquitto.log` under the external data directory. Do not post credentials
or whole runtime files publicly. Preserve another user's running services.

## MQTT broker not running

Check that Mosquitto and `mosquitto_passwd` are discoverable as described in
[Setup](SETUP.md#prerequisites). Read the broker log for password-file, config or
busy-port errors. Use one broker per port; do not replace someone else's listener.
Home configuration is generated locally. The `deploy/` examples are not this demo's config.

## Missing detection model

Check the complete trusted bundle at `$HOME/edgewatch-data/models/ew-dt12-lab-v6`
(or under `EDGEWATCH_DATA`). Reinstall dependencies using `-c constraints-model.txt`
and inspect the IDS error for version mismatch. No public download is supplied:
obtain the existing bundle from the owner. Do not retrain or modify frozen artifacts.

## Wokwi controller not reporting

Build its `esp32dev` environment, start **Wokwi: Start Simulator** in that project
window and keep the simulator tab visible. Check that serial output advances,
the hub runs and the RFC2217 port matches `controllers.example.json`. The inspector
shows firmware-reporting state; a running bridge does not imply online firmware.
Allow reconnect backoff up to 30 seconds; resume paused simulators in VS Code.

## Serial port collisions

Access, environment, lighting and safety use `4001`, `4002`, `4003`, `4004`;
the legacy board uses `4000`. Avoid duplicate simulators and bridge runners.
Inspect existing listeners first. If intentionally changing a local port, update
both `wokwi.toml` and your matching controller configuration. Do not stop another
user's listener.

## Device offline or command pending

Check hub status and device backing. Software devices need the hub; Wokwi devices
also need fresh firmware reports from their mapped controller. One firmware
channel backs one device. A command needs its own acknowledgement; submission is
not completion. Do not conceal a failed connection by changing backing. An API
restart may end its child hub: inspect status before starting your hub again.

## Network activity unavailable

Check the API connection, monitoring pause state, dumpcap/Npcap loopback support
and whether the IDS captures the broker's MQTT port. Inspect capture/monitor logs.
Missing samples are not measured zero traffic. A clone without an active IDS has
no live measurements.

## Attack simulation unavailable

Use coordinated startup so API and IDS share `EDGEWATCH_MQTT_PORT`,
`EDGEWATCH_SCHEDULE` and data/store settings. An incompatible existing service is
left untouched. Finish or stop your active run before another. Controls require
local requests, an accepted host and the token if configured. Do not bypass these
checks or expose the API. No alert may simply mean a missed detection.

## Dashboard missing or graphics unavailable

Run `npm ci` and `npm run build` in `dashboard/web`; the API serves `dist/`.
Check Node engine compatibility if installation fails. For WebGL failure, use
the device list and inspector. The existing scene-size build advisory and
Starlette/httpx deprecation warning are warnings, not test failures.
