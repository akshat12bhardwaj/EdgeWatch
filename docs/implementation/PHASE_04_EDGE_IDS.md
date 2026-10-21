# Phase 04: Edge IDS on the Gateway → Milestone M4

1. **Objective and rationale:** run the full live pipeline (C4–C9) on the gateway and measure it (E3, E4, E7). This answers RQ2.
2. **Prerequisites:** M2 (extractor, lab); M3 candidate models; the gateway set up per SETUP_GUIDE §4.
3. **Inputs / outputs:**
   - Inputs: model artefacts + cards; lab scenarios.
   - Outputs: the `edgewatch-ids` service; `stage_latency.csv`, `resource.csv`, and `capture_stats.json` per run; the E3/E4 results.
4. **Tasks:**
   1. Write the live runner: tshark subprocess (`-l -T fields`) → `features.py` (the same module) → model → alert builder → SQLite/JSONL.
   2. Add the stage timers (DATA_FLOW §1) and the psutil sampler (1 Hz).
   3. Model loader: check the scikit-learn version and the feature order against the model card, and refuse on mismatch.
   4. Wrap it as a systemd service with a restart policy.
   5. **PILOT-E3:** find the rate at which capture drops begin, then set the E3 load levels.
   6. Run E3 (3 reps per rate per model), the E4 no-IDS baseline, and E7 (evidence on vs. off).
5. **Tools:** tshark, Python, psutil, systemd, `vcgencmd`.
6. **Configuration decisions:** CPU governor `performance`; cooling (heatsink + fan, recorded); whether capture runs on `eth0` or `lo` (broker co-located, so capture on the lab interface to include the real NIC path).
7. **Expected artefacts:** `src/ids/live.py`, `src/ids/alerts.py`, `deploy/edgewatch-ids.service`, `results/E3*/`, `results/E4*/`.
8. **Tests / verification:**
   - Replay a known lab PCAP with `tcpreplay` (or the runner) and check that the live window rows equal the offline rows for that PCAP (the parity test on the device).
   - Check that the psutil overhead run has been recorded.
9. **Acceptance criteria:**
   - The service runs for 1 h at the nominal rate without crashes or memory growth (RSS slope ≈ 0).
   - E3/E4 tables have been produced with the device details.
   - Whether the resource budget (SYSTEM_ARCHITECTURE §5) is met is recorded, honestly.
10. **Failure modes:**
    - Thermal throttling. Improve the cooling and flag affected runs.
    - tshark buffer drops. Increase `-B` (buffer size), and report the rate at which drops start.
    - Python GC pauses inflating p99. Record them; this is a real cost.
11. **Dependencies:** Phases 01–03.
12. **Definition of complete:** M4 is reached when the RQ2 results are drafted and the deployed model is chosen by E6 (team decision).
13. **Rollback:** the service can be disabled (`systemctl disable --now edgewatch-ids`); the broker keeps running unaffected because detection is passive.
