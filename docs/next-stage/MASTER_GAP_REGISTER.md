# AAFC TMS — Master Gap Register

**Version:** 2026-08-12  
**Branch:** `next-stage/v1-operational` | Deployed commit: `756e65e` (production, 2026-08-12, Alembic head v51)  
**Backend tests:** 1553 passed, 5 skipped (commit `afdc263`)  
**Sources merged:**
- 2026-08-12 program audit (prior register: 18 DONE / 14 PARTIAL / 57 NOT DONE / 7 HUMAN GATE)
- Training Class architecture analysis (`parallel-class-impact-analysis.md`)
- Defence Writing Manual requirements (`defence-writing-ui-standard.md`, 46-row `interface-language-inventory.csv`)
- Original 25-gap matrix (`01_gap_matrix.md`)
- UX gap register (`ux-gap-register.md`)
- Dashboard metric dictionary, workflow map, capability manifest
- Security hardening review (`15_security_hardening_review.md`)

This is the single authoritative register. The prior `01_gap_matrix.md` and `ux-gap-register.md`
are superseded by this document for status tracking; those files remain as reference and evidence.
The "35% complete" figure from the prior register is not reproduced — that figure was computed from
only the original 25-gap matrix and predates the Training Class backend work, the Defence Writing
sweep, the UX/product gaps, and the security hardening additions merged here.

---

## Status Totals (recomputed from live codebase, 2026-08-12)

| Status | Count |
|---|---|
| CLOSED | 24 |
| STAGING VERIFIED | 5 |
| FIXED LOCALLY | 13 |
| IMPLEMENTING | 14 |
| NOT STARTED | 47 |
| HUMAN GATE | 15 |
| ACCEPTED RISK | 2 |
| **Total** | **120** |

**Completion rate** (CLOSED + STAGING VERIFIED + FIXED LOCALLY) **= 42 / 120 = 35%**

---

## Status Definitions

| Status | Meaning |
|---|---|
| CLOSED | Gap fully addressed; evidence on record; backend + frontend verified, or gap N/A to frontend |
| STAGING VERIFIED | Working in staging; not yet confirmed in production |
| FIXED LOCALLY | Fix applied to codebase; not yet deployed or staging-verified |
| IMPLEMENTING | Partial implementation exists; specific remaining work stated in Current State |
| NOT STARTED | No implementation; gap confirmed real by direct code inspection |
| HUMAN GATE | Requires a non-engineering decision, approval, or manual action by a named authority |
| ACCEPTED RISK | Acknowledged; consciously not implemented for the current level; rationale on record |

---

## 1. Core Domain Architecture — Training Stage / Class

**Scope:** The full Training Class backend (migrations v42–v50, CRUD, audience, curriculum progress,
Mission Backlog class_breakdown, class-behind-threshold detection, 12 class-specific test files) is
CLOSED as of commit `afdc263`. All remaining CLASS-series gaps are in the frontend layer —
connected-frontend `index.html` and Planning Workspace React components. None of the backend
model additions removed any existing route or table; the capability manifest must be regenerated
to formally confirm this (see DOC-12).

| ID | AREA | SEVERITY | REQUIREMENT | CURRENT STATE | STATUS |
|---|---|---|---|---|---|
| CLASS-01 | Core Domain | HIGH | TrainingClass model: squadron_id, training_year_id, training_stage_id (FK curriculum_phases), display_name, sequence, soft-delete (SoftDeleteMixin), optimistic locking (version) | Migration v48; model in `training.py` alongside CurriculumPhase/Session/Cadet; follows PlanningYear's scoping shape | CLOSED |
| CLASS-02 | Core Domain | HIGH | SessionAudience join table: session_id, training_class_id, outcome_override, outcome_override_reason | Migration v49; many-to-many Session ↔ TrainingClass implemented; replaces one-value `Session.cadet_group` pattern | CLOSED |
| CLASS-03 | Core Domain | MEDIUM | CadetClassMembership: cadet_id, training_class_id, start_date, end_date (nullable), active_status, source, created_by | Migration v50; individual cadet-level membership tracking within a class | CLOSED |
| CLASS-04 | Core Domain | HIGH | TrainingClass CRUD endpoints — create, list, get, update, archive, restore | Full CRUD in `training.py`; 12 class-specific test files pass; 1553 tests passing overall | CLOSED |
| CLASS-05 | Core Domain | HIGH | TrainingClass split endpoint — reassigns members to a new class; historical class preserved as soft-archived, never hard-deleted | Implemented in `training.py` (split / reassign-members) | CLOSED |
| CLASS-06 | Core Domain | HIGH | TrainingClass merge endpoint — absorbs one class into another; historical class soft-archived | Implemented in `training.py` | CLOSED |
| CLASS-07 | Core Domain | HIGH | Session audience GET/PUT — `GET /api/sessions/{id}/audience` and `PUT /api/sessions/{id}/audience` with per-class outcome_override | Implemented; per-class outcome_override and outcome_override_reason exposed | CLOSED |
| CLASS-08 | Core Domain | HIGH | Curriculum progress per class — `GET /api/training-classes/{id}/curriculum-progress` using SUM(delivered)/SUM(applicable) per class, not average(percentages) | Implemented in `training.py`; aggregation method confirmed | CLOSED |
| CLASS-09 | Core Domain | HIGH | Phase-level class progress — `GET /api/curriculum/phases/{id}/class-progress` | Implemented in `training.py` | CLOSED |
| CLASS-10 | Core Domain | HIGH | Mission Backlog `class_breakdown` field — backend returns per-curriculum-item breakdown of which Training Class needs action | `planning.py` Mission Backlog API returns `class_breakdown` | CLOSED |
| CLASS-11 | Core Domain | MEDIUM | Class behind-threshold detection: backend flags classes >15 pp below their stage average | Backend detects and returns flag; 1553 tests passing including class-specific tests | CLOSED |
| CLASS-12 | Core Domain | HIGH | class_curriculum_progress chart in connected-frontend — chart container rendering per-class curriculum progress from `charts.class_curriculum_progress` | Confirmed implemented: `chart-class-curriculum-progress` container at index.html:792; rendered at index.html:6857 via `_dRenderChart`; insight at 6858. Gap register was stale. | CLOSED |
| CLASS-13 | Core Domain | HIGH | class_breakdown field rendered in connected-frontend curriculum page — per-item indication of which Training Class needs each curriculum item | Implemented as MBACK-01 (commit `16f6bce`): `_loadCurriculumClassBreakdown()` + `_currClassBreakdownHtml()` render per-class badges in curriculum page | CLOSED |
| CLASS-14 | Core Domain | MEDIUM | Training Classes step in the Getting Started checklist onboarding wizard | Confirmed implemented: `setup.py` lines 79-84 query TrainingClass count; lines 139-141 emit `training_classes_created` step. Gap register was stale. | CLOSED |
| CLASS-15 | Core Domain | LOW | CustomPhase → CurriculumPhase migration and cleanup — CustomPhase is a narrower, older squadron-scoped phase-name table that predates CurriculumPhase | CustomPhase still live; migration surface identified in `parallel-class-impact-analysis.md` as CLASS-14; not acted on | IMPLEMENTING |
| CLASS-16 | Core Domain | LOW | Session.cadet_group / Cadet.phase formal deprecation — single-string fields replaced structurally by SessionAudience; all consumers (Mission Backlog, Weekly Program, dashboards, both frontends) must migrate before fields are removed | Old fields retained as read-compatibility path per capability-preservation rules; no migration schedule; no consumer yet migrated to SessionAudience | IMPLEMENTING |

