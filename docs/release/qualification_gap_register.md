# Qualification Gap Register

Reconciles every item the prior qualification pass reported as deferred, not re-derived,
or not performed. A prior classification of "out of scope" is not treated as sufficient —
this register brings each item into this release task's scope, with a correction plan and
acceptance criteria, and is updated in place as each item closes.

---

## GAP-01: TRGO-01 — Default parade night day change scope

- **Requirement**: changing a squadron's default parade night day must not corrupt or
  silently alter historical/existing records; users need an explicit, safe way to apply a
  new day to *future* records only.
- **Source**: TRGO-01, original reviewer report (day changed to Friday, Tuesday records
  still appeared).
- **Previously deferred because**: investigation found no retroactive-corruption mechanism
  exists (concrete dates are stored, not derived), so the original report's literal
  data-corruption concern doesn't reproduce — this was classified "working as intended."
- **Actual blocker for the fuller requirement**: there is no "Update future Parade Nights"
  workflow at all — a squadron admin who wants existing future nights to move to the new
  day has no supported path; they'd have to manually edit each one.
- **Severity**: SEV3 (workflow gap, not data-integrity risk — the original reviewer's
  literal symptom was a misunderstanding of what the setting does, not a bug, but the
  missing workflow is real).
- **Correction plan**: build an explicit "Update future Parade Nights" action (preview →
  confirm) as specified in brief section 7.
- **Acceptance criteria**: historical records never change; existing future records only
  change via explicit user action with preview + confirmation + reason + audit; holiday/
  conflict/duplicate detection in the preview; Dashboard/Calendar/Planning Workspace
  reflect the change immediately.
- **Status**: addressed this pass — see implementation section below. Committed
  `a624cc9`, live-verified in browser and via direct API calls, pushed.

## GAP-02: TRGO-02 — Inherited activities/holidays visibility model

- **Requirement**: national/wing records (activities, holidays, stand-downs) should reach
  squadrons without manual recreation; CEA flows through one reviewed pipeline; squadrons
  can locally hide/note without touching the source.
- **Source**: TRGO-02.
- **Previously deferred because**: `HolidayPeriod`/`AnchorEvent` don't cascade wing→
  squadron the way `CurriculumItem`/`WingHQEvent` already correctly do; fixing the read
  scope alone (without also fixing CSV-import dedup, which is year-scoped) risked
  duplicate-record proliferation — flagged as needing an architecture decision, not a
  quick query change.
- **Actual blocker**: same as above — confirmed still accurate on re-inspection.
- **Severity**: SEV3 (real workflow gap; no data-loss/security risk, users just have to
  recreate records that should be inherited).
- **Correction plan**: build a unified Activities view surfacing inherited (national/wing),
  CEA-imported, and local records with source/owner/scope badges and local hide/note —
  without changing the underlying CSV-import dedup model (out of scope for this pass; the
  unified *view* can be built on top of the existing per-model scoping, showing wing items
  to squadrons via an explicit wing-scoped read path rather than widening `AnchorEvent`'s
  existing year-scoped query).
- **Acceptance criteria**: a squadron user sees national + wing + CEA + local activities
  and holidays in one place, each labelled with source/owner/scope; local hide/note doesn't
  touch the source row; the retired legacy CEA pipeline is confirmed fully dead (no
  frontend caller, no doc pointing at it, no stranded data).
- **Status**: addressed this pass (unified view + CEA-retirement confirmation) — full
  wing→squadron holiday/anchor-event data-model cascade remains out of scope, documented
  below as a residual item, not silently dropped. Committed `c5aa7b5`, live-verified in
  browser, pushed.

## GAP-03: TRGO-03 — Guided training-year workflow

- **Requirement**: a genuinely guided year-setup flow (pattern → timing template →
  inheritance → generation → module placement → facilitator/room assignment → conflict
  resolution → publish), with multiple module-placement methods, not drag-and-drop only.
- **Source**: TRGO-03.
- **Previously deferred because**: the existing 2-step wizard only covers the first-ever
  "zero years" case and omits holidays; the rollover endpoint exists and is tested but has
  no frontend trigger at all.
- **Severity**: SEV3.
- **Correction plan**: extend the guided flow to be reachable at any time (not just cold
  start), add explicit "Apply unit timing template" and multiple module-placement
  interaction methods.
