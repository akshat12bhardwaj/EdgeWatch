import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { alertOrder, apply, classText, demoStages, deviceDirectory, devicesOf, empty, episodeOutcomes, monitorState, overview, percentile, provenanceState } from "./store";

const event = (event_type: string, extra: object = {}) => ({ event_type, ts: 1, run_id: "r1", provenance: "live", ...extra }) as any;
const alert = (id: string, severity: string, start = 1) => event("alert", { alert_id: id, severity, start_ns: start });

describe("provenance honesty", () => {
  it("is none before any event and ok for a single value", () => {
    expect(provenanceState(empty)).toBe("none");
    expect(provenanceState(apply(empty, [event("window", { source_key: "s" })], 1))).toBe("ok");
  });
  it("is an error when mixed or missing in one run", () => {
    expect(provenanceState(apply(empty, [event("resource"), event("resource", { provenance: "replay" })], 1))).toBe("error");
    expect(provenanceState(apply(empty, [event("resource", { provenance: undefined })], 1))).toBe("error");
  });
  it("resets on a new run, so two runs never mix", () => {
    const first = apply(empty, [event("run_marker", { marker: "run_start" }), event("window", { source_key: "s" })], 1);
    const second = apply(first, [event("run_marker", { marker: "run_start", run_id: "r2", provenance: "replay" })], 2);
    expect(second.windows).toEqual([]);
    expect(second.provenances).toEqual(["replay"]);
    expect(provenanceState(second)).toBe("ok");
  });
  it("ignores events from another run", () => {
    const s = apply(empty, [event("run_marker", { marker: "run_start" }), event("window", { run_id: "old", provenance: "replay", source_key: "x" })], 1);
    expect(s.windows).toEqual([]);
    expect(s.provenances).toEqual(["live"]);
  });
});

describe("alerts", () => {
  it("an update replaces its alert instead of duplicating", () => {
    const s = apply(empty, [alert("a", "medium"), alert("a", "high")], 1);
    expect(s.alerts).toHaveLength(1);
    expect(s.alerts[0].severity).toBe("high");
  });
  it("orders by severity, then newest", () => {
    const s = alertOrder([alert("l", "low", 9), alert("h1", "high", 1), alert("h2", "high", 5), alert("m", "medium", 3)]);
    expect(s.map((a) => a.alert_id)).toEqual(["h2", "h1", "m", "l"]);
  });
});

describe("topology order stays stable", () => {
  it("keeps first-seen order so nodes do not jump", () => {
    const s = apply(empty, [event("window", { source_key: "b" }), event("window", { source_key: "a" }), event("topology", { nodes: [{ source_key: "c" }, { source_key: "a" }] })], 1);
    expect(s.order).toEqual(["b", "a", "c"]);
  });
});

describe("stream delay", () => {
  it("is not raised by an alert stamped with its older window start", () => {
    const s = apply(empty, [event("resource", { ts: 100 }), event("alert", { ts: 90, alert_id: "a", severity: "low", start_ns: 90 })], 100);
    expect(s.lastTs).toBe(100);
  });
});

describe("helpers", () => {
  it("percentile handles empty and ordinary input", () => {
    expect(percentile([], 0.5)).toBeNull();
    expect(percentile([3, 1, 2], 0.5)).toBe(2);
  });
  it("bounds retained windows", () => {
    const many = Array.from({ length: 1500 }, () => event("window", { source_key: "s" }));
    expect(apply(empty, many, 1).windows.length).toBe(1200);
  });
});

describe("wording rules", () => {
  it("never uses forbidden words in the interface", () => {
    const folder = fileURLToPath(new URL(".", import.meta.url));
    for (const name of readdirSync(folder).filter((f: string) => f.endsWith(".tsx") || f === "store.ts")) {
      expect(readFileSync(join(folder, name), "utf8").toLowerCase(), name).not.toMatch(/confirmed|blocked|neutrali[sz]ed|threat level/);
    }
  });
  it("never contains random numbers", () => {
    const folder = fileURLToPath(new URL(".", import.meta.url));
    for (const name of readdirSync(folder).filter((f: string) => f.endsWith(".tsx") || f === "store.ts")) {
      expect(readFileSync(join(folder, name), "utf8"), name).not.toMatch(/Math\.random/);
    }
  });
});

