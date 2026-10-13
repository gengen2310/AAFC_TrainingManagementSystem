# Test evidence — production readiness 2026-10-09

All runs in worktree `release/production-readiness-20261009`; backend tests use a
per-run temporary SQLite DB (`tests/conftest.py`), isolated from other checkouts.

| When | SHA | Suite | Result |
|---|---|---|---|
| 2026-10-09 baseline | `56ac1af` (#72 tip) | backend full `pytest tests/ -q` | **2678 passed, 12 skipped, 0 failed** (8m46s) |
| after D1 | `4d551a1` | maintenance tests (4 files) | 36 passed |
| after D2–D4 + H1 | `ff000c1` | parade tests (4 files) + conftest invariant | 45 passed, 1 skipped (pre-existing skip) |
| after S-series | `4d9a28c` | `.claude/hooks/test_guard_prod.sh` | 52/52 |

Pending: full backend + frontend (typecheck/test/build) + 3-browser matrix at the
final SHA (Phase 5). No full-suite claim is made for intermediate SHAs.
| 2026-10-12 | `ea12454` | Planning Workspace `npm test` / `lint` / `build` | 146/146 passed; lint 0 errors (35 warnings); build clean |
| 2026-10-12 | `ea12454` | `tools/architecture/frontend_parity.mjs b93bc12` | 40 functions changed, each a deliberate edit inside a diff hunk (D11 jsq, C8, D10 can_edit, D18); none lost (each defined once, except `_apShowDateDetail` ×2, pre-existing at b93bc12 and in the monolith); 2 new (`jsq`, `_ceaRowErrorsHtml`); top-level statement order unchanged |
| 2026-10-12 | `ea12454` | `node --check` all 28 `connected-frontend/js` modules | 28/28 parse |
| 2026-10-12 | `ea12454` (**not** a final freeze: code changed afterwards — D17–D25, D10 follow-up, deploy scripts; the final-SHA rows below supersede this) | backend full `pytest tests/ -q` | **3343 passed, 12 skipped, 0 failed** (12m44s) |
| 2026-10-12 | `c9e4c0d` | CI on the exact SHA (runs 38248912546 et al.) | Backend Tests: 3,350 passed, 12 skipped; Connected E2E 202 passed × chromium/firefox/webkit; Planning Workspace E2E 42 passed × 3; dependency audit green |
| 2026-10-12 | `a10632f`, `2ed9b12` | `deploy-staging.sh` preflight (full backend suite inside) | 3,350 passed, 12 skipped (both runs) |
| 2026-10-13 | `8e5b833` (docs-only head) | CI | **3 failures**, none caused by the docs change: webkit D21 test (→ product defect **D26**), chromium REM-111 merge step (→ stale-baseline test-harness flaw, fixed `a8e844c`: 15/15 after vs 3/8 webkit failures before), pytest fixture unit-code collision `6F26` (→ 3-hex-char codes in a session-wide DB, fixed `174b996`). Not re-run to green: each was root-caused |
| 2026-10-13 | `7d5808c` | backend full `pytest tests/ -q` (local, then again in the `deploy-staging.sh` preflight) | 3,354 passed, 12 skipped, 0 failed (both runs) |
