# AAFC TMS — Planning Workspace Integrated System Test Report

**Phase 12 — Full Integrated System Verification, Security Assessment, and Operational Validation**

| Item | Value |
|------|-------|
| Report date | 2026-07-13 |
| Scope | Old TMS + Planning Workspace treated as one system |
| Assessor roles | Senior engineer · Test engineer · Authorised security tester · TRGO · SOCAD · Hostile release reviewer |
| RC branch | `release/planning-workspace-rc1` @ commit `45a757f` |
| Report status | **DRAFT — awaiting live deploy confirmation before final GO/NO-GO** |

---

## Executive Summary

The AAFC TMS Planning Workspace is architecturally sound and demonstrates strong defensive engineering: comprehensive RBAC, fail-closed startup validation, security headers, CORS allowlisting, and audit logging on all write operations. TypeScript and Python syntax checks pass clean.

**Three IDOR (Insecure Direct Object Reference) vulnerabilities were found in the CEA and Notices subsystem.** None are exploitable from the public internet (all require a valid authenticated admin session), but they allow a logged-in admin from one squadron/wing to read or write data belonging to another unit. These must be fixed before GO.

**One missing file-size guard** on the CEA CSV import endpoint is a potential server-side resource exhaustion issue that should be patched.

A known infrastructure failure (DEPLOY-001) means the fixes for BUG-004 are not yet live. The release gate cannot be finalised until deploys are confirmed.

---

## A. Integrated Architecture

### System topology

```
Browser
 ├── Old TMS frontend  →  aafc-tms-frontend  (Railway, connected-frontend/)
 └── Planning Workspace →  aafc-tms-planning-workspace-preview  (Railway, frontend/)
                                        │
                              Shared backend API
                        aafc-tms-backend  (Railway, FastAPI)
                                        │
                              Shared Postgres DB (Railway)
```

### Service identifiers (Railway)

| Service | Railway ID | URL |
|---------|-----------|-----|
| Old TMS frontend | `aafc-tms-frontend` | (old TMS URL) |
| Planning Workspace | `aafc-tms-planning-workspace-preview` | `https://aafc-tms-planning-workspace-preview-production.up.railway.app` |
| Backend | `aafc-tms-backend` / `deb53faa-ca8d-4291-aa2e-9ff3029c50f8` | `https://aafc-tms-backend-production.up.railway.app` |

### Auth model

- JWT HS256, signed with `JWT_SECRET` (validated as strong in production)
- `ACCESS_TOKEN_TTL_MIN = 30`; `REFRESH_TOKEN_TTL_MIN = 720`
- Token delivered in `aafc_session` HTTP-only cookie
- `COOKIE_SAMESITE = lax`; `COOKIE_SECURE` must be `True` in production (enforced by `validate_for_production()`)
- Planning Workspace inherits the session cookie set by the backend during TMS login — no second login required

### CORS configuration

- `CORS_ALLOWED_ORIGINS` env var; no `*` permitted in production (fail-closed)
- `allow_credentials = True`
- `allow_headers = ["Authorization", "Content-Type"]`

### Security headers (applied to every response)

| Header | Value |
|--------|-------|
| X-Content-Type-Options | nosniff |
| X-Frame-Options | DENY |
| Referrer-Policy | no-referrer |
| Content-Security-Policy | configured |
| Permissions-Policy | configured |
| HSTS | production only |

### Shared records (cross-system)

The following models are written by the Planning Workspace and read (or cross-linked) by the old TMS:
- `ParadeNight` / `TrainingSession` — linked from `ParadeDate`
- `Facilitator` — shared reference
- `CurriculumItem` — shared reference

---

## B. Cross-site Auth / Session Testing

