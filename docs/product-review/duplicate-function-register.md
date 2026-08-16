# AAFC TMS — Duplicate Function Register

**Review:** Post-Gap Human Workflow, Architecture and Design Review — Stage 1  
**Date:** 2026-08-16

**Classification system:**
- **A — Primary home:** The canonical, first-class location of this function
- **B — Contextual shortcut:** The same function reached from a different, contextually relevant place; data is shared; the shortcut provides value without confusion
- **C — Genuine duplicate:** Two entry points to the same function that both claim to be the primary home; creates confusion about which to use
- **D — Orphaned function:** A function that appears in a location with no conceptual relationship to it; not a shortcut — it is misplaced
- **E — Similar appearance, different function:** Two functions that look or sound the same but do different things; risk of user confusion

---

## Section 1: Type B — Contextual shortcuts (expected, acceptable)

These duplicates are intentional and correct. The user reaches the same function from the most relevant context. No action required.

| Function | Primary location (A) | Shortcut location (B) | Assessment |
|---|---|---|---|
| Add Holiday | Activities → Planning Year → Holidays card → + Add Holiday | Activities page header → + Add Holiday button | Header button is a useful direct shortcut for users who know they want to add a holiday without selecting a year. Both call the same modal. ✓ |
| Generate Parade Dates | Activities → Planning Year → Parade Dates card → Generate | Parade Nights page header → Generate Parade Nights | Parade Nights is arguably the better primary home (PN page is about parade nights; Activities is not). Both call the same generator modal. ✓ Mark Parade Nights as primary; Activities as shortcut. |
| Session edit (from Main TMS) | Parade Nights → night → session row → Quick Edit | Dashboard → upcoming night card → session chip (if clickable) | Parade Nights is primary. Dashboard card is a shortcut. ✓ |
| Print Weekly Program | Weekly Program page → Print button | Toolbar → Print Program button | Toolbar is a shortcut. ✓ |
| Facilitator assignment in session | Session Quick Edit modal → Facilitator field | PW Right drawer → session form → Facilitator field | Two contexts, same underlying facilitator record. ✓ |
| Mission Backlog (view) | Activities → Planning Year → Mission Backlog card | PW → Bottom drawer → Mission Backlog tab | Main TMS Activities is the (current) primary; PW tab is a contextual shortcut for use during planning. ✓ After IA-01 (Annual Plan nav), Annual Plan page becomes primary. |
| Rooms management | Resources & Training Areas page | PW → Bottom drawer → Rooms tab | Resources page is primary. PW drawer tab is a contextual shortcut. ✓ |
| Equipment management | Resources & Training Areas page | PW → Bottom drawer → Equipment tab | Same as rooms. ✓ |
| Facilitators list | Facilitators page | PW → Bottom drawer → Facilitators tab | Facilitators page is primary. PW provides contextual view + leave management. ✓ |
| Facilitator schedule (timeline) | PW → Facilitator Schedule route | Main TMS Facilitators page → stats/charts (partial; not full timeline) | PW has the full timeline; Main TMS has aggregated charts. Different format, same data. ✓ |
| Weekly Program view | Weekly Program page (Main TMS) | PW → Weekly Program route | Same output; two entry points across two apps. ✓ — Both are primary in their respective frontends. |
| Calendar view | Training Calendar page (Main TMS) | PW → Calendar route | Same. ✓ |
| Parade Nights list | Parade Nights page (Main TMS) | PW → Parade Nights route | Same. ✓ — Two-frontend design; both are equally primary. |
| Dashboard | Dashboard page (Main TMS) | PW → Dashboard route | Same. ✓ |
| Curriculum list | Curriculum page (Main TMS) | PW → Curriculum route | Same. ✓ — PW version is read-only. |
| Accounts management | Account Management page (Main TMS) | PW → Accounts route | Same. ✓ |
| Access Code change | Settings → Change my access code | PW → Access Codes route | Two entry points to the same API. ✓ |
| Needs Attention / Action Items | Needs Attention page (Main TMS) | PW → Action Items route | Same. ✓ |
| Audit log | Account Management / Wing view (Main TMS) | PW → Audit route | Same. ✓ |
| Resource clash checker | Resources page (PW) | No equivalent in Main TMS (Main TMS Resources page does not have the clash check) | PW only — no duplicate. |

