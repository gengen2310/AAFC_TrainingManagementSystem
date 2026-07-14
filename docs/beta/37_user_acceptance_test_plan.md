# AAFC TMS — User Acceptance Test Plan

Phase 6 (Operational Release Gate). Task-based acceptance testing for real users.
Created: 2026-07-14.

---

## Purpose

Automated tests verify code behaviour. This plan verifies that real users with operational knowledge can complete their actual tasks. Both are required; neither substitutes for the other.

---

## Environment

- **Test environment**: Staging (`aafc-tms-frontend-staging.up.railway.app`)
- **Planning Workspace**: `aafc-tms-planning-workspace-preview-staging.up.railway.app/planning`
- **Data**: Synthetic data only — do NOT enter real cadet names, real personal information, or real access codes during UAT
- **Pre-test state**: Staging has 16 squadrons with synthetic data. Each tester should be provided a test access code for their assigned role and squadron

---

## Required Tester Profiles

| Tester | Role | Squadron | Rationale |
|---|---|---|---|
| Tester A | Squadron admin (`sqn_admin`) — experienced | Any populated squadron | Knows expected behaviour; will find subtle issues |
| Tester B | Squadron general (`sqn_general`) — less experienced | Same or different squadron | Will reveal UX clarity gaps |
| Tester C | Wing admin (`wing_admin`) | — | Tests wing-level scope and proxy mode |
| Tester D | Squadron admin (`sqn_admin`) — different squadron from A | Different squadron | Tests data isolation |

---

## Test Account Setup (Machine-executable, done before testers begin)

Each tester requires a test access code. Claude Code will create test accounts in staging via the Accounts API. No real personal information should be used.

Test accounts to be created:
- `UAT-SQNADMIN-703` — sqn_admin for 703 SQN
- `UAT-SQNGEN-703` — sqn_general for 703 SQN
- `UAT-WINGADM-7WG` — wing_admin for 7WG
- `UAT-SQNADMIN-701` — sqn_admin for 701 SQN (data isolation test)

Access codes will be provided to testers via a secure channel. Codes must not be sent in plain text email or recorded in this document.

---

## Task Set

Each tester completes the full task set for their role. Tasks marked [WING ONLY] are skipped by Testers A, B, D.

### Task 1: Log In
- Open the staging URL in a private browser window
- Enter the provided access code
- Confirm: correct unit name and role appear on screen

### Task 2: Confirm Identity
- Confirm: correct squadron or organisation shown
- Confirm: role label visible (or can be inferred from navigation)
- Confirm: no other squadron's data is visible

### Task 3: Open or Create a Planning Year
- Navigate to Planning Workspace
- Open an existing planning year OR create a new one for current training year
- Confirm: planning year is for the correct unit

### Task 4: Configure Terms
- Within the planning year, review or set term dates
- Confirm: four terms are visible and date ranges look correct
- Confirm: holiday periods are visible if any were entered

### Task 5: Generate Parade Nights (Admin only)
- Use the Parade Nights page to generate a new set of parade dates
- Specify a weekday and date range
- Confirm: dates are generated and appear in the calendar

### Task 6: Add a Holiday
- Add a holiday or stand-down period that falls within a term
- Confirm: the holiday appears and is associated with the correct date range

### Task 7: Import or Review Activities
- Open the Activities tab in the Planning Workspace (or Activities page)
- If a CEA import file is available: import it and review the results
- If not: review any existing activities
- Confirm: activities are from the correct unit or national/wing level

### Task 8: Add a Local Activity
- Add a new local activity (a unit-specific event or commitment)
- Provide a name and date
- Confirm: activity appears in the correct list

### Task 9: Schedule a Lesson
- In the Planning Workspace, assign a curriculum item to a parade night
- Confirm: the assignment appears on the correct night
- Confirm: the curriculum item is marked as scheduled

### Task 10: Assign a Facilitator
- For the lesson assigned in Task 9, assign a facilitator
- Confirm: facilitator appears on the session
- Confirm: facilitator workload updates in the Facilitators tab

