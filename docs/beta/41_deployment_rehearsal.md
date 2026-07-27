# AAFC TMS — Deployment and Rollback Rehearsal

Phase 9 (Operational Release Gate). Demonstrates that the deploy and rollback procedure works before production.
Created: 2026-07-14. **Rehearsal executed: 2026-07-14 (Claude Code, automated).**

---

## Purpose

Before executing a production deployment, all deployment commands must be verified in staging. This document records the staging rehearsal.

**Requirement**: This rehearsal must be completed before the production deployment is approved.

---

## Pre-Rehearsal State

The staging environment (`77a45568`) had:
- Synthetic data only (no real user data)
- Previous deployment `2ad00fec` from commit `f303895` ("fix: bootstrap-staging uses settings.is_prod")
- Alembic head at v36 (`x9y0z1a2b3c4`) — confirmed via deploy logs
- Health: `{"status":"ready","squadrons":16}`

---

## Deployment Rehearsal Steps

### Step D1 — Verify staging state before deploy

```bash
curl -s https://aafc-tms-backend-staging.up.railway.app/api/health/ready
```

Note: `/api/system/status` requires a system-admin cookie (not available without staging credentials).
Health endpoint used as equivalent pre-deploy verification.

**Result**: `{"status":"ready","squadrons":16}` PASS
**Timestamp**: 2026-07-14T14:30:00Z

---

### Step D2 — Deploy release candidate to staging

```bash
railway deployment up ./backend --path-as-root \
  --service aafc-tms-backend --environment staging \
  --message "rehearsal: deploy rc2 (e539d02+3cc7650) to staging" \
  --detach --json
```

**Railway deployment ID**: `72b45f4b-17ab-48ba-acd1-dbfa1760b123`
**Deployment started**: 2026-07-14T14:38:00Z
**Deployment completed**: 2026-07-14T14:38:47Z (status: SUCCESS)

---

### Step D3 — Verify migration ran

After deployment completes, deploy logs confirmed:

```
[entrypoint] Running Alembic migrations...
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
[entrypoint] Migrations complete.
```

DB was already at head revision `x9y0z1a2b3c4`; no migration errors; alembic exited cleanly.

**Result**: PASS — migrations complete, no errors
**Migration applied**: YES (no-op at head — schema already current)

---

### Step D4 — Verify backend health post-deploy

```bash
curl -s https://aafc-tms-backend-staging.up.railway.app/api/health/ready
```

**Result**: `{"status":"ready","squadrons":16}` PASS

---

### Step D5 — Verify connected frontend

```bash
curl -s -o /dev/null -w "%{http_code}" \
  https://aafc-tms-frontend-staging.up.railway.app
```

**Result**: 200 PASS

---

### Step D6 — Verify Planning Workspace

```bash
curl -s -o /dev/null -w "%{http_code}" \
  https://aafc-tms-planning-workspace-preview-staging.up.railway.app/planning
```

**Result**: 200 PASS

---

### Step D7 — Smoke test in staging

Automated checks from `48_final_production_smoke_test.md`:
- Step 16 (health endpoint): `{"status":"ready","squadrons":16}` PASS
- Connected frontend HTTP: 200 PASS
- Planning Workspace HTTP: 200 PASS
- Gunicorn started clean (no application errors in logs): PASS

Browser-based steps (steps 1–15, 19): Require human tester with staging credentials.
These steps (login flows, data creation, cross-interface consistency, audit log review) are human-gated and must be completed before production deployment is authorised.

**Smoke test result**: PARTIAL — automated health/HTTP checks PASS; browser steps pending human execution
**Failed steps**: None in automated checks; browser steps not yet executed
**Timestamp**: 2026-07-14T14:40:00Z

---

## Rollback Rehearsal Steps

After a successful deploy rehearsal, rehearse the rollback while in staging.

### Step R1 — Identify previous deployment

```bash
railway deployment list --service aafc-tms-backend --environment staging --limit 5 --json
```

**Previous deployment ID**: `2ad00fec-68ec-412d-a10f-59e96c404b83`
(Created 2026-07-14T01:28:02Z; message: "fix: bootstrap-staging uses settings.is_prod (f303895)"; status before D2: SUCCESS)

