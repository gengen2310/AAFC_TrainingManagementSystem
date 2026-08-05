# Security Rules — AAFC TMS

## Access codes

- Never return plaintext access codes from any API endpoint
- Never return access-code hashes from any API endpoint
- Never embed seeded access codes in frontend JavaScript
- Never store access codes in localStorage or sessionStorage
- Access code reset: one-time display only; never re-show existing code

## Secrets

- Never log JWT secrets, database credentials, or environment secrets
- Never return JWT secret or database URL from any API endpoint
- Never include secrets in frontend JS, docs, or ZIP output
- Demo seed codes may appear in local pilot guide only (clearly marked)

## Role and scope

- All endpoints must check role and scope server-side
- Never rely on "if not denied then allowed" logic
- system_admin is the highest role; even system_admin must go through explicit permission checks
- system_admin actions must be audited with object_type, action, and timestamp
- Cross-scope access must return 403, not leak data from the wrong scope

## Frontend

- Never use innerHTML with unsanitised user-controlled content — use esc() helper
- Never expose API errors with full stack traces
- No operational data in localStorage (auth cookies only, set server-side)
- CSP headers are set by the backend middleware

## Audit log

- AuditLog is immutable — no delete or update endpoints
- Do not filter audit logs in a way that hides privileged actions
- Backup operations, maintenance mode changes, and role changes must be audited

## Security greps before packaging

**Use `-E` (extended regex) on every one of these — without it, `|` is a literal
pipe character, not alternation, and the whole check silently passes even when
a real match exists.** Confirmed live: the pre-`-E` versions of these exact
commands returned "0 matches, PASS" during a 2026-08-05 production release
while `grep -c -E` on the same files found 2 real matches (both later confirmed
benign — an audit-log filter option and a `pg_restore` example command, not
actual secrets/codes — but the check itself had been giving false negatives).

```bash
# Removed wording check
grep -Rc -E "your unit only|Controlled access for training" connected-frontend backend

# Access code exposure
grep -Rc -E "View current code|Show access code|Reveal code|Display existing code" connected-frontend backend

# Seeded codes in frontend
grep -Rc -E "ADMIN703|ADMIN7WG|ADMINNATIONAL|SYSADMIN2026|plain_code|code_hash|access_code|localStorage" connected-frontend

# Secrets in frontend
grep -Rc -E "JWT_SECRET|SECRET_KEY|DATABASE_URL" connected-frontend
```

All must return 0 matches -- or, if a match is found, it must be manually reviewed
and confirmed as a false positive (e.g. an audit-action-type label, a help-text
placeholder) before packaging, never assumed safe from the count alone.
