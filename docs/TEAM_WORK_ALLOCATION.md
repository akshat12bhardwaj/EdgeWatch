# Team Work Allocation (provisional)

Team members' names and expertise are not yet known, so the allocation is **role-based**. Assign names at M0 and swap roles to match each person's strengths. These are workstreams that hand work to each other, not six separate projects.

## 1. Workstreams

| ID | Role | Primary responsibility | Concrete deliverables |
|---|---|---|---|
| **S1** | Research lead | Literature, gap validation, novelty tracking, report sections 1–3 | Round-2 search; 3 full-text reviews; frozen gap analysis; REFERENCES upkeep; final claim audit (with S6) |
| **S2** | Data lead | Datasets, licences, data quality, labelling | D-01 to D-04 resolved; checksummed `data/raw`; DQ reports; label harmonisation; DATA_DICTIONARY upkeep |
| **S3** | ML lead | Splits, models, offline evaluation, calibration | `splits.py`, `train.py`, `evaluate.py`; E1-a/E1/E2/E9/E6/E7; model cards |
| **S4** | Lab & gateway lead | Isolated lab, broker, traffic generators, gateway service | Lab network; C1/C2/C14; Mosquitto config; `live.py` service; PILOT-E3/E3/E4; safety allow-list |
| **S5** | Visualisation lead | Edge Watch console, replay service, design system | C10–C12; panels P1–P8; usability walk-through; screenshots with provenance |
| **S6** | Integration & QA lead | Feature extractor (shared core), testing, integration, E5, documentation consistency, presentation coordination | `features.py` + tests (with S2); TESTING_STRATEGY; E5; rehearsals; demo archive; DECISIONS upkeep |

**Why S6 owns the extractor:** it is the shared interface between S2 (offline data), S3 (training), and S4 (live). Giving it to the integration owner keeps a single owner for the parity test.

## 2. Literature-review assignment (3 papers each)

Papers chosen are those not yet read in full and most relevant to each role. IDs are from [REFERENCES.md](research/REFERENCES.md).

| Student | Papers | Key question each must answer |
|---|---|---|
| S1 | P19 (journal version), P14, P17 | Do they report grouped/temporal splits, cross-dataset tests, or edge measurements that pre-empt RQ1–RQ2? |
| S2 | P15, P18, P21 | PCAP availability, labelling method, independence, MQTT columns |
| S3 | P13, P12, P30 | Split strategies used; baselines; the pitfalls checklist for our protocol |
| S4 | P01, P03, P05 | Attack mechanics for T1–T6; safe lab reproduction; spec references |
| S5 | P34, P35, P06 | Explanation presentation; visualisation taxonomy; protocol-validation indicators for P6 |
| S6 | P24, P25, P27 | How resource cost was measured (model-only or end-to-end? tools? device settings?) |

Optional (abstract level is sufficient for now): P02, P04, P07, P10, P11, P16, P23, P26, P28, P29, P31, P32, P33.

## 3. Interfaces between workstreams

| From → To | What is handed over | Contract |
|---|---|---|
| S2 → S6 | Raw PCAPs + labelling rules | DATA_QUALITY_PROTOCOL §4 |
| S6 → S2, S3, S4 | `features.py` (one module) | FEATURE_SPECIFICATION (versioned `fx-x.y`) |
| S2 → S3 | `windows.parquet` + DQ report | DATA_DICTIONARY §2 |
| S3 → S4 | Model artefact + model card | DATA_DICTIONARY §6; ADR-11 |
| S4 → S5, S6 | Event stream / event logs | DATA_FLOW §3 (schema v1.0) |
| S3, S4, S6 → S5 | `results/*/metrics.json` | DATA_DICTIONARY §4 |
| All → S1 | Claims for the report | Claim audit (Phase 07) |

## 4. What each student needs from others / provides

| Student | Needs | Provides |
|---|---|---|
| S1 | Results (S3, S4, S6) for the report | Frozen RQs and hypotheses (everyone depends on these at M1) |
| S2 | Extractor (S6) | Clean labelled datasets (S3) |
| S3 | Features (S2/S6) | Models (S4); results (S5, S1) |
| S4 | Models (S3); extractor (S6) | Lab runs and events (S5, S6); E3/E4 results |
| S5 | Event schema (frozen at M1); events (S4); results (S3/S4/S6) | Console; replay; screenshots |
| S6 | Everything, at integration | Tests, E5, rehearsal reports, consistent docs |

## 5. Reviews (four-eyes rule)

| Artefact | Author | Reviewer |
|---|---|---|
| Full-text reviews | each student | the student with the next number (S1→S2 … S6→S1) |
| Extractor | S6 | S2 + S4 |
| Splits and evaluation code | S3 | S6 |
| Attack scripts (safety) | S4 | S1 + supervisor |
| Dashboard wording (honesty rules) | S5 | S1 |
| Results tables | S3 / S4 / S6 | another student who re-runs one configuration |

## 6. Decisions that require team agreement

The following require the whole team, logged in [DECISIONS.md](DECISIONS.md):
- the gap and the RQs;
- Δ for H1;
- the primary dataset (after D-01);
- the extractor version freeze;
- the deployed model (E6);
- changes to the event schema;
- the official demo run;
- any change to the safety boundaries;
- adding mitigation features (default: no).

## 7. How each workstream is evaluated

| Student | Evaluated on |
|---|---|
| S1 | Accuracy of references; quality of the gap argument; no unsupported claims in the report |
| S2 | Reproducible data pipeline; documented discrepancies; DQ reports |
| S3 | Correct leakage controls (tests); completeness of E1/E2; CIs |
| S4 | Lab safety; stable gateway service; E3/E4 completeness and documented conditions |
| S5 | Spec compliance (all states); honesty rules; walk-through outcome |
| S6 | Test coverage of the shared core; integration stability; E5; documentation consistency |