---

## 2. Dashboard & Data Science

**Scope:** `dashboard.py` has ~35 chart/metric builder functions. Gap 10 (Tier 1 reports) and Wing
T2-04/T2-05 cards are CLOSED. The primary remaining gaps are frontend rendering of the new per-class
chart, metric documentation completeness, chart fault isolation, and accessible chart alternatives.
Backend dashboard builders are substantially complete; gaps are in documentation, verification, and
frontend consumption.

| ID | AREA | SEVERITY | REQUIREMENT | CURRENT STATE | STATUS |
|---|---|---|---|---|---|
| DASH-01 | Dashboard | HIGH | Wing T2-04 (wing-cancellation-trend) and T2-05 (wing-not-delivered) wired to Wing dashboard cards | All 5 wing report endpoints rendered in connected-frontend; confirmed by `01_gap_matrix.md` Gap 10 closure | CLOSED |
| DASH-02 | Dashboard | HIGH | Zero-session parade night reports as `not_planned`, never as 100% ready | `dashboard.py` and `index.html:5672/:5713` correctly guard `sessions_total===0` / `planning_status==='not_planned'` | CLOSED |
| DASH-03 | Dashboard | MEDIUM | Full §23 metric dictionary pass — all 22 inventoried chart functions documented (QUESTION / PURPOSE / POPULATION / PERIOD / NUMERATOR / DENOMINATOR / SOURCE / REFRESH / ACTION / DRILL-DOWN) | `dashboard-metric-dictionary.md` covers 2 charts fully; 20 inventoried with one-line purposes only | NOT STARTED |
| DASH-04 | Dashboard | MEDIUM | Per-chart fault isolation in backend — each chart builder in `_full_squadron_charts` wrapped in its own try/except so one failure cannot 500 the whole `/api/dashboard/charts` response | `_run_chart_builder()` at `dashboard.py:62` wraps each builder in try/except, returning `chart_type="error"` on failure; confirmed implemented | CLOSED |
| DASH-05 | Dashboard | MEDIUM | Frontend chart error handling — catch handler resets all chart containers on failure, not just 2 of 7+ (noted at `index.html:5793`) | `_DASH_CHART_IDS` at `index.html:6797` now covers all 14 chart/insight pairs; both skeleton reset and fetch-failure cleanup use the shared list — implemented and commented at lines 6789–6796 | CLOSED |
| DASH-06 | Dashboard | LOW | Cancellation reasons "Unknown" / "Reason not recorded" — UI must surface an actionable prompt when this Pareto category is non-trivial, not display it as an inert bar | `loadDashCharts()` now appends a `a-warn` alert beneath the cancellation chart when the top reason is a `data_quality_gap` row and accounts for ≥15% of cancellations, explaining how to fix it | FIXED LOCALLY |
| DASH-07 | Dashboard | MEDIUM | Accessible chart alternatives — data tables or text summaries alongside every chart element for screen-reader access | No accessible data-table alternatives alongside charts in either frontend | NOT STARTED |
| DASH-08 | Dashboard | LOW | National/Wing readiness matrix (`_readiness_matrix`), risk forecast (`_risk_forecast`), and command metrics — frontend drill-down fully wired and verified end-to-end | Backend builders exist and are inventoried; whether all national/wing drill-down paths are rendered in connected-frontend is not confirmed this pass | IMPLEMENTING |
| DASH-09 | Dashboard | MEDIUM | Curriculum progress per phase computed using governed CurriculumPhase catalogue (not hardcoded 8-phase list) | `_phases_for_squadron()` confirmed to read governed `CurriculumPhase` catalogue after earlier fix; hardcoded 8-phase list removed | CLOSED |

---

## 3. Mission Backlog

**Scope:** Backend Mission Backlog API is CLOSED (returns `class_breakdown`, per-class progress,
and curriculum item breakdown). Frontend consumption gaps are the remaining work.

