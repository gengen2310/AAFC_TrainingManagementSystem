# AAFC TMS — TRGO Planning Module

> V11 introduced the module structure; V12 corrected the integration so all pages use real training data.

## V12 Integration Architecture (what changed)

**V11 problem:** The planning module created a parallel data chain (`PlanningYear` → `ParadeDate` → `ScheduledSession`) isolated from the real training records (`parade_nights` → `sessions`). Pages appeared but were empty or disconnected.

**V12 fix:** The planning module is now wired directly to the real training data chain:

```
TimingTemplate  ──────────────────────────────────────────┐
                                                           ↓
parade_nights ─── sessions (real, with cadet_group field) ─→ Weekly Program
     ↑                                                          Long Range View
     │                                                          Term Planner
parade_dates.parade_night_id ─────────────────────────────→ Night Builder
     ↑
PlanningYear (planning year still owns the date list)
```

**Key integration points:**
1. `Session.cadet_group` — new field enables per-group rows in Night Builder grid
2. `ParadeDate.parade_night_id` — new FK links each planning date to a real `ParadeNight`
3. `_find_or_create_parade_night()` — helper called on every parade date add/generate; finds or creates the real `ParadeNight` within the current transaction
4. Planning builder/sessions/weekly/long-range/term-planner all read/write real `Session` records via `parade_night_id`
5. `GET /api/parade-nights/{id}/builder` — new endpoint returns Night Builder grid data directly from a real parade night (no planning year needed)

**Frontend navigation fix:**
- After `POST /api/parade-nights`, the response includes `parade_night_id` and the frontend navigates directly to Night Builder (`loadBuilderFromPn(parade_night_id)`) instead of showing a static alert.

---

## Overview

The TRGO Planning Module implements the Training, Recruiting and General Orders (TRGO) annual planning cycle as a structured in-app workflow. It provides:

- **Year Map** — set up the planning year, parade dates, and holiday periods
- **Anchor Events** — identify fixed events that shape the training calendar
- **Term Planner** — view the year in term blocks with session fill statistics
- **Parade Night Builder** — assign instructional sessions to cadet groups for each parade night
- **Weekly Program** — review the final published program with timing labels
- **Long Range View** — look ahead 4–20 weeks to spot gaps and conflicts
- **Rooms & Staff** — manage planning locations and view facilitator availability
- **Planning Checks** — run the decision guide and resolve all critical conflicts before publishing

---

## Access Control

| Role | Read | Write (own) | Write (all in scope) |
|------|------|-------------|----------------------|
| `sqn_admin` | own unit | own unit | — |
| `wing_admin` | own wing | own wing (years, anchors, locations) | view all subordinate units |
| `national_admin` / `system_admin` | all | all | all |
| `wing_viewer` / `national_viewer` | scope-limited | — | — |
| `auditor` | all (read-only) | — | — |
| `sqn_general` | — | — | — |

All write operations are audited in `audit_log` with actor, action, and object.

---

## Data Models

### PlanningYear
Represents one annual planning cycle for a unit or wing.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | Primary key |
| `unit_id` | FK → squadrons | Null for wing-level years |
| `wing_id` | String(36) | Wing scope |
| `year` | Integer | e.g. 2026 |
| `name` | String(120) | Display name |
| `active_status` | Boolean | |

### ParadeDate
A single parade night within a planning year.

| Field | Type | Notes |
|-------|------|-------|
| `parade_date` | String(10) | ISO date YYYY-MM-DD |
| `parade_type` | String(30) | standard / special / cancelled |
| `is_active` | Boolean | |

### HolidayPeriod
A holiday or stand-down period that may overlap parade dates.

| Field | Type | Notes |
|-------|------|-------|
| `name` | String(120) | e.g. "Easter Break" |
| `start_date` / `end_date` | String(10) | ISO dates |
| `affects_parade` | Boolean | Used by conflict engine |
| `jurisdiction` | String(40) | national / state / local |

### AnchorEvent
A fixed event (inspection, fieldcraft weekend, dining-in, wing day) around which training is planned.

| Field | Type | Notes |
|-------|------|-------|
| `event_name` | String(200) | |
| `event_type` | String(40) | ceremonial / fieldcraft / inspection / … |
| `importance` | String(20) | must_attend / key_event / optional |
| `start_date` | String(10) | |
| `audience_*` | Boolean×5 | Per cadet group (orientation…senior) |
| `planning_impact` | Text | Free-text |
| `readiness_requirements` | Text | What cadets need to know first |

### AnchorPrepRule
Seeded rule set for prep-lesson suggestions. Maps event_type → suggested subject, N weeks before.

### AnchorPrepPlan
A preparation lesson linked to an anchor event, pointing to a specific parade date and session slot.

### ScheduledSession
One instructional slot in the parade night grid (cadet_group × session_number).

| Field | Type | Notes |
|-------|------|-------|
| `cadet_group` | String(30) | orientation / initial / junior / intermediate / senior |
| `session_number` | Integer | 1-based |
| `curriculum_id` | FK → curriculum_items | Optional |
| `activity_title` | String(200) | Override title |
| `facilitator_id` | FK → facilitators | Optional |
| `location_id` | FK → planning_locations | Optional |
| `is_combined` | Boolean | Combined-group session |
| `override_conflict` | Boolean | Conflict accepted by CO |
| `override_reason` | Text | Required if override_conflict=True |
| `status` | String(20) | draft / confirmed / published |

