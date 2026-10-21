# Research Gap Analysis

**Status:** Proposed. To be frozen at milestone **M1** after the round-2 full-text reviews ([IMPLEMENTATION_ROADMAP.md](../IMPLEMENTATION_ROADMAP.md)).
Evidence tags: **[R]** reported by the authors, **[I]** our interpretation, **[U]** unverified. Paper IDs refer to [REFERENCES.md](REFERENCES.md).

## 1. Candidate gaps: verdicts

| # | Candidate gap | Verdict | One-line reason |
|---|---|---|---|
| G1 | Existing IDS have high computational overhead | **Rejected (as stated)** | Tree models and quantised small networks already infer in under 1 ms (P19, P27) and are cheapest on device (P25) |
| G2 | Lack of realistic evaluation on resource-constrained gateways | **Narrowed** | Gateway deployment exists (P24, P27, P23). What is missing for MQTT is a *stage-wise, end-to-end* measurement across multiple MQTT attack classes |
| G3 | Detection-quality vs. latency trade-off | **Accepted as an analysis, not as novelty** | Standard Pareto analysis; it becomes meaningful only when combined with G2 and G4 |
| G4 | Weak generalisation across environments and attack families | **Accepted for MQTT** | Shown for general NIDS (P33, P32). MQTT papers evaluate within one dataset with random or stratified splits (P08, P09, P19); P14's cross-dataset claim is unverified |
| G5 | Insufficient false-positive evaluation under benign MQTT traffic | **Accepted (narrow)** | Benign traffic in the datasets comes from one simulated environment each (P08: one-week simulated smart home; P09: VMs). No reviewed paper tests FPR on fresh benign traffic |
| G6 | Inadequate end-to-end evaluation of detection plus operational overhead | **Accepted: core** | P19 reports model-only latency on unspecified CPU and measures feature extraction offline and separately [R]. P27 measures on RPi 4, for DDoS only [R] |
| G7 | Limited visibility into why alerts are generated | **Rejected as primary novelty** | Addressed by P17 [U] and P19 [R]. Kept as a cheap, measured operator feature (RQ4) |

## 2. Gap-to-evidence table

| Research gap | Supporting papers | Contradicting evidence | Remaining uncertainty | Proposed experiment | Expected contribution |
|---|---|---|---|---|---|
| **G6 + G2:** End-to-end, stage-wise cost of MQTT IDS on gateway hardware is unreported | P19 (model-only 0.0725 ms/flow, hardware unspecified; feature extraction measured offline) [R]; P27 (model latency on RPi 4, DDoS only) [R]; P09, P08, P10, P13 report no compute [R/U] | P24 measured CPU and RAM on an RPi 3 gateway, but not MQTT-specific [U]; P23 designed for online use and may report full-pipeline cost [U] | Full texts of P23, P24, P27 not read; round-2 IEEE/ACM search pending | **E3/E4:** measure per-stage latency (capture → parse → window features → inference → alert), throughput, CPU, and RSS on the gateway, at increasing MQTT message rates | First stage-wise cost profile for MQTT IDS on a gateway-class device; quantifies the share of feature extraction vs. inference |
| **G4:** MQTT detectors are evaluated with splits that allow session/time leakage, and not across datasets | P08 (random 70/30 after replicating attacks) [R]; P19 (stratified random 80/20) [R]; P09 (5-fold CV) [R]; P30 (data snooping inflates results) [R]; P33 (no cross-dataset generalisation for NIDS) [R] | P14 claims generalisation to another dataset [U] | Whether P13, P14, P17 use grouped splits; whether MQTTset/MQTT-IoT-IDS2020 PCAPs allow session reconstruction (D-01) | **E1/E2:** same models and features under (a) random, (b) time-blocked, (c) attack-session-held-out, and (d) cross-dataset (MQTTset → CICIoMT2024 MQTT classes) splits | Quantifies how much reported MQTT IDS accuracy depends on the split; gives leakage-controlled baselines |
| **G5:** False-positive behaviour on benign MQTT traffic outside the training capture is unknown | P08, P09 benign traffic from one simulated environment each [R]; P29 (false positives dominate operational cost) | None found | Edge-IIoTset benign MQTT columns unverified (P21) | **E5:** run trained models on our own lab's benign workloads (varied rates, QoS, retained messages, reconnect storms, client churn) and report FPR per hour and per scenario | Operational FPR figure that a gateway operator can interpret (alerts per hour) |
| **G3:** Quality vs. cost trade-off | P25 (DT cheapest) [R]; P26 (CPU beats Edge TPU for small models) [R] | Well covered in general NIDS | None material | **E6:** Pareto front of macro-F1 (leakage-controlled) vs. end-to-end latency and RSS across LR, DT, RF, HistGradientBoosting | Model recommendation grounded in measured cost |
| **G7:** Alert evidence | P17 [U]; P19 [R]; P34 [MD] | Already addressed | Cost of explanations on the gateway not reported | **E7 (optional):** latency of per-alert top-k feature contributions (tree path or TreeSHAP) | Shows evidence can be produced within budget (supporting, not primary) |

## 3. Strongest defensible gap

> **Published MQTT intrusion detectors report near-perfect accuracy. That accuracy comes from within-dataset, random or stratified splits, and from model-only latency on unspecified hardware. No reviewed work measures, on gateway-class hardware, (i) detection quality under leakage-controlled and cross-dataset evaluation and (ii) the end-to-end, stage-wise cost of the full capture-to-alert pipeline, together with (iii) false-positive rates on independent benign MQTT traffic.**

