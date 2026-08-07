# 03 — Data Integrity & Domain Forensic Audit

Program: AAFC TMS Whole-System Adversarial Qualification (Phase A — discover and map, no
application changes). Role: Data Integrity Auditor. Status: **read-only archaeology complete for
this pass.**

Ground truth used: `docs/qualification/capability_manifest_before.json` (58 live SQLAlchemy tables,
introspected from `Base.metadata` at commit `76d6723`), the six model files under
`backend/app/models/`, and `backend/app/routers/planning.py` for call-site verification. Companion
data file: `docs/qualification/data_relationship_inventory.csv` (one row per mission entity).

This report **identifies and documents only**. Per `.claude/rules/capability-preservation.md` §4, no
merge, dedup, delete, or schema change is proposed as an action here — every candidate duplication is
classified SAME CONCEPT vs DIFFERENT CONCEPT WITH SIMILAR NAME, and anything I could not decide from
source alone is marked **needs human judgment** rather than asserted.

---

## Executive summary

The data model is materially sound and mostly single-sourced. The remediation program clearly did
real consolidation work (the Rooms merger, the facilitator absorb/merge dedup feature, the
`facilitator_workload` rewrite). The significant findings are concentrated in **three areas**:

1. **Two superseded "v14" tables still exist and are still read by live code even though nothing ever
   writes them** — `scheduled_sessions` and `planning_locations`. This is the single highest-value
   finding. The task asked me to *verify, not assume*, whether they have zero call sites. **They do
   not have zero call sites.** Writes are gone, but two live Planning-Workspace endpoints still
   *read* `scheduled_sessions`, and because the table is never populated those reads silently return
   wrong dashboard numbers. This is a genuine P1 data-correctness defect, not merely dead schema.

2. **Foreign-key enforcement is inconsistent and largely absent for tenancy columns.** `wing_id` is a
   plain unenforced `String(36)` on ~15 tables; `Session`'s curriculum/facilitator/training-area/
   squadron links are all plain strings; several columns that read like references
   (`promotion_requests.program_item_id`, `program_items.phase_id`/`source_file_id`/
   `learning_hub_resource_id`, `curriculum_items.replacement_curriculum_id`,
   `parade_dates.parade_night_id`, `parade_nights.timing_template_id`,
   `anchor_events.cea_activity_id`) carry no `ForeignKey()` at all. These are exactly where orphan
   rows accumulate silently.

3. **A handful of same-concept / different-name fragmentations** — most notably three phase/"training
   stage" tables plus free-text `phase` columns everywhere, and the parallel `curriculum_items` vs
   `program_items` and `activities` vs `cea_activities` models. These need a human product decision;
   they are **not** safe to auto-merge and I am not recommending it.

Nothing here contradicts the intentional two-frontend architecture or the Flight-is-not-tenancy rule.
The audit log's deliberate absence of FKs is correct and is explicitly **not** flagged as a defect.

Severity scale used below: **P1** = silently wrong user-visible data or real orphan pathway; **P2** =
latent integrity risk (missing constraint, no live trigger yet); **P3** = consistency/hygiene.

---

## 1. Per-entity canonical mapping

The full 25-row table (canonical table, canonical ID, natural identifier, owner scope, parent,
lifecycle states, archive behaviour, API/Main-TMS/Planning-Workspace representation, duplication
notes) is in `data_relationship_inventory.csv`. Key structural facts established there:

- **Tenancy is National → Wing → Squadron only**, confirmed in `models/organisations.py`. "Specialist
  Unit" is **not** a separate entity — it is `squadrons.unit_type` in
  `{standard_squadron, specialist_squadron, specialist_flight, support_unit}`
  (`models/organisations.py:25-39`), correctly reusing the squadron tenancy model. "Flight" is a
  sub-squadron grouping (`flights` table), correctly non-tenancy.
- **"Squadron" and "unit" are the same entity under two column names.** Organisations code says
  `squadron`; the planning module says `unit`/`unit_id` (`parade_dates.unit_id`,
  `cea_activities.unit_id`, `planning_locations.unit_id`, `scheduled_sessions.unit_id` all
  `ForeignKey("squadrons.id")`). Verified by FK target, not by name.
