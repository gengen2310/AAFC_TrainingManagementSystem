# AAFC TMS — Known Limitations

Beta release v17.1. All items listed here are known, accepted, and either deferred or under active mitigation. None are silent.

Created: 2026-07-14.

---

## Data Model Limitations

### DL-01: Physical Spaces Not Unified — RESOLVED 2026-07-24

- **Description (historical)**: Rooms and training areas were stored in two separate tables — `training_areas` (serving the connected-frontend Resources page) and `planning_locations` (serving the Planning Workspace Rooms tab). A squadron that added a room via Resources would not see it in the Planning Workspace's Rooms tab, and vice versa.
- **Resolution**: Fixed as Phase 1 of the master transformation plan. `/api/planning/locations` (list/create/update) now reads and writes `training_areas` directly instead of the separate `planning_locations` table — the same "shared table via a different router" pattern already used correctly for facilitators. Response JSON shape unchanged; no frontend changes required. Verified live: a room created in either app now appears immediately in the other.
- **Bonus finding**: this merge also fixed a real, silent bug — `create_session`/`update_session`'s room-resolution logic only ever looked up `TrainingArea` rows, so a room picked from Planning Workspace's Rooms tab (previously backed by `planning_locations`) silently failed to attach to a session (no error, just an unassigned room). This is now fixed as a side effect of the merge.
- **Also found and fixed while auditing this area**: `GET /years/{id}/facilitators/{id}/workload` (backs Planning Workspace's Facilitator Leave workload stats) queried `ScheduledSession`, a model with no live create/update path anywhere in the codebase — it always silently returned zero workload. Rewritten to use the same `TrainingSession`-based join `list_missions` already uses.
- **Not touched**: the `planning_locations` table and `ScheduledSession` model themselves are left in place (no migration, no drop) — nothing in any live, reachable code path depends on them, so leaving them avoids any data-loss or FK-constraint risk. They can be dropped in a later, purely cosmetic cleanup pass.

### DL-02: Facilitators Not Unified — CORRECTED, NOT A REAL DUPLICATION

- **Original description (incorrect)**: This entry previously claimed `facilitators` (training module) and `planning_facilitators` (Planning Workspace) were separate tables requiring double data entry.
- **Correction (2026-07-24 master transformation plan review)**: There is only one `Facilitator` model/table (`facilitators`). Planning Workspace's `/api/planning/facilitators` endpoint (`list_planning_facilitators`) reads that *same* table via a different router function — confirmed by direct model/migration inspection: no `planning_facilitators` table or `PlanningFacilitator` model class exists anywhere in `backend/app/models/` or any Alembic migration. The original claim (and the equivalent claim in `docs/beta/28_authoritative_data_model.md`) was never correct. **No merge is needed — there is nothing to merge.**
- **Action**: this entry is kept (rather than deleted) specifically as a record that the claim was investigated and found false, so it doesn't get re-reported as a live gap in a future pass without re-checking.

### DL-03: Parade Dates and Parade Nights Are Separate

- **Description**: A `ParadeDate` (planning layer) and a `ParadeNight` (operational layer) are different records linked via FK. Creating a planning year does NOT automatically create parade nights. Both must be initialised separately.
- **Impact**: Low. This is intentional architecture (plan without committing sessions). Documented in user flows.
- **Workaround**: Use the Parade Night Generator in the connected-frontend.
- **Resolution**: Not planned — intentional design.

### DL-04: CEA Import Exists as Two Separate, Differently-Permissioned Pipelines

- **Description**: connected-frontend's "Import CEA" (Activities page) and Planning Workspace's "Import CEA" (Activities tab) are genuinely separate pipelines, writing to different models, discovered during the 2026-07-24 master transformation plan review (not previously documented anywhere):
  - **Legacy pipeline** (`POST /api/activities/import-cea`, `training.py`): writes to the `Activity` model, squadron-scoped, dedups only by `cea_seq_nr`, **no review/classification workflow at all** — a row is either created or silently skipped as a duplicate. Permission: `sqn_admin` or higher (blocks only `sqn_general`/`wing_viewer`/`national_viewer`/`auditor`).
  - **Reviewed pipeline** (`POST /api/planning/years/{year_id}/cea/import`, `planning.py`): writes to the `CeaActivity` model, wing-scoped via `CeaImportBatch`, has a full needs-review/classify workflow and smarter name+date-key dedup fallback. **Permission: `wing_admin`, `national_admin`, or `system_admin` only — `sqn_admin` is explicitly excluded.**
- **Why this was not simply merged in the same pass as DL-01**: the two pipelines have a genuine role-permission mismatch, not just a data-model difference. Redirecting connected-frontend's "Import CEA" button to call the reviewed pipeline would **remove CEA import capability from every `sqn_admin` user** — a real regression, not a safe consolidation. Loosening the reviewed pipeline's role gate to include `sqn_admin` is also not a decision to make unilaterally: it may be deliberately wing-admin+-gated because CEA data is inherently wing-level (a single wing-level import feeding all its squadrons), in which case relaxing it would let a squadron admin import wing-scoped data — a different kind of regression.
- **Impact**: Medium. A squadron using the legacy pipeline gets no review/classification step and a weaker dedup than the same data would get via the reviewed pipeline; the two pipelines' resulting rows are never reconciled with each other.
- **Resolution — blocked on a product decision, not a technical one**: someone with product/organisational authority needs to decide one of:
  1. CEA import becomes exclusively a `wing_admin`+ responsibility (retire the legacy squadron-level pipeline; requires user communication since it removes a capability `sqn_admin` users have today), or
  2. The reviewed pipeline's role gate is deliberately widened to include `sqn_admin` for squadron-scoped imports (needs confirmation this doesn't violate the wing-scoping the `CeaImportBatch`/`CeaActivity` model design assumes), or
  3. Both pipelines are kept, but the legacy one is upgraded in place to use the same review/classification model and stronger dedup logic as the reviewed pipeline, without touching either one's role gate (more engineering work, but zero capability or permission change).
