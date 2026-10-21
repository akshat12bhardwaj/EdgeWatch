# Definition of Done

## A task is done when

- [ ] Its acceptance criteria in the phase guide are met.
- [ ] Non-trivial logic has at least one test, and the tests pass.
- [ ] A second team member has reviewed it (TEAM_WORK_ALLOCATION §5).
- [ ] The docs it affects are updated: feature version, schema version, tracker.
- [ ] No credentials, PCAPs, or dataset files are committed.

## An experiment is done when

- [ ] It is listed in EXPERIMENT_TRACKER with the status `completed` (or `failed`, with notes).
- [ ] `results/<exp_id>/` has `metrics.json`, the config copy, `git_commit`, and environment versions.
- [ ] Uncertainty is reported (seeds and/or bootstrap CIs; repetitions for lab runs).
- [ ] Device and conditions are recorded for edge runs (EVALUATION_PROTOCOL §6).

## A dashboard panel is done when

- [ ] Its data source, empty state, error state, and interactions match the DASHBOARD_SPECIFICATION.
- [ ] Its row in VISUALIZATION_RESEARCH_MAPPING has been validated.
- [ ] It shows the correct provenance and uses no forbidden wording.

## The project is done when

- [ ] RQ1–RQ3 have been answered in the report with traced numbers (claim audit: 0 untraced).
- [ ] The reproducibility check passed (one E1 and one E3 configuration re-run by a different member).
- [ ] The demo has been rehearsed three times; replay and recording fallbacks are ready.
- [ ] All references resolve, and every quoted result is from a paper reviewed at `FT` level.
- [ ] LIMITATIONS.md is complete and reflected in the presentation.