- **Archive behaviour is inconsistent across entities** (see §3 hygiene): most training/org entities
  use `SoftDeleteMixin` (`is_archived` + `archived_at`); reference-tag tables use `is_active` only;
  `planning_notices` and `cea_activities` have `is_archived` *without* `archived_at`; `holiday_periods`
  has no archive at all (hard delete only); `planning_years` uses `active_status` + dependency-gated
  hard delete with no `is_archived`.
- **Main-TMS vs Planning-Workspace API split**: Main TMS (connected-frontend) reads the `training`
  and `organisations` tagged endpoints (`sessions`, `parade_nights`, `training_areas`, `activities`);
  Planning Workspace reads the `planning` tagged endpoints (`parade_dates`, CEA, notices, and — post
  Rooms/session merger — the same underlying `sessions`/`training_areas` tables). The two frontends
  are two views over largely the same canonical tables, **except** where a Planning endpoint still
  reads a superseded table (§3).

---

## 2. Duplicate tables / APIs / enums, synonymous columns, text-relationships-that-should-be-FKs

### 2a. Duplicate/parallel tables (each classified)

| Pair | Classification | Evidence |
|---|---|---|
| `sessions` vs `scheduled_sessions` | **SAME CONCEPT, one live** | `scheduled_sessions` never instantiated (see §3); `sessions` is canonical. `models/training.py:79`, `models/planning.py:122`. |
| `training_areas` vs `planning_locations` | **SAME CONCEPT, one live** | Rooms merger; `planning.py:331-346` comment + `create_location` writes `TrainingArea` (`planning.py:1864`). |
| `parade_nights` vs `parade_dates` | **SAME real-world concept, two tables kept** | Delivery record vs planning-calendar slot, bridged by unenforced `parade_dates.parade_night_id` (`models/planning.py:52`). Auto-linked at `planning.py:1507-1513`. Likely intentional two-track; **needs human judgment** on whether to formalise the bridge. |
| `curriculum_items` vs `program_items` | **LIKELY SAME CONCEPT, two implementations** | Both model a lesson/mission; `program_items` (cadet-program, 35 cols) adds package/deployment/promotion. **Needs human judgment** — do not merge. |
| `activities` vs `cea_activities` | **DIFFERENT-BUT-OVERLAPPING** | Main-TMS training events vs CEA-import overlay; linked only by text (`activities.cea_seq_nr` ↔ `cea_activities.cea_activity_id`). **Needs human judgment.** |
| `phases` vs `curriculum_phases` vs `custom_phases` | **LIKELY SAME CONCEPT, three tables** | Global catalogue / scoped catalogue / per-squadron. Biggest fragmentation. **Needs human judgment.** |
| `planning_conflicts` vs `source_conflicts` vs `/resources/clashes` | **DIFFERENT CONCEPTS, similar name** | Scheduling conflict vs import field-disagreement vs computed room clash. **Do not merge.** |
| `subject_area_tags` vs `facilitator_type_tags` | **DIFFERENT CONCEPTS, identical shape** | Deliberately parallel reference-tag tables (`models/training.py:164-178`). Correct. |
| `promotion_requests` vs `cadets.promotion_interest` | **DIFFERENT CONCEPTS, colliding name** | Program-content promotion vs cadet-rank interest. See §5. |

### 2b. Synonymous columns across tables (same meaning, different name/shape)

