# AAFC TMS — Function-Purpose Register

**Review:** Post-Gap Human Workflow, Architecture and Design Review — Stage 1  
**Date:** 2026-08-16  
**Covers:** Main TMS (connected-frontend) and Planning Workspace (frontend/), squadron scope unless noted  
**Target user:** Squadron Training Officer (sqn_admin)

For every user-visible function, this register records the human need it serves, the question it answers, the decision it supports, and whether its current location makes sense.

Column definitions:
- **Recommendation:** K = Keep | M = Move | MG = Merge | S = Simplify | R = Retire (if proven genuinely unused)
- **Classification:** A = Primary home | B = Contextual shortcut to same action | C = Genuine duplicate | D = Legacy/obsolete | E = Different function that looks similar

---

## 1. Navigation and Landing

| Function | User | Human need | Question answered | Decision supported | Primary home (current) | Recommendation | Classification | Evidence |
|---|---|---|---|---|---|---|---|---|
| Navigation sidebar — squadron scope | sqn_admin | Find the right part of the system | Where do I go? | Which area to open | Main TMS sidebar | K | A | Core orientation; role-scoped correctly |
| Getting Started page | sqn_admin (new) | Know what to do first | What needs to be set up? | What to prioritise | Getting Started nav item | S | A | Checklist exists but is not a guided wizard; see IA-08 |
| Login page | all | Authenticate | Can I get in? | Whether to proceed | Login page | K | A | Standard auth |
| Session cookie / sessionStorage auth | all | Stay authenticated across pages | Am I still logged in? | None | Handled automatically | K | A | Architecture decision, correct |

---

## 2. Dashboard (Main TMS, Squadron scope)

| Function | User | Human need | Question answered | Decision | Current location | Recommendation | Classification | Evidence |
|---|---|---|---|---|---|---|---|---|
| Section A — Tonight & This Week | sqn_admin | Know what is happening at next parade night | Is the night ready? Who is training? | Whether to take action before the night | Dashboard Section A | K | A | Correctly placed as first section |
| Upcoming readiness cards | sqn_admin | See the next several parade nights at a glance | Are any upcoming nights at risk? | Which nights need preparation | Dashboard Section A | K | A | Supports weekly planning cycle |
| Section B — Session delivery analytics | sqn_admin | Track training delivery trends | How well are we delivering training? | Whether to change delivery approach | Dashboard Section B | K | A | Useful mid-page; should not be before Section A |
| Section C — Curriculum progress charts | sqn_admin | Understand what phases are complete | Where are we in the curriculum? | What training to prioritise | Dashboard Section C | K | A | Progress by phase, element, class — correctly placed |
| Section D — Strategic / staffing resilience | sqn_admin | Identify long-term capability risks | Which facilitators are overloaded? | Resource planning decisions | Dashboard Section D | K | A | Appropriate for wing_admin/national review; may need role gate |
| Period selector (This Term / Week / Year) | sqn_admin | Filter analytics to a time window | What does the data look like for this period? | None — filter | Dashboard header | K | A | Controls all chart sections |
| Refresh button | sqn_admin | Get fresh data | Is this information current? | None | Dashboard header | K | A | Needed due to cached data |
| Data freshness bar | sqn_admin | Know when data was last updated | How old is this data? | Whether to trust displayed numbers | Dashboard top (conditional) | K | A | Good transparency feature |
| Drill-down panel | sqn_admin | See the sessions behind a chart bar | What specific sessions contributed to this? | Which sessions need attention | Dashboard (hidden until clicked) | K | A | Click-to-drill is standard pattern |
| Class curriculum progress chart | sqn_admin | Track per-class training progress | Is Senior 2 ahead or behind? | Which class to prioritise | Dashboard Section C (conditional) | K | A | Only visible when classes exist — correct |
| Class enrollment chart | sqn_admin | Check class sizes | Are my classes balanced? | Whether to rebalance classes | Dashboard Section C (conditional) | K | A | Conditional display correct |

---

## 3. Training Calendar

