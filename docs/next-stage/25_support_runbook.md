# AAFC TMS — Support Runbook and Release Process

Phase 25 — Next-Stage Development Program.
Written 2026-07-16. Audience: System Admin, Wing Admin, and non-developer operators.

This document answers two questions:
1. **Who does what when something goes wrong?** (Support runbook)
2. **How is a new version released?** (Release process)

It does NOT require developer access. Every step either has a Railway/GitHub UI action
or a `curl` / `railway` CLI command that a system admin can run without editing code.

---

## Part 1 — Named Ownership

| Role | Person / Team | Contact |
|---|---|---|
| **System admin** (highest-privilege account in the TMS) | _(to be named by AAFC governance)_ | _(add contact)_ |
| **Wing admin — 7 Wing** | _(to be named by 7 Wing SOCAD)_ | _(add contact)_ |
| **Developer on-call** | _(add GitHub username)_ | _(add contact)_ |
| **Railway account owner** | _(to be named)_ | Railway project: `exemplary-emotion` |
| **Backup key custodian** | _(to be named)_ | Holds GPG private key + passphrase |
| **GitHub repository admin** | _(to be named)_ | `AAFC_TMS` repository |

Governance decision required: name each role above before V1 operational go-live.
Until these cells are filled in, the system has no defined escalation path.

---

## Part 2 — Incident Classification

| Level | Condition | Response time | Notified |
|---|---|---|---|
| **P1 — Production down** | `/api/health` returns non-200 or no response | Immediate | Developer on-call + System admin |
| **P1 — Security** | IDOR, data exposure, authentication bypass suspected | Immediate | System admin + developer on-call; isolate first |
| **P2 — Feature broken** | A core workflow is failing for all users in a role | Same business day | Developer on-call |
| **P3 — Degraded** | A secondary feature is broken or slow | Next business day | Developer on-call |
| **P4 — Cosmetic / question** | UI label wrong, user confusion, feature request | Next sprint | Log in GitHub Issues |

**What "respond" means:** within the response-time window, the responsible person
acknowledges the incident and begins diagnosis. Resolution time is separate.

---

## Part 3 — First Responder Checklist

For any P1 or P2 incident, work through this checklist in order before escalating:

### 3.1 Check system status

```bash
# Production backend
curl -s https://aafc-tms-backend-production.up.railway.app/api/health
# Expected: {"status": "ok"}

curl -s https://aafc-tms-backend-production.up.railway.app/api/health/ready
# Expected: {"status": "ready", "squadrons": 16}
```

If both return 200: the backend is up. Problem may be frontend or user-specific.
If `/api/health` returns non-200 or times out: proceed to 3.2.

### 3.2 Check Railway service status

1. Open Railway dashboard → project `exemplary-emotion` → `production` environment.
2. Check `aafc-tms-backend` service — is it **Running** or in error state?
3. Click the service → **Deployments** tab → check the last deployment log.
4. Look for: database connection failures, `alembic upgrade head` errors, OOM kills.

Common cause of backend down: failed database migration on deploy. See §5.1.

### 3.3 Check maintenance mode

```bash
# System admin token required
TOKEN="<your-system-admin-bearer-token>"
curl -s https://aafc-tms-backend-production.up.railway.app/api/system/maintenance/status \
  -H "Authorization: Bearer $TOKEN"
```

If `maintenance_active: true` and this is unintended: see §5.2 to turn it off.

### 3.4 Check recent audit log

