# Parade Night Planning Redesign — Plan B: React Planning Workspace

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all hard-coded period constants with API-driven data, redesign the planning grid with a TimingStrip, phase grouping, full cell behaviour (curriculum/facilitator/assistants/room), a TemplateImpactModal, a simplified Create Parade Night form, and apply frontend-design + apple-design to the result.

**Architecture:** The API changes from Plan A expose `instructional_periods` and `timing_strip` arrays in the night-summaries response. Plan B consumes those arrays to drive column headers, cell count, and the new TimingStrip. Phase grouping switches from the hard-coded `DISPLAY_GROUPS` constant to a derivation from training class → `curriculum_phase` name. All hard-coded period/group constants are deleted.

**Tech Stack:** React 18, TypeScript, Vite, @tanstack/react-query, existing `planningApi` client in `frontend/src/api/`.

**Spec:** `docs/superpowers/specs/2026-09-05-parade-night-planning-redesign.md`

**Depends on:** Plan A must be fully deployed (or the dev backend must have the new migrations applied) before frontend tests that hit the API can pass. The TypeScript types and component structure do not depend on Plan A — those can be written first.

## Global Constraints

- Never reintroduce `cadet_group` as a primary model — phase grouping comes from `training_stage_id` → `curriculum_phases.name`.
- Never rename or remove `session_number` — it is the existing column key in PlanningSession; period_number is the backend field name.
- BLOCK_PERIODS and BLOCK_GROUPS must be completely deleted, not kept as unused constants.
- The grid must be responsive from 1440px down to 375px. No horizontal scroll on the page body — the grid itself scrolls horizontally on narrow viewports.
- All interactive controls must have visible focus states (outline, not removed by CSS).
- `DISPLAY_GROUPS` in ParadeNightGridView.tsx must be replaced — do not keep it as a fallback.
- No operational data in localStorage (auth constraint preserved).
- Security greps must return 0 after every commit.

---

### Task 1: Add TypeScript types for new API shapes

**Files:**
- Modify: `frontend/src/api/types.ts`

**Interfaces:**
- Produces:
  - `InstructionalPeriod` — `{period_number: number; label: string; start_time: string | null; end_time: string | null}`
  - `TimingStripEntry` — `{label: string; start_time: string | null; end_time: string | null; is_instructional: boolean; display_order: number}`
  - `AssistantFacilitator` — `{user_id: string; display_name: string}`
  - `TemplateImpactResult` — `{retained_periods: number[]; removed_periods: number[]; added_periods: number[]; affected_sessions: TemplateImpactSession[]}`
  - `TemplateImpactSession` — `{session_id: string; period_number: number; has_curriculum: boolean; has_facilitator: boolean}`
  - `NightSummary` — extend existing `ParadeNight` with `instructional_periods: InstructionalPeriod[]; timing_strip: TimingStripEntry[]`
  - Extend `PlanningSession` (or `SessionRow`) with `assistant_facilitators: AssistantFacilitator[]`

- [ ] **Step 1: Add the new interfaces to `types.ts`**

Open `frontend/src/api/types.ts`. After the existing exports, add:

```typescript
/** One schedulable instructional period from a timing template snapshot. */
export interface InstructionalPeriod {
  period_number: number;
  label: string;
  start_time: string | null;
  end_time: string | null;
}

/** One block in the timing strip (instructional + non-instructional). */
export interface TimingStripEntry {
  label: string;
  start_time: string | null;
  end_time: string | null;
  is_instructional: boolean;
  display_order: number;
}

/** One assistant facilitator on a session. */
export interface AssistantFacilitator {
  user_id: string;
  display_name: string;
}

export interface TemplateImpactSession {
  session_id: string;
  period_number: number;
  has_curriculum: boolean;
  has_facilitator: boolean;
}

export interface TemplateImpactResult {
  retained_periods: number[];
  removed_periods: number[];
  added_periods: number[];
  affected_sessions: TemplateImpactSession[];
}
```

Also find the existing `ParadeNight` interface and extend it:

```typescript
// In the existing ParadeNight interface, add:
  instructional_periods: InstructionalPeriod[];     // [] for legacy nights without snapshot
  timing_strip: TimingStripEntry[];                  // [] for legacy nights
```

Find `PlanningSession` (in types.ts or wherever it is defined) and add:

```typescript
  assistant_facilitators: AssistantFacilitator[];   // [] when none assigned
  assistant_facilitator_id?: string | null;          // keep for legacy compat
```

- [ ] **Step 2: Run TypeScript check to verify no errors**

```bash
cd frontend && npm run type-check
```
Expected: 0 errors. If `type-check` is not defined, run:
```bash
npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
cd frontend && git add src/api/types.ts
git commit -m "feat(types): add InstructionalPeriod, TimingStripEntry, AssistantFacilitator, TemplateImpactResult"
```

---

### Task 2: Add API client functions for new endpoints

**Files:**
- Modify: `frontend/src/api/index.ts` (add 3 new functions to `planningApi`)

**Interfaces:**
- Consumes: Types from Task 1.
- Produces:
  - `planningApi.getTemplateImpact(nightId, newTemplateId): Promise<TemplateImpactResult>`
  - `planningApi.applyTemplate(nightId, templateId, confirmed): Promise<{id: string; session_count: number}>`
  - `planningApi.addAssistantFacilitator(sessionId, userId): Promise<void>`
  - `planningApi.removeAssistantFacilitator(sessionId, userId): Promise<void>`

- [ ] **Step 1: Open `frontend/src/api/index.ts`**

Find the `planningApi` object (or export). Add the following methods:

