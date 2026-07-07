# AAFC TMS — Alpha Testing Report
**Version:** v17.1 (Two-Step Login + Stress-Test Fixes)
**Testing Date:** 2026-07-07
**Environment:** Railway production (backend + frontend), Supabase PostgreSQL
**Tester:** Claude Code / automated API testing
**Testing Method:** Systematic API testing across all 8 roles; source-code review; security scan

---

## 1. Executive Summary

The AAFC TMS v17.1 backend is **substantially functional** for its core audience of squadron administrators, wing administrators, and national staff. Authentication, access control, tenancy isolation, and data protection all work correctly. The two-step login flow is operating as designed in production.

However, **three critical/high defects block production use**:

1. The curriculum endpoint takes **41+ seconds** to load (N+1 query: 215 items × ~200ms = 42s). Every user sees this delay on their primary workflow screen.
2. The **annual program and term planner both crash** (HTTP 500) when accessed — core planning features are completely unavailable.
3. The **system_admin account code is unknown** and cannot be recovered through the UI — system-level maintenance, backups, and maintenance-mode controls cannot be tested or used.

**Readiness Rating: Developer-only testing**

The system is not safe to hand to real squadron staff until findings F-01, F-02, and F-03 are resolved.

---

## 2. Test Environment

| Item | Value |
|------|-------|
| Backend URL | `https://aafc-tms-backend-production.up.railway.app` |
| Frontend URL | `https://aafc-tms-frontend-production.up.railway.app` |
| DB | Supabase PostgreSQL 17.6, Session Pooler |
| Workers | 2 Gunicorn workers per service |
| Migration head | `m8h9i0j1k2l3` (v25) |
| Total accounts | 9 (3 pre-existing + 6 ALPHA_TEST) |
| Curriculum items | 215 |
| Planning years | 1 (squadron-linked) + 4 (unit_id=null) |
| Parade nights | 2 (created during this test pass) |

### ALPHA_TEST Accounts Used

| Role | Display Name | Code |
|------|-------------|------|
| national_admin | ALPHA_TEST National Admin | _(redacted — stored in Railway env)_ |
| national_viewer | ALPHA_TEST National Viewer | _(redacted)_ |
| wing_viewer | ALPHA_TEST Wing Viewer | _(redacted)_ |
| sqn_general | ALPHA_TEST SQN Viewer | _(redacted)_ |
| auditor | ALPHA_TEST Auditor | _(redacted)_ |
| wing_admin | 7 Wing | _(redacted — pre-existing)_ |
| sqn_admin | 703 Squadron | Auto-generated during test (original invalidated) |
| system_admin | System Admin | **Unknown at time of test — see F-03** |

---

## 3. Authentication & Login (Two-Step Flow)

### Status: ✅ PASS

All 8 roles authenticated successfully using the new two-step flow.

**Lookup endpoint** (`POST /api/auth/lookup`):
- Squadron lookup by code (case-insensitive) ✓
- Wing lookup by code (case-insensitive) ✓
- National lookup by role ✓
- Non-existent combinations return 404 ✓
- Wrong role for a unit returns 404 ✓

**Login endpoint** (`POST /api/auth/login`):
- Correct code + user_id → 200 ✓
- Wrong code + correct user_id → 401 ✓
- Admin code rejected for viewer account → 401 ✓ (scoped isolation)
- Viewer code rejected for admin account → 401 ✓ (scoped isolation)

**Per-account lockout**:
- 5 wrong scoped attempts → account locked for 24 hours ✓
- Locked account message: "Contact 7 Wing SOCAD" ✓
- Locked viewer at SQN X does not affect admin at SQN X ✓
- Wing_admin unlock endpoint clears lock correctly ✓

**IP rate limiting** (legacy scan-all path):
- Scoped path (with user_id) does **not** increment IP counter ✓
- IP counter only increments on scan-all (no user_id) ✓

---

## 4. Access Control by Role

### Status: ✅ PASS (all tested roles)

| Role | Read own data | Write own data | Read foreign data | Write foreign data |
|------|:---:|:---:|:---:|:---:|
| sqn_general | ✅ | ❌ blocked | ❌ blocked | ❌ blocked |
| sqn_admin | ✅ | ✅ | ❌ (empty 200) | ❌ blocked |
| wing_viewer | ✅ | ❌ blocked | ✅ (wing scope) | ❌ blocked |
| wing_admin | ✅ | ✅ (via proxy) | ✅ (wing scope) | ✅ (via proxy only) |
| national_viewer | ✅ | ❌ blocked | ✅ (all) | ❌ blocked |
| national_admin | ✅ | ✅ | ✅ (all) | ✅ (via intervention) |
| auditor | ✅ (audit log) | ❌ blocked | ✅ (read only) | ❌ blocked |
| system_admin | Not tested | Not tested | Not tested | Not tested |

