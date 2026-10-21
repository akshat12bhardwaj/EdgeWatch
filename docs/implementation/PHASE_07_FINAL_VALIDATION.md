# Phase 07: Final Validation, Report, Presentation → Milestone M6

1. **Objective and rationale:** make sure every claim in the report and the presentation is backed by a result file, a reference, or a stated assumption.
2. **Prerequisites:** M5.
3. **Inputs / outputs:**
   - Inputs: all `results/`, docs, and the demo archive.
   - Outputs: the final report, slides, the reproducibility check, and the limitations section.
4. **Tasks:**
   1. **Reproducibility check:** a team member who did not run them re-runs one E1 configuration and one E3 configuration from a clean checkout.
   2. **Claim audit:** extract every number from the report and slides, then trace each one to a `results/` file or a reference. Remove anything that cannot be traced.
   3. Reference audit: resolve all DOIs again; confirm that the access levels are FT for every paper whose results we quote.
   4. Write the report from FINAL_REPORT_OUTLINE.
   5. Finalise LIMITATIONS.md.
   6. Hold two dress rehearsals of the presentation, one in replay mode.
5. **Tools:** a Crossref check script (in `tools/`), plus the report and slide tools the course requires.
6. **Configuration decisions:** what goes into the appendix versus the main text.
7. **Expected artefacts:** the final report, the slides, the claim-audit table (`docs/reports/CLAIM_AUDIT.md`), and the reproducibility log.
8. **Tests / verification:** the claim audit has 0 untraced numbers; all DOIs resolve.
9. **Acceptance criteria:** [DEFINITION_OF_DONE.md](../DEFINITION_OF_DONE.md) §Project is satisfied.
10. **Failure modes:**
    - The reproduction disagrees. Investigate before the presentation, and report the disagreement if it is not resolved.
11. **Dependencies:** all the previous phases.
12. **Definition of complete:** M6, the report is submitted and the presentation delivered.
13. **Rollback:** n/a.
