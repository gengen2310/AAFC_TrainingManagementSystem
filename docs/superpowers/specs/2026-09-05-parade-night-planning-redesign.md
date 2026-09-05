# Parade Night Planning Redesign — Design Spec

**Date:** 2026-09-05  
**Status:** Approved for implementation  
**Author:** Jenny DV  

---

## Goal

Remove competing sources of truth for Parade Night timing, training-period counts, and facilitator assignments. Replace hard-coded three-period assumptions and legacy phase fallbacks with data-driven derivation from existing canonical models. Expose the existing canonical CEA importer from TMS Activities. Produce a clean, efficient planning grid that works on desktop, tablet, and phone.

The principle throughout: **Define once, use everywhere.** No parallel records for the same domain concept.

---

## Product decisions (grill-me settled)

| # | Question | Decision |
|---|---|---|
| 1 | CEA import permissions | Wing Admin+ only; sqn_admin sees no button |
| 2 | Template change after Sessions exist | Impact preview required; explicit confirmation; Sessions never silently deleted |
| 3 | Non-instructional block presentation | Read-only timeline strip always visible above the grid |
| 4 | Backup facilitator | Keep `backup_facilitator_id` as a distinct semantic field |
| 5 | Shared session editing | Open shared Session directly; banner warns which classes are affected |
| 6 | Multi-period curriculum | Out of scope; single-period Sessions only |
| 7 | Historical archived classes | Visible in grid, labelled [Archived], cells read-only |
| 8 | Parade type | Non-standard types (`activity`, `ceremonial`, `admin`, `stand_down`, `cancelled`) remain reachable via existing flows; standard creation auto-sets `normal` |
| 9 | Notes | Exactly one user-facing planning note field on ParadeNight |

---

## Architecture overview

### Before

```
New Parade Night
  → parade_type (user selects)
  → start_time / end_time (user enters)
  → session_count 1/2/3 radio (user selects)   ← or →
  → timing_template_id (optional)
  → notes

Planning grid
  → BLOCK_PERIODS = [1, 2, 3]  ← always 3 columns
  → BLOCK_GROUPS = {O&I, Bronze, Silver, Gold}  ← fallback hard-codes phases

Session
  → facilitator_id
  → assistant_facilitator_id   ← one assistant only
  → backup_facilitator_id

TMS Activities  →  no CEA import button
```

### After

```
New Parade Night
  → Term (required)
  → Date (required)
  → timing_template_id (REQUIRED — API enforces)
  → notes (optional, one field)
  → parade_type auto-set to 'normal'
  → start_time / end_time derived from template, stored as snapshot
  → (creation triggers snapshot materialisation)

Planning grid
  → columns = parade_night_timing_snapshots WHERE is_instructional = true
  → rows = TrainingClass grouped by training_stage_id (→ TrainingStage name)
         + "Unassigned" group for classes with no stage
  → non-instructional blocks → TimingStrip component above grid

Session
  → facilitator_id (one main)
  → backup_facilitator_id (distinct semantic, kept)
  → SessionAssistantFacilitator (zero-to-many, join table)

TMS Activities
  → "Import from CEA" button → wing_admin+ only → canonical pipeline
```

---

## Database changes

### Migration A — SessionAssistantFacilitator

Create join table:

```sql
CREATE TABLE session_assistant_facilitators (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES users(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (session_id, user_id)
);
CREATE INDEX ON session_assistant_facilitators (session_id);
```

Backfill:

```sql
INSERT INTO session_assistant_facilitators (session_id, user_id)
SELECT id, assistant_facilitator_id
FROM sessions
WHERE assistant_facilitator_id IS NOT NULL
ON CONFLICT DO NOTHING;
```

**Do NOT drop `assistant_facilitator_id`** — keep as nullable deprecated column. Mark it `-- deprecated: use session_assistant_facilitators` in the model. Drop in a later migration after all consumers are confirmed migrated.

`backup_facilitator_id` — unchanged, no migration required.

### Migration B — Timing snapshots