### Task 11: Assign a Room and Equipment
- For the same lesson, assign a room (from the Rooms tab)
- Confirm: room appears on the session

### Task 12: Cancel a Lesson
- Cancel the lesson assigned in Task 9
- Provide a cancellation reason
- Confirm: lesson shows cancelled status

### Task 13: Reschedule the Cancelled Lesson
- Reschedule the cancelled lesson to a different parade night
- Confirm: original night no longer shows the lesson
- Confirm: new night shows the lesson

### Task 14: Review Mission Backlog
- Open the Mission Backlog tab in the Planning Workspace
- Filter by an unscheduled curriculum item
- Confirm: the item shows as unscheduled

### Task 15: Produce a Weekly Program
- Navigate to the Weekly Program page (or connected-frontend)
- Select a parade night that has sessions assigned
- Confirm: program renders with correct sessions, facilitators, and times
- Attempt to print or save as PDF

### Task 16: Identify Missing Training
- Use Reports or the Dashboard to find curriculum items not yet scheduled
- Confirm: missing items are listed or highlighted

### Task 17: Locate an Audit Record
- Navigate to the Audit log
- Find a record of a recent action (e.g. the lesson cancelled in Task 12)
- Confirm: the record shows the correct action, user, and timestamp

### Task 18: Move Between TMS and Planning Workspace
- While logged into the connected TMS, open the Planning Workspace (the `/planning` link or tab)
- Confirm: no second login is required
- Confirm: the same unit context is visible in both

### Task 19: Confirm No Second Login
- Refresh the Planning Workspace
- Confirm: still logged in without re-entering credentials
- Switch back to the connected TMS
- Confirm: still logged in

### Task 20: Log Out
- Log out from the connected TMS
- Confirm: session is cleared
- Attempt to reload the Planning Workspace
- Confirm: login is required again

### [WING ONLY] Task 21: Wing Oversight
- Open the Wing Overview page
- Confirm: all squadrons in the wing are visible
- Confirm: no data from outside the wing is shown
- Review curriculum coverage and facilitator load

---

## Recording Format

Testers use the template in `38_user_acceptance_results.md`. For each task record:

| Field | Value |
|---|---|
| Tester | Name and role |
| Squadron | Unit tested |
| Task | Task number and name |
| Result | PASS / FAIL / PARTIAL |
| Time taken | Approximate minutes |
| Hesitation | Yes/No — where did they pause? |
| Error encountered | Yes/No — describe |
| Unclear wording | Yes/No — quote the text |
| Incorrect expectation | Yes/No — what did they expect? |
| Workaround used | Yes/No — describe |
| Screenshot | Filename if taken |
| Severity | BLOCKER / HIGH / MEDIUM / LOW / OK |
| Recommendation | Free text |

---

## Acceptance Criteria

| Criterion | Threshold |
|---|---|
| Tasks 1-3 (login, identity, year) | All 4 testers: PASS |
| Tasks 4-15 (core workflow) | 3 of 4 testers: PASS; no BLOCKERs |
| Tasks 16-20 (oversight and session) | 3 of 4 testers: PASS |
| Task 21 (wing) | Tester C: PASS |
| New blockers discovered | 0 |
| New high defects discovered | Must be documented and assessed before GO decision |

---

## Preparation Checklist (Machine-executable)

- [x] Staging environment online with 16 squadrons
- [x] Synthetic data populated
- [ ] Test access codes created and distributed (HUMAN ACTION — provide codes securely)
- [ ] Tester briefing completed (HUMAN ACTION)
- [ ] Testers have the task sheet and recording template
- [ ] Support contact available during testing

---

## Timeline

UAT must be completed before the final production deployment is approved. Results must be reviewed and any new blockers or high defects assessed before the GO/NO-GO decision is finalised.

Actual completion date: PENDING — MANUAL USER ACTIONS required.
