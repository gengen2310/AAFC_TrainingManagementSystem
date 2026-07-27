# AAFC TMS — Support Triage Guide

Phase 12 (Operational Release Gate). Classification and escalation guide for support staff.
Created: 2026-07-14.

---

## Triage Categories

### Category 1: Security or Privacy (ESCALATE IMMEDIATELY)

**Signs**: User reports seeing another unit's data; user can perform actions their role should not allow; user receives data they should not have access to.

**Action**: Do NOT try to resolve this yourself. Escalate immediately to the system engineer and incident owner. Suspend the affected user's session if possible. Preserve all evidence (screenshots, timestamps, user details) before taking any other action.

**Response time**: Immediate — any hour.

---

### Category 2: Access Issue

**Signs**: User cannot log in; code is rejected; account appears locked; user receives 429 Too Many Requests.

**Diagnosis questions**:
- Has the code been entered correctly? (case-sensitive, no spaces)
- Has the account been locked after 5 failed attempts?
- Is the user trying to log in from a shared IP that may be rate-limited?

**Resolution steps**:
1. If account locked: a Wing Admin or National Admin can unlock via the Accounts page
2. If IP rate-limited: wait 15 minutes or have the user try from a different network
3. If code rejected with no obvious cause: verify the code was issued correctly via the Accounts page
4. If code was reset and user never received it: re-issue via Accounts page (one-time display only)

**Do not** email or message access codes in plain text.

---

### Category 3: Role or Permission Issue

**Signs**: User sees the wrong navigation; user cannot access a page they expect; user gets 403 errors.

**Diagnosis questions**:
- What role is the user? (Check the Accounts page)
- What page are they trying to access?
- Is that page visible for their role? (See `27_role_and_navigation_rationalisation.md`)

**Resolution steps**:
1. Confirm the user's role in the Accounts page
2. If role is wrong: update role (Wing Admin or higher required)
3. If role is correct but page is unavailable: explain that the page is not visible for that role (expected behaviour)

---

### Category 4: Incorrect Squadron / Organisation

**Signs**: User sees data from the wrong unit; user's dashboard shows wrong unit name.

**Diagnosis questions**:
- What access code did they use?
- What squadron does that code belong to?
- Is there a second account for the same user?

**Resolution steps**:
1. Confirm which code they used and which unit it maps to via the Accounts page
2. If the wrong code was used: have them log out and log in with the correct code
3. If an account is mapped to the wrong unit: escalate to Wing Admin or National Admin to correct

---

### Category 5: Data Inconsistency

**Signs**: Data appears in one part of the system but not another; a saved record is missing; a record shows different values in the TMS vs Planning Workspace.

**Diagnosis questions**:
- What data is missing or inconsistent?
- In which interface was it created vs where it's missing?
- When was the record created?

**Note on known limitation**: Rooms and facilitators entered via the TMS are separate from those in the Planning Workspace. A facilitator added in TMS → Facilitators page will NOT automatically appear in the Planning Workspace Facilitators tab. This is a known limitation — add facilitators in both places.

**Resolution steps**:
1. Ask the user to refresh both interfaces and check again
2. If still inconsistent: check the audit log for the record creation event
3. If the audit log shows the record was created but it's not displaying: escalate to system engineer
4. If the issue is the rooms/facilitators known limitation: explain the workaround

---

### Category 6: Save Failure

**Signs**: User clicks Save but the change is not persisted; autosave spinner doesn't stop; user receives an error after saving.

**Diagnosis questions**:
- What browser is the user on?
- What exactly were they saving?
- Is the backend health check responding? (`curl .../api/health/ready`)

**Resolution steps**:
1. Ask user to refresh and check if the change was actually saved
2. If not saved: ask user to try again and note any error message exactly
3. If error message visible: record it and escalate
4. If backend is unhealthy: escalate to system engineer immediately

---

### Category 7: Performance Issue

**Signs**: Pages load slowly; requests time out; the system feels sluggish.

**Diagnosis questions**:
- Is the issue affecting one user or multiple squadrons?
- What time of day is it?
- Which specific page is slow?

**Resolution steps**:
1. Check Railway metrics: CPU, memory, database connections
2. If database connections are near limit: restart backend service
3. If isolated to one user: may be local network issue
4. If widespread: escalate to system engineer and monitor stop conditions

---

### Category 8: Display Problem

**Signs**: Page renders incorrectly; buttons are missing or misaligned; content is cut off.

**Diagnosis questions**:
- What browser and version?
- What zoom level?
- Does a different browser show the same issue?
- Does refreshing fix it?

**Resolution steps**:
1. Ask user to try in Chrome or Edge
2. If browser-specific: document and log as a medium/low defect
3. If all browsers affected: escalate — may be a code defect

---

### Category 9: Import Problem

**Signs**: CEA import fails; file upload returns an error; imported activities don't appear.

**Diagnosis questions**:
- What file format? (Expected: CSV or XLSX from the CEA system)
- What error message exactly?
- File size? (Max 10MB)

**Resolution steps**:
1. Verify file format (must be CEA-format CSV or XLSX, not a custom spreadsheet)
2. Check file size
3. Check for special characters in the file name
4. If file is correct format and still fails: save the file and escalate with the error message and file attached

---

### Category 10: Duplicate Data

**Signs**: Two identical parade nights, activities, or curriculum items appear; the same facilitator appears twice.

**Diagnosis questions**:
- Are the IDs the same or different?
- When was each record created?

**[UPDATED 2026-07-24]**: Neither of these is actually a live duplication limitation any more, per `docs/beta/15_known_limitations.md` DL-01/DL-02 — facilitators were never a separate table to begin with (a docs error, corrected), and rooms/training-areas have been unified: `/api/planning/locations` now reads/writes the same `training_areas` table connected-frontend's Resources page uses. A room or facilitator that appears to exist twice with the same name today is a genuine duplicate, not this old known-limitation pattern.

**Resolution steps**:
1. Check audit log to determine how many records exist and when they were created
2. Treat any apparent duplicate as genuine — escalate, do not delete without instruction (the "known limitation, no action needed" branch below no longer applies)

---

### Category 11: Training or Usability Question

**Signs**: User doesn't understand what a feature does; user wants to know how to complete a task.

**Resolution steps**:
1. Refer to the task instructions in `44_beta_release_communication.md`
2. Walk the user through the relevant task from the UAT task list
3. Log if the same question comes up from multiple users — it likely indicates a UX improvement needed

---

## Escalation Path

| Severity | Contact | Response time |
|---|---|---|
| Security / isolation (Category 1) | System engineer + incident owner | Immediate |
| Data integrity / save failure | System engineer | Within 1 hour |
| Access issues | Wing Admin or designated support lead | Within 2 hours |
| Performance (widespread) | System engineer | Within 30 minutes |
| Display / usability questions | Support lead | Within 1 business day |