Create snapshot table:

```sql
CREATE TABLE parade_night_timing_snapshots (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parade_night_id  UUID NOT NULL REFERENCES parade_nights(id) ON DELETE CASCADE,
    period_number    INTEGER NOT NULL,   -- 1-based; instructional periods only
    block_label      TEXT NOT NULL,      -- e.g. "Period 1", or template block name
    start_time       TIME,               -- wall-clock start from template block
    end_time         TIME,               -- wall-clock end from template block
    is_instructional BOOLEAN NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (parade_night_id, period_number)
);
CREATE INDEX ON parade_night_timing_snapshots (parade_night_id);
```

Backfill for existing nights with a `timing_template_id`: read the template's instructional `TimingBlock` records ordered by `order_index`; assign `period_number` 1..N; write snapshot rows.

Nights with no `timing_template_id` get no snapshot rows. The grid falls back to `session_count` for legacy nights.

### Migration C — No DB constraint change on timing_template_id

`timing_template_id` remains nullable at the DB level. Legacy nights must stay valid. The NOT NULL requirement is enforced at the API layer (create endpoint only).

---

## Backend API changes

### Create Parade Night endpoint

`POST /api/planning/years/{year_id}/parade-nights`

**New validation rule:** Reject with HTTP 422 if `timing_template_id` is absent or null.

**After save:** Materialise timing snapshot immediately — call `_materialise_snapshot(parade_night_id, timing_template_id)` helper. This writes `parade_night_timing_snapshots` rows for every `TimingBlock` that is `is_instructional = True`, in `order_index` order. Also derives and stores `start_time` / `end_time` on the ParadeNight itself from the first/last instructional block times.

**auto-set fields:** `parade_type = 'normal'`, `session_count` derived from instructional block count (stored as compatibility snapshot).

### Template change impact endpoint

`GET /api/planning/parade-nights/{night_id}/template-impact?new_template_id={uuid}`

Returns:

```json
{
  "retained_periods": [1, 2],
  "removed_periods": [3],
  "added_periods": [4],
  "affected_sessions": [
    {"session_id": "...", "period_number": 3, "has_curriculum": true, "has_facilitator": true}
  ]
}
```

Used by the frontend confirmation modal before committing a template change.

### Apply template change endpoint

`PATCH /api/planning/parade-nights/{night_id}/template`

Body: `{"timing_template_id": "..."}`. 

Only accepted after frontend sends `confirmed: true`. Backend:
1. Validates no Sessions exist on removed periods, OR that `confirmed: true` was sent (warning, not block)
2. Deletes old `parade_night_timing_snapshots` for this night
3. Writes new snapshot from new template
4. Does NOT delete Sessions (user must clean up orphaned-period Sessions manually; they become visible as "period not in template" state)
5. Updates `parade_night.timing_template_id`, `start_time`, `end_time`, `session_count`

### Night summaries endpoint — instructional periods

`GET /api/planning/years/{year_id}/night-summaries`

Add `instructional_periods` array to each night's response:

```json
{
  "parade_night_id": "...",
  "instructional_periods": [
    {"period_number": 1, "label": "Period 1", "start_time": "18:30", "end_time": "19:10"},
    {"period_number": 2, "label": "Period 2", "start_time": "19:20", "end_time": "20:00"}
  ],
  "timing_strip": [
    {"label": "Opening Parade", "start_time": "18:00", "end_time": "18:30", "is_instructional": false},
    {"label": "Period 1", "start_time": "18:30", "end_time": "19:10", "is_instructional": true},
    ...
  ]
}
```

Derived from `parade_night_timing_snapshots`. Fallback: if snapshot absent, derive from `session_count` (returns periods 1..session_count with no times).

### Session assistant facilitators

`GET /api/sessions/{session_id}` — add `assistant_facilitators: [{user_id, display_name}]`  
`POST /api/sessions/{session_id}/assistants` — body: `{user_id}`  
`DELETE /api/sessions/{session_id}/assistants/{user_id}`

