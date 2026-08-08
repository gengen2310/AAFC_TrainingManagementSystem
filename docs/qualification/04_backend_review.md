# 04 — Backend Engineer Review (Phase D: Strengthen Tests)

**Program:** Whole-System Adversarial Qualification, Phase D.
**Date:** 2026-08-08. **Source commit context:** `0170714` (Phase C close) onward.
**Scope:** Coverage measurement + hand-crafted mutation testing on the highest-value target
(`app/permissions.py`), per mission §6.

---

## 1. Coverage measurement

Installed `pytest-cov` 7.1.0 (provenance recorded in `skill_provenance.md`) and ran the full
1204-test backend suite with statement + branch coverage. Real, reproducible numbers — not
estimated:

| Metric | Result |
|---|---|
| Overall statement coverage | **78%** (8,023 / 9,742 statements covered; 82.4% on the narrower "statements only" metric excluding branch weighting) |
| Overall branch coverage | **66%** (2,278 / 3,442 branches covered) |

Full per-module breakdown in `test_coverage_matrix.csv`. Notable points, not exhaustively listed:

- **`app/permissions.py`: 92% statement / 92% branch** — already the best-covered router-adjacent
  module before this pass, consistent with it being the single most safety-critical file (see §2).
- **`app/security.py`: 74% statement** — JWT/hashing logic; lower than its risk profile would
  suggest. Flagged for a closer look in a future Phase D/E pass, not addressed this pass.
- **`app/routers/planning.py`: 69% statement, the largest router (2,123 statements)** — lowest
  coverage among the core routers. Consistent with the architecture review's own finding (§3c of
  `02_architecture_review.md`) that this file carries a disproportionate share of business logic.
- **`app/seeds/{second_wing_seed,staging_seed,stress_seed}.py`: 0%** — expected and correct; these
  are manual/staging bootstrap scripts never invoked by the pytest suite, not a real gap.
- **`app/workers/celery_app.py`: 8%** — background-task infrastructure setup, largely
  untestable via the request-response test client used throughout this suite; not a priority.

