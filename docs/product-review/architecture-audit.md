# AAFC TMS — Architecture Audit

**Review:** Post-Gap Human Workflow, Architecture and Design Review — Stage 2 (Superpowers)  
**Date:** 2026-08-16  
**Scope:** System-level architectural patterns, coherence, and structural soundness  
**Method:** Analysis only — no changes recommended for implementation during this review

---

## 1. System topology

```
                    ┌─────────────────────────────────┐
                    │         PostgreSQL               │
                    │   (Supabase, prod + staging)     │
                    │   SQLite (local dev)             │
                    └──────────────┬──────────────────┘
                                   │ SQLAlchemy 2.0
                    ┌──────────────▼──────────────────┐
                    │         FastAPI backend          │
                    │   backend/app/main.py            │
                    │   6 routers, ~212 endpoints      │
                    │   JWT HS256, pbkdf2_sha256       │
                    │   Alembic migrations             │
                    └──────┬───────────────┬──────────┘
                           │               │
              ┌────────────▼───┐     ┌─────▼──────────────────┐
              │ Main TMS       │     │ Planning Workspace       │
              │ connected-     │     │ frontend/ (React+Vite)  │
              │ frontend/      │     │ Deployed at /planning   │
              │ Single-file    │     │ Module mode (no shell)  │
              │ HTML/CSS/JS    │     │ Full-app mode (has nav) │
              │ No build step  │     │ Auth: cookie handoff    │
              └────────────────┘     └─────────────────────────┘
```

### Architectural strengths

1. **Single backend, two UI surfaces** — The FastAPI backend is the single source of truth. Both frontends call the same API. There is no separate PW-only backend — all planning data is in the same PostgreSQL instance. This eliminates data-sync problems.

2. **Two-frontend separation is principled** — Main TMS is the operational system (outcomes, daily management); Planning Workspace is the planning system (forward scheduling, annual programs). The separation reflects distinct user mental models and temporal concerns: Main TMS is past/present-tense (what happened, what is happening), PW is future-tense (what should happen). This is architecturally sound.

3. **Role-based scope is server-enforced** — RBAC is implemented in `permissions.py` with explicit `require_*` helpers and scope-aware predicates. The frontend reflects the role but does not enforce it — the backend is the gate. This is correct.

4. **Audit log is write-only and immutable** — No DELETE or UPDATE endpoint for AuditLog. This is correct for compliance.

5. **Soft-delete everywhere** — Archive + restore pattern is consistent across entities. Hard deletes require zero dependents, are gated by a pre-check, and are restricted to specific roles. This is a strong data-safety pattern.

6. **Proxy / Delegated Intervention model** — Wing_admin and national_admin have explicit read access without requiring write activation. Writes require Proxy/Intervention to be active first. This prevents accidental mutation by elevated roles browsing data.

---

## 2. Architecture concerns

### AC-01: The connected-frontend is a 400KB single file

**Observation:** `connected-frontend/index.html` is ~400KB of HTML, CSS, and JavaScript in a single file. This includes all pages, all rendering logic, all modal handlers, all chart code, and all API calls.

**Risk:**
- Maintenance burden: any developer editing this file must hold the entire application's state in mind
- No module boundaries: a bug in one page's JS can affect another page
- No tree-shaking: every user downloads code for all pages, including admin-only pages they cannot use
- Onboarding cost for any future developer is high

**Architectural assessment:** This was a deliberate tradeoff — no build step means simpler deployment and a deployable single-file for offline demo distribution. For a pilot system with a single primary developer, this is defensible. If the codebase expands significantly (new roles, new reporting pages, CEA integration), the maintenance cost becomes unsustainable.

**Severity for current scope:** LOW — the system works and the tradeoff was intentional. Flag for long-term consideration only.

---

### AC-02: Two frontend session mechanisms — cookie + sessionStorage

**Observation:** Both frontends use `sessionStorage` + Bearer token as the primary mechanism. The `aafc_session` cookie (`SameSite=None; Secure`) is a fallback for cross-origin tab opens.

