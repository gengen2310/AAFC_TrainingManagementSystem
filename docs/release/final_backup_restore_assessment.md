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
- The one remaining restore-test failure (`Migration HEAD mismatch`) was
  root-caused precisely to `origin/main` being 14 commits behind local at dispatch
  time — a stale-comparison artifact, not a real defect, and resolves itself once
  this branch is pushed/merged.

## In-container manual backup path (GAP-26, new finding this pass)

- `backend/Dockerfile`'s `postgresql-client` was unpinned, resolving to a version
  (15 or 17 depending on the base image's floating Debian codename) older than
  production's actual server (17.x/18.x) — the same failure class as GAP-16, in a
  different code path (`system.py`'s `POST /api/system/backup`, the System
  Console "Download PostgreSQL Backup" button) that GAP-16/18's fix never touched
  because it was scoped to the GitHub Actions workflow only.
- Fixed by mirroring the already-proven PGDG-repo pattern from
  `backup-postgresql.yml`. **Not verified by an actual Docker build** — no Docker
  available in this environment. Flagged explicitly as needing a real build
  before full closure.

## Documentation reconciliation

`deployment/backup-dr.md` contained stale guidance directly contradicted by
GAP-18's own fix (told operators to find `PROD_DATABASE_BACKUP_URL` via "Supabase
Dashboard → Settings → Database → Session Pooler" — actively wrong after the fix
repointed it to Railway). Also contained older staleness from a prior Render-based
architecture (predating the current Railway deployment entirely). Corrected both:
the secret-location guidance now points to Railway's `DATABASE_PUBLIC_URL` pattern,
and the Render/Supabase references in the "what backup does not cover" section were
updated to reflect the actual current (Railway) deployment.

## Restore procedure — proven for the automated path, not yet drilled manually end-to-end

The automated restore-test workflow (`test-restore-postgresql.yml`) has now been
run fresh and passed (data checks) this pass. A **full manual disaster-recovery
drill** — an operator following `deployment/backup-dr.md`'s own "Restore procedure"
section by hand, from a downloaded artifact, against a real disposable target — was
not performed this pass. The automated workflow exercises materially the same
steps (decrypt, `pg_restore`, verify), so this is lower-risk than it would be
otherwise, but a literal human dry-run of the documented manual steps is still
recommended before calling backup/DR fully proven end-to-end.

## Still open / not covered this pass

- Whether Railway's native Postgres plugin offers point-in-time recovery on the
  current plan — not confirmed either way (previously assumed Supabase PITR,
  which is now known to be the wrong product entirely).
- A full manual DR drill (see above).
- Key rotation procedure (`deployment/backup-dr.md`'s own documented steps) has
  not been exercised this pass — no rotation was due.
