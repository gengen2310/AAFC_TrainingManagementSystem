# AAFC TMS — All-at-Once Release Control

Phase 16 (Operational Release Gate). Preparation and live monitoring for the simultaneous release to ~100 users.
Created: 2026-07-14.

---

## Release Model

Approximately 100 users across 16 squadrons receive access codes simultaneously. This creates a login surge over a short window (likely 5–30 minutes as users across multiple time zones open their codes).

This plan prepares for and monitors that event.

---

## Pre-Distribution Checklist (Complete before sending any codes)

| Action | Owner | Status |
|---|---|---|
| Production backend: warm and healthy | Release controller | PENDING |
| Connected frontend: warm (at least one recent request) | Release controller | PENDING |
| Planning Workspace: warm (load the `/planning` page once) | Release controller | PENDING |
| Database connections: <30 (baseline) | Release controller | PENDING |
| Smoke test (`48_final_production_smoke_test.md`): PASS | Release controller | PENDING |
| Latest backup: succeeded (GitHub Actions green) | Release controller | PENDING |
| Monitoring window: open (`43_release_monitoring_plan.md`) | Release controller | PENDING |
| Incident log: ready | Release controller | PENDING |
| Rollback commands: on screen | System engineer | PENDING |
| Support channel: active | Support lead | PENDING |
| No deployment in progress | Release controller | PENDING |
| No backup running | Release controller | PENDING |
| No large import or migration running | Release controller | PENDING |
| Release communication sent to correct distribution list | Release controller | PENDING |
| Responsible release controller confirmed and available | Named person | ___________________ |

---

## Warming the System

Before distributing access codes, warm the backend to avoid cold-start latency hitting the first users:

```bash
# Warm backend (run 5 requests before users arrive)
for i in 1 2 3 4 5; do
  curl -s https://aafc-tms-backend-production.up.railway.app/api/health/ready
  sleep 2
done

# Warm connected frontend
curl -s -o /dev/null https://aafc-tms-frontend-production.up.railway.app

# Warm Planning Workspace
curl -s -o /dev/null https://aafc-tms-planning-workspace-preview-production.up.railway.app/planning
```

---

## During Release — First 60 Minutes

### Login Rate Monitoring

| Time window | Action |
|---|---|
| T+0 to T+5 min | Watch Railway backend logs for login requests; confirm users are authenticating |
| T+5 to T+15 min | Check database connections (expect gradual rise as sessions open) |
| T+15 min | First isolation spot-check (see below) |
| T+30 min | Second isolation spot-check; review error rates |
| T+60 min | Third spot-check; review support channel; update monitoring log |

### Isolation Spot Checks

At T+15, T+30, and T+60 minutes:

1. Log in as a known test sqn_general user for one squadron
2. Confirm only that squadron's data is visible
3. Attempt to access another squadron's planning year directly (GET request with known UUID)
4. Confirm: 403 response
5. Log out
6. Log in as a different squadron's sqn_admin
7. Confirm: sees only their unit's data
8. Record result: PASS / FAIL

### Data Consistency Checks

At T+30 and T+60 minutes:

1. Log in as sqn_admin for a test squadron
2. Check Planning Workspace shows the same data as the connected TMS
3. Confirm a known curriculum item appears in both interfaces

---

## Actions to AVOID During Release Window

The following actions should NOT be taken while the login surge is active:

| Action | Why to avoid |
|---|---|
| Deploying any code change | Restarts the backend; interrupts active sessions |
| Running database migrations | Could lock tables or restart connection pool |
| Running backup (if it uses a Supabase connection) | Competes for connections |
| Running large imports from the admin panel | Competes for database capacity |
| Changing Railway environment variables | Triggers service restart |
| Updating CORS or cookie settings | Can invalidate active sessions |

---

## Concurrent Access Considerations

With ~100 users across 16 squadrons:
- Expected peak: 50–70 simultaneous HTTP requests during login surge
- Database connections: expect 20–40 during peak (well within Railway Postgres limits)
- Each squadron's data is independent — no cross-squadron lock contention expected

The one area to watch: if multiple admins in the same squadron hit the parade night generator simultaneously (same squadron, same planning year), they may create duplicate parade dates. Advise squadrons to have one admin set up the planning year first, then allow read-only users in.

---

## Post-Login Monitoring (T+1 to T+4 hours)

After the initial login surge, monitoring can shift from every-5-minutes to every-30-minutes. Key things to watch:

- Any save failures reported
- Any permission denials that seem unexpected (audit log)
- Database connections returning to baseline (<30)
- Any CEA import activity (may cause brief load spikes)
- Support channel volume

---

## Release Controller Responsibilities

The release controller is the single person responsible for the GO/STOP decision during the release event.

| Responsibility | Detail |
|---|---|
| Open monitoring before codes are sent | Ensure railway dashboard and metrics are visible |
| Make the stop call | If any stop condition is hit, initiate rollback without waiting for consensus |
| Communicate | Send maintenance message if access is suspended |
| Document | Record timeline in incident log |
| Handoff | After T+4 hours if stable, hand off to support lead |

**Release controller**: ___________________ Date: ___________
**Backup controller**: ___________________
