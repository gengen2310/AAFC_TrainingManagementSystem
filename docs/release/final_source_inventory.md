# Final Source Inventory (Stage 1)

Mechanically generated from the tracked source tree at
`release/final-assurance-2026-08-01`@`7ed573d`, not hand-summarised. Raw data:
`reports/final-assurance/file-inventory.csv`, `function-inventory.csv` (backend/app,
via Python `ast`), `frontend-function-inventory.csv` (`frontend/src`, regex-extracted),
`connected-frontend-function-inventory.csv`, `api-inventory.csv`.

## File-level totals (341 tracked files, excluding `docs/beta/`, `reports/`, stale worktrees)

| Category | Files | Lines |
|---|---:|---:|
| backend-test | 48 | 14,610 |
| backend-router | 16 | 14,331 |
| frontend-src | 77 | 13,815 |
| connected-frontend | 4 | 9,868 |
| doc | 44 | 8,981 |
| frontend-other | 18 | 7,442 |
| other | 19 | 3,088 |
| script | 7 | 2,735 |
| migration | 34 | 2,735 |
| frontend-e2e | 18 | 2,265 |
| backend-script | 7 | 1,577 |
| backend-core | 13 | 1,506 |
| ci-workflow | 4 | 1,395 |
| backend-model | 7 | 1,103 |
| backend-seed | 5 | 870 |
| tool | 8 | 828 |
| deployment-doc | 2 | 515 |
| backend-other | 10 | 308 |

`connected-frontend/index.html` alone is 9,868 lines with zero test/lint tooling of any
kind — confirmed the single largest untested surface in the system, as flagged in the
plan document before this stage began.

## Backend function/class inventory (`backend/app/`, via AST — precise, not regex)

641 definitions: 457 functions, 138 classes, 46 methods (nested `def`s inside a class
body — the low method count relative to class count reflects that most SQLAlchemy
model classes here declare no methods beyond column definitions).

**Models**: 57 SQLAlchemy model classes across 6 files (`organisations.py`: 8,
`operations.py`: 6, `planning.py`: 14, `program.py`: 9, `training.py`: 17,
`wing_calendar.py`: 3) — corrects the plan document's earlier "~30 entities" estimate,
carried forward into Stage 3's data traceability matrix.

## API inventory (`backend/app/routers/`)

237 endpoints across 15 router files, full path computed as `router prefix + route
decorator path` (not the decorator path alone — see correction below).

| Method | Count |
|---|---:|
| GET | 110 |
| POST | 94 |
| PATCH | 17 |
| DELETE | 14 |
| PUT | 1 |

By router file: `planning.py` 59, `training.py` 57, `ops.py` 19, `organisations.py` 18,
`accounts.py` 15, `program.py` 14, `system.py` 14, `timing.py` 10,
`wing_calendar.py` 9, `auth.py` 7, `dashboard.py` 4, `export_import.py` 4,
`health.py` 3, `jobs.py` 2, `setup.py` 1.

**Zero true duplicate (method, full_path) pairs** after correcting for router prefixes.

**Self-correction recorded for transparency**: the first pass of this inventory
compared route-decorator paths alone (ignoring each router's own `APIRouter(prefix=…)`)
and flagged `GET /facilitators` as defined in both `training.py` (prefix `/api`) and
`planning.py` (prefix `/api/planning`) — apparently a collision where one handler would
silently shadow the other. Investigating before reporting it as a finding: the true
paths are `/api/facilitators` (training.py, used by both frontends for basic
facilitator listing) and `/api/planning/facilitators` (planning.py, a distinct
role-scoped shape returning `display_name`/`unit_id`/`max_sessions_per_night` for the
Planning Workspace). Cross-checked against `frontend/src/api/index.ts` — it calls
`/api/facilitators` and `/api/planning/facilitators` as two genuinely separate,
correctly-routed endpoints. Not a defect; the initial flag was a tooling artifact, not
a real finding, and is recorded here rather than silently discarded so the correction
itself is auditable.

## Frontend function inventory

- `frontend/src/**/*.{ts,tsx}`: 238 top-level definitions (113 `function`, 92
  `exported-function`, 23 `const` arrow, 8 exported `const` arrow, 2 exported class) —
  regex-based, not AST; a small undercount is possible for functions defined as object
  methods or deeply nested closures, which this pass does not target (those are
  reviewed in Stage 2's line-by-line pass instead, not inventoried here).
- `connected-frontend/index.html`: 631 top-level `function`/`const =>` definitions in
  the single inline `<script>` block — the largest single-file function count in the
  system, consistent with it being a ~9,900-line no-build-step SPA.

## What this stage does not yet cover

This is a structural inventory (what exists, where, how much) — it is not yet the
line-by-line correctness/security/tenancy review (Stage 2), the full data-traceability
matrix (Stage 3), or the role/scope negative-authorization test pass (Stage 4). Those
stages consume these CSVs as their starting checklist rather than re-deriving file/
function/endpoint lists from scratch.
