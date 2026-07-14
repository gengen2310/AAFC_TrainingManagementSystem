# AAFC TMS — Deployment and Rollback Rehearsal

Phase 9 (Operational Release Gate). Demonstrates that the deploy and rollback procedure works before production.
Created: 2026-07-14.

---

## Purpose

Before executing a production deployment, all deployment commands must be verified in staging. This document records the staging rehearsal.

**Requirement**: This rehearsal must be completed before the production deployment is approved.

---

## Pre-Rehearsal State

The staging environment (`77a45568`) should have:
- Synthetic data only (no real user data)
- Release candidate commit `e918f3e` either deployed or one version behind (to rehearse deploying it)
- A known Alembic revision in place to verify migration applies correctly

---

## Deployment Rehearsal Steps

### Step D1 — Verify staging state before deploy

```bash
# Confirm current alembic revision in staging
curl -H "Cookie: [staging-system-admin-cookie]" \
  https://aafc-tms-backend-staging.up.railway.app/api/system/status

# Confirm health
curl -s https://aafc-tms-backend-staging.up.railway.app/api/health/ready
```

Expected: `{"status":"ready","squadrons":16}` (or synthetic count)

**Result**: ___________________
**Timestamp**: ___________

---

### Step D2 — Deploy release candidate to staging

```bash
# If using Railway CLI:
railway environment staging
railway up --service aafc-tms-backend

# Alternatively, push to the staging branch if Railway CI/CD is configured
git push origin release/beta-2026-07-14:staging
```

**Railway deployment ID**: ___________________
**Deployment started**: ___________
**Deployment completed**: ___________

---

### Step D3 — Verify migration ran

After deployment completes:

```bash
curl -H "Cookie: [staging-system-admin-cookie]" \
  https://aafc-tms-backend-staging.up.railway.app/api/system/status
```

Expected: `"alembic_revision": "x9y0z1a2b3c4"` (v36)

**Result**: ___________________
**Migration applied**: YES / NO

---

### Step D4 — Verify backend health post-deploy

```bash
curl -s https://aafc-tms-backend-staging.up.railway.app/api/health/ready
```

Expected: `{"status":"ready","squadrons":16}`

**Result**: ___________________

---

### Step D5 — Verify connected frontend

```bash
curl -s -o /dev/null -w "%{http_code}" \
  https://aafc-tms-frontend-staging.up.railway.app
```

Expected: 200

**Result**: ___________________

---

### Step D6 — Verify Planning Workspace

```bash
curl -s -o /dev/null -w "%{http_code}" \
  https://aafc-tms-planning-workspace-preview-staging.up.railway.app/planning
```

Expected: 200

**Result**: ___________________

---

### Step D7 — Smoke test in staging

Complete the smoke test sequence from `48_final_production_smoke_test.md` against staging.

**Smoke test result**: PASS / FAIL
**Failed steps**: ___________________
**Timestamp**: ___________

---

## Rollback Rehearsal Steps

After a successful deploy rehearsal, rehearse the rollback while in staging.

### Step R1 — Identify previous deployment

```bash
# List recent Railway deployments for staging backend
railway deployments --service aafc-tms-backend
```

**Previous deployment ID**: ___________________

---

### Step R2 — Execute rollback

```bash
# Roll back to previous deployment
railway rollback [previous-deployment-id] --service aafc-tms-backend
```

**Rollback started**: ___________
**Rollback completed**: ___________

---

### Step R3 — Verify post-rollback health

```bash
curl -s https://aafc-tms-backend-staging.up.railway.app/api/health/ready
```

**Result**: ___________________

---

### Step R4 — Verify Alembic revision after rollback

If the rollback included a migration, verify the revision has changed:

```bash
curl -H "Cookie: [staging-system-admin-cookie]" \
  https://aafc-tms-backend-staging.up.railway.app/api/system/status
```

**Result**: ___________________

---

### Step R5 — Re-deploy release candidate

After confirming rollback works, re-deploy the release candidate so staging is back on `e918f3e`:

```bash
railway up --service aafc-tms-backend
# or push to staging branch
```

**Re-deployment ID**: ___________________
**Post-rollback-rehearsal health**: ___________________

---

## Rehearsal Summary

| Step | Description | Result | Timestamp |
|---|---|---|---|
| D1 | Staging pre-deploy health | | |
| D2 | Deploy RC to staging | | |
| D3 | Migration verified | | |
| D4 | Backend health post-deploy | | |
| D5 | Connected frontend 200 | | |
| D6 | Planning Workspace 200 | | |
| D7 | Smoke test pass | | |
| R1 | Previous deployment identified | | |
| R2 | Rollback executed | | |
| R3 | Post-rollback health | | |
| R4 | Alembic revision after rollback | | |
| R5 | RC re-deployed post rehearsal | | |

**Overall rehearsal result**: PASS / FAIL
**Performed by**: ___________________
**Date**: ___________

---

## Readiness Gate

This rehearsal must be completed with all steps PASS before production deployment is approved.

**Gate status**: PENDING — MANUAL EXECUTION REQUIRED

Once this document has been completed with all PASS results, update `12_full_beta_release_readiness.md` and `35_release_evidence_chain.md` Link 11 accordingly.
