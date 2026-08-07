# 02 — Systems Architect Review

**Program:** Whole-System Adversarial Qualification (Phase A — discover and map).
**Role constraint (per charter §2A):** this document *proposes* findings and impact assessments only.
It does not redesign anything and no application code was modified to produce it.
**Source commit context:** working tree at branch `feature/restore-planning-workspace`; baseline
`capability_manifest_before.json` generated from `76d6723` (259 endpoints, 58 tables, 8 roles).
**Method:** direct code reading + grep verification of every claim below. Baseline/gap-register
assertions were re-verified against source, not trusted.

Finding tags used throughout:
- **[CONFIRMED]** — reproduced directly in source, cited.
- **[DESIGN]** — a choice I would not have made, but which is intentional and documented; **not a defect.**
- **[UNCERTAIN]** — real divergence found; user-visible impact needs a human/Data-Integrity decision.

---

## Executive summary

The system is architecturally healthier than a 15,000-line-router codebase usually is: tenancy scope
is enforced through `permissions.py` helpers on the write paths that matter, there is no raw SQL over
application data, and the two-frontend split is a deliberate, documented boundary rather than a
half-finished migration. The genuine architectural debt is concentrated in three places: (1) an
**incompletely retired legacy model (`ScheduledSession`)** that is never written but is still *read* by
two live endpoints, which is not merely dead code but a potential data-correctness divergence;
(2) **business logic living almost entirely in router modules** (`services.py` is only 158 lines while
`planning.py` is 4,514 and `training.py` is 3,492), which is a maintainability rather than correctness
problem; and (3) **N+1 query patterns and unpaginated list endpoints** that are harmless at pilot data
volume but degrade predictably at 10x. Most cross-frontend "seam" issues are already tracked in the
remediation register (REM-01, REM-41/REM-72) and need product decisions, not architecture rework.

---

## 1. Domain boundaries and coupling (Main TMS ↔ Planning Workspace)

The two frontends are a clean, intentional boundary (`.claude/rules/architecture.md`), and both call
the *same* FastAPI backend — there is no second backend or duplicated API. The real coupling story is
not frontend-to-frontend; it is that **some backend capabilities were built for one frontend and never
wired into the other**, so the "boundary" is really a capability-parity gap, already registered:

- **[CONFIRMED / already tracked]** `GET /api/dashboard/command` (readiness matrix, risk forecast,
  delivery-performance charts) is fully consumed by `connected-frontend` but had *zero* Planning
  Workspace consumer — gap register **REM-41** and **REM-72**. REM-72 records that it was subsequently
  wired into Planning Workspace's `CommandDashboardSection.tsx`; REM-72's residual note (no wing
  drill-down selector for `national_admin` in `NationalOverview`) is still open. This is the healthiest
  kind of coupling finding: one backend, feature-flagged by which frontend happened to consume it.

- **[CONFIRMED] Seam is clean at the data layer.** The planning routers reach into the *canonical*
  training tables (`TrainingSession`, `TrainingArea`, `ParadeNight`) rather than maintaining a parallel
  planning-only data store — see `backend/app/routers/planning.py:1532` (`create_session` writes a real
  `TrainingSession`) and `:343` (`_location_out` serialises a `TrainingArea`). Planning Workspace is a
  *view/workflow* over shared training data, not a separate domain with its own copies. This is the
  right direction and should be preserved.

- **[DESIGN] Two permission-helper families** (`_require_year_access` in `planning.py:164` vs.
  `require_can_write_squadron` in `permissions.py`) are the documented, intentional split
  (`architecture.md` "Permission/scope helper selection"). Verified: the planning *session* write paths
  (`get_session`/`update_session`/`delete_session`, `planning.py:1575/1591/1648`) correctly use the
  proxy-aware `require_can_write_squadron`, while pure year-scoping uses the simpler helper. Not a
  defect.

**Where one reaches into the other's concerns:** the only genuine leak is that planning endpoints still
carry Pydantic input schemas and a serializer named after the *retired* planning model
(`ScheduledSessionIn`, `_session_out`) while actually operating on `TrainingSession` — see §2. That is
naming/vestige debt, not a boundary violation.

---

## 2. Duplicated / superseded concepts

The baseline flags `scheduled_sessions`/`PlanningLocation` as "likely vestigial dead code (no live call
sites)." **I verified this and the baseline is half right and half wrong — the correction matters.**