**Assessment:**
- `SameSite=None; Secure` means the cookie is sent cross-site — necessary because Main TMS and PW are on different origins in production
- `Secure` means it only works over HTTPS — correct for production
- The cookie is set by the backend login handler; the frontend does not manage it

**Risk:** `SameSite=None` is permissive by modern browser standards. If PW is ever served from the same origin as Main TMS (e.g., under the same Railway domain), the `SameSite=None` would be unnecessary and could be tightened to `Lax`. Currently correct for the cross-origin deployment.

**Severity:** LOW — correctly implemented for the current deployment model. See also integration-audit.md.

---

### AC-03: Hardcoded year list in Training Calendar

**Observation:** Training Calendar (`page-calendar`) uses a hardcoded year selector `[2025, 2026, 2027]`. Post-2027 this will be wrong.

**Impact:** Low severity in 2026; becomes a bug in 2028. Dynamic calculation (current year ± 1) would be a 2-line fix.

**Severity:** LOW — technical debt, not a current bug.

---

### AC-04: No API versioning

**Observation:** All API endpoints are under `/api/` with no version prefix (e.g., no `/api/v1/`). 

**Assessment:** For a single-organisation internal system where both frontends and the backend are deployed together, this is acceptable. API versioning would add complexity without benefit for the current deployment model (no external API consumers). If the API were ever opened to third-party integrations, versioning would need to be added.

**Severity:** LOW — acceptable for current scope.

---

### AC-05: Backend config validation on startup

**Observation:** `backend/app/main.py` runs `validate_for_production()` on startup which fails closed if critical env vars are missing or wrong for production. `is_production` gate in `config.py` enforces this.

**Assessment:** This is a strong pattern. Production deployments cannot start with development defaults. However, the validation is in the lifespan hook — if Railway's health checks hit the service before lifespan completes, there could be a race condition on cold start.

**Severity:** VERY LOW — theoretical; no known instance.

---

### AC-06: Frontend uses `sessionStorage` which does not survive tab close

**Observation:** Both frontends store the JWT in `sessionStorage`, which is cleared when the browser tab is closed. On re-open, the user lands on the login page.

**Assessment:** This is a deliberate security decision — sessions do not persist across browser restarts. The `aafc_session` cookie provides a short-lived fallback for cross-tab navigation but is not designed for persistent login. For a Training Officer who uses the system occasionally (not every day), this means re-entering their access code at each session. This is the intended security posture for AAFC access codes.

**Severity:** LOW — by design. Worth noting in the user-facing help text so Training Officers know to keep the tab open during a session.

---

### AC-07: Planning Workspace module mode dependency on cookie

**Observation:** In module mode (the current pilot deployment), the PW opens in a new tab. Session transfer relies on the `aafc_session` cookie being present and valid at the time the tab opens. If:
- The user has the Main TMS tab idle for longer than the cookie TTL, OR
- The browser blocks third-party cookies, OR
- The user opens PW directly from a bookmark

...the PW will open unauthenticated and the user will see a login screen or blank state with no context about which unit they are.

**Assessment:** This is the primary integration risk in the current architecture. `SameSite=None` cookies are increasingly blocked by browsers in privacy modes and some default configs (Safari ITP, Firefox Enhanced Tracking Protection). A user who has privacy settings enabled will not get the handoff.

**Severity:** MEDIUM — affects discoverability and reliability of PW access. See integration-audit.md for detail.

---

### AC-08: `training.py` router is a monolith

**Observation:** `backend/app/routers/training.py` handles ~90 endpoints across curriculum, parade nights, sessions, facilitators, training areas, equipment, cadets, training classes, activities, and taxonomy tags. This is the largest single file in the backend.

**Assessment:** Logically these are distinct sub-domains. The monolithic router creates:
- Long import chains
- Reduced discoverability ("where is the facilitator endpoint?")
- Merge conflict risk if multiple developers work simultaneously
- Cognitive load for maintenance

**Severity:** LOW for a solo-developer project. MEDIUM if the team grows. The router is functionally correct; the issue is structural organisation only.

---

### AC-09: `connected-frontend` build process via `make connected`

