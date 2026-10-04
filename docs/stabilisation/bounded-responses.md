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
| `GET /api/service-desk/tickets` | national_admin, national_viewer, system_admin | **every ticket ever** — grows forever | add `limit`/`offset` (or `before` cursor) + status/date filters, and a "load more" in the Main TMS Service Desk page. A silent default limit would hide old tickets, so it needs the UI change. |
| `GET /api/accounts` | national roles, system_admin, auditor | all staff accounts nationally (low thousands) | acceptable at current scale; add server-side search/paging when the national account list exceeds ~2,000. |
| `GET /api/curriculum` (national admin, no squadron) | national admin | national + every Wing's items | acceptable (hundreds); revisit if Wing curricula grow large. |

Pagination is introduced only where the consuming UI can page; making a
full-list endpoint return a partial list without UI support would be a
behaviour change disguised as optimisation.
