# AAFC TMS — Release Stop Conditions and Rollback Plan

Phase 10 (Operational Release Gate). Defines exact stop conditions and rollback procedures.
Created: 2026-07-14.

---

## Known-Good Baselines (Before Release)

Record these immediately before production deployment:

| Service | Current deployment ID | Notes |
|---|---|---|
| `aafc-tms-backend` (production) | `20405760` | Pre-release baseline; record before deploying RC |
| `aafc-tms-frontend` (production) | `719cc4c8` | Pre-release baseline |
| `aafc-tms-planning-workspace-preview` (production) | Last successful (stale) | Record ID before deploying RC |
| Production Alembic revision before release | `x9y0z1a2b3c4` | No migration change expected; confirm matches RC |

---

## Stop Conditions

If ANY of the following are observed during or after deployment, STOP and execute the rollback procedure.

### Authentication and Security

| Condition | Detection | Threshold | Immediate Action |
|---|---|---|---|
| Authentication bypass (any user authenticated without correct code) | Login audit log shows no matching code; unexpected role | Any instance | Suspend all user access immediately; rollback; escalate |
| Cross-squadron data exposure (user sees another unit's records) | Support report; isolation spot-check failure | Any confirmed instance | Suspend access; rollback; investigate; notify affected units |
| Unauthorised Wing/National write | Audit log shows write from wrong scope | Any instance | Rollback; escalate |

### Data Integrity

| Condition | Detection | Threshold | Immediate Action |
|---|---|---|---|
| Data loss (records visible before deploy, missing after) | Support report; direct DB query | Any confirmed instance | Suspend access; restore from pre-deploy backup; rollback |
| Data corruption (records contain incorrect values after save) | Support report; cross-interface mismatch | Any confirmed instance | Suspend access; restore from backup |
| Unexplained duplicate operational records | Same parade night / session / curriculum item appears twice | More than 2 reports | Suspend writes; investigate; rollback if persists |
| Migration failure | Alembic revision mismatch; backend fails to start | Any | Rollback backend; restore database to pre-deploy state |
| Divergence between TMS and Planning Workspace | Same record shows different data in the two interfaces | Any confirmed instance | Suspend writes; investigate source |

### Application Availability

| Condition | Detection | Threshold | Immediate Action |
|---|---|---|---|
| Backend health check failing | `GET /api/health/ready` returns non-200 | >30 seconds sustained | Check Railway logs; rollback if not recovering |
| Persistent backend 500s | 500 response rate >5% for >60 seconds | 5%/60s | Rollback backend |
| Repeated login loop (successful login returns to login page) | Support reports; manual test | 3+ reports | Rollback frontend |
| Blank Dashboard on load | Dashboard renders no content, no error | 5+ reports across different users | Investigate; rollback if systemic |
| Blank Planning Workspace | `/planning` renders no content | 5+ reports | Rollback Planning Workspace |
| Database connection exhaustion | Railway Postgres connection count at limit; queries timing out | Postgres connections ≥90% of limit | Reduce backend replicas; rollback if not recovering |
| Severe sustained latency | P95 response time >10 seconds for >5 minutes | 10s P95 / 5 min | Investigate; rollback if not recovering |

### Operations

| Condition | Detection | Threshold | Immediate Action |
|---|---|---|---|
| Autosave failure (widespread) | Support reports of data not saving | 5+ reports from different units | Suspend writes; investigate; rollback |
| CEA import failure | All import attempts fail with error | All imports failing | Investigate; rollback if systemic |
| Backup workflow failure | `.github/workflows/backup-postgresql.yml` fails post-deploy | Any failure | Investigate cause; fix before next day's window |
| Inability to restore | Pre-deployment backup cannot be decrypted or restored | Any | See key custody checklist; escalate immediately |
| Rollback itself failing | Railway rollback command fails | Any | Follow manual rollback procedure below |

---

## Rollback Procedure

### Railway Rollback (Standard — under 2 minutes)

Railway stores all successful deployment history. Rolling back redeploys the previous successful deployment ID.

**Step 1: Identify the previous deployment ID** (recorded in the baselines table above)

**Step 2: Roll back each service in reverse order of deployment**

```bash
# Roll back Planning Workspace first (frontend, no migrations)
railway rollback <previous-pw-deployment-id> --service aafc-tms-planning-workspace-preview --environment production

# Roll back connected frontend
railway rollback <previous-frontend-deployment-id> --service aafc-tms-frontend --environment production

# Roll back backend last (may include migration implications)
railway rollback <previous-backend-deployment-id> --service aafc-tms-backend --environment production
```

**Step 3: Verify**
```bash
# Backend health
curl https://aafc-tms-backend-production.up.railway.app/api/health/ready

# Confirm Alembic revision
curl -H "Cookie: aafc_session=..." https://aafc-tms-backend-production.up.railway.app/api/system/status
```

**Step 4: Communicate**

Send the maintenance message (template below) to all users immediately after initiating rollback. Do not wait for rollback to complete before communicating.

### Database Rollback (Only if migration failure)

This release introduces NO new migrations. If a migration failure occurs, it means the database was already at `x9y0z1a2b3c4` and Alembic correctly identifies no action needed. A migration failure would indicate a configuration error, not a schema change.

If a data integrity issue requires restoring to the pre-deployment database state:
```bash
# 1. Trigger a fresh backup of the current (potentially corrupted) state for forensics
railway run python scripts/backup_trigger.py  # or trigger GitHub Actions workflow

# 2. Restore from the pre-deploy backup (taken in Phase 9 / rehearsal)
# Follow the runbook at deployment/backup-dr.md
# This is a DRASTIC action — confirm with the authorised owner before executing
```

---

## Maintenance Message Template

Send via the official communication channel when access is suspended:

```
Subject: AAFC TMS — Temporary Service Interruption

The AAFC Training Management System is temporarily unavailable for maintenance.

We are aware of the issue and are working to restore service.

Expected restoration: [TIME] AWST / AEST

No training data has been lost. Your planning year, sessions, facilitators,
and activities are safe.

If you need to access your training program urgently, please contact
[SUPPORT CONTACT].

We will send an update when service is restored.
```

---

## Incident Ownership

| Role | Responsibility | Contact |
|---|---|---|
| Release controller | Initiates rollback decision; communicates with users | ___________________ |
| System engineer | Executes Railway rollback commands | ___________________ |
| Database owner | Authorises and executes database restore if required | ___________________ |
| Support lead | Handles user reports and triage during incident | ___________________ |

---

## Evidence to Preserve During an Incident

Before executing any rollback:
1. Screenshot or download Railway deployment logs for the failed deployment
2. Record the exact error message or symptom
3. Note the Railway deployment ID of the failed deployment
4. Note the timestamp of first reported failure
5. Save any relevant API response bodies
6. Note which users and squadrons were affected

All evidence goes into the incident log (`17_incident_log_template.md` / actual incident file).

---

## Rollback Rehearsal

A staging rollback rehearsal must be completed before production deployment. Record:

| Item | Value |
|---|---|
| Rehearsal date | PENDING |
| Staging deployment rolled back from | — |
| Staging deployment rolled back to | — |
| Rollback duration | — |
| Health check post-rollback | — |
| Data verified after rollback | — |
| Rehearsal result | PENDING |

**Do not proceed with production deployment until the rollback rehearsal is marked complete.**
