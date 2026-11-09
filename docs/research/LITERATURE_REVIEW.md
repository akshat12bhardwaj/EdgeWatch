# Literature Review: Lightweight MQTT Intrusion Detection at the Edge

**Version:** 0.1 (round-1 synthesis, 2026-10-20). **Owner:** Literature workstream (S1).
**How to read this:** the review is organised by theme, not paper by paper. Paper IDs refer to [REFERENCES.md](REFERENCES.md), and per-paper details are in [PAPER_MATRIX.csv](PAPER_MATRIX.csv).

Statements are tagged as follows:
- **[R]** means the authors *reported* it.
- **[I]** means it is *our interpretation*.
- **[U]** means it is *unverified* (based on a secondary source or on metadata only).

---

## 1. MQTT: protocol, attack surface, and threat models (SQ1)

**MQTT basics.** MQTT is a publish/subscribe protocol carried over TCP. The standard ports are 1883 for plaintext and 8883 for TLS. Clients CONNECT to a broker, PUBLISH messages to hierarchical *topics*, and SUBSCRIBE to topic filters. Delivery guarantees are set by QoS levels 0, 1, and 2. Liveness is maintained with a client-advertised *keep-alive* interval and PINGREQ/PINGRESP packets. Version 3.1.1 [S1] and version 5.0 [S2] are the two versions in common use. Authentication (username/password, client certificates) and authorisation (topic ACLs) are broker features. The protocol does not mandate them, so many deployments run without them. [I, to be verified against S1/S2 by S4]

**Attack classes established in the literature:**

| Class | Mechanism | Evidence |
|---|---|---|
| Volumetric DoS / flooding | CONNECT or PUBLISH floods exhaust broker resources | MQTTset (MQTT-malaria, publish flood) [R, P08]; CICIoMT2024 connect/publish floods [R, P22]; 10 DoS/DDoS scenarios [R/U, P15] |
| Low-rate DoS | The client sets a long keep-alive and holds connections open (SlowITe), monopolising broker slots | [R, P04]. P19 links timeout enforcement to CVE-2020-13849 [R, P19] |
| Malformed / fuzzed packets | Crafted packets that violate the protocol and trigger parser bugs | MQTTSA malformed data in MQTTset [R, P08]; CICIoMT2024 malformed data [R, P22]; parser-validation IDS [R, P06]; fuzzing [U, P05] |
| Credential brute force | Repeated CONNECT attempts with guessed credentials | MQTTset (MQTTSA + rockyou) [R, P08]; MQTT-IoT-IDS2020 MQTT_BF (MQTT-PWN) [R, P09] |
| Unauthorised topic access / wildcard subscription | Subscribing to `#` on an open broker | Described for CICIoMT2024 [U]; to be confirmed in S1/S2 and P03 |
| Generic network attacks against IoT hosts | Port scans, SSH brute force, MitM | MQTT-IoT-IDS2020 [R, P09]; MQTT_UAD (MitM, intrusion) [R, P18] |

**Synthesis.**
- [I] Every MQTT-specific attack in the public datasets targets **the broker**. MQTTset was captured at the broker, with the attacker connected directly to it [R, P08, as characterised in P19].
- [I] This justifies placing the detector **at or next to the broker**. It also means that attacks on publishers or subscribers are outside what these datasets can show.
- [I] Two attack classes, *low-rate DoS* and *brute force*, are the hardest for volume-based features, because their per-second traffic resembles benign traffic. This is consistent with P09's finding that packet-level features fail on MQTT attacks while flow-level features succeed [R, P09], and with MQTTset's reported misclassification of SlowITe, flood, and malformed traffic [R, P08].

**Gaps in our own reading:** P01, P02, P03, and P05 have only had their metadata verified. The threat model ([THREAT_MODEL.md](../architecture/THREAT_MODEL.md)) is provisional until S4 completes those reviews.

---

## 2. MQTT-specific IDS (SQ2)

**What exists.** There is a substantial and growing body of MQTT-specific IDS work:
- Classical ML and DL classifiers trained on MQTT-IoT-IDS2020 or MQTTset (P07, P09, P10, P11, P13, P16).
- Federated variants (P14).
- Rule-learning approaches (P12).
- Protocol-validation engines (P06).
- Explainable variants (P17, P19).

**Reported performance is near ceiling.**
- Random Forest on MQTT-IoT-IDS2020 uni-flow features reaches 99.98% accuracy [R, P09].
- A DNN reaches 99.92% for binary uni-flow [R, P10].
- ECSSA + LightGBM reaches 98–99% on three datasets [U, P13].
- TabNet reaches >99% on brute force [R, P19].
- Stacking ensembles reach 0.95 [R, P16].

[I] When many dissimilar models all reach roughly 99%, the benchmark is probably not separating them. This calls for scrutiny of the *evaluation protocol* rather than for a new model (see §5).