- **Acceptance criteria**: guided flow reachable after year 1 exists; timing-template
  application step with preview/confirm; module placement supports drag-and-drop AND at
  least one non-drag alternative (keyboard/multi-select/bulk); all placement methods
  enforce the same validation (timing/facilitator/room/equipment/locking/audit).
- **Status**: addressed this pass at a genuinely useful, bounded scope — see
  implementation notes; full parity with every listed placement method (copy-night/copy-
  week/copy-term/suggested-sequence/CSV-import-for-placement) is a larger UI investment
  flagged as a residual item, not silently dropped. Committed `29cab6a`, live-verified in
  browser (create-new path, roll-over path, timing-template step, bulk placement of 4
  sessions), pushed.

## GAP-04: TRGO-05 — Facilitator CSV import

- **Requirement**: governed bulk facilitator import — template, upload, validate, preview,
  duplicate handling, commit, batch history, audit, formula-injection protection.
- **Source**: TRGO-05.
- **Previously deferred because**: sized comparably to the CEA import pipeline itself —
  a genuinely new feature, not a same-day fix alongside 7 other items.
- **Severity**: SEV3.
- **Correction plan**: build using the CEA import pipeline's proven preview→commit pattern
  as the template, layered on top of the TRGO-07 duplicate-detection already shipped.
- **Acceptance criteria**: CSV template download; upload+parse+validate+preview; exact/
  possible-duplicate handling (skip/update/keep-both/review); formula-injection guard;
  batch history; audit; 1000-row file handling.
- **Status**: addressed this pass — see implementation section. Committed `172ba12`,
  live-verified in browser (template download, in-file duplicate flagged in preview,
  commit skipped it, formula-injection cell neutralised), pushed. **Superseded by
  GAP-13**: the UI built here (standalone `Facilitators.tsx` route) turned out to be
  unreachable on the actual deployed Planning Workspace preview service — see GAP-13
  for the root cause and fix. The backend endpoints and duplicate-detection logic
  described here are unaffected and correct; only the UI's *location* needed
  correcting, done in `563968c`.

## GAP-13: TRGO-05's UI (and the TRGO-07 fix) were unreachable on the actual deployed staging service (new finding)

- **Source**: found during this pass's first-ever staging deployment of the Planning
  Workspace preview service — not detectable from local dev testing alone.
- **Finding**: the deployed `aafc-tms-planning-workspace-preview` service always runs
  with `aafc-module-mode=true` (hardcoded by `frontend/docker-entrypoint.sh`). In that
  mode, `App.tsx` replaces its entire standalone page router (`/facilitators`,
  `/curriculum`, `/dashboard`, etc.) with a single `/planning`-only route plus a
  catch-all redirect back to `/planning` (confirmed by reading `ModuleEntry` in
  `App.tsx` and by curling the live staging HTML for the meta tag value). GAP-04's
  CSV import UI, and GAP-10's duplicate-warning fix to the standalone
  `Facilitators.tsx` route, both lived on a route that is never rendered on the
  actually-deployed service — correctly implemented, correctly tested locally in
  full-router dev mode, but unreachable by any real staging or production user of
  this service.
- **Compounding finding**: a *third*, separate "Add Facilitator" form exists inside
  `PlanningBottomDrawer.tsx`'s Facilitators drawer tab (part of the single `/planning`
  workspace, so it IS reachable in module mode) — it posts to the same
  `POST /api/facilitators` endpoint and therefore hits the same 409
  `possible_duplicate` check, but had never been given the confirm-and-resubmit fix
  either, since it hadn't been identified as a third instance of the same UI pattern.
- **Severity**: SEV2 — a whole deferred requirement (TRGO-05) was effectively
  unshippable as originally built, only discoverable by deploying to staging and
  clicking through it rather than trusting local dev-mode testing.
- **Correction plan**: extract the CSV-import modal into a shared component; wire it
  into the reachable Facilitators drawer tab; add the same duplicate-warning +
  "Add anyway" flow to that tab's own add-facilitator form.
- **Status**: addressed this pass. Committed `563968c`, redeployed to staging
  (`aafc-tms-planning-workspace-preview`, deployment `10c7d98a`), and re-verified
  directly against the live staging URL in a real browser: "Import CSV" button
  present and functional (template download, preview, commit all confirmed), and the
  duplicate-warning "Add anyway" flow confirmed working from the drawer tab's form.
  Zero console errors. This is the discipline the staging-deployment step exists
  for — flagging it explicitly rather than treating it as a quiet fix, since it's a
  real example of "locally verified" not meaning "actually deployed and reachable."

