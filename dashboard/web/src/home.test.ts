import { describe, expect, it } from "vitest";
import { homeLink } from "./home";

const h = (values: object, extra = {}) => ({ configured: true, running: true, now: 1000, values, ...extra }) as any;
describe("virtual smart home status comes only from the device's own messages", () => {
  it("is absent, hub down or waiting without device evidence", () => {
    expect(homeLink(null)).toBe("absent");
    expect(homeLink({ configured: false })).toBe("absent");
    expect(homeLink(h({}, { running: false }))).toBe("broker_down");
    expect(homeLink(h({ temperature: { value: 20, ts: 999 } }))).toBe("waiting"); // no status message yet
  });
  it("is online only with a fresh reading, and honours the last will", () => {
    expect(homeLink(h({ status: { value: "online", ts: 990 } }))).toBe("online");
    expect(homeLink(h({ status: { value: "online", ts: 900 } }))).toBe("stale");
    expect(homeLink(h({ status: { value: "online", ts: 900 }, temperature: { value: 20, ts: 995 } }))).toBe("online");
    expect(homeLink(h({ status: { value: "offline", ts: 999 } }))).toBe("offline");
  });
});
