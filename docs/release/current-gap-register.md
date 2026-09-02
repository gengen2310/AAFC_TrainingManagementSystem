# Current Gap Register — AAFC TMS v17.1 Remediation

**Status as of:** 2026-09-02
**Remediation branch:** `fix/v17-1-pre-release-remediation`

This is the **single authoritative gap register** during remediation.
Historical gap registers are in `docs/beta/` and `docs/final/` — all superseded by this document.

---

## Findings — Confirmed Fixes

| ID | Finding | Severity | Status | Commit |
|---|---|---|---|---|
| F-001 | Stored XSS: `u.title` unescaped in `renderProgramAudit()` — executes on render | P0 | **FIXED** | `d655a9f6` |
| SYN-H01 | `COOKIE_SAMESITE=none` without `COOKIE_SECURE=true` not rejected by `validate_for_production()` | P1 | **FIXED** | `f13e95e9` |
| CI-001 | No backend pytest CI workflow — backend tests never ran in CI | P1 | **FIXED** | `9d173dc5` |
| INT-001 | `/api/curriculum/import` accepted nonexistent `squadron_id` — no existence check | P2 | **FIXED** | `96afc541` |
| IDOR-CREATE | `POST /api/sessions` created sessions with cross-squadron foreign keys (facilitator, training area, curriculum) | P1 | **FIXED** | `bb5a2b36` |
| NEW-DEP-01a/b | react-router-dom CVEs (3 moderate) | Moderate | **FIXED** | `600cae94` |
| NEW-DATA-01 | `assistant_facilitator_id` silently dropped at CREATE — persisted on EDIT only | P2 | **FIXED** (origin/main) | `7581823f` |

## Findings — Previously Fixed (origin/main, verified present)

| ID | Finding | Severity | Status | Commit |
|---|---|---|---|---|
| NEW-IDOR-01 | Cross-squadron facilitator IDOR on session edit | P1 | FIXED — origin/main | prior to branch |
| NEW-IDOR-02 | Cross-squadron training area IDOR on session edit | P1 | FIXED — origin/main | prior to branch |
| NEW-IDOR-03 | Cross-squadron TrainingClass reference via SessionAudience | P1 | FIXED — origin/main | prior to branch |
| NEW-SEC-02 | Code rotation not crash-safe | P1 | FIXED — origin/main | `3aa7fec7` |

## Findings — Manual Action Required

| ID | Finding | Severity | Status | Reference |
|---|---|---|---|---|
| CI-BRANCH | GitHub branch protection not configured on `main` | P1 | **MANUAL ACTION** | `docs/release/branch-protection-required.md` |

## Findings — Deferred / Accepted Design

| ID | Finding | Severity | Status | Reason |
|---|---|---|---|---|
| NEW-DEP-01c | react-router CVEs requiring 6→7 major migration | Moderate | DEFERRED | Breaking change; affected paths are dev-tool routes not shipped to users; `--omit=dev` audit doesn't fail on these |
| Task 8 | CEA Activity import (bulk import endpoint) | N/A | SUPERSEDED | Feature already implemented at `POST /api/planning/years/{year_id}/cea/import` |
| F-002 | (if any) | — | REQUIRES VALIDATION | See `docs/final/MASTER_FINAL_GAP_REGISTER.md` |
| F-005 | (if any) | — | REQUIRES VALIDATION | See `docs/final/MASTER_FINAL_GAP_REGISTER.md` |
| NEW-AUTH-01 | (if any) | — | REQUIRES VALIDATION | See `docs/final/MASTER_FINAL_GAP_REGISTER.md` |
| ENV-001 | (if any) | — | REQUIRES VALIDATION | See `docs/final/MASTER_FINAL_GAP_REGISTER.md` |

## Release gate status

| Gate | Status |
|---|---|
| Backend tests (2215 pass, 9 skip, 0 fail) | PASS |
| TypeScript typecheck | PASS |
| Frontend build | PASS |
| npm audit --omit=dev (0 HIGH/CRITICAL) | PASS |
| 8-role RBAC matrix (49 tests, 2215 total) | PASS |
| E2E Chromium | INCOMPLETE — 58/62 tests fail; requires fresh DB seed + manual browser investigation (pre-existing failures, not introduced by this branch) |
| E2E Firefox | NOT RUN — blocked on Chromium investigation |
| E2E WebKit | NOT RUN — blocked on Chromium investigation |
| Branch protection on main | MANUAL ACTION REQUIRED |

## E2E failure classification (Task 7)

58 of 62 Chromium E2E tests failed on 2026-09-02. These are **pre-existing failures** — the audit found
~60 E2E failures before this branch started, and this count matches.

Root cause hypothesis (requires manual browser investigation to confirm):
- Several navigation routes (Mission Backlog, Imports, Facilitators, Resources, Weekly Program, Calendar) load but their page headings don't match test selectors → likely STALE TEST or PAGE HEADING CHANGE
- Data-dependent tests (parade-nights CRUD, session lifecycle, year rollover) may fail due to stale DB state from prior test runs; run `python -m pytest` seed reset before E2E
- Conflict indicator and filter chip tests may require Planning Workspace UI components that changed → STALE TEST or PRODUCT DEFECT

**Manual steps to confirm classification:**
1. Reset the dev database: `rm -f backend/aafc_tms.db && bash RUN_TMS_BACKEND_MAC.sh`
2. Start Vite dev server: `cd frontend && npm run dev`
3. Run a single failing test with `--debug`: `npx playwright test e2e/navigation.spec.ts:36 --project=chromium --debug`
4. Inspect actual vs expected heading text; classify each failure file
