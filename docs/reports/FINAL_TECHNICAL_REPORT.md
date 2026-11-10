# Edge Watch: Final Technical Report

> Historical technical reference. Current operation is documented in ../README.md; old UI, deployment and research plans are not current instructions.

**Date:** 2026-11-02. **Prepared by:** Claude Code (AI assistant). **Status:** the software works end to end on a development laptop. It has never run on a Raspberry Pi or a physical network, and no result here answers RQ1-RQ3.

**Evidence levels used below:**

| Level | Meaning |
|---|---|
| **Unit** | Automated test on invented input |
| **Capture** | Compared on the real MQTTset captures |
| **Live-L** | Real Mosquitto, real capture, real IDS process, on Windows loopback |
| **Not run** | Written, but never executed |

## 1. What exists

Clients → Mosquitto → dumpcap → decoder → FeatureAggregator → model → alerts → SQLite → FastAPI and WebSocket → React dashboard. Passive, with no blocking code. Details: [FINAL_SYSTEM_ARCHITECTURE.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/architecture/FINAL_SYSTEM_ARCHITECTURE.md). To run it: [INSTALL_AND_OPERATE.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/implementation/INSTALL_AND_OPERATE.md).

**Tests (2026-11-09):** 367 Python unit tests and 18 frontend tests pass; integration tests passed at session start (2).

## 2. Verified and not verified

| Claim | Level | Evidence |
|---|---|---|
| Broker keeps serving through IDS pause, hard kill, and restart | Live-L | `tests/test_integration_live.py` |
| Missing, refused, or failing model does not stop monitoring | Live-L, Unit | same; `tests/test_service.py` |
| API restart tolerated; page reconnects with no reload | Live-L, real browser | `results/ENG-E2E/` |
| Alert reaches the dashboard; drawer shows evidence | Live-L, real browser | `results/ENG-E2E/` |
| No lab password, username, topic, client ID, or address in the store | Live-L | `results/ENG-E2E/` |
| No MQTTset strings of 12+ characters or addresses in repo files or results | Capture | `scripts/final_checks.py`: 0 of 1,349 |
| Raw capture hashes unchanged | Capture | all 6 match earlier evidence |
| Decoder equals tshark on real captures | Capture | 12,081,179 events, 0 differences, after this work's decoder changes |
| IPv6 extension headers, IP fragments, MQTT 5 framing | Unit, and tshark on invented captures | **No real traffic contains them** |
| TCP retransmission, reordering | Unit | **No real capture has any in its data** |
| Systemd units, Linux capture, `setcap`, `MemoryMax` restart | **Not run** | `deploy/` |
| Any Raspberry Pi figure | **Not run** | |
| Physical network, Wi-Fi, NAT | **Not run** | |
| Windows job-object cleanup, on Linux | Not applicable | Linux relies on SIGPIPE or the cgroup; **not run** |

## 3. Packet processing

**Changed in `decoder.py`:** IPv6 extension headers; bounded IP reassembly that drops overlaps; per-connection MQTT 5 state for SUBSCRIBE properties and AUTH; and a bad fixed header no longer discards valid messages after it, which closes the evasion risk from T3.3. **Lockstep with tshark afterwards: 0 differences on all 6 captures.** F01-F26 and `fx-0.1` are unchanged.

**Known differences from tshark, remaining on invented traffic only:** see `reports/t3_7/edge_controls.json`. Where a fragment arrives, the decoder's `tcp_len` is correct and tshark's adapter reports 0.

**Live bug found and fixed:** the live timer dropped packets still in dumpcap's pipe, so live features undercounted against offline: 43% of CONNECTs under churn. A 1 s lag fixed it, at the cost of 1 s of alert delay. **Any live figure from before this fix is invalid, and none is reported here.**

## 4. Detection: how the model was reached

Six models were trained, each exposing a defect the previous test could not show. **The perfect-looking result appeared long before the detector was usable. A held-out score from the same generator is not evidence of quality.**

| Model | Held-out episodes | Then exposed |
|---|---|---|
| v1 | 30/30, 0 false alerts | Missed brute force at half its scripted rate; low-rate run 6/15 |
| v2 | 30/30 | Flagged **100%** of legitimate high-volume clients |
| v3 | 30/30 | A 2,000 msg/s flood of 256-byte messages raised no alert |
| v4 | 30/30 | Floods with constant-length messages raised no alert, up to 50,000 msg/s |
| v5 | 29/30 | 123 false alerts from 500 long-lived K=600 clients |
| **v6, frozen** | **29/30** | Section 6 |

