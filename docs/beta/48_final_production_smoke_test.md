# AAFC TMS — Final Production Smoke Test

Phase 15 (Operational Release Gate). Five-minute smoke test to run immediately before distributing access codes.
Created: 2026-07-14.

---

## Purpose

This smoke test verifies the production system is alive and correct immediately before access is distributed to ~100 users. It is not a functional test — UAT covers that. It is a rapid sanity check.

**Do not distribute access codes before this smoke test passes.**

**Do not perform production writes in steps 1–11 until explicit approval is given by the authorised project owner.** The test record creation in step 8 is a minor write (a test parade notice or local activity); confirm approval before executing.

---

## Pre-Test Checklist

- [ ] Production backend health confirmed: `curl https://aafc-tms-backend-production.up.railway.app/api/health/ready` → `{"status":"ready","squadrons":16}`
- [ ] No deployment in progress (Railway dashboard shows no active builds)
- [ ] No backup or migration running
- [ ] Last backup succeeded (GitHub Actions green)
- [ ] Monitoring window is open (`43_release_monitoring_plan.md` pre-test checklist complete)
- [ ] Rollback commands are on screen (`42_release_stop_and_rollback_plan.md`)
- [ ] Production approval to proceed has been received: PENDING

---

## Smoke Test Sequence

**Required time**: ~5 minutes

**Tester**: Release controller or designated person
**Browser**: Chrome or Edge, private/incognito window

| Step | Action | Expected result | Pass? | Notes |
|---|---|---|---|---|
| 1 | Open `https://aafc-tms-frontend-production.up.railway.app` in a private window | Login page appears within 3 seconds | | |
| 2 | Log in using the approved squadron-admin test account (sqn_admin) | Dashboard loads; correct squadron name visible | | |
| 3 | Confirm correct squadron | Squadron name matches the test account's unit | | |
| 4 | Confirm Dashboard loads | Dashboard shows planning year health, upcoming nights, facilitator summary | | |
| 5 | Open Planning Workspace | Navigate to Planning Workspace (via sidebar); `/planning` loads without second login | | |
| 6 | Confirm no second login | Planning Workspace shows the same squadron context; no login page | | |
| 7 | Confirm correct planning year | Planning year matches the unit's current training year | | |
| 8 | Create an approved test record | Create a parade notice or local activity with the text "SMOKE TEST — DELETE" and today's date; confirm it saves | | |
| 9 | Confirm test record appears in both interfaces | The test record is visible in the Planning Workspace AND in the connected TMS | | |
| 10 | Remove or archive test record | Delete or archive the "SMOKE TEST" record; confirm it disappears | | |
| 11 | Confirm audit record | Open Audit log; find the create and delete actions from steps 8–10 | | |
| 12 | Log out | Log out from the connected TMS | | |
| 13 | Confirm both interfaces lose access | Refresh the Planning Workspace; confirm login is required again | | |
| 14 | Test read-only account | Log in with the sqn_general test account; confirm read-only view is correct; confirm write buttons are absent or disabled | | |
| 15 | Test Wing account | Log in with the wing_admin test account; confirm Wing Overview shows squadrons; confirm correct wing scope | | |
| 16 | Confirm backend readiness | `curl .../api/health/ready` → still `{"status":"ready","squadrons":16}` | | |
| 17 | Confirm database health | Railway Postgres metrics: connections <50%, no errors | | |
| 18 | Confirm backup workflow green | GitHub Actions: `backup-postgresql.yml` most recent run green | | |
| 19 | Confirm Alembic revision | `curl -H "Cookie: ..." .../api/system/status` → `"alembic_revision": "x9y0z1a2b3c4"` | | |
| 20 | Confirm no deployment in progress | Railway dashboard: no active builds or deploys | | |

---

## Result

| Overall result | PASS / FAIL |
|---|---|
| Tester | ___________________ |
| Date/time | ___________ |
| Failed steps | ___________________ |
| Decision | Proceed to distribute access / Hold and investigate |

**If any step fails**: do NOT distribute access codes. Investigate and resolve before proceeding. If a step fails and requires rollback, follow `42_release_stop_and_rollback_plan.md`.

---

## Post-Smoke-Test Actions

If all 20 steps pass:
1. Record result in this document
2. Update `12_full_beta_release_readiness.md` — Gate 7 status
3. Distribute access codes to users via secure channel
4. Open monitoring (`43_release_monitoring_plan.md` — During Release section)
