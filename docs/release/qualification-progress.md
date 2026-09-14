# Release qualification progress

Branch: `fix/post-pr60-release-qualification`
Base main: `4538200b6a54aa63579577593c13dcef7f159019`
Current working HEAD: `b0532524287d763a9588943c3f1600d3359bfa67`
Status: **NO-GO**

## Gates

- Backend full pytest: PASS on prior branch head — 2446 passed, 12 skipped; current-head recheck pending.
- PostgreSQL migration rehearsal / PW TypeScript / PW build / release static checks: PASS on prior branch head; current-head recheck pending.
- Dependency audit: PASS at `9cdaaa0`.
- Planning Workspace E2E: Chromium PASS, Firefox PASS, WebKit PASS on prior branch head; current-head recheck pending.
- Main TMS / Connected Frontend E2E: FAIL on `9dd1777` — Chromium 157/174, Firefox 157/174, WebKit 157/174. Current-head rerun pending.
- Production-backup restore qualification: latest inspected run `34783195460` FAIL — backup restores/integrity passes, but backup Alembic revision `a4e9507a9c51` is behind repo head `7f61608fa538` and `session_audiences` is absent. No production mutation authorised.

## Root-cause clusters

- TEST-ISOLATION — repeated Connected-Frontend UI logins exhaust the development/test auth limiter because several specs reset only once per file. `accessibility-hardening.spec.ts` now resets before each test; remaining login-heavy specs still under review.
- TEST — PW handoff assertions assumed an independent PW navigation/login shell. Corrected to module-only contract and shared server-side tenant/session checks.
- TEST — status-reason “Add new” still used native-dialog handling after HARD-09 replaced `prompt()` with accessible `promptText()`. Corrected to exercise `#m-text-input`.
- PRODUCT/under investigation — inherited Activity override modal does not close after Clear.
- PRODUCT/under investigation — facilitator duplicate/add/archive/stat-refresh workflows.
- TEST or PRODUCT/under investigation — hidden archived-Flight control, readiness fixture, Reference Data reload, CSV export, Training-Class/session detail and Weekly Program class rendering.
- PRODUCT — Chromium release-width test reports 390 px document overflow (`411 > 390`).

## Fixes completed in this pass

- Aligned cross-origin session-handoff E2E with the documented module-only Planning Workspace architecture while preserving same-session/same-tenant verification.
- Updated governed session-status reason creation E2E to the accessible prompt modal.
- Isolated accessibility-hardening logins from shared development/test rate-limit state without changing production limits.

## Next action

Inspect current-head CI as it completes; apply the same deterministic rate-limit isolation where current logs prove accumulation, then fix remaining root causes by cluster. Preserve all currently green backend/PW/migration/security gates. Do not merge or deploy.
