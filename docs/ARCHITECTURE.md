# Architecture

Edge Watch is a passive, software-only demo on one Windows computer. Services
stay local. The frontend has Smart Home, Attack Simulator and Alerts pages.

```text
Software devices (one MQTT client/address per device) ----+
Wokwi ESP32s -> RFC2217 serial -> controller bridges -----+-> local Mosquitto
Bounded attack clients (separate loopback addresses) -----+        |
                                                                | capture
                                                 Npcap/dumpcap -> IDS
                                                                |
                                                         SQLite event store
                                                                |
Telemetry observer -> local home snapshots -> FastAPI <----------+
                                                |
                                          WebSocket / HTTP
                                                |
                                       React + Three.js dashboard
```

## Virtual devices and transport

`lab.devices.DeviceHost` reconciles saved layouts and runs independent MQTT
clients (`ew-<id>`, stable `127.0.4.x` addresses) for all nine software types.
It persists simulated state and publishes state/status/events under
`edgewatch/devices/<id>/`. Commands carry an ID; completion requires that ID in
the device's acknowledgement.

Four Arduino/PlatformIO projects run in Wokwi: environment (climate/thermostat),
access (motion/door/lock), lighting (light/plug), safety (smoke/camera status).
`lab.controllers` translates genuine virtual-firmware serial messages into MQTT
through independent RFC2217 sessions. The ESP32 does not speak MQTT directly in
this path. Controller sources are `127.0.3.11` through `127.0.3.14`; the independent
observer uses `127.0.3.4`. Sensors on one controller share its packet-level source.
The legacy board uses port `4000` through the home bridge.

Serial and MQTT reconnection are separate. Stale firmware reports mark affected
devices offline; independent software devices continue. Bridges do not invent readings.

## Broker and IDS

`lab.home` creates authenticated loopback-only Mosquitto configuration and ACLs.
Lab accounts cannot publish protected device telemetry. Attack clients use
separate loopback sources, a 600-second maximum and `lab/safety.py` rate caps.
The simulator attaches to the home broker when available.

`ids.service` captures the MQTT port using dumpcap/Npcap, decodes packets,
aggregates five-second per-source feature windows and loads the frozen
`ew-dt12-lab-v6` model. Features, thresholds and detection behavior are unchanged.
It observes and alerts; it does not prevent traffic or guarantee detection.

## Persistence and API

The IDS writes windows, alerts, resource samples, topology and markers into a
SQLite WAL store, normally `run/events.sqlite` under the external data folder.
Capture and monitor threads serialize use of their shared connection; a failed
monitor tick is logged without ending monitoring.

FastAPI reads the store, streams WebSocket updates, serves the built frontend,
validates local controls and manages bounded simulation processes. Device
readings come from MQTT-observed home snapshots independently of the IDS.
Layouts, device state and controller snapshots live under `home/`. All-history
alert clearing deletes alerts and alert events transactionally, preserving other
telemetry and device data.

## Dashboard and startup

React/TypeScript with Three.js/React Three Fiber renders the house lazily.
The device list and inspector provide keyboard and graphics-failure alternatives.
Network activity is a ten-second mean of measured IDS samples; stale/paused/
disconnected states remain visible. Device totals use saved layouts and fresh
reports rather than equating network sources with devices.

`lab.startup` shares data/store/schedule settings and starts missing components,
preserving compatible existing services. Defaults: API `8020`, MQTT `18840`.
See [Setup](SETUP.md) and [User guide](USER_GUIDE.md).
