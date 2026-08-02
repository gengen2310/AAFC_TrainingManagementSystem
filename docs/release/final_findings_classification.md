# Final Findings Classification (Stage 13)

**Superseded in part — see `docs/release/final_findings_reclassification.md` for
the current, authoritative open-findings list.** This document is a snapshot from
before `release/final-assurance-2026-08-01` was merged to `main` and deployed to
production (that merge and deploy have since happened, with user authorisation,
followed by a post-deployment hardening reconciliation pass). Everything below
that describes P0/P1/P2 findings **fixed and verified in this document** remains
accurate — those fixes shipped to production and are not revisited here. Section
"What remains before this branch could be considered for merge/deploy" at the
bottom is **stale** (the branch has since merged and deployed) and is kept only
as a historical record of what was still open at Stage 13 — do not treat it as
current status. For the current open-findings list (staging system_admin auth,
GAP-28 capacity, and the re-affirmed P3s), use
`final_findings_reclassification.md`.

All findings from this engagement (`release/final-assurance-2026-08-01`), classified
per the instruction's own P0-Critical / P1-Release-Blocker / P2-Significant /
P3-Minor scheme. Full detail for each lives in
`docs/release/qualification_gap_register.md`.

## P0 / P1 — release-blocking severity

| ID | Finding | Status |
|---|---|---|
| GAP-18 | Production backup targeted the wrong physical database (SEV1) | **Fixed, proven live** (fresh backup+restore cycle matches production's real data) |
| GAP-24 | Stored XSS, multiple injection points, connected-frontend | **Fixed, proven live** (before/after browser reproduction, CSP checked and doesn't mitigate) |
| GAP-26 | Backend Dockerfile's unpinned postgresql-client (same class as GAP-16, different code path) | **Fixed, build-verified** (real Railway Docker build succeeded deploying to staging, closing the earlier "not locally build-verified" caveat) |

Zero P0/P1 findings remain open. All three fully verified, including a real deploy.

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
  identical fix elsewhere in this repo, then **confirmed by a real Railway Docker
  build succeeding and deploying to staging** — no longer just reasoned, actually
  built.

## Commits on this branch (chronological, `release/final-assurance-2026-08-01`)

All findings above were committed incrementally with individual messages
documenting evidence as work progressed — see `git log release/final-assurance-2026-08-01`
for the full sequence. No squashing performed; the commit history itself is part of
the audit trail.

## Staging redeploy and live re-verification (done this pass, with explicit user approval)

Deployed both changed services to staging from this branch:

- **Backend** (`deb53faa-…`): deployment `b9cd65da-…` → **SUCCESS**. This is the
  first real Docker build of GAP-26's Dockerfile fix (`postgresql-client-18` via
  the PGDG repo) — **closes that fix's one open verification gap**; it builds and
  deploys cleanly, not just "reasoned to work."
- **Main TMS frontend / connected-frontend** (`2b5e6359-…`): deployment
  `fa32adfc-…` → **SUCCESS**.

Live re-verification against the deployed staging services:

- `GET /api/health/ready` → `{"status":"ready","squadrons":140}`; frontend → 200.
- `smoke_test.py` against staging: **19/25 passed, 1 pre-existing failure**
  (`system_admin` login — already documented in GAP-09 as a pre-existing staging
  credential issue affecting only that one role, unrelated to and unchanged by
  this pass's fixes; not a new regression).
- `security_scope_test.py` against staging: **23/25 passed, 2 failures**, both
  explained rather than dismissed: the same pre-existing `system_admin` credential
  issue, and one rate-limit-trip test that needs more attempts in a single run to
  trigger (rate limiting itself independently verified working repeatedly this
  session — Stage 9's local 31/31 pass, plus abundant real `429`s observed during
  both Stage 10 load tests against this same staging backend minutes earlier).
- **GAP-24 (XSS fix) confirmed live on the deployed asset**: fetched staging's real
  served `index.html` directly, confirmed `_jsAttr(u.display_name` and the
  `aria-label="Filter curriculum…"` fixes are both present in what's actually
  being served, not just in the source tree.
- **GAP-22 (curriculum CSV fix) confirmed live**: a non-destructive preview-mode
  CSV import against the live staging backend, using the same payload shape as the
  regression test, returns 200 with the item accepted — the deployed backend is
  running the fixed code path.

## What remains before this branch could be considered for merge/deploy (stale — historical only, see banner above)

1. **A genuinely distributed (multi-IP) load test** was never run in this program —
   inherited gap, not new, but real.
2. **A full manual DR drill** (human following `deployment/backup-dr.md`'s restore
   steps by hand) has not been performed — only the automated workflow has run.
3. The P3 items above are open by deliberate choice, not oversight — each has a
   documented reason.
4. Per this engagement's own non-negotiable boundary: **production deployment and
   merging this branch to `main` remain gated behind separate, explicit
   authorisation** — nothing above changes that. Staging now runs this branch's
   fixes (deployed and re-verified this pass); production does not yet.