```typescript
async getTemplateImpact(nightId: string, newTemplateId: string): Promise<TemplateImpactResult> {
  const resp = await fetch(
    `${apiBase()}/api/training/parade-nights/${nightId}/template-impact?new_template_id=${encodeURIComponent(newTemplateId)}`,
    { headers: authHeaders() }
  );
  if (!resp.ok) throw new Error(await resp.text());
  return resp.json();
},

async applyTemplate(nightId: string, templateId: string, confirmed: boolean): Promise<{ id: string; session_count: number }> {
  const resp = await fetch(
    `${apiBase()}/api/training/parade-nights/${nightId}/template`,
    {
      method: 'PATCH',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ timing_template_id: templateId, confirmed }),
    }
  );
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    if (resp.status === 409) throw Object.assign(new Error('confirmation_required'), { detail: err.detail });
    throw new Error(JSON.stringify(err));
  }
  return resp.json();
},

async addAssistantFacilitator(sessionId: string, userId: string): Promise<void> {
  const resp = await fetch(
    `${apiBase()}/api/training/sessions/${sessionId}/assistants`,
    {
      method: 'POST',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId }),
    }
  );
  if (!resp.ok) throw new Error(await resp.text());
},

async removeAssistantFacilitator(sessionId: string, userId: string): Promise<void> {
  const resp = await fetch(
    `${apiBase()}/api/training/sessions/${sessionId}/assistants/${encodeURIComponent(userId)}`,
    { method: 'DELETE', headers: authHeaders() }
  );
  if (!resp.ok) throw new Error(await resp.text());
},
```

Note: If the existing `planningApi` uses a different pattern (e.g., a class, an axios instance, or a different auth helper name), match that pattern exactly. Do not introduce a new fetch pattern if the existing code uses something else.

- [ ] **Step 2: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```
Expected: 0 errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/index.ts
git commit -m "feat(api-client): add getTemplateImpact, applyTemplate, addAssistantFacilitator, removeAssistantFacilitator"
```

---

### Task 3: Delete BLOCK_PERIODS and BLOCK_GROUPS; derive column count from API

**Files:**
- Modify: `frontend/src/components/planning/ParadeNightBlock.tsx`
- Modify: `frontend/src/components/planning/views/ListView.tsx`
- Modify: `frontend/src/components/planning/views/ParadeNightGridView.tsx`

**Interfaces:**
- Consumes: `InstructionalPeriod[]` from `ParadeNight.instructional_periods` (Task 1).
- Produces: No more `BLOCK_PERIODS` or `BLOCK_GROUPS` anywhere in the codebase. Column count is always derived from the night's `instructional_periods.length`. Falls back to `session_count` for legacy nights with empty `instructional_periods`.

- [ ] **Step 1: Write a failing TypeScript test**

In `frontend/src/__tests__/ParadeNightBlock.test.tsx` (create if absent):

```typescript
import { describe, it, expect } from 'vitest';

describe('BLOCK_PERIODS removal', () => {
  it('ParadeNightBlock does not export BLOCK_PERIODS', async () => {
    const mod = await import('../components/planning/ParadeNightBlock');
    expect((mod as Record<string, unknown>)['BLOCK_PERIODS']).toBeUndefined();
  });
  it('ParadeNightBlock does not export BLOCK_GROUPS', async () => {
    const mod = await import('../components/planning/ParadeNightBlock');
    expect((mod as Record<string, unknown>)['BLOCK_GROUPS']).toBeUndefined();
  });
});
```

Run:
```bash
cd frontend && npm run test -- --run src/__tests__/ParadeNightBlock.test.tsx
```
Expected: FAIL (both constants are currently exported).

- [ ] **Step 2: Remove BLOCK_PERIODS from `ParadeNightBlock.tsx`**

Open `frontend/src/components/planning/ParadeNightBlock.tsx`.

Find and delete line 17:
```typescript
export const BLOCK_PERIODS = [1, 2, 3] as const;
```

Find and delete the BLOCK_GROUPS constant (around line 10):
```typescript
const BLOCK_GROUPS = [ ... ] as const;  // or export const BLOCK_GROUPS = ...
```

For every use of `BLOCK_PERIODS` in this file (lines ~321, 389, 408, 513, 529, 545, 552), replace the reference with a derived value. The component receives a `periods: InstructionalPeriod[]` prop (added in this step). Replace:

```typescript
// OLD pattern:
{BLOCK_PERIODS.map(p => (
  <Column key={p} period={p} ... />
))}

// NEW pattern:
{periods.map(p => (
  <Column key={p.period_number} period={p.period_number} label={p.label} ... />
))}
```

Add the `periods` prop to the component's Props type:

```typescript
interface ParadeNightBlockProps {
  // ... existing props ...
  periods: InstructionalPeriod[];  // from night.instructional_periods
}
```

Remove the import/usage of `BLOCK_GROUPS`. For any place that used `BLOCK_GROUPS` for phase labels, see Task 4 (phase grouping) — for now, remove the static reference and leave a `// TODO: Task 4 — phase grouping` comment so the TypeScript checker catches it.

- [ ] **Step 3: Remove BLOCK_PERIODS from `ListView.tsx`**

Open `frontend/src/components/planning/views/ListView.tsx`.

Find all imports of `BLOCK_PERIODS` from `ParadeNightBlock`. Delete the import. Find all uses:
```typescript
// OLD
{BLOCK_PERIODS.map(periodNum => ( ... ))}

// NEW — derive from night.instructional_periods
{(night.instructional_periods ?? []).map(p => (
  // use p.period_number as the column key, p.label as the header
))}
```

For legacy nights where `instructional_periods` is empty, fall back:
```typescript
const periods = (night.instructional_periods?.length ?? 0) > 0
  ? night.instructional_periods
  : Array.from({ length: night.session_count }, (_, i) => ({
      period_number: i + 1,
      label: `Period ${i + 1}`,
      start_time: null,
      end_time: null,
    }));
```

