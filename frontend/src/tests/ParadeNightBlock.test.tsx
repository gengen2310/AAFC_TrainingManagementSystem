import { describe, it, expect } from 'vitest';

describe('BLOCK_PERIODS removal (Task 3)', () => {
  it('ParadeNightBlock does not export BLOCK_PERIODS', async () => {
    const mod = await import('../components/planning/ParadeNightBlock');
    expect((mod as Record<string, unknown>)['BLOCK_PERIODS']).toBeUndefined();
  });

  it('ParadeNightBlock does not export BLOCK_GROUPS', async () => {
    const mod = await import('../components/planning/ParadeNightBlock');
    expect((mod as Record<string, unknown>)['BLOCK_GROUPS']).toBeUndefined();
  });

  it('ParadeNightBlock still exports fromNightSummary', async () => {
    const mod = await import('../components/planning/ParadeNightBlock');
    expect(typeof (mod as Record<string, unknown>)['fromNightSummary']).toBe('function');
  });

  it('ParadeNightBlock still exports ParadeNightBlock component', async () => {
    const mod = await import('../components/planning/ParadeNightBlock');
    expect(typeof (mod as Record<string, unknown>)['ParadeNightBlock']).toBe('function');
  });
});
