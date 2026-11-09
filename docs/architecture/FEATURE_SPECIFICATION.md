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
- `mqtt.topic` is read **only** to compute topic counts and wildcard flags. The topic string itself is never stored or used as a feature. §8.1 gives the rules for the tshark path.

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
| MQTTset | **Present in all 6 PCAPs, by parser (D-01 remains Open)** | All, if PCAP; tshark not yet verified | The combined CSV removes IP addresses and absolute timestamps, according to `rawparsing_normal.py` and P08, so features cannot be windowed from it. **That script still retains `tcp.time_delta` and `mqtt.msg`.** The CSVs have not been opened, and the contents of the per-file CSVs are unknown |
| MQTT-IoT-IDS2020 | Yes (P09) | All | Plaintext |
| CICIoMT2024 | Yes (P22) | All for Wi-Fi/MQTT PCAPs | Check whether IPs were anonymised |
| Lab captures | Yes | All | Ground truth from the run schedule |

**`fx-0.1` is unaffected by the published CSV columns.** It excludes payload content and identifiers (§4), and it is computed from PCAPs. See DOCUMENTATION_AUDIT §12 (F-55, F-56).

## 6. Tests required (Phase 01)

1. A hand-crafted PCAP with known counts (3 CONNECT, 1 refused CONNACK, 10 PUBLISH) produces the expected F09–F12.
2. **Parity test:** feature rows from the offline path (PCAP file) equal those from the live path (`tshark -r` replayed through the streaming code) for the same capture.
3. Throughput micro-benchmark of the extractor on the laptop and on the RPi (feeds RQ2).

## 7. Implementation clarifications (T1, 2026-10-31)

**Version stays `fx-0.1`.** All 26 features and the no-row rule are kept. These rules settle what §2 and §3 left open, implemented in `src/ids/features.py` and tested in `tests/test_features.py`. They are **not** yet checked against real traffic or tshark.

### 7.1 Common rules

| Topic | Rule | Why it was needed |
|---|---|---|
| **Direction** | A packet is *to-broker* if its destination port is the broker port, *from-broker* if its source port is. Other traffic is ignored and counted. To-broker wins if both ports match | §2 names direction for only some features |
| **Attribution** | A to-broker packet belongs to its source. A from-broker packet belongs to its destination | §3 says replies are attributed to the source |
| **Default direction** | Features count **to-broker only**, unless listed otherwise. Only F04 and F10 use from-broker packets | §2 says "both directions" for F04 alone, and "to the source" for F10 |
| **Window** | `index = ts_ns // (W × 10⁹)`, in integer nanoseconds. A packet at exactly `kW` belongs to window `k`. W is 1, 5, or 10 s | Avoids floating-point boundary errors (U2) |
| **No-row rule** | A source gets a row only with at least one to-broker packet. Replies in a window with no such packet are dropped and counted (`reply_only_windows`) | Consequence: a late CONNACK can be lost, and F10 can undercount |
| **Reordering** | Events wait in a buffer and are applied in time order once the newest timestamp is at least 1 ms ahead. Older events arrive too late and are dropped and counted (`late_events`) | Measured MQTTset reversals reach 38 µs. Late events cannot alter final rows |
| **Message timing** | A message counts in the frame that completes it. Input adapters must do reassembly and attach messages this way | Messages can span frames |
| **Closing a window** | A window closes when the buffer passes its end, or at end of stream. A live timer uses `advance()` | Live traffic can stop |
| **Incomplete windows** | Rows from the first and last observed windows have `complete = False`. They are still emitted. `complete` is not a feature | The stream may start or stop inside them |
| **Grouping key** | `source_key` defaults to the source address. Callers supply the pseudonymising function. It is separate from the feature tuple | DATA_DICTIONARY §2 requires a hash, but salting belongs to the caller |
| **Sensitive data** | Topics are held only as a set for the open window, then discarded. From the tshark adapter they are run-scoped tokens, not text (§8.1). `MqttMessage` has no payload, client-ID, or credential field | §4 exclusions |

**Output order:** window, then `source_key`. Output does not depend on hash seed.

### 7.2 Every feature

"Persist" means state that survives between windows. **Only F22 has it.** Missing means the value when no qualifying event exists.

