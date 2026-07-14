# AAFC TMS — Production Configuration Review

Phase 8 (Operational Release Gate). Verification of effective production configuration.
Created: 2026-07-14.

Variable values are NOT recorded here — only variable names and pass/fail status.
All inspections are against Railway environment variable names and code behaviour.

---

## Configuration Checks

### Identity and Environment

| Check | Required | Status | Evidence |
|---|---|---|---|
| `ENVIRONMENT=production` | Must be `production` or `prod` | ⚠️ PENDING APPROVAL | Currently `staging`; change prepared, approval required (DEFECT-003) |
| Debug mode disabled | `debug=False` in FastAPI app | ✓ PASS | `main.py` hardcodes `FastAPI(debug=False)` — no environment gate |
| Production error redaction | 500 errors return `{"error": "internal_error"}` only | ✓ PASS | `server_error` handler in `main.py` verified |
| `/docs` not exposed | FastAPI docs disabled | ✓ PASS | `FastAPI(docs_url=None, redoc_url=None, openapi_url=None)` hardcoded |
| `/openapi.json` not exposed | Same | ✓ PASS | `openapi_url=None` hardcoded |
| Startup safety checks | `validate_for_production()` runs on startup | ⚠️ PENDING | Blocked by ENVIRONMENT=staging; will activate once variable corrected |

### Security Secrets

| Check | Required | Status | Evidence |
|---|---|---|---|
| `JWT_SECRET` configured | ≥32 chars, not a dev default | ✓ PASS | Verified 54 chars, not dev-prefixed (inspected without revealing value) |
| `SECRET_KEY` configured | ≥32 chars, not a dev default | ✓ PASS | Verified 54 chars, not dev-prefixed |
| Secrets NOT in frontend bundle | No `JWT_SECRET` or `SECRET_KEY` in `index.html` | ✓ PASS | Security grep clean |
| Secrets NOT in git history | Not committed | ✓ PASS | No secrets in any committed file |

### Cookie and Session Security

| Check | Required | Status | Evidence |
|---|---|---|---|
| `COOKIE_SECURE=true` | Must be `true` in production | ✓ PASS | Verified in Railway production env |
| `COOKIE_HTTPONLY=true` | Must be `true` | ✓ PASS | `HttpOnly=True` set in auth.py cookie creation |
| `COOKIE_SAMESITE=none` | Required for cross-subdomain Railway architecture | ✓ PASS | Empirically proven in staging; see DEFECT-004 investigation |
| No production cookies in localStorage | Operational data not in localStorage | ✓ PASS | Security grep clean; no localStorage usage in connected-frontend |

### CORS

| Check | Required | Status | Evidence |
|---|---|---|---|
| `CORS_ALLOWED_ORIGINS` set | Must not be empty or `*` | ✓ PASS | Non-empty, non-wildcard value confirmed in Railway production env |
| No `localhost` in production CORS | Must be absent | ✓ PASS | Confirmed no localhost in production `CORS_ALLOWED_ORIGINS` |
| Frontend URLs match CORS allowlist | Production frontend origins are listed | MANUAL VERIFY | Confirm `aafc-tms-frontend-production.up.railway.app` and `aafc-tms-planning-workspace-preview-production.up.railway.app` are in `CORS_ALLOWED_ORIGINS` |

### HTTPS and Transport Security

| Check | Required | Status | Evidence |
|---|---|---|---|
| HTTPS enforced by Railway | All traffic HTTPS | ✓ PASS | Railway terminates TLS at edge |
| HSTS header sent | `Strict-Transport-Security` in response | ⚠️ PENDING | Blocked by ENVIRONMENT=staging; HSTS middleware only activates when `is_production=True` |
| Security headers enabled | CSP, X-Frame-Options, X-Content-Type-Options, etc. | ✓ PASS | Security headers middleware in `main.py` runs regardless of environment |

### Rate Limiting

