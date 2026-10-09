# AAFC TMS — Production-Readiness Execution Plan (approved 2026-10-09)

## Context

The user chose to **plan against issue #70's 13 exit criteria** plus the `beta-release` skill's 11 gates, because "Sections 1–19" was never attached. They also chose to **build on the unmerged stack** (#69 `f8a5dca` → #71 `34b1d4b` → #72 `56ac1af`; all green and mergeable, 174 commits ahead of main `15b0d29`).

The result will be one integration branch, one final PR to main, and an evidence-backed GO/NO-GO. **Production deployment is out of scope.** Even a GO only allows asking for prod approval for the exact SHA, services, order and rollback.

### Verified starting state (2026-10-09, at #72 tip unless stated)
- **Shared checkout** `~/AAFC_TrainingManagementSystem` is on stale `fix/post-v17-frontend-workflow-remediation`, may belong to another session and must not be touched. All work goes in a new worktree.
- **Live defects from the Codex review on #71:**
  - **D1 (P1)** `backend/app/main.py:105`: `_confirm_maintenance_before_refusal()` sets `_maint_cache["expires"]=0.0` and then re-queries. This defeats the 2 s failure backoff, so every gated request hits a down DB.
  - **D2 (P2)** `services_parade_dates.py:76`: an `end_date` beyond 30 y is rejected even when `max_repeats` would bound the request.
  - **D3 (P2)** same file, line 77: `max_repeats` alone is silently truncated at the 30 y horizon (yearly ×200 → 3 dates).
  - **D4 (P2)** same file, line 82: `fortnight_anchor` overflows near `date.max` → `OverflowError` → 500.
  - **D5 (P1, process)**: commit mixes areas. The commit is pushed and force-push is banned, so the disposition is recorded rather than rewritten.
- **D6 Restore/migration mismatch.** Root cause is confirmed: `main`'s `test-restore-postgresql.yml` requires restored head == repo head. Prod is at `a4e9507a9c51` (v64); main head is `7f61608fa538`. The run 37238968630 failure shows `session_audiences` missing. So it fails every week by construction (09-13 → 10-04). The fix (restore → `alembic upgrade head` → verify) is on #69 (run 37132802899 passed). It clears only once that workflow is on main. Nightly backups are green (37856864407).
- **Ratchet** (`tools/architecture/architecture-baseline.json`): connected frontend 1,248,133 B / 20,123 lines / 788 fns; 43 router `p.role` checks; 0 router cross-imports.
- **Sizes:** `training.py` 8,129 lines / 142 routes; `planning.py` 6,290 / 74 routes; `dashboard.py` 818 (done).
- **Scope derivation is duplicated:** 22 inline `Squadron.wing_id == p.wing_id` sites (accounts 5, organisations 3, planning 4, search 6, service_desk 3, system 1), plus `dashboard._view_squadron_id_for_dashboard` and `custom_phases._above_wing_visible`. `permissions.resolve_view_squadron_id` already exists.
- **Unbounded lists:** `GET /service-desk/tickets` (`service_desk.py:285`) and `GET /accounts` (`accounts.py:307`).
- **No `.claude/settings.json`**, so no hooks or permission controls. Prod env id `571a8028-3640-4542-a4ab-7a1ee6b1f693`; staging `77a45568-…`.
- **Tooling exists:** `backend/scripts/qualification/{seed_national_dataset,national_load}.py`, `scripts/deploy-staging.sh`, `scripts/check_restore_workflow_sync.py`, `tools/architecture/` guards.

## Branching and isolation
- Worktree: `<scratchpad>/wt-prd` on new branch **`release/production-readiness-20261009`** from `56ac1af`. First check that the name is free (`git ls-remote --heads`, `gh pr list --head`). Prune the three stale `prunable` worktrees.
- Parallel implementation streams each get a child worktree off the integration branch and are merged back by me (lead) with `--no-ff`. Two streams never touch the same files at the same time.
- Evidence goes in `docs/release/production_readiness_20261009/` (EXECUTION_PLAN, TASK_REGISTER, SKILL_REGISTER, DEFECT_REGISTER, then TEST/MIGRATION/SECURITY/STAGING evidence and RELEASE_DECISION as evidence accrues). `docs/stabilisation/README.md` is updated in place. A checkpoint is committed at each phase end.

## Workstreams (task register seed)