- [ ] **Step 4: Remove DISPLAY_GROUPS from `ParadeNightGridView.tsx`**

Open `frontend/src/components/planning/views/ParadeNightGridView.tsx`.

Find (lines 9-14):
```typescript
const DISPLAY_GROUPS = [
  { label: "Orientation & Initial", groups: ["orientation", "initial"] },
  { label: "Junior & Bronze CLP", groups: ["junior"] },
  { label: "Intermediate & Silver CLP", groups: ["intermediate"] },
  { label: "Senior & Gold CLP", groups: ["senior"] },
] as const;
```

Delete this constant entirely. Replace usages with a `// TODO: Task 4 — phase grouping` comment for now (Task 4 will replace these with actual phase data from the API).

- [ ] **Step 5: Run TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

Fix all type errors introduced by removing the constants. Do not suppress errors with `// @ts-ignore` or `as any` — fix them.

- [ ] **Step 6: Run the test to verify BLOCK_PERIODS is gone**

```bash
npm run test -- --run src/__tests__/ParadeNightBlock.test.tsx
```
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/
git commit -m "refactor(planning): delete BLOCK_PERIODS, BLOCK_GROUPS, DISPLAY_GROUPS

Dynamic column count now derived from night.instructional_periods.
Legacy nights fall back to session_count. TODO comments mark phase
grouping (Task 4) and will not compile until resolved."
```

---

### Task 4: Phase grouping from curriculum phases

**Files:**
- Modify: `frontend/src/components/planning/views/ParadeNightGridView.tsx`
- Modify: `frontend/src/api/types.ts` (if `CurriculumPhase` type is missing)
- Modify: `frontend/src/api/index.ts` (if a phases fetch is needed)

**Interfaces:**
- Consumes: The existing `/api/planning/years/{year_id}/training-classes` (or equivalent) endpoint that returns `TrainingClass` records including `training_stage_id` and a `phase_name` / `curriculum_phase` field. If this endpoint does not include `phase_name`, read from the backend and find the correct field — do not guess.
- Produces: `CurriculumPhaseGroup[]` — an array of `{phase_id: string; phase_name: string; training_classes: TrainingClass[]}` grouped from active training classes. This replaces DISPLAY_GROUPS as the row grouping in the planning grid. Historical/archived classes appear as read-only rows (greyed, no drop target) within their original phase group.

- [ ] **Step 1: Investigate the current training-class API**

Read `backend/app/routers/planning.py` near the `training-classes` endpoint and `backend/app/models/training.py`'s `TrainingClass` model. Find:
- The exact endpoint URL for fetching active training classes for a planning year or squadron.
- Whether the response includes `phase_name` (from the `curriculum_phases` join).
- The `training_stage_id` FK and what it joins to.

Record findings in the ledger before proceeding.

- [ ] **Step 2: Add or extend API client function**

If a training-class fetch doesn't exist in `planningApi`, add:

```typescript
async getTrainingClasses(squadronId: string, options?: { includeArchived?: boolean }): Promise<TrainingClassWithPhase[]> {
  const params = new URLSearchParams({ squadron_id: squadronId });
  if (options?.includeArchived) params.set('include_archived', 'true');
  const resp = await fetch(`${apiBase()}/api/training/classes?${params}`, { headers: authHeaders() });
  if (!resp.ok) throw new Error(await resp.text());
  return resp.json();
},
```

And the type:

```typescript
export interface TrainingClassWithPhase {
  training_class_id: string;
  display_name: string;
  training_stage_id: string;
  phase_name: string;           // joined from curriculum_phases
  active_status: boolean;
  cadet_count?: number | null;
}
```

- [ ] **Step 3: Write the `groupByPhase` helper**

Create `frontend/src/components/planning/utils/groupByPhase.ts`:

```typescript
import type { TrainingClassWithPhase } from '../../../api/types';

export interface PhaseGroup {
  phase_id: string;
  phase_name: string;
  training_classes: TrainingClassWithPhase[];
}

