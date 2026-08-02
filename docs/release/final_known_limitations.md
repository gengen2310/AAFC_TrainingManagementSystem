# Final Known Limitations (Post-Deployment Reconciliation)

New document, requested explicitly in the reconciliation instruction. A single,
plain-language list of everything currently true about this system that a
reasonable stakeholder would want to know before relying on it — regardless of
whether it blocks release. Each item links to its full detail elsewhere rather
than duplicating it.

## Capacity

- **Proven safe up to 300 genuinely concurrent users** (server-measured 0%
  error rate, CPU/memory far under limits). **Not proven, and actively shown
  to degrade, at ~1,000 simultaneous connections** on staging's current
  `GUNICORN_WORKERS=6` / `DB_POOL_SIZE=8`+`DB_POOL_MAX_OVERFLOW=4`
  configuration (p50 latency 20.5s, real server-side errors under corrected
  load-test tooling). Production's own worker/pool sizing has not been
  tested this way and may differ. Full detail: GAP-28,
  `final_performance_assessment.md`.
- No load or soak test in this program has used genuinely distributed
  (multi-source-IP) traffic generation — every test, including this pass's,
  runs from one machine. This is an inherited methodology ceiling across the
  whole engagement, not new to this pass.
- The initial soak-test dispatch this pass hit a client-side thundering-herd
  timeout artifact (150 simultaneous logins, no ramp) that server metrics
  showed was not a real backend issue; fixed in the tool and re-run. Recorded
  here only because it's the kind of thing worth knowing exists as a test
  design pitfall, not because it reflects an application limitation.

## Accessibility

- `color-contrast`: **fixed in code, verified locally (18 page-scans, zero
  violations), but not yet deployed to staging or production** — see the
  correction in `final_accessibility_assessment.md`. Until deployed, the
  live application still has the original 40-43 failing nodes/page.
- 83 remaining unlabeled `<select>` elements in `connected-frontend` (2 of 85
  fixed this engagement) — real, sized, deliberately not guessed at with
  unverified labels.
- No `<h1>` / semantic landmark regions anywhere in `connected-frontend` — a
  whole-app structural gap, batched as a future markup/design decision
  rather than patched ad hoc.
- Screen-reader testing substituted automated axe-core scans for literal
  VoiceOver/NVDA operation throughout this engagement (disclosed, not a new
  gap this pass) — full manual keyboard-only traces remain incomplete.

## Staging-specific verification gaps

- **System Administrator role cannot currently be verified on staging** — the
  seeded account is healthy (confirmed via safe read-only DB inspection) but
  its access code was legitimately rotated (2026-07-30) and the test
  tooling's recorded code no longer matches. Blocked on the user supplying
  the current code. Does not affect production (verified separately, live,
  during this session's GAP-27 fix).
- Of the 4 non-`auditor` staging role scopes, **2 have full live-browser
  verification this pass** (`sqn_admin`, `wing_admin` — 18 page-scans each).
  `national_admin` verification was cut short by browser-tab instability
  (not retried, to avoid risking already-good evidence). `system_admin` is
  blocked per above. This is disclosed as the actual verification scope, not
  presented as exhaustive.

## Known, deliberately-not-fixed-this-pass items (all P3, all reasoned, none newly discovered)

- CEA import swallows per-row error detail on partially malformed files
  (GAP-23) — low-moderate probability, no data loss, scoped future work.
- Business-date logic uses server clock rather than a canonical Australian
  timezone (GAP-25) — narrow, cosmetic display-only impact near local
  midnight; a real design decision (which timezone), not mechanical.
- `COOKIE_SAMESITE` value is not validated by the fail-closed production
  config check — needs a scope decision (validate always vs. only when the
  cross-origin handoff feature is active).
- No CSRF token mechanism (CORS-only mitigation) — previously documented and
  accepted, not revisited this pass.
- `TrainingArea`/`PlanningLocation` and `facilitators`/`planning_facilitators`
  parallel-model duplication — flagged in prior passes, unchanged.

## Backup / disaster recovery

- The automated restore-test workflow is fully proven (zero caveats,
  including a new application-level check this pass — see
  `final_backup_restore_assessment.md`). A literal, hand-run manual DR drill
  by a human operator following the documented steps keystroke-by-keystroke
  has still never been performed — the operator DR walkthrough this pass
  confirmed every referenced artefact exists and matches the docs, which is
  meaningfully de-risking but not the same thing.
- Point-in-time recovery availability on Railway's native Postgres plan is
  unconfirmed either way.
- Key rotation procedure is documented but has never been exercised (no
  rotation has been due).

## What this list deliberately does not include

Anything closed with verified evidence (GAP-16, GAP-18, GAP-22, GAP-24,
GAP-26, `select-name` a11y, the two React hook-dependency warnings) is not
repeated here — see `final_findings_reclassification.md` for the full
investigated-and-closed record. This document is scoped to what remains
genuinely open or limited, so it stays trustworthy as a single reference
rather than growing to restate the whole engagement.
