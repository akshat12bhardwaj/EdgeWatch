# Documentation Audit

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

## 2. Scope and method

Every file under `docs/` was read in full, starting with the blueprint. Related documents were then cross-checked. A script checked all relative Markdown links and anchors (one failure, F-40). `PAPER_MATRIX.csv` was parsed to count access levels and assignments.

**Not checked:** no DOI, dataset page, or paper was opened, so all literature claims are as recorded in the documents. Commands in the setup guide and phase guides were not run. Findings tagged **[verify on device]** rest on general tool knowledge and need a test.

## 3. File inventory (44)

| # | File | Lines | Purpose |
|---|---|---:|---|
| 1 | [README.md](README.md) | 27 | Entry point, status, conventions, layout |
| 2 | [MASTER_PROJECT_BLUEPRINT.md](MASTER_PROJECT_BLUEPRINT.md) | 97 | Authoritative overview, canonical names, confidence table |
| 3 | [PROJECT_CHARTER.md](PROJECT_CHARTER.md) | 46 | Problem, goal, scope, success criteria, constraints, sign-off table |
| 4 | [DECISIONS.md](DECISIONS.md) | 31 | Team decisions (DEC) and open questions (D, Q) |
| 5 | [DEFINITION_OF_DONE.md](DEFINITION_OF_DONE.md) | 30 | Done criteria for tasks, experiments, panels, project |
| 6 | [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) | 32 | M0–M6, acceptance criteria, gate owners, critical path |
| 7 | [RISKS_AND_MITIGATIONS.md](RISKS_AND_MITIGATIONS.md) | 20 | Risk register R1–R14 |
| 8 | [TEAM_WORK_ALLOCATION.md](TEAM_WORK_ALLOCATION.md) | 89 | Roles S1–S6, paper assignments, interfaces, reviews |
| 9 | [TESTING_STRATEGY.md](TESTING_STRATEGY.md) | 49 | Unit, parity, integration, and measurement validation tests |
| 10 | [architecture/ARCHITECTURE_DECISIONS.md](architecture/ARCHITECTURE_DECISIONS.md) | 97 | ADR-01 to ADR-12, all Proposed |
| 11 | [architecture/DATA_FLOW.md](architecture/DATA_FLOW.md) | 115 | Live and offline flows, stage latencies, event contract, storage |
| 12 | [architecture/FEATURE_SPECIFICATION.md](architecture/FEATURE_SPECIFICATION.md) | 84 | `fx-0.1`: tshark fields, F01–F26, window rules, exclusions |
| 13 | [architecture/SYSTEM_ARCHITECTURE.md](architecture/SYSTEM_ARCHITECTURE.md) | 113 | Planes, components C1–C14, deployment views, resource budget |
| 14 | [architecture/THREAT_MODEL.md](architecture/THREAT_MODEL.md) | 79 | Adversary, T1–T7, detectability matrix, lab safety boundaries |
| 15 | [data/DATASET_SELECTION.md](data/DATASET_SELECTION.md) | 71 | Dataset comparison, roles, label harmonisation, blockers |
| 16 | [data/DATA_DICTIONARY.md](data/DATA_DICTIONARY.md) | 54 | On-disk tables, results files, model card |
| 17 | [data/DATA_QUALITY_PROTOCOL.md](data/DATA_QUALITY_PROTOCOL.md) | 47 | Checks Q1–Q12, labelling rules, imbalance rules |
| 18 | [experiments/EVALUATION_PROTOCOL.md](experiments/EVALUATION_PROTOCOL.md) | 104 | Splits, E1–E9, measurement method, threats to validity |
| 19 | [experiments/EXPERIMENT_TRACKER.md](experiments/EXPERIMENT_TRACKER.md) | 28 | Experiment status table and run log; all planned or deferred |
| 20 | [implementation/PHASE_00_RESEARCH.md](implementation/PHASE_00_RESEARCH.md) | 25 | Research validation, leads to M1 |
| 21 | [implementation/PHASE_01_DATA.md](implementation/PHASE_01_DATA.md) | 32 | Data, quality checks, extractor, leads to M2 |
| 22 | [implementation/PHASE_02_TRAFFIC_LAB.md](implementation/PHASE_02_TRAFFIC_LAB.md) | 35 | Isolated lab and traffic generators, leads to M2 |
| 23 | [implementation/PHASE_03_BASELINES.md](implementation/PHASE_03_BASELINES.md) | 33 | Offline evaluation, leads to M3 |
| 24 | [implementation/PHASE_04_EDGE_IDS.md](implementation/PHASE_04_EDGE_IDS.md) | 31 | Gateway service and measurement, leads to M4 |
| 25 | [implementation/PHASE_05_DASHBOARD.md](implementation/PHASE_05_DASHBOARD.md) | 33 | Edge Watch build, leads to M5 |
| 26 | [implementation/PHASE_06_INTEGRATION.md](implementation/PHASE_06_INTEGRATION.md) | 25 | Integration, E5, demo run, leads to M5 |
| 27 | [implementation/PHASE_07_FINAL_VALIDATION.md](implementation/PHASE_07_FINAL_VALIDATION.md) | 24 | Claim audit, reproducibility, report, leads to M6 |
| 28 | [implementation/SETUP_GUIDE.md](implementation/SETUP_GUIDE.md) | 82 | Environment inventory and setup steps (not executed) |
| 29 | [ml/MODEL_EVALUATION.md](ml/MODEL_EVALUATION.md) | 51 | Metrics, uncertainty, calibration, alert policy, evidence |
| 30 | [ml/MODEL_SELECTION.md](ml/MODEL_SELECTION.md) | 37 | Models, exclusions, grids, deployed-model rule |
| 31 | [ml/TRAINING_PIPELINE.md](ml/TRAINING_PIPELINE.md) | 56 | Training steps, rules, suggested layout, library status |
| 32 | [presentation/DASHBOARD_SPECIFICATION.md](presentation/DASHBOARD_SPECIFICATION.md) | 93 | Global behaviour and panels P1–P8 |
| 33 | [presentation/DEMO_STORYBOARD.md](presentation/DEMO_STORYBOARD.md) | 69 | Demo modes, preflight, scenes, recovery |
| 34 | [presentation/PRESENTATION_PLAN.md](presentation/PRESENTATION_PLAN.md) | 50 | Talk narrative, speakers, anticipated questions |
| 35 | [presentation/VISUALIZATION_RESEARCH_MAPPING.md](presentation/VISUALIZATION_RESEARCH_MAPPING.md) | 25 | UI-to-research traceability, rejected elements |
| 36 | [presentation/VISUAL_CONCEPT.md](presentation/VISUAL_CONCEPT.md) | 106 | Design system, motion rules, layout, anti-patterns |
| 37 | [reports/FINAL_REPORT_OUTLINE.md](reports/FINAL_REPORT_OUTLINE.md) | 18 | Report structure |
| 38 | [reports/LIMITATIONS.md](reports/LIMITATIONS.md) | 25 | Known limitations (living document) |
| 39 | [reports/RESULTS_TEMPLATE.md](reports/RESULTS_TEMPLATE.md) | 44 | Empty results tables; no results recorded |
| 40 | [research/LITERATURE_REVIEW.md](research/LITERATURE_REVIEW.md) | 172 | Thematic round-1 synthesis and review template |
| 41 | [research/PAPER_MATRIX.csv](research/PAPER_MATRIX.csv) | 37 | Per-paper details, access level, reviewer |
| 42 | [research/REFERENCES.md](research/REFERENCES.md) | 83 | Bibliography P01–P36, S1–S2, with access level |
| 43 | [research/RESEARCH_GAP_ANALYSIS.md](research/RESEARCH_GAP_ANALYSIS.md) | 92 | G1–G7 verdicts, RQs, hypotheses, novelty risks, title |
| 44 | [research/SEARCH_PROTOCOL.md](research/SEARCH_PROTOCOL.md) | 102 | Search log, criteria, exclusions, round-2 plan |

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
