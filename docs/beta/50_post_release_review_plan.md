# AAFC TMS — Post-Release Review Plan

Phase 17 (Operational Release Gate). Template and schedule for the retrospective after beta release.
Created: 2026-07-14.

---

## Purpose

A post-release review captures what went well, what did not, and what must change for the next release. It closes the release gate officially.

**This review must be completed regardless of whether the release was smooth or not.** A successful release still produces lessons.

---

## Review Schedule

| Event | Timing | Attendees |
|---|---|---|
| T+24hr quick check | 24 hours after access codes distributed | Release controller, support lead |
| T+7d interim review | 7 days after release | All named stakeholders |
| T+30d post-beta review | 30 days after release (end of beta period) | All named stakeholders + squadron contacts |

---

## T+24 Hour Quick Check

### Metrics to collect

| Metric | Value |
|---|---|
| Total accounts created | |
| Total logins (from audit log) | |
| Failed login attempts | |
| Account lockouts | |
| Support tickets raised | |
| Category 1 (security) incidents | |
| Backend errors (Railway logs) | |
| Database connections: peak | |
| Database connections: current | |
| Any deployments since release | |
| Any rollbacks since release | |

### Questions to answer

- Did the smoke test findings (if any) predict any issues that occurred?
- Did any user hit a limitation listed in `47_known_limitation_acceptance.md`?
- Was the support channel staffed adequately?

### T+24hr check completed by

**Name**: ___________________
**Date/time**: ___________

---

## T+7 Day Interim Review

### Issue log review

Review all support issues raised in the first 7 days. For each:

| Issue | Category | Root cause | Resolution | Recurrence risk |
|---|---|---|---|---|
| | | | | |

### UAT completion check

- How many of the 20 UAT tasks were completed by actual users?
- Were any tasks blocked by limitations not anticipated in `47_known_limitation_acceptance.md`?
- Were any tasks completed differently than the test plan expected?

### Defect log update

- Have any of the open defects in `47_known_limitation_acceptance.md` progressed?
- Any new defects discovered during beta use?

---

## T+30 Day Post-Beta Review

### Beta period summary

| Metric | Final count |
|---|---|
| Total unique users | |
| Active squadrons (at least 1 login) | |
| Inactive squadrons (0 logins) | |
| Total sessions created (if measurable) | |
| Total support issues | |
| Unresolved issues at review time | |
| Category 1 incidents | |

### Feature and usability findings

For each of the 8 roles released, answer:
- Did the role behave as documented in `27_role_and_navigation_rationalisation.md`?
- Were there unexpected navigation or permission issues?
- Were users able to complete their intended tasks?

### Limitation status update

For each limitation in `47_known_limitation_acceptance.md`:

| Limitation | Accepted at release | Impact during beta | Action now? |
|---|---|---|---|
| DL-01: Rooms duplication | ACCEPT | | |
| DL-02: Facilitators duplication | ACCEPT | | |
| SL-03: No CSRF tokens | ACCEPT | | |
| FL-02: No E2E coverage | ACCEPT | | |
| FL-03: No load test | ACCEPT with monitoring | | |
| FL-04: Browser verification incomplete | ACCEPT for controlled beta | | |

---

## What Went Well

(Fill in post-beta)

---

## What Did Not Go Well

(Fill in post-beta)

---

## Improvements for Next Release

| Improvement | Priority | Owner |
|---|---|---|
| | | |

---

## Gate Closure

This post-release review closes the **AAFC TMS Final Operational Release Gate**.

| Field | Value |
|---|---|
| Beta release date | ___________ |
| Review completed | ___________ |
| Review conducted by | ___________________ |
| Final release status | SUCCESSFUL / CONDITIONAL / WITHDRAWN |
| Recommendation for GA | PROCEED TO GENERAL AVAILABILITY / EXTEND BETA / HALT |

**Signed off by**: ___________________
**Date**: ___________

---

## Archive

After completion, this document and all documents `33–50` should be:
1. Committed to the repository (if not already)
2. Archived in the project's official documentation system
3. Referenced in the next release's preparation as a baseline

**Documents in this release gate series**: `docs/beta/33_feature_freeze.md` through `docs/beta/50_post_release_review_plan.md`