Conflict engine: extend `PlanningConflict` detection to treat `session_assistant_facilitators` rows the same as `facilitator_id` — a person cannot be assistant in two simultaneous sessions, and cannot be both main and assistant in overlapping sessions.

### CEA import — no new endpoint

No changes to `POST /api/planning/years/{year_id}/cea/import`. Permission model unchanged (Wing Admin+).

The CEA parser alias audit: verify the canonical parser accepts these exact column names:

```
SeqNr, Name, Start date, Start time, End date, End time, Unit, Location, Activity Notes
```

If any alias is missing, add it to the canonical parser's alias map only. No new parser.

---

## Frontend — React Planning Workspace

### Dynamic column derivation (replaces BLOCK_PERIODS)

In `ParadeNightBlock.tsx` and `ListView.tsx`, replace:

```ts
const BLOCK_PERIODS = [1, 2, 3]
```

with:

```ts
const periods = night.instructional_periods  // from night-summaries API
// [{period_number, label, start_time, end_time}]
```

If `instructional_periods` is empty and `session_count` is present, fall back to:

```ts
Array.from({length: session_count}, (_, i) => ({period_number: i+1, label: `Period ${i+1}`}))
```

This preserves legacy nights. Modern nights always have snapshot data.

### Phase-grouped rows (replaces BLOCK_GROUPS fallback)

Build grid rows from `TrainingClass` records grouped by `training_stage_id`:

```ts
const groups = groupBy(classes, c => c.training_stage_id ?? '__unassigned__')
const rows = Object.entries(groups).map(([stageId, classes]) => ({
  groupLabel: stages.find(s => s.id === stageId)?.name ?? 'Unassigned — needs configuration',
  rows: classes.map(c => ({classId: c.id, label: c.name, archived: c.is_archived}))
}))
```

Archived classes: included in rows, `archived: true` → cell renders as read-only with `[Archived]` label. `is_archived` comes from the existing `TrainingClass` query. Historical nights: SessionAudience rows referencing archived classes are read from the existing Session data — the class name is stored on the SessionAudience as a snapshot (verify this; if not snapshotted, fetch archived classes in a separate query gated by `include_archived=true`).

BLOCK_GROUPS fallback: retained as a separate code path activated only when `training_classes.length === 0` AND the night has `cadet_group` data on Sessions. Never activates for modern configured years.

### Non-instructional timeline strip

New component `TimingStrip.tsx`:

```tsx
<TimingStrip blocks={night.timing_strip} />
```

Renders a read-only horizontal row above the planning grid showing all blocks — instructional and non-instructional — as coloured chips with times. Non-instructional blocks (Opening Parade, Break, Admin, Closing Parade) use a muted colour. Instructional blocks match the column positions below.

Hidden when `timing_strip` is empty (legacy nights without template).

### Shared session banner

When a Session has multiple SessionAudience rows, the cell renders normally in each participating class row. When opened in the inspector, a banner appears:

```
This session is shared with [Class A] and [Class B]. 
Changes affect all listed classes.
```

No split/merge controls in scope for this task.

### Template change confirmation modal

New component `TemplateImpactModal.tsx`:

Shows:
- Retained periods (green)
- Removed periods (red) with count of affected Sessions
- Added periods (blue)

Requires checkbox confirmation if Sessions would be orphaned. Cancel returns to current template. Confirm calls `PATCH /parade-nights/{id}/template`.

### Simplified Create Parade Night form

In `PlanningWorkspace.tsx` (or equivalent create form):

Remove: `parade_type` selector, `start_time` input, `end_time` input, `session_count` radio.  
Keep: Term, Date, Timing Template (required, searchable), Notes.  
After creation: navigate directly to the planning grid for the new night.

### Cell editor — assistant facilitators

The right-side inspector/panel for a Session cell adds:

- Main facilitator: single-select (existing)
- Backup facilitator: single-select (existing, keep)
- Assistant facilitators: multi-select with add/remove; shows current list; max display 3 names inline + "+N more"

---

## Frontend — Connected TMS (index.html)

