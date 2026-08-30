# Changelog

## Unreleased — UX consistency and System Administrator account recovery (2026-08-30)

Staging: `df3fff6`. Not released to production.

### Planning Workspace route split now fails closed

`frontend/src/App.tsx` serves two route tables: module mode is `/planning` plus
a catch-all; otherwise it serves twenty routes, eighteen of which duplicate
surfaces the connected-frontend owns — `/accounts`, `/admin`, `/settings`,
`/audit` and `/imports` among them.

Which table a deployed container served was decided entirely by a Railway
environment variable, and it defaulted **open**: unset, cleared, or spelled
`TRUE` instead of `true`, the container served the full duplicate admin
surface. A deployed container now defaults to module mode, and serving the full
table is an explicit `MODULE_MODE=false` opt-out.

Staging and production both set `MODULE_MODE=true` today, so no environment
changes behaviour — only the failure mode does.

The full-app routes are kept rather than deleted: `frontend/e2e/` holds 141
tests across 25 spec files that reach planning, tenancy and proxy behaviour
through them, and no equivalent coverage exists elsewhere yet. Local
development and the e2e suite run Vite directly and never execute the
entrypoint, so they are unaffected.

- 8 tests in `backend/tests/test_pw_module_mode_fail_closed.py`, executing the
  real `frontend/docker-entrypoint.sh` (6 of them red before the fix).

### Custom training phases are no longer shared across national entities

`CustomTrainingPhase` carries a polymorphic scope pair — `scope_type` in
{squadron, wing, national, system} and `scope_id` holding that scope entity's
id. Squadron and wing scope populated `scope_id` correctly; national scope
forced it to `None`, so visibility could only match on `scope_type` and every
national saw every other national's phases, inherited all the way down to
squadrons.

`scope_id` now names the national entity, which is what the column already
meant — no new column, and no change to the date window (`applies_from` /
`applies_to`), which stays the phase's temporal scope.

- `scope_type = "system"` is deliberately unchanged: it means installation-wide,
  above any one national, and is the one scope that carries no `scope_id`.
- A national admin can no longer edit or delete another national's phase.
- Migration `v61 f2c8e51d7a93` is data-only. It attributes existing
  national-scoped rows **only when exactly one `NationalEntity` exists**, where
  the attribution is provable. With two or more it leaves them NULL and prints
  a warning naming the count and the query to find them: the row records
  nothing about who created it, and a NULL keeps the pre-v61 behaviour rather
  than misfiling data under a guessed owner. Both branches rehearsed on
  PostgreSQL, along with the downgrade.
- 9 tests in `backend/tests/test_custom_phase_national_scope.py` (5 red before
  the fix; the other 4 guard against over-filtering).

The national resolver is now shared — `services.resolve_national_id` — so this
and the tag tables derive a caller's national identically. They must not
disagree, or one endpoint would file a caller under a different national than
the other.

### Reference-data tags: sibling squadrons no longer collide, and "global" is per-national

The five user-creatable reference-data tables — subject areas, facilitator
types, session status reasons, activity types and training area capabilities —
shared one copy-pasted create path, and with it one defect. The duplicate check
ORed the scope columns independently, so `wing_id == <my wing>` matched every
tag anywhere in the wing.

- **A squadron could not name a tag that a sibling squadron had already used.**
  703 creating "Aeromodelling" blocked all 14 other squadrons in 7 Wing.
- **The resulting 409 returned the other squadron's tag id**, which the caller
  has no right to see (Part 82: no cross-squadron IDOR).

A tag now conflicts only with its own scope, or an ancestor scope that already
covers it — never with a sibling. Genuine conflicts are unchanged: the same
squadron twice is still a 409, and a global tag still blocks a squadron
duplicate.

- **`scope = "global"` now means global within one national entity.** The five
  tables gained `national_id`, resolved through the org tree when the caller
  does not carry one directly (squadron and wing users are not seeded with
  `User.national_id`). This closes a cross-national leak that would have opened
  the moment a second `NationalEntity` existed.
- Migration `v60 e9b2d47a1c05`: `national_id` on all five tables, backfilled
  through squadron → wing → national. Pre-v60 `global` rows keep `national_id`
  NULL and stay visible to everyone: their origin is unrecoverable, and NULL
  preserves exactly the pre-v60 behaviour rather than hiding data in use.
  Rehearsed on PostgreSQL forward and back, including the self-check.
- 30 tests in `backend/tests/test_reference_tag_scope.py`, parametrised across
  all five endpoints (20 of them red before the fix).

### System Administrator account recovery

Closes the gap where a System Administrator who lost their access code had no
way back in. Access codes are still stored only as hashes and are never
retrieved — every route below *replaces* a code rather than revealing one.

- **Forgot access code** on the sign-in screen. Sends a one-time link to a
  **verified** recovery email; 20-minute expiry, single use, superseded by any
  newer request. The response is byte-identical whether or not an account
  matched, and is rate limited per IP and per submitted address.
- **Recovery email** on privileged accounts (`system_admin`, `national_admin`,
  `wing_admin`, `sqn_admin`). Setting one requires the caller's current access
  code, since that address becomes a credential-reset channel. Always stored
  unverified until a verification link is followed.
- Completing a reset retires every existing code, clears lockout, and
  increments `token_version`, which signs out all existing sessions.
- **Archived and disabled accounts cannot self-recover** — an administrator
  restores them first.
- **Break-glass**: `backend/scripts/breakglass_reset_sa.py`, run by an operator
  through Railway. No hard-coded secret, nothing in git, no HTTP route.
- Migration `v59 c3a7f2e91b48`: four `users.recovery_email*` columns and the
  `recovery_tokens` table. No backfill — existing administrators are surfaced
  in `GET /api/setup/status` rather than given an invented address.
- `docs/security/system-admin-recovery.md` documents all five procedures.

### Last System Administrator

Removal protection extended from demote and archive to **disable** and
**permanent delete**.

### Interface

- **Training Year selector** rebuilt to match the controls beside it: 1.5px
  border, 6px radius, light surface, 38px against a neighbouring button's 37px.
  The 44px touch target is preserved through a transparent `::after` rather
  than by making the control taller. Replaces a dark 22px capsule that read as
  a separate module.
- Fixed the selector rendering an em-dash placeholder before years resolved,
  which looked like a broken control.
- **Account Management**: an active account's button read *Delete* but archived
  the account, while archived accounts carried *Delete Permanently…*. Renamed
  to **Archive** so each word names one action.
- **Notifications**: connected-frontend (10/14px) and the React app (9/16px)
  now share `--toast-pad-y/-x/-gap/-edge/-max-w`, declared in both.
- **Inherited Activities** is year-scoped; selecting 2027 no longer shows
  2026's holidays.
- Repaired a JavaScript syntax error that stopped the entire single-file SPA
  from parsing, and added a test that parses every inline script block.

## v17.1.1 — Final System Assurance, Accelerated Release Qualification, and Public Release to Authorised Users (2026-08-02)

Released to authorised AAFC users. Consolidates the full Final System Assurance
engagement (Stages 0-14, `docs/release/`) and a subsequent post-deployment
hardening / accelerated release qualification pass.

### Capabilities included in this release

- NATHQ Activities and Wing Activities, with read-only inheritance at
  subordinate Squadron level; owning-scope edits propagate, archive removes
  from active subordinate views.
- Wing and National Training Dashboards, alongside the existing Squadron
  view; corrected backend routing for the Training Dashboard.
- Expanded System Administrator scope: operational National/Wing/Squadron
  pages reachable via a persistent scope-selector bar, backed by the
  existing Delegated Intervention mechanism for writes (reads are
  unconditional per existing `can_view_*` authority).
