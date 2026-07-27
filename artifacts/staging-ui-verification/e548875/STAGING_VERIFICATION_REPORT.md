# Staging UI Verification Report
**Commit:** `e548875` (branch: `feature/restore-planning-workspace`)  
**Date:** 2026-07-22T03:57:32Z (original run) / 2026-07-22 (updated)  
**Test suite:** `tools/playwright-staging/tests/staging-verification.spec.ts`  
**Projects:** `chromium` (Desktop Chrome), `mobile` (Pixel 7)  
**Result: ⚠ CONDITIONAL FAIL — CORRECTIONS REQUIRED**

---

## Status Override — Reason for CONDITIONAL FAIL

The original 36/36 PASS result was produced by a test harness that:

1. **Suppressed CSP violations** via `KNOWN_CSP_TEXTS` filter — masked `api('GET', '/api/...')` calls producing `railway.appget/` URLs
2. **Excluded `/api/subject-area-tags` 500 errors** via `KNOWN_500` list — masked a real backend defect (`updated_by` column missing)
3. **Checked mobile navigation by DOM presence only** — did not open the hamburger drawer, did not assert `.sidenav` is visible, did not click "Parade Nights" and verify page change

These suppressions hid three real defects. The PASS was not clean. Staging remains unverified until:
- All three defects are fixed and deployed
- The Playwright suite runs with zero suppressions (`attachErrorCollector` replaces `collectErrors`)
- The suite passes with 0 failures, 0 suppressed errors, 0 excluded HTTP failures

---

## Defects Confirmed

| ID | Description | Root Cause | Fix |
|---|---|---|---|
| D-API-1 | Dashboard charts fail; CSP violation on every load | `api('GET', '/api/...')` passes method as path; URL becomes `API_BASE+'GET'` | Change `api('GET', path)` → `api(path)` in `loadDashCharts()` and `_loadDashStrategic()` |
| D-TAGS-1 | `/api/subject-area-tags` returns 500 | v39 migration created table without `updated_by`; `TimestampMixin` generates SELECT including that column | v40 migration: `ALTER TABLE subject_area_tags ADD COLUMN updated_by VARCHAR(36)` |
| D-NAV-MOB | Mobile navigation inaccessible | `.sidenav { display:none }` at max-width 768px with no hamburger toggle | Add `#btn-hamburger`, `toggleMobileNav()`, `closeMobileNav()`, `#nav-overlay` CSS/HTML/JS |
| D-STACK | `Maximum call stack size exceeded` on Activities and Headings pages | Broken `loadYearMap` monkey-patch: `const _origLoadYearMap=loadYearMap` captures hoisted duplicate declaration → infinite recursion | Remove patch; inline wing overlay call inside original `loadYearMap` |

---

## Original Test Results (with suppressions — NOT clean)

| Project | Tests | Result |
|---|---|---|
| chromium | 18 | ✅ 18 passed (with suppressions) |
| mobile | 18 | ✅ 18 passed (with suppressions) |
| **Total** | **36** | **⚠ 36 passed with 3 active defect suppressions** |

---

## Corrected Test Run (no suppressions — new `attachErrorCollector`)

Re-run with strict Playwright policy (no KNOWN_CSP_TEXTS, no KNOWN_500, pageerror listener added) produced:

| Test | Result |
|---|---|
| `[Nav] Mobile — hamburger opens drawer, Parade Nights visible and clickable` | ❌ FAIL — `#btn-hamburger` not in deployed HTML |
| `[Activities] * console/pageerrors` | ❌ FAIL — `[pageerror] Maximum call stack size exceeded` |
| `[Headings] * console/pageerrors` | ❌ FAIL — `[pageerror] Maximum call stack size exceeded` |
| `[Dashboard] Zero CSP violations, no appget/ requests` | ❌ FAIL — appget/ requests detected |
| `[Facilitators] Subject-area-tag workflow` | ❌ FAIL — Server error from `/api/subject-area-tags` |
| `[Network] Zero unexpected HTTP errors` | ❌ FAIL — 500 on `/api/subject-area-tags` |

