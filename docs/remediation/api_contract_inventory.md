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

## Not yet done

- Full per-endpoint contract documentation (request schema, response schema,
  error codes, auth requirement) — `docs/api_reference.md` exists from a prior pass
  and should be reconciled against, not re-derived, once Stage 1 formally starts.
- Versioning strategy — none exists today (no `/v1/` prefix, no header-based
  versioning); not flagged as broken, just unaudited.
