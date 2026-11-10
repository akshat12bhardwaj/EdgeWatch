# Documentation Audit

> Historical technical reference. Current operation is documented in README.md; old UI, deployment and research plans are not current instructions.

**Audit date:** 2026-10-31. **Audited baseline:** v0.1 (2026-10-20), commit `bd8c85d`.
**Conducted by:** Claude Code (AI assistant), for team review. Findings are not decisions. No existing document was changed, and no open decision was resolved.

**Labels:** **VERIFIED** (checked directly in the repository during this audit, or a recorded full-text finding) · **PROPOSED** (a design choice awaiting approval) · **REJECTED** · **UNRESOLVED** · **PROVISIONAL** · **UNKNOWN**. "Suggested resolution" entries are PROPOSED only.

## 1. Result in brief

- **Files inspected: 44 of 44.** Every file was read in full, directly, in this session. No sampling and no subagents. `.gitattributes`, the only tracked file outside `docs/`, was also read.
- **No implementation exists (VERIFIED).** The repository holds only the 44 documents and `.gitattributes`. `tshark`, `mosquitto`, and `docker` are not on PATH.
- **The core research logic is coherent.** The gap, RQs, hypotheses, architecture, and honesty rules agree across documents. No document contradicts the overall design.
- **13 high-severity findings** could block M1 or invalidate a result (§4.1). The most serious:
  - D-01 is due after the protocol that depends on it is frozen (F-01).
  - The D-01 fallback leaves almost no family-level cross-dataset test (F-02).
  - H2 cannot be computed from the defined timers (F-03).
- **M1 is not ready to be passed, and M0 is not recorded as complete.** Phase 00 reading can start now (§10).
- **Later additions:** §11 (planning findings) and §12 (measured D-01 evidence). D-01 remains Open.

## 2. Scope and method

Every file under `docs/` was read in full, starting with the blueprint. Related documents were then cross-checked. A script checked all relative Markdown links and anchors (one failure, F-40). `PAPER_MATRIX.csv` was parsed to count access levels and assignments.

**Not checked:** no DOI, dataset page, or paper was opened, so all literature claims are as recorded in the documents. Commands in the setup guide and phase guides were not run. Findings tagged **[verify on device]** rest on general tool knowledge and need a test.

## 3. File inventory (44)

| # | File | Lines | Purpose |
|---|---|---:|---|
| 1 | [README.md](README.md) | 27 | Entry point, status, conventions, layout |
| 2 | [MASTER_PROJECT_BLUEPRINT.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/MASTER_PROJECT_BLUEPRINT.md) | 97 | Authoritative overview, canonical names, confidence table |
| 3 | [PROJECT_CHARTER.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/PROJECT_CHARTER.md) | 46 | Problem, goal, scope, success criteria, constraints, sign-off table |
| 4 | [DECISIONS.md](DECISIONS.md) | 31 | Team decisions (DEC) and open questions (D, Q) |
| 5 | [DEFINITION_OF_DONE.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/DEFINITION_OF_DONE.md) | 30 | Done criteria for tasks, experiments, panels, project |
| 6 | [IMPLEMENTATION_ROADMAP.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/IMPLEMENTATION_ROADMAP.md) | 32 | M0–M6, acceptance criteria, gate owners, critical path |
| 7 | [RISKS_AND_MITIGATIONS.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/RISKS_AND_MITIGATIONS.md) | 20 | Risk register R1–R14 |
| 8 | [TEAM_WORK_ALLOCATION.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/TEAM_WORK_ALLOCATION.md) | 89 | Roles S1–S6, paper assignments, interfaces, reviews |
| 9 | [TESTING_STRATEGY.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/TESTING_STRATEGY.md) | 49 | Unit, parity, integration, and measurement validation tests |
| 10 | [architecture/ARCHITECTURE_DECISIONS.md](architecture/ARCHITECTURE_DECISIONS.md) | 97 | ADR-01 to ADR-12, all Proposed |
| 11 | [architecture/DATA_FLOW.md](architecture/DATA_FLOW.md) | 115 | Live and offline flows, stage latencies, event contract, storage |
| 12 | [architecture/FEATURE_SPECIFICATION.md](architecture/FEATURE_SPECIFICATION.md) | 84 | `fx-0.1`: tshark fields, F01–F26, window rules, exclusions |
| 13 | [architecture/SYSTEM_ARCHITECTURE.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/architecture/SYSTEM_ARCHITECTURE.md) | 113 | Planes, components C1–C14, deployment views, resource budget |
| 14 | [architecture/THREAT_MODEL.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/architecture/THREAT_MODEL.md) | 79 | Adversary, T1–T7, detectability matrix, lab safety boundaries |
| 15 | [data/DATASET_SELECTION.md](data/DATASET_SELECTION.md) | 71 | Dataset comparison, roles, label harmonisation, blockers |
| 16 | [data/DATA_DICTIONARY.md](data/DATA_DICTIONARY.md) | 54 | On-disk tables, results files, model card |
| 17 | [data/DATA_QUALITY_PROTOCOL.md](data/DATA_QUALITY_PROTOCOL.md) | 47 | Checks Q1–Q12, labelling rules, imbalance rules |
| 18 | [experiments/EVALUATION_PROTOCOL.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/experiments/EVALUATION_PROTOCOL.md) | 104 | Splits, E1–E9, measurement method, threats to validity |
| 19 | [experiments/EXPERIMENT_TRACKER.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/experiments/EXPERIMENT_TRACKER.md) | 28 | Experiment status table and run log; all planned or deferred |
| 20 | [implementation/PHASE_00_RESEARCH.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/implementation/PHASE_00_RESEARCH.md) | 25 | Research validation, leads to M1 |
| 21 | [implementation/PHASE_01_DATA.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/implementation/PHASE_01_DATA.md) | 32 | Data, quality checks, extractor, leads to M2 |
| 22 | [implementation/PHASE_02_TRAFFIC_LAB.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/implementation/PHASE_02_TRAFFIC_LAB.md) | 35 | Isolated lab and traffic generators, leads to M2 |
| 23 | [implementation/PHASE_03_BASELINES.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/implementation/PHASE_03_BASELINES.md) | 33 | Offline evaluation, leads to M3 |
| 24 | [implementation/PHASE_04_EDGE_IDS.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/implementation/PHASE_04_EDGE_IDS.md) | 31 | Gateway service and measurement, leads to M4 |
| 25 | [implementation/PHASE_05_DASHBOARD.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/implementation/PHASE_05_DASHBOARD.md) | 33 | Edge Watch build, leads to M5 |
| 26 | [implementation/PHASE_06_INTEGRATION.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/implementation/PHASE_06_INTEGRATION.md) | 25 | Integration, E5, demo run, leads to M5 |
| 27 | [implementation/PHASE_07_FINAL_VALIDATION.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/implementation/PHASE_07_FINAL_VALIDATION.md) | 24 | Claim audit, reproducibility, report, leads to M6 |
| 28 | [implementation/SETUP_GUIDE.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/implementation/SETUP_GUIDE.md) | 82 | Environment inventory and setup steps (not executed) |
| 29 | [ml/MODEL_EVALUATION.md](ml/MODEL_EVALUATION.md) | 51 | Metrics, uncertainty, calibration, alert policy, evidence |
| 30 | [ml/MODEL_SELECTION.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/ml/MODEL_SELECTION.md) | 37 | Models, exclusions, grids, deployed-model rule |
| 31 | [ml/TRAINING_PIPELINE.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/ml/TRAINING_PIPELINE.md) | 56 | Training steps, rules, suggested layout, library status |
| 32 | [presentation/DASHBOARD_SPECIFICATION.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/presentation/DASHBOARD_SPECIFICATION.md) | 93 | Global behaviour and panels P1–P8 |
| 33 | [presentation/DEMO_STORYBOARD.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/presentation/DEMO_STORYBOARD.md) | 69 | Demo modes, preflight, scenes, recovery |
| 34 | [presentation/PRESENTATION_PLAN.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/presentation/PRESENTATION_PLAN.md) | 50 | Talk narrative, speakers, anticipated questions |
| 35 | [presentation/VISUALIZATION_RESEARCH_MAPPING.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/presentation/VISUALIZATION_RESEARCH_MAPPING.md) | 25 | UI-to-research traceability, rejected elements |
| 36 | [presentation/VISUAL_CONCEPT.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/presentation/VISUAL_CONCEPT.md) | 106 | Design system, motion rules, layout, anti-patterns |
| 37 | [reports/FINAL_REPORT_OUTLINE.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/reports/FINAL_REPORT_OUTLINE.md) | 18 | Report structure |
| 38 | [reports/LIMITATIONS.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/reports/LIMITATIONS.md) | 25 | Known limitations (living document) |
| 39 | [reports/RESULTS_TEMPLATE.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/reports/RESULTS_TEMPLATE.md) | 44 | Empty results tables; no results recorded |
| 40 | [research/LITERATURE_REVIEW.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/research/LITERATURE_REVIEW.md) | 172 | Thematic round-1 synthesis and review template |
| 41 | [research/PAPER_MATRIX.csv](research/PAPER_MATRIX.csv) | 37 | Per-paper details, access level, reviewer |
| 42 | [research/REFERENCES.md](research/REFERENCES.md) | 83 | Bibliography P01–P36, S1–S2, with access level |
| 43 | [research/RESEARCH_GAP_ANALYSIS.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/research/RESEARCH_GAP_ANALYSIS.md) | 92 | G1–G7 verdicts, RQs, hypotheses, novelty risks, title |
| 44 | [research/SEARCH_PROTOCOL.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/research/SEARCH_PROTOCOL.md) | 102 | Search log, criteria, exclusions, round-2 plan |

