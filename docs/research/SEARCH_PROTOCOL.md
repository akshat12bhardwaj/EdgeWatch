# Search Protocol and Search Log

**Status:** Initial search complete (round 1). Full-text review of papers marked `MD`/`AB` is assigned in [TEAM_WORK_ALLOCATION.md](../TEAM_WORK_ALLOCATION.md).
**Search date (round 1):** 2026-10-20
**Conducted by:** Claude Code (AI assistant), for team review. Every entry must be re-checked by the assigned student before it is cited in the final report.

## 1. Research questions driving the search

| ID | Search question |
|---|---|
| SQ1 | What attack surfaces does MQTT expose, and which attacks have been demonstrated? |
| SQ2 | Which IDS approaches target MQTT specifically, and on what data? |
| SQ3 | Which datasets genuinely contain MQTT traffic and MQTT-specific attacks? |
| SQ4 | Which IDS work has been deployed or measured on edge/gateway-class hardware, and what was measured (model only vs. full pipeline)? |
| SQ5 | What evaluation pitfalls (leakage, dataset artefacts, generalisation) are documented for ML-based NIDS? |
| SQ6 | How have alert explanation and security visualisation been approached? |

## 2. Sources searched

| Source | How it was used | Limitation |
|---|---|---|
| Crossref REST API (`api.crossref.org`) | Verified every DOI, title, author list, venue, year, volume, pages | Metadata only; abstracts often missing |
| Semantic Scholar Graph API | Retrieved abstracts and open-access PDF links | Rate-limited; several abstracts not retrieved |
| General web search engine | Discovery of recent (2023–2026) work and dataset pages | Snippets are secondary; never used as sole evidence for a result |
| PubMed Central (PMC) | Full text of MQTTset (PMC7698741) | Only open-access MDPI papers |
| arXiv | Full text of MQTT-IoT-IDS2020 (arXiv:2006.15340v3) | Preprint versions may differ from published versions |
| YorkSpace (York University repository) | Full text of the MSc thesis underlying MQTTFlowLyzer | Thesis, not the published journal version |
| Official dataset pages (UNB CIC) | CICIoT2023 and CICIoMT2024 attack/feature lists | Pages do not state licences |

**Not searched directly in round 1:** IEEE Xplore, ACM Digital Library, Scopus, and Web of Science search interfaces. IEEE and ACM papers were found through Crossref and web search instead. **Round 2 must repeat the core queries (Q1–Q6 below) directly in IEEE Xplore and ACM DL** through the university library and record the results in this file.

## 3. Queries executed (round 1, 2026-10-20)

| # | Query | Engine | Purpose |
|---|---|---|---|
| Q1 | `lightweight intrusion detection MQTT Raspberry Pi edge gateway inference latency 2024` | Web (extended) | SQ4 |
| Q2 | `MQTT intrusion detection machine learning MQTTset MQTT-IoT-IDS2020 2023 2025 journal` | Web (extended) | SQ2 |
| Q3 | `"Dos and Don'ts of Machine Learning in Computer Security" USENIX Security 2022 Arp` | Web | SQ5 |
| Q4 | `MQTT IDS cross-dataset generalization flow features broker-side detection 2024 2025` | Web (extended) | SQ2, SQ5 |
| Q5 | `MQTTFlowLyzer BCCC-IoT-MQTT-IDS-Augmented-2025 TabNet zero-day MQTT` | Web (extended) | SQ2 (closest competitor) |
| Q6 | `CICIoMT2024 MQTT attacks malformed data connect flood publish flood dataset features` | Web | SQ3 |
| Q7 | `Edge-IIoTset MQTT features mqtt.msgtype mqtt.topic attack types 61 features` | Web | SQ3 |
| Q8 | `CICIoT2023 46 features list protocol types MQTT attack categories 33 attacks` | Web | SQ3 |
| Q9 | Title look-ups (`query.bibliographic`) for 13 candidate papers | Crossref | Verification |
| Q10 | DOI look-ups for 30+ candidate papers | Crossref, Semantic Scholar | Verification, abstracts |
| Q11 | `Tekin ... energy consumption on-device machine learning IoT intrusion detection` | Web | SQ4 |
| Q12 | `Alatram DoS/DDoS-MQTT-IoT dataset Computer Networks 2023` | Web | SQ3 |
| Q13 | `XMID-MQTT Zeghida SHAP LIME MQTT-IoT-IDS2020` | Web | SQ6 |
| Q14 | `Passban IDS Raspberry Pi isolation forest LOF results CPU memory` | Web | SQ4 |
| Q15 | `"Exploring Edge TPU for Network Intrusion Detection in IoT"` | Web | SQ4 |

