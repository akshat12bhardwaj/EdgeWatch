# Threat Model

**Status:** Provisional. P01, P02, P03, and P05 must be reviewed in full and S1/S2 (the MQTT specifications) checked by S4 before M1.

## 1. System and assets

| Asset | Why it matters |
|---|---|
| A1 Broker availability | All IoT telemetry and commands pass through it |
| A2 Broker authentication/authorisation | Controls who can publish and subscribe |
| A3 Integrity of published messages | Wrong sensor values or commands can cause physical effects |
| A4 Confidentiality of topics and payloads | Telemetry can reveal occupancy, health, etc. |
| A5 The IDS itself (gateway CPU/RAM, event store) | An IDS that the attack traffic itself can overload is a liability |

## 2. Adversary

- **Position:** a host on the IoT LAN that can reach the broker on TCP/1883. Examples are a compromised device or a rogue client.
- **Capabilities:** opening arbitrary TCP connections and sending valid or malformed MQTT packets.
- **Not assumed:** compromise of the gateway itself, or on-path interception of other clients' traffic (MitM is listed as out of scope for detection, see §6).
- **Goals:** denial of service (A1), credential guessing (A2), protocol exploitation (A1/A5), and unauthorised data access (A4).

## 3. In-scope attack classes

| ID | Attack | MQTT mechanism | Datasets containing it | Lab reproduction (ADR-12) |
|---|---|---|---|---|
| T1 | CONNECT flood (DoS/DDoS) | Many CONNECTs exhaust connection slots | CICIoMT2024 [P22]; DoS/DDoS-MQTT-IoT [P15, U] | Scripted client(s), rate-limited, local broker only |
| T2 | PUBLISH flood / broker overload | High-rate PUBLISH, large payloads | MQTTset flood + "DoS" (MQTT-malaria) [P08]; CICIoMT2024 [P22] | Scripted |
| T3 | Low-rate DoS (SlowITe-style) | Long keep-alive; held connections | MQTTset SlowITe [P08, P04] | Scripted keep-alive hold |
| T4 | Malformed packets | Protocol-violating packets | MQTTset malformed (MQTTSA) [P08]; CICIoMT2024 [P22] | Scripted malformed CONNECT/PUBLISH (only against our broker) |
| T5 | Credential brute force | Repeated CONNECT with guessed credentials | MQTTset [P08]; MQTT-IoT-IDS2020 MQTT_BF [P09] | Scripted, against a lab account with a known weak password |
| T6 | Wildcard subscription / topic harvesting | SUBSCRIBE `#` on a permissive broker | Not clearly present in the reviewed datasets [U] | Lab-only scenario; **no training data → evaluated as a rule-based indicator, not by the ML model** |
| T7 | Generic reconnaissance (port scans) | TCP/UDP scans | MQTT-IoT-IDS2020 Scan_A, Scan_sU [P09] | Optional; not MQTT-specific |

## 4. Detectability matrix

How each attack could be seen by a **passive** observer on the gateway (ADR-02):

| Attack | Plaintext (1883): packet metadata + MQTT headers | TLS (8883): TCP/timing only | Broker log (either) | Expected difficulty [I] |
|---|---|---|---|---|
| T1 CONNECT flood | CONNECT count, SYN count, distinct ports | SYN count, connection rate | Connection log lines | Easy |
| T2 PUBLISH flood | PUBLISH count, length stats | Bytes, packet rate | — | Easy |
| T3 Low-rate DoS | Keep-alive value, long idle connections | Long-lived idle connections | Client connect with keepalive | **Hard**: low volume (P08 reports misclassification) |
| T4 Malformed | tshark malformed flag, CONNACK refusals, RST | RST patterns only | Protocol-error disconnects | Medium |
| T5 Brute force | CONNACK refused ratio | Many short connections | Auth-failure lines | Medium (P09: packet features are insufficient) |
| T6 Wildcard subscribe | Topic filter contains `#`/`+` | **Not visible** | Only with log level ≥ debug | Rule, not ML |
| T7 Scans | SYN/RST to many ports | Same | — | Easy |

**Honest limits.** A passive observer **cannot**:
- (a) tell a brute-force success from a legitimate login once credentials are correct;
- (b) see payload-level abuse (wrong sensor values from an authorised client);
- (c) see anything inside TLS except sizes and timing;
- (d) detect authorisation abuse by a client that has valid credentials and permitted topics.

## 5. Threats to the IDS itself

| Threat | Effect | Measurement / mitigation |
|---|---|---|
| Floods overload capture → packet drops | Detection becomes blind exactly during the attack | Report tshark drop counts per run (RQ2). This is a finding, not something to hide |
| Alert storm | Operator overload | De-duplication policy; report alerts per hour (RQ3) |
| Evasion by mimicry (attack rate kept within benign ranges) | Missed detection | Out of scope for training; discussed as a limitation |
| Poisoning of training data | Biased model | Training only on checksummed dataset PCAPs + lab runs |

## 6. Out of scope

- Mitigation or blocking (ADR-02).
- MitM and ARP spoofing. Present in some datasets (P18, P22), but they need a different observation point.
- Attacks on cloud back-ends, on firmware, and on physical/radio layers (BLE, Zigbee).
- MQTT 5-specific features (e.g., enhanced auth). Datasets are 3.1.1 (P08).
- Any traffic outside the isolated lab.

## 7. Lab safety boundaries

1. **Network:** an isolated switch/AP with no internet uplink, or a host-only virtual network. The gateway's Wi-Fi is disabled during attack runs unless it *is* the isolated network.
2. **Targets:** attack scripts accept a target only from an allow-list containing the lab broker's IP and refuse any other host. The allow-list is checked at start-up, and a mismatch aborts the run.
3. **Rates:** every attack script has a maximum rate and duration parameter, with defaults below the gateway's measured capacity. Higher rates are used only in the explicit stress experiment (E3).
4. **Credentials:** lab-only accounts with throw-away passwords, stored in `.env` (gitignored). Never reuse a real password.
5. **No public brokers, no scanning of other networks, no third-party devices.** This includes "test" brokers on the internet.
6. **Recovery:** the runbook ([DEMO_STORYBOARD.md](../presentation/DEMO_STORYBOARD.md#5-recovery-steps)) restarts the broker and gateway services. A run that crashes the broker is recorded as a result.
7. **Records:** every run writes a manifest with the operator, start/end times, scenario, and allow-list hash.