```bash
curl -s "https://aafc-tms-backend-production.up.railway.app/api/audit?limit=20" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Look for unexpected `action: delete`, `action: reset_codes`, or auth failures in
the last 20 entries. If you see suspicious entries, escalate to P1 Security.

### 3.5 Check Railway logs

In Railway → service → **Logs** tab. Look for stack traces or `ERROR:` lines.
The access log format is:
```
{"method":"POST","path":"/api/auth/login","status":403,"dur_ms":12.3,"client":"1.2.3.4","req_id":"<uuid>"}
```
Use the `req_id` to find the full request context if a user reports an error code.

---

## Part 4 — Common Issues and Fixes

### 4.1 User reports "Access Denied" (403)

- Check the user's role in Account Management.
- Confirm they are in the correct squadron/wing scope.
- Check if their account is locked (visible in Account Management → user detail).
- Check if maintenance mode is on (§3.3).

### 4.2 User reports "Session expired" or can't log in

- Confirm the access code is correct (System Admin → Account Management → copy code to user).
- If the user changed their own code and lost it, System Admin can generate a new one.
- Check if rate limiter is blocking them (too many failed attempts → see lockout in audit log).

### 4.3 Planning Workspace shows "Session not found"

- The user opened a new browser tab without an active TMS session.
- Direct them to: log into the main TMS first, then click "Planning Workspace ↗" from the nav.
- The shared session cookie will carry over automatically.

### 4.4 Connected-frontend shows blank page / console error

- Open browser DevTools → Console tab → note the error.
- Check if `AAFC_API_BASE` is set correctly in Railway (wrong URL → all API calls fail).
- Reload the page with Ctrl+Shift+R (hard reload, no cache).

### 4.5 Reports showing stale or unexpected data

- Reports are generated in real time from the current database state.
- If data looks wrong, check the underlying records (parade nights, sessions, facilitators) first.
- Reports do not cache — if the records are correct, the report is correct.

---

## Part 5 — Escalation Procedures

### 5.1 Failed database migration on deploy

**Symptom:** Backend is down after a deploy. Deployment log shows:
`alembic upgrade head` error or `OperationalError: no such column`.

**Do NOT retry the deploy immediately.**

Steps:
1. Note the failed migration revision from the log.
2. Contact the developer on-call — this requires developer action to roll back or fix the migration.
3. If the previous version was stable, in Railway → Deployments → click the last good deploy → **Redeploy**.
4. After redeploying the previous version, verify `/api/health/ready` returns 200.
5. Do not merge or deploy new code until the migration issue is diagnosed.

### 5.2 Turn maintenance mode off

Maintenance mode may have been left on after a planned outage:

```bash
curl -X POST https://aafc-tms-backend-production.up.railway.app/api/system/maintenance/off \
  -H "Authorization: Bearer $SYSTEM_ADMIN_TOKEN" \
  -H "Content-Type: application/json"
