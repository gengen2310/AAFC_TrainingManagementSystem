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

## DEFECT-003 — MEDIUM — Production `ENVIRONMENT` variable reads `staging`, not `production`

**Status**: Open, investigation not complete. Not changed — do not change without further verification (see `docs/beta/00_release_state.md`, Phase G).

**Detail**: `backend/app/config.py`'s `is_production`/`validate_for_production()` fail-closed startup checks key off `ENVIRONMENT == "production"/"prod"`. Production's Railway backend service currently has `ENVIRONMENT=staging`. Confirmed **not** to expose `/docs` (that's hardcoded off in `main.py` regardless of environment). Full trace of what else this disables is not yet complete.

---

## DEFECT-004 — MEDIUM — Production `COOKIE_SAMESITE=none` vs. project rule of `strict`

**Status**: Open, investigation not complete — do not change without testing (frontend/backend are cross-subdomain; changing this could break login). See `docs/beta/00_release_state.md`, Phase G.

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

## Summary

| ID | Severity | Status |
|---|---|---|
| DEFECT-001 | BLOCKER | Fixed on release branch, staging-verified; **open in production** |
| DEFECT-002 | HIGH | **Fixed** |
| DEFECT-003 | MEDIUM | Open, under investigation |
| DEFECT-004 | MEDIUM | Open, under investigation |
| DEFECT-005 | HIGH | Fixed on release branch, staging-verified; **open in production** |
| DEFECT-006 | BLOCKER | **Resolved — proven end-to-end (backup, restore, application-level reads), all against real production data** |
| DEFECT-007 | LOW | Fixed |
| DEFECT-008 | HIGH (process) | Open — belongs to a concurrent session, flagged not fixed |

**One of two BLOCKERs fully resolved (DEFECT-006, backup/restore — proven end-to-end).** DEFECT-001 (live-production IDOR) is fixed and verified on the release branch/staging but requires a production deploy + approval to close there. Not release-ready until that deploy happens, DEFECT-002/DEFECT-005-in-production are addressed, and DEFECT-008 (migration-ID collision, owned by a concurrent session) is resolved.
