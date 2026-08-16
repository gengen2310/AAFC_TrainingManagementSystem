# AAFC TMS — Workflow Effort Audit

**Review:** Post-Gap Human Workflow, Architecture and Design Review — Stage 1  
**Date:** 2026-08-16  
**Method:** For the 20 highest-frequency workflows, measure current effort (screens, clicks, form fields, decisions). Then design the ideal path. Flag any gap ≥ 3 steps between current and ideal.  
**Target user:** Squadron Training Officer (sqn_admin), Desktop browser

---

## How to read this document

**Current effort columns:**
- **Screens:** Distinct page loads or modal opens
- **Clicks:** All distinct click/tap actions including nav clicks, button presses, dropdown selections
- **Fields:** Form fields the user must fill in
- **Decisions:** Moments where the user must choose between options without obvious default

**Gap:** `(Current clicks) − (Ideal clicks)`. Flag ≥ 3.

---

## WF-01: Record outcomes for last parade night

**Frequency:** Weekly (after every parade night)  
**Human need:** "Capture what was delivered and why anything wasn't."

### Current path
1. Nav → Parade Nights (1 click)
2. Find last night in the list — may need to scroll or filter (1 click / 1 scroll)
3. Click night to expand it (1 click)
4. Find each session row (0 clicks — visible)
5. Click pencil icon on Session 1 (1 click)
6. Quick Edit modal opens — change status dropdown (1 click)
7. If cancelled: select reason (1 click)
8. Save (1 click)
9. Repeat steps 5–8 for Session 2 (3–4 clicks each)
10. Repeat for Session 3 (3–4 clicks each)
11. Repeat for Session 4 (3–4 clicks each)

| | Screens | Clicks | Fields | Decisions |
|---|---|---|---|---|
| **Current** | 2 | 13–17 (for 3-session night) | 3–4 (status per session + reason) | 3–4 (one per session) |
| **Ideal** | 1 | 4–6 | 3 | 1 |
| **Gap** | -1 | -9 to -11 | -1 | -2 to -3 |

**Ideal path:** Dashboard → "Record outcomes for last night" card (auto-appears after parade night date) → opens inline outcome sheet (all sessions on one screen) → set status + reason per session on one form → Save all. 4 clicks, 1 screen, all sessions at once.

**Flag:** ✗ Gap ≥ 3 steps. No "record last night" workflow shortcut currently exists.

---

## WF-02: Check what training is still outstanding for a class

**Frequency:** Weekly-to-fortnightly  
**Human need:** "What does Senior 2 still need to cover before end of year?"

### Current path
1. Nav → Activities (1)
2. Scroll past activities table (1 scroll)
3. Scroll past Getting Help card (1 scroll)
4. See Planning Year section — select current year from dropdown (1)
5. Training Classes card visible — look for Mission Backlog (scroll down) (1 scroll)
6. See Mission Backlog card (0)
7. Filter by class: select Senior 2 from dropdown (1)
8. Review list

| | Screens | Clicks | Fields | Decisions |
|---|---|---|---|---|
| **Current** | 1 | 4 clicks + 3 scrolls = 7 effective taps | 1 filter field | 2 (which year, which class) |
| **Ideal** | 1 | 3 | 1 | 1 |
| **Gap** | 0 | -4 effective taps | 0 | -1 |

**Ideal path:** Nav → Mission Backlog (new top-level) → filter by class → view. OR Dashboard → Mission Backlog card → select class. 3 clicks, 1 screen.

**Flag:** ✗ Gap ≥ 3 effective taps.

---

## WF-03: Plan sessions for the next parade night

**Frequency:** Weekly  
**Human need:** "Decide what will be taught next Thursday and who will deliver it."

### Current path (via Parade Nights)
1. Nav → Parade Nights (1)
2. Find next night in list (0–1 scroll)
3. Click night to expand (1)
4. Click + Add Session or Guided mode (1)
5. Set period number, cadet group, curriculum item (3 fields)
6. Set facilitator (1 click + selection)
7. Set room (1 click + selection)
8. Save (1)
9. Repeat for each session (6–8 clicks each)

