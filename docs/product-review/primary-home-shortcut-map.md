# AAFC TMS — Primary Home and Contextual Shortcut Map

**Review:** Post-Gap Human Workflow, Architecture and Design Review — Stage 1  
**Date:** 2026-08-16

For every function in the system, this document records:
1. **Primary home** — where the function *should* live (proposed IA, not necessarily current location)
2. **Current home** — where it currently lives (may differ from proposed)
3. **Contextual shortcuts** — additional entry points that add value by proximity to related work
4. **Missing shortcuts** — entry points that would reduce friction but don't currently exist
5. **Mis-homed** — whether the current location is wrong

✓ = current home matches proposed  ⚠ = currently mis-homed  — = no shortcut needed

---

## Navigation / Orientation

| Function | Proposed primary home | Current home | Match? | Contextual shortcuts (exist) | Missing shortcuts |
|---|---|---|---|---|---|
| Dashboard | Dashboard | Dashboard | ✓ | Toolbar shortcut (implicit — home page) | — |
| Getting Started | Getting Started | Getting Started | ✓ | — | Link from first login; link from Dashboard when setup incomplete |
| Getting Help / Support | Persistent ? icon (toolbar) | Activities page (body text) | ⚠ | — | ? icon must be added to toolbar |
| Navigation itself | Sidebar nav | Sidebar nav | ✓ | — | — |

---

## Annual Plan / Training Year Setup

| Function | Proposed primary home | Current home | Match? | Contextual shortcuts (exist) | Missing shortcuts |
|---|---|---|---|---|---|
| Planning Year selector | Training Year (new nav) | Activities → Planning Year | ⚠ | — | From Getting Started; from Dashboard (setup prompt when no year exists) |
| + New Year | Training Year | Activities → + New Year | ⚠ | Getting Started checklist link | PW GuidedYearSetup modal (linked from Training Year) |
| Annual overview / summary | Training Year | Activities → year selected | ⚠ | Dashboard (period selector gives year view) | — |
| Training Classes | Training Year → Training Classes | Activities → year → Training Classes card | ⚠ | — | From Dashboard when no classes exist (setup prompt) |
| + Add Training Class | Training Year → + Add | Activities → year → Training Classes → + Add | ⚠ | — | From Getting Started |
| Parade Dates list | Training Year → Parade Dates | Activities → year → Parade Dates card | ⚠ | PW Year view (read-only) | — |
| Generate Parade Dates | Training Year → Generate | Activities → year → Parade Dates → Generate | ⚠ | Parade Nights page header → Generate (B — keep) | — |
| + Add single Parade Date | Training Year → + Add Date | Activities → year → Parade Dates → + Add Date | ⚠ | — | — |
| Holiday Periods list | Training Year → Holidays | Activities → year → Holiday & Stand-down card | ⚠ | Activities header → + Add Holiday (B — keep as shortcut) | — |
| + Add Holiday | Training Year → + Add Holiday | Activities → year → Holidays card → + Add / Activities header | ⚠ | Activities header button (keep as B after move) | — |
| Mission Backlog | Training Year → Mission Backlog | Activities → year → Mission Backlog card | ⚠ | PW → Bottom drawer → Mission Backlog (B — keep) | Dashboard card (missing) |
| Class Planning Forecasts | Training Year → Forecasts | Activities → year → Class Forecasts card | ⚠ | Dashboard (chart section C, partial — add on-track/at-risk badge) | Dashboard summary card |
| Rollover planning year | Training Year → [year action] | Activities → year (no direct UI — API exists) | ⚠ | — | Visible rollover action at year end |

---

## Parade Nights

