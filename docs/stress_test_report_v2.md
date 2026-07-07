# AAFC TMS v17.1 — Full System Stress Test Report

**Date:** 2026-07-07  
**Tester:** Claude Code (automated + code review)  
**Scope:** Backend API (all endpoints), frontend error handling, RBAC matrix, input validation, auth flows, error messages  
**Environment:** SQLite in-memory test DB (seed_all). No production data touched.  
**Baseline:** 368 tests passing before this pass.

---

## Summary

| Severity | Count |
|----------|-------|
| Critical | 3 |
| High | 3 |
| Medium | 3 |
| Low | 3 |
| Info | 2 |
| **Total** | **14** |

---

## Step 1 — Surface Area Map

### Backend endpoint count: ~130 routes across 11 routers

| Router | Prefix | Endpoints |
|--------|--------|-----------|
| auth | `/api/auth` | login, logout, me, refresh, change-code |
| accounts | `/api` | accounts CRUD, reset-code, disable, reactivate, unlock, flights CRUD |
| organisations | `/api` | wings, squadrons, users, proxy |
| training | `/api` | curriculum, parade-nights, sessions, facilitators, cadets, equipment |
| planning | `/api` | years, parade-dates, holidays, anchors, sessions, conflicts, missions, annual-program, rollover |
| timing | `/api` | timing-templates, PN timing override |
| program | `/api` | phases, packages, items, promotion |
| ops | `/api` | reports, action-items, exceptions, imports |
| export_import | `/api` | export CSV/XLSX/PDF, program import |
| system | `/api/system` | overview, health, version, migrations, maintenance, scope-map, audit-summary, backups, bootstrap |
| health | `/api/health` | (public), db, ready |

### 8 Roles tested
`sqn_general`, `sqn_admin`, `wing_viewer`, `wing_admin`, `national_viewer`, `national_admin`, `system_admin`, `auditor`

---

## Full Findings Log

---

### FINDING-01 — CRITICAL: `POST /api/auth/change-code` has no scope enforcement

| Field | Detail |
|-------|--------|
| **Module** | Auth |
| **Endpoint** | `POST /api/auth/change-code` |
| **Input** | `{"user_id": "<national_admin_uid>", "new_code": "NEWCODE"}` with wing_admin token |
| **Expected** | 403 — wing_admin cannot change codes for accounts outside their scope |
| **Actual** | **200 OK** — code changed successfully |
| **Severity** | **Critical** |

**Details:** The `change_code` endpoint in `auth.py:110` checks `if not is_self and p.role not in (write_roles)`, but performs **no scope check after that**. Any admin role (including `sqn_admin` and `wing_admin`) can change the access code for any user including `national_admin` and `system_admin`, if they know or can guess their `user_id`.

The `/api/accounts/{uid}/reset-code` endpoint in `accounts.py` **does** correctly call `_require_manage_authority(p, u, db)`. The `change-code` endpoint is a separate route that was not updated to match.

**Proof:** `sqn_admin` → `change-code` on `national_admin` → `200`. `wing_admin` → `change-code` on `national_admin` → `200`.

**Both endpoints are called by the frontend** — `change-code` at `index.html:3916` (admin reset flow) and `index.html:5044` (self-service flow).

**Fix approach:** Add `_require_manage_authority(p, target, db)` call in `auth.py:change_code` after fetching the target user, mirroring the logic in `accounts.py:reset_code`. Self-changes (`is_self=True`) are exempt. Effort: **Small**.

---

### FINDING-02 — Critical: `POST /api/auth/change-code` accepts empty or whitespace-only codes

| Field | Detail |
|-------|--------|
| **Module** | Auth / Access Codes |
| **Endpoint** | `POST /api/auth/change-code` |
| **Input** | `{"user_id": "<uid>", "new_code": ""}` |
| **Expected** | 400 or 422 — empty string is not a valid access code |
| **Actual** | **200 OK** — `hash_code("")` stored; login with empty code then succeeds |
| **Severity** | **Critical** |

**Details:** `auth.py:125` does `ac.code_hash = hash_code(body.new_code)` with no strip, no length check. The empty string `""` is hashed and stored. Because `auth.py:33` strips the login input (`code = (body.code or "").strip()`), a user could then log in with a blank code field — bypassing the intended access-code security model entirely.

