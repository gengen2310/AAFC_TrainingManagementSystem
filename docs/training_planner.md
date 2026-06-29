# Training Planner — Module Reference

## Purpose

The Training Planner provides a curriculum-centric view of the planning workflow. It shows all curriculum items in scope for the unit, with their scheduling status for a selected planning year, and allows administrators to assign each mission to a specific parade night, session slot, cadet group, and facilitator.

---

## Navigation

From the left sidebar: **Training Planner → Training Planner**

---

## Concepts

| Term | Meaning |
|---|---|
| **Mission** | A curriculum item (module) to be delivered during a parade night |
| **Part** | One of multiple delivery sessions for a multi-session module |
| **Planning Year** | A named calendar year with parade dates, holidays, and activities |
| **Parade Date** | A specific night within the planning year, linked to a real ParadeNight record |
| **Session Slot** | Period 1, 2, or 3 within a parade night |
| **Cadet Group** | One of: orientation, initial, junior, intermediate, senior |

---

## Using the Training Planner

### 1. Select a Planning Year

Choose a planning year from the dropdown at the top. The table populates with all curriculum items visible to your scope.

### 2. Apply Filters

| Filter | Effect |
|---|---|
| Cadet Level | Restrict to curriculum phases (Orientation, Initial, etc.) |
| Status | Show only Scheduled or Unscheduled items |
| Search | Filter by module code or title fragment |

### 3. Assign a Mission

Click **Assign** on any row. The assignment modal requires:
- **Parade Night** — one of the active parade dates for this year
- **Session** — Period 1, 2, or 3
- **Cadet Group** — which group receives this session
- **Part Number** — for multi-part modules only
- **Facilitator** — optional; can be set later from the Parade Night Program

Assignments create real `Session` records linked to the parade night. They appear immediately in the Parade Night Program grid and in the Weekly Program output.

### 4. Instructor Suitability

The **Suitability** column shows the recommended instructor type (Staff / Senior Cadet OR Staff / etc.). This is read-only and reflects the national curriculum specification.

---

## Data Model

Assignments are stored as `Session` records in the `sessions` table. The Training Planner is a view over these records — it does not use a separate parallel table.

Key relationships:
- `Session.curriculum_item_id` → `CurriculumItem.id`
- `Session.parade_night_id` → `ParadeNight.id`
- `ParadeNight.date` determines which planning year the session belongs to

---

## Access Control

| Role | Can view missions | Can assign |
|---|---|---|
| `sqn_admin` | Own squadron scope | Yes |
| `sqn_general` | Own squadron scope | No |
| `wing_admin` | Own wing scope | Yes (within wing) |
| `wing_viewer` | Own wing scope | No |
| `national_admin` | All | Yes |
| `national_viewer` | All | No |
| `auditor` | All | No |

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/planning/years/{year_id}/missions` | List missions with scheduling status |
| `POST` | `/api/planning/years/{year_id}/assign-mission` | Create a session assignment |
| `DELETE` | `/api/planning/sessions/{session_id}` | Remove an assignment |

### Query Parameters for GET /missions

| Parameter | Values | Effect |
|---|---|---|
| `phase` | e.g. `A. Orientation` | Filter by curriculum phase |
| `element` | e.g. `Drill` | Filter by subject area |
| `term` | `T1`–`T4` | Filter by WA school term |
| `status` | `scheduled` / `unscheduled` | Filter by assignment status |
| `search` | text | Partial match on code or title |