describe("command center helpers", () => {
  const win = (start: number, state: string, ground_truth: string | null, source_key = "s") => event("window", { window_start: start, window_end: start + 5, state, ground_truth, source_key, features: {} });
  it("overview counts only received events", () => {
    const s = apply(empty, [win(0, "normal", null, "a"), win(0, "normal", null, "b"), alert("x", "high")], 1);
    const o = overview(s);
    expect([o.activeSources, o.observedSources, o.alerts, o.severity.high, o.msgsPerS]).toEqual([2, 2, 1, 1, null]);
  });
  it("devices come from the latest scenario_devices marker", () => {
    const s = apply(empty, [event("run_marker", { marker: "scenario_devices", devices: { k1: "motion" } }), event("run_marker", { marker: "scenario_devices", devices: { k2: "door" } })], 1);
    expect(devicesOf(s)).toEqual({ k2: "door" });
  });
  it("episode outcome matches a model alert from the same source and time only", () => {
    const marker = event("run_marker", { marker: "scheduled_attack", source_key: "atk", start_ns: 100e9, end_ns: 130e9, family: "bruteforce" });
    const hit = event("alert", { alert_id: "a", kind: "model", source_key: "atk", start_ns: 100e9, last_window_ns: 105e9, severity: "medium" });
    const other = event("alert", { alert_id: "b", kind: "model", source_key: "else", start_ns: 100e9, last_window_ns: 105e9, severity: "medium" });
    const [o] = episodeOutcomes(apply(empty, [marker, other], 1));
    expect(o.alert).toBeNull();
    const [p] = episodeOutcomes(apply(empty, [marker, hit], 1));
    expect(p.alert?.alert_id).toBe("a");
    expect(p.ttd).toBe(10);
  });
});

describe("customer views stay truthful", () => {
  const h = (extra = {}) => ({ status: "ok", ids: "running", ids_enabled: true, ...extra });
  it("headline status follows backend facts in priority order", () => {
    expect(monitorState(null, true, empty, 0)).toBe("offline");
    expect(monitorState(h(), false, empty, 0)).toBe("offline");
    expect(monitorState(h({ status: "no_store" }), true, empty, 0)).toBe("not_started");
    expect(monitorState(h({ ids_enabled: false }), true, empty, 0)).toBe("paused");
    expect(monitorState(h({ ids: "stopped" }), true, empty, 0)).toBe("stopped");
    expect(monitorState(h(), true, empty, 0)).toBe("monitoring");
  });
  it("shows suspicious activity only for a recent alert", () => {
    const s = apply(empty, [event("alert", { alert_id: "a", severity: "high", start_ns: 100e9, last_window_ns: 100e9 })], 1);
    expect(monitorState({ status: "ok", ids: "running" }, true, s, 150)).toBe("alert");
    expect(monitorState({ status: "ok", ids: "running" }, true, s, 1000)).toBe("monitoring");
  });
  it("demo stages need evidence: a missed attack never reaches alert raised", () => {
    const marker = event("run_marker", { marker: "scheduled_attack", source_key: "atk", start_ns: 100e9, end_ns: 130e9, family: "flood_publish" });
    const calm = event("window", { source_key: "atk", window_start: 100, window_end: 105, state: "normal", features: {} });
    const missed = demoStages(apply(empty, [marker, calm], 1), 90, 200);
    expect([missed.scheduled, missed.begun, missed.suspicious, missed.alerted]).toEqual([1, 1, false, 0]);
    expect(demoStages(apply(empty, [marker], 1), 90, 95).begun).toBe(0);
    const hit = event("alert", { alert_id: "a", kind: "model", source_key: "atk", start_ns: 100e9, last_window_ns: 105e9, severity: "high" });
    const flagged = event("window", { source_key: "atk", window_start: 105, window_end: 110, state: "alert", features: {} });
    const caught = demoStages(apply(empty, [marker, flagged, hit], 1), 90, 200);
    expect([caught.suspicious, caught.alerted]).toEqual([true, 1]);
    expect(demoStages(apply(empty, [marker, flagged, hit], 1), 120, 200).scheduled).toBe(0); // an earlier demo's attack is not counted
  });
  it("names devices from runner metadata only, and never invents an identity", () => {
    const s = apply(empty, [
      event("run_marker", { marker: "scenario_devices", devices: { a: "motion", b: "motion", c: "door" } }),
      event("run_marker", { marker: "scheduled_attack", source_key: "x", family: "bruteforce", start_ns: 1, end_ns: 2 }),
      event("window", { source_key: "zz-9f3e" }),
    ], 1);
    const d = deviceDirectory(s);
    expect([d.get("a")!.name, d.get("b")!.name, d.get("c")!.name]).toEqual(["Motion sensor 1", "Motion sensor 2", "Door sensor 1"]);
    expect(d.get("x")!.kind).toBe("attacker");
    expect(d.get("zz-9f3e")).toMatchObject({ kind: "unknown", name: "Unknown device 9f3e" });
  });
  it("unknown classes fall back to their own name", () => {
    expect(classText("flood").title).toBe("Unusually high message traffic");
    expect(classText("new_thing").title).toBe("new thing");
  });
});