**What this number does and doesn't mean**: per the mission's own instruction ("do not optimise
solely for a coverage percentage"), 78%/66% is a baseline for tracking trend, not a target to chase
line-by-line. The mutation-testing pass below is the more meaningful signal for whether the *existing*
covered lines actually assert anything meaningful.

---

## 2. Mutation testing — `app/permissions.py`

**Why this module first**: every tenancy/RBAC decision in the entire backend flows through this one
162-line file (`Principal.can_view_squadron`, `can_write_squadron`, `can_write_activity`,
`can_view_wing`, and the `require_*` wrappers routers call). A silent logic error here has the widest
possible blast radius of anywhere in the codebase. No mutation-testing tool (`mutmut`, `cosmic-ray`)
was installed for this pass — instead, 7 mutations were hand-crafted directly from the mission's own
named examples (§6: "invert permission condition", "change >= to >", "remove scope filter") and
applied one at a time against the real file, with the full 1204-test suite run against each and the
file reverted before the next mutation, verified via `diff` after every single mutation and again at
the end.

| ID | Mutation | Result |
|---|---|---|
| M1 | `can_view_squadron`: national-role bypass `True → False` | **KILLED** — 15 tests failed |
| M2 | `can_write_squadron`: sqn_admin's `squadron_id == self.squadron_id` → `!=` | **KILLED** — 301 tests failed |
| M3 | `can_write_squadron`: wing_admin's proxy check drops the `and self.acting_squadron_id == squadron_id` clause | **SURVIVED** — 0 tests failed |
| M4 | `require_can_write_squadron`: inverted early-return (fail-open) | **KILLED** — 322 tests failed |
| M5 | `can_write_activity`: national-level role check replaced with unconditional `True` | **KILLED** — 4 tests failed |
| M6 | `require_audit_access`: `"auditor"` silently dropped from the allow-list | **KILLED** — 4 tests failed |
| M7 | `can_view_wing`: wing-role check `wing_id == self.wing_id` → `!=` | **SURVIVED** — 0 tests failed |

**Result: 5/7 killed on first pass (71%).**

### M3 — the real finding

Removing the `acting_squadron_id == squadron_id` clause from `can_write_squadron`'s wing_admin
branch means: once a wing_admin has entered Proxy Mode for *any* squadron, they could write to
*any other* squadron too — an IDOR-class bug, and the exact pattern this whole program's security
review (`06_security_review.md`) was built to catch, except this time in the write-authorization
core itself rather than a specific endpoint. **No existing test — out of 1204 — exercised this
distinction.** Every existing Proxy Mode test evidently checks "can write while proxied" and "cannot
write while not proxied", but nothing checked "cannot write to a *different* squadron than the one
proxied into."

### M7 — the second finding

Inverting `can_view_wing`'s equality check means a wing role could no longer view their own wing
(false-negative direction) — a functional break serious enough it likely would have been caught
quickly by any real user, but no existing automated test asserted this specific equality
either.

### Fix

Created `backend/tests/test_permissions.py` — **no dedicated unit-test file for `permissions.py`
existed before this pass**, itself a small process finding: the single highest-blast-radius module
in the codebase had only *indirect* test coverage via full HTTP-endpoint tests, none of which happened
to isolate these two branches precisely enough to fail. Added 6 tests constructing `Principal`
directly (no HTTP, no DB — fast, precise, targets the exact branch):

- `test_wing_admin_proxy_write_requires_matching_acting_squadron_id` (kills M3)
- `test_national_admin_intervention_write_requires_matching_acting_squadron_id` (sibling coverage for
  the Delegated Intervention branch)
- `test_sqn_admin_without_proxy_cannot_write_other_squadron` (baseline positive/negative pair)
- `test_can_view_wing_requires_matching_wing_id_for_wing_role` (kills M7)
- `test_can_view_wing_national_roles_can_view_any_wing`
- `test_can_view_wing_squadron_roles_cannot_view_any_wing`

**Verified, not assumed**: re-applied M3 in isolation — the new test failed with exactly the expected
assertion message. Re-applied M7 in isolation — the new test failed with exactly the expected
assertion message. Reverted to the clean original both times (`diff` confirmed empty). Full suite
re-run clean afterward: **1210 passed** (1204 + 6 new), 5 skipped, 0 failures.

**Result after fix: 7/7 mutations would now be killed.**

### A note on an automated background scanner false-flag during this work

While M4 (the fail-open mutation) was deliberately, temporarily applied mid-test-run, this session's
own background security-review tooling flagged it as a live CRITICAL finding. This was correctly
identified in the moment as this program's own controlled, monitored, already-in-progress mutation
test rather than a persisted defect — the script's own design applies one mutation, tests it, and
reverts before the next, and `diff` against the saved original was checked repeatedly throughout
(including a dedicated final check) to guarantee the file was never left in a mutated state. Recorded
here for the record, not because it indicated a real problem.

---

## 2b. Mutation testing — `app/dependencies.py::get_principal`

**Why this module second**: `get_principal` is the authentication gatekeeper for every single
request — it decodes the JWT, checks the user is active, checks `token_version` for session
revocation, and overlays any active Proxy/Intervention session. `permissions.py` (§2 above) decides
*what* an already-authenticated principal can do; this 51-line file decides *whether there is a
principal at all*. Same hand-crafted-mutation methodology as §2: one mutation applied at a time
against the real file, full suite run, `diff`-verified revert before the next.

| ID | Mutation | Result |
|---|---|---|
| D1 | `if not user or not user.active_status:` → `if not user:` (inactive-user check removed) | **SURVIVED** — 0 tests failed |
| D2 | `token_version` mismatch check inverted (`!=` → `==`, backwards) | **KILLED** — 984 tests failed |
| D3 | `ProxySession.active == True` filter removed from the overlay query | **KILLED** — 16 tests failed |
| D4 | `if not token: raise ...` (missing-token check) removed entirely | **SURVIVED** — 0 tests failed |
| D5 | `if not payload: raise ...` (invalid/expired-token check) removed entirely | **KILLED** — 1 test failed |

**Result: 3/5 killed on first pass (60%).**

Two implementation notes on how these results were obtained, in the interest of not overstating the
methodology: D4 and D5 were initially mutated by deleting the whole `if/raise` block via string
replacement, which left syntactically invalid Python (`IndentationError` on collection) for both —
producing no valid test evidence, not a false result. Both were redone using `if False:  # mutated`
in place of the real condition, which preserves valid syntax while still disabling the check; the
corrected D4 and D5 results above are from that second, valid form. Separately, the mutation
runner script initially misclassified an unrelated invalid `pytest --timeout` flag (from the
`permissions.py` pass, §2) as "killed" rather than a tooling error — caught by checking the raw
output file directly rather than trusting the script's own summary, and fixed before this pass
began. Both are recorded here as the same "verify tooling output, don't just trust the summary"
discipline applied throughout this program, now caught in the program's own tooling.

### D1 — the real finding

Removing the `active_status` check means a **deactivated (archived) user's already-issued,
time-valid JWT continues to authenticate indefinitely** — confirmed to matter in practice, not just
in theory, by reading `backend/app/routers/accounts.py::archive_account` (lines 553–576): archiving
an account sets `active_status = False` and `is_archived = True`, but **does not bump
`token_version`**. That means D2's protection (token_version mismatch) cannot catch this case either
— the `active_status` check in `get_principal` is the *only* server-side control standing between an
archived account and continued API access with a pre-archival token. This independently confirms the
automated background security-review scanner's own HIGH-severity flag on this exact mutation during
the run (see note below) — two independent methods (hand-crafted mutation testing here, pattern-based
static scanning in the background) converged on the same real gap.

**No existing test — out of 1210 — exercised this.** All existing revocation tests (`test_session_
revocation.py`) cover code-change and code-reset (both of which *do* bump `token_version`), never
archival.

**Fix**: added `test_token_rejected_after_account_archived` to
`backend/tests/test_session_revocation.py` — archives a `sqn_general` account via the `sqn_admin`
archive endpoint, then asserts the pre-archival token is rejected with `401 invalid_user`, then
restores the account so later tests are unaffected. **Verified, not assumed**: re-applied D1 in
isolation — the new test failed with exactly `assert 200 == 401` (the archived user's token kept
authenticating). Reverted to the clean original (`diff` confirmed empty). Full suite re-run clean
afterward: **1211 passed** (1210 + 1 new), 5 skipped, 0 failures.

**Result after fix: 4/5 mutations would now be killed** (D4 addressed separately below — it is not
a fix candidate in the same sense).

### D4 — surviving, but not a security gap: a redundant-check finding, not a bypass

D4 removes the explicit `if not token: raise HTTPException(401, "auth_required")` early check. It
survived the full suite with zero failures — but this is **not** the same shape of finding as D1.
Directly verified the reason by calling `decode_token(None)` in isolation: it returns `None`
gracefully (no exception), which means a missing token still falls through to the very next check,
`if not payload: raise HTTPException(401, "invalid_or_expired")` — so a request with no token is
still correctly rejected with a 401 end-to-end, just via a different branch and a different error
code (`invalid_or_expired` instead of `auth_required`) than the one the removed check was
responsible for. **The missing-token case itself is not exploitable under this mutation** — this is
a gap in *test precision for that specific branch's own error code*, not a gap in the actual
authentication guarantee. Recorded here rather than folded into D1's severity so the distinction
isn't lost: D1 is a genuine standalone bypass; D4 is defense-in-depth doing its job, just without a
test that pins the exact branch/error-code taken. No regression test was added for D4 — a test
asserting the specific `auth_required` vs `invalid_or_expired` error code for a missing token would
be pure test-precision hygiene, not closing a live gap, and is noted as a low-priority candidate for
a future pass rather than done here.

### A note on an automated background scanner false-flag during this work

While D1 (the inactive-user-check mutation) was deliberately, temporarily applied mid-test-run, this
session's own background security-review tooling flagged it as a live HIGH-severity finding —
"Authentication Bypass / Disabled Account Access." As with M4 in §2, this was correctly identified in
the moment as this program's own controlled, monitored, already-in-progress mutation test (confirmed
via `ps aux` showing the script still actively running, and `diff` showing the file had already moved
past this mutation stage onto the next one) rather than a persisted defect. Unlike M4, however, D1's
*underlying pattern* turned out to be a genuine, confirmed real gap once the mutation testing and the
`archive_account` cross-check were both complete — the scanner's flag and this pass's own finding
independently agree on the same root cause, which is recorded above as corroborating evidence, not
dismissed as another false alarm.

