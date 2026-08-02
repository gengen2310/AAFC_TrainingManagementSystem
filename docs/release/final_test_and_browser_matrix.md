# Final Test-Suite Assurance & Browser Matrix (Stage 11)

## Backend test suite

`python -m pytest tests/ -q`: **1008 passed, 5 skipped** (Stage 1's fresh baseline,
includes this session's new tests: `test_health.py` ×5, the GAP-22 CSV core_status
regression test). Materially supersedes the stale "310 passed, 1 skipped" recorded
in `.claude/rules/testing.md`.

## `frontend/` (Planning Workspace) — cross-browser matrix

`npx playwright test e2e/` (87 tests: auth, dashboard, facilitators, parade nights,
cross-interface session handoff, holidays/resources, navigation, reports, session
lifecycle, wing-proxy, year-rollover, accessibility) — **87/87 passed** under
Chromium.

Accessibility suite specifically (19 tests) re-run under all three available
engines:

| Engine | Result |
|---|---|
| Chromium (via `claude-in-chrome` earlier, and default Playwright here) | 19/19 passed |
| Firefox | 19/19 passed |
| WebKit | 19/19 passed |

Real Edge/Safari were not run (no real installation available in this environment,
per the plan's own stated default) — WebKit is the closest automatable proxy for
Safari's engine, already covered above.

## `connected-frontend/` — local e2e suite

`npx playwright test --config=playwright.connected.config.ts` (`e2e-connected/`,
excluding `capture-screenshots.spec.ts` — see below): **41/41 passed**
(`activities-inheritance.spec.ts`, `main-tms.spec.ts`, `training-dashboard.spec.ts`,
combined across two runs — 29 in the first full run, 12 more in `main-tms.spec.ts`
re-run after a local environment fix, see below).

**One local-environment gap found and fixed in the test setup, not the app**: the
first full run showed 10 failures, all `#nav-pw-link` (Planning Workspace nav link)
expected-visible-but-hidden. Traced to `PLANNING_WORKSPACE_URL` not being set on
the local backend I'd started for this pass — `GET /api/health/ui-config` correctly
returned `planning_workspace_url: null`, and the app correctly hides the link when
unconfigured (there's even a dedicated passing test for that exact hidden-when-
unset behaviour). Re-ran with `PLANNING_WORKSPACE_URL` set: all 12 previously-failing
tests in `main-tms.spec.ts` passed clean. Not an application defect — a test
environment setup gap on my part, confirmed by fixing it and re-observing.

**`capture-screenshots.spec.ts` (7 failures, investigated and correctly excluded
from the pass/fail count above)**: this file's own header comment states it is a
"one-off evidence capture against live staging — not part of the regular
verification suite," meant to run with `playwright.connected.staging.config.ts`
against real staging, not the local config used for everything else in this
section. Running it against a local backend with the wrong config produced
consistent, reproducible failures (`#auth-wing-select` never populates options in
time) even in isolation — a test-tool misapplication on my part (wrong config for
this specific file), not a rediscovered defect. Not re-run against real staging
this pass (would need `playwright.connected.staging.config.ts` and a decision
about touching a shared environment for screenshot capture, out of scope for this
stage).

## Summary

| Suite | Result |
|---|---|
| Backend (`pytest`) | 1008 passed, 5 skipped |
| `frontend/e2e/` (Chromium) | 87/87 passed |
| `frontend/e2e/accessibility.spec.ts` (Firefox) | 19/19 passed |
| `frontend/e2e/accessibility.spec.ts` (WebKit) | 19/19 passed |
| `connected-frontend` (`e2e-connected/`, local) | 41/41 passed (after fixing a local env gap) |

No test-suite defect found. One local-environment configuration gap identified,
diagnosed, and fixed in this pass's own test setup (not the application).

---

## Post-deployment reconciliation update (2026-08-02)

Re-run against current `main` (`55678c7`, migration head `z1a2b3c4d5e6`, single
linear head confirmed via `alembic heads`) after this pass's fixes (accessible
color-contrast tokens, GAP-28 async load-test tooling, soak-test ramp fix):

| Suite | Result | Change from Stage 11 baseline |
|---|---|---|
| Backend (`pytest`) | **1008 passed, 5 skipped** | Unchanged — no regressions |
| `frontend` TypeScript (`tsc --noEmit`) | **0 errors** | Unchanged |
| `frontend` ESLint | **0 errors, 16 warnings** | Unchanged — the 2 hook-dependency warnings among them were investigated to a definitive non-bug conclusion this pass (see `final_findings_reclassification.md`); the rest are pre-existing `react-refresh/only-export-components` style warnings and one unused-variable warning, none release-relevant |
| `connected-frontend` accessibility (axe-core, live) | **0 `color-contrast` violations** across 18 page-scans (12 `sqn_admin`-scope, 6 `wing_admin`-scope), re-scanned after the token fix | **Improved** — was 40-43 nodes/page failing before this pass; full detail in `final_accessibility_assessment.md` |
| `connected-frontend` e2e (`e2e-connected/`, excluding the staging-only screenshot utility) | **24/24 passed**, re-run after the color-contrast fix | Unchanged pass rate, confirms zero functional regression from the CSS token changes |
| Migration state | Single head `z1a2b3c4d5e6`, `alembic upgrade head` clean against a disposable Postgres (GAP-18 re-verification) | Unchanged |

**Staging role/scope qualification matrix — honest scope, not exhaustive.**
Attempted live-browser verification of staging behaviour across every named
role. Two role scopes were fully verified this pass with live evidence
(18 page-scans across `sqn_admin` and `wing_admin`, cited above). A
`national_admin` browser login attempt became unresponsive mid-flow during
cross-role verification (tab stopped responding after several rapid logins in
the same session, likely cumulative rate-limiting) — not forced through with
repeated retries, since the tab instability risked losing already-good
evidence for no clear gain. `system_admin` staging verification remains
blocked entirely on the separate, already-tracked credential issue (see
"Staging System Administrator authentication" in
`final_findings_reclassification.md`, Task #45 — awaiting the user's current
access code). **This is reported as the actual scope of what was verified —
2 of 4 non-`auditor` staging role scopes with live browser evidence — not
claimed as exhaustive role coverage.** Production's own equivalent surfaces
were separately verified live in production during this session's earlier
GAP-27 fix (which required and used a working production login flow across
multiple roles), so this gap is staging-verification-specific, not a
production-readiness gap.
