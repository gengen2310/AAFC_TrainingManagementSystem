# Final Security Assessment (Stage 9, in progress)

OWASP-aligned review. Builds on Stage 2's line-by-line pass (GAP-24 XSS, health-leak
fix) and Stage 4's tenancy/IDOR verification — this doc consolidates security-specific
findings and adds checks not already covered there.

## Mandated pre-packaging security greps (`.claude/rules/security.md`) — re-run, all clean

- Removed wording check: 0 matches
- Access-code exposure wording: 0 matches
- Seeded codes / access_code / code_hash / localStorage in `connected-frontend`: 0 matches
- Secrets (`JWT_SECRET`/`SECRET_KEY`/`DATABASE_URL`) in `connected-frontend`: 0 matches

## Injection

- **SQL injection**: only 3 raw-SQL `text()` calls exist in the entire backend
  (`system.py` ×2, `health.py` ×1) — all static, hardcoded strings (`SELECT 1`,
  `SELECT version_num FROM alembic_version`), zero user input interpolated. No
  f-string/`.format()`/`%`-based SQL construction found anywhere. Everything else
  goes through the SQLAlchemy ORM (parameterized by construction).
- **XSS**: see GAP-24 (found, fixed, live-verified) in the gap register — the
  significant finding of this pass. React frontend (`frontend/`) has zero
  `dangerouslySetInnerHTML` usage — relies on JSX's default escaping throughout.
  Neither frontend uses `eval()`/`new Function()`.
- **CSP due diligence**: confirmed `connected-frontend`'s actual deployed CSP
  (`nginx.conf`) includes `script-src 'unsafe-inline'` (a deliberate, documented
  trade-off for the single-file-SPA architecture) — meaning CSP provides no
  XSS backstop for that frontend; escaping discipline is the only real defense,
  which is why GAP-24 mattered. Verified empirically (two minimal test pages,
  each real policy) rather than assumed from reading the config alone.

## Secrets handling

- No hardcoded secrets/passwords found in backend source (`grep` for
  `SECRET_KEY=`/`JWT_SECRET=`/`password=` literals, excluding legitimate
  `settings.`/`os.environ`/Pydantic field references — zero matches).
- JWT verification pins `algorithms=[settings.JWT_ALG]` from server config, not
  from the token's own header — prevents algorithm-confusion attacks (Stage 2
  finding, `security.py:57`).
- `verify_code()` wraps passlib's `.verify()` in `except Exception: return False`
  — correct fail-closed pattern for hash verification, not a defect (initially
  flagged by static analysis, reviewed and confirmed safe).

## Fail-closed production config (`config.py::validate_for_production`)

Confirmed the checks that exist: `SECRET_KEY`/`JWT_SECRET` ≥32 chars and not a dev
prefix, `COOKIE_SECURE` must be true, `CORS_ALLOWED_ORIGINS` non-empty/no
wildcard/no localhost, `DATABASE_URL` must not be SQLite. All fail closed (refuse to
start) per `main.py`'s `lifespan()`.

**Gap noted, not a new defect**: this check does **not** validate `COOKIE_SAMESITE`'s
value. `.claude/rules/architecture.md` documents `SameSite=None` as load-bearing for
the cross-origin Planning Workspace handoff cookie fallback, and explicitly warns
against "tightening" it without re-verifying that flow. A future config-drift
incident (someone sets `COOKIE_SAMESITE=strict` in production) would silently break
that one fallback path rather than fail closed at startup. Not fixed this pass —
worth a deliberate decision (add a check that only validates the value *when* the
cross-origin handoff feature is actually in use) rather than a reflexive addition
here; documented for Stage 13 prioritisation.

## Role/scope/tenancy

Full writeup in `final_role_and_scope_matrix.md` (Stage 4) — 31 pre-existing +
6 new live cross-Wing tests, all passing; no defects found.

## Rate limiting

Confirmed present and functioning: `security_scope_test.py`'s repeated-bad-login
test tripped 429 as expected. Login has its own DB-backed per-IP + per-account
limiter (`security.py`); all other `/api/` routes share a separate per-IP sliding
window (`api_rate_limit` middleware, `main.py`), with OPTIONS/health/login
correctly exempted from the general limiter to avoid double-counting (a real fix
already recorded in this file's own comments, not new this pass).

## Not yet done in this pass (remaining Stage 9 work)

- Full OWASP Top 10 structured pass using the `security-guidance` skill (only an
  ad hoc subset covered so far: injection, XSS, secrets, fail-closed config).
- `42crunch-api-security-testing` live OpenAPI/BOLA/BFLA conformance scan against
  staging — not yet dispatched.
- Privacy/PII handling review (Part 23 of the original instruction) — not started.
- CORS preflight behavior and header allowlist verified only by reading config,
  not by a live cross-origin request test.
