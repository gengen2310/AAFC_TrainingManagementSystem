# 06 — Security Review (Reconnaissance Stage)

**Role:** Security Reviewer — reconnaissance / static code review only.
**Scope:** Map the attack surface and identify credible, specific candidate vulnerabilities for a
later live-testing phase to verify against staging. **No live HTTP requests, logins, or exploitation
were performed.** No application code was modified.
**Date:** 2026-08-08
**Repo state:** branch `feature/restore-planning-workspace`, HEAD `1a376bb` (working tree clean at start).
**Method:** Reading of `backend/app/` (routers, permissions, dependencies, security, config, models,
services), `connected-frontend/index.html`, and cross-reference against
`docs/remediation/master_gap_register.csv` (REM-01…REM-112) so already-fixed, already-tested defects
are not re-reported as new.

---

## Executive summary

The authentication and authorization core of this system is, on static review, **well-built and
consistent**. The permission layer (`permissions.py`) centralises all tenancy decisions; write
endpoints across `training.py`, `accounts.py`, `organisations.py`, and the Flight endpoints follow a
correct anti-IDOR pattern (fetch the target row first, then authorize against **the row's own**
`squadron_id`/`wing_id`, never client-supplied context). The historical IDOR/tenancy defects called
out in the task (planning.py scope gaps, cross-squadron facilitator reads) are genuinely fixed and
carry regression tests (`test_planning_idor.py`, `test_wing_squadron_view_scope.py`,
`test_session_revocation.py`). CSV/XLSX formula-injection is defended on export; raw-SQL surface is
effectively nil (ORM throughout). The security greps from `.claude/rules/security.md` still pass.

No **BLOCKER** issues were found by code reading. The findings worth a live phase are, in priority
order:

1. **The production fail-closed configuration gate keys entirely off `ENVIRONMENT`** — and this repo
   documents that production has previously run with `ENVIRONMENT` mis-set to `staging`. If that
   recurs, every production security check (dev secrets, secure cookies, CORS lockdown, non-SQLite
   DB) is silently skipped. **HIGH / PLAUSIBLE** — verify the actual live env-var values.
2. **Proxy / Delegated Intervention sessions never expire and survive logout** — no timeout column,
   and `logout` does not deactivate the active `ProxySession`; `get_principal` re-attaches it on next
   login. **MEDIUM / CONFIRMED (code) — persistence needs live confirmation.**
3. **A handful of `innerHTML` sites insert admin-controlled org names/addresses without `esc()`** —
   stored-XSS candidate requiring a privileged writer. **LOW–MEDIUM / PLAUSIBLE.**

Everything else reviewed was clean or already-remediated; those areas are stated briefly rather than
padded out.

---

## 1. Authentication

**Reviewed:** `backend/app/routers/auth.py`, `backend/app/dependencies.py::get_principal`,
`backend/app/security.py`, `backend/app/models/organisations.py` (User.token_version).

**Finding 1.1 — Token handling is correct and fail-safe. (CONFIRMED, no defect)**
`get_principal` (`dependencies.py:22-49`) rejects: missing token → 401 `auth_required`;
malformed/expired token → 401 `invalid_or_expired` (JWT `exp` enforced by `decode_token`,
`security.py:55-58`, which pins `algorithms=[HS256]` — no `alg=none`/algorithm-confusion surface);
inactive/deleted user → 401 `invalid_user`; and **token-version mismatch → 401 `session_revoked`**
(`dependencies.py:35`). `token_version` (`organisations.py:83`) is bumped on every access-code change
(`auth.py:233`, self and admin-reset paths), so rotating a credential invalidates outstanding tokens.

**Finding 1.2 — Role is resolved live per-request, not trusted from the JWT. (CONFIRMED, positive)**
The JWT carries a `role` claim (`security.py:52`) but `get_principal` builds the Principal from the
**live** `user.role` DB value (`dependencies.py:38`), not the claim. A demotion/role change therefore
takes effect on the very next request with no token reissue required — closing what would otherwise
be a stale-privilege window. Note this means `token_version` is *not* strictly required for
role-change revocation (the live lookup covers it); it is the credential-rotation mechanism.
*Candidate to confirm in the live phase:* whether `accounts.py::change_role` also bumps
`token_version` for defense-in-depth (REM-106 notes the UI does not surface "you will be logged out";
the authz correctness does not depend on it, but worth a spot check). **LOW / LOW-CONFIDENCE.**

