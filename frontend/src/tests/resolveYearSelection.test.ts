import { describe, it, expect } from "vitest";
import { resolveYearSelection } from "../routes/PlanningWorkspace";

/** The TMS → PW handoff carries a year NUMBER. A year with no row is still a
 *  real year, so the id may legitimately be null. */
const YEARS = [
  { year: 2025, planning_year_id: "id-2025", active_status: true },
  { year: 2026, planning_year_id: "id-2026", active_status: true },
  { year: 2027, planning_year_id: null, active_status: true },
  { year: 2028, planning_year_id: null, active_status: true },
];

describe("resolveYearSelection", () => {
  it("honours a handover to a year that has a row", () => {
    expect(resolveYearSelection(YEARS, 2026, null)).toEqual({ year: 2026, id: "id-2026" });
  });

  it("honours a handover to a year with NO row", () => {
    // The regression this function exists for: an unmatched year used to fall
    // through to the default, so TMS showed 2027 while PW quietly showed 2026.
    expect(resolveYearSelection(YEARS, 2027, null)).toEqual({ year: 2027, id: null });
  });

  it("lets the handover override a different stored year", () => {
    expect(resolveYearSelection(YEARS, 2028, 2025)).toEqual({ year: 2028, id: null });
  });

  it("keeps the stored year while it is still offered", () => {
    expect(resolveYearSelection(YEARS, null, 2025)).toEqual({ year: 2025, id: "id-2025" });
  });

  it("re-resolves the id when a stored year has since been materialised", () => {
    const after = YEARS.map(y => y.year === 2027 ? { ...y, planning_year_id: "id-2027" } : y);
    expect(resolveYearSelection(after, null, 2027)).toEqual({ year: 2027, id: "id-2027" });
  });

  it("drops a stored year that is no longer offered and falls back to the default", () => {
    const r = resolveYearSelection(YEARS, null, 1999);
    expect(r).not.toBeNull();
    expect(r!.year).not.toBe(1999);
  });

  it("keeps the stored year when the API returned nothing", () => {
    // An empty list must not yank the user off the year they were on.
    expect(resolveYearSelection([], null, 2027)).toEqual({ year: 2027, id: null });
  });

  it("returns null when there is nothing to select at all", () => {
    expect(resolveYearSelection([], null, null)).toBeNull();
  });

  it("ignores a non-finite requested year rather than selecting NaN", () => {
    const r = resolveYearSelection(YEARS, Number.NaN, 2025);
    expect(r).toEqual({ year: 2025, id: "id-2025" });
  });
});
