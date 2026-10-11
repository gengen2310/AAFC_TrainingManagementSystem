# Bounded responses inventory (2026-10-04)

86 GET list endpoints were scanned (`backend/app/routers/*.py`). Only 3 accept
a limit parameter (`/audit`-style endpoints, `/search`, CEA lists) and a few
cap internally. Most need no pagination: their scope bounds them.

## Bounded by scope (no change needed)

| Endpoint family | Scope | Expected size |
|---|---|---|
| `/cadets`, `/cadets/risk`, `/facilitators`, `/equipment`, `/parade-nights` | the caller's active Squadron | tens–hundreds |
| `/years/{id}/term-planner`, `long-range`, `annual-program`, `parade-dates`, `holidays` | one Squadron's year | ≤ ~60 nights, ≤ ~400 sessions (query count now constant: see `test_query_count_session_serialisation.py`) |
| `/parade-dates/{id}/builder`, `weekly-program`, `/parade-nights/{id}/*` | one night | ≤ ~20 sessions |
| reference lists (`/curriculum/phases`, `/curriculum/elements`, tag lists, `/wings`, `/squadrons`) | national reference data | tens–low hundreds; the UI needs the full set |
| `/reports/*` | aggregated server-side | one row per unit/phase, not per record |

## Unbounded by design — decisions needed (not changed)

| Endpoint | Who sees everything | Growth | Recommendation |
|---|---|---|---|
| `GET /api/service-desk/tickets` | national_admin, national_viewer, system_admin | every ticket ever | **Done (C8, 2026-10-10):** always paged (`limit` default 100, max 200; `offset`; newest first, id tie-break), `X-Total-Count`, server-side status/category/unit filters, `/tickets/summary` for true counts and the unit list; Main TMS "Load more" de-duplicates by id. `test_service_desk_paging.py`, `e2e-connected/service-desk-paging.spec.ts`. |
| `GET /api/accounts` | national roles, system_admin, auditor | all staff accounts nationally (low thousands) | **Kept as a full scoped list by default (C8, 2026-10-11)**: the Main TMS Accounts page filters and batch-edits it in memory. Added: opt-in `limit` (max 500)/`offset` on a stable order (display name, id), `X-Total-Count` always, repeatable `role`. The Service Desk now asks only for active admin assignees instead of every account. Constant query count proven at 1,000 accounts (`test_accounts_paging.py`). Server-side search + a paged Accounts table remain the step when the national list passes ~2,000. |
| `GET /api/curriculum` (national admin, no squadron) | national admin | national + every Wing's items | acceptable (hundreds); revisit if Wing curricula grow large. |

Pagination is introduced only where the consuming UI can page; making a
full-list endpoint return a partial list without UI support would be a
behaviour change disguised as optimisation.