| ID | AREA | SEVERITY | REQUIREMENT | CURRENT STATE | STATUS |
|---|---|---|---|---|---|
| MBACK-01 | Mission Backlog | HIGH | class_breakdown per curriculum item displayed in connected-frontend curriculum page — identifies which Training Class needs each item | Implemented commit `16f6bce`: `_loadCurriculumClassBreakdown()` fetches mission backlog on curriculum page nav; `_currClassBreakdownHtml()` renders per-class badges (b-ok/b-blue/b-amber/b-red by status). | FIXED LOCALLY |
| MBACK-02 | Mission Backlog | MEDIUM | Per-class Mission Backlog filtering in UI — view backlog filtered to a single Training Class | `mission-filter-class` select populated dynamically from `class_breakdown` in `loadMissions()`; `renderMissions()` filters to missions where selected class is not resolved — confirmed present in `index.html:10485–10522` | CLOSED |
| MBACK-03 | Mission Backlog | MEDIUM | Needs Attention consolidated queue (§39) — single prioritised surface combining readiness warnings, class gaps, and required planning actions | Individual pieces exist (readiness warnings, Mission Backlog panel); not consolidated into one action queue | NOT STARTED |
| MBACK-04 | Mission Backlog | LOW | Plan-faster shortcut from Mission Backlog item directly to a session slot (§41) | Not implemented; currently requires navigating to the session separately | NOT STARTED |
| MBACK-05 | Mission Backlog | MEDIUM | Per-class facilitator / resource conflict detection (§69) — when assigning a facilitator or room to a session, detect conflicts against other sessions that the same class attends | No class-aware conflict detection; current conflict checks are session-level only, blind to a class being split across parallel sessions | NOT STARTED |
| MBACK-06 | Mission Backlog | LOW | Per-class delivery summary — ability to export a per-class delivery record (what each Training Class has received, by curriculum item) as a report or CSV | No per-class delivery report exists; reports are per-squadron or per-phase only | NOT STARTED |

---

## 4. Help & First-Time Experience

**Scope:** No Help Centre, Glossary, or contextual help feature exists in either frontend. The
Getting Started wizard (`setup.py`) exists but is incomplete for Training Classes. "Getting Help"
is an empty-string admin-editable text field — no default content ships.

| ID | AREA | SEVERITY | REQUIREMENT | CURRENT STATE | STATUS |
|---|---|---|---|---|---|
| HELP-01 | Help | MEDIUM | Contextual help tooltips on key fields across both frontends — hover/focus reveals a plain-language explanation of each field's purpose | Not implemented in either frontend | NOT STARTED |
| HELP-02 | Help | LOW | Glossary of terms accessible from within the application — defines Training Stage, Training Class, Parade Night, Curriculum Item, Mission Backlog, and other domain terms | Not implemented; no glossary surface in either frontend | NOT STARTED |
| HELP-03 | Help | MEDIUM | Help Centre 17-question acceptance test — all questions a new Training Officer would ask are answerable from within the application, without external reference | No Help Centre feature exists; investigated and confirmed absent from both frontends | NOT STARTED |
| HELP-04 | Help | MEDIUM | Pre-flight / readiness check UI — explainable per-item checklist (✓ / ! per item) rather than a single blended readiness percentage | `_renderTonightReadiness()` now renders a "Readiness checklist" section below the session list showing Sessions planned (b-ok badge), Facilitators assigned (b-ok/b-amber/b-red with N/M count), Rooms assigned (same) — derived from `d.fac_filled`, `d.room_filled`, `d.sessions_total` already returned by `_tonight_readiness` backend | FIXED LOCALLY |
| HELP-05 | Help | LOW | "What changed?" view (§40) — changelog or activity feed showing recent modifications to the current week's plan | Not found anywhere in either frontend | NOT STARTED |
| HELP-06 | Help | LOW | Universal search / command palette (§6) — single-keystroke access to any entity, page, or action from anywhere in the application | Not implemented in either frontend | NOT STARTED |
| HELP-07 | Help | LOW | Getting Help panel — admin-editable free text must have meaningful default guidance content for a new squadron's first session | Empty-string default (`training.py:2583–2609`); any admin can write to it but no default guidance ships with the system | ACCEPTED RISK |
| HELP-08 | Help | MEDIUM | Setup status endpoint surfaced in UI — `GET /api/setup/status` exists but no setup-status summary is shown to a wing_admin or sqn_admin who has just completed Getting Started | `page-getting-started` renders `GET /api/setup/status` response via `loadGettingStarted()` at `index.html:4462`; accessible from nav as "Getting Started" for squadron/wing/national/system_admin scopes | CLOSED |

---

## 5. Workflow Efficiency

**Scope:** No click/field count baselines have been measured for any workflow. Three restore-UI
gaps affect four entity types. Bulk-import and smart-planning features are Level B/C items.

| ID | AREA | SEVERITY | REQUIREMENT | CURRENT STATE | STATUS |
|---|---|---|---|---|---|
| WORK-01 | Workflow | LOW | Click/field count baseline measured for all 12 high-frequency workflows (§37) so improvements can be measured | `workflow-map.md` scaffold exists with workflow names; no click counts measured for any workflow | NOT STARTED |
| WORK-02 | Workflow | MEDIUM | Restore UI for curriculum items — soft-archived via `is_archived=True` but no restore endpoint or UI control exists in either frontend | `POST /api/curriculum/{cid}/restore` at `training.py:3933`; `doRestoreCurrItem()` at `index.html:7819` shows Restore button in archived rows | CLOSED |
| WORK-03 | Workflow | MEDIUM | Restore UI for facilitators — soft-archived but no restore endpoint or UI control in either frontend | `POST /api/facilitators/{fid}/restore` at `training.py:1715`; `doRestoreFacilitator()` at `index.html:8787`; "Show archived" checkbox with Restore button per row | CLOSED |
| WORK-04 | Workflow | MEDIUM | Restore UI for Wing HQ calendar events and anchor events — soft-archived but no restore endpoint or UI | Wing HQ events: fully implemented — `doRestoreWingEvent()` at `index.html:12710`. Anchor events: `POST /api/planning/anchors/{id}/restore` added (commit `aaf3a2d`→next); `include_archived` param added to list endpoint; `doRestoreAnchor()` added to frontend; anchor tab hidden from pilot nav but backend+JS ready | FIXED LOCALLY |
| WORK-05 | Workflow | LOW | Flexible time blocks within a parade night (§11/§12) — variable-length training blocks, not only fixed-template slots | Not implemented; timing blocks are fixed-template only | NOT STARTED |
| WORK-06 | Workflow | LOW | Smart planning assistance — when building a session, suggest under-covered curriculum items for the attending class (§13) | Not implemented in either frontend | NOT STARTED |
| WORK-07 | Workflow | MEDIUM | Bulk holiday import with explicit `holiday_type` field (§41) — if built, must not silently default to `school_holiday`; no holiday import path exists today | `export_import.py` has zero references to `holiday_type`; flagged as design constraint for future import work | ACCEPTED RISK |
| WORK-08 | Workflow | LOW | Session move by drag-and-drop or equivalent shortcut within Planning Workspace | Planning Workspace (React) is better positioned for this; not confirmed implemented | NOT STARTED |
| WORK-09 | Workflow | MEDIUM | PlanningLocation Phase 2 table drop — `planning_locations` is inert (no new writes since canonical model decision), but the table still exists and the fallback resolver still queries it | Decision in `04_canonical_data_model.md`; Phase 2 (table drop + removal of fallback resolver) deferred to Level B; not yet scheduled | IMPLEMENTING |

