# AAFC TMS — Findability Audit

**Review:** Post-Gap Human Workflow, Architecture and Design Review — Stage 1  
**Date:** 2026-08-16  
**Method:** For every user-facing function, count the number of taps/clicks and cognitive decisions from application entry (after login) to reaching the function. Flag any function reachable only via a path longer than 3 taps.  
**Standard:** ≤ 3 taps from entry = acceptable. 4 taps = review. ≥ 5 taps = critical finding.  
**Scope:** Squadron Training Officer (sqn_admin), Desktop browser, Main TMS + Planning Workspace

---

## Tap counting method

- **Tap 0:** Application is open and the user is on the landing page (Dashboard).
- Each required navigation click, page load, scroll-to-find, and decision counts as one tap.
- Scrolling to find a section that is not visible above the fold counts as one tap.
- Selecting from a dropdown (e.g., year selector, class filter) counts as one tap.
- Completing a form and submitting counts as one tap per distinct field group.

---

## Section 1: Functions within 3 taps (acceptable)

| Function | Path | Taps from Dashboard | Notes |
|---|---|---|---|
| Dashboard | Already there | 0 | — |
| Training Calendar | Nav → Calendar | 1 | — |
| Parade Nights list | Nav → Parade Nights | 1 | — |
| Weekly Program view | Nav → Weekly Program | 1 | — |
| Curriculum list | Nav → Curriculum | 1 | — |
| Facilitators list | Nav → Facilitators | 1 | — |
| Rooms and Equipment | Nav → Locations and Resources | 1 | — |
| Needs Attention | Nav → Needs Attention | 1 | — |
| Unit Settings | Nav → Settings | 1 | — |
| Activities (AAFC events) | Nav → Activities | 1 | — |
| Account Management | Nav → Account Management | 1 | — |
| Open Planning Workspace | Nav → Planning Workspace ↗ | 1 | External tab |
| Getting Started | Nav → Getting Started | 1 | — |
| Add Parade Night | Nav → Parade Nights → + Add Parade Night | 2 | — |
| Add Facilitator | Nav → Facilitators → + Add Facilitator | 2 | — |
| Add Room | Nav → Resources → + Add Room | 2 | — |
| Add Equipment | Nav → Resources → + Add Equipment | 2 | — |
| Add AAFC Activity | Nav → Activities → + Add Activity | 2 | — |
| Add Account | Nav → Accounts → + Add Account | 2 | — |
| Print Weekly Program | Nav → Weekly Program → Print | 2 | — |
| Print Program (shortcut) | Toolbar → Print Program button | 1 | — |
| Curriculum by phase | Nav → Curriculum → [phase tab] | 2 | — |
| Curriculum Matrix | Nav → Curriculum → Matrix tab | 2 | — |
| Parade Night detail | Nav → Parade Nights → click night | 2 | — |
| Add Session to night | Parade Nights → click night → + Add Session | 3 | — |
| Session Quick Edit | Parade Nights → night → session row → pencil icon | 3 | — |
| Tonight's readiness | Dashboard → Section A | 1 | Visible without scroll on most screens |
| Delivery analytics | Dashboard → Section B | 1 (+ scroll) | Requires scroll on most screens |
| Curriculum progress charts | Dashboard → Section C | 1 (+ scroll) | Requires scroll |
| Audit log | Nav → Account Management → [if wing+] OR PW → Audit | 1 | wing+ only; or PW nav |
| Change access code | Nav → Settings → Change my access code | 2 | — |
| Facilitator Stats | Nav → Facilitators → Stats (chart icon per row) | 2 | — |
| Generate Parade Nights | Nav → Parade Nights → Generate Dates button | 2 | Better location than Activities |
| Copy Sessions to Night | Nav → Parade Nights → night → Copy sessions | 3 | — |
| Save as Template | Nav → Parade Nights → night → Save as template | 3 | — |
| Publish Parade Night | Nav → Parade Nights → night → Publish | 3 | — |
| Close Parade Night | Nav → Parade Nights → night → Close | 3 | — |

---

## Section 2: Functions reachable in 4 taps (review)

