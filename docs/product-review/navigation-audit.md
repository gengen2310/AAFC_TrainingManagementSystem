# AAFC TMS — Navigation Audit

**Review:** Post-Gap Human Workflow, Architecture and Design Review — Stage 1  
**Date:** 2026-08-16  
**Method:** For every navigation item: record what the user's mental model would expect to find, what they actually find, and whether there is a mismatch.  
**Target user:** Squadron Training Officer (sqn_admin), Year 10 English, no technology background

---

## How to read this document

- **Expected contents (user's mental model):** What an 80-year-old Training Officer who has never seen the application would assume this nav item contains, based on the label alone.
- **Actual contents:** What is actually in the page.
- **Mismatch severity:** None | Minor | Moderate | High | Critical

---

## Part 1: Main TMS Navigation (Squadron scope, sqn_admin)

Nav items appear in this order for squadron scope.

---

### Getting Started

| | |
|---|---|
| **User expects** | A guide explaining what to do when first starting out |
| **Actually contains** | A step-by-step setup checklist that changes as items are completed |
| **Mismatch** | None |
| **Assessment** | Correctly named. However, the checklist links to pages without walking the user through the task on that page. "Getting Started" describes entry-level onboarding but does not provide guided forms. A Training Officer who completes step 3 (Add parade dates) is sent to Activities → Planning Year — which has its own discovery problem. |

---

### Dashboard

| | |
|---|---|
| **User expects** | A summary overview of what is happening |
| **Actually contains** | A 4-section analytics and readiness page: Tonight & This Week, Session Delivery analytics, Curriculum Progress charts, Staffing Resilience |
| **Mismatch** | Minor |
| **Assessment** | "Dashboard" is a standard label and is largely correct. Section A (Tonight & This Week) matches expectations. Section B (delivery analytics) and Section C (curriculum charts) are a layer deeper than "what is happening" — they answer "how did we go?" not "what is happening now." Section D (staffing resilience, deferred behind a button) is clearly managerial and may not be expected by a Training Officer. The page does a lot and the Training Officer must learn that the Dashboard is also the analytics view. |

---

### Training Calendar

| | |
|---|---|
| **User expects** | A calendar showing the squadron's training events |
| **Actually contains** | A monthly calendar grid showing parade nights, activities, and holidays |
| **Mismatch** | None |
| **Assessment** | Correctly named. The label "Training Calendar" precisely describes the contents. The year selector is hardcoded to 2025/2026/2027 — this will break post-2027 and should be dynamic. |

---

### Parade Nights

| | |
|---|---|
| **User expects** | The list of nights the squadron parades |
| **Actually contains** | A list of all parade nights with sessions, readiness scores, and management actions |
| **Mismatch** | None |
| **Assessment** | Correctly named and scoped. The list provides the primary session management workflow. Parade Nights is also where outcome recording happens — which may not be expected by a user who thinks "Parade Nights" means the schedule, not the record-keeping tool. |

---

### Weekly Program

| | |
|---|---|
| **User expects** | The printable program for this week's training |
| **Actually contains** | A printable view of sessions for a selected parade night |
| **Mismatch** | Minor |
| **Assessment** | The label says "Weekly" but the content is per-parade-night. For most squadrons a parade night = one night per week so this is functionally correct. If a squadron parades twice a week (less common) the label becomes misleading. Low severity but the label could be more precise: "Parade Night Program" or "Training Program." |

---

### Curriculum

| | |
|---|---|
| **User expects** | The list of things the cadets need to learn |
| **Actually contains** | A full curriculum library with delivery tracking, progress filters, matrix view, and Learning Hub links |
| **Mismatch** | None |
| **Assessment** | Correctly named. The curriculum view is appropriately comprehensive. The matrix view (class × curriculum item) is inside a tab — discoverable but not prominently signposted. |

---

### Activities

| | |
|---|---|
| **User expects** | A list of events the unit is attending or running (camps, competitions, ceremonies) |
| **Actually contains** | 1. AAFC events (matches expectation) PLUS 2. Getting Help text PLUS 3. Planning Year selector PLUS 4. Parade Dates management PLUS 5. Holiday & Stand-down Periods PLUS 6. Training Classes PLUS 7. Mission Backlog PLUS 8. Class Planning Forecasts |
| **Mismatch** | **CRITICAL** |
| **Assessment** | The word "Activities" has a specific meaning in the AAFC context: organised squadron/wing/national activities (camps, competitions, cadet training events, excursions). A Training Officer using this navigation item expects to see a table of events. Instead they find year setup, training class management, parade date generation, holiday administration, and the mission backlog — none of which has any semantic relationship to "Activities." This is the most severe navigation problem in the application. A Training Officer looking to set up the Training Year would not click "Activities." A Training Officer looking for the Mission Backlog would not click "Activities." A Training Officer looking for help would not click "Activities." |

---

### Facilitators

| | |
|---|---|
| **User expects** | The people who deliver training |
| **Actually contains** | Facilitator table, analytics charts (workload, coverage, gaps, type), add/edit/archive actions |
| **Mismatch** | None |
| **Assessment** | "Facilitators" is clear. The analytics charts at the top are a bonus — they add value but a Training Officer may not expect to see workload charts when they click "Facilitators." Consider whether charts belong on the Dashboard or on this page. Both locations are defensible. |

---

### Locations and Resources

| | |
|---|---|
| **User expects** | Places and things available for training |
| **Actually contains** | Two tables: (1) Rooms / Training Areas (2) Equipment |
| **Mismatch** | Minor — **naming inconsistency** |
| **Assessment** | "Locations and Resources" describes the contents correctly. However: the page heading says "Resources & Training Areas" — the nav and page title disagree. This inconsistency erodes trust (did I click the right thing?). Standard: align both to one label. Recommended: "Rooms and Equipment" (concrete, specific) or "Training Areas and Equipment" (AAFC terminology). The current nav label "Locations and Resources" is the weakest version — "locations" is vague and "resources" is vague. |

---

### Needs Attention

| | |
|---|---|
| **User expects** | A list of things that need to be done |
| **Actually contains** | Action items (P0 command decision, P1 automation alerts, P2 outcomes not recorded, P3 missing reasons, P4 no curriculum, P5 unscheduled curriculum) PLUS "What Changed?" activity feed |
| **Mismatch** | Minor |
| **Assessment** | "Needs Attention" is correct for the primary use case (things that need action). The P5 items (all unscheduled curriculum) can generate hundreds of rows — a Training Officer who opens Needs Attention expecting a short list of critical items may be overwhelmed by planning backlog. The "What Changed?" feed is a good addition but may not be expected under "Needs Attention" — it is informational, not action-required. |

---

### Settings (Unit Settings)

| | |
|---|---|
| **User expects** | Controls for the squadron's configuration |
| **Actually contains** | Squadron details, parade day/time, session structure, display size, timing templates, access code change, user directory |
| **Mismatch** | Minor |
| **Assessment** | "Settings" is correct. However, Display Size is present here but is also relevant to sqn_general users who cannot access this page — they would need to find it elsewhere (or they cannot change it). "Access Code" is in Settings as "Change my access code" but is also in a separate section in some views — minor duplication. Timing Templates are buried in Unit Settings below the fold; many users may never discover them. |

---

### Account Management

| | |
|---|---|
| **User expects** | A place to manage who has access |
| **Actually contains** | User accounts table, Wings table (national admin), Squadrons table (wing/national), Flights (local groupings), Reference Data (training stages, facilitator types, subject areas) |
| **Mismatch** | Moderate (Reference Data) |
| **Assessment** | "Account Management" correctly describes the accounts table. However, "Reference Data" (Training Stages, Facilitator Types, Subject Areas) is hidden inside Account Management with no logical connection — a Training Officer wanting to add a new Facilitator Type would not look under "Account Management." This is a secondary discovery problem. The Flights section is logically in the right place (flights are a unit organisational grouping linked to accounts/users) but a Training Officer expecting "Account Management" to mean "user logins" may be confused by Flights appearing here. |

---

## Part 2: Navigation Structure Findings

### Items a Training Officer might expect but cannot find

| Expected nav item | Where it actually is | Gap severity |
|---|---|---|
| "Training Year Setup" or "Annual Plan" | Inside Activities page, not in nav | **Critical** |
| "Training Classes" | Inside Activities → Planning Year | **Critical** |
| "Mission Backlog" | Inside Activities → Planning Year | **Critical** |
| "Help" or "Support" | Inside Activities page (Getting Help text block) | **High** |
| "Planning Calendar" or "Parade Dates" | Inside Activities → Planning Year | **High** |
| "Holiday Periods" | Inside Activities → Planning Year (and Activities header) | **High** |
| "Planning Workspace" | External link in nav (often invisible if not configured) | **High** |
| "Class Progress" | Dashboard → Curriculum Progress section (conditional display) | **Moderate** |
| "Timing Templates" | Unit Settings → scroll down | **Moderate** |

---

### Items in nav that contain unexpected content

| Nav item | Unexpected content | Severity |
|---|---|---|
| Activities | Planning Year, Training Classes, Parade Dates, Holidays, Mission Backlog, Getting Help | **Critical** |
| Needs Attention | Hundreds of P5 backlog items that swamp operational items | **Moderate** |
| Account Management | Reference Data (Facilitator Types, Subject Areas, Training Stages) | **Moderate** |
| Settings | Display size (relevant to all users, but page is sqn_admin only) | **Minor** |

---

### Navigation label vs page title mismatches

| Nav label | Page title | Match? |
|---|---|---|
| Getting Started | Getting Started | ✓ |
| Dashboard | Training Dashboard | ✓ (acceptable) |
| Training Calendar | Training Calendar | ✓ |
| Parade Nights | Parade Nights | ✓ |
| Weekly Program | Weekly Program | ✓ |
| Curriculum | Curriculum | ✓ |
| Activities | Activities | ✓ (but contents mismatch nav concept) |
| Facilitators | Facilitators | ✓ |
| Locations and Resources | Resources & Training Areas | ✗ |
| Needs Attention | Needs Attention | ✓ |
| Settings (nav) | Unit Settings (page) | ✗ (minor) |
| Account Management | Account Management | ✓ |

---

## Part 3: Planning Workspace Navigation (when running in full-app mode)

The PW runs in module mode in the current pilot deployment — the user opens a new tab. If it ran in full-app mode, its nav would expose the following. These findings apply to the full-app architecture.

| Nav group | Nav item | Mismatch level | Finding |
|---|---|---|---|
| Operations | Planning Workspace | None | Correctly labelled |
| Operations | Dashboard | None | Correct |
| Operations | Calendar | None | Correct |
| Operations | Parade Nights | None | Correct |
| Operations | Weekly Program | None | Correct |
| Operations | Curriculum | None | Correct |
| Capability | Facilitators | None | Correct |
| Capability | Facilitator Schedule | None | Correct (adds leave management vs Main TMS) |
| Capability | Resources | None | Correct |
| Capability | Cadets | Minor | A Training Officer expects "Cadets" to contain cadet names and records — it does, but also cadet risk flags and class assignments. The risk flags may be unexpected under a nav item called simply "Cadets." |
| Assurance | Reports | Minor | "Reports" is a broad label — there are 17 report types; a Training Officer may not know which report to expect |
| Assurance | Report Catalogue | None | Correct — explicitly labelled |
| Assurance | Needs Attention | None | Correct |
| Assurance | Imports | Moderate | "Imports" placed in Assurance group but it is an admin utility function; "Assurance" implies oversight, not data import |
| Assurance | Audit | None | Correct |
| Admin | Account Management | None | Correct |
| Admin | Unit Settings | None | Correct |
| Account | Access Codes | Minor | "Access Codes" (change your code) is in an "Account" group but it is also present in Unit Settings → Settings → Change my access code — two entry points for the same function |
| Account | ← Main TMS | None | The back-link is clear and helpful |

---

## Summary of Navigation Findings

### Critical

1. **Activities page identity crisis** — The Activities nav item contains 8 distinct functions only one of which is conceptually "activities." Move non-activities content to a dedicated Annual Plan section.

2. **Planning Year setup has no nav item** — There is no top-level nav item for "set up the training year." This is the most common annual task.

### High

3. **Mission Backlog has no nav item** — One of the most important daily-use functions is buried 3 clicks inside Activities.

4. **Getting Help has no nav item** — Help content is inside Activities.

5. **Planning Workspace is a conditional external link** — Users cannot discover PW exists from the navigation in all configurations.

### Moderate

6. **"Locations and Resources" ≠ "Resources & Training Areas"** — Nav label and page title disagree.

7. **Reference Data hidden in Account Management** — Training Stages, Facilitator Types, Subject Areas have no relationship to accounts.

8. **P5 items swamp Needs Attention** — Operational items (P0-P4) are buried under hundreds of planning backlog items.

### Minor

9. **"Weekly Program" is per-night, not per-week** — Minor label imprecision.

10. **"Settings" vs "Unit Settings"** — Inconsistent label between nav and page.

11. **Display Size accessible only to sqn_admin** — A user preference relevant to all roles is in a page restricted to admins.

