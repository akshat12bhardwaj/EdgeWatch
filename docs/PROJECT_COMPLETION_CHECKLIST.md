# Project Completion Checklist

## Software-only brief, 2026-11-09 (current)

The owner's brief puts hardware out of scope (see DECISIONS, "Owner brief of 2026-11-09"). Key: ✅ verified · 🟡 verified with a stated limit · ⏳ pending · ⛔ blocked, with what blocks it.

| ID | Status | Evidence |
|---|---|---|
| SG-01 Baseline | ✅ | 334 unit + 2 integration + 13 frontend tests passed at start; OD/D/DEC decisions identified |
| SG-02 Core IDS | ✅ | F22 hard limit 65,536 (OD-1 hard-limit part), exact alert-state pruning, display retention, decoder fuzz; `tests/test_features.py`, `test_alerts_store.py`, `test_service.py`, `test_decoder.py`; ENG-P3 |
| SG-03 Run reliably | ✅ | Start script fixed for stale PID files and passes simulation settings. ENG-E2E-CC verifies a missing model refused with a message, refused double start, clean start, stop with no orphans, and repeat start |
| SG-04 Lab traffic | ✅ | Smart-home profiles, T7 topic probing, bounded `--families`/`--rate-factor`; real-broker test; caps tested |
| SG-05 Models | ✅ | ENG-C1: v6 tree, LR, RF, rule and rate baselines on identical held-out runs, thresholds from dev only |
| SG-06 Research | 🟡 / ⛔ | Engineering analogues: ENG-R1 (RQ1 splits on lab data), ENG-P1/P2/P3 (RQ2 on a Windows software gateway), ENG-B1/L3/X1/C1 smart-home (RQ3). **E1-E9 blocked:** D-01/Option B/DEC-02..05 not approved; MQTT-IoT-IDS2020 and CICIoMT2024 not downloaded (D-04) |
| SG-07 Dashboard | ✅ | Tabs Live/Simulate/Investigate/Compare/Research on real endpoints; 22 API tests, 18 frontend tests, build. In headless Chrome: alert count matches the stream, device labels drawn, Investigate lists alerts, Compare renders results, disconnect banner, **no horizontal overflow at 390 px on any tab** (settles the 2026-11-02 question) |
| SG-08 End to end | ✅ | `results/ENG-E2E-CC/`: 31/31 checks, run_started_epoch 1794209145, 257 s, on the vite-8 build. Brute force, publish flood and malformed each alerted and matched the runner's schedule; 0 of 233 benign windows flagged. Earlier runs: one hung on an inherited pipe (fixed), one was stopped by a concurrent session, one failed a selector that clicked the tab instead of the button (fixed) |
| SG-09 Performance | ✅ | ENG-P1 (to 50,000 msg/s, 0% loss), ENG-P2 (1 h soak), ENG-P3 (state bounds, stage costs); laptop only |
| SG-10 Security | ✅ | Host allow-list, WebSocket Origin check, loopback-only simulation control, token, bounded and validated parameters, no shell, path-like ids refused. pip-audit: no known vulnerabilities. npm audit: 0 after upgrading dev tooling to vite 8.3.6, vitest 5.1.0, plugin-react 6.3.0. pyflakes: no undefined names in `src`, `dashboard/api` |
| SG-11 Docs | ✅ | INSTALL_AND_OPERATE, WINDOWS_QUICK_START, FINAL_SYSTEM_ARCHITECTURE, FEATURE_SPECIFICATION, DECISIONS, report section 11, this checklist |
| SG-12 Final verification | ✅ | 371 Python unit, 2 integration, 18 frontend tests; typecheck and build; ENG-E2E-CC 31/31; audits above |
| Soak after changes | ✅ | ENG-P2-soak-v2: 1 h (benign 30 min + churn 30 min at 100 conn/s), 0 alerts, 0 TCP gaps, 0 late events, 130,784/130,784 CONNECTs seen, IDS CPU mean 0.4-1.9% of a core. RSS 156→182 MB under churn; ENG-P4 shows it is the decoder stream table filling to 32,768 (16,384 ephemeral ports × 2), then flat (+0.09 MiB over the second 100 k connections) |
| OD-1 expiry | 🟡 | Implemented opt-in as `fx-0.1+ka1.5`; 0 of 100,370 rows changed on 29 lab runs (ENG-OD1-expiry). **Enabling it needs owner approval** |
| Research analogues | ✅ | ENG-R1 (splits), ENG-W1 (window size), ENG-C1 (detectors, benign FPR, Pareto), ENG-P1-P4 (cost), evidence cost in ENG-P3. **E1-E9 themselves stay not run** (DECISIONS, decision review) |