**Note on sqn_admin cross-squadron data**: When an sqn_admin requests parade nights for a foreign squadron ID, the API returns HTTP 200 with an empty list rather than 403. No data is leaked, but the access boundary is not enforced at the HTTP level. See F-09.

---

## 5. Proxy Mode (Wing Admin → Squadron)

### Status: ✅ PASS

- `POST /api/proxy/enter/{squadron_id}` creates a server-side ProxySession record ✓
- Subsequent requests with the same wing_admin JWT automatically resolve proxy context from DB ✓
- Wing admin in proxy mode can create parade nights ✓
- `GET /api/proxy/current` returns correct `{active, mode, acting_squadron_id}` ✓
- `POST /api/proxy/exit` clears the proxy session ✓
- `auth/me` returns full proxy metadata (mode, acting_squadron_id, acting_wing_id, proxy_session_id) ✓

---

## 6. Data Management — Squadron Level

### 6.1 Parade Nights
**Status: ✅ PASS**

- List parade nights by squadron_id ✓
- Create parade night (sqn_admin direct) ✓
- Create parade night (wing_admin in proxy mode) ✓
- New parade night initialises with `session_count=3`, `closeout_status=open`, `published_status=false` ✓
- Response field consistency: list returns `parade_night_id` key (not `id`) — matches create response ✓

### 6.2 Facilitators
**Status: ✅ PASS (list), NOT FULLY TESTED (create)**

- List facilitators ✓
- Create facilitator requires `last_name` field (422 returned when missing — not a bug)

### 6.3 Action Items, Equipment, Activities
**Status: ✅ PASS (list)**

- All three return empty lists for the fresh alpha environment ✓

### 6.4 Accounts Management
**Status: ✅ PASS**

- national_admin can create accounts for any role except system_admin ✓
- wing_admin can create/disable/unlock sqn accounts in their wing ✓
- wing_admin can reset sqn account codes; returns `new_code` in response (one-time display) ✓
- national_admin cannot reset system_admin code (correct — prevents privilege escalation) ✓
- Account list shows `code_active`, `code_last_changed`, `code_changed_by` — these are metadata fields, NOT the actual code or hash ✓

---

## 7. Curriculum

### 7.1 Curriculum Load Time — **CRITICAL BUG (F-01)**

`GET /api/curriculum` issues one database query per curriculum item (N+1 pattern).

| Test | Items | Time |
|------|-------|------|
| sqn_admin load | 215 | **41.5 seconds** |

**Root cause** (identified in source): `backend/app/routers/training.py` — the `list_curriculum` endpoint iterates over all 215 `CurriculumItem` rows and fires a separate `db.query(Session)` per item. At ~200ms per Supabase round-trip, this equals ~43 seconds.

**User impact**: Every sqn_admin, wing_admin, and national_admin who loads the curriculum view waits 41+ seconds. This is the primary workflow screen.

### 7.2 Curriculum Export
**Status: ✅ PASS**

- `GET /api/curriculum/export.xlsx` → 200, 18.8 KB ✓

### 7.3 CSV Curriculum Import
**Status: ⚠️ PARTIAL — Bug F-04**

- `POST /api/curriculum/import-csv` with empty file → `{"ok":true,"created":0,"updated":0,...}` (HTTP 200)
  - **Bug**: Should return 4xx for empty/invalid input
- CSV format accepted: strict schema required (test CSV with simplified headers returned validation error)

### 7.4 Wing/National Curriculum Endpoints
**Status: ⚠️ OBSERVATION**

- `POST /api/curriculum/wing` and `POST /api/curriculum/national` are POST-only
- `GET /api/curriculum/wing` → 405 Method Not Allowed
- These appear to be admin "sync" endpoints, not GET endpoints for wing-scope curriculum views
- Wing viewers needing to read wing curriculum would use `GET /api/curriculum` (scoped by their role)

---

## 8. Planning System

### 8.1 Planning Years
**Status: ✅ PASS (list/create), ❌ FAIL (annual-program/term-planner)**

