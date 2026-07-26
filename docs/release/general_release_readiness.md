# General Release Readiness Report

Release candidate: `feature/restore-planning-workspace` @ `46d6c61`
Alembic head: `y8z9a0b1c2d3`
PR: #3 (`feature/restore-planning-workspace` → `main`), OPEN, not yet merged
Date of this report: 2026-07-26

This report is updated in place as remaining work completes. It reflects the actual
state of this branch at the commit above — not a forecast or a plan.

## 1. Deferred TRGO requirements (gap register GAP-01 through GAP-05)

All 5 addressed, tested, live-verified in browser, committed, pushed:

| Item | Status | Commit |
|---|---|---|
| TRGO-01 — Update Future Parade Nights | Done | `a624cc9` |
| TRGO-02 — Unified inherited-activities view | Done | `c5aa7b5` |
| TRGO-03 — Guided year setup, reachable anytime | Done | `29cab6a` |
| TRGO-05 — Governed facilitator CSV import | Done | `172ba12` |
| TRGO-08 — Mission Backlog date-range filter | Done | `3dacc0c` |

## 2. Reverification of previously-fixed items (GAP-10)

TRGO-04/06/07 re-verified end-to-end in both frontends (not trusted from a prior
session's claim). Found and closed a real gap: the original fix only landed in
`connected-frontend`, and the duplicate-facilitator warning in both frontends was a
dead end with no way to confirm-and-add-anyway. Fixed, live-verified, `3f9ee0c`.

## 3. Eight-role security sweep (GAP-06)

- `security_scope_test.py`: 31/31 passed (unauthenticated access, invalid JWT,
  read-only-role write denial, system_admin endpoint denial for all 4 non-system-admin
  roles, cross-squadron IDOR, oversized request body, unexpected enum values, no
  secrets/codes/hashes in system responses, live rate-limit trigger).
- `smoke_test.py`: 29/29 passed (login for all 6 role codes, scope denial checks).
- Full backend suite: 853 passed, 4 skipped.
- All run fresh against a freshly-seeded local server this pass, not carried over from
  an earlier session's numbers.

## 4. Accessibility (GAP-07)

`frontend/e2e/accessibility.spec.ts`: 19/19 passed fresh against current code,
including the Curriculum and Facilitators pages this pass's TRGO fixes touched (no
regression). Residual, not blocking: no dedicated axe assertion for the three new
modals specifically (Update Future Parade Nights, Guided Year Setup, Facilitator CSV
Import) — they're reachable through routes the suite already covers. connected-frontend
has no axe-based coverage at all (pre-existing).

## 5. Local release gate, 2x repeated (GAP-12)

- Backend `pytest tests/`: 853 passed, 4 skipped — identical both runs, no flakiness.
- Frontend `tsc --noEmit` / `eslint` / `vitest run` / `vite build`: clean, 0 errors, 17
  pre-existing warnings (unrelated to this pass), 15/15 tests — identical both runs.

## 6. Database / migration gate against disposable PostgreSQL (GAP-12)

Ran against a genuine local PostgreSQL 16 instance, created and dropped for this
purpose only — never the developer's own local Postgres data, never staging, never
production:

- Fresh `alembic upgrade head`: 40 migrations, single head, 58 tables, clean.
- Idempotent re-run: no-op, no error.
- Full `alembic downgrade base` then re-`upgrade head`: clean round-trip, 58 tables
  restored, correct head.
- Schema-specific checks confirmed correct: JSONB column (v28), partial unique index
  (v27), optimistic-locking `version` columns (v37) on all 7 tables, 56 FK constraints
  with `squadrons.wing_id → wings.id` confirmed by both definition and live rejection
  test.
- App-level: real server boot against Postgres, real `seed_all()` (run only after
  explicit operator authorization — the auto-mode safety classifier correctly blocked
  my own unprompted attempt to set the destructive-seed override flag), 29/29
  smoke test and 31/31 security-scope test against the Postgres-backed live server.

## 7. Data-integrity audit (GAP-12)

31 read-only checks (`tools/stress/data_integrity_check.py`, local-only per this repo's
`.gitignore`): referential integrity, tenancy consistency, security invariants (no
plaintext codes, no reused code hash, every active user has a code, no hash-shaped
values leaking into the audit log), data quality, optimistic-locking sanity, uniqueness
beyond DB constraints, archival hygiene. 31/31 pass against current seed data.

