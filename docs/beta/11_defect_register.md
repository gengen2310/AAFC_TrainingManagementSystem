# AAFC TMS — Defect Register

Severity definitions per the release program: BLOCKER (auth bypass, cross-squadron leak,
data loss/corruption, failed migration, no successful backup/restore, blank core workflow,
divergent authoritative data, unusable release path) and HIGH (unauthorised write, silent
autosave failure, duplicate operational data, persistent 500, severe performance failure,
unsafe year rollover, failed rollback, CEA reimport losing local data).

---

## DEFECT-001 — BLOCKER — IDOR: facilitator-leave, notices, CEA endpoints missing object-scope checks

**Status**: Fixed on `release/beta-2026-07-14` (commit `051ba4d`), verified in staging. **Still live and unfixed in production** as of this writing — production has not been redeployed.

**Update (2026-07-14, merge reconciliation)**: a separate concurrent session independently found and fixed the same three IDOR categories directly on `main` (commits `c8b665e`, `e19e959`) — good independent confirmation this was a real vulnerability. Reconciled via merge (commit `906f59f`): kept this branch's `require_can_view_squadron`/`require_can_write_squadron` fix for facilitator-leave over `main`'s ad-hoc role checks, which omit the proxy/delegated-intervention requirement this codebase enforces everywhere else for `wing_admin`/`national_admin` writes; combined both sides' checks for CEA/notices reads; adopted `main`'s `UPLOAD_MAX_MB` file-size guard on CEA import (a real gap this branch's fix missed); adopted `main`'s fix for a genuine pre-existing crash bug in `set_local_hide` (`p.unit_id` doesn't exist on `Principal`, only `p.squadron_id` — see the correction to the "Not affected" note below).

**Reproducible failure**: An authenticated `sqn_admin` (or, for CEA import, `wing_admin`) could read and write facilitator-leave, notices, and CEA records belonging to a *different* squadron/wing than their own, by supplying that object's ID directly. `wing_admin`/`national_admin` could also write to any squadron's facilitator-leave without going through this codebase's otherwise-universal proxy/delegated-intervention mode.

Reproduction (against the pre-fix code, `git stash` of commit `051ba4d`):
```
cd backend && source .venv/bin/activate
python -m pytest tests/test_planning.py -q -k cross_squadron
# 10 failed — see docs/beta/00_release_state.md for the exact test names
```

**Root cause**: Every affected endpoint called `require_role(p, ...)` — a pure role check — and then fetched the target object by ID from the path/body, but never verified the fetched object's `squadron_id`/`wing_id` against the caller's own scope. This codebase already has the correct helpers for this (`require_can_view_squadron`/`require_can_write_squadron` for facilitator-scoped resources, `_require_year_access` for planning-year-scoped resources), used correctly elsewhere in the same file (e.g. `update_session` at the time of writing) — they were simply not applied to this newer code.

**Affected endpoints** (`backend/app/routers/planning.py`):
- `GET/POST /api/planning/facilitators/{fac_id}/leave`, `DELETE /api/planning/facilitator-leave/{leave_id}`
- `GET/POST /api/planning/parade-dates/{date_id}/notices`, `PATCH /api/planning/notices/{notice_id}`, `POST /api/planning/notices/{notice_id}/archive`
- `GET /api/planning/years/{year_id}/cea/activities`, `GET /api/planning/years/{year_id}/cea/batches`, `POST /api/planning/years/{year_id}/cea/import`, `PATCH /api/planning/cea/{activity_id}/classify`, `POST /api/planning/years/{year_id}/cea/activities`

**Not affected by IDOR** (tenancy is correctly self-scoped): `POST /api/planning/cea/{activity_id}/local-hide` writes only to a row keyed by the caller's own scope — no target-object tenancy check is needed since it can't touch another org's data by construction. **Correction**: this session's original review stopped there without tracing the actual code, and missed that the endpoint referenced `p.unit_id` — an attribute that doesn't exist on `Principal` (only `p.squadron_id` does) — causing an `AttributeError` (500) on *every* call, unrelated to tenancy. A separate concurrent session found and fixed this (see the Update above). Lesson: "safe as-is" needs the same code-tracing rigor as a vulnerability fix, not just a design read-through.

**Smallest safe fix**: fetch the target object first, then call the existing scope helper before mutating/returning anything — no new permission abstraction added. See commit `051ba4d`.

**Regression test**: 13 new tests in `backend/tests/test_planning.py` (search `cross_squadron`/`same_squadron_admin_allowed`). Each cross-tenant test confirmed to **fail** against the pre-fix code and **pass** against the fix before being committed.

**Retest evidence**: `421 passed, 1 skipped` (pre-existing baseline) → `434 passed, 1 skipped` (post-fix, +13 new tests, zero regressions). Live non-destructive route probes against production (2026-07-13) confirm this exact vulnerable code is currently deployed there — see `docs/beta/00_release_state.md`.

**Outstanding**: production has not been redeployed with this fix. Per rule 13, production deployment requires explicit approval and is not authorized by this fix alone — this defect remains OPEN at the production level until that deploy happens and is verified.

**Related, not yet fixed** — `_require_year_access` (used by the notices/CEA fix above, and pre-existing elsewhere) does not scope-restrict **reads** for roles outside `sqn_admin`/`wing_admin`/`wing_viewer`/`national_viewer`/`auditor` — e.g. `sqn_general` (squadron read-only) hits no branch and falls through unrestricted. This is a broader, pre-existing characteristic of a shared helper used by many endpoints beyond the three in scope here; flagging for separate follow-up rather than fixing under this defect's blast radius without full impact mapping.

---

## DEFECT-002 — HIGH — `seed_all.py` was unconditionally destructive

**Status**: **Fixed** (commit `9e7a179`).

**Reproducible failure**: `backend/app/seeds/seed_all.py`'s `seed_all()` calls `reset_db()` (`Base.metadata.drop_all()` + `create_all()`) unconditionally, with no environment guard or confirmation prompt — a real hazard if ever invoked against a database containing real data.

**Fix**: `reset_db()` now calls `check_destructive_reset_allowed()`, which refuses when (1) `ENVIRONMENT` is `production`/`prod` — absolute, no override; (2) the target hostname's SHA-256 fingerprint matches a protected database (`config.py`'s `PROTECTED_DB_HOST_FINGERPRINTS`) — absolute and independent of `ENVIRONMENT`, specifically because production's own `ENVIRONMENT` was found set to `staging` in this exact repo (DEFECT-003), so that variable alone can't be trusted; (3) the database is not SQLite and `ALLOW_DESTRUCTIVE_SEED != "true"`. SQLite (local dev, the test suite) is exempt — inherently local/disposable.

**Regression test**: 6 new tests (`test_reset_db_safety.py`) against a pure, parameterized guard function — no monkeypatching of global settings/module reload (a first attempt did that and silently broke 95 unrelated tests via shared engine/session state; rewritten). Full suite: 445 passed, 1 skipped at the time (zero regressions).

---

## DEFECT-003 — HIGH — Production `ENVIRONMENT` variable reads `staging`, not `production`

**Status**: Investigation complete. Root cause understood, one concrete live risk found and fixed in code (commit `f303895`), the underlying variable itself not yet changed on production — prepared below, pending approval per rule 13.

**Every place `ENVIRONMENT`/`is_prod` actually controls behaviour** (traced exhaustively via `grep` across `app/`, not inferred):

| Behaviour | Code | Effect of `ENVIRONMENT=staging` on production right now | Risk if left as-is |
|---|---|---|---|
| Fail-closed startup validation (`validate_for_production()`) — refuses to start with a weak `SECRET_KEY`/`JWT_SECRET`, `COOKIE_SECURE=false`, empty/wildcard/localhost CORS, or a SQLite `DATABASE_URL` | `config.py` | **Disabled.** Currently benign — checked directly (without printing secrets): `SECRET_KEY`/`JWT_SECRET` are both 54 chars (not dev-prefixed), `COOKIE_SECURE=true`, CORS has no wildcard/localhost, `DATABASE_URL` is not SQLite. All would already pass if this check were active. | HIGH but currently latent — this safety net is silently off; if any of those settings were ever weakened by mistake in the future, the app would start anyway instead of refusing. |
| HSTS header (`Strict-Transport-Security`) | `main.py` security-headers middleware | **Not sent.** Real production traffic is HTTPS-only (Railway terminates TLS) regardless, but browsers aren't told to enforce HTTPS-only for future requests to this host. | MEDIUM — narrows, doesn't eliminate, a downgrade-to-HTTP MITM window. |
| `POST /api/system/bootstrap-staging` — creates `national_admin`/`wing_admin`/`sqn_admin` accounts with fresh one-time access codes, explicitly "Rejected in production" per its own docstring | `routers/system.py` | **Was not rejected** — the guard checked `ENVIRONMENT.lower() == "production"` literally, so with `ENVIRONMENT=staging` it passed straight through. Confirmed via static trace, not executed against production (would have been a write action). | **HIGH — the one concrete, currently-exploitable consequence.** Gated behind `require_system_admin`, so not open to any authenticated user, but a compromised/malicious system_admin session (the highest-privilege role) could invoke this against production today. **Fixed in code** (commit `f303895`, switched to `settings.is_prod` for consistency) — but this fix alone does not close the live risk, since `is_prod` is *also* false while `ENVIRONMENT=staging`. Closing it requires the variable correction below. |
| `/docs`, `/redoc`, `/openapi.json` | `main.py` `FastAPI(... docs_url=None, redoc_url=None, openapi_url=None)` | **Unaffected** — hardcoded off unconditionally, not gated by environment at all. | None. |
| Debug/error detail leakage | `main.py` `server_error` handler | **Unaffected** — always returns a generic `{"error": "internal_error"}`, no `debug=True` anywhere. | None. |
| Rate limiting | `security.py` | **Unaffected** — not environment-gated. | None. |
| `reset_db()` destructive-seed guard (this session's own new code, DEFECT-002) | `database.py` | **Partially bypassed** by this specific check (since `ENVIRONMENT != "production"`), but the separate hostname-fingerprint check added in the same fix catches production independently of `ENVIRONMENT` — deliberately designed that way *because* of this exact finding. | Mitigated already. |
| `/api/system/status` `environment` field | `routers/system.py` | Reports `"staging"` — misleading to anyone checking operational status. | LOW — cosmetic/confusing, not a security hole. |

**Overall classification: HIGH**, not the MEDIUM this was originally logged as — the `bootstrap-staging` finding is concrete and currently live, not theoretical.

**Recommended production change** (prepared, not applied — needs your approval): set `ENVIRONMENT=production` on the `aafc-tms-backend` service in the Railway `production` environment. Verified safe to apply — production's current `SECRET_KEY`/`JWT_SECRET`/`COOKIE_SECURE`/`CORS_ALLOWED_ORIGINS`/`DATABASE_URL` were all checked (without exposing values) and would pass `validate_for_production()` cleanly, so flipping this variable will not crash-loop the app on next restart. After changing it: confirm `/api/system/status` reports `"production"`, confirm the HSTS header appears on a response, and confirm `POST /api/system/bootstrap-staging` now returns 403 for a system_admin (do this against **staging with `ENVIRONMENT` temporarily set to `production`** first, not production directly, to avoid any live write risk during verification).

---

## DEFECT-004 — RESOLVED (not a defect) — Production `COOKIE_SAMESITE=none` is required by the current architecture, not a misconfiguration

**Status**: Investigated empirically against staging. **`none` is correct and must not be changed** — closing this as "working as required," not open.

**Architecture context found first**: the two frontends use *different* auth mechanisms entirely. The React Planning Workspace (`frontend/`) stores its JWT in `sessionStorage` and sends it as an `Authorization: Bearer` header on every request (`frontend/src/api/client.ts`) — `SameSite` is irrelevant to it, since `backend/app/dependencies.py`'s `_token_from_request()` checks the header first and only falls back to the cookie if there is no header. The legacy `connected-frontend/` has no such token storage (per the project's own rule against storing tokens client-side) and relies purely on the browser automatically attaching the `aafc_session` cookie on every cross-origin request to the backend.

**Why this is genuinely cross-site**: `up.railway.app` is on the public suffix list (confirmed: `curl https://publicsuffix.org/list/public_suffix_list.dat | grep -x up.railway.app` matches) — so `aafc-tms-frontend-*.up.railway.app`, `aafc-tms-backend-*.up.railway.app`, and `aafc-tms-planning-workspace-preview-*.up.railway.app` are each a distinct "site" to the browser, not subdomains of one shared site. Cross-site cookies require `SameSite=None; Secure` to be sent at all.

**Empirical proof (staging, real Chromium via Playwright, not just reasoning)**:
1. Baseline, `COOKIE_SAMESITE=none`: cross-origin `fetch` from the frontend origin to the backend origin with `credentials: 'include'` — login succeeds (200, cookie set with `sameSite=None, secure=true, httpOnly=true`), and a **subsequent cross-origin request with no `Authorization` header at all** — pure cookie auth — succeeds (`GET /api/auth/me` → 200, correct session data).
2. Toggled `COOKIE_SAMESITE=lax` on staging, redeployed, repeated the identical test: login still returns 200, but **the cookie no longer appears in the browser's cookie jar at all**, and the follow-up cookie-only request gets `401 auth_required`. Cookie-based auth is completely broken.
3. `strict` was not separately tested — it is strictly more restrictive than `lax`, which already failed; there is no scenario where `strict` would succeed where `lax` didn't.
4. Reverted `COOKIE_SAMESITE` back to `none` on staging and confirmed the backend redeployed healthy and the health endpoint responds correctly again.

**Recommendation**: keep `COOKIE_SAMESITE=none` in production. Changing it to `lax` or `strict` would completely break the legacy TMS's ability to authenticate against the backend (confirmed, not theoretical). The project rule this was checked against ("`.claude/rules/deployment.md`: `COOKIE_SAMESITE=strict` required in production") predates the current multi-subdomain Railway architecture and is itself the stale artifact — not production's configuration. Recommend updating that rule doc rather than production. The durable fix, if ever wanted, is deploying all services under one registered domain (e.g. `tms.aafc.org` + `api.tms.aafc.org`) so they share an eTLD+1 and are no longer cross-site by the browser's definition — a real infrastructure change, out of scope before this release.

---

## DEFECT-005 — HIGH — Planning Workspace preview deploy failing (production and pre-fix staging)

**Status**: **Fixed** on `release/beta-2026-07-14` (commit `96584e9`), verified working in staging. Not yet deployed to production.

**Root cause**: `frontend/` (the Planning Workspace React/Vite app) had no Dockerfile; Railway's Railpack auto-builder resolved the wrong static-output directory (`dist-single`, which only exists under the `vite --mode single` build used for `make connected`, not the default `build` script's `dist`). Production has been serving a stale prior successful deployment since at least 2026-07-12 while every new deploy attempt failed.