---

## 6. Defence Writing

**Scope:** All Defence Writing fixes are applied to codebase (FIXED LOCALLY status). None has been
formally staging-verified as a separate post-deploy check. Source: 46-row
`interface-language-inventory.csv` (all items reviewed; 35+ fix-applied or reviewed-no-change),
`defence-writing-ui-standard.md` (Manual §2.4–§5.82 translated to UI rules), and
`ui-copy-review-checklist.md`.

| ID | AREA | SEVERITY | REQUIREMENT | CURRENT STATE | STATUS |
|---|---|---|---|---|---|
| WRITE-01 | Defence Writing | MEDIUM | All jargon / software terms removed from normal-user copy — `backend`, `endpoint`, `payload`, `schema`, `UUID`, raw HTTP codes — across both frontends (Manual §2.13.g) | 36 strings reviewed; 29 fix-applied: network errors, audit log subtitle, account management banners, planning error messages, reports page explanation, scope bar footnote, access-codes card, load-error hints | FIXED LOCALLY |
| WRITE-02 | Defence Writing | MEDIUM | Unambiguous date formats throughout — `DD Mon YYYY` or `DD Mon YY` only; numeric `DD/MM/YY` and `MM/DD/YY` forms prohibited (Manual §5.72) | 6 call sites fixed: Weekly Program footer, facilitator duplicate-warning card, Accounts last-login (Planning Workspace), Audit time column (Planning Workspace), facilitator card (Planning Workspace) | FIXED LOCALLY |
| WRITE-03 | Defence Writing | MEDIUM | 24-hour time for all operational time display — `1830` not `6:30 PM`; explicit `hour12:false` in all `toLocaleString` calls (Manual §5.79–5.80) | Planning Workspace Audit time column corrected to explicit `hour12:false` and unambiguous date format; no other 12-hour violations found | FIXED LOCALLY |
| WRITE-04 | Defence Writing | LOW | "Given name" / "Family name" — not "First name" / "Surname" — for all personal-name form fields in both frontends (Manual §3.34) | Both frontends already use correct labels. One stale error message "First and last name are required" in `PlanningBottomDrawer.tsx:861` updated to "Given name and family name are required" | FIXED LOCALLY |
| WRITE-05 | Defence Writing | LOW | No contractions in formal copy — `cannot` not `can't`; `will not` not `won't`; `you would` not `you'd` (Manual §2.13.h) | 6 instances fixed via multi-line Python sweep (archive confirmations, scope bar, unit settings, delete toasts, Getting Started subtitle, Unit Settings parade-day explanation); sweep confirmed no remaining instances | FIXED LOCALLY |
| WRITE-06 | Defence Writing | LOW | Australian English spelling throughout — `organise`, `colour`, `program` (single m) (Manual §3.4, §3.15) | No violations found in targeted grep sweep; confirmed clean | FIXED LOCALLY |
| WRITE-07 | Defence Writing | LOW | Active voice throughout — subject-verb-object; passive permitted only where a deliberate technical/objective register is required (Manual §2.53–2.58) | Applied in rewrites for error messages, confirmation dialogs, and network error copy | FIXED LOCALLY |
| WRITE-08 | Defence Writing | MEDIUM | Confirmations for irreversible actions state what changes, what stays, and whether the action can be undone — hard-delete must say "cannot be undone"; soft-archive must say "records are preserved" (Manual §2.14, checklist §25) | Hard-delete confirmations (parade dates, holidays) updated with "cannot be undone"; soft-archive confirmations (parade nights, activities, training areas, equipment) updated with "records are preserved"; cascade blast-radius (all sessions on a parade night) explicitly named | FIXED LOCALLY |
| WRITE-09 | Defence Writing | MEDIUM | Error messages follow WHAT HAPPENED / WHAT IT AFFECTS / WHAT TO DO NEXT; empty states distinguish FAILED TO LOAD from NO DATA from NOT CONFIGURED (checklist §23/§24) | Applied to TermView, YearView, ParadeNightGridView, PlanningBottomDrawer, ListView (ListView previously displayed a failed fetch as NO DATA — real logic gap fixed, not copy-only) | FIXED LOCALLY |
| WRITE-10 | Defence Writing | LOW | Platform-neutral, accurate copy in maintenance and system notices — no stale hosting-platform names in any user-visible string | Staging cold-start banner corrected from "Render's free tier" to platform-neutral phrasing; `ENVIRONMENT` reference corrected to Railway | FIXED LOCALLY |
| WRITE-11 | Defence Writing | LOW | Defence Writing Manual Chapter 4 (Punctuation), 6 (Document presentation), 14 (Projection), 23 (Editing), 24 (Publications) — paragraph-level citation pass applied to all TMS UI copy and help text | Only table-of-contents level reviewed; paragraph-level rules not yet extracted or applied; headings/lists/chart-construction guidance currently implemented from program addendum text, not yet cross-cited against Manual paragraphs | NOT STARTED |

---

## 7. P0 / P1 Functional Defects

**Scope:** Confirmed defects or architectural gaps that block correct operation for real user journeys.
Items marked P0 are potentially showstopping for V1 if their scope is confirmed wider than currently
known. Firefox and the Planning Workspace 404 are uninvestigated — root causes unknown.

