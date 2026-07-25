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

### AL-01: Curriculum-Link Search Dropdown Has No Real Keyboard Navigation — RESOLVED

- **Description**: Planning Workspace's curriculum-link search dropdown (`PlanningRightDrawer.tsx`, the "Curriculum link" search box on session/anchor detail) had no arrow-key/Enter selection — the dropdown items only responded to a mouse. Found during the 2026-07-24 accessibility widening pass (Phase 7) via `eslint-plugin-jsx-a11y`, which flagged the item's `onMouseDown` handler with no keyboard equivalent.
- **Resolution (master transformation plan Block 12)**: implemented the real ARIA 1.2 combobox-list pattern — the input carries `role="combobox"`/`aria-expanded`/`aria-controls`/`aria-activedescendant`, the dropdown is `role="listbox"`, each item is `role="option"`. ArrowUp/ArrowDown move a highlighted option (`aria-selected`, matching visual highlight), Enter selects it, Escape closes without selecting — all via a `handleSearchKeyDown` handler on the input, which owns focus throughout (the ARIA-correct model: listbox options are never separately focusable). The pre-existing `onMouseDown`-before-`onBlur` timing trick is unchanged; mouse selection still works exactly as before, `onMouseEnter` now also syncs the keyboard highlight so mouse and keyboard stay consistent.
- **Impact**: None remaining — a keyboard-only user can now search, navigate, and select without a mouse.
- The `eslint-disable` at the option `<div>` remains, now accurately justified (a comment explains why): the option itself intentionally has no independent keyboard handler because the combobox pattern puts all keyboard interaction on the input, not the option.

### AL-02: Pre-existing Test Bugs Found (Not Introduced This Pass)

Found while widening `frontend/e2e/accessibility.spec.ts` coverage (Phase 7) and reproduced against a clean pre-Phase-7 checkout to confirm they predate this work:
- `e2e/facilitators.spec.ts` › "facilitator leave can be recorded via API" asserted `body.facilitator_id` but the real response shape is `body.leave.facilitator_id` — a test bug, not a backend defect (the API is already returning the more informative nested shape). **RESOLVED** (2026-07-25, found and fixed while verifying DEFECT-004 below) — now asserts `body.leave.facilitator_id`.
- `e2e/reports.spec.ts` › "facilitator load card renders without error" and "not delivered card renders without error" — **RESOLVED, see DEFECT-003 below.**

### DEFECT-003 (2026-07-25): `reports.spec.ts` Timing-Race Tests — RESOLVED

