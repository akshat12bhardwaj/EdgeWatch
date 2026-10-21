# References

All DOIs were resolved through the Crossref API on 2026-10-20. IDs (`P01`…) are used throughout the documentation. The **Access** column shows how much of each source has been reviewed (see [SEARCH_PROTOCOL.md](SEARCH_PROTOCOL.md#7-access-levels-used-in-the-paper-matrix)).

## Standards and software

| ID | Reference | Access |
|---|---|---|
| S1 | OASIS. *MQTT Version 3.1.1*. OASIS Standard, 29 October 2014. https://docs.oasis-open.org/mqtt/mqtt/v3.1.1/mqtt-v3.1.1.html | To be read by the threat-model owner |
| S2 | OASIS. *MQTT Version 5.0*. OASIS Standard, 7 March 2019. https://docs.oasis-open.org/mqtt/mqtt/v5.0/mqtt-v5.0.html | To be read by the threat-model owner |
| P36 | R. A. Light, "Mosquitto: server and client implementation of the MQTT protocol," *Journal of Open Source Software*, 2(13), 265, 2017. doi:10.21105/joss.00265 | MD |

## Theme 1: MQTT vulnerabilities and attacks

| ID | Reference | Access |
|---|---|---|
| P01 | S. N. Firdous, Z. Baig, C. Valli, A. Ibrahim, "Modelling and Evaluation of Malicious Attacks against the IoT MQTT Protocol," *IEEE iThings/GreenCom/CPSCom/SmartData*, 2017. doi:10.1109/iThings-GreenCom-CPSCom-SmartData.2017.115 | MD |
| P02 | S. Andy, B. Rahardjo, B. Hanindhito, "Attack scenarios and security analysis of MQTT communication protocol in IoT system," *4th Int. Conf. EECSI*, 2017. doi:10.1109/EECSI.2017.8239179 | MD |
| P03 | A. J. Hintaw, S. Manickam, M. F. Aboalmaaly, S. Karuppayah, "MQTT Vulnerabilities, Attack Vectors and Solutions in the Internet of Things (IoT)," *IETE Journal of Research*, 69(6), 3368–3397, 2023 (online 2021). doi:10.1080/03772063.2021.1912651 | MD |
| P04 | I. Vaccari, M. Aiello, E. Cambiaso, "SlowITe, a Novel Denial of Service Attack Affecting MQTT," *Sensors*, 20(10), 2932, 2020. doi:10.3390/s20102932 | AB |
| P05 | G. Casteur, A. Aubaret, B. Blondeau, V. Clouet, A. Quemat, V. Pical, R. Zitouni, "Fuzzing attacks for vulnerability discovery within MQTT protocol," *IWCMC*, 2020. doi:10.1109/IWCMC48107.2020.9148320 | MD |

## Theme 2: MQTT-specific intrusion detection

| ID | Reference | Access |
|---|---|---|
| P06 | M. Husnain, K. Hayat, E. Cambiaso, U. U. Fayyaz, M. Mongelli, H. Akram, S. Ghazanfar Abbas, G. A. Shah, "Preventing MQTT Vulnerabilities Using IoT-Enabled Intrusion Detection System," *Sensors*, 22(2), 567, 2022. doi:10.3390/s22020567 | AB |
| P07 | H. Alaiz-Moreton, J. Aveleira-Mata, J. Ondicol-Garcia, A. L. Muñoz-Castañeda, I. García, C. Benavides, "Multiclass Classification Procedure for Detecting Attacks on MQTT-IoT Protocol," *Complexity*, 2019, 6516253. doi:10.1155/2019/6516253 | AB |
| P10 | M. A. Khan, M. A. Khan, S. U. Jan, J. Ahmad, S. S. Jamal, A. A. Shah, N. Pitropakis, W. J. Buchanan, "A Deep Learning-Based Intrusion Detection System for MQTT Enabled IoT," *Sensors*, 21(21), 7016, 2021. doi:10.3390/s21217016 | AB |
| P11 | F. Mosaiyebzadeh, L. G. Araujo Rodriguez, D. Macedo Batista, R. Hirata, "A Network Intrusion Detection System using Deep Learning against MQTT Attacks in IoT," *IEEE LATINCOM*, 2021. doi:10.1109/LATINCOM53176.2021.9647850 | AB |
| P12 | Q. Liu, H. B. Keller, V. Hagenmeyer, "A Bayesian Rule Learning Based Intrusion Detection System for the MQTT Communication Protocol," *Proc. 16th Int. Conf. on Availability, Reliability and Security (ARES)*, 2021. doi:10.1145/3465481.3470046 | MD |
| P13 | C. Prajisha, A. R. Vasudevan, "An efficient intrusion detection system for MQTT-IoT using enhanced chaotic salp swarm algorithm and LightGBM," *Int. J. of Information Security*, 21(6), 1263–1282, 2022. doi:10.1007/s10207-022-00611-9 | AB (one-sentence TL;DR) + SEC |
| P14 | A. Omotosho, Y. Qendah, C. Hammer, "IDS-MA: Intrusion Detection System for IoT MQTT Attacks Using Centralized and Federated Learning," *IEEE COMPSAC*, 2023. doi:10.1109/COMPSAC57700.2023.00093 | MD + SEC |
| P16 | A. Hanif, M. Ilyas, "Enhance the Detection of DoS and Brute Force Attacks within the MQTT Environment through Feature Engineering and Employing an Ensemble Technique," *Int. J. of Artificial Intelligence & Applications*, 15(4), 1–19, 2024. doi:10.5121/ijaia.2024.15401 | AB (venue flagged E5: check peer-review status) |
| P17 | H. Zeghida, M. Boulaiche, R. Chikh, A. Patel, A. Barros, A. M. Bamhdi, "XMID-MQTT: explaining machine learning-based intrusion detection system for MQTT protocol in IoT environment," *Int. J. of Information Security*, 24(3), 128, 2025. doi:10.1007/s10207-025-01036-w | MD + SEC |
| P19 | A. KouhiRonaghi, A. Habibi Lashkari, "MQTTFlowLyzer: interpretable TabNet-based flow-level MQTT intrusion detection for IoT," *The Journal of Supercomputing*, 82(5), 334, 2026. doi:10.1007/s11227-026-08485-7. Underlying thesis read in full: A. KouhiRonaghi, *An MQTT Application-Layer Traffic Analyzer for Interpretable Flow-Level Intrusion Detection and Zero-Day Threat Identification in IoT Environment Using TabNet*, MA thesis, York University, Aug. 2025 (YorkSpace) | FT (thesis version) |

## Theme 3: Datasets

| ID | Reference | Access |
|---|---|---|
| P08 | I. Vaccari, G. Chiola, M. Aiello, M. Mongelli, E. Cambiaso, "MQTTset, a New Dataset for Machine Learning Techniques on MQTT," *Sensors*, 20(22), 6578, 2020. doi:10.3390/s20226578 | FT (PMC7698741) |
| P09 | H. Hindy, E. Bayne, M. Bures, R. Atkinson, C. Tachtatzis, X. Bellekens, "Machine Learning Based IoT Intrusion Detection System: An MQTT Case Study (MQTT-IoT-IDS2020 Dataset)," in *Selected Papers from INC 2020*, LNNS vol. 180, Springer, 2021. doi:10.1007/978-3-030-64758-2_6 | FT (arXiv:2006.15340v3) |
| P15 | A. Alatram, L. F. Sikos, M. Johnstone, P. Szewczyk, J. J. Kang, "DoS/DDoS-MQTT-IoT: A dataset for evaluating intrusions in IoT networks using the MQTT protocol," *Computer Networks*, 231, 109809, 2023. doi:10.1016/j.comnet.2023.109809 | MD + SEC |
| P18 | J. Aveleira-Mata, H. Alaiz-Moretón, M. Bayón-Gutiérrez, M. T. García-Ordás, N. Prieto-Fernández, I. García-Rodríguez, "MQTT_UAD: MQTT Under Attack Dataset…," *Data in Brief*, 63, 112167, 2025. doi:10.1016/j.dib.2025.112167 | AB |
| P20 | E. C. P. Neto, S. Dadkhah, R. Ferreira, A. Zohourian, R. Lu, A. A. Ghorbani, "CICIoT2023: A Real-Time Dataset and Benchmark for Large-Scale Attacks in IoT Environment," *Sensors*, 23(13), 5941, 2023. doi:10.3390/s23135941 | FT (official dataset page) |
| P21 | M. A. Ferrag, O. Friha, D. Hamouda, L. Maglaras, H. Janicke, "Edge-IIoTset: A New Comprehensive Realistic Cyber Security Dataset of IoT and IIoT Applications for Centralized and Federated Learning," *IEEE Access*, 10, 40281–40306, 2022. doi:10.1109/ACCESS.2022.3165809 | AB (TechRxiv) + SEC |
| P22 | S. Dadkhah, E. C. P. Neto, R. Ferreira, R. C. Molokwu, S. Sadeghi, A. A. Ghorbani, "CICIoMT2024: A benchmark dataset for multi-protocol security assessment in IoMT," *Internet of Things*, 28, 101351, 2024. doi:10.1016/j.iot.2024.101351 | FT (official dataset page) |

## Theme 4: Lightweight and edge-deployed IDS

| ID | Reference | Access |
|---|---|---|
| P23 | Y. Mirsky, T. Doitshman, Y. Elovici, A. Shabtai, "Kitsune: An Ensemble of Autoencoders for Online Network Intrusion Detection," *NDSS*, 2018. doi:10.14722/ndss.2018.23204 | MD |
| P24 | M. Eskandari, Z. H. Janjua, M. Vecchio, F. Antonelli, "Passban IDS: An Intelligent Anomaly-Based Intrusion Detection System for IoT Edge Devices," *IEEE Internet of Things Journal*, 7(8), 6882–6897, 2020. doi:10.1109/JIOT.2020.2970501 | AB + SEC |
| P25 | N. Tekin, A. Acar, A. Aris, A. S. Uluagac, V. C. Gungor, "Energy consumption of on-device machine learning models for IoT intrusion detection," *Internet of Things*, 21, 100670, 2023. doi:10.1016/j.iot.2022.100670 | AB (via repository summary) |
| P26 | S. Hosseininoorbin, S. Layeghy, M. Sarhan, R. Jurdak, M. Portmann, "Exploring edge TPU for network intrusion detection in IoT," *J. of Parallel and Distributed Computing*, 179, 104712, 2023. doi:10.1016/j.jpdc.2023.05.001 | AB (arXiv snippet) |
| P27 | M. Akhi, C. Eising, L. Dhirani, "Securing IoT Using Lightweight TCN for Edge Deployment on Raspberry Pi 4," *IEEE Open Journal of the Communications Society*, 7, 442–460, 2026. doi:10.1109/OJCOMS.2025.3649498 | AB |
| P28 | P. Spadaccino, F. Cuomo, "Intrusion detection systems for IoT: Opportunities and challenges offered by edge computing," *ITU Journal on Future and Evolving Technologies*, 3, 408–420, 2022. doi:10.52953/WNVI5792 | MD |

## Theme 5: Evaluation methodology and generalisation

| ID | Reference | Access |
|---|---|---|
| P29 | R. Sommer, V. Paxson, "Outside the Closed World: On Using Machine Learning for Network Intrusion Detection," *IEEE Symposium on Security and Privacy*, 2010. doi:10.1109/SP.2010.25 | MD (foundational) |
| P30 | D. Arp, E. Quiring, F. Pendlebury, A. Warnecke, F. Pierazzi, C. Wressnegger, L. Cavallaro, K. Rieck, "Dos and Don'ts of Machine Learning in Computer Security," *31st USENIX Security Symposium*, 3971–3988, 2022. https://www.usenix.org/conference/usenixsecurity22/presentation/arp. Condensed version: "Lessons Learned on Machine Learning for Computer Security," *IEEE Security & Privacy*, 2023. doi:10.1109/MSEC.2023.3287207 | AB |
| P31 | G. Engelen, V. Rimmer, W. Joosen, "Troubleshooting an Intrusion Detection Dataset: the CICIDS2017 Case Study," *IEEE Security and Privacy Workshops (SPW)*, 2021. doi:10.1109/SPW53761.2021.00009 | AB |
| P32 | M. Sarhan, S. Layeghy, M. Portmann, "Towards a Standard Feature Set for Network Intrusion Detection System Datasets," *Mobile Networks and Applications*, 27(1), 357–370, 2022. doi:10.1007/s11036-021-01843-0 | AB |
| P33 | S. Layeghy, M. Portmann, "Explainable Cross-domain Evaluation of ML-based Network Intrusion Detection Systems," *Computers and Electrical Engineering*, 108, 108692, 2023. doi:10.1016/j.compeleceng.2023.108692 | AB |

## Theme 6: Explanation and visualisation

| ID | Reference | Access |
|---|---|---|
| P34 | S. Neupane, J. Ables, W. Anderson, S. Mittal, S. Rahimi, I. Banicescu, M. Seale, "Explainable Intrusion Detection Systems (X-IDS): A Survey of Current Methods, Challenges, and Opportunities," *IEEE Access*, 10, 112392–112415, 2022. doi:10.1109/ACCESS.2022.3216617 | MD |
| P35 | H. Shiravi, A. Shiravi, A. A. Ghorbani, "A Survey of Visualization Systems for Network Security," *IEEE TVCG*, 18(8), 1313–1329, 2012. doi:10.1109/TVCG.2011.144 | MD (foundational) |

## Notes

- **Name discrepancies to resolve:** P19's thesis calls its dataset *BCCC-MQTT-IDS-2025*, while the BCCC web page uses *BCCC-IoT-MQTT-IDS-2025*. Cite whatever the published journal version uses.
- **P03 year:** published online in 2021 and in an issue in 2023. Cite as 2023 and note "online 2021".
- **P13 author name:** Crossref lists "Prajisha C; Vasudevan A". Verify the full name on the publisher page.
- **P16 venue:** IJAIA (AIRCC). Do not rely on it for key claims until its peer-review status is confirmed.
