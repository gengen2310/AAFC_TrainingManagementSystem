# AAFC TMS — Canonical Data Model Decision

**Decision recorded:** 2026-08-12
**Gap register:** Gap #3 (TrainingArea vs PlanningLocation overlap)

---

## Decision

**`training_areas` is the canonical model for physical training locations.**

`PlanningLocation` (table: `planning_locations`) is deprecated and will be retired
in a future migration. It is NOT used by any active business logic — all reads and
writes route through `TrainingArea`.

---

## Evidence

`backend/app/routers/planning.py` lines 30–36 (as of commit `cf9a377`):

```python
# ScheduledSession and PlanningLocation models are intentionally NOT imported here:
# both are fully superseded (TrainingSession/TrainingArea are canonical -- see
# planning.py:312-319 for the room-ID resolver that transparently bridges the old
# planning_locations table while the schema migration to fully drop it is pending).
```

`planning.py:312-319` — the Rooms tab of the Planning Workspace reads and writes
`training_areas`, not `planning_locations`. A legacy location_id that resolves to
an old `PlanningLocation` row is handled by a fallback lookup that presents an
identical JSON shape, preserving any existing room assignments without requiring a
data migration.

`planning.py:1600` — the ScheduledSession room resolver checks both tables in order
(TrainingArea first, then PlanningLocation as fallback), so no historical session
assignments break.

---

## Migration Plan

**Phase 1 (CURRENT STATE — complete):**
All new room assignments use `training_areas`. The Rooms tab creates, edits, and
deletes `TrainingArea` rows. The `planning_locations` table still exists but
receives no new writes from any frontend.

**Phase 2 (Level B — pending a quiet release window):**
- Migrate any remaining `planning_locations` rows that have `scheduled_session`
  references into `training_areas` (a one-time data migration)
- Remove the fallback resolver from `planning.py:1600`
- Drop the `planning_locations` table and `PlanningLocation` model

**Phase 2 is NOT required for Level A (7WG V1 operations)** because:
- No active user-visible workflow writes to `planning_locations`
- The fallback resolver ensures historical data remains readable
- The table is inert — it causes no data divergence in practice

**Phase 2 requires:**
1. A database backup immediately before migration
2. A staging run of the migration script (with output review)
3. Explicit authorisation to drop the table (capability-preservation.md §1)

---

## What Is NOT Duplicated

The following were identified as potential overlaps but are NOT duplicates:

| Concern | Reality |
|---|---|
| Facilitator records | One canonical `Facilitator` table; `PlanningFacilitatorLeave` is a supplement (additional data on the same entity), not a separate duplicate |
| Activity types | Hierarchical ownership (National → Wing → Squadron); not duplicates, just scoped variants |
| Parade dates vs parade nights | Separate linked concepts (a `ParadeDate` in a planning year is linked to a `ParadeNight` in operations); not duplicate data |
| Training areas vs resources | `Equipment` and `TrainingArea` are correctly separate models (equipment is consumable/movable; area is a fixed location) |

---

## Residual Risk (Low)

If a Wing that used the Planning Workspace before the Rooms tab switch (pre-commit
`cf9a377`) has historical sessions with `room_id` pointing at `PlanningLocation`
rows, those sessions will continue to render the room correctly (via the fallback
resolver) but the room will not appear in the Rooms tab's editable list (which only
shows `TrainingArea` rows). The affected operator would need to recreate the room
in the Rooms tab and then update the session's room assignment. **For 703 SQN (the
beta squadron), this risk is zero** — all room assignments in the demo data use
`TrainingArea` rows.