Two bugs, both in the test file, not the app:
1. Both tests used an immediate `.isVisible().catch(() => false)` check with no wait/retry, so they could read the DOM before the async report query had resolved out of its Loading state (`<Loading />`, already a proper `role="status" aria-live="polite"` indicator — confirmed the UI does not need a clearer loading state; the gap was purely the test's lack of a wait). Fixed by replacing the one-shot check with `expect(table.or(empty)).toBeVisible({ timeout: 10000 })`, which uses Playwright's built-in polling.
2. A second, previously-undiscovered bug found while fixing the first: the facilitator-load test used `page.locator("table").nth(0)`, assuming the facilitator table is always the first `<table>` on the page. It isn't — the Curriculum coverage card above it also renders a `<table>` (inside a closed `<details>`, for the unscheduled-items list) whenever `unscheduled.length > 0`, which is present in the DOM but hidden. `nth(0)` picked that hidden table, not the facilitator one. Same risk existed for the not-delivered test's `.last()`. Fixed by locating each table by its actual header content (`Facilitator.*Sessions.*Delivered.*Risk` / `Code.*Reason`), matching the pattern already used elsewhere in the same file ("facilitator load table has correct columns when data is present").

Verified: both tests pass consistently across repeated runs against a freshly-restarted backend. Remaining intermittent failures observed only under rapid back-to-back full-suite reruns against the same never-restarted backend process are the general API rate limiter / login lockout (429s, login timeouts) — the pre-existing, separately-tracked DEFECT-004, not a regression from this fix.

### AL-03: `term` Number/String Contract Mismatch — RESOLVED (DEFECT-002, 2026-07-25)

- **Description**: `ParadeNight.term` (`backend/app/models/training.py`, `String(10)`) has always been a string (`"T1"`–`"T4"`), and `ParadeIn.term` (`backend/app/routers/training.py`) has always been typed `str | None`. `frontend/src/routes/ParadeNights.tsx`'s "New parade night" form used a numeric `<input type="number">` and sent `term: Number(term)` to the API — a genuine type mismatch, not test-only. `frontend/e2e/parade-nights.spec.ts` (4 tests, direct API calls) and `frontend/src/api/types.ts`/`api/index.ts` (declared `term: number`) mirrored the same wrong type.
- **Correction to this doc's prior entry**: the previous version of this entry claimed "Impact: Test-only... the real create-parade-night flow ... is unaffected." That was incorrect — `ParadeNights.tsx`'s real UI form was sending the wrong type (`Number(term)`) to the live API on every submission from any browser, not just in the test. The claim was never re-verified against the actual form's `onClick` handler before being written; corrected here rather than left standing.
- **A second, related bug found investigating this one**: `CurriculumItem.recommended_term` is the same `String(10)` `"T1"`-style value (confirmed via seed data, e.g. `("SNR-M01", ..., "T3", ...)` in `backend/app/seeds/seed_all.py`), but `frontend/src/api/types.ts` typed it `number | null`, and `frontend/src/components/planning/PlanningBottomDrawer.tsx`'s Mission Backlog "Rec. Term" column rendered `` `T${m.recommended_term}` ``, double-prefixing an already-`"T1"`-shaped value into `"TT1"` on screen.
- **Resolution**: Fixed both. `ParadeNights.tsx`'s term input is now a `<select>` of T1–T4 (matching connected-frontend's existing equivalent select), sending the string directly with no `Number()` coercion; `frontend/src/api/types.ts`/`api/index.ts` retyped `term`/`recommended_term` as `string`; `PlanningBottomDrawer.tsx` renders `recommended_term` directly, no re-prefix. `parade-nights.spec.ts` updated to send `"T4"`; two further pre-existing bugs in the same file were uncovered once the 422 stopped masking them (an assertion expecting HTTP `201` when this app's POST routes have always returned `200`, and two Playwright strict-mode locator ambiguities) — fixed alongside, all 4 originally-failing tests plus the whole file now pass. Added a new regression test (`navigation.spec.ts`) asserting no Mission Backlog Rec. Term cell can ever render outside `^T[1-4]$`; confirmed it fails with `"TT1"` against the pre-fix code and passes against the fix.

---

## Observability

### OB-01: No APM / Error-Tracking Tool Configured

- **Description**: Neither backend nor either frontend has an APM or error-tracking SDK (e.g. Sentry) wired in. Structured JSON access logs plus request-ID/response-time headers exist server-side; log aggregation is assumed to be handled externally by the deploy platform. There is no proactive error surfacing — diagnosing an issue today means reading logs after the fact, not getting paged/notified when it happens.
- **Why not implemented in this pass**: adding a real APM tool requires a third-party account and a secret (e.g. a Sentry DSN) that only the project owner can create — not something to add unilaterally without that account/credential existing first.
- **Status (2026-07-24)**: deliberately deferred, by explicit choice — asked and confirmed "skip for now, document only" rather than stub unused SDK plumbing or guess at a provider. Revisit once a provider/account is chosen; at that point the DSN is the only piece needed (env-var-gated init on both frontends + backend), not a design decision.

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

### IL-04 (DEFECT-004, 2026-07-25): Rate-Limiter Test Instability — RESOLVED for both root causes found; one edge case accepted

- **Description**: Repeated/rapid Playwright e2e runs against a long-lived local/CI backend process were tripping the general per-IP API rate limiter (300 req/60s) and/or the DB-backed per-IP login limiter, producing flaky 429s unrelated to the feature under test. The only prior workaround was restarting the backend between runs, which `backend/tests/conftest.py`'s own `client` fixture already avoided for pytest (in-process reset) but had no equivalent for Playwright, a separate process driving the backend over HTTP.
- **Root cause 1 -- no cross-run reset for Playwright**: fixed with `POST /api/system/reset-rate-limits` (`backend/app/routers/system.py`, system_admin only, rejected in production via `settings.is_prod` -- same guard as `bootstrap-staging`), doing over HTTP the same reset `conftest.py` already does in-process. Added to `main.py`'s `_RATE_LIMIT_EXEMPT` set so the endpoint stays reachable even while the general limiter it resets is itself currently tripped (otherwise a self-defeating deadlock). Wired into all four Playwright configs via a shared `globalSetup` (`frontend/playwright-global-setup.ts`) that logs in as system_admin and calls the reset endpoint once before a full suite run.
- **Root cause 2 -- CORS preflight requests silently counted against the budget**: found investigating why a *single* reset at suite-start still wasn't always enough. Confirmed live: a connected-frontend spec file made 220 `OPTIONS` (CORS preflight) requests alongside 253 real `GET`/`POST` requests in 45 seconds -- 473 total, over the 300/60s budget, even though the real operation count (253) was comfortably under it. `main.py`'s `api_rate_limit` middleware counted every non-exempt `/api/*` request regardless of method, so preflight overhead was silently halving the effective budget for any cross-origin caller -- **this affects real cross-origin production traffic identically to test traffic**, not just tests. Fixed by excluding `OPTIONS` from the count (`API_RATE_LIMIT`/`API_RATE_WINDOW_SEC` themselves are unchanged -- this corrects what counts as a request, not the threshold). Regression tests added (`backend/tests/test_rate_limiting.py`): confirmed failing before the fix, passing after. Result: the same connected-frontend suite dropped from ~45-72s (with intermittent 429-driven failures) to a consistent ~16s, 12/12 passing across 3 repeated runs.
- **Belt-and-braces**: even after fix 2, a single global reset was not always enough for the React app's 12-file, 87-test suite (28+ tests' worth of legitimate accumulated `GET`/`POST` traffic can still approach the 300/60s budget within one run). Added a `test.beforeAll()` reset (via shared helper `frontend/e2e-rate-limit-reset.ts`) to every spec file in `frontend/e2e/` and `frontend/e2e-connected/main-tms.spec.ts`, giving each file its own fresh budget. Verified: full 87-test `e2e/` suite run clean (86 passed, 1 pre-existing unrelated failure -- see below), zero rate-limit-related failures.
- **Bonus fix found along the way**: `e2e/facilitators.spec.ts`'s "facilitator leave can be recorded via API" test (the AL-02 item above) was fixed while verifying this suite end-to-end -- trivial one-line correction now that the surrounding suite was stable enough to isolate it cleanly.
- **Accepted edge case, not silently worked around**: if the IP `reset-rate-limits` would clear is *already* fully login-locked-out before it's called, the required system_admin login also fails (`login_blocked_db` blocks every login attempt from a locked IP, including a correct code, before the code is even checked) -- so this one scenario cannot self-heal via this endpoint. An authentication-bypass path for the reset endpoint (a shared-secret header skipping `require_system_admin`) was implemented, then deliberately reverted after review: it would have weakened the same login-lockout protection the endpoint exists to reset, which is a higher cost than the narrow inconvenience it would have solved. In practice this only occurs if a *previous* run left the IP locked out and its own reset was never reached; the existing 900s lockout window, or a one-time manual backend restart, remains the fallback for that specific case.