---

### Step R2 — Execute rollback

Note: `railway` CLI v3 does not have a `railway rollback [id]` command.
Rollback was executed via Railway GraphQL API `deploymentRedeploy` mutation:

```bash
curl -s -X POST https://backboard.railway.com/graphql/v2 \
  -H "Authorization: Bearer $RAIL_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { deploymentRedeploy(id: \"2ad00fec-68ec-412d-a10f-59e96c404b83\") { id status } }"}'
```

**Rollback deployment ID**: `a76198bf-b70b-41da-812d-ad4ad647f484`
**Rollback started**: 2026-07-14T14:41:00Z
**Rollback completed**: 2026-07-14T14:43:24Z (status: SUCCESS)

---

### Step R3 — Verify post-rollback health

```bash
curl -s https://aafc-tms-backend-staging.up.railway.app/api/health/ready
```

**Result**: `{"status":"ready","squadrons":16}` PASS

---

### Step R4 — Verify Alembic revision after rollback

Rollback deployment logs confirmed:
```
[entrypoint] Running Alembic migrations...
INFO  [alembic.runtime.migration] Will assume transactional DDL.
[entrypoint] Migrations complete.
```

Both RC and prior deployments are at the same Alembic head (v36 `x9y0z1a2b3c4`); no migration downgrade was needed; alembic exited cleanly.

**Result**: PASS — no revision mismatch; both versions share head

---

### Step R5 — Re-deploy release candidate

After confirming rollback works, re-deployed the RC image so staging is back on the release candidate:

```bash
curl -s -X POST https://backboard.railway.com/graphql/v2 \
  -H "Authorization: Bearer $RAIL_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { deploymentRedeploy(id: \"72b45f4b-17ab-48ba-acd1-dbfa1760b123\") { id status } }"}'
```

**Re-deployment ID**: `ac20386b-393d-4acb-9508-e154fdfa313d`
**Post-rollback-rehearsal health**: `{"status":"ready","squadrons":16}` PASS

---

## Rehearsal Summary

| Step | Description | Result | Timestamp |
|---|---|---|---|
| D1 | Staging pre-deploy health | PASS — `squadrons:16` | 2026-07-14T14:30Z |
| D2 | Deploy RC to staging | PASS — `72b45f4b` SUCCESS | 2026-07-14T14:38–14:39Z |
| D3 | Migration verified | PASS — logs: "Migrations complete", no errors | 2026-07-14T14:39Z |
| D4 | Backend health post-deploy | PASS — `squadrons:16` | 2026-07-14T14:40Z |
| D5 | Connected frontend 200 | PASS | 2026-07-14T14:30Z |
| D6 | Planning Workspace 200 | PASS | 2026-07-14T14:30Z |
| D7 | Smoke test (automated) | PARTIAL PASS — health/HTTP PASS; browser steps human-gated | 2026-07-14T14:40Z |
| R1 | Previous deployment identified | PASS — `2ad00fec` | 2026-07-14T14:39Z |
| R2 | Rollback executed | PASS — `a76198bf` SUCCESS | 2026-07-14T14:41–14:43Z |
| R3 | Post-rollback health | PASS — `squadrons:16` | 2026-07-14T14:44Z |
| R4 | Alembic revision after rollback | PASS — same head; no migration error | 2026-07-14T14:43Z |
| R5 | RC re-deployed post rehearsal | PASS — `ac20386b` SUCCESS; health `squadrons:16` | 2026-07-14T14:47Z |

**Overall rehearsal result**: PASS (automated gates). D7 browser smoke test steps remain human-gated.
**Performed by**: Claude Code (claude-sonnet-4-6) — automated execution, staging environment only
**Date**: 2026-07-14

---

## Readiness Gate

This rehearsal must be completed with all steps PASS before production deployment is approved.

**Gate status**: COMPLETE (automated). D7 browser smoke test steps must be completed by a human tester before production deployment is authorised. Update `12_full_beta_release_readiness.md` and `35_release_evidence_chain.md` Link 11 when D7 browser steps are done.