**True result: 6 failures — FAIL**

---

## Fixes Applied (local, not yet deployed)

| Fix | Files | Status |
|---|---|---|
| Dashboard API call: `api('GET', path)` → `api(path)` | `connected-frontend/index.html` | Local — not deployed |
| `loadYearMap` recursion: inline wing overlay, remove monkey-patch | `connected-frontend/index.html` | Local — not deployed |
| Mobile nav hamburger: add `#btn-hamburger`, CSS, JS | `connected-frontend/index.html` | Local — not deployed |
| Mobile nav close on navigate: `closeMobileNav()` in `nav()` | `connected-frontend/index.html` | Local — not deployed |
| `/api/subject-area-tags` 500: v40 migration adds `updated_by` | `backend/alembic/versions/b2c3d4e5f6a7_...py` | Local — not deployed |
| Playwright strict error policy: `attachErrorCollector` | `tools/playwright-staging/tests/staging-verification.spec.ts` | Local — not deployed |

---

## Screenshot Review (19 screenshots from e548875 run)

Screenshots captured with suppressed error policy. Review below identifies what each screenshot proves and any visible defects.

| # | Screenshot | Content Confirmed | Defects / Gaps |
|---|---|---|---|
| 1 | `nav-squadron-admin--703-.png` | sqn_admin nav — retired items absent | Dashboard may show chart error state due to D-API-1 |
| 2 | `nav-squadron-general--703-.png` | sqn_general nav | Same |
| 3 | `nav-wing-admin--7wg-.png` | wing_admin nav | Same |
| 4 | `nav-national-admin.png` | national_admin nav | Same |
| 5 | `nav-system-admin.png` | system_admin nav | System console landing, not dashboard |
| 6 | `nav-mobile-sqn-admin.png` | Mobile nav — retired items absent | D-NAV-MOB: hamburger not present; sidenav likely hidden; DOM presence check only |
| 7 | `activities-page.png` | Activities page buttons and subtitle | D-STACK defect present in deployed code but test did not fail on this screenshot |
| 8 | `add-holiday-modal.png` | Add Holiday modal | No visible defect |
| 9 | `activities-holiday-created.png` | Holiday in list after creation | No visible defect |
| 10 | `generate-activities-modal.png` | Generate Activities modal | No visible defect |
| 11 | `parade-nights-page.png` | Parade Nights nav present, Generate button | No visible defect |
| 12 | `generate-parade-nights-modal.png` | Generate Parade Nights modal | No visible defect |
| 13 | `planning-workspace.png` | Planning Workspace — no retired tabs | No visible defect |
| 14 | `page-curriculum.png` | Curriculum heading check | D-STACK defect: stack overflow occurs on this page navigation |
| 15 | `page-activities.png` | Activities heading check | D-STACK defect: stack overflow occurs on this page navigation |
| 16 | `page-facilitators.png` | Facilitators heading | No visible defect |
| 17 | `page-resources.png` | Resources heading | No visible defect |
| 18 | `dashboard.png` | Dashboard — chart placeholders | D-API-1: charts show "Could not load chart data" (CSP violation filtered in this run) |
| 19 | `facilitators-page.png` | Facilitators page | D-TAGS-1: subject-area-tags 500 hidden by test suppression |

**NOT SUFFICIENT EVIDENCE:** Screenshots 6 (mobile nav), 18 (dashboard charts), 19 (facilitator tags workflow) — defects were present but hidden by test suppressions.

---

## Next Steps

1. Commit all local fixes into one correction commit
2. Deploy backend first (to run v40 migration), then Main TMS frontend
3. Rerun Playwright suite with no suppressions against deployed commit
4. Produce final verification report under `artifacts/staging-ui-verification/<NEW_SHA>/`