### 2a. `PlanningLocation` — fully retired write-side, one dead read [CONFIRMED]
- **Never instantiated** anywhere: `grep "PlanningLocation("` returns zero constructor calls.
- All three location endpoints now read/write `TrainingArea` instead: `list_locations`
  (`planning.py:1830`), `create_location` (`:1846` → `TrainingArea(...)` at ~1863), `update_location`
  (`:1879`). The reconciliation is documented in-code at `planning.py:331-341` and in gap register
  **REM-01** ("TrainingArea/PlanningLocation already router-reconciled (verified)").
- **Residual dead code:** `_session_out` (`planning.py:300-328`) still calls
  `db.get(PlanningLocation, s.location_id)` at `:313`. But `_session_out` itself has **no callers** —
  every live path uses `_real_session_out` (`:349`). So the `planning_locations` table + `PlanningLocation`
  model + `_session_out` are fully vestigial. Safe to retire together.

### 2b. `ScheduledSession` — NOT fully dead; a read-only orphan with correctness risk [UNCERTAIN]
The baseline's "no live call sites" is **incorrect**. Verified:
- **Never written:** `grep "ScheduledSession("` finds only the code's own comment at `planning.py:3758`
  ("no `ScheduledSession(...)` instantiation exists"). Confirmed — nothing creates rows. REM-01 calls it
  "confirmed dead legacy."
- **But still read by two live endpoints**, which is the part the baseline missed:
  1. `GET /api/planning/command-centre` (`get_command_centre`, endpoint at `planning.py:2247`) computes
     `unscheduled_required` from `ScheduledSession.curriculum_id` (`:2348`) and `nights_missing_fac` from
     `ScheduledSession` (`:2375`).
  2. `POST /api/planning/facilitators/{fac_id}/leave` (`add_facilitator_leave`) computes its
     "affected sessions" warning from `ScheduledSession` (`:3678`).
- **Why this is more than dead code:** the canonical session data is now written to `TrainingSession`
  (§1), but these two endpoints query the table *nothing writes*. On any DB without pre-v14 legacy rows
  (i.e. staging, and any fresh production seed) `scheduled_curriculum_ids` is always empty → the command
  centre would report **every** core curriculum item as "unscheduled required" and **`nights_missing_fac`
  as 0**, regardless of the real `TrainingSession` schedule; and the leave endpoint would never warn
  about a genuine booking clash. I am confident the divergence is real (table never written + these reads
  confirmed); I am **not** asserting the user-visible severity because I did not trace whether these
  specific response fields are surfaced/relied upon in either frontend. **This needs Data-Integrity
  confirmation (feeds `03_data_integrity_review.md`) and is the single most important item in this
  review.**

### 2c. Other superseded-model pairs (already registered, product-blocked) [DESIGN/tracked]
REM-01 enumerates the full set and its status; I confirm the model classes co-exist but did not
re-litigate the product decisions:
- `Activity` / `CeaActivity` — read-visibility gap already closed per REM-01.
- `ParadeDate` / `ParadeNight` — genuinely separate live models (planning-calendar row vs. delivered
  parade). Both written; not a duplicate to collapse blindly.
- `AnchorEvent` / `WingHQEvent` / `Activity` — overlapping "event" concepts, three live models. REM-01
  marks these "blocked on product decisions, not engineering effort." Agree — do not consolidate under
  this program without a product owner.
- **Naming vestige:** `ScheduledSessionIn`/`ScheduledSessionUpdateIn` (`planning.py:1462/1477`) are the
  request schemas for endpoints that write `TrainingSession`. Rename when 2b is resolved so the schema
  name matches the table it targets.

---

## 3. Service boundaries, raw SQL, and inline role checks

### 3a. Raw SQL — clean [CONFIRMED]
No raw SQL over application data. `grep` for `.execute(text(...`/`text(` in routers returns only
infrastructure pings: `system.py:113` (`SELECT 1`), `system.py:149` (`SELECT version_num FROM
alembic_version`), `health.py:19` (`SELECT 1`). `services.py:63` uses SQLAlchemy Core
`select(func.count())` — not raw text. This satisfies the `.claude/rules/capability-preservation.md`
"no raw SQL for ordinary application operations" rule.

### 3b. "Never write ad hoc role checks inline in routers" — partial, nuanced [DESIGN, with one caveat]
There are 99 inline `p.role ==` / `p.role in` occurrences across the routers (training.py 38,
planning.py 18, accounts.py 16). Reading a representative sample, these fall into two categories:
- **Named role-set gates** — `p.role in _WRITE_BLOCKED` (`planning.py:160`), `p.role in _NAT_ADMIN_ROLES`
  (`training.py:112`). These are constant-backed, centrally defined role tiers, effectively a lightweight
  helper. Acceptable and consistent.