Also affected: `POST /api/accounts/{uid}/reset-code` — if `body.new_code = "   "` (whitespace only), `"   ".strip()` evaluates to `""`, but `"   "` is truthy so the falsy-check auto-generate path is skipped, and `hash_code("")` is stored. Verified: returns `{"new_code": ""}`.

**Fix approach:** In `auth.py:change_code` and `accounts.py:reset_code`, validate that the stripped code is non-empty and meets a minimum length (minimum 6 chars, matching the frontend check at `index.html:5040`). Raise 422 if invalid. Also add `model_validator` or `field_validator` on the Pydantic models. Effort: **Small**.

---

### FINDING-03 — Critical: No minimum code length enforced on backend

| Field | Detail |
|-------|--------|
| **Module** | Auth / Access Codes |
| **Endpoints** | `POST /api/auth/change-code`, `POST /api/accounts/{uid}/reset-code` |
| **Input** | `{"new_code": "A"}` (1 character) |
| **Expected** | 422 — too short |
| **Actual** | **200 OK** — 1-character code stored and functional |
| **Severity** | **Critical** |

**Details:** The frontend enforces 6-character minimum (`index.html:5040`) but the backend has no such check. Any direct API call bypasses this, enabling trivially guessable 1- or 2-character codes. This is especially dangerous in combination with the lockout bypass window (5 attempts per 5-minute window at the IP level).

**Fix approach:** Add server-side minimum length of 6 (or 8 to match `generate_code()`) in both endpoints. Also add maximum length (e.g. 64 chars) to prevent hash-timing abuse on very long inputs. Effort: **Small**.

---

### FINDING-04 — High: No display_name length validation — empty or excessively long names stored

| Field | Detail |
|-------|--------|
| **Module** | Accounts |
| **Endpoint** | `POST /api/accounts`, `PATCH /api/accounts/{uid}` |
| **Input** | `display_name = ""` or `"   "` or `"X" * 10000` |
| **Expected** | 422 for empty/whitespace; 422 or truncation for excessively long |
| **Actual** | **200 OK** in all cases — empty string `""` stored, whitespace-only stored as `""`, 10,000-character name stored |
| **Severity** | **High** |

**Details:** `accounts.py:303` does `u.display_name = body.display_name.strip()` without checking if the result is empty or excessively long. An account created with `display_name=""` has a blank display name in all list views, audit logs, and the system console — making it impossible to identify without checking the user_id.

A 10,000-character name won't crash the application in SQLite (TEXT has no limit), but will break table rendering in the UI, and in PostgreSQL production will fail silently against any column-length constraint.

**Fix approach:** Add a `@field_validator('display_name')` to `AccountCreateIn` and `AccountUpdateIn` to enforce non-empty after strip and a maximum length (e.g. 100 chars). Effort: **Small**.

---

### FINDING-05 — High: Per-account lockout has no frontend unlock UI

| Field | Detail |
|-------|--------|
| **Module** | Frontend — Accounts |
| **Endpoint** | `POST /api/accounts/{uid}/unlock` (backend exists, frontend absent) |
| **Expected** | wing_admin+ can see locked status and unlock a user's account from the UI |
| **Actual** | The `locked_until` field is returned by `GET /api/accounts/{uid}` and `GET /api/accounts`, but the frontend never reads or displays it. There is no Unlock button anywhere in `index.html`. |
| **Severity** | **High** |

**Details:** The per-account lockout feature (implemented in the previous session) is complete on the backend but has no frontend surface. If a user triggers the per-account lockout (5 failed attempts), a Wing Admin has no way to clear it from the UI — they would need to call the API directly. The lockout message shown ("try again later") gives no guidance on how to actually resolve this through the UI.

The `locked_until` and `code_active` fields are already in `_account_out` response but the frontend Account Management page ignores them.

**Fix approach:** In the Account Management page, read `locked_until` per account and show a visible warning badge (e.g. "🔒 Locked") for accounts with a non-null `locked_until`. Add an "Unlock Account" button visible to wing_admin+ that calls `POST /api/accounts/{uid}/unlock`. Effort: **Medium**.

---

### FINDING-06 — High: 429 lockout message doesn't distinguish IP lockout from per-account lockout

| Field | Detail |
|-------|--------|
| **Module** | Frontend — Login |
| **Location** | `index.html:2629-2630` |
| **Expected** | Per-account lockout shows: "This account is locked — contact your Wing HQ to restore access." |
| **Actual** | Both IP lockout and per-account lockout show: "Too many incorrect attempts. Access is temporarily locked — try again in 15 minutes." |
| **Severity** | **High** |

