import { describe, it, expect } from "vitest";
import { pwYearView } from "../routes/PlanningWorkspace";

describe("pwYearView", () => {
  it("offers setup for a future year that has no container", () => {
    expect(pwYearView(true, { year: 2028, materialised: false, state: "future" }, null))
      .toBe("setup");
  });

  it("offers setup for the current year before anything is written to it", () => {
    expect(pwYearView(true, { year: 2026, materialised: false, state: "current" }, null))
      .toBe("setup");
  });

  it("does NOT offer setup for an empty past year", () => {
    // Past years are read-only. Offering to set one up would contradict the
    // 403 the backend returns for the same write.
    expect(pwYearView(true, { year: 2019, materialised: false, state: "past" }, null))
      .toBe("past-empty");
  });

  it("shows the workspace once the year has a container", () => {
    expect(pwYearView(true, { year: 2026, materialised: true, state: "current" }, "id-2026"))
      .toBe("workspace");
  });

  it("waits while the year list is still loading", () => {
    expect(pwYearView(false, null, null)).toBe("loading");
  });

  it("reaches setup even though the year list is never empty", () => {
    // The regression this guards: PW lists logical years, so selectable_years
    // always returns current + 2 and `years.length === 0` stopped being
    // reachable -- which silently made SetupPanel unreachable too.
    const listedButUnconfigured = { year: 2026, materialised: false, state: "current" };
    expect(pwYearView(true, listedButUnconfigured, null)).toBe("setup");
  });
});
