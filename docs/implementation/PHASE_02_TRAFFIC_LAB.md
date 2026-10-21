# Phase 02: Isolated MQTT Traffic Lab → Milestone M2

1. **Objective and rationale:** build the lab that produces benign and attack traffic with recorded ground truth. It is needed for RQ2, RQ3, and the demo, and must be safe by construction (ADR-07).
2. **Prerequisites:** M1; the lab hardware (gateway RPi, a second machine for load generation, an isolated switch/AP); SETUP_GUIDE §4.
3. **Inputs / outputs:**
   - Inputs: scenario YAML files.
   - Outputs: benign simulator C1, attack client C2, experiment runner C14, a working broker, and lab runs with `manifest.json` + `schedule.json`.
4. **Tasks:**
   1. Set up the isolated network. Verify that it has no default route to the internet (`ip route`). Document the IP plan.
   2. Install and configure Mosquitto with authentication and binding to the lab interface (SETUP_GUIDE §4).
   3. **Benign simulator:** paho-mqtt with N devices from YAML (`topic`, `period_s`, `jitter`, `qos`, `retain`, `payload_bytes`, `reconnect_prob`). The seed is recorded.
   4. **Attack client:** one script per family T1–T5.
      - On start-up it checks the target against the allow-list and refuses anything else. It has rate and duration caps.
      - It writes `schedule.json` **before** it sends the first packet.
   5. **Experiment runner:** sequences the benign phase, then the attack, then the stop; emits `run_marker` events.
   6. Define the 5+ E5 benign scenarios (EVALUATION_PROTOCOL §4).
   7. S4 reviews the dataset attack tools (MQTT-malaria, MQTTSA, MQTT-PWN): their licence, what they do, and whether they are safe to run in the lab. Record the decision.
5. **Tools:** Mosquitto 2.x, paho-mqtt, PyYAML, tshark.
6. **Configuration decisions:** device count (start with 12, as in P09); the benign rate range; default attack rate caps below the gateway capacity measured in PILOT-E3.
7. **Expected artefacts:** `lab/sim/benign.py`, `lab/attacks/*.py`, `lab/runner.py`, `lab/scenarios/*.yaml`, and a lab network diagram in this file.
8. **Tests / verification:**
   - The allow-list unit test: the attack client exits non-zero for a non-allow-listed IP.
   - The schedule is written before the first packet, checked by a timestamp comparison in the capture.
   - A 10-minute benign run produces the expected msgs/s ±10%.
9. **Acceptance criteria:**
   - A full run (benign 5 min → T5 2 min → benign 3 min) completes with manifest, schedule, and PCAP.
   - The attack traffic is visible in the PCAP only from the attacker IP.
   - No packets leave the lab network, verified with a capture on the uplink port or with no uplink present.
10. **Failure modes:**
    - The broker refuses connections (wrong credentials or ACLs). Check `mosquitto.log`.
    - Clock skew. Timestamp schedules on the gateway, or use NTP within the lab only.
    - Wi-Fi interference. Use wired Ethernet.
11. **Dependencies:** Phase 00. Runs in parallel with Phase 01.
12. **Definition of complete:** an acceptance run is archived in `results/lab-acceptance/`.
13. **Rollback:** reflash the gateway's SD card from a saved image. Keep the image after the first successful setup.
