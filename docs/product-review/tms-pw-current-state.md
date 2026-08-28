# TMS ↔ Planning Workspace — Current State Snapshot

**Branch:** main
**HEAD SHA:** 6d45e22
**Date recorded:** 2026-08-28
**Purpose:** Baseline for the TMS ↔ PW Integration, Function Ownership and Workflow
Simplification Program. Do not restructure any feature area until this document exists.

---

## 1. Repository layout

| Path | Service | Technology | Deployed at |
|---|---|---|---|
| `connected-frontend/index.html` | `aafc-tms-frontend` | Single-file HTML/CSS/JS SPA (~400 KB) | `/` (root) |
| `frontend/` | `aafc-tms-planning-workspace-preview` | React + Vite + TypeScript | `/planning` |
| `backend/` | `aafc-tms-backend` | FastAPI + SQLAlchemy + Alembic | `/api/*` |

Both frontends read their backend URL from a `<meta name="aafc-api-base">` tag
rewritten at container start. They are intentionally separate services.

---

## 2. TMS frontend — navigation pages

Pages registered via `nav(id)` in `connected-frontend/index.html` (current HEAD):

**Squadron scope**
- `dashboard` — squadron overview
- `getting-started` — setup checklist
- `parade-nights` — parade night list + session editor
- `calendar` — annual calendar view
- `weekly-program` — weekly schedule
- `curriculum` — curriculum browser
- `facilitators` — staff roster
- `resources` — training areas + equipment
- `activities` — activity log
- `accounts` — account management
- `action-items` — action item list
- `audit` — audit log
- `settings` — squadron settings
- `help` — contextual help

**Wing scope** (additions/replacements)
- `wing-overview` — wing-level overview
- `wing-activities` — wing activity log
- `wing-calendar` — wing calendar

**National scope** (additions/replacements)
- `national` — national overview
- `national-activities` — national activity log

**System admin only**
- `system-console` — system administration console
- `service-desk` — service desk

---

## 3. Planning Workspace — routes

From `frontend/src/App.tsx` (current HEAD):

**Planning-specific (correct ownership)**
- `/planning` — main planning canvas
- `/calendar` — PW calendar view
- `/parade-nights` — PW parade night list
- `/weekly-program` — PW weekly view
- `/facilitator-schedule` — facilitator schedule (PW-specific)

**Duplicated from TMS (target for Section 43 audit)**
- `/dashboard` — overlaps TMS dashboard
- `/curriculum` — overlaps TMS curriculum browser
- `/facilitators` — overlaps TMS facilitators page
- `/resources` — overlaps TMS resources page
- `/cadets` — overlaps TMS cadet management
- `/reports` — overlaps TMS reporting
- `/report-catalogue` — overlaps TMS
- `/action-items` — overlaps TMS action items
- `/imports` — overlaps TMS imports
- `/audit` — overlaps TMS audit log
- `/admin` — overlaps TMS admin/settings
- `/accounts` — overlaps TMS accounts
- `/settings` — overlaps TMS settings
- `/wing-overview` — overlaps TMS wing-overview
- `/national-overview` — overlaps TMS national overview

**Module mode**: When TMS opens PW via "Open Planning Workspace" button, the
`<meta name="aafc-module-mode" content="true">` tag is set. In this mode only the
`/planning` route renders; `AppShell` is suppressed. The PW tab shows the planning
canvas only.

---

## 4. Context handoff: TMS → PW

When TMS opens PW (`connected-frontend/index.html`, line 5931–5936):

```
/planning#t={token}&y={yearInt}
```

- `t` — JWT token (required for Firefox cross-origin sessionStorage limitation; FF-01 fix)
- `y` — training year integer

**What is NOT passed**: squadron ID. PW must resolve squadron from the token's principal.
The token carries `squadron_id` in its claims, so PW can recover it — but the explicit
year integer is the only planning context passed.

---

## 5. Key backend models — current state

### Training / Schedule