### Simplified Create Parade Night form

In the TMS parade night creation flow:

Remove from the form: `parade_type` dropdown, `start_time`, `end_time`, `session_count` radio.  
Add: Timing Template searchable dropdown (required — form submission blocked without it).  
Keep: Term, Date, Notes.

The existing non-standard parade night creation paths (admin, ceremonial, etc.) are separate flows — audit and ensure they remain reachable for the appropriate roles. They may continue to accept the full field set.

### CEA import button in Activities

In the Activities page section (`page-activities` or equivalent):

Add "Import from CEA" button, visible only when:

```js
getScopeType() === 'wing' || getScopeType() === 'national' || getScopeType() === 'system_admin'
```

On click: navigate to the Planning Workspace CEA import flow for the current planning year (open in the same tab or navigate to Planning Workspace with the import panel active). Do NOT call any backend endpoint directly from TMS for the import; the entire workflow runs in Planning Workspace.

---

## UX design principles (to be developed with frontend-design + apple-design)

The planning grid is a **working tool**, not a dashboard. Design priorities in order:

1. Clarity of state — at a glance, can the Training Officer see what's planned and what's missing?
2. Efficiency — editing a single cell must take ≤3 taps/clicks
3. Context — the user always knows which date, phase, class, and period they're editing
4. Density — show the full matrix on a 1280px desktop without horizontal scrolling
5. Progressive disclosure — advanced detail (assistants, conflicts, room) behind one click

**Desktop** (1280px+): Sticky left column (class names), sticky top row (period headers + timing strip), right-side inspector panel for cell editing. Matrix overview dominates.

**Tablet** (768–1024px): Same matrix, inspector overlays as a bottom drawer or side sheet. Pinch to zoom if needed.

**Phone** (≤430px): Period tabs at top, scroll class list below, bottom-sheet editor. Sticky header shows date + period + class while editing.

---

## Accessibility

- Keyboard: Tab between cells, Enter to open inspector, Escape to close, Arrow keys within matrix
- Every cell has an accessible name: "{class name}, {period label}, {status}"
- Conflict indicators use icon + colour (not colour alone)
- Archived class rows have `aria-disabled="true"` and visible label
- Shared session banner announced to screen readers
- Visible focus ring on all interactive elements

---

## Invariants enforced by this design

| Invariant | Enforcement point |
|---|---|
| New standard Parade Nights require a Timing Template | API create endpoint (HTTP 422 if absent) |
| Instructional period count derives from template, not user input | Snapshot written at creation; grid reads snapshot |
| Changing master template does not silently rewrite existing nights | Snapshot is written once at creation; separate PATCH endpoint for deliberate changes |
| Template change with Sessions requires confirmation | Frontend blocks without `confirmed: true`; backend does not auto-delete Sessions |
| session_count is always consistent with snapshot | Derived and stored at creation time; updated when template is deliberately changed |
| One main facilitator per Session | Existing FK constraint unchanged |
| Zero-to-many assistants via join table | SessionAssistantFacilitator; old column deprecated but not dropped |
| Backup facilitator is a distinct concept | Separate column; not merged into assistant join table |
| CEA import is Wing Admin+ only | Existing endpoint permission unchanged; button hidden below wing scope |
| Non-standard Parade Night types remain reachable | Standard creation auto-sets 'normal'; other types accessible via existing separate flows |
| One notes field per Parade Night (user-facing) | Form and API expose ParadeNight.notes only; ParadeDate.notes and Session.notes serve different semantics and are not surfaced as "the notes field" |

---

## Legacy compatibility

| Legacy state | Behaviour |
|---|---|
| Night with `timing_template_id = NULL` | Opens; grid shows `session_count` columns (or period 1..N fallback); TimingStrip hidden; no regeneration of Sessions |
| Night with `session_count` but no snapshot | Backfill script writes snapshot if template exists; otherwise falls back to count |
| `assistant_facilitator_id` column non-null | Read as an assistant for display; join table authoritative going forward |
| BLOCK_GROUPS cadet_group fallback | Active only when no `TrainingClass` records exist for the year; modern years unaffected |
| Historical Sessions referencing archived TrainingClass | Displayed read-only in grid; archived-class query run with `include_archived=true` for historical nights |

