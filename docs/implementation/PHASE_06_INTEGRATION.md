# Phase 06: Integration and Benign-Lab Evaluation → Milestone M5

1. **Objective and rationale:** connect the gateway, the lab, and the dashboard end-to-end; run E5 (RQ3); record the demo run.
2. **Prerequisites:** M4; Phase 05 working in replay mode.
3. **Inputs / outputs:**
   - Inputs: the deployed model (chosen at E6); the E5 scenarios.
   - Outputs: the E5 results; the demo run `events.jsonl` + recording; the integration test log.
4. **Tasks:**
   1. Run the live stream from the gateway into the dashboard over the lab network.
   2. Run the E5 benign scenarios (≥ 5 × 30 min). Record FPR and alerts per hour.
   3. Rehearse the storyboard live three times, and log any deviations.
   4. Record the official demo run (live). Archive its events for replay and screen-record it.
   5. Fill in the RESULTS_TEMPLATE sections for RQ2 and RQ3.
5. **Tools:** everything from the previous phases.
6. **Configuration decisions:** which run becomes the official demo run (team decision).
7. **Expected artefacts:** `results/E5*/`, `results/demo-<date>/`, the rehearsal log.
8. **Tests / verification:** the integration tests in [TESTING_STRATEGY.md](../TESTING_STRATEGY.md#3-integration-tests): I1–I5.
9. **Acceptance criteria:**
   - Three consecutive rehearsals without manual intervention, or with the recovery steps used successfully.
   - The E5 results have been recorded, whatever they show.
10. **Failure modes:**
    - Benign alerts during the demo. Do not retune the model on E5 data, because that would leak. Report them; if the team decides to retune, the change goes into a new model with a new exp ID and is evaluated on fresh benign runs.
11. **Dependencies:** Phases 04 and 05.
12. **Definition of complete:** M5 is reached when the demo can be repeated, and the E5 results and the demo archive exist.
13. **Rollback:** use the replay of the archived demo run.