**Finding 1.3 — Two-tier login lockout; per-IP tier is per-worker. (LOW / informational)**
Targeted brute force is well-defended: a **DB-backed per-account** lockout (5 failures → 24h,
`auth.py:107-117,150-157`) holds across gunicorn workers. The scan-all/per-IP limiter
(`security.py:_attempts/_lockouts`) is **in-memory per-worker** (explicitly documented as needing
Redis for production). Under multiple workers the per-IP scan limiter is weaker than it appears, but
the per-account tier is the meaningful control and is robust. Not a blocker; note for the load/abuse
test.

---

## 2. Authorization / IDOR

**Reviewed:** write endpoints in `training.py`, `planning.py` (via gap register + helper audit),
`organisations.py`, `accounts.py`; `permissions.py`; the two-helper selection rule in
`.claude/rules/architecture.md`.

**Finding 2.1 — Write endpoints use the correct anti-IDOR pattern. (CONFIRMED, no defect)**
Sampled every mutating route in `training.py` (`grep` of `@router.(post|patch|put|delete)` vs. its
guard, lines 271–1437). Uniform pattern: fetch the row (`pn`, `s`, `f`, `r`, `e`, `target`), then
`require_can_write_squadron(p, row.squadron_id, row.wing_id)` — authority is derived from the
persisted row, so ID-guessing a foreign object cannot bypass tenancy. Examples: PATCH parade-night
`training.py:345`; POST session `:458`; PUT session `:503`; PATCH facilitator `:1044`; facilitator
absorb/merge `:1275`; PATCH/DELETE training-area `:1345/:1367`; PATCH/DELETE equipment `:1416/:1437`.
`permissions.py::can_write_activity` (`:77-100`) explicitly documents resolving authority from the
row's own `owning_level`, "never from caller-supplied context."

**Finding 2.2 — accounts.py and Flights are correctly scoped. (CONFIRMED, no defect)**
All account mutations gate through `_require_write_actor` + `_require_manage_authority`
(`accounts.py:121-138`), which checks the actor's authority over the **target's** role and org, with
wing/squadron ownership re-verified from the DB (`db.get(Squadron, target.squadron_id)`). Flight
writes use `_can_write_flight` (`:767-779`) which re-derives scope from the squadron row. `change_code`
(`auth.py:199-238`) reuses `_require_manage_authority` for the non-self path.

**Finding 2.3 — Historical planning.py IDOR gaps are fixed; one residual remains by design.
(CONFIRMED fixed / one PLAUSIBLE live candidate)**
REM-44, REM-45, REM-61, REM-64 fixed the `_require_plan_write`/`_require_year_access` scope gaps
(create_planning_year, create/update_location, override_conflict, planning facilitators, tag
creation) by adding `require_can_write_squadron`, each with regression tests. Do **not** re-flag
these. **Residual, per REM-45's own `residual_limitation`:** Annual Program CSV/XLSX import into a
**wing/national-scoped** plan year that routes rows to *multiple* squadrons via the sheet's Unit
column is **not** per-row scope-checked — a single `require_can_write_squadron` on the year is not
sufficient there. This is documented, not hidden, but it is a genuine **candidate for the live phase**
(craft an import as wing_admin with rows targeting a squadron outside the wing and observe whether the
commit path rejects per row). **MEDIUM / PLAUSIBLE.**

**Finding 2.4 — `_require_year_access` vs `require_can_write_squadron` usage looks correct.
(CONFIRMED, no defect)** Per the architecture rule, I checked that the simpler year-access helper is
only used where no proxy/delegation concept applies, and the proxy-aware helper is used on
squadron-scoped writes. After the REM-44/45 fixes the squadron-scoped writes in `planning.py` use the
proxy-aware helper. No misapplied-helper IDOR found in the sampled set.

---

## 3. Proxy / Delegated Intervention Mode

**Reviewed:** `organisations.py:564-617` (enter/exit/current), `models/organisations.py:114-123`
(`ProxySession`), `dependencies.py:40-48` (overlay), `permissions.py:66-100` (write gating).

