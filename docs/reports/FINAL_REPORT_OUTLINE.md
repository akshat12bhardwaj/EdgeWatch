# Final Report Outline

Adapt the structure to the course format (Q-06). The target is a paper-style report.

1. **Abstract.** Problem, gap, method, headline measured results (after M5 only), limitation.
2. **Introduction.** MQTT's role; why the edge; the gap in one paragraph; RQ1–RQ3; contributions (RESEARCH_GAP_ANALYSIS §6).
3. **Background and related work.** Organised by theme, from LITERATURE_REVIEW §1–6; closest work P19, P27, P24 compared in a table.
4. **Threat model.** THREAT_MODEL §2–4, including the detectability matrix and its honest limits.
5. **System design.** Architecture, features (26 vs. 404), event contract, the provenance principle.
6. **Methodology.** Datasets and quality checks; splits; models; metrics; latency and resource measurement; lab set-up and safety.
7. **Results.** RQ1 (Tables 1–3), RQ2 (Tables 4–5, stage-share figure), RQ3 (Table 6), RQ4, Pareto.
8. **Discussion.** What the results mean for practitioners; comparison with reported numbers; when "lightweight" is lightweight.
9. **Demonstration.** Edge Watch console; how it maps to the measurements (VISUALIZATION_RESEARCH_MAPPING).
10. **Limitations and threats to validity.** From LIMITATIONS.md and EVALUATION_PROTOCOL §10.
11. **Conclusion and future work.** TLS, physical devices, MQTT 5, mitigation studies.
12. **Reproducibility statement.** Code, configs, versions, dataset sources; what cannot be shared.
13. **References.** From REFERENCES.md; only results reviewed at FT level are quoted.
14. **Appendices.** Search protocol; paper matrix; full feature table; hardware details; claim-audit table.