/** Group active (and optionally archived) training classes by curriculum phase.
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
```

- [ ] **Step 4: Write test for `groupByPhase`**

Create `frontend/src/__tests__/groupByPhase.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { groupByPhase } from '../components/planning/utils/groupByPhase';

const classes = [
  { training_class_id: 'c1', display_name: 'Orientees', training_stage_id: 'p1', phase_name: 'Orientation', active_status: true },
  { training_class_id: 'c2', display_name: 'Initial', training_stage_id: 'p1', phase_name: 'Orientation', active_status: true },
  { training_class_id: 'c3', display_name: 'Junior', training_stage_id: 'p2', phase_name: 'Junior', active_status: true },
] as const;

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
});
```

```bash
cd frontend && npm run test -- --run src/__tests__/groupByPhase.test.ts
```
Expected: PASS.

- [ ] **Step 5: Wire phase grouping into `ParadeNightGridView.tsx`**

Replace the deleted `DISPLAY_GROUPS` usage with a `useQuery` call for training classes and the `groupByPhase` helper:

```typescript
// In ParadeNightGridView, add query:
const { data: trainingClasses = [] } = useQuery({
  queryKey: ['training-classes', squadronId],
  queryFn: () => planningApi.getTrainingClasses(squadronId, { includeArchived: true }),
  staleTime: 5 * 60 * 1000,
});
const phaseGroups = useMemo(() => groupByPhase(trainingClasses), [trainingClasses]);

// Replace DISPLAY_GROUPS.map(...) with phaseGroups.map(group => ...)
// Each row in the grid: group.training_classes.map(tc => ...)
// Archived class rows: render with opacity: 0.5, cursor: 'default', no drop target
```

The grid rows are now: for each phase group → for each training class in the group → one row spanning all period columns.

- [ ] **Step 6: TypeScript check + test run**

```bash
cd frontend && npx tsc --noEmit
npm run test -- --run
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/
git commit -m "feat(planning): phase grouping from curriculum phases replaces DISPLAY_GROUPS

Training classes grouped by training_stage_id → phase_name via API.
Archived classes shown as read-only rows. groupByPhase utility tested."
```

---

### Task 5: TimingStrip component above the planning grid

**Files:**
- Create: `frontend/src/components/planning/TimingStrip.tsx`
- Modify: `frontend/src/components/planning/views/ParadeNightGridView.tsx` (add TimingStrip above grid)

**Interfaces:**
- Consumes: `timing_strip: TimingStripEntry[]` from `ParadeNight` (Task 1). `instructional_periods: InstructionalPeriod[]` for column alignment.
- Produces: `<TimingStrip blocks={timing_strip} periods={instructional_periods} />` — a horizontal row above the grid header. Each block is a colored pill showing label + time range. Instructional blocks align with their grid column. Non-instructional blocks (breaks, opening/closing parade) span proportionally between columns.

- [ ] **Step 1: Write a rendering test**

Create `frontend/src/__tests__/TimingStrip.test.tsx`:

```typescript
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { TimingStrip } from '../components/planning/TimingStrip';

const blocks = [
  { label: 'Opening Parade', start_time: '18:00', end_time: '18:20', is_instructional: false, display_order: 0 },
  { label: 'Period 1', start_time: '18:30', end_time: '19:10', is_instructional: true, display_order: 1 },
  { label: 'Break', start_time: '19:10', end_time: '19:20', is_instructional: false, display_order: 2 },
  { label: 'Period 2', start_time: '19:20', end_time: '20:00', is_instructional: true, display_order: 3 },
];

const periods = [
  { period_number: 1, label: 'Period 1', start_time: '18:30', end_time: '19:10' },
  { period_number: 2, label: 'Period 2', start_time: '19:20', end_time: '20:00' },
];

describe('TimingStrip', () => {
  it('renders all blocks', () => {
    render(<TimingStrip blocks={blocks} periods={periods} />);
    expect(screen.getByText('Opening Parade')).toBeTruthy();
    expect(screen.getByText('Period 1')).toBeTruthy();
    expect(screen.getByText('Break')).toBeTruthy();
    expect(screen.getByText('Period 2')).toBeTruthy();
  });

  it('applies data-instructional attribute for styling', () => {
    const { container } = render(<TimingStrip blocks={blocks} periods={periods} />);
    const pills = container.querySelectorAll('[data-instructional]');
    expect(pills.length).toBeGreaterThan(0);
  });

  it('renders gracefully with empty blocks', () => {
    const { container } = render(<TimingStrip blocks={[]} periods={[]} />);
    expect(container.firstChild).toBeTruthy();
  });
});
```

```bash
cd frontend && npm run test -- --run src/__tests__/TimingStrip.test.tsx
```
Expected: FAIL (component doesn't exist yet).

- [ ] **Step 2: Create `TimingStrip.tsx`**

```typescript
// frontend/src/components/planning/TimingStrip.tsx
import type { TimingStripEntry, InstructionalPeriod } from '../../api/types';
import styles from './TimingStrip.module.css';

interface Props {
  blocks: TimingStripEntry[];
  /** Instructional periods from the night snapshot, in period_number order. */
  periods: InstructionalPeriod[];
}

function formatTimeRange(start: string | null, end: string | null): string {
  if (!start && !end) return '';
  if (start && end) return `${start}–${end}`;
  return start ?? end ?? '';
}