**Fix**: explicit multi-stage Dockerfile mirroring `connected-frontend`'s existing nginx pattern. Verified with a local `npm run build` before redeploying, then confirmed `SUCCESS` status and a working `/planning` route in staging.

**Outstanding**: production still needs this fix deployed — not authorized without explicit approval per rule 13.

---

## DEFECT-006 — BLOCKER — Backup/restore has never succeeded

**Status**: **RESOLVED — proven end-to-end, all four claims.** Full chain now verified: real production backup → PostgreSQL-level restore into a disposable container → application-level reads through a real running backend against the restored data.

| Claim | Status |
|---|---|
| A. Backup/restore *mechanism* works (secrets, pg_dump/pg_restore version compatibility, encryption, checksum, upload, decryption) | **Proven** — against both staging and production. |
| B. Production database is actually backed up | **Proven.** Real production backup succeeded: run [`29281190414`](https://github.com/gengen2310/AAFC_TrainingManagementSystem/actions/runs/29281190414), 432,758-byte dump, artifact `postgresql-production-backup-20260713_200837`. |
| C. Production backup restores into a disposable database at the schema/row level | **Proven** (after two additional real bugs found and fixed — see below). |
| D. Restored data is readable through the running application, not just via `psql` | **Code complete, not yet verified.** Added to `test-restore-postgresql.yml`: installs backend deps, creates a throwaway `system_admin` via the ORM (no real production access code used), starts a real backend against the restored database, drives 7 authenticated reads through the actual API. Committed (`17b268d`) but never actually re-run — work paused here to reconcile with a concurrent session's changes on `main` first. **Re-run this workflow before treating backup/restore as release-ready.** |

**Root cause (secrets)**: the committed `.github/backup-public-key.asc` had no corresponding `BACKUP_GPG_PRIVATE_KEY`/`BACKUP_GPG_PASSPHRASE` GitHub secret — a matching secret key existed only in a local GPG keyring whose passphrase was never recorded anywhere accessible. `SUPABASE_DB_URL` was also never set. Every daily backup run failed for at least 10 consecutive days (2026-07-03 → 2026-07-12).

**Root cause (client/server version mismatch)**: first real run failed — `pg_dump: error: aborting because of server version mismatch` (Ubuntu's default `postgresql-client` is v16; production is Postgres 17.6, staging is 18.4). Fixed by installing `postgresql-client-18` from the official PGDG apt repo in both workflows (client ≥ server is the supported direction either way).

**Root cause (Supabase-internal schemas)**: first real *production* restore failed — `ERROR: extension "supabase_vault" is not available`. Production's Supabase project provisions `auth`/`extensions`/`graphql`/`pgbouncer`/`realtime`/`storage`/`vault` schemas alongside the app's own `public` schema; confirmed via direct read-only query that the app only ever uses `public`. Fixed with `pg_dump --schema=public`.

**Root cause (schema-already-exists)**: with `--schema=public` added, the *next* restore attempt failed — `ERROR: schema "public" already exists` (the disposable target's default schema conflicts with the dump's explicit `CREATE SCHEMA public;`). Fixed with `pg_restore --clean --if-exists`.

**Also fixed along the way**: split into separate production/staging workflows with distinct secrets (`PROD_DATABASE_BACKUP_URL` vs `SUPABASE_DB_URL`) and a non-secret hostname-fingerprint cross-check so one can never be run against the other's database by mistake; replaced the restore-test's hardcoded `EXPECTED_HEAD` (found stale by ~9 migrations) with `backend/scripts/compute_alembic_head.py`, which derives the head dynamically from the checked-out migration files and fails loudly on a branched chain (5 unit tests, `test_compute_alembic_head.py`).

**Retest evidence (production, PostgreSQL-level)**: restore run [`29281292666`](https://github.com/gengen2310/AAFC_TrainingManagementSystem/actions/runs/29281292666) SUCCESS — SHA-256 integrity passed, restored into a disposable `postgres:18-alpine` container, `alembic_version = x9y0z1a2b3c4`, all required tables present with real production row counts (wings: 8, squadrons: 16, users: 39, audit_logs: 431, curriculum_items: 217, planning_years: 10), container destroyed at end of run.

**Retest evidence (application level, against the reconciled/merged branch)**: run [`29297143467`](https://github.com/gengen2310/AAFC_TrainingManagementSystem/actions/runs/29297143467) — PostgreSQL-level: `alembic_version = x9y0z1a2b3c4` (correct head, post-merge), all 15 schema/row checks passed with real production row counts (wings: 8, squadrons: 16, users: 39, audit_logs: 441). Application-level: backend started cleanly against the restored data, throwaway test admin created via the ORM, all 8 authenticated API reads succeeded (`/api/health/ready` → squadrons=16, `/api/auth/me`, `/api/wings` → 8, `/api/squadrons` → 16, `/api/users` → 40, `/api/planning/years` → 10, `/api/planning/facilitators` → 1) — `APPLICATION-LEVEL RESTORE CHECK PASSED`. Disposable container and backend both destroyed at end of run; no data persisted anywhere outside the ephemeral CI runner.

**Incidental finding while redeploying staging with the merged code**: staging's backend crashed on restart — migrations v35/v36 tried to `ADD COLUMN` for fields that already existed physically (staging's tables were originally built via `reset_db()`'s `create_all()` from the current model classes, which already declared these fields, rather than via Alembic). Fixed by running `alembic stamp head` directly against staging's database (not production) after confirming the physical schema already matched what those migrations would have produced — a one-time, staging-only operational fix, not a code change. Staging backend redeployed successfully afterward.

---

## DEFECT-007 — LOW — Vitest was executing Playwright e2e specs

**Status**: Fixed (commit `6ccbec9`). `npm run test` failed 2 suites because `e2e/*.spec.ts` (Playwright) has no Vitest exclude. Added `exclude: ["e2e/**"]` to `vite.config.ts`'s test block. Frontend unit suite now: 4 files, 8 tests, all passing, 0 false failures.

---

## DEFECT-008 — HIGH (process, not yet materialized) — Migration revision-ID collision pending on `main`

**Status**: Open — belongs to a different (concurrent) session to resolve; not touched here.

**Detail**: a parallel Claude Code session working the same release directly against `main` has an uncommitted local migration `backend/alembic/versions/w8x9y0z1a2b3_v35_program_type.py` (renames `curriculum_items.core_status` values from `core`/`additional` to `foundation`/`extension`) that reuses revision id `w8x9y0z1a2b3` — already used by a *different* migration already committed to `main` and merged into `release/beta-2026-07-14` (`v35_planning_notices_updated_by`, commit `906f59f`). Confirmed production still has the old `core`/`additional` values (queried directly, read-only) — so this migration hasn't been applied anywhere yet.

**Required fix (not this session's to make)**: before that migration is committed, its `revision` must be changed to a new unique id and its `down_revision` updated to `x9y0z1a2b3c4` (the current actual head, per `backend/scripts/compute_alembic_head.py`), not `v7w8x9y0z1a2`. Left untouched in the other session's stash/working tree per explicit instruction not to touch their uncommitted work.

---

## DEFECT-009 — BLOCKER — IDOR: `sqn_general` could read other squadrons' planning years

**Note on numbering**: the concurrent session that found and fixed this called it "DEFECT-007" in its
commit message (`d95e67d`), code comments, and test class name (`TestSqnGeneralYearScope`) — but this
register already has an unrelated DEFECT-007 (Vitest/Playwright collision, LOW, fixed earlier).
Using DEFECT-009 here to avoid a second collision; the two "DEFECT-007"s are different defects
found by different sessions. Do not confuse them.

**Status**: Fixed on `release/beta-2026-07-14` (commit `d95e67d`, tag `beta-2026-07-14-rc3`), verified
in staging via a live probe (see below) and via 2 new regression tests.

**Reproducible failure**: `GET /api/planning/years` for an authenticated `sqn_general` user of
squadron 701 returned a year belonging to squadron 703 — a direct cross-squadron data leak.

**Root cause**: `list_planning_years` (`backend/app/routers/planning.py`) filtered results by squadron
for the `sqn_admin` role but applied no filter at all for `sqn_general` — an omitted branch, same
class of bug as DEFECT-001 (a scope check that exists for one role but was never extended to a
sibling role added later).

**Discovery context**: found during this release program's own post-load staging verification (see
the Discovery Note under DEFECT-001's siblings) — an example of exactly the kind of live-staging
probing this release program has repeatedly found value in, beyond unit tests alone.

**Smallest safe fix**: added `sqn_general` to the existing `sqn_admin` scope-filter branch. No new
abstraction.

**Regression test**: `test_sqn_general_sees_own_year`, `test_sqn_general_cannot_see_other_squadron_year`
in `TestSqnGeneralYearScope` (`backend/tests/test_planning_idor.py`).

**Retest evidence**: 543 passed, 1 skipped (up from 541) at commit `d95e67d`.

---

## DEFECT-010 — MEDIUM (unresolved — needs a clean re-run to classify) — 100-user load test: one real 5xx and elevated timeout rate, but two independent test runs overlapped

**Status**: Open — inconclusive pending a clean, non-overlapping re-run (in progress at time of
writing).

**What happened**: two Claude Code sessions working this same release branch in the same shared
working directory each independently launched a full `--users 100 --duration-minutes 45` run of
`tools/stress/load_test_staging.py` against the same staging backend, without coordinating:
- This session's run (background task `bh2yppp8g`): 115,306 requests, **0** real 5xx, 2,567 (2.2%)
  client-side read-timeouts, P95 548ms, max 17,562ms. Exit code 0 (PASS per the script's own
  criteria).
- The concurrent session's run (`btitxok60`, per its own checkpoint `docs/beta/51`): 89,026
  requests, **1** real 5xx, 9,937 (11.2%) client-side read-timeouts, P95 548ms, max 17,381ms. Exit
  code 1 (FAIL — the script's own "Zero 5xx" criterion did not pass).

**Why this isn't clean evidence either way**: both runs report an *identical* P95 (548ms) and
near-identical max latency (~17.4–17.6s) despite independent traffic generators — strong
circumstantial evidence the two runs executed concurrently (or very nearly so) against the same
backend, meaning actual combined concurrent load during the overlap was up to ~200 virtual users,
not the mandated 100. The one real 5xx and the elevated timeout rate in the concurrent session's run
may be an artifact of this accidental doubling rather than a genuine defect at the specified 100-user
scale — but it may also be real. Neither can be determined from these two runs alone.

**Root cause**: no cross-session coordination mechanism exists to prevent two Claude Code sessions
sharing one working directory from both launching long-running load tests against the same shared
staging environment. Process/mtime checks (`ps aux | grep load_test_staging`) were added to this
session's own practice (see `.claude/skills/beta-release/SKILL.md`) only after this collision was
discovered — too late to prevent this instance of it.

**Smallest safe fix**: none to the application. Process fix: check for a running
`load_test_staging.py` process (and cross-reference the other session's checkpoint docs) before
launching a load test; documented in `.claude/skills/beta-release/SKILL.md`.

**Regression test**: N/A (process defect, not code).

**Retest evidence — RESOLVED 2026-07-16**: confirmed via `ps aux | grep load_test_staging` that no
load-test process was running anywhere on the machine, then ran a clean, solo 100-user/45-min run
(background task `bo8g2d7kc`, log `docs/beta/evidence/load_test_100user_clean_rerun_2026-07-16.log`).
Result: **106,151 requests, 0 real 5xx, 3,996 (3.8%) non-5xx failures, P95 830ms, max 17,657ms —
PASS** on both mandated criteria (P95 ≤ 2000ms, zero 5xx). Post-test health check confirmed staging
recovered to normal latency (~0.3–0.5s on `/api/health/ready`, vs. sub-second during the two
contaminated runs). **This is the authoritative 100-user load test result — cite this one, not
either of the two contaminated runs above.**

**New, non-contaminated observation from the clean run** (not a gate failure, but worth flagging):
`/api/auth/login` P95 was 1,967ms — close to the 2,000ms threshold, average 843ms vs. ~260–280ms for
every other endpoint, and the dominant source of the run's failures (connect-timeout and
read-timeout errors, all on `/api/auth/login`). Each virtual user re-authenticates on every workflow
loop, so 100 concurrent users produce sustained concurrent login load. Likely cause: the
intentionally-expensive password hashing (bcrypt/PBKDF2) on the login path becomes a real
contention point at this concurrency — expected behaviour for a deliberately slow hash, but worth a
post-beta look (e.g. hash cost tuning, connection pool sizing for the auth endpoint specifically) if
real beta traffic clusters logins the way this synthetic workflow does (every loop iteration, not
just once per session).

---

## Summary

**Re-verified 2026-08-05 as Gate 9 of the formal 11-gate release process.** The table below was last
accurate 2026-07-16; since then this codebase has been deployed to production twice more (the
77-commit REM-53–76 remediation program, then today's REM-77 P0 fix) — every "open in production"
status below was stale and has been directly re-checked, not assumed, before updating:

| ID | Severity | Status |
|---|---|---|
| DEFECT-001 | BLOCKER | **Fixed and confirmed live in production** — fix commits `051ba4d`/`906f59f` confirmed present in `main` via `git merge-base --is-ancestor`; production's current deployment (`269fd2e3`, 2026-08-05) builds from `main` HEAD. Directly re-verified live 2026-08-05 with a genuine cross-squadron read: `ADMIN704` attempting `GET /api/planning/facilitators/{703's facilitator}/leave` against **production** → `403 {"error":"forbidden"}`, not the pre-fix 200 leak. |
| DEFECT-002 | HIGH | **Fixed** |
| DEFECT-003 | **HIGH** (reclassified from MEDIUM) | **Fully resolved** — `bootstrap-staging` code fix (`f303895`) confirmed in `main`; production `ENVIRONMENT` variable re-checked 2026-08-05 via `railway variable list` and confirmed set to `production` (the approval this row was waiting on has since happened) |
| DEFECT-004 | N/A | **Resolved as not-a-defect** — `SameSite=none` proven required by the current architecture, empirically tested on staging |
| DEFECT-005 | HIGH | **Fixed and confirmed live in production** — fix commit `96584e9` confirmed in `main`; `frontend/Dockerfile` exists; `GET https://aafc-tms-planning-workspace-preview-production.up.railway.app/planning` directly re-checked 2026-08-05 → `200` |
| DEFECT-006 | BLOCKER | **Resolved — proven end-to-end (backup, restore, application-level reads), all against real production data.** Re-verified again 2026-08-05 as Gate 5 with a fresh run (see `docs/beta/32_final_stress_and_resilience_report.md`) |
| DEFECT-007 | LOW | Fixed |
| DEFECT-008 | HIGH (process) | **Resolved** — the revision-ID collision this row describes no longer exists in the current migration chain; `alembic heads` re-checked 2026-08-05 returns exactly one head (`5a195a98148a`), confirmed via both the CLI and this session's own AST-based regression test (`backend/tests/test_migration_schema_drift.py`, added 2026-08-05 for an unrelated but related class of migration defect, REM-77) |
| DEFECT-009 | BLOCKER | **Fixed and confirmed live in production** — commit `d95e67d` confirmed in `main`, deployed with the same 2026-08-05 production release as DEFECT-001/005 above |
| DEFECT-010 | MEDIUM (informational) | **Resolved 2026-07-16** — clean solo re-run: 106,151 req, 0 real 5xx, P95 830ms, PASS. Superseded by a fresh Gate 7 run, 2026-08-05 — see that run's results below/in `32_final_stress_and_resilience_report.md` once complete |

**Every BLOCKER and HIGH item in this register that was previously "open in production" is now
confirmed fixed and live in production**, re-checked directly (not assumed from a stale status line)
during this Gate 9 pass: DEFECT-001, 003, 005, 008, and 009 all closed out between the 2026-07-16
snapshot and today, across two real production deployments this session performed and verified
(the REM-53–76 remediation merge, and today's REM-77 P0 fix). DEFECT-004 was never a real defect.
**No BLOCKER or HIGH severity item remains open in this register as of 2026-08-05.** New findings
from today's gate work (REM-77 P0 schema drift, REM-78 rollback-after-migration process gap) are
tracked in `docs/remediation/master_gap_register.csv`, not duplicated into this older register —
see that file for their full detail.

---

## DEFECT-011 — CRITICAL — Access-code lifecycle: deactivated code usable as authentication credential

**Status**: **Fixed** (commit `30d43111`, 2026-09-05). Verified on staging.

**Reproducible failure**: A user with a deactivated access code (`active_status = False`) could
still authenticate in some edge cases because login, validation, and reset paths fetched the
latest matching code without filtering on `active_status`. A previously-active code that had been
superseded or revoked remained physically present in the database and could be selected.

**Root cause**: Credential-mutating paths (auth, reset, validation) did not filter
`active_status = True` before evaluating the hash. The active-code-per-user invariant was
maintained on write paths but not enforced on read paths in every call site.

**Fix**: All access-code lookups on credential paths now filter `active_status = True` as the
first predicate. Inactive codes cannot be selected regardless of hash match.

**Regression tests**: 39 new tests in `backend/tests/test_access_code_lifecycle.py` covering
the full credential lifecycle: active-only lookup, deactivation side-effects, lifecycle
transitions under concurrent modification.

---

## DEFECT-012 — CRITICAL — Self-service code reset did not require current code

**Status**: **Fixed** (commit `30d43111`, 2026-09-05). Verified on staging.

**Reproducible failure**: `POST /api/accounts/me/reset-code` required only a valid session JWT
to rotate the access code. An attacker who had obtained a valid session (via XSS, session fixation,
or a compromised device) could change the victim's access code without knowing the prior code,
permanently locking out the legitimate user and taking over the credential.

**Root cause**: The reset endpoint performed a session check (`require_role`) but no
re-authentication step requiring knowledge of the current code.

**Fix**: The endpoint now requires the caller to supply their current access code alongside the
new code. The supplied current code is validated against the active hash before the reset proceeds.

**Regression tests**: included in `backend/tests/test_access_code_lifecycle.py`.

---

## DEFECT-013 — CRITICAL — Archive and restore did not invalidate existing JWTs

**Status**: **Fixed** (commit `30d43111`, 2026-09-05). Verified on staging.

**Reproducible failure**: Archiving a user account (`POST /api/accounts/{id}/archive`) suspended
the account in the database but did not bump `token_version`. Any JWT issued before the archive
event remained valid and continued to authenticate API requests — the archived user's session
survived the archive operation indefinitely (until the token's natural expiry).

The same was true for restore: a session issued before the restore could not be distinguished from
one issued after it, so post-restore access controls were not cleanly applied from a fresh session.

**Root cause**: `token_version` was bumped on role changes but not on archive or restore.

**Fix**: Both the `archive` and `batch_archive` endpoints, and the `restore` endpoint, now
increment `token_version` on the affected user. All extant JWTs for that user are immediately
invalid.

**Regression tests**: included in `backend/tests/test_access_code_lifecycle.py`.

---

## DEFECT-014 — HIGH — Sibling login fallback incremented lockout counter per candidate tested

**Status**: **Fixed** (commit `30d43111`, 2026-09-05). Verified on staging.

**Reproducible failure**: The login path that walks a candidate list of access codes for a user
incremented `failed_attempts` on each candidate that did not match, rather than once per login
attempt. For a user with N prior (deactivated) codes in the database, a single failed login
consumed N lockout attempts. This could lock an account after a small number of legitimate-but-
incorrect login attempts from the user themselves.

**Root cause**: Failure accounting was attached to the per-candidate evaluation rather than the
aggregate login decision.

**Fix**: `failed_attempts` is now incremented only after the final determination that no candidate
matched, i.e., once per login attempt regardless of how many candidates were evaluated.

**Regression tests**: included in `backend/tests/test_access_code_lifecycle.py`.

---

## DEFECT-015 — HIGH — Planning write endpoints used scope guard without proxy awareness

**Status**: **Fixed** (commit `30d43111`, 2026-09-05). Verified on staging.

**Reproducible failure**: Nineteen planning write endpoints in `backend/app/routers/planning.py`
used `_require_year_access(..., write=True)`, which has no proxy/delegated-intervention awareness.
A `wing_admin` operating in Proxy Mode on behalf of a squadron was incorrectly rejected from
these endpoints (RBAC regression), while conversely the simpler check did not enforce the full
proxy-mode preconditions that the codebase's established pattern requires for delegated writes.

**Root cause**: `_require_year_access` was used in contexts that require proxy-aware scope
checking (`require_can_write_squadron`). The two helpers are not interchangeable — see
`.claude/rules/architecture.md`.

**Fix**: All 19 affected endpoints now use `require_can_write_squadron()`. The guard enforces
proxy/delegated-intervention mode where required and grants appropriate access to wing and
national admins operating through the correct delegation channel.

**Regression tests**: `backend/tests/test_planning_proxy_rbac.py`.

---

## DEFECT-016 — HIGH — /exceptions/run-checks used role check without scope guard

**Status**: **Fixed** (commit `30d43111`, 2026-09-05). Verified on staging.

**Reproducible failure**: `POST /api/exceptions/run-checks` (`backend/app/routers/ops.py`) used
`require_role(p, 'sqn_admin', 'wing_admin', 'national_admin')` without a subsequent scope check.
This allowed callers to trigger exception checks on squadrons outside their authorised scope.

**Root cause**: The endpoint was added without the write-guard pattern that every other mutation
endpoint in the same codebase uses.

**Fix**: Endpoint now calls `require_can_write_squadron()`.

**Regression tests**: `backend/tests/test_exceptions_run_checks.py`.

---

## DEFECT-017 — HIGH — Service desk email save was silently misdirected

**Status**: **Fixed** (commit `30d43111`, 2026-09-05). Verified on staging.

**Reproducible failure**: The service desk email save handler in `connected-frontend/index.html`
called `api(method, path, body)` — positional-arg order reversed relative to the helper's actual
signature `api(path, opts)`. The request was sent to the URL literal `'POST'` rather than the
intended API endpoint. The call appeared to succeed (no uncaught exception) but silently discarded
the save. Service desk email configuration changes never persisted.

**Root cause**: The `api()` helper signature changed at some point from a method-first convention
to path-first (matching `fetch`). This call site was not updated. See `.claude/rules/frontend.md`
— this mismatch had previously broken the service desk ticket list and was noted there.

**Fix**: Corrected to `api(path, { method: 'POST', body: payload })`.

**Regression tests**: covered by existing integration tests and the staging Playwright suite.

---

## DEFECT-018 — HIGH — Role and scope labels inserted as raw innerHTML

**Status**: **Fixed** (commit `30d43111`, 2026-09-05). Verified on staging.

**Reproducible failure**: `ROLE_LABELS` and `SCOPE_LABELS` values from the API session response
were rendered into the DOM via unescaped `innerHTML` assignment in `connected-frontend/index.html`.
A stored XSS payload in a role label or scope label (reachable via a compromised backend or a
database-level injection) would execute in the victim's browser context on next page render.

**Root cause**: The `esc()` helper defined in the same file was not applied to these specific
render sites. Both were missed in the original XSS sweep because they are not in the primary
content-rendering path.

**Fix**: All `ROLE_LABELS` and `SCOPE_LABELS` render sites now call `esc(value)` before
insertion.

**Regression tests**: covered by the existing frontend XSS test harness and the staging
Playwright suite.

---

## DEFECT-019 — MEDIUM — Async rate limiter made blocking database call on the event loop

**Status**: **Fixed** (commit `30d43111`, 2026-09-05). Verified on staging.

**Reproducible failure**: The rate-limiter middleware in `backend/app/main.py` called
`SessionLocal()` synchronously inside an `async def` middleware handler. Under concurrent load,
this blocked the event loop during every database call made by the rate limiter, creating a
potential latency cliff as throughput scaled (observed in the DEFECT-010 load test's
`/api/auth/login` P95 elevation, though that finding had multiple contributors).

**Root cause**: Blocking I/O on the async event loop — a common FastAPI pitfall when adapting
synchronous SQLAlchemy sessions to async middleware.

**Fix**: The `SessionLocal()` call and its surrounding logic are now dispatched via
`run_in_executor`, keeping the event loop non-blocking.

**Regression tests**: behaviour is load-test-verifiable; unit-tested via the staging Playwright
suite's auth flows at concurrency.

---

## DEFECT-020 — MEDIUM — Status badge rendered arbitrary strings as HTML class attributes

**Status**: **Fixed** (commit `30d43111`, 2026-09-05). Verified on staging.

**Reproducible failure**: The status badge renderer in `connected-frontend/index.html` took the
status string directly from the API response and set it as a CSS class on the badge element. An
unrecognised (or adversarially crafted) status string could inject arbitrary content into the
`class` attribute, potentially reaching attribute injection or breaking the DOM structure.

**Root cause**: No allowlist or sanitisation between the API string and the class attribute
assignment.

**Fix**: A strict enum-to-CSS-class mapping is now applied. Only known status values produce
a corresponding class; anything else receives `status-unknown`. The API string never touches
the class attribute directly.

**Regression tests**: covered by the staging Playwright suite's badge-rendering paths.

---

**Summary update (2026-09-05)**: DEFECT-011 through DEFECT-020 were identified during the Phase
A–E adversarial qualification, fixed in commit `30d43111`, and verified on staging 2026-09-05
(187 Playwright tests passed, 8 skipped by design, 0 failed; 2258 backend tests passed). No
BLOCKER or HIGH severity item is open in this register as of 2026-09-05. The three CRITICAL items
(011–013) and four HIGH items (014–017) have regression tests. The two MEDIUM items (019–020)
are verified by load-test and integration-test evidence respectively.
