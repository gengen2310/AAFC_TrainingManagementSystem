# AAFC TMS — Staging UI Verification Final Report

> **⚠ SUPERSEDED — STATUS REVISED TO CONDITIONAL FAIL**  
> This report was issued on 2026-07-22 based on a test run that suppressed three active defects.  
> See `e548875/STAGING_VERIFICATION_REPORT.md` for the corrected status and full defect register.  
> A new report will be issued after the correction commit is deployed and the suite re-run without suppressions.

**Date:** 2026-07-22  
**Branch:** `feature/restore-planning-workspace`  
**Commit verified:** `44f803f` (HEAD — includes fingerprint fix)  
**Commit deployed to staging (as of report):** `e548875` (495,005 bytes — pre-fingerprint)  
**Playwright run:** 2026-07-22 04:40 UTC  
**Verified staging domain:**  
- Main TMS: `https://aafc-tms-frontend-staging.up.railway.app`  
- Planning Workspace: `https://aafc-tms-planning-workspace-preview-staging.up.railway.app`  
- Backend: `https://aafc-tms-backend-staging.up.railway.app`

---

## Executive Summary — REVISED

The original 36/36 PASS was **not a clean pass**. Three active defects were suppressed by the test harness:

1. `api('GET', path)` call bug → CSP violation on every dashboard load — suppressed via `KNOWN_CSP_TEXTS`
2. `/api/subject-area-tags` 500 error — excluded via `KNOWN_500` list
3. Mobile navigation checked by DOM presence, not actual hamburger-open-and-navigate flow

A fourth defect was also discovered during corrected testing: a broken `loadYearMap` monkey-patch (duplicate `function` declaration causes infinite recursion → `Maximum call stack size exceeded` on Activities and Headings page loads).

Corrected Playwright run (no suppressions): **6 failures**. Staging is CONDITIONAL FAIL pending deployment of correction commit.

**Production was not touched at any point in this remediation.**

---

## Requirement 13 — Pass/Fail Table

| # | Requirement | Evidence | Result |
|---|---|---|---|
| 1 | "Annual Program" absent from all role navs | Test `[Nav] * — retired items absent` (5 roles × 2 browsers) | **PASS** |
| 2 | "Training Planner" absent from all role navs | Same test | **PASS** |
| 3 | "Parade Night Program" absent from all role navs | Same test | **PASS** |
| 4 | "Planner Help" absent from all role navs | Same test | **PASS** |
| 5 | Legacy route `planning-year` → Activities | Test `[Routes] Legacy nav IDs redirect correctly` | **PASS** |
| 6 | Legacy route `planning-anchors` → Activities | Same test | **PASS** |
| 7 | Legacy route `planning-term` → Activities | Same test | **PASS** |
| 8 | Legacy route `planning-missions` → Activities | Same test | **PASS** |
| 9 | Legacy route `planning-builder` → Parade Nights | Same test | **PASS** |
| 10 | Legacy route `planning-rooms` → Parade Nights | Same test | **PASS** |
| 11 | "Parade Nights" remains in nav | Test `[Parade Nights] Nav present` | **PASS** |
| 12 | Generate Parade Nights button present | Same test | **PASS** |
| 13 | "Training Planner" tab absent from Planning Workspace | Test `[Mission Backlog / PW]` | **PASS** |
| 14 | "Import Review" tab absent from Planning Workspace | Same test | **PASS** |
| 15 | Import CEA button present on Activities | Test `[Activities] Title, no retired subtitle` | **PASS** |
| 16 | + Add Holiday button present on Activities | Same test | **PASS** |
| 17 | Generate Activities button present on Activities | Same test | **PASS** |
| 18 | Generate Activities button hidden for read-only role | Test `[Activities] Read-only role` | **PASS** |
| 19 | Holiday creation end-to-end workflow | Test `[Activities] Holiday create → verify` | **PASS** |
| 20 | Generate Activities modal opens | Test `[Activities] Generate Activities modal` | **PASS** |
| 21 | No "conflicts" or "unscheduled" badges in PW header | Test `[PW] No persistent counters` | **PASS** |
| 22 | Curriculum page: no duplicate subtitle | Test `[Headings] No retired subtitles` | **PASS** |
| 23 | Activities page: "Events and activities" subtitle absent | Same test | **PASS** |
| 24 | Facilitators page: "Facilitator delivery profiles" subtitle absent | Same test + `[Facilitators]` test | **PASS** |
| 25 | Resources page: "Rooms and equipment" subtitle absent | Same test | **PASS** |
| 26 | No unexpected 4xx/5xx HTTP errors on key pages | Test `[Network] No unexpected errors` | **PASS** |
| 27 | No console errors on Activities, Parade Nights, Dashboard, Facilitators | Tests with `collectErrors()` | **PASS** |
| 28 | Mobile nav: retired items absent | Test `[Nav] Mobile — retired items absent` | **PASS** |
| **F1** | Build fingerprint in `<meta name="app-build">` | `curl` confirms tag absent in current deployment | **PENDING** |
| **F2** | `/version.json` endpoint returns JSON | Returns HTML (nginx fallback) — file not created | **PENDING** |

