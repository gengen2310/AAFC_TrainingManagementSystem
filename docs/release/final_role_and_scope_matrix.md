# Final Role/Scope/Tenancy Assurance (Stage 4)

Empirical verification, not just source reading — every claim below was tested against
a live local backend (fresh SQLite, demo-seeded), not asserted from `permissions.py`
alone. Complements the Stage 2 manual review of `permissions.py`/`dependencies.py`/
`security.py` (no defects found there).

## Role catalogue (from `permissions.py`)

`sqn_general`, `sqn_admin`, `wing_viewer`, `wing_admin`, `national_viewer`,
`national_admin`, `system_admin`, `auditor`. Tenancy hierarchy: National → Wing →
Squadron only (Flight is a sub-squadron grouping, not a tenancy level — confirmed no
Flight-scoped permission checks exist anywhere in `permissions.py`).

## Existing automated coverage — re-run fresh, all passing

`tools/stress/security_scope_test.py` against a fresh local backend: **31/31 passed.**
Covers unauthenticated access (8 routes → 401), invalid/fake JWT (401), read-only-role
write attempts (403), system_admin-only endpoint denial for 4 other roles × 2 endpoints
(403), same-tenant IDOR (403), oversized request bodies, unexpected enum values, no
secrets/access-codes in any response body, and login rate-limiting (429 after repeated
failures).

**Gap in that tool identified and closed this pass**: its cross-Wing IDOR check was
unconditionally skipped ("Only one wing in DB") because the demo seed data creates
exactly one Wing (7 Wing) — cross-Wing tenancy had never actually been exercised by
this tool. Not treated as "probably fine by extension of cross-squadron passing" —
tested directly instead (below).

## New tests run this pass (live, against a real second Wing/Squadron created via the API)

| Test | Expected | Actual | Result |
|---|---|---|---|
| `wing_admin` (Wing A) GET `/api/facilitators?squadron_id=<Wing B sqn>` | 403 | 403 `forbidden` | PASS |
| `wing_admin` (Wing A) GET `/api/curriculum?squadron_id=<Wing B sqn>` | 403 | 403 `forbidden` | PASS |
| `wing_admin` (Wing A) POST `/api/facilitators` targeting Wing B sqn | 403 | 403 `proxy_required` | PASS |
| `wing_admin` (Wing A) GET `/api/wing-calendar/events?wing_id=<Wing B>` | 403 | 403 `out_of_scope` | PASS |
| `wing_admin` (Wing A) GET `/api/setup/status?squadron_id=<Wing B sqn>` | 403 | 403 `forbidden` | PASS |
| `wing_admin` (Wing A) POST `/api/proxy/enter/<Wing B squadron_id>` (enter Proxy Mode directly on a squadron outside their own Wing) | 403 | 403 `out_of_scope` | PASS |

**Deeper check — does an active Proxy session let a write "leak" to an unrelated
squadron via a client-supplied `squadron_id`?** Entered Proxy Mode legitimately on a
Wing A squadron, then called `POST /api/facilitators` with `squadron_id` set to the
*unrelated* Wing B squadron in the request body. The call returned 200 — initially
looked like a real defect (a write succeeding against a squadron outside the active
proxy's target) until traced further: `training.py`'s `add_fac` handler resolves the
actual write target via `_active_squadron(p)`, which reads the write target from
**server-side session state** (`p.acting_squadron_id`, set only by a verified
`/api/proxy/enter` call) and **never** from the client-supplied `squadron_id` in the
request body at all. Confirmed by checking both squadrons' facilitator lists directly
afterward: both facilitators created during the test landed in the proxied squadron
(Wing A); the "target" squadron (Wing B) had zero. This is secure-by-design (the
server never trusts a client-supplied target ID for a privileged write) — recorded
here as a verified non-issue, not silently dropped after the initial 200 looked
suspicious.

## Source-level findings (Stage 2, carried forward as supporting evidence)

- `can_write_squadron` for `wing_admin` requires both `proxy_mode == "proxy"` **and**
  `acting_squadron_id == squadron_id` — an exact match against the currently-proxied
  squadron, not merely "any squadron in the proxied Wing."
- `POST /api/proxy/enter/{squadron_id}` itself rejects a `wing_admin` entering proxy on
  a squadron outside `p.wing_id` before a `ProxySession` row is ever created — a second,
  independent layer catching the same class of attempt even earlier.
- `can_write_activity` explicitly resolves authority from the target row's own
  `owning_level`/`wing_id`/`squadron_id` (fetched server-side), never from
  caller-supplied context — the source comment names ID-guessing as the exact threat
  this defends against.
- JWT verification pins the algorithm list from server config (`settings.JWT_ALG`), not
  from the token's own header — prevents algorithm-confusion attacks.
- Session revocation (`token_version` mismatch → 401) verified present in
  `get_principal`; matches `tests/test_session_revocation.py`.

## Outcome

No tenancy/IDOR defects found in this pass, across both automated (31 pre-existing +
6 new live tests) and manual source review. The one real gap found — cross-Wing IDOR
coverage being silently skipped by the existing stress tool for lack of test data — is
now closed with direct evidence rather than left as an untested assumption.
