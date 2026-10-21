# Final Presentation Plan

**Format assumed:** 20 min talk + 10 min Q&A. Adjust once the course requirements are known (open question Q-07 in [DECISIONS.md](../DECISIONS.md)).
**Core message:** *"Lightweight" MQTT intrusion detection has to be judged end-to-end, on the gateway, without leakage. We measured it, and the dashboard is the window onto those measurements.*

## Narrative

| # | Section | Min | Content | Visual | Source doc |
|---|---|---|---|---|---|
| 1 | The problem | 1.5 | MQTT brokers are central and often unauthenticated; the attack classes T1–T5 | One MQTT pub/sub diagram + attack icons | THREAT_MODEL |
| 2 | What research already achieves | 2 | ~99% accuracy on MQTTset and MQTT-IoT-IDS2020; gateway IDS exists; P19 as the closest work | Table: paper, dataset, reported accuracy, what was measured | LITERATURE_REVIEW |
| 3 | The gap | 2 | Random splits; model-only latency; no benign-lab FPR | Gap-to-evidence table (3 rows) | RESEARCH_GAP_ANALYSIS |
| 4 | RQ and contribution | 1 | Main RQ, RQ1–RQ3, hypotheses H1–H3 | One slide, three boxes | RESEARCH_GAP_ANALYSIS |
| 5 | Architecture | 2 | Lab → gateway → event store → console; one extractor for offline and live | Mermaid diagram from SYSTEM_ARCHITECTURE, redrawn | SYSTEM_ARCHITECTURE |
| 6 | Data, features, models | 2 | Why these datasets (CICIoT2023 has no MQTT); 26 features vs. 404; why tree models | Dataset comparison table; feature groups | DATASET_SELECTION, FEATURE_SPEC |
| 7 | **Demo** | 8 | Storyboard scenes 0–8 | Live console | DEMO_STORYBOARD |
| 8 | What it actually detects | (in demo) | Brute force, floods; what it *cannot* see (TLS, valid-credential abuse) | Detectability matrix | THREAT_MODEL §4 |
| 9 | Results vs. baselines | 2 | E1 split bars; E2 heatmap; E5 FPR | Charts from P8 | results/ |
| 10 | Edge cost and trade-offs | 1.5 | E3 stage breakdown; E4 CPU/RAM; E6 Pareto | Stacked bars; Pareto | results/ |
| 11 | Limitations and future work | 1 | Lab data; plaintext; one device; no mitigation | Bullet list | LIMITATIONS |

**Rules:**
- No result slide is finalised before its experiment is `completed` in [EXPERIMENT_TRACKER.md](../experiments/EXPERIMENT_TRACKER.md).
- Until then, slides show the *planned* chart with the label "to be measured".

## Speaker allocation (provisional)

| Sections | Speaker (role) |
|---|---|
| 1–4 | S1 (literature) |
| 5–6 | S2 (data) + S3 (ML) |
| 7–8 | S5 (dashboard) drives; S4 (gateway) operates the lab |
| 9–10 | S3 + S6 |
| 11 + Q&A moderation | S6 |

## Anticipated questions (prepare answers with evidence)

1. "Why not deep learning?" → ADR-05; P27 already covers TCN at the edge; the RQ is about evaluation.
2. "Isn't 99% already solved?" → E1 shows what remains under S-time (whatever the result is).
3. "Would this work with TLS?" → E8 / ADR-08; the honest answer is "reduced feature set".
4. "Is the attack in the demo real?" → It is real traffic from our scripted client in an isolated lab, scheduled with ground truth. It is not a real adversary.
5. "How does it compare with MQTTFlowLyzer?" → Different goals: they report model latency and accuracy with 404 features; we measure the end-to-end cost of a compact feature set on a gateway.

## Assets checklist

- [ ] Redrawn architecture diagram (SVG)
- [ ] Screenshots of the console **from a real run**, captioned with the run id and provenance
- [ ] Charts exported from `results/` with experiment IDs in the captions
- [ ] Backup recording of a live run
- [ ] One-page handout: RQ, setup, headline numbers (after M5)
