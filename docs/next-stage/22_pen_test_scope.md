# AAFC TMS — External Penetration Test Scope of Work

**Gap register:** Gap #22 (External penetration testing)
**Prepared:** 2026-08-12
**Status:** SCOPE READY — requires organisational budget and vendor approval before execution
**Release gate:** Level B (second Wing pilot) — strongly recommended. Level C (National) — required.

---

## Purpose

This document defines the scope of work for an independent external penetration test of the
AAFC Training Management System. It is written to be handed directly to a qualified security
vendor as the Statement of Work (SOW) / scoping document.

The test must be performed by a party with no prior access to the AAFC TMS codebase. An
independent test validates controls that internal testing cannot — including business-logic
bypasses, chained vulnerabilities, and attack paths not anticipated by the development team.

---

## System Description

| Component | Technology | URL (staging) |
|---|---|---|
| Legacy TMS frontend | Single-file SPA (HTML/CSS/JS, nginx) | `https://aafc-tms-frontend-staging.up.railway.app` |
| Planning Workspace | React 18 + Vite, served by nginx | `https://aafc-tms-planning-workspace-preview-staging.up.railway.app` |
| API backend | FastAPI (Python 3.13), gunicorn | `https://aafc-tms-backend-staging.up.railway.app` |
| Database | PostgreSQL 16 (Railway managed) | Internal to Railway — not directly reachable from public internet |
| Session mechanism | `Authorization: Bearer <JWT HS256>` (primary); `aafc_session` cookie (`HttpOnly; SameSite=None; Secure`) as fallback for cross-origin tab handoff |
| Auth model | Shared access codes per role per unit (no email/password); codes are hashed (pbkdf2_sha256) and never returned from the API |

**Authentication roles (ascending privilege):**
1. `sqn_general` — read-only, squadron scope
2. `sqn_admin` — read/write, squadron scope
3. `wing_viewer` — read-only, wing scope
4. `wing_admin` — read/write, wing scope; can proxy-write to child squadrons
5. `national_admin` — read/write, national scope; cross-wing visibility
6. `auditor` — read-only audit log; all wings
7. `system_admin` — highest privilege; system configuration, account management, maintenance

---

## Test Environment

**Target: STAGING ONLY. Production must never be targeted.**

The staging environment (`*-staging.up.railway.app`) contains synthetic data only — no real
cadet names, no real operational records. It is structurally identical to production (same
codebase, same Railway deployment, same migration state).

The test vendor will be provided:
- One access code per role (7 codes total, all staging synthetic)
- The Railway staging frontend URL
- The Railway staging backend API URL
- The API OpenAPI specification (`GET /api/docs` on staging)
- This scoping document

The vendor must not attempt to reach production. The Railway production URLs differ only
in the `-staging` segment — this distinction must be respected at all times.

---

## In Scope

### Authentication and Access Control

| Area | Specific tests |
|---|---|
| Access code brute-force | Rate limiting effectiveness; lockout at 5 attempts per IP per 5 min; lockout bypass via IP rotation; lockout bypass via X-Forwarded-For spoofing |
| Access code enumeration | Whether API timing differences leak code format or length; whether error messages distinguish "wrong code" from "no such role" |
| JWT forgery | Unsigned tokens; algorithm confusion (none, HS256 with HMAC+RSA); expired tokens; tampered claims; `tv` (token_version) rollback |
| Role escalation | Horizontal: sqn_admin of 703 SQN accessing 704 SQN data. Vertical: sqn_admin calling system_admin endpoints. Wing: wing_admin of 7WG accessing 1WG data |
| Wing isolation (IDOR) | Every resource endpoint that accepts a `wing_id` or `squadron_id` param must be tested with an out-of-scope ID; expected: 403, not 200 or 404 |
| Proxy / Delegated Intervention bypass | wing_admin must enter Proxy Mode to write to squadron records; test whether write endpoints enforce this without the mode header |
| system_admin scope bar | system_admin can browse Wing/Squadron pages via scope selector; test whether browsing unlocks write operations without Delegated Intervention |

### Session Management