## 4. Contradictions and inconsistent decisions

Evidence is cited as `FILE §section` or `FILE line`. Under the blueprint's own rule, a disagreement is raised in DECISIONS.md, and the detailed document wins until it is resolved. **None of these has yet been raised there.**

### 4.1 High severity: could block M1 or invalidate a result

| ID | Finding | Evidence | Consequence | Suggested resolution (PROPOSED) |
|---|---|---|---|---|
| **F-01** | **D-01 timing conflict.** Final dataset selection is "at M1, after D-01 to D-04 are resolved", but D-01 is due at M2 and is resolved in Phase 01, which starts after M1. The protocol frozen at M1 names MQTTset as primary | DATASET_SELECTION status line; DECISIONS D-01; PHASE_01 tasks 3; EVALUATION_PROTOCOL §2; PHASE_00 §6 | The team could pre-register a protocol on a dataset it cannot use | Answer D-01 before the freeze. It needs a download and a file listing, and no project tool install. Team decides |
| **F-02** | **The D-01 fallback is understated.** R2 and D-01 say to use MQTT-IoT-IDS2020 as primary. Its only MQTT attack is brute force, which CICIoMT2024 lacks. Using the harmonisation table, that pair shares **only `benign`** at family level. `lowrate` would have no public dataset, and `flood`/`malformed` no dataset pair | DATASET_SELECTION §3; RISKS R2; EVALUATION_PROTOCOL §3 | Without MQTTset, family-level S-cross is effectively gone, and only a binary test across different attacks remains. E1 on the fallback becomes close to two-class. RQ1 would need redesign, not a swap | Add a written fallback plan. D-02 (P15) and D-03 (P18) are the natural candidates |
| **F-03** | **H2 cannot be computed from the defined stages.** H2 needs "capture + feature extraction" as a share of "per-window processing time". `processing_total` starts at window end, so it excludes per-packet decoding and aggregation during the window. `capture_to_parse` is per packet. No rule combines them | DATA_FLOW §1; RESEARCH_GAP_ANALYSIS §5; EVALUATION_PROTOCOL §1 | The core RQ2 hypothesis has no defined numerator or denominator. The answer could change with the definition | Define the formula before freezing. Consider counting tshark and aggregation CPU time as well as wall time |
| **F-04** | **Incompatible clocks.** `t_*` stamps use `perf_counter_ns()`, while `capture_to_parse` compares them with `frame.time_epoch`, a wall-clock value. The protocol calls these "the same host clock". `perf_counter` has an undefined reference point | DATA_FLOW lines 28, 32; EVALUATION_PROTOCOL §6 | The capture stage cannot be calculated as specified | Use a wall-clock stamp for that comparison, and `perf_counter_ns` for intervals inside the process |
| **F-05** | **Episode bootstrap vs. one episode.** CIs resample attack episodes and benign blocks, but MQTTset probably has one episode per class (R3 rates this likelihood 3 of 3). The primary comparison, S-rand vs. S-time, would run there | MODEL_EVALUATION §2; EVALUATION_PROTOCOL §3, §8; RISKS R3 | CIs may be degenerate for the primary H1 comparison. O1 and the charter require CIs | Define a CI method for single-episode data before freezing |
| **F-06** | **Threshold chosen on data the model has seen.** The pipeline refits on TRAIN+VAL, then selects the threshold on VAL | TRAINING_PIPELINE §1 steps H, I | The threshold is optimistic and the FPR target is unreliable. This is a leakage issue inside a leakage study | Reorder or hold out a threshold set. S3 + S6 decide |
| **F-07** | **A priority paper has no reader.** P23 (Kitsune) is a Phase 00 priority read and a named novelty risk, but it is "optional, abstract level is sufficient" and unassigned | PHASE_00 task 2; RISKS R1; RESEARCH_GAP_ANALYSIS §7; TEAM §2; PAPER_MATRIX P23 | The paper most likely to have measured a full pipeline on a Raspberry Pi could go unread before the gap is frozen | Assign an owner and record the reason, as a team decision |
| **F-08** | **Hypothesis decision rules are missing.** H1 does not say how results combine across models and datasets, and Δ is open. H2 has no CI rule. H3 has no margin or test ("higher") | RESEARCH_GAP_ANALYSIS §5; RESULTS_TEMPLATE Tables 1, 6; DEC-03 | Results could be interpreted after the fact, which pre-registration is meant to stop | Add rules to the protocol before freezing |
| **F-09** | **T3 conflicts with the window rule.** SlowITe works by holding quiet connections, but "sources with zero packets produce no row" and "idle sources are not classified". F22 carries over only in windows where a row exists | FEATURE_SPECIFICATION §3 lines 56–57; THREAT_MODEL §3–4; ADR-04 | The attack class called hardest may be structurally unobservable in many windows | S6 + S4 define handling for open idle connections, then bump `fx` |
| **F-10** | **The deployed and E5 model's training data is undefined.** E5 says "trained models". The P1 example implies MQTTset. DATASET_SELECTION mentions a "lab-trained condition" that has no experiment ID | EVALUATION_PROTOCOL §4; DASHBOARD_SPEC P1; DATASET_SELECTION §4; PHASE_06 | H3's meaning and the demo's behaviour both depend on it. A dataset-trained model may not fire on lab T5, yet the storyboard assumes it will. No risk entry covers this | Decide and pre-register it. Add a demo-detection risk |
| **F-11** | **Lab detection has no experiment.** Time-to-detect and alert-level recall are required metrics, and the storyboard cites them "from E5/E3". E5 is benign-only, and E3's outputs are latency and throughput | MODEL_EVALUATION §5; EVALUATION_PROTOCOL §4–5; DEMO_STORYBOARD §4 | Whether the gateway detects lab attacks is not formally measured | Extend an experiment or add one with an owner |
| **F-12** | **The CPU measurement may miss capture work. [verify on device]** PIDs are "tshark, Python IDS, mosquitto". Live tshark normally does capture through a `dumpcap` child process | EVALUATION_PROTOCOL §7 | Understates capture cost, the quantity RQ2 exists to expose | Sample the process tree, and confirm during the pilot |
| **F-13** | **M1 criteria are scattered.** The roadmap omits items that other documents require by M1 | See §4.1a | Different people could declare M1 met on different grounds | Consolidate into one checklist (the handover §15 gives a draft) |

