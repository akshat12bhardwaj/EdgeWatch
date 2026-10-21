# Demo Storyboard and Runbook

**Goal:** an 8–10 minute demonstration that can be repeated identically. **Default attack:** T5 credential brute force. It has a clear, explainable signal (refused-CONNACK ratio), works in plaintext, and is low-risk. **Optional second attack:** T1 CONNECT flood.

## 1. Modes

| Mode | When | Badge | Source |
|---|---|---|---|
| **Live** | Lab network and gateway are healthy, and preflight passes | `LIVE` | Gateway pipeline |
| **Replay** (fallback) | Any preflight failure, or the venue forbids running the lab | `REPLAY` + magenta border | `results/<demo_run_id>/events.jsonl` recorded from a real live run |
| **Recording** (last resort) | Laptop failure | Video file, with a title card "Recorded on <date>, live run <id>" | Screen capture of a live run |

The presenter states the mode aloud at the start: *"What you are seeing is live / a replay of run X recorded on date Y."*

## 2. Preflight (T−30 min)

| # | Check | Command / action | Pass |
|---|---|---|---|
| 1 | Isolated network up, no uplink | Gateway: `ip route` shows no default route to the internet | ✔ |
| 2 | Broker running | Gateway: `systemctl status mosquitto` | active |
| 3 | Capture permissions | `tshark -i <if> -c 5 -f "tcp port 1883"` | 5 packets |
| 4 | IDS service | `/api/health` returns `ok` and the model id | ✔ |
| 5 | Model card matches the deployed model | P1 model id = card id | ✔ |
| 6 | Clock | Gateway time ±1 s of the laptop | ✔ |
| 7 | Replay file present | `events.jsonl` checksum matches the manifest | ✔ |
| 8 | Attack allow-list | Attack client prints the allow-list = broker lab IP | ✔ |
| 9 | Temperature | Gateway SoC < 60 °C idle | ✔ |

If any of checks 1–6 fail, switch to **Replay**.

## 3. Scenes

| # | Time | What happens in the system | What the audience sees | Presenter says (gist) |
|---|---|---|---|---|
| 0 | 0:00 | Nothing running | P1 "No run active"; empty topology with broker + gateway | "This is the gateway console. Right now, nothing is connected." |
| 1 | 0:30 | Runner starts the benign scenario (12 simulated devices, 2 zones) | Devices fade in; cyan particles; P3 rises to a steady rate; P4 starts showing ms values | "Every particle is a real MQTT message measured on the gateway." |
| 2 | 1:30 | Benign steady state, 2 min | **P5: "No alerts in this run"**; P7 CPU/RAM steady | "This quiet panel is a result: false alarms on benign traffic are what we measure in RQ3." |
| 3 | 3:30 | Runner writes `attack_scheduled_start` (bruteforce), then the attack client starts | Amber scheduled band appears on P3; the `attack_sim` node appears | "The runner has scheduled an attack and recorded the ground truth before it starts." |
| 4 | 3:40–4:00 | Windows from attack_sim show the refused ratio rising | Node pulses amber ▲; after 2 windows an alert ◆ ripples to the gateway; the P5 chip reads "matches scheduled attack" | "The model flagged it after N seconds. It is a prediction, which we check against the schedule." |
| 5 | 4:30 | Presenter clicks the alert | P6 opens: refused ratio 0.9x vs. benign median 0; CONNECT count; sparkline | "This is the evidence the model used. It explains the alert; it does not prove intent." |
| 6 | 5:30 | Attack ends (`attack_scheduled_end`) | Band closes; alert closes | — |
| 7 | 6:00 | (Optional) T1 CONNECT flood at a moderate rate | P4 Packets stage time rises; P7 CPU rises; possibly drops appear | "Look at where the time goes: in packets and features, not in the model. That is H2." |
| 8 | 7:00 | Presenter presses `R` | P8 Research view: E1 split bars, E3 stage bars, E5 FPR | "These are the measured results behind what you just saw." |
| 9 | 8:30 | — | Limitations card | "Plaintext MQTT, lab traffic, one device model. Here is what this does not show." |

The timings in scenes 3–7 are expectations to be confirmed in rehearsal. They are **not** claimed results.

## 4. Expected observations to verify in rehearsal

- No alert during scenes 1–2. If alerts appear, they are genuine false positives: **do not hide them**. Explain them as part of RQ3.
- An alert within the measured time-to-detect for brute force (from E5/E3 runs).
- P4 numbers are consistent with the E3 results for the same rate.

## 5. Recovery steps

| Symptom | Action | Time |
|---|---|---|
| Dashboard frozen / disconnected | Reload the browser; the stream resumes from the event store | 10 s |
| Broker crashed (flood) | Gateway: `sudo systemctl restart mosquitto`; say: "the flood crashed the broker – that is itself an observation" | 20 s |
| IDS service down | `sudo systemctl restart edgewatch-ids` | 20 s |
| Network failure | Switch to Replay: `python -m replay results/<demo_run_id>/events.jsonl` | 30 s |
| Anything else | Play the recording | 10 s |

## 6. Reset between runs

1. Stop the attack client and the simulator.
2. Runner writes `run_end`.
3. Restart the IDS service, which starts a new `run_id`.
4. Verify P1 shows the new run and "No alerts".