| ID | Definition | Event source | Direction | Type | Aggregation | Missing | Persist |
|---|---|---|---|---|---|---|---|
| F01 | Frames | Packet | To broker | int | Count | Always ≥ 1 | No |
| F02 | Sum of `tcp.len` | Packet | To broker | int | Sum | 0 | No |
| F03 | SYN without ACK | TCP flags | To broker | int | Count | 0 | No |
| F04 | RST | TCP flags | **Both** | int | Count | 0 | No |
| F05 | FIN | TCP flags | To broker | int | Count | 0 | No |
| F06 | Distinct source ports | Packet | To broker | int | Set size | Always ≥ 1 | No |
| F07 | Mean gap between consecutive packets, in seconds, inside the window | Timestamps | To broker | float | Mean | **W** under 2 packets | No |
| F08 | **Population** standard deviation of those gaps | Timestamps | To broker | float | Std | 0 with under 2 gaps | No |
| F09 | CONNECT messages | MQTT | To broker | int | Count | 0 | No |
| F10 | CONNACK with a non-zero code | MQTT | **From broker** | int | Count | 0 | No |
| F11 | F10 / max(F09, 1), **not clamped** | Derived | Mixed | float | Ratio | 0 | No |
| F12 | PUBLISH messages | MQTT | To broker | int | Count | 0 | No |
| F13 | SUBSCRIBE messages | MQTT | To broker | int | Count | 0 | No |
| F14 | PINGREQ messages | MQTT | To broker | int | Count | 0 | No |
| F15 | DISCONNECT messages | MQTT | To broker | int | Count | 0 | No |
| F16 | Mean remaining length of **all** messages, including zero-length pings | MQTT | To broker | float | Mean | 0 | No |
| F17 | **Population** standard deviation of those lengths | MQTT | To broker | float | Std | 0 with under 2 | No |
| F18 | Maximum of those lengths | MQTT | To broker | int | Max | 0 | No |
| F19 | Distinct PUBLISH topics and SUBSCRIBE filters | MQTT | To broker | int | Set size | 0 | No |
| F20 | Share of PUBLISH with QoS above 0 | MQTT | To broker | float | Ratio | 0 without PUBLISH | No |
| F21 | Share of PUBLISH with retain set | MQTT | To broker | float | Ratio | 0 without PUBLISH | No |
| F22 | Largest keep-alive of the source's connections open at any point in the window (see below) | CONNECT and TCP | To broker sets; both directions expire | int | Max | 0 | **Yes** |
| F23 | Frames flagged malformed by the input adapter | Adapter flag | To broker | int | Count | 0 | No |
| F24 | SUBSCRIBE **messages** with any filter containing `#` or `+` | MQTT | To broker | int | Count | 0 | No |
| F25 | MQTT messages from all sources | MQTT | To broker | int | Count | Can be 0 | No |
| F26 | Sources with at least one to-broker packet | Packet | To broker | int | Set size | Always ≥ 1 | No |

**F25 and F26** take the same value in every row of a window.

**Choices that could have gone another way:**
- **F05 to-broker:** consistent with F03; §2 names both directions only for F04. Broker FINs would otherwise mirror client behaviour.
- **F08, F17 population deviation:** the window is the full set of observed values, not a sample.
- **F11 not clamped:** a value above 1 means refusals exceed CONNECTs in that window. It is informative, and the §2 formula has no clamp.
- **F16–F18 all messages:** §2 says only "mean `mqtt.len`". Zero-length pings lower the mean.
- **F24 per message:** §2 says "SUBSCRIBEs whose topic filter contains". One SUBSCRIBE with two wildcard filters counts once.
- **F23 to-broker:** the threat is packets sent to the broker.

### 7.3 F22 state rule

This resolves audit finding F-31, where §2 and §3 conflicted. §3's carry-over rule is used.

- A CONNECT records its keep-alive against its connection (client, client port, broker).
- The value applies in the CONNECT's window and in later windows with a row for that source.
- **The first FIN or RST, from either side, expires the connection.** It still counts for the window in which it ended.
- **A new to-broker SYN on the same port** also expires the earlier connection.
- DISCONNECT does not expire it; the connection ends on FIN or RST.
- A connection opened before capture has no known value, so it contributes 0.

