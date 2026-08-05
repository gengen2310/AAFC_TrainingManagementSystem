# AAFC TMS — Known Limitation Acceptance

Phase 14 (Operational Release Gate). Residual risk assessment for all medium and low defects.
Created: 2026-07-14.

---

## Review Basis

Source: `docs/beta/15_known_limitations.md`
All BLOCKER and HIGH items have fixes committed to the release candidate. This document addresses medium and low items only.

For each limitation, Claude Code provides a technical recommendation. Only the authorised project owner may formally accept residual risk.

---

## Data Model Limitations

### DL-01: Physical Spaces Not Unified (Medium)

| Field | Value |
|---|---|
| Description | Rooms created via TMS Resources page are not visible in Planning Workspace Rooms tab, and vice versa |
| User impact | Users must add rooms in two places if using both TMS and Planning Workspace |
| Affected roles | sqn_admin, sqn_general (anyone using both apps) |
| Affected squadron scope | All 16 squadrons |
| Workaround | Add room in both TMS Resources and Planning Workspace Rooms tab with the same name |
| Likelihood of causing an issue | HIGH — any user of both apps will encounter this |
| Consequence | Operational duplication; minor confusion; no data loss |
| Visible to users | YES — users will notice rooms don't sync |
| Recommended action | Accept for beta with documented workaround; merge post-beta |
| Release recommendation | **ACCEPT FOR BETA** |
| Owner acceptance | PENDING — MANUAL APPROVAL REQUIRED |
| Target fix date | Post-beta (Task #10) |

### DL-02: Facilitators Not Unified (Medium)

| Field | Value |
|---|---|
| Description | Facilitators in TMS and Planning Workspace are separate lists |
| User impact | Must add facilitator in both places |
| Workaround | Add in both TMS Facilitators page and Planning Workspace Facilitators tab |
| Likelihood | HIGH — anyone using both apps |
| Consequence | Duplication; no data loss |
| Recommended action | Accept for beta |
| Release recommendation | **ACCEPT FOR BETA** |
| Owner acceptance | PENDING |

### DL-03: Planning Dates and Parade Nights Are Separate (Low)

| Field | Value |
|---|---|
| Description | Intentional architecture — planning dates and operational parade nights are separate records |
| User impact | Must use Parade Night Generator after creating a planning year |
| Workaround | Documented in user communication |
| Recommended action | Document as expected behaviour, not a limitation |
| Release recommendation | **DOCUMENT AS EXPECTED BEHAVIOUR** |
| Owner acceptance | N/A |

---

## Security Limitations

### SL-01: ENVIRONMENT=staging in Production (High — RESOLVED)

| Field | Value |
|---|---|
| Description | Production backend running with ENVIRONMENT=staging; fail-closed startup check and HSTS not active |
| User impact | None visible to users; technical configuration issue |
| Fix status | **DEPLOYED AND VERIFIED 2026-08-05** — `railway variable list` against production confirms `ENVIRONMENT=production`; re-checked as part of Gate 9 |
| Release recommendation | Fixed — no longer a release blocker |
| Owner acceptance | N/A — technical fix confirmed live, this line item is closed |

### SL-02: IDOR Gap (Blocker — RESOLVED)

| Field | Value |
|---|---|
| Fix status | **DEPLOYED AND VERIFIED 2026-08-05** — confirmed via a genuine cross-squadron read attempt directly against production (`ADMIN704` → 403 on another squadron's facilitator-leave, not the pre-fix 200 leak); see Gate 9 update in `docs/beta/11_defect_register.md` |
| Release recommendation | Fixed — no longer a release blocker |
| Owner acceptance | N/A — technical fix confirmed live, this line item is closed |

### SL-03: No CSRF Tokens (Low)

| Field | Value |
|---|---|
| Description | Cookie-based auth with SameSite=none; CORS whitelist is the primary CSRF mitigation |
| User impact | None visible to users |
| Workaround | CORS configuration (current) is effective mitigation |
| Likelihood of exploitation | LOW — requires attacker on an allowed CORS origin |
| Consequence | Potential unauthorised state change if CORS were bypassed; currently not possible |
| Recommended action | Accept for beta; implement CSRF tokens post-beta |
| Release recommendation | **ACCEPT FOR BETA** |
| Owner acceptance | PENDING |

---

## Functional Limitations

### FL-01: Planning Workspace Stale in Production (High — RESOLVED)

| Field | Value |
|---|---|
| Fix status | **DEPLOYED AND VERIFIED 2026-08-05** — `GET https://aafc-tms-planning-workspace-preview-production.up.railway.app/planning` directly re-checked, returns 200 |
| Release recommendation | Fixed — no longer a release blocker |
| Owner acceptance | N/A — technical fix confirmed live, this line item is closed |

### FL-02: No Playwright E2E Coverage (Low)

| Field | Value |
|---|---|
| Description | No automated browser-level tests; manual verification only |
| User impact | None |
| Consequence | Regression risk if future changes are made without manual verification |
| Recommended action | Accept for beta; add Playwright post-beta |
| Release recommendation | **ACCEPT FOR BETA** |
| Owner acceptance | PENDING |

### FL-03: No 100-User Load Test (Medium)

| Field | Value |
|---|---|
| Description | Load test not yet executed; concurrent capacity unknown |
| User impact | Possible performance degradation during initial access surge |
| Workaround | Release monitoring plan (`43_release_monitoring_plan.md`) covers this case |
| Likelihood | LOW (16 squadrons × ~5 users each = 80 max concurrent) |
| Consequence | Possible slowness; no data loss |
| Recommended action | Accept for beta with monitoring; run load test before general availability |
| Release recommendation | **ACCEPT FOR BETA WITH MONITORING** |
| Owner acceptance | PENDING |

### FL-04: Squadron Browser Verification Incomplete (Medium)

| Field | Value |
|---|---|
| Description | Browser-level login not manually verified for all 16 squadrons |
| Workaround | UAT testers from at least 2 different squadrons will partially cover this |
| Recommended action | Accept for controlled beta where a designated person can verify each squadron's first login |
| Release recommendation | **ACCEPT FOR CONTROLLED BETA** |
| Owner acceptance | PENDING |

### FL-05: CEA Import Requires Manual File (Low)

| Field | Value |
|---|---|
| Description | No automated CEA feed; manual upload required |
| User impact | Operational step required |
| Recommended action | Accept; expected for this release |
| Release recommendation | **ACCEPT** |
| Owner acceptance | N/A — not a system defect |

---

## Infrastructure Limitations

### IL-01: No Commit Hash Tracking in Deployments (Low)

| Recommended action | Accept; deployment IDs are the authoritative record |
|---|---|
| Release recommendation | **ACCEPT** |

### IL-02: SQLite Datetime Warnings in Tests (Low)

| Recommended action | Accept; production uses PostgreSQL |
|---|---|
| Release recommendation | **ACCEPT** |

### IL-03: Stash Unreviewed (Info)

| Recommended action | Stash is local; does not affect deployed code; investigate post-release |
|---|---|
| Release recommendation | **ACCEPT** |

---

## Acceptance Summary

| Limitation | Recommended action | Owner accepted? |
|---|---|---|
| DL-01: Rooms duplication | Accept for beta | PENDING |
| DL-02: Facilitators duplication | Accept for beta | PENDING |
| DL-03: Dates vs nights | Expected behaviour | N/A |
| SL-01: ENVIRONMENT=staging | **RESOLVED 2026-08-05** — deployed and verified live | N/A — closed |
| SL-02: IDOR gap | **RESOLVED 2026-08-05** — deployed and verified live | N/A — closed |
| SL-03: No CSRF | Accept for beta | PENDING |
| FL-01: Stale PW in production | **RESOLVED 2026-08-05** — deployed and verified live | N/A — closed |
| FL-02: No E2E coverage | Accept for beta (partially addressed — see FL-04) | PENDING |
| FL-03: No 100-user test | Accept with monitoring (in progress — Gate 7 load test running against staging as of this update; result to be recorded here on completion) | PENDING |
| FL-04: Browser verification | Accept for controlled beta (partially addressed 2026-08-05 — Gate 6 ran connected-frontend's full e2e suite live against staging: 35/45 passed, all 10 failures traced to one disclosed, non-code limitation — see `09_browser_e2e_verification.md`. Planning Workspace's own suite and full multi-role human browser walkthrough remain outstanding.) | PENDING |
| FL-05: CEA manual | Expected | N/A |
| IL-01–03 | Accept | N/A |

**All PENDING items require explicit confirmation from the authorised project owner before the GO decision is finalised.** Three items previously in this category (SL-01, SL-02, FL-01) are now technically resolved and no longer need an approval decision — they needed a production deploy, which happened 2026-08-05, and this document has been updated accordingly rather than left claiming a stale PENDING status.

**Claude Code's technical recommendation**: all accepted items are appropriate for a controlled beta with ~100 users from known squadrons. The three former "Fix before release" items (SL-01, SL-02, FL-01) are now deployed and verified — no further action needed on those specifically. The remaining PENDING rows are genuinely this project's owner's decision to make, not something further technical work can close on their behalf.