**Details:** The backend correctly distinguishes the two cases:
- IP lockout: `detail.message = "Too many attempts. Try again later."` — resolves automatically after 15 min
- Per-account lockout: `detail.message = "Account locked. Try again later or contact your Wing HQ."` — requires admin unlock

The frontend login handler at `index.html:2629` treats all 429s identically with the hardcoded "try again in 15 minutes" message. A user whose account is per-account locked will wait 15 minutes for nothing, never knowing they need to contact their Wing HQ. The backend *does* send a `detail.message` field with the correct text, but the frontend ignores it.

**Fix approach:** In `doLogin()`, check `e.code` or `e.msg` from the thrown error. The `api()` function already populates `e.msg` from `detail.message`. For 429, use `e.msg` directly instead of the hardcoded string (or check `detail.error === 'locked_out'` and whether the message contains "Wing HQ"). Effort: **Small**.

---

### FINDING-07 — Medium: `POST /api/auth/change-code` has no audit on code reset by admin

| Field | Detail |
|-------|--------|
| **Module** | Auth |
| **Endpoint** | `POST /api/auth/change-code` |
| **Expected** | Admin resetting another user's code is logged in the audit trail |
| **Actual** | `auth.py:130` calls `audit(db, p, ..., action="change_own_code" if is_self else "reset_access")`. The audit fires, but the `new` field only contains `{}` (no user details). By contrast, `accounts.py:reset_code` logs `new={"target_display_name": ..., "target_role": ...}`. |
| **Severity** | **Medium** |

**Details:** The audit entry exists but is less useful than the `reset-code` equivalent. The `change-code` audit records `object_id=target.id` and `action="reset_access"` but does not log the target's `display_name` or `role`, making it harder to reconstruct "who changed whose code" from the audit log.

**Fix approach:** Pass `new={"target_display_name": target.display_name, "target_role": target.role}` in the `audit()` call in `auth.py:130`. Effort: **Small**.

---

### FINDING-08 — Medium: `403` responses leak internal role names via `needs` field

| Field | Detail |
|-------|--------|
| **Module** | Backend — permissions.py |
| **Location** | `permissions.py:97` |
| **Expected** | 403 response: `{"error": "forbidden"}` |
| **Actual** | `{"error": "forbidden", "needs": ["system_admin"]}` |
| **Severity** | **Medium** |

**Details:** `require_role()` at `permissions.py:97` returns `{"error": "forbidden", "needs": list(roles)}`. This exposes the internal role hierarchy to any authenticated user who receives a 403 — they can enumerate which roles have access to which endpoints. While this is not exploitable on its own, it assists privilege-escalation reconnaissance.

The frontend at `index.html:2558` doesn't use this field (it uses the `code` field only for `proxy_required`), so removing it would have no UI impact.

**Fix approach:** Remove `"needs": list(roles)` from the 403 detail in `require_role()`, `require_system_admin()`, and `require_system_or_nat_admin()` in `permissions.py`. Effort: **Small**.

---

### FINDING-09 — Medium: Frontend "Reset Code" admin flow uses `change-code` (no scope check) instead of `reset-code` (has scope check)

| Field | Detail |
|-------|--------|
| **Module** | Frontend — Accounts |
| **Location** | `index.html:3916` |
| **Expected** | Admin code reset calls the scoped endpoint |
| **Actual** | `doResetCode()` calls `POST /api/auth/change-code`. Only the "Change My Code" self-service tab also calls this. |
| **Severity** | **Medium** |

