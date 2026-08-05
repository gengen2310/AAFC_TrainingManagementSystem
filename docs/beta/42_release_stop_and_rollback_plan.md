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

**CORRECTION (2026-08-05, from a real Gate 8 rehearsal — see REM-78 in
`docs/remediation/master_gap_register.csv`)**: the version of this section below dated 2026-07-14
assumed `railway rollback <id>` exists as a CLI command and that a code-only rollback is always
safe. Neither is true. `railway rollback` is not a real command (confirmed via `railway --help` —
the only options are `railway deployment redeploy` [latest deployment only, no target-ID selection]
or the GraphQL `deploymentRedeploy(id)` mutation). And a code-only rollback **crash-loops the backend**
if any migration ran between the rollback target and the current deployment — reproduced live on
staging 2026-08-05: `alembic upgrade head` on the older codebase fails with `Can't locate revision
identified by '<newer-id>'` because that codebase's migration graph has no entry for a revision
created after it was cut. **Step 0 below is now mandatory, not optional.**

### Step 0 — Check for migrations since the rollback target (MANDATORY, do this first)

```bash
cd backend
git log --oneline <previous-good-commit>..HEAD -- alembic/versions/
```

- **No output (no new migration files)** → code-only rollback is safe. Proceed to Step 1.
- **Any output (one or more new migration files)** → a code-only rollback WILL crash-loop the
  backend. Do not run Step 1 yet. Choose one:
  - **(a) Preferred — roll forward with a fix instead of rolling back.** If the incident is caused
    by application logic, not the schema change itself, a small forward-fix commit (deployed the
    normal way) resolves it without ever taking the database out of sync with what's been deployed
    to it. This is almost always faster and safer than a coordinated rollback.
  - **(b) Coordinated rollback — only if (a) is not viable.** Roll back the database schema and the
    application code together, in this order:
    1. `cd backend && source .venv/bin/activate && railway run --service aafc-tms-backend --environment production alembic downgrade <previous-good-revision>` — confirm the migration(s) being undone have real, safe `downgrade()` functions (check the migration file itself; a migration that only adds nullable columns, like REM-77/v47, downgrades safely by dropping them — but not every migration is this simple, e.g. one with a data backfill may not be cleanly reversible. If any migration in the range lacks a safe downgrade, (b) is not available — use (a) instead).
    2. Only after the downgrade succeeds and is verified (`railway run ... alembic current`), redeploy the older application code per Step 1 below.
  - Do not attempt a "partial" rollback (app code back, schema left forward, or vice versa) outside
    of these two options — that is exactly the state that crash-loops.

### Railway Rollback (Standard — under 2 minutes, once Step 0 confirms it's safe)

**Step 1: Identify the previous deployment** (recorded in the baselines table above, or via
`railway deployment list --service <svc> --environment production --json`)

**Step 2: Roll back each service in reverse order of deployment**, using `railway up` from a
worktree/checkout of the target commit (the mechanism actually proven working this session — not
the nonexistent `railway rollback` command):

```bash
# Roll back Planning Workspace first (frontend, no migrations)
git worktree add --detach /tmp/rollback-pw <previous-pw-good-commit>
cd /tmp/rollback-pw/frontend && railway up --detach -m "ROLLBACK: <reason>" \
  --service aafc-tms-planning-workspace-preview --environment production

# Roll back connected frontend
git worktree add --detach /tmp/rollback-fe <previous-frontend-good-commit>
cd /tmp/rollback-fe/connected-frontend && railway up --detach -m "ROLLBACK: <reason>" \
  --service aafc-tms-frontend --environment production

# Roll back backend last — ONLY if Step 0 confirmed no migration in the range,
# or Step 0(b)'s coordinated downgrade has already completed and been verified
git worktree add --detach /tmp/rollback-be <previous-backend-good-commit>
cd /tmp/rollback-be/backend && railway up --detach -m "ROLLBACK: <reason>" \
  --service aafc-tms-backend --environment production

# Clean up worktrees once verified
git worktree remove /tmp/rollback-pw --force
git worktree remove /tmp/rollback-fe --force
git worktree remove /tmp/rollback-be --force
```

**Step 3: Verify**
```bash
# Backend health
curl https://aafc-tms-backend-production.up.railway.app/api/health/ready

# Confirm the backend actually started (not crash-looping) — check for repeated
# "Starting Container" / Alembic FAILED lines, which the health check alone can
# mask for a few seconds if the previous container is still draining
railway logs --service aafc-tms-backend --environment production --lines 50

# Confirm Alembic revision matches expectation
railway run --service aafc-tms-backend --environment production alembic current
```

**Step 4: Communicate**

Send the maintenance message (template below) to all users immediately after initiating rollback. Do not wait for rollback to complete before communicating.

### Database Rollback (only when Step 0 found a migration in range and forward-fix isn't viable)

See Step 0(b) above for the coordinated procedure. Do not run `alembic downgrade` against
production without first confirming every migration being undone has a genuinely safe `downgrade()`
— read the migration file, don't assume. If a data integrity issue (not just a schema mismatch)
requires restoring to the pre-deployment database state entirely:
```bash
# 1. Trigger a fresh backup of the current (potentially corrupted) state for forensics
railway run python scripts/backup_trigger.py  # or trigger GitHub Actions workflow

# 2. Restore from the pre-deploy backup (taken in Phase 9 / rehearsal, or the most
# recent daily backup — see docs/beta/32_final_stress_and_resilience_report.md for
# the proven restore procedure, which includes an application-level verification step)
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
| Rehearsal date | 2026-08-05 (full re-run; see `docs/beta/41_deployment_rehearsal.md` for the 2026-07-14 first rehearsal and today's re-rehearsal detail) |
| Staging deployment rolled back from | `4d1bc434` (main @ `5414abf`, includes REM-77 migration `5a195a98148a`) |
| Staging deployment rolled back to | `0fdd21e` (pre-REM-77, does not know about the migration) |
| Rollback duration | ~1–2 min to redeploy old code; service was down (502, crash-loop) for the full duration until the forward redeploy completed |
| Health check post-rollback (to the OLD commit) | **502 `Application failed to respond`, crash-looping** — this is the REM-78 finding, not a rehearsal failure to execute, a genuine discovered defect in the naive rollback path |
| Data verified after rollback | N/A — backend never came up; database itself was untouched (no data loss, no data risk — only the application container failed to start) |
| Recovery action | Immediately redeployed current head (`main` @ `3184766` at the time) — `railway up` from the real branch, ~1–2 min, restored `200 {"status":"ready"}` and both REM-77 endpoints re-confirmed 200 |
| Rehearsal result | **FAIL for naive code-only rollback when a migration is in range (REM-78, open)**; **PASS for the underlying deploy mechanism** (both the broken and the fixed deploys completed and were verifiable via health check + logs within the expected ~1-2 minute window) |

**This rehearsal is exactly why Gate 8 exists**: it found a real gap (no migration-awareness in the
rollback procedure) before it was needed in a genuine incident, not during one. Production was never
touched by this rehearsal — the FAIL above is a staging-only, fully-recovered-within-minutes finding.
Do not treat "rehearsal executed and found a real problem" as equivalent to "rollback procedure is
production-ready" — REM-78 must be resolved (Step 0 above adopted as mandatory practice, ideally with
the entrypoint fast-fail improvement also implemented) before this plan can be considered complete.
