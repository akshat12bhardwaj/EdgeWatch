# Model Evaluation

> Historical technical reference. Current operation is documented in ../README.md; old UI, deployment and research plans are not current instructions.

The experimental protocol (splits, repeats, hypotheses) is defined in [EVALUATION_PROTOCOL.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/experiments/EVALUATION_PROTOCOL.md). This file defines the **metrics and the alert policy**.

## 1. Detection metrics (per window)

For each class *c*, TP/FP/FN are counted per window:

- Precision_c = TP_c / (TP_c + FP_c)
- Recall_c = TP_c / (TP_c + FN_c)
- F1_c = 2 · Precision_c · Recall_c / (Precision_c + Recall_c)
- **Macro-F1** = (1/|C|) Σ_c F1_c. **Primary metric**, because classes are imbalanced.
- Balanced accuracy = (1/|C|) Σ_c Recall_c
- **FPR** (binary view) = FP / (FP + TN), where positive = any attack class
- **False alerts per hour** (lab only) = alerts during benign-only periods / benign hours
- PR-AUC for the binary view (more informative than ROC-AUC under imbalance)

We **do not** report plain accuracy as a headline. It is included in the tables only so that results can be compared with P08–P16, which report it.

## 2. Uncertainty

- Report mean ± std over seeds 0–4.
- 95% CIs by **episode-level bootstrap**: resample attack episodes and benign blocks, not windows, so that correlated windows do not shrink the interval. 1,000 resamples.
- Compare models with a paired bootstrap of the macro-F1 difference on the same test episodes.

## 3. Calibration (decides whether the UI may say "confidence")

- Reliability diagram and Brier score on the test fold for the deployed model.
- If expected calibration error > 0.05, the UI label is **"model score"** rather than "confidence" ([DATA_FLOW.md §3.2](../architecture/DATA_FLOW.md#32-window-event)).

## 4. Cost metrics (offline, laptop)

`train_time_s`, `model_size_bytes` (joblib file), and `inference_us_per_window` (batch = 1, median of 10,000 calls). These are for ranking only. **Gateway figures come from E3/E4.**

## 5. Alert policy

- An alert opens when `score ≥ τ` for **k = 2 consecutive windows** from the same source. τ is chosen on validation (see [MODEL_SELECTION.md](https://github.com/akshat12bhardwaj/EdgeWatch/blob/e7c6db8791b14aa2280f29fbb71a0fc32c3d42ca/docs/ml/MODEL_SELECTION.md#3-hyperparameter-search)).
- The alert remains open while windows stay positive. A repeat alert for the same source and class is suppressed for 60 s.
- Severity:
  - `high`: flood or malformed class with score ≥ 0.9, or a source alerting for > 60 s.
  - `medium`: other attack classes with score ≥ τ.
  - `low`: rule indicators only (e.g., F24 wildcard subscribe; T6 has no ML label).
- Time-to-detect (lab) = alert open time − scheduled attack start. Report the median and p95 per family.
- Alert-level metrics are reported **in addition to** window-level metrics: alert precision, attack episodes detected / total, and time-to-detect.

## 6. Evidence for each alert (RQ4)

- RF/DT/HistGB: per-feature contributions by summing the decision-path contributions. TreeSHAP is used only if the `shap` package is approved; it is not installed, so the decision-path method is the default.
- LR: coefficient × standardised value.
- Show the top-5 features with their value and the benign median ("F11 refused ratio = 0.94; benign median = 0.00").
- **Wording rule:** evidence shows *what the model weighted*. It is not proof of an attack.