| Model | Table | Key fields | Notes |
|---|---|---|---|
| `TrainingYear` | `training_years` | `year` (int), `squadron_id` | The annual envelope |
| `TrainingClass` | `training_classes` | `training_stage_id` (nullable FK → `curriculum_phases`), `stage_code` (nullable) | Stage link is OPTIONAL at HEAD — Section 15 addresses this |
| `CurriculumPhase` | `curriculum_phases` | `name`, `short_name`, `display_order` | Training Stage (ORI/INI/JNR/INT/SNR) |
| `TimingTemplate` | `timing_templates` | `name`, `squadron_id` | Evening structure template |
| `TimingBlock` | `timing_blocks` | `template_id`, `block_type`, `is_instructional_period`, `order_index`, `duration_minutes` | Block within an evening; `is_instructional_period=True` → generates schedulable session slots |
| `ParadeNight` | `parade_nights` | `session_count` (int, default 3), `timing_template_id` (nullable) | `session_count` = fallback training period count when no timing template assigned |
| `Session` | `sessions` | `timing_block_id` (nullable FK to `timing_blocks.id`, app-layer only), `audience` (via `SessionAudience`) | |
| `SessionAudience` | `session_audiences` | `session_id`, `training_class_id`, `outcome_override` | Many-to-many; supports combined sessions with per-class outcome overrides |
| `CustomTrainingPhase` | `custom_training_phases` | `name`, `scope_type`, `scope_id`, `start_date`, `end_date` | Very minimal — just a named date-range envelope. No curriculum linkage at HEAD. |

### Planning Workspace

| Model | Table | Key fields | Notes |
|---|---|---|---|
| `PlanningYear` | `planning_years` | `unit_id` (nullable), `wing_id` (nullable), `year`, `active_status` | Note: "PlanningYear" ≠ "TrainingYear" — different tables/concepts |
| `ParadeDate` | `parade_dates` | `planning_year_id`, `parade_date`, `parade_type`, `term`, `week_number`, `parade_night_id` (nullable FK) | Links parade schedule to `parade_nights` records |
| `HolidayPeriod` | `holiday_periods` | `planning_year_id`, `start_date`, `end_date`, `affects_parade` | |
| `ParadeNightTemplate` | `parade_night_templates` | `name`, `squadron_id` | Reusable session *content* template (curriculum/facilitator/room intent). Separate from `TimingTemplate`. |

### Resources

| Model | Table | Key fields | Notes |
|---|---|---|---|
| `TrainingArea` | `training_areas` | `name`, `type`, `capacity`, `capabilities` (JSON list of strings) | `capabilities` is NOT typed in PW's TypeScript types; NOT displayed in PW's Resources route |

### Program

| Model | Table | Key fields | Notes |
|---|---|---|---|
| `ProgramPackage` | `program_packages` | `owning_scope`, `wing_id`, `squadron_id` | Tiered visibility: national → all, wing → wing+, squadron → squadron+ |
| `ProgramItem` | `program_items` | `code`, `title`, `owning_scope`, `core_status` | |
| `PromotionRequest` | `promotion_requests` | `program_item_id`, `from_scope`, `to_scope`, `status` | Scope-filtered at HEAD (REM-155, 6d45e22) |

---

## 6. Getting Started checklist — current state

File: `backend/app/routers/setup.py`

Steps emitted at HEAD (in order):

| Key | Label | Blocking? | Logic |
|---|---|---|---|
| `planning_year_created` | Set up your training year | Yes | `PlanningYear` count > 0 |
| `parade_dates_configured` | Configure your parade dates | Yes | `ParadeDate` count > 0 |
| `training_classes_created` | Create your training classes | Yes | `TrainingClass` count > 0 |
| **`cadets_added`** | **Add cadets to the squadron roster** | **Yes** | `Cadet` count > 0 |
| `sessions_scheduled` | Schedule your first session | Yes | `Session` count > 0 |

`cadets_added` is a non-optional step that blocks `complete=True`. **Section 7 of the
integration brief removes this step from the checklist UI** (capability is preserved —
adding cadets remains a core function; it is simply not gated in the onboarding flow).

---

## 7. Planning Checks / Decision Guide — current state

Location: `connected-frontend/index.html`, functions `loadPlanningChecks()`,
`_renderDecisionGuide()`, `runAllChecks()`.

Current behaviour:
- "Run All Checks" = manual button → POST `/api/planning/years/{yearId}/run-checks`
- Decision Guide = boolean ✅/🔴 yes/no questions
- Planning Checks exist **only in TMS** — absent from PW entirely
- Output is a flat pass/fail list — no outcome statements, no severity tiers
- "Publish Readiness" is not a separate concept — conflated with check results

Target state (Sections 26–34 of brief): replace with auto-triggered "Plan Review"
producing outcome statements (READY / READY WITH WARNINGS / NOT READY / NOT ENOUGH
INFORMATION), with Publish Readiness as a distinct concept surfaced in PW.