| ID | #70 criterion / gate | Pri | Depends | Owner | Files (likely) | Done when |
|---|---|---|---|---|---|---|
| S0 | Safety controls (protocol §G) | P0 | — | lead | `.claude/settings.json`, `.claude/hooks/guard_prod.sh` | PreToolUse hook blocks Bash containing prod env id, `--environment production`, `deploy-production.sh`, `seed_all`/`reset_db` against a non-SQLite URL. Tested: each blocked pattern is denied and a staging/local equivalent is allowed. Documented in SECURITY_EVIDENCE |
| D1 | maintenance backoff | P1 | S0 | lead (TDD) | `backend/app/main.py`, `tests/test_maintenance*.py` | Failing test first: DB down + locked + stale cache → N gated requests cause ≤1 DB attempt per 2 s per worker. Fix: confirm-refresh honours an in-flight failure backoff (don't zero `expires` inside the backoff window). Maintenance drill re-run; 0 refused-in-error regressions |
| D2–D4 | parade-date edges | P2 | S0 | lead (TDD) | `backend/app/services_parade_dates.py`, its tests, generator modal error copy | Three failing tests → pass. `max_repeats` bounds the scan when present (horizon check applies only without it). An unmet `max_repeats` inside the horizon → explicit `422 max_repeats_exceeds_horizon` instead of silent truncation. Anchor/iteration near `date.max` → 422, never 500. Preview and write paths share the rule (already single-sourced) |
| D5 | review: mixed commit | P3 | — | lead | PR #71 reply | Disposition posted: history not rewritten (force-push ban). Each area is isolated by file and has its own tests. Rollback stays a single merge revert |
| D6 | restore test vs prod lag | P1 | final PR merge | lead | `.github/workflows/test-restore-postgresql*.yml` (already fixed) | `workflow_dispatch` run on the integration branch passes (restore → upgrade to head → app-level reads). After merge, the first scheduled run on main passes. Root cause written up in MIGRATION_EVIDENCE |
| C3 | router authz → permissions.py | P1 | S0 | security agent (worktree A) | `backend/app/permissions.py`, routers listed in baseline, `docs/stabilisation/role-check-classification.md` | Each of the 43 checks is reclassified. Every "pure allow/deny" check moves to a named predicate with unit tests. The remainder is documented as data-selection/product rule. Baseline lowered. Role matrix (8 roles) shows identical status codes before/after |
| C4 | one scope source of truth | P1 | C3 (same files) | security agent (worktree A) | new `backend/app/services_scope.py` (reuses `resolve_view_squadron_id`), accounts/organisations/planning/search/service_desk/system/dashboard/custom_phases | All 24 derivation sites call `visible_squadron_ids`/`squadron_scope_filter(p)`. New ratchet counts inline `wing_id == p.wing_id` in routers (baseline 0). Cross-Wing isolation tests plus a new per-router scope test pass |
| C8 | bound high-cardinality lists | P2 | C4 | backend agent | `service_desk.py`, `accounts.py`, connected-frontend Service Desk + Accounts views, `bounded-responses.md` | Follows the pattern already in `bounded-responses.md` (limit/offset, default cap, total). Existing callers' contracts are preserved. UI pages through results. Query-count and 1,000-row tests. Browser-checked in Chrome (DESIGN.md compliant) |
| C5 | training/planning seams | P1 | C4 (planning.py) | backend agent (worktree B) | `training.py`, `planning.py` → `services_training_*`, `services_planning_*` | Same method as the dashboard work: pure computation/query helpers moved verbatim, by domain (conflict detection, coverage/readiness, session serialisation, import validation, scope filters). Parity harness: every GET route on both routers returns byte-identical responses before/after on the seeded fixture. Boundary test (no FastAPI/HTTP in services). Router line-count ratchet added. HTTP models are not moved in the same commit |
| C6/C7 | Main TMS off the monolith | P1 | — (independent) | frontend agent (worktree C) | `connected-frontend/index.html` → `connected-frontend/js/*.js`, Dockerfile copy list, `connectedFrontendParses.test.ts`, deploy sha256 check | Extracted verbatim in the Phase 4 order (API/error → auth/session → shell/nav → table/form utils → Training Program → Planning/Parade/Weekly → Cadets → Accounts → Service Desk → Admin/System → reports/imports/audit). Classic `<script src>`, CSP unchanged. Done = index.html holds only markup, bootstrap and load order; every feature area lives in its own module; baseline lowered each step. Three-browser Playwright parity after each batch. Planning Workspace untouched |
| C9 | N+1 evidence | P2 | C5 | perf agent | query-count tests | Query-count tests are kept for all Phase 5 endpoints. Training/planning hot GETs profiled after C5; fixes only where measured |
| C10/C12 | national scale + failure drills on **staging** | P1 | integration deploy to staging | lead (sequential, never parallel) | `backend/scripts/qualification/*`, STAGING_EVIDENCE | Precheck: staging holds only synthetic data and no other session is mid-run (else stop and ask). Seed 10k+ cadets / 6 Wings / 60 Sqns. 50/100/250 users with 0 errors and p95 recorded. Maintenance, worker restart, DB-pool pressure, bulk CEA import burst, attendance write burst, Wing/National reports under load. Endpoints curl-verified with a real token first |
| C11 | backup + verified restore | P0 | D6 | lead | workflows | Backup run (nightly, green) plus restore run on the integration SHA, with app-level reads against the restored DB, run IDs recorded |
| C13 | clean clone → deploy | P1 | all code done | general-purpose agent with docs only | `README.md`, `docs/stabilisation/request-trace.md` (new) | A fresh agent given only README/docs does: clone → startup → tests → migration rehearsal → staging dry-run deploy. Every gap found gets fixed in the docs. A representative request is traced end-to-end in writing (Phase 7 box). Inventory of subsystems needing product-owner knowledge, each closed by a doc or flagged |
| C1/C2 | canonical history + PR to main | P0 | all | lead | GitHub | `git merge-base --is-ancestor` proves #67/#68/#69/#71/#72 heads are contained. Final PR to main from the integration branch. All CI, including e2e-tests.yml (runs because base is main), green on the exact final SHA. #69/#71/#72 closed as superseded with the containment proof. Issue #70 boxes ticked only with evidence links |

## Execution order
1. **Baseline (Phase 1).** Worktree and branch. S0 hook. Registers. Baseline full backend suite + frontend typecheck/test/build + local 3-browser matrix on `56ac1af`, run against an isolated DB with the server pid verified.
2. **Remediation (Phase 2).** D1 and D2–D4 via TDD (systematic-debugging, then test-driven-development). Dispatch the restore workflow (D6/C11). Post the D5 reply.
3. **Operational closure (Phase 3).** C3 → C4 (worktree A), then C8.
4. **Architecture (Phase 4).** C5 (worktree B, after C4 lands) **in parallel with** C6 (worktree C, from Phase 1 onward, since it doesn't touch backend files). C9 follows C5.
5. **Qualification (Phase 5).** Full suites after the last code change. Alembic upgrade/downgrade on SQLite + PostgreSQL. Security greps from `.claude/rules/security.md`, plus `pip-audit`, `npm audit`, and the `security-review` skill on the full diff. Staging deploy of the integration SHA via `deploy-staging.sh` (DRY_RUN first, from an independent GitHub clone). Staging rollback rehearsal (redeploy prior SHA, then forward again). C10/C12 on staging. C13 clean-clone.
6. **Adversarial review (Phase 6).** An independent general-purpose agent is told to find reasons to refuse the release: falsely closed defects, stale evidence, misleading green checks, permission regressions, restore gaps. Every disproven PASS is fixed or downgraded.
7. **Integration (Phase 7).** Final PR, CI on the exact SHA, issue #70 updated, superseded PRs closed, RELEASE_DECISION.md.

## Skills to invoke (register kept in SKILL_REGISTER.md)
- **beta-release** (loaded): gate structure and final GO/NO-GO.
- **superpowers:** using-git-worktrees (P1), systematic-debugging + test-driven-development (D1–D4), dispatching-parallel-agents / subagent-driven-development (C3–C6), requesting-code-review plus `code-review` at each workstream close, verification-before-completion at every closure, finishing-a-development-branch (P7).
- **security-review** (C3/C4/S0/final diff); **frontend-design** + DESIGN.md (C8 paging UI only); **claude-in-chrome** (user-visible checks); **railway:use-railway** + **engineering:deploy-checklist** (staging deploy/rollback).
- **Not used:** `simplify`, because extractions must be verbatim and simplify would redesign. `/batch` and `/goal` aren't installed.

## Migration, deploy and rollback implications
- **Migrations:** no new migration is planned. If D2–D4 or C8 turn out to need one, it gets a single head and a SQLite + PG up/down rehearsal. Prod v64 → head is rehearsed by the restore workflow on real prod data.
- **Deploy:** staging only. Uses the 3 Railway services and the fingerprint/sha256 module checks, which must include any new `js/*.js`.
- **Rollback:** the final PR merges with a merge commit, so rollback = one revert. Staging rollback is rehearsed. Prod rollback is documented in `docs/release/rollback_runbook.md` and re-verified, not executed.

## Known external blockers (likely NO-GO items)
- Merging the final PR to main needs you; my earlier merge attempt was permission-blocked.
- Human UAT, data governance, key custody and known-limitation sign-off (beta-release gate 10).
- Staging credentials beyond sys/sqn admin may be stale (`tests/helpers/auth.ts` throws on missing codes).
- Production deployment approval is a separate decision either way.

## Verification (end-to-end)
- `cd backend && python -m pytest tests/ -q` (record real counts); `cd frontend && npm run typecheck && npm test && npm run build`; local Playwright chromium/firefox/webkit against both frontends.
- Architecture guards (`tools/architecture/`) pass with lowered baselines; parity harnesses for C5/C6 show 0 diffs.
- `alembic heads` = 1; up/down on SQLite + PG.
- Restore workflow run ID green on the final SHA. Staging deploy gates all pass with the deployed SHA verified on all 3 services. Staging load/drill numbers recorded.
- Final PR checks green on the exact SHA. The adversarial reviewer's findings are all dispositioned before RELEASE_DECISION.md is written.
