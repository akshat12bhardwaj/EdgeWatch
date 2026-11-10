import { describe, expect, it } from "vitest";
import { deviceActivity } from "./smarthome";

const dev = (id: string, type: string, name: string) => ({ id, type, name, room: "living", x: 0, y: 0, source: "software" }) as any;
const rep = (ts: number, state: object, status: "online" | "offline" = "online", events: any[] = []) => ({ ts, state, status, events });
const devices = [dev("d1", "light", "Hall light"), dev("d2", "climate", "Thermometer")];

describe("network feed reports only observed device activity", () => {
  it("invents nothing from the first snapshot", () => {
    expect(deviceActivity(undefined, { d1: rep(10, { on: true }) }, devices, 10)).toEqual([]);
  });
  it("labels state updates, readings and acknowledgements by type", () => {
    const prev = { d1: rep(10, { on: false }), d2: rep(10, { temperature: 21 }) };
    const next = { d1: rep(12, { on: true, ack: "c1" }), d2: rep(13, { temperature: 21.2 }) };
    expect(deviceActivity(prev, next, devices, 13).map((e) => `${e.who}: ${e.what}`)).toEqual(["Hall light: command acknowledged", "Thermometer: reading received"]);
  });
  it("reports disconnects, and ignores topics that are not configured devices", () => {
    const out = deviceActivity({ d1: rep(10, {}), x9: rep(10, {}) }, { d1: rep(10, {}, "offline"), x9: rep(11, {}) }, devices, 20);
    expect(out).toEqual([{ at: 20, who: "Hall light", what: "disconnected", tone: "muted" }]);
  });
});
