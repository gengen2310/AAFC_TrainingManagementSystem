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
- Mutation testing on other critical modules (`security.py`, `dependencies.py::get_principal`,
  `accounts.py`'s `_require_manage_authority`) — `permissions.py` was deliberately prioritised as the
  single highest-blast-radius target; the pattern established here (hand-crafted mutations from the
  mission's own examples, `diff`-verified revert, `test_permissions.py`-style direct unit tests) is
  reusable for the next module.
- Full static analysis suite (`ruff` baseline only; no `mypy`/type-checking, no dead-code analysis
  tool like `vulture`, no duplicate-code or circular-import analysis run this pass).
- `frontend/` and `connected-frontend/` have no coverage/mutation-testing pass yet — this document
  covers backend only.

---

*Coverage and mutation-testing evidence in this document is reproducible: `pytest --cov=app
--cov-branch --cov-report=term-missing` for coverage; the mutation script and its exact mutations are
preserved in this session's job directory and summarised verbatim in the table above.*