| Test | Method | Result | Notes |
|------|--------|--------|-------|
| TMS login sets `aafc_session` cookie | Code audit | ✅ | Cookie is set on the backend domain; both frontends send to same origin |
| Planning Workspace inherits session without second login | Code audit | ✅ | Both `connected-frontend/` and `frontend/` hit `aafc-tms-backend`; cookie is included in credentialed requests |
| Session expiry (30 min) forces re-auth | Code audit | ✅ | `decode_token()` returns `None` on expired JWT; `get_principal()` returns 401 |
| Cookie secure in production | Code audit | ✅ | `validate_for_production()` raises `RuntimeError` if `COOKIE_SECURE=False` |
| Cross-origin requests carry cookie | Code audit | ✅ | CORS `allow_credentials=True`; browser sends cookie when request is credentialed |
| CSRF risk from lax cookie | Code audit | ⚠️ | `SameSite=lax` is acceptable for navigation but may allow CSRF via top-level POST from attacker-controlled site in some browsers. Mitigation: `allow_headers` does not include `*`; POST requires `Content-Type: application/json` which triggers CORS preflight. Assessed as **low risk** given JSON-only API. |
| Session invalidation on logout | 🔲 | Not tested — requires live browser session |
| Session cookie not visible in JS | Code audit | ✅ | HttpOnly flag implied by FastAPI cookie creation with `httponly=True` |

> **Browser testing required:** B tests marked 🔲 require a live authenticated session and cannot be completed from the CLI. User must verify these in the browser.

---

## C. Cross-site Data Consistency

| Test | Method | Result | Notes |
|------|--------|--------|-------|
| ParadeNight created in PW visible in old TMS | Code audit | ✅ | PW writes to `ParadeNight` table; old TMS reads same table |
| Sessions assigned in PW visible as training sessions | Code audit | ✅ | PW creates `TrainingSession` records; old TMS session views read same |
| Facilitator created in old TMS available in PW | Code audit | ✅ | `Facilitator` is a shared model, no copy |
| CEA activities do not appear in old TMS session builder | Code audit | ✅ | `CeaActivity` is PW-only; old TMS session builder is separate |
| Live end-to-end consistency | 🔲 | Requires browser |

---

## D. Code Coverage

| Area | Coverage method | Result |
|------|----------------|--------|
| TypeScript (frontend) | `tsc --noEmit` | ✅ Exit 0 — no type errors |
| Python syntax | `py_compile` | ✅ All key backend modules pass |
| Unit tests | `pytest` | 🔲 No test suite found in repo — coverage tooling not configured |
| Integration tests | Manual curl (prior sessions) | ⚠️ Backend API validated manually; no automated test suite |

**Gap:** There is no automated test suite (no `tests/` directory, no pytest configuration). This is a known gap in the project. All functional validation has been manual.

---

## E. Static Code Analysis

### E1. TypeScript

```
npx tsc --noEmit   →   EXIT 0 (no errors)
```

All type signatures are sound. `planningApi.listAnchors()` method name corrected from `anchors()` in prior session.

### E2. Python syntax

```
python3 -m py_compile main.py config.py security.py permissions.py dependencies.py routers/planning.py
→   SYNTAX_OK
```

### E3. Secrets scan

Scanned for hardcoded credentials: no production secrets found in source.

- `config.py` lines 23–24: `SECRET_KEY = "dev-only-..."` and `JWT_SECRET = "dev-only-..."` are development defaults, clearly labelled, and **blocked at startup** in production by `validate_for_production()`.
- `system.py` line 324: `PGPASSWORD` is set from an environment variable at runtime, not hardcoded.

### E4. Dependency vulnerability scan

Dependency scan not run (no `pip-audit` or `safety` installed in the sandbox). Versions in `requirements.txt` use `>=` lower bounds — actual pinned versions in production should be audited with `pip-audit` before RC sign-off.

Key dependencies and known vulnerability exposure:
| Package | Min version | Notes |
|---------|------------|-------|
| fastapi | ≥0.110 | Actively maintained |
| pyjwt | ≥2.8 | Fix for algorithm confusion (CVE-2022-29217) requires ≥2.4 — met |
| passlib | ≥1.7 | PBKDF2-SHA256 in use — secure; argon2 preferred for higher security |
| sqlalchemy | ≥2.0 | Parameterised queries throughout — no raw SQL injection risk found |

### E5. Security TODOs / bypass markers

Scanned for `TODO`, `FIXME`, `HACK`, `skip.*auth`, `bypass`, `NOAUTH`:
- No security bypass markers found in source.

