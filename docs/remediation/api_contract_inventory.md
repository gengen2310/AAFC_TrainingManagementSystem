# API Contract Inventory — Stage 0 starting point

Raw route list (242 routes across 15 routers, extracted via static analysis) lives
in `capability_manifest_before.json` → `backend.routes_by_router`. This document is
for contract-level notes (request/response shape decisions, versioning,
backward-compatibility paths) that the raw list doesn't capture — filled in as
Stage 1 (canonical domain map / API contracts) proceeds, not exhaustively here.

## Known dual-shape endpoints (backward compatibility already in place)

- `GET /api/activities` — bare-array legacy shape when no `scope_type` param is
  given (session-scoped, what both frontends' "give me my activities" calls use);
  `{"items": [...], "truncated": bool}` shape when `scope_type` is given
  (inheritance-aware, what the shared Wing/National Activities widget uses). Both
  paths verified live this session — see `domain_model_inventory.md`.
- `GET /api/planning/years` — always a bare array; no `scope_type` variant. Now
  also drives rename/archive/restore/delete UI (this session's work), previously
  create/list/rollover only.

## Newly added contracts this session (2026-08-04)

| Endpoint | Method | Added for |
|---|---|---|
| `/api/activities/{id}/restore` | POST | REM-11 |
| `/api/planning/years/{id}` | DELETE | REM-08 |
| `/api/accounts/{id}` | DELETE | REM-07 |
| `/api/wings/{id}` | DELETE | REM-07 |
| `/api/squadrons/{id}` | DELETE | REM-07 |
| `/api/accounts/{id}/change-role` | POST | REM-05 (added in the plan immediately prior to this program) |
| `/api/wings`, `/api/squadrons` | GET | gained `include_archived` query param (previously archived-only-excluded, no way to list them) |

All of the above: audited, tested (see `master_gap_register.csv`'s `tests` column
per gap ID), staging-verified 2026-08-04.

## Reconciliation with `docs/api_reference.md` (Stage 1, 2026-08-04)

`docs/api_reference.md` is a real, substantive prior-pass document (219 lines,
request/response bodies, RBAC tables, block-type enums) — reconciled against
current code rather than re-derived:

- Account/Flight endpoints, Timing Template endpoints, Wing/Squadron/Curriculum
  endpoints, Parade Night Builder/Timing endpoints — spot-checked against current
  router source, still accurate.
- **"V9.1 Cadet Program routes" section (lines 68-76) confirms `program-packages`/
  `program-items`/`learning-hub-resources`/`program-coverage`/`program-promotion`
  were a real, deliberately-documented API surface at the time they were built** —
  this reinforces (doesn't contradict) the Stage 1 finding in
  `domain_model_inventory.md`: the backend was intentionally built and is
  correctly documented, it simply was never wired into either frontend's UI as the
  product evolved toward `CurriculumItem` instead. Worth stating precisely: this
  is not evidence of a mistake or abandoned half-feature, it's evidence of a real,
  complete feature that lost its frontend investment when the product direction
  shifted. That distinction matters for the eventual product decision (REM-26).
- `PATCH /api/accounts/{id}` documented as "update `display_name` and/or
  `flight_id`" (line 42) — still accurate for that endpoint; `POST
  /api/accounts/{id}/change-role` (added this session, REM-05) is a separate,
  additive endpoint, not a change to this one's contract.
- No `DELETE` endpoints for accounts/wings/squadrons/planning-years existed in
  this doc's original scope (predates this session's hard-delete work) — now
  documented in the "Newly added contracts" table above.

## Not yet done

- Full per-endpoint contract documentation for the remaining ~200 routes not
  covered by either `docs/api_reference.md` or this file's own additions.
- Versioning strategy — none exists today (no `/v1/` prefix, no header-based
  versioning); not flagged as broken, just unaudited.
