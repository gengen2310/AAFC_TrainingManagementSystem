# Reference Key / Variable Inventory — Stage 0 starting point

Full duplicate/near-duplicate scan across DB columns, enum values, Pydantic
fields, frontend state keys, storage keys, CSV headers, etc. (Section 4 of the
remediation instruction) is a substantial, dedicated audit — not attempted
exhaustively in Stage 0. What's confirmed so far, surfaced during this session's
actual work rather than a separate sweep:

## Confirmed real duplication (feeds `domain_model_inventory.md`)

- `Activity.squadron_id`/`wing_id` are **plain `String(36)` columns, not DB-enforced
  foreign keys** (denormalized by design, since an Activity can be
  national-owned with both null) — contrast with `TrainingArea.squadron_id`,
  `Facilitator.squadron_id`, etc., which *are* real FKs. This distinction mattered
  directly this session: the generic `fk_dependents()` safety check (built for
  hard-delete) does **not** catch Activity references, so every hard-delete
  endpoint explicitly adds a supplementary Activity count check alongside it. Any
  future entity with a similar denormalized reference needs the same treatment,
  not just `fk_dependents()`.
- `year` / `training_year` / `planning_year_id` — checked, no drift found: the
  codebase consistently uses `planning_year_id` as the FK column name and
  `PlanningYear.year` (an int) for the display year. Section 4's example is
  hypothetical here, not a confirmed finding.
- `unit_id` vs `squadron_id` — both exist and both mean "squadron" in different
  tables (`PlanningYear.unit_id`, `ParadeDate.unit_id` vs. `Activity.squadron_id`,
  `Facilitator.squadron_id`). Confirmed real naming inconsistency, low risk (both
  resolve to the same FK target `squadrons.id`), not yet consolidated.

## Not yet done

- Frontend state/storage key audit (`S.*` fields in connected-frontend,
  sessionStorage keys, React state variable names) — not started.
- Enum-value consistency audit (`cancelled`/`canceled`, `not_delivered`/
  `undelivered`, session-status strings, role names) — not started.
- CSV import header audit (facilitator import, curriculum import, CEA import) —
  not started.
- Learning Hub URL field audit — folded into REM-19 in the gap register, not
  started.

This file will grow as Stage 1 (canonical domain map) proceeds — recorded now as a
placeholder with real, dated findings rather than a fabricated complete audit, per
`.claude/rules/capability-preservation.md` §3 (no false closure).
