# 02 — TMS ↔ Planning Workspace ownership matrix

Date: 2026-08-30 · Baseline `fecbcde` · Instruction Part 7

Rebuilt from the code, not from the previous matrix. Route lists are measured:
24 `id="page-*"` surfaces in `connected-frontend`, 24 `<Route>` paths in PW.

## The decision rule (Part 7)

| question | primary home |
|---|---|
| What is this thing? What are its authoritative details? What happened? Who owns it? How is it configured? | **TMS** |
| When should it happen? What conflicts? Can this facilitator deliver it? What changes if I move it? Is the plan workable? | **PW** |

## Matrix

| function | canonical backend owner | primary home | secondary representation | write in TMS | write in PW | why | duplicate? | disposition |
|---|---|---|---|---|---|---|---|---|
| Account management | `User` | **TMS** | none | yes | **no** | Identity and authority are "what is true" | **YES — PW `/accounts`** | **REMOVE from PW** |
| Organisation management | `Wing`/`Squadron` | **TMS** | read-only context | yes | no | Configuration | **YES — PW `/admin`, `/settings`** | **REMOVE from PW** |
| Audit log | `AuditLog` | **TMS** | contextual "who changed this" | n/a | n/a | History is a record, not a plan | **YES — PW `/audit`** | **REDUCE to contextual** |
| Facilitator roster | `Facilitator` | **TMS** | availability + suitability while scheduling | yes | no | Roster is master data; suitability is a planning question | **YES — PW `/facilitators`** | **REPLACE with contextual view** |
| Training Areas | `TrainingArea` | **TMS** | capability/availability filter during selection | yes | no | Same split | **YES — PW `/resources`** | **REPLACE with contextual view** |
| Curriculum / Program | `CurriculumItem` (live) | **TMS** | gap analysis, backlog placement | yes | no | Content is governed; placement is planning | **YES — PW `/curriculum`** | **REPLACE with gap view** |
| Cadets | `Cadet` | **TMS** | not needed to plan | yes | no | Class-level planning must work without a roster (Part 16) | **YES — PW `/cadets`** | **REMOVE from PW** |
| Imports (CEA, curriculum) | `CeaActivity` | **TMS** | read-only anchors | yes | no | Import is a data-governance act | **YES — PW `/imports`** | **REMOVE from PW** |
| Reports / catalogue | various | **TMS** | none | n/a | n/a | Reporting is "what happened" | **YES — PW `/reports`, `/report-catalogue`** | **REMOVE from PW** |
| Wing / National overview | various | **TMS** | none | n/a | n/a | Oversight is not planning | **YES — PW `/national-overview`** | **REMOVE from PW** |
| Action items | `ActionItem` | **TMS** | planning consequences only | yes | partial | Ownership vs consequence | **PARTIAL — PW `/action-items`** | **ASSESS** |
| Dashboard | derived | **TMS** | PW has its own planning summary | n/a | n/a | Two different questions | **PARTIAL — PW `/dashboard`** | **ASSESS** |
| Activities | `Activity` | **TMS** | timeline anchor, impact-if-moved | yes | no | Classify in TMS, schedule around in PW | no | keep split |
| Parade Nights | `ParadeNight` | **TMS** (list, publish state) | **PW** (the planning canvas) | yes | yes | Both, deliberately | no | keep split |
| Sessions | `Session` | **PW** (placement) | TMS shows outcome and record | yes | yes | Placement is planning; outcome is record | no | keep split |
| Session audience | `SessionAudience` | **PW** | TMS detail | yes | yes | Chosen while placing | no | keep split |
| Training Classes | `TrainingClass` | **TMS** | audience selection | yes | no | Structure is configuration | no | keep split |
| Timing Templates | `TimingTemplate` | **TMS** (authoring) | **PW must display blocks** (Part 14) | yes | future-night override only | Structure vs use | no | **PW display MISSING** |
| Holidays | `HolidayPeriod` | **TMS** | excluded dates on canvas | yes | no | Reference data | no | keep split |
| Notices | `PlanningNotice` | both | both | yes | yes | Written where noticed | no | keep split |
| Mission Backlog | derived | **PW** | none | n/a | n/a | Purely a planning question | no | PW only |
| Plan Review / publish readiness | derived | **PW** | TMS shows published state | n/a | n/a | "Will the plan work?" | no | PW only |
| Training Year context | `PlanningYear` | shared context | shared context | materialise-on-write | materialise-on-write | Context, not a page | no | **already unified** |

## Result

**11 PW routes are duplicated TMS management surfaces** and are dispositioned
REMOVE or REPLACE-WITH-CONTEXTUAL. Two more (`/dashboard`, `/action-items`)
need assessment rather than assumption.

**Part 8 requires proof before deletion**, not grep. None of these has had
reachability proven yet, so none is removed in this document — this is the
disposition, and the removal is the next piece of work.

## The one confirmed missing capability

**Timing Template blocks are not displayed in PW** (Part 14). Every other row is
either correct today or a duplicate to remove; this is the only row where PW
lacks something it must have.