## Earlier checklist, 2026-11-02 (kept for history)


Against section 13 of the brief, on 2026-11-02. Evidence: [FINAL_TECHNICAL_REPORT.md](reports/FINAL_TECHNICAL_REPORT.md). **Overall: not complete, because the unmet items need your decisions or a physical device.**

Key: ✅ met and evidenced · 🟡 met with a stated limit · ⛔ not met, with what blocks it.

## A. Packet processing
- ✅ Validated path exists: 0 differences from tshark on 12 M events
- ✅ MQTT reconstruction for supported cases (rare cases on invented traffic only)
- ✅ Feature extraction; `fx-0.1` unchanged
- ✅ Privacy requirements pass
- ⛔ Memory acceptable for the target gateway: **unmeasured on a gateway; unclosed connections unbounded until OD-1**

## B. Detection
- ✅ Trained, versioned model: `ew-dt12-lab-v6`, with card and refusal on mismatch
- 🟡 Evaluation defensible: held-out runs and group splits, but only this project's simulated traffic. **Not a research result; D-01 open**
- ✅ Inference works live
- ✅ Alerts correct: threshold, k, suppression, severity, status
- 🟡 False positives measured on lab scenarios only; no real-world rate exists
- ✅ Research limitations documented

## C. Gateway
- ✅ Broker and IDS run independently (Windows loopback)
- 🟡 IDS monitors real traffic: real packets through a real broker, on loopback only
- ✅ Disabling the IDS does not stop the broker
- 🟡 Start, stop, restart tested on Windows; systemd units **not run**
- 🟡 Resources measured on a laptop only

## D. Backend
- ✅ API endpoints, WebSocket, alert persistence, failure handling

## E. Dashboard
- ✅ All panels show real data, or say that they have none
- ✅ Live updates, without reload, in a real browser
- ✅ Alert investigation
- ✅ Empty and error states. Tested: no alerts, disconnected, no store (by API), unreadable result. Viewed in screenshots: loading only briefly
- 🟡 Coherent design, viewed at 1920×1080 and 1280×720; panels stack below 1280 px. **At phone width the headless browser appeared to lay out wider than the window and clipped the right edge. This is either a screenshot artefact or a real overflow; it was not settled**

## F. End-to-end
- ✅ Benign traffic through the broker
- ✅ Simulated attacks detected; 5 of 5 families in the final run
- ✅ Results reach the dashboard
- ✅ Tolerated failures: IDS kill, API kill, missing model, model error, store error

## G. Documentation and reproducibility
- ✅ Install, configuration, test commands, architecture, limitations, reproducible measurements
- 🟡 "No critical undocumented dependency": gateway steps are written but unexecuted

## H. Verification integrity
- ✅ Claims trace to tests, results, or are marked "not run"

## Blocked items

| Item | Needs |
|---|---|
| Gateway memory, CPU, latency, deployment, RQ2 | A Raspberry Pi |
| Physical network behaviour | An isolated switch or AP |
| Memory bound on live state | OD-1 |
| Stable F23 meaning | OD-2 |
| Any research claim, E1-E9, RQ1, RQ3 | OD-3, D-04, frozen protocol, other datasets |
