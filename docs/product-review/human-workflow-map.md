# AAFC TMS — Human Workflow Map

**Review:** Post-Gap Human Workflow, Architecture and Design Review — Stage 1  
**Date:** 2026-08-16  
**Author:** Review 1 — Human Workflow and Information Architecture Audit  
**Target user:** Squadron Training Officer (~80 years old, Year 10 English, no technology background)

---

## Natural Training Officer Work Sequence

This map starts from the actual work of a Training Officer — not the existing navigation.

---

## Phase 1: START OF YEAR (typically February–March)

### What the Training Officer is trying to do

> "I need to set up the year so my cadets can train."

### Step-by-step natural workflow

| Step | Human goal | Where it should be | Where it currently is | Friction |
|---|---|---|---|---|
| 1 | "What do I need to do to get started?" | An onboarding checklist, clearly labelled | Getting Started (nav item, visible) | LOW — page exists |
| 2 | "I need to create the Training Year" | Year Setup — a dedicated area | **Activities → scroll down → Planning Year → + New Year** | HIGH — buried under wrong nav label |
| 3 | "What groups of cadets do I have?" | Training Year → Training Classes | **Activities → select year → Training Classes card** | HIGH — nested under Activities |
| 4 | "When do we parade?" | Training Year → Parade Dates → Generate | **Activities → select year → Parade Dates → Generate** | HIGH — nested under Activities |
| 5 | "What holidays will we miss?" | Training Year → Holiday Periods | **Activities → select year → Holiday & Stand-down card OR Activities header** | HIGH — two entry points, both obscure |
| 6 | "What events does Wing have coming up?" | Activities or Calendar | Wing Activities (separate nav, wing_admin only to add) | MEDIUM — squadron read-only |
| 7 | "What curriculum do my cadets need?" | Curriculum | Curriculum page (top level nav) | LOW — correctly placed |
| 8 | "How much unscheduled training is there?" | Mission Backlog | **Activities → select year → Mission Backlog card** | HIGH — buried |
| 9 | "I need to plan the whole year" | Planning Workspace | Planning Workspace ↗ (external link, sometimes invisible) | HIGH — different app, not always configured |

### Key finding — Steps 2–5 all live inside "Activities"

The word "Activities" in the navigation means AAFC-level events (camps, ceremonies, excursions). A Training Officer looking to set up the Training Year does not expect to find it there. This is the single highest-friction discovery problem in the entire application.

---

## Phase 2: PLANNING A TERM (ongoing, typically at term boundaries)

| Step | Human goal | Where it should be | Where it currently is | Friction |
|---|---|---|---|---|
| 1 | "What training is still outstanding?" | Mission Backlog | **Activities → select year → Mission Backlog** | HIGH |
| 2 | "Who is available to deliver?" | Facilitator availability | Planning Workspace → Facilitators tab + leave calendar | MEDIUM — in PW only |
| 3 | "What rooms/equipment do we have?" | Resources | Locations and Resources (nav) | LOW |
| 4 | "I want to plan the term visually" | Term calendar view | Planning Workspace → Term view | MEDIUM — if PW is configured |
| 5 | "Schedule Senior 2 for next Friday" | Planning Workspace | Planning Workspace → parade night → add session | MEDIUM — once inside PW |
| 6 | "Assign facilitator to a session" | Session editor | Parade Nights → session → quick edit → facilitator field | MEDIUM |
| 7 | "See what's still unplanned" | Mission Backlog or Needs Attention | Mission Backlog (Activities) or Needs Attention page | HIGH — two places |

---

## Phase 3: BEFORE A PARADE NIGHT (weekly)

| Step | Human goal | Where it should be | Where it currently is | Friction |
|---|---|---|---|---|
| 1 | "What is happening tonight?" | Dashboard → Tonight section | Dashboard Section A — Tonight & This Week | LOW — good |
| 2 | "Who is training in which class?" | Parade Night detail | Parade Nights → find night → view sessions | MEDIUM |
| 3 | "Who is delivering?" | Parade Night detail | Parade Nights → session detail | MEDIUM |
| 4 | "Where is each session held?" | Parade Night detail | Parade Nights → session detail | MEDIUM |
| 5 | "Do we have equipment ready?" | Parade Night detail | Parade Nights → session detail | MEDIUM |
| 6 | "Are there unresolved issues?" | Needs Attention | Needs Attention page (nav item) | LOW |
| 7 | "Print the weekly program" | Weekly Program | Weekly Program (nav item) OR toolbar Print button | LOW |

---

## Phase 4: AFTER A PARADE NIGHT (weekly, within 48 hours)

