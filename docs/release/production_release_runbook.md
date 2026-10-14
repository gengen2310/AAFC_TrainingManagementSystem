# Production Release Runbook

Applies to: the production-readiness release (`release/production-readiness-20261009` →
`main`; production database v64 `a4e9507a9c51` → v76 `63c110addb63`), Railway project
`exemplary-emotion`. **Rewritten 2026-10-12**; the July version (PR #3) is superseded.
Do not execute any step until `docs/release/production_readiness_20261009/RELEASE_DECISION.md`
reads **GO** and the owner has approved the exact commit, services, order and rollback plan.

## 0. Fail-closed environment verification (required before every Railway action)

Before every single Railway CLI/MCP action in this runbook, print and verify all of the
following against the values the operator provides at execution time — this document
does not hardcode them as ground truth, because IDs recorded in a document can drift
from the live project between the time this was written and the time it's executed:

- Project ID
- Environment ID (must resolve to the `production` environment, never `staging`)
- Service ID (must match the service you intend to act on: backend, Main TMS frontend,
  or Planning Workspace frontend)
- Target domain
- Source branch (`main`, post-merge)
- Exact deployed Git SHA
- Build fingerprint
- Target database revision (`alembic heads` must show one head, matching what this
  runbook's migration step expects)

If any of these does not match what the operator expects, stop and resolve the
mismatch before proceeding. Do not guess or proceed on a partial match.

## 1. Pre-deployment checklist

- [ ] `RELEASE_DECISION.md` reads GO; owner approval names the exact commit (the merge
      commit on `main`), the three services, the order below, and rollback 1a.
- [ ] The release PR is merged to `main`; CI is green on the merge commit; you deploy from a
      clean checkout of `main` at that commit (`deploy-production.sh` refuses anything else).
- [ ] **Identify the build production is running now** (Railway dashboard → each service →
      active deployment: ID and source). Production's `/api/health/ready` reports
      `0cf2e8d` (a v46-era commit) against a v64 database, so that value is stale metadata
      and must not be used as the rollback target (2026-10-12 finding). Record the real
      deployment IDs / commit in the change record — they are the rollback target.
- [ ] **Owner decisions applied in production variables:** `API_RATE_LIMIT` set explicitly
      (the per-IP limit is now enforced accurately; see `STAGING_EVIDENCE.md`), and
      `CORS_ALLOWED_ORIGINS` contains exactly `https://aafc-tms-frontend-production.up.railway.app`
      and `https://aafc-tms-planning-workspace-preview-production.up.railway.app` (cookie writes
      from any other origin are refused, D13). The script re-checks both and aborts otherwise.
- [ ] **Fresh, verified backup — mandatory for this release** (the previous build cannot start
      once v70–v76 have run, D23): run `backup-postgresql.yml` (workflow_dispatch) and then
      `test-restore-postgresql.yml` on `main`; both must succeed; the backup must be under
      6 hours old at deploy time. Their run IDs are required by the script
      (`PRE_DEPLOY_BACKUP_RUN_ID`, `PRE_DEPLOY_RESTORE_RUN_ID`).
- [ ] An operator can decrypt that backup **outside GitHub** with a key they hold (owner
      action — key custody, `docs/beta/36_backup_key_custody_checklist.md`); otherwise rollback
      1a is not executable.
- [ ] `rollback_runbook.md` §1a has been read; the operator knows the export step for data
      written after the deploy.
- [ ] Announce the window; maintenance mode is available (System Console) if wanted.

## 2. Deployment sequence (`scripts/deploy-production.sh`)

```bash
git checkout main && git pull --ff-only     # at the approved merge commit
PRE_DEPLOY_BACKUP_RUN_ID=<run id> PRE_DEPLOY_RESTORE_RUN_ID=<run id> \
PRODUCTION_SYSTEM_ADMIN_CODE=<code> bash scripts/deploy-production.sh
# type: DEPLOY TO PRODUCTION <short sha>
```

The script, in order, fails closed at every step: Railway project/environment/service IDs
against its allow-list → git (branch `main`, clean, pushed) → security greps → backend suite →
single Alembic head (computed) → login → **backup gate** (fresh backup + later successful
restore test) → **configuration gate** (CORS origins, explicit `API_RATE_LIMIT`) →
authorization phrase → backend (`APP_BUILD_COMMIT` stamped, `railway up`, health, new
deployment ID, database revision = head, CRUD smoke) → Main TMS (stamp, fingerprint, modules)
→ Planning Workspace (stamp, fingerprint). The backend container runs
`scripts/migrate_or_hold.py` (upgrades v64 → v76: 15 migrations, rehearsed on restored
production data, run 38221096962).

## 3. Post-deployment production smoke tests

Run only the following against production — per the standing safety boundary, load
tests, stress tests, penetration tests, chaos tests, bulk destructive tests, test-data
seeding, migration-failure simulations, mass imports, and automated duplicate cleanup
must never be run against production:

- [ ] `GET /api/health`, `/api/health/db`, `/api/health/ready` all return healthy
- [ ] Log in as one real (or designated test) account per role tier that exists in
      production — confirm each lands on the correct scope/landing page
- [ ] Confirm `/docs` (Swagger UI) is NOT publicly reachable
- [ ] Confirm CORS origins are locked to the production frontend origins only (no `*`,
      no localhost)
- [ ] Spot-check one read-only page per frontend (Dashboard on Main TMS, Planning
      Workspace's Year view) renders real data with no console errors
- [ ] Confirm the security greps in `.claude/rules/security.md` still return 0 against
      whatever was actually deployed (re-run locally against the exact deployed commit,
      not from memory)

## 4. Post-release monitoring window

Monitor for at least 4 hours after deployment completes:

- Error rate / 5xx rate on the backend
- Login success rate (a spike in failures could indicate a CORS/URL misconfiguration
  from step 2/3 above)
- Database connection pool health
- No unexpected spike in audit log volume (could indicate an automated/scripted attack
  rather than real usage)

## 5. Rollback trigger conditions

Roll back immediately (see `rollback_runbook.md`) if any of the following occur within
the monitoring window:

- Health checks fail or the backend is unreachable
- A SEV1 defect is discovered (data loss, security bypass, authentication broken for a
  whole role tier)
- Error rate exceeds a level the operator judges abnormal for current traffic
- A migration left the database in an inconsistent state

**For this release, rolling back means restoring the pre-deploy backup** (`rollback_runbook.md`
§1a) and losing everything written since the deploy: the previous build cannot start against the
migrated database. Prefer a forward fix unless data integrity or security is at stake; if you
roll back, export post-deploy changes first and restore into an empty schema (D25).
