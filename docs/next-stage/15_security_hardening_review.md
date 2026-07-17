# Phase 15 — Security Hardening Review (Level C)

**Date completed:** 2026-07-17  
**Scope:** Full OWASP Top-10 audit of the AAFC TMS backend, connected-frontend, and React Planning Workspace.

---

## Status by OWASP Category

### A01 — Broken Access Control ✅ COMPLETE
- All endpoints enforce role/scope via `permissions.py` helpers.
- DEFECT-001 (sqn_general IDOR — parade nights) fixed on branch.
- DEFECT-007 (sqn_general planning years IDOR) fixed in rc3.
- Token version revocation: added in Phase 13 — old tokens rejected after code reset.
- Audit log is immutable; no delete/update endpoints exist.

### A02 — Cryptographic Failures ✅ COMPLETE
- Access codes: PBKDF2-SHA256 via passlib. No plaintext or hash in any API response.
- JWTs: HS256 with `jti` (unique per token) and `tv` (token version) claims.
- `COOKIE_SECURE=True` required in production (`validate_for_production()` fails closed).
- HSTS injected by backend security_headers middleware in production.

### A03 — Injection ✅ COMPLETE
- All SQL via SQLAlchemy ORM (parameterized). The only `text()` calls are `SELECT 1` health checks.
- XSS: connected-frontend uses `esc()` helper for all innerHTML insertion; React app uses no `dangerouslySetInnerHTML`.
- No `eval()` or `new Function()` in frontend code.

### A04 — Insecure Design ✅ COMPLETE
- Per-IP sliding window rate limiter: login (DB-backed) + all API endpoints (in-memory, Phase 14).
- Per-account lockout on login (`AccessCode.failed_attempts`, `locked_until`).
- Token version revocation on code reset (Phase 13).

### A05 — Security Misconfiguration ✅ COMPLETE (+ improvement in this phase)
- `validate_for_production()` fails closed on insecure JWT secret, weak cookie config, localhost CORS.
- `/docs`, `/redoc`, `/openapi.json` all disabled in production.
- **IMPROVEMENT (this phase):** `nginx.conf` for `connected-frontend` now includes:
  - `Content-Security-Policy` (runtime-injected `connect-src` via `docker-entrypoint.sh`)
  - `Permissions-Policy: geolocation=(), microphone=(), camera=()`
  - Previously missing from the legacy SPA's nginx layer.

### A06 — Vulnerable and Outdated Components ⚠️ PERIODIC ACTION REQUIRED
- **Gap:** No automated dependency vulnerability scan in CI.
- **Action:** Run `pip-audit` (backend) and `npm audit` (frontend) before each release.

```bash
# Backend
cd backend && source .venv/bin/activate && pip-audit

# Frontend (React)
cd frontend && npm audit --audit-level=high

# Connected-frontend has no npm deps (single-file SPA).
```

These commands should be added to the pre-packaging checklist and run before any production deployment.

### A07 — Identification and Authentication Failures ✅ COMPLETE
- JWTs are short-lived (`ACCESS_TOKEN_TTL_MIN=30` default).
- Token version revocation invalidates sessions immediately after code reset (Phase 13).
- Per-IP and per-account login rate limiting.
- No personal identity fields in the User model — shared access codes by design.

### A08 — Software and Data Integrity Failures ✅ COMPLETE
- Protected DB fingerprints prevent `reset_db()` and `seed_all()` from running against production hosts.
- `second_wing_seed.py` refuses to run if `ENVIRONMENT=production`.
- Alembic migration chain enforced by `compute_alembic_head.py`.

### A09 — Security Logging and Monitoring Failures ✅ PARTIAL
- Structured JSON access log with `X-Request-ID` correlation (Phase 18).
- `AuditLog` table records all privileged actions.
- **Remaining gap:** No alerting on failed login spike or 5xx rate above threshold. This requires external monitoring (Railway metrics, Loki/CloudWatch alerts) — beyond code-level control.
- **Remaining gap:** DEFECT-003 (`ENVIRONMENT=staging` in production Railway config) — must be corrected in Railway dashboard (requires approved production change).

### A10 — Server-Side Request Forgery ✅ COMPLETE
- No user-controlled URL fetching. All external references are static (Google Fonts CDN, hardcoded at build time).

---

## Residual Risks (accepted for V1)

| Risk | Acceptance reason |
|---|---|
| `script-src 'unsafe-inline'` in connected-frontend CSP | App is a single-file SPA with all JS inline; nonce approach requires nginx-level request-scoped nonce injection. `esc()` is the primary XSS control. |
| No real-time alerting | Requires external monitoring infrastructure outside the application layer. Out of scope for V1 code work. |
| DEFECT-003 (Railway ENVIRONMENT var) | Pending approved production change — not a code defect. |
| No CSRF tokens | CORS is locked per-environment; `SameSite=lax` (default) prevents most CSRF. Cross-origin requests require an `Authorization: Bearer` header which JS code on a third-party site cannot obtain from an httpOnly cookie. Architecture decision documented in `.claude/rules/architecture.md`. |
| Dependency vulnerability scan not automated | Manual scan required before each release. Can be added to GitHub Actions workflow. |

---

## Pre-release Security Checklist (updated)

```bash
# 1. Security greps (from .claude/rules/security.md)
grep -Rc "your unit only|Controlled access for training" connected-frontend backend
grep -Rc "View current code|Show access code|Reveal code|Display existing code" connected-frontend backend
grep -Rc "ADMIN703|ADMIN7WG|ADMINNATIONAL|SYSADMIN2026|plain_code|code_hash|access_code|localStorage" connected-frontend
grep -Rc "JWT_SECRET|SECRET_KEY|DATABASE_URL" connected-frontend

# 2. Dependency vulnerability scan
cd backend && pip-audit
cd frontend && npm audit --audit-level=high

# 3. Verify validate_for_production passes in staging config
cd backend && ENVIRONMENT=production python -c "from app.config import settings; problems = settings.validate_for_production(); print('OK' if not problems else problems)"
```

All security grep checks must return 0 matches. `pip-audit` and `npm audit` must show no high/critical vulnerabilities.
