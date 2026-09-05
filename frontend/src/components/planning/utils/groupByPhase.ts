import type { TrainingClassWithPhase } from '../../../api/types';

export interface PhaseGroup {
  phase_id: string;
  phase_name: string;
  training_classes: TrainingClassWithPhase[];
}

/** Group training classes by curriculum phase (training_stage_id → phase_name).
 *  Preserves phase ordering from the input array (backend returns in display_order).
 *  Archived classes are included when present; callers render them distinctly. */
export function groupByPhase(classes: TrainingClassWithPhase[]): PhaseGroup[] {
  const phaseMap = new Map<string, PhaseGroup>();
  for (const tc of classes) {
    if (!phaseMap.has(tc.training_stage_id)) {
      phaseMap.set(tc.training_stage_id, {
        phase_id: tc.training_stage_id,
        phase_name: tc.phase_name,
        training_classes: [],
      });
    }
    phaseMap.get(tc.training_stage_id)!.training_classes.push(tc);
  }
  return Array.from(phaseMap.values());
}