**Known limits:**
- A connection whose FIN or RST was missed stays open until end of stream, which can overstate F22 and use memory (measured in §8, T3.4 finding). **Optional hard limit (`max_open_connections`, 2026-11-09):** when set, the oldest client's oldest open connection is dropped once the total exceeds the limit, and `evicted_connections` counts it. Below the limit output is identical to `fx-0.1`, so the extractor version is unchanged. The IDS service, live and replay, sets 65,536 (OD-1 hard limit); offline tables leave it unset. Measured: 300,000 held connections retain about 25 MiB with the limit and about 102 MiB without (`results/ENG-P3-bounds/`). **Proposed expiry (`keepalive_expiry=1.5`, opt-in, version `fx-0.1+ka1.5`):** a connection whose client sent nothing for 1.5 × its keep-alive before a window began is dropped, as the MQTT broker must drop it. K = 0 never expires. It changed 0 of 100,370 rows on 29 lab runs (`results/ENG-OD1-expiry/`). Off by default until OD-1 is approved.
- **F23 is only valid from an adapter that can detect malformed packets.** A parser that cannot will report 0, which must not be read as "none". The tshark adapter sets it (§8).
- §2's target of O(1) state per source does not hold for F06, F19, and F22 (audit finding F-30).

### 7.4 Effect on earlier measurements

No feature table has ever been produced, so **no cached data is invalidated**. The D-01 reports came from temporary parsers, not this extractor.

| Earlier measurement | Effect |
|---|---|
| Row counts at W = 1, 5, 10 s; F26 values | Same rule (to-broker packets). **Still to be confirmed on real files with this extractor** |
| F25 summaries | Same definition (to-broker messages) |
| `retain` totals, distinct-topic totals, Report 1–2 per-client summaries | **Not comparable:** those combined both directions, and these features are to-broker only. `malformed`'s to-broker retain is 0 |
| Message-length means | To-broker in both. Reported per capture, not per window |
| Keep-alive summaries | Per capture, not the F22 window rule |

## 8. TShark adapter (T3, 2026-11-01)

**Version stays `fx-0.1`; no feature definition changed.** `src/ids/fields.py` replaces the §1 field list for the tshark path.

**Interface:** `read_pcap(pcap, tshark=None, stats=None)` yields `PacketEvent` one frame at a time. `parse_ek_lines(lines, stats=None)` is the same decoder without a process. The path comes from the argument, then `TSHARK_PATH`, then `PATH`, then the default Windows install. Failures raise `TSharkError`; invalid or cut-short output raises its subclass `TSharkOutputError`. Messages never quote tshark's output.

**Command:** `tshark -n -T ek -l`, with `tcp.desegment_tcp_streams`, `tcp.analyze_sequence_numbers`, and `tcp.reassemble_out_of_order` all `TRUE`, one pass, and no `-2` or `-M`.

**Fields:** `frame.time_epoch`, `ip.src`, `ip.dst`, `ipv6.src`, `ipv6.dst`, `tcp.srcport`, `tcp.dstport`, `tcp.len`, `tcp.flags.syn`, `tcp.flags.ack`, `tcp.flags.fin`, `tcp.flags.reset`, `mqtt.hdrflags`, `mqtt.len`, `mqtt.kalive`, `mqtt.conack.val`, `mqtt.topic`, `mqtt.topic_len` (T3.1, §8.1), `_ws.malformed.expert`.

| Case | Behaviour | `stats` key |
|---|---|---|
| Type, QoS, retain | From `mqtt.hdrflags` by position. QoS and retain are set for PUBLISH only | |
| Non-TCP frame | Skipped | `non_tcp_frames` |
| Bad or repeated time, address, or port; bad optional value | Frame skipped. Repeats include an ICMP error quoting TCP, where direction would be a guess | `bad_metadata_frames` |
| Missing `tcp.len` or flag | 0 or False | `missing_tcp_field_frames` |
| `hdrflags` and `len` counts differ, or a value is invalid | Packet kept, no messages | `mqtt_mismatch_frames` |
| Keep-alive or CONNACK count differs from its messages | Messages kept, value `None` for that frame | `mqtt_kalive_mismatch_frames`, `mqtt_conack_val_mismatch_frames` |
| Reserved type 0 or 15 | Passed on: counts in F16–F18 and F25, not as a type | `reserved_messages` |
| Topic fields do not fit the frame's messages | Messages kept, no tokens for **any** message in that frame | `topic_mismatch_frames` |

**Known limits:**
- **F23 means a dissector exception only.** Reserved types and QoS 3 dissect cleanly and are not flagged.
- **Offline files only.** Live capture is untested.
- **Windows and tshark 4.6.9 only.** Linux and Raspberry Pi behaviour is untested.

