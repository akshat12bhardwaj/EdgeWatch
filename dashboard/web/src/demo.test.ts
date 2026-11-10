import { describe, expect, it } from "vitest";
import { focusedAlerts } from "./alerts";
import { SETTLE_S, simFlow, SimRun } from "./demo";
import { apply, empty } from "./store";

const event = (event_type: string, extra: object = {}) => ({ event_type, ts: 1, run_id: "r1", provenance: "live", ...extra }) as any;
const marker = event("run_marker", { marker: "scheduled_attack", source_key: "atk", start_ns: 100e9, end_ns: 130e9, family: "flood_publish" });
const hit = event("alert", { alert_id: "a1", kind: "model", source_key: "atk", start_ns: 105e9, last_window_ns: 110e9, severity: "high" });
const other = event("alert", { alert_id: "b9", kind: "model", source_key: "someone-else", start_ns: 105e9, last_window_ns: 110e9, severity: "low" });
const run = (extra: Partial<SimRun> = {}): SimRun => ({ running: false, pid: 1, started: 80, ended: 140, planned_s: 60, exit_code: 0, request: { benign: "layout", families: ["flood_publish"] }, ...extra });

describe("attack flowchart follows backend evidence only", () => {
  it("is Ready with nothing else claimed before a run", () => {
    expect(simFlow(empty, null, 0)).toMatchObject({ stages: ["running", "pending", "pending", "pending"], result: null });
  });
  it("does not treat a started run as attacking until the scheduled attack begins", () => {
    const f = simFlow(apply(empty, [marker], 1), run({ running: true, ended: undefined }), 90);
    expect(f.stages).toEqual(["running", "pending", "pending", "pending"]);
  });
  it("shows attacking and analyzing while the attack runs", () => {
    const f = simFlow(apply(empty, [marker], 1), run({ running: true, ended: undefined }), 110);
    expect(f.stages).toEqual(["done", "running", "running", "pending"]);
    expect(f.result).toBeNull();
  });
  it("reports a detection with its own alert and time, ignoring other sources", () => {
    const f = simFlow(apply(empty, [marker, hit, other], 1), run(), 150);
    expect(f).toMatchObject({ result: "detected", label: "Detected", ttd: 15 });
    expect(f.stages[3]).toBe("alert");
    expect(f.alerts.map((a) => a.alert_id)).toEqual(["a1"]);
  });
  it("waits before calling a quiet run missed, then says so without a time", () => {
    const s = apply(empty, [marker, other], 1);
    expect(simFlow(s, run(), 140 + SETTLE_S - 1).result).toBeNull();
    const f = simFlow(s, run(), 140 + SETTLE_S + 1);
    expect(f).toMatchObject({ result: "missed", label: "Not detected", ttd: null, alerts: [] });
    expect(f.stages).toEqual(["done", "done", "done", "warn"]);
  });
  it("separates stopped and failed runs from missed detections", () => {
    const s = apply(empty, [marker], 1);
    expect(simFlow(s, run({ stopped_by_user: true, exit_code: -15 }), 141).result).toBe("stopped");
    expect(simFlow(s, run({ exit_code: 2 }), 141)).toMatchObject({ result: "failed", label: "Failed" });
  });
});

describe("alert navigation uses verified alert IDs", () => {
  const a1 = { ...hit, start_ns: 1 }, b9 = { ...other };
  it("selects only the simulation's alerts and drops unknown IDs", () => {
    expect(focusedAlerts("a1", [b9, a1], []).map((a) => a.alert_id)).toEqual(["a1"]);
    expect(focusedAlerts("a1,zz", undefined, [a1]).map((a) => a.alert_id)).toEqual(["a1"]);
  });
  it("selects nothing for a missed simulation", () => {
    expect(focusedAlerts("", [a1, b9], [a1])).toEqual([]);
  });
});