- Proxy Mode and Delegated Intervention Mode across affected roles.
- Organisation and Account Management linking, bulk account archiving,
  organisation archive workflow with dependency preview, Show
  archived/restore, and a guard against archiving the final System
  Administrator account.
- Parade Night template propagation; accessible drag-and-drop and a
  keyboard-operable "Move To" control for the Weekly Program.
- Weekly Program and facilitator filtering, with save-action feedback.
- Facilitator CSV import; curriculum CSV preview with corrected
  Foundation/Extension handling.
- Guided "Getting Started" setup workflow.

### Security fixes

- Stored XSS across multiple free-text fields in `connected-frontend`
  (attribute-context and plain-text-content injection patterns) — fixed and
  live-verified; now has automated regression coverage
  (`frontend/e2e-connected/hostile-value-xss.spec.ts`).
- Health endpoints no longer leak raw database driver exception text.
- Backend Dockerfile's `postgresql-client` version pin corrected (matches
  production's actual PostgreSQL major version); build-verified via a real
  Railway deploy.
- Production backup/restore workflows corrected to target the actual
  Railway production database (previously silently targeting the wrong
  physical database — see GAP-16/GAP-18 in the qualification gap register).

### Accessibility

- `color-contrast`: WCAG-AA-compliant contextual tokens introduced
  alongside the unchanged AAFC brand palette; verified via 18 live
  page-scans with zero violations. **Note**: fixed in code and verified
  locally; deployment status is tracked separately — see Known Limitations.
- A critical `select-name` violation (two Curriculum page filter dropdowns
  with no accessible name) fixed and re-verified live.

### Known limitations (see `docs/release/final_known_limitations.md` for full detail)

- Proven safe up to 300 genuinely concurrent users; a documented capacity
  ceiling exists above that on staging's current infrastructure
  configuration, precisely diagnosed as PostgreSQL's `max_connections`
  limit rather than an application defect (see GAP-29). Not yet re-tested
  against a raised connection ceiling or a connection pooler.
- The color-contrast accessibility fix is verified but not yet deployed to
  any live environment as of this changelog entry — see the release
  candidate report for current deployment status.
- 83 remaining unlabeled `<select>` elements in `connected-frontend`, and no
  `<h1>`/landmark structure — both real, sized, deliberately deferred
  structural gaps.
- Staging System Administrator (and other staging role) live verification
  was blocked this pass on credential availability — disclosed in
  `docs/release/final_staging_feature_verification_accelerated.md`, not
  silently skipped. Does not affect production, which was separately
  verified live.

### Methodology note

Performance qualification for this release used an accelerated load
sequence (baseline → progressive ramp; spike and 30-minute endurance phases
were planned but not reached, see below) against staging, per an explicit
instruction to replace the originally-planned 4-hour soak test. The ramp
phase cleanly proved 300 concurrent users (0 5xx, sub-100ms p95) before
revealing the GAP-29 capacity ceiling around 600-1000; the spike and
endurance phases were not run given that result. See
`docs/release/qualification_gap_register.md` (GAP-28, GAP-29) and
`docs/release/final_performance_assessment.md` for full detail and honest
disclosure of what was and was not proven at each concurrency level.

## v17.1 — Maintenance Enforcement, Scope Forms, and Test Hardening (2026-06-29)

### Backend changes

**Maintenance mode enforcement middleware** (`backend/app/main.py`):
- `maintenance_gate` HTTP middleware blocks POST/PUT/PATCH/DELETE for all non-`system_admin` users when maintenance mode is ON
- Returns `503 {"error":"maintenance_mode","message":"..."}` with `Retry-After: 300` header
- 10-second TTL cache (`_maint_cache`) avoids DB hit on every request; `invalidate_maintenance_cache()` ensures immediate propagation after enable/disable
- Exempt paths: `/api/auth/login`, `/api/auth/logout`, `/api/auth/me`, `/api/auth/refresh`, `/api/system/maintenance*`, `/api/health*`, `/`
- `system_admin` bypass checks both HTTP-only session cookie (browser) **and** `Authorization: Bearer <token>` header (API/programmatic clients); previously only the cookie was checked, causing `system_admin` API calls to be blocked during maintenance

**Wing and Squadron archive endpoints** (`backend/app/routers/organisations.py`):
- `POST /api/wings/{wing_id}/archive` — requires `system_admin` or `national_admin`; blocks if Wing has active squadrons (409 `has_active_squadrons`)
- `POST /api/squadrons/{squadron_id}/archive` — requires `system_admin`, `national_admin`, or `wing_admin`; wing_admin scope-checked; both set `is_archived=True`, `archived_at=now`, audit action `"archive"`

**New test file:** `backend/tests/test_maintenance_enforcement.py` — 16 tests (1 skipped):
- POST/PUT/PATCH/DELETE blocked with 503 during maintenance
- GET requests remain accessible
- Login endpoint always exempt
- `system_admin` writes pass through (both cookie and Bearer token)
- Writes resume after disable
- Wing create + archive cycle
- Squadron create + archive cycle
- RBAC denial for under-privileged roles

### Frontend changes

**Scope Management forms** in System Console (`page-system-console`):
- "Create Wing" form: Wing Code, Full Name, Short Name fields → calls `POST /api/wings`
- "Create Squadron / Specialist Unit" form: Wing selector (populated from scope-map), Unit Code, Full Name, Unit Type → calls `POST /api/squadrons`
- Archive button on each Wing row → calls `POST /api/wings/{id}/archive` with confirmation dialog
- Archive button on each Squadron chip → calls `POST /api/squadrons/{id}/archive` with confirmation dialog
- All forms show inline success/error messages; scope map auto-refreshes after create/archive

### Tooling corrections
- `tools/stress/smoke_test.py` — fixed endpoint paths (`/api/wings`, `/api/squadrons`, `/api/curriculum`); moved unauthenticated check before login calls to prevent cookie-jar contamination
- `tools/stress/security_scope_test.py` — fixed endpoint paths throughout; moved "No secrets in API responses" section before the rate-limit hammer so sysadmin login succeeds; added `else` branch to report a failure if sysadmin login cannot be obtained
- `backend/tests/test_maintenance_enforcement.py` — fixed cookie-jar leakage in unauthenticated test; fixed curriculum path to `/api/curriculum`

### Test results
- **Automated pytest:** 327 passed, 1 skipped, 0 failed
- **Smoke test:** 29/29 passed
- **Security scope test:** 31/31 passed (includes "No secrets in API responses" and rate-limit trigger)
- **Auth load test:** 100 req / 20 concurrent — 100/100 success, 0.0% error rate, p95 286ms, 69.3 req/s
- **Read load test:** 200 req / 30 concurrent — 200/200 success, 0.0% error rate, p95 40ms, 745 req/s

---

## v17 — System Admin Console, Alpha Readiness and Stress Testing (2026-06-29)

### Backend changes

**Migration:** `e7a9c2f4b8d1` — adds `system_settings` table (key/value store for maintenance mode and platform state). Down revision: `d1e3f5a7c9b0`.

**New router:** `backend/app/routers/system.py` — all `/api/system/*` endpoints:
- `GET /api/system/overview` — system stats for system_admin
- `GET /api/system/health` — platform health (DB, CORS, cookie security)
- `GET /api/system/version` — app and package version
- `GET /api/system/migrations` — expected and current Alembic head
- `GET /api/system/maintenance` — maintenance mode state
- `POST /api/system/maintenance/enable` — enable (requires confirmation `ENABLE MAINTENANCE`)
- `POST /api/system/maintenance/disable` — disable
- `GET /api/system/scope-map` — all Wings and Squadrons
- `GET /api/system/backups` — list backups
- `POST /api/system/backups` — create SQLite backup (local demo only)
- `GET /api/system/audit-summary` — audit log (system_admin + auditor)