export function TimingStrip({ blocks, periods }: Props) {
  if (blocks.length === 0 && periods.length === 0) {
    return <div className={styles.strip} aria-hidden="true" />;
  }

  // Fallback: if no strip data, synthesise from periods only
  const displayBlocks = blocks.length > 0
    ? blocks
    : periods.map((p, i): TimingStripEntry => ({
        label: p.label,
        start_time: p.start_time,
        end_time: p.end_time,
        is_instructional: true,
        display_order: i,
      }));

  return (
    <div
      className={styles.strip}
      role="list"
      aria-label="Parade night timing"
    >
      {displayBlocks.map((block, idx) => (
        <div
          key={idx}
          className={styles.block}
          data-instructional={block.is_instructional ? 'true' : 'false'}
          role="listitem"
          title={formatTimeRange(block.start_time, block.end_time) || block.label}
        >
          <span className={styles.blockLabel}>{block.label}</span>
          {(block.start_time || block.end_time) && (
            <span className={styles.blockTime}>
              {formatTimeRange(block.start_time, block.end_time)}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Create `TimingStrip.module.css`**

```css
/* frontend/src/components/planning/TimingStrip.module.css */
.strip {
  display: flex;
  align-items: stretch;
  gap: 2px;
  padding: 4px 0;
  min-height: 40px;
  overflow-x: auto;
}

.block {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  text-align: center;
  white-space: nowrap;
  min-width: 80px;
  background: var(--surface-2, #f0f5fa);
  border: 1px solid var(--border-light, #e4edf5);
  color: var(--muted, #5c6a76);
}

.block[data-instructional='true'] {
  background: var(--accent-light, #e0f0fa);
  border-color: var(--accent, #51b0e3);
  color: var(--text, #1e2d3d);
}

.blockLabel {
  display: block;
  font-weight: 600;
}

.blockTime {
  display: block;
  font-size: 10px;
  font-weight: 400;
  opacity: 0.75;
  margin-top: 1px;
}
```

- [ ] **Step 4: Wire TimingStrip into `ParadeNightGridView.tsx`**

In the grid, above the column-header row and below the parade night title/date, add:

```tsx
<TimingStrip
  blocks={night.timing_strip ?? []}
  periods={night.instructional_periods ?? []}
/>
```

Apply `frontend-design` and `apple-design` skills to the visual treatment of the TimingStrip at the end of Task 9 — for now the CSS module above is functional. Mark with a `// DESIGN: Task 9 will apply visual polish` comment.

- [ ] **Step 5: Run tests**

```bash
cd frontend && npm run test -- --run src/__tests__/TimingStrip.test.tsx
npx tsc --noEmit
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/planning/TimingStrip.tsx \
        frontend/src/components/planning/TimingStrip.module.css \
        frontend/src/components/planning/views/ParadeNightGridView.tsx \
        frontend/src/__tests__/TimingStrip.test.tsx
git commit -m "feat(planning): add TimingStrip component above planning grid

Shows all timing blocks (instructional + non-instructional) in a visual
strip above the column headers. Falls back to period labels for legacy
nights without snapshots. DESIGN polish deferred to Task 9."
```

---

### Task 6: Full cell behaviour — Curriculum, Facilitator, Assistants, Room

**Files:**
- Modify: `frontend/src/components/planning/views/ParadeNightGridView.tsx`
- Modify: `frontend/src/components/planning/PlanningRightDrawer.tsx` (assistant facilitator UI in drawer)

**Interfaces:**
- Consumes: `session.assistant_facilitators: AssistantFacilitator[]` (Task 1).
- Consumes: `planningApi.addAssistantFacilitator` / `removeAssistantFacilitator` (Task 2).
- Produces: Grid cells now display:
  1. Curriculum code + title (existing)
  2. Main facilitator name (existing)
  3. Assistant facilitator names (new) — compact list, tap to expand in drawer
  4. Room/training area label (existing, but now verified displayed)

- [ ] **Step 1: Verify existing cell rendering for curriculum + facilitator**

Open `ParadeNightGridView.tsx`. Find where session cells are rendered (look for `s.facilitator_id`, `s.curriculum_title_at_time`, etc.). These should already be displayed — verify. If they are missing from the cell, add them now.

- [ ] **Step 2: Add assistant facilitators to cell display**

In the cell renderer, after the main facilitator line:

```tsx
{session.assistant_facilitators.length > 0 && (
  <div className={styles.assistants} aria-label={`${session.assistant_facilitators.length} assistant(s)`}>
    {session.assistant_facilitators.slice(0, 2).map(a => (
      <span key={a.user_id} className={styles.assistantChip}>
        {a.display_name}
      </span>
    ))}
    {session.assistant_facilitators.length > 2 && (
      <span className={styles.assistantMore}>
        +{session.assistant_facilitators.length - 2}
      </span>
    )}
  </div>
)}
```

- [ ] **Step 3: Add assistant facilitator management in the right drawer**

In `PlanningRightDrawer.tsx`, find the session detail panel. Add an "Assistants" section after the main facilitator section:

```tsx
// Assistant facilitators section
<section className={styles.drawerSection} aria-labelledby="asst-fac-heading">
  <h4 id="asst-fac-heading">Assistant Facilitators</h4>
  {session.assistant_facilitators.map(a => (
    <div key={a.user_id} className={styles.asstRow}>
      <span>{a.display_name}</span>
      <button
        type="button"
        className={styles.removeBtn}
        aria-label={`Remove ${a.display_name} as assistant`}
        onClick={() => handleRemoveAssistant(a.user_id)}
      >
        ×
      </button>
    </div>
  ))}
  <FacilitatorPicker
    placeholder="Add assistant facilitator…"
    onSelect={(userId) => handleAddAssistant(userId)}
    excludeIds={[session.facilitator_id, ...session.assistant_facilitators.map(a => a.user_id)].filter(Boolean)}
  />
</section>
```

Implement `handleAddAssistant` and `handleRemoveAssistant` using the mutation helpers from Task 2, and invalidate the relevant query key after each mutation.

- [ ] **Step 4: Verify room/training area is displayed in the cell**

Find where `session.location_id` / `session.training_area_id` is rendered. If missing, add:
```tsx
{session.location_id && locationName && (
  <div className={styles.room} aria-label="Room">
    {locationName}
  </div>
)}
```

Use the existing location map (if the grid already fetches training areas, reuse that data — do not add a duplicate query).

- [ ] **Step 5: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/planning/views/ParadeNightGridView.tsx \
        frontend/src/components/planning/PlanningRightDrawer.tsx
git commit -m "feat(planning): full cell behaviour — curriculum, main fac, assistants, room

Grid cells now show all four data points. Assistant facilitators listed
with +N overflow chip. Drawer section allows add/remove assistant
facilitators via SessionAssistantFacilitator API."
```

---

### Task 7: TemplateImpactModal

**Files:**
- Create: `frontend/src/components/planning/TemplateImpactModal.tsx`
- Modify: `frontend/src/components/planning/views/ParadeNightGridView.tsx` (trigger modal on template change)

**Interfaces:**
- Consumes: `planningApi.getTemplateImpact` + `planningApi.applyTemplate` (Task 2).
- Produces: A modal that shows `retained_periods`, `removed_periods`, `added_periods`, and a list of affected sessions. Requires user confirmation before applying. On confirmation, calls `applyTemplate(nightId, templateId, true)` and invalidates queries.

- [ ] **Step 1: Write a rendering test**

```typescript
// frontend/src/__tests__/TemplateImpactModal.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { TemplateImpactModal } from '../components/planning/TemplateImpactModal';

const impact = {
  retained_periods: [1, 2],
  removed_periods: [3],
  added_periods: [4],
  affected_sessions: [
    { session_id: 's1', period_number: 3, has_curriculum: true, has_facilitator: false },
  ],
};

describe('TemplateImpactModal', () => {
  it('shows retained, removed, and added periods', () => {
    render(
      <TemplateImpactModal
        impact={impact}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
        loading={false}
      />
    );
    expect(screen.getByText(/removed/i)).toBeTruthy();
    expect(screen.getByText('3')).toBeTruthy();
  });

  it('calls onConfirm when user clicks confirm', () => {
    const onConfirm = vi.fn();
    render(
      <TemplateImpactModal
        impact={impact}
        onConfirm={onConfirm}
        onCancel={vi.fn()}
        loading={false}
      />
    );
    fireEvent.click(screen.getByRole('button', { name: /confirm/i }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it('calls onCancel when user clicks cancel', () => {
    const onCancel = vi.fn();
    render(
      <TemplateImpactModal
        impact={impact}
        onConfirm={vi.fn()}
        onCancel={onCancel}
        loading={false}
      />
    );
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });
});
```

```bash
cd frontend && npm run test -- --run src/__tests__/TemplateImpactModal.test.tsx
```
Expected: FAIL.

- [ ] **Step 2: Create `TemplateImpactModal.tsx`**

```typescript
// frontend/src/components/planning/TemplateImpactModal.tsx
import type { TemplateImpactResult } from '../../api/types';

interface Props {
  impact: TemplateImpactResult;
  onConfirm: () => void;
  onCancel: () => void;
  loading: boolean;
}

export function TemplateImpactModal({ impact, onConfirm, onCancel, loading }: Props) {
  const hasRemovals = impact.removed_periods.length > 0;
  const affectedWithData = impact.affected_sessions.filter(
    s => s.has_curriculum || s.has_facilitator
  );

  return (
    <div role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <div>
        <h2 id="modal-title">Template Change Impact</h2>
        <p>Changing the timing template will affect this parade night's structure.</p>

        <dl>
          <dt>Periods kept</dt>
          <dd>{impact.retained_periods.length > 0 ? impact.retained_periods.join(', ') : 'None'}</dd>

          {impact.added_periods.length > 0 && (
            <>
              <dt>New periods added</dt>
              <dd>{impact.added_periods.join(', ')}</dd>
            </>
          )}

          {hasRemovals && (
            <>
              <dt>Periods removed</dt>
              <dd>{impact.removed_periods.join(', ')}</dd>
            </>
          )}
        </dl>

        {affectedWithData.length > 0 && (
          <div role="alert" aria-live="polite">
            <p>
              <strong>{affectedWithData.length} session{affectedWithData.length > 1 ? 's' : ''}</strong> on removed
              period{impact.removed_periods.length > 1 ? 's' : ''} have planned content.
              They will remain in the system but will no longer have an assigned period.
            </p>
            <ul>
              {affectedWithData.map(s => (
                <li key={s.session_id}>
                  Period {s.period_number}
                  {s.has_curriculum ? ' — has curriculum' : ''}
                  {s.has_facilitator ? ' — has facilitator' : ''}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div>
          <button type="button" onClick={onCancel} disabled={loading}>
            Cancel
          </button>
          <button type="button" onClick={onConfirm} disabled={loading} aria-busy={loading}>
            {loading ? 'Applying…' : 'Confirm change'}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Wire into the grid or a template-change control**

Find where the timing template selector exists in the UI (or in SetupPanel.tsx, or ParadeNightSummaryCard.tsx). When the user selects a new template for an existing parade night that has sessions:

1. Call `planningApi.getTemplateImpact(nightId, newTemplateId)`.
2. If `removed_periods.length > 0` or `affected_sessions.length > 0`, show `TemplateImpactModal`.
3. On confirm, call `planningApi.applyTemplate(nightId, newTemplateId, true)` and invalidate queries.
4. If no removals, call `applyTemplate` immediately without showing the modal.

```typescript
const handleTemplateChange = async (nightId: string, newTemplateId: string) => {
  try {
    const impact = await planningApi.getTemplateImpact(nightId, newTemplateId);
    const needsConfirmation = impact.removed_periods.length > 0 || impact.affected_sessions.length > 0;
    if (needsConfirmation) {
      setPendingTemplateChange({ nightId, newTemplateId, impact });
      setShowImpactModal(true);
    } else {
      await planningApi.applyTemplate(nightId, newTemplateId, false);
      queryClient.invalidateQueries({ queryKey: ['parade-night', nightId] });
    }
  } catch (e) {
    setError('Failed to check template impact. Try again.');
  }
};
```

- [ ] **Step 4: Run tests**

```bash
cd frontend && npm run test -- --run src/__tests__/TemplateImpactModal.test.tsx
npx tsc --noEmit
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/planning/TemplateImpactModal.tsx \
        frontend/src/components/planning/views/ParadeNightGridView.tsx \
        frontend/src/__tests__/TemplateImpactModal.test.tsx
git commit -m "feat(planning): add TemplateImpactModal for template change confirmation

Shows retained/removed/added periods and affected sessions before
applying a template change. Immediate apply when no removals detected."
```

---

### Task 8: Simplified Create Parade Night form + redirect to training plan

**Files:**
- Modify: The file containing the "Create Parade Night" form. Search for the form in:
  - `frontend/src/components/planning/GuidedYearSetupModal.tsx`
  - `frontend/src/components/planning/SetupPanel.tsx`
  - `frontend/src/routes/` (any route file with parade night creation)
  - Run: `grep -rl "create.*parade" frontend/src --include="*.tsx" -i` to locate it.
- Modify: `frontend/src/api/index.ts` if the create function needs updating.

**Interfaces:**
- Produces: Create Parade Night form accepts exactly: Term (dropdown), Date (date picker), Timing Template (required select), Notes (optional textarea). No period count input. On submit, calls the create endpoint with `timing_template_id` required. On success, navigates to the training plan for the created night.

- [ ] **Step 1: Locate the Create Parade Night form**

```bash
grep -rl "parade.night\|parade_night\|createParadeNight\|create.*parade" frontend/src --include="*.tsx" -i | head -10
```

Open the file(s) found. Document in the ledger: which file, which function/component, current form fields.

- [ ] **Step 2: Remove the session_count / period_count input**

Find the `<input type="number" ... session_count>` or equivalent field. Delete it entirely — period count is derived from the template.

- [ ] **Step 3: Add the Timing Template field as required**

If a template picker doesn't exist in the form, add:

```tsx
<label htmlFor="timing_template_id">
  Timing Template <span aria-label="required">*</span>
</label>
<select
  id="timing_template_id"
  name="timing_template_id"
  required
  value={formState.timing_template_id}
  onChange={e => setFormState(s => ({ ...s, timing_template_id: e.target.value }))}
  aria-required="true"
>
  <option value="">Select a timing template…</option>
  {templates.map(t => (
    <option key={t.id} value={t.id}>{t.name}</option>
  ))}
</select>
```

Fetch templates using the existing endpoint (find the route in the backend — likely `GET /api/training/timing-templates?squadron_id=...`).

- [ ] **Step 4: Remove parade_type input (auto-set to 'normal')**

If the form has a parade_type field, remove it. It is now set server-side to `'normal'` by default.

- [ ] **Step 5: On successful creation, navigate to the training plan**

After the create call returns, navigate to the planning view for the created night. The exact navigation call depends on the routing library used (React Router, etc.):

```typescript
const result = await planningApi.createParadeNight(formData);
// Navigate to the parade night's planning grid:
navigate(`/planning/parade-nights/${result.id}`);
// OR if using the existing nav pattern:
setActiveNight(result.id);
queryClient.invalidateQueries({ queryKey: ['parade-nights'] });
onClose();
```

Find the exact navigation pattern by searching for how other create flows redirect (e.g. `grep -n "navigate\|setActive\|onClose" frontend/src/components/planning/ -r`).

- [ ] **Step 6: Test the form manually**

Start the Vite dev server and the backend:
```bash
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000 &
cd frontend && npm run dev
```

1. Open `http://localhost:5173/planning` (or the configured dev port)
2. Log in
3. Click "Create Parade Night"
4. Verify form shows: Term, Date, Timing Template (required), Notes. No session count field.
5. Try submitting without a template — verify browser validation prevents submission.
6. Submit with all fields — verify redirect to the planning grid for the new night.
7. Verify the planning grid shows the correct number of columns (from the template's instructional periods).

- [ ] **Step 7: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 8: Commit**

```bash
git add frontend/src/
git commit -m "feat(planning): simplified Create Parade Night form + redirect to training plan

Form now accepts: Term, Date, Timing Template (required), Notes.
Period count and parade_type removed from form — derived server-side.
After creation, navigates directly to the training plan for the new night."
```

---

### Task 9: Apply frontend-design + apple-design to the planning grid

**Note:** This task invokes two design skills. Load them using the `Skill` tool before writing any CSS. This task is primarily visual — it must be verified in the browser.

**Files:**
- Modify: `frontend/src/components/planning/TimingStrip.module.css`
- Modify: `frontend/src/components/planning/views/ParadeNightGridView.tsx` + its CSS
- Modify: `frontend/src/styles/tokens.css` (if adding new design tokens; do not rename existing tokens)
- Modify: Any cell, row, header, and phase-group label CSS

**Interfaces:**
- Produces: A planning grid that follows the AAFC VIG palette (tokens in `frontend/.claude/rules/frontend.md`), passes WCAG AA contrast, looks polished at both 1440px and 375px, and has visible keyboard focus on all interactive controls.

**Design invariants:**
- Use AAFC brand tokens: `--aafc-blue` (or `var(--blue, #51b0e3)`), `--aafc-dark` (`#002f65`), existing semantic tokens.
- Do not rename existing CSS variables — only ADD new ones.
- Instructional period column headers: use `--accent` (AAFC blue) background with white text.
- Non-instructional blocks in the TimingStrip: `--surface-2` background, `--muted` text.
- Phase group headers: `--aafc-dark` (`#002f65`) background, white text, uppercase, letter-spacing 0.08em.
- Archived training class rows: `opacity: 0.5`, `cursor: not-allowed`, a "Archived" badge in `--lgrey`.
- Focus ring: `outline: 2px solid var(--accent)`, `outline-offset: 2px` — visible on all buttons and dropdowns.
- Responsive: grid uses `overflow-x: auto` container, minimum cell width `140px`, column header and row label are sticky (`position: sticky`) so they don't scroll with the grid.
- Grid row height: minimum 80px per training class row to accommodate curriculum + facilitator + room content.
- Session cell with data: white background, `--sh` box-shadow, `border-left: 3px solid var(--accent)` for sessions with curriculum.
- Session cell empty: `--surface-2` background, dashed `--border` border, 40% opacity "+" hint that becomes fully visible on hover/focus.

- [ ] **Step 1: Load the frontend-design skill**

```
Skill: frontend-design:frontend-design
```

Apply the skill's design process — brainstorm a compact token system for the planning grid, review it against generic defaults, revise if needed.

- [ ] **Step 2: Load the apple-design skill**

```
Skill: apple:hig-reviewer
```

Use the HIG reviewer's principles for the planning grid's interactive cells, focus states, and touch targets (minimum 44×44pt for the empty cell "+ add" target).

- [ ] **Step 3: Write the CSS**

Apply the design from Steps 1-2 to the component CSS modules. Key areas:

**Grid structure:**
```css
.gridWrapper {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.gridTable {
  border-collapse: collapse;
  table-layout: fixed;
  min-width: 100%;
}

.colHeader {
  position: sticky;
  top: 0;
  background: var(--accent);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  text-align: center;
  padding: 8px 12px;
  white-space: nowrap;
  min-width: 140px;
  z-index: 2;
}

.rowLabel {
  position: sticky;
  left: 0;
  background: var(--surface);
  z-index: 1;
  border-right: 1px solid var(--border);
}

.phaseHeader td {
  background: var(--aafc-dark, #002f65);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding: 4px 12px;
}
```

**Session cell:**
```css
.sessionCell {
  min-height: 80px;
  padding: 8px;
  vertical-align: top;
  border: 1px solid var(--border-light);
  cursor: pointer;
  transition: background 0.1s ease;
}

.sessionCell:focus-within {
  outline: 2px solid var(--accent);
  outline-offset: -2px;
}

.sessionCell[data-has-curriculum='true'] {
  border-left: 3px solid var(--accent);
  background: var(--surface);
  box-shadow: var(--sh);
}

.sessionCell[data-empty='true'] {
  background: var(--surface-2);
  border: 1px dashed var(--border);
}

.sessionCell[data-has-conflict='true'] {
  border-left: 3px solid var(--red);
}
```

- [ ] **Step 4: Verify in browser — golden path**

With dev server running:

1. Open the planning workspace at 1440px viewport width.
2. Select a parade night that has a timing template with 3+ instructional periods.
3. Verify: TimingStrip shows above the column headers, non-instructional blocks are distinguishable.
4. Verify: Column headers show the period labels from the template (not "1", "2", "3").
5. Verify: Phase groups show the curriculum phase name, not "Orientation & Initial" or similar hardcoded text.
6. Verify: Archived training class rows are visually distinct (muted appearance).
7. Verify: A session cell with curriculum has the left accent border.
8. Verify: An empty cell has the dashed border and a visible "+ add" hint.
9. Resize to 375px: verify the grid scrolls horizontally within its container (page body does not scroll sideways).
10. Tab through the grid: verify every interactive element has a visible focus ring.

Report browser findings in the ledger (pass/fail per check) before committing.

- [ ] **Step 5: Fix any visual regressions from the golden path**

If any check fails, fix and re-verify in browser before moving on.

- [ ] **Step 6: TypeScript check + test run**

```bash
cd frontend && npx tsc --noEmit
npm run test -- --run
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/
git commit -m "design(planning): apply frontend-design + apple-design to planning grid

AAFC VIG palette, sticky row/col headers, instructional period accent,
phase group headers, archived class styling, WCAG AA focus rings,
responsive overflow-x on grid at 375px."
```

---

### Task 10: Regression sweep and cross-browser check

**Files:**
- Run: full TypeScript check + Vitest suite
- Run: browser golden path at 1440px and 375px
- Verify: BLOCK_PERIODS and BLOCK_GROUPS are completely gone

- [ ] **Step 1: Grep to confirm no BLOCK_PERIODS or BLOCK_GROUPS remain**

```bash
grep -rn "BLOCK_PERIODS\|BLOCK_GROUPS\|DISPLAY_GROUPS" frontend/src/
```
Expected: 0 matches.

- [ ] **Step 2: Run full TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```
Expected: 0 errors.

- [ ] **Step 3: Run full test suite**

```bash
npm run test -- --run
```
Expected: all tests pass.

- [ ] **Step 4: Run backend test suite**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/ -q
```
Expected: same pass count as baseline (no regressions from any TypeScript changes that touched the API layer).

- [ ] **Step 5: Browser golden path — shared session banner**

For a session that belongs to multiple training classes (a `shared` session via `SessionAudience`):
- Open the session detail in the right drawer.
- Verify a banner is shown: "This session is shared across [N] classes. Changes affect all."
- Verify it opens directly (no extra confirm) per grill-me decision 5A.

- [ ] **Step 6: Browser golden path — historical archived class**

- Open a parade night.
- If an archived training class exists in the phase group, verify it appears as a greyed, non-interactive row with an "Archived" badge.
- Verify clicking the cell does not open the edit drawer.

- [ ] **Step 7: Security greps**

```bash
grep -rcE "ADMIN703|ADMIN7WG|ADMINNATIONAL|SYSADMIN2026|plain_code|code_hash|access_code" connected-frontend/ || true
grep -rcE "JWT_SECRET|SECRET_KEY|DATABASE_URL" connected-frontend/ || true
```
All must return 0.

- [ ] **Step 8: Push**

```bash
git push origin main
```

---

## Plan B complete

React Planning Workspace API contract delivered:

| Feature | Status |
|---|---|
| BLOCK_PERIODS deleted | Done |
| BLOCK_GROUPS deleted | Done |
| DISPLAY_GROUPS deleted | Done |
| Dynamic columns from `instructional_periods` | Done |
| TimingStrip above grid | Done |
| Phase grouping from curriculum phases | Done |
| Full cell behaviour (curriculum/fac/assistants/room) | Done |
| TemplateImpactModal | Done |
| Simplified Create Parade Night form | Done |
| Redirect to training plan after creation | Done |
| frontend-design + apple-design applied | Done |
| Responsive 1440→375px | Done |
| WCAG AA focus, keyboard nav | Done |

**Next:** Plan C (Connected TMS + CEA button) can proceed independently.
