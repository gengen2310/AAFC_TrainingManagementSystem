# Architecture Rules — AAFC TMS

## Two frontends, by design — not a migration in progress

- `connected-frontend/` (`aafc-tms-frontend` service) is the TMS root frontend: a single-file
  HTML/CSS/JS SPA, no build step, served by its own Dockerfile/nginx. This is what beta users land
  on.
- `frontend/` (`aafc-tms-planning-workspace-preview` service) is a React/Vite app, mounted at
  `/planning`, deployed separately.
- Both call the same FastAPI backend and read its base URL from a `<meta name="aafc-api-base">` tag
  rewritten at container start by each service's own `docker-entrypoint.sh` from `AAFC_API_BASE`.

This split is intentional, not a half-finished consolidation. Do not:
- Deploy the React app as a replacement for `connected-frontend/`.
- Merge the two into a single build/bundle/repo output.
- Point `aafc-tms-frontend` at the Vite build output, or vice versa.
- Treat one as "legacy to be deleted" in a task unless the user explicitly asks for that migration.

If a task seems to call for unifying them (shared components, a common design system, one deploy
pipeline), that is a large, explicit architectural decision — surface it to the user rather than
doing it as a side effect of an unrelated change.

## Session/auth mechanism across the two frontends

- Both frontends use `sessionStorage` + `Authorization: Bearer <token>` as the *primary* session
  mechanism (same-origin, fast, no cross-site cookie policy involved).
- The `aafc_session` cookie (`SameSite=None; Secure`) is the *fallback*, used only when there is no
  `sessionStorage` token to send — e.g. a fresh tab opened cross-origin, such as clicking "Open
  Planning Workspace" from the legacy TMS nav. `SameSite=None` is load-bearing for this handoff, not
  an accidental misconfiguration — do not "tighten" it to `Lax`/`Strict` without re-verifying this
  flow end-to-end in a real browser.
- A script or test that logs in via a direct API call (bypassing each frontend's own login handler)
  will not populate `sessionStorage`, and will therefore appear "logged out" on reload even with a
  valid cookie. That is expected test-harness behaviour, not a product defect — don't misdiagnose it
  as one.

## Tenancy vs. sub-squadron grouping

- Tenancy hierarchy is **National → Wing → Squadron** only.
- "Flight" (`Flight` model, `flight_id` on `User`/`Cadet`) is a sub-squadron grouping for cadet
  organisation — it is not a tenancy level. Do not create Flight-scoped permission/tenancy checks.

## Permission/scope helper selection

`backend/app/permissions.py` has two families of scope check used in different routers:
- `require_can_view_squadron` / `require_can_write_squadron` — tenancy-aware, proxy/delegated-
  intervention-aware. Use these whenever a `wing_admin` or similar role might legitimately act
  through a proxy/delegation mechanism.
- `_require_year_access` (in `planning.py`) — simpler, no proxy awareness. Only appropriate where
  the endpoint has no proxy/delegation concept.

Do not swap one for the other without checking which behaviour the endpoint actually needs — using
the simpler check where proxy access is required is a real regression (it silently blocks legitimate
delegated access), and using the proxy-aware check everywhere adds unnecessary complexity where no
proxy concept exists.