**§4.1a Items required by M1 but missing from the roadmap's M1 row:** ADR approval (DEC-04); novelty-risk disposition and the alert threshold target (PHASE_00); event contract frozen (PHASE_05, TEAM §4); threat model checked against the specifications (THREAT_MODEL status); final dataset selection (DATASET_SELECTION); Q-02, Q-03, Q-04 (DECISIONS).

### 4.2 Medium severity

| ID | Finding | Evidence |
|---|---|---|
| F-14 | **"8 sources read in full" vs. 5.** The matrix and references show exactly 5 at FT level: P08, P09, P19 (thesis), P20 and P22 (dataset pages only). The search log also lists 5 fetched pages. Which 8 is UNKNOWN | RESEARCH_GAP_ANALYSIS §8; LIMITATIONS; PAPER_MATRIX; SEARCH_PROTOCOL §3 |
| F-15 | **"18 papers not read in full" undercounts.** VERIFIED: 31 of 36 are below FT. 18 are assigned (one is P19's journal version, whose thesis is already FT), leaving 14 unassigned below FT. SEARCH_PROTOCOL §8 wants all MD/AB read, TEAM says optional papers can stay at abstract level, and the DoD requires FT for every quoted result. The report's planned citations include optional papers, such as P33 and P31 | PHASE_00 §1; BLUEPRINT §7; TEAM §2; DoD; PHASE_07 task 3 |
| F-16 | **P16 is cited despite its flag.** Exclusion code E5 means "flagged, not cited for results", yet its 0.95 appears as [R] and it supports HistGB | SEARCH_PROTOCOL §5; REFERENCES notes; LITERATURE_REVIEW §2; MODEL_SELECTION §1 |
| F-17 | **S-rand vs. "never over rows".** Data dictionary: splits are "never over individual rows". Protocol: S-rand is over windows | DATA_DICTIONARY §3; EVALUATION_PROTOCOL §3 |
| F-18 | **E9 is scheduled before its dependency.** E9 includes "E3 at the nominal rate", but sits in Phase 03/M3 and the tracker lists only E1 as a dependency. E3 happens in Phase 04/M4 | EVALUATION_PROTOCOL §4; ROADMAP; TRACKER |
| F-19 | **E7 optional or mandatory?** The gap analysis says optional; M4 requires it completed. E8 is the optional one elsewhere | RESEARCH_GAP_ANALYSIS §2; ROADMAP M4; EVALUATION_PROTOCOL §4 |
| F-20 | **Reproducibility check timing.** "Before M5" vs. Phase 07, which starts after M5 | EVALUATION_PROTOCOL §9; PHASE_07; ROADMAP M6 |
| F-21 | **"Replay" has two meanings.** E3 "replays" lab traffic while `replay` is reserved for event provenance. The provenance of an E3 run is not stated. E3 also needs real broker load: `tcpreplay` suits the parity test, but replayed TCP without real sessions may not exercise the broker **[verify on device]** | EVALUATION_PROTOCOL §4; PHASE_04 §8; DATA_FLOW §3 |
| F-22 | **Storyboard honesty conflicts.** (a) "Every particle is a real MQTT message", but density is proportional to log(rate) and capped. (b) Scene 7's script states the H2 outcome before it has been measured | DEMO_STORYBOARD §3; VISUAL_CONCEPT §3 |
| F-23 | **Circular rate caps.** Phase 02 attack caps use capacity measured in PILOT-E3, which runs in Phase 04, after M3 | PHASE_02 §6; THREAT_MODEL §7; TRACKER |
| F-24 | **Latency budget vs. k = 2.** `end_to_end` runs from the first packet of the triggering window, and is called what "an operator experiences". With k = 2 the operator's delay from attack start is about two windows. The W + 1 s budget can pass while real delay is near 2W | SYSTEM_ARCHITECTURE §5; DATA_FLOW §1; MODEL_EVALUATION §5 |
| F-25 | **Threshold with multi-class output is undefined.** The alert rule uses one score and τ for a target FPR, while `prediction` can be multi-class. Whether the deployed model is binary or family-level is also unspecified | MODEL_EVALUATION §5; MODEL_SELECTION §3; DATA_FLOW §3.2 |
| F-26 | **HistGB evidence. [verify]** "Decision-path contributions" and a test that they sum to (score − base value) are specified for all tree models. HistGB does not expose trees the way DT/RF do, and its contributions sum in raw log-odds. `shap` is unapproved | MODEL_EVALUATION §6; TESTING U10; MAPPING row "Operators need evidence" |
| F-27 | **CICIoMT2024 anonymisation has no owner.** Source-keyed windows and labels need real source IPs. FEATURE_SPECIFICATION says "check", with no ID. Its network-tap vantage point also differs from broker-side capture, which is this audit's observation and is not discussed in the documents | FEATURE_SPECIFICATION §5; DATA_QUALITY §4; PAPER_MATRIX P22 |
| F-28 | **Exact device is open, and results depend on it.** "Pi 4 or Pi 5" remains open while the budget assumes a 4 GB Pi 4. ADR-07 allows AP or host-only networks, while E3 requires wired Ethernet on a physical gateway | ADR-06; SYSTEM_ARCHITECTURE §5; ADR-07; EVALUATION_PROTOCOL §6; Q-02; Q-03 |
| F-29 | **T7 is half in scope.** The BPF is `tcp port 1883`, so scans of other ports and UDP scans are not captured, yet F03/F04 cite T7 and the matrix rates it "easy". It is excluded from harmonised labels. E8 on port 8883 would also need a different filter | SYSTEM_ARCHITECTURE C4; FEATURE_SPECIFICATION §2; DATASET_SELECTION §3; THREAT_MODEL §4; ADR-08 |

### 4.3 Low severity

| ID | Finding | Evidence |
|---|---|---|
| F-30 | "O(1) state per source" is untrue for distinct-count features and the per-connection keep-alive map | FEATURE_SPECIFICATION §2, §3 |
| F-31 | F22 is defined by CONNECTs in the window, but also as carried across windows | FEATURE_SPECIFICATION §2, §3; TESTING U3 |
| F-32 | `traffic_source` includes `mixed` in one document only | DATA_FLOW §3.1; SYSTEM_ARCHITECTURE §2 |
| F-33 | `calibration_ece` is read from the model card but is not in the model-card schema | MAPPING; DATA_DICTIONARY §6 |
| F-34 | P4 shows 4 stages; DATA_FLOW defines 6 latency values, with no mapping | DASHBOARD_SPEC P4; DATA_FLOW §1 |
| F-35 | Talk minutes add up to 23 for a "20 min talk". The demo is 8 min in one document and 8–10 in the other | PRESENTATION_PLAN; DEMO_STORYBOARD |
| F-36 | Priority lists differ: P15 is top priority only in the literature review | LITERATURE_REVIEW §7; PHASE_00; RISKS R1 |
| F-37 | Rehearsal rule: "3 clean" vs. "recovery steps allowed" | ROADMAP M5; PHASE_06 §9; DoD |
| F-38 | T6 evidence differs: "described for CICIoMT2024 [U]" vs. "not clearly present". Also, F13/F19/F24 are T6-rationale inputs to the model, while T6 is "rule, not ML" | LITERATURE_REVIEW §1; THREAT_MODEL §3 |
| F-39 | Edge-IIoTset is a "benign-shift probe" and tagged RQ3, but no experiment uses it | DATASET_SELECTION §2; PAPER_MATRIX P21; EVALUATION_PROTOCOL |
| F-40 | Broken or stale references: `#6-novelty-risks` (now §7); protocol "§10" for change log (it is §11); `configs/E1b.yaml` (no E1b exists); `time_blocked` vs. canonical `S-time` | SEARCH_PROTOCOL line 102; EVALUATION_PROTOCOL line 3; TRAINING_PIPELINE line 35; DATA_DICTIONARY §3 |
| F-41 | **ID collisions:** `S1/S2` = standards and students; `T1…` = attacks and matrix themes; `E1–E5` = exclusion codes and experiments; `Q1…` = search queries, DQ checks, and open questions. The blueprint warns only about P1 vs. P01. S5's task says "indicators for P6", meaning the panel, beside paper P06 | REFERENCES; PAPER_MATRIX; SEARCH_PROTOCOL; TEAM §2 |
| F-42 | S2 co-writes the extractor ("with S2") and also reviews it, which weakens four-eyes | TEAM §1, §5 |
| F-43 | Ownership wording: E3/E4 are S4 + S6 in the tracker and S4 in TEAM §1 | TRACKER; TEAM §1 |
| F-44 | Setup omissions: `pytest`, `matplotlib`, `tcpreplay` are used but not installed. `requirements.txt` vs. `requirements.lock.txt`. Pinning from x86 to ARM is untested | SETUP_GUIDE §3–4; PHASE_03–04; EVALUATION_PROTOCOL §9 |
| F-45 | **[verify on device]** Inline comment on the `listener` line may fail in Mosquitto config. "Answer No" to tshark's prompt may defeat the `wireshark` group step. `log_type all` may inflate broker cost during E3/E4. Combining rotating PCAP output with field streaming, and live 1 Hz drop counts, are unproven tshark assumptions | SETUP_GUIDE §3–4; SYSTEM_ARCHITECTURE C4; DATA_FLOW §3.4 |

## 5. Outdated information

| Item | States | Now (VERIFIED, 2026-10-31) |
|---|---|---|
| SETUP_GUIDE §1, §2; PHASE_00 task 6 | "Not a Git repository"; `git init` needs team approval | A repository exists: one commit, `bd8c85d`, 2026-10-21, no remote configured. DECISIONS.md has no approval entry |
| SETUP_GUIDE §2 | Recommends `.gitignore` entries | No `.gitignore` exists. **Add one before any data, PCAP, or `.env` file appears**, because datasets must never be committed |
| README, BLUEPRINT status | Dated 2026-10-20 | Still accurate in substance |
| Environment table | Python 3.13.7; tshark, Mosquitto, Docker not installed | Python and tool absence reconfirmed. Package versions and Node version not rechecked |
| ADR-05, C8 | Packages "already installed" | True of Anaconda only. The recommended WSL2 venv starts empty |

## 6. Missing documentation

**Overdue or needed for M1 (not present, and not clearly scheduled):**
- Written decision rules for H1–H3 (F-08), and a defined H2 formula (F-03).
- A fallback research plan if D-01 fails (F-02).
- A consolidated M1 checklist (F-13).
- Named team and skills (Q-01), and course deadlines (Q-05): UNKNOWN.
- A record of the supervisor's approval, ethics, and safety decision (Q-04): no form or template exists.
- A decision record for the existing Git repository, plus a `.gitignore`.

**Expected later, correctly absent now:** `research/reviews/*.md`, `reports/CLAIM_AUDIT.md`, `data/SOURCES.md`, `data/MANIFEST.sha256`, `results/`, `configs/`, `requirements*.txt`, the lab network diagram, the Phase 02 benign scenario files, and the rehearsal log.

**Coverage gaps with no planned document:** a demo-failure risk if the model does not detect lab attacks (F-10); a risk entry for CICIoMT2024 IP anonymisation (F-27); and a repeat of the access-level check, since `FT` in the matrix covers both papers and dataset pages.

## 7. Unresolved references

| Reference | Status |
|---|---|
| `RESEARCH_GAP_ANALYSIS.md#6-novelty-risks` | Broken anchor (the only one found by the link check) |
| `docs/research/reviews/<ID>.md` | Planned, does not exist yet |
| `results/*`, `data/*`, `configs/*`, `src/ids/*`, `lab/*`, `dashboard/*`, `replay/*`, `deploy/*`, `tools/*` | Planned, none exist (consistent with no implementation) |
| `configs/E1b.yaml` | Illustrative only; no such experiment |
| "8 sources read in full" | Cannot be traced to a list (F-14) |
| P19 journal version | Cited with DOI, not yet read. Thesis-derived claims are not confirmed against it |

## 8. Areas requiring supervisor approval

| Topic | Reference |
|---|---|
| Project scope and safety; charter sign-off (table is blank) | PROJECT_CHARTER |
| Final title (with the team) | DEC-05 |
| Raspberry Pi availability or purchase, else the labelled fallback | Q-02, R4 |
| Isolated lab type: physical switch or AP vs. host-only | Q-03 |
| Ethics or safety approval for attack traffic | Q-04 |
| Attack script safety review (with S1) | TEAM §5 |
| Report format and presentation format | Q-06, Q-07 |

**Team approvals pending:** DEC-01, DEC-02, DEC-03, DEC-04; the items in TEAM §6.

## 9. Areas requiring further literature verification

| Priority | Item | Why |
|---|---|---|
| 1 | P19 **journal** version | Could add edge deployment. The split, latency, and 37× inference come from the thesis. S1 |
| 1 | P23 Kitsune | Possible full-pipeline RPi measurement; no owner (F-07) |
| 1 | P27 | Does its latency include feature extraction? Closest edge competitor. S6 |
| 1 | P14 | Cross-dataset claim could pre-empt RQ1 [U]. S1 |
| 1 | P17 | May include grouped splits; explanation overlap. S1 |
| 2 | P24 | CPU and RAM numbers known only via P26 [U]. S6 |
| 2 | P13 | Results known only second-hand; split unknown. S3 |
| 2 | P15, P18 | Dataset and PCAP availability (D-02, D-03); fallback candidates. S2 |
| 2 | P01, P02, P03, P05, specifications S1 and S2 | Threat model is provisional until reviewed. MQTT basics are tagged [I]. S4 |
| 2 | **Round-2 search** of IEEE Xplore, ACM DL, Scopus, plus forward citations | Not yet searched directly; the gap holds only for the reviewed literature |
| 3 | P04 (SlowITe), P33, P31, P30, P25, P26 | Abstract level, but relied on for design or planned citations (F-15) |
| 3 | P16 peer-review status; P13 author name; BCCC dataset name; P03 year | Noted in REFERENCES.md |
| 3 | tshark MQTT field names | Unverified until a tshark install (FEATURE_SPECIFICATION §1) |

## 10. Readiness assessment

| Question | Answer |
|---|---|
| Is M0 complete? | **No.** Not recorded. Names (Q-01) and deadlines (Q-05) are open; DEC-01 is pending |
| Can Phase 00 begin? | **Yes.** It has no phase dependency and needs no installation. Assignments are role-based, so names are needed first |
| Is M1 achievable from the current documents? | **Only after protocol fixes.** F-01 to F-13 should be resolved or explicitly accepted before the protocol is frozen, because freezing locks them in |
| Is any existing document wrong about the project's core? | **No.** The findings concern consistency and measurement detail, not the research direction |

## 11. Addendum: Phase 00 planning findings (2026-10-31)

**Prepared by:** Claude Code (AI assistant), for team review. **Nothing in this section is an accepted decision.** No existing finding was renumbered, and no D-xx, Q-xx, or DEC-xx status changed. The original audit is §1–§10 above.

**Sources and access:** this round opened the primary sources below, unlike §2.
- Kaggle's public metadata for MQTTset (no dataset file was downloaded for this section).
- The MQTTset paper (P08) and the CICIoMT2024 page.
- P14 (accepted manuscript) and P23 (arXiv v1), read through a rough text extraction that lost some lines. **Their readers must verify every figure. Neither paper counts as reviewed.**
- P27: abstract only. P17 and the P19 journal version: the publisher redirected to a login, so no content was read.

### 11.1 Evidence on existing items

| Item | Evidence | Status of the item |
|---|---|---|
| D-01 (F-01) | Kaggle's file list (dataset version 5, updated 2021-07-14, 9,570,862,030 bytes in total) names `Data/PCAP/capture_1w.pcap` and five attack captures: `bruteforce.pcapng`, `capture_flood.pcap`, `capture_malariaDoS.pcap`, `malformed.pcap`, `slowite.pcap`. P08 says the dataset is "released both as CSV and PCAP raw data" [R]. PCAP contents were inspected later; see §12 | **Still open** |
| D-01, attacker | No attacker IP appears in Kaggle's description or the part of P08 read verbatim (truncated). Broker 10.16.100.73; sensor IPs are listed | Open; check in the PCAPs |
| R3 | One file per attack type. This suggests one episode per class, but a file could hold several | Open |
| D-04, MQTTset | Kaggle lists the licence as CC BY-NC-SA 4.0. The dataset README states Apache License 2.0 (F-58) | Open; S2 to resolve |
| D-04, CICIoMT2024 | The official page states no licence or terms | Open; enquiry needed |
| F-12 | Wireshark source notes describe a parent process spawning a capture child | Open; verify on the device |
| F-27 | The page does not mention IP handling. It confirms a network tap and that MQTT attacks ran against "MQTT simulated devices" | Open |
| Q4 preview | Kaggle file sizes match P08 Table 3 exactly for four attack captures. **`slowite.pcap` differs: 807,678 bytes vs. 972,272** | Open; check under Q4 |

### 11.2 New findings

| ID | Severity | Finding | Evidence | Consequence |
|---|---|---|---|---|
| **F-46** | High | **Very few attack windows (corrected with measurements, §12.2).** At W = 5 s the five attack PCAPs yield **566 rows: `bruteforce` 442, `flood` 69, `malformed` 54, `lowrate` 1**. S-time test rows are 81, 9, 10, and 0. The earlier estimate from P08's durations (about 672 windows) is withdrawn | Measured PCAP aggregates; EVALUATION_PROTOCOL §3 | With four classes, one missed flood window moves macro-F1 by about 0.015 [calculated], so Δ = 0.05 equals about 3–4 flood or malformed errors. CIs may be wide and H1 inconclusive |
| **F-47** | High | **F-04 is wider than recorded.** `processing_total` and `end_to_end` also subtract wall-clock values from `perf_counter_ns` stamps | DATA_FLOW §1 | These stages cannot be computed as specified |
| **F-48** | High | **S-episode conflicts with the RQ1 training rule.** The protocol applies S-episode to lab data, yet lab data must never enter RQ1 training. If MQTTset has one episode per class, S-episode may never run under E1 | EVALUATION_PROTOCOL §3–4; DATASET_SELECTION §4 | RQ1's session-held-out arm has no valid home |
| **F-49** | High | **The statement that MQTT papers evaluate within one dataset is wrong as written.** P14 trains on its own testbed and validates on MQTT-IoT-IDS2020, merged with a public DoS/MitM set. RF brute-force F1 is 88.74 in cross-validation and 76.38 in validation [R, Tables VIII, IX; verify]. No gateway or per-stage timing was found | RESEARCH_GAP_ANALYSIS §1–2; LITERATURE_REVIEW §5 | The cross-dataset wording needs narrowing. The combination claim is not affected by this paper alone |
| **F-50** | Medium | **E5 uses optional stopping.** A second run happens only if FPR exceeds 1%, which also conflicts with "a single run is never a result" | EVALUATION_PROTOCOL §4, §8 | FPR results could be biased |
| **F-51** | Medium | **Capture-level shortcut risk.** Benign traffic and each attack sit in separate files, so F25 and F26 (broker-wide context) could identify the capture rather than the attack | Kaggle file list; FEATURE_SPECIFICATION §2 | Could inflate results under every split (hypothesis; no model has been run). §12.2 records the measured F26 separation |
| **F-52** | Medium | **P23 may be a pipeline-throughput precedent.** It reports about 1,000 to 5,400 packets/s on a Raspberry Pi 3B, single core, for k = 1 to 35 [R; verify]. Whether parsing and capture are included is not established. It is not MQTT-specific | P23 evaluation section | G2 must cite it fairly. Adds weight to F-07 |
| **F-53** | Low | **The suggested `data/` ignore pattern is too broad.** It would also match `docs/data/`. The committed `.gitignore` is anchored instead | SETUP_GUIDE §2 | SETUP_GUIDE §2 needs a wording fix |

### 11.3 Recommendations awaiting decision (all PROPOSED)

Each row is the assistant's recommendation only. The experiment impact and approver are given so that the team can decide.

| ID | Recommendation | Impact on experiments | Approver |
|---|---|---|---|
| D-01 / F-01 | Answer D-01 before the freeze. Pass only if the PCAPs show stable source IPs, timestamps, and an identifiable attacker | Sets the primary dataset, E1, E2 | Team; S2 executes |
| F-02 | Write a tiered fallback. **A:** current plan. **B:** MQTT-IoT-IDS2020 and CICIoMT2024 within-dataset, with P15 as a `flood` cross target if D-02 passes. **C:** binary cross-test only, labelled as attack-family shift. `lowrate` is lab-only in B and C | RQ1 wording, E1, E2 in B or C | Team + supervisor |
| F-03 | H2 primary metric: CPU-time share per run, `(C_capture + C_extract) / (C_capture + C_extract + C_inference + C_alert)`. Wall-clock share is secondary. H2 applies to a tshark-based pipeline only | E3 needs per-stage CPU timers | Team (S6 + S4) |
| F-04 / F-47 | `perf_counter_ns` for in-process intervals, `time_ns` for wall-clock comparisons, a paired clock anchor at run start, NTP off during runs | Timer code, data dictionary | S4 + S6 |
| F-05 | Episode bootstrap where ≥3 episodes exist. Otherwise a moving-block bootstrap on consecutive windows: 60 s blocks, 30 s and 120 s sensitivity, 1,000 resamples, labelled "conditional on one capture". Bootstrap S-rand and S-time test sets independently for the Δ CI | CIs cannot generalise across episodes | Team (S3) |
| F-06 / F-25 | Remove the refit: train on TRAIN, tune and set τ on VAL, test once. `score = 1 − P(benign)`; at `score ≥ τ` assign the top attack class, otherwise benign. S-cross uses the same inner split of A | Less training data; pipeline diagram changes | S3 + S6, then team |
| F-07 / F-52 | Assign P23 to S4, cross-checked by S5 | 19 reviews rather than 18 | Team |
| F-08 | Three outcomes for each hypothesis: supported, rejected, inconclusive. **H1** (S-rand − S-time, primary dataset, ≥3 of 4 models): CI lower bound > Δ / upper bound < Δ. **H2** (DT, RF, HistGB at the nominal rate set before E3): share > 0.5 in all 3 repetitions for all three models / ≤ 0.5 in all / otherwise inconclusive. **H3** (dataset-trained model, same τ, pooled scenarios): lab lower bound > test upper bound + 0.01 / lab upper bound ≤ test upper bound | Fixes interpretation before any result exists | Team |
| F-09 | Measure the share of attack-interval windows with no attacker packets. Above 20%, adopt `fx-0.2` (rows for open connections, new `open_conns` feature); otherwise keep `fx-0.1` and report the share. Close windows by timer | A 27th feature needs approval; benign rows and FPR denominators change | Team (S6 + S4) |
| F-10, F-11, F-48 | **Proposed E10, lab detection (owner S6).** A: dataset-trained model on scheduled lab attacks. B: lab-trained model under S-episode, reported separately, never in RQ1 training. The dataset-trained model answers H3. A lab-trained model may run the demo only if the dataset-trained model fails and the team agrees, shown in P1. E5 scenarios stay out of its training | Adds a run set and a risk entry. E10 is **not** in the tracker | Team + supervisor |
| F-12 | Sample the tshark process tree, plus system-wide CPU against the no-IDS baseline | E3, E4 | S4 |
| F-13 | Adopt one consolidated M1 checklist | Single gate definition | Team; S1 |
| F-18, F-23 | Split E9 into offline (M3) and gateway (M4) parts. Use a conservative fixed rate cap until PILOT-E3 | E9, Phase 02 | S3, S4 |
| F-27 | Inspect one PCAP after D-04. Stable pseudonyms are acceptable; if IPs are randomised, use file-level labels and exclude source-level families | Could reduce E2 to binary | S2; team if E2 changes |
| F-46 | Report test-window counts beside every F1. Set a minimum per class (proposed 30), below which the class is descriptive | E1, E2, reporting | Team |
| F-49 | Narrow G4 and LITERATURE_REVIEW §5 after S1 verifies P14 | Gap v1.0 | S1, then team (DEC-02) |
| F-50 | Fixed 2 runs per E5 scenario | About 6 h of runs for six scenarios | Team |
| F-51 | Inspect F25 and F26 explicitly under Q6 and Q11 | Data-quality reports; may affect features | S2 + S3 |

## 12. Addendum: measured D-01 evidence (2026-10-31)

**Prepared by:** Claude Code (AI assistant), for team review. **Nothing in this section is an accepted decision. D-01 remains Open.** No D-xx, Q-xx, or DEC-xx status changed.

**Evidence base:** read-only inspection of all six MQTTset PCAPs and three author reference files, using temporary standard-library parsers. **tshark was not used, so MQTT-level figures are not independently confirmed.** No model was trained. The reports and aggregates are kept outside Git, on the coordinating laptop, in `C:\Users\aksha_q43exq6\edgewatch-data\reports\`:

| Report | Covers |
|---|---|
| `D-01_evidence_report.md` | `slowite`, `bruteforce` |
| `D-01_remaining_attack_captures.md` | The other three attack captures |
| `D-01_benign_capture_report.md` | `capture_1w` |
| `D-01_leakage_and_option_b_analysis.md` | Leakage analysis, Option B |
| `D-01_original_processing_audit.md` | README and two author scripts |
| `D-01_team_decision_brief.md` | Supervisor summary |

Where those reports disagree, the later one prevails. Each older report carries a superseded-status notice. A full index is in `reports\team-review\D-01_EVIDENCE_INDEX.md`.

### 12.1 Raw PCAP availability (measured)

| Capture | Packets (matches P08) | Measured duration | P08 duration | Rows at W = 5 s |
|---|---:|---:|---:|---:|
| `capture_1w` | 11,915,716 (yes) | 7 d 0 h 5 min | One week | 655,535 |
| `bruteforce` | 14,501 (yes) | 37:17 | 30:00 | 442 |
| `capture_flood` | 613 (yes) | 3:27 | 05:00 | 42 |
| `capture_malariaDoS` | 130,223 (yes) | 2:07 | 05:00 | 27 |
| `malformed` | 10,924 (yes) | 6:15 | 06:00 | 54 |
| `slowite` | 9,202 (yes) | **0.697 s** | 10:00 | **1** |

All six files parsed completely and contain IP addresses and timestamps. Timestamps are ordered except for small reversals (at most 38 µs) in `capture_flood` and `capture_1w`.

### 12.2 Corrected F-46 figures (measured; rows follow the `fx-0.1` no-row rule)

| Family | Rows W = 1 s | Rows W = 5 s | Rows W = 10 s | S-time at W = 5 s: train / val / test |
|---|---:|---:|---:|---|
| `benign` | 3,114,630 | 655,535 | 352,985 | 393,315 / 131,085 / 131,095 |
| `bruteforce` | 1,454 | 442 | 224 | 268 / 87 / 81 |
| `flood` (two captures) | 229 | 69 | 35 | 41 / 7 / 9 |
| `malformed` | 144 | 54 | 34 | 30 / 9 / 10 |
| `lowrate` | 1 | 1 | 1 | 0 / 0 / 0 |

Benign rows outnumber attack rows by about 1,158 to 1 at W = 5 s [calculated]. S-time counts use a working rule (blocks at 60% and 80% of measured duration, whole windows, a 2W gap before validation and test), which is **not** a protocol change. At W = 10 s, `capture_malariaDoS` has no validation or test rows.

### 12.3 Measured facts versus unverified hypotheses

| Measured (parser only; no tshark) | Unverified hypothesis (no experiment) |
|---|---|
| **F26 is 5 or 10 in all benign rows and 1 in all attack rows** at W = 5 s; benign minimum 5 at W = 1 and 10 s | F26 or F25 would change a model's scores |
| Each attack file holds one client, and no file holds attack and benign traffic together | A live attack with other clients active would show F26 above 1 |
| Three capture setups, by broker address and link type; only `capture_flood` shares the benign setup | Other features (for example F03, F06, F09, F14, F16–F20) separate captures at window level |
| `malformed.pcap`: no invalid framing or violations of the selected MQTT 3.1.1 rules | tshark would agree, or that the file holds no malformed packets by any definition |
| `capture_1w`: 10 clients, one connection each, near-constant hourly volume, no attack-like counts | The file is purely benign; the clients came from one generator run |

### 12.4 New findings

| ID | Severity | Finding | Evidence | Consequence |
|---|---|---|---|---|
| **F-54** | High | **Author labels are file-level.** `rawparsing_normal.py` sets one constant `target` value per CSV. It has no packet-level check, attacker address, or time interval. Broker replies and TCP-only packets receive the file's label. Labels are author assignments, not verified ground truth | Original processing audit §3 | Use them as provenance only. Project labels follow DATA_QUALITY_PROTOCOL §4 |
| **F-55** | High | **PCAP-to-CSV conversion is undocumented in the inspected files.** The link is inferred from file names. Neither script reads a PCAP or calls tshark. The code implies only the combined CSV drops IPs and absolute times, so the per-file CSVs may retain identity or other sensitive fields [inferred; **no CSV has been opened**] | Audit §3–4 | FEATURE_SPECIFICATION §5 corrected accordingly. Handle per-file CSVs under privacy rules |
| **F-56** | High | **Payload is a retained feature.** `mqtt.msg` is among the script's 33 retained fields, along with `mqtt.willmsg` and `mqtt.willtopic`. `tcp.time_delta` is also retained, and capture identity is not addressed. **This comes from the script; the published CSVs have not been opened.** The effect on models is unmeasured | Audit §4, §6 | **E1-a uses published CSVs, but the project's rule says payload bytes are never features.** Team decision needed |
| **F-57** | Medium | **Limits in the inspected `processingdata_ml.py`:** train and test category-encoded separately; test data used for neural-network early stopping; cumulative "training time"; weighted F1. **Whether this code produced the published results is not established**, so these are limits of the inspected scripts, and they say nothing about the validity of published scores | Audit §2 | Do not reuse the script |
| **F-58** | Medium | **Licence discrepancy.** README: Apache License 2.0. Kaggle: CC BY-NC-SA 4.0. Applicable licence and redistribution rights are unresolved | Audit §2, §7 | D-04 stays open; DATASET_SELECTION §2 and §6 corrected. Follow the stricter practical limits meanwhile |
| **F-59** | High | **`lowrate` cannot be split.** `slowite.pcap` yields 1 row at every W, so S-rand, S-time, and macro-F1 cannot include it as specified. Its holding phase is not visible, so **the F-09 measurement cannot be made from this file** | §12.1, §12.2 | Five-class macro-F1 is not computable as written |
| **F-60** | High | **`malformed` is not shown to contain malformed packets** (see §12.3). `F23` remains unavailable without tshark | §12.3 | Class meaning and E2 equivalence with CICIoMT2024 are unproven |

### 12.5 Other author-document differences

| Topic | Paper or README | Inspected scripts or measurement |
|---|---|---|
| Mixing seed | P08: 7 | `rawparsing_normal.py` shuffles with 10; `processingdata_ml.py` uses 7 for a commented-out split and some models |
| Sensors | "8" in text; 10 in Table 2 | 10 clients measured |
| Sensor rates | Table 2 | Differ for 6 of 10 sensors |
| "Mix" | Combined legitimate and malicious traffic | Row concatenation and shuffle; no traffic injection in the inspected code |
| Reduced and augmented sets | Described | Creation code not inspected |

**This audit does not claim that any published MQTTset score is invalid or inflated.** F25 and F26 are this project's features and are absent from the authors' pipeline. No published result was reproduced.

### 12.6 Recommendations awaiting decision (all PROPOSED)

The assistant's "Option B" and its alternatives are in `D-01_team_decision_brief.md`. Approval rows are in [DECISIONS.md](DECISIONS.md). **Option B is not approved.**