### DEFECT-005 (2026-07-25): CEA Import Pipeline Consolidation — retirement and permission gap RESOLVED; automatic squadron inheritance identified and deliberately deferred

- **Confirmed**: two CEA import pipelines existed. Legacy (`connected-frontend`): `POST /api/activities/import-cea`, wrote squadron-scoped `Activity` rows, had a preview-before-commit step but no *persisted* review/classification, dedup only by `cea_seq_nr` within one squadron. Current (Planning Workspace): `POST /api/planning/years/{year_id}/cea/import`, writes `CeaActivity` rows with a full needs-review/classify workflow, `CeaImportBatch` history, and a squadron-local hide/note overlay (`ActivityLocalHide`) that was already correctly scoped and untouched by this fix.
- **Retired the legacy pipeline** (as required): `POST /api/activities/import-cea` now responds `410 Gone` with a message pointing to Planning Workspace, rather than a bare `404` for any caller with the old URL bookmarked/scripted -- still requires authentication so it isn't accidentally made public. Removed connected-frontend's "Import CEA" button, its modal, and the three JS functions that called it (`openCeaImport`/`previewCeaImport`/`commitCeaImport`) -- confirmed zero console errors on page load and normal Activities-page rendering after removal (live browser check). Zero backend test coverage existed for the legacy endpoint before this change (confirmed via search), so retiring it carried no regression risk to the existing suite; 3 new regression tests added instead (`backend/tests/test_cea_consolidation.py`).
- **Closed a real permission gap**: `PATCH /api/planning/cea/{id}/classify` mutates the shared `CeaActivity` row directly (unlike `local-hide`, which only ever writes a squadron-local overlay row) and previously allowed `sqn_admin`. `CeaActivity.unit_id` is set only for manually-created, squadron-owned activities (`create_manual_activity`) -- never by CSV import, which leaves it null for a wing-wide activity. Because a wing_admin can import CEA data into *any* squadron's own `year_id` in their wing (`require_year_access`'s wing_admin branch checks only `wing_id`, not `unit_id`), that squadron's own sqn_admin could reach and reclassify a wing-imported, `unit_id=None` activity -- overwriting a wing-level classification decision. Fixed: a sqn_admin may still classify their own squadron's manual activity (`unit_id == p.squadron_id`), but is now rejected (403 `wing_wide_activity`) for any activity where `unit_id != p.squadron_id`, including every CSV-imported one. Verified live: reverted the fix, confirmed the new regression test fails (200 instead of 403) against the old code, restored the fix, confirmed it passes. 3 new tests cover the denial, the wing_admin-still-allowed case, and the regression guard that a sqn_admin's own manual activities are unaffected.
- **Deliberately deferred, not silently dropped**: "squadron inherits [wing-imported CEA activities] automatically" is not yet true. Today a squadron only sees `CeaActivity` rows tied to its own specific `planning_year_id` (`GET /years/{year_id}/cea/activities` filters by `planning_year_id` only) -- there is no wing-wide broadcast. Widening that read to also match `CeaActivity.wing_id` looked like a safe, additive fix at first (a superset of what's already returned), but investigation found a real blocker: `import_cea_csv`'s duplicate-detection is *also* scoped to `planning_year_id` only (`existing_by_cea_id`/`existing_by_name_date` built from a query filtered to one `year_id`). Widening reads to wing-wide without also reworking dedup to be wing-scoped would let the same CEA activity be imported once per squadron and then appear duplicated in the merged wing-wide view -- a real duplicate-protection regression, which the brief this work is under explicitly prohibits introducing to "get a fix in." Properly closing this needs a deliberate decision on the dedup/visibility model (e.g. importing once at wing level with squadrons reading a shared row, vs. current per-squadron-year rows), not a quick query change. Recorded here as a scoped, well-understood follow-up rather than left undiscovered.

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
