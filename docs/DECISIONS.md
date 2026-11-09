# Decisions Log and Open Questions

Architecture-level rationale is in [ARCHITECTURE_DECISIONS.md](architecture/ARCHITECTURE_DECISIONS.md). This file records **team decisions** (who decided, and when) and **open questions**.

## Decisions

| ID | Date | Decision | Ref | Decided by | Status |
|---|---|---|---|---|---|
| DEC-01 | 2026-10-20 | Adopt the documentation baseline v0.1 for review | — | (proposed by the AI assistant) | **Pending team approval** |
| DEC-02 | | Approve the gap, RQ1–RQ3, H1–H3 | RESEARCH_GAP_ANALYSIS | team | Pending (M1) |
| DEC-03 | | Fix Δ for H1 (proposal: 0.05 macro-F1) | EVALUATION_PROTOCOL | team | Pending (M1) |
| DEC-04 | | Approve ADR-01 to ADR-12 | ARCHITECTURE_DECISIONS | team | Pending (M1) |
| DEC-05 | | Final project title | RESEARCH_GAP_ANALYSIS §9 | team + supervisor | Pending |

## Open questions and blockers

| ID | Question | Owner | Needed by | Status |
|---|---|---|---|---|
| D-01 | Does MQTTset include raw PCAPs with IPs and timestamps? | S2 | M2 | Open, **critical** |
| D-02 | DoS/DDoS-MQTT-IoT PCAP availability and scenario list | S2 | M2 | Open |
| D-03 | MQTT_UAD format and independence | S2 | M2 | Open |
| D-04 | Licence/terms for MQTTset and CICIoMT2024 | S2 | M2 | Open |
| D-05 | Keep `data/` outside OneDrive sync? | S6 | Phase 01 start | Open (recommended: yes) |
| Q-01 | Team member names and skills, to map onto S1–S6 | all | M0 | Open |
| Q-02 | Is a Raspberry Pi 4/5 available (or can one be purchased)? If not, use the emulated-constraint fallback (ADR-06) | supervisor | M1 | Open |
| Q-03 | Can the lab use an isolated switch/AP, or only a host-only virtual network? | S4 + supervisor | M1 | Open |
| Q-04 | Does the course require ethics or safety approval for attack-traffic generation in a lab? | supervisor | M1 | Open |
| Q-05 | Course deadlines, to set milestone dates | all | M0 | Open |
| Q-06 | Report format (paper-style? page limit?) | supervisor | M3 | Open |
| Q-07 | Presentation length and format | supervisor | M4 | Open |
| Q-08 | Approval to install WSL2, tshark, Mosquitto, and paho-mqtt on the dev machines | each owner | Phase 01 | Open |

## Audit findings raised for decision (2026-10-31)