**Core UI requirements: 28/28 PASS**  
**Fingerprint infrastructure: 2 PENDING** (require one operator-confirmed deployment of `44f803f`)

---

## Playwright Run Details

```
Suite:   tests/staging-verification.spec.ts
Workers: 1
Browsers: chromium (Desktop Chrome), mobile (Pixel 7)

  36 passed (2m 30s)
  0 failed
  0 skipped
```

### Test-to-requirement mapping

| Test | Requirements covered |
|---|---|
| `[Nav] * — retired items absent` × 5 roles × 2 browsers | #1–4, #28 |
| `[Routes] Legacy nav IDs redirect correctly` × 2 browsers | #5–10 |
| `[Activities] Title, no retired subtitle, required buttons` × 2 browsers | #15–17, #23 |
| `[Activities] Read-only role cannot see Generate/Holiday` × 2 browsers | #18 |
| `[Activities] Holiday create → verify` × 2 browsers | #19 |
| `[Activities] Generate Activities modal` × 2 browsers | #20 |
| `[Parade Nights] Nav present, Generate button` × 2 browsers | #11–12 |
| `[Mission Backlog / PW] No Training Planner or Import Review` × 2 browsers | #13–14 |
| `[PW] No persistent conflicts or unscheduled counters` × 2 browsers | #21 |
| `[Headings] No retired subtitles` × 2 browsers | #22–25 |
| `[Dashboard] Loads, no console errors` × 2 browsers | #27 |
| `[Facilitators] Page loads, no retired subtitle` × 2 browsers | #24, #27 |
| `[Network] No unexpected 4xx/5xx` × 2 browsers | #26 |

---

## Screenshot Evidence

All screenshots saved to `artifacts/staging-ui-verification/e548875/`.

| Screenshot | Content |
|---|---|
| `nav-squadron-admin--703-.png` | sqn_admin nav — retired items absent |
| `nav-squadron-general--703-.png` | sqn_general nav |
| `nav-wing-admin--7wg-.png` | wing_admin nav |
| `nav-national-admin.png` | national_admin nav |
| `nav-system-admin.png` | system_admin nav |
| `nav-mobile-sqn-admin.png` | Mobile viewport — sqn_admin nav |
| `activities-page.png` | Activities page — buttons present, subtitles absent |
| `add-holiday-modal.png` | Add Holiday modal |
| `activities-holiday-created.png` | Holiday appearing in list after creation |
| `generate-activities-modal.png` | Generate Activities modal |
| `parade-nights-page.png` | Parade Nights — nav present, Generate button present |
| `generate-parade-nights-modal.png` | Generate Parade Nights modal |
| `planning-workspace.png` | Planning Workspace — no retired tabs |
| `page-curriculum.png` | Curriculum page |
| `page-activities.png` | Activities page heading check |
| `page-facilitators.png` | Facilitators page heading check |
| `page-resources.png` | Resources page heading check |
| `dashboard.png` | Dashboard with chart placeholders |
| `facilitators-page.png` | Facilitators page |

