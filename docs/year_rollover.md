# Year Rollover — Reference

## Purpose

Year rollover creates the next planning year by copying the structure (holidays, parade date pattern) from the current year, adjusted for the new calendar year.

---

## Rollover Procedure

1. Navigate to the **Planning Workspace**, select the current planning year
2. Call `POST /api/planning/years/{year_id}/rollover` with optional parameters
3. Review the new planning year — verify parade dates don't fall in the wrong weeks
4. Add or adjust holiday periods if the new year has different public holiday dates
5. Begin assigning curriculum items to parade nights for the new year

---

## What is Copied

| Item | Copied | Notes |
|---|---|---|
| Parade dates | Yes | Same weekday, dates shifted by year delta |
| Holiday periods | Yes (if `copy_holidays=True`) | Dates shifted by year delta |
| Anchor events | No | Must be re-added manually or via CEA import |
| Mission assignments (sessions) | Noted | Incomplete sessions from prior year are counted but not auto-assigned |
| Facilitators / rooms | N/A | Already linked to the squadron, not copied |
| Timing template | N/A | Already linked to the squadron |

---

## Incomplete Sessions

When `carry_incomplete_sessions=True` (default), the rollover endpoint counts sessions from the source year that have status `planned` or `not_delivered`. These are returned in `incomplete_sessions_noted` for the planner to review.

These sessions are **not** automatically assigned to the new year — review them in Parade Nights and re-assign curriculum items as needed.

---

## Duplicate Prevention

If a planning year with the same `unit_id` and `target_year` already exists, the endpoint returns HTTP 409 with `error: planning_year_already_exists`.

---

## API

```
POST /api/planning/years/{year_id}/rollover
```

**Body:**

```json
{
  "target_year": 2027,
  "name": "703 SQN Training Year 2027",
  "copy_holidays": true,
  "carry_incomplete_sessions": true
}
```

**Response:**

```json
{
  "ok": true,
  "new_planning_year_id": "...",
  "year": 2027,
  "name": "703 SQN Training Year 2027",
  "holidays_copied": 9,
  "parade_dates_copied": 32,
  "incomplete_sessions_noted": 3
}
```

---

## Access Control

Only `sqn_admin`, `wing_admin`, `national_admin`, and `system_admin` can perform a rollover.
