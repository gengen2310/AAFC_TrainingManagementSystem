# AAFC TMS — Master Remediation Plan

Durable source of context for the "Complete System Remediation, Integration and
Workflow Program" instruction. Update this continuously so a future session can
resume without relying on chat history.

## Branch / baseline

- Branch: `remediation/2026-08-04-complete-system-remediation`, created from `main` @
  `ab1dd8d` (2026-08-04).
- `main` at branch-creation time: working tree clean, 0 unpushed commits, Alembic
  head `b99b8f07eded` (single linear head).
- Immediately prior work on `main` (this same session, commits `971c160`..`ab1dd8d`):
  the "TMS / Planning Workspace Integration" pass — session-restore-on-refresh fix,
  Parade Day 7-day support, Account Management hierarchy ordering, Activities
  Restore, Getting Started Holidays step, Calendar default-to-today + Holidays
  overlay, Planning Year rename/archive/restore UI + dependency-gated delete,
  Account/Wing/Squadron dependency-gated permanent delete, page Refresh controls,
  Planning Workspace reading canonical Activities. All deployed and verified on
  staging before this branch was created — see `docs/remediation/staging_verification_report.md`
  for the specific evidence and treat these as **already-closed** against several of
  this instruction's own sections (16, 19, 10, 8, 7, 4) rather than re-doing them.

## Not a blank slate

This repository has multiple prior remediation/QA passes already on record:
- `docs/release/qualification_gap_register.md` (2273 lines) — GAP-01 through GAP-29,
  spanning TRGO features, security (GAP-24 stored XSS, fixed+verified), production
  incidents (GAP-16 backup failure, GAP-18 wrong backup target DB, GAP-20/27 wrong
  URLs), and capacity work (GAP-28/29). Most are already marked addressed/fixed in
  that document — `master_gap_register.csv` below **carries these forward by
  reference**, not by re-deriving them from scratch.
- `docs/beta/00`–`37` — a 38-document "Operational Release Gate" suite (page/function
  inventory, authoritative data model, role/navigation rationalisation, code
  inventory, stress/resilience, feature freeze, release evidence chain, backup key
  custody, UAT plan).
- `docs/release/final_*.md` — a second full "Final System Assurance" pass (source
  inventory, data traceability, role/scope matrix, security/accessibility/database/
  performance assessments, accelerated release report).

Per this instruction's own rule (compare before/after, prove parity, no false
closure), every prior claim is a **lead to re-verify against current code**, not a
fact to cite blindly — but re-deriving 2000+ lines of prior, dated, evidence-backed
work from zero would itself violate the instruction's efficiency intent. Stage 1
below is where reconciliation against this prior art happens explicitly.

## Staged order (per instruction Section 25) — status