| ID | AREA | SEVERITY | REQUIREMENT | CURRENT STATE | STATUS |
|---|---|---|---|---|---|
| DEF-01 | Defect | P0 | Firefox authentication — Planning Workspace cross-origin session handoff works in Firefox | Confirmed implemented: `index.html:4347-4354` — FF-01 fix already in place; uses `#t=<token>` hash fragment handoff bypassing SameSite=None cookie (which Firefox ETP blocks). `main.tsx` reads hash before React renders. Gap register was stale. | CLOSED |
| DEF-02 | Defect | P0 | Planning Workspace unexpected 404 — specific navigation path causes an unhandled 404 | Not reproduced; not investigated; exact triggering route unknown | NOT STARTED |
| DEF-03 | Defect | P1 | Planning Workspace "Your scope" card — displays raw Wing ID and Squadron ID UUIDs instead of Wing code / name | `SessionInfo` in `api/types.ts` has `wing_code` / `squadron_code`; `Admin.tsx:17-18` uses `session.wing_code` / `session.squadron_code` directly — confirmed correct | CLOSED |
| DEF-04 | Defect | P1 | Facilitator rank stored as uncontrolled free text (`Facilitator.rank` String) — no link to a canonical AAFC rank catalogue, no validation | Implemented commit `16f6bce`: `_AAFC_RANKS` catalogue in training.py; `GET /api/facilitators/ranks` endpoint; `_normalise_rank()` applied on create/update/import; frontend datalist populated from API. 8 regression tests added. | FIXED LOCALLY |
| DEF-05 | Defect | MEDIUM | Legacy "Annual Program" stale text — `connected-frontend/index.html:6842` still says "Annual Program" linking to `nav('planning-year')`; functional redirect exists (`nav('planning-year')→'activities'`) but text misleads users | Confirmed resolved: `nav('planning-year')` as user-visible text no longer exists in index.html; all remaining references are code comments. Gap register was stale (original line number drifted). | CLOSED |
| DEF-06 | Defect | MEDIUM | Wing-onboarding CLI-only — no HTTP API endpoint for Wing provisioning; requires direct server/DB access | `second_wing_seed.py` is CLI-only; no API path; appropriate for Level B staging, not National | NOT STARTED |
| DEF-07 | Defect | MEDIUM | Multi-Wing report cross-scope verification — Wing reports show only their Wing's data; National aggregates all Wings; no cross-Wing data leak | No synthetic second Wing in staging; multi-Wing aggregation path unproven; blocked on Level B Wing activation | NOT STARTED |
| DEF-08 | Defect | MEDIUM | Celery export task (`generate_export`) is a stub — sync fallback records success without writing a real file; no object-storage or presigned-URL path | `dispatcher.py` tries Celery; falls back to sync stub; Redis not provisioned | IMPLEMENTING |
| DEF-09 | Defect | MEDIUM | Background job polling UI — no frontend polling of `GET /api/jobs/{id}` when an async export is in flight; users cannot tell whether a large export is still running | `JobStatus` endpoint exists; no polling UI in either frontend | NOT STARTED |
| DEF-10 | Defect | MEDIUM | DB-backed general rate limiter — in-memory `_api_hits` degrades proportionally with Gunicorn worker count; `GUNICORN_WORKERS ≤ 2` operational cap enforced until Option A (DB-backed) is implemented | Assessed in `15_rate_limiting_assessment.md`; Option A designed; not yet implemented | NOT STARTED |
| DEF-11 | Defect | MEDIUM | Per-account rate limiting on non-login API endpoints | Only login has per-account lockout (`AccessCode.failed_attempts`, `locked_until`); all other endpoints have per-IP limiting only | NOT STARTED |
| DEF-12 | Defect | LOW | Maintenance mode frontend banner — users already in session see no in-app banner when write-block is active | Login-block and write-block implemented; no banner rendered to users already authenticated | NOT STARTED |
| DEF-13 | Defect | LOW | Maintenance mode expected return time — no return-time field in `SystemSetting`; cannot be communicated to users | Maintenance message is admin-settable text; no structured return-time field exists | NOT STARTED |
| DEF-14 | Defect | LOW | Maintenance mode Celery drain — in-flight jobs may fail silently if write-block activates mid-task | Not implemented; no drain step in maintenance activation sequence | NOT STARTED |
| DEF-15 | Defect | MEDIUM | `ENVIRONMENT=staging` in production Railway config (DEFECT-003) — `is_production` and `validate_for_production()` key off this value; risks production safety checks not triggering | Code fix merged; Railway production env var not corrected; requires System Admin action | HUMAN GATE |

---

## 8. Visual Design & Accessibility

**Scope:** Axe staging tests (34 tests across `tools/playwright-staging/`) verify WCAG rules but are
not in main CI. Level A does not require formal WCAG certification. Accessibility automation in CI
and a formal conformance declaration are Level B/C requirements. Shared design tokens are Level B.