### E6. Dead code / unused exports

Not scanned (no tooling configured). Minor: `night-summaries` endpoint (`/years/{year_id}/night-summaries`) is now superseded by the embedded `sessions_summary` in `annual-program`. The endpoint is still registered and functional but is no longer called by the frontend. It is harmless (read-only, gated behind RBAC) but could be removed in a future cleanup.

---

## F. Functional Break Testing

### Authentication boundary

| Test | Result | Notes |
|------|--------|-------|
| Unauthenticated request to planning API | ✅ 401 | `get_principal()` raises 401 if no token |
| Invalid/expired token | ✅ 401 | `decode_token()` returns `None` → 401 |
| Inactive user | ✅ 401 | `user.active_status` checked post-decode |
| Correct role required for write | ✅ 403 | `_require_plan_write()` and `_require_year_access(write=True)` gate all mutations |
| `sqn_general` cannot write | ✅ 403 | `_WRITE_BLOCKED` frozenset includes `sqn_general` |
| `wing_admin` cannot write squadron data without proxy | ✅ 403 | `require_can_write_squadron()` raises with `proxy_required` detail |
| National admin cannot write without intervention | ✅ 403 | Raises `intervention_required` |

### RBAC scope

| Test | Result | Notes |
|------|--------|-------|
| `sqn_admin` sees only own squadron years | ✅ | `list_planning_years()` filters by `unit_id == p.squadron_id` |
| `wing_admin` sees only own wing years | ✅ | Filter by `wing_id == p.wing_id` |
| `national/system_admin` sees all years | ✅ | No filter |
| `sqn_admin` cannot GET year from different squadron | ✅ | `_require_year_access()` raises 403 |
| Wing HQ overlay scoped to squadron's wing | ✅ | `annual-program` resolves `overlay_wing_id` from planning year's wing |

### Input validation

| Test | Result | Notes |
|------|--------|-------|
| Invalid date format in `HolidayIn` | ✅ 422 | `model_post_init` validates ISO-8601 |
| `end_date` before `start_date` | ✅ 422 | Pydantic validator rejects |
| `generate-parade-dates` without `end_date` or `max_repeats` | ✅ 400 | Explicit check |
| Invalid `cadet_group` in session create | ✅ 422 | Checked against `CADET_GROUPS` constant |
| CSV injection in XLSX export | ✅ Protected | `_neutralise_cell()` prefixes `=`, `+`, `-`, `@` with `'` |
| XLSX upload too large (schedule import) | ✅ 413 | `UPLOAD_MAX_MB` guard in place |

### Error leakage

| Test | Result | Notes |
|------|--------|-------|
| 500 error response body | ✅ | Returns `{"error": "internal_error"}` — no stack trace |
| OpenAPI docs accessible in production | ✅ | `docs_url=None, redoc_url=None, openapi_url=None` |

---

## G. Authorised Penetration Testing (Code-Level)

> **Safety boundary:** All testing performed by code audit against staging/local source only. No production data queried, no access codes exposed, no personal information exfiltrated, no production records altered.

### G1. IDOR-001 — CEA endpoints missing planning-year scope check (MEDIUM-HIGH)

**Affected endpoints:**
- `GET /api/planning/years/{year_id}/cea/activities` (line 3641)
- `GET /api/planning/years/{year_id}/cea/batches` (line 3660)
- `POST /api/planning/years/{year_id}/cea/import` (line 3741)
- `POST /api/planning/years/{year_id}/cea/activities` (line 3976)
- `PATCH /api/planning/cea/{activity_id}/classify` (line 3894)
- `POST /api/planning/cea/{activity_id}/local-hide` (line 3925)

**Root cause:** These endpoints call `require_role(p, "sqn_admin", ...)` but do NOT call `_require_year_access(p, py)` after fetching the planning year or CEA activity. A `sqn_admin` from Squadron A can supply the UUID of a planning year owned by Squadron B and read or write its CEA activities.

**Exploitability:** Requires a valid admin session and knowledge of a target planning year UUID (random UUID4). Not exploitable from outside the auth boundary, but a malicious or confused admin could cross squadron boundaries.