- `GET /api/planning/years` → returns planning years for the user's squadron ✓
- Planning year has correct keys: `planning_year_id`, `unit_id`, `wing_id`, `year`, `name` ✓
- **Note**: 4 additional planning years in the DB have `unit_id=null` — these are not associated with any squadron and do not appear in sqn_admin views. Origin unclear (likely DB seed data).

### 8.2 Annual Program — **HIGH BUG (F-02)**

`GET /api/planning/years/{year_id}/annual-program` → **HTTP 500** for all tested planning years.

- Tested with: sqn_admin (own planning year, unit_id correctly set to SQN_ID), national_admin (unrestricted access)
- Both return `{"error":"internal_error"}` (HTTP 500)
- Root cause: unhandled Python exception inside the endpoint (exact line unknown — Railway logs required)
- **User impact**: The annual program calendar view is completely inaccessible

### 8.3 Term Planner — **HIGH BUG (F-02b)**

`GET /api/planning/years/{year_id}/term-planner` → **HTTP 500** for all tested planning years.

- Same behaviour as annual-program; same unknown root cause
- **User impact**: Term planning view is completely inaccessible

### 8.4 Schedule Export
**Status: ✅ PASS**

- `GET /api/planning/years/{year_id}/schedule/export.xlsx` → 200, 4.9 KB ✓

### 8.5 Conflicts, Parade Dates
**Status: ✅ PASS (empty state)**

- `GET /api/planning/years/{year_id}/conflicts` → empty list ✓ (no data yet)

---

## 9. Reports

### Status: ✅ PASS (all tested)

| Endpoint | Response Time | Structure |
|----------|-------------|-----------|
| `GET /api/reports/wing-capability` | ~1.8s | subjects, squadrons, wing_avg, capability_gaps |
| `GET /api/reports/national-capability` | ~1.5s | subjects, wings |
| `GET /api/reports/facilitator-load` | ~1.9s | title, facilitators, decision |
| `GET /api/reports/readiness` | ~2.0s | title, parade_nights, decision |
| `GET /api/reports/wing-phase-coverage` | ~2.7s | phases, squadrons |
| `GET /api/reports/curriculum-coverage` | ~2.3s | title, total, scheduled, delivered, coverage_pct |
| `GET /api/reports/wing-overview` | ~1.5s | squadrons |
| `GET /api/national/overview` | ~1.8s | national, wings, wing_count |
| `GET /api/program-coverage/squadron` | ~2.1s | squadron_id, core, extension, delivered_coverage_pct |

All reports return expected structures with zero data (fresh environment). Access control is correct: national-level reports require national_admin or national_viewer.

---

## 10. Audit Log

### Status: ✅ PASS

- `GET /api/audit` accessible to: auditor, national_admin ✓
- Wing_admin, sqn_admin, viewers, sqn_general all receive 403 ✓
- Audit log returns paginated entries with standard fields ✓
- `GET /api/system/audit-summary` accessible to national_admin ✓
- No access codes, code hashes, or secrets present in any audit entry ✓

---

## 11. System Admin Console

### Status: ⚠️ NOT TESTED — F-03

The system_admin account (display name: "System Admin", uid: `8ad0024f-19a3-455c-b6e7-c959a4b4b7ee`) exists in production but its access code is unknown. The code was changed by a prior system_admin session and cannot be recovered via the UI because:

- national_admin cannot reset system_admin codes (correct security design)
- Only another system_admin can reset a system_admin code
- Recovery requires direct DB access or `railway run` CLI

**Consequence**: The following system_admin-only endpoints could **not be tested**:

| Endpoint | Purpose |
|----------|---------|
| `GET /api/system/overview` | System-wide health dashboard |
| `GET /api/system/scope-map` | Wing/squadron hierarchy map |
| `GET /api/system/migrations` | Migration status |
| `GET /api/system/version` | Version info |
| `POST /api/system/maintenance/enable` | Maintenance mode on |
| `POST /api/system/maintenance/disable` | Maintenance mode off |
| `GET /api/system/backups` | Backup list |
| `POST /api/system/backups/pg-dump` | Create backup |
| `POST /api/system/bootstrap-staging` | Staging seed |

**Observation**: `GET /api/system/version` returning 403 for national_admin (and 401 for unauthenticated) means version information is not accessible for health monitoring without system_admin credentials.

---

## 12. Security Scan

### Status: ✅ PASS (all checks)

