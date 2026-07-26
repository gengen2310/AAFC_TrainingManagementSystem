# Production Release Runbook

Applies to: PR #3 (`feature/restore-planning-workspace` → `main`), Railway project
`exemplary-emotion`. Do not execute any step in this runbook until
`general_release_readiness.md` states `READY FOR GENERAL RELEASE`.

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

- [ ] `general_release_readiness.md` states `READY FOR GENERAL RELEASE`
- [ ] PR #3 has been merged to `main` (not before — do not deploy an unmerged branch to
      production)
- [ ] Staging soak period completed with no SEV1/SEV2 defects open
- [ ] `rollback_runbook.md` has been read and the operator understands the rollback path
      before starting
- [ ] A recent production backup exists and its restore has been verified (see
      `deployment/backup-dr.md`) — do not deploy without a fresh, restore-verified backup
      point to fall back to
- [ ] No financial-commitment or infrastructure-scaling decision is pending (those are a
      separate, explicit conversation with the operator, not part of this runbook)

## 2. Deployment sequence

Each step targets exactly one Railway service. Re-run Section 0's verification before
each step, not just once at the start.

1. **Backend** (service: Main TMS backend, per Section 0's verified service ID)
   - Confirm the target environment's `DATABASE_URL` points at the production database,
     not staging (read-only check — never copy a secret value between environments).
   - Trigger deployment from the merged `main` branch.
   - Wait for the build to complete; confirm the deployed Git SHA matches `main`'s HEAD.
   - `alembic upgrade head` runs automatically as part of the container's entrypoint
     (mirroring `docker-entrypoint-staging.sh`'s pattern) — confirm the post-deploy
     `alembic heads` shows one head and it matches this backend's expected head.
   - Hit `GET /api/health/ready` on the production backend URL — must return
     `{"status": "ready", ...}`.
2. **Main TMS frontend** (`connected-frontend`, `aafc-tms-frontend` service)
   - Confirm `AAFC_API_BASE` for this environment is set to the production backend URL
     from step 1 (the container's `docker-entrypoint.sh` rewrites the
     `<meta name="aafc-api-base">` tag from this variable at start — do not rely on
     whatever is checked into `connected-frontend/index.html`'s default, which per
     `qualification_gap_register.md` GAP-11 currently defaults to production anyway, but
     this must not be assumed without checking the live environment variable).
   - Trigger deployment; confirm the deployed Git SHA matches.
   - Load the production URL in a browser; confirm the login page renders with no
     console errors.
3. **Planning Workspace frontend** (`aafc-tms-planning-workspace-preview` service)
   - Same pattern as step 2, mounted at `/planning`.
   - Confirm the deployed Git SHA matches.
   - Load `<production-url>/planning`; confirm it renders with no console errors.

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

Do not attempt a "fix forward" for a SEV1 under time pressure — roll back first, then
diagnose calmly against the rolled-back, stable state.