| Function | Path | Taps | Finding |
|---|---|---|---|
| Session status history | Nav → Parade Nights → night → session → [history tab in Quick Edit] | 4 | Not a frequent need; acceptable |
| Facilitator leave management | Open PW → Bottom drawer → Facilitators tab → add leave | 4 | PW is a separate tab (1) + bottom drawer (1) + tab (1) + action (1) |
| Curriculum item drill-down (sessions) | Nav → Curriculum → click item → view sessions | 4 | Click in list = 1; drill panel = 1 extra; total = 4 |
| Class Planning Forecast (detail) | Nav → Curriculum → Matrix → expand class → forecast detail | 4 | OR via Activities → year → class forecasts card |
| Resource Clash Checker | PW → Resources → Date picker → Check | 4 (via PW) | Or Main TMS Resources → exists but less prominent |
| Wing HQ Calendar | Nav → [requires wing_admin or proxy] | N/A for sqn | Wing+ only |
| Bulk cancel sessions | Nav → Parade Nights → night → [bulk cancel button] | 3–4 | Night must be expanded |
| Template apply to multiple nights | Nav → Parade Nights → [bulk bar] → Apply template | 4 | Requires multi-select |
| Reset another user's code | Nav → Accounts → find user → Reset code | 3–4 | Search adds tap |
| Facilitator subject areas tag edit | Nav → Facilitators → row → Tags | 3–4 | Row-level action |
| Archive Facilitator | Nav → Facilitators → row → Archive | 3–4 | Confirmation modal |
| Archive Training Class | Nav → Activities → year → Training Classes card → Archive button | 5 | ⚠ See Section 3 |
| Timing Template create | Nav → Settings → scroll → + New Template | 3–4 | Scroll to templates card = extra tap |
| Timing Template edit | Nav → Settings → scroll → template → edit | 4–5 | ⚠ See Section 3 |
| Import curriculum CSV | Nav → Curriculum → Import CSV button (national only) | 2 | Admin only; fine |
| Export curriculum | Nav → Curriculum → Export XLSX | 2 | Fine |

---

## Section 3: Functions reachable only in ≥ 5 taps — CRITICAL findings

These are flagged for immediate attention. Five-tap functions are effectively hidden from non-expert users.

---

### CF-01: Create Training Year (Year Setup)
**Path:** Nav → Activities → scroll past Activities table → scroll past Getting Help card → Planning Year selector → + New Year  
**Taps:** 5 (Nav=1, Activities=1, scroll-to-Planning-Year=1, Planning Year section=1, +New Year=1)  
**Severity:** CRITICAL — start-of-year essential task  
**Root cause:** Planning Year setup is buried inside the Activities page under two unrelated sections  
**Proposed resolution:** Annual Plan as a first-class nav item (IA-01)

---

### CF-02: Create Training Classes
**Path:** Nav → Activities → scroll past Activities table → scroll past Getting Help → Planning Year selector → select year → Training Classes card → + Add Training Class  
**Taps:** 6 (Nav=1, Activities=1, scroll=1, year select=1, Training Classes card=1, +Add=1)  
**Severity:** CRITICAL — required before any session can be assigned to a class  
**Root cause:** Same as CF-01  
**Proposed resolution:** Annual Plan as first-class nav item

---

### CF-03: Generate Parade Dates (Annual date generation via Activities)
**Path:** Nav → Activities → scroll → Planning Year → select/create year → Parade Dates card → Generate  
**Taps:** 6  
**Severity:** CRITICAL — required to create the squadron's parade schedule  
**Root cause:** Same as CF-01  
**Note:** Generate Dates is also accessible via Nav → Parade Nights → Generate Parade Nights button (3 taps) — this secondary entry point is better but not intuitive for new users following Getting Started (which links to Activities)

---

### CF-04: Add Holiday / Stand-Down Period
**Path:** Nav → Activities → scroll → Planning Year → select year → Holidays card → + Add Holiday  
**Taps:** 6 (via Activities)  
**Note:** Also accessible via Nav → Activities → + Add Holiday (header button, 2 taps) — but only if the user spots the header button, which is visually competing with + Add Activity and Generate Activities. Most users follow the card-based flow.  
**Severity:** HIGH — annual setup task  
**Proposed resolution:** Move to Annual Plan section

---

### CF-05: Mission Backlog — view outstanding curriculum
**Path:** Nav → Activities → scroll to bottom of page → Planning Year → select year → scroll to Mission Backlog card → view  
**Taps:** 7 (Nav=1, Activities=1, scroll to year=1, year select=1, Activities expand=1, scroll to backlog=1, view=1)  
**Severity:** CRITICAL — one of the most important daily-use functions. A Training Officer asking "what does Senior 2 still need?" must navigate 7 steps to find the answer.  
**Proposed resolution:** Mission Backlog as first-class nav item or prominent Dashboard card

---

### CF-06: Getting Help / Support Contact
**Path:** Nav → Activities → scroll past Activities table → Getting Help card  
**Taps:** 4 (Nav=1, Activities=1, Activities page loads=1, scroll=1)  
**Note:** 4 taps is already a problem; getting help should be 1 tap. The scroll step makes this feel closer to 5.  
**Severity:** HIGH — help must be instantly accessible  
**Proposed resolution:** Persistent help icon (?) in navigation bar

---

### CF-07: Timing Templates — create / edit
**Path:** Nav → Settings → scroll past Squadron Details, Session Structure, Display Size → Timing Templates card → + New Template / edit  
**Taps:** 5 (Nav=1, Settings=1, scroll-past-3-sections=1, Timing Templates card=1, action=1)  
**Severity:** Moderate — infrequent but needed during setup  
**Proposed resolution:** Visible heading jump within Settings; or move Timing Templates higher in the page

---