**Selection:** the four model families were compared with S-episode group 5-fold on development runs. Differences were within noise, so a depth-12 decision tree was chosen on cost: about 25 µs against about 750 µs for the closest random forest and about 5,000 µs for boosting, and about 2 KB against about 30 KB and over 200 KB.

### `ew-dt12-lab-v6`

| Measure, on lab runs never used to train or select | Result |
|---|---|
| Fresh held-out run, attacks at varied rates and sizes among long-lived clients | **29 of 30 episodes alerted, 0 false alerts.** Missed: 1 lowrate episode |
| Windows in that run | macro-F1 1.000, 0 of 1,233 benign flagged, 176 attack windows. **Few windows; the CI of 1.00-1.00 reflects a small easy sample, not certainty** |
| Time to detect | Median 8.5-8.6 s for most families, 13.5 s for publish flood (W = 5, k = 2) |
| Long-lived benign clients, fresh, 15 minutes | 0 of 1,122 windows flagged, 0 alerts |
| Heavy benign clients, seen by v5, not by v6 | 2 of 4,146 windows flagged, 0 alerts |
| Six benign scenarios, 30 minutes each | 0 of 20,091 windows flagged, 0 alerts in 3 hours. **These ran before v2-v6 were built, but their results influenced no training** |
| Low-rate run, 15 episodes (not seen by v6) | 15/15, 0 false alerts |
| Live, one end-to-end run, all 5 families | All alerted in about 8.7 s from scheduled start, 0 false alerts |

**All of this is simulated traffic from this project's own scripts,** so it is not a real-world false-positive or detection rate. Calibration reads ECE 0.00, but a tree scoring nearly 0 or 1 on easy data says little, so the UI keeps the label "Score" and never says "confidence".

## 5. Research data: D-01 evidence

**D-01 stays open. Option B is not approved. Nothing here is E1-E9.**

| Check (MQTTset, W = 5, labels per file, not verified ground truth) | Result |
|---|---|
| Q10: identity and time fields alone | Macro-F1 **1.000** |
| Q11: features separating benign from attack alone, above 0.95 | **8**: F01, F02, F03, F05, F06, F09, F16, F26 |
| F26 values | Benign 5 or 10; every attack 1 |
| F21, F23 | Constant, so unusable by any model |
| `lowrate` | 1 row, excluded (F-59 undecided) |
| Macro-F1, 4 classes, S-rand | 0.948-0.972 |
| Macro-F1, 4 classes, S-time | 0.884-0.903 |
| Without F25, F26 under S-time | 0.841-0.913 |

**The S-rand minus S-time gap is about 0.05-0.09, which resembles H1. This is not a test of H1.** Test sets have 9-10 windows for two classes, and Q10 shows class and capture are entangled.

**Transfer is the clearest result:** a random forest trained on MQTTset and tested on lab traffic **flags 98.5-99.1% of benign windows**, macro-F1 0.23-0.24 (`results/ENG-X1-transfer/`). KS statistics between benign MQTTset and benign lab traffic reach 0.99 on F18. **This model cannot be deployed on this lab.** It does not show that published scores are invalid, or that it would fail elsewhere, and it mixes dataset shortcuts with ordinary differences between networks.

**Not done:** S-cross and E2, since MQTT-IoT-IDS2020 and CICIoMT2024 were not downloaded (terms unresolved under D-04); E1-a; the literature tasks.

## 6. Known limits of the deployed model

| Limit | Status |
|---|---|
| **Slow attackers below its learned rates go unnoticed:** 1 CONNECT per second, 0.3 malformed packets per second | Measured: 4 of 6 evasion variants alerted (`results/ENG-L4-evasion/`). Those variants informed training for v4 onward, so this is not a blind result |
| **A silent hold is invisible after its ramp.** Only windows with packets produce rows, so a hold shows up only while connections open (F-09) | Measured: about 2 rows per 40 s episode; one low-rate episode missed |
| **A legitimate client like an attack one is flagged.** 50 msg/s benign clients produced isolated flagged windows; k = 2 absorbed them here | Measured |
| **Thresholds are learned from one lab.** Real devices may fall on the wrong side | Not measured, and likely |
| **Depends on the decoder's F23 signal** | Retrain if OD-2 changes it |
| Trained on loopback addresses and Windows timing | Offload, Wi-Fi, and Linux timing untested |
| Plaintext MQTT only; a source behind NAT merges clients | By design |
| Bundle refuses another scikit-learn version | By design; retrain or pin on the gateway |
| Live memory for connections never closed | **Bounded since 2026-11-09** at 65,536 tracked connections, about 25 MiB (ENG-P3); evictions counted. Exact below the limit. The OD-1 expiry is not applied |

