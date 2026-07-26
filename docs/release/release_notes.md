# Release Notes — General Release Qualification Candidate

Release candidate: `feature/restore-planning-workspace` @ `c90b086`
Alembic head: `y8z9a0b1c2d3`
Target: PR #3 → `main`
Date: 2026-07-26

This document summarizes what changed in this qualification pass, for the benefit of
anyone reviewing the PR or the eventual production deployment. It is not a claim of
release readiness — see `general_release_readiness.md` for that.

## New features

- **TRGO-01 — Update future parade nights.** An explicit "Update future parade
  nights…" workflow (preview → confirm) lets a squadron admin move upcoming standard
  parade nights to a new day of the week without touching historical records or
  one-night exceptions. Detects holiday and duplicate-date conflicts before commit,
  requires a reason, and writes a full audit trail.
- **TRGO-02 — Unified inherited-activities view.** The Activities panel now shows
  national/wing/CEA/local activities and holidays together with source/owner/scope
  labels, and squadrons can locally hide an item or attach a note without altering the
  shared source record. The legacy, unreviewed CEA import pipeline is confirmed fully
  retired (no frontend caller, no stranded data).
- **TRGO-03 — Guided year setup, reachable at any time.** A new "Guided year setup…"
  toolbar action walks a squadron admin through creating a new planning year (or
  rolling over from the most recent one), applying a unit timing template, generating
  parade dates, and bulk-placing curriculum across multiple open slots at once — a
  second, non-drag-and-drop placement method alongside the existing click-to-schedule
  flow, enforcing the same conflict/locking/audit rules either way.
- **TRGO-05 — Governed facilitator CSV import.** A CSV template, preview-before-commit
  upload flow, duplicate detection (reusing the existing name-match logic), per-row
  override for genuine same-name-different-person cases, and formula-injection
  protection on imported cells.
- **TRGO-08 — Mission Backlog date-range filter.** The Mission Backlog panel gained a
  From/To date filter; unscheduled items are never hidden by it, since they have no
  date to filter on and still need attention regardless of the visible window.
- **TRGO-04/06/07 parity fixes.** The Learning Hub "missing link" filter and
  save-in-progress button feedback, previously fixed only in the legacy connected
  frontend, now also exist in the React Planning Workspace. The duplicate-facilitator
  warning in both frontends now has a working "Add anyway" path (it previously dead-
  ended once the backend's 409 fired).

## Fixes

- Facilitator CSV import and single-facilitator create share one duplicate-detection
  rule (case-insensitive first+last name match within the squadron).
- Corrected a stale documentation claim (`bcrypt` → the app's actual
  `pbkdf2_sha256` access-code hashing scheme).

## Known residual items (not blocking, tracked)

- CEA import consolidation's wing→squadron auto-inheritance for holidays/anchor events
  remains deferred — a product decision on the merge direction is needed first
  (`docs/release/qualification_gap_register.md`, GAP-02).
- `connected-frontend/index.html`'s checked-in `<meta name="aafc-api-base">` defaults to
  the production Railway backend rather than localhost, contradicting
  `RUN_TMS_CONNECTED_FRONTEND_MAC.sh`'s own comment. Deliberate in an earlier commit;
  flagged for an explicit owner decision (GAP-11).
- Per-modal accessibility specs (Update Future Parade Nights, Guided Year Setup,
  Facilitator CSV Import) were not added to `frontend/e2e/accessibility.spec.ts` this
  pass — the existing route-level coverage exercises the pages they live on, but no
  dedicated axe assertion targets the modals themselves (GAP-07).
- `connected-frontend` has no axe-based accessibility coverage at all (pre-existing).

## Database

40 Alembic migrations, verified against a disposable local PostgreSQL 16 instance this
pass: clean fresh-to-head apply, idempotent re-run, full downgrade-to-base and
re-upgrade round-trip, all with a single consistent head. No new migration was added in
this pass — all TRGO work reused existing schema and endpoints.

## Upgrade notes

No manual data migration is required. `alembic upgrade head` is sufficient. No
environment variables were added or changed.
