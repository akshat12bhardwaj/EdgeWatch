# Decisions Log and Open Questions

Architecture-level rationale is in [ARCHITECTURE_DECISIONS.md](architecture/ARCHITECTURE_DECISIONS.md). This file records **team decisions** (who decided, and when) and **open questions**.

## Decisions

| ID | Date | Decision | Ref | Decided by | Status |
|---|---|---|---|---|---|
| DEC-01 | 2026-10-20 | Adopt the documentation baseline v0.1 for review | — | (proposed by the AI assistant) | **Pending team approval** |
| DEC-02 | | Approve the gap, RQ1–RQ3, H1–H3 | RESEARCH_GAP_ANALYSIS | team | Pending (M1) |
| DEC-03 | | Fix Δ for H1 (proposal: 0.05 macro-F1) | EVALUATION_PROTOCOL | team | Pending (M1) |
| DEC-04 | | Approve ADR-01 to ADR-12 | ARCHITECTURE_DECISIONS | team | Pending (M1) |
| DEC-05 | | Final project title | RESEARCH_GAP_ANALYSIS §9 | team + supervisor | Pending |

## Open questions and blockers

| ID | Question | Owner | Needed by | Status |
|---|---|---|---|---|
| D-01 | Does MQTTset include raw PCAPs with IPs and timestamps? | S2 | M2 | Open, **critical** |
| D-02 | DoS/DDoS-MQTT-IoT PCAP availability and scenario list | S2 | M2 | Open |
| D-03 | MQTT_UAD format and independence | S2 | M2 | Open |
| D-04 | Licence/terms for MQTTset and CICIoMT2024 | S2 | M2 | Open |
| D-05 | Keep `data/` outside OneDrive sync? | S6 | Phase 01 start | Open (recommended: yes) |
| Q-01 | Team member names and skills, to map onto S1–S6 | all | M0 | Open |
| Q-02 | Is a Raspberry Pi 4/5 available (or can one be purchased)? If not, use the emulated-constraint fallback (ADR-06) | supervisor | M1 | Open |
| Q-03 | Can the lab use an isolated switch/AP, or only a host-only virtual network? | S4 + supervisor | M1 | Open |
| Q-04 | Does the course require ethics or safety approval for attack-traffic generation in a lab? | supervisor | M1 | Open |
| Q-05 | Course deadlines, to set milestone dates | all | M0 | Open |
| Q-06 | Report format (paper-style? page limit?) | supervisor | M3 | Open |
| Q-07 | Presentation length and format | supervisor | M4 | Open |
| Q-08 | Approval to install WSL2, tshark, Mosquitto, and paho-mqtt on the dev machines | each owner | Phase 01 | Open |
