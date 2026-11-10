import { describe, expect, it } from "vitest";
import { empty, networkActivity, ResourceEvent, State } from "./store";

const res = (ts: number, rate: number, extra: Partial<ResourceEvent> = {}) => ({ event_type: "resource", ts, mqtt_msgs_per_s: rate, ...extra }) as unknown as ResourceEvent;
const with_ = (...r: ResourceEvent[]): State => ({ ...empty, resources: r });
const NOW = 1000;

describe("network activity is one measured reading, never a guess", () => {
  it("a fresh nonzero sample is Receiving with the measured rate", () => {
    expect(networkActivity(with_(res(NOW - 1, 12.5)), { ids_enabled: true }, true, NOW)).toEqual({ status: "Receiving", rate: 12.5, ts: NOW - 1 });
  });
  it("a fresh zero is a valid 0.0 reading, not missing data", () => {
    expect(networkActivity(with_(res(NOW - 1, 0)), null, true, NOW)).toMatchObject({ status: "No recent traffic", rate: 0 });
  });
  it("regression: a stale last sample (dead IDS monitor) is Data unavailable, not zero", () => {
    expect(networkActivity(with_(res(NOW - 23_000, 4)), { ids_enabled: true }, true, NOW)).toMatchObject({ status: "Data unavailable", rate: null });
    expect(networkActivity(empty, null, true, NOW)).toMatchObject({ status: "Data unavailable", rate: null });
  });
  it("paused monitoring and a lost backend connection are their own states", () => {
    expect(networkActivity(with_(res(NOW - 1, 3)), { ids_enabled: false }, true, NOW)).toMatchObject({ status: "Monitoring paused", rate: null });
    expect(networkActivity(with_(res(NOW - 1, 3, { ids_enabled: false } as Partial<ResourceEvent>)), null, true, NOW)).toMatchObject({ status: "Monitoring paused" });
    expect(networkActivity(with_(res(NOW - 1, 3)), { ids_enabled: true }, false, NOW)).toMatchObject({ status: "Disconnected", rate: null });
  });
  it("uses the newest sample even when events arrive out of order", () => {
    expect(networkActivity(with_(res(NOW - 1, 7), res(NOW - 30, 0)), null, true, NOW)).toMatchObject({ status: "Receiving", rate: 7 });
  });
});

describe("rolling window", () => {
  it("averages the genuine 1 Hz samples over 10 s, so periodic device publishes are not shown as idle", () => {
    const r = [0, 0, 4, 0, 0, 0, 0, 12, 0, 0].map((v, i) => res(NOW - 10 + i + 1, v));
    expect(networkActivity(with_(...r), null, true, NOW)).toMatchObject({ status: "Receiving", rate: 1.6 });
  });
  it("ignores samples older than the window and is idle only when every recent sample is zero", () => {
    expect(networkActivity(with_(res(NOW - 30, 50), res(NOW - 1, 0)), null, true, NOW)).toMatchObject({ status: "No recent traffic", rate: 0 });
  });
});
