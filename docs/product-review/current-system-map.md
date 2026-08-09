# Current system map

Status: initial pass, 2026-08-09. Built by direct inspection of the checked-out
repository at commit `4c5e384` — not from prior documentation, which the
whole-system hardening program (`CLAUDE.md`, this program's governing
instructions) explicitly warns may be stale. Cross-references existing
baseline docs (`docs/qualification/01_capability_baseline.md`,
`docs/qualification/02_architecture_review.md`, `docs/architecture.md`,
`docs/role_matrix.md`, `docs/remediation/role_capability_matrix.md`,
`docs/remediation/capability_manifest_before.json`) rather than duplicating
them — those remain the record of the prior remediation program's baseline;
this document is the baseline for the new whole-system product/UX/data
program layered on top.

## Stack

- Backend: FastAPI 0.110+, SQLAlchemy 2.0, Python 3.13, Alembic, Pydantic v2.
  SQLite for local dev/tests, PostgreSQL (Supabase-hosted) in staging/production.
- Two independently deployed frontends (see `.claude/rules/architecture.md` —
  this split is intentional, not a migration in progress):
  - `connected-frontend/` — single-file HTML/CSS/JS SPA (`index.html`, ~400KB),
    no build step, served by its own Dockerfile/nginx. This is the TMS root
    frontend beta users land on ("Main TMS" in this program's language).
  - `frontend/` — React + Vite + TypeScript "Planning Workspace", mounted at
    `/planning`, deployed separately (`aafc-tms-planning-workspace-preview`).
- Both read the backend base URL from a `<meta name="aafc-api-base">` tag,
  rewritten at container start from `AAFC_API_BASE`.

## Backend routers (`backend/app/routers/`)

| Router | Responsibility |
|---|---|
| `auth.py` | Access-code lookup/login, JWT issue, `/auth/me` |
| `accounts.py` | Account CRUD, role/scope authority (`_CREATE_AUTHORITY`), archive/restore |
| `organisations.py` | Wing/Squadron/Specialist Unit CRUD, archive/restore |
| `training.py` | ParadeNight, Session, Facilitator, TrainingArea, Equipment, Activity, Cadet, TimingTemplate/Block, CurriculumItem/Element/Phase, SubjectAreaTag, FacilitatorTypeTag — the largest router; most of Main TMS's operational surface |
| `planning.py` | PlanningYear, ParadeDate, HolidayPeriod, AnchorEvent, PlanningNotice, locations/facilitators read models consumed by Planning Workspace, conflict overrides, CEA import |
| `dashboard.py` | `_curriculum_progress()`, `_full_squadron_charts()`, `/api/dashboard/command`, readiness aggregation |
| `program.py` | Phase, ProgramPackage, ProgramItem, LearningHubResource, SourceFile/SourceConflict, PromotionRequest — **off-limits per prior explicit user instruction; do not modify as part of this program without a fresh explicit ask** |
| `wing_calendar.py` | Wing-level calendar/notice aggregation |
| `timing.py` | Timing-template-adjacent endpoints (distinct from `TimingTemplate`/`TimingBlock` CRUD living in `training.py`) |
| `system.py` | System Console: maintenance mode, backup status, scope-map, audit |
| `export_import.py` | CSV/annual-program import, CEA mapping |
| `setup.py` | Guided setup flow support endpoints |
| `ops.py`, `jobs.py`, `health.py` | Operational/maintenance/health-check endpoints |

## Backend models (`backend/app/models/`)

| File | Tables |
|---|---|
| `organisations.py` | Wing, Squadron (incl. `default_parade_day`/`default_start_time`/`default_end_time`/`default_session_count`), Specialist Unit variants, Account |
| `training.py` | CurriculumItem, CustomPhase, ParadeNight, Session, SessionStatusHistory, Facilitator, FacilitatorRankHistory, SubjectAreaTag, FacilitatorTypeTag, TrainingArea, Equipment, Activity, Cadet, TimingTemplate, TimingBlock, ParadeNightTimingOverride, CurriculumElement, CurriculumPhase |
| `planning.py` | PlanningYear, ParadeDate, HolidayPeriod, AnchorEvent, PlanningNotice, plus a **dead** `PlanningLocation`/`ScheduledSession` pair (confirmed zero live call sites in an earlier pass this program — `TrainingArea` is the one live model behind both interfaces' location/room views) |
| `program.py` | Phase, ProgramPackage, ProgramItem, LearningHubResource, SourceFile, SourceConflict, PromotionRequest, JobStatus — **off-limits, see above** |
| `operations.py`, `wing_calendar.py` | Operational/maintenance state, wing calendar entries |

## Permission model (`backend/app/permissions.py`)

- `Principal` dataclass carries role, squadron/wing scope, and active
  Proxy Mode / Delegated Intervention state.
- Two helper families in active use (see `.claude/rules/architecture.md`):
  `require_can_view_squadron`/`require_can_write_squadron` (tenancy- and
  proxy-aware) vs `_require_year_access` in `planning.py` (simpler, no proxy
  concept). Using the wrong one for a given endpoint is a known regression
  class (see REM-45 residual case, REM-130 this program).
- Roles observed in `_CREATE_AUTHORITY`/tests: `system_admin`, `national_admin`,
  `national_viewer`, `wing_admin`, `wing_viewer`, `sqn_admin`, `sqn_general`,
  `auditor`.
- Tenancy hierarchy is National → Wing → Squadron only. `Flight` (`flight_id`
  on `User`/`Cadet`) is a sub-squadron cadet-organisation grouping, not a
  tenancy level — do not create Flight-scoped permission checks (per
  `.claude/rules/architecture.md`, restated here because this program's
  addendum introduces a second, unrelated "Training Class" grouping concept
  that must not be confused with Flight).

## Reference-data scoping pattern (reusable template)

`CurriculumElement` and `CurriculumPhase` (`training.py`) both implement the
same proven pattern: `scope_level` (`system|national|wing|squadron`) +
nullable `wing_id`/`squadron_id`, visibility computed as national + own-wing +
own-squadron, higher scopes read-only to lower-scope admins. `SubjectAreaTag`/
`FacilitatorTypeTag` follow the same shape. This is the template this
program's addendum §18/§66 asks to reuse for any new configurable type,
including the new Training Class concept's Training Stage half (§32.1 —
already effectively satisfied by `CurriculumPhase`; see
`parallel-class-impact-analysis.md` for what is and is not already present).

## Existing capability baselines (do not duplicate, cross-reference)

- `docs/qualification/01_capability_baseline.md`, `02_architecture_review.md`,
  `capability_matrix.csv` — prior program's capability inventory.
- `docs/remediation/capability_manifest_before.json`,
  `role_capability_matrix.md` — prior remediation program's before/after
  capability-preservation record (per `.claude/rules/capability-preservation.md`).
- `docs/role_matrix.md` — role/permission matrix.
- `docs/remediation/master_gap_register.csv` — 170 entries as of this program's
  start (REM-1 through REM-131), 51 open, all P2/P3/MEDIUM/LOW. This program's
  new WRITE-*/CLASS-* items are being appended to the same register (§103)
  rather than starting a parallel one.

These remain authoritative for what was true at the end of the prior
remediation program (commit `4c5e384`). This document is the entry point for
the new program layered on top; it will be kept current as work proceeds
rather than written once and left stale (per this program's own §2 instruction
not to trust documentation that isn't verified against real code).
