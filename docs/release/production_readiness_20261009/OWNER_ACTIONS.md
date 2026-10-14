# Owner actions to reach GO (2026-10-13)

Six items remain. Everything else in `RELEASE_DECISION.md` is done and evidenced. All six need
the owner, because they are sign-offs, production settings, or a key only the owner should hold.
Do them in this order. **Do not paste access codes, keys or tokens into chat, issues or these
docs**; tell Claude only that a step is done, and give the run IDs or deployment IDs.

## B1: user acceptance testing (half a day with real users)
1. On **staging** (`https://aafc-tms-frontend-staging.up.railway.app`), one real Training Officer
   per role works through `docs/beta/37_user_acceptance_test_plan.md`. That includes the addendum
   checks U1–U11.
2. Each tester records pass, fail or comment per row in `docs/beta/38_user_acceptance_results.md`.
   Claude must not fill these rows in.
3. Read and sign `docs/beta/46_data_governance_and_approval.md` and
   `docs/beta/47_known_limitation_acceptance.md`.
4. **Send back:** "B1 done", plus any failed rows. Claude fixes each one with a regression test.

## B2: backup key custody
1. Follow `docs/beta/36_backup_key_custody_checklist.md`:
   - a production GPG key separate from staging's, held outside GitHub by a named person;
   - private storage for the encrypted artifacts;
   - one copy kept off GitHub.
2. Sign the checklist.
3. **Send back:** "B2 done". Never send the key itself.

## B3: restore rehearsal on PostgreSQL 17, with your key
1. Download the latest production backup artifact. Decrypt it with the B2 key on a machine you control.
2. Restore it into an **empty** PostgreSQL 17 database, following `docs/release/rollback_runbook.md`
   §1a. Never use `pg_restore --clean` over an existing schema (D25).
3. Point a local backend at it. Confirm `/api/health/ready` responds and that one sign-in works.
4. **Send back:** "B3 done", with the PostgreSQL version and the row counts reported for
   `users` and `parade_nights`.

## B4: production configuration (Railway dashboard → production → backend → Variables)
1. Set `API_RATE_LIMIT` = `1200`. This is your decision R1; staging already runs it.
2. Make sure `CORS_ALLOWED_ORIGINS` contains exactly these two values:
   - `https://aafc-tms-frontend-production.up.railway.app`
   - `https://aafc-tms-planning-workspace-preview-production.up.railway.app`

   It must not contain `*` or localhost.
3. Save **without redeploying**. The values take effect at the release deploy, and
   `deploy-production.sh` re-checks both.
4. **Send back:** "B4 done".

## B5: identify what production runs now (the rollback target)
1. In the Railway dashboard, open production. For each of backend, frontend and Planning
   Workspace, open **Deployments**. Note the active deployment ID and its source (commit or upload).
2. Production's health endpoint reports `0cf2e8d`. That value is stale and must not be used (R6).
3. **Send back:** the three deployment IDs, plus a commit SHA for each if one is shown.

## B8: merge and the first scheduled restore test
1. When B1–B5 are done, mark PR #73 *Ready for review*. Then merge it with a **merge commit**,
   not squash or rebase, so that rolling back the code is a single revert.
2. Close #69, #71 and #72. Each has a comment proving it is contained in #73. Close issue #70
   only if its acceptance criteria are met.
3. Claude then checks CI on the merge commit and the next scheduled
   `PostgreSQL Restore Test — Production — Weekly` run on `main`. That run currently fails on
   `main` because of D6, which is fixed in #73.

## Then: the production deploy (separate approval)
Re-run the beta gate 11 consolidation. Then approve, in writing, the exact merge commit, the
three services, the order (backend → Main TMS → Planning Workspace) and the rollback (§1a).
Immediately before deploying:
1. Run `backup-postgresql.yml` and then `test-restore-postgresql.yml` by hand on `main`
   (Actions → workflow → *Run workflow*).
2. Then run, from a clean checkout of `main`:

```bash
PRE_DEPLOY_BACKUP_RUN_ID=<backup run id> PRE_DEPLOY_RESTORE_RUN_ID=<restore run id> \
PRODUCTION_SYSTEM_ADMIN_CODE=<code> bash scripts/deploy-production.sh
```

The full sequence is in `docs/release/production_release_runbook.md`. Claude does not run this
script. Production deployment is the owner's action.
