import { describe, expect, it } from "vitest";
import { alertHistoryRequest } from "./alerts";

describe("clearing alert history requires consent and covers every session", () => {
  it("prepares no request until the user confirms (Cancel or unchecked deletes nothing)", () => {
    expect(alertHistoryRequest(false)).toBeNull();
  });
  it("asks the service for all history, not one session", () => {
    expect(alertHistoryRequest(true)).toEqual({ scope: "all", run_id: null, confirmation: "CLEAR ALERT HISTORY" });
  });
});
