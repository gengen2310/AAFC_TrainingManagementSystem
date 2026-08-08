# Duplicate-Concept Review

Program: Final Remediation, Product Hardening and Public-Release Program, Section 8.
Status: **complete for the concepts named in the governing instruction; broader findings inherited
from and cross-referenced against `docs/qualification/03_data_integrity_review.md` (Phase A, Data
Integrity Auditor) rather than re-derived from scratch.**

This document classifies every candidate duplicate concept as either **(A) same concept, duplicated
historically — one now canonical** or **(B) genuinely different concepts with a similar name**, per
the governing instruction's explicit requirement not to merge automatically and to document evidence.
**No schema change, merge, or delete is proposed or performed in this document.**

---

## Headline: TrainingArea vs PlanningLocation — **(A) same concept, duplicated historically**

**Verdict: fully migrated. `TrainingArea` is the one live, canonical model. `PlanningLocation` (and
its sibling `ScheduledSession`) are 100% dead code as of this program — confirmed fresh, not assumed.**

Evidence, verified directly against current source (not inherited from any prior claim):

```
grep -rn "PlanningLocation\b" backend/app/routers/*.py backend/app/services*.py
grep -rn "ScheduledSession\b" backend/app/routers/*.py backend/app/services*.py
```

Every remaining match is a **comment**, not a live reference. No `PlanningLocation(...)` or
`ScheduledSession(...)` constructor call exists anywhere in the codebase — confirmed by direct grep,
not inferred. `create_location`/`update_location` (the Planning Workspace room-management endpoints)
read and write `TrainingArea` exclusively.

This is stronger than the finding in `docs/qualification/03_data_integrity_review.md` §3, which
(written 2026-08-08, before this program) found one remaining harmless legacy read
(`_session_out()`, reading `PlanningLocation` only for pre-existing legacy `ScheduledSession` rows).
That function was removed entirely by a subsequent commit (`0170714`, QUAL-002, "remove dead
`_session_out()`/`ScheduledSession`+`PlanningLocation` router code — zero live callers after
QUAL-001"). **As of this program, both tables have zero read and zero write call sites anywhere in
the application.**

The two P1 defects the same review found — `get_command_centre` and `add_facilitator_leave` silently
reading the never-populated `scheduled_sessions` table, producing wrong dashboard/safety data — were
fixed as `QUAL-001` (commit `e747d3b`), migrated to the same `ParadeDate → ParadeNight →
TrainingSession` join `facilitator_workload` already used as the proven template. Deployed to
production; live-verified.

**What remains, unresolved by explicit user decision, not an oversight:** the tables themselves
(`scheduled_sessions`, `planning_locations`) and their now-fully-inert cross-FKs
(`planning_conflicts.scheduled_session_id`, `scheduled_sessions.location_id`) still exist in the
schema. Dropping them was explicitly offered to the user during the qualification program and
**declined** ("leave them in place for now" — recorded in `docs/qualification/decision_log.md`).
This document does not re-open that decision; per capability-preservation §1, removal requires fresh
explicit authorization, which has not been given.

---

## Other candidate duplicates (inherited from `03_data_integrity_review.md` §2a, status updated)

| Pair | Classification | Status this program |
|---|---|---|
| `sessions` vs `scheduled_sessions` | (A) same concept, one live | Unchanged — `sessions` (TrainingSession) canonical, `scheduled_sessions` fully dead (see above) |
| `training_areas` vs `planning_locations` | (A) same concept, one live | Unchanged, strengthened (see above) |
| `parade_nights` vs `parade_dates` | Same real-world concept, two tables kept by design | **Needs human judgment** — not re-litigated this pass; delivery-record vs planning-calendar-slot distinction appears intentional |
| `curriculum_items` vs `program_items` | (B), likely same concept, two implementations | **Needs human judgment** — `program_items` adds package/deployment/promotion fields `curriculum_items` doesn't have; not safe to merge on naming alone |
| `activities` vs `cea_activities` | (B), different-but-overlapping | **Needs human judgment** — Main-TMS training events vs CEA-import overlay, linked only by text (`cea_seq_nr`) |
| `phases` vs `curriculum_phases` vs `custom_phases` | Likely same concept, three tables (global/scoped/per-squadron catalogues) | **Needs human judgment** — largest fragmentation found; a real product decision, not a mechanical merge |
| `planning_conflicts` vs `source_conflicts` vs `/resources/clashes` | (B) different concepts, similar name | Confirmed correct as-is — scheduling conflict vs import field-disagreement vs computed room clash are genuinely distinct |
| `subject_area_tags` vs `facilitator_type_tags` | (B) different concepts, identical shape by design | Confirmed correct as-is — deliberately parallel reference-tag tables |
| `promotion_requests` vs `cadets.promotion_interest` | (B) different concepts, colliding name | Confirmed correct as-is — program-content promotion vs cadet-rank interest are different domains |

None of the "needs human judgment" items were merged, altered, or auto-resolved in this pass — per
the governing instruction's own rule, a naming resemblance is not sufficient grounds to act.

---

*No application code, migration, or data was modified in the preparation of this document.*
