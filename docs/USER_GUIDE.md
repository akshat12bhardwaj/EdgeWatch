# Using Edge Watch

Follow [Setup](SETUP.md), then open [the dashboard](http://127.0.0.1:8020).
Navigation has Smart Home, Attack Simulator and Alerts. No attack starts automatically.

## Build and control a home

1. Open **Smart Home**. Use **Start hub** in the right panel if stopped.
2. Start with a sample home or add devices from the palette. Drag into a room,
   or use Add buttons and the inspector. Layouts support up to 24 devices.
3. Select a device to edit its name, room, position and backing. Orbit/pan/zoom
   the 3D camera or focus a room. The device list and inspector also work without
   dragging. Keyboard access and reduced-motion preferences are supported.
4. New devices use software backing. To use Wokwi, start the appropriate visible
   simulator and choose its named controller. Each firmware channel backs only
   one device. Existing layouts are never replaced automatically at startup.
5. Use device controls. Commands stay pending until the device acknowledges
   them. Read-only Wokwi sensors use their simulator's controls.

The nine types are light, motion, climate, door, lock, camera, plug, thermostat
and smoke. Controls vary by type: on/off, open/close, lock/unlock, target
settings and simulated motion/smoke events. Camera status has no video, plug
consumption is modeled, thermostat dynamics are simulated, and smoke input is
virtual. Smoke safety alarms are independent of security alerts.

Changes save automatically. Online counts refer to saved devices with fresh
reports; controller-backed devices also need a fresh controller. Removal stops
the software client and clears its retained topics. **Stop hub** interrupts home
MQTT reporting; **Start hub** resumes the saved arrangement. API/IDS can keep
running. See [shutdown](SETUP.md#shutdown) for stopping your launcher's stack.

## Read network activity

The global status and Network communication panel use the same measured MQTT
rate, averaged over ten seconds. The panel shows a two-minute sparkline, active
sources and new device, acknowledgement, connectivity and IDS activity. It does
not replay device history or display payloads. One source can represent several
Wokwi sensors; unknown sources remain unidentified.

**No recent traffic** differs from **Monitoring paused**, **Disconnected** and
**Data unavailable**. Missing measurements are not shown as zero traffic.

## Run an attack simulation

Open **Attack Simulator**, choose **Start Attack** and configure a scenario,
duration and rate. Controls enforce loopback, rate caps and at most 600 seconds.
Some choices are marked **Not trained**; detection is not promised. Use
**Stop Attack** to end your current run early.

The flow follows Ready, Attacking, Analyzing and the actual outcome: detected,
not detected, stopped or failed. Analysis allows ten seconds after traffic ends
for IDS events to arrive. The result popup links to alerts actually associated
with that run. A missed simulation creates no fabricated alert.

## Inspect and clear alerts

Filter **Alerts** by time, severity or source. Select an event to inspect traffic
evidence. Severity and model output are demo indications, not proof of compromise.

**Clear Alert History** requires accepting a warning and submitting the dialog.
It permanently deletes every stored security alert across all sessions, including
the current session. Monitoring continues and new alerts can arrive. Other
telemetry, devices, layouts and models remain intact. Cancel preserves history.

See [Troubleshooting](TROUBLESHOOTING.md) for unavailable controls or stale devices.