| ID | AREA | SEVERITY | REQUIREMENT | CURRENT STATE | STATUS |
|---|---|---|---|---|---|
| VIS-01 | Visual | MEDIUM | Shared CSS design tokens — Main TMS (`--blue`, `--dark`) and Planning Workspace (`--aafc-blue`, `--aafc-dark-blue`) use divergent token names on the same AAFC VIG palette | Both frontends share the same underlying hex values; token names differ; Level B requirement; deliberate architectural decision to surface to user, not silently merge | IMPLEMENTING |
| VIS-02 | Accessibility | HIGH | Axe automation in main CI — accessibility checks run on every push, not only in staging-specific scripts | `a11y-staging.spec.ts` (25 tests) and `a11y-wcag.spec.ts` (9 tests) in `tools/playwright-staging/`; not wired into `frontend/e2e/` suite or any CI workflow | NOT STARTED |
| VIS-03 | Accessibility | MEDIUM | High-contrast mode — `forced-colors` / `prefers-contrast: more` media queries honoured throughout both frontends | Not tested; no high-contrast CSS overrides in either frontend | NOT STARTED |
| VIS-04 | Accessibility | MEDIUM | Keyboard-only workflow coverage — all primary workflows completable without a pointer device | Partial: 25 Axe staging tests include keyboard focus checks; full keyboard-only walkthroughs not verified for any workflow end-to-end | IMPLEMENTING |
| VIS-05 | Accessibility | MEDIUM | SC 1.4.3 Color Contrast (WCAG AA) — all text/background pairs meet 4.5:1 minimum (3:1 for large text) | `a11y-wcag.spec.ts` tests with Axe `color-contrast` rule in staging for all four roles; not in main CI | STAGING VERIFIED |
| VIS-06 | Accessibility | MEDIUM | SC 1.4.10 Reflow at 320 px — content usable without horizontal scrolling at 320 px viewport | `a11y-wcag.spec.ts` tests this in staging; not in main CI | STAGING VERIFIED |
| VIS-07 | Accessibility | MEDIUM | SC 1.4.4 Resize Text — all content functional at 200% zoom (640 px simulation) | `a11y-wcag.spec.ts` tests this in staging; not in main CI | STAGING VERIFIED |
| VIS-08 | Accessibility | LOW | No-duplicate-IDs and aria-label rules verified for all four roles (system_admin, sqn_admin, wing_admin, national_admin) | `a11y-staging.spec.ts` covers all four roles; not in main CI | STAGING VERIFIED |
| VIS-09 | Accessibility | LOW | WCAG 2.1 AA formal conformance declaration for National rollout | Staging Axe tests provide technical evidence; formal declaration document not drafted | NOT STARTED |
| VIS-10 | Visual | LOW | Multi-Wing E2E playwright tests — visual and data-scope verification with a second Wing activated in staging | 266 E2E tests cover core single-Wing workflows; multi-Wing scope tests require Level B Wing activation | IMPLEMENTING |

---

## 9. Security & Hardening

**Scope:** OWASP Top 10 audit (`15_security_hardening_review.md`) rated A01–A05, A07–A10 as complete
or improved. Remaining gaps are A06 (dependency scanning not in CI), A09 (external alerting), and
production-deployment verification steps that require a live HTTP check, not code inspection alone.
Four gaps require System Admin action as Human Gates.

| ID | AREA | SEVERITY | REQUIREMENT | CURRENT STATE | STATUS |
|---|---|---|---|---|---|
| SEC-01 | Security | HIGH | CSRF env var verification — System Admin confirms `COOKIE_SAMESITE=none` and `COOKIE_SECURE=true` in Railway production dashboard; confirms `CORS_ALLOWED_ORIGINS` has no wildcard | Code default is `lax`; Planning Workspace cross-origin session breaks without this env var; documented in `20_csrf_assessment.md` | HUMAN GATE |
| SEC-02 | Security | HIGH | Backup key custody — GPG private key stored offline, GitHub Secrets updated, daily backup manually confirmed, first restore test result reviewed | Public key committed to repo; `v1_go_no_go_checklist.md §C` documents steps; not yet completed by System Admin | HUMAN GATE |
| SEC-03 | Security | HIGH | DR rehearsal — disaster recovery rehearsal run per `19_disaster_recovery_rehearsal.md`; result recorded in Evidence Table | Procedure written; never run | HUMAN GATE |
| SEC-04 | Security | CRITICAL | External penetration test — grey-box, 5-day engagement per `22_pen_test_scope.md`; Critical and High findings remediated before National rollout | Scope documented; vendor not engaged; budget and organisational approval required | HUMAN GATE |
| SEC-05 | Security | MEDIUM | Alerting on failed-login spike — active notification when login failure rate exceeds threshold in a rolling window | Structured JSON access log with `X-Request-ID` exists; no alert rule wired to any monitoring channel | NOT STARTED |
| SEC-06 | Security | MEDIUM | Alerting on 5xx error rate above threshold | Same gap; structured logs exist; no external alert rule configured | NOT STARTED |
| SEC-07 | Security | LOW | Alerting on daily backup workflow failure — active channel beyond GitHub Actions default email | GitHub Actions emails on failure; no Slack/PagerDuty/Teams alert channel configured | NOT STARTED |
| SEC-08 | Security | MEDIUM | Dependency vulnerability scanning in CI — `pip-audit` (backend) and `npm audit --audit-level=high` (React frontend) in an automated workflow before each release | Manual pre-release only; not in any CI workflow; A06 gap identified in security hardening review | NOT STARTED |
| SEC-09 | Security | MEDIUM | CSP `connect-src` runtime injection verified in deployed connected-frontend nginx response | `nginx.conf` and `docker-entrypoint.sh` updated in Phase 15 security hardening; staging verification post-deploy not recorded | IMPLEMENTING |
| SEC-10 | Security | LOW | `Permissions-Policy` header confirmed in production connected-frontend nginx HTTP response | Added in Phase 15; not verified by live HTTP check in production post-deploy 2026-08-12 | IMPLEMENTING |
| SEC-11 | Security | MEDIUM | Token version revocation triggered automatically on account disable or role change — not only on code reset | Revocation mechanism exists (increment `token_version`); no automated hook on disable/role-change; documented as a manual operator step in support runbook | IMPLEMENTING |
| SEC-12 | Security | LOW | Quarterly DR rehearsal schedule established — first rehearsal date set and rehearsal completed | Post-release action H4; not yet scheduled | NOT STARTED |
| SEC-13 | Security | LOW | HSTS header confirmed in production backend HTTP response — injected by `security_headers` middleware when `is_production=True` | Code gate exists; not verified by live HTTP check post-production deploy | IMPLEMENTING |
| SEC-14 | Security | LOW | `/docs`, `/redoc`, `/openapi.json` confirmed absent from production via live HTTP request | Code gate (`is_production` check) exists; not verified by live HTTP request post-deploy | IMPLEMENTING |

---

## 10. Documentation & Release Assurance

**Scope:** V1 deployed 2026-08-12. Post-release actions H2–H5 are due within 7 days of deployment.
Level B and C documentation items (Tier 3 reports, Wing onboarding API, capability manifest refresh)
are not yet started. The support runbook and year rollover procedure are CLOSED at Level A.