### PlanningLocation
A room or outdoor area available for scheduling.

### PlanningConflict
A conflict detected by the conflict engine, with optional CO override.

| Field | Type | Notes |
|-------|------|-------|
| `conflict_type` | String(60) | facilitator_double_booked / room_double_booked / empty_session / holiday_conflict / … |
| `severity` | String(10) | info / warning / critical |
| `is_resolved` | Boolean | |
| `override_reason` | Text | Required for CO override |

---

## API Endpoints

All endpoints require a valid JWT. Base path: `/api/planning/`

### Planning Years
| Method | Path | Description |
|--------|------|-------------|
| GET | `/years` | List years in scope |
| POST | `/years` | Create planning year |
| GET | `/years/{id}` | Get single year |
| PATCH | `/years/{id}` | Update year |

### Parade Dates
| Method | Path | Description |
|--------|------|-------------|
| GET | `/years/{id}/parade-dates` | List dates with holiday flags |
| POST | `/years/{id}/parade-dates` | Add single date |
| POST | `/years/{id}/generate-parade-dates` | Auto-generate by weekday |
| DELETE | `/parade-dates/{id}` | Remove date |

### Holidays
| Method | Path | Description |
|--------|------|-------------|
| GET | `/years/{id}/holidays` | List holidays |
| POST | `/years/{id}/holidays` | Add holiday period |
| DELETE | `/holidays/{id}` | Remove |

### Anchor Events
| Method | Path | Description |
|--------|------|-------------|
| GET | `/years/{id}/anchors` | List anchors (filterable) |
| POST | `/years/{id}/anchors` | Create anchor |
| PATCH | `/anchors/{id}` | Update anchor |
| DELETE | `/anchors/{id}` | Archive anchor |
| GET | `/anchors/{id}/prep-suggestions` | Rule-based prep suggestions |

### Term Planner
| Method | Path | Description |
|--------|------|-------------|
| GET | `/years/{id}/term-planner` | Full year or single term overview |

### Parade Night Builder
| Method | Path | Description |
|--------|------|-------------|
| GET | `/parade-dates/{id}/builder` | Grid + conflicts for one night |

### Scheduled Sessions
| Method | Path | Description |
|--------|------|-------------|
| POST | `/parade-dates/{id}/sessions` | Add session to grid cell |
| PATCH | `/sessions/{id}` | Update session |
| DELETE | `/sessions/{id}` | Soft-delete session |

### Weekly Program
| Method | Path | Description |
|--------|------|-------------|
| GET | `/parade-dates/{id}/weekly-program` | Published program with timing blocks |

### Long Range View
| Method | Path | Description |
|--------|------|-------------|
| GET | `/years/{id}/long-range` | Forward view (`?weeks=8&from_date=YYYY-MM-DD`) |

### Locations
| Method | Path | Description |
|--------|------|-------------|
| GET | `/locations` | List active locations in scope |
| POST | `/locations` | Create location |
| PATCH | `/locations/{id}` | Update location |

### Facilitators (planning view)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/facilitators` | List with subject_areas and session limits |

### Conflict Detection
| Method | Path | Description |
|--------|------|-------------|
| GET | `/years/{id}/conflicts` | Unresolved conflicts |
| POST | `/years/{id}/run-checks` | Re-run all checks for the year |
| POST | `/conflicts/{id}/override` | Override with reason (audited) |

### Decision Guide
| Method | Path | Description |
|--------|------|-------------|
| GET | `/years/{id}/decision-guide` | Rule checklist (pass/fail + action) |

### Prep Rules
| Method | Path | Description |
|--------|------|-------------|
| GET | `/prep-rules` | Seeded rules (filterable by event_type) |

---

## Conflict Engine

The engine runs automatically after any session create/update, and can be triggered manually via `POST /years/{id}/run-checks`. It detects:

| Type | Severity | Trigger |
|------|----------|---------|
| `facilitator_double_booked` | critical | Same facilitator in 2+ groups, same session number |
| `room_double_booked` | critical | Same location in 2+ groups, same session number |
| `empty_session` | warning | A cadet group has no session scheduled for the night |
| `holiday_conflict` | warning | Parade date falls within an `affects_parade=True` holiday period |

Sessions with `override_conflict=True` are excluded from conflict re-detection. Override requires a non-empty `override_reason`.

---

## Decision Guide Rules

| # | Question | Trigger |
|---|----------|---------|
| 1 | Must Attend / Key Event in next 3 weeks? | Anchor events in window |
| 3 | Cadet group with no mission assigned? | Missing cadet group for date_id |
| 7 | Unresolved critical conflicts? | Any critical conflict unresolved |
| 10 | Night ready to publish? | No critical conflicts → true |

---

## Security Invariants

- No access codes, hashes, or seeded credentials appear in frontend JavaScript.
- All write endpoints require sqn_admin or higher role.
- sqn_admin is scoped to own unit only; wing_admin to own wing.
- All mutations generate an entry in `audit_log` (actor, action, object_id, reason).
- `override_reason` is required (validated server-side) before accepting a conflict override.
- No drag-and-drop; no external libraries loaded for planning UI.
