# Phase 01: Data Acquisition, Quality, and Feature Extractor → Milestone M2

1. **Objective and rationale:** obtain the datasets, verify them, and build the **shared** feature extractor (ADR-03). Every later number depends on this phase.
2. **Prerequisites:** M1; the dev environment from SETUP_GUIDE §3; dataset terms accepted (D-04).
3. **Inputs / outputs:**
   - Inputs: the MQTTset, MQTT-IoT-IDS2020, and CICIoMT2024 downloads.
   - Outputs: `data/raw/` with checksums; `windows.parquet` per dataset; data-quality reports; the extractor `fx-0.1` with tests.
4. **Tasks:**
   1. Download the datasets to `data/raw/<dataset>/` (outside OneDrive sync, D-05). Record each in `data/SOURCES.md`.
   2. `sha256sum` every file into `data/MANIFEST.sha256`.
   3. Resolve D-01: does MQTTset include PCAPs with IPs and timestamps? If not, MQTT-IoT-IDS2020 becomes primary; record this in DECISIONS.md.
   4. Verify the tshark MQTT field names (FEATURE_SPECIFICATION §1).
   5. Implement `src/ids/fields.py` (the tshark runner) and `src/ids/features.py` (a streaming windowed aggregator that works on an iterator of field rows).
   6. Write the tests: a hand-crafted PCAP with known counts, plus the offline/live parity test.
   7. Implement the label joins per the DATA_QUALITY_PROTOCOL §4 rules.
   8. Run checks Q1–Q12 and write `results/data_quality/<dataset>.md`.
5. **Tools:** tshark, Python stdlib, pandas + pyarrow (offline only), pytest. To create the hand-crafted PCAP, record a short session with `mosquitto_pub`/`mosquitto_sub` and tshark on a local broker.
6. **Configuration decisions:** W = 5 s (fixed for M2; E9 tests others); the source-key salt; how straddling windows are treated (excluded from test).
7. **Expected artefacts:** `src/ids/fields.py`, `src/ids/features.py`, `src/ids/labels.py`, `tests/test_features.py`, `data/features/...`, data-quality reports.
8. **Tests / verification:**
   ```bash
   pytest tests/test_features.py -q
   tshark -r data/raw/mqttset/<file>.pcap -T fields -e mqtt.msgtype | sort | uniq -c   # compare with P08 Table 3
   ```
9. **Acceptance criteria:** the feature tests pass; the parity test passes (identical rows); data-quality reports are reviewed by S2 and S3; class counts are documented; any discrepancy with the papers is documented.
10. **Failure modes:**
    - The tshark field names differ by version. Pin the tshark version and update the field list.
    - Memory blow-up on large PCAPs. Stream with `tshark -r ... -T fields` piped into the aggregator, and do not load the whole capture into pandas.
    - OneDrive locking files. Move `data/` outside OneDrive.
11. **Dependencies:** Phase 00.
12. **Definition of complete:** M2 is reached when Phase 01 and Phase 02 are both complete.
13. **Rollback:** raw data is read-only and checksummed. Feature tables can be regenerated, so delete `data/features/<version>` and re-run.
