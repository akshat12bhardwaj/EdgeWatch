# Dashboard Specification

> **Status (2026-11-09):** describes the original console. The shipped dashboard has three sections (Smart Home, Attack Simulator, Alerts); the research, comparison and diagnostics panels described here were removed. See [INSTALL_AND_OPERATE.md §8](../implementation/INSTALL_AND_OPERATE.md).

**Data contract:** [DATA_FLOW.md §3](../architecture/DATA_FLOW.md#3-event-contract). **Visual language:** [VISUAL_CONCEPT.md](VISUAL_CONCEPT.md). **Justification per panel:** [VISUALIZATION_RESEARCH_MAPPING.md](VISUALIZATION_RESEARCH_MAPPING.md).

## Global behaviour

| Aspect | Specification |
|---|---|
| Transport | WebSocket `/ws/events` (push) + REST `/api/results`, `/api/runs/<id>` |
| Update cadence | Render ≤ 10 Hz; events are buffered between frames |
| Provenance | Read from each event; the most recent event's provenance drives the P1 badge. Mixed provenance in one view is an **error state** |
| Stream delay | `now − event.ts`, shown in P1. Turns amber if > 2 s and red if > 10 s |
| Disconnection | Overlay "Stream disconnected – last event hh:mm:ss"; panels freeze, grey out, and keep their last values |
| Keyboard | `R` toggles the research view; `Esc` closes the drawer; arrow keys move between alerts |
| Screen sizes | 1920×1080 (primary), 1440×900, 1280×720 (projector). Below 1280 px wide, panels stack vertically |

## Panels

### P1 Status bar
- **Purpose:** identity and honesty of what is shown.
- **Displays:** run id; scenario name; model id and its training split (e.g., `rf-v3 · trained S-time · MQTTset`); **provenance badge** (`LIVE` cyan / `REPLAY` magenta / `SYNTHETIC` grey, ≥ 28 px); gateway clock; stream delay.
- **Source:** the latest event envelope; `run_marker`.
- **Empty state:** "No run active", with the gateway status taken from `/api/health`.
- **Error state:** if provenance is mixed or missing, a red bar reading "Provenance unknown – do not present".
- **Interactions:** clicking the model id opens the model card.

### P2 Topology
- **Purpose:** what is connected, and where activity and suspicion are.
- **Displays:**
  - Nodes: devices, broker, gateway IDS, and `attack_sim`, which is shown only when the traffic source says so.
  - Edges: client→broker links, with thickness and particle density from `msgs_per_s`.
  - Node state shape and colour from the latest window prediction.
- **Source:** `topology` events (every 1 s) plus `window` predictions.
- **Update:** layout fixed after the first 10 s (no jitter). New nodes fade in.
- **Empty state:** the broker and gateway nodes only, with "Waiting for clients".
- **Error state:** a node with no events for 3 windows is drawn hollow and marked "silent". This is not shown as an attack.
- **Interactions:** hover shows the source key, msgs/s, and the last prediction with its score. Click filters P3 and P5 to that source.

### P3 Traffic timeline
- **Purpose:** what is happening over time, aligned with the ground-truth schedule.
- **Displays:** total MQTT msgs/s (line), packets/s (thin line), per-family **scheduled attack bands** (amber shading from `run_marker`), and alert markers (◆).
- **Source:** `resource.mqtt_msgs_per_s`, `run_marker`, `alert`.
- **Window:** last 5 min, with a scroll-back of 30 min.
- **Empty state:** axis with "no traffic yet".
- **Interaction:** brushing a range filters P5.
- **Rule:** the scheduled band is labelled "scheduled attack (ground truth from runner)". The audience can then see detections against truth.

### P4 Pipeline strip
- **Purpose:** show *how efficiently* the gateway runs (RQ2) as events move through the pipeline.
- **Displays:** four stages (Packets → Features → Inference → Alert), each with rolling p50/p95 latency in ms over the last 60 windows, and the throughput in windows/s. A thin bar shows the share of processing time per stage, which is the visual form of H2.
- **Source:** `window.stage_latency_ms`.
- **Empty state:** stages greyed with "—".
- **Error state:** if capture drops increase, the Packets stage shows "drops: N" in amber.
- **Interaction:** click opens a histogram of the last 1,000 windows.

### P5 Detection feed
- **Purpose:** what the gateway detects.
- **Displays:** one row per source with its current prediction, score, and windows-in-a-row; the alert queue above it, sorted by severity then time. Each alert shows its class, severity, start time, duration, and **status chip** (`unverified prediction` / `matches scheduled attack` / `no scheduled attack`).
- **Source:** `window`, `alert`.
- **Empty state:** "No alerts in this run". This state is shown proudly during the benign phase, because it is the FPR story.
- **Interaction:** click an alert to open P6.
- **Wording rules:** the column heading is "Score" unless calibration has passed (see MODEL_EVALUATION §3). Never use "confirmed".

### P6 Investigation drawer
- **Purpose:** why an alert was raised (RQ4) and what supports it.
- **Displays:** an evidence table with the top-5 features, their values, the benign median, and the contribution; sparklines of those features over the last 12 windows; raw counts (CONNECT, refused CONNACK, PUBLISH); ground-truth status; model id; and the time-to-detect when it matches a scheduled attack.
- **Source:** the `alert.evidence` and `window` history for the source.
- **Footer text:** "Evidence shows what the model weighted; it is not proof of malicious intent."
- **Empty state:** n/a (opened only from an alert).

### P7 Edge resources
- **Purpose:** the cost of running the IDS on the gateway (RQ2).
- **Displays:** IDS CPU % and broker CPU % (two numbers + sparkline), IDS RSS MB, SoC temperature and throttle flag, capture drops, and pkts/s and msgs/s.
- **Source:** `resource` events (1 Hz).
- **Error state:** a throttle flag set shows the amber note "thermal throttling – latency figures affected".

### P8 Research view (tab)
- **Purpose:** measured results that answer RQ1–RQ3.
- **Displays:**
  - E1: grouped bars of macro-F1 by split for each model, with CIs.
  - E2: cross-dataset heatmap (train × test).
  - Confusion matrix of the deployed model under S-time.
  - E3/E4: stage-latency stacked bars, plus CPU/RSS vs. load.
  - E5: false alerts per hour per benign scenario.
  - E6: Pareto plot.
- **Source:** `/api/results` reading `results/*/metrics.json`.
- **Rule:** every chart shows its experiment ID, run date, and device. A chart with no result file shows "Experiment not yet run". It never shows placeholder bars.

## Non-functional requirements

- Handles ≥ 50 sources and ≥ 20 window events/s without dropping frames on the presentation laptop.
- No external network calls at runtime: fonts and libraries are bundled, because the lab has no internet.
- All text is in English. Units are always shown (ms, %, MB, msgs/s).
