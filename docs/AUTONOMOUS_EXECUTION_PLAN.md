# Autonomous Execution Plan

Status words: **Done**, **Blocked** (names the decision or resource). Levels are kept apart: implemented, unit-tested, integration-tested, real-capture-validated, hardware-validated.

## Baseline, verified 2026-11-02 against code, tests and reports

| Item | Status | Verified how |
|---|---|---|
| T1 extractor, `fx-0.1` | Done, unchanged | `src/ids/features.py`, tests |
| T2 tshark validation | Done | `reports/T2_TSHARK_VALIDATION.md` |
| T3, T3.1 adapter, topic privacy | Done | `src/ids/fields.py`, `reports/t3`, `reports/t3_1` |
| T3.2 tshark memory | Done; unbounded | `reports/T3_2_INFLIGHT_MEMORY_EXPERIMENT.md` |
| T3.3 decoder | Done | `reports/T3_3_BOUNDED_DECODER_EVALUATION.md` |
| T3.4 F22 lifecycle | Done; unclosed connections unbounded | `reports/T3_4_F22_STATE_LIFECYCLE.md` |

## Dependency graph

```text
A1 F22 evidence ---> GATE OD-1          A2 F23 evidence ---> GATE OD-2
A3 decoder gaps -> A4 live stream -> D1 lab -> D2 models -> E1 alerts and store -> G1 API -> H1 dashboard -> I1 end-to-end -> J1 performance -> K1 report
A3 -> B1 pipeline -> C1 dataset validation -> D2
```

## Subgoals

| ID | Subgoal | Acceptance | Status | Evidence |
|---|---|---|---|---|
| A1 | T3.5 F22 | All required cases measured; production unchanged | **Done; blocked on OD-1 for applying** | `reports/T3_5_F22_POLICY_EVIDENCE.md` |
| A2 | T3.6 F23 | Rules evaluated; F23 unchanged | **Done; blocked on OD-2 for applying** | `reports/T3_6_F23_EVIDENCE.md` |
| A3 | Decoder gaps | Fixtures against tshark; capture digests unchanged | Done | `tests/test_decoder.py`, `reports/t3_7/` |
| A4 | Live stream | Real loopback traffic decoded | Done | `tests/test_integration_live.py` |
| B1 | Offline pipeline | Schema, diagnostics, reproducible digest | Done | `src/ids/pipeline.py` |
| C1 | Dataset validation | Reproducible; D-01 stays open | Done; **blocked on OD-3 for research use** | `results/DQ-MQTTSET/` |
| D1 | Lab | Loopback only; caps tested; schedule first | Done | `lab/`, `tests/test_lab.py` |
| D2 | Models | Compared by protocol splits, no test tuning, card, refusal | Done, engineering only | `results/ENG-L*` |
| E1 | Alerts, store, service | Policy tested; failures tolerated | Done | `tests/test_alerts_store.py`, `tests/test_service.py` |
| G1 | API | Failure paths tested | Done | `tests/test_api.py` |
| H1 | Dashboard P1-P8 | Real data; states; screenshots | Done | `dashboard/web/`, `reports/e2e_shots_v6/` |
| I1 | End-to-end | All checks pass | Done on Windows loopback | `results/ENG-E2E/` |
| J1 | Performance | Scenarios measured, labelled | Done on the laptop; **blocked on hardware for a gateway result** | `results/ENG-P1/`, `results/ENG-P2-soak/` |
| K1 | Docs and report | Verified separated from unverified | Done | `docs/reports/FINAL_TECHNICAL_REPORT.md` |

## Blockers

| Blocker | Kind | Effect |
|---|---|---|
| OD-1 F22 policy | Your decision | Live memory unbounded for connections never closed |
| OD-2 F23 meaning | Your decision | Decoder-path F23 stays adapter-defined |
| OD-3 D-01, Option B | Your decision | Nothing can be called a research result |
| OD-4, OD-5 | Your decision | Architecture differences stay proposed |
| Raspberry Pi | Hardware | No gateway measurement exists; RQ2 unanswered |
| Physical isolated network | Hardware | Lab is Windows loopback |
| MQTT-IoT-IDS2020, CICIoMT2024 | Terms (D-04), not downloaded | S-cross, E2 not run |
