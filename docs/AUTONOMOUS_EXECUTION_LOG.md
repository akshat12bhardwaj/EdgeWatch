# Autonomous Execution Log

One entry per iteration, in order. Nothing here is staged or committed. Evidence paths starting `reports/` are under `edgewatch-data`.

| # | Subgoal | What changed and why | Tests and result | Remaining limit |
|---|---|---|---|---|
| 0 | Inspect, reconcile | Ledger written. T1-T3.4 verified against code. Mosquitto 2.0.15 installed outside the repo, in `edgewatch-data/tools/mosquitto`, without admin rights | 238 passed at start | Conflict recorded: brief says "confirmed", rule 23 forbids it. UI uses normal, suspicious, alert |
| 1 | T3.5 F22 evidence | Isolated subclass, 4 limits, K=0, K=65535, long-lived, SlowITe-style, churn, every reference window | 0 changed rows on captures, weak evidence; eviction can erase a hold | **Decision OD-1** |
| 2 | A3 decoder gaps | IPv6 extension headers, bounded IP reassembly, MQTT 5 framing, a bad header no longer hides valid messages | 257 passed; lockstep against tshark: 12,081,179 events, 0 differences | Lockstep script reused from T3.3; results in `reports/t3_7/` |
| 3 | Lab | Stdlib MQTT client, benign profiles, T1-T6, allow-list, caps, schedule before first packet | Real broker test; loopback capture | Windows loopback only |
| 4 | T3.6 F23 evidence | Three signals compared on captures and on real T4 traffic | Decoder flags a superset on T4 | **Decision OD-2** |
| 5 | Offline pipeline | `pipeline.py`: schema validation, pseudonyms, diagnostics; tables stored outside Git, labelled engineering | Tests pass | Not research tables |
| 6 | Alerts, store, detector | Policy from MODEL_EVALUATION; refusal on mismatch | **Bug found by a test:** emitted alerts were aliased to the open one. Fixed | |
| 7 | IDS service | Live and replay share a code path; model and store failures tolerated | 312 passed | |
| 8 | MQTTset evaluation, leakage | ENG-M1, DQ-MQTTSET | Q10 = 1.0; 8 features alone above 0.95 | D-01 stays open |
| 9 | API | Health, alerts, traffic, control, WebSocket | 20 tests, including corrupt store and rejected control | |
| 10 | Dashboard | React P1-P8, no chart library | Build, 12 tests, screenshots | **Bug:** replay drew every node silent. Fixed |
| 11 | Model v1 | Depth-4 tree, perfect on held-out | **E2E missed brute force and malformed.** Model had memorised script rates | Low-rate run: 6/15 |
| 12 | Model v2 | Trained on varied rates | Low-rate run 15/15. **Probe: flagged 100% of heavy benign clients** | |
| 13 | Model v3 | Added heavy benign clients | 30/30, 0 false alerts. **Evasion probe: a 2,000 msg/s flood of 256-byte messages raised no alert** | |
| 14 | Model v4 | Varied flood sizes and keep-alives | 30/30. **Perf run: floods with constant-length messages raised no alert** | |
| 15 | **Live bug** | 43% of CONNECTs lost live but 0% from file. The timer's watermark dropped packets still in dumpcap's pipe. Added a 1 s live lag and a late-event counter | Regression test; loss 0% up to 50,000 msg/s | Adds 1 s of alert delay |
| 16 | **Orphan bug** | Hard-killing the IDS left dumpcap running. Fixed with a Windows job object | Asserted in the integration test | Linux path is by SIGPIPE or cgroup, not run |
| 17 | Model v5 | Constant-length floods, variable-length benign | 29/30. **Perf run: 123 false alerts from long-lived K=600 clients, introduced by v4's training** | |
| 18 | Model v6, frozen | Long-lived benign clients with varied keep-alives | 29/30, 0 false alerts; long-lived 0 alerts; E2E all checks pass | Section 6 of the report |
| 19 | **UI bugs** | Research view crashed on a null in a result file (guard added); stream delay spiked on alert timestamps | 13 frontend tests | |
| 20 | Final validation | Soak, privacy scan, hashes, report | See `docs/reports/FINAL_TECHNICAL_REPORT.md` | |
| 21 | SG-01 baseline (2026-11-09) | Re-inspected under the software-only brief | 334 unit + 2 integration pass, 13 frontend | Brief makes hardware out of scope; recorded in DECISIONS |
| 22 | SG-02 bounds | F22 hard limit 65,536 with eviction counter (OD-1 hard limit only); exact alert-state pruning; display-state retention; decoder fuzz test | 8 regression tests | 1.5K expiry not applied |
| 23 | SG-04 lab | Smart-home device profiles; T7 topic probing; `--families`, `--rate-factor`, `--lead-s`; device-profile file for topology | Real-broker test | T6, T7 untrained |
| 24 | SG-05 comparison | `lab-compare`: v6 vs LR, RF, rule, rate on identical held-out runs; new 5-min smart-home benign run | ENG-C1 | Post-freeze, no retuning |
| 25 | SG-07 API | Simulation control (loopback, bounded, tree-kill, watchdog), replay comparison, alert search, runs; Host allow-list; WS Origin check | 22 API tests | |
| 26 | SG-07 UI | Tabs Live/Simulate/Investigate/Compare/Research; overview KPIs, P9 analytics, device labels; phone-width CSS | 18 frontend tests, build | |
| 27 | **Bench bug** | ENG-P3 first timed model loading as inference (958 us); fixed to warm timing (35 us) | ENG-P3 | |
| 28 | SG-06 RQ1 analogue | `lab-splits` on dev runs | ENG-R1 | Engineering, not E1 |
| 29 | **Start-script bug** | A stale PID file with a reused PID would block start; now checked by command line | E2E | |
| 30 | **E2E hang** (2026-11-09) | `e2e_cc` hung 40 min: services started by the start script inherited `capture_output` pipes, so `subprocess.run` never saw EOF (its Windows timeout path re-waits unbounded). Script output now goes to a file; Chrome CDP/recv calls bounded; Chrome closed in `finally`; Compare check clicked the tab, not the action button | ENG-E2E-CC all 26 checks, 256 s, no orphans | A second session ran the same E2E on the same ports; one run was invalidated. Run E2E from one session at a time |

