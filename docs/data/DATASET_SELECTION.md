# Dataset Selection

**Status:** Shortlist proposed. Final selection at M1, after blockers D-01 to D-04 are resolved.
Evidence for each property is in [PAPER_MATRIX.csv](../research/PAPER_MATRIX.csv) and the literature review [§3](../research/LITERATURE_REVIEW.md#3-datasets-which-ones-actually-contain-mqtt-sq3).

## 1. Selection criteria

1. **Genuine MQTT traffic** with **MQTT-protocol attacks** (not just generic attacks on hosts that also run MQTT).
2. **Raw PCAP** available. This is required by ADR-03, one extractor for offline and live.
3. Labels that can be mapped to windows (per file, attacker IP, or time range).
4. A licence or terms that allow academic use. Redistribution is not needed.
5. **Independent lineage** from the training dataset, for cross-dataset tests.

## 2. Comparison

| Property | MQTTset (P08) | MQTT-IoT-IDS2020 (P09) | CICIoMT2024 (P22) | DoS/DDoS-MQTT-IoT (P15) | MQTT_UAD (P18) | Edge-IIoTset (P21) | CICIoT2023 (P20) |
|---|---|---|---|---|---|---|---|
| Genuine MQTT traffic | Yes, broker-side [R] | Yes [R] | Yes, Wi-Fi/MQTT subset [R] | Yes [U] | Yes [R] | Present in testbed [U] | **No** MQTT feature in the official list [R] |
| MQTT-specific attacks | Flood, publish flood, SlowITe, malformed, brute force [R] | MQTT brute force only (+ scans, SSH BF) [R] | Malformed; DoS/DDoS connect flood; DoS/DDoS publish flood [R] | 10 DoS/DDoS scenarios [U] | DoS, MitM, intrusion [R] | No (generic attacks) [R] | No |
| Environment | Simulated smart home (IoT-Flock), Mosquitto 1.6.2, 1 week [R] | VMs: 12 sensors + camera [R] | 40 IoMT devices (25 real) [R] | Physical testbed [U] | Test environment [R] | 7-layer testbed [R] | 105 devices [R] |
| PCAP | **Present in all 6 files, by parser (D-01 remains Open)** | Yes [R] | Yes [R] | Verify (D-02) | Verify (D-03) | Yes [U] | Yes [R] |
| Label generation | Per attack capture; packet class labels [R] | Per attack capture [R] | Per attack PCAP [R] | Verify | "Malicious frames tagged" [R] | Per attack | Per attack |
| Imbalance | Severe; benign ≫ attacks; authors balanced by replicating attacks [R] | Varies by class [R] | Varies (secondary counts unverified) | Verify | Verify | Severe [U] | Severe |
| Licence | Article CC BY 4.0 [R]. **Dataset licence conflicting and unresolved: README states Apache 2.0; Kaggle lists CC BY-NC-SA 4.0** (D-04) | Open access (IEEE DataPort) [R] | Not stated on page [R] | CC BY 4.0 per repository [U] | Data in Brief (open) [U] | Verify | Not stated |
| Lineage | Original | Original | Original (CIC) | Original | Original (León group; P07 lineage) | Original | Original |
| **Role** | **Primary train/test** | **Secondary + brute-force cross test** | **Cross-dataset target** | Candidate cross target (DoS) | Candidate | Benign-shift probe only (optional) | **Rejected** |

**Rejected or downgraded:**
- **CICIoT2023**: no MQTT protocol indicator and no MQTT attack in its official feature and attack lists [R].
- **BCCC-MQTT-IDS-2025**: aggregated from MQTTset, MQTT-IoT-IDS2020, and DoS/DDoS-MQTT-IoT [R, P19], so it is not independent. It could be used only for an "as-published" comparison with P19.
- **Edge-IIoTset**: its attacks are not MQTT-protocol attacks.

## 3. Label harmonisation for cross-dataset tests (E2)

| Harmonised family | MQTTset | MQTT-IoT-IDS2020 | CICIoMT2024 | Lab |
|---|---|---|---|---|
| `benign` | Legitimate | Normal | Benign (Wi-Fi/MQTT) | benign_sim |
| `flood` | Flood, DoS (MQTT-malaria) | — | DoS/DDoS connect flood, DoS/DDoS publish flood | T1, T2 |
| `malformed` | Malformed | — | Malformed data | T4 |
| `bruteforce` | Bruteforce | MQTT_BF | — | T5 |
| `lowrate` | SlowITe | — | — | T3 |
| excluded | — | Scan_A, Scan_sU, Sparta | Non-MQTT attacks (SYN/UDP/ICMP floods, recon, ARP spoofing) | — |

**Important consequences:**
- The cross-dataset overlap is only `benign`, `flood`, and `malformed` (MQTTset ↔ CICIoMT2024), plus `bruteforce` (MQTTset ↔ MQTT-IoT-IDS2020).
- `lowrate` exists only in MQTTset and our lab, so for it we can test only *within-dataset* and *lab transfer*.
- **Binary** (benign vs. attack) cross-dataset results are reported in addition to family-level results.

## 4. Do we need our own captures?

**Yes.** Our own lab captures are needed for three reasons, none of which the public datasets can satisfy:
1. RQ2 needs live traffic on the gateway.
2. RQ3 needs benign traffic that is independent of every training set.
3. Session-held-out splits need **multiple attack episodes per class**, and MQTTset has one capture file per attack type, by measurement. Episode boundaries inside each file are undocumented (DOCUMENTATION_AUDIT §12).

Lab data is **never** mixed into the training sets used for RQ1. It is used for RQ3 testing and as a separate "lab-trained" condition, which is reported separately.

## 5. Blockers

| ID | Question | Owner | How to resolve |
|---|---|---|---|
| D-01 | Does the MQTTset Kaggle release include raw PCAPs with IPs and timestamps? | S2 | **Open.** Availability is measured; suitability is inconclusive (DOCUMENTATION_AUDIT §12). Contact the authors (CNR-IEIIT). Fallback under team review |
| D-02 | DoS/DDoS-MQTT-IoT PCAP availability and scenario list | S2 | Read P15 full text |
| D-03 | MQTT_UAD format and independence from P15/P08 | S2 | Read P18 full text |
| D-04 | Licence/terms for CICIoMT2024 and MQTTset | S2 | Email the dataset owners if no terms are stated; record replies in [DECISIONS.md](../DECISIONS.md) |

## 6. Data handling rules

- Raw data stays outside Git, in `data/raw/`, with SHA-256 checksums in `data/MANIFEST.sha256`.
- Never redistribute dataset files or lab PCAPs. Publish only code and derived aggregate results.
- **MQTTset licence handling (D-04, F-58):** the applicable licence and redistribution rights are unresolved, and neither stated licence is assumed to apply. Until the authors or source confirm, follow the stricter practical limits: academic, non-commercial use, with attribution and no redistribution.
- Record each download's source URL, date, and version in `data/SOURCES.md`.