| Function | Proposed primary home | Current home | Match? | Contextual shortcuts (exist) | Missing shortcuts |
|---|---|---|---|---|---|
| Parade Nights list | Parade Nights | Parade Nights | ✓ | Dashboard → Section A upcoming nights | Training Calendar (click day → night detail) |
| Add Parade Night | Parade Nights → + Add | Parade Nights → + Add | ✓ | — | — |
| Generate Parade Nights | Parade Nights → Generate | Activities → year → Parade Dates → Generate (secondary) + Parade Nights header (primary) | ✓ (PN header is better) | Activities page (B — keep) | — |
| Parade Night detail | Parade Nights → click night | Parade Nights → click night | ✓ | Training Calendar → click date | Dashboard → Section A → upcoming card → click |
| Add Session | Parade Nights → night → + Add Session | Parade Nights → night → + Add Session | ✓ | PW → click empty cell (B) | — |
| Quick Edit Session | Parade Nights → night → session → pencil | Parade Nights → night → session → pencil | ✓ | PW → session cell → right drawer (B) | Dashboard → Record last night card (missing shortcut) |
| Record session outcome | Parade Nights → night → session → Quick Edit | Same | ✓ | Needs Attention → P2 item link | Dashboard "Record last night" card (missing shortcut to bulk recording) |
| Publish Parade Night | Parade Nights → night → Publish | Same | ✓ | — | — |
| Close Parade Night | Parade Nights → night → Close | Same | ✓ | — | — |
| Bulk cancel sessions | Parade Nights → night → Cancel All | Same | ✓ | — | — |
| Copy sessions to another night | Parade Nights → night → Copy | Same | ✓ | — | — |
| Save night as template | Parade Nights → night → Save as template | Same | ✓ | — | — |
| Bulk apply template | Parade Nights → bulk select → Apply template | Same | ✓ | — | — |
| Navigate to calendar | Parade Nights → Calendar link | Same (contextual nav link in header) | ✓ | — | — |
| Navigate to weekly program | Parade Nights → Weekly Program link | Same | ✓ | — | — |

---

## Training Calendar

| Function | Proposed primary home | Current home | Match? | Contextual shortcuts (exist) | Missing shortcuts |
|---|---|---|---|---|---|
| Monthly calendar grid | Training Calendar | Training Calendar | ✓ | PW → Calendar route (B) | — |
| Month navigation | Training Calendar | Same | ✓ | — | — |
| Year selector | Training Calendar | Same (hardcoded 2025/2026/2027) | ✓ (but needs dynamic) | — | — |
| Navigate to parade night from calendar | Training Calendar → click date | Training Calendar → click date (if wired) | ✓ | — | — |

---

## Weekly / Parade Night Program

| Function | Proposed primary home | Current home | Match? | Contextual shortcuts (exist) | Missing shortcuts |
|---|---|---|---|---|---|
| Print-ready program | Weekly Program | Weekly Program | ✓ | Toolbar → Print Program button (B) | Parade Nights header → Print button |
| Select parade night | Weekly Program → selector | Same | ✓ | — | — |
| Filter sessions | Weekly Program → filter | Same | ✓ | — | — |

---

## Curriculum

| Function | Proposed primary home | Current home | Match? | Contextual shortcuts (exist) | Missing shortcuts |
|---|---|---|---|---|---|
| Curriculum list | Curriculum | Curriculum | ✓ | PW → Curriculum route (B) | — |
| Phase/stage tabs | Curriculum → tabs | Same | ✓ | — | — |
| Matrix view | Curriculum → Matrix tab | Same | ✓ | — | — |
| Filter by element/progress | Curriculum → filters | Same | ✓ | — | — |
| Drill-down sessions for item | Curriculum → item click → panel | Same | ✓ | — | — |
| Learning Hub link | Curriculum → item → LH link | Same | ✓ | — | — |
| Export curriculum | Curriculum → Export | Same | ✓ | — | — |
| Import curriculum (admin) | Curriculum → Import | Same | ✓ | System Console → Curriculum Import (B for system_admin) | — |
| Add/edit curriculum (admin) | Curriculum → add | Same | ✓ | — | — |
| Archive/restore curriculum (admin) | Curriculum → archive | Same | ✓ | — | — |

---

## Activities (AAFC Events)

After IA-01 implementation, the Activities page contains only:

| Function | Proposed primary home | Current home | Match? | Contextual shortcuts (exist) | Missing shortcuts |
|---|---|---|---|---|---|
| Squadron activities list | Activities | Activities | ✓ | Training Calendar (display only, B) | — |
| + Add Activity | Activities | Activities | ✓ | — | — |
| Generate Activities | Activities | Activities | ✓ | — | — |
| Inherited wing activities | Activities (display) | Activities | ✓ | Wing Activities page for wing users (B) | — |
| Inherited national activities | Activities (display) | Activities | ✓ | — | — |
| Filter by type/importance | Activities | Same | ✓ | — | — |
| Import CEA activities | Activities → Import CEA | Same | ✓ | — | — |

---

## Facilitators