**Finding 3.1 — Entry is reason-gated, scope-checked, and target-switch-safe. (CONFIRMED, positive)**
`enter_proxy` (`:569-598`) requires a non-empty `reason` (400 `reason_required`), enforces
wing_admin→own-wing only (`s.wing_id != p.wing_id` → 403), sets `delegated_intervention` for
national/system_admin, **closes all existing active sessions before opening a new one** (`:586-590`),
and audits with the reason and squadron. Switching target therefore cannot happen silently — it
requires a fresh `enter` call with a fresh reason. Writes are independently gated
(`can_write_squadron` requires `proxy_mode`+matching `acting_squadron_id`, `permissions.py:66-75`), so
merely holding a session is not enough — a direct API write still checks mode+target.

**Finding 3.2 — Proxy/Intervention sessions have no expiry. (MEDIUM / CONFIRMED code)**
`ProxySession` (`models/organisations.py:114-123`) has **no `expires_at`/TTL column** — grep for
`expire|ttl` against proxy returns nothing. A session stays `active=True` until the actor explicitly
exits or enters a different target. There is no server-side auto-timeout on an elevated write window.
For a national_admin/system_admin Delegated Intervention (which can target *any* squadron), an
unattended active session is a standing write capability.

**Finding 3.3 — Logout does not end the Proxy/Intervention session; it survives re-login.
(MEDIUM / CONFIRMED code, PLAUSIBLE live impact)**
`logout` (`auth.py:160-165`) only deletes the cookie and audits — it does **not** deactivate the
`ProxySession`. `get_principal` re-attaches *any* active session for the user by
`actor_user_id`+`active` on the next authenticated request (`dependencies.py:40-48`), independent of
which token is presented. Net effect: enter Intervention → log out → log back in ⇒ **still in
Intervention Mode**, with no re-prompt and no new reason. Combined with 3.2, an elevated write context
can persist far beyond the operator's awareness. Live-phase candidate: enter proxy as wing_admin,
logout, re-login via the normal flow, then attempt a squadron write and confirm it succeeds without
re-entering. Recommended remediation direction (for the later phase, not this one): deactivate active
sessions on logout and/or add a TTL enforced in `get_principal`.

---

## 4. Input / Output handling

**Reviewed:** `connected-frontend/index.html` (esc/innerHTML), `export_import.py`, `planning.py`
upload paths, raw-SQL grep across `backend/app`.

**Finding 4.1 — XSS: `esc()` is used broadly but a few `innerHTML` sites omit it for
admin-controlled org data. (LOW–MEDIUM / PLAUSIBLE)**
`esc()` appears 339× against 244 `innerHTML` sites. Most unescaped template-literal insertions carry
non-user data (server-computed counts, `location.origin`, weekday labels, ISO dates). The genuine
exceptions insert **organisation names/addresses** without `esc()`:
- `connected-frontend/index.html:8650` — Wing drill panel title: `${r.short_name||r.code}`
- `connected-frontend/index.html:8705` — National drill panel title: `${w?(w.name||w.code):'Wing'}`
- `connected-frontend/index.html:8709` — squadron rows: `${s.short_name||s.code}` and
  `${(s.address||'').split(',')[0]}`

These values are set by admins with org-write authority, so exploitation requires a privileged writer
(stored XSS via a malicious Wing/Squadron `name`/`short_name`/`address`), which is why this is
LOW–MEDIUM rather than high. It nonetheless violates this project's own rule ("always use `esc()` for
user-supplied content inserted into innerHTML"). Live-phase candidate: set a Wing/Squadron short name
to an `<img onerror>` payload and open the National/Wing drill panels. (Report only — not fixed here.)

**Finding 4.2 — SQL injection surface is effectively nil. (CONFIRMED, no defect)**
The only raw SQL is fixed-string health/version probes — `health.py:19` and `system.py:113`
(`SELECT 1`), `system.py:149` (`SELECT version_num FROM alembic_version`) — and
`services.py::fk_dependents` (`:63`) which builds a parameterised SQLAlchemy `select(...).where(col ==
target_id)` from `Base.metadata`, not string interpolation. No f-string/`%`/`+` SQL construction, no
`executescript`, no user-controlled table/column names. Everything else is ORM.

**Finding 4.3 — CSV/XLSX formula injection is already defended. (CONFIRMED, positive)**
`export_import.py::_neutralise` (`:28-30`) prefixes a leading `= + - @` cell with `'` and is applied
to **both** CSV (`:38`) and XLSX (`:52`) export rows. Import preview explicitly "treats all cell
content as data (no formula execution)" (`:111`), loading workbooks with `data_only=True`. Export
`export_type` is validated (only `program-items`, else 400) so the value flowing into the
`Content-Disposition` filename is not attacker-controlled — no response-header/filename injection.