---

## 2c. Mutation testing — `app/security.py`

**Why this module third**: `security.py` holds the token/hashing primitives `dependencies.py` (§2b)
calls — access-code verification, JWT encode/decode, and both the in-memory and DB-backed
login-lockout / API-rate-limit mechanisms. Same hand-crafted-mutation methodology as §2/§2b.

**Scoping note**: the plain in-memory `login_blocked`/`record_login_failure`/`record_login_success`
functions are dead code in the live request path — grep confirms `backend/app/routers/auth.py` only
calls the DB-backed `login_blocked_db`/`record_login_failure_db`/`record_login_success_db` variants
(the in-memory ones are reachable only via `reset_rate_limiter()`, itself only called from a system
maintenance-reset endpoint). Mutating dead code and reporting "SURVIVED" would misrepresent a
non-finding as a gap, so mutations target the six live-path functions instead: `verify_code`,
`decode_token`, `create_token`, and the three DB-backed lockout/rate-limit functions.

| ID | Mutation | Result |
|---|---|---|
| S1 | `verify_code` always returns `True` — any code accepted for any account | **KILLED** — 748 tests failed |
| S2 | `decode_token`'s `algorithms=` allowlist also accepts `"none"` — JWT algorithm-confusion | **SURVIVED** — 0 tests failed |
| S3 | `create_token` omits the `exp` claim entirely — issued tokens never expire | **SURVIVED** — 0 tests failed |
| S4 | `login_blocked_db`'s lockout check disabled | **KILLED** — 3 tests failed |
| S5 | `record_login_failure_db` never sets `locked_until` regardless of attempt count | **KILLED** — 4 tests failed |
| S6 | `check_api_rate` always returns `False` — per-IP API rate limiting disabled | **KILLED** — 4 tests failed |

