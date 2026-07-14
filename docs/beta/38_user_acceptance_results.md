# AAFC TMS — User Acceptance Test Results

Phase 6 (Operational Release Gate). Actual results to be recorded by testers.
Template created: 2026-07-14. Results: PENDING — HUMAN ACTION REQUIRED.

---

## Status

**NOT COMPLETE.** Actual user testing has not yet occurred. This document is a template. Results must be entered by real testers following the task set in `37_user_acceptance_test_plan.md`.

Do not mark UAT complete until this document contains results for all four tester profiles and the acceptance criteria have been reviewed.

---

## Tester Profiles

| Tester | Name | Role | Squadron/Unit | Access code distributed | Date |
|---|---|---|---|---|---|
| Tester A | ___________________ | sqn_admin | 703 SQN | [ ] Yes | ___________ |
| Tester B | ___________________ | sqn_general | 703 SQN | [ ] Yes | ___________ |
| Tester C | ___________________ | wing_admin | 7WG | [ ] Yes | ___________ |
| Tester D | ___________________ | sqn_admin | 701 SQN | [ ] Yes | ___________ |

---

## Results Template

Copy this section for each tester. Complete all fields.

### Tester A (sqn_admin — experienced)

| Task | Task Name | Result | Time (min) | Hesitation | Error | Severity | Notes |
|---|---|---|---|---|---|---|---|
| 1 | Log in | | | | | | |
| 2 | Confirm identity | | | | | | |
| 3 | Open planning year | | | | | | |
| 4 | Configure terms | | | | | | |
| 5 | Generate parade nights | | | | | | |
| 6 | Add holiday | | | | | | |
| 7 | Review activities | | | | | | |
| 8 | Add local activity | | | | | | |
| 9 | Schedule a lesson | | | | | | |
| 10 | Assign facilitator | | | | | | |
| 11 | Assign room | | | | | | |
| 12 | Cancel lesson | | | | | | |
| 13 | Reschedule | | | | | | |
| 14 | Mission Backlog | | | | | | |
| 15 | Weekly Program | | | | | | |
| 16 | Missing training | | | | | | |
| 17 | Audit record | | | | | | |
| 18 | Switch interfaces | | | | | | |
| 19 | No second login | | | | | | |
| 20 | Log out | | | | | | |

**Overall result**: PASS / FAIL / PARTIAL
**Tester comments**: ___________________
**New defects found**: ___________________
**Signed**: ___________________ Date: ___________

---

### Tester B (sqn_general — less experienced)

| Task | Task Name | Result | Time (min) | Hesitation | Error | Severity | Notes |
|---|---|---|---|---|---|---|---|
| 1 | Log in | | | | | | |
| 2 | Confirm identity | | | | | | |
| 3 | Open planning year | | | | | | |
| 4 | Configure terms | | | | | | |
| 5 | Generate parade nights (admin skipped) | N/A | | | | | |
| 6 | Add holiday | | | | | | |
| 7 | Review activities | | | | | | |
| 8 | Add local activity | | | | | | |
| 9 | Schedule a lesson | | | | | | |
| 10 | Assign facilitator | | | | | | |
| 11 | Assign room | | | | | | |
| 12 | Cancel lesson | | | | | | |
| 13 | Reschedule | | | | | | |
| 14 | Mission Backlog | | | | | | |
| 15 | Weekly Program | | | | | | |
| 16 | Missing training | | | | | | |
| 17 | Audit record | | | | | | |
| 18 | Switch interfaces | | | | | | |
| 19 | No second login | | | | | | |
| 20 | Log out | | | | | | |

**Overall result**: PASS / FAIL / PARTIAL
**Tester comments**: ___________________
**New defects found**: ___________________
**Signed**: ___________________ Date: ___________

---

### Tester C (wing_admin)

| Task | Task Name | Result | Time (min) | Hesitation | Error | Severity | Notes |
|---|---|---|---|---|---|---|---|
| 1 | Log in | | | | | | |
| 2 | Confirm identity | | | | | | |
| 3–20 | (Wing proxy — check squadron in proxy mode) | | | | | | |
| 21 | Wing overview | | | | | | |

**Overall result**: PASS / FAIL / PARTIAL
**Tester comments**: ___________________
**New defects found**: ___________________
**Signed**: ___________________ Date: ___________

---

### Tester D (sqn_admin — data isolation)

| Task | Task Name | Result | Time (min) | Hesitation | Error | Severity | Notes |
|---|---|---|---|---|---|---|---|
| 1 | Log in (701 SQN) | | | | | | |
| 2 | Confirm only 701 SQN visible | | | | | | |
| 3-15 | Core tasks (701 SQN only) | | | | | | |
| 20 | Log out | | | | | | |

**Isolation check**: Confirm no 703 SQN data visible to 701 SQN user: PASS / FAIL
**Overall result**: PASS / FAIL / PARTIAL
**Tester comments**: ___________________
**New defects found**: ___________________
**Signed**: ___________________ Date: ___________

---

## New Defects Found During UAT

| ID | Tester | Task | Description | Severity | Recommendation |
|---|---|---|---|---|---|
| | | | | | |

---

## UAT Coordinator Sign-Off

After reviewing all tester results:

| Item | Status |
|---|---|
| All 4 tester profiles completed | PENDING |
| Acceptance criteria reviewed | PENDING |
| New blockers: 0 | PENDING |
| New high defects: assessed | PENDING |

**UAT coordinator**: ___________________ Date: ___________
**Decision**: PASS / FAIL / CONDITIONAL PASS (specify conditions)
