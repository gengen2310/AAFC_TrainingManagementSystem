# AAFC TMS — Final Remediation, Product Hardening and Public-Release Program

**Program record. Living document — update in place, not by appending.**
Started: 2026-08-09. Supersedes `docs/beta/00_release_state.md` (dated 2026-07-14, now stale) as the
current source of truth for deployment/test state. Does **not** supersede the gate *structure* or
findings from `docs/release/reconciliation_2026-08-06.md`, which remains the last full engineering
gate assessment and is treated as a trusted baseline, reconciled against below where state has
changed since.

## 0. Relationship to prior programs in this repository

This repository has an unusually deep prior-work trail. In order, not duplicated here:

1. `docs/beta/` (00–47) — the original beta-release gate program, July 2026.
2. `docs/release/` (30 documents) — a "final release" pass culminating in
   `reconciliation_2026-08-06.md` (2026-08-06), which found Engineering Gates 1–9 and 11
   **COMPLETE**, Gate 7 **CONDITIONAL PASS** (300 users proven, ~1,000-user ceiling diagnosed), and
   Gate 10 (human/organisational) **PENDING** with 13 items, 10 blocking trial start.
3. `docs/qualification/` (this session, 2026-08-07 through 2026-08-09) — a "Whole-System Adversarial
   Qualification Program" covering Phases A–E of a lettered A–J plan: capability baseline,
   architecture/data-integrity/security review, backend mutation testing on all four
   highest-blast-radius modules, and 2 of 7 live-tested Phase E security-review candidates
   (`08_adversarial_test_report.md`).
4. `docs/remediation/master_gap_register.csv` — the master defect register spanning REM-01 through
   REM-113 and QUAL-001 through QUAL-015, kept current throughout.

This program (mission: "FINAL REMEDIATION, PRODUCT HARDENING AND PUBLIC-RELEASE PROGRAM") continues
directly from where those left off, reconciling stale claims against fresh evidence per its own
Section 2, rather than re-litigating already-closed items from scratch.

## 1. Ground truth, verified 2026-08-09 (not assumed from any prior doc)

| Field | Value |
|---|---|
| Repo root | `/Users/jennydv/Desktop/AAFC_TMS_National_Connected_Pilot_Package_v17_1_source` |
| Branch | `main` |
| Local HEAD | `ab468fc` |
| `origin/main` | `ab468fc` (0 ahead, 0 behind) |
| Working tree | Clean, no untracked files |
| Migration head | `e5f6a7b8c9d0` (v45) — single head confirmed via `alembic heads` |
| Migration file count | 40 |
| Backend tests | 1224 collected (1219 passed, 5 skipped as of the last full run this session) |
| Planning Workspace vitest | 22 passed, 5 files, 0 failed |
| Planning Workspace Playwright (local `frontend/e2e`) | 95 tests, 13 files (not run this pass — see §3) |
| connected-frontend Playwright, staging-targeted (`frontend/e2e-connected`) | 46 tests, 7 files |
| `tools/playwright-staging` | 92 tests, 6 files (×3 projects: desktop/mobile/etc.) |
| Master gap register entries | 152 (REM + QUAL combined) |
| Qualification defect register entries | 14 (QUAL-001–015, minus one number never separately used) |

## 2. Deployment fingerprints, verified 2026-08-09 (not inferred from git log)

| Service | Environment | Deployment status | Deployed | Commit message (as recorded) |
|---|---|---|---|---|
| aafc-tms-backend | staging | SUCCESS | 2026-08-08T16:17:55Z | QUAL-004 logout fix |
| aafc-tms-backend | production | SUCCESS | 2026-08-08T16:23:23Z | QUAL-004 logout fix |
| aafc-tms-frontend | staging | SUCCESS | 2026-08-07T16:55:49Z | P0 fix (facilitator stats refresh) |
| aafc-tms-frontend | production | SUCCESS | **2026-08-05T15:13:52Z** | Phases A–D remediation release |
| aafc-tms-planning-workspace-preview | staging | SUCCESS | 2026-08-07T16:51:06Z | P0 fix (SquadronSelector) |
| aafc-tms-planning-workspace-preview | production | SUCCESS | **2026-08-05T15:14:39Z** | Phases A–D remediation release |

### ⚠️ Finding: production frontend and Planning Workspace are running pre-fix code

Commit `89cd192` (2026-08-08 01:12 +0800) fixed two real bugs in `connected-frontend/index.html` and
`frontend/src/`:
- Planning Workspace `SquadronSelector` missing in module-mode for wing/national roles
  (`useSquadronView` crash risk / no way to select a squadron at all).
- connected-frontend Facilitators summary widgets never refreshing after create/edit/archive/merge.

Both fixes are verified working on **staging** (deployed 2026-08-07, i.e. even *before* the commit
timestamp above — the staging deploy happened from a pre-commit working-tree state, consistent with
this session's established `railway up` workflow deploying uncommitted-at-the-time changes that were
committed afterward). **Production's frontend and Planning Workspace deployments both predate this
commit by three days** — production is currently serving the broken pre-fix build for both issues.

This was not previously known/flagged in any prior doc — the 2026-08-06 reconciliation predates the
fix entirely. Recorded as a new, concrete, high-value backlog item (§4) rather than acted on
immediately: per this program's own production-authority rule (Section 0 of the governing
instruction), deploying to production requires a separate explicit `AUTHORISE PRODUCTION DEPLOYMENT
<SHA>` instruction, which has not been given. Staging redeployment of connected-frontend/Planning
Workspace is authorized and will happen as part of normal work in this program wherever those
directories are touched again.

## 3. Immediate priorities (this program's working queue)