| Function | Proposed primary home | Current home | Match? | Contextual shortcuts (exist) | Missing shortcuts |
|---|---|---|---|---|---|
| Facilitators table | Facilitators | Facilitators | ✓ | PW → Facilitators route (B); PW → Bottom drawer Facilitators tab (B) | — |
| Analytics charts (workload, coverage) | Facilitators | Same | ✓ | Dashboard → Section D (partial, B) | — |
| + Add Facilitator | Facilitators | Same | ✓ | — | — |
| Edit / Archive Facilitator | Facilitators → row action | Same | ✓ | — | — |
| Facilitator Stats drill-down | Facilitators → Stats icon | Same | ✓ | — | — |
| Import facilitators CSV | Facilitators → Import CSV | Same | ✓ | — | — |
| Facilitator suggestions in session | Session Quick Edit modal → Facilitators suggestions | Session Quick Edit modal | ✓ | PW → session form (B) | — |
| Facilitator leave management | PW → Bottom drawer → Facilitators tab → leave | PW only | ✓ (PW is correct home) | — | Main TMS Facilitators profile page (shortcut to add leave while in admin context) |
| Facilitator schedule timeline | PW → Facilitator Schedule route | PW only | ✓ (PW is correct home) | Main TMS Facilitators → link to PW schedule (missing) | Link from Main TMS Facilitators page to PW Facilitator Schedule |
| Facilitator absorb (merge) | Facilitators → absorb action | Facilitators row action | ✓ | — | — |

---

## Rooms and Equipment

| Function | Proposed primary home | Current home | Match? | Contextual shortcuts (exist) | Missing shortcuts |
|---|---|---|---|---|---|
| Rooms list | Rooms and Equipment | Resources & Training Areas | ✓ (after rename) | PW → Rooms tab (B); PW → Resources route (B) | — |
| + Add Room | Rooms and Equipment | Same | ✓ | PW → Rooms tab → + Add (B) | — |
| Equipment list | Rooms and Equipment | Same | ✓ | PW → Equipment tab (B) | — |
| + Add Equipment | Rooms and Equipment | Same | ✓ | PW → Equipment tab → + Add (B) | — |
| Resource Clash Checker | Rooms and Equipment → Clash Check | PW → Resources → Clash Checker | ⚠ | PW Resources (current home, B) | This tool should be in Main TMS Resources page too |

---

## Needs Attention

| Function | Proposed primary home | Current home | Match? | Contextual shortcuts (exist) | Missing shortcuts |
|---|---|---|---|---|---|
| P0 Command Decision items | Needs Attention (top) | Needs Attention | ✓ | Dashboard quick action | — |
| P1–P4 Operational alerts | Needs Attention | Needs Attention | ✓ | Dashboard quick action | — |
| P5 Curriculum backlog (Mission Backlog) | Training Year → Mission Backlog (separate) | Needs Attention (mixed in) | ⚠ | — | — |
| What Changed? activity feed | Needs Attention (visible above fold) | Needs Attention (below fold, after all action items) | ⚠ | — | Dashboard "Last activity" section |
| Run exception checks | Needs Attention → Run Checks button | Same | ✓ | — | — |

---

## Planning Workspace

| Function | Proposed primary home | Current home | Match? | Contextual shortcuts (exist) | Missing shortcuts |
|---|---|---|---|---|---|
| Planning Workspace (entry) | Planning Workspace ↗ nav link | Nav → Planning Workspace ↗ (conditional) | ⚠ | — | "Open in Planning Workspace" button on Mission Backlog page; on Parade Nights page |
| PW Year view | PW → Year | PW canvas | ✓ | — | — |
| PW Term view | PW → Term | PW canvas | ✓ | — | — |
| PW 8-week/2-week/Night views | PW → view selector | PW canvas | ✓ | — | — |
| Guided Year Setup wizard | PW → Guided Year Setup button | PW (first-run prompt) | ✓ | — | Getting Started → link to PW wizard |
| Right drawer (session edit) | PW → session cell click | PW | ✓ | — | — |
| Conflict management | PW → conflict badge click | PW | ✓ | — | — |
| Bottom drawer — "Planning Tools" | PW → Planning Tools ▲ button | PW → Activities ▲ button (mislabelled) | ⚠ (rename needed) | — | — |
| Facilitator schedule | PW → Facilitator Schedule route | PW | ✓ | — | Link from Main TMS Facilitators page |
| Cadet management | PW → Cadets route | PW | ✓ | — | — |
| Imports | PW → Imports route | PW | ✓ | — | — |
| Reports | PW → Reports route | PW | ✓ | — | — |
| Report Catalogue | PW → Report Catalogue route | PW | ✓ | — | — |
| Action Items | PW → Action Items route | PW | ✓ | Main TMS → Needs Attention (B) | — |
| Wing Assurance / Wing Overview | PW → Wing Assurance / Main TMS → Wing Overview | Both | ✓ | — | — |
| National Assurance / National Overview | PW → National Assurance / Main TMS → National | Both | ✓ | — | — |