**Closest competitor: P19 (MQTTFlowLyzer, 2026).**
- It defines MQTT-aware flows: a flow is a ClientID plus topic session, closed by DISCONNECT, a maximum duration, or 2× keep-alive inactivity.
- It extracts 404 features and trains TabNet with confidence-based detection of unseen attacks and attention-based interpretation [R].
- **What P19 already covers, which we therefore must not claim as novel:** MQTT-aware flow features, interpretability, and zero-day flagging.
- **What P19 does not do**, verified in the thesis full text:
  - It does not deploy on gateway hardware. Latency is "≈0.0725 ms per flow … CPU-only", with hardware unspecified, and it measures the model alone [R].
  - Feature extraction is measured separately and offline. For example, extraction for 2,925 flows of the MQTTset malformed subset took 7.76 s [R]. [I] That is about 2.65 ms per flow, roughly 37× the model latency, on unspecified hardware. *This is an inference from the thesis tables and must be re-derived by S1 from the journal version.*
  - It uses a **stratified random 80/20 split after downsampling** [R]. Under that split, flows from the same attack session can appear in both train and test [I].
  - It names "deployment in real-time environments" as future work [R].

**Synthesis.**
- [I] MQTT IDS research is mature on *detection accuracy on fixed benchmarks*.
- [I] It is thin on three things:
  - (a) evaluation designs that prevent session- and time-level leakage;
  - (b) measuring the *whole* capture → feature → inference pipeline on the device that would run it;
  - (c) false positives on benign traffic that differs from the training capture.

---

## 3. Datasets: which ones actually contain MQTT? (SQ3)

| Dataset | MQTT traffic? | MQTT-specific attacks? | Raw PCAP? | Verdict |
|---|---|---|---|---|
| MQTTset [P08] | Yes, broker-side, 33 features (30 `mqtt.*`) [R] | Yes: flood, publish flood, SlowITe, malformed, brute force [R] | Kaggle release; PCAPs present by parser, D-01 remains Open (DOCUMENTATION_AUDIT §12) | **Primary** (proposed; suitability inconclusive) |
| MQTT-IoT-IDS2020 [P09] | Yes [R] | Only MQTT brute force; the other attacks are scans and SSH brute force [R] | Yes (IEEE DataPort) [R] | **Secondary** |
| CICIoMT2024 [P22] | Yes, Wi-Fi/MQTT subset [R] | Yes: malformed, DoS/DDoS connect flood, DoS/DDoS publish flood [R] | Yes [R] | **Cross-dataset target** (independent lineage) |
| DoS/DDoS-MQTT-IoT [P15] | Yes, physical testbed [U] | DoS/DDoS only (10 scenarios) [U] | To verify | Candidate cross-dataset target |
| MQTT_UAD [P18] | Yes [R] | DoS, MitM, intrusion [R] | Frame-tagged capture [R] | Candidate |
| BCCC-MQTT-IDS-2025 [P19] | Yes | Yes | Derived | **Not independent**: aggregates P08 + P09 + P15 |
| Edge-IIoTset [P21] | MQTT traffic in testbed [U] | No; the attacks are generic (DDoS, injection, MitM, malware…) [R] | Yes | Benign-shift test only |
| CICIoT2023 [P20] | **No** MQTT protocol indicator among the 46 features; no MQTT attack [R, official page] | No | Yes | **Rejected** for MQTT claims |

[I] **Key finding.** CICIoT2023 is often cited as an IoT benchmark, but its official feature and attack lists contain no MQTT element. Some secondary sources state otherwise [U]. Any MQTT claim made on CICIoT2023 would be unsupported.

[I] **Dataset-quality risks.**
- MQTTset balances classes by *replicating* attack records [R]. Combined with a random split, this can put identical rows in both train and test.
- P09 retains ports as features [R], which can act as a shortcut.
- Count inconsistencies exist within the MQTTset paper [R].
- Engelen et al. showed that construction errors of this kind changed more than 20% of CICIDS2017 labels and materially changed benchmark results [R, P31].
- These risks motivate re-extracting features ourselves from PCAP ([DATA_QUALITY_PROTOCOL.md](../data/DATA_QUALITY_PROTOCOL.md)).

---

## 4. Lightweight and edge-deployed IDS (SQ4)

**Established facts:**
- **Gateway-deployed IDS is not new.** Passban ran on a Raspberry Pi 3 gateway, using about 54 MB RAM and about 47% CPU, with a 97.25% F1 [U, P24 via P26]. Kitsune was designed for online detection on simple hardware [U, P23; verify the RPi evaluation in full text].
- **Tree models are cheap.** Decision Trees were best on training time, inference time, and power in an on-device energy comparison [R, P25]. For small models, a CPU outperforms an Edge TPU [R, P26].
- **Edge measurement of MQTT-related detection exists for DDoS.** A quantised TCN on a Raspberry Pi 4 reached 0.19 ms latency and 4.22 W on an MQTT-based H-IoT DDoS dataset [R, P27].