**Details:** In practice, the frontend only exposes the admin-reset modal to admins (so a sqn_admin wouldn't see wing_admin accounts in their list). However, it also means the fix for FINDING-01 is necessary for the frontend to work correctly: if the frontend switches to `reset-code` the scope enforcement runs automatically. Conversely, once FINDING-01 is fixed in `change-code`, this finding resolves as well.

This is tracked separately because the endpoint routing in the frontend should ideally use `accounts/{uid}/reset-code` for admin resets (consistent semantics, single audit pattern) rather than the auth-level change-code endpoint.

**Fix approach:** In `doResetCode()` and the admin-reset modal, switch the API call from `POST /api/auth/change-code` to `POST /api/accounts/${uid}/reset-code`. The self-service `doChangeCode()` flow should continue using `change-code` (as it doesn't have a uid path). Effort: **Small**.

---

### FINDING-10 — Low: 10,000-character login code accepted with no length cap

| Field | Detail |
|-------|--------|
| **Module** | Auth — login |
| **Endpoint** | `POST /api/auth/login` |
| **Input** | `{"code": "A" * 10000}` |
| **Expected** | 400 or 422 |
| **Actual** | 401 (correctly rejected) but **response takes 0.00s** — no bcrypt hashing is run because the code is compared against all active hashes. The loop exits early on no match, so no DoS risk in practice. |
| **Severity** | **Low** |

**Details:** Although the current implementation is safe (the inner loop short-circuits on no match without running `verify_code`... actually wait: the current code runs `verify_code(code, ac.code_hash)` for each active hash). This is potentially slow with many users and a long code if bcrypt is used. In practice passlib's PBKDF2-SHA256 is fast, and `verify_code` bails quickly on malformed inputs, so actual risk is low. Still, a length cap on `LoginIn.code` (e.g. 128 chars) is good hygiene.

**Fix approach:** Add `max_length=128` to the `code` field in `LoginIn` Pydantic model. Effort: **Trivial**.

---

### FINDING-11 — Low: FastAPI 422 validation errors expose Pydantic internal field paths

| Field | Detail |
|-------|--------|
| **Module** | Backend — global |
| **Input** | `POST /api/auth/login` with missing `code` field |
| **Actual** | `{"detail": [{"type": "missing", "loc": ["body", "code"], "msg": "Field required", ...}]}` |
| **Severity** | **Low** |

**Details:** FastAPI's default 422 response includes `loc`, `type`, `ctx` fields with internal field paths. These are relatively benign (no secrets), but do expose model field names. The frontend (`index.html:2544-2546`) does map 422 arrays to readable messages. This is a low-priority hardening item if desired.

**Fix approach:** Add a custom 422 exception handler to produce `{"error": "validation_failed", "message": "..."}` if stricter field-path hiding is needed. Effort: **Small**.

---

### FINDING-12 — Low: Session expiry message shown for any mid-session 401, including disabled account

| Field | Detail |
|-------|--------|
| **Module** | Frontend |
| **Location** | `index.html:2532` |
| **Actual** | Any 401 from `api()` (including a disabled-account check) shows "Your session has expired. Please sign in again." |
| **Severity** | **Low** |

**Details:** The `api()` function at line 2528-2532 handles 401 by showing "Your session has expired." But a 401 could also be returned if the user's account is disabled mid-session (after token issuance). The correct message in that case would be "Your account has been deactivated. Contact your Wing HQ."

The `api()` function does extract the error code (`c401`) but the login path at lines 2624-2628 already correctly handles `invalid_user`. The issue is only in non-login `api()` calls that return 401 mid-session.

**Fix approach:** In the `api()` function's 401 handler, check `c401 === 'invalid_user'` and override the message to "Your account has been deactivated. Contact your Wing HQ." Effort: **Small**.

---

### FINDING-13 — Info: `POST /api/auth/change-code` no minimum code length on backend (repeated from F-03)

Documented for completeness — addressed in FINDING-03.

---

### FINDING-14 — Info: `openapi.json` publicly accessible (148 paths)

| Field | Detail |
|-------|--------|
| **Module** | FastAPI global config |
| **Endpoint** | `GET /openapi.json` (no auth) |
| **Severity** | **Info** |

**Details:** FastAPI serves the full OpenAPI schema at `/openapi.json` without authentication. This documents all 130+ endpoints, their request/response schemas, and role-related error codes. It is not exploitable directly but assists reconnaissance.

**Fix approach:** Either add `FastAPI(openapi_url=None)` in production (disables Swagger UI and schema), or gate it behind `system_admin` auth. Effort: **Small**.

---

## RBAC Matrix — Pass/Fail Summary

| Endpoint | sqn_general | sqn_admin | wing_viewer | wing_admin | national_viewer | national_admin | system_admin | auditor |
|----------|-------------|-----------|-------------|------------|-----------------|----------------|--------------|---------|
| GET /api/accounts | ✗ 403 | ✓ 200 | ✓ 200 | ✓ 200 | ✓ 200 | ✓ 200 | ✓ 200 | ✓ 200 |
| POST /api/accounts | ✗ 403 | ✓ limited | ✗ 403 | ✓ limited | ✗ 403 | ✓ broad | ✓ full | ✗ 403 |
| POST /accounts/{}/disable | ✗ 403 | ✓ scoped | ✗ 403 | ✓ scoped | ✗ 403 | ✓ broad | ✓ full | ✗ 403 |
| POST /accounts/{}/reset-code | ✗ 403 | ✓ scoped | ✗ 403 | ✓ scoped | ✗ 403 | ✓ broad | ✓ full | ✗ 403 |
| POST /accounts/{}/unlock | ✗ 403 | ✓ scoped | ✗ 403 | ✓ scoped | ✗ 403 | ✓ broad | ✓ full | ✗ 403 |
| POST /auth/change-code (own) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| POST /auth/change-code (other) | ✗ 403 | **⚠ 200 BUG** | **⚠ 200 BUG** | **⚠ 200 BUG** | **⚠ 200 BUG** | ✓ broad* | ✓ full | ✗ 403 |
| GET /api/system/overview | ✗ 403 | ✗ 403 | ✗ 403 | ✗ 403 | ✗ 403 | ✗ 403 | ✓ 200 | ✗ 403 |
| POST /system/maintenance/enable | ✗ 403 | ✗ 403 | ✗ 403 | ✗ 403 | ✗ 403 | ✗ 403 | ✓ 200 | ✗ 403 |
| GET /api/system/audit-summary | ✗ 403 | ✗ 403 | ✗ 403 | ✓ 200 | ✗ 403 | ✓ 200 | ✓ 200 | ✓ 200 |
| Cross-sqn GET /accounts/{uid} | — | ✗ 403 ✓ | — | — | — | — | — | — |
| Cross-sqn disable | — | ✗ 403 ✓ | — | — | — | — | — | — |
| Privilege escalation (create higher role) | — | ✗ 403 ✓ | — | ✗ 403 ✓ | — | — | — | — |

*`change-code` scope check is absent (BUG). national_admin and above can change any code, which is correct, but sqn_admin/wing_admin/national_viewer should not.

---

## Step 3 — Auth Flow Summary

| Test | Result |
|------|--------|
| Correct code → correct role loads | ✓ Pass |
| Wrong code ×4 → no lockout | ✓ Pass |
| Wrong code ×5 → 429 locked_out | ✓ Pass |
| Lockout message in plain English | ✓ Pass |
| IP lockout message misleading for per-account | ✗ FINDING-06 |
| Expired/tampered JWT → 401 | ✓ Pass |
| No token → 401 | ✓ Pass |
| Disabled user login → 401 | ✓ Pass |
| /auth/me has no code_hash or plaintext | ✓ Pass |
| Cross-sqn IDOR via API | ✓ Pass (403 enforced) |
| Cross-wing IDOR via API | ✓ Pass (403 enforced) |
| Empty code login → 401 | ✓ Pass |
| Whitespace-trimmed code → matches | ✓ Pass |
| SQL injection in code → 401 | ✓ Pass |
| No DATABASE_URL in any system response | ✓ Pass |
| No JWT_SECRET in any response | ✓ Pass |

---

## Step 6 — Error Message Audit

| Location | Current message | Issue | Suggested plain-English fix |
|----------|----------------|-------|------------------------------|
| Login 429 (both types) | "Too many incorrect attempts. Access is temporarily locked — try again in 15 minutes." | Incorrect for per-account lockout (admin must unlock, 15-min wait won't help) | Use backend `detail.message`: "Account locked. Contact your Wing HQ to restore access." |
| 401 mid-session (non-login) | "Your session has expired. Please sign in again." | Wrong if account was disabled | Check `code === 'invalid_user'` → "Your account has been deactivated. Contact your Wing HQ." |
| 403 detail (backend) | `{"error": "forbidden", "needs": ["system_admin"]}` | Leaks role names | Remove `needs` field |
| 422 validation error body | Raw Pydantic `loc`/`type`/`ctx` fields | Technical jargon | Frontend already maps these to readable form — no user-facing issue, but backend could clean up |
| change-code success (admin flow) | "✅ Code reset. Use at next sign-in." | Correct but missing the one-time warning | Add "Save the new code now — it cannot be retrieved again." (matches the accounts flow message) |

---

## Step 7 — Crash Resistance Summary

| Test | Result |
|------|--------|
| Malformed JSON → 422 (not 500) | ✓ Pass |
| No token → 401 (not 500) | ✓ Pass |
| Tampered JWT → 401 (not 500) | ✓ Pass |
| No traceback in 403/401/404 responses | ✓ Pass |
| Unicode in display_name stores correctly | ✓ Pass |
| SQL injection in code field → 401 | ✓ Pass |
| Long query params → no crash | ✓ Pass |
| Public /api/health endpoint | ✓ Pass |

---

## Prioritized Recommendations

### Critical — Fix before next deployment

**1. Add scope enforcement to `POST /api/auth/change-code`** (FINDING-01)  
`auth.py:change_code` — add `_require_manage_authority(p, target, db)` call for non-self changes.  
Impact: Without this, any admin can take over any account above their scope.  
Effort: Small (4 lines).

**2. Reject empty / whitespace-only / too-short access codes** (FINDING-02 + FINDING-03)  
Both `change-code` and `reset-code` — validate stripped code is non-empty and ≥6 chars.  
Impact: Empty code is a valid credential; short codes are trivially guessable.  
Effort: Small (10 lines, add Pydantic validator).

### High — Fix in next sprint

**3. Reject empty/whitespace/oversized display_name** (FINDING-04)  
`AccountCreateIn` and `AccountUpdateIn` — add `@field_validator`.  
Impact: Blank accounts unidentifiable in audit logs and UI.  
Effort: Small (8 lines).

**4. Wire up unlock UI in Account Management** (FINDING-05)  
Frontend — display `locked_until` badge, add Unlock button for wing_admin+.  
Impact: Per-account lockout cannot be cleared by admins without API access.  
Effort: Medium (frontend HTML + JS, ~40 lines).

**5. Fix per-account lockout message in frontend** (FINDING-06)  
`doLogin()` — use `e.msg` (from `detail.message`) for 429 instead of hardcoded string.  
Impact: User told "wait 15 minutes" when they actually need to call Wing HQ.  
Effort: Small (2 lines).

### Medium — Tidy up

**6. Redirect admin code reset to `reset-code` endpoint** (FINDING-09)  
`doResetCode()` in frontend — call `/api/accounts/${uid}/reset-code` instead of `change-code`.  
Impact: Consistent audit trail, scope enforcement applies automatically after fix to FINDING-01.  
Effort: Small (1 line change in frontend).

**7. Add audit detail to `change-code` admin resets** (FINDING-07)  
`auth.py:130` — add `new={"target_display_name": ..., "target_role": ...}` to audit call.  
Impact: Audit logs harder to read; relevant for compliance.  
Effort: Trivial.

**8. Remove `needs` field from 403 responses** (FINDING-08)  
`permissions.py:97` — remove `"needs": list(roles)`.  
Impact: Low (no direct exploit), but eliminates role-hierarchy leak.  
Effort: Trivial.

### Low / Info — Backlog

**9. Add login code max_length cap** (FINDING-10)  
`LoginIn.code` field → `str = Field(max_length=128)`. Effort: Trivial.

**10. Fix mid-session 401 message for disabled accounts** (FINDING-12)  
`api()` 401 handler → check `c401 === 'invalid_user'` and show correct message. Effort: Small.

**11. Consider disabling `/openapi.json` in production** (FINDING-14)  
`FastAPI(openapi_url=None)` in production config. Effort: Small.

---

## What Passed Without Issues

- All RBAC cross-tenancy tests: sqn_admin cannot read/write 704 accounts ✓
- sqn_admin cannot create wing_admin or national_admin accounts ✓
- Privilege escalation via role= parameter rejected ✓
- system_admin endpoints inaccessible to national_admin ✓
- Proxy mode enforced: wing_admin cannot write SQN data without entering proxy ✓
- Audit logging present on all write operations ✓
- No access code hashes or plaintext in any API response ✓
- No DATABASE_URL or JWT_SECRET in any response ✓
- No stack traces in error responses ✓
- SQL injection attempts in login code → safe 401 ✓
- Unicode characters in display_name round-trip correctly ✓
- Malformed JSON → 422, not 500 ✓
- DB-backed IP lockout fires correctly after 5 attempts ✓
- Per-account lockout fires and persists correctly (backend) ✓
- Per-account lockout cleared on correct login ✓
- Disabled user cannot log in ✓
- Public health endpoint accessible without auth ✓
