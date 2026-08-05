# Staging Verification Report

Living document — append a new dated entry per deployment, per
`.claude/rules/capability-preservation.md` §5 ("after every stage: ... record
tests/evidence").

## 2026-08-05 — Post-program review pass: REM-39 (conflict override in every Planning Workspace view)

Branch `remediation/2026-08-04-complete-system-remediation`, commit
`ef8e75e1eeb9983530a09eec0005278955382da7`.

**Pre-deploy gates**: no migration, no backend change (Planning Workspace only).
`tsc --noEmit` clean. `vitest run` → 19 passed. Planning Workspace e2e → 87
passed, 0 failed. connected-frontend e2e → 27 passed, 10 pre-existing
unrelated.

**Notable investigation this pass**: an interim e2e run took **1.1 hours**
(vs. the normal ~40 seconds) with 10+ failures across unrelated spec files
(dashboard, facilitators, resources, parade-nights, reports, session-
lifecycle, wing-proxy, year-rollover) — diagnosed as local-machine resource
contention after a very long continuous session (load average 9.85, <100MB
free physical memory at the time), not a code regression. Verified the root
cause was NOT this change specifically by re-running the single previously-
flaky test with the new `planning-conflicts` query explicitly disabled
(`enabled: false`) — it still failed identically, proving the query itself
wasn't the trigger. Killed stray processes, confirmed load had dropped, and
reran clean: 87 passed in 42 seconds.

**Deployed**: Planning Workspace only.

| Service | Deployment ID | Result |
|---|---|---|
| `aafc-tms-planning-workspace-preview` (staging) | `c947434d-6a30-45ae-8a6f-6ea91bec4906` | SUCCESS |

**Post-deploy verification**: `/planning` → HTTP 200.

**Known gap, same as prior entries**: no live browser verification that a
real unresolved conflict actually shows and can be overridden from, say,
Year view (no Chrome extension connectivity) — verified at the code/type-
check/e2e-regression level, plus direct reasoning about the exact data flow
(scheduled_session_id matching, cache invalidation) rather than an
end-to-end click-through.

## 2026-08-05 — Post-program review pass: REM-46 (Account Management parity) + REM-49 remainder (calendar chip icons)

Branch `remediation/2026-08-04-complete-system-remediation`, commit
`860121af73114ff87c3d344062e377f6ad61ab80`.

**Context**: continuing a review of Stages 6-12's remaining open gap-register
items to re-check whether any were actually tractable (REM-45 turned out
smaller than its original sizing). Also fixed 7 gap-register rows with
unescaped-comma CSV quoting bugs found while re-parsing the register
properly for this review.

**Pre-deploy gates**: no migration, no backend change (both frontends only).
`tsc --noEmit` clean. `vitest run` → 19 passed. Planning Workspace e2e →
87 passed, 0 failed (incl. the Account Management accessibility check).
connected-frontend e2e → 27 passed, 10 pre-existing unrelated (identical
baseline) — **one transient failure seen on an interim run** (`Accessibility
— Audit` test's login timed out) that reproduced as a pass in isolation and
disappeared entirely on a fresh-backend full rerun, consistent with the
same login/rate-limit contention pattern already documented for this suite,
not a regression from these changes.

**Deployed**: Main TMS and Planning Workspace (backend untouched).

| Service | Deployment ID | Result |
|---|---|---|
| `aafc-tms-frontend` (staging, Main TMS) | `e302b350-28f5-4a93-a03e-c70b5964b0b3` | SUCCESS |
| `aafc-tms-planning-workspace-preview` (staging) | `ea1551bc-a8b1-4f6f-8881-44957e896889` | SUCCESS |

**Post-deploy verification**: Main TMS `<meta name="app-build">` confirmed
exact commit SHA. `/planning` → HTTP 200.

**Known gap, same as prior entries**: no live browser verification that the
new Account Management actions (archive/restore/delete/change-role/unlock)
or the calendar chip icons actually render/function correctly against real
staging data (no Chrome extension connectivity in this background session)
— verified at the code/type-check/e2e-regression level only.

## 2026-08-05 — REM-45 follow-up (closed the flagged security gap from Stage 10)

Branch `remediation/2026-08-04-complete-system-remediation`, commit
`0cf2e8d724ed90a311f88daebf53619bc86af8bd`.

**Context**: after closing Stage 12 (the program's last planned stage), continued
directly to close REM-45 — the P1 security-relevant gap flagged in Stage 10
but deliberately not fixed at the time due to blast radius. `create_location`,
`update_location`, `override_conflict`, and `import_annual_program`'s write
path now all require Proxy/Delegated Intervention for delegated squadron
writes, matching `create_planning_year` (REM-44).

**Pre-deploy gates**: no migration. Backend `pytest tests/` → 1100 passed,
5 skipped (12 new). Planning Workspace e2e → 87 passed, 0 failed.
connected-frontend e2e → 27 passed, 10 pre-existing unrelated (identical
baseline). **Both e2e suites were re-run against a genuinely fresh backend
after an initial pass showed spurious failures** — running the same suite
twice against one long-lived backend process without reseeding produced
duplicate-date/rate-limit contamination (the identical false-alarm pattern
already documented in Stage 5's entry above); killing the process and
reseeding fresh resolved it completely, confirming the fix itself introduced
no regression.

**Deployed**: backend only.

| Service | Deployment ID | Result |
|---|---|---|
| `aafc-tms-backend` (staging) | `bad3f2ce-8a5a-446f-9e99-0d6e500b7076` | SUCCESS |

**Post-deploy verification**: `/api/health/ready` → ready, 140 squadrons.
`POST /api/planning/locations` unauthenticated → 401 (route live, auth
enforced).

**Known gap, same as prior entries**: no live browser verification that a
wing_admin/national_admin/system_admin session is actually correctly
blocked/allowed through the real UI flow on staging (no Chrome extension
connectivity) — verified at the code/test/contract level only.

**Residual limitation carried forward**: Annual Program import into a
wing/national-scoped plan year that routes CSV rows to multiple squadrons
via the Unit column is not covered by this fix — recorded in REM-45's
gap-register entry, not silently left uncovered.

## 2026-08-05 — Stage 12 (final stage: DB pool-sizing doc fix + full program regression)

Branch `remediation/2026-08-04-complete-system-remediation`, commit
`8a06a07f7977dd23d6163ddfd7c9b9202e17e09f`.

**Pre-deploy gates — full final regression across the entire program, not
just this stage's own small change**: backend `pytest tests/` → **1091
passed, 5 skipped, 0 failed**. `tsc --noEmit` clean. Frontend `vitest run`
→ 19 passed. Planning Workspace e2e (`playwright.config.ts`) → **87
passed, 0 failed**. connected-frontend e2e (`playwright.connected.config.ts`)
→ **27 passed, 10 pre-existing unrelated (`PLANNING_WORKSPACE_URL`
local-env gap) — the identical baseline held across every single stage
of this program (Stages 2 through 12), confirming no regression was ever
introduced across the whole remediation pass.**

**Deployed**: backend only (this stage's fix was a documentation/rationale
correction with no functional or frontend change).

| Service | Deployment ID | Result |
|---|---|---|
| `aafc-tms-backend` (staging) | `cb8d2574-4c42-40d5-9f24-443720d3dd9d` | SUCCESS |

**Post-deploy verification**: `/api/health/ready` → `{"status":"ready","squadrons":140}`.
`/api/health/db` → `{"status":"ok","db":"ok"}` — both live-checked directly
against staging, confirming the health-check infrastructure this stage's
research verified (genuine DB-connectivity checks, not fake always-200
probes) is actually working in the deployed environment, not just correct
in source.

**Program-wide known-gap summary** (see `master_gap_register.csv` for full
detail on every item below — not re-litigated here):
- No live browser (`claude-in-chrome`) was available in this background
  session for any stage — every stage's frontend-visible changes were
  verified at the code/type-check/e2e-regression/served-HTML level, never
  by an actual browser session. This is the single most consistent residual
  limitation across the whole program, honestly disclosed in every stage's
  entry above rather than glossed over.
- REM-45 (P1, security-relevant): 4 sibling endpoints to the one fixed in
  Stage 10 (`create_location`, `update_location`, `override_conflict`,
  Annual Program import) share the same missing-Proxy/Intervention-check
  gap. Flagged with elevated priority for prompt dedicated follow-up — not
  fixed in this program due to blast radius requiring its own test
  coverage per endpoint.
- REM-13/REM-41 (P2): full multi-scope Wing/National calendar grid and
  Wing/National command-dashboard parity in Planning Workspace — both real,
  substantial, well-scoped features documented but not built (comparable
  in size to a stage's worth of work each).
- REM-26: `ProgramItem`/`ProgramPackage`/`LearningHubResource`/
  `PromotionRequest` system remains explicitly untouched pending the user's
  own review, per their stated intent.
- Several smaller P2/P3 items (REM-30, REM-32, REM-34, REM-35, REM-39,
  REM-46, REM-47, REM-49's a11y-suite/color-only-chip halves, REM-50) are
  documented, not built — each with its own stated reason in the gap
  register, none silently dropped.

## 2026-08-05 — Stage 11 (Session status labels + accessibility fixes)

Branch `remediation/2026-08-04-complete-system-remediation`, commit
`e5b60d07518863a0d485e98b3784a8a5137422f3`.

**Pre-deploy gates**: no migration, no backend change (connected-frontend
only). connected-frontend e2e → 27 passed, 10 pre-existing unrelated
(identical established baseline).

**Deployed**: Main TMS only.

| Service | Deployment ID | Result |
|---|---|---|
| `aafc-tms-frontend` (staging, Main TMS) | `37161ed6-c21d-45d0-a6df-8c4c80c98385` | SUCCESS |

**Post-deploy verification**: `<meta name="app-build">` confirmed exact
commit SHA. **Live-checked the actual fix, not just the build fingerprint**:
`curl`'d the served HTML and counted `aria-label="Close"` occurrences →
39 (matches the exact number of modal-close buttons fixed), confirming
the change is really in the rendered output the browser receives, not
just present in source.

**Known gap, same as prior entries**: no live browser verification that
the new status dropdown options / badge colors render correctly for an
actual `delivered_with_issue`/`cancelled_late` session, or that a screen
reader correctly announces the new aria-labels (no Chrome extension
connectivity in this background session) — verified at the code/
e2e-regression/served-HTML level, not with an actual browser or screen
reader.

## 2026-08-05 — Stage 10 (Planning Workspace squadron-scoping + Proxy/Intervention fix)

Branch `remediation/2026-08-04-complete-system-remediation`, commit
`76ce841625df26a6ba8e5f3f9c0549ce976183e0`.

**Pre-deploy gates**: no migration. Backend `pytest tests/` → 1091 passed,
5 skipped (3 new; one existing test updated to correctly enter Delegated
Intervention rather than rely on the now-fixed permissive behaviour).
`tsc --noEmit` clean. `vitest run` → 19 passed. Planning Workspace e2e
(`playwright.config.ts`) → 87 passed, 0 failed (incl. wing-proxy specs).
connected-frontend e2e → 27 passed, 10 pre-existing unrelated (identical
baseline — connected-frontend itself wasn't touched this stage, but its
regression suite was still run since the backend permission model changed).

**Deployed**: backend and Planning Workspace (Main TMS untouched this stage).

| Service | Deployment ID | Result |
|---|---|---|
| `aafc-tms-backend` (staging) | `ef5386e0-2de6-4904-86b1-3bcfe2ce9c6e` | SUCCESS |
| `aafc-tms-planning-workspace-preview` (staging) | `a00db96d-722c-41b7-a2d2-42db75d9011c` | SUCCESS |

**Post-deploy verification**: `/api/health/ready` → ready, 140 squadrons.
`/planning` → HTTP 200. `POST /api/planning/years` unauthenticated → 401
(route live, auth enforced).

**Known gap, same as prior entries**: no live browser verification that a
wing_admin/national_admin/system_admin session now sees the correct
squadron's plan after picking one via the selector (no Chrome extension
connectivity in this background session) — verified at the
code/contract/e2e-regression/new-test level, not by an actual browser
session walking through the fixed flow on staging.

## 2026-08-05 — Stage 9 (Wing dashboard data rendering + Training Summary merge verification)

Branch `remediation/2026-08-04-complete-system-remediation`, commit
`cef77ac5c732a9ea09278b266677db91f0166a4b`.

**Pre-deploy gates**: no migration, no backend change (frontend-only fixes,
both frontends). `tsc --noEmit` clean. `vitest run` → 19 passed. Planning
Workspace e2e (`playwright.config.ts`) → 87 passed, 0 failed (includes the
Report Catalogue accessibility check, unaffected by the two corrected row
values). connected-frontend e2e → 27 passed, 10 pre-existing unrelated
(identical established baseline).

**Deployed**: Main TMS and Planning Workspace (backend untouched this stage).

| Service | Deployment ID | Result |
|---|---|---|
| `aafc-tms-frontend` (staging, Main TMS) | `829ae2ce-21ff-4f85-a70f-189c4e192e07` | SUCCESS |
| `aafc-tms-planning-workspace-preview` (staging) | `beb8780b-56d6-4041-b301-4abec108cdc2` | SUCCESS |

**Post-deploy verification**: Main TMS `<meta name="app-build">` confirmed
exact commit SHA. `/planning` → HTTP 200.

**Known gap, same as prior entries**: no live browser verification of the
new Wing Dashboard tables (connected-frontend) or the new capability
heatmap (Planning Workspace's Wing Overview) against real staging data (no
Chrome extension connectivity in this background session) — verified at
the code/contract/e2e-regression level only.

## 2026-08-05 — Stage 8 (Session conflict enforcement + silent data-loss fix + facilitator-type reference data)

Branch `remediation/2026-08-04-complete-system-remediation`, commit
`63df2ce2237788b867fb8189d8b2a10399a61e6d`.

**Pre-deploy gates**: no migration. Backend `pytest tests/` → 1088 passed,
5 skipped (4 new). `tsc --noEmit` clean. `vitest run` → 19 passed. Planning
Workspace e2e (`playwright.config.ts`) → 87 passed, 0 failed. connected-frontend
e2e (`playwright.connected.config.ts`) → 27 passed, 10 pre-existing unrelated
(same established baseline).

**Deployed**: all three staging services (backend, Main TMS, Planning Workspace).

| Service | Deployment ID | Result |
|---|---|---|
| `aafc-tms-backend` (staging) | `08aff83e-33b6-4a75-99d5-05808d6daad1` | SUCCESS |
| `aafc-tms-frontend` (staging, Main TMS) | `73ef945a-0eaf-405e-82af-bfb4018fa75a` | SUCCESS |
| `aafc-tms-planning-workspace-preview` (staging) | `2f9c8ac0-fea8-4806-95f5-89b81edde409` | SUCCESS |

**Post-deploy verification**: `/api/health/ready` → ready, 140 squadrons.
Main TMS `<meta name="app-build">` confirmed exact commit SHA. `/planning`
→ HTTP 200.

**Known gap, same as prior entries**: no live browser verification of the
actual fixed create-session flow (room/curriculum now saving correctly) or
the new facilitator-type dropdown's rendered behavior on the real staging
environment (no Chrome extension connectivity in this background session)
— verified at the schema/contract/test level, not by an actual browser
performing the flows end-to-end against staging.

## 2026-08-05 — Stage 7 (Session status-history endpoint + UI)

Branch `remediation/2026-08-04-complete-system-remediation`, commit
`13c42ec479ab6a0cd63d1f69e7ace3d4993489e9`.

**Pre-deploy gates**: no migration needed (no new columns — SessionStatusHistory
already existed, only a read endpoint was added). Backend `pytest tests/` →
1084 passed, 5 skipped (6 new). connected-frontend e2e → 27 passed, 10
pre-existing unrelated failures (identical established baseline).

**Deployed**: backend and Main TMS (Planning Workspace untouched this stage).

| Service | Deployment ID | Result |
|---|---|---|
| `aafc-tms-backend` (staging) | `879965b6-cb53-4067-83b4-ba7e0301c0de` | SUCCESS |
| `aafc-tms-frontend` (staging, Main TMS) | `e883771f-b17f-431d-b699-86437ed45033` | SUCCESS |

**Post-deploy verification**: `/api/health/ready` → ready, 140 squadrons.
Main TMS `<meta name="app-build">` confirmed exact commit SHA. `GET
/api/sessions/some-id/status-history` unauthenticated against live staging →
401 (not 404) — confirms the new route is registered and live.

**Known gap, same as prior entries**: no live browser verification of the
new "History" toggle's actual rendered behavior in the Parade Night Detail
modal (no Chrome extension connectivity in this background session) —
verified at the API/contract level and via e2e regression only.

## 2026-08-05 — Stage 6 (Planning Workspace canonical-Activities visibility fix)

Branch `remediation/2026-08-04-complete-system-remediation`, commit
`91938d12676aae08ae67e15fc37c096c694a895c`.

**Pre-deploy gates**: no migration, no backend change (frontend-only fix).
`tsc --noEmit` clean. `vitest run` → 19 passed (no regressions). Planning
Workspace e2e (`playwright.config.ts`, the React-app suite, distinct from
`playwright.connected.config.ts`) → **87 passed**, 0 failed, against a
freshly reseeded local backend.

**Deployed**: Planning Workspace only (backend and Main TMS untouched this
stage).

| Service | Deployment ID | Result |
|---|---|---|
| `aafc-tms-planning-workspace-preview` (staging) | `6a944919-6d5a-4a07-8e73-9e4f4cca0623` | SUCCESS |

**Post-deploy verification**: `/planning` → HTTP 200.

**Known gap**: no live browser verification that Wing/National activities
now actually render in the drawer's unified list on the live staging
environment (no Chrome extension connectivity in this background session)
— verified at the type-check/unit-test/e2e level and by direct code trace
of the request URL and response shape, not by an actual browser opening
the drawer against real Wing/National activity data on staging.

## 2026-08-05 — Stage 5 (Parade Night PATCH + cross-interface verification)

Branch `remediation/2026-08-04-complete-system-remediation`, commit
`98154a49bd32e80dee39eaf160583d448923e12d`.

**Pre-deploy gates**: no migration needed (no new columns). Backend
`pytest tests/` → 1078 passed, 5 skipped (9 new: 7 for the PATCH endpoint, 2
cross-interface). connected-frontend e2e → 27 passed, 10 pre-existing
unrelated failures (identical baseline) — **on the second run**; the first
run showed 32 failures across unrelated spec files (login/dashboard/XSS/
screenshots), traced to an hours-old leftover `uvicorn` process (PID
started `Wed 5 Aug 00:34:11`, left running since an earlier stage this
session) still bound to port 8000 with accumulated rate-limit/lockout
state — not a regression from this stage's code. Killed it, reseeded a
genuinely fresh backend (`python manage.py --seed`), re-ran, got the
established baseline. Flagging this explicitly since it could otherwise
look like a silently-dismissed regression.

**Deployed**: backend and Main TMS (Planning Workspace untouched, no
changes this stage).

| Service | Deployment ID | Result |
|---|---|---|
| `aafc-tms-backend` (staging) | `eba995eb-7ae9-487a-ae59-f3ed10bfd864` | SUCCESS |
| `aafc-tms-frontend` (staging, Main TMS) | `c444616d-5de0-4c50-820f-d45997394b9c` | SUCCESS |

**Post-deploy verification**: `/api/health/ready` → ready, 140 squadrons.
Main TMS `<meta name="app-build">` confirmed exact commit SHA
`98154a49bd32e80dee39eaf160583d448923e12d`. `PATCH /api/parade-nights/some-id`
unauthenticated against the live staging backend → 401 (not 404) —
confirms the new route is actually registered and live, not just present
in source.

**Known gap, same as prior entries**: no live browser verification of the
new "Parade Night Details" edit block's actual rendered behavior in
connected-frontend's detail modal (no Chrome extension connectivity in
this background session) — verified at the API/contract level (curl,
pytest) and via e2e regression, not with an actual browser opening the
modal and clicking Save Details.

## 2026-08-05 — Stage 4 (Squadron Crest URL)

Branch `remediation/2026-08-04-complete-system-remediation`, commit
`9d3e2165326ae44344f9ab586765a9a169cf998e`.

**Pre-deploy gates**: migration `81734c0f34bf` verified up/down/up against
disposable Postgres 18. Backend `pytest tests/` → 1069 passed, 5 skipped (3
new). connected-frontend e2e → 27 passed, 10 pre-existing unrelated failures
(identical baseline).

**Deployed**: backend and Main TMS (Planning Workspace untouched, not
redeployed).

| Service | Deployment ID | Result |
|---|---|---|
| `aafc-tms-backend` (staging) | `7f35b3e9-1056-41d7-a983-fe2addab3126` | SUCCESS |
| `aafc-tms-frontend` (staging, Main TMS) | `7eb77046-b87b-484b-be36-84d5109bf9e6` | SUCCESS |

**Post-deploy verification**: `/api/health/ready` → ready. `railway ssh ...
alembic current` → `81734c0f34bf (head)`. Main TMS build fingerprint confirmed.
**CSP header live-checked via `curl -I`** (not just read from source) —
confirmed `img-src 'self' data: https:` is actually being served by the real
nginx container, not just present in the config file that was edited. This is
the one item this stage where I specifically avoided the "verified by reading
source, not the rendered app" trap capability-preservation.md warns against.

## 2026-08-05 — Stage 3 (FacilitatorTypeTag reference data)

Branch `remediation/2026-08-04-complete-system-remediation`, commit
`5b2a9420e0d1c93c93941501c7653944299faad0`.

**Pre-deploy gates**: migration `abc97c354bbb` verified up/down/up against a
disposable Postgres 18 in both an empty-table and already-seeded starting state
(the latter simulating what a Postgres environment already carrying the same
data via a different path would see — no-op, no error). Backend `pytest tests/`
→ 1066 passed, 5 skipped (17 new). connected-frontend e2e → 27 passed, 10
pre-existing unrelated failures (identical baseline). Live local verification:
`GET /api/facilitator-type-tags` with a real ADMIN703 session token returned all
5 seeded global types correctly.

**Deployed**: backend and Main TMS (Planning Workspace untouched this stage, not
redeployed).

| Service | Deployment ID | Result |
|---|---|---|
| `aafc-tms-backend` (staging) | `2b56a061-a55c-4181-88d2-e5678cef3144` | SUCCESS |
| `aafc-tms-frontend` (staging, Main TMS) | `b0cee8d9-7b9e-433f-a372-c5fb940433ee` | SUCCESS |

**Post-deploy verification**: `/api/health/ready` → ready, 140 squadrons.
`railway ssh ... alembic current` confirmed `abc97c354bbb (head)` — the
migration ran automatically via `docker-entrypoint-staging.sh`'s own `alembic
upgrade head` step. Main TMS `<meta name="app-build">` confirmed exact commit
SHA. `GET /api/facilitator-type-tags` unauthenticated → 401 (correct — auth
required, endpoint live).

**Known gap, same as prior entries**: no live browser verification of the
`#fac-type` dropdown's actual rendered behavior (no Chrome extension
connectivity in this background session) — verified at the API/contract level
and via e2e regression, not with an actual browser opening the Add Facilitator
modal.

## 2026-08-05 — Stage 2 (error classification fixes)

Branch `remediation/2026-08-04-complete-system-remediation`, commit
`d937cd79fc6a41e1b5917fc5bc1f95005e5c5d84`.

**Pre-deploy gates**: backend `pytest tests/` → 1049 passed, 5 skipped (includes
an incidental fix to a date-fragile test found while running this gate — see
commit `83da2be`, unrelated to Stage 2's own scope). connected-frontend e2e → 27
passed, 10 pre-existing `PLANNING_WORKSPACE_URL` failures (identical baseline, no
new regressions). Frontend `tsc --noEmit` clean, `vitest run` → 19 passed (4 new
this stage).

**Deployed**: Main TMS and Planning Workspace staging (backend untouched this
stage, not redeployed).

| Service | Deployment ID | Result |
|---|---|---|
| `aafc-tms-frontend` (staging, Main TMS) | `d8466d2e-b5dc-43b5-84c4-3ee52aa18b37` | SUCCESS |
| `aafc-tms-planning-workspace-preview` (staging) | `156365fd-ca3d-4c69-a5bb-42b060e72978` | SUCCESS |

**Post-deploy verification**: Main TMS `<meta name="app-build">` confirmed exact
commit SHA. Planning Workspace `/planning` → HTTP 200. Backend `/api/health/ready`
→ `{"status":"ready","squadrons":140}` (sanity check, unchanged).

**Known gap, same as last entry**: no live browser verification available in this
background session (no Chrome extension connectivity) — the error-classification
fixes are verified at the unit-test and code level, not with an actual browser
hitting a real 502/cancelled-request/malformed-response scenario against staging.

## 2026-08-04 — "TMS/Planning Workspace Integration" pass (pre-dates this branch, on `main`)

Commit `ab1dd8dbece88d12c76db6c19b76bd0d53bc852e`.

**Pre-deploy gates**: backend `pytest tests/` → 1049 passed, 5 skipped, 0 failed.
connected-frontend e2e (`playwright.connected.config.ts`) → 27 passed, 10 failed
(all `PLANNING_WORKSPACE_URL`-not-set local-env gap, pre-existing, confirmed
identical failure set before and after this session's changes — not a regression).
Frontend `tsc --noEmit` → clean. Frontend `vitest run` → 15 passed.

**Deployed**: all three staging services —

| Service | Deployment ID | Result |
|---|---|---|
| `aafc-tms-backend` (staging) | `ee9799ab-8179-4efc-8e67-6e2c4e3d52fe` | SUCCESS |
| `aafc-tms-frontend` (staging, Main TMS) | `eba7f19e-082a-4fba-9556-3e7b64c58747` | SUCCESS |
| `aafc-tms-planning-workspace-preview` (staging) | `d501b1d2-d080-4644-a60b-261787a96483` | SUCCESS |

**Post-deploy verification**:
- Backend `/api/health/ready` → `{"status":"ready","squadrons":140}`.
- Main TMS rendered `<meta name="app-build">` → confirmed exact commit SHA
  `ab1dd8dbece88d12c76db6c19b76bd0d53bc852e`.
- Planning Workspace `/planning` → HTTP 200.
- **Session-restore fix, backend half, verified live**: logged in against staging
  with a real account, then called `GET /api/auth/me` with the resulting Bearer
  token directly → HTTP 200, correct `{"session": {...}}` shape matching exactly
  what `tryRestoreSession()` expects. This is real evidence the fix works
  end-to-end for the backend contract; the frontend half (does the browser
  actually stay logged in across F5) was **not** independently verified via a live
  browser this session — no Chrome extension connectivity available in this
  background session. Flagged honestly rather than claimed as fully verified; the
  connected-frontend e2e suite passing with no session-restore-path regressions is
  the next-best evidence available, not a substitute for the real thing.

**Known gap**: no live browser verification (claude-in-chrome unavailable in this
background session) for any of the UI-only items (Parade Day 7-day picker, Account
ordering visual check, Activities Restore button, Planning Year action buttons,
hard-delete typed-confirmation flows). Code-level correctness confirmed (syntax
checks, matching existing patterns), backend contracts confirmed via curl/pytest,
but the actual rendered UI has not been visually confirmed working. **This is a
real residual limitation, not silently omitted** — first item for whoever next has
live browser access to verify.

## Prior sessions (carried forward, not re-verified this pass)

See `docs/release/final_staging_feature_verification_accelerated.md` for the
detailed `system_admin`-role live staging verification (login, System Console,
Account Management at scale, `sa-scope-bar`, Wing Training Dashboard, Activities,
Curriculum, Audit Log, Delegated Intervention Mode entry/exit) from an earlier pass
this same multi-day engagement.