- Squadron identity: `squadron_id` (organisations/training) ≡ `unit_id` (planning). Same FK target.
- Session number: `sessions.period_number` ≡ `scheduled_sessions.session_number` (both "which
  instructional period"). The live `create_session` maps PW `session_number` → `period_number`
  (`planning.py:1534`).
- Location/room: `sessions.training_area_id` ≡ `scheduled_sessions.location_id` (different FK targets:
  `training_areas.id` vs the dead `planning_locations.id`).
- Curriculum link: `sessions.curriculum_item_id` ≡ `scheduled_sessions.curriculum_id`.
- Phase: `curriculum_items.phase`, `cadets.phase`, `learning_hub_resources.phase`,
  `sessions.phase_at_time`, `program_items.phase_name_at_time` — five free-text homes for one concept.
- Subject area: `subject_area_tags.normalised_name`, `facilitators.subject_areas` (JSON list),
  `anchor_prep_rules.subject_area` (free text) — three homes.

### 2c. Text relationships that should (arguably) be real FKs — **needs human judgment on each**

- `parade_dates.parade_night_id` → `parade_nights.id` (comment even says "FK →" but it is not one).
- `parade_nights.timing_template_id` → `timing_templates.id` (plain String; note the *override* table
  `parade_night_timing_overrides.timing_template_id` **is** a real FK — inconsistent).
- `promotion_requests.program_item_id` → `program_items.id` (plain String).
- `program_items.phase_id` → a phase table (plain String, and unclear *which* phase table).
- `program_items.source_file_id` → `source_files.id`; `source_conflicts.source_file_id` →
  `source_files.id` (both plain String).
- `program_items.learning_hub_resource_id` → `learning_hub_resources.id` (plain String).
- `program_items.replacement_item_id` / `curriculum_items.replacement_curriculum_id` → self (plain
  String).
- `cadets.flight` (free text) vs `flights.id` — text label, not a link to the Flight table.
- `squadron_event_status.local_activity_id` → `activities.id` (plain String).
- `anchor_events.cea_activity_id` — **broken by type**: declared `Integer`
  (`models/planning.py:87`) while `cea_activities.id` is a UUID string. It can never join. Almost
  certainly vestigial. **Needs human judgment** (likely dead column).

---

## 3. Verification of `scheduled_sessions` and `planning_locations` (task item 3 — verified, not assumed)

I grepped `backend/app/routers/` and `backend/app/services.py` for every reference. Findings:

**Instantiation (writes): ZERO for both.**
`grep -rn "ScheduledSession(\|PlanningLocation(" app/` returns only a *comment* at
`planning.py:3758`. No `ScheduledSession(...)` or `PlanningLocation(...)` constructor call exists
anywhere. Confirmed independently: `create_session` (`POST /api/planning/parade-dates/{id}/sessions`,
`planning.py:1491-1561`) builds a **`TrainingSession`** (the canonical `sessions` table), and
`create_location`/`update_location` (`planning.py:1844-1899`) build/read **`TrainingArea`**.

**So "zero write call sites" is TRUE. But "zero call sites" is FALSE — both tables are still READ by
live code:**

`planning_locations` — one residual read:
- `planning.py:313` — `_session_out()` does `db.get(PlanningLocation, s.location_id)` when serialising
  a *legacy* `ScheduledSession`. Only reachable for pre-existing legacy rows; harmless for new data.

`scheduled_sessions` — **three live read sites, two of which produce wrong numbers:**
- `get_command_centre` (`GET /api/planning/command-centre`, `planning.py:2344-2383`): computes
  `scheduled_curriculum_ids` and `nights_missing_fac` from `ScheduledSession`. Because the table is
  never written, `scheduled_curriculum_ids` is **always empty** → **every core curriculum item is
  always reported as "unscheduled required"**, and `nights_missing_fac` is **always 0**, regardless of
  the real `sessions` data. **P1 — silently wrong command-centre output.**
- `add_facilitator_leave` (`POST /api/planning/facilitators/{fac_id}/leave`, `planning.py:3675-3690`):
  computes the "affected sessions in the leave window" from `ScheduledSession` → **always returns an
  empty `affected` list**, so the leave-vs-schedule conflict warning never fires for real sessions.
  **P1 — safety/conflict check silently no-ops.**
- `facilitator_workload` (`planning.py:3740-3789`): **already fixed** — the code comment
  (`planning.py:3756-3761`) documents that it *used* to query the never-populated `ScheduledSession`
  and "always silently returned zero workload", and was rewritten to the
  `ParadeDate → ParadeNight → TrainingSession` join. **This is the template fix**; the other two
  callers above were missed in the same migration.

Additional dead cross-links to these tables:
- `planning_conflicts.scheduled_session_id` is a real FK to `scheduled_sessions.id`
  (`models/planning.py:161`) — conflicts about a session cannot be linked to the live `sessions` data.
- `scheduled_sessions.location_id` is a real FK to `planning_locations.id` — a live FK pointing at a
  dead table.

**Conclusion:** the two tables are *superseded, not retired.* Removing them is a Phase-B/C decision
requiring the two live `scheduled_sessions` readers to be migrated first (same fix already applied to
`facilitator_workload`). I am **not** recommending dropping any table in this read-only pass.

---

## 4. Orphan-row risk: relationships not enforced at the DB level

Every `ForeignKey` in the schema is declared **without** an `ondelete=` clause, and SQLite (local/test
DB) does not enforce FKs unless `PRAGMA foreign_keys=ON`. Hard deletes are gated in application logic
(`services.fk_dependents` — the shipped dependency-gated delete pattern), so the *primary* protection
is app-level, not DB-level. Where a column isn't even a declared FK, there is **no** protection at all:

**Columns that look like references but have NO `ForeignKey()` (orphan-prone):**
- Tenancy: `wing_id` on `parade_nights`, `activities`, `cea_activities`, `cea_import_batches`,
  `anchor_events`, `curriculum_items`, `curriculum_elements`, `curriculum_phases`, `program_items`,
  `program_packages`, `program_item_deployments`, `action_items`, `exceptions`, `planning_years`,
  `subject_area_tags`, `facilitator_type_tags` — all plain `String(36)`. (Only `users.wing_id` is a
  real FK.) `squadron_id` on `sessions`, `activities`, `curriculum_items` similarly plain.
- Session links: `sessions.curriculum_item_id`, `facilitator_id`, `assistant_facilitator_id`,
  `backup_facilitator_id`, `training_area_id`, `squadron_id` — all plain String; only
  `sessions.parade_night_id` is enforced. A deleted facilitator/curriculum/room leaves dangling
  session references (partially mitigated by the `*_at_time` denormalised snapshots, which is likely
  *why* they were left unenforced — **needs human judgment**).
- Cross-model: `parade_dates.parade_night_id`, `parade_nights.timing_template_id`,
  `promotion_requests.program_item_id`, `program_items.{phase_id, source_file_id,
  learning_hub_resource_id, replacement_item_id}`, `curriculum_items.replacement_curriculum_id`,
  `squadron_event_status.local_activity_id`, `source_conflicts.source_file_id`,
  `anchor_events.cea_activity_id` (also wrong type — §2c).

**Nullable FKs with no delete behaviour (orphan-on-parent-delete):** `activity_local_hides.unit_id`,
`anchor_prep_plans.{curriculum_id, planned_parade_date_id}`, `planning_conflicts.{parade_date_id,
scheduled_session_id}`, `cea_activities.{import_batch_id, planning_year_id, unit_id}`,
`scheduled_sessions.{curriculum_id, facilitator_id, location_id}`. These are declared FKs so app-level
gating applies, but no `ON DELETE SET NULL/CASCADE` is set, so integrity depends entirely on every
delete path going through `fk_dependents`. **P2** — recommend Phase D invariant tests assert no
orphans rather than schema changes in Phase B.

**Verdict:** no evidence of *actual* orphan rows was gathered (that requires querying a real DB, which
this read-only pass must not do). The **pathways** exist and are well-defined above; confirming/denying
live orphans belongs in Phase D database-invariant tests.

---

## 5. Singleton data islands

- **SITREP** — `cadets.sitrep_part_1_status` / `sitrep_part_2_status` are two nullable `String(20)`
  columns with no table, no status-enum constant, no history, and no dedicated write endpoint. SITREP
  exists *only* on the cadet row, surfaced only through `GET /api/cadets`. If SITREP status is
  meaningful command data, it is under-modelled. **Needs human judgment** (also relevant to the
  personnel-information review, doc 13).
- **Cadet promotion** — the only representation is `cadets.promotion_interest` (free-text
  `String(20)`). There is **no** cadet promotion-request/approval workflow. The similarly-named
  `promotion_requests` table is about **program-content** promotion between org scopes, not cadets
  (`/api/program-promotion/*`). If the mission's "Promotion requirement" entity means cadet promotion
  readiness, that capability is effectively a single flag on one table — an island. **Needs human
  judgment on intended scope.**
- **`readiness_score`** on `parade_nights` is a derived 0-100 projection (documented at
  `models/training.py:63-68`) not independently authoritative — `planning_status`/`data_quality` are
  the real source. Consumers reading `readiness_score` as truth would be reading a shadow of data that
  lives (authoritatively) elsewhere. Lower priority; flagged for the dashboard-lineage work (doc
  `ui_data_lineage.csv`).
- **`equipment_required` / `required_equipment`** free-text columns (on `sessions` and `program_items`)
  are an information island relative to the `equipment` table — the requirement never links to the
  inventory. Likely intentional free-form; noted for completeness.

---

## 6. Missing uniqueness constraints (silent-duplicate accumulation)

Tables where the natural/business identifier is only *indexed*, not *unique*, so re-import or
double-submit can silently create duplicates:

- `cadets.service_number` — indexed, not unique. **P2** (personnel duplication on re-import).
- `curriculum_items.identifier` — uniqueness enforced in **app logic only** (409 check;
  `models/training.py:19-22`), no DB constraint.
- `facilitators` — no natural-key constraint (mitigated by the shipped absorb/merge dedup feature).
- `subject_area_tags` / `facilitator_type_tags` — `normalised_name` indexed but **no UNIQUE on
  (normalised_name, scope, wing_id/squadron_id)**; duplicate tags can accumulate.
- `planning_years` — no UNIQUE on `(unit_id, year)`; a squadron could hold duplicate years.
- `parade_nights` — no UNIQUE on `(squadron_id, date)`; `holiday_periods`, `planning_notices` — no
  natural-key uniqueness.

**Correctly constrained (for contrast):** `wings.code`, `squadrons.code` (UNIQUE);
`squadron_event_status` `(wing_event_id, squadron_id)`; `wing_event_curriculum_links`
`(wing_event_id, curriculum_item_id)`; `parade_night_timing_overrides.parade_night_id` (UNIQUE).

These are **P2** — they are latent (no evidence of live dupes gathered here) and adding a UNIQUE
constraint on tables that may already contain duplicates is itself risky, so any fix must first audit
existing data. **Not** an auto-fix.

---

## Prioritised feed into Phase B (trust / data-defect correction)

**P1 — silently wrong user-visible data (fix first, with regression tests that fail before the fix):**
1. `get_command_centre` reads the never-populated `scheduled_sessions` for `unscheduled_required`
   curriculum coverage and `nights_missing_fac` (`planning.py:2344-2383`). Migrate to the live
   `ParadeDate → ParadeNight → sessions` join, exactly as `facilitator_workload` was already fixed.
2. `add_facilitator_leave` computes leave-vs-schedule "affected sessions" from `scheduled_sessions`
   (`planning.py:3675-3690`) → conflict warning never fires. Same migration.
   *(Both are the tail of a migration whose head — `facilitator_workload` — is already done; this is
   completing an existing fix, low blast radius.)*

**P2 — latent integrity (schedule after P1; several need a data audit before any constraint change):**
3. Decide the fate of the superseded `scheduled_sessions` / `planning_locations` tables and their live
   cross-FKs (`planning_conflicts.scheduled_session_id`, `scheduled_sessions.location_id`) once (1)/(2)
   land. **Do not drop without user authorisation** (capability-preservation §1).
4. Missing-uniqueness set (§6) — audit existing data for dupes, then decide constraints. `cadets.
   service_number` and the tag tables first.
5. Un-enforced tenancy/reference columns (§2c, §4) — treat as Phase D database-invariant tests
   asserting "no orphans" before considering schema FKs; converting live String columns to FKs is a
   Phase C architecture decision, not a quick Phase B fix.

**Needs human judgment before ANY action (do not merge/alter on naming alone):**
6. Phase/"training stage" three-table fragmentation (§2a) and free-text `phase` columns.
7. `curriculum_items` vs `program_items`, and `activities` vs `cea_activities` — same-concept parallel
   models; convergence vs deliberate two-track is a product call.
8. `anchor_events.cea_activity_id` (Integer, cannot join a UUID) — confirm vestigial, then remove via
   the normal capability-preservation removal record.
9. SITREP and cadet-promotion modelling gaps (§5) — product-scope questions, route to docs 09/13.

**Explicitly NOT defects (recorded so a later pass doesn't "fix" them):** the audit log's absence of
FKs (intentional, history must survive deletes); the two-frontend split; Flight-not-tenancy;
`unit_type` on squadrons instead of a Specialist-Unit table; `readiness_score` being derived;
the advisory (non-FK) nature of `subject_area_tags`/`facilitator_type_tags` vs the free-text columns.

---

*Prepared read-only. No database was queried; no application code, migration, seed, or data was
modified. All line references are against commit `76d6723` / current HEAD source under `backend/`.*