---

## Section 2: Type C — Genuine duplicates (confusion risk)

These are cases where two functions appear to claim equal authority over the same action. They may point to the same data but present as different authorities.

| Function | Instance 1 | Instance 2 | Confusion risk | Recommendation |
|---|---|---|---|---|
| Create a session | Parade Nights → night → + Add Session (Main TMS, `POST /api/sessions`) | PW → click empty cell → New Session (Planning Workspace, `POST /api/planning/parade-dates/.../sessions`) | MODERATE — two different API paths to the same sessions table. A user creating a session in Main TMS vs PW may get different input shapes, but the result is the same row. If a user uses both tools interchangeably, sessions created in one are visible in the other — correct. However: the Main TMS path triggers the Night Builder, the PW path triggers the PW right drawer. Behaviour differs even if the data is the same. | Acceptable under the two-frontend architecture. Document this clearly for admins. Consider adding "Open in PW" context button from the Main TMS night builder for cross-app continuity. |
| Update a room | Resources page → edit room (Main TMS, `PATCH /api/training-areas/{id}`) | PW → Bottom drawer → Rooms → edit room (PW, `PATCH /api/planning/locations/{id}`) | LOW — same database record; UI differences only. User might not know which location to use for edits. | Acceptable — PW rooms tab calls the same endpoint as Main TMS via a different UI. Label clarification ("manage rooms" vs "add room here") would reduce confusion. |
| Update parade day settings | Unit Settings → Parade Day selector | PW → Update Future Parade Nights modal | HIGH — Settings changes the default for new generation only. PW updates existing dates. A user who only changes Settings believes they have updated their schedule; they have not. | **This is a functional integrity gap (see WF-20).** The two controls must either be linked (Settings change triggers offer to also update existing dates) or Settings must visually clarify the scope of the change ("this changes the default for new date generation only — use Planning Workspace to update existing dates"). |

---

## Section 3: Type D — Orphaned functions (misplaced)

These functions appear in a location with no conceptual relationship to them. They are not shortcuts — they are in the wrong home.

| Function | Current location | Why it is orphaned | Correct home |
|---|---|---|---|
| Planning Year selector | Activities page | "Activities" means AAFC events; year setup has no relationship to activities | New "Annual Plan" top-level nav section |
| + New Year button | Activities page | Same as above | Annual Plan section |
| Training Classes card | Activities → Planning Year | Training classes are a staffing/curriculum function, not an activities function | Annual Plan section |
| Parade Dates card | Activities → Planning Year | Parade dates are a scheduling function, not an activities function | Annual Plan section |
| Holiday & Stand-down Periods card | Activities → Planning Year | Holidays are a calendar function with some overlap to activities, but they belong to year planning | Annual Plan section |
| Mission Backlog card | Activities → Planning Year | Mission backlog is a curriculum/planning function; no relationship to activities | Annual Plan section OR Dashboard card OR top-level nav |
| Class Planning Forecasts card | Activities → Planning Year | Forecasts are a planning function | Annual Plan section |
| Getting Help text | Activities page | Help has no relationship to activities | Persistent help icon in nav bar OR dedicated Help page |
| Reference Data (Training Stages, Facilitator Types, Subject Areas) | Account Management → Reference Data section | Reference data is about configuring the system's taxonomy, not about user accounts | Unit Settings → Reference Data section OR dedicated Admin section |
| Flights management | Account Management → Flights section | Flights are a cadet organisational grouping (sub-squadron), not account management | Unit Settings → Organisational Structure OR a dedicated structure section |
| Display Size preference | Unit Settings page (sqn_admin only) | Display size is a per-user preference that should be available to ALL roles (sqn_general users cannot access Settings) | Accessible from every page (user avatar dropdown or settings icon in toolbar) |