- **Not done**: no code change was made for this item. Flagging it accurately, with the actual blocker named, was judged more valuable than forcing a guess at a decision that affects who can do a real, currently-working task.

---

## Accessibility Limitations

### AL-01: Curriculum-Link Search Dropdown Has No Real Keyboard Navigation

- **Description**: Planning Workspace's curriculum-link search dropdown (`PlanningRightDrawer.tsx`, the "Curriculum link" search box on session/anchor detail) has no arrow-key/Enter selection — the dropdown items only respond to a mouse. Found during the 2026-07-24 accessibility widening pass (Phase 7) via `eslint-plugin-jsx-a11y`, which flagged the item's `onMouseDown` handler with no keyboard equivalent.
- **Why not fixed in the same pass**: the items deliberately use `onMouseDown` rather than `onClick` so selection fires before the search input's `onBlur` closes the dropdown — a timing-sensitive pattern. Properly fixing this means implementing a real combobox interaction model (ArrowUp/ArrowDown to move a highlighted option, Enter to select, Escape to close) without breaking that blur/mousedown timing, which needs live verification of a working feature rather than a mechanical lint fix.
- **Impact**: Low-medium. A keyboard-only user can still link curriculum via the same underlying data (no data is unreachable), but must currently do so through some other path; the search box itself isn't operable without a mouse.
- **Resolution**: Not done this pass. `eslint-disable` with a `TODO(a11y follow-up)` comment left in place at the call site so the gap stays visible in code, not just here.

### AL-02: Pre-existing Test Bugs Found (Not Introduced This Pass, Not Fixed)