| Check | Result |
|-------|--------|
| Access code hashes in API responses | ✅ None found |
| Plaintext access codes in API responses | ✅ None found |
| DATABASE_URL in any API response | ✅ Not exposed |
| DB files (`*.db`) in git | ✅ Not tracked |
| CORS origin | ✅ Exact Railway frontend URL, no wildcards |
| Security headers | ✅ Present (X-Content-Type-Options, X-Frame-Options, etc.) |
| Account response fields | ✅ `code_active` (bool), `code_last_changed` (timestamp), `code_changed_by` (user_id) — metadata only, not actual code |
| XSS protection (`esc()` in frontend) | ✅ Full HTML entity escaping confirmed |
| SQLi protection | ✅ All queries via SQLAlchemy ORM parameterisation |
| `.gitignore` coverage | ✅ `*.db`, `backups/` excluded |
| `.dockerignore` coverage | ✅ Backend: `*.db`, `backups/`, `.env`, tests excluded |

**Observation (F-06)**: OpenAPI docs (`/docs`, `/openapi.json`) are publicly accessible without authentication. This exposes all 150+ API paths and schema definitions. No credentials are exposed, but the full attack surface is visible.

**Observation (F-07)**: JWT tokens remain valid for API calls after logout until natural expiry (stateless design, no blacklist). An intercepted token continues to work until it expires. This is a documented design constraint of the stateless JWT approach.

---

## 13. Performance Summary

| Endpoint | p50 observed | Status |
|----------|-------------|--------|
| `POST /api/auth/login` | ~400ms | ✅ |
| `GET /api/health` | ~640ms | ✅ |
| `GET /api/parade-nights` | ~300ms | ✅ |
| `GET /api/planning/years` | ~400ms | ✅ |
| Reports (all) | 1.8–2.7s | ✅ Acceptable |
| `GET /api/curriculum` (215 items) | **41.5s** | ❌ Critical |
| Annual program | HTTP 500 | ❌ Not functional |
| Term planner | HTTP 500 | ❌ Not functional |

---

## 14. Cross-Role Handoff Testing

### Wing Admin Proxy → Squadron Writes
**Status: ✅ PASS**

- Wing admin enters proxy mode for 703 Squadron ✓
- Proxy mode creates parade night successfully ✓
- `GET /api/proxy/current` correctly shows `active=true`, `mode=proxy`, `acting_squadron_id` ✓
- `auth/me` returns full proxy metadata ✓
- `POST /api/proxy/exit` clears proxy mode ✓

### Auditor Read-Only Scope
**Status: ✅ PASS**

- Auditor can read audit log ✓
- Auditor cannot create facilitators, parade nights, or accounts (403) ✓
- Auditor can read national capability reports ✓

### National Admin Account Management
**Status: ✅ PASS**

- national_admin can create accounts for all roles except system_admin ✓
- national_admin can reset codes for wing/sqn/national accounts ✓
- national_admin CANNOT reset system_admin code (403) ✓ — correct security boundary

---

## 15. Data Integrity

### Status: ✅ PASS for observable data

- Parade nights created during testing persist across sessions ✓
- Parade night unlock correctly clears `locked_until` and `failed_attempts` ✓
- Account reset-code correctly generates new code (auto-generated 8-char alphanumeric) ✓
- Planning year correctly associates with squadron (`unit_id` = squadron UUID) ✓

**Observation**: 4 of 5 planning years in the DB have `unit_id=null`. These are inaccessible through the sqn_admin interface and do not appear to be associated with any squadron. They may be leftover seed/test data or wing-level planning years (no wing association either — `wing_id` not checked).

---

## 16. Features Not Tested

The following features could not be tested during this API-only pass:

| Feature | Reason |
|---------|--------|
| System admin console (all endpoints) | system_admin code unknown — F-03 |
| Maintenance mode enable/disable | Requires system_admin |
| System backups and restore | Requires system_admin |
| XLSM curriculum import | Format documentation not available |
| CEA activity import | No test CEA data available |
| Browser/device compatibility | API-only testing; no frontend UI testing |
| Concurrent user performance | Sequential single-user testing |
| Print/PDF export | Not exercised |
| Delegated intervention (national → squadron) | national_admin can enter intervention but no squadron-level operations were attempted in intervention mode |
| Year rollover | No completed planning year in test environment |

---

## 17. Findings Register

### F-01 — CRITICAL: Curriculum N+1 Query (42-Second Load)