**Fix required:**
```python
# In list_cea_activities, list_cea_batches, import_cea_csv, create_manual_activity:
year = _get_year_or_404(year_id, db)
_require_year_access(p, year, write=False)   # or write=True for mutations

# In classify_cea_activity, set_local_hide:
act = db.get(CeaActivity, activity_id)
if not act:
    raise HTTPException(404, ...)
year = _get_year_or_404(act.planning_year_id, db)
_require_year_access(p, year, write=True)
```

**Severity:** MEDIUM-HIGH (cross-tenant data access within authenticated system).

---

### G2. IDOR-002 — Notice endpoints missing parade-date ownership check (MEDIUM)

**Affected endpoints:**
- `GET /api/planning/parade-dates/{date_id}/notices` (line 3511)
- `POST /api/planning/parade-dates/{date_id}/notices` (line 3533)
- `PATCH /api/planning/notices/{notice_id}` (line 3565)
- `POST /api/planning/notices/{notice_id}/archive` (line 3586)

**Root cause:** `list_notices()` and `create_notice()` fetch the `ParadeDate` and check role, but do not call `_require_year_access()` on the linked planning year. `update_notice()` and `archive_notice()` only call `require_role()` with no scope check at all.

**Fix required:**
```python
# In list_notices / create_notice:
pd = db.get(ParadeDate, date_id)
if not pd:
    raise HTTPException(404, ...)
py = _get_year_or_404(pd.planning_year_id, db)
_require_year_access(p, py)   # or write=True for create

# In update_notice / archive_notice:
notice = db.get(PlanningNotice, notice_id)
if not notice:
    raise HTTPException(404, ...)
py = _get_year_or_404(notice.planning_year_id, db)
_require_year_access(p, py, write=True)
```