| Area | Specific tests |
|---|---|
| Session revocation | After code reset, does the old token produce 401 within one request? (token_version check) |
| Cross-origin session handoff | Planning Workspace receives the session cookie from Main TMS; test whether a cross-origin attacker can capture or re-use this cookie |
| Concurrent sessions | Two simultaneous sessions for the same role; revoke one; confirm the other is also revoked |
| Session fixation | Whether the session cookie can be pre-set by an attacker before login |

### CSRF

The architecture relies on CORS + Bearer token for CSRF protection. The test must verify:
- CORS preflight is enforced for all mutating endpoints from non-allowlisted origins
- `Content-Type: application/json` is enforced (rejects form-encoded CSRF)
- SameSite=None cookie cannot be used by an attacker origin (CORS blocks the preflight)
- Test with and without the `Authorization` header to confirm CORS enforcement

### Cross-Site Scripting (XSS)

**Session architecture note for the vendor:** The application uses `Authorization: Bearer <JWT>` stored in `sessionStorage` as the primary session mechanism. The HttpOnly `aafc_session` cookie is a cross-origin fallback only. **The primary XSS impact is theft of the Bearer token from `sessionStorage` (key: `aafc_token`)** — not the HttpOnly cookie. An attacker who retrieves this token can make fully authenticated API calls for the duration of the token's validity. Tests should specifically attempt to exfiltrate `sessionStorage.getItem('aafc_token')` rather than `document.cookie`.

| Area | Specific tests |
|---|---|
| Legacy TMS frontend | All user-controlled text rendered via `innerHTML` must use `esc()` — test all visible fields (facilitator names, squadron names, parade night notes, training session titles, notice content) |
| Planning Workspace (React) | React auto-escapes most content; focus on `dangerouslySetInnerHTML` if any, and user-controlled URLs in link elements |
| Stored XSS | Text stored in the database and re-rendered to other users (e.g. training notices visible to all sqn_general users) — primary goal: exfiltrate `sessionStorage` Bearer token |
| Reflected XSS | URL parameters rendered in error messages or page state |

### Import Abuse

| Area | Specific tests |
|---|---|
| CSV imports | Oversized files; CSV injection (leading `=`, `@`, `+`, `-`); non-UTF-8 encoding; malformed rows; quoting attacks |
| Calendar import (ICS) | Malformed ICS; calendar injection via SUMMARY/DESCRIPTION fields; iCal injection; XXE (if ICS is parsed via XML) |
| Export endpoints | Path traversal in filename params; ZIP slip if exports are zipped |

### Audit Log Integrity

| Area | Specific tests |
|---|---|
| Immutability | Attempt to POST/PATCH/DELETE to `/api/audit`; expected: 405 or 403 |
| Completeness | Perform a privileged action (e.g. account creation); confirm audit log entry appears |
| Scope isolation | Access audit log as `sqn_admin`; confirm only squadron-scoped entries are returned |
| Injection | Attempt to inject SQL or special characters into audit-logged fields; confirm log entry is clean |

### Infrastructure

| Area | Specific tests |
|---|---|
| API information exposure | `/api/docs` (Swagger UI), `/api/redoc`, and `/api/openapi.json` should not expose system-admin or internal endpoints publicly; test all three paths in unauthenticated state |
| Error messages | Unhandled exceptions must return 500 without stack traces in production equivalents |
| HTTP headers | Presence of `Strict-Transport-Security`, `X-Frame-Options`/`frame-ancestors`, `X-Content-Type-Options`, `Content-Security-Policy`; absence of `Server` detail |
| Dependency scan | Known CVEs in Python packages (`requirements.txt`), npm packages (`package.json`); CVSS ≥ 7.0 must be reported |
| Rate limiting | Effectiveness of per-IP API rate limit. **Important for the vendor:** the general API limiter (`check_api_rate`) is per-worker in-memory; at the current default of 2 workers the effective limit is ~600 req/60 s. The login limiter (`IpLoginAttempt` DB-backed) is exact regardless of worker count — test these two limiters separately. Also verify that the IP source is extracted from Railway's trusted proxy header only, not from a client-supplied `X-Forwarded-For` (rotation bypass). |
| Maintenance mode bypass | Confirm write endpoints are blocked in maintenance mode; confirm login block (when enabled) is enforced |

---

## Out of Scope