| | Screens | Clicks | Fields | Decisions |
|---|---|---|---|---|
| **Current** | 2 | 12–16 for 3 sessions | 9+ fields | 6 (period, class, curriculum × 3, facilitator × 3, room × 3) |
| **Ideal** | 1 | 8–10 for 3 sessions | 6 fields | 3 |
| **Gap** | -1 | -4 to -6 | -3 | -3 |

**Ideal path:** Dashboard → Tonight section → click next night → inline session builder (one card per period, pre-populated with defaults from timing template, class set from last visit) → confirm or change → Save. Facilitator suggestions appear inline without a separate lookup.

**Flag:** ✗ Gap ≥ 3. Session creation requires too many individual field decisions per session. Defaults (last-used facilitator, last-used room) would reduce per-session cost.

---

## WF-04: Set up the Training Year (annual)

**Frequency:** Once per year (critical path)  
**Human need:** "Create a new training year so the system knows when we parade and what groups we have."

### Current path
1. Nav → Activities (1)
2. Scroll past activities table (1)
3. Scroll past Getting Help card (1)
4. See Planning Year selector → + New Year (1)
5. Fill year setup form: name, start date, end date, terms (4 fields)
6. Save year (1)
7. Parade Dates card appears → Generate (1)
8. Generate Dates modal: set day of week, term boundaries (3–4 fields + decisions)
9. Preview → confirm (2)
10. Training Classes card → + Add Training Class (1)
11. Add class: name, stage, set active (3 fields)
12. Save (1)
13. Repeat for each class (4–5 clicks each × 3–5 classes)

| | Screens | Clicks | Fields | Decisions |
|---|---|---|---|---|
| **Current** | 2 (Activities + modal) | 15–20 | 10–14 | 6–8 |
| **Ideal** | 1 (wizard) | 8–10 | 8 | 4 |
| **Gap** | -1 | -7 to -10 | -2 to -6 | -2 to -4 |

**Ideal path:** Getting Started → Step: Set Up Your Year → Guided Year Setup Wizard (already exists in PW; connect to from Main TMS) → one wizard, 4 steps: (1) Year name/dates, (2) Parade day/generate dates, (3) Training classes, (4) Confirm. 10 clicks, 1 wizard, 8 fields.

**Flag:** ✗ Gap ≥ 3. The GuidedYearSetupModal in PW already implements this wizard — it is not surfaced from Main TMS.

---

## WF-05: Create and assign a facilitator to a session

**Frequency:** Weekly (adding a new person) / Multiple times per night  
**Human need:** "This person will deliver Session 2 next Thursday."

### Current path (new facilitator + assignment)
1. Nav → Facilitators (1)
2. + Add Facilitator (1)
3. Fill: given name, family name, rank, type, subject areas (5 fields)
4. Save (1)
5. Nav → Parade Nights (1)
6. Find night (0–1 scroll)
7. Click night (1)
8. Session row → Quick Edit (1)
9. Facilitator field: type to search / select (1)
10. Save (1)

| | Screens | Clicks | Fields | Decisions |
|---|---|---|---|---|
| **Current** | 3 (Facilitators, Parade Nights, Quick Edit modal) | 9–10 | 5 + 1 | 2 |
| **Ideal** | 2 | 7 | 5 | 1 |
| **Gap** | -1 | -2 to -3 | -1 | -1 |

**Flag:** ✗ Minor gap (2–3). The path is acceptable if the facilitator record already exists (reduces to 4 clicks). The multi-screen cost is inherent to having separate management pages.

---

## WF-06: Print the training program for tonight

**Frequency:** Weekly  
**Human need:** "Get the printout for tonight's parade."

### Current path A (toolbar shortcut — best path)
1. Toolbar → Print Program button (1 click)
2. Parade night auto-selected or select from dropdown (0–1 click)
3. Browser print (1 click)

| | Screens | Clicks | Fields | Decisions |
|---|---|---|---|---|
| **Current (A)** | 1–2 | 2–3 | 0 | 0–1 |
| **Ideal** | 1 | 2 | 0 | 0 |
| **Gap** | 0 | 0 | — | — |

**Flag:** ✓ No gap. The toolbar shortcut is effective. If the user does not discover the shortcut and uses Nav → Weekly Program instead: 3 clicks, still acceptable.

---