### CF-08: Planning Workspace discovery (if link not in nav)
**Path:** If Planning Workspace link is not configured in nav (current pilot behaviour for some roles): user must know that PW exists as a separate app. No path from within Main TMS.  
**Taps:** ∞ (unreachable by nav if not configured)  
**Severity:** CRITICAL — PW is a key tool; it must be discoverable  
**Proposed resolution:** Contextual "Open in Planning Workspace" link from Parade Nights and Mission Backlog pages; or ensure PW link is always visible in nav

---

### CF-09: Class Planning Forecasts
**Path:** Nav → Activities → scroll → Planning Year → select year → scroll to Forecasts card  
**Taps:** 6–7  
**Severity:** HIGH — forward planning information deeply buried  
**Proposed resolution:** Surface key forecast on Dashboard (on-track / at-risk summary) or move to Annual Plan

---

### CF-10: Archive or restore a Training Class
**Path:** Nav → Activities → scroll → year → Training Classes card → find class → Archive/Restore button  
**Taps:** 6  
**Severity:** Moderate — infrequent but important admin task  
**Proposed resolution:** Resolve with Annual Plan move

---

### CF-11: Reference Data management (Facilitator Types, Subject Areas, Training Stages)
**Path:** Nav → Account Management → scroll to Reference Data section  
**Taps:** 4 (Nav=1, Accounts=1, page loads=1, scroll to Reference Data=1)  
**Severity:** Moderate — done rarely but conceptually disconnected from accounts  
**Proposed resolution:** Move Reference Data to Unit Settings or a dedicated Admin page

---

### CF-12: Facilitator Schedule (PW only)
**Path:** Open Planning Workspace (1) → navigate to Facilitator Schedule in PW nav (1) → select zoom/filter (1)  
**Taps:** 3 from within PW; 4 from Main TMS (includes opening PW tab)  
**Severity:** Low — PW is an accepted tool switch; 4 taps once context is known

---

### CF-13: Cadet Risk Assessment
**Path:** Open Planning Workspace (1) → navigate to Cadets (1) → view risk panel (1)  
**Taps:** 3 within PW; 4 from Main TMS  
**Severity:** Low — specialist view; acceptable

---

## Section 4: Findability summary

| Severity | Count | Functions |
|---|---|---|
| ✓ ≤ 3 taps | 34 | Core nav, common actions, well-placed |
| ⚠ 4 taps | ~12 | Review — some justified (specialist tools), some need shortcuts |
| ✗ 5–7 taps | 10 | Critical / High — CF-01 to CF-11 |
| ✗ Unreachable | 1 | CF-08 (PW when not configured) |

### Functions that should be ≤ 2 taps but currently are not

| Function | Current taps | Target taps | Gap |
|---|---|---|---|
| Training Year setup | 5 | 2 | -3 |
| Training Classes | 6 | 2 | -4 |
| Generate Parade Dates | 6 | 2 | -4 |
| Mission Backlog | 7 | 2 | -5 |
| Getting Help | 4 | 1 | -3 |
| Planning Workspace discovery | ∞ | 1 | -∞ |
| Class Planning Forecasts | 6 | 2 | -4 |

---

## Section 5: Cognitive load at each tap

Findability is not only about tap count. Some single taps require high cognitive load.

| Decision point | Cognitive demand | Rating |
|---|---|---|
| "Where do I set up the Training Year?" (no nav item) | Scanning all nav items for one that might contain year setup | HIGH |
| "Is the Mission Backlog on this page?" (in Activities) | Scrolling a long page looking for something that is not named in the section heading | HIGH |
| "What does Activities contain?" (ambiguous label) | Resolving semantic mismatch between label and contents | HIGH |
| "Where is Getting Help?" (inside Activities) | Counter-intuitive location; must explore | HIGH |
| "How do I open the Planning Workspace?" (external link, conditional) | Not obvious that a second application exists | VERY HIGH |
| "Is this the right page?" (Locations vs Resources) | Nav label doesn't match page title | MODERATE |
| "Where are timing templates?" (buried in Settings) | Long Settings page, templates below fold | MODERATE |
| "What is the Mission Backlog?" (terminology) | AAFC-specific term may need explanation | LOW-MODERATE |
| "How do I record outcomes?" (multi-step, no shortcut) | Correct path is Parade Nights but the entry from Dashboard is indirect | MODERATE |

---

## Section 6: Findings for Resolution Planning

The following critical-path items must be resolved before the product can be used confidently by the target user persona (80-year-old Training Officer, Year 10 English):

1. **CF-01, CF-02, CF-03** — Year setup functions need a dedicated first-class nav item. A new officer setting up the year for the first time would not find these without assistance.

2. **CF-05** — Mission Backlog needs to be surfaced to Dashboard or given a nav item. "What training is still outstanding?" is a daily question that currently requires 7 taps.

3. **CF-06** — Help must be accessible in 1 tap. It does not belong inside Activities.

4. **CF-08** — Planning Workspace must be discoverable from relevant pages in Main TMS regardless of nav configuration.

