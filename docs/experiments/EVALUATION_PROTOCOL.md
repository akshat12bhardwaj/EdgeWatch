# Evaluation Protocol

**Status:** Draft. To be pre-registered (frozen, with a date) at milestone M1, **before** any test-fold result is seen. Changes made after freezing are listed in §10 with a reason.

## 1. Research questions and hypotheses

These are defined in [RESEARCH_GAP_ANALYSIS.md §5](../research/RESEARCH_GAP_ANALYSIS.md#5-research-questions-objectives-hypotheses) and summarised here:

| RQ | Hypothesis | Experiments |
|---|---|---|
| RQ1 Leakage-controlled and cross-dataset quality | H1: macro-F1 under leakage-controlled splits is lower than under a random split by more than Δ (proposed Δ = 0.05) | E1, E2, E9 |
| RQ2 End-to-end edge cost | H2: capture + feature extraction take > 50% of per-window processing time for tree models | E3, E4, E6 |
| RQ3 Benign-lab FPR | H3: FPR on lab benign traffic is higher than FPR on the dataset test split | E5 |
| RQ4 Alert evidence cost | Descriptive | E7 |

## 2. Datasets

MQTTset (primary), MQTT-IoT-IDS2020 (secondary), CICIoMT2024 (cross-dataset target), and lab captures (RQ2/RQ3). Justification: [DATASET_SELECTION.md](../data/DATASET_SELECTION.md). Every dataset must pass the [DATA_QUALITY_PROTOCOL.md](../data/DATA_QUALITY_PROTOCOL.md) checks first.

## 3. Splits

| Split | Definition | Leakage it controls | Applicable to |
|---|---|---|---|
| **S-rand** (reference) | Stratified random 70/15/15 over windows | None. Reproduces common practice (P08: 70/30; P19: 80/20 stratified [R]) | All datasets |
| **S-time** | For each capture (each attack type and the benign capture), the first 60% of its duration is train, the next 20% validation, the last 20% test, with a **gap of 2W** between blocks | Temporal autocorrelation; adjacent-window near-duplicates | All datasets |
| **S-episode** | Group k-fold (k = 5) over attack **episodes** (contiguous attack intervals) and benign blocks of equal length | Session/episode leakage | Lab data; any dataset with ≥ 3 episodes per class (MQTTset probably has 1 per class, see D-01) |
| **S-cross** | Train on all of dataset A (train+val), test on dataset B, using harmonised families only | Testbed artefacts; dataset shortcuts (P33) | MQTTset ↔ CICIoMT2024 (benign/flood/malformed); MQTTset ↔ MQTT-IoT-IDS2020 (benign/bruteforce) |

**Rules:**
- No oversampling before splitting.
- No feature selection using test data.
- The same features and models are used across splits, so the *split* is the only variable in E1.

## 4. Experiments

| ID | Question | Design | Output |
|---|---|---|---|
| **E1** | How much does the split change detection quality? | {LR, DT, RF, HistGB} × {S-rand, S-time, S-episode where possible} × seeds 0–4, on MQTTset and MQTT-IoT-IDS2020. **E1-a:** additionally train RF on the dataset's *published* feature CSV with S-rand to reproduce published numbers as a sanity anchor | Macro-F1, per-class recall, FPR with CIs; Δ(S-rand − S-time) per model |
| **E2** | Cross-dataset generalisation | {LR, DT, RF, HistGB, IsolationForest (binary only)} trained on A, tested on B, both directions; binary and family level | Same metrics; asymmetry A→B vs. B→A (as in P33) |
| **E3** | Stage-wise latency and throughput on the gateway | Replay benign + attack lab traffic at rates {50, 200, 1000, 5000} MQTT msgs/s (adjusted after a pilot) for 10 min each, 3 repetitions, one deployed model at a time | p50/p95/p99 per stage ([DATA_FLOW.md §1](../architecture/DATA_FLOW.md#1-live-pipeline-one-window)); max rate with < 0.1% capture drops |
| **E4** | Resource consumption | During E3: 1 Hz CPU % and RSS for IDS processes and broker; idle baseline (no IDS) for comparison; model size | Mean/peak CPU and RSS; **overhead vs. no-IDS baseline** |
| **E5** | Benign-lab FPR | ≥ 5 benign scenarios not used in training: steady sensors; bursty publishers; QoS 1/2 heavy; retained-message churn; reconnect storm (benign mass reconnect after broker restart); new device joining. 30 min each | FPR per window; false alerts per hour per scenario |
| **E6** | Quality vs. cost Pareto | Combine E1 (S-time macro-F1) with E3/E4 per model | Pareto plot; deployed-model choice |
| **E7** | Evidence cost | E3 at the nominal rate with evidence on vs. off | Added p95 latency per alert |
| **E8** (optional) | TLS-visible features only | Retrain using TLS-available features (F01–F08, F26) under S-time | Δ macro-F1 vs. full feature set |
| **E9** | Window-size sensitivity | W ∈ {1, 5, 10} s for the best model under S-time, plus E3 at the nominal rate | Quality and latency vs. W |

## 5. Metrics

Defined in [MODEL_EVALUATION.md](../ml/MODEL_EVALUATION.md). Primary: macro-F1 (S-time) and end-to-end p95 latency (E3). Secondary: per-class recall, FPR, false alerts per hour, time-to-detect, CPU %, and RSS.

## 6. Latency measurement method (E3)

- **Clock:** `time.perf_counter_ns()` inside the gateway process for stage timings. Packet times come from tshark `frame.time_epoch`, from the same host clock.
- **Batch size:** 1 window per inference call. This is the live behaviour; batch effects are excluded.
- **Warm-up:** 60 s discarded at the start of each run.
- **Controlled conditions (recorded in the manifest):**
  - CPU governor set to `performance`; the SoC temperature is logged and runs with throttling are flagged (`vcgencmd get_throttled` on the RPi).
  - Heatsink/fan configuration.
  - Wired Ethernet only; Wi-Fi off.
  - No other user processes.
- **Load generation** runs on a **separate** machine, so that it does not consume gateway CPU.
- **Report:** device model, RAM, OS image and date, kernel, Python, scikit-learn, tshark, and Mosquitto versions.

## 7. Resource measurement method (E4)

- psutil at 1 Hz for each PID (tshark, the Python IDS process, mosquitto). CPU % is normalised per core and reported both per process and as a total.
- RSS is measured in MB; peak and mean are reported.
- **Baseline:** the same traffic with the IDS stopped (broker only). The overhead is the difference.
- The observer effect of psutil is measured once (monitor-only run) and reported.

## 8. Repetition and variability

- Offline: 5 seeds × each split; episode-bootstrap CIs.
- Lab: 3 repetitions per (rate, model) in E3; 1 run per scenario in E5, with a second run if the FPR exceeds 1%.
- Report the std or IQR for every number. A single run is never a result.

## 9. Reproducibility requirements

- Configs in `configs/`, a fixed seed list, and pinned `requirements.txt`.
- Dataset checksums; extractor version recorded in every output.
- `results/<exp_id>/` contains `metrics.json`, the config copy, `git_commit`, and environment versions.
- Lab runs keep the manifest, schedule, and events (see [DATA_DICTIONARY.md §5](../data/DATA_DICTIONARY.md#5-resultsrun_id-lab-run)).
- Another team member re-runs one E1 and one E3 configuration from scratch before M5 (the reproducibility check in [DEFINITION_OF_DONE.md](../DEFINITION_OF_DONE.md)).

## 10. Threats to validity

| Type | Threat | Mitigation / acknowledgement |
|---|---|---|
| Internal | Label errors in datasets | DATA_QUALITY checks; mixed windows excluded |
| Internal | Our extractor differs from the published features, so numbers are not comparable with papers | E1-a anchor run; state this explicitly |
| Internal | One episode per class in MQTTset limits S-episode | Use S-time there; use S-episode on lab data |
| Construct | Window-level metrics ≠ operator experience | Also report alert-level metrics and alerts per hour |
| Construct | "Score" ≠ probability | Calibration check before using the word "confidence" |
| External | All data is lab or simulated, including ours | State this; no claim of real-world FPR |
| External | One gateway model | Report the exact device; the emulated-constraint fallback is labelled |
| External | Plaintext MQTT only | E8 quantifies the TLS feature loss; claim limited to plaintext / TLS-terminating gateways |
| Conclusion | Multiple comparisons across models × splits | Pre-registered primary comparison (S-rand vs. S-time, macro-F1); others are exploratory |

## 11. Change log (after freezing)

| Date | Change | Reason | Approved by |
|---|---|---|---|
| | | | |