| Step | Human goal | Where it should be | Where it currently is | Friction |
|---|---|---|---|---|
| 1 | "Record what was delivered" | Parade Night → mark sessions done | Parade Nights → find past night → open → session → Quick Edit → record status | HIGH — multiple steps |
| 2 | "Record why something was cancelled" | Same as above | Same as above + reason field | HIGH |
| 3 | "What needs to be rescheduled?" | Needs Attention OR Mission Backlog | Needs Attention (shows outcome-not-recorded) → Missions in Activities | MEDIUM |
| 4 | "Reschedule undelivered training" | Session editor or Planning Workspace | Planning Workspace → Mission Backlog → find item → schedule | MEDIUM |

### Key finding — Outcome recording friction

After a parade night, the Training Officer must: navigate to Parade Nights → find last Thursday's night (in a list of all nights) → open it → find each session → click Quick Edit on each → record outcome. There is no "Record outcomes for last night" shortcut from Dashboard or Needs Attention.

---

## Phase 5: ONGOING MANAGEMENT

| Task | Natural entry point | Current location | Friction |
|---|---|---|---|
| "What requires attention?" | Needs Attention | Needs Attention page ✓ | LOW |
| "Which Training Classes are behind?" | Class progress view | Dashboard → C Curriculum Progress → Class progress chart (when enabled) | MEDIUM — conditional display |
| "Add a new facilitator" | Facilitators | Facilitators page ✓ | LOW |
| "Get help / contact support" | Help | **Getting Help text inside Activities page** | HIGH — wrong location |
| "Change when we parade" | Unit Settings | Unit Settings page | LOW — but isolated from consequences |
| "See recent changes" | What Changed? | Needs Attention page → What Changed? section (bottom) | MEDIUM — below action items |
| "What Activities are approaching?" | Calendar or Activities | Training Calendar OR Activities table | LOW |

---

## Cognitive Walkthrough Summary

For each major workflow, applying the 10-question test:

### "Create a Training Year"

1. Would the user know what to do? NO — they see "Activities" in nav and assume it's about AAFC events, not year setup.
2. Would the user know where to find it? NO — it requires finding Activities, noticing the Planning Year section, and scrolling past the activities table and Getting Help card.
3. Would the wording make sense? NO — "Activities" does not suggest year/class/date setup.
4. Would they recognise the action achieves their goal? UNCERTAIN — "+ New Year" in a dropdown inside Activities is not prominent.
5. After acting, would they understand what happened? YES — confirmation is visible.
6. Would they know what to do next? PARTIAL — next steps (add classes, dates) are visible below.
7. Would they need to remember information? NO.
8. Would they need to enter information the system already knows? NO.
9. Would they need to switch between Main TMS and PW? YES — dates/classes in Main TMS, then PW for calendar planning.
10. Is there a simpler path? YES — a dedicated "Training Year Setup" or "Annual Plan" section.

### "Record outcomes for last parade night"

1. Would the user know what to do? PARTIAL — Needs Attention shows "Outcome needed" items.
2. Would the user know where to find each outcome? NO — each item links to Quick Edit but from a different page.
3. Would the wording make sense? YES — "Record delivered, cancelled or not delivered."
4. Would they recognise the action? YES — once in Quick Edit.
5. After acting, would they understand what happened? YES.
6. Would they know what to do next? NO — no aggregate confirmation that the night is fully recorded.
7. Remember information? NO.
8. Re-enter known information? NO.
9. Switch frontends? NO.
10. Simpler path? YES — a "Record last night's outcomes" card on Dashboard.

### "Find what training is still unscheduled for Senior 2"

1. Know what to do? NO — Mission Backlog is not in nav.
2. Know where to find it? NO — it requires finding Activities, selecting a year, scrolling to Mission Backlog, filtering by class.
3. Wording make sense? YES — "Mission Backlog" is clear once found.
4. Recognise the action? YES.
5. After acting? YES.
6. Know next step? PARTIAL — would need to go to Planning Workspace.
7. Remember information? NO.
8. Re-enter info? NO.
9. Switch frontends? YES — to Planning Workspace.
10. Simpler path? YES — Mission Backlog deserves its own nav item or prominent Dashboard card.

---

## Top 20 Highest-Friction Workflows