**Not Raspberry Pi ready.** tshark reached 6,765 MB on `capture_1w`, while Python stayed at 27 MB. Measured with `tshark -T ek` on that capture:

| Setting changed from the validated baseline | Peak | Conclusion |
|---|---:|---|
| None, stdout to a pipe or to NUL | 6,765 / 6,764 MB | Output buffering is not the cause |
| Desegmentation off | 6,765 MB | TCP stream reassembly is not a measurable cause here |
| Out-of-order reassembly off | 6,765 MB | Not a measurable cause here |
| MQTT dissector disabled | 6,763 MB | Not the cause |
| **Sequence analysis off** | **1,920 MB** | **Main cause: about 4.8 GB. It stays required, because T2's retransmission control miscounts without it** |
| Only `tcp.track_bytes_in_flight` off | 5,014 MB | About 1.75 GB of that. **Correct on all 6 captures and both T2 controls (T3.2), but not applied to the adapter** |
| All three off | 1,920 MB | Remaining cost is unrelated to these settings; its source was not isolated |

Memory grew steadily, at about 550 MB per million frames (about 570 bytes per frame), with no release in `capture_1w`. Whether closing a connection frees any of it was not isolated, because this capture's connections stay open.

**T3.2 finding (2026-11-01):** with in-flight tracking off, growth on `capture_1w` falls from 586 to 433 bytes per frame but stays linear. On invented traffic, closing connections released nothing measurable, so **no connection pattern bounds tshark's memory**. Details are in `edgewatch-data/reports/T3_2_INFLIGHT_MEMORY_EXPERIMENT.md`.

**Future task (not started):** bound memory without losing correctness. Evaluate a purpose-built decoder, or restarts on connection-safe boundaries. Measure on the real gateway.

**T3.3 finding (2026-11-02):** `src/ids/decoder.py`, an evaluation-only byte decoder, gave events and rows identical to this adapter on all 6 captures, with flat memory. It is not selected. **Its `malformed` flag is a different signal, so it does not give the same F23 on malformed traffic.** Its other differences are listed in `edgewatch-data/reports/T3_3_BOUNDED_DECODER_EVALUATION.md`.

**T3.4 finding (2026-11-02):** empty per-client F22 entries, found in T3.3, are now removed, with no feature changed. **Connections with no FIN or RST still stay in memory, about 200 bytes each, because §7.3 requires it.** Idle limits of 30 s or less change F22 on `capture_1w`. Longer ones expire nothing on the 6 captures, so those captures cannot select a limit. No limit is applied, and bounding this needs a decision. See `edgewatch-data/reports/T3_4_F22_STATE_LIFECYCLE.md`.

### 8.1 Topic processing (T3.1, 2026-11-01)

**Version stays `fx-0.1`; F19 and F24 keep their §7.2 definitions.** This replaces T3's "always 0" limit: from this adapter, a 0 now means none was seen, or the frame's topics were dropped and counted.

**Transient processing.** `mqtt.topic` and `mqtt.topic_len` are read only by `_topic_tokens` in `src/ids/fields.py`, while one frame is decoded. Each string becomes a token at once, and the decoder drops its references to the raw line and document before it hands over the event.

**Token.** `HMAC-SHA256(key, UTF-8 topic)` as 64 hex characters, plus a trailing `#` if the string contains `#` or `+`.

| Property | Rule |
|---|---|
| Key | 32 bytes from `secrets.token_bytes`, created at the start of each `parse_ek_lines` or `read_pcap` call. Held in a local variable only: never written, logged, or counted |
| Scope | Equal topics give equal tokens within a run. Tokens from different runs cannot be compared. **Feature values do not depend on the key** |
| Retained | The token, in `MqttMessage.topics`, only until the window closes. Neither length nor raw text is retained |
| F19 | Size of the set of tokens. Equal strings give equal tokens whatever the message type, so the count equals the count on the strings, except as listed under limits |
| F24 | The unchanged test in `features.py` finds the `#` flag. Hex digests contain neither character, so no token can match by chance |

**Wildcard detection.** It applies to the text of SUBSCRIBE filters as tshark delimits them, never to other fields. F24 ignores PUBLISH topics and UNSUBSCRIBE filters. **§7.2 says "containing", so `a+b` counts even though MQTT makes it an invalid filter;** a filter a broker would reject is still a probe worth flagging. Changing that would change the definition.

