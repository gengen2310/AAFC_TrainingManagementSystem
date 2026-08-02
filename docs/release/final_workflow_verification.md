# Final Critical End-to-End Workflow Verification (Stage 5, partial)

Honest scope statement first: literally clicking through every critical workflow in a
real browser, for every role, is not something this pass completed exhaustively —
that is a genuinely large undertaking on its own. This doc records what *was* verified
live this pass, and is explicit about what instead relies on the existing 1008-test
automated suite (`backend/tests/`, including dedicated files named for exactly this
purpose: `test_planner_v14.py`, `test_planning.py`, `test_curriculum_import.py`,
`test_accounts.py`, `test_system_admin.py`) rather than fresh manual click-through.

## Verified live this pass (fresh local backend + isolated frontend copy, never a deployed environment)

1. **Login, `system_admin`, full flow through the real UI** (account type → role →
   access code → sign in) — landed on System Console with correct build info,
   platform health, CORS origins list, zero console errors.
2. **Login, `sqn_admin` (703 Squadron), full flow through the real UI** (account type
   → wing → squadron → role → access code → sign in) — landed on the squadron
   Dashboard with correct scope chip ("SQN"), zero console errors.
3. **Dashboard** (`sqn_admin`): "Tonight & This Week" and "This Term — Session
   Delivery" sections render with real computed data (upcoming parade nights,
   staffing status, a weekly delivery chart) — not placeholder/broken states.
4. **Curriculum** (`sqn_admin`): full curriculum list renders grouped by phase
   (Orientation/Initial/Junior/etc.), correct NAT HQ badges, correct delivered/
   planned/unscheduled status chips, filter controls present and functional.
5. **Parade Nights** (`sqn_admin`): list renders real historical data — a fully
   delivered parade night (6 Feb 2026) showing **15 real sessions**, each with a
   real assigned facilitator, real room, and correct delivered-status styling. This
   is live proof the full schedule→facilitator→room→delivery pipeline produces
   correct data end-to-end (from existing seed data, not freshly created in this
   session — see "not completed" below).
6. **Weekly Program** (`sqn_admin`): parade-night selector correctly populates from
   real data, print-view renders the correct squadron/wing header and correctly
   reports "No sessions match the filter" for a genuinely empty future parade night
   (30 Jan 2026) rather than erroring.
7. **Account Management** (`system_admin`) — see GAP-24's verification in the gap
   register: full live account-creation-through-rendering cycle, including the
   before/after XSS check.
8. **Cross-Wing tenancy** (`wing_admin`) — see Stage 4 (`final_role_and_scope_matrix.md`):
   6 live cross-Wing IDOR/proxy tests via direct authenticated API calls.
9. **Curriculum CSV import with mixed core_status** — not re-clicked through the
   file-upload UI this pass, but verified end-to-end via the new automated test
   (`test_import_csv_core_status_column_is_respected`, added this session) which
   exercises the real HTTP multipart upload endpoint, not a unit-level shortcut.

## Not completed live this pass (relies on the automated suite instead)

- Actually creating a new session on an empty parade night through the UI
  (attempted; the "Weekly Program" page turned out to be a print/report view rather
  than the session editor — the real editor is reached from a different entry point
  not located within this pass's time budget).
  **Closed by Stage 11**: `frontend/e2e/parade-nights.spec.ts`'s
  `sqn_admin can add a session to a parade night` (real Playwright browser test,
  not a unit shortcut) passes clean. `connected-frontend`'s own equivalent flow is
  covered separately in Stage 11's `e2e-connected` run.
- Full click-through of Proxy Mode / Delegated Intervention entry and exit via the
  UI. **Closed by Stage 11**: `frontend/e2e/wing-proxy.spec.ts` covers both
  `wing admin can enter and exit proxy mode` and `wing viewer cannot enter proxy
  mode` as real browser tests, corroborating Stage 4's direct-API tenancy tests
  from the UI layer too.
- Facilitator CRUD, Activities, Resources, Wing/National dashboards, System Console's
  maintenance-mode toggle and backup-download button — not clicked through live this
  pass. All have dedicated automated test coverage in `backend/tests/`.

## Recommendation

Given the size of what remains, a dedicated Stage 5 continuation (or a
`claude-in-chrome`-driven scripted pass covering the remaining pages per role) should
run before final release sign-off, rather than treating this partial pass as
sufficient on its own — flagged explicitly rather than silently presented as complete.