| # | Workflow | Priority | Root cause |
|---|---|---|---|
| 1 | Create/select Training Year | P1 | Buried in Activities |
| 2 | Create Training Classes | P1 | Buried in Activities → Planning Year |
| 3 | Generate Parade Dates for the year | P1 | Buried in Activities → Planning Year |
| 4 | Find Mission Backlog (unscheduled training) | P1 | Buried in Activities → Planning Year |
| 5 | Get Help / contact support | P1 | Buried inside Activities page |
| 6 | Discover Planning Workspace exists | P1 | External link, conditionally visible, no guidance |
| 7 | Record outcomes for last parade night | P2 | No bulk "record last night" workflow |
| 8 | Find "what does Senior 2 still need?" | P2 | Mission Backlog hidden under Activities |
| 9 | Add holiday/stand-down periods | P2 | Entry point in Activities (two locations, neither obvious) |
| 10 | Understand Planning Workspace tabs (8 tabs in bottom drawer) | P2 | No onboarding within PW |
| 11 | Navigate between Main TMS and Planning Workspace without losing context | P2 | Different apps, requires re-selection of year/class |
| 12 | See class-level curriculum progress | P2 | Only visible on Dashboard when classes exist; not directly accessible |
| 13 | Distinguish "Activities" (AAFC events) from "Activities" (the page containing planning setup) | P2 | Same word used for different concepts |
| 14 | Understand why some Needs Attention items are backlog vs operational | P2 | P5 items (unscheduled curriculum) swamp P0-P1 operational items |
| 15 | Find timing templates | P3 | Unit Settings → scroll down to Timing Templates card |
| 16 | Know what "Mission Backlog" means (terminology) | P3 | Military terminology may be unfamiliar |
| 17 | Find facilitator suggestions for a session | P3 | Available in Quick Edit (quick-entry mode) but not labelled prominently |
| 18 | Export curriculum or delivery data | P3 | Export buttons on Curriculum page, not obvious |
| 19 | Find CEA (Cadet Enterprise Application) activities | P3 | Mixed into activities list with no clear separation |
| 20 | Access Wing events from Squadron view | P3 | Wing Events appear as read-only overlays on Activities, not well-signposted |

---

## Proposed Simplification Backlog

These are proposals for Review 2 and 3 — no code changes in Review 1.

### IA-01 — Annual Plan as a first-class nav item
**Problem:** Training Year setup, Training Classes, Parade Dates, Holidays, and Mission Backlog all live inside the Activities page — a page primarily associated with AAFC events, not year setup.
**Proposal:** Create a dedicated "Annual Plan" or "Training Year" section at the top level of navigation. Move Planning Year, Training Classes, Parade Dates, Holidays, and Mission Backlog there. Activities page reverts to being only about Activities/Events.
**Priority:** P1
**Impact:** Resolves Friction items 1–4 above.

### IA-02 — Help as a top-level item
**Problem:** Getting Help (contact info, common tasks) lives inside Activities.
**Proposal:** Move Getting Help to a persistent help icon (?) in the nav bar or a dedicated Help page.
**Priority:** P1

### IA-03 — Mission Backlog visibility
**Problem:** "What training is still outstanding?" has no clear answer from the Dashboard or Needs Attention.
**Proposal:** Add Mission Backlog as either (a) a prominent card on Dashboard or (b) a top-level nav item. Dashboard card shows count by class with direct link.
**Priority:** P1

### IA-04 — Record Last Night's Outcomes workflow
**Problem:** No fast path from "parade night happened" to "outcomes recorded."
**Proposal:** Dashboard → Section A (Tonight & This Week) — when a past parade night has unrecorded outcomes, show a "Record [date] outcomes" primary action card that opens the parade night directly in outcome-recording mode.
**Priority:** P2

### IA-05 — Needs Attention — separate operational from backlog
**Problem:** P5 items (all unscheduled curriculum) swamp operational P0-P4 items.
**Proposal:** Split Needs Attention into two sections: "Requires Action Now" (P0-P4) and "Planning Backlog" (P5 — curriculum not yet scheduled). Only "Requires Action Now" shows by default; backlog is a collapsed secondary view.
**Priority:** P2

### IA-06 — Planning Workspace discovery
**Problem:** New users do not know Planning Workspace exists. The link is conditional and external.
**Proposal:** Integrate a persistent "Open in Planning Workspace" action within relevant pages (Parade Nights, Mission Backlog) with a tooltip explaining what PW is.
**Priority:** P2

### IA-07 — Navigation labels match user language
**Problem:** Nav uses some technical/system labels. Current issues:
- "Locations and Resources" vs page title "Resources & Training Areas" (inconsistent)
- "Activities" means both "AAFC events" and "the page where everything lives"
**Proposal:** Once IA-01 is implemented, rename "Activities" to "Events" or "AAFC Activities". Standardise "Locations and Resources" vs "Resources & Training Areas".
**Priority:** P3

### IA-08 — Getting Started as guided workflow
**Problem:** Getting Started shows a checklist but not a guided sequence. It links to pages without explaining what to do on each page.
**Proposal:** Getting Started becomes a narrative guide: "Step 1: Create your Training Year (we'll create one together)" with an inline form/wizard, not just a link to another page.
**Priority:** P2