| Function | User | Human need | Question answered | Decision | Current location | Recommendation | Classification | Evidence |
|---|---|---|---|---|---|---|---|---|
| Monthly calendar grid | sqn_admin | See the shape of the training year month by month | When are parade nights, activities, and holidays? | Planning decisions | Training Calendar (Main TMS) | K | A | Monthly overview; complements PW's year view |
| Month navigation | sqn_admin | Browse through months | What is coming up in [month]? | None — navigation | Training Calendar | K | A | Standard |
| Year selector | sqn_admin | See a different calendar year | What does next year look like? | None — navigation | Training Calendar | S | A | Hardcoded 2025/2026/2027 — will break post-2027; should be dynamic |
| Legend (parade, activity, holiday, delivered) | sqn_admin | Understand what the dots mean | What does each colour indicate? | None — reference | Training Calendar bottom | K | A | Required; verify colour-only meaning (accessibility) |

---

## 4. Activities Page (Main TMS) — Critical finding: identity crisis

**This page contains 7 distinct conceptual areas under one nav label.**

### 4a. AAFC Activities list

| Function | User | Human need | Question answered | Decision | Current location | Recommendation | Classification | Evidence |
|---|---|---|---|---|---|---|---|---|
| Activities table (Must Attend, Key Event, Optional) | sqn_admin | Know what AAFC events are coming | What activities does the unit need to attend? | Which activities to accommodate in the training plan | Activities page (top) | M | A | This is correctly named "Activities" — the primary home for AAFC events. The problem is everything else on this page. |
| Add Activity button | sqn_admin (admin) | Create a local squadron activity | What should I create? | What type and importance | Activities page header | K | A | Correctly placed for the Activities concept |
| Generate Activities button | sqn_admin | Copy/seed standard activities for the year | Which activities should we include? | Whether to use defaults | Activities page header | K | A | Contextually appropriate |
| Inherited wing/national activities section | sqn_admin | See what Wing/National has scheduled | What external activities affect us? | Whether to plan around them | Activities page (auto-rendered section) | K | B | Contextual supplement to squadron activities — correct |
| Filter by type | sqn_admin | Narrow the activities list | Show me only camps | Which type to look at | Activities page filter bar | K | A | Standard filter |

### 4b. Getting Help section — MISPLACED

| Function | User | Human need | Question answered | Decision | Current location | Recommendation | Classification | Evidence |
|---|---|---|---|---|---|---|---|---|
| Getting Help card (admin text, contact info) | sqn_admin | Find help or support contact | Who do I call if something breaks? | Who to contact | **Activities page — after Activities table** | **M** | D | Help information has no relationship to Activities. User looking for help would never click "Activities". Move to a dedicated Help section or a persistent help icon. |

### 4c. Planning Year section — MISPLACED

| Function | User | Human need | Question answered | Decision | Current location | Recommendation | Classification | Evidence |
|---|---|---|---|---|---|---|---|---|
| Planning Year selector | sqn_admin | Select the training year to view | Which year am I looking at? | Which year to manage | **Activities page — after Getting Help card** | **M** | D | The planning year selector is the gateway to Training Classes, Parade Dates, Holidays, and Mission Backlog. It does not belong inside "Activities". Move to a dedicated "Annual Plan" or "Training Year" area. |
| + New Year button | sqn_admin | Create the year's training plan | When does this year start? | Whether to create or select existing | Activities page | M | D | Same as above |
| Annual overview map | sqn_admin | See the full year's parade schedule summary | How many parade nights per term? | Term capacity | Activities page (after year select) | M | D | Annual overview is a planning function, not an activities function |

### 4d. Parade Dates card — MISPLACED

| Function | User | Human need | Question answered | Decision | Current location | Recommendation | Classification | Evidence |
|---|---|---|---|---|---|---|---|---|
| Parade Dates card | sqn_admin | See and manage the schedule of parade nights for the year | When do we parade? | Whether to add or adjust dates | **Activities page → Planning Year selected** | **M** | D | A Training Officer looking to "set up our parade schedule for the year" would not look in Activities. Move with Planning Year to Annual Plan section. |
| Generate dates button | sqn_admin | Create all parade nights for the year | When does the system need to know? | Generate vs manual entry | Activities page | M | D | Same move needed |
| Add Date button | sqn_admin | Add a single extra parade date | What night to add? | Whether to add manually | Activities page | M | D | Same |