---

## Unit Settings

| Function | Proposed primary home | Current home | Match? | Contextual shortcuts (exist) | Missing shortcuts |
|---|---|---|---|---|---|
| Squadron Details | Unit Settings | Unit Settings | ✓ | — | — |
| Parade Day and Time | Unit Settings | Unit Settings | ✓ | — | PW → Update Future Parade Nights (link these together) |
| Session Structure | Unit Settings | Unit Settings | ✓ | — | — |
| Timing Templates | Unit Settings → Timing Templates | Unit Settings (below fold) | ✓ | — | Quick link from Parade Nights (contextual: "Manage templates") |
| Display Size preference | Toolbar → all users | Unit Settings (sqn_admin only) | ⚠ | — | Toolbar icon must be added |
| Flights | Unit Settings → Flights | Account Management → Flights | ⚠ | — | — |
| Reference Data | Unit Settings → Reference Data | Account Management → Reference Data | ⚠ | — | — |
| Change my access code | Unit Settings / PW Access Codes route | Both | ✓ | Both locations correct | — |

---

## Account Management

| Function | Proposed primary home | Current home | Match? | Contextual shortcuts (exist) | Missing shortcuts |
|---|---|---|---|---|---|
| User accounts list | Account Management | Account Management | ✓ | PW → Accounts route (B) | — |
| + Add Account | Account Management | Same | ✓ | — | — |
| Edit / Disable / Archive account | Account Management | Same | ✓ | — | — |
| Reset access code | Account Management | Same | ✓ | — | — |
| Unlock account | Account Management | Same | ✓ | — | — |
| Wings management | Account Management (national) | Same | ✓ | System Console → Scope Map (national admin B) | — |
| Squadrons management | Account Management (wing/nat) | Same | ✓ | System Console → Scope Map (system_admin B) | — |

---

## System Console (system_admin only)

| Function | Proposed primary home | Current home | Match? | Contextual shortcuts (exist) | Missing shortcuts |
|---|---|---|---|---|---|
| System Overview | System Console | Same | ✓ | — | — |
| Platform Health | System Console | Same | ✓ | — | — |
| Scope Map | System Console | Same | ✓ | Account Management → Wings/Squadrons (B) | — |
| Maintenance Mode | System Console | Same | ✓ | — | — |
| Curriculum Import | System Console | Same | ✓ | Curriculum page → Import (B) | — |
| Bootstrap / Provision | System Console | Same | ✓ | — | — |
| Backup | System Console | Same | ✓ | — | — |
| Audit Summary | System Console | Same | ✓ | Audit page (B) | — |

---

## Summary of missing shortcuts (implementation candidates for Review 3)

| Missing shortcut | Where to add | What it provides |
|---|---|---|
| "Record last night's outcomes" | Dashboard → Section A (post-parade) | Bulk outcome recording path (resolves WF-01 gap) |
| Mission Backlog summary card | Dashboard → Section C | Quick class-level backlog overview (resolves WF-02 partially) |
| "Open in Planning Workspace" button | Parade Nights page; Mission Backlog page | Cross-app discovery and transition |
| Link to PW Facilitator Schedule | Main TMS Facilitators page | Quick access to timeline from facilitator management context |
| "Manage templates" link | Parade Nights page | Quick access to Timing Templates in Unit Settings |
| Persistent ? Help icon | Toolbar | Always-on help access (resolves CF-06) |
| PW Year Setup link in Getting Started | Getting Started page | Guides new users to the wizard that already exists |
| PW wizard link from Annual Plan (Training Year) | Training Year (new nav) | Direct path to GuidedYearSetupModal for first-time setup |
| Update Existing Dates offer on Parade Day change | Unit Settings → Parade Day change | Links the Settings change to the PW Update Future Dates modal |
| Display Size in toolbar | Toolbar icon | Accessible to all roles, not just sqn_admin |

