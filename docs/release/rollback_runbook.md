# Rollback Runbook

Use this when `production_release_runbook.md`'s Section 5 trigger conditions are met, or
whenever an operator judges the newly-deployed production build unsafe to keep running.

## 0. Fail-closed environment verification (required before every Railway action)

Same discipline as the deployment runbook: before every Railway action in this
procedure, print and verify project ID, environment ID (must be `production`), service
ID, target domain, source branch/SHA, and target database revision against what the
operator provides at execution time. Do not proceed on a partial match.

## 1. Decide: redeploy previous build, or forward-fix?

- **Redeploy previous build** — the default choice for anything SEV1/SEV2, anything
  involving data integrity or auth, or anything where root cause isn't yet understood.
  Faster, safer, and doesn't require writing new code under pressure.
- **Forward-fix** — only appropriate for a narrowly-understood, low-risk issue where a
  rollback would itself be disruptive (e.g. a rollback would lose data written since
  deploy that a redeploy can't safely reconcile). If forward-fixing, still follow the
  same fail-closed verification and post-deploy smoke test steps as a fresh deployment.

Default to redeploying the previous build unless there's a specific, articulable reason
forward-fixing is safer in this instance.

## 2. Application rollback (no migration involved)

If the deployed backend migration is unchanged from the previous release (i.e. this
release added no new Alembic revision, or the new revision is purely additive and
backward-compatible with the previous application code):

1. Identify the previous known-good Git SHA and Railway deployment ID for each of the
   three services (backend, Main TMS frontend, Planning Workspace frontend).
2. Redeploy each service from that prior deployment/SHA — Railway supports redeploying
   a specific prior build directly; use that rather than reverting commits and pushing
   a new one, since a direct redeploy is faster and doesn't touch git history.
3. Re-run `production_release_runbook.md` Section 3's smoke tests against the
   rolled-back build.
4. Confirm the rollback resolved the triggering condition before standing down.

## 3. Rollback involving a migration

If the release included a new Alembic migration:

1. **Do not** run `alembic downgrade` against the production database as a first
   resort. A downgrade that drops a column or table the new application code already
   wrote data into will lose that data. Assess first:
   - If the migration was purely additive (new nullable column, new table) and no
     rolled-back code path depends on the new schema being absent, it is usually safe
     to leave the schema at the new revision and simply redeploy the previous
     application code (Section 2) — the old code ignores columns/tables it doesn't
     know about.
   - If the migration is destructive or the old code would break against the new
     schema (e.g. a `NOT NULL` column the old code never sets), a downgrade is
     necessary. Back up the database first (see `deployment/backup-dr.md`), run
     `alembic downgrade <previous-revision>` against production only after confirming
     via Section 0 that this is genuinely the production database, then redeploy the
     previous application code.
2. This is exactly the kind of destructive-migration-without-a-safe-alternative
   scenario that the standing safety boundary requires stopping for — if the safe path
   isn't clear from the two bullets above, stop and get an explicit operator decision
   rather than guessing.

## 4. Data recovery (if data loss is suspected)

1. Do not attempt ad hoc data reconstruction. Use the documented, tested restore
   procedure in `deployment/backup-dr.md`.
2. Identify the most recent backup taken *before* the problematic deployment.
3. Restore to a separate, disposable database first (never restore directly over the
   live production database) and verify the restored data at the application level
   (real login, real authenticated reads) before deciding whether/how to reconcile it
   with any data written after the problematic deployment.
4. Reconciling data written between the last good backup and the rollback is a
   case-by-case decision — do not automate it. Get an explicit operator decision on
   which records (if any) should be preserved from the rolled-back window.

## 5. Post-rollback verification

- [ ] All three services report the expected (rolled-back) Git SHA
- [ ] `production_release_runbook.md` Section 3 smoke tests pass
- [ ] The specific trigger condition from `production_release_runbook.md` Section 5 no
      longer reproduces
- [ ] Audit log confirms the rollback deployment itself is recorded, for the incident
      record

## 6. After the rollback

Do not immediately re-attempt the same deployment. Root-cause the failure first,
correct it, prove the correction with the same local + staging gates the original
release went through, and only then reschedule a new production deployment attempt.
