# Phase 00: Research Validation → Milestone M1

1. **Objective and rationale:** confirm (or narrow) the research gap before building anything. Round 1 left 18 papers at abstract or metadata level, and some of them could pre-empt our claims.
2. **Prerequisites:** the docs in `docs/research/`; library access to IEEE Xplore, ACM DL, and SpringerLink.
3. **Inputs / outputs:**
   - Inputs: [PAPER_MATRIX.csv](../research/PAPER_MATRIX.csv) and [SEARCH_PROTOCOL.md](../research/SEARCH_PROTOCOL.md).
   - Outputs: 18 full-text reviews; an updated matrix; a frozen gap analysis; a pre-registered evaluation protocol.
4. **Tasks:**
   1. Each student reviews their three papers with the [template](../research/LITERATURE_REVIEW.md#appendix-a-full-text-review-template), saved as `docs/research/reviews/<ID>.md`.
   2. **Priority reads:** P19 journal version, P14, P17, P27, P23. Each must answer "does it pre-empt RQ1–RQ3?"
   3. Round-2 database search (SEARCH_PROTOCOL §8). Log the hit counts.
   4. Re-run the gap-to-evidence table, then accept or narrow the strongest gap.
   5. Fix Δ for H1 and the alert threshold target. Freeze EVALUATION_PROTOCOL with a date.
   6. `git init` and commit the docs baseline (needs approval, see SETUP_GUIDE §2).
5. **Tools:** university library, Zotero (shared group library), this repository.
6. **Configuration decisions:** Δ (proposed 0.05); final title; whether MQTTset is primary (depends on D-01).
7. **Expected artefacts:** `reviews/*.md`, an updated `PAPER_MATRIX.csv` (no `NOT YET REVIEWED` left for assigned papers), RESEARCH_GAP_ANALYSIS v1.0, EVALUATION_PROTOCOL frozen.
8. **Tests / verification:** every DOI in REFERENCES.md resolves; every claim tagged [R] cites a table or section of the paper; a second student cross-checks each review.
9. **Acceptance criteria:** the team signs off on the gap statement, RQ1–RQ3, and H1–H3 in [DECISIONS.md](../DECISIONS.md); the novelty risks in RESEARCH_GAP_ANALYSIS §7 are each marked *cleared*, *narrowed*, or *accepted risk*.
10. **Failure modes:**
    - A paper pre-empts a gap. Narrow the claim (e.g., cross-dataset only), and do not hide the paper.
    - A full text is inaccessible. Ask the library or the authors, and mark the paper `INACCESSIBLE` in the matrix.
11. **Dependencies:** none (first phase).
12. **Definition of complete:** M1 recorded in DECISIONS.md with the date and the names of the people approving it.
13. **Rollback:** if the gap collapses, return to RESEARCH_GAP_ANALYSIS §1 and pick the next-strongest accepted gap (G4 cross-dataset, or G5 benign FPR) as the sole focus.
