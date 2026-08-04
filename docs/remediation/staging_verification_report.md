# Staging Verification Report

Living document — append a new dated entry per deployment, per
`.claude/rules/capability-preservation.md` §5 ("after every stage: ... record
tests/evidence").

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
