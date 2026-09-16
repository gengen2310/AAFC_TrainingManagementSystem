import { describe, it, expect } from 'vitest';
import sourceText from '../components/planning/ParadeNightBlock.tsx?raw';

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

  it('renders planned cells as exactly curriculum, facilitator, and room rows', () => {
    const marker = 'The operational scan order is deliberately fixed at';
    const start = sourceText.indexOf(marker);
    const end = sourceText.indexOf('</div>\n                      </td>', start);
    const cell = sourceText.slice(start, end);
    expect(cell.match(/className="pw-nc-title"/g)).toHaveLength(1);
    expect(cell.match(/className="pw-nc-detail"/g)).toHaveLength(2);
    expect(cell).toContain('No facilitator');
    expect(cell).toContain('No room');
    expect(cell).not.toContain('pw-nc-equip');
    expect(cell).not.toContain('pw-nc-classes');
  });
});