### 4e. Holiday & Stand-Down Periods card — MISPLACED

| Function | User | Human need | Question answered | Decision | Current location | Recommendation | Classification | Evidence |
|---|---|---|---|---|---|---|---|---|
| Holidays card (view) | sqn_admin | Know what periods to exclude from training | When are the school holidays? | Whether to adjust parade dates | **Activities page → Planning Year selected** | M | D | Move to Annual Plan section. Holiday information has some relationship to Activities (activities don't run during holidays) but the primary management need is in planning context. |
| + Add Holiday button (in Holidays card) | sqn_admin | Record a school holiday or stand-down | When is the next break? | Whether to record it | Activities page → Holidays card | M | B | This is a contextual shortcut to the same modal as the header button. Both call openAddHolidayModal(). After Annual Plan move, the card button remains correct. |
| + Add Holiday button (in Activities page header) | sqn_admin | Record a holiday from the Activities page | Same | Same | **Activities page header** | M | B | Contextual shortcut — after moving the main home, this becomes a less necessary entry point |

### 4f. Training Classes card — MISPLACED

| Function | User | Human need | Question answered | Decision | Current location | Recommendation | Classification | Evidence |
|---|---|---|---|---|---|---|---|---|
| Training Classes card | sqn_admin | Define the learning groups within the squadron | Who is studying what? | Which classes to create and name | **Activities page → Planning Year selected** | **M** | D | A Training Officer thinks "I need to set up my Training Classes" — they would not look in Activities. This is a year-setup function. Move to Annual Plan section. |
| + Add Training Class button | sqn_admin | Create a new training group | What stage are they at? | Whether to create parallel classes | Activities page | M | D | Same |
| Archive/restore class | sqn_admin (admin) | Remove a class no longer active | Is this class still running? | Whether to archive | Activities page | M | D | Same |

### 4g. Mission Backlog card — MISPLACED

| Function | User | Human need | Question answered | Decision | Current location | Recommendation | Classification | Evidence |
|---|---|---|---|---|---|---|---|---|
| Mission Backlog (table) | sqn_admin | See what curriculum is still unscheduled | What training still needs to be planned? | What to schedule next | **Activities page → Planning Year selected → scroll** | **M** | D | This is the single most important planning tool and it is the hardest to find. A Training Officer asking "what does Senior 2 still need?" would not look in Activities. Move to Annual Plan section OR add as a Dashboard card. |
| Filter: Training Class | sqn_admin | Filter backlog by class | What does Senior 1 still need? | Which class to focus on | Activities page Mission Backlog | K after move | A | Correct filter type |
| Filter: Training Stage | sqn_admin | Filter by stage | What Senior training is outstanding? | Which stage to focus on | Activities page Mission Backlog | K after move | A | Correct |
| Export per-class CSV | sqn_admin | Export class delivery data | Exportable data | None | Activities page Mission Backlog | K after move | A | Keep after move |

### 4h. Class Planning Forecasts card

| Function | User | Human need | Question answered | Decision | Current location | Recommendation | Classification | Evidence |
|---|---|---|---|---|---|---|---|---|
| Forecast cards (unplanned items, parade capacity) | sqn_admin | Know if there is enough time left | Will we finish the curriculum? | Whether to accelerate | **Activities page → Planning Year selected → scroll** | M | D | Move with Mission Backlog to Annual Plan section |

---

## 5. Parade Nights Page

| Function | User | Human need | Question answered | Decision | Current location | Recommendation | Classification | Evidence |
|---|---|---|---|---|---|---|---|---|
| Parade nights list | sqn_admin | See all parade nights and their status | What happened at each night? What is coming up? | Which night to open | Parade Nights page (correct) | K | A | Primary home for parade nights |
| Filter by term | sqn_admin | Narrow to one term | What happened in Term 2? | None — filter | Parade Nights filter bar | K | A | Standard filter |
| Filter by status | sqn_admin | See only planned/delivered nights | What is still outstanding? | Which to action | Parade Nights filter bar | K | A | Standard filter |
| Search sessions | sqn_admin | Find a specific session | Where is the drill session? | Which night to open | Parade Nights filter bar | K | A | Useful text search |
| Bulk selection toolbar | sqn_admin | Set term or archive multiple nights | Apply Term 2 to these nights | Bulk update | Parade Nights (conditional) | K | A | Useful bulk operation |
| + Add Parade Night | sqn_admin (admin) | Create a single new parade night | When is the extra parade? | Whether to add manually | Parade Nights header | K | A | Correctly placed |
| Generate Parade Nights button | sqn_admin | Create all parade nights for the year automatically | How many nights per term? | Whether to generate vs add manually | Parade Nights header | B | B | Also accessible via Activities → Planning Year. This is the better location — more discoverable. Both entry points call the same function (openGenerateDatesModal). Type B — contextual shortcut. **Consider making Parade Nights the primary home for generation.** |
| Calendar button (links to Training Calendar) | sqn_admin | Switch to calendar view | What does this look like on a calendar? | View preference | Parade Nights header | K | B | Contextual shortcut — helps transition between views |
| Weekly Program button (links to Weekly Program) | sqn_admin | Print the program for tonight | Get the printable program | Whether to print | Parade Nights header | K | B | Correct contextual shortcut |
| Parade Night detail card (click to expand) | sqn_admin | See what is happening at a specific night | What is planned? Who is delivering? | Whether to add/change sessions |  Parade Nights list → expand | K | A | Core workflow |
| Session row in detail | sqn_admin | See session details for one period | What is happening in Period 1? | Whether to edit | Parade Night detail → session row | K | A | Correct |
| Quick Edit session (pencil) | sqn_admin | Edit a session's plan or outcome | Who is delivering this? What was the outcome? | Whether to save changes | Parade Night detail → Quick Edit modal | K | A | Primary session edit flow |
| Guided session wizard | sqn_admin | Create a new session with step-by-step help | Walk me through adding a session | What to schedule | Parade Night detail → Add Session bar → Guided mode | K | A | Good addition — reduce to preferred entry for new users |
| Quick-entry form | sqn_admin (experienced) | Add a session fast | Just add it quickly | Speed vs thoroughness | Parade Night detail → Add Session bar → Quick entry | K | A | Expert shortcut |
| Facilitator suggestions panel | sqn_admin | See who is available and suitable | Who should I ask to deliver this? | Facilitator selection | Session Quick Edit modal | K | A | Correctly embedded in session edit |
| Bulk cancel remaining sessions | sqn_admin | Cancel all remaining sessions in one action | Cancel everything for tonight | Emergency action | Parade Night detail header | K | A | Edge-case use case |
| Training Class assignment per session | sqn_admin | Link a session to a Training Class | Who is this session for? | Class association | Session Quick Edit modal | K | A | Required for class-level tracking |
| Publish parade night | sqn_admin (admin) | Mark the night as officially published | Is this ready to go? | Go/no-go decision | Parade Night detail | K | A | Operational workflow |
| Close parade night | sqn_admin (admin) | Lock the night after it is complete | Are we done? | Finalisation decision | Parade Night detail | K | A | Operational workflow |

---

## 6. Weekly Program

| Function | User | Human need | Question answered | Decision | Current location | Recommendation | Classification | Evidence |
|---|---|---|---|---|---|---|---|---|
| Parade Night selector | sqn_admin | Choose which night to print | Which night's program? | Which night | Weekly Program page | K | A | Primary home for print view |
| Search/filter overlay | sqn_admin | Find specific sessions in the printed view | Where is the drill session? | None | Weekly Program filter bar | K | A | Useful |
| Print program (browser print) | sqn_admin | Get the physical printout | What gets printed? | Print | Weekly Program | K | A | Core use case |
| Print Program toolbar button | sqn_admin | Quick print without navigating | Get the printout | Print | Main TMS toolbar (top right) | K | B | Type B shortcut — correct |

---

## 7. Curriculum

| Function | User | Human need | Question answered | Decision | Current location | Recommendation | Classification | Evidence |
|---|---|---|---|---|---|---|---|---|
| Curriculum items list | sqn_admin | Browse the full curriculum | What topics are in the curriculum? | What to teach | Curriculum page | K | A | Primary home for curriculum reference |
| Phase tabs (Orientation / Initial / Junior etc.) | sqn_admin | Filter by training stage | What Junior curriculum do we have? | Stage selection | Curriculum page tab bar | K | A | Stage tabs match AAFC stages |
| Filter by element (Drill, Air & Space, etc.) | sqn_admin | Narrow to a subject area | What Drill items do we have? | Element focus | Curriculum filter bar | K | A | Standard filter |
| Filter by progress status | sqn_admin | See what has or hasn't been delivered | What is still unscheduled? | Planning | Curriculum filter bar | K | A | Useful — complements Mission Backlog |
| Search | sqn_admin | Find a specific item | Where is the navigation lesson? | None — search | Curriculum filter bar | K | A | Standard |
| Missing Learning Hub link filter | sqn_admin (admin) | Find items that need LH URLs | What items need links? | Data quality | Curriculum filter bar | K | A | Admin function correctly nested |
| Matrix view | sqn_admin | See all curriculum in a class-vs-item grid | Which classes have covered which items? | Planning | Curriculum → Matrix tab | K | A | Powerful planning tool — good addition |
| Learning Hub link | sqn_admin | Open the online resource | What does this lesson look like? | Whether to use the resource | Curriculum item row | K | A | Direct link to external content |
| Export XLSX / Export CSV | sqn_admin | Get curriculum data in a spreadsheet | Formatted export | What to export | Curriculum header | K | A | Standard export |
| Drill-down panel (sessions for a curriculum item) | sqn_admin | See when a specific item was taught | When did we do ORI-M01-01? | Historical review | Curriculum page | K | A | Correct contextual detail |
| Add/archive curriculum (admin) | sqn_admin (admin) | Manage the curriculum library | What to add or remove | Curation decision | Curriculum header | K | A | Admin function |
| Import CSV | national_admin | Bulk-add curriculum from a spreadsheet | Bulk import | Import | Curriculum header | K | A | Admin function |

---

## 8. Facilitators

| Function | User | Human need | Question answered | Decision | Current location | Recommendation | Classification | Evidence |
|---|---|---|---|---|---|---|---|---|
| Facilitator table | sqn_admin | Know who can teach | Who is available to deliver training? | Who to assign | Facilitators page | K | A | Primary home |
| Facilitator status chart | sqn_admin | At-a-glance staffing health | Are we well-staffed? | Whether to recruit | Facilitators page (header charts) | K | A | Useful summary |
| Workload distribution chart | sqn_admin | See overload risk | Is anyone doing too much? | Whether to redistribute | Facilitators page (header charts) | K | A | Important equity/sustainability check |
| Subject area coverage chart | sqn_admin | See single-point-of-failure risk | What if [person] leaves? | Succession planning | Facilitators page (header charts) | K | A | High-value strategic view |
| Repeated gaps chart | sqn_admin | Identify chronic staffing shortfalls | What areas are always unfilled? | Recruitment priority | Facilitators page (header charts) | K | A | Useful pattern-detection |
| Facilitators by type chart | sqn_admin | Understand staffing composition | How many Officers vs staff cadets vs civilians? | Workforce planning | Facilitators page (header charts) | K | A | Reference chart |
| Add Facilitator | sqn_admin (admin) | Register a new person | What details do I need? | Whether to create | Facilitators page header | K | A | Correct location |
| Edit Facilitator | sqn_admin (admin) | Update a person's details | What changed? | Whether to save | Facilitators row → edit | K | A | Correct inline edit |
| Archive Facilitator | sqn_admin (admin) | Remove someone who has left | Is this person still active? | Whether to archive | Facilitators row → archive | K | A | Correct |
| Facilitator profile (click name) | sqn_admin | See one person's full record | What subjects can they teach? | Assignment decision | Facilitators row → click | K | A | Correct detail view |
| Subject area filter | sqn_admin | Find facilitators for a specific area | Who can teach Drill? | Assignment | Facilitators filter | K | A | Useful |
| Search (name/rank) | sqn_admin | Find a specific person | Where is the record for [name]? | None | Facilitators search | K | A | Standard |
| Facilitator suggestions (in session edit) | sqn_admin | Get recommendations for who to assign | Who should deliver this session? | Facilitator selection | Session Quick Edit modal → suggestions | K | B | Type B — contextual shortcut backed by scoring algorithm. Correctly placed adjacent to the assignment action. |
| Facilitator leave management (PW only) | sqn_admin | Record when someone is unavailable | Is [person] available on this date? | Planning decisions | PW → Bottom drawer → Facilitators tab | K | A | PW is the correct home — used in planning context |
| Facilitator schedule timeline (PW) | sqn_admin | See one person's session load across dates | How busy is [person] this term? | Assignment decisions | PW → Bottom drawer → Schedule tab | K | A | PW context correct |

---

## 9. Locations and Resources

| Function | User | Human need | Question answered | Decision | Current location | Recommendation | Classification | Evidence |
|---|---|---|---|---|---|---|---|---|
| Rooms list | sqn_admin | Know what training areas are available | Which rooms can we use? | Room assignment | Resources & Training Areas page | K | A | Primary home — but page and nav title inconsistent |
| Add/edit/archive room | sqn_admin (admin) | Manage the room inventory | What rooms do we have? | Whether to add | Resources page | K | A | Correct |
| Equipment list | sqn_admin | Know what equipment is available | What can we use? | Equipment assignment | Resources page | K | A | Correct |
| Add/edit/archive equipment | sqn_admin (admin) | Manage equipment inventory | What do we have? | Whether to add | Resources page | K | A | Correct |
| Rooms tab in PW | sqn_admin | Manage rooms in planning context | Add a room while planning | Room planning | PW → Bottom drawer → Rooms | K | B | Type B — same data, contextual access during planning |
| Equipment tab in PW | sqn_admin | Manage equipment in planning context | Add equipment while planning | Equipment planning | PW → Bottom drawer → Equipment | K | B | Type B — same data, contextual access during planning |

**Note:** Nav label "Locations and Resources" ≠ page title "Resources & Training Areas". These should match.

---

## 10. Needs Attention

| Function | User | Human need | Question answered | Decision | Current location | Recommendation | Classification | Evidence |
|---|---|---|---|---|---|---|---|---|
| Action items table (P0-P4) | sqn_admin | Know what needs to be done today | What requires my attention right now? | Which actions to take | Needs Attention page (top) | K | A | Correct primary home for operational attention items |
| P0: Command decision required | sqn_admin | See decisions pending from command | Is there a pending decision? | Whether to escalate | Needs Attention (priority sort) | K | A | High priority correctly surfaced |
| P1: Automation alerts | sqn_admin | See system-detected issues | What has the system flagged? | Whether to act | Needs Attention | K | A | Correct |
| P2: Outcomes not recorded | sqn_admin | Record what happened last parade night | Which sessions still need an outcome? | Whether to record | Needs Attention | K | A | Correctly surfaced — but workflow to record is still multi-step |
| P3: Missing reasons | sqn_admin | Add reasons for cancellations | Why was this cancelled? | Data quality | Needs Attention | K | A | Correct |
| P4: Sessions without curriculum | sqn_admin | Assign curriculum to empty sessions | What should this session teach? | Content planning | Needs Attention | K | A | Correct — though may be rare |
| P5: Curriculum not scheduled (backlog) | sqn_admin | Know what training is outstanding | What have we not planned yet? | Planning decisions | **Needs Attention — mixed with P0-P4** | S | D | This is the Mission Backlog. Including it in Needs Attention creates a list that can have hundreds of items and buries P0-P4 operational alerts. **Separate backlog from operational items.** |
| Run checks button | sqn_admin (admin) | Trigger automation alerts | Are there new issues? | Whether to proceed | Needs Attention header | K | A | Correct placement |
| What Changed? activity feed | sqn_admin | See recent changes | What happened since I last logged in? | Whether to investigate | Needs Attention page (bottom) | S | E | Correctly named and useful, but buried at the bottom of Needs Attention. Consider a persistent "Last activity" indicator in the toolbar or a dedicated Recent Changes card on Dashboard. |

---

## 11. Unit Settings

| Function | User | Human need | Question answered | Decision | Current location | Recommendation | Classification | Evidence |
|---|---|---|---|---|---|---|---|---|
| Squadron Details (name, address, unit type) | sqn_admin | Configure the unit's profile | What is our unit's basic information? | Settings | Unit Settings page | K | A | Correct |
| Parade Day and Time | sqn_admin | Set when the squadron parades | What day and time? | Configuration | Unit Settings page | K | A | Correct — with the important note that this only affects future date generation |
| Crest URL | sqn_admin | Set the squadron crest for print documents | Which crest image to use? | Appearance | Unit Settings | K | A | Correct |
| Session Structure (sessions per night) | sqn_admin | Set default session count | How many sessions per parade night? | Configuration | Unit Settings | K | A | Correct |
| Display Size (Comfortable / Compact) | sqn_admin | Adjust how much content fits on screen | Too cramped or too spacious? | Accessibility | Unit Settings | K | A | Correct; browser-session only |
| Timing Templates | sqn_admin (admin) | Define the block structure of parade nights | When is Period 1? When is the break? | Configuration | Unit Settings → scroll | K | A | Correct location — but hidden below fold; users may not know it exists |
| Template editor | sqn_admin (admin) | Edit a timing template | What time does each block start? | Block configuration | Unit Settings → Timing Template → edit | K | A | Correct |

---

## 12. Account Management

| Function | User | Human need | Question answered | Decision | Current location | Recommendation | Classification | Evidence |
|---|---|---|---|---|---|---|---|---|
| Account table | sqn_admin (admin) | See who has access to the system | Who can log in? | Security management | Account Management page | K | A | Correct |
| Create account | sqn_admin (admin) | Give someone access | Which role should they have? | Role assignment | Account Management | K | A | Correct |
| Disable / reactivate account | sqn_admin (admin) | Remove or restore access | Can this person still log in? | Security | Account Management | K | A | Correct |
| Access code reset | sqn_admin (admin) | Give someone a new one-time code | Someone forgot their code | Access recovery | Account Management → reset | K | A | Correct; one-time-display only |
| Create Flight | sqn_admin (admin) | Define internal cadet groupings | What flights/groups do we have? | Organisation | Account Management | M | E | Flight creation is an admin function but users may not understand its relationship to accounts. Consider moving to Unit Settings. |

---

## 13. Wing Overview (wing_admin only)

| Function | User | Human need | Question answered | Decision | Current location | Recommendation | Classification | Evidence |
|---|---|---|---|---|---|---|---|---|
| Wing overview dashboard | wing_admin | See all squadrons at once | How is each squadron performing? | Where to focus wing support | Wing Overview page | K | A | Correct scope |
| Command centre dashboard | wing_admin | Command-level analytics across wing | What is the wing's overall delivery rate? | Strategic decisions | Wing Overview page | K | A | Correct |

---

## 14. Planning Workspace (PW)

| Function | User | Human need | Question answered | Decision | Current location | Recommendation | Classification | Evidence |
|---|---|---|---|---|---|---|---|---|
| Year/Term/8-week/2-week view | sqn_admin | Plan across different time horizons | What does the term look like? | Planning decisions | PW canvas | K | A | Core PW function |
| Parade Night view | sqn_admin | Plan a specific night in detail | What sessions are on this night? | Session scheduling | PW canvas | K | A | Core PW function |
| List view | sqn_admin | See sessions in list format | What are all sessions in this period? | None — different format | PW canvas | K | A | Useful alternative |
| Left panel — filter layers | sqn_admin | Show/hide information overlays | Do I want to see national events? | View configuration | PW left panel | S | A | 9 checkbox filters with unclear Wing-specific labels (hardcoded "7WG HQ", "AOW") — should be dynamic |
| Left panel — Backlog summary | sqn_admin | See at-a-glance what is outstanding | How much is unplanned? | Whether to plan now | PW left panel | K | A | Correctly placed for quick reference |
| Session cell (click to edit) | sqn_admin | Edit or view session details | What is in this session? | Whether to edit | PW canvas cell | K | A | Core interaction |
| Right drawer — session edit | sqn_admin | Change session plan or details | Who is delivering? What curriculum? | Session planning | PW right drawer | K | A | Primary session edit in PW context |
| Right drawer — conflict display | sqn_admin | Understand a planning problem | Why is there a warning? | Whether to override | PW right drawer | K | A | In-context conflict explanation is correct |
| Right drawer — move to another night | sqn_admin | Reschedule a session | When else can this session run? | Reschedule decision | PW right drawer | K | A | Useful direct action |
| Bottom drawer — Activities tab | sqn_admin | See all events affecting the year | What events affect our planning? | Event awareness | PW bottom drawer | K | A | Correct reference view |
| Bottom drawer — Mission Backlog tab | sqn_admin | See and schedule outstanding curriculum | What still needs to be taught? | Planning decisions | PW bottom drawer | K | B | Also available in Main TMS Activities page (Type B). PW location is correct for planning context. Main TMS location should move (see Activities findings). |
| Bottom drawer — Facilitators tab | sqn_admin | Manage facilitators in planning context | Who is available? | Facilitator decisions | PW bottom drawer | K | B | Type B — Main TMS Facilitators is primary home. PW version adds leave management. |
| Bottom drawer button label "Activities ▲" | sqn_admin | Open the reference panel | What is this button for? | Open drawer | PW sticky button | S | A | The label "Activities ▲" gives no indication that the panel contains Facilitators, Rooms, Equipment, Holidays, Notices, and Mission Backlog. Better: "Planning Tools ▲" or "Resources ▲" |
| GuidedYearSetupModal | sqn_admin (new) | Walk through year setup step-by-step | How do I set up a new year? | Whether to proceed with each step | PW → "Guided year setup" button | K | A | Correct location; good wizard |
| SetupPanel (cold start) | sqn_admin (new) | Complete first-time setup | First time in PW — what do I do? | Whether to create a year | PW canvas when no years exist | K | A | Good onboarding |
| Help drawer | sqn_admin | Get in-context help about PW | How does this work? | Whether to continue | PW → ? button | K | A | Correct location |

---

## 15. Wing HQ Calendar (wing_admin)

| Function | User | Human need | Question answered | Decision | Current location | Recommendation | Classification | Evidence |
|---|---|---|---|---|---|---|---|---|
| Wing calendar grid/table | wing_admin | Manage wing-level events | What events has Wing HQ set? | Event management | Wing HQ Calendar page | K | A | Correct |
| + New Event | wing_admin | Add a wing-level event | When and what? | Creation | Wing HQ Calendar | K | A | Correct |

---

## Summary of Recommendations

| Recommendation | Function | Count |
|---|---|---|
| K — Keep as-is | Most functions | ~65 |
| M — Move (out of Activities page) | Training Year, Training Classes, Parade Dates, Holidays, Mission Backlog, Getting Help, Class Forecasts | 7 areas |
| S — Simplify | Needs Attention P5 separation, "Activities ▲" button label, Getting Started wizard, hardcoded years in calendar, left-panel Wing labels in PW | 5 items |
| MG — Merge | Not recommended at this stage (need Review 2 code analysis) | 0 |
| R — Retire | None confirmed | 0 |

**Primary finding: The Activities page is an information container — not a conceptual home.** Moving its non-Activities content to appropriate first-class locations would resolve 5 of the top 8 highest-friction workflows.

