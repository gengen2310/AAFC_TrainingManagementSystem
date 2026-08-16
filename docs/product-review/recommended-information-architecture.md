# AAFC TMS — Recommended Information Architecture

**Review:** Post-Gap Human Workflow, Architecture and Design Review — Stage 1  
**Date:** 2026-08-16  
**Status:** Proposals only — DO NOT implement during Review 1. Awaiting user approval.

This document proposes a restructured information architecture based on the findings from:
- `human-workflow-map.md`
- `navigation-audit.md`
- `findability-audit.md`
- `workflow-effort-audit.md`
- `duplicate-function-register.md`

---

## Design principles applied

1. **Navigate by intent, not by system concept** — nav items must match what a Training Officer is trying to do, not how the database is organised.
2. **Everything a Training Officer does weekly must be ≤ 3 taps from the home page.**
3. **Annual setup tasks must be in one clearly-labelled place.**
4. **Help is always 1 tap away.**
5. **Terminology must match AAFC language, not software language.**
6. **The Activities nav item must only contain Activities** (AAFC events/camps/activities).

---

## Proposed Navigation Tree — Squadron scope (sqn_admin)

```
AAFC TMS
│
├── Dashboard                           [unchanged]
│   ├── Section A: Tonight & This Week  [unchanged]
│   ├── Section B: Delivery analytics   [unchanged]
│   ├── Section C: Curriculum progress  [unchanged — but add Mission Backlog card]
│   ├── Section D: Staffing resilience  [unchanged]
│   └── [NEW] Record last night's outcomes card
│          (appears after a parade night date; one-click path to outcome entry)
│
├── Training Year                       [NEW nav item — replaces Planning Year in Activities]
│   ├── Year selector / + New Year
│   ├── Annual overview (calendar grid of terms + parade nights)
│   ├── Training Classes
│   │   ├── View classes, add, archive, restore
│   │   └── Class membership / cadet assignment
│   ├── Parade Dates
│   │   ├── List of dates with holiday flags
│   │   ├── Generate dates (rule-based)
│   │   └── Add single date
│   ├── Holiday Periods
│   │   ├── List of holiday/stand-down periods
│   │   └── Add/edit/delete period
│   ├── Mission Backlog                [MOVED FROM Activities — now prominently accessible]
│   │   ├── Filter by class, stage, status
│   │   └── Per-class CSV export
│   └── Class Forecasts
│       └── On-track / at-risk indicators per class
│
├── Parade Nights                       [unchanged content; minor label refinements]
│   ├── List of parade nights (filter by term, status)
│   ├── Parade Night detail
│   │   ├── Session grid
│   │   ├── Quick Edit per session
│   │   ├── Guided session entry
│   │   └── Bulk actions (publish, close, cancel all, copy template)
│   ├── Generate Parade Nights          [currently also in Activities; promote as primary here]
│   ├── Calendar link                   [contextual shortcut to Training Calendar]
│   └── Weekly Program link             [contextual shortcut to Weekly Program]
│
├── Training Calendar                   [unchanged]
│
├── Weekly Program                      [unchanged; consider renaming to "Parade Night Program"]
│
├── Curriculum                          [unchanged]
│
├── Activities                          [SIMPLIFIED — removes all non-activities content]
│   ├── Squadron activities (add, edit, archive)
│   ├── Inherited Wing/National activities (read-only from owning scope)
│   ├── Inherited CEA activities (read-only)
│   ├── Generate activities
│   └── Import CEA
│   [REMOVED: Getting Help, Planning Year, Parade Dates, Training Classes, Holidays, Mission Backlog]
│
├── Facilitators                        [unchanged]
│
├── Rooms and Equipment                 [RENAMED from "Locations and Resources"]
│   ├── Rooms / Training Areas          [unchanged content]
│   └── Equipment                       [unchanged content]
│
├── Needs Attention                     [RESTRUCTURED — separate operational from backlog]
│   ├── Requires Action (P0–P4 items)   [shown by default — short list]
│   ├── Planning Backlog (P5 items)     [collapsed — expandable]
│   └── What Changed?                   [moved up; visible without scroll]
│
├── Planning Workspace ↗                [external link — ensure always visible; add tooltip]
│
├── Getting Started                     [unchanged; improve to guided wizard — IA-08]
│
├── Unit Settings                       [EXPANDED — absorbs Reference Data and Flights]
│   ├── Squadron Details
│   ├── Parade Day and Time
│   ├── Session Structure
│   ├── Timing Templates
│   ├── Display Size                    [MOVE from sqn_admin-only to all users via toolbar]
│   ├── Flights                         [MOVED from Account Management]
│   └── Reference Data                  [MOVED from Account Management]
│       ├── Training Stages
│       ├── Facilitator Types
│       └── Subject Areas
│
└── Account Management                  [SIMPLIFIED — removes Reference Data and Flights]
    ├── User Accounts (add, edit, disable, archive)
    ├── Wings (national+)
    └── Squadrons (wing/national)
```

### Persistent UI elements (always visible, not in nav)

```
TOOLBAR (top right, always visible)
├── Print Program button                [unchanged]
├── ? Help icon                         [NEW — opens Getting Help content]
│      (replaces Getting Help buried in Activities)
├── Display Size toggle                 [MOVED from Unit Settings page]
└── User avatar / Access Code change    [access code always accessible]
```

---

## What moves, what merges, what retires

### Moves

