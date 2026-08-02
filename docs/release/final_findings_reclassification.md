# Final Findings Reclassification (Post-Deployment Reconciliation)

Rigorous re-review of every open finding, per the reconciliation instruction's own
explicit rule: *"A finding must not be reduced to P3 because it is inconvenient or
involves a design decision."* Each item below was actively re-investigated this
pass, not reflexively re-stamped with its prior severity. Two items were
investigated to closure and are no longer open (marked accordingly).

## Investigated and closed this pass

### Colour-contrast failures (were: serious, undetermined severity)

**Was reconsidered rather than left at a design-decision P3.** Investigated
further, computed exact WCAG-AA-compliant replacement values against every real
background the failing colours appear on, and **fixed** — contextual accessible
tokens introduced, brand palette itself untouched. Re-scanned (local server, per
this repo's established Stage 7 methodology for `connected-frontend`): zero
color-contrast violations across 18 page-scans (12 `sqn_admin`-scope, 6
`wing_admin`-scope pages). **Code-level finding closed; deployment status
corrected below — this fix is NOT yet live on staging or production**, see
`final_accessibility_assessment.md`'s 2026-08-02 correction. An earlier version
of that document incorrectly claimed it was deployed and confirmed live at
both; that was checked and found false while preparing this pass's final
documents (`app-build` fingerprints on both deployed connected-frontend
services still read commit `699b01f`, which precedes the fix commit
`ca785b4`).

### React hook dependency warnings (were: unexamined "worth a closer look")

**Investigated to a definitive conclusion, not left uncertain.**
- `frontend/src/routes/Curriculum.tsx`: `items = q.data?.items ?? []` creates a
  new array reference on renders where `q.data` is still loading, so
  `useMemo`-derived `phases`/`elements` recompute more often than strictly
  necessary. This is a **performance** characteristic (excess recomputation),
  not a stale-state bug — the recomputed value is always correct, just
  sometimes recomputed unnecessarily.
- `frontend/src/routes/PlanningWorkspace.tsx`: a `useEffect` syncing
  `selectedYearId` to the active year only depends on `[years]`, deliberately
  excluding `selectedYearId`/`persistYear` from the dependency array. Traced
  through React's actual effect/closure semantics: each render creates a fresh
  closure capturing the *current* `selectedYearId`, and the effect only *runs*
  when `years` changes — so when it does run, it always sees the up-to-date
  `selectedYearId`, not a stale one. This is a standard, deliberate "sync only
  when the source data loads, don't fight a user's manual selection on every
  other render" pattern, not a bug.
- **Conclusion: neither warning causes real stale state. Closed, not a
  release-relevant finding of any severity.**

## Open findings, reclassified with full disclosure fields

### 1. Staging System Administrator authentication

- **Severity: P2** (re-affirmed, not reflexively downgraded to P3). Reasoning
  against inflation to P1: the underlying account was directly inspected via a
  safe, read-only database query (never touching `code_hash`) and confirmed
  healthy — active, not archived, zero failed attempts, not locked. This rules
  out an application defect; the cause is a legitimate prior access-code reset
  (`code_updated_at` shows a real rotation on 2026-07-30) that the test tooling's
  recorded demo code no longer matches, which is the access-code system working
  exactly as designed (one-time display, never re-shown). Reasoning against
  deflation to P3: system_admin gates System Console, Account Management,
  National/Wing/Squadron scope inspection, Proxy/Intervention Mode, archive/
  restore, and audit — a real, material block on verifying a large,
  high-privilege functional surface on staging, not a cosmetic gap.
- **Operational effect**: cannot verify system_admin-specific staging behaviour
  (items 3-20 of the reconciliation instruction's own system_admin checklist)
  until access is restored.
- **Affected users**: none directly (production is unaffected; this is a
  staging verification-coverage gap, not a live defect).
- **Probability**: certain (currently blocking, not intermittent).
- **Workaround**: none for verification purposes; a human with the actual
  current code can complete the checklist manually.
- **Owner**: user (holds or can regenerate the actual current staging
  credential).
- **Target date**: before any future pass that specifically needs to verify
  system_admin staging behaviour end-to-end.
- **Release decision**: does not block this release — production's own
  system_admin path is separately verified live in production earlier this
  session (GAP-27's fix required and used a working production login flow).
- **Explicit acceptance authority**: open, awaiting the user's supplied
  credential (asked, not yet provided as of this writing).

### 2. 1,000-concurrent-user capacity (GAP-28)

- **Severity: P2** (reasoned from real evidence, not a default). See GAP-28 in
  the gap register for full detail. Not P0/P1: 300-user capacity is solidly
  proven, and this is a staging-configuration-specific finding (production's own
  worker/pool sizing is untested by this specific method and may differ). Not
  P3: this is real, server-confirmed evidence (20.5s p50 latency, real 5xx
  errors, both client- and server-measured in agreement) of a genuine capacity
  ceiling, not a design nicety.
- **Operational effect**: a burst of ~1,000 truly-concurrent users against
  staging's current `GUNICORN_WORKERS=6` configuration would see severe latency
  degradation and some real errors.
- **Affected users**: none currently (no realistic scenario puts 1,000
  simultaneous users on staging, which is synthetic-data/internal-only); a
  production capacity question if user growth ever approaches this scale.
- **Probability**: low near-term (current pilot scale is far below 1,000
  concurrent users) but real if/when the deployment scales.
- **Workaround**: none needed at current scale; horizontal/vertical capacity
  tuning (`GUNICORN_WORKERS`, `DB_POOL_SIZE`/`DB_POOL_MAX_OVERFLOW`) is the
  long-term fix.
- **Owner**: whoever owns infrastructure capacity planning for this deployment.
- **Target date**: before any onboarding push that would bring concurrent usage
  close to this scale.
- **Release decision**: does not block this release given current real usage is
  nowhere near this concurrency, and the finding is disclosed rather than hidden.
- **Explicit acceptance authority**: recorded here for the user's review; not
  independently re-confirmed as "accepted" pending their read of this document.

### 3. Fresh multi-hour soak (current release candidate)

- **Status**: in progress at time of writing (Task #48) — a genuine 4-hour soak
  against staging on the exact current release candidate, 150 concurrent
  persistent users, realistic multi-endpoint workload, periodic safe write
  probes, 15-minute metric snapshots. Not yet complete; full results will be
  appended to `final_performance_assessment.md` once finished. **This item is
  intentionally not finalised in this document** — closing it out before the
  soak actually completes would misrepresent the evidence.

### 4. CEA import swallows per-row error detail (GAP-23)

- **Severity: P3** (re-affirmed after active reconsideration, not by default).
  Checked specifically for the possibility of inflation: no data loss (rows
  simply aren't imported, safely retryable), no security/tenancy implication
  (same admin-only gating as the working curriculum-import path next to it in
  the same file), and a directly comparable sibling code path in the same
  codebase already does this correctly — meaning the *pattern* to fix it is
  already proven, this is scoped, low-risk future work, not an open-ended
  unknown.
- **Operational effect**: an admin importing a CEA file with some malformed
  rows sees only a failure count, not which rows or why.
- **Affected users**: national_admin/system_admin performing CEA imports with
  partially-malformed source files (uncommon; most real CEA exports are clean).
- **Probability**: low-moderate, dependent on source data quality.
- **Workaround**: re-check the source file section by section, or contact
  support with the failure count for manual diagnosis.
- **Owner**: whoever picks up the next CEA-import-focused work item.
- **Target date**: bundled with the next dedicated CEA workflow pass, not a
  fixed date.
- **Release decision**: does not block release.
- **Explicit acceptance authority**: documented here; no separate user
  sign-off requested given the low real-world impact already reasoned above.

### 5. Server-timezone vs. Australian operational-date behaviour (GAP-25)

- **Severity: P3** (re-affirmed after active reconsideration). Checked for
  inflation: no data corruption (dates stored/compared consistently; only a
  narrow, few-hour-per-day display/counting window near local midnight AEST/
  AWST could be affected), no security implication. Checked for deflation: this
  is real and affects every business-date computation in the system, not a
  one-off — but the *width* of user-visible impact (a few hours near midnight,
  and only for date-boundary-sensitive countdowns) keeps it below P2.
- **Operational effect**: a "days until parade night" or similar countdown
  could be off by one during a narrow window near local midnight in the
  relevant Australian timezone.
- **Affected users**: any user checking a date-relative dashboard figure during
  that narrow window; effect is cosmetic (a countdown number), not a scheduling
  error (the underlying stored dates are correct).
- **Probability**: certain to occur during the affected window, but the window
  itself is narrow and infrequently the moment of a critical decision.
- **Workaround**: none needed — the underlying data is correct; only a
  transient display figure could be briefly off.
- **Owner**: whoever makes the (real, non-mechanical) design decision on a
  canonical AAFC business timezone.
- **Target date**: no fixed date; a deliberate design decision, not urgent.
- **Release decision**: does not block release.
- **Explicit acceptance authority**: documented here; no separate sign-off
  requested given the narrow, cosmetic-only impact.

### 6. Remaining structural/scope items (unchanged from earlier passes, re-affirmed not inflated or deflated)

- 83 remaining unlabeled `<select>` elements in `connected-frontend` (2 of 85
  fixed live this session) — P3, real remaining scope, not guessed at.
- No `<h1>` / landmark regions in `connected-frontend` — P3, whole-app semantic
  structure gap, a markup/design decision.
- `COOKIE_SAMESITE` value not validated by the fail-closed production config
  check — P3, needs a scope decision (validate always vs. only when the
  cross-origin handoff feature is active).
- GAP-26 Dockerfile fix — **no longer open**, build-verified via the staging
  deploy earlier this session (real Docker build succeeded).
- GAP-17 (500-user/2-hour soak, two 5xx clusters) — **not reopened**, already
  explicitly accepted by the user as residual risk in a prior session.

## Summary

| Finding | Prior status | This pass | Final severity |
|---|---|---|---|
| Colour-contrast failures | Serious, undetermined | Investigated, fixed in code | Closed (code); **not yet deployed to staging/production** |
| React hook warnings | Unexamined | Investigated, confirmed non-issues | Closed |
| Staging system_admin auth | Open | Re-affirmed with full disclosure | P2, open, blocked on user |
| 1,000-user capacity (GAP-28) | New this pass | Reasoned from real evidence | P2, open, disclosed |
| Fresh soak | Not started | In progress | Pending completion |
| CEA import error detail (GAP-23) | P3 | Re-affirmed, not inflated/deflated | P3, open |
| Server timezone (GAP-25) | P3 | Re-affirmed, not inflated/deflated | P3, open |
| 83 unlabeled selects | P3 | Unchanged | P3, open |
| Heading/landmark structure | P3 | Unchanged | P3, open |
| `COOKIE_SAMESITE` validation gap | P3 | Unchanged | P3, open |
| Dockerfile pin (GAP-26) | P1/P2, fixed | Build-verified | Closed |
| GAP-17 (500-user soak) | Accepted residual risk | Not reopened | Accepted, closed |

**Zero P0 findings. Zero P1 findings.** Two P2 findings remain open, both with
full disclosure fields above and neither indicating the deployed candidate is
broken at realistic current-scale usage.