Found while widening `frontend/e2e/accessibility.spec.ts` coverage (Phase 7) and reproduced against a clean pre-Phase-7 checkout to confirm they predate this work:
- `e2e/facilitators.spec.ts` › "facilitator leave can be recorded via API" asserts `body.facilitator_id` but the real response shape is `body.leave.facilitator_id` — a test bug, not a backend defect (the API is already returning the more informative nested shape).
- `e2e/reports.spec.ts` › "facilitator load card renders without error" and "not delivered card renders without error" use an immediate `.isVisible().catch(() => false)` check with no wait/retry, so they can read the DOM before the async report data has rendered — a flaky-by-design pattern, not a rendering bug (manually confirmed the tables render correctly with real data).
- Neither was fixed in this pass — out of scope for an accessibility-coverage widening — but recorded here since they were newly discovered, not previously tracked.

---

## Security Limitations

### SL-01: Production ENVIRONMENT Variable Mismatch

- **Description**: The production backend is running with `ENVIRONMENT=staging` instead of `ENVIRONMENT=production`. The `validate_for_production()` fail-close check in `main.py` is therefore not running in production, which means: (a) the `bootstrap-staging` endpoint is reachable by `system_admin`; (b) some production-only guards may not fire.
- **Severity**: HIGH.
- **Status**: Code fix deployed to branch. Variable change requires explicit approval before applying to Railway production environment.
- **Mitigation**: The bootstrap endpoint requires `system_admin` authentication. The risk is constrained to internal admins.
- **Defect**: DEFECT-003.

### SL-02: IDOR Gap on sqn_general Scope (Production)

- **Description**: The production backend does not enforce that `sqn_general` users can only access their own squadron's planning data. A `sqn_general` user who knows another squadron's planning year UUID could read that squadron's annual program, missions, and CEA data.
- **Severity**: BLOCKER.
- **Status**: Fixed on branch (`67e8f13`). Not yet deployed to production. Production deployment requires explicit approval.
- **Defect**: DEFECT-001.

### SL-03: No CSRF Protection for State-Changing Endpoints

- **Description**: Authentication uses `HttpOnly` cookie-based sessions. No CSRF token is required for state-changing requests. `SameSite=None` is set (required for cross-origin embedded iframe use case), which reduces but does not eliminate CSRF risk.
- **Impact**: Low in practice. The application is deployed on Railway with CORS locked to specific allowed origins; cross-site requests from third-party origins are blocked by CORS policy. The embedded iframe mode is the primary reason for `SameSite=None`.
- **Workaround**: CORS whitelist is the primary mitigation.
- **Resolution**: Adding double-submit CSRF tokens is the next hardening step, deferred to post-beta.

---

## Functional Limitations

### FL-01: Planning Workspace Not in Production (Stale Build)

- **Description**: The Planning Workspace (React, `aafc-tms-planning-workspace-preview`) has a stale build in production. The Dockerfile was broken (DEFECT-005); a fix is on the branch but not deployed.
- **Impact**: HIGH. Users accessing `/planning` in production may see outdated UI or errors.
- **Status**: Fix on branch. Production deployment requires explicit approval.
- **Update (2026-07-23)**: root-caused and fixed for **staging** — see `docs/ui/final_ui_root_cause.md`. Staging was also stale (backend/frontend deployed 2026-07-21, Planning Workspace 2026-07-14) purely because nobody redeployed after later commits landed, plus `PLANNING_WORKSPACE_URL` was never set on the staging backend (a separate cause, unrelated to the Dockerfile defect). Both fixed and verified live on staging via Playwright (`frontend/e2e-connected/`) and screenshots (`artifacts/final-beta-consolidation/d999623/`). **Production is still on the stale build and still requires the explicit approval this limitation already flagged.**
- **Defect**: DEFECT-005.

### FL-06: Mission Backlog does not surface Cancelled / Not-delivered lessons distinctly

