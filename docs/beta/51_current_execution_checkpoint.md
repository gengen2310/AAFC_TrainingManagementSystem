# AAFC TMS — Execution Checkpoint

Phase 18 (Operational Release Gate). Durable checkpoint written 2026-07-14 while
corrected 100-user load test is running. Survives context compaction.

**DO NOT INTERRUPT THE RUNNING LOAD TEST (task ID: baw9zh1fw).**

---

## Repository State

| Field | Value |
|---|---|
| Path | `/Users/jennydv/Desktop/AAFC_TMS_National_Connected_Pilot_Package_v17_1_source` |
| Branch | `release/beta-2026-07-14` |
| HEAD | `2e1f437` — docs: record staging deployment and rollback rehearsal results |
| Working tree | Clean — nothing to commit |
| Remote | `origin/release/beta-2026-07-14` — up to date |

### Recent commits (HEAD → oldest)

| SHA | Message |
|---|---|
| `2e1f437` | docs: record staging deployment and rollback rehearsal results (2026-07-14) |
| `3cc7650` | docs: update release gate docs to reflect rc2 state — E2E pass, load test/rehearsal pending |
| `e539d02` | fix: replace useBlocker with useLocation in useProxyGuard; fix 35 Playwright E2E tests ← **RC2** |
| `4a9c178` | test: 36 new backend tests + 35 Playwright E2E specs; visual consistency audit |
| `467e0fa` | docs: Operational Release Gate — 18 new documents (phases 1–19, docs 34–50) |
| `e918f3e` | refactor: remove 9 dead planning page divs + simplify nav hook + fix ops N+1 ← **RC1** |

### Tags

| Tag | Commit | Status |
|---|---|---|
| `beta-2026-07-14-rc1` | `e918f3e` | Superseded — rc2 exists |
| `beta-2026-07-14-rc2` | `e539d02` | Current RC — pushed to origin |

---

## Currently Running Process

| Field | Value |
|---|---|
| Task ID | `baw9zh1fw` |
| Output file | `/private/tmp/claude-501/-Users-jennydv/fa4ea2d6-cc66-4422-b865-406dd21c7fe8/tasks/baw9zh1fw.output` |
| Command | `python3 tools/stress/load_test_staging.py --users 100 --duration-minutes 45 --ramp-seconds 60` |
| Target | `https://aafc-tms-backend-staging.up.railway.app` |
| Start time | ~2026-07-14T15:48Z |
| Expected completion | ~2026-07-14T16:34Z |
| Status at checkpoint | [SUSTAINED] ~145s / 2760s, 5,444 requests, 0 5xx |

**Do not kill, interrupt, or restart this process.**

---

## Why the First Load Test Run Is Not Release Evidence

First run task ID: `b4343awtj` (completed, exit code 1).

Three of the six endpoint paths in the original script were incorrect:

| Path used | Correct path | Status code returned | Request count |
|---|---|---|---|
| `/api/dashboard` | `/api/reports/summary` | 404 | 21,380 |
| `/api/planning/sessions` | `/api/years` or `/api/sessions/{id}` | 404 | 19,753 |
| `/api/planning/annual-program` | `/api/years/{year_id}/annual-program` | 404 | 19,740 |

Total 404 requests from wrong paths: **60,873** — exactly matching the "failed (non-5xx)" count.

The three correct paths (login, /api/auth/me, /api/parade-nights) produced **64,130** successful
responses across 46.2 minutes of sustained load with P95 534ms and 1 transient 5xx.

**The first run is not valid release evidence because the workflow was not representative.**
It may be cited as a partial performance baseline only.

Corrected paths in second run:
- `/api/reports/summary` (dashboard summary)
- `/api/years` (planning years list)
- Second read of `/api/parade-nights` (simulates navigation back)

---

## Staging Environment

