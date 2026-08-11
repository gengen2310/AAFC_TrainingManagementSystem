import { describe, it, expect } from "vitest";
import { conflictMapFromPlanningConflicts } from "../components/planning/ParadeNightBlock";
import type { PlanningConflict } from "../api/types";

// REM-39 residual: EightWeekView/TwoWeekView/the custom-range view previously
// built their per-cell conflict dot from a client-side heuristic instead of
// this canonical backend data, so an already-resolved conflict could still
// show a dot. These tests exercise the exact discrepancy the residual note
// described, directly against the conversion function the fix introduced.

function conflict(overrides: Partial<PlanningConflict> = {}): PlanningConflict {
  return {
    conflict_id: "c1", planning_year_id: "y1", parade_date_id: "d1",
    scheduled_session_id: "s1", conflict_type: "room_double_booked", severity: "warning",
    message: "Room double-booked", is_resolved: false, override_reason: null,
    created_at: null,
    ...overrides,
  };
}

describe("conflictMapFromPlanningConflicts", () => {
  it("maps an unresolved room conflict to room:true for its session", () => {
    const map = conflictMapFromPlanningConflicts([conflict({ conflict_type: "room_double_booked" })]);
    expect(map.get("s1")).toEqual({ room: true, fac: false, load: false });
  });

  it("maps an unresolved facilitator conflict to fac:true for its session", () => {
    const map = conflictMapFromPlanningConflicts([conflict({ conflict_type: "facilitator_double_booked" })]);
    expect(map.get("s1")).toEqual({ room: false, fac: true, load: false });
  });

  it("does NOT produce a dot for an already-resolved conflict -- the exact bug this fix closes", () => {
    const map = conflictMapFromPlanningConflicts([conflict({ is_resolved: true })]);
    expect(map.has("s1")).toBe(false);
  });

  it("ignores non-session-specific conflict types (e.g. holiday_conflict), matching sessionConflictCategory", () => {
    const map = conflictMapFromPlanningConflicts([conflict({ conflict_type: "holiday_conflict" })]);
    expect(map.has("s1")).toBe(false);
  });

  it("ignores conflicts with no scheduled_session_id (night-level, not cell-level)", () => {
    const map = conflictMapFromPlanningConflicts([conflict({ scheduled_session_id: null })]);
    expect(map.size).toBe(0);
  });

  it("merges room and facilitator conflicts for the same session into one entry", () => {
    const map = conflictMapFromPlanningConflicts([
      conflict({ conflict_type: "room_double_booked" }),
      conflict({ conflict_type: "facilitator_double_booked" }),
    ]);
    expect(map.get("s1")).toEqual({ room: true, fac: true, load: false });
  });
});
