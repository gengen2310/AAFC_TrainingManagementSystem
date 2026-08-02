# Final Findings Classification (Stage 13)

All findings from this engagement (`release/final-assurance-2026-08-01`), classified
per the instruction's own P0-Critical / P1-Release-Blocker / P2-Significant /
P3-Minor scheme. Full detail for each lives in
`docs/release/qualification_gap_register.md`.

## P0 / P1 — release-blocking severity

| ID | Finding | Status |
|---|---|---|
| GAP-18 | Production backup targeted the wrong physical database (SEV1) | **Fixed, proven live** (fresh backup+restore cycle matches production's real data) |
| GAP-24 | Stored XSS, multiple injection points, connected-frontend | **Fixed, proven live** (before/after browser reproduction, CSP checked and doesn't mitigate) |
| GAP-26 | Backend Dockerfile's unpinned postgresql-client (same class as GAP-16, different code path) | **Fixed by analogy to a proven pattern; not Docker-build-verified (no Docker in this environment)** |

Zero P0/P1 findings remain open. GAP-26 carries one explicit caveat (below).

## P2 — significant, fixed

| ID | Finding | Status |
|---|---|---|
| GAP-22 | Curriculum CSV import silently discarded the Foundation/Extension column | **Fixed, regression-tested** |
| — | Health endpoints leaked raw driver exception text (hostname, not credentials) | **Fixed, regression-tested** |
| — | `select-name` critical a11y violation, 2 confirmed instances | **Fixed, re-scanned clean** |

## P3 — minor, documented and deliberately not fixed this pass

| ID | Finding | Reason not fixed |
|---|---|---|
| GAP-23 | CEA import swallows per-row error detail | Small but real UX behaviour change, better bundled with a full CEA-workflow pass than rushed in isolation |
| GAP-25 | Business-date logic uses server clock, not an AU timezone | No canonical timezone concept exists yet in the codebase — a real design decision (single national tz vs per-Wing/Squadron), not mechanical |
| — | Color-contrast failures traced to AAFC VIG brand palette tokens (40-43 elements/page) | Official brand colours — a design/branding decision, not code owner's to change unilaterally |
| — | 83 remaining unlabeled `<select>` elements (2 of 85 fixed, confirmed via live scan) | Guessing labels for elements never live-scanned risks worse-than-nothing incorrect labels |
| — | No `<h1>` / landmark regions in `connected-frontend` | Whole-app semantic-structure gap, real but batched as a design/markup decision |
| — | `COOKIE_SAMESITE` value not validated by the fail-closed production config check | Needs a deliberate decision on scope (validate always vs. only when the cross-origin handoff feature is in use) |

## Explicitly re-confirmed as already-accepted residual risk (not re-litigated this pass)

| ID | Finding | Status |
|---|---|---|
| GAP-17 | 500-user/2-hour soak, two 5xx clusters (one explained, one not) | User already explicitly accepted this as residual risk in a prior pass — not reopened |

## Verification status of every fix

- **Backend**: full suite re-run clean after every change (1008 passed, 5 skipped,
  final confirmation this stage).
- **connected-frontend (GAP-24, select-name)**: live browser reproduction before
  and after, JS syntax re-validated after every edit.
- **GAP-18**: live backup+restore cycle with real data matching production.
- **GAP-22**: new regression test, full suite green.
- **GAP-26**: reasoned from Debian package-archive evidence and an already-proven
  identical fix elsewhere in this repo; **explicitly not build-verified** — flagged
  as the one open verification gap among all fixes this pass.

## Commits on this branch (chronological, `release/final-assurance-2026-08-01`)

All findings above were committed incrementally with individual messages
documenting evidence as work progressed — see `git log release/final-assurance-2026-08-01`
for the full sequence. No squashing performed; the commit history itself is part of
the audit trail.

## What remains before this branch could be considered for merge/deploy

1. **GAP-26 needs a real Docker build** to fully close (currently reasoned, not built).
2. **A genuinely distributed (multi-IP) load test** was never run in this program —
   inherited gap, not new, but real.
3. **A full manual DR drill** (human following `deployment/backup-dr.md`'s restore
   steps by hand) has not been performed — only the automated workflow has run.
4. The P3 items above are open by deliberate choice, not oversight — each has a
   documented reason.
5. Per this engagement's own non-negotiable boundary: **production deployment and
   merging this branch to `main` remain gated behind separate, explicit
   authorisation** — nothing above changes that.
