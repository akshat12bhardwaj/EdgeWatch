# Project Charter

## Problem

Published MQTT intrusion detectors claim near-perfect accuracy and sub-millisecond latency. Those claims come from evaluation set-ups that do not reflect deployment on an edge gateway: random splits, model-only timing, and no benign-traffic shift. See [RESEARCH_GAP_ANALYSIS.md §4](research/RESEARCH_GAP_ANALYSIS.md#4-problem-statement).

## Goal

Produce credible, reproducible measurements of how well, and at what cost, lightweight MQTT intrusion detection works on a gateway-class device. Present them through a live, honest demonstration.

## Scope

| In scope | Out of scope |
|---|---|
| Plaintext MQTT 3.1.1 broker-targeted attacks T1–T5 (T6 as a rule) | Mitigation / blocking |
| Datasets: MQTTset, MQTT-IoT-IDS2020, CICIoMT2024 | New deep-learning architectures |
| Isolated lab with simulated clients and scripted attacks | Public brokers, real third-party devices, any external network |
| Raspberry Pi 4/5 gateway measurements | Cloud deployment; microcontroller (TinyML) deployment |
| Edge Watch console (live / replay) | Production-grade SOC features (case management, users) |
| TLS-feature ablation (optional E8) | MQTT 5-specific attacks; MitM detection |

## Success criteria

1. RQ1–RQ3 are each answered with pre-registered experiments and confidence intervals, whatever the outcome.
2. Every number in the report traces to a `results/` file (claim audit, Phase 07).
3. The demo runs repeatably in live mode and has a working replay fallback.
4. A team member who did not run them reproduces one offline and one edge experiment.
5. Every reference is verified, and the access level of each is recorded.

## Constraints

- Six students. Team expertise is unknown, so the role allocations are provisional.
- Budget: one Raspberry Pi 4/5 with power supply, cooling, and SD card; one small switch. The other hardware is the students' own laptops.
- Ethics and safety: attack generation runs only in the isolated lab ([THREAT_MODEL.md §7](architecture/THREAT_MODEL.md#7-lab-safety-boundaries)).
- Datasets must not be redistributed.

## Stakeholders

The six students (S1–S6), the course supervisor (approves scope and safety), and the presentation audience.

## Approval

| Role | Name | Date |
|---|---|---|
| Team (all six) | | |
| Supervisor | | |