---

## Test requirements (abbreviated — full suite in implementation plan)

**Timing:**
- Templates with 1, 2, 3, 4, 5 instructional periods → correct column count each
- Template with mixed instructional/non-instructional blocks → only instructional become columns; all blocks appear in TimingStrip
- New night without template → API returns 422
- Legacy night without template → opens and displays correctly
- Template change without Sessions → allowed without confirmation
- Template change with Sessions → impact preview shown; Sessions not deleted on confirm

**Training classes:**
- 3 phases × 2–3 classes each → all render
- Class with no stage → visible in "Unassigned" group
- Archived class in active year → read-only row visible
- Historical night with archived class → row visible and read-only

**Facilitators:**
- 0 assistants; 1 assistant; 3 assistants — each saves and reads correctly
- Existing `assistant_facilitator_id` migrated → appears as assistant after migration
- Conflict: main vs assistant in same period → conflict detected
- Backup facilitator unchanged by migration

**CEA:**
- Wing Admin sees button; sqn_admin does not
- Button navigates to canonical workflow; no call to retired endpoint
- Canonical parser accepts exact heading set: SeqNr, Name, Start date, Start time, End date, End time, Unit, Location, Activity Notes

---

## Files materially changed

| File | Change |
|---|---|
| `backend/app/models/planning.py` | Add `SessionAssistantFacilitator`, `ParadeNightTimingSnapshot` models |
| `backend/app/routers/planning.py` | Create endpoint enforces template; template-change impact + apply endpoints; night-summaries adds period data |
| `backend/app/routers/sessions.py` | Assistant facilitator CRUD endpoints; conflict engine extension |
| `backend/alembic/versions/` | Migration A (SessionAssistantFacilitator) + Migration B (snapshots) |
| `frontend/src/components/planning/ParadeNightBlock.tsx` | Dynamic columns; phase-grouped rows; TimingStrip; shared-session banner; archived read-only |
| `frontend/src/components/planning/views/ListView.tsx` | Dynamic columns |
| `frontend/src/components/planning/TimingStrip.tsx` | New component |
| `frontend/src/components/planning/TemplateImpactModal.tsx` | New component |
| `frontend/src/routes/ParadeNightDetail.tsx` | Template change UX; template-impact wiring |
| `frontend/src/routes/PlanningWorkspace.tsx` | Simplified create form; assistant facilitator cell editor |
| `frontend/src/api/index.ts` | New API calls for impact, apply-template, assistants |
| `frontend/src/api/types.ts` | New types for snapshot, assistants, impact response |
| `connected-frontend/index.html` | Simplified create form; CEA button in Activities |
| `backend/tests/test_planning.py` | Extended timing + class + snapshot tests |
| `backend/tests/test_sessions.py` | Assistant facilitator tests |
| `backend/tests/test_cea_consolidation.py` | CEA heading alias tests |

---

## Out of scope for this task

- Multi-period curriculum (spanning two consecutive periods) — deferred
- Drag-and-drop reordering
- Copy-session / copy-period efficiency features
- Full responsive redesign of the Planning Workspace shell (only the grid and create form)
- Wholesale merge of ParadeDate and ParadeNight models
- Dropping `assistant_facilitator_id` column (deprecated but kept for compatibility)
- Non-standard Parade Night creation flow redesign

---

## Risks

| Risk | Mitigation |
|---|---|
| Snapshot backfill uses current template state (not historical) | Documented; acceptable for backfill; new nights always correct |
| Many existing consumers of `assistant_facilitator_id` | Compatibility shim in model/router; column not dropped |
| Large ParadeNightBlock.tsx changes | Tested against all views (Year/Term/8-week/List/Detail) after each change |
| CEA parser alias gaps | Audit run before implementation; aliases added to canonical parser |
