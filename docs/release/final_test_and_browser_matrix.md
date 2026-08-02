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
