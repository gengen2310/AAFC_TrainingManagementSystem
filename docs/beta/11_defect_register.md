# AAFC TMS — Defect Register

Severity definitions per the release program: BLOCKER (auth bypass, cross-squadron leak,
data loss/corruption, failed migration, no successful backup/restore, blank core workflow,
divergent authoritative data, unusable release path) and HIGH (unauthorised write, silent
autosave failure, duplicate operational data, persistent 500, severe performance failure,
unsafe year rollover, failed rollback, CEA reimport losing local data).

---

## DEFECT-001 — BLOCKER — IDOR: facilitator-leave, notices, CEA endpoints missing object-scope checks

**Status**: Fixed on `release/beta-2026-07-14` (commit `051ba4d`), verified in staging. **Still live and unfixed in production** as of this writing — production has not been redeployed.

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

**Not affected** (checked, found correctly self-scoped): `POST /api/planning/cea/{activity_id}/local-hide` writes only to a row keyed by the caller's own `unit_id` — no target-object tenancy check is needed since it can't touch another org's data by construction.

**Smallest safe fix**: fetch the target object first, then call the existing scope helper before mutating/returning anything — no new permission abstraction added. See commit `051ba4d`.

**Regression test**: 13 new tests in `backend/tests/test_planning.py` (search `cross_squadron`/`same_squadron_admin_allowed`). Each cross-tenant test confirmed to **fail** against the pre-fix code and **pass** against the fix before being committed.

**Retest evidence**: `421 passed, 1 skipped` (pre-existing baseline) → `434 passed, 1 skipped` (post-fix, +13 new tests, zero regressions). Live non-destructive route probes against production (2026-07-13) confirm this exact vulnerable code is currently deployed there — see `docs/beta/00_release_state.md`.

**Outstanding**: production has not been redeployed with this fix. Per rule 13, production deployment requires explicit approval and is not authorized by this fix alone — this defect remains OPEN at the production level until that deploy happens and is verified.

**Related, not yet fixed** — `_require_year_access` (used by the notices/CEA fix above, and pre-existing elsewhere) does not scope-restrict **reads** for roles outside `sqn_admin`/`wing_admin`/`wing_viewer`/`national_viewer`/`auditor` — e.g. `sqn_general` (squadron read-only) hits no branch and falls through unrestricted. This is a broader, pre-existing characteristic of a shared helper used by many endpoints beyond the three in scope here; flagging for separate follow-up rather than fixing under this defect's blast radius without full impact mapping.

---

## DEFECT-002 — HIGH (foot-gun, not yet exploited) — `seed_all.py` is unconditionally destructive

**Status**: Open, not fixed.

**Reproducible failure**: `backend/app/seeds/seed_all.py`'s `seed_all()` calls `reset_db()` (`Base.metadata.drop_all()` + `create_all()`) unconditionally at the top of the function, with no environment guard or confirmation prompt.

**Root cause**: no safety check on the destructive path.

**Severity rationale**: not itself a live incident, but a real hazard — if ever invoked against a database containing real data (wrong `DATABASE_URL`, muscle-memory command in a real environment), it silently deletes everything with no confirmation.

**Recommended fix**: gate `reset_db()` behind an explicit check (e.g. refuse when `settings.ENVIRONMENT == "production"`, or require an explicit `--i-am-sure` / confirmation env var) before it's used for anything beyond fresh local/CI databases.

**Regression test**: not yet written.

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

## DEFECT-006 — BLOCKER (now remediated, unproven end-to-end) — Backup/restore has never succeeded

**Status**: Remediated this session, not yet proven by an actual successful workflow run.

**Root cause**: the committed `.github/backup-public-key.asc` had no corresponding `BACKUP_GPG_PRIVATE_KEY`/`BACKUP_GPG_PASSPHRASE` GitHub secret — a matching secret key existed only in a local GPG keyring whose passphrase was never recorded anywhere accessible. `SUPABASE_DB_URL` was also never set. Every daily backup run failed for at least 10 consecutive days (2026-07-03 → 2026-07-12); both restore-test runs failed.

**Fix**: rotated to a fresh keypair (commit `3e9acd6`) per the project's own key-rotation runbook, set all three GitHub secrets (`SUPABASE_DB_URL` now points at the new staging Postgres, not production), established offline key custody at `~/Documents/AAFC-TMS-Backup-Recovery/`.

**Outstanding**: has not yet been proven by an actual successful backup workflow run + restore-test + restored-data read-back. This remains a BLOCKER until that evidence exists.

---

## Summary

| ID | Severity | Status |
|---|---|---|
| DEFECT-001 | BLOCKER | Fixed on release branch, staging-verified; **open in production** |
| DEFECT-002 | HIGH | Open |
| DEFECT-003 | MEDIUM | Open, under investigation |
| DEFECT-004 | MEDIUM | Open, under investigation |
| DEFECT-005 | HIGH | Fixed on release branch, staging-verified; **open in production** |
| DEFECT-006 | BLOCKER | Remediated, unproven |

**Zero blocker defects resolved end-to-end in production. Zero unresolved-high-defect count is not yet zero. Not release-ready.**
