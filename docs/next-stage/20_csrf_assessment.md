# AAFC TMS — CSRF Mitigation Assessment

**Audience:** System Administrator, Security Reviewer
**Gap register:** Gap #20 (CSRF controls)
**Last updated:** 2026-08-12

---

## Summary

AAFC TMS uses the **CORS + SameSite Cookie** CSRF mitigation model, backed by the system's
primary session mechanism (Bearer token in `sessionStorage`). CSRF tokens are not implemented
and are not required given the current architecture. This document records the assessment and
required verification.

---

## Architecture Facts

### Primary session mechanism — Bearer token

The Planning Workspace (`frontend/`) stores its JWT in `sessionStorage` and attaches it as
`Authorization: Bearer <token>` on every API request (`frontend/src/api/client.ts`). The
backend's `dependencies.py:_token_from_request()` checks the `Authorization` header first and
falls back to the cookie only if no header is present.

**CSRF implication:** A cross-origin form, iframe, or scripted request cannot set the
`Authorization` header. Any forged request that relies on tricking the browser into making a
request (the standard CSRF model) will not carry the token and will be rejected with 401.
This covers the Planning Workspace entirely.

### Cookie fallback — SameSite=None; Secure

The legacy Main TMS (`connected-frontend/`) has no `sessionStorage` token. It relies on the
browser automatically sending the `aafc_session` cookie (set by `auth.py:140/207`) on every
request to the backend.

The cookie is set with:
- `httponly=True` — not readable by JavaScript
- `secure=settings.COOKIE_SECURE` — HTTPS only in production
- `samesite=settings.COOKIE_SAMESITE` — configurable; **must be `none` in production**

**Why SameSite=None is required:** `up.railway.app` is on the public suffix list. Each
Railway subdomain (`aafc-tms-frontend-*.up.railway.app`, `aafc-tms-backend-*.up.railway.app`,
`aafc-tms-planning-workspace-preview-*.up.railway.app`) is a distinct "site" to the browser.
Cross-site cookies require `SameSite=None; Secure` to be sent at all. Without this, the
cross-origin tab handoff (Main TMS → Planning Workspace) fails entirely. This is confirmed and
documented in `docs/beta/11_defect_register.md:DEFECT-004`.

**CSRF implication of SameSite=None:** With `SameSite=None`, the cookie IS sent on cross-site
requests, which means the cookie-based session IS theoretically CSRF-vulnerable.

---

## CSRF Mitigation Model

### Layer 1 — CORS lockdown

`main.py:69` registers `CORSMiddleware` with `allow_origins=settings.cors_origins`. This is
set per environment from the `CORS_ALLOWED_ORIGINS` Railway environment variable — never a
wildcard. In production, only the two frontend Railway origins are allowed.

CORS preflight blocks cross-origin requests from unknown origins at the network layer before
they reach any application logic. This eliminates CSRF from any origin not in the allowlist.

### Layer 2 — SameSite=None is load-bearing for legitimate cross-site, not an opening

The only legitimate cross-site cookie consumer is the Planning Workspace handoff from the Main
TMS. Both are in the CORS allowlist. An attacker's origin would be blocked by CORS (Layer 1)
before the cookie could carry any authority.

### Why CSRF tokens are not required

1. The Planning Workspace uses Bearer tokens — immune to CSRF by construction.
2. The Main TMS cookie is `HttpOnly` — cannot be read or manipulated by scripts.
3. CORS lockdown blocks all cross-origin requests from unauthorised origins, including forged
   form submissions (browsers send CORS preflight for non-simple requests; simple form POSTs
   with non-JSON content types are not what the API accepts — all API endpoints expect
   `Content-Type: application/json`).
4. `Content-Type: application/json` is not a "simple" request content type, so browsers will
   always send a preflight for API calls, and CORS will block the preflight from unknown
   origins.

The incremental security benefit of adding CSRF tokens is minimal given the above, and the
implementation complexity (synchronising tokens across two frontends that have different session
mechanisms) is non-trivial.

---

## Required Verification Before V1 Deployment

The code default for `COOKIE_SAMESITE` is `"lax"` (`config.py:50`). Production MUST have the
Railway environment variable `COOKIE_SAMESITE=none` set, or the Planning Workspace cross-origin
cookie handoff will fail.

**Verification checklist (operator must confirm):**

| # | Item | How to verify |
|---|---|---|
| 1 | `COOKIE_SAMESITE=none` is set in Railway production environment | Railway dashboard → `aafc-tms-backend` production service → Variables → confirm `COOKIE_SAMESITE=none` |
| 2 | `COOKIE_SECURE=true` is set in Railway production environment | Same location — confirms cookies are HTTPS-only |
| 3 | `CORS_ALLOWED_ORIGINS` does not contain a wildcard | Same location — must list specific frontend domains only |
| 4 | Login from Main TMS → open Planning Workspace in new tab → confirm session is active | Manual browser test: logged-in user clicks "Planning Workspace" link, Planning Workspace loads authenticated |

Items 1–3 must not be performed by Claude Code — they involve reading production credentials.
Perform these as a pre-deployment operator checklist step.

---

## Risk Acceptance

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| CSRF via cookie on non-JSON endpoint | Low — no non-JSON mutating endpoints exist | Medium | CORS blocks all cross-origin preflights from unknown origins; all mutating endpoints expect `application/json` |
| Targeted attack from allowlisted origin (e.g., XSS in Main TMS) | Low — `esc()` is consistently used in connected-frontend for user content | High | Defence-in-depth: XSS prevention is the primary control |
| `SameSite=None` accidentally set in development | Low — code default is `lax`; `none` is only in production env var | Low | Each environment has its own `COOKIE_SAMESITE` variable |

**Residual CSRF risk: LOW.** Accepted for 7WG Operational V1 with the verification checklist
completed.

---

## Decision Record

| Field | Value |
|---|---|
| Decision | CORS + SameSite=None is the CSRF mitigation; CSRF tokens not required |
| Date | 2026-08-12 |
| Precondition | `COOKIE_SAMESITE=none` and `COOKIE_SECURE=true` confirmed in Railway production vars |
| Review trigger | If a non-JSON mutating endpoint is added, or if CORS origins are relaxed |
