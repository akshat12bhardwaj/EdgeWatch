# Architecture Decision Records

> Historical technical reference. Current operation is documented in ../README.md; old UI, deployment and research plans are not current instructions.

Format: Context → Decision → Alternatives → Consequences. Status values: **Proposed**, **Accepted**, **Superseded**. All records start as *Proposed* and require team agreement at M1 ([DECISIONS.md](../DECISIONS.md)).

---

## ADR-01 Frame the contribution as an evaluation and systems-measurement study
- **Status:** Proposed
- **Context:** Model design for MQTT IDS is crowded (P07–P19). Evaluation realism is the documented weakness ([RESEARCH_GAP_ANALYSIS.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/research/RESEARCH_GAP_ANALYSIS.md)).
- **Decision:** No new model architecture. Contributions are the leakage-controlled benchmark (RQ1), stage-wise edge cost (RQ2), benign FPR (RQ3), and a reproducible pipeline and demo.
- **Alternatives:** A new deep model (high novelty risk, high cost); federated learning (P14, P21 already cover it).
- **Consequences:** Rigour of the protocol becomes the core deliverable. A "negative" result (no drop) is still publishable as a finding.

## ADR-02 Passive, broker-adjacent detection; no mitigation
- **Status:** Proposed
- **Context:** All public MQTT-specific attacks target the broker (P08, P22). Inline blocking adds safety and availability risks that are outside the research question.
- **Decision:** Capture passively on the gateway that hosts the broker. Raise alerts only.
- **Alternatives:** Inline proxy (adds latency to the data plane and is a single point of failure); broker plugin (couples the IDS to Mosquitto internals, and cannot see TCP-level behaviour).
- **Consequences:** Cannot stop attacks. Cannot see attacks that never reach the gateway (e.g., attacks on subscribers elsewhere). Documented in [THREAT_MODEL.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/architecture/THREAT_MODEL.md).

## ADR-03 One feature extractor for offline training and live inference
- **Status:** Proposed
- **Context:** Datasets ship pre-computed features with different definitions (P08: per-packet `mqtt.*` fields without IP or time; P09: packet, uni-flow, and bi-flow features; P20/P22: CIC features). A model trained on them cannot run on live traffic without train/serve skew. P32 shows that proprietary per-dataset feature sets block cross-dataset comparison.
- **Decision:** Re-extract all features from **raw PCAP** with our own extractor (tshark field decoding → Python windowing), and use exactly the same code live.
- **Alternatives:** Use the dataset CSVs (fast, but no live parity and no common features); MQTTFlowLyzer (404 features, offline-oriented; candidate for a later comparison).
- **Consequences:** Requires PCAPs for every dataset used (blocker D-01 in [DATASET_SELECTION.md](../data/DATASET_SELECTION.md)). Results are not directly comparable to the numbers papers report, which is intentional. We also run one "as-published" baseline for reference (E1-a).

## ADR-04 Windowed per-source aggregation
- **Status:** Proposed
- **Context:** Flow-level features beat packet-level ones for MQTT attacks (P09). Brute force and connect floods open many short TCP connections, so per-connection flows fragment them. Fixed windows give a constant latency bound for the alert.
- **Decision:** Tumbling windows of **W = 5 s** (sensitivity analysis: 1, 5, 10 s), keyed by **source IP**, plus broker-wide context features. Source IP is a grouping key only, **never a model input**.
- **Alternatives:** P19-style ClientID + topic sessions (semantically richer, but a session must end before it can be classified, and SlowITe sessions are long by design); 5-tuple flows (fragmentation).
- **Consequences:** DDoS from many sources appears as many moderately abnormal sources, handled by the context features. NAT would merge sources (a lab limitation, documented).

## ADR-05 Model set
- **Status:** Proposed
- **Context:** The question is cost vs. quality, so the candidates must span that range. P25 found DT cheapest on device. Gradient boosting and RF are strong tabular baselines (P08, P13). P33 found unsupervised models generalise better across datasets.
- **Decision:** Four supervised models plus one unsupervised reference:
  - **Logistic Regression**: linear baseline, trivially explainable.
  - **Decision Tree** with depth capped (cheapest).
  - **Random Forest**: the strongest model in P08 and P09.
  - **HistGradientBoosting** (scikit-learn): a boosting representative with no new dependency.
  - **Isolation Forest**: unsupervised reference, cross-dataset experiment (E2) only.