## Process notes

- **A mistake made during the run:** campaign 2's low-rate run started on a port already in use by another run. It was stopped within seconds and restarted on its own port. A few refused logins reached `campaign1/stealth`, which only v1 and later reference checks read. v6's headline results do not use it.
- **Every model after v1 is a new ID with results kept.** `results/ENG-*-v1` to `-v5` preserve each one's numbers. No result was overwritten without a copy.
- **Earlier live runs are invalid as measurements** before iteration 15, because of the watermark loss. Offline tables read files and are unaffected.
- **I said v4, then later v6, would be frozen regardless.** v4 was reopened because a missed 50,000 msg/s flood is not an acceptable limit. v6 stands: its remaining misses are listed, not fixed.

## Checkpoint 2026-11-09 (for recovery)

- **Done:** SG-01, SG-02, SG-04, SG-05, SG-09, SG-11. SG-06, SG-07 and SG-10 are done with stated limits (see PROJECT_COMPLETION_CHECKLIST).
- **Active:** SG-08 `lab/e2e_cc.py`. Run 1 hung: `script()` captured a pipe that the started services inherited. Another session (iot-project-c2) fixed this to use a temp file and is running the check on ports 8010/18860. Run 2 was invalidated by that session's concurrent stop. No `results/ENG-E2E-CC/metrics.json` from this session is valid.
- **Tests:** 367 Python unit, 18 frontend, frontend build; 2 integration tests passed at session start and have not been rerun since the service changes.
- **Next action:** read `results/ENG-E2E-CC/metrics.json` from the other session's run, then fix any failed check. Rerun `python -m pytest tests -m integration` when ports are free, then mark SG-03/07/08/12.

## Checkpoint 2026-11-09, later (supersedes the one above)

- **SG-08 passed:** ENG-E2E-CC 31/31 (run_started_epoch 1794209145), on the vite-8 build. Before that: one hang (inherited pipe, fixed by iot-project-c2), one run stopped by a concurrent session, and one selector bug (the Compare tab matched before the button), fixed and then passed.
- **Hang protections:** script output goes to a file, not a pipe; Chrome CDP calls are bounded and its whole tree is killed in `finally`; metrics are written atomically with a run stamp only after every step.
- **Also done:** 2 integration tests pass. Dev tooling upgraded (npm audit 0) with `@types/node` and `types: ["node"]` for the test file. pyflakes: two dead variables removed.
- **Open:** E1-E9 (approvals, D-04 datasets), the OD-1 expiry, and a fresh 1 h soak after these changes.

