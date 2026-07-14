# AAFC TMS — Known Limitations

Beta release v17.1. All items listed here are known, accepted, and either deferred or under active mitigation. None are silent.

Created: 2026-07-14.

---

## Data Model Limitations

### DL-01: Physical Spaces Not Unified

- **Description**: Rooms and training areas are stored in two separate tables — `training_areas` (serving the connected-frontend Resources page) and `planning_locations` (serving the Planning Workspace Rooms tab). A squadron that adds a room via Resources will not see it in the Planning Workspace's Rooms tab, and vice versa. Users must duplicate entries.
- **Impact**: Medium. Squadrons using both apps may maintain two separate room lists.
- **Workaround**: Configure rooms in both places using the same names.
- **Resolution**: Post-beta. Merge path documented in `28_authoritative_data_model.md` (Task #10).

### DL-02: Facilitators Not Unified

- **Description**: `facilitators` (training module) and `planning_facilitators` (Planning Workspace) are separate tables. A facilitator must be added in both places for full functionality across both apps.
- **Impact**: Medium. Operational setup is duplicated.
- **Workaround**: Add facilitators in both the connected-frontend Facilitators page and the Planning Workspace Facilitators tab.
- **Resolution**: Post-beta. Merge requires migration + router updates.

### DL-03: Parade Dates and Parade Nights Are Separate

- **Description**: A `ParadeDate` (planning layer) and a `ParadeNight` (operational layer) are different records linked via FK. Creating a planning year does NOT automatically create parade nights. Both must be initialised separately.
- **Impact**: Low. This is intentional architecture (plan without committing sessions). Documented in user flows.
- **Workaround**: Use the Parade Night Generator in the connected-frontend.
- **Resolution**: Not planned — intentional design.

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
- **Defect**: DEFECT-005.

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