## 7. Performance

**Development laptop (i7-14700HX, 28 logical CPUs), Windows loopback, generator on the same machine, single 60 s runs. This is not E3 or E4, and nothing here predicts a Raspberry Pi.** CPU is percent of one core.

| Scenario | Sent msgs/s | IDS CPU mean | dumpcap CPU | IDS RSS peak | Inference p95 | Window end to alert p95 | Unseen PUBLISH | Alerts |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Idle broker | 0 | 0.08% | 0.05% | 159 MB | | | | 0 |
| 12 benign clients | | 0.81% | 0.11% | 160 MB | 0.60 ms | 1,032 ms | | 0 |
| 60 clients | | 1.20% | 0.11% | 161 MB | 0.31 ms | 1,080 ms | | 0 |
| 500 long-lived | | 0.71% | 0.03% | 164 MB | 0.22 ms | 1,246 ms | | 0 |
| Churn, 100 per s | | 1.96% | 0.18% | 166 MB | 0.71 ms | 1,173 ms | CONNECT 0% | 0 |
| Attack mix | | 4.53% | 0.24% | 171 MB | 0.30 ms | 1,159 ms | | 5 |
| 1,000 msgs/s | 1,000 | 2.06% | 0.03% | 160 MB | 0.55 ms | 1,240 ms | 0% | 4 |
| 5,000 msgs/s | 5,002 | 8.49% | 0.38% | 160 MB | 0.53 ms | 1,231 ms | 0% | 4 |
| 20,000 msgs/s | 19,999 | 26.7% | 1.04% | 160 MB | 0.41 ms | 1,245 ms | 0% | 4 |
| 50,000 msgs/s | 50,000 | 56.2% | 2.31% | 160 MB | 0.44 ms | 1,241 ms | 0% | 4 |

- **Maximum sustained rate: not found.** The highest tested rate had no loss. "Unseen" compares generator and IDS counts. dumpcap's own drop counter is unavailable live.
- **"Churn" raised 0 alerts at 100 connections per second,** while `flood_connect` at a similar nominal rate does alert. The cause was not investigated: **read this as a limit, not a pass.**
- **Rates here are per 4 senders,** and each alerted: 4 alerts per run.
- **Most of "window end to alert" is the deliberate 1 s lag.** Processing itself is sub-millisecond for inference.
- **Most RSS is imports.** About 159 MB at idle, mostly from loading scikit-learn and psutil. The design target of 256 MB is met here, but the tree could run without scikit-learn at a fraction of this: **unmeasured, worth doing for a gateway.**
- **Broker CPU with and without the IDS** differed by no consistent amount in these single runs. Noise is larger than any effect, so **no overhead is claimed.**

**One-hour soak, 12 benign clients (`results/ENG-P2-soak/`):** 0 alerts in 6,837 windows, 0 TCP gaps, 0 late events; IDS CPU mean 0.4%, RSS 159 MB at start, 126 MB at end, peak 163 MB; store 14 MB, about 2 KB per window, so about 335 MB per day for this load, capped by retention at 500,000 events. **One hour on a laptop is not a stability result for a gateway.**

## 8. Honesty rules held

Provenance is server-set and cannot be changed by the UI. Replay shows `REPLAY`. Predictions are never called confirmed, and a test scans the interface for forbidden words. Empty states are shown, not filled. No random numbers exist in the UI. Replaying real captures replaced a synthetic generator, so `SYNTHETIC` is supported in the store but nothing produces it.

**Your brief asked for "confirmed" events, which conflicts with the project's rule 23.** The UI shows normal, suspicious, and alert, where alert means k consecutive windows. Say if you want that word used.

## 9. Decisions needed

Recorded in [DECISIONS.md](../DECISIONS.md) as OD-1 to OD-5. Evidence: `edgewatch-data/reports/T3_5_F22_POLICY_EVIDENCE.md`, `T3_6_F23_EVIDENCE.md`.

## 10. Reproduction

Commands are in [INSTALL_AND_OPERATE.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/implementation/INSTALL_AND_OPERATE.md) section 4. Lab traffic is real and timed, so reruns are similar, not identical. Earlier model results stay in `results/ENG-*-v1` to `-v5`.

