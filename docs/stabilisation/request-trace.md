# How a request flows: one traced end to end

Written 2026-10-12 after the clean-clone walkthrough (C13) found no document that
maps a screen to its code. References are to functions and files, not line
numbers, so they survive edits; `rg` finds each in seconds.

## The layers

```
Main TMS (connected-frontend/js/*.js)  or  Planning Workspace (frontend/src)
        │  fetch via api() / api client, Authorization: Bearer <token>
        ▼
FastAPI middleware (backend/app/main.py): request size, maintenance gate,
        per-IP rate limit, access log, security headers, concurrency cap, CORS
        ▼
Router endpoint (backend/app/routers/<area>.py)
        │  Depends(get_principal)  → backend/app/dependencies.py
        │     token → User → Principal (role, Wing, Squadron, proxy/intervention);
        │     token_version check; per-account rate limit; must_change_code gate;
        │     cookie-only writes need a TMS Origin (D13)
        │  permission / scope helper → backend/app/permissions.py
        ▼
Domain services (backend/app/services*.py) where extracted; otherwise the router
        ▼
SQLAlchemy models (backend/app/models/) → PostgreSQL (SQLite locally/tests)
```

Rules that hold everywhere: the backend decides every permission (frontend role
checks are presentation only); scope comes from `permissions.py` (view-scope
helpers, named predicates), never from an inline comparison in a router
(`tools/architecture/guard.py` ratchets this).

## Traced: a Squadron Admin opens Parade Nights

1. **Screen → JS.** `nav('parade-nights')` reloads data through
   `loadData()` in `connected-frontend/js/data.js`, which calls
   `_apiT('/api/parade-nights' + squadronQuery)`. `_apiT` wraps `api()` in
   `connected-frontend/js/api.js`, which adds the Bearer token from
   `sessionStorage`, the API base from `<meta name="aafc-api-base">`, and
   maps errors (maintenance banner, 401 → sign-in).
2. **Middleware.** The request passes the maintenance gate (reads are allowed
   unless `maintenance_block_reads`) and the per-IP limiter
   (`security.check_api_rate_db` in staging/production: one atomic UPDATE, D14).
3. **Endpoint.** `list_parades` in `backend/app/routers/training.py`
   (`@router.get("/parade-nights")`).
4. **Who is asking.** `get_principal` in `backend/app/dependencies.py` decodes
   the JWT, loads the `User`, checks `token_version` (revoked sessions → 401),
   applies the per-account limit and builds a `Principal`.
5. **Which Squadron.** `_active_squadron(p)` in `training.py` picks the caller's
   Squadron (the proxied one during Proxy Mode / Delegated Intervention);
   `permissions.require_can_view_squadron` → `Principal.can_view_squadron`
   refuses another Wing's Squadron with 403.
6. **Data.** The router queries `ParadeNight` (`backend/app/models/training.py`)
   with its `Session` and `SessionAudience` rows directly; serialisation helpers
   live in `backend/app/services_training_serialisers.py` (C5).
7. **Back in the browser.** `data.js` stores the list in `S`, and
   `renderPN()` in `connected-frontend/js/parade-nights.js` renders it; every
   interpolated value goes through `esc()` (HTML) or `jsq()` (inline-handler
   JavaScript, D11).

## Tracing any other request

1. In the browser's network panel (or `rg "'/api/<path>" connected-frontend/js frontend/src`)
   find the call site.
2. `rg '@router\.(get|post|put|patch|delete)\("/<path>' backend/app/routers` finds
   the endpoint (routers are mounted under `/api` in `main.py`).
3. In the endpoint, read the `Depends(...)` and the first `require_*` /
   `may_*` / `*_outside_*` call: that is the authorisation decision, defined in
   `permissions.py`. `docs/stabilisation/role-check-classification.md` explains
   the few role checks that remain in routers and why.
4. Follow imports into `services_*.py` for the domain logic, then the models.
5. Tests: `rg '<path>' backend/tests frontend/e2e-connected frontend/e2e`.
