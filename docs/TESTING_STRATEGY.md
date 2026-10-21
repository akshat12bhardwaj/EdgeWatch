# Testing Strategy

The focus is on the parts where a silent bug would invalidate the research: features, splits, labels, timing, and provenance. In line with the team's Ponytail rule, every non-trivial piece of logic gets at least one small test. We do not chase coverage numbers.

## 1. Unit tests (pytest)

| ID | Target | Test |
|---|---|---|
| U1 | `features.py` | Hand-crafted PCAP → expected counts for F01–F26 |
| U2 | `features.py` | Window boundary: a packet at exactly t = kW belongs to window k |
| U3 | `features.py` | Keep-alive carry-over across windows (F22); expiry on FIN/RST |
| U4 | `splits.py` | No episode in two folds; S-time gap ≥ 2W; test indices never passed to `fit` |
| U5 | `labels.py` | Straddling windows marked `mixed`; the attacker's out-of-interval windows handled per the rules |
| U6 | Model loader | Refuses on a scikit-learn version or feature-order mismatch |
| U7 | Attack client | Exits non-zero for a non-allow-listed target |
| U8 | Replay service | Never emits `provenance=live` |
| U9 | Alert builder | k-consecutive rule; suppression window; status computed against the schedule |
| U10 | Evidence | Tree contributions sum to (score − base value) |

## 2. Parity tests

| ID | Test |
|---|---|
| PT1 | Offline (`tshark -r file`) vs. streaming path on the laptop produce identical rows |
| PT2 | The same comparison on the Raspberry Pi |

## 3. Integration tests

| ID | Scenario | Pass |
|---|---|---|
| I1 | Benign run of 10 min → events stored → dashboard shows the devices | Node count = simulated devices |
| I2 | Scheduled T5 → alert → status `matches scheduled attack` | Alert within the configured k windows after the attack rate stabilises |
| I3 | Broker restart mid-run | IDS survives; gap visible in P3; no crash |
| I4 | Dashboard disconnect/reconnect | Overlay shown; the stream resumes |
| I5 | Replay of the demo run | Same alert sequence and timing (±1 s) as the original |

## 4. Measurement validation

- psutil vs. `top`: CPU agrees within 5 percentage points (pilot).
- Stage timer overhead is measured with the timers disabled vs. enabled.
- tshark drop counter vs. the packets sent by the generator.

## 5. Commands

```bash
pytest -q                       # unit + parity (laptop)
pytest -q -m device             # parity on the Raspberry Pi
python -m ids.integration I2    # integration scenario (lab only)
```