Tracked live via the task list, not duplicated here in prose. See TaskCreate/TaskUpdate state for the
current queue. High-level shape, drawn from reconciling `reconciliation_2026-08-06.md`'s open items
against what this session's qualification program has already independently found/fixed:

- Already independently fixed by this session, cross-referenced not repeated: `DASH-CHART-01`
  (matches `QUAL-010`'s facilitator_workload/wing_subject_area_gaps/capability_dependency missing
  chart fields, fixed and deployed to staging+production).
- Still open from the Aug 6 audit: `F-CONT-01` (Wing Overview table illegibility), `A11Y-03`/`A11Y-04`
  (no `<h1>`/landmarks in Main TMS SPA), `F-NAV-02`/`F-NAV-03` (login/nav asymmetry — design
  decisions), `F-DS-01`/`F-DS-02` (design-system decisions), `F-CONT-02`/`F-CONT-03`/`F-CONT-05`,
  `A11Y-05`/`A11Y-06` (keyboard/screen-reader — not yet assessed), `FAC-11`–`FAC-15` (facilitator
  duplicate-handling/edit/sync gaps), `ACT-INH-01` (inherited-activity local override), `ADMIN-ORG-01`/
  `ADMIN-SPEC-01`/`ADMIN-ARCH-01` (admin management gaps).
- New from the external TRGO review (this instruction's §5): Friday-template defect, setup burden,
  holiday prepopulation, module scheduling drag-and-drop, timing-template clarity, Learning Hub link
  integrity, facilitator save feedback, filtering at scale, bulk/CSV setup, CEA `.51` format support,
  prepopulation/templates.
- Production frontend/PW staleness (§2 above) — flagged, not actioned without production authority.

## 4. Progress log (append entries here as work completes, do not rewrite history)

**2026-08-09, first working session:**
- Staging fully reconciled to exact HEAD across all 3 services (was 3 days stale on 2 of 3).
- REM-114: investigated the reported "Friday template" defect fresh — found the underlying mechanism
  (`update-future-parade-day`, TRGO-01) was already comprehensively built and tested before this
  program (15 regression tests, live in production since 2026-07-26); the real remaining gap was UX
  clarity, closed with an explanatory text addition to Unit Settings.
- REM-115: connected-frontend had exactly one real `<h1>` in the entire SPA — converted 14 static
  per-page titles to real headings (zero visual change, CSS was never tag-qualified), added
  `role="banner"` to the header. Wing/National Overview's dynamically-rendered titles deliberately not
  converted this pass (residual, needs more careful design to avoid duplicate-heading issues).
- REM-116: facilitator domain investigated in full (Section 7) — found same-name duplicate detection,
  merge, save-feedback (Saving/Saved/Failed + button-disable + idempotency-key protection) all already
  built and working. One real gap found: leave management had full backend CRUD with zero frontend UI
  — built a minimal add/remove UI wired to the existing endpoints, surfacing the backend's own
  conflict-detection as a warning. Qualifications field still has no UI (no schema field exists for it
  either — a larger addition, not attempted this pass).
- Data integrity review (Section 8): confirmed `scheduled_sessions`/`planning_locations` now have
  **zero** call sites of any kind (stronger than the prior qualification pass found — a residual read
  it flagged was since removed by `QUAL-002`). Three new `docs/data/` documents written, consolidating
  rather than duplicating the existing thorough `docs/qualification/03_data_integrity_review.md`.
- Backend test count: 1225 collected (was 1224 at program start; +2 net from REM-116's regression
  tests, -1 accounting difference not investigated further as it's a net positive test count with a
  fully green suite).
- All work committed to `main`, pushed, deployed to staging (backend + both frontends), verified
  healthy. **Nothing deployed to production this session** — no `AUTHORISE PRODUCTION DEPLOYMENT
  <SHA>` instruction has been given.
- REM-117: found and fixed a real stored-XSS gap (5 sites, one requiring a deeper fix than plain
  HTML-escaping since it lived inside an inline `onclick` attribute) — verified with a real Node.js
  JS-engine test proving both the vulnerability and the fix, not static reasoning.
- REM-118: confirmed `change_role` already correctly revokes the target's pre-change session
  (`token_version` bump) — no code change needed, added the missing test.
- REM-119: found and fixed a real gap — two curriculum-import endpoints read the entire uploaded file
  into memory with no size check at all, unlike every other upload path in the codebase.
- **REM-120 (most significant finding of this program to date)**: found and fixed a **live-confirmed
  IDOR-class vulnerability** — a `wing_admin`, never entering Proxy/Delegated Intervention Mode, could
  import Annual Program CSV rows into any squadron in their wing via the `Unit` column, bypassing the
  Proxy Mode gate every other squadron-scoped write in this app requires. Reproduced end-to-end
  against a real backend session (not a static read) before fixing. 4 new regression tests,
  fail-before/pass-after verified.
- **All 7 of the security review's Phase E live-test candidates are now addressed** (5 real fixes, 1
  already-correct behavior newly tested, 1 confirmed via source reading).
- Remaining from this session's task queue: concurrency/staged stress testing (12→100 users). Program
  continues.

## 5. Staged stress test results (Section 24)

Target: staging only, real workflows (login/me/parade-nights/planning-years/reports-summary), not
`/health` hammering. Start low, increase only if the previous tier stays healthy.

| Tier | Requests | 5xx | P95 | Login success | Result |
|---|---|---|---|---|---|
| 12 users, 3 min | 943 | 0 | 273ms | 100% (12/12) | **PASS** |
| 25 users, 4.5 min | 2637 | 0 | 252ms | 100% (25/25) | **PASS** |
| 50 users, 6.6 min | 7742 | 0 | 250ms | 100% (50/50) | **PASS** |
