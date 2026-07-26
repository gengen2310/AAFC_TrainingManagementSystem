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
  commit skipped it, formula-injection cell neutralised), pushed.

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
  discipline applied). See commit message for full detail.

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

## GAP-09: Staging/load/production work not performed

- **Source**: brief sections 18-27, 31-34.
- **Previously deferred because**: the prior session held a self-imposed boundary against
  real infrastructure actions pending explicit confirmation.
- **Status this pass**: that boundary is explicitly superseded by the user's current
  instruction (section 2 of the current brief). Proceeding through staging deployment,
  staging security/load/soak testing, and production deployment per the exact protocol in
  sections 18-34, with the fail-closed Railway environment guard in section 4 applied
  before every infrastructure action.
