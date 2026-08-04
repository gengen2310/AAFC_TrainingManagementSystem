# Staging Verification Report

Living document — append a new dated entry per deployment, per
`.claude/rules/capability-preservation.md` §5 ("after every stage: ... record
tests/evidence").

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
