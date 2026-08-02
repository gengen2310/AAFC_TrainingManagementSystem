# Section 10 — Immediate Production Smoke Test

## Public service state — all verified live, clean

| Check | Result |
|---|---|
| Backend health (`/api/health/ready`) | `{"status":"ready","squadrons":1}` |
| Backend readiness / environment (`/api/health/ui-config`) | `environment: "production"`, `planning_workspace_url` correctly points at production |
| Main TMS HTTP status | 200 |
| Planning Workspace HTTP status | 200 |
| Build fingerprints (all 3 services) | `d4f00cb083ece0c846fc2d4e2666c287d1dfc399` — confirmed live via `app-build` meta tag on both frontends |
| Migration head | `z1a2b3c4d5e6` — unchanged, confirmed via direct read-only query post-deploy (no migration in this release) |
| Production API domains | Both frontends' `aafc-api-base` correctly resolves to `https://aafc-tms-backend-production.up.railway.app` — no localhost/staging/placeholder |
| Console errors (both frontends) | None |
| Network requests (both frontends) | Main TMS: 4 requests, all legitimate (self + Google Fonts). Planning Workspace: 8 requests, all legitimate (self, fonts, and one `GET /api/auth/me` correctly hitting the **production** backend, correctly returning `401` pre-authentication) |
| Cross-environment requests | None found on either frontend |

## Authenticated state — blocked, same credential gap as Section 6

No production login credentials were available in this session to exercise
the authenticated checklist (System Administrator login, National/Wing/
Squadron views, Dashboard, Activities, calendar, Parade Nights, curriculum,
facilitators, Account Management, Scope Map, audit, Proxy Mode entry/exit,
Intervention Mode entry/exit, logout). No authenticated production browser
session was already open in this session.

**This is a narrower gap than it looks**: production's core authenticated
paths were already live-verified earlier in this same session, using a real
production login flow, during the GAP-27 fix (pointed `PLANNING_WORKSPACE_URL`
at the correct production domain and confirmed the fix live). That
verification predates this specific release's two changes (the
color-contrast CSS fix and the `docker-entrypoint.sh` hardening), neither of
which touches authentication, routing, or API logic — so the risk this gap
represents is low, but it is disclosed as open rather than silently assumed
covered by the earlier session's evidence.

**Disposition**: open, P2, consistent with the Section 6 disclosure.
Recommended follow-up: a human operator (or a future session with valid
credentials) should complete the authenticated checklist above against
production, focusing specifically on Account Management (where the
color-contrast fix changes rendered colors) and general navigation (to
confirm the Planning Workspace link and Delegated Intervention entry still
work end-to-end).

## No write test performed

Per Section 10's own instruction, any write test must use a clearly marked
temporary record cleaned up via the authorised archive process. Since no
authenticated session was available, no write test was attempted — nothing
to clean up, no risk taken.