**New model:** `SystemSetting` in `models/operations.py` — key/value table for platform settings.

**New permission helpers:** `require_system_admin(p)`, `require_system_or_nat_admin(p)`, `require_audit_access(p)`, `is_system_admin` property on Principal.

**App version:** bumped to `17.0.0`.

**New tests:** `backend/tests/test_system_admin.py` — 33 tests covering login, overview, health, version, migrations, maintenance, scope map, audit, backups, RBAC denial, and audit trail.

### Frontend changes

**System Console page:** `page-system-console` — visible only to `system_admin`. Sections:
- System Overview (app version, environment, DB type, wings/sqns/users, maintenance status, last backup)
- Platform Health (backend status, DB status, cookie security, CORS origins)
- Scope Map (all Wings and Squadrons with inactive indicators)
- Maintenance Mode (enable/disable with typed confirmation, message/until fields)
- Backup (list backups, create backup button)
- Recent Audit Activity (filterable by action, monospace log display)

**Nav changes:** "System" label + "System Console" nav item added (visible only to `system_admin`).

**Scope changes:** `system_admin` added as a first-class scope in `getScopeType()`, `NAV_BY_SCOPE`, `SCOPE_LANDING`, `effectiveScope()`, `getCurrentUnitInfo()`, `updateScopeBanner()`. Landing page: System Console. `renderAll()` short-circuits for system_admin (System Console loads its own data).

### Scripts and tools

**New scripts:**
- `scripts/backup_sqlite_demo.sh` — timestamped SQLite demo backup
- `scripts/smoke_test_local.sh` — bash smoke test using curl
- `scripts/pre_alpha_check.sh` — pre-alpha readiness check

**New stress tools:**
- `tools/stress/smoke_test.py` — full functional smoke test (Python)
- `tools/stress/load_test_auth.py` — concurrent auth load test
- `tools/stress/security_scope_test.py` — RBAC and IDOR security test
- `tools/stress/data_volume_seed.py` — volume data generator (test DB only)

### Documentation

**New docs:**
- `docs/system_admin_console.md` — System Console user guide
- `docs/pre_alpha_readiness_checklist.md` — full alpha readiness checklist
- `docs/security_review_checklist.md` — structured security review
- `docs/stress_testing_plan.md` — stress testing plan and results template
- `docs/deployment_guide.md` — local demo, staging, and production deployment guide (replaces earlier stub)
- `docs/role_matrix.md` — updated with System Console rows

**Claude Code configuration:**
- `CLAUDE.md` — project overview, run commands, security invariants, packaging rules
- `.claude/rules/security.md` — security review rules and grep commands
- `.claude/rules/backend.md` — backend coding rules
- `.claude/rules/frontend.md` — frontend coding rules
- `.claude/rules/deployment.md` — deployment rules and pre-packaging checklist
- `.claude/rules/testing.md` — test patterns and commands

**Regression:** 310 passed, 1 skipped, 0 failed (277 prior + 33 new system_admin tests).

**Security greps:** 0 access-code exposure matches, 0 localStorage, 0 seeded codes in frontend, 0 JWT secrets in frontend.

## v16.2 — UI Text Cleanup and Annual Program Calendar (2026-06-29)

**Frontend changes only — no backend changes, no migration, no seed changes.**

### Text cleanup

- Removed "your unit only" suffix from the scope banner for squadron users (scope banner now shows just the unit name)
- Removed login description sentence "Controlled access for training program management, curriculum planning and unit administration."
- Login screen now shows: title, access code field, Sign In button, authorised-use notice only

### Annual Program — live calendar view

- Replaced term-block card layout with a 12-month calendar grid
- Calendar reads live data from the existing `/api/planning/years/{id}/annual-program` endpoint — no new API calls
- Each month grid cell shows colour-coded indicators:
  - AAFC blue cell = parade night
  - Fill dot colour = session allocation status (green ≥50%, AAFC blue >0%, grey = empty)
  - Amber/yellow = holiday or stand-down period
  - Red-tinted cell = Must Attend activity
  - Blue-tinted cell = Key Event activity
- Clicking any date with an event shows a detail panel containing:
  - Day name and date
  - Holiday/stand-down details including date range
  - Parade night: sessions assigned / total slots, allocation percentage badge
  - Quick-nav buttons to Parade Night Program and Training Planner
  - Anchor events with importance badge and unit name
- Calendar legend rendered above the grid
- Detail panel rendered below the grid, dismissed with Close button
- `window._AP_DATA` holds indexed data for click interactions (no sensitive data)
- Training Planner mission assignments immediately reflected in calendar on next Annual Program load

**Confirmation:** Assigning a mission in Training Planner updates the `filled_count` in the annual-program API response, which is reflected in the calendar dot colour and detail panel on next load of Annual Program.

**Regression:** 277 passed, 1 skipped, 0 failed. Security: 0 removed-wording matches, 0 localStorage, 0 access-code exposure, 0 seeded codes.

## v16.1 — AAFC Visual Identity Alignment and Planning Tab Consolidation (2026-06-29)

**Frontend changes only — no backend changes, no migration, no seed changes.**

### AAFC Visual Identity Guide alignment

- Restored AAFC approved colour palette: `#51b0e3` (AAFC blue), `#002f65` (dark blue), `#004b8d` (royal blue), `#455560` (gunmetal grey), `#b0b7bb` (light grey), `#e51937` (red), `#7db2ce` (pale blue)
- Reverted from generic Apple-system colours to AAFC brand colours throughout
- Font: Montserrat (primary) → Arial → system sans-serif (VIG-compliant fallback chain)
- Auth screen: dark blue gradient background instead of flat black
- Topbar: AAFC dark blue (`#002f65`) with AAFC blue on separator/chips
- Active nav state: AAFC blue border and background — not generic blue
- Table headers: light grey background with gunmetal text (not dark navy)
- Stat card border-top: AAFC blue
- Primary buttons: dark blue with royal blue hover
- Secondary buttons: white with dark blue border
- Badges: AAFC palette (no off-palette colours)
- Calendar: AAFC blue parade cells, appropriate chips
- Parade Night headers: dark→royal gradient
- Scope banners: AAFC blue tags

### Navigation restructure

- Planning sub-items moved from the bottom of the sidenav into the Training section
- Planning items appear as indented sub-items under Training (not a separate disconnected section)
- Order: Annual Program → Training Planner → Parade Night Program → Planner Help
- "Training Planner" section label replaced with a subtle sub-header within Training
- `applyNavScope` updated to handle `.nav-planning-hdr` class alongside `.nav-lbl`

### Weekly Program consolidation

- **Removed**: "Weekly Program" as a separate Planning tab and nav item
- **Added**: Weekly Program preview panel at the bottom of Parade Night Program page
- When a parade date is selected in Parade Night Program, the weekly program table renders automatically below the session grid
- `loadBuilderGrid` now calls `loadWeeklyProgram(dateId)` after loading the grid (planning date mode)
- `loadBuilderFromPn` now calls `_renderBuilderWeeklyPreview()` using already-fetched data (direct PN mode — avoids second API call)
- `_renderBuilderWeeklyPreview(sessions, timingBlocks, dateStr)` helper added
- `_PLANNING_PAGES` updated: removed `'planning-weekly'`
- `loadPWDates` made null-safe (element removed with standalone page)
- `pw-year-sel` removed from `_loadPlanningYears` selector list

### Result