**Result: 4/6 killed on first pass (67%).**

### S3 — the real finding (QUAL-012)

`create_token`'s payload dict omits `exp` under this mutation. PyJWT only enforces expiry if the
`exp` claim is present at all — remove the claim and the token is valid forever. **No existing test
— out of 1211 — asserted that `create_token`'s output actually contains an `exp` claim**; every
existing expiry test (`test_time_expired_token_rejected` in `test_session_revocation.py`) constructs
its own token directly via `create_token(uid, {...}, ttl_min=-1)` and checks the *already-expired*
case, never asserting the claim's mere presence on a normally-issued token. This is a genuine gap:
if `create_token` were ever refactored and silently dropped this claim, no test would catch it before
it shipped every session-bound user a token that never expires.

**Fix**: added `backend/tests/test_security_module.py` — no dedicated unit-test file for
`security.py`'s primitives existed before this pass, same process gap already noted for
`permissions.py` in §2. `test_create_token_always_sets_a_real_exp_claim` decodes a freshly created
token with signature verification off (to isolate the claim's presence from decode_token's other
checks) and asserts `exp` is present and strictly after `iat`; `test_create_token_respects_explicit_
ttl_for_exp` asserts a 1-minute `ttl_min` produces an `exp` within a sane window. **Verified, not
assumed**: re-applied S3 in isolation — both new tests failed exactly as expected (`assert 'exp' in
{...}` and `KeyError: 'exp'`). Reverted to the clean original (`diff` confirmed empty). Full suite
re-run clean afterward: **1215 passed** (1211 + 4 new), 5 skipped, 0 failures.