**Observation:** CLAUDE.md states that `frontend/` has a `--mode single` build (`npm run build:single`) that regenerates `connected-frontend/index.html`. This means the Main TMS frontend is technically generated from the React source in some flows.

**Assessment:** This creates a subtle coupling: changes to `frontend/` (the PW React app) potentially affect `connected-frontend/` if the `make connected` target is run. The architecture rules explicitly say "do not conflate the two build outputs" but the regeneration path exists.

**Risk:** A developer running `make connected` accidentally could overwrite operational Main TMS changes. The reverse is also true: if the Main TMS HTML is edited directly and then `make connected` is run, those edits are overwritten by the React build.

**Severity:** MEDIUM — operational risk. The `make connected` workflow's scope and trigger conditions should be documented clearly in CLAUDE.md.

---

## 3. Security architecture assessment

| Concern | Status | Notes |
|---|---|---|
| Access codes: no plaintext in API responses | ✓ | Confirmed by API inventory — only one-time creation response |
| Access codes: no hashes returned | ✓ | Confirmed |
| JWT HS256 — key per environment | ✓ | `JWT_SECRET` is per-environment |
| CORS — no wildcard in production | ✓ | `CORS_ALLOWED_ORIGINS` is env-specific |
| localStorage — no operational data | ✓ | sessionStorage only; cleared on tab close |
| Audit log — immutable | ✓ | No delete/update endpoints |
| Proxy/Intervention — required for writes by elevated roles | ✓ | Correct pattern |
| XSS — `esc()` used in innerHTML | Requires verification | Main TMS uses `esc()` helper; not independently verified for 100% coverage |
| CSRF — SameSite=None cookie | Partial | SameSite=None means CSRF protection is weaker than Strict/Lax; mitigated by JWT bearer token being the primary auth (CSRF only applies to cookie-based auth) |
| Rate limiting | ✓ | Rate limits exist (reset endpoint in System Console); specifics not reviewed |
| Input validation | ✓ | FastAPI + Pydantic v2; server-side validation |

**Overall:** Security architecture is sound for the deployment model. The SameSite=None cookie is the only meaningful exposure and is mitigated by the JWT bearer being the primary auth.

---

## 4. Deployment architecture assessment

| Concern | Status | Notes |
|---|---|---|
| Railway multi-service deployment | ✓ | Backend, frontend, PW as separate services |
| Environment separation (production/staging) | ✓ | Separate DATABASE_URL, JWT_SECRET, etc. per environment |
| Staging never touches production DB | ✓ | Separate Postgres instance per environment |
| Backup / restore | ✓ | GitHub Actions workflow for daily backup; weekly restore test |
| Migration on deploy | ✓ | `alembic upgrade head` in docker-entrypoint-staging.sh |
| Health check | ✓ | `GET /api/health/ready` exists |
| HTTPS only | ✓ | Railway provides HTTPS; COOKIE_SECURE=true enforces it |

---

## 5. Summary findings

| ID | Finding | Severity | Domain |
|---|---|---|---|
| AC-01 | connected-frontend is a 400KB monolithic file | LOW | Frontend architecture |
| AC-02 | Two session mechanisms (cookie + sessionStorage) — correct but complex | LOW | Auth |
| AC-03 | Hardcoded year list in Training Calendar | LOW | Technical debt |
| AC-04 | No API versioning | LOW | API design |
| AC-05 | Startup config validation is correct | N/A (strength) | Backend |
| AC-06 | sessionStorage cleared on tab close | LOW | Auth / UX |
| AC-07 | PW module mode cookie handoff blocked by browser privacy settings | MEDIUM | Integration |
| AC-08 | training.py is a monolithic router (~90 endpoints) | LOW | Backend |
| AC-09 | `make connected` creates a coupling between frontend/ and connected-frontend/ | MEDIUM | Build process |

**No critical architectural issues found.** The two-frontend separation is principled and correctly implemented. Security architecture is sound. The medium-severity findings (AC-07, AC-09) are manageable. The low-severity findings are technical debt that does not affect current functionality.

