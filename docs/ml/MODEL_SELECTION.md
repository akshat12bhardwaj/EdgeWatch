# Model Selection

Decision record: ADR-05 in [ARCHITECTURE_DECISIONS.md](../architecture/ARCHITECTURE_DECISIONS.md#adr-05-model-set).

## 1. Candidates and justification

| Model | Why include | Literature basis | Expected cost on gateway [I] | Role |
|---|---|---|---|---|
| Logistic Regression | Linear baseline; coefficients give direct evidence; tiny | Baseline in P09 [R] | Microseconds; KB-sized | Baseline |
| Decision Tree (depth ≤ 12) | Cheapest on-device model for training, inference, and power [R, P25]; readable rules | P08, P09, P25 | Microseconds; KB–MB | Lightweight candidate |
| Random Forest (≤ 100 trees, depth-capped) | Best or near-best in P08 (acc 0.9943) and P09 (99.98% uni-flow) [R] | P08, P09, P10 | Tens–hundreds of µs; MB-sized | Strong candidate |
| HistGradientBoosting | Boosting is strong on tabular data (LightGBM in P13); scikit-learn native, so no new dependency | P13 (LightGBM) [U], P16 (XGBoost) [R] | Comparable to RF | Strong candidate |
| Isolation Forest | Unsupervised reference: P33 found unsupervised methods generalise better cross-domain [R]. Passban uses anomaly detection on a gateway [U, P24] | P33, P24 | Like RF | E2 (cross-dataset) only |

## 2. Explicitly not included (and why)

| Model | Reason |
|---|---|
| XGBoost / LightGBM | Extra dependency; HistGB covers boosting. Add only if a reviewer requests it |
| DNN / LSTM / CNN | Already extensively covered (P10, P11, P17). No RQ needs them |
| TCN (TFLite) | Already measured on RPi 4 (P27). Cite as an external reference point rather than re-implement |
| TabNet | P19's model. 404 features exceed our gateway feature budget. Optional offline comparison only if time permits |
| kNN, SVM-RBF | Inference cost grows with training-set size; a poor fit for the gateway |

## 3. Hyperparameter search

- Small grids only, selected on the **validation** fold of each split (never on test).
  - DT: `max_depth ∈ {4, 8, 12}`.
  - RF: `n_estimators ∈ {25, 50, 100}` × `max_depth ∈ {8, 16}`.
  - HistGB: `max_iter ∈ {100, 200}` × `learning_rate ∈ {0.05, 0.1}`.
  - LR: `C ∈ {0.1, 1, 10}` with standardisation.
- Selection criterion: macro-F1 on validation. Ties go to the smaller model.
- The decision threshold is chosen on validation to meet a target FPR, with the default target ≤ 1% of benign windows. The threshold is stored in the model card.

## 4. Selection of the "deployed" model for the demo

Choose the model on the **Pareto front** of leakage-controlled macro-F1 vs. gateway end-to-end p95 latency (E6) that meets the resource budget in [SYSTEM_ARCHITECTURE.md §5](../architecture/SYSTEM_ARCHITECTURE.md#5-resource-budget-target-device-to-be-validated-in-phase-04). This is a decision the team must agree on, logged in [DECISIONS.md](../DECISIONS.md).