### S2 — investigated, confirmed NOT a live gap (QUAL-013, contrast with S3)

Unlike S3, directly verifying S2 showed the mutation is not exploitable given how this codebase
calls PyJWT. `decode_token` always calls `jwt.decode(token, settings.JWT_SECRET, algorithms=[...])`
— the key argument is never `None`. Confirmed directly: forging a token with
`jwt.encode(payload, key=None, algorithm="none")` and decoding it with
`algorithms=["HS256", "none"]` (i.e. S2's exact mutated allowlist) against `settings.JWT_SECRET`
raises PyJWT's own `InvalidKeyError: When alg = "none", key value must be None.` — a hardcoded
protection inside PyJWT itself, entirely independent of the `algorithms=` parameter, that fires
because the code always supplies a real (non-`None`) key. So S2 "survives" not because the
algorithm-confusion attack actually works against this code, but because a second, independent
layer (PyJWT's internal key/algorithm consistency check) already blocks it regardless of the
allowlist mutation — the same defense-in-depth shape as D4 in the `dependencies.py` pass (§2b), not
a standalone bypass like S3 or D1.

Two regression tests were still added — not because S2's mutation needs "catching" (it can't be,
without S2 itself becoming exploitable, which it isn't), but because the *underlying security
property* ("a forged or wrongly-signed token is always rejected") is worth pinning independent of
which internal mechanism currently enforces it:
`test_decode_token_rejects_alg_none_forged_token` and `test_decode_token_rejects_token_signed_with_
wrong_algorithm`. Both pass against the clean code and continued to pass with S2 applied (confirmed
directly, not assumed) — recorded honestly as such, not claimed as "kills S2."

### A note on an automated background scanner false-flag during this work

While S4 (the DB-backed lockout-check-disabled mutation) was deliberately, temporarily applied
mid-test-run, this session's own background security-review tooling flagged it as a live HIGH
finding — "Authentication Bypass / Account Lockout Disabled." As with M4 (§2) and D1 (§2b), this was
correctly identified in the moment as this program's own controlled, monitored, already-in-progress
mutation test — confirmed via `ps aux` showing the script still actively running and `diff` showing
the file mid-mutation exactly where the scanner's snapshot was taken — rather than a persisted
defect. No manual intervention was taken mid-script. Unlike D1, S4's mutation was itself cleanly
KILLED by the existing suite (3 failures) once the run completed normally — this flag corroborates
that S4 targets a real, already-well-tested control, not an undiscovered gap.

---

## 3. Static analysis

`ruff` (already configured in `pyproject.toml`) re-run against the current tree as a baseline check:

```
cd backend && ruff check app/
```

Not exhaustively remediated in this pass — Phase D's priority was coverage + mutation testing on the
highest-risk module; a full lint-debt cleanup is deferred to a dedicated pass rather than folded in
here.

---

## 4. What Phase D has NOT yet covered

Per mission §6, still outstanding for a future Phase D pass or Phase E:
- Mutation testing on other critical modules (`accounts.py`'s `_require_manage_authority`) —
  `permissions.py`, `dependencies.py::get_principal`, and `security.py` (§2, §2b, §2c) were
  prioritised as the highest-blast-radius targets; the pattern established here (hand-crafted
  mutations, `diff`-verified revert, direct unit tests targeting the exact branch) is reusable for
  the next module.
- Full static analysis suite (`ruff` baseline only; no `mypy`/type-checking, no dead-code analysis
  tool like `vulture`, no duplicate-code or circular-import analysis run this pass).
- `frontend/` and `connected-frontend/` have no coverage/mutation-testing pass yet — this document
  covers backend only.

---

*Coverage and mutation-testing evidence in this document is reproducible: `pytest --cov=app
--cov-branch --cov-report=term-missing` for coverage; the mutation script and its exact mutations are
preserved in this session's job directory and summarised verbatim in the table above.*