| ID | AREA | SEVERITY | REQUIREMENT | CURRENT STATE | STATUS |
|---|---|---|---|---|---|
| DOC-01 | Docs | HIGH | Support runbook — 280-line operator runbook covers common failures, Railway deploy, account recovery, DR steps, incident response; written for non-developer operators | `25_support_runbook.md` complete and reviewed; ownership table not yet filled (H2) | CLOSED |
| DOC-02 | Docs | HIGH | Year rollover E2E procedure proven in staging — 10/10 tests pass; annual operator procedure documented | `test_year_rollover_e2e.py` 10/10 pass; `08_year_rollover_procedure.md` complete; not yet exercised in production | STAGING VERIFIED |
| DOC-03 | Docs | MEDIUM | Playwright E2E — multi-Wing scope tests pass with a second Wing activated in staging | 266 E2E tests cover core single-Wing workflows; multi-Wing tests gated on Level B | IMPLEMENTING |
| DOC-04 | Docs | HIGH | Named support ownership — `25_support_runbook.md` Part 1 ownership table completed with named contacts | Support runbook content complete; ownership table empty; post-release action H2 | HUMAN GATE |
| DOC-05 | Docs | HIGH | Weekly restore test — first-week `test-restore-postgresql.yml` GitHub Actions pass confirmed after production deploy | Workflow exists and ran in staging; post-production first pass not yet confirmed; post-release action H3 | NOT STARTED |
| DOC-06 | Docs | MEDIUM | First quarterly DR rehearsal run and result recorded in Evidence Table | Not yet run; post-release action H4 | NOT STARTED |
| DOC-07 | Docs | MEDIUM | V1 go-live communicated to 7WG beta testers | Not yet done; post-release action H5 | NOT STARTED |
| DOC-08 | Docs | HIGH | Beta feedback register populated — all 7WG beta-tester findings classified; critical/high items resolved | `02_beta_feedback_register.md` template exists; items not yet populated (requires beta testers) | HUMAN GATE |
| DOC-09 | Docs | LOW | Defence Writing Manual Chapters 4/6/14/23/24 paragraph-level citation pass applied to all TMS UI copy | Only table-of-contents level reviewed; paragraph-level rules not yet extracted or applied (see WRITE-11) | NOT STARTED |
| DOC-10 | Docs | HIGH | Wing onboarding runbook §0 governance gate — organisational approval obtained before activating any Wing beyond 7WG in production | `10_wing_onboarding_runbook.md` complete; governance gate not yet passed for any second Wing | HUMAN GATE |
| DOC-11 | Docs | MEDIUM | Report catalogue Tier 3 — National-level reports defined, implemented, and verified with multi-Wing data | Tier 1 (5 sqn) implemented; Tier 2 (5 wing) wired; Tier 3 requires Level B multi-Wing staging data | NOT STARTED |
| DOC-12 | Docs | MEDIUM | Wing onboarding HTTP API — endpoint equivalent of `second_wing_seed.py` for provisioning a Wing without direct server/DB access | CLI seed only; no API path; Level B requirement | NOT STARTED |
| DOC-13 | Docs | LOW | Capability manifest regenerated after Training Class model additions (v48–v50) — diff confirms no route or table removed | 1553 tests pass; `capability_manifest_current.json` not regenerated post-v48–v50; regeneration is a one-command step | NOT STARTED |
| DOC-14 | Docs | MEDIUM | CEA import / CEA relationship documentation — `export_import.py` handles CEA imports; how CEA activities relate to curriculum items and Training Classes under the new model is not yet documented for operators | CEA import router exists; relationship to TrainingClass/SessionAudience not yet described in any operator-facing runbook | NOT STARTED |
| DOC-15 | Docs | LOW | Role matrix updated to include Training Class operations — who can create, archive, split, and merge a TrainingClass; whether wing_admin can act cross-squadron | `docs/role_matrix.md` predates Training Class model; no Training Class rows exist | NOT STARTED |

---

## 11. Human Gates

These gaps require a decision, approval, or manual action by a named human authority. Engineering
work is either complete (awaiting human confirmation) or blocked until the decision is made.
No engineering work is underway on these items.

| ID | AREA | SEVERITY | REQUIREMENT | CURRENT STATE | STATUS |
|---|---|---|---|---|---|
| HG-01 | Human Gate | HIGH | Individual accountability — choose Option A (individual accounts), Option B (claimed display name), or Option C (defer); record decision with authority name and date | Options in `05_individual_accountability_options.md`; decision record not filled; no individual attribution exists today; Option C (defer) recommended for V1 | HUMAN GATE |
| HG-02 | Human Gate | HIGH | Multi-Wing load test — 250-user test with synthetic second Wing in staging; second Wing must be activated in staging DB; governance gate §0 of Wing onboarding runbook must be passed first | Procedure in `17_multi_wing_load_test_procedure.md`; staging second Wing not provisioned | HUMAN GATE |
| HG-03 | Human Gate | HIGH | CSRF env var verification — System Admin confirms `COOKIE_SAMESITE=none`, `COOKIE_SECURE=true`, and no-wildcard `CORS_ALLOWED_ORIGINS` in Railway production dashboard | Assessed and documented in `20_csrf_assessment.md`; verification is a manual Railway dashboard step | HUMAN GATE |
| HG-04 | Human Gate | HIGH | Backup key custody — GPG private key stored offline, GitHub Secrets updated, daily backup confirmed, first restore test pass reviewed | Steps in `v1_go_no_go_checklist.md §C`; not yet completed by System Admin | HUMAN GATE |
| HG-05 | Human Gate | HIGH | DR rehearsal — System Admin runs disaster recovery rehearsal per `19_disaster_recovery_rehearsal.md`; result recorded in Evidence Table | Procedure complete; never run | HUMAN GATE |
| HG-06 | Human Gate | CRITICAL | External penetration test — vendor selected and engaged; grey-box 5-day engagement completed; critical and high findings remediated before National rollout | Scope in `22_pen_test_scope.md`; vendor not engaged; budget/organisational approval required | HUMAN GATE |
| HG-07 | Human Gate | CRITICAL | Data governance decisions — all 9 decisions resolved: personal data policy, cadet data policy, audit log access, retention periods, archive/delete requirements, incident reporting, production data ownership, support ownership, account removal | Template with 9 pending decisions exists; all 9 unresolved; required before storing personal data at National scale | HUMAN GATE |

