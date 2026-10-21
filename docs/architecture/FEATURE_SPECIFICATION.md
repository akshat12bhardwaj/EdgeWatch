# Feature Specification

**Extractor version:** `fx-0.1` (draft). Any change to this table bumps the version and invalidates cached feature tables.
**Unit of analysis:** a window of `W` seconds (default 5 s, tumbling) × `source_key` (source IP of packets sent **to** the broker port), plus the broker's replies to that source (ADR-04).

## 1. Input fields (tshark)

Live and offline use the same field list:

```
frame.time_epoch  ip.src  ip.dst  tcp.srcport  tcp.dstport  tcp.len
tcp.flags.syn  tcp.flags.ack  tcp.flags.reset  tcp.flags.fin
mqtt.msgtype  mqtt.len  mqtt.qos  mqtt.retain  mqtt.kalive
mqtt.conack.val  mqtt.topic  _ws.malformed
```

- Field names follow the Wireshark MQTT dissector. **S4 must verify them** against the installed tshark version with `tshark -G fields | grep -E "^F\s+.*\smqtt\."` and record the result here.
- `mqtt.topic` is read **only** to compute topic counts and wildcard flags. The topic string itself is never stored or used as a feature.

## 2. Features

| ID | Name | Definition (per window, per source) | Attack rationale | Available under TLS? |
|---|---|---|---|---|
| F01 | `pkts` | Packets from the source to the broker port | T1, T2 | Yes |
| F02 | `bytes` | Sum of `tcp.len` from the source | T2 | Yes |
| F03 | `syn` | TCP SYN (without ACK) count | T1, T7 | Yes |
| F04 | `rst` | TCP RST count (both directions) | T4, T7 | Yes |
| F05 | `fin` | TCP FIN count | T1, T5 | Yes |
| F06 | `conn_distinct` | Distinct source ports seen (≈ connections) | T1, T5 | Yes |
| F07 | `iat_mean` | Mean inter-arrival time of the source's packets (s; W if fewer than 2 packets) | T3 | Yes |
| F08 | `iat_std` | Std of inter-arrival time | T2, T3 | Yes |
| F09 | `mqtt_connect` | CONNECT count (msgtype 1) | T1, T5 | No |
| F10 | `mqtt_connack_refused` | CONNACK to the source with return code ≠ 0 | T5 | No |
| F11 | `mqtt_refused_ratio` | F10 / max(F09, 1) | T5 | No |
| F12 | `mqtt_publish` | PUBLISH count (msgtype 3) | T2 | No |
| F13 | `mqtt_subscribe` | SUBSCRIBE count (msgtype 8) | T6 | No |
| F14 | `mqtt_pingreq` | PINGREQ count (msgtype 12) | T3 | No |
| F15 | `mqtt_disconnect` | DISCONNECT count (msgtype 14) | T1, T5 | No |
| F16 | `mqtt_len_mean` | Mean `mqtt.len` | T2, T4 | No |
| F17 | `mqtt_len_std` | Std `mqtt.len` (the top P19 feature for MalariaDoS was a length-std feature [R]) | T2 | No |
| F18 | `mqtt_len_max` | Max `mqtt.len` | T2, T4 | No |
| F19 | `topics_distinct` | Distinct topics published or subscribed (count only) | T2, T6 | No |
| F20 | `qos_gt0_frac` | Fraction of PUBLISH with QoS > 0 | T2 | No |
| F21 | `retain_frac` | Fraction of PUBLISH with retain = 1 | T2 | No |
| F22 | `keepalive_max` | Max keep-alive in CONNECTs (0 if none) | **T3** (SlowITe abuses keep-alive [P04]) | No |
| F23 | `malformed` | Packets flagged `_ws.malformed` | T4 | No |
| F24 | `wildcard_sub` | SUBSCRIBEs whose topic filter contains `#` or `+` | T6 (rule indicator) | No |
| F25 | `ctx_broker_msgs` | All MQTT messages to the broker in the window (all sources) | DDoS context | Partially (packets) |
| F26 | `ctx_active_sources` | Distinct sources active in the window | DDoS context | Yes |

**Design target:** fewer than 30 features, all computable in one pass with O(1) state per source. This contrasts with 404 features in P19 [R]. Whether the compact set loses detection quality is part of E1 (compare against the "as-published" baseline features where available).

## 3. Window and edge cases

- Windows align to `floor(t / W) × W` on the gateway clock. In offline mode, `frame.time_epoch` from the PCAP is used.
- Sources with zero packets in a window produce **no row**. Idle sources are not classified.
- Long-lived connections (T3) span windows. F22 is carried from the CONNECT into later windows of the same TCP connection; the extractor keeps a per-connection keep-alive map that expires on FIN/RST.
- Broker replies are attributed to the destination source (e.g., CONNACK → F10).
- Missing MQTT fields (non-MQTT TCP packets on 1883) count toward F01–F08 only.

## 4. Excluded fields

| Field | Reason |
|---|---|
| IP addresses, ports, MAC addresses | Identity shortcuts: the model would learn "attacker = 10.x.x.y". P09 dropped IPs [R]; P08 dropped IPs and ports [R] |
| Absolute timestamps, `tcp.stream` | Time and order shortcuts (P30 "spurious correlations") |
| Client ID, username, password | Privacy; identity shortcut |
| Topic strings, payload bytes | Privacy; dataset-specific vocabulary does not transfer |
| TTL, window size, checksums | Testbed artefacts (P08 removed window size and checksum [R]) |

## 5. Dataset coverage of the input fields

| Dataset | PCAP available? | Fields available | Notes |
|---|---|---|---|
| MQTTset | **To verify (D-01)** | All, if PCAP | The CSV release dropped IPs and time, so features cannot be windowed from the CSV |
| MQTT-IoT-IDS2020 | Yes (P09) | All | Plaintext |
| CICIoMT2024 | Yes (P22) | All for Wi-Fi/MQTT PCAPs | Check whether IPs were anonymised |
| Lab captures | Yes | All | Ground truth from the run schedule |

## 6. Tests required (Phase 01)

1. A hand-crafted PCAP with known counts (3 CONNECT, 1 refused CONNACK, 10 PUBLISH) produces the expected F09–F12.
2. **Parity test:** feature rows from the offline path (PCAP file) equal those from the live path (`tshark -r` replayed through the streaming code) for the same capture.
3. Throughput micro-benchmark of the extractor on the laptop and on the RPi (feeds RQ2).