## Checkpoint 2026-11-09, end of session

- **Dashboard:** started with `start-edgewatch.ps1` (demo) at 13:34 and verified (health ok, live, model loaded, windows with predictions). **Left running for the owner.**
- **Soak v2: PASS** (ENG-P2-soak-v2 + ENG-P4 plateau). **OD-1 expiry** implemented opt-in (ENG-OD1-expiry: 0 rows changed). **ENG-W1** window-size analogue. Evidence cost added to ENG-P3 (that rerun overlapped other jobs).
- **Decisions:** review table in DECISIONS. OD-1 (expiry), OD-2, D-01/Option B, D-04 and DEC-02..05 need approval; nothing protected was changed.
- **Tests:** 371 unit, 2 integration, 18 frontend, build; ENG-E2E-CC 31/31 earlier today.
- **Next action:** only approvals remain. If OD-1 is approved, set `keepalive_expiry=1.5` in `ids/service.py` Pipeline and relabel or rebundle v6 for `fx-0.1+ka1.5`.

## Checkpoint 2026-11-09, customer experience redesign

- **Dashboard IA:** Overview, Security Demo, Alerts, Advanced (Detector Comparison, Research Results, System Diagnostics). Hash deep links: `#/demo`, `#/alerts?source=<key>`, `#/advanced/<section>`. `R` still opens Research. No API or detection change.
- **Honesty helpers (tested):** `monitorState`, `demoStages`, `deviceDirectory`, plain-language class/scenario/feature text in `store.ts`. Drawer time-to-alert now uses the `episodeOutcomes` definition (k-th window end).
- **E2E selectors updated:** `lab/e2e.py` (clear-state text), `lab/e2e_cc.py` (hash navigation, `[data-metric=alerts]`, `.alert-list .alert-row`; PID file honours `EDGEWATCH_DATA`).
- **Verified:** 23 frontend, 371 unit, 2 integration, build; `lab.e2e` 14/14 (output to scratch, `results/ENG-E2E` untouched); one 65 s Security Demo driven through the UI (alert after 7.2 s, 1/1 matched); 6 routes at 390/768/1366/1920 with no overflow or console errors.
- **Not rerun:** `lab.e2e_cc` (its start/stop scripts would stop the owner's running stack on :8000).

## Checkpoint 2026-11-09, Wokwi virtual smart home

- **Built:** `simulators/wokwi-smart-home` (PlatformIO esp32dev: DHT22, PIR, LED; MQTT with last will, `light/set` control, bounded reconnect) builds to `firmware.bin`/`.elf`. `lab/home.py` provides a persistent home broker (loopback v4+v6, ACL) and a read-only bridge writing `home/telemetry.json`. `lab.run --attach`, scenario `wokwi_only`, `/api/home`, `/api/home/light`, the Virtual Smart Home card, and `scripts/start|stop-wokwi-home.ps1`. Documented in INSTALL_AND_OPERATE §7.
- **Found and fixed on the live stack:** the bridge's `edgewatch/home/#` subscription raised a genuine low-severity wildcard rule alert (the bridge now subscribes to exact topics). API connect-probes from 127.0.0.1 were attributed to the Wokwi label (probes removed or moved to 127.0.3.3). After the fix: 0 Wokwi-labelled windows and 0 alerts over 45 s.
- **Verified:** 405 unit and integration tests, 25 frontend tests, build; IDS captured the home broker's traffic (bridge CONNECT, SUBSCRIBE and PING windows, normal); stop script leaves no processes.
- **Not verified:** a real Wokwi simulator run. It needs the owner to start it in VS Code, and the Private IoT Gateway (Wokwi paid plan) for `host.wokwi.internal`.
- **Live state:** home hub running on 18840 (`wokwi-home-pid.json`); the API was restarted twice with the start-script environment, and the PID file was updated.

## Checkpoint 2026-11-09, Wokwi serial bridge (outcome A)

- **Path:** Wokwi ESP32 → UART → RFC2217 `localhost:4000` (VS Code, current license; no paid gateway) → `lab.home` serial bridge (`127.0.3.10`) → home broker 18840 → IDS → dashboard. The ESP32 itself does not speak MQTT; the bridge publishes for it, and the docs and UI say so.
- **Verified live:** ROM boot lines received; DHT22 22.5 °C / 45 %; PIR clicked twice (1→0 each time); light 5/5 confirmed by the firmware, and the LED was seen lit; IDS 34 windows, all normal, 0 alerts on the device; flood_publish demo in `wokwi_only` mode alerted after 11.3 s, with the device normal throughout.
- **Fixed during verification:** serial line reassembly across read timeouts, and a single count per over-long line.
- **Observed:** restarting the hub ends the Wokwi run (the serial client disconnects); the simulator must be restarted. One light command in the first, uninstrumented session was not applied; the cause is unexplained.
- **Tests:** 419 Python, 25 frontend, build. Results and models untouched.

## Checkpoint 2026-11-09, Smart Home builder

- **Built:** the Smart Home floor plan (drag and drop, inspector, saved layout through `/api/home/layout`) and the Attack Simulator (attack against the layout, attacker shown outside the house). Navigation: Smart Home, Attack Simulator, Alerts, Advanced. The circular source map moved to Diagnostics. The hardware-equivalence statement is in the UI and docs (conceptual, not measured).
- **Honesty:** software devices show activity and IDS state only (their lab payloads are counters). Wokwi devices show readings only while reporting, never stale ones as current. A linked silent device reads "Quiet", not "Not running". Failed lab runs are shown as failed.
- **Fixed:** an attached run plus a device mix crashed (IndexError in labelling). It now has a regression test.
- **Verified:** 13/13 browser builder checks with trusted input; a live home run with 6 software devices plus the Wokwi ESP32, all normal; Message flooding alerted after 8.2 s with home devices normal; 434 Python and 30 frontend tests, build; no overflow at 390, 768 and 1366 px.

## Checkpoint 2026-11-09, all nine Smart Home devices

- **Built:** `lab/devices.py` device host: nine state machines, one MQTT client and stable loopback identity per software device, retained state, last-will status, events, and acked commands. Hub ACL for device topics; layout-following reader with exact subscriptions; `/api/home/devices/{id}/command` (per-type validation); `/api/home/start` and `/api/home/stop`. Per-type dashboard controls that wait for the ack, device-state visuals, and a smoke safety banner separate from IDS alerts.
- **Fixed during verification:** the reader thread died on a Windows file-replace collision (retrying atomic writes); controls leaked a pending command across devices (per-device keys); duplicate default names after removals; a new device inheriting a removed device's saved state (unique ids, pruning).
- **Verified:** 19/19 UI checks for all nine types (controls acked, visuals, two doors, removal, refresh, hub restart recovery, IDS observes each device as normal); attack with Wokwi plus 9 devices live: all online, control confirmed mid-attack, alert on attacker only after 8.7 s; 447 Python and 33 frontend tests.

## Checkpoint 2026-11-09, Advanced section removed

- **Removed:** advanced.tsx, research.tsx, views.tsx, panels.tsx, dashboard/api/compare.py; /api/compare, /api/compare/models, /api/results, /api/model; NetworkMap, useMedia and dead store helpers; their tests and 153 unused CSS rules. Old #/advanced links open Smart Home.
- **Kept:** IDS (including ids/baselines.py), models, training code, results/, and every endpoint the three remaining pages use.
- **Verified:** 437 Python and 30 frontend tests, typecheck, build; lab.e2e 14/14 (with a new three-sections check); browser: 3 tabs, no runtime errors or overflow at 1366 and 390 px.

## Checkpoint 2026-11-09, handoff to Codex

- **Added:** CODEX_HANDOFF.md (state, commands, running services, protected files) and AGENTS.md (working rules).
- **Test resource leaks fixed (tests only, plus socket cleanup on lab error paths):** sqlite's `with` commits but does not close, so integration tests now use `closing(...)` and the context manager; store fixtures close their stores; wire.Client closes its socket when connect fails. Full suite passes with `-W error::ResourceWarning`, with 0 unclosed connections.