---

## Section 4: Type E — Similar appearance, different function

These pairs look or sound similar but do different things. Risk: a user may use the wrong one.

| Pair | Function 1 | Function 2 | Confusion scenario | Recommendation |
|---|---|---|---|---|
| "Activities ▲" button (PW bottom drawer) | Opens the PW bottom drawer containing 8 tabs: Activities, Mission Backlog, Facilitators, Schedule, Rooms, Equipment, Holidays, Notices | "Activities" nav item (Main TMS) | A user familiar with Main TMS sees "Activities" in PW and expects AAFC events, not the multi-purpose reference drawer. | Rename PW drawer button: "Planning Tools ▲" or "Reference Panel ▲" |
| Facilitator Schedule (PW route) | A per-facilitator Gantt timeline showing sessions and leave across the year | Workload Distribution chart (Facilitators page) | Both answer "how busy are facilitators?" but in different formats and timeframes | Low confusion risk — clearly different visual formats. No action needed. |
| "Needs Attention" (Main TMS page) | Operational alerts (P0-P4) + Mission Backlog items (P5) + What Changed? | "Needs Attention" (PW Action Items route) | Same concept, but Main TMS version includes P5 backlog items making it much longer; PW version allows manual creation of action items | Acceptable — different entry points to a shared operational concept. Main TMS should separate P5 from P0-P4. |
| Session status "Not Delivered" | A session that was not delivered on the night for any reason | Cancellation status | Both represent a session that did not happen; the distinction is whether it was cancelled before the night (planned cancellation) or not delivered during the night | Low confusion risk for experienced users. May confuse new users. Consider tooltip or inline explanation. |
| "Planning Year" (PW concept) | A data container for all forward planning: parade dates, anchors, sessions, conflicts | "Training Year" (used in other contexts / user language) | Users may say "training year" to mean either the PW planning year or just the calendar year. The system uses "Planning Year" but users think "Training Year." | Align UI label to "Training Year" throughout (already partially done in some UI labels). |
| Close Parade Night | A finalisation action that locks the night and prevents further edits | Archive Parade Night | Both make a night "done" but Close preserves it; Archive hides it | Consider renaming "Archive" to "Hide from main list" for clarity. |

---

## Section 5: Duplication heat map

The Activities page concentrates the most D-type (orphaned) functions, all of which should move to a dedicated Annual Plan section. This is the single highest-priority duplication remediation.

```
ACTIVITIES PAGE — D-type concentration
├─ AAFC Activities list (correct — A)
├─ Getting Help text (D — should move to Help)
├─ Planning Year selector (D — should move to Annual Plan)
│  ├─ Parade Dates card (D)
│  ├─ Holiday & Stand-down card (D)
│  ├─ Training Classes card (D)
│  ├─ Mission Backlog card (D)
│  └─ Class Forecasts card (D)
└─ Activity Type/Importance/Audience filters (correct — A)

ACCOUNT MANAGEMENT PAGE — D-type
├─ User Accounts table (correct — A)
├─ Wings table (correct — B for national scope)
├─ Squadrons table (correct — B for wing/national scope)
├─ Flights section (D — should move to Unit Settings)
└─ Reference Data section (D — should move to Unit Settings or Admin)
```

---

## Summary

| Type | Count | Priority |
|---|---|---|
| A — Primary home | All well-identified | — |
| B — Contextual shortcut | ~18 pairs | No action needed |
| C — Genuine duplicate | 3 pairs | 1 functional integrity fix needed (WF-20 parade day) |
| D — Orphaned function | 10 functions | High priority — all within Activities page and Account Management |
| E — Similar appearance | 6 pairs | 1 rename needed (PW "Activities ▲" button); rest acceptable |