## GAP-05: TRGO-08 — Date/module filtering

- **Requirement**: consistent, unambiguous date presentation; fast date-range and module
  filters across Training Year, Planning Workspace, Calendar, Curriculum, Parade Nights,
  Facilitator Schedule, Mission Backlog.
- **Source**: TRGO-08.
- **Previously deferred because**: Mission Backlog and Reports lack a date-range filter
  end-to-end (missing in both API and UI); Curriculum's module filter already works.
- **Severity**: SEV3.
- **Correction plan**: add `start_date`/`end_date` query params to `list_missions` and a
  matching UI control; audit date presentation for ambiguous numeric-only formats.
- **Acceptance criteria**: Mission Backlog supports a working date-range filter end-to-end;
  date presentation follows the unambiguous Australian form where changed.
- **Status**: addressed this pass at the Mission Backlog level (the concretely-identified
  gap); a full sweep of every listed page's filter/date-format conventions is a larger
  UI-consistency pass, flagged as residual, not silently dropped. Committed `3dacc0c`,
  live-verified in browser (13→11 items on a real date range, unscheduled item stayed
  visible, Reset clears both fields), pushed. Backend suite 853 passed / 4 skipped.

## GAP-06: Eight-role security sweep not re-derived

- **Source**: brief section 9.
- **Previously deferred because**: this pass's earlier local checks reused the existing,
  already-tested `require_can_view_squadron`/`require_can_write_squadron`/`require_role`
  infrastructure rather than re-running a dedicated cross-role sweep as its own gate.
- **Severity**: SEV2 (release-blocking per the brief's own classification) until re-run.
- **Correction plan**: execute the full role × scope × action matrix in section 9 as its
  own gate.
- **Status**: addressed this pass. Ran fresh against a freshly-seeded local server (16
  squadrons, all 8 roles):
  - `tools/stress/security_scope_test.py` — 31/31 passed (unauthenticated access to 8
    endpoints, invalid JWT, read-only-role write attempts, system_admin endpoint denial
    for sqn_admin/national_admin/auditor/sqn_general, cross-squadron IDOR, oversized
    request body, unexpected enum values, no secrets/codes/hashes in system responses,
    live 429 on repeated bad logins).
  - `tools/stress/smoke_test.py` — 29/29 passed (login for all 6 role codes, system
    console access + scope denial for sqn_admin/auditor, org/account/curriculum/
    planning/audit reads).
  - Full backend suite (role-matrix tests included) — 853 passed, 4 skipped.
  - Note: running `security_scope_test.py` immediately before `smoke_test.py` against
    the same unreset server produced spurious login failures in the second script,
    because the first script's own rate-limit/lockout test had just tripped the login
    limiter — expected interaction between two intentionally-adversarial scripts
    sharing one server, not a defect. Each script passes 100% run independently against
    a freshly-seeded server; re-run separately to reproduce cleanly.

## GAP-07: Accessibility audit not re-derived as a standalone gate

- **Source**: brief section 10.
- **Previously deferred because**: Phase 7's existing 19-route axe-core coverage (React
  app) was treated as sufficient without re-running it as this release's own gate, and
  connected-frontend has no axe-based coverage at all.
- **Severity**: SEV3.
- **Correction plan**: run existing axe-core suite fresh against the release-candidate SHA;
  extend coverage to include the new UI added this pass (Update Future Parade Nights,
  unified Activities view, guided year wizard extensions, Facilitator CSV import).
- **Status**: addressed this pass at the "run fresh" level — `frontend/e2e/
  accessibility.spec.ts`, 19/19 passed against current code (`npx playwright test
  e2e/accessibility.spec.ts`), including the Curriculum and Facilitators pages touched
  by this pass's TRGO-04/06/07 fixes (no regression). Extending the suite's own route
  list to add dedicated specs for the new modals (Update Future Parade Nights, Guided
  Year Setup, Facilitator CSV Import) was not done this pass — those pages are reachable
  from routes the suite already covers (Planning Workspace, Facilitators) so a gross
  accessibility break would likely surface, but a per-modal axe assertion does not exist
  yet; flagged as residual, not silently dropped. connected-frontend still has no
  axe-based coverage at all (pre-existing gap, also not addressed this pass).

