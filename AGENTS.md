# Agent rules: Edge Watch

Read [CODEX_HANDOFF.md](CODEX_HANDOFF.md) first. It holds the current state, commands, running services and protected files.

## Working style

- Minimize tokens: read targeted files and line ranges, search with grep/rg, and don't dump directories or re-audit the repository.
- Reuse existing code, components and patterns. Make the smallest change that fully solves the task.
- Make safe, reversible decisions on your own. Ask only for irreversible or outward-facing actions.
- Test focused first, then broad. Run the tests for what you touched, then `.venv\Scripts\python.exe -m pytest -q -m "not integration"` and `cd dashboard\web; npm test; npm run build`, then the full `pytest -q`.
- Compile-check Python (`python -m py_compile <files>`) before restarting any service.
- Report results faithfully, including failures. Don't claim anything you haven't verified.

## Hard limits

- Do not stage, commit or push without the owner's explicit approval.
- Do not modify or delete frozen models (`~/edgewatch-data/models/*`), `constraints-model.txt`, `results/`, or datasets and evidence under `~/edgewatch-data/{raw,reference,engineering,reports}`.
- Do not change IDS detection logic, features, thresholds or models, and never to make results look better. No retraining.
- Do not start scientific research experiments. This is a college demo.
- Keep everything software-only: no hardware, no cloud services, no paid simulators, no public exposure of the broker or API.
- Do not recreate the Advanced section (detector comparison, research results, diagnostics). The UI is Smart Home, Attack Simulator and Alerts.
- Do not stop, restart or kill user-owned processes (the API on :8000, the IDS on 18840, VS Code/Wokwi on :4000) or run `scripts/stop-edgewatch.ps1` / `lab/e2e_cc.py` while they run, unless the owner asks. Use isolated ports for tests.
- Pass `--out` to a scratch directory when running `lab.e2e`; its default writes into `results/`.
- Attacks stay local (loopback), bounded (at most 600 s) and rate-capped through `lab/safety.py`.
- UI honesty: never show simulated values as real sensor readings, never call a submitted command "done" without the device's ack, keep smoke alarms (device safety) apart from IDS alerts, and never claim Edge Watch blocks traffic. A frontend test forbids words like "blocked" and "confirmed" in the UI sources.
- Install nothing system-wide without approval. Project-local `.venv` and npm installs are fine.