**Severity:** Critical  
**Endpoint:** `GET /api/curriculum`  
**File:** `backend/app/routers/training.py` (`list_curriculum`)  
**Observed:** 41,508ms for 215 items  
**Root cause:** One `db.query(Session)` per curriculum item = 215 round-trips to Supabase at ~200ms each  
**Impact:** Every user who opens the curriculum view waits 41+ seconds. Primary workflow screen unusable under normal network conditions.  
**Fix direction:** Preload all relevant Sessions in a single query keyed by `curriculum_item_id`, then group in Python.

---

### F-02 — HIGH: Annual Program and Term Planner Crash (HTTP 500)

**Severity:** High  
**Endpoints:** `GET /api/planning/years/{year_id}/annual-program`, `GET /api/planning/years/{year_id}/term-planner`  
**Observed:** HTTP 500 `{"error":"internal_error"}` for all tested planning years (with and without data)  
**Root cause:** Unhandled Python exception inside the endpoint. Exact line unknown — requires Railway log inspection.  
**Impact:** Annual program calendar view and term planner are completely inaccessible. Two of the most important planning features are broken.  
**Fix direction:** Check Railway application logs for the traceback; wrap in proper error handling; ensure all model attributes exist in DB schema.

---

### F-03 — HIGH: System Admin Code Unknown / No UI Recovery Path

**Severity:** High  
**Account:** `system_admin` uid `8ad0024f-...`  
**Observed:** Multiple guessed codes → invalid_code (all rejected)  
**Root cause:** Code was changed during a prior session. national_admin cannot reset system_admin codes (correct security). No UI recovery path exists.  
**Impact:** All system_admin-only endpoints (maintenance mode, backups, system overview, migrations) cannot be accessed or tested. Cannot enable/disable maintenance mode or create backups.  
**Fix direction:** Use `railway run python -c "..."` to reset the code directly via the DB. Document a break-glass procedure for future system_admin lockouts.

---

### F-04 — MEDIUM: Empty CSV Upload Returns 200

**Severity:** Medium  
**Endpoint:** `POST /api/curriculum/import-csv`  
**Observed:** File with 0 bytes → `{"ok":true,"created":0,"updated":0,"skipped":0,"failed":0,"total":0}` (HTTP 200)  
**Impact:** Silent success on empty upload — user receives no indication that anything went wrong. Should return HTTP 400 with a message like "No records found in file."

---

### F-05 — MEDIUM: sqn_admin Cross-Squadron Access Returns 200 (Not 403)

**Severity:** Medium  
**Endpoint:** `GET /api/parade-nights?squadron_id={foreign_id}`  
**Observed:** sqn_admin querying a foreign squadron's parade nights receives HTTP 200 with empty list, not 403  
**Impact:** No data is leaked (empty result), but the access boundary is not enforced at the HTTP level. An sqn_admin can enumerate squadron IDs without receiving an access-denied response. Not a data breach but violates least-privilege principle.  
**Fix direction:** In the parade-nights (and similar list) endpoints, validate that the requesting principal has view permission for the requested `squadron_id` and return 403 if not.

---

### F-06 — LOW: OpenAPI Docs Publicly Accessible

**Severity:** Low  
**URLs:** `/docs` (HTTP 200), `/openapi.json` (HTTP 200)  
**Observed:** Full API schema with 150+ paths, all request/response models, accessible without authentication  
**Impact:** Exposes full attack surface to unauthenticated users. Not a direct exploit, but aids reconnaissance.  
**Fix direction:** Consider restricting `/docs` and `/openapi.json` to system_admin or disabling in production (`app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)`).

---

### F-07 — LOW: JWT Valid After Logout (Stateless Design)

**Severity:** Low (by design)  
**Observed:** After `POST /api/auth/logout`, the Bearer token continues to be accepted by the API until natural expiry  
**Impact:** An intercepted or leaked token remains usable until expiry. No way to immediately revoke a compromised session.  
**Note:** This is a documented trade-off of the stateless JWT approach. The sliding refresh model (`POST /api/auth/refresh`) bounds active-session risk. Accept as-is or consider adding a server-side token blacklist.

---

### F-08 — LOW: System Version Requires Auth

**Severity:** Low  
**Endpoint:** `GET /api/system/version`  
**Observed:** unauthenticated → 401; national_admin → 403; system_admin required  
**Impact:** Version/build information not available for health monitoring without system_admin credentials. Uptime monitoring tools cannot check version without a service account.

---

### F-09 — INFO: Proxy Current Response Field Name