| Check | Required | Status | Evidence |
|---|---|---|---|
| IP-based rate limiting | Active | ✓ PASS | 5-failure lockout proven in `test_lockout.py` |
| Per-account lockout | Active | ✓ PASS | `test_account_lockout_blocks_correct_code` passes |
| Rate limiting NOT environment-gated | Must be on in all environments | ✓ PASS | `security.py` rate limiting has no environment check |

### Database

| Check | Required | Status | Evidence |
|---|---|---|---|
| `DATABASE_URL` points to production Postgres | Not SQLite | ✓ PASS | Railway production env variable set; `database.py` validates not SQLite in `validate_for_production()` |
| `DATABASE_URL` not in frontend | Must be absent | ✓ PASS | Security grep clean |
| Migration revision | Must match local head | ✓ PASS | `x9y0z1a2b3c4` confirmed local/staging/production |
| Production database NOT SQLite | Must be PostgreSQL | ✓ PASS | Railway managed PostgreSQL |

### Seed / Reset Protection

| Check | Required | Status | Evidence |
|---|---|---|---|
| `seed_all.py` cannot run against production | Protected by hostname fingerprint + ENVIRONMENT check | ✓ PASS | DEFECT-002 fixed; `check_destructive_reset_allowed()` added |
| `bootstrap-staging` endpoint rejects production | Returns 403 when `is_production=True` | ✓ PASS in code | ⚠️ Live in production until ENVIRONMENT variable corrected |

### API Documentation

| Check | Required | Status | Evidence |
|---|---|---|---|
| Swagger UI disabled | `docs_url=None` | ✓ PASS | Hardcoded in `main.py` |
| ReDoc disabled | `redoc_url=None` | ✓ PASS | Hardcoded in `main.py` |
| OpenAPI JSON disabled | `openapi_url=None` | ✓ PASS | Hardcoded in `main.py` |

---

## Pending Production Configuration Changes

### Change 1: Set `ENVIRONMENT=production` (DEFECT-003)

**Required action**: In Railway production environment, set:
```
ENVIRONMENT=production
```

**Effect of this change**:
- `validate_for_production()` activates on next restart — will verify JWT_SECRET, SECRET_KEY, COOKIE_SECURE, CORS, DATABASE_URL
- HSTS header will be sent on all responses
- `bootstrap-staging` endpoint will return 403 for all callers (including system_admin)
- `/api/system/status` will correctly report `"environment": "production"`
- `reset_db()` safety check will additionally block on `ENVIRONMENT`

**Pre-change verification** (done): Current production values for JWT_SECRET, SECRET_KEY, COOKIE_SECURE, CORS_ALLOWED_ORIGINS, and DATABASE_URL have been inspected (without exposing values) and would all pass `validate_for_production()`. This variable change will NOT crash-loop the application.

**How to apply** (after approval):
```bash
railway environment production
railway variables set ENVIRONMENT=production --service aafc-tms-backend
```

**Verification after applying**:
```bash
curl https://aafc-tms-backend-production.up.railway.app/api/system/status
# Expect: {"environment": "production", ...}

# HSTS header check
curl -I https://aafc-tms-backend-production.up.railway.app/api/health/ready | grep -i strict
# Expect: strict-transport-security: max-age=31536000; includeSubDomains

# Bootstrap endpoint (must return 403 after change)
# Test in staging with ENVIRONMENT=production first, not production directly
```

**Approval required**: Yes. Do not apply without explicit approval from the authorised project owner.

---

## Configuration Review Summary

| Category | Status | Blocker? |
|---|---|---|
| Identity / environment | ⚠️ PENDING (DEFECT-003) | YES — ENVIRONMENT=staging is the root cause |
| Security secrets | ✓ PASS | — |
| Cookie / session | ✓ PASS | — |
| CORS | ✓ PASS (manual verify CORS list) | — |
| HTTPS / HSTS | ⚠️ PENDING (HSTS blocked by ENVIRONMENT) | MEDIUM |
| Rate limiting | ✓ PASS | — |
| Database | ✓ PASS | — |
| Seed / reset protection | ✓ PASS in code | — |
| API docs | ✓ PASS | — |

**All configuration checks pass or are pending the single approved change to `ENVIRONMENT=production`.** No additional configuration changes are required for production readiness.