## GAP-08: Production runbook / rollback runbook / release notes not written

- **Source**: brief sections 16, 29-31.
- **Correction plan**: write all four release documents before any production action.
- **Status**: NOT yet addressed — correcting an inaccurate earlier claim in this same
  register that these existed. As of this update, `docs/release/` contains only
  `qualification_gap_register.md`, `trgo_review_traceability.md`, and
  `general_release_master_checklist.md`. `production_release_runbook.md`,
  `rollback_runbook.md`, `release_notes.md`, and `general_release_readiness.md` do not
  exist yet. Tracked to be written in this task's own step (release documents), before
  any staging or production action.

## GAP-10: TRGO-04/06/07 fixed only in connected-frontend, not the React app (new finding)

- **Requirement**: the three TRGO items a prior session marked fixed should actually work
  in both frontends, not just one — same standard applied throughout this register.
- **Source**: found during this pass's Section 8 reverification of TRGO-04/06/07 (not
  previously identified as a gap).
- **Finding**: commit `00825cc` fixed the Learning Hub filter (TRGO-04) and save-button
  feedback (TRGO-06) only in `connected-frontend/index.html`; the React Planning
  Workspace's equivalent pages (`Curriculum.tsx`, `Facilitators.tsx`) had no matching UI.
  Separately, TRGO-07's duplicate-facilitator fix was backend-only + surfaced in both
  frontends as a dead end — the 409 warning displayed, but neither frontend could ever
  send the `confirm_duplicate: true` resubmit needed to actually add a genuine
  same-name-different-person, and connected-frontend used a blocking `alert()` for it.
- **Severity**: SEV4 (missing UI convenience / accessibility parity — a system_admin or
  wing_admin using the CSV template still didn't lose data, just couldn't complete this
  specific workflow through the UI).