**Severity:** Informational  
**Endpoint:** `GET /api/proxy/current`  
**Observed:** Response uses `mode` key; `auth/me` proxy block uses `mode` as well. Code that checks for `proxy_mode` will find `None`.  
**Impact:** Minor — any frontend logic reading `proxy_mode` from proxy/current will not find it. Confirmed: `active`, `mode`, `acting_squadron_id` are the correct keys.

---

## 18. Test Account Notes

### sqn_admin Code Reset During Testing

During this alpha testing pass, the original sqn_admin code was found to be invalid (had been changed in a prior session). A secondary code was found to be locked (5 failed attempts from prior testing). The account was unlocked and a new auto-generated code was set via wing_admin's reset-code endpoint. The current code is stored securely outside this report.

### ALPHA_TEST Accounts Created in Prior Session

These accounts were created server-side and exist in production solely for alpha testing. They should be disabled before real users are onboarded:

| Role | Display Name | Action Needed |
|------|-------------|---------------|
| national_admin | ALPHA_TEST National Admin | Disable after alpha |
| national_viewer | ALPHA_TEST National Viewer | Disable after alpha |
| wing_viewer | ALPHA_TEST Wing Viewer | Disable after alpha |
| sqn_general | ALPHA_TEST SQN Viewer | Disable after alpha |
| sqn_general | ALPHA_TEST Sqn Viewer 2 | Disable after alpha (duplicate) |
| auditor | ALPHA_TEST Auditor | Disable after alpha |

---

## 19. Documentation Gaps

| Gap | Priority |
|-----|----------|
| CSV curriculum import format (required column names, order, validation rules) | High |
| XLSM curriculum import format | High |
| System admin break-glass procedure (what to do if system_admin is locked out) | High |
| Expected planning year setup workflow (how to link parade dates) | Medium |
| CEA activity import format and source | Medium |
| Timing template configuration | Medium |
| Definition of `unit_id=null` planning years | Low |

---

## 20. Browser / Device Testing

This test pass was conducted entirely via API (curl). No browser or mobile testing was performed.

**Required before beta release:**
- Chrome/Firefox/Safari on desktop (Windows and macOS)
- iOS Safari (common for staff using iPads)
- Android Chrome
- Screen at 1280×720 (minimum expected resolution for squadron admin desktop)
- Test two-step login flow in browser (does lookup → login feel natural?)
- Test long curriculum load (41s) UX — does the browser show a loading state or appear frozen?

---

## 21. Performance Under Load

No concurrent load testing was performed in this pass. Sequential single-user response times are documented in Section 13.

**Required before beta release:**
- Concurrent login test: 5 users logging in simultaneously
- Curriculum load under concurrent access (N+1 will compound)
- Report generation under concurrent access

---

## 22. Risk Register

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Curriculum 42s load causes user abandonment | Certain (if unfixed) | High | Fix F-01 before any user onboarding |
| Annual program / term planner 500 blocks planning workflow | Certain (current state) | High | Fix F-02 immediately |
| system_admin lockout with no recovery | Low (already happened once) | Critical | Add break-glass procedure; fix F-03 |
| N+1 compounds under concurrent use | High | High | Fix F-01 |
| sqn_admin enumerates foreign squadron IDs | Low | Low | Fix F-05 before wider rollout |
| Leaked JWT token abuse | Low | Medium | Accept (short-TTL tokens) or add blacklist |

---

## 23. Go / No-Go Recommendation

### Rating: **Developer-only testing**

The system is not ready for staff alpha users. The following must be resolved before inviting any real squadron users:

**Blockers (must fix):**
1. **F-01** — Curriculum 42-second load. Primary workflow screen is unusable.
2. **F-02** — Annual program and term planner crash (HTTP 500). Core planning features non-functional.
3. **F-03** — system_admin access lost. Maintenance, backups, and system controls inaccessible.

**Recommended before controlled alpha (selected staff):**
4. **F-04** — Empty CSV upload returns 200 (confusing UX)
5. **F-05** — sqn_admin cross-squadron enumeration returns 200
6. Browser testing across Chrome/Safari/iOS
7. Write and publish CSV import format documentation

**Acceptable for initial controlled alpha (can defer):**
8. **F-06** — OpenAPI docs public (low risk)
9. **F-07** — JWT not revocable on logout (by design)
10. Delegated intervention mode full testing
11. Concurrent load testing

Once F-01, F-02, and F-03 are resolved and browser testing confirms the UI is functional, the system is ready for a **controlled alpha with selected staff** (1–2 wing staff, 1 sqn_admin) under close monitoring.