- **Description**: The Planning Workspace's Mission Backlog (`BacklogContent` in `PlanningBottomDrawer.tsx`) filters curriculum items by `Unscheduled`/`Scheduled` only, driven by whether a session exists — not by session status. A session that was scheduled and later cancelled or not delivered shows as "Scheduled" in this view, with no distinct status tag and no direct reschedule action from Mission Backlog itself.
- **Impact**: Medium. Cancelled/not-delivered sessions are still visible and manageable from the Parade Nights page (each session shows its real status there), so nothing is silently lost — but staff working from Mission Backlog specifically won't see a ranked "needs rescheduling" view for these.
- **Status**: Not implemented. Identified during the 2026-07-23 UI consolidation pass; out of scope for that pass given its size (new status filter option, distinct tag styling, a reschedule action, retaining the original date/reason) relative to the rest of that pass's scope.
- **Resolution**: Post-beta, or a dedicated follow-up pass.

### FL-02: No Playwright End-to-End Coverage

- **Description**: No automated browser-level E2E tests are configured. All testing is unit/integration (backend) or TypeScript-only (frontend). Browser behaviour is verified manually.
- **Impact**: Low for regression catching; medium for confidence in release.
- **Workaround**: Manual verification checklist in `12_full_beta_release_readiness.md`.
- **Resolution**: Playwright setup deferred to post-beta.

### FL-03: No 100-User Load Test Completed

- **Description**: The 100-user concurrent load test (Phase 15) has not been run. Load test requires scheduling against the staging environment and explicit approval.
- **Impact**: Unknown concurrent user limits. Single-user response times are acceptable based on manual testing.
- **Status**: Not yet executed. Blocked pending approval.

### FL-04: Squadron Verification Matrix Not Complete

- **Description**: Browser-level login verification for all 16 squadrons in staging (Phase 2) has not been completed. This requires a browser session per squadron.
- **Impact**: Unknown. All 16 squadrons exist in the staging database (confirmed via health endpoint). Login flows have not been verified per-squadron in a browser.
- **Status**: Human-gated.

### FL-05: CEA Import Requires Manual File

- **Description**: The CEA import flow requires a user to provide a CEA-format CSV or XLSX file. There is no automated CEA data feed. Squadron staff must manually export from the CEA system and import via the Activities tab.
- **Impact**: Operational. Expected for this release.
- **Resolution**: Potential future automated feed; not in scope for v17.1.

---

## Infrastructure Limitations

### IL-01: Commit Hashes Not Tracked in Deployments

- **Description**: All Railway deployments are made via `railway up` from a local working tree (`meta.commitSha: null`). There is no deployment-to-commit traceability in the Railway dashboard.
- **Impact**: Low operational impact. Deployment IDs and timestamps are recorded as the authoritative record.
- **Resolution**: Switch to Railway GitHub integration for commit-linked deployments. Deferred.

### IL-02: SQLite Datetime Adapter Deprecation Warnings

- **Description**: SQLAlchemy emits a Python 3.12+ `DeprecationWarning` about the default `datetime` adapter when using SQLite in tests. This is a SQLAlchemy/SQLite compatibility issue, not a production issue (production uses PostgreSQL).
- **Impact**: None in production. Test output has 874 warnings; these are suppressed in CI with `--no-header -q`.
- **Resolution**: Update to SQLAlchemy `DateTime(timezone=True)` column types. Deferred.

### IL-03: Stash `stash@{0}` Unreviewed

- **Description**: A large prior-session WIP stash (709 insertions, 20 files) exists in the local repo as `stash@{0}`. It includes facilitator workload UI, N+1 fix in `ops.py`, and CSS for phase-progress and inter-term styling. It conflicts with current state and has not been applied.
- **Impact**: No production impact (stashes are local). Risk of confusion if applied incorrectly.
- **Resolution**: Review stash contents post-release before discarding.

---

## Scope of Known Limitations

| Category | Count | Highest severity |
|---|---|---|
| Data model | 3 | Medium |
| Security | 3 | BLOCKER (SL-02, awaiting deploy) |
| Functional | 5 | HIGH (FL-01, awaiting deploy) |
| Infrastructure | 3 | Low |
| **Total** | **14** | — |

All BLOCKER and HIGH items have fixes on the release branch awaiting production deployment approval.