Pages fetched directly: UNB CIC CICIoMT2024 page; UNB CIC CICIoT2023 page; PMC7698741 (MQTTset); arXiv 2006.15340v3 (MQTT-IoT-IDS2020); YorkSpace thesis PDF (MQTTFlowLyzer).
Fetch failures (403/DNS): MDPI direct page, TechRxiv Edge-IIoTset, FIU PDF of Tekin et al., Abertay repository. These papers are marked `AB` or `MD`.

## 4. Inclusion criteria

1. Primary research, a dataset paper, an official specification, or a widely cited methodological paper (pitfalls, generalisation).
2. Directly addresses at least one of SQ1–SQ6.
3. Bibliographic data verifiable through a DOI or a stable official URL.
4. Preference for 2021–2026. Earlier work is included only if foundational (e.g., Sommer & Paxson 2010, Kitsune 2018) or if it introduced a dataset we may use (MQTTset 2020).

## 5. Exclusion criteria

| Code | Reason |
|---|---|
| E1 | Not about MQTT, not about IoT/edge IDS, and not methodological |
| E2 | Cannot be bibliographically verified |
| E3 | Duplicate (preprint superseded by the published version; the published version is cited) |
| E4 | Dataset that is not MQTT-focused **and** not needed for cross-dataset or edge comparison |
| E5 | Predatory or unclear peer-review status (flagged, not cited for results) |

## 6. Excluded or deferred items

| Item | Code | Note |
|---|---|---|
| N-BaIoT (Meidan et al., 2018, doi:10.1109/MPRV.2018.03367731) | E4 | Verified; botnet traffic, not MQTT. Background only |
| Bot-IoT (Koroniotis et al., 2019, doi:10.1016/j.future.2019.05.041) | E4 | Verified; MQTT not central. Background only |
| TON_IoT telemetry (Alsaedi et al., 2020, doi:10.1109/ACCESS.2020.3022862) | E4 | Verified; telemetry focus |
| Ullah & Mahmoud 2021 (doi:10.1109/ACCESS.2021.3094024) | E1 (partial) | Deep-learning anomaly detection over several datasets; not edge-measured. Optional background |
| CIC IoT Dataset 2022 (Dadkhah et al., PST 2022, doi:10.1109/PST55820.2022.9851966) | E4 | Profiling dataset |
| CICIDS2017 dataset paper (Sharafaldin et al., 2018, doi:10.5220/0006639801080116) | E1 | Cited indirectly through Engelen et al. |
| "A Review on Intrusion Detection Systems for MQTT in IoT Environments" (IIETA IJSSE) | E2/E5 | Venue details not verified; deferred |
| Memon et al. 2023 "Explainable IDS for IoMT" (KMIS, doi:10.5220/0012210300003598) | Deferred | Uses MQTT-IoT-IDS2020 with LIME; candidate for round 2 |
| Sharma et al. 2022 "MQTT equipped IDS for IoT devices" (doi:10.1109/icccis56430.2022.10037613) | Deferred | Found incidentally; not reviewed |
| Several 2025–2026 Raspberry Pi IDS papers found in Q1 (TinyML IIoT, Dual-GA RPi 5, LSTM-AE) | Deferred | Not MQTT-specific; round-2 candidates for the edge theme |
| BCCC-(IoT-)MQTT-IDS-2025 dataset | Covered via P19 | Aggregated from MQTTset, MQTT-IoT-IDS2020, DoS/DDoS-MQTT-IoT, so it is **not** an independent dataset for cross-dataset tests |

## 7. Access levels used in the paper matrix

| Code | Meaning |
|---|---|
| `FT` | Full text (or the official dataset page) was read in this session |
| `AB` | Abstract read; results are quoted only from the abstract |
| `SEC` | Some figures are known only from a secondary source; marked as such |
| `MD` | Only metadata verified; content **not yet reviewed**. Do not cite results until a student completes the full-text review |

## 8. Round 2 plan

1. Repeat Q1, Q2, Q4, and Q5 in IEEE Xplore, ACM DL, and Scopus. Restrict to 2021–2026. Record hit counts.
2. Forward-citation search ("cited by") on MQTTset, MQTT-IoT-IDS2020, and MQTTFlowLyzer to find newer competitors.
3. Full-text review of all `MD` and `AB` papers using the template in [LITERATURE_REVIEW.md](LITERATURE_REVIEW.md#appendix-a-full-text-review-template).
4. Re-run the novelty check in [RESEARCH_GAP_ANALYSIS.md](RESEARCH_GAP_ANALYSIS.md#6-novelty-risks) before the gap is frozen (milestone M1).