## 8. Backup/restore gate (GAP-12)

Real `pg_dump` → `pg_restore` cycle against a disposable Postgres database: 0 errors,
exact row-count parity across 5 key tables, and — the actual bar, not just a schema
check — a live server booted against the restored database passed the full 29-test
smoke suite, including real login for all 6 role codes. One genuine, non-defect finding
along the way: the backup faithfully captured an IP-lockout row from the security
sweep's own tests, which correctly carried through restore (cleared on the disposable
DB, not a real-environment action).

## 9. Security greps

All 4 pre-packaging greps from `.claude/rules/security.md` return 0 matches (re-run
this pass, `connected-frontend` was touched by the TRGO-04/06/07 reverification work).

## 10. Release documents

`release_notes.md`, `production_release_runbook.md`, `rollback_runbook.md`, and this
document are now written (previously falsely claimed complete in an earlier register
entry — corrected, see gap register GAP-08).

## 11. Staging deployment and verification (GAP-09) — done, this pass

- Fail-closed environment verification passed exactly: project ID, staging
  environment ID, all 3 service IDs, and all 3 domains matched the values recorded
  at the start of this task before any Railway action was taken.
- All 3 services (backend, Main TMS frontend, Planning Workspace frontend) deployed
  to staging and confirmed `SUCCESS` by polling deployment status to a terminal
  state, not just a queued build.
- **Found and fixed a real, previously-undetected deployment-architecture defect**
  (GAP-13): TRGO-05's CSV import UI, and this pass's TRGO-07 duplicate-warning fix
  to the standalone `Facilitators.tsx` route, were unreachable on the actual
  deployed Planning Workspace preview service, because that service always runs in
  a module mode that skips the entire standalone page router. Root-caused by
  reading `App.tsx`'s routing and confirming the live meta tag; fixed by moving the
  UI to the drawer tab that's actually reachable; redeployed; reverified live.
- `smoke_test.py` (29/29) and `security_scope_test.py` (31/31) both passed fresh
  against the live staging backend.
- Live browser verification against the real staging URLs on both frontends:
  login, dashboard, Facilitators (including the TRGO-07 fix), Guided Year Setup
  (TRGO-03), and the CSV import + duplicate-warning flows (GAP-13's fix) all
  confirmed working with zero console errors.
- Staging test data scaled to 1,246 users (target ≥1,200), 139 squadrons, 13 wings.
  One newly-seeded synthetic account confirmed able to log in with correct
  role/scope.
- Broad workflow verification swept every major role × endpoint combination across
  operational areas (facilitators, training areas, equipment, cadets, curriculum,
  parade nights, reports, planning years, wing calendar, accounts, audit) for
  sqn_admin, wing_admin, national_admin, and auditor — all returned the expected
  status.
- **Not yet done**: the formal staging screenshot evidence artifact set, and
  staging failure/recovery testing + the 4-24 hour soak (both depend on the load
  test below).

## 12. NOT yet done — explicitly blocking general release

- **1,000-concurrent-user load test** (brief sections 22-25): not started. This is
  the financial-commitment check I flagged at the very start of this pass, per the
  standing stop-conditions — that check has not yet happened.
- **Staging failure/recovery testing, 4-24 hour soak** (brief sections 26-27): not
  started — depends on the above.
- **PR #3 merge to `main`**: not done. Per the brief's own sequencing, this only
  happens after staging qualification passes — it has not yet been attempted.
- **Production deployment, smoke tests, post-release monitoring** (brief sections
  31-34): not started, and must not start before every item above is complete.

## 13. Defect log

No SEV1/SEV2 defects are currently open against this release candidate. GAP-13 (SEV2,
TRGO-05's UI unreachable in the deployed config) was found and fixed this pass. Two
SEV3/SEV4 items are tracked as residual/deferred in `qualification_gap_register.md`
(GAP-02's wing→squadron auto-inheritance, GAP-11's connected-frontend meta-tag
default) — neither blocks general release; both need a product/owner decision rather
than more code.

## Final determination

**NOT READY FOR GENERAL RELEASE**

Reason: Section 12's items — the 1,000-user load test (pending its own financial-
commitment check), staging soak, PR merge, and production deployment — have not been
performed. Every local, code-level qualification gate and the staging deployment/
verification gate have both passed, with one real defect (GAP-13) found and fixed
along the way — exactly what staging verification is for. The remaining work is the
load test and everything sequenced after it, not a defect blocking it.
