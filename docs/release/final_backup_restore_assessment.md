# Final Backup/Restore & Deployment Artefact Assessment (Stage 12)

Consolidates evidence already produced this pass (GAP-18, GAP-26) rather than
re-deriving it — this doc is the single place to check backup/DR release-readiness
without re-reading the full gap register.

## Backup targets the correct, real production database (GAP-18)

- **Confirmed broken, then fixed, then proven working** with a fresh backup +
  restore-test cycle whose restored row counts (`squadrons: 1`, `wings: 1`,
  `users: 1`, `audit_logs: 13`, `curriculum_items: 214`) exactly match production's
  independently-known live state. Full detail: gap register, GAP-18.
- Staging's backup independently re-verified to already target the correct
  database (a misleadingly-named secret, not a functional defect).
- **Updated 2026-08-02 (post-deployment reconciliation): the earlier `Migration
  HEAD mismatch` caveat is now fully resolved, not just explained.** A fresh
  restore-test dispatch against current `main` (fully pushed, containing the
  complete migration set) came back with **zero caveats — all 15 checks pass**,
  expected head `z1a2b3c4d5e6` exactly matching the restored database's actual
  head. Confirms the earlier hypothesis (stale `origin/main` at dispatch time)
  was correct.
- **New evidence layer, this pass**: beyond the SQL-level checks, the workflow
  (already built this way, not new this pass) creates a throwaway admin, starts
  a real backend against the restored database, and drives 8 authenticated API
  reads through it — all 8 pass. This is genuine application-level proof a
  restored backup produces a fully functional, API-servable application, not
  merely a SQL dump that restores without error.

## In-container manual backup path (GAP-26)

- `backend/Dockerfile`'s `postgresql-client` was unpinned, resolving to a version
  (15 or 17 depending on the base image's floating Debian codename) older than
  production's actual server (17.x/18.x) — the same failure class as GAP-16, in a
  different code path (`system.py`'s `POST /api/system/backup`, the System
  Console "Download PostgreSQL Backup" button) that GAP-16/18's fix never touched
  because it was scoped to the GitHub Actions workflow only.
- Fixed by mirroring the already-proven PGDG-repo pattern from
  `backup-postgresql.yml`. **Updated: now build-verified, not just reasoned.** A
  real Railway Docker build of this Dockerfile succeeded and deployed to staging
  during Stage 13 — the earlier "not verified by an actual Docker build" gap is
  closed.

## Documentation reconciliation

`deployment/backup-dr.md` contained stale guidance directly contradicted by
GAP-18's own fix (told operators to find `PROD_DATABASE_BACKUP_URL` via "Supabase
Dashboard → Settings → Database → Session Pooler" — actively wrong after the fix
repointed it to Railway). Also contained older staleness from a prior Render-based
architecture (predating the current Railway deployment entirely). Corrected both:
the secret-location guidance now points to Railway's `DATABASE_PUBLIC_URL` pattern,
and the Render/Supabase references in the "what backup does not cover" section were
updated to reflect the actual current (Railway) deployment.

## Restore procedure — proven for the automated path, plus an operator DR walkthrough this pass; still not literally hand-run

The automated restore-test workflow (`test-restore-postgresql.yml`) has now been
run fresh and passed cleanly, zero caveats (see above). This pass additionally
performed an **operator DR walkthrough**: every artefact `deployment/backup-dr.md`
tells an operator to rely on was independently confirmed to exist and match the
doc exactly — `.github/backup-public-key.asc` (a real key, not a placeholder),
all 4 backup/restore workflow files, `backend/scripts/compute_alembic_head.py`,
and all 4 required GitHub secrets
(`BACKUP_GPG_PASSPHRASE`, `BACKUP_GPG_PRIVATE_KEY`, `PROD_DATABASE_BACKUP_URL`,
`SUPABASE_DB_URL`). **What this walkthrough did not do**: actually generate a new
GPG keypair or run `pg_restore` by hand from a downloaded artifact — a literal
human dry-run of the documented manual steps, keystroke by keystroke, remains
un-run. The automated workflow exercises materially the same decrypt/restore/
verify sequence end-to-end (including, now, live application-level verification —
see above), which meaningfully de-risks this gap without fully closing it.

## Still open / not covered this pass

- Whether Railway's native Postgres plugin offers point-in-time recovery on the
  current plan — not confirmed either way (previously assumed Supabase PITR,
  which is now known to be the wrong product entirely).
- A literal, hand-run manual DR drill (artefacts confirmed present and correct
  this pass; the steps themselves were not manually executed — see above).
- Key rotation procedure (`deployment/backup-dr.md`'s own documented steps) has
  not been exercised this pass — no rotation was due.
