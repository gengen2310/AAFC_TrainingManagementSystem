# 08 — Adversarial Test Report (Phase E)

**Role:** Adversarial QA / live-test execution against the prioritized candidate list in
`06_security_review.md`.
**Scope:** Live verification only — no code changes in this document's own scope (fixes, when
needed, are implemented and cross-referenced in `defect_register.csv` /
`docs/remediation/master_gap_register.csv`, same as every other phase).
**Production control:** Per the program charter, all active/adversarial testing here targets
**staging**, never production. The one exception is item 1 below, which is a **non-destructive
read** of production's own live config (`railway variable list`) — not an adversarial action.

---

## Candidate 1 — `ENVIRONMENT` / production config gate (HIGH, cross-cutting)

**Verdict: PASS. Verified, not assumed.**

Read `backend/app/config.py::validate_for_production()` first to know exactly what it checks (not
just "is ENVIRONMENT set"), then read the live values via `railway variable list --service
aafc-tms-backend --environment production` (non-destructive, read-only):

| Check | Requirement | Production live value | Result |
|---|---|---|---|
| `ENVIRONMENT` | `production`/`prod` (gate active at all) | `production` | PASS |
| `SECRET_KEY` | ≥32 chars, not `dev-only-`/`changeme`-prefixed | 64 chars | PASS |
| `JWT_SECRET` | ≥32 chars, not `dev-only-`/`changeme`-prefixed | 64 chars | PASS |
| `COOKIE_SECURE` | `true` | `true` | PASS |
| `CORS_ALLOWED_ORIGINS` | non-empty, no `*`, no `localhost`/`127.0.0.1` | `https://aafc-tms-frontend-production.up.railway.app,https://aafc-tms-planning-workspace-preview-production.up.railway.app` | PASS |
| `DATABASE_URL` | not `sqlite` | `postgresql` | PASS |

All five checks `validate_for_production()` actually performs pass against production's real,
current values — this is a positive confirmation that `main.py`'s fail-closed startup gate is both
active and would find no problems today, not merely that the historical mis-set risk (documented in
`config.py:77-79`) isn't currently manifesting.

Staging cross-checked for comparison (same method): `ENVIRONMENT=staging` (correctly *not*
`production` — the gate is deliberately inert there, which is correct, not a gap) with the same
strong secrets/HTTPS-cookie/real-CORS hygiene applied anyway as good practice beyond the minimum.

**Residual risk (unchanged from the security review's own framing):** this is a point-in-time
verification, not a standing guarantee. `ENVIRONMENT` has drifted before (per `config.py`'s own
comment). Recommend a scheduled/CI check rather than treating this verification as permanent — noted
already in `QUAL-003`'s `residual_risk` field, not duplicated as a new defect here.

---

## Candidate 2 — Proxy/Intervention persistence across logout/login (MEDIUM)

**Verdict: CONFIRMED. Verified live on staging, not assumed.** Matches the security review's §3.2/3.3
prediction exactly. Tracked as `QUAL-004`.

**Method** (real browser session throughout, staging only — user logged in themselves per the
credential-handling rule; the assistant drove the rest via Claude in Chrome, using direct API calls
in place of UI clicks only where a native `prompt()`/`confirm()` dialog would otherwise freeze
automation, per `.claude/rules/frontend.md`'s documented workaround):

1. User logged into `aafc-tms-frontend-staging.up.railway.app` as `wing_admin` (7 Wing).
2. Located the Proxy entry point: Wing Overview → "Squadron Comparison" table → per-row **Proxy**
   button (`enterMode(squadronId, label)`, `index.html:8615`). Clicking it directly triggers a native
   `prompt()` for the audited reason, which froze the CDP connection exactly as documented in
   `frontend.md`'s "system_admin scope" note (the same underlying `enterMode()`/`exitMode()`
   machinery) — recovered by having the user dismiss the dialog manually, then called
   `POST /api/proxy/enter/{squadron_id}` directly with a reason via `javascript_tool`, replicating
   the handler's own post-call refresh (`loadData(); renderAll(); updateScopeBanner(); ...`).
3. Confirmed Proxy Mode active: UI banner showed "🛡️ PROXY MODE — WING VIEWING 703SQN · REASON:
   ..." with an Exit Mode control; squadron-scoped nav (Parade Nights, Facilitators, Unit Settings,
   etc.) replaced the wing-scoped nav, matching `effectiveScope()` flipping to `'squadron'` per
   `frontend.md`.
4. Signed out via the real **Sign Out** button (not a session-clear workaround).
5. User logged back in via the real login flow (fresh access-code submission, new JWT).
6. **Result: the Proxy Mode banner reappeared immediately on the post-login dashboard — no
   re-prompt, no new reason required, no indication anything needed re-confirming.**