- One source of truth for Weekly Program: inside Parade Night Program
- Assignment changes in Training Planner → visible in Parade Night Program and weekly preview on reload
- No orphaned nav buttons
- No blank pages
- Weekly Program output preserved (not removed — consolidated)

**Regression:** 277 passed, 1 skipped, 0 failed. Security: 0 localStorage, 0 access-code hashes, 0 seeded codes, 0 old planner labels.

## v16 — Apple-Inspired Visual Polish (2026-06-29)

**Frontend changes only — no backend changes, no migration, no seed changes.**

**Design system:**
- Replaced full CSS block with a coherent V16 visual system using design tokens
- Switched font stack from `Montserrat` (Google Font) to `-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif`
- New tokens: `--bg:#f2f2f7`, `--surface:#fff`, `--text:#1c1c1e`, `--accent:#0055cc`, `--border:#d1d1d6`
- Lighter shadows (`0 1px 3px rgba(0,0,0,.08)`) replacing heavy navy-tinted shadows
- Table headers changed from dark navy background to light grey — cleaner, less aggressive
- Reduced uppercase/900-weight overuse throughout nav, buttons, labels
- All legacy alias classes preserved for JS-generated HTML compatibility

**Missing CSS classes defined (all were used in V14-added HTML/JS but never styled):**
- `.btn-primary`, `.btn-secondary`, `.btn-danger` — standard button variants
- `.data-table` — alias for `table` element styling
- `.page-header` with subtitle — consistent planning page headers
- `.page-actions` — page-level action area
- `.form-group` — form field wrapper
- `.muted` — muted text utility class
- `.badge-green`, `.badge-grey`, `.badge-red`, `.badge-amber` — status badge set

**HTML wording:**
- Login title: "AIR F◉RCE CADETS" → "AAFC Training Management System"
- Login description updated to professional, concise copy; added security notice
- Topbar: "AIR F◉RCE CADETS" → "AAFC · Training Management"
- Nav label: "Weekly Program (Planner)" → "Weekly Program"
- Version marker updated to V16
- Page subtitles added to all 5 planning tabs:
  - Training Planner: "Assign curriculum missions to parade dates, sessions, facilitators and locations."
  - Planner Help: "Reference guidance for sequencing training around key activities."
  - Annual Program: "View the training year, key activities, holidays and available parade nights."
  - Parade Night Program: "Review one parade night by cadet group and session."
  - Weekly Program: "Facilitator-facing program for the selected parade night."

**Regression:** 277 passed, 1 skipped, 0 failed. Security greps: 0 localStorage, 0 access-code hashes, 0 seeded codes in frontend.

## v15 — Frontend Rendering Fix: Planning Tabs Now Visible (2026-06-29)

**Root cause fixed:** All 10 planning page `<div>` elements had inline `style="display:none"` which overrides the `.page.active{display:block}` CSS rule (inline style specificity > class specificity). Non-planning pages had no inline style and worked correctly. All planning tabs were invisible on click.

**Frontend changes only — no backend changes, no migration, no seed changes:**

- Removed inline `style="display:none"` from all 10 planning page divs (`page-planning-missions`, `page-planning-guide`, `page-planning-year`, `page-planning-anchors`, `page-planning-term`, `page-planning-builder`, `page-planning-weekly`, `page-planning-longrange`, `page-planning-rooms`, `page-planning-checks`)
- Fixed `_loadPlanningYears()`: now auto-selects the active/first planning year if none selected, and returns the selected year ID
- Fixed nav hook (`nav = function(pg)`): now calls the correct load function with the auto-selected year ID after loading year list — Training Planner calls `loadMissions()`, Annual Program calls `loadYearMap()`, Parade Night Program calls `loadBuilderDates()` then auto-selects first date, Weekly Program calls `loadPWDates()` then auto-selects first date
- Added `_autoSelectFirstDate(selId, loadFnName)` helper for Parade Night Program and Weekly Program
- Fixed `_canWrite()`: was referencing undefined `_session` variable — corrected to use `S.role`
- Expanded Planner Help (static, no API call) to include: Planning Cycle, Quick Decision Guide, How to Use Training Planner, How to Use Annual Program, How to Use Parade Night Program, How to Use Weekly Program, Access Control
- Added V15 version marker in Training Planner page title and in Planner Help footer
- Added pilot data status panel ("Data Status") on Training Planner page (localhost only, collapsed by default) showing: role, unit, selected year, missions loaded count, parade dates loaded count, annual program status, selected parade night, last API error — does not expose tokens, access codes, or hashes

**Test results:** 277 passed, 1 skipped — no regressions.

---

## v14 — Training Planner Integration, Annual Program, Rollover, Backup and Maintenance (2026-06-29)

**Backend changes:**

- **New migration `d1e3f5a7c9b0`** (down_revision: `a2c4e6f8b1d3`):
  - `sessions.part_number` — which part of a multi-part curriculum module
  - `curriculum_items.part_count` — total parts in a module (default 1)
  - `curriculum_items.instructor_suitability` — recommended instructor type
  - `anchor_events.cea_activity_id`, `nomination_end_date`, `unit_name`, `importance_level`
  - `anchor_events.audience_staff_only`, `audience_proficient`, `audience_first_years`
  - `holiday_periods.holiday_type` — school_holiday / public_holiday / exam_period / stand_down / no_parade / reduced_attendance
  - `parade_dates.term`, `week_number`, `cancellation_reason`

- **New endpoints** (all in `/api/planning/`):
  - `GET /years/{id}/missions` — Training Planner: curriculum items with scheduling status, filterable by phase, element, term, status, search
  - `POST /years/{id}/assign-mission` — Assign curriculum item to a parade night session (creates real Session record)
  - `GET /years/{id}/annual-program` — Full-year calendar view: 4 term blocks with parade dates, holidays, activities, fill statistics
  - `POST /years/{id}/rollover` — Create next planning year: copy holidays, regenerate parade dates, note incomplete sessions

- **Extended serialisers**: `_anchor_out`, `_holiday_out`, `_date_out` include new V14 fields