- **Production environment** — staging only, no exceptions
- **Denial-of-service attacks** — do not attempt to exhaust Railway resources or trigger autoscaling charges
- **Social engineering** — phishing, pretexting, or contacting users directly
- **Physical access** — Railway data centre access is out of scope
- **Railway platform itself** — the Railway managed infrastructure is not the target; only the AAFC TMS application layer
- **Third-party services** — GitHub, Google, or any third party integrated with Railway
- **Password cracking** — access codes are hashed with pbkdf2_sha256 with a high work factor; offline cracking is not in scope
- **Self-XSS** — attacks that require the victim to execute something in their own console

---

## Test Methodology

**Engagement type:** Grey-box penetration test.

The vendor is provided working credentials for all 7 roles (staging only) and the API
specification. Source code is NOT provided — this preserves the independent security
assessment value while allowing efficient role-based testing.

**Suggested approach:**

1. Unauthenticated reconnaissance (API endpoints, headers, error messages)
2. Authentication testing (all 7 roles independently)
3. IDOR testing (systematically test all parameterized resource endpoints with
   out-of-scope IDs for each role)
4. Session and CSRF testing
5. XSS testing (both frontends)
6. Import/export abuse
7. Audit log integrity
8. Infrastructure and dependency scan

---

## Duration and Timeline

**Suggested engagement:** 5 business days (40 hours) for the application test + 1 day for
report writing and debrief.

| Day | Activity |
|---|---|
| 1 | Environment access verification; unauthenticated recon; auth/lockout tests |
| 2 | IDOR systematic testing (all parameterized endpoints × all roles) |
| 3 | Session, CSRF, XSS, import abuse |
| 4 | Audit log, infrastructure, dependency scan |
| 5 | Retesting of any findings from Days 1–4; edge cases |
| 6 | Report writing and preparation |
| 7 | Findings debrief with AAFC TMS system administrator |

---

## Report Requirements

The vendor must deliver:

1. **Executive summary** — risk posture narrative, 1–2 pages, suitable for non-technical
   leadership
2. **Findings register** — one finding per page:
   - Title and CVSS v3.1 base score
   - Affected component and URL
   - Description (what the vulnerability is)
   - Reproduction steps (exact HTTP request/response or browser steps)
   - Impact assessment (what an attacker could achieve)
   - Remediation recommendation (specific and actionable)
3. **Evidence** — screenshots, HTTP request/response captures for each finding
4. **Dependency scan** — full list of CVE findings from `requirements.txt` and `package.json`,
   with CVSS ≥ 7.0 highlighted
5. **Out-of-scope / not-tested** — explicit list of areas not tested and reason

**Severity classification:** Use CVSS v3.1 base score ranges:
- Critical: 9.0–10.0
- High: 7.0–8.9
- Medium: 4.0–6.9
- Low: 0.1–3.9
- Informational: 0.0

**Remediation timeline expectations:**
- Critical: patch within 48 hours of report delivery
- High: patch within 2 weeks
- Medium: patch before National rollout
- Low/Informational: at developer discretion

---

## Access Arrangements

Access codes for the staging environment will be provided by the AAFC TMS system administrator
to the vendor's lead tester via an end-to-end-encrypted channel (e.g. Signal or equivalent).

Codes must not be shared outside the pen test team and must be changed by the system
administrator immediately after the engagement concludes (via account management → generate
new access code).

The system administrator will provide:
- Staging frontend URL
- Staging backend API URL
- 7 access codes (one per role), valid for the duration of the engagement
- OpenAPI spec (`GET /api/docs`)
- Contact point for technical questions during the test

---

## Acceptance Criteria

The AAFC TMS is considered pen-test PASS for a given release level when:
- All Critical and High findings are remediated and re-tested
- All Medium findings are either remediated or have an accepted risk record signed by the
  organisational authority
- Low and Informational findings are reviewed and a remediation schedule is documented

---

## Organisational Approval Record

| Field | Value |
|---|---|
| Approved by | MANUAL APPROVAL REQUIRED — Commanding Officer / System Owner |
| Approval date | — |
| Budget allocated | — |
| Selected vendor | — |
| Engagement start date | — |
| Engagement completion date | — |
| Report delivery date | — |
| Sign-off that all Critical/High are resolved | — |