- **Per-router query scoping** — e.g. `list_locations` (`planning.py:1833-1842`) and `list_facs`
  branch on `p.role` to filter the query by squadron/wing. This is *data scoping*, not an
  authorization allow/deny decision, so it does not violate the security intent of the rule — but it
  **is** logic that `permissions.py` could own once and does not, so it is duplicated across many
  routers (each router re-derives "which squadron ids can this principal see"). This is the honest
  reading of the backend.md rule: the *authorization* decisions correctly go through helpers; the
  *scope-derivation* is copy-pasted. **[DESIGN / refactor candidate, not a security defect.]**

I did **not** find an inline check that *weakens* a permission (e.g. an "if not denied then allowed"
path). The tenancy write gates consistently call `require_can_write_squadron`.

### 3c. Thin service layer, fat routers [CONFIRMED — the core maintainability debt]
`services.py` is 158 lines (only `fk_dependents` + the readiness-scoring engine). Business logic —
conflict detection, coverage computation, rollover, CEA import, timing-template resolution — lives
inside the router modules: `planning.py` 4,514 lines, `training.py` 3,492, `dashboard.py` 2,307. There
is no architectural firewall between HTTP concerns and domain logic. This is not a correctness bug and
nothing here says "must fix," but it is the reason a single file (`planning.py`) can hide a
read-from-a-dead-table bug (§2b) between an HTTP decorator and a `return`. See §5.

---

## 4. Data-flow traces

**Trace A — session write → builder display (canonical, healthy).**
`POST /api/planning/parade-dates/{date_id}/sessions` (`planning.py:1491`) auto-links/creates a real
`ParadeNight` (`:1510`), resolves the room against `TrainingArea` (`:1527`), and writes a
`TrainingSession` with denormalised at-time snapshots of curriculum/facilitator/room
(`:1543-1556`) — a deliberate, sound denormalisation so historical records survive later edits to the
referenced entities. It then runs `_run_conflict_check` and audits (`:1558-1560`). Read-back
(`get_weekly_program`, builder endpoints) serialises via `_real_session_out` (`:349`). This flow is
clean and single-sourced.

**Trace B — session data → command-centre dashboard (divergent).**
The same `TrainingSession` write from Trace A is **not** what `GET /api/planning/command-centre` reads
for its "unscheduled required curriculum" and "nights missing facilitator" numbers — those come from the
orphaned `ScheduledSession` table (`:2348`, `:2375`; see §2b). So two dashboard-style numbers are
computed from a data source the write path no longer populates. This is the concrete "unusually
indirect / duplicated" data flow the task asks to surface, and it is the same root cause as §2b.

**Observation on aggregation flows:** wing/national report endpoints (`reports/*`, `dashboard/command`)
aggregate by iterating squadrons; combined with the N+1 patterns in §6 this is where cost concentrates
at scale, not in the single-squadron write path.

---

## 5. Technical debt (maintainability — genuine, not style)

1. **[CONFIRMED] Incomplete model migration left live reads against a dead table** (§2b). The most
   concerning item: a half-completed `ScheduledSession → TrainingSession` migration removed the writes
   but not all the reads. Retire the reads (repoint to `TrainingSession`) *or* the table, but the
   current in-between state is the worst option.
2. **[CONFIRMED] No service/domain layer** (§3c). 10k+ lines of domain logic embedded in three router
   files. Long-term this makes every change a router change and makes bugs like §2b easy to hide. A
   staged extraction of the pure-computation functions (conflict detection, coverage, readiness) into
   `services/` would pay for itself; **propose for a later phase, do not attempt under Phase C's
   defect-correction scope.**
3. **[CONFIRMED] Dead serializer + schemas** (`_session_out`, `PlanningLocation`,
   `ScheduledSessionIn` naming) — low-risk cleanup, do it alongside §2 so the register entry closes
   cleanly.
4. **[DESIGN] Scope-derivation duplicated per router** (§3b) — refactor candidate, centralise "visible
   squadron ids for principal" in `permissions.py`.

---

## 6. Scaling risks (10x data volume)

