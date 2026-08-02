# Final Operational Readiness (Post-Deployment Reconciliation)

New document, requested explicitly in the "AAFC TMS — Final Pre-Production
Reconciliation" instruction (treated as post-deployment hardening per the
user's own reframing, since production was already deployed by the time this
instruction was issued). States, precisely and as of this writing, what is
actually running where, what has and has not been verified against it, and
what is still open.

## Exact current state (verified live, not asserted, 2026-08-02)

| | Production | Staging |
|---|---|---|
| Backend deployment ID | `9c183e03-3e2b-4b83-a7bf-a970acb98a56` (SUCCESS) | (not re-checked this pass; unchanged since Stage 13's deploy unless noted below) |
| `connected-frontend` deployment ID | `4166d3ef-2d0d-40b0-8c79-da0c257864bb` (SUCCESS) | — |
| `connected-frontend` `app-build` fingerprint | `699b01f` @ 2026-08-02T06:29:06Z | `699b01f` @ 2026-08-02T06:29:23Z |
| Planning Workspace `app-build` fingerprint | `5667382` @ 2026-07-27T15:05:51Z | (not re-checked this pass) |
| `GET /api/health/ready` | `{"status":"ready","squadrons":1}` | `{"status":"ready","squadrons":140}` (synthetic volume data) |
| `GET /api/health/ui-config` | `planning_workspace_url` correctly points at the production Planning Workspace, `environment: production` | — |
| Backend test suite (local, against current `main`) | 1008 passed, 5 skipped | same code |
| Migration head | `z1a2b3c4d5e6`, single linear head | same |
| Local `main` vs `origin/main` | 9 commits ahead, 0 behind — **not yet pushed** | — |

**What "commit `699b01f`" means for this release**: that is the exact commit
both production and staging are currently serving. It is the Stage 14 release
candidate — the version that was reviewed, tested, and explicitly authorised
for production deployment earlier in this engagement ("Merge to main and
deploy to production"). **Everything committed on `main` after `699b01f`
(9 commits: GAP-28's async load-test tooling, the color-contrast accessibility
fix, the soak-test ramp fix, and this reconciliation pass's documentation) is
local-only** — on `main` in this git checkout, not pushed to `origin/main`,
and not deployed anywhere. This is intentional and correct given this pass's
explicit instruction ("do not deploy production, do not merge to main [further]
without a fresh authorization... treat as post-deployment hardening") — it is
recorded here so the exact boundary between "what production is running" and
"what this reconciliation pass produced" is never ambiguous.

## What has changed in code since production's current deployment

Of the 9 unpushed/undeployed commits, exactly **one** touches served
application code:

- `ca785b4` — the color-contrast accessible-token fix
  (`connected-frontend/index.html`). Verified correct via local axe-core
  scans (18 page-scans, zero violations) and the full local e2e suite
  (24/24), but **not live anywhere** — see the correction recorded in
  `final_accessibility_assessment.md` and `final_findings_reclassification.md`.

The other 8 are test tooling (`tools/stress/`, gitignored, never deployed by
design) and documentation. **No backend code has changed since production's
current deployment.**

## Monitoring status

- Railway `metrics`/`logs` for both backend services confirmed reachable and
  returning current data throughout this pass (used repeatedly to
  cross-check load-test and soak-test client results against server-side
  truth).
- No dedicated external uptime/alerting service is wired up beyond Railway's
  own dashboard — consistent with prior passes' documented state, not a new
  gap introduced here.
- Recommended monitoring period after any future deploy of the pending fix:
  at minimum the duration of one full soak-equivalent window (a few hours)
  watching `railway metrics` for error-rate and latency drift, per the
  pattern already established and exercised in this pass's soak test.

## Rollback / forward-fix position

- Production is currently running a known-good, already-tested commit
  (`699b01f`) with **zero P0/P1 findings** against it (per
  `final_findings_reclassification.md`). There is nothing pending rollback —
  the reconciliation pass's one code fix has not shipped yet, so there is
  nothing to roll back from.
- If/when `ca785b4` (or the branch head containing it) is deployed to
  production in the future: rollback is a `railway rollback` to deployment
  `9c183e03-3e2b-4b83-a7bf-a970acb98a56` (current, proven-stable) or a fresh
  `railway up` from the `699b01f` commit, either of which is a pure CSS/token
  revert with no migration or data implication (the fix touches only
  `:root` custom properties and a handful of `color:` declarations in one
  static HTML file).

## Open items this document does not resolve (see `final_known_limitations.md` and `final_findings_reclassification.md`)

- Staging System Administrator authentication (P2, blocked on user-supplied
  credential).
- 1,000-concurrent-user capacity ceiling on staging's current worker/pool
  configuration (P2, GAP-28).
- The fresh 4-hour soak test is in progress at time of writing; its final
  result is appended to `final_performance_assessment.md`, not duplicated
  here.
- Whether/when to push the 9 pending commits to `origin/main`, and
  whether/when to deploy the color-contrast fix to staging and/or
  production, are **explicit decisions for the user** — not made
  unilaterally in this pass, per its own standing boundary.
