# General Release Master Checklist

Release candidate: `feature/restore-planning-workspace` @ `297270c`
Alembic head: `y8z9a0b1c2d3`
Date of this pass: 2026-07-27

This consolidates the **local, code-level** qualification work completed early in this
session (Sections 1-9 below), as a historical record of that phase. **Superseded for
staging/load/production status**: the standing boundary Section 8 refers to was later
explicitly superseded by the user in chat, and staging deployment, load/soak testing,
a rollback drill, and production backup/restore verification were all subsequently
performed — see `general_release_readiness.md` for the authoritative, current status
and final determination. Do not treat this document's Section 8/9 as current.

---

## 1. Defects fixed this pass

All five, each with root-cause analysis, a regression test confirmed failing before the
fix and passing after, and live in-browser verification where UI-facing. Full detail in
each commit and in `docs/beta/15_known_limitations.md`.

| ID | Summary | Commit |
|---|---|---|
| DEFECT-001 | Training Phase permission model — wing/national admin could create squadron-scope phases without Proxy/Delegated Intervention | `ddbf649` |
| DEFECT-002 | `term`/`recommended_term` number-vs-string contract — real UI bug (not test-only, contrary to prior doc claim), plus a related double-prefix display bug | `0bbae86` |
| DEFECT-003 | `reports.spec.ts` flaky tests — timing race + wrong-table locator bug | `bb3c7c7` |
| DEFECT-004 | Rate-limiter test instability — CORS preflight silently halving the production rate-limit budget (real bug, not test-only) + deterministic reset infrastructure | `6983e84` |
| DEFECT-005 | CEA import consolidation — retired legacy pipeline, closed a `classify` permission gap; wing→squadron auto-inheritance deliberately deferred (specific blocker documented) | `23de010`, `a8ec56f` |

## 2. TRGO user-feedback items traced

All 8 investigated against current code; 3 fixed, 5 deferred with a specific, recorded
reason (not silently dropped). Full detail: `docs/release/trgo_review_traceability.md`.
Commit: `00825cc`.

## 3. Backend test suite

- 823 passed, 4 skipped, 0 failed — confirmed stable across 2 consecutive full runs.
- Includes 24 new regression tests added this pass across `test_rate_limiting.py`,
  `test_system_admin.py`, `test_cea_consolidation.py`, `test_trgo_items.py`.
- Command: `cd backend && source .venv/bin/activate && python -m pytest tests/ -q`

## 4. Frontend test suite

- `frontend/e2e/` (React Planning Workspace): 87/87 passed, single worker, fresh seed.
- `frontend/e2e-connected/main-tms.spec.ts` (connected-frontend): 12/12 passed, single
  worker, fresh seed.
- `frontend/e2e-connected/capture-screenshots.spec.ts` intentionally excluded — its own
  header documents it as one-off evidence capture against live staging, not part of the
  local verification suite (confirmed in an earlier pass this session).
- `tsc --noEmit`, `eslint`, `vitest` (15/15), `vite build`: all clean, 0 errors. 17
  pre-existing warnings unrelated to this session's changes (unused-var / react-hooks/
  react-refresh lint rules, not correctness issues).

## 5. Database / migration gate

Ran against a genuine disposable PostgreSQL 16 database (`aafc_migration_gate_test`,
local Homebrew install, created and dropped within this session — the pre-existing
`aafc_tms` Postgres database on this machine was never touched):

- `alembic upgrade head` from empty → `y8z9a0b1c2d3`: clean, single head, 58 tables
  created, no errors.
- `seed_all()` (blocked by `check_destructive_reset_allowed()`'s fail-closed guard until
  `ALLOW_DESTRUCTIVE_SEED=true` was explicitly set — confirmed this safety mechanism
  works correctly against a non-SQLite target): succeeded.
- Functional smoke test: real uvicorn against the Postgres DB, real login, 6 authenticated
  GETs (5× 200, 1× correctly-denied 403 for a role-gated endpoint) — matches the same bar
  the existing backup/restore workflow already uses.
- Spot-checked a Postgres-specific migration (`facilitators.subject_areas` JSONB, v28):
  round-tripped correctly through a real API create+read.
- Verified this session's two new endpoints (`reset-rate-limits`, the retired
  `import-cea` 410) also behave correctly against Postgres, not just SQLite.
- **Observation, not a defect**: `reset_db()`'s `Base.metadata.drop_all/create_all` does
  not touch Alembic's own `alembic_version` bookkeeping table (it's outside SQLAlchemy's
  metadata registry) — `CLAUDE.md`'s note that this table "will be gone" after a reset is
  imprecise for the Postgres case specifically (it likely originates from the common local
  workflow of deleting the SQLite file first, which does wipe it). Re-stamping after a
  reset remains a safe habit regardless; worth a small doc correction, not fixed here as
  it's outside this pass's scope.
- **Not done in this pass**: a full CI-equivalent migration-chain test (down-migrations,
  concurrent-writer behavior under PostgreSQL's actual MVCC semantics vs SQLite's, a true
  production-data-volume load). This was a correctness/compatibility gate, not a
  performance or concurrency gate.

## 6. Data integrity

Direct SQL spot-checks against the fully-seeded local dataset (16 squadrons, users/access
codes, curriculum, 703 demo data): 0 orphaned rows across users/access_codes/facilitators/
sessions/parade_nights/curriculum_items/squadrons/audit_logs/cea_activities, 0 duplicate
active access codes per user. All 10 checks passed.

## 7. Security

The four pre-packaging greps from `.claude/rules/security.md`, all return 0 matches:
removed-wording check, access-code-exposure check, seeded-codes-in-frontend check,
secrets-in-frontend check.

**Not independently re-run as a dedicated document in this pass**: the full 8-role
permission matrix sweep, a dedicated accessibility audit pass, and a live backup/restore
drill. These have established, previously-verified mechanisms documented elsewhere in
`docs/beta/` (accessibility: Phase 7's 19-route axe-core coverage; backup/restore: the
existing daily-backup/weekly-restore workflow, verified at the application level per
`docs/beta/15_known_limitations.md` and this repo's `.github/workflows/`) — this pass
did not re-derive or re-verify those from scratch, and this document does not claim it did.

## 8. Superseded — see `general_release_readiness.md`

The standing boundary this section originally described (staging deployment, load
testing, and production deployment all pending separate explicit go-ahead) was
explicitly superseded by the user later in this same qualification pass. All of those
were subsequently performed, with full results, root-cause analysis, and explicit
user acceptance of the real findings surfaced along the way, documented in
`qualification_gap_register.md` and `general_release_readiness.md`. This section is
kept as a historical record of this document's original, local-only scope — it is not
a current statement of what remains undone.

## 9. Working tree state (as of this document's original local-gate pass)

Historical: clean at the time Sections 1-7 were completed. For current working-tree
and push/PR state, see `general_release_readiness.md`'s header and
`qualification_gap_register.md`'s Section 1 state-confirmation entries.
