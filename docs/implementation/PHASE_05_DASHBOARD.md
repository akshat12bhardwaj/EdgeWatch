# Phase 05: Command-Center Dashboard → Milestone M5

1. **Objective and rationale:** build the Edge Watch console ([DASHBOARD_SPECIFICATION.md](../presentation/DASHBOARD_SPECIFICATION.md)) that makes the measured system visible without overstating it.
2. **Prerequisites:** M1 (the event contract is frozen). Work can start in parallel with Phases 01–04 using **synthetic** events.
3. **Inputs / outputs:**
   - Inputs: the event contract; a synthetic event file; later, replay files and the live stream.
   - Outputs: the FastAPI backend C10, the frontend C11, and the replay service C12.
4. **Tasks:**
   1. Write a synthetic event generator that emits events conforming to the schema with `provenance=synthetic`. Its only purpose is layout work.
   2. Backend: `/ws/events`, `/api/health`, `/api/results`, `/api/runs/<id>`. It stamps provenance on the server side.
   3. Frontend: P1–P7, in order of importance: P1 → P5 → P2 → P4 → P3 → P7 → P6. P8 comes last, once results exist.
   4. Replay service: read `events.jsonl`, preserve the original timing, force `provenance=replay`.
   5. Apply the design tokens from VISUAL_CONCEPT §3 and the reduced-motion handling.
   6. Usability walk-through with 2 people outside the team. Ask them: "What is connected? Is anything wrong? Is this live?"
5. **Tools:** FastAPI, uvicorn, Vite + TypeScript, Cytoscape.js, uPlot. All assets are bundled locally.
6. **Configuration decisions:** the render rate cap (10 Hz); the event buffer size; the colour tokens.
7. **Expected artefacts:** `dashboard/api/`, `dashboard/web/`, `replay/replay.py`, plus screenshots **labelled with provenance**.
8. **Tests / verification:**
   - Schema validation of every incoming event; malformed events are rejected and counted.
   - The replay service cannot emit `live` (unit test).
   - An alert outside a scheduled band renders `no scheduled attack`.
   - P8 snapshot test: the rendered values equal the JSON values.
9. **Acceptance criteria:**
   - All the panels' empty and error states have been implemented.
   - It runs offline (no network) on the presentation laptop at 1280×720 and 1920×1080.
   - The walk-through participants correctly identify the provenance and an active alert.
10. **Failure modes:**
    - The UI lags with many sources. Throttle rendering and aggregate the particles.
    - Fonts are missing offline. Bundle them.
    - Mixed provenance. This is treated as an error state by design.
11. **Dependencies:** M1 (the contract). Live mode needs M4.
12. **Definition of complete:** the storyboard scenes 0–8 run in REPLAY mode from a real lab run.
13. **Rollback:** the dashboard is read-only, so failures cannot affect detection. Fall back to the replay or the recording.