## 11. Software-only completion, 2026-11-09

**Everything here is engineering evaluation on a Windows laptop with simulated clients on loopback.** Nothing is an E1-E9 result or a Raspberry Pi figure.

**Detector comparison (ENG-C1).** Held-out run `campaign6/ep_s2` (30 episodes) and 3.3 h of benign lab runs, including a new 5-minute smart-home run that no model saw. Thresholds come from dev runs only; nothing was retuned afterwards.

| Detector | Macro-F1 (95% CI) | Episodes | False alerts / h | µs / window | Bytes |
|---|---|---|---|---|---|
| DT `ew-dt12-lab-v6` (deployed) | 1.000 (1.00-1.00) | 29/30 | 0.00 | 28 | 1,895 |
| RF (25, depth 16) | 0.978 (0.89-1.00) | 29/30 | 1.22 | 798 | 30,303 |
| LR (C=10) | 0.913 (0.83-0.98) | 29/30 | 4.16 | 94 | 2,470 |
| Rule baseline, dev benign q0.999 | 0.844 (0.77-0.91) | 29/30 | 0.24 | 7 | 91 |
| Rate baseline, F01 only | 0.324 (0.26-0.43) | 17/30 | 0.24 | 2 | 30 |

A rate threshold alone misses most non-flood attacks. The per-class rules reach the same episodes as the models, with more flagged benign windows. The intervals overlap for DT and RF, so **no superiority is claimed.** The `campaign1/stealth` run shaped training after v1, so its 15/15 here is not a blind result.

**RQ1 analogue on lab data (ENG-R1).** These are dev runs only, 5 seeds, and DT and RF scored within about 0.01 macro-F1 under all three splits: random windows (DT 0.994), episode-grouped (0.991) and run-held-out (0.996). This lab generator has no strong split leakage. MQTTset's random-versus-time gap of 0.05-0.09 is therefore more likely dataset shortcuts than a general effect. **This is not a test of H1.**

**Bounds and stage costs (ENG-P3).** With 300,000 never-closed connections, F22 state holds about 25 MiB with the limit and 102 MiB without it. Under 20,000-source churn, alert state stays at 14 sources. On a recorded capture (163,767 frames), decoding costs 30 µs per frame and features 3.6 µs per frame. Inference costs 35 µs per window and the alert policy 0.9 µs. That is about 29,500 frames per second offline on one thread.

**New software.** The dashboard has Simulate, Investigate, Compare and analytics views, with matching API endpoints. Dashboard-started runs are loopback-only, capped at 600 s, one at a time, and killed as a whole process tree. The lab has smart-home profiles and T7 topic probing. Security guards: a Host allow-list and a WebSocket Origin check.

**End to end (ENG-E2E-CC, 31/31).** The documented start script launches the API and IDS. A dashboard-triggered simulation (smart-home devices plus brute force, publish flood and malformed) raises one alert per family, each matching the runner's schedule. 0 of 233 benign windows are flagged. The WebSocket, store and browser views agree. A missing model, a double start, an off-limits request, a duplicate start, a rapid stop and API loss are all handled. Stop leaves no orphans, and a restart reads earlier alerts. The page has no horizontal overflow at 390 px.

**Soak after changes (ENG-P2-soak-v2).** One hour, 0 alerts, 0 TCP gaps, every CONNECT seen. Under 100 connections per second, IDS RSS rose from 156 to 182 MB. ENG-P4 replays 200,000 churned connections through the in-process pipeline: memory rises while the decoder's stream table fills to 32,768 entries (ephemeral ports × 2 directions), then stays flat. **Bounded, not leaking.**

**Window size (ENG-W1, E9 analogue, dev runs only).** 1 s windows alerted 175 of 180 episodes with a median time to detect of 2.7 s; 5 s gave 167/180 and 12.3 s; 10 s gave 147/180 and 24.2 s. Window macro-F1 was about 0.99 at every size. Windows straddling an episode edge are excluded, which removes more at larger sizes, so the episode counts favour small windows. The deployed 5 s model is unchanged.

**Evidence cost (E7 analogue).** Building the explanation for one alert costs about 59 µs, in a run made while other jobs were using the CPU.

**OD-1 expiry.** Implemented as an opt-in `fx-0.1+ka1.5`. It changes 0 of 100,370 rows on 29 lab runs. Enabling it awaits approval.

**Still not done.** E1-E9 themselves (approvals and datasets). Any hardware figure.
