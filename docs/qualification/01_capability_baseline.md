# Capability Baseline — AAFC TMS

Generated 2026-08-08 from commit `76d6723`. Machine-readable form: `capability_manifest_before.json`.

## Method

Every number in this document was extracted mechanically, not hand-counted or estimated:

- **API endpoints**: `app.openapi()` on the real, fully-imported FastAPI app (not a grep over
  `@router.` decorators, which would double-count or miss decorator variations) — 259 endpoints
  across 259 (method, path) pairs.
- **Database tables**: introspected from `Base` metadata via every model class in `app/models`
  that subclasses `Base` and declares `__tablename__` — 58 tables, with column counts and
  foreign-key edges extracted per table.
- **Planning Workspace routes**: every `<Route path=...>` in `frontend/src/App.tsx` — 21 routes
  (full-app mode; `/planning` itself is also the sole module-mode route).
- **connected-frontend pages**: every `id="page-*"` element in `connected-frontend/index.html` —
  20 top-level pages (each may contain many tabs/modals/forms not separately counted here yet).
- **Roles**: the literal `ROLES` set in `backend/app/permissions.py` — 8 roles (`sqn_general`,
  `sqn_admin`, `wing_viewer`, `wing_admin`, `national_viewer`, `national_admin`, `system_admin`,
  `auditor`).

## Headline numbers

| Dimension | Count |
|---|---|
| API endpoints | 259 |
| Database tables | 58 |
| Planning Workspace routes | 21 |
| connected-frontend top-level pages | 20 |
| Roles | 8 |

### API endpoints by router/tag

| Router | Endpoints |
|---|---|
| training | 67 |
| planning | 61 |
| organisations | 20 |
| ops | 19 |
| cadet-program | 19 |
| accounts | 17 |
| system | 14 |
| timing | 10 |
| wing-calendar | 9 |
| auth | 7 |
| dashboard | 4 |
| export-import | 4 |
| health | 4 |
| jobs | 2 |
| setup | 1 |
| untagged | 1 |

## What this baseline is, and is not, yet

This is the **mechanical skeleton** of the capability baseline §5 asks for (routes, tables, roles,
top-level pages/routes) — real, verified counts anyone can reproduce by re-running the same
introspection. It is **not yet** the full granular inventory §5 describes: "every tab; every modal;
every drawer; every form; every field; every table [UI table]; every chart; every action; every
context menu; every filter; every search; every import; every export; every archive; every restore;
every bulk operation." That finer-grained inventory is a substantially larger undertaking (order of
magnitude more items than the 259+58+41 counted here) and will be built incrementally into
`capability_matrix.csv` as each functional area is reviewed in Phases B onward, rather than attempted
as a single exhaustive pass before any other work starts — attempting to enumerate every field of
every form by hand-reading source before doing anything else would consume a large fraction of this
program's budget on transcription rather than analysis, and this repository already has a large body
of accurate capability documentation from the preceding remediation program
(`docs/remediation/master_gap_register.csv`, 112 entries; `docs/beta/`) that the architecture and
data-integrity reviews below draw on directly rather than re-deriving from zero.

**Known pre-existing findings this baseline already confirms mechanically** (previously documented
in this session's own plan-mode research, now independently corroborated by table introspection):

- `scheduled_sessions` (22 columns, 5 foreign keys) and `planning_locations` (11 columns, 1 foreign
  key) both still exist as real tables in the schema. Prior investigation (this program's
  predecessor session) found these vestigial — `TrainingArea` and `sessions` are the actual
  live-traffic tables for physical-space and session-scheduling data respectively, with
  `scheduled_sessions`/`PlanningLocation` model classes present in `app/models/planning.py` but with
  zero live call sites in any router. This baseline confirms the tables are still physically present
  (not yet cleaned up) — carried into `03_data_integrity_review.md` as a tracked, not-yet-actioned
  item, not re-investigated from scratch.

## Next steps for this document

1. Extend `capability_matrix.csv` per functional area (Dashboard, Parade Nights, Facilitators,
   Activities, Curriculum, Accounts, System Console, Planning Workspace's own component tree) with
   the full role → frontend → API → table → test trace §5 specifies, prioritised by Phase B/C's own
   findings rather than done exhaustively up front.
2. Cross-reference the 259-endpoint list against `docs/remediation/master_gap_register.csv`'s 112
   entries to identify which endpoints already have documented test/verification history and which
   do not — feeds `api_contract_matrix.csv`.
3. Regenerate `capability_manifest_after.json` at the end of Phase C (architecture/integration
   defect correction) and diff against this file — any endpoint/table/route count reduction must be
   explained in the decision log, not silently absorbed.
