import { describe, it, expect } from 'vitest';
import { groupByPhase } from '../components/planning/utils/groupByPhase';

const classes = [
  { training_class_id: 'c1', display_name: 'Orientees', training_stage_id: 'p1', phase_name: 'Orientation', active_status: true },
  { training_class_id: 'c2', display_name: 'Initial', training_stage_id: 'p1', phase_name: 'Orientation', active_status: true },
  { training_class_id: 'c3', display_name: 'Junior', training_stage_id: 'p2', phase_name: 'Junior', active_status: true },
];

describe('groupByPhase', () => {
  it('groups classes by training_stage_id', () => {
    const groups = groupByPhase([...classes]);
    expect(groups).toHaveLength(2);
    expect(groups[0].phase_id).toBe('p1');
    expect(groups[0].training_classes).toHaveLength(2);
    expect(groups[1].phase_id).toBe('p2');
    expect(groups[1].training_classes).toHaveLength(1);
  });

  it('preserves input order for phases', () => {
    const groups = groupByPhase([...classes]);
    expect(groups[0].phase_name).toBe('Orientation');
    expect(groups[1].phase_name).toBe('Junior');
  });

  it('includes archived classes', () => {
    const withArchived = [
      ...classes,
      { training_class_id: 'c4', display_name: 'Archived Juniors', training_stage_id: 'p2', phase_name: 'Junior', active_status: false },
    ];
    const groups = groupByPhase(withArchived);
    const junior = groups.find(g => g.phase_id === 'p2')!;
    expect(junior.training_classes).toHaveLength(2);
  });

  it('returns empty array for empty input', () => {
    expect(groupByPhase([])).toEqual([]);
  });

  it('handles a single class', () => {
    const groups = groupByPhase([classes[0]]);
    expect(groups).toHaveLength(1);
    expect(groups[0].training_classes).toHaveLength(1);
  });
});