## WF-07: See which parade nights are not yet ready

**Frequency:** Weekly  
**Human need:** "Which of my upcoming nights still need session plans?"

### Current path
1. Dashboard → Section A — Tonight & This Week (visible, no click)
2. Upcoming readiness cards show next 8 nights with readiness scores

| | Screens | Clicks | Fields | Decisions |
|---|---|---|---|---|
| **Current** | 1 | 0 | 0 | 0 |
| **Ideal** | 1 | 0 | 0 | 0 |
| **Gap** | 0 | 0 | — | — |

**Flag:** ✓ No gap. This works well.

---

## WF-08: Record a school holiday period

**Frequency:** 4 times per year (once per term break)  
**Human need:** "We don't parade in the holidays — add the school holiday dates."

### Current path A (via Activities header button — best path)
1. Nav → Activities (1)
2. + Add Holiday button in page header (1)
3. Fill: name, start date, end date, type (4 fields)
4. Save (1)

| | Screens | Clicks | Fields | Decisions |
|---|---|---|---|---|
| **Current (A)** | 2 | 3 | 4 | 1 |
| **Ideal** | 2 | 3 | 3 | 1 |
| **Gap** | 0 | 0 | -1 | 0 |

**Note:** Path A is correct and short. Problem is discoverability: a user following Getting Started → "Add holidays" may be directed to Activities → Planning Year → Holidays card → + Add Holiday (7 taps). The function itself is fast once found; the gap is in the discovery path.

**Flag:** ✓ No effort gap once discovered. Discoverability gap recorded in CF-04.

---

## WF-09: Check which cadet classes are behind schedule

**Frequency:** Monthly  
**Human need:** "Is any class behind where they should be at this point in the year?"

### Current path
1. Dashboard → scroll to Section C (1 scroll)
2. Training Class progress chart visible (if classes exist — conditional)
3. (Optional) Mission Backlog → Activities → year → Mission Backlog → filter by class

| | Screens | Clicks | Fields | Decisions |
|---|---|---|---|---|
| **Current** | 1 (Dashboard) | 1 scroll | 0 | 0 |
| **Ideal** | 1 | 0 | 0 | 0 |
| **Gap** | 0 | -1 scroll | — | — |

**Note:** The class-level chart is conditional — only displays when Training Classes exist. When they don't exist, the user cannot determine class progress at a glance. The Mission Backlog path is the more precise tool but requires 7 taps.

**Flag:** Minor. Dashboard coverage is good if classes exist.

---

## WF-10: Add a wing-level activity to the squadron view

**Frequency:** 0–2 times per year (wing-only action)  
**Human need:** (wing_admin) "Add a wing event so squadrons can see it."

### Current path (wing_admin)
1. Nav → Wing Activities (1)
2. + Add Wing Activity (1)
3. Fill form: name, date, type, importance, audience, prep notes (6 fields)
4. Save (1)

| | Screens | Clicks | Fields | Decisions |
|---|---|---|---|---|
| **Current** | 2 | 3 | 6 | 2 |
| **Ideal** | 2 | 3 | 5 | 1 |
| **Gap** | 0 | 0 | -1 | -1 |

**Flag:** ✓ No significant gap.

---

## WF-11: Find what a specific facilitator has delivered this year

**Frequency:** Monthly (staff management)  
**Human need:** "How many sessions has [name] delivered? Are they overloaded?"

### Current path
1. Nav → Facilitators (1)
2. Find facilitator row (0–1 scroll or search)
3. Click Stats icon (1)
4. View stats drill-down: sessions by status, by phase, load score

| | Screens | Clicks | Fields | Decisions |
|---|---|---|---|---|
| **Current** | 1 + modal | 3 | 0 | 0 |
| **Ideal** | 1 | 2 | 0 | 0 |
| **Gap** | 0 | -1 | — | — |

**Flag:** ✓ Acceptable.

---

## WF-12: Plan a term from the Planning Workspace

**Frequency:** Quarterly (at start of each term)  
**Human need:** "I want to see the whole term and plan what each class is doing each night."

### Current path
1. Nav → Planning Workspace ↗ (opens new tab) (1)
2. PW loads — select planning year if not pre-selected (0–1)
3. Switch view to Term view (1)
4. Click parade night to plan (1)
5. Right drawer opens → fill session (multiple steps per session)