**These are recommendations by the AI assistant, not decisions.** The tables above stay authoritative, and their statuses are unchanged. Details and evidence are in [DOCUMENTATION_AUDIT.md §11](DOCUMENTATION_AUDIT.md#11-addendum-phase-00-planning-findings-2026-10-31). Each row stays `Not decided` until the listed approver records an outcome here, with a date and names.

| ID | Issue | Recommendation (proposed) | Approver | Status |
|---|---|---|---|---|
| F-01 | D-01 is due after the freeze that depends on it | Answer D-01 before the freeze | Team | Not decided |
| F-02 | D-01 fallback leaves almost no family-level cross-dataset test | Written tiered fallback | Team + supervisor | Not decided |
| F-03 | H2 has no computable formula | CPU-time share per run | Team | Not decided |
| F-04, F-47 | Latency stages mix incompatible clocks | Separate clocks, with a paired anchor | S4 + S6 | Not decided |
| F-05 | CI method fails with one episode per class | Moving-block bootstrap, labelled conditional | Team | Not decided |
| F-06, F-25 | Threshold chosen after refit; multi-class score undefined | Remove the refit; `score = 1 − P(benign)` | S3 + S6, then team | Not decided |
| F-07, F-52 | P23 has no reader | Assign to S4 | Team | Not decided |
| F-08 | H1–H3 have no complete decision rules | Supported / rejected / inconclusive rules | Team | Not decided |
| F-09 | T3 may be invisible under the no-row rule | Measure first, with a pre-registered 20% rule | Team | Not decided |
| F-10, F-11, F-48 | Deployed model's training data undefined; lab detection has no experiment; S-episode conflicts with the RQ1 training rule | **Proposed experiment E10** (not in the tracker) | Team + supervisor | Not decided |
| F-12 | CPU sampling may miss capture work | Process tree plus system-wide CPU | S4 | Not decided |
| F-13 | M1 criteria are scattered | One consolidated checklist | Team | Not decided |
| F-27 | CICIoMT2024 IP handling unknown | Inspect one PCAP after D-04 | S2; team if E2 changes | Not decided |
| F-46 | Very few attack windows per class | Report counts; minimum per class | Team | Not decided |
| F-49 | Within-one-dataset statement contradicted by P14 | Narrow the wording after S1 verifies | S1, then team | Not decided |
| F-50 | E5 uses optional stopping | Fixed 2 runs per scenario | Team | Not decided |
| F-51 | F25 and F26 may identify the capture. F26 separation is now measured (audit §12.3) | Inspect under Q6 and Q11; with-and-without comparison | S2 + S3, then team | Not decided |
| F-54 | **Original-label reliability:** author labels are per file, not verified ground truth | Use as provenance only; apply DATA_QUALITY_PROTOCOL §4 | Team | Not decided |
| F-55 | PCAP-to-CSV conversion undocumented; per-file CSVs may retain identity fields | Ask the authors; privacy handling if inspected | S2, then team | Not decided |
| F-56 | **E1-a and `mqtt.msg`:** the inspected script retains payload in the combined CSV, which project rules forbid as a feature (published CSVs not opened) | Exclude content fields and call E1-a a partial anchor, or drop E1-a | Team | Not decided |
| F-57 | Limits in the inspected author scripts | Do not reuse `processingdata_ml.py` | S3 | Not decided |
| F-58 | Licence discrepancy: README vs. Kaggle; redistribution rights unresolved | Resolve under D-04; follow the stricter practical limits meanwhile | S2 | Not decided |
| F-59 | `lowrate` has 1 row; five-class macro-F1 not computable | Exclude from primary macro-F1; test T3 in the lab | Team + supervisor | Not decided |
| F-60 | `malformed` not shown to contain malformed packets | Keep provisionally, with tshark and a three-class sensitivity result | Team | Not decided |
| Option B | Protocol response to the D-01 evidence (decision brief) | Four classes; F25/F26 comparison; S-cross and proposed E10; revised H1 | Team + supervisor | **Proposed; not approved** |

## Evidence recorded against open questions (2026-10-31)

Evidence only. **D-01 and D-04 remain Open.**

| ID | Evidence | Still needed |
|---|---|---|
| D-01: raw-PCAP availability | **Measured by temporary parsers:** all 6 PCAPs parse completely and contain IP addresses and timestamps (audit §12.1) | tshark validation; team review of this evidence |
| D-01: dataset suitability | **Inconclusive.** File-level labels only (F-54); `lowrate` cannot be split (F-59); `malformed` unconfirmed (F-60); measured F26 separation (F-51); benign purity and attacker identity not established | Authors' answers, tshark, S2 review, and a team decision. **A yes on availability would not approve MQTTset as primary** |
| D-04 | **MQTTset licence conflict:** Kaggle lists CC BY-NC-SA 4.0, README states Apache License 2.0. The CICIoMT2024 page states no terms | S2 resolves MQTTset; enquiry to CIC |

Assistant repository action, committed on branch `docs/phase-00-baseline` and awaiting team review: `.gitignore`, the handover, and the audit. This is not the Git decision that M1 requires.

## Decisions needed from the project owner (2026-11-02)

Recorded by the AI assistant during autonomous implementation. **None is decided.** The system runs on the "current" column until they are.

| ID | Decision | Current | Recommendation | Evidence |
|---|---|---|---|---|
| OD-1 | F22: 1.5K expiry plus a hard limit with eviction | **Since 2026-11-09:** the IDS service applies the 65,536 hard limit with an eviction counter (the owner's brief requires bounded state). Exact `fx-0.1` below the limit; offline tables stay unbounded. **The 1.5K expiry is not applied** | Apply 1.5K + 65,536 for live use, with an eviction counter | `edgewatch-data/reports/T3_5_F22_POLICY_EVIDENCE.md` |
| OD-2 | F23 meaning | Adapter-defined; the live decoder signal is recorded in the model card | Tool-independent rule list, `fx-0.2`, before any research table | `edgewatch-data/reports/T3_6_F23_EVIDENCE.md` |
| OD-3 | D-01 and Option B | Open, not approved; all results labelled engineering | Do not use MQTTset as the primary source of a deployed detector; see the transfer result | `docs/reports/FINAL_TECHNICAL_REPORT.md` section 5 |
| OD-4 | Approve `decoder.py` plus dumpcap as the live path instead of tshark | In use for live, labelled as candidate; tshark stays the offline reference | Approve | Report section 3 |
| OD-5 | ADR-10 amendment: React without Cytoscape.js or uPlot | Built that way, as the brief asked | Approve | `docs/architecture/FINAL_SYSTEM_ARCHITECTURE.md` section 5 |
## Owner brief of 2026-11-09 (software-only completion)

Recorded by the AI assistant. **The project owner's brief states the project runs entirely on a Windows laptop: no Raspberry Pi, ESP32, physical network or cloud.** This is recorded as the owner's instruction and as evidence for Q-02 and Q-03; the team rows above are unchanged.

| Effect | Applied as |
|---|---|
| Hardware items (Pi, isolated switch) are out of scope, not blocked | Gateway figures are labelled "Windows software gateway"; nothing claims Pi results |
| Connection state must be bounded | OD-1's hard limit only (row above). OD-1 stays open for the expiry and for formal approval |
| Research decisions stay protected | D-01, Option B, DEC-02 to DEC-05, OD-2 to OD-5 unchanged. New results are labelled engineering (`ENG-C1`, `ENG-R1`, `ENG-P3`, `ENG-E2E-CC`) |

## Decision review, 2026-11-09 (owner approved reversible software-only preparation; protected decisions not overridden)

Recommendations by the AI assistant. **Nothing below changes a protected decision's status.** Rows marked "needs approval" stay as they are until the named approver records an outcome.

| ID | Options | Evidence | Recommendation | Done now (reversible) | Status |
|---|---|---|---|---|---|
| OD-1 | (a) exact, unbounded; (b) hard limit only; (c) hard limit + 1.5 K keep-alive expiry | Hard limit: ENG-P3 (300 k holds, about 25 MiB). Expiry: **0 of 100,370 rows changed on 29 lab runs** (ENG-OD1-expiry), 0 on MQTTset (T3.5). MQTT requires the broker to drop a client after 1.5 K of silence | (c), as a new version `fx-0.1+ka1.5`; let the v6 model read it only after approval, because 0 rows differ on every recording | `FeatureAggregator(keepalive_expiry=1.5)`, opt-in, own version label; `validate_row` refuses it for fx-0.1 models; 4 tests | (b) in service; (c) **needs owner approval** to enable |
| OD-2 | (a) decoder flag, adapter-defined; (b) tool-independent rule list, `fx-0.2` | T3.6: decoder flags a superset of tshark on T4 traffic | (b) before any research table; keep (a) for the deployed engineering model | None. A new F23 changes model inputs, so it needs retraining and its own evaluation | **Needs team approval** |
| D-01 / Option B | Use MQTTset as primary, or Option B (four classes, F25/F26 comparison, S-cross, E10) | DQ-MQTTSET: identity and time alone give macro-F1 1.0; 8 single features above 0.95; ENG-X1: no transfer to lab; ENG-R1: lab splits show no comparable gap | Option B, with MQTTset as a leakage case study, not the source of a deployed detector | None | **Needs team and supervisor** |
| D-04 | Download MQTT-IoT-IDS2020 and CICIoMT2024 under their terms, or proceed without them | MQTTset licence conflict (CC BY-NC-SA vs Apache); CICIoMT2024 states no terms | Resolve terms first. Until then, E2 and S-cross stay not run, and no cross-dataset claim is made | None | **Needs S2 and the dataset owners** |
| DEC-02 | Approve gap, RQ1-RQ3, H1-H3 | Engineering analogues exist for all three RQs (checklist) | Approve, with H1 reworded as in Option B | None | **Needs team** |
| DEC-03 | Δ for H1 = 0.05 macro-F1 | MQTTset gap 0.05-0.09 measured on 9-10 test windows per class | Keep 0.05, but require the episode-bootstrap CI to exclude 0 | None | **Needs team** |
| DEC-04 | Approve ADR-01 to ADR-12 | OD-4 (dumpcap + decoder) and OD-5 (no chart library) are as built | Approve with OD-4 and OD-5 amendments | None | **Needs team** |
| DEC-05 | Final title | Built system is a Windows software gateway | Keep the title; say "software edge gateway" in the abstract | None | **Needs team and supervisor** |
