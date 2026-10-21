# Results (TEMPLATE: do not fill before the experiments are run)

Every cell must link to a `results/<exp_id>/` file. Leave a cell as "—" until then.

## RQ1: Leakage-controlled and cross-dataset quality

**Table 1.** Macro-F1 [95% CI] by model and split (dataset: ___).

| Model | S-rand | S-time | S-episode | Δ (S-rand − S-time) | H1 (Δ > ___) |
|---|---|---|---|---|---|
| LR | — | — | — | — | — |
| DT | — | — | — | — | — |
| RF | — | — | — | — | — |
| HistGB | — | — | — | — | — |

**Table 2.** Per-class recall under S-time (deployed model).

**Table 3.** Cross-dataset results (E2): train ↓ / test →; binary and family level.

**Anchor (E1-a):** published-feature RF under S-rand = ___ vs. reported in P08/P09 = ___.

## RQ2: End-to-end edge cost (device: ___, OS: ___, versions: ___)

**Table 4.** Per-stage latency p50/p95/p99 (ms) by load level (E3).

**Table 5.** CPU % and RSS (MB): no-IDS baseline vs. IDS, by load (E4).

**Figure.** Share of processing time per stage (H2).

**Max sustainable rate** with < 0.1% capture drops: ___ msgs/s.

## RQ3: Benign-lab false positives (E5)

**Table 6.** FPR per window and false alerts per hour, per benign scenario; dataset-test FPR for comparison (H3).

## RQ4: Evidence cost (E7)

Added p95 latency per alert: ___.

## Pareto (E6) and the deployed-model decision

## Failed or deferred experiments

(List each one, with its reason.)