| Function | From | To | Priority |
|---|---|---|---|
| Planning Year selector + New Year | Activities page | Training Year (new top-level) | P1 |
| Training Classes card | Activities → Planning Year | Training Year section | P1 |
| Parade Dates card | Activities → Planning Year | Training Year section | P1 |
| Holiday Periods card | Activities → Planning Year | Training Year section | P1 |
| Mission Backlog card | Activities → Planning Year | Training Year section (+ Dashboard card) | P1 |
| Class Planning Forecasts | Activities → Planning Year | Training Year section | P1 |
| Getting Help content | Activities page body | Persistent ? help icon | P1 |
| Reference Data | Account Management | Unit Settings | P2 |
| Flights management | Account Management | Unit Settings | P2 |
| Display Size preference | Unit Settings (sqn_admin only) | Toolbar (all users) | P2 |
| What Changed? | Needs Attention (bottom) | Needs Attention (top, after action items) | P2 |
| Generate Parade Nights | Activities → Parade Dates card (secondary) | Parade Nights page header (primary) | P3 |

### Restructures (no data changes — presentation only)

| Page | Change | Priority |
|---|---|---|
| Needs Attention | Split P5 backlog from P0-P4 operational items | P2 |
| Dashboard | Add Mission Backlog summary card (count by class) | P2 |
| Dashboard | Add "Record last night's outcomes" shortcut card | P2 |
| Unit Settings | Group into clear sections with headings | P3 |

### Renames

| Current label | Proposed label | Reason |
|---|---|---|
| "Locations and Resources" (nav) | "Rooms and Equipment" | Concrete and specific; eliminates nav/page title mismatch |
| "Resources & Training Areas" (page title) | "Rooms and Equipment" | Match nav |
| "Weekly Program" | "Parade Night Program" (or keep "Weekly Program") | Clarifies it is per-night, not per-week |
| "Activities ▲" (PW bottom drawer button) | "Planning Tools ▲" | Label matches contents (facilitators, rooms, equipment, etc.) |
| "Settings" (nav, when referring to Unit Settings) | "Unit Settings" | Match page title |

### Retires / Hides

| Function | Action | Reason |
|---|---|---|
| P5 items in Needs Attention (visible by default) | Collapse to secondary tab / expand-on-demand | Currently floods the page; hides P0-P4 operational items |
| Hardcoded year selector (2025/2026/2027 in Training Calendar) | Replace with dynamic calculation | Will fail post-2027 |

### No change recommended

| Function | Reason |
|---|---|
| Dashboard sections A, B, C | Well-structured and correctly prioritised |
| Parade Nights page structure | Session management works well |
| Curriculum page | Good filter system, matrix view is a strong feature |
| Facilitators page | Analytics + table structure is appropriate |
| Account Management (accounts portion) | Correct design; remove only Reference Data and Flights |
| Planning Workspace architecture | Correct as-is; label and discovery improvements only |
| Two-frontend separation (Main TMS + PW) | Architecture decision — do not merge |

---

## Proposed navigation labels (final)

Squadron scope (sqn_admin), in display order:

1. Getting Started *(rename to "New Here?" if audience is always new officers — discuss)*
2. Dashboard
3. **Training Year** *(new)*
4. Parade Nights
5. Training Calendar
6. Parade Night Program *(or Weekly Program)*
7. Curriculum
8. Activities
9. Facilitators
10. Rooms and Equipment *(renamed)*
11. Needs Attention
12. Planning Workspace ↗
13. Unit Settings
14. Account Management

---

## Impact assessment

### What changes for users
- Finding Training Year setup: 5–7 taps → 2 taps (major improvement)
- Finding Mission Backlog: 7 taps → 2 taps (major improvement)
- Finding Help: 4 taps + scroll → 1 tap (major improvement)
- Activities page: now contains only AAFC activities (cleaner, matches label)
- Needs Attention: shorter operational list, backlog separate (less overwhelming)

### What does NOT change for users
- All existing workflows that currently work well
- All data — nothing is deleted or archived
- Planning Workspace (no structural changes)
- Parade Nights workflow (no structural changes)
- Curriculum, Facilitators, Dashboard (no structural changes)

### Backend API impact
None — all proposed changes are frontend navigation and presentation changes. The underlying API endpoints, data models, and permissions are unchanged. All proposed moves are restructuring the HTML/JS navigation in `connected-frontend/index.html`, not changes to the data layer.

---

## Implementation sequencing (for Review 2 → Review 4 consideration)

When authorised to implement, recommended sequence:

**Phase 1 (highest impact, lowest risk — navigation restructure):**
1. Create "Training Year" nav item; move Planning Year + sub-cards there
2. Add "? Help" persistent icon with Getting Help content
3. Simplify Activities page (remove moved content)
4. Rename "Locations and Resources" → "Rooms and Equipment"

**Phase 2 (medium impact — dashboard shortcuts):**
5. Add Mission Backlog summary card to Dashboard
6. Add "Record last night's outcomes" shortcut card to Dashboard
7. Separate P0-P4 from P5 in Needs Attention
8. Move What Changed? above the fold in Needs Attention

**Phase 3 (lower impact — cleanup):**
9. Move Reference Data and Flights to Unit Settings
10. Move Display Size to toolbar (all roles)
11. Dynamic year selector in Training Calendar
12. Rename PW bottom drawer button: "Activities ▲" → "Planning Tools ▲"
13. Update Getting Started to guided wizard

