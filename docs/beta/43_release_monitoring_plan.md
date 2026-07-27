# AAFC TMS — Release Monitoring Plan

Phase 11 (Operational Release Gate). Monitoring checklist for release day and ongoing.
Created: 2026-07-14.

---

## Monitoring Must Be Active Before Access Is Distributed

Open all monitoring channels and establish baselines before any user access code is sent out.

---

## Monitoring Sources

| Source | How to access | What it shows |
|---|---|---|
| Backend logs | Railway dashboard → `aafc-tms-backend` → Logs | All requests, errors, auth events |
| Frontend logs | Railway dashboard → `aafc-tms-frontend` → Logs | Nginx access and error log |
| Planning Workspace logs | Railway dashboard → `aafc-tms-planning-workspace-preview` → Logs | Nginx access and error log |
| Railway metrics | Railway dashboard → each service → Metrics | CPU, memory, restarts |
| PostgreSQL metrics | Railway dashboard → PostgreSQL → Metrics | Connections, CPU, memory |
| GitHub Actions | `Actions` tab → `backup-postgresql.yml` | Daily backup status |
| Health endpoint | `curl https://aafc-tms-backend-production.up.railway.app/api/health/ready` | Backend ready + squadron count |
| Support channel | [Define communication channel] | User-reported issues |

---

## Monitoring Checklist — Release Day

### Before Opening Access (T-30 min)

| Check | Command / Action | Expected | Actual | Status |
|---|---|---|---|---|
| Backend health | `curl .../api/health/ready` | `{"status":"ready","squadrons":16}` | | |
| Backend memory | Railway metrics | <70% of allocation | | |
| Backend CPU | Railway metrics | <20% idle | | |
| Database connections | Railway Postgres metrics | < 50% of max | | |
| Container restarts | Railway metrics | 0 in last hour | | |
| Last backup success | GitHub Actions | Green ✓ | | |
| No deployment in progress | Railway dashboard | No running deployments | | |
| No migration pending | `/api/system/status` (system_admin) | Alembic revision = `x9y0z1a2b3c4` | | |
| Monitoring window open | This checklist active | Responsible person confirmed | | |
| Incident log ready | `docs/beta/17_incident_log_template.md` | Open and ready | | |
| Rollback commands ready | `42_release_stop_and_rollback_plan.md` | On screen | | |
| Support channel monitored | [Channel] | Active monitor confirmed | | |

### During Access Release (T+0 to T+60 min)

| Metric | Check frequency | Normal baseline | Warning threshold | Stop threshold | Action if stop |
|---|---|---|---|---|---|
| HTTP 5xx rate | Every 5 min | <0.1% | >1% | >5% for >60s | Rollback backend |
| HTTP 401 rate (auth failures) | Every 5 min | <2% (login page hits) | >10% | Unexpected spike | Investigate auth |
| HTTP 403 rate | Every 5 min | <1% | >5% | Sustained spike | Check scope enforcement |
| HTTP 422 rate | Every 10 min | <0.5% | >3% | — | Check API clients |
| P95 response time | Every 5 min | <500ms warm | >3000ms | >10000ms for >5min | Check DB connections |
| Database connections | Every 5 min | <30 | >60 | >80 (of 100 max) | Restart backend; rollback |
| Backend CPU | Every 5 min | <40% under load | >70% sustained | >90% sustained | Scale or rollback |
| Backend memory | Every 5 min | <60% | >80% | >95% | Rollback |
| Container restarts | Every 5 min | 0 | 1 | 2+ | Investigate crash; rollback |
| Login failures | Every 10 min | Normal authentication noise | Sudden spike | Any reports of blocked legitimate users | Check lockout logic |
| Support reports | Continuous | — | 3+ similar reports | 5+ similar reports or 1 security/isolation report | Investigate immediately |

### Isolation Spot Checks (T+15, T+30, T+60 min)

Perform a manual cross-squadron isolation check at each interval:
1. Log in as a known test sqn_general user for squadron A
2. Attempt to access squadron B's planning year UUID directly via the API
3. Confirm 403 response
4. Log in as a different squadron's sqn_admin
5. Confirm correct squadron data visible; no other squadron's data

Record result at each interval: PASS / FAIL

---

## Monitoring Checklist — T+2 Hours

| Check | Expected | Status |
|---|---|---|
| Any incidents opened | 0 or documented | |
| Error rate trends | Declining or stable | |
| Database connection trend | Stable | |
| Login failures normalised | Yes | |
| Support volume | Manageable | |
| All squadrons able to log in | Yes (spot check 4+ squadrons) | |
| Planning Workspace accessible | Yes | |
| Audit log recording actions | Yes | |

---

## Monitoring Checklist — T+24 Hours

| Check | Expected | Status |
|---|---|---|
| Nightly backup succeeded | GitHub Actions green | |
| No overnight incidents | Review incident log | |
| Error rate overnight | <0.5% 5xx | |
| Database connections overnight | Stable | |
| Any data integrity reports | 0 | |
| Support reports reviewed | Triaged and responded to | |

---

## Alert Contacts

| Alert type | Contact | Response time |
|---|---|---|
| Security / isolation breach | [Name] | Immediate (any hour) |
| Database failure / data loss | [Name] | Immediate (any hour) |
| Authentication failure | [Name] | Within 15 minutes |
| Performance degradation | [Name] | Within 30 minutes |
| User access issue | [Support lead] | Within 2 hours during business hours |

---

## Incident Log

If an incident occurs, create an entry in `docs/beta/release-day-incidents.md` (create if not exists) with:

```
## Incident [number] — [date/time]

**Type**: [security / data integrity / availability / performance / usability]
**Detected**: [how and when]
**Affected users**: [which squadrons/roles]
**Symptoms**: [exact error message or behaviour]
**Timeline**: [sequence of events]
**Root cause**: [once identified]
**Resolution**: [action taken]
**Evidence preserved**: [what was saved]
**Status**: [open / resolved]
```
