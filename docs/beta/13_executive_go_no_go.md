# AAFC TMS — Executive GO / NO-GO

v17.1 Beta Release Decision Record.
Created: 2026-07-14.

---

## Decision Summary

**Current status: CONDITIONAL GO**

The system is feature-complete and structurally sound for beta. Three security/deployment defects are fixed on the release branch but not yet deployed to production. Deployment requires explicit approval. Once deployed and browser-verified, this becomes a full GO.

---

## What Is Ready

| Area | Status | Confidence |
|---|---|---|
| All planned features implemented | Yes — all P0, P1 tasks complete | HIGH |
| Backend tests: 503 pass, 0 failures | Yes | HIGH |
| TypeScript: 0 errors | Yes | HIGH |
| Backup/restore: proven end-to-end | Yes | HIGH |
| IDOR protection: fixed on branch | Yes (deployed: NO) | HIGH (fix quality) |
| Navigation rationalised | Yes — 4 retired planning pages, 2 tabs removed, 4 subtitles removed | HIGH |
| Security greps: all clean | Yes | HIGH |
| Migration chain: all environments synced at v36 | Yes | HIGH |
| 16 squadrons confirmed in staging | Yes | HIGH |
| Documentation suite complete | Yes | HIGH |

---

## What Requires Action Before Full GO

| Item | Action required | Who | Risk if deferred |
|---|---|---|---|
| Deploy DEFECT-001 (sqn_general IDOR) to production | Approve + execute `railway up` | Beta coordinator | HIGH — cross-squadron data readable |
| Apply ENVIRONMENT=production (DEFECT-003) | Approve + `railway variable set` | Beta coordinator | MEDIUM — bootstrap endpoint reachable |
| Deploy DEFECT-005 (Planning Workspace Dockerfile) to production | Approve + execute deploy | Beta coordinator | HIGH — stale build in production |
| Browser verification (all 8 roles, 16 squadrons in staging) | Login per role/squadron | Beta coordinator | MEDIUM — regression may be invisible |
| Load test (100 concurrent users) | Schedule + run against staging | Test team | LOW for beta; required before GA |

---

## Risk Register at This Decision Point

| Risk | Severity | Mitigated? | Notes |
|---|---|---|---|
| Cross-squadron data leak (sqn_general IDOR) | BLOCKER | On branch only | Must deploy before any sqn_general user has access |
| Planning Workspace stale in production | HIGH | On branch only | Users may see outdated UI at `/planning` |
| ENVIRONMENT mismatch | HIGH | Fix ready | bootstrap-staging endpoint accessible; sqn-level risk only |
| No load test completed | MEDIUM | Deferred | Single-user performance is acceptable; beta with known squadrons is low concurrency |
| Room/facilitator duplication | MEDIUM | Documented | Users aware; workaround exists |
| No browser verification complete | MEDIUM | Deferred | All workflows code-verified; browser check is the remaining gap |

---

## Decision Criteria

For a **full GO**, the following must ALL be true:
1. DEFECT-001 fix deployed to production
2. DEFECT-003 variable change applied to production
3. DEFECT-005 Planning Workspace deployed to production
4. Browser verification confirms connected-frontend and Planning Workspace load correctly
5. No new P0/P1 defects discovered during browser verification

For a **limited beta GO** (known test squadrons, supervised use):
1. DEFECT-001 fix deployed to production (non-negotiable — required before any sqn_general logins)
2. At minimum: sqn_admin and wing_admin browser flows verified

---

## What This Release Does NOT Claim

- Browser E2E test coverage: NONE (no Playwright; manual verification only)
- 100-user load tested: NO
- Physical space consolidation (`TrainingArea`/`PlanningLocation`): DEFERRED post-beta
- Facilitator deduplication: DEFERRED post-beta
- Stash `stash@{0}` applied: NO (too risky; investigate post-release)
- CSRF tokens: NOT implemented (CORS mitigation only)

---

## Sign-Off Record

| Role | Name | Date | Decision |
|---|---|---|---|
| System author / Claude Code audit | Automated consolidation audit | 2026-07-14 | CONDITIONAL GO |
| Beta coordinator | ___________________ | ___________ | ___________ |
| Approving authority | ___________________ | ___________ | ___________ |

---

## Post-Beta Backlog (Top 5)

1. Merge `TrainingArea` and `PlanningLocation` into unified physical space model (Task #10)
2. Merge `facilitators` and `planning_facilitators` (Task #11 data layer)
3. Playwright E2E test suite for golden path flows
4. 100-user concurrent load test
5. CSRF token implementation
