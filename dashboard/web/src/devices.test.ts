import { describe, expect, it } from "vitest";
import { addDevice, canBeWokwi, HUB, linkSources, look, MAX_DEVICES, mixFor, place, PlacedDevice, roomAt, sampleHome, summary, TYPES } from "./devices";

describe("device tiles show the device's own state", () => {
  it("summarises each type, labelling simulated power", () => {
    expect(summary("plug", { on: true, power_w: 1500 })).toBe("1500 W (simulated)");
    expect(summary("thermostat", { current: 19.25, mode: "heating" })).toBe("19.3 °C · heating");
    expect(summary("smoke", { alarm: false, level: 4 })).toBe("Clear · level 4");
    expect(summary("lock", { locked: false })).toBe("Unlocked");
  });
  it("uses its own visual states, and a smoke alarm is a safety state, not a security one", () => {
    expect(look("door", { open: true })).toEqual({ classes: ["dv-open"], icon: "doorOpen" });
    expect(look("lock", { locked: false }).icon).toBe("unlock");
    expect(look("smoke", { alarm: true }).classes).toEqual(["dv-alarm"]);
    expect(look("light", { on: false }).classes).toEqual([]);
    for (const t of Object.keys(TYPES) as (keyof typeof TYPES)[]) expect(look(t, {}).classes.every((c) => c.startsWith("dv-"))).toBe(true);
  });
});

describe("smart home layout", () => {
  it("knows which room a point is in, and nothing outside the house", () => {
    expect(roomAt(100, 100)).toBe("living");
    expect(roomAt(800, 500)).toBe("garage");
    expect(roomAt(1050, 300)).toBeNull();
    expect(place([], 1050, 300)).toBeNull();
  });
  it("places devices inside their room, snapped and apart, never on the hub", () => {
    let d: PlacedDevice[] = [];
    for (let i = 0; i < 6; i++) d = addDevice(d, "light", 200, 150);
    expect(d.every((x) => x.room === "living" && roomAt(x.x, x.y) === "living" && x.x % 10 === 0)).toBe(true);
    for (const a of d) for (const b of d) if (a !== b) expect(Math.hypot(a.x - b.x, a.y - b.y)).toBeGreaterThanOrEqual(105);
    const near = place([], HUB.x + 5, HUB.y - 20)!;
    expect(Math.hypot(near.x - HUB.x, near.y - HUB.y)).toBeGreaterThan(78);
  });
  it("never repeats a default name after removals", () => {
    let d: PlacedDevice[] = [];
    for (let i = 0; i < 3; i++) d = addDevice(d, "door", 100, 400);
    d = d.filter((x) => x.name !== "Door sensor 2");
    d = addDevice(d, "door", 100, 400);
    d = addDevice(d, "door", 100, 400);
    expect(d.map((x) => x.name).sort()).toEqual(["Door sensor 1", "Door sensor 2", "Door sensor 3", "Door sensor 4"]);
  });
  it("caps the layout and gives unique ids", () => {
    let d: PlacedDevice[] = [];
    for (let i = 0; i < MAX_DEVICES + 3; i++) d = addDevice(d, "plug", 500, 100);
    expect(d.length).toBe(MAX_DEVICES);
    expect(new Set(d.map((x) => x.id)).size).toBe(MAX_DEVICES);
  });
  it("only sensors the Wokwi board really has can be Wokwi-backed, once each", () => {
    const home = sampleHome(true);
    expect(home.filter((x) => x.source === "wokwi").map((x) => x.type).sort()).toEqual(["climate", "light", "motion"]);
    expect(canBeWokwi(home, "camera")).toBe(false);
    expect(canBeWokwi(home, "light")).toBe(false);
    expect(canBeWokwi(home, "light", home.find((x) => x.type === "light")!.id)).toBe(true);
    expect(sampleHome(false).every((x) => x.source === "software")).toBe(true);
  });
  it("runs only software devices in the lab, as their traffic pattern, and links sources back by id", () => {
    const home = sampleHome(true);
    const mix = mixFor(home);
    expect(mix.length).toBe(home.length - 3);
    expect(mix).toContain(`${TYPES.camera.profile}@${home.find((x) => x.type === "camera")!.id}`);
    const links = linkSources({ "src-a": "bursty@d6", "src-b": "steady", "src-c": "wokwi_serial" });
    expect([...links.entries()]).toEqual([["d6", "src-a"]]);
  });
});
