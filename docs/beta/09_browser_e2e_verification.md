# Browser-Level E2E Verification (Workstream 9) — Staging

Real Chromium via Playwright against `https://*-staging.up.railway.app`, not just unit tests or
curl. Evidence screenshot: `docs/beta/evidence/planning-workspace-staging-handoff-2026-07-14.png`.

## Session handoff: legacy TMS → Planning Workspace — PASSED

**Test**: established a real logged-in browser session (squadron 703 admin), then opened the
Planning Workspace staging URL in a **new tab in the same browser context** — simulating a user
clicking "Open Planning Workspace" from the legacy TMS nav, which opens it as a separate tab/origin.

**Result**: the Planning Workspace picked up the session automatically with **no login form shown**
and **zero console/page errors**. Rendered real, substantive content: correct squadron/role banner
("703 SQN · Sqn Admin · 703 Admin"), Year view with real scheduled curriculum items (New Cadet
Welcome, Junior Drill and Ceremonial), real facilitator names, parade-night cards, term dates,
filters, and the warning legend. See the evidence screenshot.

**Mechanism confirmed**: this works because of the architecture traced for DEFECT-004 — in module
mode (`MODULE_MODE=true`, no login form), the React app's `AuthProvider` calls `/api/auth/me` with
`credentials: 'include'`; since a fresh tab has no `sessionStorage` token to send as a Bearer
header, the request relies purely on the `aafc_session` cookie (`SameSite=None; Secure`), which the
browser correctly attaches on this cross-origin (different Railway subdomain) request. This is a
second, independent, real-world confirmation that `SameSite=None` is load-bearing — not just for
the legacy frontend's own API calls, but for this exact handoff flow.

## Testing-methodology note (not a product defect)

An earlier pass through this test logged in via a scripted direct `fetch()` to `/api/auth/login`
(bypassing the legacy frontend's own UI) and found that reloading the legacy TMS page afterward
still showed the login form. **This was a test artifact, not a bug**: traced the legacy frontend's
actual login handler (`connected-frontend/index.html`, `doLogin()`) and found it calls
`tokenSet(out.token)` — storing the JWT in `sessionStorage` — immediately after a successful login,
and every subsequent API call attaches it as `Authorization: Bearer <token>` (`tokenGet()`,
line ~2742). My scripted `fetch()` login never called `tokenSet()`, so `sessionStorage` stayed
empty and the page correctly treated the tab as logged out on reload — exactly as it would for any
real user who somehow got a valid cookie without going through the login form. A real user going
through the actual UI would have `sessionStorage` populated and reload correctly.

**Architecture takeaway, confirmed empirically**: both frontends use `sessionStorage` + Bearer token
as their *primary*, same-origin session-persistence mechanism (fast, reliable, no cross-site cookie
policy involved). The `aafc_session` cookie exists specifically as the *fallback* for the one
scenario where there's no `sessionStorage` to inherit — a fresh tab/origin, i.e. exactly the
Planning Workspace handoff case tested above. This is a deliberate, sensible design, not an
inconsistency.

## Not yet covered by this session (scope for a follow-up pass)

The full Workstream 9 matrix (all personas, all views at multiple zoom levels/resolutions,
accessibility, slow-network simulation, every known regression target from the original brief) was
not exhaustively run — this session covered the highest-value, previously-unverified item (real
cross-origin session handoff, the thing most likely to be silently broken by a `SameSite` change or
CORS misconfiguration) with genuine browser evidence rather than assuming it works. Recommend before
final GO/NO-GO: Term/8-week/2-week/Custom-range views specifically (the original brief's named
regression targets — blank screen, infinite loading, Custom Range 422), logout propagation across
both origins, and a pass at 125%/150% browser zoom.

## Gate 6 re-run — full `playwright.connected.staging.config.ts` suite, 2026-08-05

Full connected-frontend e2e suite run against live staging (`aafc-tms-frontend-staging`,
`aafc-tms-backend-staging`), real Chromium, not localhost.

**Result: 35 passed, 10 failed.**

### The 10 failures — all one known, disclosed limitation, not new defects

Every failing test calls a login helper with the hardcoded code `SYSADMIN2026`
(`training-dashboard.spec.ts` ×8, `activities-inheritance.spec.ts` ×1, `hostile-value-xss.spec.ts`
×1). Confirmed directly via `curl -X POST .../api/auth/login -d '{"code":"SYSADMIN2026"}'` against
staging: `401 {"detail":{"error":"invalid_code"}}`. Staging's actual system_admin bootstrap code is
generated from the `STAGING_BOOTSTRAP_SYSADMIN_CODE` env var at deploy time and was never disclosed
to this session — correctly so, per this project's own security discipline (`.claude/rules/security.md`:
never retrieve existing access codes). Counted the total `SYSADMIN2026`-dependent tests in the suite
(`grep -c SYSADMIN2026 e2e-connected/*.spec.ts`) — exactly 10, an exact match to the 10 failures. No
unexplained failure exists in this run.

