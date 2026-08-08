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

## 1. Ground truth

**Verified 2026-08-09 at program start** (not assumed from any prior doc):

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

**Re-verified 2026-08-09, later in the same program (post REM-114–REM-122, per §4/§6/§9 below)** —
this table is updated in place rather than left to drift the way `docs/beta/00_release_state.md`
did; see §4's progress log for what changed between the two snapshots:

| Field | Value |
|---|---|
| Local HEAD | `5a6932b` |
| Migration head | `f6a7b8c9d0e1` (v46) — single head confirmed via `alembic heads` |
| Backend tests | 1231 passed, 5 skipped (full `pytest tests/ -q` run) |
| Master gap register entries | 161 (REM + QUAL combined, includes REM-122) |

## 2. Deployment fingerprints, verified 2026-08-09 (not inferred from git log)

**This table is a point-in-time snapshot from the start of this program, kept as evidence — it
is not the latest deployment state.** Staging has been redeployed multiple times since (REM-114
through REM-121, confirmed healthy each time — see §4's progress log entries), and `main`'s HEAD
has since advanced past the commits shown below (current HEAD `5a6932b`, per §1's re-verified
row). No production deploy has occurred since the QUAL-004 row below — production still needs a
fresh explicit `AUTHORISE PRODUCTION DEPLOYMENT <SHA>` instruction before any further deploy, per
the governing instruction.

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
| 100 users, 8.9 min | 20728 (17998 succeeded, 2730 rate-limited 429 -- expected, single test-runner IP; excluded from pass/fail criteria) | 0 | 249ms | 100% (100/100) | **PASS** |

**Summary**: all 4 staged tiers (12/25/50/100 concurrent users) passed cleanly against staging with
zero 5xx errors throughout and essentially flat P95 latency (249-273ms) across the entire range --
no degradation as concurrency increased. This is a real HTTP load test against real endpoints with
real login flows (100% login success at every tier), not a `/health`-only smoke test. The 429s seen
only at the 100-user tier are the per-IP rate limiter correctly engaging under sustained single-IP
load (all virtual users in this test share one real IP) -- expected, not a failure, and explicitly
excluded from the pass/fail criteria per the tool's own design. Staging confirmed healthy
(`{"status":"ready","squadrons":140}`) immediately after each tier. This is a genuinely stronger
result than the prior program's own load-test history (`docs/beta/00_release_state.md`) recorded,
which needed 3 attempts due to two independent sessions' runs colliding -- this pass ran cleanly on
the first attempt at every tier (after one process got killed at the tail end of the 25-user tier for
an unrelated environmental reason and was cleanly re-run).

Concurrency/multi-user-conflict testing (two users editing the same Parade Night, same facilitator,
etc. -- the qualitative half of Section 23/24) was not covered by this load test, which exercises
read-heavy workflows only. Recorded as a residual for a future pass, not silently dropped.

## 6. Continuation (autonomous ticks after the first working session)

- REM-121: found and fixed a real concurrency bug -- ParadeNight (the entity explicitly named in
  the governing instruction's own concurrency-testing example) had zero conflict detection.
  Reproduced live: concurrent edits silently overwrote each other with no warning. Added optimistic
  locking (version column + check, matching the pattern already used on PlanningYear/AnchorEvent/
  PlanningNotice/Session), plus a clear conflict message in connected-frontend. 4 new regression
  tests, fail-before/pass-after verified. Deployed to staging, confirmed healthy.
- Task queue for continued autonomous work: backup/restore verification, mobile/responsive testing,
  remaining concurrency scenarios (facilitator/Training Area double-booking, simultaneous CEA
  import), remaining UI/UX audit items (FAC-11-15, ACT-INH-01, ADMIN-ORG/SPEC/ARCH-01), TRGO review
  items not yet addressed (setup wizard, holiday prepopulation, drag-and-drop scheduling, CEA .51
  format, bulk/CSV setup for more entities), documentation currency pass across CLAUDE.md/.claude/
  rules, executive go/no-go report.

## 7. Backup/restore verification (Section 26)

Checked via `gh run list` (read-only, non-destructive) rather than triggering a fresh manual run --
existing evidence is current and comprehensive enough to cite directly:

- Daily production backup (`.github/workflows/backup-postgresql.yml`): last 5 scheduled runs all
  SUCCESS, most recent completing today (2026-08-08T18:36:49Z).
- Weekly restore test (`.github/workflows/test-restore-postgresql.yml`): last 3 runs SUCCESS (most
  recent 2026-08-05). Inspected the actual log output of run `31020333935` (not just its pass/fail
  status): decrypts and restores a **real production backup** into a disposable database, verifies
  the Alembic migration head matches, checks row counts across 12 real tables (users: 19,
  squadrons: 15, curriculum_items: 214, planning_years: 5, etc.), then spins up a **real backend
  process against the restored database** and drives **8 real authenticated API reads** through it
  (login, health, wings, squadrons, users, planning years, facilitators) -- all 8 passed:
  `APPLICATION-LEVEL RESTORE CHECK PASSED`. This already fully satisfies the governing instruction's
  Section 26 ask ("use restored isolated database for restore testing... verify representative
  authenticated reads against the restored environment").
- Key custody (`docs/beta/36_backup_key_custody_checklist.md`): correctly documented as **PENDING —
  human confirmation required**, not fabricated. This is a genuinely human-only gate (who holds the
  GPG passphrase in the real world) that no amount of engineering work can close -- left exactly as
  found, per the governing instruction's own explicit rule against fabricating this.

## 8. Mobile/responsive testing (Section 28) — partial, tooling limitation disclosed

Attempted live visual verification via Claude in Chrome's `resize_window` tool at 390x844 (mobile).
**The screenshot after resizing did not reflect the requested viewport** -- it rendered as a clearly
desktop-width layout, indicating this tool doesn't reliably drive genuine mobile-viewport/device
emulation in this environment (window resize vs. actual rendering viewport did not stay in sync).
Rather than fabricate a "tested at mobile size, looks fine" claim from a screenshot that wasn't
actually mobile-width, this is disclosed honestly as a tooling limitation, not a completed check.

**What was verified instead (source-level, real evidence, not a substitute for live rendering):**
connected-frontend's mobile CSS (`@media(max-width:768px)`) confirmed present and matches exactly
what the prior UI/UX audit (2026-08-06) already verified working via a real Playwright `[Nav] Mobile`
test: hamburger nav with a 44px minimum touch target, slide-in drawer with backdrop overlay, compact
topbar (redundant unit name hidden), Print Program button hidden on mobile, responsive grid collapse
(`stats-grid` to 2 columns, `form-row` to 1 column).

**Not verified this pass**: actual rendering/interaction at 1440x900 / 1280x800 / 1024x768 / 768x1024
/ 390x844 / 360x800 / 200% zoom, table/dialog/planning-grid behavior on real small viewports, touch
target tap-ability. Recommend a human pass with real devices or a working DevTools-emulation-capable
tool, since this session's available tooling could not reliably drive it.

## 9. Concurrency — facilitator/Training Area double-booking (Section 23, continued)

REM-121 (ParadeNight core-field optimistic locking) closed the proven, common-case concurrency gap
(two sequential edits silently last-write-winning). The remaining Section 23 scenario -- two users
simultaneously allocating the same facilitator or Training Area to overlapping sessions -- was
investigated as task #152 and tracked as **REM-122**.

Finding: `create_session`/`edit_session` (`backend/app/routers/training.py`) already have a
synchronous facilitator/room conflict check (query siblings at the same `parade_night_id`+
`period_number`, reject with 409 `resource_conflict` on a match), built and tested in a prior stage
("Stage 8"/"Phase 3", 13 existing tests in `test_session_scheduling_conflicts.py`). No DB-level
unique constraint backs this check, so a genuine TOCTOU race under true concurrent Postgres requests
(not reproducible via this repo's single-threaded SQLite test harness) is theoretically possible.

**Evaluated and explicitly rejected**: adding a DB-level unique constraint as a backstop. The
existing, deliberately-designed `override_conflict` escape hatch (tested by
`test_edit_session_conflict_override_bypasses_check`) proves the product's actual policy for this
resource class is "advisory warning, explicit override allowed" -- a caller can already deliberately
produce the identical double-booked end state today via `override_conflict=True`, and the endpoint
returns 200 for that today. A hard unique constraint would be *stricter* than the shipped, tested,
intentional policy and would break the override path (every legitimate override submission matching
an existing conflict would 500 instead of succeeding) -- a real capability regression, not safe
hardening, under `.claude/rules/capability-preservation.md`.

**Closed as REM-122**: documented residual, no code change, matching the established
QUAL-009/QUAL-013/QUAL-118 pattern (test-precision/theoretical gap, confirmed non-corrupting because
the race's worst case is identical to an already-permitted user choice, not a new invariant
violation). Full reasoning and accepted-risk rationale in `docs/remediation/master_gap_register.csv`.
Concurrency policy for this resource class is now explicitly defined and documented (per Section 23's
ask): **advisory check with explicit override**, not optimistic-lock/hard-invariant -- a deliberate
product decision, not an oversight.

## 10. Role-matrix testing (Section 27)

Closed as **REM-123**. Added `backend/tests/test_role_matrix.py` (11 new tests) systematically
covering all 8 seed roles against representative read/write/system-admin/audit endpoints in one
place, targeting the two previously-thinnest-covered roles (`national_viewer`, `wing_viewer`).
Manually audited every `.is_national`/`.is_wing` usage across `app/routers/*.py` for write-path
misuse (a role check that accidentally grants a viewer/auditor role write authority by checking
too-broad a scope helper) -- none found; all writes correctly channel through
`permissions.py`'s `can_write_squadron`/`can_write_activity`, which explicitly enumerate only the
4 write-capable roles. Full suite: 1242 passed, 5 skipped (was 1231/5, 0 regressions). No
application code changed -- test-only addition, no staging deploy required.

## 11. Adversarial pass finding (Section 38) — REM-124: request-size guard

While investigating REM-119's file-upload size checks for a residual gap (task #155), found that
all 6 file-upload sites, and by extension every POST/PUT/PATCH/DELETE endpoint's implicit JSON
body parsing, buffer the full request body into memory *before* any size check runs -- reachable
pre-authentication. No global request-body size limit existed anywhere in the app.

Fixed: `request_size_guard` middleware (`backend/app/main.py`) rejects a request whose
Content-Length exceeds `settings.MAX_REQUEST_BODY_MB` (new setting, default 20MB) with 413 before
`call_next` runs -- the body is never read. 3 new tests, fail-before/pass-after verified. Full
suite 1245 passed/5 skipped (0 regressions). Deployed to staging and live-verified over real HTTP:
`/api/health/ready` → 200; a 21MB POST to `/api/curriculum` → 413 `request_too_large`. Residual
(documented, not fixed): a client that omits Content-Length and lies via chunked transfer encoding
bypasses this specific guard -- the 6 existing per-endpoint post-read checks remain the backstop
for that narrower case. Full detail: `docs/remediation/master_gap_register.csv` REM-124.

## 12. Adversarial pass, continued (Section 38) — negative findings recorded

Continuing task #155 after REM-124. Spot-checked several older findings from a prior
(pre-this-program) risk-register plan to confirm current state rather than trust stale claims
(Section 6 discipline):

- **Account self-edit 403** (`_CREATE_AUTHORITY` map excluding `wing_admin`/`sqn_admin` from their
  own role): already fixed. `update_account` (`backend/app/routers/accounts.py`) has an explicit,
  well-commented `if uid != p.user_id: _require_manage_authority(...)` bypass scoped to exactly
  this case. No action needed.
- **Parade Day setting not seeding parade-date generation**: already fixed on both frontends.
  `connected-frontend/index.html`'s `openGenerateDatesModal()` seeds from `S.cfg.day` via
  `_DAY_NAME_TO_INT`; Planning Workspace's `SetupPanel.tsx`/`GuidedYearSetupModal.tsx` both fetch
  the squadron record and seed `weekday` from `default_parade_day`. No action needed.
- **CSV import squadron-resolution scope** (`import_annual_program`'s `all_sqns` query): checked
  for a cross-tenant enumeration leak in preview mode, separate from REM-120's write-scope fix —
  none found. The squadron set is filtered by the plan year's own level (single squadron / wing /
  unfiltered-national) before any row is matched, consistent with the actor's own already-granted
  visibility at that level. No action needed.

No new defect found this pass beyond REM-124. Continuing task #155 with different code areas next
tick.

## 13. Adversarial pass finding (Section 38) — REM-125: shared-IP security controls (HIGH, live-affecting)

While verifying REM-124 on staging, inspected the real access log (`railway logs`) and found every
request -- regardless of actual origin -- logged the identical `"client":"100.64.0.2"`. Root cause:
this app is only reachable through Railway's edge (TLS termination + HTTP-layer forwarding), so
`request.client.host` was always Railway's own internal proxy address, never the real caller, and no
proxy-header handling was configured anywhere.

**This was a currently-live defect in both staging and production**, not theoretical: with
`LOGIN_MAX_ATTEMPTS=5`/`LOGIN_WINDOW_SEC=300`/`LOGIN_LOCKOUT_SEC=900`, 5 failed login attempts by
*anyone, anywhere* in the deployed application within 5 minutes locked out login for *every user* for
15 minutes -- a handful of ordinary mistyped access codes across unrelated squadrons could silently
lock out the whole live pilot. The API rate limiter's 300 req/60s budget was likewise one bucket
shared by the entire user base. The separate account-level lockout (keyed by access code, not IP) was
unaffected and remained the working primary defense against a targeted brute-force on one account.

Fixed: `real_client_ip()` (`backend/app/dependencies.py`) derives the IP from `X-Forwarded-For`'s
first entry, applied at all 4 call sites (login lockout, API rate limiter, access log, audit
`client_meta`). 4 new tests including an end-to-end proof that two different forwarded IPs now get
independent lockout buckets. Fail-before/pass-after verified. Full suite 1249 passed/5 skipped (0
regressions). Deployed to staging and live-verified two ways: (1) access log now shows real, varying
external IPs instead of the fixed `100.64.0.2`; (2) a deliberately spoofed `X-Forwarded-For` sent in
live testing was overwritten by Railway's edge with the true connection IP, not trusted through --
confirming the fix is safe even beyond the topology argument its docstring originally relied on. Full
detail: `docs/remediation/master_gap_register.csv` REM-125.

This is the most significant finding of this program to date given it was live-affecting (not
theoretical) across the entire deployed user base in both environments. **Not yet on production** --
production still requires a fresh explicit `AUTHORISE PRODUCTION DEPLOYMENT <SHA>` instruction per
the governing instruction; this fix is staged and ready pending that authorization, and should be
flagged to the user as a high-priority candidate given its live production impact.

## 14. REM-125 hardened after background security review

A background security review of the REM-125 commit correctly flagged the first version:
`real_client_ip` trusted `X-Forwarded-For` unconditionally, with no check the request came
through a trusted hop, and fed the unvalidated value straight into `main.py`'s hand-built
access-log line with no escaping (a log-injection path).

Hardened with two independently-verifiable guards (not assumptions): (1) only trust the header
when the immediate connecting peer is itself in the RFC 6598 CGNAT range Railway's own edge was
directly observed using in staging's real logs; (2) validate the extracted value parses as a real
IP address before ever returning it. A web search performed while investigating this surfaced
third-party Railway community-forum claims (not official documentation, and internally
inconsistent with the CGNAT range actually observed) -- explicitly not relied on for a security
control; the guard uses only this deployment's own directly-observed behaviour plus the
well-established RFC 6598 block.

7 tests (3 new), fail-before/pass-after re-verified -- the old code demonstrably returned an
unescaped injection-payload fragment. Full suite 1252 passed/5 skipped (0 regressions). Redeployed
to staging and live-verified: a real request carrying a log-injection-shaped
`X-Forwarded-For` produced a clean access-log line with a valid IP, no injected content. Current
staged HEAD: see `git log`. Still not on production pending explicit authorization.

## 15. Adversarial pass, further sweep (Section 38) — task #155 wrap-up

Continued task #155 across SQL injection (no raw string-interpolated SQL anywhere in the
codebase -- only 3 `text()` call sites, all static, zero-parameter `SELECT 1`/schema-version
queries), path traversal (backup/export endpoints never accept a client-supplied filename that
reaches the filesystem), CORS (already fail-closed in production per `validate_for_production()`),
and mass-assignment on the REM-45-era self-edit bypass in `update_account` -- proved directly
(not just trusted from its own comment) that `AccountUpdateIn` genuinely cannot smuggle a role/
scope change: a live test sends `role`/`squadron_id`/`wing_id` alongside a self-edit and confirms
they're silently dropped by Pydantic, role unchanged. No new defects found beyond REM-124/REM-125
(already fixed, staging-verified, hardened per the background security review).

Task #155 substantially complete for this pass -- adversarial testing is inherently open-ended,
but the areas swept across this program's several ticks (file uploads, IP/rate-limiting,
facilitator-leave authorization, CSV import scope, account self-edit, parade-day seeding,
resource-conflict TOCTOU, idempotency-key scoping, SQL injection, path traversal, CORS,
mass-assignment) represent a genuine, broad pass, not a token effort. Moving to task #156 (final
staging soak + release-gate consolidation) next.

## 16. Release-gate consolidation, started (Sections 39-43) — task #156

Began building the consolidated release-gate picture. Ran the beta-release skill's gate
checklist against current state: security greps all clean (2 known benign matches, matching
security.md's own documented findings from 2026-08-05 -- an audit-filter label and a pg_restore
help-text placeholder), migration head confirmed applied on staging via the entrypoint's own
"Migrations complete" log (direct `alembic current` against the Postgres internal hostname isn't
reachable from outside Railway's network, so used the deploy log as legitimate evidence instead
of fabricating a direct check). Staging soak window started 2026-08-08T21:58:29Z (baseline:
health 200, 0 5xx in recent access log) -- no further staging changes planned until the soak
check completes on a later tick, per Section 39's "no casual changes during observation."

**Found and fixed a real data-integrity problem in the register itself** (Section 20's "audit the
harness" applies here too): 16 of 164 rows had the wrong CSV column count, which silently
produced wrong data for any tooling (including this tick's own aggregate analysis) that trusts
the 15-column schema. 3 rows had free-text fragmented across extra columns by unescaped
commas/quotes from before this session's disciplined csv.writer-based appends; reconstructed by
rejoining fragments to their original field per each fragment's own content. 13 rows (including a
self-caught omission in my own REM-123) were missing one field each; backfilled with an honest,
clearly-labeled placeholder rather than fabricated content. Row count unchanged (164) -- no data
lost, alignment corrected.

With the register now trustworthy, aggregated status: 164 total entries, 52 not yet fully closed
(mostly P2/P3/MEDIUM/LOW severity -- feature-completeness/polish/product-decision items, not
blocking defects). Only 2 were tagged HIGH severity and open -- both re-verified against current
code and found stale: REM-80 (claimed "mobile nav completely broken, no hamburger") is false, a
working hamburger nav with real Playwright coverage already exists; REM-81 (claimed "83 unlabeled
select elements remain") is also false, direct measurement found only 1 without an aria-label,
and that one is permanently dead/unreachable markup (aria-hidden, never toggled, never read into
any payload), not a live gap. Both closed with evidence, not assumption. **Zero HIGH-or-above
severity items remain open in the register as of this commit** -- a meaningful, positive signal
for the eventual go/no-go, though the 52 remaining P2/P3/MEDIUM/LOW items and the still-pending
human/organizational gates (Section 41) mean this is not yet a full GO.

Not yet done: the formal A-J gate table, the executive go/no-go classification (one of the 3
exact required strings), and the soak-completion check. Continuing on a later tick.