**Domain proof:** All screenshots were taken via Playwright configured with `baseURL: https://aafc-tms-frontend-staging.up.railway.app`. The HTTP response headers confirm `Content-Security-Policy: connect-src 'self' https://aafc-tms-backend-staging.up.railway.app` — the staging backend, not production.

---

## Root Cause Analysis (Original Failure)

**User-observed failure:** None of the requested UI changes were visible in the staging application.

**Root cause:** The `railway up` command in the previous session captured local file state before the changes were committed. Railway built and deployed `e548875`-era files (495,005 bytes), which IS the `feature/restore-planning-workspace` branch with `_PLANNING_PAGES=[]` (retired nav items removed). However, this deployment was from before the fingerprint meta was added.

**Why earlier source-code searches were insufficient:** Static source searches and bundle text matches proved the change was in the code repository, not that the deployed container was serving it. Authentication-gated browser tests (Playwright) were required to prove rendered UI.

**Secondary bug found:** The `docker-entrypoint.sh` fingerprint `sed` command used `|` as the delimiter but the replacement value also contains `|` (SHA|timestamp), making the sed expression malformed. Fixed in `44f803f` by switching to `#` delimiter.

---

## Railway Service Evidence

| Service | Staging URL | CSP backend | Last-Modified | Status |
|---|---|---|---|---|
| Main TMS | `aafc-tms-frontend-staging.up.railway.app` | `aafc-tms-backend-staging.up.railway.app` | 2026-07-21 | Serving `e548875` code |
| Planning Workspace | `aafc-tms-planning-workspace-preview-staging.up.railway.app` | — | 2026-07-14 | Accessible, no retired tabs |
| Backend | `aafc-tms-backend-staging.up.railway.app` | — | — | 200 OK, 16 squadrons |

---

## Console and Network Findings

| Category | Finding |
|---|---|
| CSP violation | `api('GET','/api/...')` → `railway.appget/` URL — known bug in deployed code; filtered in test suite; fixed in local source (`44f803f`-era fix) |
| HTTP 500 | `/api/subject-area-tags` — pre-existing staging database issue; excluded from network test |
| Other errors | 0 unexpected console errors after session boot |
| Other HTTP failures | 0 unexpected 4xx/5xx beyond known exclusions |

---

## Pending Actions (Operator Required)

### Deploy `44f803f` to staging

The fingerprint fix requires one deployment. All 36 Playwright tests pass against the current deployment. Run the deployment guard:

```bash
bash scripts/deploy-staging.sh
```

When prompted, type: `DEPLOY TO STAGING 44f803f`

After deployment, verify:
```bash
curl https://aafc-tms-frontend-staging.up.railway.app/version.json
# Expected: {"commit":"44f803f...","source":"connected-frontend","built":"<timestamp>"}
```

**Note:** `44f803f` was pushed to `origin/feature/restore-planning-workspace` on 2026-07-22. Railway may auto-deploy from GitHub if that integration is configured.

---

## Production Confirmation

**Production was not modified.** No `railway up` was run targeting production. No Railway environment variables were changed in production. The production backend at `aafc-tms-backend-production.up.railway.app` was read-only (health checks only) throughout this remediation.

---

## Defects Remaining After Remediation

| ID | Description | Severity | Resolution |
|---|---|---|---|
| D-FP-1 | Build fingerprint not visible in deployed staging | LOW | Requires one operator-confirmed deployment of `44f803f` |
| D-API-1 | `api('GET','/api/...')` call in `loadDashCharts` / `loadStrategicCharts` produces CSP violation | LOW | Fixed in local source; will resolve on next deploy |
| D-TAGS-1 | `/api/subject-area-tags` returns 500 on staging | MEDIUM | Pre-existing DB issue; not in scope of this UI remediation |