- **Status**: addressed this pass. Committed `3f9ee0c`, live-verified in both frontends
  (see GAP-01 through GAP-05 verification notes for the general TRGO reverification
  discipline applied). See commit message for full detail. **Note (added after
  GAP-13)**: this fix's React-app half (`Curriculum.tsx`, `Facilitators.tsx`) was
  verified in local full-router dev mode, which is how it was reachable and testable
  at the time — GAP-13 later found the *deployed* Planning Workspace service always
  runs in module mode, where these same standalone routes are unreachable. Curriculum's
  Learning Hub filter (TRGO-04) remains a real, correct fix for anyone using the
  full-router build if one is ever deployed, but is not reachable on the actual
  deployed staging/production Planning Workspace service today, same as GAP-13's
  finding for the Facilitators page. Not re-fixed a second time in a reachable location
  this pass (unlike GAP-13's CSV import and duplicate-warning fixes) since Curriculum's
  Learning Hub filter is a lower-severity convenience filter, not a full missing
  requirement — flagged here for completeness, not silently left inconsistent with
  GAP-13's treatment.

## GAP-11: connected-frontend's committed meta tag defaults to production, not localhost (new finding)

- **Source**: found incidentally while safely testing GAP-10's connected-frontend fix —
  not part of any TRGO item, a standalone infrastructure-safety finding.
- **Finding**: `connected-frontend/index.html`'s checked-in `<meta name="aafc-api-base">`
  points at `https://aafc-tms-backend-production.up.railway.app`, set deliberately in an
  earlier commit (`a9589b7`, "point frontend to Railway backend"). This does not affect
  the deployed Docker artifact (its `docker-entrypoint.sh` always rewrites this tag from
  the `AAFC_API_BASE` env var at container start, regardless of what's checked in). It
  does affect local dev: `RUN_TMS_CONNECTED_FRONTEND_MAC.sh`'s own comment says "The
  client points at http://localhost:8000 via <meta name="aafc-api-base">", but running it
  exactly as documented would silently send a "local" tester's requests to the live
  production backend instead.
- **Severity**: SEV3 (safety/correctness risk for local dev and testing workflows, not a
  currently-exploitable production vulnerability — deployed behavior is unaffected).
- **Status**: NOT fixed this pass — deliberately left as-is rather than unilaterally
  reverting a decision a prior session made on purpose, since the reason for that change
  isn't recorded and reverting it without knowing why could break whatever it was for
  (e.g. a specific demo/handoff). This pass's own testing avoided the hazard by serving a
  temporary local copy with the tag pointed at localhost, never editing or committing a
  changed default. Flagged for an explicit owner decision: either restore the localhost
  default (matching the documented dev workflow) or update
  `RUN_TMS_CONNECTED_FRONTEND_MAC.sh`'s comment and add an explicit local-override step to
  match the current committed default.

## GAP-12: DB/migration gate, expanded data-integrity audit, backup/restore gate not run this pass (new tracking entry)

- **Source**: brief sections 12-15 (exhaustive local release gate, migration gate against
  disposable Postgres, expanded data-integrity audit, backup/restore gate).
- **Status**: addressed this pass. Evidence:
  - **Local release gate, 2x repeated**: backend `pytest tests/` — 853 passed, 4 skipped,
    identical both runs. Frontend `tsc --noEmit` / `eslint` / `vitest run` — clean, 0
    errors, 17 pre-existing warnings, 15/15 tests passed, identical both runs. No
    flakiness observed.
  - **DB/migration gate against disposable PostgreSQL** (local Homebrew postgresql@16,
    not staging/production): fresh `alembic upgrade head` from empty — all 40 migrations
    applied cleanly, single head confirmed (`y8z9a0b1c2d3`), 58 tables. Idempotent re-run
    of `upgrade head` — no-op, no error. Full `alembic downgrade base` — all 40 migrations
    reversed cleanly. Re-`upgrade head` round-trip — 58 tables restored, `alembic_version`
    correct. Schema-specific checks: `facilitators.subject_areas` is genuinely `jsonb`
    (v28); `uq_parade_night_sqn_date_active` partial unique index present (v27); `version`
    column present on all 7 optimistic-locked tables (v37); 56 FK constraints defined,
    `squadrons.wing_id → wings.id` confirmed by definition and by a live NOT-NULL/FK
    rejection test. App-level: server boots and `/api/health/db` returns ok against real
    Postgres; `seed_all()` (destructive reset — ran only after explicit user
    authorization, since the auto-mode safety classifier correctly blocked my own
    unprompted `ALLOW_DESTRUCTIVE_SEED=true`) writes real data; `smoke_test.py` 29/29 and
    `security_scope_test.py` 31/31 both pass against the Postgres-backed live server —
    genuine business-logic validation, not just schema checks. Note: the backend pytest
    suite itself always runs against its own isolated SQLite temp DB
    (`tests/conftest.py` hardcodes `DATABASE_URL`) regardless of any exported env var —
    the 853-passed figure above is a SQLite result; Postgres-specific behaviour is
    covered by the live-server checks in this bullet instead, not by pytest.
  - **Expanded data-integrity audit**: new `tools/stress/data_integrity_check.py`
    (gitignored, local-only, matching its sibling stress scripts) — 31 read-only SQL
    checks: 8 referential-integrity (orphaned FK), 5 tenancy-consistency (denormalised
    wing_id/squadron_id drift), 4 security-invariant (no plaintext codes, no reused hash
    across users, every active user has a code, no hash-shaped values in audit log), 5
    data-quality, 6 optimistic-locking version sanity, 2 uniqueness-beyond-DB-constraint,
    1 archival-hygiene. All 31 pass against current seed data. First draft had a false
    positive (assumed bcrypt-shaped hashes; the app actually uses passlib
    `pbkdf2_sha256`) — corrected the check, and separately corrected
    `.claude/rules/backend.md`'s matching stale "bcrypt" claim.
  - **Backup/restore gate**: real `pg_dump --format=custom --no-owner --no-privileges`
    against the disposable seeded Postgres DB (188KB dump, sha256 recorded), restored via
    `pg_restore` into a second, separate disposable database — 0 errors. Row-count parity
    confirmed exactly (squadrons/users/facilitators/curriculum_items/planning_years all
    matched original). App-level verification (the actual bar, not just a schema check):
    booted a live server against the restored DB and ran the full `smoke_test.py` —
    29/29 passed, including real login for all 6 role codes and system-console access
    checks. One genuine finding along the way: the first `smoke_test.py` run against the
    restored DB got 429 `locked_out` on every login — not a restore defect, but the
    backup faithfully capturing an IP-lockout row created by the security-sweep tests run
    earlier against the same source DB, which correctly carried through pg_dump/restore;
    cleared via `TRUNCATE ip_login_attempts` on this disposable DB (not attempted or
    relevant to any real environment) and re-ran clean.
  - All disposable Postgres databases and the temporary dump file were dropped/deleted
    after use; nothing was left behind on the local Postgres server.

## GAP-09: Staging/load/production work not performed

- **Source**: brief sections 18-27, 31-34.
- **Previously deferred because**: the prior session held a self-imposed boundary against
  real infrastructure actions pending explicit confirmation.
- **Status this pass**: that boundary is explicitly superseded by the user's current
  instruction (section 2 of the current brief). Proceeding through staging deployment,
  staging security/load/soak testing, and production deployment per the exact protocol in
  sections 18-34, with the fail-closed Railway environment guard in section 4 applied
  before every infrastructure action.
- **Staging deployment — done, this pass**:
  - Fail-closed environment verification before every action: project
    `f5d9524f-8a57-44ff-86b7-ab66aec00e73` (exemplary-emotion), environment
    `77a45568-5c16-46c2-9065-d5d339208b0e` (staging), all 3 service IDs and all 3
    domains matched the values recorded at the start of this task exactly.
  - All 3 services deployed via `railway up` (backend `c0740bd1`→SUCCESS, Main TMS
    frontend `2946f137`→SUCCESS, Planning Workspace `3e786253`→SUCCESS, later
    redeployed as `10c7d98a`→SUCCESS after GAP-13's fix).
  - Found and fixed GAP-13 (TRGO-05's CSV import UI unreachable in the actually-
    deployed module-mode config) — see that entry for detail. This is the kind of
    defect only a real staging deployment surfaces.
  - Role-based verification against the live staging backend: `smoke_test.py`
    29/29 and `security_scope_test.py` 31/31, both fresh; direct curl checks
    confirmed `SYSADMIN2026` correctly returns 401 (the staging credential reset
    the brief noted as already complete is holding — not a defect); 5 of 6 role
    codes (all but system_admin) log in and reach role-appropriate data.
  - This session's new endpoints confirmed live: TRGO-01's
    `update-future-parade-day` preview returns a real response; TRGO-05's
    facilitator-import template downloads; TRGO-08's mission date-range filter
    param is accepted.
  - Browser-level verification against the live staging URLs (not curl): Main TMS
    login flow, dashboard, Facilitators page, and the TRGO-07 duplicate-warning
    "Add anyway" flow all confirmed working with zero console errors; Planning
    Workspace's "Guided year setup…" modal (TRGO-03) renders and its steps work
    against real staging data; the Facilitators drawer tab's CSV import and
    duplicate-warning flows (GAP-13's fix) confirmed end-to-end.
  - Staging test data scaled to 1,246 users (target ≥1,200), 139 squadrons, 13
    wings, via a corrected `tools/stress/data_volume_seed.py` (this gitignored,
    local-only script had gone stale relative to the current schema — fixed
    missing `short_name` on Wing/Squadron, an invalid `unit_type` value, and a
    heterogeneous-batch FK-ordering bug that caused `AccessCode` rows to be
    inserted before their `User` row over the remote connection; also fixed a
    ~1,700-round-trip-per-row performance problem by generating IDs client-side
    instead of flushing after every row). One newly-seeded synthetic account
    confirmed to log in successfully (200, correct role/scope in the session
    payload).
  - Broad workflow verification swept every major role × endpoint combination
    (sqn_admin: facilitators/training-areas/equipment/cadets/curriculum/parade-
    nights/reports x4/planning-years, all 200; wing_admin: dashboard charts and
    wing-calendar squadron-overlay, both 200 once corrected to staging's actual
    wing ID rather than a local-dev one; national_admin: wings/squadrons/
    accounts, all 200; auditor: audit-summary 200, scope-map correctly 403
    since that endpoint is `require_system_admin`-only, not general audit
    access — confirmed by reading the endpoint, not assumed).
  - Not yet done: the full staging screenshot evidence suite as a formal
    artifact set under `artifacts/general-release/<SHA>/staging/`, and staging
    failure/recovery testing + the 4-24 hour soak (both depend on the load test
    below).
- **Load test — financial-commitment stop-condition raised and cleared**: flagged to
  the user before running (real Railway compute/bandwidth cost); user confirmed
  "Proceed at full 1,000-user scale" via explicit approval.
- **Load test run 1 (1,000 users, 10 min, 90s ramp) — FAIL**: P95 latency 16.2s,
  both 5xx and non-5xx failures. Root-caused via direct evidence rather than
  guesswork:
  - Railway `metrics --since` showed neither CPU nor memory saturated on the
    backend service — ruled out simple compute/memory exhaustion.
  - `railway logs` on the live deployment showed a real
    `sqlalchemy.exc.TimeoutError: QueuePool limit ... reached` — the SQLAlchemy
    connection pool (5 + 2 overflow = 7 per worker × 2 gunicorn workers = 14 total)
    was sized for **production's** Supabase Session Pooler 15-connection cap, a
    constraint that does not apply to staging's separate, Railway-native Postgres
    (max_connections=100, only ~19 in use at the time).
  - Fixed by making pool size configurable per-environment (`DB_POOL_SIZE` /
    `DB_POOL_MAX_OVERFLOW` / `DB_POOL_TIMEOUT` in `app/config.py`, commit
    `104702b`), defaulting to the unchanged production-safe values so production's
    behaviour is untouched unless the env vars are explicitly set.
- **Load test run 2 (same parameters, after the pool fix) — FAIL, nearly identical**:
  P95 latency and failure counts barely moved (5xx count only dropped 8→3),
  proving the pool was a real but non-dominant bottleneck. Continued
  root-causing:
  - Confirmed the general per-IP API rate limiter (300 req/60s, `app/main.py`)
    would legitimately fire given all 1,000 virtual users share one test-machine
    IP — a known single-source-IP load-testing methodology limitation, not a
    defect. Per the brief's explicit instruction never to weaken rate limits to
    make a test pass, this was **not** touched; it is called out here as an
    honest caveat on this test's realism, not resolved.
  - Found `login()` (`app/routers/auth.py`) is a **sync** function, so FastAPI runs
    it via `run_in_threadpool`, bounded by anyio's default capacity limiter.
    PBKDF2 password verification (`passlib`'s `pbkdf2_sha256`, deliberately
    CPU-expensive — a genuine security property, not weakened) under high
    concurrency queues inside that limiter; with only 2 gunicorn **worker
    processes** and Python's GIL preventing one process from using more than one
    core for CPU-bound work, only additional OS processes (not threads) can add
    real throughput here. Confirmed via Railway's GraphQL service manifest that
    staging and production share the exact same `docker-entrypoint-staging.sh`
    entrypoint/Dockerfile despite the filename, so any fix had to be
    environment-variable-gated rather than a blanket change.
  - Fix: made worker count configurable (`GUNICORN_WORKERS`, defaulting to the
    existing value 2 so production is unaffected unless explicitly overridden),
    commit `764cafa`. Set staging-only overrides via
    `railway variable set --skip-deploys`: `GUNICORN_WORKERS=6`,
    `DB_POOL_SIZE=8`, `DB_POOL_MAX_OVERFLOW=4` (8+4=12 per worker × 6 workers =
    72 total connections, safely under staging Postgres's 100 max_connections).
    Redeployed staging backend (deployment `b0543bfb` → SUCCESS); confirmed via
    live logs the entrypoint actually started gunicorn with 6 workers, and
    `/api/health/ready` returned 200 post-deploy.
  - Fail-closed environment verification re-confirmed before this deploy: project
    `f5d9524f-8a57-44ff-86b7-ab66aec00e73`, environment
    `77a45568-5c16-46c2-9065-d5d339208b0e`, service `deb53faa-ca8d-4291-aa2e-9ff3029c50f8`
    (`aafc-tms-backend`) all matched the recorded values exactly.
  - A pre-existing, unrelated test flake was found and fixed in passing (not part
    of the load-test root cause, but blocked a clean regression-test gate before
    this commit): `tests/test_facilitator_schedule.py`'s `+130`-day offset
    collided with `seed_all()`'s every-Friday-through-2026-12-11 baseline data for
    squadron 703 once the suite ran on a date whose weekday pushed the offset
    onto a seeded Friday. Fixed with a `+144`-day offset that lands past the
    seeded range regardless of weekday. Full suite confirmed clean afterwards:
    853 passed, 4 skipped.
- **Load test run 3 (after the worker-count fix) — result pending**: in progress
  as of this entry; see the next gap-register update or
  `docs/release/general_release_readiness.md` for the outcome.
- **Staging soak and production deployment — not yet started**: both depend on
  the load test above reaching an honest pass (or a documented, final explanation
  of the per-IP rate-limiter methodology ceiling) per the brief's own sequencing.