**Finding 4.4 — File-upload size enforcement is worth a live check. (LOW / PLAUSIBLE)**
`planning.py` has `UploadFile` paths (`:3235`, `:3412`) that `await file.read()` the whole body into
`openpyxl`/`csv`. `UPLOAD_MAX_MB=5` exists in config (`config.py:64`) but I did not confirm by reading
that every upload path enforces it before `read()`. A missing check would be a DoS/memory candidate,
not a data-exposure one. Verify the limit is applied on these two routes in the live phase.

---

## 5. Secrets (greps re-run against current tree)

All four `.claude/rules/security.md` greps were re-run **with `-E`** against the current
`connected-frontend/` and `backend/`:

| Grep | Result | Verdict |
|------|--------|---------|
| Removed wording (`your unit only` / `Controlled access…`) | 0 across all files | PASS |
| Access-code exposure (`View current code` / `Show access code` / …) | 0 across all files | PASS |
| Seeded codes / hashes / `localStorage` | **1** in `index.html` | False positive — confirmed |
| Secrets (`JWT_SECRET`/`SECRET_KEY`/`DATABASE_URL`) | **1** in `index.html` | False positive — confirmed |

The two matches were manually reviewed (per the rule's requirement never to trust the count alone):
- `index.html:1522` — `<option value="access_code_reset">` — an **audit-log filter dropdown option**
  (an audit action-type label), not a code. Matches `access_code` as a substring only.
- `index.html:4250` — help text `pg_restore --clean … -d "DATABASE_URL" filename.dump` — a **literal
  placeholder in a restore-command example**, not a secret value.

Both are exactly the benign cases `.claude/rules/security.md` already documents from the 2026-08-05
review. No real secret, access code, or hash is embedded in the frontend. (`.local-dev/index.html`
mirrors the same two benign matches.) **PASS.**

---

## 6. Audit integrity

**Reviewed:** `models/operations.py:47-65` (AuditLog), `organisations.py:620-643` (audit read),
`services.py::audit`, and audit calls across routers.

**Finding 6.1 — AuditLog is immutable via the API. (CONFIRMED, no defect)**
The model is documented "Immutable. There is no update/delete path through the API."
(`operations.py:48`). The only exposed route is `GET /api/audit` (`organisations.py:623-643`) —
role-gated (`_AUDIT_READ_ROLES`, `:620/:626`) and tenancy-filtered (non-national callers are
constrained to their wing/squadron rows, `:629-633`). No POST/PATCH/PUT/DELETE against `audit_logs`
exists anywhere in the routers.

**Finding 6.2 — Privileged actions are audited. (CONFIRMED, spot-checked)**
Confirmed `audit(...)` calls on: login/logout (`auth.py:146,163`), access-code change/reset
(`auth.py:237`), proxy/intervention enter+exit (`organisations.py:595,608`), Wing/Squadron
create/archive/restore/**delete** (`organisations.py:78,161,179,214,287,401,427,468`), account
change-role/reset/archive/restore/delete/unlock (`accounts.py`), Flight create/update/archive
(`accounts.py:809,…`), and backup create/download (`system.py:338,403`). Deletes record old values.
No sampled privileged write was missing an audit call.

---

## Cross-cutting finding — production fail-closed gate depends on `ENVIRONMENT`

**Severity: HIGH · Confidence: PLAUSIBLE (needs live env-var verification)**

`Settings.validate_for_production` (`config.py:97-126`) enforces the real security posture —
rejecting dev `SECRET_KEY`/`JWT_SECRET`, `COOKIE_SECURE=false`, wildcard/localhost CORS, and a SQLite
DATABASE_URL — and `main.py:54-58` raises `RuntimeError` (refuses to boot) if any problem is found.
**But the very first line of the check is `if not self.is_prod: return []`** (`config.py:103`), and
`is_prod` is true only when `ENVIRONMENT ∈ {production, prod}` (`config.py:93-95`). So the entire
production security gate is bypassed whenever `ENVIRONMENT` is anything else.

This is not hypothetical for this system: `config.py:77-79` documents that **"production's ENVIRONMENT
was found set to 'staging' in practice"** — which is exactly why a separate fingerprint-based guard
(`PROTECTED_DB_HOST_FINGERPRINTS`) was added for `reset_db()`. That secondary guard protects the
database from destructive reset, but it does **not** cover the startup security gate: if production
again runs with `ENVIRONMENT=staging`, the app will happily boot with dev secrets / insecure cookies /
loose CORS and no `RuntimeError`. CLAUDE.md lists `ENVIRONMENT must accurately reflect the deployment`
as a named invariant precisely for this reason.

**Live-phase action:** read the actual `ENVIRONMENT`, `COOKIE_SECURE`, `COOKIE_SAMESITE`,
`CORS_ALLOWED_ORIGINS`, and secret-length values in the real production and staging Railway
environments (via `railway variable list`, not by guessing) and confirm production genuinely has
`ENVIRONMENT=production` and passes all five checks. This is the single highest-value item to verify
live.

---

## Prioritized live-test candidate list (for the later adversarial phase)

1. **`ENVIRONMENT` / production config gate (HIGH, cross-cutting).** Confirm production's live
   `ENVIRONMENT=production` and that `validate_for_production` would actually fire — i.e. verify
   `COOKIE_SECURE=true`, `COOKIE_SAMESITE`, no `*`/localhost in CORS, ≥32-char unique secrets,
   non-SQLite DB. A mis-set `ENVIRONMENT` silently disables all of it.
2. **Proxy/Intervention persistence (MEDIUM, §3.2/3.3).** Enter Proxy (wing_admin) and Delegated
   Intervention (national/system_admin); log out; log back in via the real login flow; attempt a
   squadron write. Confirm whether the elevated write context persists with no re-prompt/no new
   reason, and whether any timeout ever ends it.
3. **Multi-squadron Annual Program import scope (MEDIUM, §2.3 / REM-45 residual).** As wing_admin,
   commit a wing/national-scoped Annual Program import whose Unit column routes rows to a squadron
   outside the actor's authority; confirm whether per-row scope is enforced on the commit path.
4. **Stored XSS via org names (LOW–MEDIUM, §4.1).** Set Wing/Squadron `short_name`/`name`/`address`
   to an HTML/script payload; open the Wing and National drill-down panels (index.html ~8650/8705/
   8709) and confirm whether it renders unescaped.
5. **Upload size enforcement (LOW, §4.4).** POST oversized files to the two `planning.py` upload
   routes; confirm `UPLOAD_MAX_MB` is enforced before the full body is read.
6. **Per-IP rate-limit behaviour under multiple workers (LOW, §1.3).** Confirm whether the per-IP
   scan limiter holds across gunicorn workers (per-account DB lockout is expected to hold regardless).
7. **change_role session behaviour (LOW, §1.2).** Confirm a live role change takes effect on the next
   request (expected, since role is read live) and note whether `token_version` is also bumped.

## Areas reviewed and found clean (stated briefly, no action)

- JWT decoding pins `algorithms=[HS256]` — no `alg=none`/confusion surface (`security.py:57`).
- Raw-SQL surface: fixed-string health/version probes + one parameterised metadata count only (§4.2).
- CSV/XLSX export formula-injection neutralised on both formats (§4.3).
- AuditLog immutable; no mutation endpoint exists (§6.1).
- Swagger/OpenAPI disabled globally (`main.py:66`, `docs_url=None, redoc_url=None, openapi_url=None`)
  — the root response's `"docs":"/docs"` string (`main.py:250`) is cosmetic and resolves to 404.
- Security response headers set globally: `X-Content-Type-Options`, `X-Frame-Options: DENY`,
  `Referrer-Policy`, a `default-src 'self'` CSP, `Permissions-Policy`, and HSTS when `is_prod`
  (`main.py:220-229`).
- The mounted-but-frontend-unreachable `program.py` router (REM-26) is **not** an unauthenticated
  hole: every endpoint takes `Depends(get_principal)` and writes go through `_require_owner`/
  `require_role` (`program.py:27-274`). It is an authenticated, low-sensitivity (curriculum reference
  data) surface, not an open one.

---

*Reconnaissance only. No live requests were issued and no code was changed. All severities on
"PLAUSIBLE" findings are pre-live estimates for the coordinating session to confirm or downgrade
against staging with proper safety controls.*
