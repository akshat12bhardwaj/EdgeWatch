# Visual Concept: "Edge Watch" Command Center

**Working name:** *Edge Watch*, an MQTT gateway defence console.
**Principle:** the interface is a window onto a **measured** system. Every moving element is driven by an event in the [event contract](../architecture/DATA_FLOW.md#3-event-contract). Nothing animates without data behind it.

## 1. What the audience must understand within 5 seconds

1. **What is connected:** devices → broker → gateway (topology).
2. **What is happening:** message flow and rates (animated links, timeline).
3. **What the gateway detects:** which source is flagged, as what, and why (detection panel, evidence).
4. **How efficiently it operates:** per-stage milliseconds, CPU, and RAM (pipeline strip, resource gauges).
5. **Whether this is live or replayed:** a large provenance badge, always visible.

## 2. Reference patterns (inspiration, not copies)

| Source domain | Pattern borrowed | Where used |
|---|---|---|
| Network observability (service maps) | Node-link graph with edge thickness proportional to rate | Topology |
| SOC consoles | Alert queue with severity, status, and drill-down | Detection panel |
| Mission control / telemetry | Monospaced live numerics; a timeline with scheduled-event bands | Pipeline strip; timeline |
| Digital twins | A spatial model of the environment, state-coloured | Topology (devices grouped by "room/zone" from the simulator config) |
| Security visualisation research (P35 taxonomy) | Separate *monitoring* views from *investigation* views | Main view vs. investigation drawer |

## 3. Design system

### Colour tokens (dark theme first)

| Token | Hex | Use |
|---|---|---|
| `--bg` | `#0A0E16` | Page background |
| `--surface` | `#111827` | Panels |
| `--surface-2` | `#1A2233` | Raised elements, drawer |
| `--line` | `#243047` | Borders, grid |
| `--text` | `#E6EAF2` | Primary text (contrast ≥ 12:1 on `--bg`) |
| `--text-dim` | `#93A0B8` | Labels |
| `--cyan` | `#22D3EE` | Benign flow, live data |
| `--blue` | `#3B82F6` | Gateway, pipeline stages |
| `--violet` | `#A78BFA` | Model and inference elements |
| `--amber` | `#F59E0B` | Suspicious / medium alert, scheduled-attack band |
| `--red` | `#F43F5E` | High-severity alert only (used sparingly) |
| `--replay` | `#E879F9` | REPLAY badge and border tint |

**Accessibility rules:**
- State is never conveyed by colour alone. Every state also has a shape or icon: benign ●, suspicious ▲, alert ◆, offline ○.
- Text contrast ≥ 4.5:1.
- Motion respects `prefers-reduced-motion`; flow particles are replaced by thickness changes.
- Optional light theme for projectors with weak contrast. Tokens are redefined for it, never hard-coded.

### Typography

- **Inter** for UI text.
- **JetBrains Mono** for all numbers, ids, and timings. Tabular figures prevent numbers from jittering as they update.
- Scale: 12 / 14 / 16 / 20 / 28 / 40 px. The provenance badge and the headline latency use 28–40 px, so they are readable from the back of a room.

### Motion (each element is tied to an event)

| Motion | Trigger | Duration |
|---|---|---|
| Particles along topology edges | `topology.edges[].msgs_per_s`; particle density ∝ log(rate) | Continuous; capped at 60 fps |
| Node pulse (amber) | A `window` event with an attack prediction for that source | 600 ms |
| Alert ripple from node to gateway | New `alert` event | 800 ms, once |
| Pipeline stage flash | A window passes through the stage; the number updates | 150 ms |
| No idle "radar sweeps" or decorative scanning lines | — | — |

## 4. Layout (1920×1080; scales down to 1440×900)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ EDGE WATCH   run 2026-11-xx-A   model rf-v3 (S-time)   ● LIVE   delay 0.4 s │  P1 status bar
├───────────────────────────────────────────────┬──────────────────────────────┤
│                                               │ DETECTION                     │
│        TOPOLOGY (P2)                          │ ▲ dev-07  bruteforce  0.93   │  P5 detection feed
│   [zone A]  ●dev-01 ●dev-02                   │   2 windows · unverified     │
│        \      |                               │ ● dev-02  benign      0.02   │
│         \     |          ◆ attack_sim         │ ...                          │
│      ═══[ BROKER ]═══[ GATEWAY IDS ]          │──────────────────────────────│
│         /     |                               │ EDGE RESOURCES (P7)          │
│   ●dev-05 ●dev-06   [zone B]                  │ CPU 23%  RSS 142 MB  52 °C   │
│                                               │ drops 0   msgs/s 214         │
├───────────────────────────────────────────────┴──────────────────────────────┤
│ PIPELINE (P4)  packets ▸ features ▸ inference ▸ alert   p95: 1.8 | 0.9 | 0.1 | 0.2 ms │
├──────────────────────────────────────────────────────────────────────────────┤
│ TIMELINE (P3)  msgs/s ▁▂▂▃▂▂▂▂▂▇█▇▆▂▂   [ scheduled attack: bruteforce ]  ◆ alert │
└──────────────────────────────────────────────────────────────────────────────┘
```

All numbers in this sketch are **placeholders for layout only**. They are not results.

- **Investigation drawer (P6):** slides in from the right when an alert is clicked. It shows the evidence table, the feature sparkline over the last 12 windows, and the ground-truth status.
- **Research view (P8):** a separate tab with measured results from `results/`. Each chart is captioned with its experiment ID and run date.

## 5. Visual prototype proposal

- **Step 1 (Phase 05, week 1):** a static HTML prototype fed by a hand-written **synthetic** event file. The page displays a permanent `SYNTHETIC` badge. Its purpose is to agree on the layout with the team.
- **Step 2:** connect it to the replay service, using real lab-run events, with `REPLAY` shown.
- **Step 3:** connect it to the live gateway, with `LIVE` shown.

The provenance badge is driven by the server-side `provenance` field at every step. It cannot be toggled in the UI.

## 6. Anti-patterns we commit to avoiding

- Fake "threat level" meters with no defined metric.
- World maps, global attack arcs, or IP geolocation. The lab has no geography.
- Random numbers used to make panels look busy. An empty panel shows its empty state instead.
- The words "confirmed", "blocked", or "neutralised". We detect; we do not block.
- Saturated neon on large areas. Accents are kept to under ~10% of the screen area.