**Severity:** MEDIUM (cross-tenant write access to another unit's parade notices).

---

### G3. IDOR-003 — Facilitator leave endpoints missing squadron scope check (MEDIUM)

**Affected endpoints:**
- `GET /api/planning/facilitators/{fac_id}/leave` (line 3162)
- `POST /api/planning/facilitators/{fac_id}/leave` (line 3197)

**Root cause:** Both check role but do not verify the facilitator belongs to the user's squadron. A `sqn_admin` from Squadron A can read or add leave for a facilitator in Squadron B by supplying the facilitator's UUID.

**Fix required:**
```python
fac = db.get(Facilitator, fac_id)
if not fac:
    raise HTTPException(404, ...)
if p.role == "sqn_admin" and fac.squadron_id != p.squadron_id:
    raise HTTPException(403, detail={"error": "out_of_scope"})
elif p.role == "wing_admin" and fac.wing_id != p.wing_id:
    raise HTTPException(403, detail={"error": "out_of_scope"})
```

**Severity:** MEDIUM.

---

### G4. Missing file size limit on CEA CSV import (LOW-MEDIUM)

**Affected endpoint:** `POST /api/planning/years/{year_id}/cea/import` (line 3741)

`import_cea_csv()` calls `await file.read()` without a size check. By contrast, `import_annual_program()` (line 3010) and `import_schedule_xlsx()` (line 2816) both check `len(content) > 5 MB` before processing.

A large malformed CSV (e.g., 500 MB) would be fully loaded into memory before any error is raised.

**Fix:**
```python
content = await file.read()
if len(content) > settings.UPLOAD_MAX_MB * 1024 * 1024:
    raise HTTPException(413, detail={"error": "file_too_large"})
```

**Severity:** LOW-MEDIUM (requires authenticated wing_admin session to exploit; not a public-facing endpoint).

---

### G5. In-memory rate limiter — does not survive multi-worker deployment (INFO)

`_attempts` and `_lockouts` dicts in `security.py` are in-process. If Railway auto-scales to multiple workers (e.g., via gunicorn), login rate limiting is per-worker and an attacker with N workers of requests can bypass the limit.

**Current situation:** Railway single-instance deployment; single worker. Risk is low in current setup.

**Documented fix:** Comment in `security.py` notes "Production: replace with Redis." This should be done before scaling.

**Severity:** INFO (no immediate risk in single-worker deployment).

---

### G6. `GET /sessions/{session_id}` uses write permission for read (INFO)

`get_session()` (line 1253) calls `require_can_write_squadron()` to gate a GET request. This is overly strict: `wing_admin` without active proxy cannot read sessions. The correct check for a read-only endpoint is `require_can_view_squadron()`. No data leakage risk — it's too strict rather than too permissive.

**Severity:** INFO (UX limitation, not a security issue).

---

### G7. SQL injection assessment

All queries use SQLAlchemy ORM with parameterised statements. No raw SQL string interpolation found in scoped review. CSV/XLSX injection in exports is neutralised by `_neutralise_cell()`. **No SQL injection vectors found.**

### G8. XSS assessment

The frontend is a React SPA — React escapes all rendered content by default. No `dangerouslySetInnerHTML` calls found in Planning Workspace components (not fully audited; requires browser audit). The backend is API-only with no HTML rendering. **Low risk; browser audit recommended.**

### G9. Authentication algorithm confusion

`decode_token()` specifies `algorithms=[settings.JWT_ALG]` (not `algorithms=["*"]`) — not vulnerable to algorithm substitution attacks (CVE-2022-29217 class). **Pass.**

### G10. Privilege escalation

No endpoint allows a user to set their own role. Role is pulled from the database `User.role` field after token validation. Token payload is not trusted for role decisions. **Pass.**

---

## H. Stress / Endurance Testing (Staging Only)

> Testing not executed — no staging environment available. Results documented as design targets.

**Design targets from Phase 6 (RC plan):**

| Scenario | Target | Expected behaviour |
|----------|--------|--------------------|
| 10 concurrent users | < 2s p95 annual-program | Should pass (2-query bulk load, no N+1) |
| 25 concurrent users | < 3s p95 | Monitor DB connection pool |
| 50 concurrent users | < 5s p95 | Likely hits Railway free-tier limits |
| 100 concurrent users | Graceful degradation | Not expected to meet targets on free tier |

**To execute:** Use `k6` or `locust` against staging environment with synthetic users. Do not run load tests against production.

---

## I. Chaos / Resilience Testing (Staging Only)

> Not executed. Design assessment only.

| Scenario | Expected behaviour | Notes |
|----------|--------------------|-------|
| DB connection drop during write | SQLAlchemy connection pool retry; 500 to client | Acceptable |
| DB connection drop during read | 500 to client | `{"error": "internal_error"}` — no internals leaked |
| Malformed JWT | 401 | Tested by code audit ✅ |
| CEA import with malformed CSV | 400 with `file_parse_failed` | Tested by code audit ✅ |
| Large (>5 MB) file upload | 413 | ✅ for schedule/program import; ❌ for CEA import (IDOR-004 above) |
| Railway restart mid-request | Request fails; client retries | Autosave on frontend retries |

---

## J. Backup / Recovery Testing (Staging / Disposable Only)

> Not executed. Railway Postgres auto-backup policy should be verified by user in Railway dashboard.

**Data export endpoints available for manual backup before any rollback:**
- `GET /api/planning/years/{year_id}/annual-program`
- `GET /api/planning/years/{year_id}/cea/activities`
- `GET /api/planning/years/{year_id}/anchors`
- `GET /api/planning/years/{year_id}/holidays`

---

## K. TRGO Operational Review

> TRGO items that require browser access are marked 🔲. Code-auditable items are assessed.

| Area | TRGO Check | Status | Notes |
|------|-----------|--------|-------|
| Planning year access | TRGO can view all squadron years | ✅ (code) | `national_admin` / `system_admin` unrestricted in `list_planning_years()` |
| Squadron data isolation | Wing cannot write into squadron without proxy | ✅ (code) | `require_can_write_squadron()` enforces proxy requirement |
| Audit log | Every write is logged | ✅ (code) | `audit()` called on create/update/delete throughout planning router |
| CEA import restricted | Only wing_admin+ can import CEA | ✅ (code) | `require_role(p, "wing_admin", ...)` on import endpoint |
| Export available | XLSX export for annual program and schedule | ✅ (code) | Both export endpoints implemented |
| Rollback plan documented | Rollback plan exists | ✅ | `docs/planning_workspace_rollback_plan.md` |
| Old TMS unaffected | Old TMS frontend unchanged | ✅ | No changes to `connected-frontend/` or `aafc-tms-frontend` service |
| User guide available | User test guide exists | ✅ | `docs/planning_workspace_user_test_guide.md` |
| Live workflow test | TRGO must test in browser | 🔲 | |

---

## L. SOCAD Oversight Review

| Area | SOCAD Check | Status | Notes |
|------|-----------|--------|-------|
| No personal information in CEA export | XLSX cells contain activity data, not personal info | ✅ (code) | CEA activities contain `activity_poc` (name/contact) — this is operational, not personal |
| Access code never in response | `generate_code()` returns plaintext exactly once to caller; `hash_code()` stores hash | ✅ (code) | |
| Session token not in response body | JWT delivered as HttpOnly cookie only | ✅ (code) | |
| Security headers | Comprehensive headers applied | ✅ (code) | |
| HTTPS enforced in production | `COOKIE_SECURE=True` required; HSTS applied | ✅ (code) | |
| OpenAPI disabled in production | `docs_url=None` etc. | ✅ (code) | |
| Rate limiting on login | 5 attempts / 5 min window; 15 min lockout | ✅ (code) | Single-process limitation noted (IDOR-005 / G5) |
| IDOR findings | 3 IDOR vulnerabilities found | ❌ | Must be patched before GO |
| CEA file size limit | Missing on CEA import | ⚠️ | Medium priority fix |
| Data segregation in multi-tenant load | CEA endpoints missing year-scope checks | ❌ | Must be patched before GO |

---

## M. Bug-Fix Loop

### Open issues ranked by severity

| ID | Severity | Title | Status |
|----|----------|-------|--------|
| IDOR-001 | **HIGH** | CEA endpoints missing `_require_year_access()` | Must fix before GO |
| IDOR-002 | **MEDIUM-HIGH** | Notice endpoints missing scope check | Must fix before GO |
| IDOR-003 | **MEDIUM** | Facilitator leave missing squadron scope | Must fix before GO |
| BUG-004 | **MEDIUM** | CEA History tab 500 — `created_by` column missing | Fix in v36 migration (pending deploy) |
| MISS-001 | **LOW-MEDIUM** | CEA CSV import missing file size guard | Fix recommended before GO |
| DEPLOY-001 | **INFRA** | Railway deploys failing silently | Must resolve to deploy any fixes |
| G5 | **INFO** | In-memory rate limiter, single-process | Document; fix before horizontal scaling |
| G6 | **INFO** | `get_session()` uses write check for read | Minor UX issue; low priority |

### Fix plan

**IDOR-001, IDOR-002, IDOR-003, MISS-001** should be patched in a single commit on `main` and cherry-picked to `release/planning-workspace-rc1`. Changes are additive (adding scope checks) and safe to deploy without a migration.

**BUG-004** is already fixed in v36 migration — blocked only on DEPLOY-001.

**DEPLOY-001** — user must resolve Railway deploy mechanism before any fixes can go live.

---

## N. Integrated Release Gate

### GO / GO-with-limitations / NO-GO assessment

**Current verdict: NO-GO — pending fixes**

Cannot issue GO until:

1. **DEPLOY-001 resolved** — current deploy pipeline is broken. All fixes are in code but not live.
2. **IDOR-001, IDOR-002, IDOR-003 patched and deployed** — cross-tenant data access vulnerabilities in authenticated system.
3. **BUG-004 migration deployed** — CEA History tab must be confirmed working.
4. **End-to-end browser workflow tested** — manual test cycle against live system (sections B, C, K browser items) not yet completed.

### Conditions for GO-with-limitations

Once IDOR fixes, BUG-004, and DEPLOY-001 are resolved, may issue **GO-with-limitations** if:
- CEA History tab confirmed working post-migration
- Activities tab (unified view) confirmed working in browser
- No new P0/P1 issues found in browser test

Limitations to disclose at GO-with-limitations:
- No automated test suite
- Rate limiting is single-process
- Custom date range performance under extreme ranges untested

### Conditions for full GO

All of the above plus:
- TRGO live workflow sign-off (section K browser items)
- SOCAD confirmation of IDOR patch deployment
- Performance baseline confirmed in staging under 25 concurrent users

---

## O. Summary Table

### Sections completed

| Section | Title | Status |
|---------|-------|--------|
| A | Integrated architecture | ✅ Complete |
| B | Cross-site auth/session | ✅ Code audit complete; 🔲 browser tests pending |
| C | Cross-site data consistency | ✅ Code audit complete; 🔲 browser tests pending |
| D | Code coverage | ✅ TypeScript clean; Python syntax clean; no unit test suite |
| E | Static code analysis | ✅ Complete — no hardcoded secrets, no syntax errors, TS clean |
| F | Functional break testing | ✅ Code audit complete |
| G | Authorised penetration testing | ✅ Complete — 3 IDOR vulnerabilities found |
| H | Stress/endurance testing | 🔲 Not executed (no staging environment) |
| I | Chaos/resilience testing | 🔲 Not executed (design assessment only) |
| J | Backup/recovery testing | 🔲 Not executed |
| K | TRGO operational review | ✅ Code items complete; 🔲 browser items pending |
| L | SOCAD oversight review | ✅ Code items complete |
| M | Bug-fix loop | ✅ Findings logged; fixes required before GO |
| N | Release gate | ✅ **NO-GO — pending fixes** |
| O | This report | ✅ |

---

## Appendix — Files Changed (RC1)

| File | Change |
|------|--------|
| `backend/alembic/versions/x9y0z1a2b3c4_v36_cea_import_batch_created_by.py` | v36 migration: add `created_by`/`updated_by` to `cea_import_batches` |
| `frontend/src/components/planning/PlanningBottomDrawer.tsx` | Unified Activities tab (CEA + anchors + holidays); CEA History renamed |
| `frontend/src/routes/PlanningWorkspace.tsx` | Default tab changed to Activities |
| `docs/planning_workspace_rc1_test_report.md` | RC1 test report |
| `docs/planning_workspace_user_test_guide.md` | User test guide |
| `docs/planning_workspace_rollback_plan.md` | Rollback plan |
| `docs/planning_workspace_integrated_system_test_report.md` | This document |

---

## Appendix — IDOR Fix Summary (for reviewer)

All three IDOR fixes follow the same pattern: add a `_require_year_access()` or squadron-scope check immediately after the primary object is fetched. No schema changes required. Estimated effort: 30–60 minutes.

```python
# IDOR-001 pattern (CEA endpoints with year_id in URL):
year = _get_year_or_404(year_id, db)
_require_year_access(p, year)  # add this line

# IDOR-001 pattern (CEA endpoints without year_id, using activity's year):
act = db.get(CeaActivity, activity_id)
if not act:
    raise HTTPException(404, ...)
year = _get_year_or_404(act.planning_year_id, db)
_require_year_access(p, year, write=True)  # add this block

# IDOR-002 pattern (notices with date_id):
pd = db.get(ParadeDate, date_id)
if not pd:
    raise HTTPException(404, ...)
year = _get_year_or_404(pd.planning_year_id, db)
_require_year_access(p, year)  # add this line

# IDOR-002 pattern (notices with notice_id):
notice = db.get(PlanningNotice, notice_id)
if not notice:
    raise HTTPException(404, ...)
year = _get_year_or_404(notice.planning_year_id, db)
_require_year_access(p, year, write=True)  # add this block

# IDOR-003 pattern (facilitator leave):
fac = db.get(Facilitator, fac_id)
if not fac:
    raise HTTPException(404, ...)
# Add after role check:
if p.role == "sqn_admin" and fac.squadron_id != p.squadron_id:
    raise HTTPException(403, detail={"error": "out_of_scope"})
if p.role == "wing_admin" and fac.wing_id != p.wing_id:
    raise HTTPException(403, detail={"error": "out_of_scope"})
```

---

*Report generated 2026-07-13. Next action: patch IDOR vulnerabilities, resolve DEPLOY-001, then re-issue gate assessment.*