---

## Level Gate Summary

### Level A — 7 Wing Operational V1

**Status: DEPLOYED** — commit `756e65e`, production, 2026-08-12. Alembic head v51 confirmed.
All engineering gates closed. Human post-release actions due within 7 days:

| Action | Item | Due |
|---|---|---|
| H2 | Fill named ownership table in `25_support_runbook.md` Part 1 | Within 7 days |
| H3 | Confirm first weekly restore test GitHub Action passed | Within 7 days |
| H4 | Schedule first quarterly DR rehearsal | Within 7 days |
| H5 | Communicate V1 go-live to 7WG beta testers | Within 7 days |

Human gates HG-01 (individual accountability decision), HG-03 (CSRF env vars), HG-04 (backup key custody), HG-07 (data governance) remain open per `v1_go_no_go_checklist.md`.

### Level B — Second Wing Pilot (additional requirements beyond Level A)

| Gaps | Description |
|---|---|
| CLASS-12, CLASS-13, CLASS-14 | Training Class frontend gaps and Getting Started step |
| DEF-06, DOC-12 | Wing onboarding API (not CLI-only) |
| DEF-07, DOC-11 | Multi-Wing reports cross-scope verified |
| DEF-10, DEF-11 | DB-backed rate limiter for higher GUNICORN_WORKERS |
| HG-01 | Individual accountability model implemented |
| HG-02 | 250-user multi-Wing load test |
| HG-06 | External pen test (recommended before second Wing) |
| HG-07 | Data governance decisions resolved |
| VIS-01 | Shared design tokens complete |
| VIS-10 | Multi-Wing E2E playwright tests |

### Level C — National Readiness (additional requirements beyond Level B)

| Gaps | Description |
|---|---|
| VIS-02, VIS-09 | Axe automation in main CI; WCAG 2.1 AA formal declaration |
| SEC-04 / HG-06 | External pen test REQUIRED (not only recommended) |
| DOC-11 | Tier 3 National reports implemented and verified |
| DEF-08, DEF-09 | Async export pipeline complete with frontend polling |
| SEC-05, SEC-06 | Full alerting stack operational |
| DASH-03 | Full metric dictionary documentation |

---

## Decision Log

| Gap | Decision | Date | Authority |
|---|---|---|---|
| GAP-03 | Adopt `training_areas` as canonical location; `planning_locations` deprecated as adapter; Phase 2 table drop deferred to Level B | 2026-08-12 | `04_canonical_data_model.md` |
| GAP-05 | Individual accountability: Option C (defer to Level B/National) recommended for V1 | — | MANUAL APPROVAL REQUIRED — CO / Wing SOCAD |
| GAP-20 | CSRF: CORS + SameSite=None sufficient; CSRF tokens not required given Bearer token architecture; production env var verify still required by System Admin | 2026-08-12 | `20_csrf_assessment.md` |
| GAP-22 | External pen test budget and scope | — | MANUAL APPROVAL REQUIRED |
| GAP-23 | All 9 data governance decisions | — | MANUAL GOVERNANCE REQUIRED — CO / Data Authority |
| WRITE-* | Training Summary → Dashboard merge authorised; Training Summary nav tab may be removed only after content/action parity is proven and a redirect is preserved; no other feature removal pre-authorised | 2026-08-04 | User instruction; recorded in `.claude/rules/capability-preservation.md` |

---

## Cross-Reference: Original 25-Gap Matrix to This Register

| Original Gap | Title | Register IDs | Status |
|---|---|---|---|
| 1 | Legacy page retirement | DEF-05 | NOT STARTED |
| 2 | Visual / session unification | VIS-01, VIS-10 | IMPLEMENTING |
| 3 | TrainingArea / PlanningLocation | Decision log | CLOSED |
| 4 | Facilitator records | (Capability preserved; no open gap) | CLOSED |
| 5 | Individual accountability | HG-01 | HUMAN GATE |
| 6 | Optimistic locking | (Phase 7 complete; all critical models) | CLOSED |
| 7 | 7WG hardcodes | (Bootstrap parameterised) | CLOSED |
| 8 | Multi-Wing onboarding | DEF-06, DOC-12 | NOT STARTED |
| 9 | Multi-Wing reports | DEF-07 | NOT STARTED |
| 10 | Report catalogue | DASH-01, DASH-02, DOC-11 | IMPLEMENTING |
| 11 | Year rollover | DOC-02 | STAGING VERIFIED |
| 12 | Playwright E2E | DOC-03, VIS-10 | IMPLEMENTING |
| 13 | Accessibility automation | VIS-02–VIS-09 | IMPLEMENTING |
| 14 | Load testing | HG-02 | HUMAN GATE |
| 15 | Distributed rate limiting | DEF-10, DEF-11 | NOT STARTED |
| 16 | Async imports/exports | DEF-08, DEF-09 | IMPLEMENTING |
| 17 | Monitoring and alerting | SEC-05, SEC-06, SEC-07, SEC-13 | NOT STARTED |
| 18 | Maintenance mode | DEF-12, DEF-13, DEF-14 | NOT STARTED |
| 19 | Session revocation | SEC-11 | IMPLEMENTING |
| 20 | CSRF controls | SEC-01, HG-03 | HUMAN GATE |
| 21 | Backup and restore | SEC-02, SEC-03, HG-04, HG-05 | HUMAN GATE |
| 22 | External pen test | SEC-04, HG-06 | HUMAN GATE |
| 23 | Data governance | HG-07 | HUMAN GATE |
| 24 | Beta feedback register | DOC-08 | HUMAN GATE |
| 25 | Support runbook | DOC-01, DOC-04 | CLOSED |