| Service | Deployment ID | Status | Source |
|---|---|---|---|
| `aafc-tms-backend` | `ac20386b-393d-4acb-9508-e154fdfa313d` | SUCCESS | Rehearsal deploy of rc2 code (`e539d02+3cc7650`) |
| `aafc-tms-frontend` | `ce2420c3-70f0-472d-8b86-f98448c70eb1` | SUCCESS | Connected frontend |
| `aafc-tms-planning-workspace-preview` | `8f93e841-6879-4226-9ff4-7e0b016fe11a` | SUCCESS | Planning Workspace |

### Staging URLs

| Service | URL |
|---|---|
| Backend | `https://aafc-tms-backend-staging.up.railway.app` |
| Connected TMS | `https://aafc-tms-frontend-staging.up.railway.app` |
| Planning Workspace | `https://aafc-tms-planning-workspace-preview-staging.up.railway.app/planning` |

**Environment ID**: `77a45568-5c16-46c2-9065-d5d339208b0e` (staging)

---

## Release Gate Status at Checkpoint

| Gate | Status |
|---|---|
| Feature freeze | ✅ COMPLETE |
| RC2 created and pushed | ✅ COMPLETE — `e539d02` / `beta-2026-07-14-rc2` |
| Backend tests: 541 pass | ✅ COMPLETE (at `e539d02`) |
| TypeScript: 0 errors | ✅ COMPLETE |
| Playwright E2E: 35/35 pass | ✅ COMPLETE (at `e539d02`, against localhost:5173) |
| Playwright E2E against staging | ❌ NOT DONE |
| Production backup/restore | ✅ COMPLETE (runs 29281190414, 29281292666, 29297143467) |
| Staging deployment rehearsal (D1–D7) | ✅ COMPLETE (2026-07-14) |
| Staging rollback rehearsal (R1–R5) | ✅ COMPLETE (2026-07-14) |
| 100-user load test — first run | ❌ INVALID (wrong paths) |
| 100-user load test — corrected run | ⏳ IN PROGRESS (task baw9zh1fw) |
| Post-load data integrity checks | ❌ NOT DONE (blocked on load test) |
| Workload realism assessment | ❌ NOT DONE (blocked on load test) |
| Backend tests for open tasks | ⚠️ PARTIAL — task 12 largely addressed (422→541); scope needs verification |
| Resource model consistency (task 10) | ⚠️ DEFERRED — documented in known limitations |
| Visual consistency (task 11) | ⚠️ NOT ASSESSED this session |
| Beta docs phases 19–22 (task 13) | ⚠️ NEEDS CLASSIFICATION |
| Security greps | ✅ COMPLETE |
| Migration chain v36 | ✅ COMPLETE |
| Backup key custody | ⚠️ PENDING — 5 human actions |
| UAT | ⚠️ PENDING — human testers required |
| Data governance | ⚠️ PENDING — 9 org decisions |
| Known limitation acceptance | ⚠️ PENDING — owner sign-off |
| Browser verification | ⚠️ PENDING — human in Chrome |
| Production config (ENVIRONMENT var) | ⚠️ PENDING — requires approval |
| Production deploy of DEFECT fixes | ⚠️ PENDING — requires approval |
| Production smoke test | ⚠️ PENDING — after deployment approval |
| Final GO/NO-GO | **NO-GO** |

---

## Open Technical Tasks (non-human-gated)

### Task 10 — Canonical resource model (TrainingArea vs PlanningLocation)

Status: **DEFERRED WITH EXPLICIT DOCUMENTED RISK**

The duplication is recorded in `docs/beta/15_known_limitations.md` and `docs/beta/28_authoritative_data_model.md`.
No fix is required before beta; users informed in release communication.
Requires owner acceptance in `47_known_limitation_acceptance.md` (human action).

### Task 11 — Visual consistency / shared design tokens

Status: **NEEDS ASSESSMENT** — commit `4a9c178` included a visual consistency audit.
Must verify what was actually completed vs deferred. Not confirmed COMPLETE.

