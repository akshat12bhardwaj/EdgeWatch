# Edge Watch: MQTT Intrusion Detection on an Edge Gateway

Documentation-first repository for a six-student IoT security research project.

**Start here:** [MASTER_PROJECT_BLUEPRINT.md](MASTER_PROJECT_BLUEPRINT.md).

## Status

- 2026-10-20: research and design baseline v0.1 created. No code, no installations, no experiments yet.
- Next gate: **M1**. Complete the full-text reviews ([PHASE_00_RESEARCH.md](implementation/PHASE_00_RESEARCH.md)), freeze the gap and the evaluation protocol, and record approval in [DECISIONS.md](DECISIONS.md).

## Conventions

- Evidence tags in the research docs: **[R]** reported by the authors · **[I]** our interpretation · **[U]** unverified.
- Paper IDs `P01`–`P36` and standards `S1`–`S2` are listed in [research/REFERENCES.md](research/REFERENCES.md).
- **Never** write a number into a results document unless it comes from a file in `results/`.
- Attack traffic only ever runs inside the isolated lab ([THREAT_MODEL.md §7](architecture/THREAT_MODEL.md#7-lab-safety-boundaries)).
- Code style: the team uses the Ponytail rules installed in Claude Code. In short: the smallest complete change; a test for every non-trivial piece of logic; known limits marked with `shortcut: <limit>, <when to upgrade>` comments.

## Layout

```
docs/
  README.md, MASTER_PROJECT_BLUEPRINT.md, PROJECT_CHARTER.md, IMPLEMENTATION_ROADMAP.md,
  TEAM_WORK_ALLOCATION.md, DECISIONS.md, RISKS_AND_MITIGATIONS.md, TESTING_STRATEGY.md, DEFINITION_OF_DONE.md
  research/  architecture/  data/  ml/  experiments/  presentation/  implementation/  reports/
```
