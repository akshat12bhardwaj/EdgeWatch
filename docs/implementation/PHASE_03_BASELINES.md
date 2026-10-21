# Phase 03: Offline Baselines and Leakage-Controlled Evaluation → Milestone M3

1. **Objective and rationale:** answer RQ1 with experiments E1-a, E1, E2, and E9, and select candidate models for the gateway.
2. **Prerequisites:** M2 (feature tables and data-quality reports); a frozen EVALUATION_PROTOCOL.
3. **Inputs / outputs:**
   - Inputs: `windows.parquet` per dataset; `configs/*.yaml`.
   - Outputs: `results/E1*/`, `results/E2*/`, `results/E9*/`; model artefacts with model cards.
4. **Tasks:**
   1. Implement `splits.py` (S-rand, S-time with a 2W gap, S-episode, S-cross) with tests.
   2. Implement `train.py` / `evaluate.py` following TRAINING_PIPELINE §2 (Pipeline objects; test fold touched once).
   3. Run E1-a, the anchor: an RF on the published CSV with S-rand. Compare it with P08/P09 and explain the differences.
   4. Run E1 across 4 models × splits × 5 seeds, then E2 in both directions, then E9.
   5. Produce a calibration report for the top two models.
   6. Update EXPERIMENT_TRACKER.md after **every** run, including failures.
5. **Tools:** scikit-learn, pandas, matplotlib (for plots), pytest.
6. **Configuration decisions:** the hyperparameter grids (MODEL_SELECTION §3); the target FPR used for the threshold (default 1%).
7. **Expected artefacts:** metrics JSON, confusion matrices, model cards, and plots: split-comparison bars and the cross-dataset heatmap.
8. **Tests / verification:**
   ```bash
   pytest tests/test_splits.py -q   # no episode in two folds; gap respected; test never used in fit
   python -m ids.train configs/E1_rf_stime.yaml && python -m ids.evaluate results/E1_rf_stime
   ```
9. **Acceptance criteria:**
   - All the E1/E2 cells in the protocol are completed or explicitly deferred with a reason.
   - CIs are reported.
   - A second student reproduces one configuration within ±0.01 macro-F1.
10. **Failure modes:**
    - Near-perfect scores in every split. Run Q10/Q11 shortcut checks before believing them.
    - A class missing from a fold. Merge it into its family or report it as not evaluable.
    - Long RF training times. Reduce `n_estimators` for the grid search, then refit.
11. **Dependencies:** Phase 01.
12. **Definition of complete:** M3 is reached when the RQ1 results table is drafted in RESULTS_TEMPLATE and the candidate models are chosen for Phase 04.
13. **Rollback:** results are immutable per exp_id. Any re-run gets a new exp_id suffix (`E1_rf_stime_r2`).