**Synthesis.**
- [I] The claim "existing IDS have high computational overhead" is **not supported as a general statement**. Lightweight models already infer in well under a millisecond (P19, P27). We therefore reject the over-broad gap G1 ([RESEARCH_GAP_ANALYSIS.md](RESEARCH_GAP_ANALYSIS.md)).
- [I] What the literature reports inconsistently is *where the time goes*. Model-only latency (P19, P27) leaves out packet capture, parsing, and windowed feature aggregation. P19's own offline numbers suggest that feature extraction costs much more than inference. Kitsune is a notable exception, because its feature extractor was designed for incremental online use [U, P23].
- [I] For MQTT, we found no study that measures stage-by-stage cost (capture, parse, features, inference, alert) on gateway hardware across *multiple MQTT attack classes*. This remains to be confirmed in round 2.

---

## 5. Evaluation methodology, leakage, and generalisation (SQ5)

- Sommer & Paxson argue that ML NIDS operate in an open world, where false positives are expensive and benign diversity is high [P29, foundational].
- Arp et al. reviewed 30 top-tier security papers. They found pitfalls to be widespread, including data snooping, spurious correlations, inappropriate baselines, and lab-only evaluation, and showed that these pitfalls inflate results [R, P30].
- Layeghy & Portmann found that **no** model generalised across all four NIDS datasets tested. Generalisation was asymmetric, and SHAP traced the failures to dataset-specific feature/label correspondences [R, P33].
- Sarhan et al. showed that proprietary per-dataset features prevent cross-dataset comparison, and proposed common NetFlow feature sets [R, P32].

**Implications for MQTT research.**
- [I] Every MQTT IDS paper we reviewed in full or in abstract evaluates within a single dataset using random or stratified-random splits (P08, P09, P19). P14 is the only possible exception: it claims generalisation to another dataset [U].
- [I] No reviewed MQTT paper reports results under time-blocked or session-grouped splits.
- [I] Taken together with P30 and P33, we should *expect* within-dataset random-split scores to overstate real-world performance. **How much** they overstate it for MQTT attacks is an open, measurable question. That question is RQ1.

---

## 6. Explanation and visualisation (SQ6)

- Explainability for MQTT IDS is already addressed by XMID-MQTT [U, P17] and by TabNet attention in P19 [R]. Neupane et al. survey X-IDS more broadly [P34, MD].
- [I] Explanation is therefore **not** a defensible primary contribution for us. Showing *evidence for each alert* is still a sound operator requirement. It can be met cheaply with tree-path or feature-contribution summaries, and its cost can be measured (RQ4, secondary).
- Shiravi et al.'s survey of security visualisation [P35, MD] gives a taxonomy (host/server monitoring, internal/external, attack patterns, routing, investigation). S5 will use it to justify the dashboard panels ([VISUALIZATION_RESEARCH_MAPPING.md](../presentation/VISUALIZATION_RESEARCH_MAPPING.md)).

---

## 7. Overall synthesis

1. **Confirmed [R]:**
   - Public MQTT datasets exist with broker-targeted attacks (P08, P09, P22, P15, P18).
   - Flow-level features are needed for MQTT attacks (P09).
   - Tree models and small networks infer in under a millisecond (P19, P27).
   - Gateway IDS deployment is feasible (P24, P27).
   - Cross-dataset generalisation of NIDS is poor and asymmetric (P33).
2. **Our interpretation [I]:**
   - The weakest part of the MQTT IDS literature is *evaluation realism*, not model design. Three things are missing in particular:
     - leakage-controlled splits;
     - end-to-end cost on the gateway, including feature extraction;
     - false-positive rates on fresh benign traffic.
3. **Not yet established [U]:**
   - Whether P14, P15, P17, P23, or P27 already include end-to-end or grouped-split evaluations. Their full texts are the top round-2 priority.

The defended gap and research questions follow in [RESEARCH_GAP_ANALYSIS.md](RESEARCH_GAP_ANALYSIS.md).

---

## Appendix A: Full-text review template

Copy this template for each assigned paper into `docs/research/reviews/<ID>.md`, then update the matching row in `PAPER_MATRIX.csv`.

```markdown
# <ID> <short title>
- Reviewer / date:
- Version read (journal / preprint / thesis):
- Problem and motivation:
- Method / model:
- Dataset(s), how labelled, split strategy (random? grouped? temporal?):
- Attack classes:
- Metrics and headline results (quote the table/figure number):
- Hardware and computational measurements (model-only or end-to-end? batch size?):
- Limitations stated by the authors:
- Limitations we can substantiate (cite the section):
- Does it pre-empt any of our RQ1–RQ4? (yes/no + why):
- Quotes worth keeping (with page):
```