**Assigning topics to messages.** `mqtt.topic` is a flat list for the whole frame, walked in message order:

| Message | Values consumed | Check |
|---|---|---|
| PUBLISH | 1 | `2 + topic_len ≤ mqtt.len` |
| SUBSCRIBE | Until `2 + Σ(2 + topic_len + 1) = mqtt.len` | Must end exactly |
| UNSUBSCRIBE | Until `2 + Σ(2 + topic_len) = mqtt.len`, then discarded | Must end exactly. **T2 §9 omitted this: tshark 4.6.9 reports these filters in `mqtt.topic`** |
| Zero-length topic | One `topic_len` of 0, **no** `mqtt.topic` value, and no token | Seen on tshark 4.6.9 |

Every value must be consumed. Any misfit, or any invalid type or value, drops all the frame's tokens and adds 1 to `topic_mismatch_frames`. A will topic has its own tshark field and is not requested.

**Privacy boundary.**

| Place | Raw topic allowed? |
|---|---|
| tshark process and its stdout pipe | Yes, unavoidably |
| One frame's decoding in `parse_ek_lines` and `_topic_tokens` | Yes, transiently |
| `PacketEvent`, `MqttMessage`, aggregator state, `WindowRow`, `stats` | **No: tokens or numbers only** |
| Exceptions and logs | **No.** The module logs nothing. Errors quote neither the output nor a value, and invalid JSON leaves no `__context__` holding the raw line |
| Files and reports | **No.** The adapter writes no files |

Tests in `tests/test_fields.py` check these with invented sentinel strings. **A dashboard or API does not exist yet,** so that boundary is untested. They must take `WindowRow` values only.

**Measured on the 6 MQTTset captures (W = 5 s):**

| Measure | `slowite` | `bruteforce` | `capture_flood` | `capture_malariaDoS` | `malformed` | `capture_1w` |
|---|---:|---:|---:|---:|---:|---:|
| F19 sum over rows / max | 0 / 0 | 42 / 37 | 42 / 1 | 190,660 / 18,967 | 286 / 36 | 643,768 / 1 |
| F24 sum over rows / max | 0 / 0 | 2 / 2 | 0 / 0 | 0 / 0 | 80 / 4 | 0 / 0 |
| Distinct topics, to broker | 0 | 42 | 1 | 150,000 | 50 | 9 |
| Distinct topics, both directions (equal to T2 §3) | 0 | 47 | 1 | 150,000 | 54 | 9 |
| SUBSCRIBE messages / with a wildcard filter | 0 / 0 | 2 / 2 | 0 / 0 | 0 / 0 | 80 / 80 | 7 / 0 |
| `topic_mismatch_frames` | 0 | 0 | 0 | 0 | 0 | 0 |

**F19 sums count per window and per source, so they exceed the distinct totals.** Wildcard filters equal the D-01 parser's counts, which do not use tshark. All were valid under the MQTT rules, and no SUBSCRIBE had more than one filter, so the multi-filter path is proven only on synthetic input. Row counts, PUBLISH counts, and all other features were unchanged from T3. Rows from runs with different keys, and from an in-memory run on raw strings, had identical digests.

**Limits:**
- **Discarding is not erasing.** Python cannot wipe strings, so raw text can remain in freed memory, and in tshark's own memory, until overwritten. A memory dump of a running gateway could expose topics.
- **Tokens are pseudonyms, not anonymity.** Anyone holding the key could test guessed topics. The key is never stored, so this applies only during a run.
- **MQTT 5 SUBSCRIBE is not walked.** Its properties break the length rule, so the frame's topics are dropped and counted, and **F19 and F24 undercount for those clients**. A nonzero `topic_mismatch_frames` is the signal. The lab must use MQTT 3.1.1 or fix this before relying on F24.
- **Topics that are not valid UTF-8 can collapse.** tshark shows invalid bytes as U+FFFD, so two different invalid topics can share a token, and F19 undercounts.
- **A mismatch drops the whole frame's tokens,** including valid ones. This never invents a value, but it undercounts.
- **tshark's stderr is still quoted in `TSharkError`.** It was empty on all 6 captures, but its content is not under this project's control.
- **The wildcard flag shares the `topics` field,** which keeps `MqttMessage` and T1 unchanged. `MqttMessage` cannot itself reject raw text: T1 tests pass plain strings, so any future adapter must tokenize too.
