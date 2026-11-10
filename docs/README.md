# Documentation

## Current guides

- [Setup](SETUP.md): Windows prerequisites, frozen model, broker, Wokwi and shutdown.
- [Architecture](ARCHITECTURE.md): devices, bridges, passive IDS, API and storage.
- [User guide](USER_GUIDE.md): Smart Home, Attack Simulator and Alerts.
- [Troubleshooting](TROUBLESHOOTING.md): common local-demo failures.
- [Project overview](../README.md), [contributor rules](../AGENTS.md) and
  [maintenance handoff](../CODEX_HANDOFF.md).

## Preserved technical and historical references

These describe earlier research designs or recorded engineering evidence. They
are retained for attribution, safety, model interpretation and reproducibility;
their old UI, hardware and experiment instructions are not the current demo.
No new experiments or training are required to operate this project.

- [Decisions and unresolved approvals](DECISIONS.md) (preserved unchanged),
  [architecture decisions](architecture/ARCHITECTURE_DECISIONS.md) and
  [2026-10-31 audit](DOCUMENTATION_AUDIT.md).
- [Feature definitions](architecture/FEATURE_SPECIFICATION.md),
  [event contract](architecture/DATA_FLOW.md) and
  [alert/model evaluation policy](ml/MODEL_EVALUATION.md), referenced by source.
- [Data dictionary](data/DATA_DICTIONARY.md),
  [quality protocol](data/DATA_QUALITY_PROTOCOL.md) and
  [dataset provenance and redistribution restrictions](data/DATASET_SELECTION.md).
- [Recorded technical report](reports/FINAL_TECHNICAL_REPORT.md).
- [Bibliography](research/REFERENCES.md) and [paper matrix](research/PAPER_MATRIX.csv).

Historical retention tables may mention publishing result files; this publication
excludes all datasets, captures, models and `results/`. Dataset licensing questions
remain unresolved; no redistribution rights are assumed. Existing third-party
notices and references are preserved; no new project license is implied.

## November 2026 consolidation

The cleanup reduced 55 Markdown files to 19. Eleven technical/historical documents
remain at their original paths alongside the current guides and instructions.
Forty superseded files were removed only after checking active references and
verifying a backup of the current documentation, including uncommitted changes.

- **Merged:** three installation guides into Setup/Troubleshooting; the final
  architecture draft into Architecture; current operating checkpoints and
  completion notes into the README, User guide and handoff.
- **Removed from the working tree:** duplicate handovers and execution logs,
  obsolete project plans/checklists/allocation, eight phase plans, old dashboard
  proposals/storyboards, empty report templates, and superseded research/model plans.
- **Archived in Git history:** the removed tracked documents remain available in
  [the previous publication](https://github.com/akshat12bhardwaj/EdgeWatch/tree/e7c6db8/docs).
  Retained documents link to immutable historical versions where needed.

No runtime source, tests, firmware, model constraints or protected evidence were
removed. Source references to the alert-policy document remain valid. Old launcher
error messages now point to the current setup guide.