7. Confirmed this was not merely a stale UI banner: issued a genuinely no-op write,
   `PATCH /api/squadrons/{acting_squadron_id}` (re-submitting 703SQN's own current settings
   unchanged) using only the fresh post-relogin session — **returned `200 {"ok": true}`**, proving
   `require_can_write_squadron`'s `proxy_mode`+`acting_squadron_id` gate still passed.
8. Exited Proxy Mode explicitly (`exitMode()`) to leave the environment clean; confirmed
   `S.proxy.active === false` afterward.

**Why this matters:** an operator who forgets they are in Proxy/Intervention Mode, logs out, and
logs back in — including on a shared or handed-off device — silently regains the exact same
elevated write context with zero re-authorization step. Combined with §3.2's separate finding (no
TTL at all — a session stays active indefinitely until explicitly exited), this is a standing,
unbounded elevated-write window with no operator-visible expiry and no re-consent on re-login.

**Fixed, 2026-08-09, user-directed.** Asked the user which remediation direction to take (deactivate
on logout / add a TTL / both / not now) rather than deciding unilaterally, since this is
security-session behavior with more than one defensible answer. User chose **deactivate on
logout**. `logout()` (`auth.py`) now queries every active `ProxySession` row for the actor's
`user_id` and deactivates them — mirroring `exit_proxy`'s own `ps.active = False` pattern — auditing
each as `proxy_exit_on_logout`/`intervention_exit_on_logout` before the normal logout audit entry.

Added `test_proxy_mode_does_not_survive_logout_and_relogin` to `backend/tests/test_core.py`,
reproducing the exact live-verified scenario: enter Proxy, write succeeds, log out via the real
endpoint, log back in with a fresh token, assert `GET /api/proxy/current` returns `active: false`
and a write attempt is rejected (400/403). **Verified, not assumed:** temporarily stripped the fix
and re-ran — failed with `AssertionError: Proxy session silently re-attached after logout+relogin`,
the exact right reason. Reverted and re-ran clean. Full suite: **1219 passed**, 5 skipped, 0
failures.

**Deliberately not fixed as part of this change:** the separate TTL/unattended-session gap (security
review §3.2 — a session that's never logged out of at all, e.g. an unattended device, still has no
auto-expiry). The user was offered "both" and chose deactivate-on-logout only; this residual is
recorded in `QUAL-004`'s `residual_risk` field, not silently dropped.

Recorded as `QUAL-004`, status **CLOSED**, in both `defect_register.csv` and
`master_gap_register.csv` (the latter had never actually received a QUAL-004 row despite being
referenced — added when the live finding was first confirmed).

**Fix re-verified live on staging after deploy**, same real browser session, same 703SQN: entered
Proxy Mode (fresh reason), confirmed `GET /api/proxy/current` → `active: true`, logged out via
`POST /api/auth/logout`, user logged back in via the real login flow. Result:
`GET /api/proxy/current` → `{"active": false}`, and an actual write attempt
(`POST /api/parade-nights`) now correctly returns `403 proxy_required` ("Wing Admin must enter
Proxy Mode to edit squadron data.") instead of silently succeeding. Deployed commit: `b3cff98`.

---

## Candidate 4 — Stored XSS via org names (LOW–MEDIUM)

**Verdict: CONFIRMED and FIXED.** Recorded as `REM-117` (Final Remediation, Product Hardening and
Public-Release Program, not a QUAL-number since it was found and fixed under that later program,
continuing this same candidate list). All 5 sites the original review named (`index.html`
~8664/8674/8709/8764/8766) were genuinely unescaped. One (the Proxy button's
`onclick="...enterMode('id','NAME')"`) is a materially different, deeper vulnerability class than
the other four — plain HTML-escaping does not prevent breakout in an inline event-handler attribute,
since browsers HTML-decode attribute values before compiling them as JS. Fixed with `esc()` for the
4 plain-content sites and the codebase's existing `_jsAttr()` helper (already used correctly
elsewhere for the identical pattern) for the onclick site. Verified with a real Node.js JS-engine
test — not static reasoning — confirming the payload is received as inert string data post-fix and
confirming the identical test methodology DOES detect the live breakout pre-fix. Full detail:
`master_gap_register.csv` REM-117.

## Candidates not yet started

3. Multi-squadron Annual Program import scope (MEDIUM, REM-45 residual)
5. Upload size enforcement (LOW)
6. Per-IP rate-limit behaviour under multiple workers (LOW)
7. `change_role` session behaviour (LOW)
