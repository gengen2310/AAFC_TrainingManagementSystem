---
name: beta-release
description: Use before packaging, tagging, or deploying an AAFC TMS beta release — runs the full release-gate checklist and points to the docs/beta/ evidence trail for each gate.
---

# AAFC TMS Beta Release Gate

This skill is the release-gate process referenced from `CLAUDE.md`'s "Before
packaging/releasing" section. It does not replace `docs/beta/` — it tells you which document
proves which gate, and in what order to run the checks. Treat `docs/beta/00_release_state.md`
as the current living status; everything else in `docs/beta/` is either a plan, a checklist, or
an evidence record for one gate.

## Non-negotiable rules (apply to every release pass)

- Work from a clean release branch or isolated worktree — never straight on `main` for the
  destructive/live-verification phases.
- Never run destructive load/chaos/migration/penetration testing against production. Staging
  (synthetic data) only.
- Never weaken an assertion, permission check, tenancy filter, or error-handling path to make a
  test pass. If a test is failing because the check is correct and the test's expectation is
  wrong, fix the test — not the check.
- Never mark a gate complete without evidence (a command output, a test run, a screenshot, a
  workflow run ID) recorded in `docs/beta/`.
- Passing tests is not production deployment approval. Production deployment additionally
  requires: the release report finished, and explicit user sign-off naming the exact commit,
  services, deploy order, migration impact, and rollback plan.
- Do not deploy the React Planning Workspace (`frontend/`) as a replacement for the legacy root
  frontend (`connected-frontend/`), and do not merge the two builds — see
  `.claude/rules/architecture.md`.

## Gate checklist and where the evidence lives

Run in roughly this order; later gates assume earlier ones are real, not just claimed.

| # | Gate | Command / action | Evidence doc |
|---|---|---|---|
| 1 | Backend tests pass | `cd backend && python -m pytest tests/ -q` | `docs/beta/00_release_state.md`, `.claude/rules/testing.md` |
| 2 | Frontend typecheck/tests/build clean | `cd frontend && npm run typecheck && npm test && npm run build` | `docs/beta/00_release_state.md` |
| 3 | Security greps return 0 | greps in `.claude/rules/security.md` | `docs/beta/00_release_state.md` |
| 4 | Migration chain has one head, matches all environments | `cd backend && alembic heads`; `backend/scripts/compute_alembic_head.py` | `docs/beta/28_authoritative_data_model.md` |
| 5 | Backup proven end-to-end (not staging-only) | GPG backup workflow + restore-test workflow + app-level read against restored DB | `docs/beta/32_final_stress_and_resilience_report.md`, `.github/workflows/backup-postgresql.yml`, `test-restore-postgresql.yml` |
| 6 | Browser E2E against staging (both frontends) | Playwright against the live staging URLs, not just localhost | `docs/beta/09_browser_e2e_verification.md` |
| 7 | 100-user concurrent load test against staging | `python3 tools/stress/load_test_staging.py --users 100 --duration-minutes 45 --ramp-seconds 60` (script is gitignored — local tool only) | `docs/beta/32_final_stress_and_resilience_report.md`, `docs/beta/35_release_evidence_chain.md` |
| 8 | Deployment + rollback rehearsal on staging | `docs/beta/41_deployment_rehearsal.md` | same doc |
| 9 | Defect register accurate | every open defect has repro, severity, root cause, fix, regression test, retest evidence | `docs/beta/11_defect_register.md` |
| 10 | Human-gated items (UAT, data governance, key custody, account creation, known-limitation sign-off) | — | `docs/beta/37`–`39`, `46`, `47` |
| 11 | Executive GO/NO-GO | consolidate 1–10 | `docs/beta/13_executive_go_no_go.md` |

Only after gate 11 reads GO (or an explicit, user-approved LIMITED BETA GO scope) do you ask the
user for production deployment approval — and only for the exact commit/services/order named in
the go/no-go doc.

## Before running the load test or any live-staging check

Verify the script's target endpoints against the real staging server with `curl` first (a real
login token, a couple of GET requests) — this repo's load-test tooling has twice shipped with a
stale endpoint path that silently 404s every request of one workflow step. A quick curl check is
cheaper than discovering it 40 minutes into a run.

## If another Claude Code session is working the same release

Check `git log --oneline -15` and `docs/beta/00_release_state.md` before starting destructive or
long-running staging work (load test, deploy rehearsal, backup/restore). If a concurrent session's
commits or checkpoint docs (e.g. `docs/beta/51_current_execution_checkpoint.md`-style files) show
in-flight work against the same staging environment, don't assume it's finished — read the
checkpoint, check elapsed time against the process's expected duration, and only proceed once it's
clearly safe (finished, abandoned, or genuinely non-conflicting).

## Updating this gate

When a gate's evidence doc is superseded (new RC, new commit, re-run test), update
`docs/beta/00_release_state.md` and the specific evidence doc together — a gate marked ✅ against
a commit that's no longer HEAD is not evidence, it's a stale claim.
