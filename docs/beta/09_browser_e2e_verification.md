# Browser-Level E2E Verification (Workstream 9) — Staging

Real Chromium via Playwright against `https://*-staging.up.railway.app`, not just unit tests or
curl. Evidence screenshot: `docs/beta/evidence/planning-workspace-staging-handoff-2026-07-14.png`.

## Session handoff: legacy TMS → Planning Workspace — PASSED

**Test**: established a real logged-in browser session (squadron 703 admin), then opened the
Planning Workspace staging URL in a **new tab in the same browser context** — simulating a user
clicking "Open Planning Workspace" from the legacy TMS nav, which opens it as a separate tab/origin.

**Result**: the Planning Workspace picked up the session automatically with **no login form shown**
and **zero console/page errors**. Rendered real, substantive content: correct squadron/role banner
("703 SQN · Sqn Admin · 703 Admin"), Year view with real scheduled curriculum items (New Cadet
Welcome, Junior Drill and Ceremonial), real facilitator names, parade-night cards, term dates,
filters, and the warning legend. See the evidence screenshot.

**Mechanism confirmed**: this works because of the architecture traced for DEFECT-004 — in module
mode (`MODULE_MODE=true`, no login form), the React app's `AuthProvider` calls `/api/auth/me` with
`credentials: 'include'`; since a fresh tab has no `sessionStorage` token to send as a Bearer
header, the request relies purely on the `aafc_session` cookie (`SameSite=None; Secure`), which the
browser correctly attaches on this cross-origin (different Railway subdomain) request. This is a
second, independent, real-world confirmation that `SameSite=None` is load-bearing — not just for
the legacy frontend's own API calls, but for this exact handoff flow.

## Testing-methodology note (not a product defect)

An earlier pass through this test logged in via a scripted direct `fetch()` to `/api/auth/login`
(bypassing the legacy frontend's own UI) and found that reloading the legacy TMS page afterward
still showed the login form. **This was a test artifact, not a bug**: traced the legacy frontend's
actual login handler (`connected-frontend/index.html`, `doLogin()`) and found it calls
`tokenSet(out.token)` — storing the JWT in `sessionStorage` — immediately after a successful login,
and every subsequent API call attaches it as `Authorization: Bearer <token>` (`tokenGet()`,
line ~2742). My scripted `fetch()` login never called `tokenSet()`, so `sessionStorage` stayed
empty and the page correctly treated the tab as logged out on reload — exactly as it would for any
real user who somehow got a valid cookie without going through the login form. A real user going
through the actual UI would have `sessionStorage` populated and reload correctly.

**Architecture takeaway, confirmed empirically**: both frontends use `sessionStorage` + Bearer token
as their *primary*, same-origin session-persistence mechanism (fast, reliable, no cross-site cookie
policy involved). The `aafc_session` cookie exists specifically as the *fallback* for the one
scenario where there's no `sessionStorage` to inherit — a fresh tab/origin, i.e. exactly the
Planning Workspace handoff case tested above. This is a deliberate, sensible design, not an
inconsistency.

## Not yet covered by this session (scope for a follow-up pass)

The full Workstream 9 matrix (all personas, all views at multiple zoom levels/resolutions,
accessibility, slow-network simulation, every known regression target from the original brief) was
not exhaustively run — this session covered the highest-value, previously-unverified item (real
cross-origin session handoff, the thing most likely to be silently broken by a `SameSite` change or
CORS misconfiguration) with genuine browser evidence rather than assuming it works. Recommend before
final GO/NO-GO: Term/8-week/2-week/Custom-range views specifically (the original brief's named
regression targets — blank screen, infinite loading, Custom Range 422), logout propagation across
both origins, and a pass at 125%/150% browser zoom.
