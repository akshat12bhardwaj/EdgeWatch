# Risks and Mitigations

Scale: likelihood (L) and impact (I) are each rated 1–3. The risks are reviewed at every milestone.

| ID | Risk | L | I | Mitigation | Trigger / owner |
|---|---|---|---|---|---|
| R1 | Unread papers (P14, P17, P19 journal version, P23, P27) pre-empt the gap | 2 | 3 | Phase 00 priority reads; narrow the claim | M1 / S1 |
| R2 | MQTTset has no usable PCAP (D-01) | 2 | 3 | Fall back to MQTT-IoT-IDS2020 as primary, plus CICIoMT2024; contact the authors | Phase 01 / S2 |
| R3 | Only one episode per attack class in the datasets, so S-episode is not possible | 3 | 2 | Use S-time on the datasets and S-episode on lab data; state this explicitly | Phase 03 / S3 |
| R4 | No Raspberry Pi available | 2 | 2 | Emulated-constraint fallback, labelled (ADR-06) | M1 / supervisor |
| R5 | Train/serve skew between offline and live features | 2 | 3 | One module; parity tests offline and on the device | Phase 01, 04 / S6 |
| R6 | Attack traffic escapes the lab | 1 | 3 | No uplink; allow-list in the scripts; rate caps; review by S1 + supervisor | Phase 02 / S4 |
| R7 | Results look "too good" (shortcuts) | 2 | 2 | DQ checks Q10–Q12; E1-a anchor | Phase 03 / S3 |
| R8 | Dashboard overstates the system (fake or unlabeled data) | 2 | 3 | Server-set provenance; mapping table; wording rules; S1 review | Phase 05 / S5 |
| R9 | Demo failure on presentation day | 2 | 2 | Preflight; replay; recording; rehearsals | M5 / S6 |
| R10 | Thermal throttling distorts the latency results | 2 | 2 | Cooling; log `vcgencmd get_throttled`; flag affected runs | Phase 04 / S4 |
| R11 | The team spends its time on visuals before the research is done | 2 | 2 | P8 shows only real results; dashboard work starts on synthetic data, in parallel but timeboxed | All milestones / S6 |
| R12 | OneDrive sync corrupts large files | 2 | 1 | Keep `data/` and `node_modules/` outside OneDrive (D-05) | Phase 01 / S6 |
| R13 | H1–H3 are rejected | 2 | 1 | Report them honestly; a negative result is still a finding (ADR-01) | M3–M5 / S1 |
| R14 | Dataset licences forbid our use | 1 | 3 | D-04 enquiries; use only datasets with clear terms | M2 / S2 |