```

Expected response: `{"ok": true}`.

### 5.3 Security incident — suspected IDOR or data exposure

1. **Isolate immediately:** turn maintenance mode ON.
   ```bash
   curl -X POST https://aafc-tms-backend-production.up.railway.app/api/system/maintenance/on \
     -H "Authorization: Bearer $SYSTEM_ADMIN_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"message": "Temporary maintenance — please try again shortly"}'
   ```
2. Pull the audit log for the last 24 hours and preserve it offline.
3. Notify developer on-call and Wing Admin within 30 minutes.
4. Do NOT turn maintenance mode off until the developer has reviewed the log.
5. If cadet personal data may have been exposed, follow your organization's data breach policy.

### 5.4 Production database data loss

If rows are missing or corrupted and a backup restore is needed:
1. Follow `deployment/backup-dr.md` — full restore procedure.
2. Do not restore against the live production database — restore to a new database first, verify integrity, then cut over.
3. Notify governance authority before any data restoration action.

---

## Part 6 — Release Process (non-developer operator reference)

A release involves: code merged → tested → deployed to staging → approved → deployed to production.
This section covers the operator's actions, not the developer's.

### 6.1 What triggers a release

| Trigger | Who initiates |
|---|---|
| Security defect fix | Developer + System Admin approval |
| Bug fix requiring deployment | Developer + Wing Admin acknowledgement |
| New feature (Level A, B, or C) | Developer + governance approval per Phase plan |

### 6.2 Before any production deployment

The developer must provide:
- [ ] Passing test suite (1553+ tests, 0 failures)
- [ ] Migrations tested on staging with rollback plan
- [ ] Security grep results showing 0 matches for known violations
- [ ] Changelog entry describing the change
- [ ] Smoke test result from staging

The operator (System Admin or Wing Admin) must confirm:
- [ ] Backup of current production DB taken and verified within 24 hours
- [ ] Maintenance window communicated to known users if downtime expected
- [ ] Rollback plan understood: which previous Railway deployment to redeploy if needed

### 6.3 Executing a production deployment

Deployments are triggered by Railway's Git integration (push to production branch) or
manually via Railway dashboard → Deployments → Deploy.

The developer handles the Git push. The operator's role is:
1. Confirm the backup is current before deployment starts.
2. Monitor `/api/health/ready` during and after deployment.
3. Run the D7 smoke test checklist (see `docs/beta/D7_smoke_test_checklist.md`) after deployment.
4. Confirm in writing (Slack / email) that the deployment is GO or HOLD.

### 6.4 If a deployment needs to be rolled back

1. In Railway → `production` environment → `aafc-tms-backend` service → Deployments.
2. Find the last known-good deployment (before the current deploy).
3. Click **Redeploy** on that deployment.
4. Verify `/api/health/ready` returns 200 with the expected squadron count.
5. Notify the developer that the rollback was executed and why.

### 6.5 Deploying to staging (safe to do without governance approval)

Staging is the `staging` environment in Railway. It points to a separate PostgreSQL
database with synthetic data only. Deploying to staging does not affect production.

To deploy to staging: developer pushes to the relevant branch or manually triggers
a Railway redeploy on the staging service. The operator does not need to approve
staging deployments.

---

## Part 6A — Scaling Constraints (read before changing Railway env vars)

### GUNICORN_WORKERS cap

**Do not raise `GUNICORN_WORKERS` beyond 2 in production without first implementing a
DB-backed general API rate limiter** (Option A in `docs/next-stage/15_rate_limiting_assessment.md`).

**Why:** The general API rate limiter (`check_api_rate` in `security.py`) uses an in-memory
dict that is per-worker, not shared across gunicorn workers. At `GUNICORN_WORKERS=2`, the
effective per-IP limit is ~600 req/60 s (2× the configured 300). At `GUNICORN_WORKERS=4`
it degrades to ~1 200 req/60 s — insufficient to throttle automated enumeration.

The **login rate limiter** (`IpLoginAttempt` table) is DB-backed and is NOT affected by
worker count — it enforces exactly 5 attempts per 300 s per IP regardless of how many
workers are running.

**Current production default:** `GUNICORN_WORKERS` is unset → defaults to 2. Both the staging
and production Railway services use `docker-entrypoint-staging.sh` as the container entrypoint
(the filename is historical — it is not staging-only). To confirm the current value: Railway
dashboard → production environment → `aafc-tms-backend` service → Variables tab → search
`GUNICORN_WORKERS`. If the variable is absent, the default of 2 is active. To change it:
Variables → set `GUNICORN_WORKERS`.

**Important — horizontal scaling also degrades the limit:** If Railway horizontal scaling is
enabled (more than one backend replica), the effective per-IP limit degrades by an additional
factor equal to the replica count (e.g., 2 replicas × 2 workers = ~1 200 req/60 s). Contact
the developer on-call before enabling horizontal scaling.

**Before raising above 2:** implement the DB-backed rate limiter or Redis counter and
document the new effective limit in this runbook. See `15_rate_limiting_assessment.md`
for implementation options and effort estimates.

---

## Part 7 — Routine Maintenance Schedule

| Task | Frequency | Who | Where |
|---|---|---|---|
| Verify daily backup ran | Weekly | System Admin | GitHub Actions → backup-postgresql |
| Verify weekly restore test passed | Weekly | System Admin | GitHub Actions → test-restore-postgresql |
| DR rehearsal (full) | Quarterly | System Admin | Follow `docs/next-stage/19_disaster_recovery_rehearsal.md` |
| Access code audit | Monthly | Wing Admin | Account Management → review all accounts |
| GPG key rotation | Per key expiry (2y) | System Admin | Follow `deployment/backup-dr.md` §Key rotation |
| Railway billing review | Monthly | Railway account owner | Railway dashboard |

---

## Part 8 — System Admin Token (how to get one)

The System Admin token is needed for several of the `curl` commands above.

1. Open the main TMS frontend.
2. Log in with the `system_admin` access code.
3. Open browser DevTools → Application → Session Storage → find `aafc_token`.
4. Copy the token value. It expires after 24 hours.
5. Never paste this token into an untrusted terminal, email, or chat.

Alternatively, use the Planning Workspace Settings page → it shows the current auth
state and can be used to log in and obtain a token via the network tab.

---

## Revision History

| Date | Change | Author |
|---|---|---|
| 2026-07-16 | Initial version (Phase 25) | Next-Stage Program |
| 2026-08-12 | Added Part 6A: GUNICORN_WORKERS cap + rate limiting constraint | Next-Stage Program |