- **`seed_planning_data()`** seeded in `seed_all.py`:
  - 703 SQN 2026 planning year
  - WA 2026 holidays (9 entries: Labour Day, Good Friday, Anzac Day, WA Day, King's Birthday, 4 school holiday blocks)
  - Friday parade dates for all of 2026, linked to parade night records
  - 4 demo anchor events (7 Wing Camp, Anzac Day Service, 703 Annual Dinner, Orientation Weekend)
  - 8 national prep rules (adventure_training, ceremonial, dining_in, orientation_weekend, inspection, fieldcraft)

**Frontend changes:**

- **New "Training Planner" tab** (`planning-missions`) added to Training Planner section nav — first visible tab
- **Training Planner page** (`page-planning-missions`):
  - Year selector with live filter: Cadet Level, Status (scheduled/unscheduled), free-text search
  - Mission table: Code, Title, Level, Subject, Suitability, Parts, Rec. Term, Scheduled date/session, Facilitator, Location, Status badge
  - Assign button per row → assignment modal
- **Assign Mission modal** (`m-assign-mission`): parade night selector, session selector, cadet group, part number (for multi-part), facilitator
- **Annual Program** page (`page-planning-year`) — `loadYearMap()` now fetches `/annual-program` and renders 4 term blocks showing parade count, fill percentage, holidays, and activities per term
- `_PLANNING_PAGES` updated: `planning-missions` added; nav hook triggers `_loadPlanningYears()` on visit
- `_loadPlanningYears()` updated to populate `mission-year-sel`

**Security greps (all clean):**
1. No hardcoded access codes in frontend
2. No localStorage for operational data
3. No access code hashes in frontend
4. No plaintext codes returned to frontend
5. No embedded unit hierarchy in frontend

**Tests:**
- 36 new tests in `tests/test_planner_v14.py`
- Full suite: 277 passed, 1 skipped, 0 failed

**Documentation added:**
- `docs/training_planner.md` — module reference, API, RBAC
- `docs/annual_program_lifecycle.md` — lifecycle, seeded holidays, term blocks
- `docs/year_rollover.md` — rollover procedure, what is/is not copied, API
- `docs/backup_and_restore.md` — pilot and production backup procedures
- `docs/maintenance_procedure.md` — routine maintenance, DB reset, migrations, log location

---

## v13 — Training Planner Simplification + Professional Language Review (2026-06-28)

**Product decision:**
Simplified the TRGO Planning section into a focused "Training Planner" set of three pages visible during the pilot:
- **Planner Help** (formerly "Planning Guide") — static workflow reference, rewritten for the simplified pilot workflow
- **Annual Program** (formerly "Year Map") — create planning years, generate and manage parade dates
- **Parade Night Program** (formerly "Night Builder") — select a parade night, view Period 1/Period 2/Period 3 timing blocks, assign sessions per cadet group and period, save, verify persistence
- **Weekly Program (Planner)** — confirm saved sessions appear in the program view

Hidden from nav for this pilot (HTML retained for future activation):
- Anchor Events, Term Program, Long-Range View, Locations and Facilitators, Program Checks

These tabs were either non-functional or required setup steps beyond the minimum pilot workflow.

**Frontend changes (`connected-frontend/index.html`):**
- `_PLANNING_PAGES` reduced to `['planning-guide','planning-year','planning-builder','planning-weekly']` — controls which pages are in scope for each role
- Navigation section label: "TRGO Planning" → "Training Planner"
- All navigation item labels: removed decorative emoji, replaced with plain text. No emoji-only navigation labels remain.
- Main nav: Dashboard, Calendar, Parade Nights, Weekly Program, Curriculum, Activities, Facilitators, Locations and Resources, Training Summary, Needs Attention, Unit Settings, Account Management, Wing Overview, National Overview, Curriculum Coverage, Training Balance, Facilitator Load, Risk and Bottlenecks, Audit
- Training Planner nav: Planner Help, Annual Program, Parade Night Program, Weekly Program (Planner)
- Page headings updated to match nav labels
- JS-generated dashboard headings cleaned up (Wing, National, Coverage, Balance, Load, Risk pages)
- All `.ei` emoji-only decorators removed from empty states
- Empty states rewritten in operational language: professional, specific, action-oriented
- Error message translations expanded in `api()`: `forbidden`, `no_squadron_scope`, `out_of_scope`, `invalid_status`, `reason_required_not_delivered`, `invalid_date_format`, `invalid_cadet_group`, `no_parade_night_linked`, `parade_night_not_found`, `planning_year_not_found`, `override_requires_reason`
- Internal comment: "Night Builder" → "Parade Night Program", "TRGO PLANNING MODULE" → "TRAINING PLANNER MODULE"

**No backend changes.** All 241 tests pass (1 skipped).

**Frontend security grep results:**
- Hardcoded seeded access codes in JS: 0 ✓
- `code_hash` / `access_code` / `plain_code` in frontend: 0 ✓
- `localStorage` usage for operational data: 0 ✓
- `View current code` / `Show access code` / `Reveal code`: 0 ✓
- Emoji navigation labels: 0 ✓ (functional status indicators only remain)

**Live browser test:**
- ADMIN703 (sqn_admin): Training Planner nav shows Planner Help, Annual Program, Parade Night Program, Weekly Program (Planner). Parade Night Program loads builder with 12 timing blocks and Period 1/2/3. Sessions persist. Weekly Program shows saved sessions.
- ADMIN7WG (wing_admin): Wing Overview shows professional heading without emoji. Curriculum Coverage, Training Balance, Facilitator Load, Risk and Bottlenecks all show clean headings. Curriculum tab visible and functional.
- ADMINNATIONAL (national_admin): National Overview shows professional heading. Curriculum tab visible.

---

## v12 — TRGO Planning Corrective Integration + Timing Template Seed + Wing Auth Fix (2026-06-28)

**Root causes fixed:**
- **Empty TRGO pages:** V11 created a parallel data system (`PlanningYear` → `ParadeDate` → `ScheduledSession`) completely disconnected from the real training chain (`parade_nights` → `sessions`). Night Builder wrote `ScheduledSession` records; weekly program and long-range view read `ScheduledSession` records; none read or wrote real `Session` records.
- **Disconnected parade night creation:** After `POST /api/parade-nights`, the frontend showed a static alert and did not navigate to the Night Builder.
- **Missing Wing/NAT Curriculum tab:** `NAV_BY_SCOPE.wing` and `NAV_BY_SCOPE.national` arrays did not include `'curriculum'`.

**Integration points fixed:**

*Data model (`backend/app/models/`):**
- `Session` (training.py): added `cadet_group` field — enables per-group grid rows in Night Builder
- `ParadeDate` (planning.py): added `parade_night_id` FK column — links planning dates to real parade nights

*Migration `a2c4e6f8b1d3_v12_integration.py`:*
- `down_revision = 'f3a1b5c9d7e2'`
- Adds `cadet_group` to `sessions` table
- Adds `parade_night_id` to `parade_dates` table

*Training router (`app/routers/training.py`):*
- `SessionIn` now accepts `cadet_group`
- `create_session`, `edit_session` now set/update `cadet_group`
- `_sess_dict` includes `session_id` alias
- NEW: `GET /api/parade-nights/{pnid}/builder` — returns parade_night_id, parade_date, squadron_id, session_count, timing_template_id, timing_blocks, cadet_groups, and real `Session` records in grid format

*Planning router (`app/routers/planning.py`):*
- `_date_out()` now includes `parade_night_id`
- NEW: `_find_or_create_parade_night()` — finds or creates a real `ParadeNight` for a given unit+date within the current transaction
- NEW: `_real_session_out()` — serializes a real `Session` in Night Builder grid format
- `add_parade_date`, `generate_parade_dates`: both now call `_find_or_create_parade_night()` and set `parade_night_id` on created `ParadeDate` records
- `get_builder`: now uses `pd.parade_night_id` → real `ParadeNight` → real `Session` records
- `create_session` (planning): creates real `TrainingSession` (not `ScheduledSession`); auto-links `parade_night_id` if missing; denormalizes curriculum/facilitator/room
- `update_session`, `delete_session` (planning): now operate on real `Session` records
- `get_weekly_program`, `get_long_range`, `get_term_planner`: all use real sessions via `parade_night_id`
- `_run_conflict_check`, `get_decision_guide`: both rewritten to use real `Session` records instead of `ScheduledSession`

*Frontend (`connected-frontend/index.html`):*
- `NAV_BY_SCOPE.wing` and `.national` now include `'curriculum'` — Wing and National admin see Curriculum tab
- `renderAll()` calls `renderCurr()` for non-squadron scopes
- `doCreatePN()` success handler navigates to Night Builder via `loadBuilderFromPn(r.parade_night_id)` — no more static alert
- Session edit modal: added `sess-curr-inp` curriculum dropdown (first field); status options updated to real workflow values (planned/published/delivered/cancelled/not_delivered)
- `_populateSessionSelectsReal()`: populates curriculum, facilitator, room selects from real `S.facs/S.rooms/S.curr` with API fallback
- `loadBuilderGrid()`: uses `session_id` (not `scheduled_session_id`); shows timing block times; info banner; linked/unlinked state; action-oriented error state
- `openEditSessionModal()`, `openNewSessionCell()`: use `session_id`; call `_populateSessionSelectsReal()`
- `doSaveSession()`: handles 'pn' vs 'date' mode; includes `curriculum_id`; reloads correct builder after save
- `loadLocations()`: uses real `/api/training-areas` (primary) + planning locations as supplement
- `loadPlanningFacilitators()`: uses real `S.facs` or `/api/facilitators`
- All planning tab empty states: action-oriented with next-step navigation links
- NEW: `loadBuilderFromPn(pnId)` — direct parade night → builder navigation
- NEW: `_loadDirectPnSelector()` — populates direct parade night dropdown
- `P` state object: added `currentPnId` and `_directPnId` fields

**Demo seed fix (blocking demo gap closed):**
- `backend/app/seeds/seed_all.py`: added seeded `TimingTemplate` for 703 SQN — "703 Standard Friday Night"
  - 12 blocks: Arrival (18:00), Roll Call (18:15), Forming Up (18:25), Parade (18:30), **Period 1** (18:50–19:25, IP), **Period 2** (19:25–20:00, IP), Drinks Break (20:00), **Period 3** (20:30–21:05, IP), Fatigues (21:05), Final Parade (21:15), Debrief (21:25), Dismissal (21:30)
  - `is_default=True`, `effective_from="2026-01-01"`, `active_status=True`
  - All 3 demo parade nights (`2026-02-06`, `2026-05-01`, `2026-07-24`) now link to this template
  - After clean DB reset, `GET /api/parade-nights/{id}/builder` immediately returns all 12 blocks with Period 1, 2, 3 labeled

**timing_blocks serialization fix:**
- `GET /api/parade-nights/{id}/builder`: timing_blocks dict now includes `period_number` and `duration_minutes`
- `GET /api/planning/parade-dates/{id}/builder`: same fix
- `GET /api/planning/parade-dates/{id}/weekly-program`: same fix

**auth/me wing_code fix:**
- `_me(user)` now accepts optional `db` parameter; looks up `Wing` by `user.wing_id` to include `wing_code` in response
- All 3 callers (login, refresh, /me) now pass `db`
- Wing admin: `GET /api/auth/me` returns `wing_id`, `wing_code: "7WG"`, `is_wing: true`
- Squadron admin under 7 Wing: also returns `wing_code: "7WG"`

**Backend tests — 18 new V12 tests (`tests/test_planning.py`), 241 total (1 skipped):**
- `test_add_parade_date_creates_parade_night_link`
- `test_generate_parade_dates_links_parade_nights`
- `test_planning_session_creates_real_session`
- `test_builder_returns_real_sessions`
- `test_weekly_program_uses_real_sessions`
- `test_parade_night_builder_endpoint_returns_timing_blocks`
- `test_wing_curriculum_visible_to_sqn`
- `test_national_curriculum_visible_to_wing_and_sqn`
- `test_703_default_timing_template_seeded` — seed creates active default template for 703
- `test_703_timing_template_has_three_instructional_periods` — exactly Period 1, 2, 3
- `test_703_timing_template_period_numbers_correct` — period_number values are 1, 2, 3
- `test_parade_night_links_timing_template_after_seed` — fresh parade night has timing_template_id set
- `test_builder_returns_nonempty_timing_blocks` — 12 blocks, 3 IPs, period_number + times present
- `test_planning_session_persists_in_weekly_program` — session appears in Weekly Program
- `test_planning_session_appears_in_long_range` — session appears in Long Range View
- `test_wing_admin_auth_me_returns_wing_id` — wing_id not None for wing_admin
- `test_wing_admin_auth_me_returns_wing_code` — wing_code = "7WG" for ADMIN7WG
- `test_sqn_admin_auth_me_returns_wing_code` — wing_code = "7WG" for ADMIN703

**Live browser test results (clean DB, after seed):**
- ADMIN703 Story A: create PN → builder shows Period 1/2/3 with times → create planning year → auto-generate 5 Friday dates (5 linked to real PNs) → add sessions → weekly program populated → long range populated → PASS
- ADMIN7WG: `GET /api/auth/me` returns `wing_id` + `wing_code: "7WG"` → `POST /api/curriculum/wing` creates wing item → visible to SQN → PASS
- ADMINNATIONAL: `POST /api/curriculum/national` creates national item → visible to Wing and SQN → PASS

**Frontend security grep results:**
- Hardcoded seeded access codes in JS: 0 ✓
- `code_hash` / `access_code` / `plain_code` in frontend: 0 ✓
- `localStorage` usage for operational data: 0 ✓
- `View current code` / `Show access code` / `Reveal code`: 0 ✓

---

## v11 — TRGO Planning Module (2026-06-28)

**New backend module — `app/routers/planning.py` (32 endpoints):**
- `POST/GET/PATCH /api/planning/years` — create and manage planning years per unit or wing
- `POST/GET /api/planning/years/{id}/parade-dates` — add parade nights to a planning year
- `POST /api/planning/years/{id}/generate-parade-dates` — auto-generate recurring dates by weekday, skipping holidays
- `DELETE /api/planning/parade-dates/{id}` — remove a parade date
- `POST/GET /api/planning/years/{id}/holidays` — manage holiday/stand-down periods
- `DELETE /api/planning/holidays/{id}`
- `POST/GET /api/planning/years/{id}/anchors`, `PATCH/DELETE /api/planning/anchors/{id}` — anchor events (ceremonies, FTX, inspections)
- `GET /api/planning/anchors/{id}/prep-suggestions` — rule-based preparation lesson suggestions
- `GET /api/planning/years/{id}/term-planner` — term-by-term overview with session fill stats
- `GET /api/planning/parade-dates/{id}/builder` — parade night grid with timing template integration
- `POST /api/planning/parade-dates/{id}/sessions`, `PATCH/DELETE /api/planning/sessions/{id}` — schedule individual sessions per group/period
- `GET /api/planning/parade-dates/{id}/weekly-program` — published weekly program with timing blocks
- `GET /api/planning/years/{id}/long-range` — 4–20 week forward view
- `POST/GET/PATCH /api/planning/locations` — planning locations (rooms, outdoor areas)
- `GET /api/planning/facilitators` — facilitators in planning scope with subject areas
- `GET /api/planning/years/{id}/conflicts`, `POST /api/planning/years/{id}/run-checks` — conflict detection
- `POST /api/planning/conflicts/{id}/override` — override a conflict with required reason (audited)
- `GET /api/planning/years/{id}/decision-guide` — rule-based checklist (10 checks)
- `GET /api/planning/prep-rules` — seeded preparation rules by event type

**New models (`app/models/planning.py`):**
- `PlanningYear`, `ParadeDate`, `HolidayPeriod`, `AnchorEvent`, `AnchorPrepRule`, `AnchorPrepPlan`, `ScheduledSession`, `PlanningLocation`, `PlanningConflict`

**Alembic migration `f3a1b5c9d7e2_v11_trgo_planning.py`:**
- `down_revision = 'e6f8a2d4c1b3'` — creates all 9 planning tables

**Connected frontend — 9 new TRGO Planning sub-tabs:**
- Planning Guide (static intro/how-to)
- Year Map — create year, auto-generate parade dates, manage holiday periods
- Anchor Events — CRUD with importance/type filters, prep suggestion view
- Term Planner — term-by-term capacity overview with cadet group breakdown
- Night Builder — session grid (groups × periods) with click-to-edit
- Weekly Program — published program with timing block labels
- Long Range View — 4–16 week forward calendar with anchor overlays
- Rooms & Staff — planning locations + facilitator list
- Planning Checks — decision guide + unresolved conflicts with inline override

**Backend tests — 54 new tests (`tests/test_planning.py`), 224 total (1 skipped):**
- Planning year CRUD, RBAC (sqn_admin/wing_admin/nat_admin/general/auditor/unauthenticated)
- Parade date creation, listing, generation, deletion
- Holiday period creation, listing, conflict flagging
- Anchor event CRUD, archive, prep suggestions
- Term planner structure and term filter
- Parade night builder and session CRUD
- Override-conflict validation (reason required)
- Weekly program, long range view
- Location CRUD
- Facilitators planning view
- Conflict detection (facilitator double-booking)
- Decision guide structure and date_id param
- Prep rules listing and event_type filter
- Wing admin and NAT admin scope

**Live endpoint tests: 40 PASS, 0 FAIL**

**Frontend security grep results:**
- Seeded access codes in JS: 0 ✓
- `code_hash` in frontend: 0 ✓
- `localStorage` usage: 0 ✓
- `sessionStorage`: JWT token only ✓
- `ca-flight-row` shown as inline: 0 ✓

---

## v10 — CORS PATCH Fix, Session Structure Save, Combined Wing Workflow, Error Detail (2026-06-27)

**Root cause fix — Session Structure and Curriculum edit never reached backend:**
- `app/main.py`: `allow_methods` was missing `"PATCH"` — browser CORS preflight rejected all PATCH requests (squadrons settings, curriculum edits, account updates) before they reached the server; every attempt showed "Cannot reach the backend" in the browser
- `app/config.py`: default `CORS_ALLOWED_ORIGINS` now includes `http://localhost:8080` and `http://127.0.0.1:8080` so the connected frontend works without setting env vars manually

**Wing account creation fixes:**
- `doCreateAccount()`: added pre-submit validation for required Wing and Squadron fields; shows "Please select a Wing." or "Please select a Squadron / Specialist Unit." before submitting — eliminates cryptic "Some fields are invalid." fallback
- `openCreateAccountModal()`: for wing admin, squadron list is now filtered to their own wing on initial population; accepts optional `preselectedSqnId` parameter

**Combined Wing Workflow (Issue 3):**
- After `doCreateSqn()` succeeds, user is prompted "Create an account for [code] now?"; if confirmed, account creation modal opens with the new squadron pre-selected

**Flight sub-group UI removed from account creation (Issue 8):**
- "Flight (optional)" row (`ca-flight-row`) permanently hidden in account creation modal — flight sub-groups are not part of the account creation scope
- Removed `_populateCreateFlights()` function, removed flight logic from `onCreateAccountRoleChange()`, `onCreateAccountWingChange()`, and account creation payload

**Error detail improvements:**
- `api()` function: named code handlers added for `squadron_id_required` → readable message, `wing_id_required` → readable message, `code_exists` (409) → uses backend message directly

**Documentation:**
- `AAFC_TMS_Setup_Run_Rollout_Guide.md` section 8.3: full demo credentials table including `SYSADMIN2026` with note about system admin scope and production replacement requirement

**Backend tests (9 new, 170 total):**
- `test_sqn_admin_can_patch_own_squadron_settings` — PATCH /api/squadrons persists all settings fields
- `test_sqn_admin_patch_settings_is_audited` — audit entry for update_settings
- `test_wing_admin_cannot_patch_squadron_without_proxy` — 403 proxy_required without proxy
- `test_sqn_admin_cannot_patch_other_squadron` — 403 for out-of-scope squadron
- `test_wing_admin_can_create_sqn_admin_account` — wing_admin creates sqn_admin for own wing
- `test_wing_admin_create_sqn_admin_without_squadron_returns_422` — 422 squadron_id_required
- `test_wing_admin_can_create_wing_viewer_account` — wing_viewer account creation
- `test_nat_admin_can_patch_wing_curriculum_without_proxy` — nat_admin PATCH wing item
- `test_nat_admin_can_delete_wing_curriculum_without_proxy` — nat_admin DELETE wing item

**Live endpoint tests: 26 PASS 0 FAIL**

**Frontend security grep results:**
- Seeded access codes in JS: 0 ✓
- `code_hash` in frontend: 0 ✓
- `localStorage` usage: 0 ✓
- `sessionStorage`: JWT token only ✓
- `ca-flight-row` shown as inline: 0 ✓

---

## v9 — Specialist Unit Model, Wing/SQN CRUD, Multi-Level Curriculum, JWT Safety (2026-06-27)

**Backend features:**
- `Squadron.unit_type` column: `standard_squadron | specialist_squadron | specialist_flight | support_unit`; all use same tenancy/account model as standard squadron
- `UNIT_TYPES` constant in `models/organisations.py`; invalid values fall back to `standard_squadron`
- Alembic migration `e6f8a2d4c1b3` adds `squadrons.unit_type` column with index
- `POST /api/wings` — NAT HQ admin / system_admin creates a new Wing (audited, 409 on duplicate code)
- `POST /api/squadrons` — Wing admin (own wing) or NAT HQ admin creates any squadron-equivalent unit (audited, 409 on duplicate code, 403 on out-of-scope)
- `GET /api/squadrons` now returns `unit_type` and `active_status` fields; accepts `?wing_id=` and `?unit_type=` query filters
- `PATCH /api/squadrons/{id}` accepts `unit_type` in update body
- `GET /api/curriculum` now includes wing-level items (where `owning_level=wing` and `wing_id` matches actor's wing); returns `wing_id` and `squadron_id` fields on each item
- `POST /api/curriculum/wing` — Wing admin / NAT HQ admin creates wing-owned curriculum (visible to all squadrons in that Wing)
- `POST /api/curriculum/national` — NAT HQ admin / system_admin creates national curriculum (visible to all)
- `PATCH /api/curriculum/{cid}` and `DELETE /api/curriculum/{cid}` enforce ownership by `owning_level`: national → NAT HQ admin only; wing → wing/nat admin + wing scope check; squadron → existing logic
- JWT secret dev default changed from 22 bytes to 40 bytes (≥32, suppresses HS256 InsecureKeyLengthWarning)
- `config.py` `validate_for_production()`: `_is_dev()` helper now rejects `dev-only-*` prefix values regardless of length
- `datetime.utcnow()` deprecation fixed in `models/training.py`, `models/operations.py`, `seeds/seed_all.py`, `routers/export_import.py`

**Backend tests (31 new, 152 total):**
- Wing creation: nat_admin OK, system_admin OK, wing_admin 403, sqn_admin 403, duplicate 409, audited
- Squadron creation: all 4 unit types, wing_admin own wing OK, wing_admin another wing 403, sqn_admin 403, duplicate 409, invalid unit_type fallback, audited
- PATCH squadron unit_type, list includes unit_type
- Wing curriculum visible to SQN in same wing; national curriculum visible to all
- SQN cannot edit/delete wing or national curriculum (403); NAT HQ can edit/delete own; wing admin can edit own wing curriculum
- JWT secret production validation: short secret rejected, dev-prefix rejected, strong secret passes, class default ≥32 bytes

**Connected frontend:**
- Subject column headers: emoji replaced with full text labels per spec (Service Knowledge, Drill and Ceremonial, Field Skills, Personal Development and Leadership, Community Engagement, Aviation and Air Power)
- Subject filter dropdown updated to match spec labels
- SUBJECTS constant labels updated to match spec
- Curriculum source badges: `NAT HQ` (dark), `Wing code` (purple), `SQN` (teal) shown on each item
- `canEditCurr(e)` helper: editable only by the appropriate level admin
- Wing and National curriculum creation buttons (shown by role): `+ Add Wing Curriculum` (wing/nat admin), `+ Add National Curriculum` (nat admin only)
- `openAddCurrWing()` / `openAddCurrNat()` / `_currSaveEndpoint` variable — same modal, different endpoint
- `editCurr(code)` now looks in all editable curriculum (not just `S.addCurr`)
- "Squadrons / Specialist Units" card added to Accounts page for wing/nat admins showing all units with type badge and wing
- `+ Add Wing` button (NAT HQ only), `+ Add Squadron / Specialist Unit` button (wing/nat admin)
- Wing creation modal (`m-create-wing`) with code, short name, full name
- Squadron/Specialist Unit creation modal (`m-create-sqn`) with wing selector, unit type, code, name
- Wing admin: Wing selector pre-locked to own wing in unit creation modal (already locked in account creation modal)
- "Flights (Squadron Groupings)" renamed to "Local Squadron Flights (Sub-Squadron Groupings)" for clarity

**Security invariants maintained:**
- No access codes, hashes, or seeded codes in frontend JavaScript
- Wing admin cannot create units under another wing (403, enforced backend + frontend)
- NAT HQ admin cannot view existing plaintext codes or hashes (unchanged)
- All new mutations audited server-side

## v8 — Flexible Parade Night Timing Templates and Error Handling Fixes (2026-06-27)

**New backend features:**
- `TimingTemplate` model — squadron-scoped, named ordered timing schedules with effective-date range
- `TimingBlock` model — ordered blocks within a template (`is_instructional_period=True` generates a schedulable curriculum session; `block_type="flight_period"` is a timing slot before Period 1, NOT a squadron sub-group scope)
- `ParadeNightTimingOverride` model — per-parade-night template override (does not change future defaults); archived for audit retention
- `BLOCK_TYPES` constant: arrival, administration, roll_call, parade, flight_period, instructional_period, break, fatigues, debrief, dismissal, custom
- `ParadeNight.timing_template_id` — point-in-time recording of effective template at creation
- Alembic migration `c4d8e1f3a0b2` — creates timing_templates, timing_blocks, parade_night_timing_overrides tables and adds timing_template_id to parade_nights
- `routers/timing.py` — full timing template CRUD + apply-from-date + parade night override endpoints
- `create_parade` uses effective timing template to derive session_count when not explicitly provided; `ParadeIn.session_count` now defaults to `None` (use template or fallback)
- `test_timing.py` — 32 new automated tests; total suite 121 passed, 0 failed

**Connected frontend fixes and features:**
- **Fixed false "Cannot reach backend" error**: separated network failures from HTTP errors; shows accurate per-status messages (400 bad request, 401 session expired, 403 access not permitted, 404 not found, 422 validation, 500 server error)
- Settings page "Session Structure" card supplemented with "Timing Templates" card
- Timing template editor modal: block table with name, type, start/end times, auto-calculated duration, instructional period and optional checkboxes, up/down/delete controls, quick auto-populate N-session setup, apply-from-date functionality
- One-night override modal linked from parade night detail
- `S.timingTemplates` loaded from backend in `loadData()`; `getEffectiveTemplate(date, sqnId)` client-side helper
- `renderTimingTemplates()` populates settings card; highlights the current effective template
- `esc()` HTML-escaping helper added for user-controlled values in innerHTML
- All timing template mutations are audited server-side

**Effective-date model:**
- A new template with `effective_from=DATE` takes effect for all parade nights on/after that date going forward
- Past parade nights retain the `timing_template_id` recorded at their creation — they are never rewritten
- `apply-from-date` automatically closes overlapping open templates by setting their `effective_to` to the day before
- One-night override uses `POST /api/parade-nights/{id}/timing-override` — does not alter the squadron's default template

**Security invariants maintained:**
- No access codes, hashes, or seeded codes in frontend JavaScript
- No localStorage for operational data
- All timing mutations RBAC-enforced: viewers/auditors read-only; SQN admin own unit only; wing/national write only via Proxy/DI Mode
- SQN admin cannot edit another squadron's timing templates (403 enforced)
- Wing admin without proxy scope cannot write timing (403 enforced)

## v6 — Account Management, Access-Code Administration and Flight Assignment (2026-06-27)

**New backend features:**
- `Flight` model (local squadron grouping — no separate tenancy or permission scope)
- `users.flight_id` FK and `users.last_login_at` timestamp
- `generate_code()` — cryptographically random 8-char code (unambiguous alphabet)
- `auth.py` — sets `last_login_at` on login
- `routers/accounts.py` — 11 new endpoints: account CRUD, reset-code, disable/reactivate, flight CRUD/archive
- Alembic migration `b3e9f4c2a0d1` for the above schema additions
- `test_accounts.py` — 42 new automated tests; total suite 89 passed, 0 failed

**Security invariants enforced:**
- Access-code hashes never returned by any API endpoint
- Existing plaintext codes never returned by any API endpoint
- New plaintext code returned exactly once (create/reset response), never retrievable after
- Codes stored as PBKDF2-SHA256 hashes (passlib) only; never in frontend JS/localStorage/sessionStorage
- Flight assignment does not create separate tenancy or change permissions
- All account/flight mutations audited with actor, action, and object

**Connected frontend:**
- Account Management page added to navigation (role-aware visibility)
- Create Account modal with one-time code display
- Reset Code modal (auto-generate or manual set)
- Disable / Reactivate controls
- Edit Account modal (display_name + flight assignment)
- Flight management: create, rename (PATCH), archive
- Filter dropdowns pass `?wing_id=` / `?squadron_id=` to backend (server-side scoping)

**Demo data:**
- `seed_all.py` now creates Alpha Flight and Bravo Flight for 703 SQN
- 703 sqn_general demo user assigned to Alpha Flight

## v9.1.0 — Cadet Program Integration (Milestone 2, in progress)
- **Baseline preserved:** existing backend suite re-run before any change → 22/22 passing.
- Added Cadet Program backend: phases, program_packages, program_items, learning_hub_resources,
  program_item_deployments, source_files, source_conflicts, job_status models + Alembic migration.
- Added program inheritance/visibility enforcement (National→Wing→Squadron) and a coverage engine,
  both backend-authoritative and tenant-scoped.
- Added program routers (packages + lifecycle, items, learning-hub-resources, coverage, visibility,
  promotion requests) and seeds (phases, national/wing/703-local packages, LH resources, deployments).
- Added XLSX + PDF export (real files) and a generic source-import preview that reads real .xlsx/.xlsm.
- New backend tests for the visibility matrix, coverage, version snapshot and scope-edit enforcement.
- React/TypeScript frontend scaffold (login, dashboards, Cadet Program Library) wired to the API.

# Changelog

## v9.0.0 — National backend core (Milestone 1)
- New FastAPI + SQLAlchemy 2.x backend; National → Wing → Squadron multi-tenancy.
- 8 roles, hashed access codes, JWT (HTTP-only cookie), login rate-limit/lockout.
- Backend-enforced tenancy with IDOR regression test; Proxy + Delegated Intervention
  (reason required, audited).
- Curriculum (single source), parade nights/sessions (incl. not-delivered), readiness engine,
  publish/close validation, facilitators w/ rank history, resources + clash detection, cadets
  w/ gated sensitive notes, reports w/ drill-down, action items + automation, import
  preview/commit/rollback.
- Immutable audit log; security headers; CORS lockdown.
- Alembic migration; seeds (National HQ, 7 Wing, 16 squadrons, all role codes, 703 demo).
- Docker (dev + prod compose), Caddy/Nginx, backup/restore/smoke scripts, systemd, stress seed.
- Tests: 22 passing (pytest).
- Deferred: React frontend, Celery workers, full report catalogue, 100k stress run, XLSX/PDF export.
