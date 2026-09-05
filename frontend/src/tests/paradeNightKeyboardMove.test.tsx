import { describe, it, expect, vi } from "vitest";
import { useState, useCallback } from "react";
import { render, screen, fireEvent, within, act } from "@testing-library/react";
import {
  ParadeNightBlock,
  type DisplaySession,
  type DragSessionPayload,
} from "../components/planning/ParadeNightBlock";

// A11Y-G6. Moving a session was previously reachable only by mouse drag: the cell was
// draggable and onMoveSession had a single call site behind onDrop. Enter merely opened
// the session detail. These tests pin the keyboard equivalent so it cannot regress to
// pointer-only again.

// Plan B Task 4 migrated ParadeNightBlock from cadet_group strings to TrainingClass
// objects. Tests that render sessions must now supply trainingClasses and sessions
// with matching training_classes membership.
const TC_JUNIOR = { training_class_id: "tc-j1", display_name: "Junior", class_number: 1,
  squadron_id: "s1", training_year_id: "y1", training_stage_id: "st1",
  start_date: null, end_date: null, expected_count: null, notes: null,
  is_archived: false, version: 1 };

const session = (id: string, _group: string, period: number, title: string): DisplaySession => ({
  session_id: id,
  period,
  cadet_group: _group,
  title,
  code: "SVC-101",
  location: "Hut 3",
  facilitator: "FSGT Rowe",
  conflict: null,
  training_classes: [{ training_class_id: TC_JUNIOR.training_class_id, display_name: TC_JUNIOR.display_name }],
  source: {
    curriculum_id: "c1",
    facilitator_id: "f1",
    location_id: "l1",
    activity_title: title,
    status: "planned",
  } as unknown as DisplaySession["source"],
});

/** Two nights sharing one move state, mirroring how EightWeekView wires this up. */
function Harness({ onMove }: { onMove: (p: DragSessionPayload, d: string, per: number, cg: string) => Promise<void> }) {
  const [moveSource, setMoveSource] = useState<DragSessionPayload | null>(null);
  const onPickUpSession = useCallback((p: DragSessionPayload) => setMoveSource(p), []);
  const onCancelMove = useCallback(() => setMoveSource(null), []);
  const shared = {
    moveSource, onPickUpSession, onCancelMove,
    onMoveSession: async (p: DragSessionPayload, d: string, per: number, cg: string) => {
      await onMove(p, d, per, cg); setMoveSource(null);
    },
    onHeaderClick: () => {},
    onSessionClick: () => {},
  };
  return (
    <div>
      <div data-testid="night-a">
        <ParadeNightBlock {...shared} dateId="night-A" date="2026-09-04"
          trainingClasses={[TC_JUNIOR]}
          sessions={[session("s1", "junior", 1, "Drill Fundamentals")]} />
      </div>
      <div data-testid="night-b">
        <ParadeNightBlock {...shared} dateId="night-B" date="2026-09-11"
          trainingClasses={[TC_JUNIOR]} sessions={[]} />
      </div>
    </div>
  );
}

const sessionCell = () => screen.getByLabelText(/Drill Fundamentals.*M to pick it up/i);

describe("ParadeNightBlock — keyboard move (G6 gesture alternative)", () => {
  it("advertises the shortcut on the session cell", () => {
    render(<Harness onMove={vi.fn()} />);
    expect(sessionCell()).toHaveAttribute("aria-keyshortcuts", "M");
  });

  it("M picks the session up and every empty slot becomes a labelled target", () => {
    render(<Harness onMove={vi.fn()} />);
    fireEvent.keyDown(sessionCell(), { key: "m" });
    expect(screen.getByLabelText(/picked up to move/i)).toBeInTheDocument();
    expect(screen.getAllByLabelText(/Press Enter to move Drill Fundamentals here/i).length).toBeGreaterThan(0);
  });

  it("Enter on an empty slot performs the move with the right target", async () => {
    const onMove = vi.fn().mockResolvedValue(undefined);
    render(<Harness onMove={onMove} />);
    fireEvent.keyDown(sessionCell(), { key: "m" });
    const targets = screen.getAllByLabelText(/Press Enter to move Drill Fundamentals here/i);
    await act(async () => { fireEvent.keyDown(targets[0], { key: "Enter" }); });
    expect(onMove).toHaveBeenCalledTimes(1);
    const [payload, dateId, period] = onMove.mock.calls[0];
    expect(payload.session_id).toBe("s1");
    expect(typeof dateId).toBe("string");
    expect(typeof period).toBe("number");
  });

  it("reaches a different parade night — parity with cross-block drag", async () => {
    const onMove = vi.fn().mockResolvedValue(undefined);
    render(<Harness onMove={onMove} />);
    fireEvent.keyDown(sessionCell(), { key: "m" });
    const nightB = within(screen.getByTestId("night-b"));
    const target = nightB.getAllByLabelText(/Press Enter to move Drill Fundamentals here/i)[0];
    await act(async () => { fireEvent.keyDown(target, { key: "Enter" }); });
    expect(onMove).toHaveBeenCalledTimes(1);
    expect(onMove.mock.calls[0][1]).toBe("night-B");
  });

  it("Escape cancels and leaves the session where it was", () => {
    const onMove = vi.fn();
    render(<Harness onMove={onMove} />);
    fireEvent.keyDown(sessionCell(), { key: "m" });
    fireEvent.keyDown(screen.getByLabelText(/picked up to move/i), { key: "Escape" });
    expect(screen.queryByLabelText(/picked up to move/i)).not.toBeInTheDocument();
    expect(onMove).not.toHaveBeenCalled();
  });

  it("M on the picked-up cell puts it back down", () => {
    render(<Harness onMove={vi.fn()} />);
    fireEvent.keyDown(sessionCell(), { key: "m" });
    fireEvent.keyDown(screen.getByLabelText(/picked up to move/i), { key: "M" });
    expect(screen.queryByLabelText(/picked up to move/i)).not.toBeInTheDocument();
  });

  it("with nothing picked up, Enter on an empty slot still means 'add', not 'move'", () => {
    const onMove = vi.fn();
    render(<Harness onMove={onMove} />);
    const empties = screen.getAllByLabelText(/No lesson|Press Enter to add a session/i);
    if (empties.length) fireEvent.keyDown(empties[0], { key: "Enter" });
    expect(onMove).not.toHaveBeenCalled();
  });
});