1. **[CONFIRMED] N+1 query patterns in list/serialize loops.** `list_facs` (`training.py:772`) issues a
   separate `PlanningFacilitatorLeave` query **per facilitator** inside a Python loop. `_real_session_out`
   / `_session_out` issue `db.get(...)` per session for curriculum/facilitator/room. `add_facilitator_leave`
   loops `db.get(ParadeDate, ...)` per session (`:3687`). At pilot volume these are invisible; at 10x
   facilitators/sessions they become the dominant cost. Fix pattern: eager-load / batch (`selectinload`
   or a single `IN` query). **Highest-value scaling item.**
2. **[CONFIRMED] Unpaginated list endpoints.** 252 bare `.all()` calls across routers. Many are
   naturally bounded because they are squadron-scoped (`list_cadets` `training.py:1131`, `list_facs`,
   `list_curriculum`, `list_parades`) — a single squadron's cadet/facilitator count is small, so these
   are acceptable. The ones to watch are the **cross-squadron / wing / national aggregations** and any
   list that grows unbounded over time (audit is capped at 1000 via `system.py:277`; good). Endpoints
   that *do* cap (`training.py:1537` CEA `.limit(2000)`, `:1585` holidays `.limit(500)`,
   `wing_calendar.py:301` proper `offset/limit`) show the team already knows the pattern — it is just
   applied inconsistently. **Recommend a standard paginate helper; not urgent for the squadron-scoped
   lists.**
3. **[CONFIRMED] Indexing is broadly sound.** FK columns in `models/planning.py` carry `index=True`
   (e.g. `planning_year_id`, `unit_id`, `facilitator_id`). No obvious missing index on a hot filter
   column was found in the models reviewed. The `.in_(parade_date_ids)` filters (`planning.py:2350`)
   pass a Python list that itself came from a full `ParadeDate` scan of the year (`:2340`) — fine for a
   single squadron-year, but this two-step (materialise all ids, then `IN`) is an anti-pattern that
   should become a join if year sizes grow. **[DESIGN / watch.]**
4. **[tracked, not arch] UI-side density** (REM-85, wing overview table renders all squadron rows with
   no pagination) — a frontend concern, noted for completeness.

---

## Prioritised feed into Phase C (architecture/integration defect correction)

| # | Finding | Type | Priority | Cite |
|---|---|---|---|---|
| C-1 | `command-centre` + `add_facilitator_leave` read the never-written `ScheduledSession` table → coverage/conflict numbers computed off dead data | **[UNCERTAIN → likely CONFIRMED defect]** | **P1** — confirm impact with Data-Integrity first, then repoint reads to `TrainingSession` | `planning.py:2348,2375,3678` |
| C-2 | Retire `PlanningLocation` model + `planning_locations` table + dead `_session_out` serializer | CONFIRMED (cleanup) | P3 | `planning.py:300-328,313`; model `:144` |
| C-3 | Rename `ScheduledSessionIn`/`ScheduledSessionUpdateIn` to match `TrainingSession`; do with C-1/C-2 | CONFIRMED (naming) | P3 | `planning.py:1462,1477` |
| C-4 | N+1 in `list_facs`, `_real_session_out`, `add_facilitator_leave` — batch/eager-load | CONFIRMED (perf) | P2 (Phase F) | `training.py:772`; `planning.py:349,3687` |
| C-5 | Centralise per-principal squadron-scope derivation now duplicated across routers | DESIGN (refactor) | P3 | §3b, `planning.py:1833` et al. |
| C-6 | Standard pagination helper for cross-scope/growing lists (squadron-scoped lists OK as-is) | CONFIRMED (perf) | P3 (Phase F) | 252× `.all()`; good examples `wing_calendar.py:301` |
| C-7 | REM-72 residual: no wing drill-down selector for `national_admin` Command Dashboard in Planning Workspace | tracked (parity) | P3 | gap register REM-72 |
| C-8 | Longer-term: extract domain logic from 10k-line routers into a service layer | DESIGN (debt) | **Out of Phase C scope** — propose as its own architectural decision, not a defect fix | §3c, §5.2 |

**Explicitly NOT flagged as defects** (verified intentional per the rules files): the two-frontend
split; the two permission-helper families; Flight-as-grouping (not tenancy); divergent design-token
naming between frontends; `ParadeDate`/`ParadeNight` and the anchor/event model trio (product-blocked
per REM-01, not engineering defects).

**Areas that looked clean and are reported as such, briefly:** raw-SQL discipline (§3a); write-path
tenancy enforcement through `permissions.py` (§1, §3b); the canonical session write flow (Trace A);
FK indexing (§6.3). No fabricated issues were added to these.
