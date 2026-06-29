# AAFC TMS — Security Review Checklist

## Authentication

| Check | Status | Notes |
|---|---|---|
| Access-code login requires bcrypt match | PASS | `security.py:verify_code` |
| Login rate limiting (5 attempts / 5 min / IP) | PASS | `security.py:login_blocked` |
| Lockout after max attempts (15 min) | PASS | `LOGIN_LOCKOUT_SEC=900` in config |
| Disabled account cannot log in | PASS | `auth.py:login` checks `active_status` |
| Session JWT created with TTL (30 min default) | PASS | `ACCESS_TOKEN_TTL_MIN=30` |
| JWT verified on every request | PASS | `dependencies.py:get_principal` |
| Logout deletes session cookie | PASS | `auth.py:logout` |
| Sliding refresh extends session | PASS | `auth.py:refresh` |
| Old reset code invalidated on use | PASS | Access code one-time display |

## Authorisation

| Check | Status | Notes |
|---|---|---|
| system_admin is highest role | PASS | All system endpoints require it |
| national_admin cannot access system endpoints | PASS | Test confirmed 403 |
| Cross-scope SQN access denied | PASS | `permissions.py:can_view_squadron` |
| Cross-scope wing access denied | PASS | `permissions.py:can_view_wing` |
| Wing admin cannot write SQN without proxy | PASS | `require_can_write_squadron` |
| national_admin cannot write SQN without intervention | PASS | `require_can_write_squadron` |
| Read-only roles cannot POST/PUT/DELETE | PASS | `_WRITE_ROLES` check per router |
| Auditor is read-only | PASS | Auditor blocked from all write paths |
| IDOR protection via scope check | PASS | All list/get endpoints filter by scope |

## Secrets

| Check | Status | Notes |
|---|---|---|
| No plaintext access codes in API responses | PASS | All code lookups use hash only |
| No access-code hashes in API responses | PASS | No hash field in any serialiser |
| No seeded codes in frontend JS | PASS | Grep returns 0 |
| JWT secret not in frontend | PASS | Config only, server-side |
| Database URL not in frontend | PASS | Config only, server-side |
| Production validates strong secrets | PASS | `config.py:validate_for_production` |
| Production rejects dev-prefix secrets | PASS | Checked in `validate_for_production` |

## Frontend

| Check | Status | Notes |
|---|---|---|
| User content escaped before innerHTML | PASS | `esc()` helper used throughout |
| No operational localStorage | PASS | Grep returns 0 |
| No secrets in frontend JS | PASS | Grep returns 0 |
| API errors do not leak internal details | PASS | `apiErr()` maps error codes to messages |
| CSP header set by backend | PASS | `main.py:security_headers` |
| X-Frame-Options DENY | PASS | `main.py:security_headers` |
| X-Content-Type-Options nosniff | PASS | `main.py:security_headers` |

## Backend

| Check | Status | Notes |
|---|---|---|
| Input validation via Pydantic | PASS | All route bodies are typed models |
| Error responses do not expose stack traces | PASS | `main.py:server_error` handler |
| CORS locked to configured origins | PASS | `main.py:CORSMiddleware` |
| HSTS set in production | PASS | `main.py:security_headers` (prod only) |
| Audit log is immutable (no delete/update path) | PASS | No delete endpoint on AuditLog |
| SQLite migrations safe (batch_alter) | PASS | All migrations use batch_alter_table |

## Gaps / Post-Alpha Work

| Item | Risk | Priority |
|---|---|---|
| Maintenance mode does not block backend writes | Low (admin control only) | Post-alpha |
| Session revocation (force logout) not implemented | Medium | Post-alpha |
| CSRF protection not implemented (cookie + CORS is current control) | Low (SameSite=lax mitigates) | Post-alpha |
| Rate limiting is per-IP in-memory (resets on restart) | Low for demo | Post-alpha |
| Audit log pagination not implemented (limit=500) | Low | Post-alpha |
| Log retention policy not defined | Low | Pre-production |

## Running the security tests

```bash
# Automated backend tests
cd backend && python -m pytest tests/test_system_admin.py tests/test_accounts.py -q

# Live security scope test (requires server running)
python tools/stress/security_scope_test.py

# Frontend greps
grep -Rc "ADMIN703|ADMIN7WG|ADMINNATIONAL|SYSADMIN2026|plain_code|code_hash|localStorage" connected-frontend
grep -Rc "JWT_SECRET|SECRET_KEY|DATABASE_URL" connected-frontend
```

All greps must return 0 matches before packaging.
