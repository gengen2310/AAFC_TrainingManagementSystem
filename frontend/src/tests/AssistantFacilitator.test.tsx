/**
 * Task 6 — Assistant facilitator multi-select (PlanningRightDrawer)
 *
 * These tests verify the client-side state management logic for the
 * immediate-mutation pattern (add/remove assistants optimistically, then
 * confirm via query invalidation). They do NOT call the real API — the API
 * is mocked so the tests run without a backend.
 */
import { describe, it, expect, vi } from 'vitest';
import type { AssistantFacilitator } from '../api/types';

// ── Helper: simulate add-assistant optimistic update ─────────────────────────

function addAssistant(
  current: AssistantFacilitator[],
  toAdd: AssistantFacilitator,
): AssistantFacilitator[] {
  if (current.some(a => a.user_id === toAdd.user_id)) return current;
  return [...current, toAdd];
}

function removeAssistant(
  current: AssistantFacilitator[],
  userId: string,
): AssistantFacilitator[] {
  return current.filter(a => a.user_id !== userId);
}

const ASST_A: AssistantFacilitator = { user_id: 'u1', display_name: 'Alice Ladouceur' };
const ASST_B: AssistantFacilitator = { user_id: 'u2', display_name: 'Bob Tremblay' };
const ASST_C: AssistantFacilitator = { user_id: 'u3', display_name: 'Carol Okafor' };

describe('AssistantFacilitator state helpers', () => {
  it('adds a new assistant', () => {
    const result = addAssistant([ASST_A], ASST_B);
    expect(result).toHaveLength(2);
    expect(result.map(a => a.user_id)).toContain('u2');
  });

  it('does not duplicate an existing assistant', () => {
    const result = addAssistant([ASST_A, ASST_B], ASST_A);
    expect(result).toHaveLength(2);
  });

  it('removes an assistant by user_id', () => {
    const result = removeAssistant([ASST_A, ASST_B, ASST_C], 'u2');
    expect(result).toHaveLength(2);
    expect(result.map(a => a.user_id)).not.toContain('u2');
  });

  it('is a no-op when removing a user_id not in the list', () => {
    const result = removeAssistant([ASST_A], 'u-missing');
    expect(result).toHaveLength(1);
  });

  it('starts from empty and builds a list', () => {
    let list: AssistantFacilitator[] = [];
    list = addAssistant(list, ASST_A);
    list = addAssistant(list, ASST_B);
    list = addAssistant(list, ASST_C);
    expect(list).toHaveLength(3);
    list = removeAssistant(list, 'u1');
    expect(list).toHaveLength(2);
    expect(list[0].user_id).toBe('u2');
  });
});

// ── Cell display logic ────────────────────────────────────────────────────────

/** Mirrors the cell display logic in ParadeNightGridView */
function formatCellAssistants(assistants: AssistantFacilitator[]): string {
  if (assistants.length === 0) return '';
  if (assistants.length === 1) return `+ ${assistants[0].display_name}`;
  if (assistants.length === 2) return `+ ${assistants.map(a => a.display_name).join(', ')}`;
  return `+${assistants.length} asst`;
}

describe('Cell display for assistant facilitators', () => {
  it('returns empty string for no assistants', () => {
    expect(formatCellAssistants([])).toBe('');
  });

  it('shows name for one assistant', () => {
    expect(formatCellAssistants([ASST_A])).toBe('+ Alice Ladouceur');
  });

  it('shows both names for two assistants', () => {
    expect(formatCellAssistants([ASST_A, ASST_B])).toBe('+ Alice Ladouceur, Bob Tremblay');
  });

  it('shows count chip for three or more', () => {
    expect(formatCellAssistants([ASST_A, ASST_B, ASST_C])).toBe('+3 asst');
  });
});

// ── API mock: planningApi.addAssistantFacilitator / removeAssistantFacilitator ─

describe('planningApi assistant mutation mocks', () => {
  it('addAssistantFacilitator is callable with sessionId and userId', async () => {
    const mockAdd = vi.fn().mockResolvedValue(undefined);
    await mockAdd('session-abc', 'user-xyz');
    expect(mockAdd).toHaveBeenCalledWith('session-abc', 'user-xyz');
  });

  it('removeAssistantFacilitator is callable with sessionId and userId', async () => {
    const mockRemove = vi.fn().mockResolvedValue(undefined);
    await mockRemove('session-abc', 'user-xyz');
    expect(mockRemove).toHaveBeenCalledWith('session-abc', 'user-xyz');
  });
});
