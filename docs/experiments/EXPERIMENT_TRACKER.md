# Experiment Tracker

**Rule:** do not fill in a result until the experiment has been run. A result cell links to `results/<exp_id>/`. Status values: `planned`, `running`, `completed`, `failed`, `deferred`.

| Exp ID | Description | RQ | Owner | Depends on | Status | Started | Finished | Result link | Notes / failures |
|---|---|---|---|---|---|---|---|---|---|
| DQ-mqttset | Data quality checks on MQTTset | RQ1 | S2 | D-01 | planned | | | | |
| DQ-mqttiot | Data quality checks on MQTT-IoT-IDS2020 | RQ1 | S2 | — | planned | | | | |
| DQ-ciciomt | Data quality checks on CICIoMT2024 | RQ1 | S2 | D-04 | planned | | | | |
| E1-a | Reproduce a published-feature RF baseline (S-rand) | RQ1 | S3 | DQ-* | planned | | | | Sanity anchor vs. P08/P09 |
| E1 | Split-strategy comparison | RQ1 | S3 | Phase 01, DQ-* | planned | | | | |
| E2 | Cross-dataset | RQ1 | S3 | E1 | planned | | | | |
| E9 | Window-size sensitivity | RQ1/RQ2 | S3 | E1 | planned | | | | |
| PILOT-E3 | Gateway pilot to set the load levels | RQ2 | S4 | Phase 04 | planned | | | | |
| E3 | Stage-wise latency on the gateway | RQ2 | S4 + S6 | PILOT-E3 | planned | | | | |
| E4 | Resource consumption | RQ2 | S4 + S6 | E3 | planned | | | | |
| E5 | Benign-lab FPR | RQ3 | S6 | Phase 02, E1 | planned | | | | |
| E6 | Pareto analysis | RQ2 | S3 | E1, E3, E4 | planned | | | | |
| E7 | Evidence cost | RQ4 | S3 | E3 | planned | | | | |
| E8 | TLS-visible features only | RQ1 (ext.) | S3 | E1 | deferred | | | | Optional; decide at M3 |

## Run log

Append one line per run attempt, including failures.

| Date | Exp ID | Run ID | Operator | Outcome | Notes |
|---|---|---|---|---|---|
| 2026-11-09 | (E1 analogue) | ENG-R1-lab-splits | AI assistant | completed | Random vs episode vs run split on lab dev runs; **not E1** (no DQ-*, no MQTTset) |
| 2026-11-09 | (E3/E4 analogue) | ENG-P1, ENG-P2-soak, ENG-P2-soak-v2, ENG-P3-bounds, ENG-P4-churn-memory | AI assistant | completed | Windows software gateway on the development laptop; **not the gateway pilot** |
| 2026-11-09 | (E5 analogue) | ENG-C1-compare (benign runs), ENG-B1-* | AI assistant | completed | 3.3 h of benign lab runs incl. an unseen smart-home run; **not E5** (E1 not done) |
| 2026-11-09 | (E6 analogue) | ENG-C1-compare | AI assistant | completed | Quality vs cost per detector, report section 11 |
| 2026-11-09 | (E7 analogue) | ENG-P3-bounds `evidence_us_per_alert` | AI assistant | completed | Explanation cost per alert |
| 2026-11-09 | (E9 analogue) | ENG-W1-window-size | AI assistant | see result | 1, 5, 10 s windows on lab dev runs; **not E9** |
| 2026-11-09 | E1-a, E1, E2, E8 | — | — | not run | E1-a/E1 need D-01 and Option B; E2 needs D-04 datasets; E8 deferred by design |