---

## 8. Training Area capabilities — current state

Backend: `TrainingArea.capabilities` = JSON list of display-name strings.

PW TypeScript API type (`frontend/src/api/types.ts`):
```typescript
TrainingArea: { training_area_id, name, type, capacity, [k: string]: unknown }
```
`capabilities` is in the index signature only — not a typed field.

PW Resources route (`frontend/src/routes/Resources.tsx`): shows name, type, capacity
only. **Capabilities are NOT displayed.** Section 21–25 of the brief addresses this.

---

## 9. Mission Backlog — current state

Only location: `frontend/src/components/planning/PlanningBottomDrawer.tsx` (tab key
`"backlog"`). Calls `planningApi.missions(yearId)` and renders a filtered list.

There is **no dedicated Mission Backlog view** in TMS or PW. The backlog is accessible
only via the bottom drawer of the PW planning canvas. Section 35–40 of the brief
addresses cross-surface Backlog/Activities/Facilitators alignment.

---

## 10. Two "template" concepts — potential confusion

At HEAD there are two distinct template models:

| Name | Table | Purpose |
|---|---|---|
| `TimingTemplate` | `timing_templates` | Evening **time structure** — ordered blocks with durations, block types, instructional period flags |
| `ParadeNightTemplate` | `parade_night_templates` | Session **content intent** — curriculum, facilitator, room planning intent for a reusable parade night pattern |

These are separate concepts. The brief (Sections 19–20) adds PW display of `TimingTemplate`
structure. Do not conflate the two when implementing that feature.

---

## 11. Terminology divergence — current state

| Current term used | Correct term (per brief §9) | Notes |
|---|---|---|
| "Session Structure" | Parade Night Structure | TMS settings label |
| "Default Training Periods" | (merge into Parade Night Structure) | Separate settings card at HEAD |
| "Timing Template" | Timing Template | Correct — keep |
| "Training Period" | Training Period = WHEN training can occur | Backend model name correct; UI sometimes conflates with Session |
| "Session" | Session = WHAT training occurs | Correct in backend; UI inconsistent |

---

## 12. Key API endpoints (relevant to integration program)

| Method | Path | Owner | Notes |
|---|---|---|---|
| GET | `/api/setup/getting-started` | TMS | Returns checklist steps including `cadets_added` |
| GET/POST | `/api/training-years` | TMS | Training year management |
| GET/POST | `/api/training-classes` | TMS | Class management |
| GET | `/api/curriculum-phases` | TMS/PW | Stages (ORI/INI/JNR/INT/SNR) |
| GET/POST | `/api/timing-templates` | TMS | Evening structure templates |
| GET/POST | `/api/parade-nights` | TMS/PW | Parade night records |
| GET/POST | `/api/sessions` | TMS/PW | Session scheduling |
| POST | `/api/planning/years/{id}/run-checks` | TMS | Manual planning checks trigger |
| GET | `/api/planning/years/{id}/decision-guide` | TMS | Boolean planning questions |
| GET | `/api/training-areas` | TMS/PW | Resources (capabilities NOT in PW types) |
| GET | `/api/planning/years/{id}/missions` | PW | Mission backlog |
| GET | `/api/program-promotion/requests` | TMS | Scope-filtered at 6d45e22 |

---

## 13. Known structural gaps (summary)

| Gap | Affected surface | Brief section |
|---|---|---|
| `cadets_added` blocks Getting Started unnecessarily | TMS | §7 |
| "Session Structure" / "Default Training Periods" / "Timing Templates" = three cards | TMS settings | §8–12 |
| Training Year + Training Class not passed seamlessly to PW | Context handoff | §13–14 |
| `TrainingClass.training_stage_id` nullable — no enforcement | Backend | §15–16 |
| `CustomTrainingPhase` model is minimal; naming ambiguous | Backend/TMS | §17–18 |
| PW does not display `TimingTemplate` structure | PW | §19–20 |
| `TrainingArea.capabilities` not surfaced in PW | PW | §21–25 |
| Planning Checks manual, boolean, TMS-only | TMS | §26–34 |
| Mission Backlog only in PW bottom drawer | PW | §35–40 |
| Context handoff does not include squadron (token-derived only) | Both | §42 |
| PW has ~15 routes duplicating TMS pages | PW | §43 |

---

*This document was machine-generated from HEAD state 6d45e22 on 2026-08-28.
Update it whenever a section of the integration brief is completed.*