**Disclosed limitation, not closed**: this session cannot exercise system_admin-only flows against
staging (National Training Dashboard, System Administrator scope-drill, hostile-value XSS check
under system_admin, National-scope activity inheritance) without a human supplying the real staging
bootstrap code out-of-band. This is Gate 10 (human-gated items) territory, not a Gate 6 defect.

### A real P0 defect found and fixed during this pass (see REM-77)

One of the failures investigated in this run — `activities-inheritance.spec.ts`'s companion
`main-tms.spec.ts` "Reference Data / Training Stage" test — led to discovering that
`GET /api/curriculum/phases` and `GET /api/facilitator-type-tags` were 500ing on **any** real
Postgres environment (both staging and production) with `psycopg2.errors.UndefinedColumn:
...updated_by does not exist`. Root-caused to migrations v42/v45 both omitting a `TimestampMixin`
column (the same defect class v24 and v40 already patched twice before). Fixed via migration
`5a195a98148a` (v47), given a permanent AST-based regression test
(`backend/tests/test_migration_schema_drift.py`), deployed to staging then production, verified via
direct curl against both live URLs (200 with real data, previously 500), and merged to `main`. Full
detail: `docs/remediation/master_gap_register.csv` REM-77.

Two unrelated bugs in this session's own test code were found and fixed in the same investigation
(not product defects): `main-tms.spec.ts`'s "bulk-mark remaining sessions delivered" test had a
`localhost:8000` fallback that ignored `E2E_BACKEND_BASE_URL` when set, and a hardcoded date that
collided with a leftover record from an earlier manual run against staging's persistent (never
reseeded) database. Both fixed; the test now passes cleanly against live staging.

### Planning Workspace suites

**`playwright.planning.staging.config.ts` run against live staging: 5 passed, 40 failed.** Investigated
before accepting this number: every failure is a `loginWing`/`loginNational`/legacy-DOM-selector
timeout (`#auth-type`, `#auth-code`, `nav()`) — this config points the `e2e-connected` test
directory (written against connected-frontend's plain-HTML login form and `nav()` routing) at the
**Planning Workspace's** baseURL, a completely different React SPA with no such DOM. The config
file's own header comment confirms this was built for a narrower purpose (screenshot evidence
capture matching the deployed module-mode build), not as a full-suite runner — running the entire
`e2e-connected` directory against it was this session's own scoping mismatch, not a Planning
Workspace defect. The 5 passes are almost certainly the handful of tests with no legacy-DOM
dependency. **Not counted as Gate 6 evidence either way** (neither a pass nor a fail signal for
Planning Workspace itself) — re-run only `capture-screenshots.spec.ts` against this config for its
intended purpose, or run Planning Workspace's own `frontend/e2e/` suite instead, before treating
Planning Workspace as separately verified.

`playwright.staging.config.ts` (Planning Workspace's own 95-test `e2e/` suite via local Vite dev
server proxied to staging backend, historically CORS-blocked for most tests) was not run this pass —
recommend running before final GO/NO-GO consolidation (Gate 11), or accepting this as a disclosed
gap in Gate 6 coverage.

### Staging data hygiene — observation, not a defect, RESOLVED before Gate 7

`GET /api/health/ready` on staging reported `squadrons: 139–140`, not the ~16 real seeded squadrons.
Investigated via `/api/squadrons` (national_admin token): 16 real squadrons (701–723 series) plus
123 `Test Sqn ...`-named records, accumulated from e2e test runs across this multi-day session —
staging is deliberately never reseeded between runs (see `main-tms.spec.ts` fix comment, this same
gate), so test-created entities persist indefinitely. Not a code defect.

**User approved cleanup 2026-08-05.** Archiving the 123 squadrons required first archiving 1,208
accounts tied to them (of 1,246 total on staging) — the squadron-archive endpoint correctly blocks
on active accounts (`.claude/rules/capability-preservation.md` §4's data-safety guard working as
designed). Both operations used only existing, real, audited API endpoints — no direct DB writes:
`POST /api/accounts/batch-archive` (9 chunks of ≤150, reason recorded, `confirm_session_revocation`
required) → 1,208/1,208 archived, 0 failures; then `POST /api/squadrons/{id}/archive` per squadron →
123/123 archived, 0 failures, 0 remaining blockers. Both are reversible via their `/restore`
counterparts and fully audit-logged (`account_archived` / `squadron` archive actions, all
attributable to the acting `national_admin` principal). Verified after: `GET /api/squadrons` (via
API, not the raw table-count health endpoint) shows exactly 16 active squadrons, `GET /api/users`
shows exactly 38 active users — matching the original synthetic seed. `ADMIN703` login and session
still work correctly (real squadron/account untouched). Staging is now a clean baseline for Gate 7's
load test.