### Task 12 — Backend tests for new endpoints and behaviours

Status: **LARGELY COMPLETE** — test count grew from 422 to 541 (119 new tests).
Must verify: are all new endpoints from this release branch covered?
Needs a targeted grep of routers added in this branch vs test coverage.

### Task 13 — Beta documentation phases 19–22

Status: **NEEDS CLASSIFICATION** — the Operational Release Gate docs (33–50) were written.
"Phases 19–22" may refer to specific sub-phases of the release gate that need to be
mapped to written documents. Must determine which specific docs are missing.

---

## Open Technical Actions After Load Test Completes

In execution order:

1. **Read full corrected load test result** from `baw9zh1fw.output`
2. **Assess workload realism** — endpoint distribution, write operations, role coverage
3. **If PARTIAL LOAD TEST**: classify gate accordingly; do not close 100-user gate
4. **Run post-load data integrity checks**:
   - Squadron isolation: check for cross-squadron rows
   - Duplicate checks: planning years, parade nights, activities, sessions
   - Orphan FK checks
   - Stuck transactions / stale locks
   - Service recovery to normal latency (health endpoint)
5. **Classify tasks 10–13** with evidence
6. **Verify backend test coverage** for all endpoints added on this branch
7. **Run Playwright E2E against staging** (requires configuring playwright baseURL to staging)
8. **Update `35_release_evidence_chain.md`** Link 10 with load test result
9. **Update `12_full_beta_release_readiness.md`** Gate 5
10. **Update `13_executive_go_no_go.md`** gate table
11. **Commit and push** all evidence updates
12. **Determine if RC2 needs a new commit** (if new test evidence or fixes are added after e539d02)
13. **Final technical recommendation** (NO-GO unless all gates pass)

---

## Open Manual Actions (human-gated — cannot proceed without person)

1. Rotate Railway access token (token inadvertently exposed this session)
2. Browser verification — Chrome, staging, 8 roles × 2 squadrons minimum
3. D7 staging smoke test browser steps (steps 1–15 of `48_final_production_smoke_test.md`)
4. UAT — 4 testers, 20 tasks, results into `38_user_acceptance_results.md`
5. Data governance — 9 decisions in `46_data_governance_and_approval.md`
6. Known limitation acceptance — `47_known_limitation_acceptance.md`
7. Backup key custody — 5 actions in `36_backup_key_custody_checklist.md`
8. Account creation — all beta users, per `39_account_and_role_release_matrix.md`
9. Set `ENVIRONMENT=production` in Railway production (DEFECT-003)
10. Deploy DEFECT-001/003/005 to production (requires explicit approval)
11. Production smoke test — 20 steps in `48_final_production_smoke_test.md`
12. Explicit named production deployment approval

---

## Corrected Load Test Command (for re-execution if needed)

```bash
cd /Users/jennydv/Desktop/AAFC_TMS_National_Connected_Pilot_Package_v17_1_source
python3 tools/stress/load_test_staging.py --users 100 --duration-minutes 45 --ramp-seconds 60
```

Environment variable override:
```bash
BASE_URL=https://aafc-tms-backend-staging.up.railway.app \
  python3 tools/stress/load_test_staging.py --users 100 --duration-minutes 45 --ramp-seconds 60
```

---

## Security Note

Railway access token was inadvertently exposed during this session when reading
`~/.railway/config.json` with a Python filter that did not traverse nested dicts.
The token appeared in the conversation context. **User must rotate at railway.com/account/tokens.**
No further commands should pass the token as an explicit argument.

---

## Current Release Recommendation

**NO-GO**

Corrected load test in progress. Post-load integrity checks not yet run.
Playwright against staging not yet run. Tasks 11–13 not fully assessed.
Human acceptance gates all pending.

This checkpoint was written 2026-07-14 while task `baw9zh1fw` is running.
Do not mark GO or CONDITIONAL GO until all mandatory technical gates above are closed.