This is an **evaluation and systems-measurement gap**, not a new-algorithm gap. That is deliberate. The model-design space is crowded (§2 of the literature review), while the evaluation weaknesses are documented in general (P30, P33) but not quantified for MQTT.

## 4. Problem statement

Edge gateways are a natural place to detect attacks on MQTT brokers. However, the literature does not let a practitioner answer two questions:
- *Will a lightweight detector still detect these attacks when evaluated without leakage, and how often will it raise false alarms on my benign traffic?*
- *Can my gateway afford to run the whole pipeline at my message rate?*

Reported accuracies near 99% come from within-dataset random splits. Reported latencies cover the model only. Both therefore over-state readiness for deployment by an amount nobody has measured.

## 5. Research questions, objectives, hypotheses

**Main research question (RQ).**
*On a gateway-class edge device, what detection quality and end-to-end operational cost do lightweight classifiers achieve for MQTT attacks when evaluated with leakage-controlled splits and independent benign traffic?*

| ID | Sub-question | Objective (measurable) | Hypothesis |
|---|---|---|---|
| RQ1 | How much does detection quality change between random, time-blocked, session-held-out, and cross-dataset splits? | **O1:** Report macro-F1, per-class recall, and FPR with 95% CIs for ≥3 models under ≥3 split strategies on ≥2 datasets | **H1:** macro-F1 under leakage-controlled splits is lower than under random splits by more than the pre-registered practical threshold Δ (team to fix Δ at M1; proposed Δ = 0.05) |
| RQ2 | What is the end-to-end, stage-wise latency, throughput, CPU, and memory of the full pipeline on the gateway? | **O2:** Report p50/p95/p99 latency per stage, sustainable msg/s before drops, mean/peak CPU %, and peak RSS on the target device at ≥4 load levels | **H2:** for tree models, capture + feature extraction accounts for >50% of end-to-end per-window processing time |
| RQ3 | What FPR does the detector produce on independent benign MQTT traffic? | **O3:** Report FPR (per window) and false alerts per hour on ≥5 benign lab scenarios not used for training | **H3:** FPR on lab benign traffic is higher than FPR on the dataset test split |
| RQ4 (secondary) | Can per-alert evidence be generated within the latency budget? | **O4:** Report added latency of top-k feature contributions per alert | none (descriptive) |

## 6. Proposed contribution and difference from the closest work

| Closest work | What it does | What we add |
|---|---|---|
| P19 MQTTFlowLyzer + TabNet | 404 MQTT flow features; TabNet; zero-day confidence; model-only latency; stratified random split | Small, live-computable feature set; leakage-controlled and cross-dataset splits; stage-wise cost **on gateway hardware**; benign-lab FPR |
| P27 TCN on RPi 4 | DDoS detection; quantised TFLite; model latency and power on RPi 4 | Multiple MQTT attack classes (brute force, low-rate DoS, malformed, floods); end-to-end incl. feature extraction; classical baselines |
| P24 Passban | Anomaly IDS on an RPi 3 gateway; CPU/RAM | MQTT-specific attacks and features; supervised baselines; leakage-controlled evaluation |

**Contribution statement (draft):**
1. A leakage-controlled benchmark of lightweight classifiers on MQTT attack data, showing how results change across split strategies and datasets.
2. A stage-wise cost profile of a complete capture-to-alert MQTT IDS pipeline on a gateway-class device.
3. A benign-traffic false-alarm assessment in an isolated lab.
4. An open, reproducible pipeline and a demonstration interface that shows only measured or explicitly labelled data.

## 7. Novelty risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| P14, P17, P23, P27 (unread full texts) already report grouped splits or end-to-end cost | Medium | Round-2 full-text reviews before M1. If pre-empted, narrow the claim to the MQTT multi-attack combination, or to cross-dataset only |
| Journal version of P19 adds edge deployment that the thesis lacks | Medium | S1 reads the journal version (doi:10.1007/s11227-026-08485-7) first |
| Unsearched IEEE Xplore / ACM DL papers | Medium | Round-2 search ([SEARCH_PROTOCOL.md](SEARCH_PROTOCOL.md#8-round-2-plan)) |
| "Evaluation study" is judged less novel than a new model | Low–medium | Frame it as an empirical systems contribution with reproducible artefacts. P30 and P33 show this type of work is valued |
| Results show no drop (H1 rejected) | Possible | Still a valid finding: it would establish that MQTT benchmarks are robust. Report it honestly |

**We do not claim publication-level originality.** The claim is that the combination is under-evaluated in the reviewed literature, as of the round-1 search.

## 8. Limitations of the gap analysis

- Eight sources were read in full. The rest were reviewed at abstract or metadata level ([SEARCH_PROTOCOL.md](SEARCH_PROTOCOL.md#7-access-levels-used-in-the-paper-matrix)).
- IEEE Xplore and ACM DL were not searched directly in round 1.
- The datasets are simulated or lab-generated. Our lab is also a lab, so "independent benign traffic" means *different from training*, not *real-world production*.

## 9. Recommended title

**"How Lightweight Is Lightweight? End-to-End, Leakage-Controlled Evaluation of MQTT Intrusion Detection on an Edge Gateway"**

Plain alternative: *"End-to-End Evaluation of Lightweight MQTT Intrusion Detection on a Resource-Constrained Edge Gateway"*.

Why not the original title: "Lightweight Intrusion Detection for MQTT-Based IoT Networks Using an Edge Gateway" describes a system that already exists in several forms (P19, P24, P27). It also does not state what is being *investigated*.