| | Screens | Clicks | Fields | Decisions |
|---|---|---|---|---|
| **Current** | 2 (tabs) | 4 + per-session cost | 2 per session | 1 per session |
| **Ideal** | 2 | 3 + per-session cost | 2 per session | 1 per session |
| **Gap** | 0 | -1 | — | — |

**Flag:** ✓ No significant gap once in PW. The cost is the tab context switch (1 tap), which is inherent to the two-frontend architecture.

---

## WF-13: Find and resolve a planning conflict

**Frequency:** Monthly  
**Human need:** "There is a conflict warning — what is it and how do I fix it?"

### Current path
1. PW → conflict badge on parade night card (visible without nav)
2. Click night or session (1)
3. Right drawer shows conflict details and resolution options (0)
4. Choose resolution: override with reason (1 click + 1 field)
5. Save (1)

| | Screens | Clicks | Fields | Decisions |
|---|---|---|---|---|
| **Current** | 1 (PW) | 3 | 1 | 1 |
| **Ideal** | 1 | 3 | 1 | 1 |
| **Gap** | 0 | 0 | — | — |

**Flag:** ✓ Works well.

---

## WF-14: Add a new room to the resources list

**Frequency:** 1–2 times per year  
**Human need:** "We now have access to a new training room."

### Current path
1. Nav → Locations and Resources (1)
2. + Add Room (1)
3. Fill: name, type, capacity (3 fields)
4. Save (1)

| | Screens | Clicks | Fields | Decisions |
|---|---|---|---|---|
| **Current** | 2 | 3 | 3 | 0 |
| **Ideal** | 2 | 3 | 3 | 0 |
| **Gap** | 0 | 0 | — | — |

**Flag:** ✓ No gap.

---

## WF-15: Create a new user account

**Frequency:** 2–5 times per year  
**Human need:** "I need to give [name] access to the system."

### Current path
1. Nav → Account Management (1)
2. + Add Account (1)
3. Fill: display name, role (select), flight (optional) — code is auto-generated (2–3 fields)
4. Save → one-time code display (1)
5. Record/share the code securely (human action)

| | Screens | Clicks | Fields | Decisions |
|---|---|---|---|---|
| **Current** | 2 | 3 | 2–3 | 1 (role) |
| **Ideal** | 2 | 3 | 2 | 1 |
| **Gap** | 0 | 0 | 0 | 0 |

**Flag:** ✓ No gap. The one-time code display is well-handled.

---

## WF-16: Review curriculum delivery for the year (annual review)

**Frequency:** Once per year (end-of-year review)  
**Human need:** "What did we cover? What did we miss?"

### Current path
1. Nav → Curriculum (1)
2. Filter by progress: "Unscheduled" (1)
3. Review list (0)
4. Export XLSX for a record (1)
5. OR: Nav → Dashboard → Section C → Curriculum Progress charts

| | Screens | Clicks | Fields | Decisions |
|---|---|---|---|---|
| **Current** | 2 | 3–4 | 1 | 1 |
| **Ideal** | 1 | 2 | 0 | 0 |
| **Gap** | -1 | -2 | -1 | -1 |

**Flag:** ✓ Minor — acceptable. A dedicated "End of Year Report" view would improve this but is not critical.

---

## WF-17: Check tonight's readiness and take any required actions

**Frequency:** Weekly (day of parade)  
**Human need:** "Is everything ready for tonight?"

### Current path
1. Dashboard → Section A — Tonight (visible immediately on login, 0 clicks)
2. See readiness score, sessions, facilitators
3. If action needed: click action link → Needs Attention (1) or session (2)

| | Screens | Clicks | Fields | Decisions |
|---|---|---|---|---|
| **Current** | 1 (+ modal/nav if action) | 0–2 | 0 | 0–1 |
| **Ideal** | 1 | 0–1 | 0 | 0 |
| **Gap** | 0 | 0 to -1 | — | — |

**Flag:** ✓ Works well. Dashboard Section A correctly surfaces this.

---

## WF-18: Archive a departed facilitator

**Frequency:** 2–4 times per year  
**Human need:** "This person has left — remove them from active assignments."

