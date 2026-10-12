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
| 2026-10-12 | `ea12454` (code freeze; later commits docs-only until noted) | backend full `pytest tests/ -q` | **3343 passed, 12 skipped, 0 failed** (12m44s) |