- **Alternatives:**
  - XGBoost/LightGBM: an extra dependency that HistGB approximates. Can be added later if a reviewer asks.
  - Small MLP/TCN: no defensible reason for this RQ. P27 already covers TCN at the edge.
  - TabNet: P19's model, too heavy for the gateway budget. Possible as an offline comparison only.
- **Consequences:** Everything runs with scikit-learn, which is already installed on the laptop (1.8.0) and is pip-installable on the RPi.

## ADR-06 Edge deployment target
- **Status:** Proposed
- **Options compared:**

| Option | Realism for an "edge gateway" claim | Cost and risk | Measurement quality | Verdict |
|---|---|---|---|---|
| Laptop running broker and IDS | Low: a laptop CPU is 3–10× faster than gateway SoCs [I] | Lowest | Good, but not representative | Development only |
| **Raspberry Pi 4 (4 GB) or Pi 5 as gateway** | High: P24 and P27 use the same device class, so results are comparable | ~1 device; low risk | Good with fixed CPU governor and cooling | **Recommended** |
| Linux VM/container with CPU and RAM limits | Medium: limits cores and memory, but not micro-architecture or I/O | Low | Labelled `emulated-constraint` | Fallback |

- **Decision:** Measure on an RPi 4 (4 GB) or Pi 5 running 64-bit Raspberry Pi OS Lite. Record the exact model, OS, kernel, Python, and library versions. Physical hardware is justified **only** because the gateway is the object of measurement in RQ2.
- **What physical hardware adds over emulation:** ARM micro-architecture, real NIC and driver capture behaviour, thermal throttling, and SD-card I/O.

## ADR-07 Isolated lab network
- **Status:** Proposed
- **Decision:** A dedicated switch or access point with **no uplink**, or a host-only virtual network. All attack scripts carry a hard-coded allow-list containing the broker's lab IP. There is no public broker and no third-party device. Details are in [THREAT_MODEL.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/architecture/THREAT_MODEL.md#7-lab-safety-boundaries).

## ADR-08 Plaintext MQTT for primary experiments; TLS as a limitation study
- **Status:** Proposed
- **Context:** All candidate datasets are plaintext (P08 states MQTT 3.1.1 without TLS). Under TLS, `mqtt.*` fields are unavailable to a passive observer.
- **Decision:** Primary experiments use port 1883. An optional experiment (E8) retrains on TLS-available features only (TCP/timing, plus Mosquitto log events) to quantify the loss.
- **Consequences:** Results apply to plaintext deployments or to a gateway that terminates TLS. This is stated in every results section.

## ADR-09 Event contract with mandatory provenance
- **Status:** Proposed
- **Decision:** Every event that reaches the UI carries `provenance`, `traffic_source`, `ground_truth` (nullable), and `model_id`. The server sets them, and the UI cannot override them. Schema: [DATA_FLOW.md](DATA_FLOW.md#3-event-contract).

## ADR-10 Dashboard stack
- **Status:** Proposed
- **Decision:**
  - Backend: FastAPI + WebSocket. It runs in Python, the same language as the pipeline.
  - Frontend: Vite + TypeScript, with Cytoscape.js for the topology and uPlot for time series.
  - No CSS framework beyond a small design-token file.
- **Alternatives:** Grafana (fast, but generic look and weak interactive topology); Node-RED dashboard (same issue); React + D3 (more code than needed).
- **Consequences:** The frontend developer must be comfortable with TypeScript. The topology and charts are libraries, not hand-written.

## ADR-11 Model artefact format
- **Status:** Proposed
- **Decision:** joblib-serialised scikit-learn estimators. A model card (JSON) records the training data hash, feature list and order, scikit-learn version, seed, and threshold. The gateway refuses to load a model whose scikit-learn version or feature order differs.
- **Alternatives:** ONNX via skl2onnx (portable, but adds a dependency); treelite (faster trees). Revisit if E3 shows inference is the bottleneck, which H2 predicts it will not be.

## ADR-12 Traffic generation
- **Status:** Proposed
- **Decision:**
  - Benign traffic comes from our own paho-mqtt simulator, configured by scenario files.
  - Attacks are our own minimal scripts reproducing the dataset attack classes (connect flood, publish flood, brute force, keep-alive hold, malformed packets).
  - Dataset tools (MQTT-malaria, MQTTSA, MQTT-PWN) may be used only after S4 reviews them, and only inside the isolated lab.
- **Consequences:** Lab attacks resemble but do not equal the dataset attacks. That gap is part of the RQ3 domain-shift discussion.