| Stage | Scope | Status |
|---|---|---|
| 0 | Ground rules, baseline, capability manifest, gap register, key/variable inventory | **IN PROGRESS** — branch created, `capability-preservation.md` written, capability manifest v1 (static-analysis pass) written, gap register seeded from prior art + new instruction sections, this plan document written. Key/variable inventory not yet done. |
| 1 | Canonical domain map, API contracts, duplicate-model migration designs | **DONE (research/design; no code changes — Stage 1 is a design stage)** — reconciled against `docs/beta/28_authoritative_data_model.md` and `docs/api_reference.md` (both real prior-pass docs, verified against current code rather than re-derived). **Major new finding**: `ProgramPackage`/`ProgramItem` (9 models, 14 live registered endpoints) is a complete, real backend system with zero references in either frontend and no join to `CurriculumItem` — strong evidence it's an early (v9.1, the *first* migration in the chain) design superseded by `CurriculumItem`, never removed. Flagged as REM-26, **needs explicit product confirmation before any action** — not touched. Migration designs for all 5 duplicate/near-duplicate pairs written to `data_migration_plan.md` in the Section-4 table format; only the two already-confirmed-dead ones (`ScheduledSession`, `PlanningLocation`) have a concrete recommended action (retirement, pending authorisation), the rest are genuinely blocked on product decisions, not engineering effort. |
| 2 | Auth hydration, refresh, error classification, stale-data invalidation | **DONE** — session-restore-on-refresh and page-Refresh controls (prior stage, staging-verified). Error classification: audited both frontends' error handling against the full classification list (transport/401/403/404/409/422/429/5xx/cancellation/invalid-response) — most already solid; fixed 3 real gaps (no cancellation classification, no 502/503/504 retry, no invalid-response detection; Planning Workspace additionally had *no retry at all*), 4 new passing tests. 403 root-cause audit: spot-checked every squadron/year-scoped write's permission-helper selection across ops.py/organisations.py/planning.py (training.py already had 27 confirmed-correct uses) — **no misapplication found, architecture is sound**; did not mass-rewrite the 61 bare-"forbidden" messages (low value at that scale, most are correct simple role gates). Stale-data invalidation on scope/year/Proxy change: **verified already correct** in both frontends (connected-frontend's full-reload pattern on scope-switch/Proxy-entry-exit; Planning Workspace's React-Query key-based refetch via `useScopedSquadron()`) — no code change needed. One residual, lower-priority item: neither frontend cancels the now-stale in-flight request early (discarded safely, not aborted) — not fixed, judged disproportionate effort for this stage. |
| 3 | Training Stage / Facilitator Type / Subject Area reference data | **PARTIALLY DONE** — Subject Area was already a real, working example of this exact pattern (found, not built). Replicated it for Facilitator Type: new `facilitator_type_tags` table (migration `abc97c354bbb`, additive, disposable-Postgres-verified), same endpoints/permission model, seeded with the *actual* short codes in use (found the hardcoded dropdown's values didn't match its own display text, and most real data uses "Staff" — not one of the 4 originally-hardcoded options; fixed a related latent bug as a side effect). Frontend `#fac-type` is now API-driven with inline type creation. 17 new tests, full suite 1066 passed. Training Stage deliberately deferred — entangled with the still-open REM-26 (`ProgramItem`) decision; building it now risks a third parallel system. Session Status Reason / Notice Type / Training Area Capability not started — same proven pattern ready to replicate. |
| 4 | Squadron Details, Timing Templates, Parade Night generation/editing | **DONE** — research found Squadron Details (Full/Short Name, all timing fields), the full Timing Template block editor, and Parade Night generation (5 recurrence types, holiday/date exclusion, genuine preview-before-commit) were all already built; did not rebuild any of it. "Annual Program" confirmed a deliberately-retired redirect, functionality lives in Planning Workspace now. Added the one real gap: `Squadron.crest_url` (external URL, no new storage infra) — caught and fixed a would-have-shipped-broken issue where connected-frontend's own nginx CSP would have silently blocked every external crest image. |
| 5 | Parade Night cross-interface sync, Planning Year lifecycle | **DONE** — Planning Year rename/archive/restore/delete shipped (prior stage). This stage: added `PATCH /api/parade-nights/{id}` (the one real gap — no endpoint existed anywhere to edit a Parade Night's own date/term/times/type/notes after creation), gated on `closeout_status!='closed'`, audited, 7 new tests, wired into connected-frontend's Parade Night Detail modal. Added 2 cross-interface tests mirroring the proven Rooms pattern, confirming `ParadeNight` is already one canonical table both frontends read via the same `GET /api/parade-nights` endpoint (Planning Workspace's `ParadeNights.tsx`/`Calendar.tsx`/`Dashboard.tsx`/`WeeklyProgram.tsx` all call it directly) — no sync gap existed to fix. Corrected two stale docs found along the way: `docs/next-stage/08_year_rollover_procedure.md` said a rollover UI was "planned for V1" when it has existed in Planning Workspace's `GuidedYearSetupModal.tsx` since 2026-07-26; gap register REM-09 said "not yet investigated" for the same reason. Documented (not built) that Planning Year archiving is cosmetic-only (no dependent-record endpoint filters by parent year, `ParadeNight` carries no `planning_year_id` FK) — a real schema change with migration risk, not clearly requested by name, flagged as REM-30 for an explicit product decision. Full backend suite 1078 passed/5 skipped; connected-frontend e2e 27 passed/10 pre-existing-unrelated (baseline, confirmed via re-run against a genuinely fresh backend after an early run was contaminated by an hours-old leftover server process from earlier stages — see staging_verification_report.md for detail). |
| 6 | Activities, CEA, Holidays, anchors, unified Calendar | **PARTIALLY DONE** — research (Explore agent) found Anchor Events/Prep Rules already fully built (models, router, seed data, both frontends — the "NOT started" note below was wrong, correcting it here) and Holidays CRUD solid. Real gap found and fixed: Planning Workspace's `canonicalActivities()` used the legacy `/api/activities` path which silently dropped all Wing/National-owned Activities (their `squadron_id` is always NULL) despite its own comment claiming to show them — switched to the already-correct `scope_type=squadron` inheritance-aware path connected-frontend already uses (REM-31). Documented, not built: full multi-scope (Wing/National) calendar grid remains genuinely absent (REM-13, precise evidence this time — only squadron scope has `renderCal()`'s month grid; wing/national get a table view instead) and a dead `planningApi.wingEvents()` client method with a working-but-unwired backend endpoint (REM-32) — both flagged for explicit product/scope decisions rather than built speculatively mid-stage. |
| 7 | Mission Backlog, status lifecycle, Long Range, Weekly Program, notices | **PARTIALLY DONE** — research found this area mostly already solid: Mission Backlog (a computed view over CurriculumItem+Session, not a separate model), status lifecycle (Session.status/12 states, server-validated, both frontends call the same endpoint), and Weekly Program are all correctly built and consistent across both frontends. Real gap fixed: added `GET /api/sessions/{id}/status-history` (SessionStatusHistory rows were written on every transition but never read back — squadron-level users had no way to see a session's timeline) + a "History" toggle in connected-frontend's Parade Night Detail modal (REM-33). Documented, not built: connected-frontend has zero Notices UI (REM-34 — root-caused to the ParadeDate/ParadeNight architectural split from REM-29, needs a real design decision, not a same-stage port); Mission Backlog is curriculum-linked only, ad-hoc/non-syllabus sessions never appear in it (REM-35, product scope question). Long Range confirmed a real, working feature that's deliberately unreachable in connected-frontend for this pilot (`_PLANNING_PAGES=[]`) — added a code comment so this isn't mistaken for dead/incomplete code by a future engineer. |
| 8 | Facilitators, Training Areas, Equipment, conflicts | **PARTIALLY DONE** — research found Facilitator CRUD, leave tracking, Training Areas/Rooms, and Equipment all solid with one canonical table each. Fixed 3 real gaps: (1) `POST /api/sessions` (create) had zero conflict enforcement while `PUT` (edit) did — added the identical check (REM-36); (2) connected-frontend's direct-parade-night session "+ Add" cell silently dropped room/curriculum/notes on create due to a field-name mismatch against the actual `SessionIn` schema — fixed the mapping, notes now follow up via the existing PATCH endpoint (REM-37, P1 — real silent data loss, the highest-severity finding this stage); (3) Planning Workspace's Add Facilitator form ignored `FacilitatorTypeTag` entirely (hardcoded values that didn't even match connected-frontend's seed set) — wired it to the real reference-data endpoint (REM-38). Documented, not built: conflict-override UI only works from 1 of 6 Planning Workspace views, including not the default landing view (REM-39, real UI-wiring project, not a one-line fix); Training Area "capability" concept still doesn't exist beyond plain `capacity: int` (already tracked, not duplicated); `Session.equipment_required` is a fully dead column (informational only, no user-facing impact since nothing reads or writes it). |
| 9 | Readiness, dashboards, charts, higher-level parity, Training Summary migration | **PARTIALLY DONE** — verified the pre-authorized Training Summary→Dashboard merge (`.claude/rules/capability-preservation.md`'s one standing removal authorization) was **already fully executed before this program began** (commits from 2026-07-21/24), content parity confirmed, guarded by an existing e2e assertion — nothing left to do (REM-40). Squadron-scope readiness confirmed single-sourced and consistent between both frontends, no drift. Fixed 4 concrete "computed but not shown" gaps: `facilitator_leave_impact` chart added to connected-frontend's Dashboard; wing-phase-coverage and wing-capability data (previously fetched and silently discarded, with UI footnote text pointing at page names that don't exist) now rendered as real tables in connected-frontend's Wing Dashboard; wing-capability also newly wired into Planning Workspace's Wing Overview (new `reportApi.wingCapability()`); `ReportCatalogue.tsx`'s two stale rows corrected (REM-42). Documented, not built: `GET /api/dashboard/command` (readiness matrix, 8-week risk forecast, 4 delivery charts) has zero Planning Workspace consumer — a Wing/National Planning Workspace user sees a materially thinner, client-derived risk view instead of the rich command dashboard connected-frontend already has (REM-41, a real UI-wiring project comparable in scope to REM-13/REM-39, flagged for focused follow-up). |
| 10 | Accounts, organisations, Proxy, Intervention, 403 corrections | **PARTIALLY DONE** — Account/Wing/Squadron dependency-gated permanent delete, role-change endpoint, and account ordering already shipped (earlier this session). This stage's real finding: Planning Workspace's `/planning` page had **no squadron-scoping at all** for wing/national/system_admin — it silently showed an undifferentiated squadron's plan, completely decoupled from the SquadronSelector already in the same nav block. Fixed by wiring the existing `useScopedSquadron()` pattern into it (REM-43). While fixing that, found and fixed a real, pre-existing security-relevant gap it was about to make more reachable: `create_planning_year` had no Proxy/Intervention check at all for delegated squadron writes (REM-44, P1). **Found and, as a same-session follow-up, fixed** 3 of 4 sibling endpoints with the identical gap (`create_location`, `update_location`, `override_conflict` — 12 new regression tests, full suite 1100 passed/5 skipped) plus the equivalent fix for `import_annual_program`'s squadron-scoped write path (REM-45). One residual case intentionally not covered: Annual Program import into a wing/national-scoped year that routes CSV rows to *multiple* squadrons via the Unit column — a genuinely harder multi-squadron-delegation design question, not a same-pass fix. Documented, not built: Planning Workspace Account Management has partial parity with connected-frontend (REM-46); Planning Workspace has zero org-management UI at all, unclear if intentional (REM-47, needs product decision). Stage 2's earlier 403/permission-helper audit (ops.py/organisations.py/planning.py/training.py) remains sound — this stage's findings are additive, not a contradiction of it. |
| 11 | Learning Hub links, terminology, accessibility, visual consistency | **PARTIALLY DONE** — research found the Learning Hub link feature already correctly built in both frontends (uses the in-scope `CurriculumItem.learning_hub_url` field, confirmed architecturally separate from the off-limits REM-26/`ProgramItem`/`LearningHubResource` system — not touched) and terminology already consistent between the two frontends (Parade Night/Unit/Instructor-Facilitator, no drift found). Fixed 2 concrete gaps: (1) `delivered_with_issue`/`cancelled_late` — 2 of 7 valid session statuses were unreachable in connected-frontend's status dropdowns and rendered as a raw mislabelled grey badge with no CSS class if set via Planning Workspace (REM-48); (2) 39 of 40 icon-only modal-close buttons and 2 calendar nav buttons had no `aria-label` (REM-49). Documented, not built: connected-frontend's calendar day-chips still convey status by color only (no icon/text fallback like Planning Workspace's `StatusBadge`), and connected-frontend has no automated accessibility test suite at all (Planning Workspace has one, axe-core, ~15 pages, currently passing) — both flagged as real but separately-scoped follow-ups (REM-49). |
| 12 | Capacity, monitoring, complete regression, staging deployment, verification | **DONE** — capacity/monitoring research confirmed health checks (`/api/health/ready` genuinely checks DB connectivity, not a fake always-200 probe), structured logging, and the release monitoring plan (`docs/beta/43`) are all already adequate; error-tracking/APM and an in-app `/metrics` endpoint are genuine absences but correctly out of scope (real infra/spend decisions, not code fixes) (REM-52). Found and fixed one real, concrete issue: `config.py`/`database.py`'s DB connection-pool sizing comments still cited a stale "Supabase Session Pooler caps at 15" premise, when production has run on Railway-native Postgres since the GAP-18 fix — this exact kind of stale premise already caused one real incident (GAP-29, a mis-sized pool config that produced a >50% staging error rate) — corrected the comments and the regression test that enforced the stale number (REM-51). `TrainingArea.capacity` confirmed a pure display field with a dead soft-scoring hook, documented for a future product decision (REM-50). Final full regression run clean: backend 1091 passed/5 skipped; `tsc --noEmit` clean; frontend vitest 19 passed; Planning Workspace e2e 87 passed; connected-frontend e2e 27 passed/10 pre-existing-unrelated (identical baseline maintained across every stage of this program, 4 through 12). |

## Post-program review pass (2026-08-05, user-requested: "review of remaining REM items")

After Stage 12 closed the program, went back through every open Stage 6-12 gap-
register item to re-check whether any were actually tractable rather than
trusting the original sizing (REM-45 had already proven smaller than its initial
scoping once looked at closely, in the RE-45-follow-up work done right after the
program's closing report). Also found and fixed 7 gap-register rows with
unescaped-comma CSV quoting bugs (introduced when originally written via raw
heredoc) — fixed those first so the register is actually machine-parseable.

Converted from "documented, not built" to "fixed, tested, staging-verified":
- **REM-45** — closed the P1 security-relevant gap fully: all 4 sibling
  endpoints (`create_location`, `update_location`, `override_conflict`,
  `import_annual_program`) now require Proxy/Intervention for delegated
  squadron writes, matching `create_planning_year` (REM-44). 12 new tests.
- **REM-46** — Account Management parity in Planning Workspace: archive/
  restore/permanent-delete/change-role/unlock, mirroring connected-frontend's
  already-correct backend-scope-checked endpoints.
- **REM-49 (half)** — added a status icon prefix to Training Calendar day chips
  (not colour alone) in connected-frontend, closing the visual half of the
  finding. The automated-a11y-test-suite half remains a genuine, separately-
  scoped test-infrastructure project, not attempted.
- **REM-39 (half)** — wired the previously-dead `planningApi.conflicts()` into
  `PlanningWorkspace.tsx` so conflict override now works from every view, not
  just the single-night grid. The cell-level visual-indicator half (a warning
  dot on unopened session cells) remains a separate, view-by-view follow-up.

Left open, confirmed genuinely requiring a product/architecture decision or a
separately-scoped larger effort rather than a same-pass fix: REM-13 (unified
calendar grid), REM-26 (explicitly deferred to the user's own review), REM-30
(Planning Year archive cascading visibility), REM-32 (dead `wingEvents` client
method — needs a decision on whether the surface is wanted), REM-34
(connected-frontend Notices UI — blocked on a ParadeDate/ParadeNight linkage
design decision), REM-35 (Mission Backlog non-syllabus scope), REM-41 (Wing/
National command dashboard parity in Planning Workspace), REM-47 (Planning
Workspace org-management UI), REM-50 (`TrainingArea.capacity` enforcement).

Notable operational finding this pass: one e2e run took 1.1 hours (vs. the
normal ~40s) with cascading unrelated failures, diagnosed as local-machine
resource exhaustion after a very long continuous session (load average 9.85,
<100MB free memory) rather than a code regression — confirmed by disabling the
suspected new code path and reproducing the identical failure anyway, then
getting a clean run immediately after killing stray processes. Documented in
`staging_verification_report.md` rather than silently retried away.

## Working method going forward

- Every stage's changes get committed separately (small, coherent commits, one
  functional area each), tested (backend pytest + relevant frontend suite), and
  staging-verified before being marked STAGING VERIFIED in the gap register — not
  before.
- No item is silently dropped: anything descoped gets an explicit entry in the gap
  register with a reason, not a quiet omission.
- Continuing autonomously per user instruction (2026-08-04) — no per-stage approval
  gate, but every turn's real, verifiable progress is reported honestly rather than
  claiming full closure early.