### Current path
1. Nav → Facilitators (1)
2. Find facilitator (0–1 scroll or search = 1)
3. Archive button (1)
4. Confirm (1)

| | Screens | Clicks | Fields | Decisions |
|---|---|---|---|---|
| **Current** | 1 | 4 | 0 | 1 |
| **Ideal** | 1 | 3 | 0 | 1 |
| **Gap** | 0 | -1 | — | — |

**Flag:** ✓ No significant gap.

---

## WF-19: See what has changed since last login

**Frequency:** Weekly  
**Human need:** "What happened while I was away?"

### Current path
1. Nav → Needs Attention (1)
2. Scroll to bottom to find "What Changed?" section (1)
3. Select time window (1)
4. Review changes

| | Screens | Clicks | Fields | Decisions |
|---|---|---|---|---|
| **Current** | 2 | 3 | 0 | 1 (time window) |
| **Ideal** | 1 | 1 | 0 | 0 |
| **Gap** | -1 | -2 | — | -1 |

**Ideal path:** Dashboard → "Last Activity" section or card showing changes since last login, auto-calculated. Or persistent notification badge.

**Flag:** ✗ Gap ≥ 2. "What Changed?" is buried below the operational action items. A Training Officer who logs in wanting to see what happened first would need to scroll past a potentially long list of action items to reach it.

---

## WF-20: Change the parade day of week (moving from Thursday to Tuesday)

**Frequency:** Once per year (if squadron changes parade day)  
**Human need:** "We're moving from Thursdays to Tuesdays starting next term."

### Current path
1. Nav → Settings (1)
2. Parade Day → change dropdown (1)
3. Save Settings (1)
4. Note: changing parade day in Settings only affects future date generation, not existing dates
5. Existing parade nights are NOT automatically updated (separate action via PW → Update Future Parade Nights)
6. PW → Update Future Parade Day modal (separate app tab = 1)
7. Select new day and from date (2 fields)
8. Preview → confirm (2)

| | Screens | Clicks | Fields | Decisions |
|---|---|---|---|---|
| **Current** | 3 (Settings + PW + modal) | 7–8 | 3–4 | 2 |
| **Ideal** | 1 (guided modal) | 4 | 2 | 1 |
| **Gap** | -2 | -3 to -4 | -1 to -2 | -1 |

**Ideal path:** Nav → Settings → Parade Day change → confirmation dialog: "Do you want to update existing future parade nights too? [Yes — from this date] [No — only new generation]" → one action handles both. 

**Flag:** ✗ Gap ≥ 3. The two-step nature (Settings update + PW update) requires users to know that Settings alone is not sufficient. A Training Officer who only changes Settings would discover later that their existing parade nights are still on Thursdays. The disconnect between Main TMS Settings and PW's Update Future Parade Day is a workflow integrity gap.

---

## Consolidated findings

### Workflows with gap ≥ 3 (flag)

| WF | Workflow | Current clicks | Ideal clicks | Gap | Root cause |
|---|---|---|---|---|---|
| WF-01 | Record last parade night outcomes | 13–17 | 4–6 | **-9 to -11** | No bulk "record outcomes" workflow |
| WF-04 | Set up Training Year | 15–20 | 8–10 | **-7 to -10** | Buried in Activities; wizard in PW not linked |
| WF-02 | Find outstanding curriculum (Mission Backlog) | 7 effective | 3 | **-4** | Mission Backlog buried |
| WF-20 | Change parade day of week | 7–8 | 4 | **-3 to -4** | Two-step: Settings + PW disconnect |
| WF-19 | See what changed since last login | 3 | 1 | **-2** | What Changed? buried below action items |
| WF-03 | Plan sessions for a parade night | 12–16 | 8–10 | **-4 to -6** | Repetitive per-session decisions; no defaults |

### Workflows with no significant gap (well-designed)

- WF-06: Print training program (toolbar shortcut effective)
- WF-07: See which nights are not ready (Dashboard Section A)
- WF-13: Find and resolve a planning conflict (PW right-drawer inline)
- WF-14: Add a room
- WF-15: Create a user account
- WF-17: Check tonight's readiness (Dashboard Section A)

