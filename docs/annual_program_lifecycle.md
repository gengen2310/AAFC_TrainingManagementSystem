# Annual Program — Lifecycle Reference

## Purpose

The Annual Program is the calendar backbone of the Training Planner. It defines when parade nights occur, which periods are excluded due to school holidays or public holidays, and which key activities fall within the year.

---

## Lifecycle

```
Create Planning Year
  → Generate/Add Parade Dates
    → Add Holidays (or use seeded WA defaults)
      → Add Anchor Events (activities)
        → Assign Missions via Training Planner
          → Publish Parade Nights
            → Year Rollover (→ next year)
```

---

## Planning Year

A `PlanningYear` record scopes all parade dates, holidays, and activities for a specific calendar year and unit.

- Squadron admins create and manage years for their own unit
- Wing admins create years at wing level (shared across units)
- Multiple active years can coexist (e.g. 2026 and 2027 for forward planning)

---

## Parade Dates

Each `ParadeDate` record represents a specific night in the planning year:

| Field | Description |
|---|---|
| `parade_date` | ISO date (YYYY-MM-DD) |
| `parade_type` | standard / special / cancelled |
| `term` | WA school term label (T1–T4) |
| `week_number` | Sequential parade number within the year |
| `parade_night_id` | Links to the operational `ParadeNight` record |
| `cancellation_reason` | Populated when type = cancelled |

**Auto-Generate** creates parade dates for a selected weekday between two dates, automatically skipping any existing holiday periods that have `affects_parade = True`.

---

## Holiday Periods

`HolidayPeriod` records define non-parade windows. Types:

| `holiday_type` | Meaning |
|---|---|
| `school_holiday` | WA school term holidays |
| `public_holiday` | State or national public holiday |
| `exam_period` | Senior cadet exam period (reduced attendance expected) |
| `stand_down` | Directed stand-down (no parade) |
| `no_parade` | Admin cancellation |
| `reduced_attendance` | Noting only — parade continues |

### Seeded WA 2026 Holidays

On DB reset, the following WA 2026 periods are seeded for the 703 SQN 2026 planning year:

| Name | Dates | Type |
|---|---|---|
| Labour Day 2026 | 2026-03-02 | public_holiday |
| Good Friday 2026 | 2026-04-03 | public_holiday |
| Term 1 School Holidays | 2026-04-04 – 2026-04-19 | school_holiday |
| Anzac Day | 2026-04-25 | public_holiday |
| WA Day 2026 | 2026-06-01 | public_holiday |
| Term 2 School Holidays | 2026-07-04 – 2026-07-19 | school_holiday |
| Term 3 School Holidays | 2026-09-26 – 2026-10-11 | school_holiday |
| King's Official Birthday 2026 | 2026-09-28 | public_holiday |
| Term 4 / Summer Holidays | 2026-12-18 – 2027-01-31 | school_holiday |

---

## Anchor Events / Activities

`AnchorEvent` records are activities that affect training planning. V14 extended fields:

| Field | V14 Purpose |
|---|---|
| `importance_level` | 1=Must Attend, 2=Key Event, 3=Weekly, 4=Optional, 5=Noting |
| `cea_activity_id` | CEA system import reference |
| `nomination_end_date` | Nomination closing date (from CEA) |
| `audience_staff_only` | Staff-only event flag |
| `audience_proficient` | Proficient cadets (LCDT+) flag |
| `audience_first_years` | First-year cadets flag |
| `unit_name` | Unit name from CEA import |

---

## Term Blocks in Annual Program View

The Annual Program page renders the year as 4 term blocks using WA default term boundaries:

| Term | Default Range |
|---|---|
| T1 | Late Jan – mid-Apr |
| T2 | Late Apr – late Jun |
| T3 | mid-Jul – late Sep |
| T4 | Early Oct – mid-Dec |

Each term block shows: parade count, holiday periods, and activities in that window.

---

## API Endpoint

```
GET /api/planning/years/{year_id}/annual-program
```

Returns term blocks with parade dates, holidays, activities, and fill statistics.
