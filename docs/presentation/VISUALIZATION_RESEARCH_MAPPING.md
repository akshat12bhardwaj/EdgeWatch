# Visualization ↔ Research Mapping

Each major UI element must trace to a literature finding, a research requirement, or a demonstration requirement. If an element cannot be traced, it is removed.

| Literature finding or research requirement | System capability | UI element | Data source | Validation method |
|---|---|---|---|---|
| Model-only latency is what is usually reported (P19: 0.0725 ms/flow; P27: 0.19 ms); feature extraction cost is under-reported (P19's offline extraction times) → RQ2, H2 | Per-stage timing inside the gateway process | **P4 Pipeline strip** (per-stage p50/p95 + share bar) | `window.stage_latency_ms` | Compare with E3 offline analysis of `stage_latency.csv`; must agree within 5% over the same run |
| Gateway-class devices are the deployment target (P24 RPi 3; P27 RPi 4) → RQ2 | psutil CPU/RSS, temperature, throttle flag | **P7 Edge resources** | `resource` events | Cross-check against `top`/`vcgencmd` during a pilot run |
| Floods can overload the observer itself → THREAT_MODEL §5 | tshark drop counters | P4 "drops" badge; P7 drops | `capture_stats`, `resource.capture_drops_total` | Stress pilot (E3 highest rate) must show non-zero drops when tshark reports them |
| False positives dominate operational cost (P29); benign diversity is untested in MQTT work → RQ3 | Benign-only phases with scheduled ground truth | **P5 empty state** during the benign phase; P3 timeline with no ◆ markers; P8 E5 chart | `alert`, `run_marker`, E5 results | Number of alerts shown = number in `events.jsonl` for that interval |
| Prediction ≠ ground truth (P30; project rule) | `ground_truth` from the runner schedule; alert status chips | **P5 status chip**; P3 scheduled bands | `run_marker`, `alert.status` | Unit test: an alert outside a scheduled band must render `no scheduled attack` |
| Random-split scores may overstate quality (P30, P33) → RQ1, H1 | Offline experiments E1/E2 | **P8 split-comparison bars, cross-dataset heatmap** | `results/E1*/metrics.json`, `results/E2*/metrics.json` | Values rendered = values in JSON (snapshot test) |
| Quality–cost trade-off (P25, P26) → E6 | Combined offline + edge results | **P8 Pareto plot**; P1 model id shows the chosen model | E1 + E3/E4 results | Deployed model must lie on the plotted front |
| MQTT attacks target the broker; flow-level behaviour matters (P08, P09) → THREAT_MODEL | Topology from observed sources; per-source windows | **P2 Topology** (client→broker edges, per-source state) | `topology`, `window` | Node count = distinct `source_key` in the last 60 s |
| Topic-level and message-type activity distinguishes MQTT attacks (P09 flow features; F09–F24) | Per-window MQTT counters | P6 raw counts; P2 edge rate | `window.features` | Hand-crafted PCAP test (FEATURE_SPECIFICATION §6) |
| Operators need evidence for alerts (P34 X-IDS; P17 and P19 already offer explanation) → RQ4 | Decision-path feature contributions | **P6 Investigation drawer** | `alert.evidence` | Contributions sum to (score − base value) within 1e-6 for trees |
| "Confidence" requires calibration | Reliability diagram (MODEL_EVALUATION §3) | Column label "Score" vs. "Confidence" in P5 | Model card `calibration_ece` | UI reads the label from the model card |
| Demonstration must be repeatable and honest (project requirement) | Replay service with server-set provenance | **P1 provenance badge**; magenta border in REPLAY | `provenance` | Test: the replay service cannot emit `live`; the UI has no toggle |
| Monitoring and investigation are distinct tasks (P35 taxonomy) | Separate main view and drawer | Main view vs. P6 | — | Usability walk-through with 2 non-team viewers (Phase 05) |

**Elements considered and rejected:**
- A threat-level gauge: there is no defined metric.
- A geographic attack map: the lab has no geography.
- A packet-payload viewer: it would breach the privacy rule in FEATURE_SPECIFICATION §4.
- A "Blocked attacks" counter: there is no mitigation (ADR-02).
