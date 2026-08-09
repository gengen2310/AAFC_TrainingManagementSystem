# Canonical data map

Status: initial pass, 2026-08-09. Per §8/§9 — for every entity shared between
Main TMS and Planning Workspace, document the canonical model and confirm
both interfaces read/write the same UUID, not a shadow copy. Format follows
§2's required per-entity fields.

| Concept | Canonical model | Owning scope | Main TMS API | Planning Workspace API | Shared UUID confirmed? |
|---|---|---|---|---|---|
| Parade Night | `ParadeNight` (`training.py`) | Squadron | `POST/GET/PATCH /api/parade-nights` | `GET /api/planning/years/{id}/parade-dates` via `ParadeDate` join | **Yes, with a caveat**: `ParadeDate` is a separate table joined by `planning_year_id`+date, not the same row as `ParadeNight`. REM-129 (this program's predecessor phase) fixed `POST /api/parade-nights` to also create the matching `ParadeDate` row — before that fix, a plain-created ParadeNight had no PW-visible counterpart at all. The two tables share `parade_night_id` as the link, not a single canonical row — worth a follow-up question of whether this two-table design is the right long-term shape or should be consolidated (not decided this pass). |
| Session | `Session` (`training.py`) | Squadron, via `parade_night_id` | `training.py` session endpoints | Read via Parade Night/ParadeDate join | Yes — one table, no shadow. |
| Facilitator | `Facilitator` (`training.py`) | Squadron | `/api/facilitators` | `/api/planning/facilitators` (separate read endpoint, same table) | Yes, but the two READ endpoints have independently-implemented scoping logic (`planning.py`'s own ad hoc filter vs `training.py`'s `_view_squadron_id()` pattern) — REM-130 found and fixed one instance of this divergence (missing `sqn_general` branch). The underlying *data* is one canonical table; the *access-control logic* is duplicated across two code paths, which is itself a latent-defect risk even when both happen to agree today. Flagged as a hygiene item, not re-fixed this pass. |
| Training Area | `TrainingArea` (`training.py`) | Squadron | `/api/training-areas` | `/api/planning/locations` | Yes — confirmed in an earlier pass this program via a passing regression test proving a PW-created room attaches correctly to a session. A dead `PlanningLocation`/`ScheduledSession` pair exists in `planning.py` with zero live call sites — vestigial, not a second data path. Deletion is a cheap hygiene item, not urgent (no user-visible effect). |
| Equipment | `Equipment` (`training.py`) | Squadron | `training.py` equipment endpoints | Not confirmed this pass whether PW has an equipment read path — **needs verification** |
| Holiday | `HolidayPeriod` (`planning.py`) | Squadron, via `planning_year_id` | Read via `/api/planning/years/{id}/holidays`, same table used by both interfaces' Activities pages | Same | Yes — single table, confirmed via this program's own REM-131 work (both frontends' Activities pages against the identical live rows). |
| Activity | `Activity` (`training.py`) | National/Wing/Squadron via `owning_level` | `training.py` activity endpoints | Merged with `CeaActivity` at read time via `source` tagging (per earlier program research) | Believed yes, not re-verified this pass |
| Training Year | `PlanningYear` (`planning.py`) | Squadron (`unit_id`) or Wing | `/api/planning/years` | Same | Yes — one table. |
| Subject Area | `SubjectAreaTag` (`training.py`) | National/Wing/Squadron scoped | `/api/subject-area-tags` | Consumed via Facilitator records | Yes, but `Facilitator.subject_areas` is a **denormalized string list**, not a real FK to `SubjectAreaTag` rows — this was the direct root cause of REM-128 (a deleted/archived tag catalogue entry does not remove the name from a facilitator's own list). Still true; not fixed this pass, only worked around at the test-hygiene level in REM-128/REM-131. |
| Training Stage | `CurriculumPhase` (`training.py`) | National/Wing/Squadron scoped | via Curriculum endpoints | via Curriculum endpoints | Yes — single table, effectively already satisfies addendum §32.1. |
| **Training Class** | **Does not exist yet** | — | — | — | **N/A — see `parallel-class-impact-analysis.md`. This is the single largest confirmed data-model gap in this document.** |

## Not yet mapped this pass (needs a follow-up entry)

Notices, Reference Types beyond Subject Area/Facilitator Type (e.g. Equipment
categories if any), Cadet records, Account/Organisation profiles. Listed here
so they are not silently dropped from the program's scope — tracked as
follow-up rows, not fabricated in this pass without direct verification.
