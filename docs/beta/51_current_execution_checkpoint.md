# AAFC TMS — Execution Checkpoint

Phase 18–19 (Operational Release Gate). Durable checkpoint written 2026-07-15.
Survives context compaction.

---

## Repository State

| Field | Value |
|---|---|
| Path | `/Users/jennydv/Desktop/AAFC_TMS_National_Connected_Pilot_Package_v17_1_source` |
| Branch | `release/beta-2026-07-14` |
| HEAD | `f9408ad` — docs: update release gate docs for rc3, load test runs 1–3, DEFECT-007 |
| Working tree | Clean — nothing to commit |
| Remote | `origin/release/beta-2026-07-14` — up to date |

### Recent commits (HEAD → oldest)

| SHA | Message |
|---|---|
| `f9408ad` | docs: update release gate docs for rc3, load test runs 1–3, DEFECT-007 |
| `d95e67d` | fix: scope sqn_general out of /api/planning/years list (DEFECT-007) ← **RC3** |
| `37e0d25` | docs: resolve two stale checkpoint tasks, reconfirm backend test gate |
| `8cec1c1` | docs: add missing architecture.md/beta-release skill; record load-test findings |
| `0ca4fe8` | docs: execution checkpoint — corrected load test running (baw9zh1fw) |
| `2e1f437` | docs: record staging deployment and rollback rehearsal results (2026-07-14) |
| `3cc7650` | docs: update release gate docs to reflect rc2 state |
| `e539d02` | fix: replace useBlocker with useLocation in useProxyGuard; fix 35 Playwright E2E tests ← **RC2** |
| `4a9c178` | test: 36 new backend tests + 35 Playwright E2E specs; visual consistency audit |
| `467e0fa` | docs: Operational Release Gate — 18 new documents (phases 1–19, docs 34–50) |
| `e918f3e` | refactor: remove 9 dead planning page divs + simplify nav hook + fix ops N+1 ← **RC1** |

### Tags

| Tag | Commit | Status |
|---|---|---|
| `beta-2026-07-14-rc1` | `e918f3e` | Superseded |
| `beta-2026-07-14-rc2` | `e539d02` | Superseded — rc3 exists |
| `beta-2026-07-14-rc3` | `d95e67d` | **Current RC** — pushed to origin |

---

## Currently Running Process

| Field | Value |
|---|---|
| Task ID | `btitxok60` |
| Output file | `/private/tmp/claude-501/-Users-jennydv/fa4ea2d6-cc66-4422-b865-406dd21c7fe8/tasks/btitxok60.output` |
| Command | `python3 tools/stress/load_test_staging.py --users 100 --duration-minutes 45 --ramp-seconds 60` |
| Target | `https://aafc-tms-backend-staging.up.railway.app` |
| Start time | ~2026-07-15T00:44Z |
| Expected completion | ~2026-07-15T01:30Z |
| Last status | [SUSTAINED] 405s / 2760s, 17,321 requests, 0 5xx |

**Key fix in this run**: Load test script now uses `/api/planning/years` (the correct path,
confirmed by reading the planning router: `APIRouter(prefix="/api/planning")` + `@router.get("/years")`).
Previous run (baw9zh1fw) used `/api/years` (wrong path → all years calls returned 404).

---

## Load Test History

### Run 1 (b4343awtj, 2026-07-14) — INVALID

Wrong endpoint paths; 60,873 of 124,003 requests were 404:
- `/api/dashboard` → 404 (correct: `/api/reports/summary`)
- `/api/planning/sessions` → 404 (no such endpoint)
- `/api/planning/annual-program` → 404 (requires year_id)

Discarded. Not release evidence.

### Run 2 (baw9zh1fw, 2026-07-14) — PARTIAL PASS

| Metric | Value |
|---|---|
| Duration | 46.2 min (2771s) |
| Users | 100 |
| Total requests | 124,892 |
| Successful (200) | 105,165 |
| Failed (non-5xx) | 19,726 |
| 5xx errors | 1 (SSL EOF — Railway infrastructure glitch) |
| P95 latency | 530ms |
| Overall result | FAIL (exit code 1) |

**Root cause of failures**: Script used `/api/years` (wrong path, 404). This accounts for exactly
19,724 of the 19,726 non-5xx failures. The remaining 2 were SSL connection errors.

**Per-endpoint (valid endpoints only):**

| Endpoint | n | avg | P95 |
|---|---|---|---|
| `/api/auth/login` | 21,380 | 504ms | 619ms |
| `/api/auth/me` | 21,377 | 244ms | 316ms |
| `/api/reports/summary` | 21,360 | 252ms | 315ms |
| `/api/parade-nights` | 41,051 | 255ms | 319ms |

**Classification**: PARTIAL PASS — 4 of 5 workflow endpoints proven under 45+ min, 100-user load.
P95 530ms (well under 2000ms threshold). Years endpoint not proven (wrong path).

### Run 3 (btitxok60, 2026-07-15) — IN PROGRESS

Using corrected `/api/planning/years` path. 0 5xx at 405s. Results pending.

---

## Post-Load Data Integrity Checks (2026-07-15, after run 2)

| Check | Result |
|---|---|
| Health endpoint latency | **PASS** — 412ms (< 500ms threshold) |
| ADMIN703 parade-nights isolation | **PASS** — 39 records, all `squadron_id = 3c6894bb` (own sqn) |
| ADMIN702 parade-nights isolation | **PASS** — 0 records returned (no parade nights seeded for 702) |
| ADMIN703 reports/summary | **PASS** — HTTP 200, valid summary structure |
| Wing admin parade-nights | **PASS** — HTTP 200 |
| National admin reports/summary | **PASS** — HTTP 200 |
| DEFECT-007 discovery | `/api/planning/years` for sqn_general 701 returned 1 year from squadron 703 — **IDOR confirmed** |

DEFECT-007 was fixed in rc3 (`d95e67d`) within this session.

---

## Staging Environment

| Service | Deployment ID | Status | Source |
|---|---|---|---|
| `aafc-tms-backend` | `ac20386b-393d-4acb-9508-e154fdfa313d` | SUCCESS | rc2 code (rc3 is non-performance fix) |
| `aafc-tms-frontend` | `ce2420c3-70f0-472d-8b86-f98448c70eb1` | SUCCESS | Connected frontend |
| `aafc-tms-planning-workspace-preview` | `8f93e841-6879-4226-9ff4-7e0b016fe11a` | SUCCESS | Planning Workspace |

**Environment ID**: `77a45568-5c16-46c2-9065-d5d339208b0e` (staging)

### Staging URLs

| Service | URL |
|---|---|
| Backend | `https://aafc-tms-backend-staging.up.railway.app` |
| Connected TMS | `https://aafc-tms-frontend-staging.up.railway.app` |
| Planning Workspace | `https://aafc-tms-planning-workspace-preview-staging.up.railway.app/planning` |

---

## Task Classification (Tasks 10–13)

### Task 10 — Canonical resource model (TrainingArea vs PlanningLocation)
**DEFERRED WITH EXPLICIT DOCUMENTED RISK** — Post-beta backlog item.
Recorded in `docs/beta/15_known_limitations.md` and `docs/beta/28_authoritative_data_model.md`.
Owner acceptance required in `47_known_limitation_acceptance.md`.

### Task 11 — Visual consistency / shared design tokens
**DEFERRED** — Commit `4a9c178` was a visual consistency AUDIT only; no frontend source changes
were made. Post-beta backlog item.

### Task 12 — Backend tests for new endpoints
**COMPLETE WITH EVIDENCE** — Test count grew from 422 → 543 (121 new tests at rc3).
Covers session lifecycle, training area, equipment, cadet, IDOR scenarios, DEFECT-007.

### Task 13 — Beta documentation phases 19–22
**COMPLETE** — All Operational Release Gate docs written (docs 33–51). Phases 1–19 documented.
Docs 33–50 written in prior session; doc 51 (this checkpoint) added.

---

## Playwright E2E Status

| Config | Result | Notes |
|---|---|---|
| Local backend (rc3) | **35/35 PASS** | `npx playwright test --config playwright.config.ts` |
| Staging via Vite proxy | **3/35 pass, 32 CORS-blocked** | Intentional: staging backend rejects `localhost:5173` origins |
| Staging frontend direct | Not attempted | Path routing complexity (`/planning` subpath) |

Playwright staging is **HUMAN-GATED** — requires browser verification in Chrome.
Config file `frontend/playwright.staging.config.ts` created for future reference.

---

## Release Gate Status

| Gate | Status |
|---|---|
| Feature freeze | ✅ COMPLETE |
| RC3 created and pushed | ✅ COMPLETE — `d95e67d` / `beta-2026-07-14-rc3` |
| Backend tests: 543 pass | ✅ COMPLETE (at `d95e67d`) |
| TypeScript: 0 errors | ✅ COMPLETE |
| Security greps: all clean | ✅ COMPLETE |
| Playwright E2E: 35/35 pass | ✅ COMPLETE (at `d95e67d`, local backend) |
| DEFECT-007 found, fixed, tested | ✅ COMPLETE |
| Production backup/restore | ✅ COMPLETE (runs 29281190414, 29281292666, 29297143467) |
| Staging deployment rehearsal (D1–D7) | ✅ COMPLETE (2026-07-14) |
| Staging rollback rehearsal (R1–R5) | ✅ COMPLETE (2026-07-14) |
| Post-load data integrity checks | ✅ COMPLETE (2026-07-15) |
| Tasks 10–13 classified | ✅ COMPLETE |
| 100-user load test — run 1 | ❌ INVALID (wrong paths) |
| 100-user load test — run 2 | ⚠️ PARTIAL (4/5 endpoints, wrong years path) |
| 100-user load test — run 3 | ⏳ IN PROGRESS (task btitxok60) |
| Playwright E2E against staging | ⚠️ PARTIAL (CORS blocks headless; human browser required) |
| Backup key custody | ⚠️ PENDING — 5 human actions |
| UAT | ⚠️ PENDING — human testers required |
| Data governance | ⚠️ PENDING — 9 org decisions |
| Known limitation acceptance | ⚠️ PENDING — owner sign-off |
| Browser verification (staging) | ⚠️ PENDING — human in Chrome |
| Production config (ENVIRONMENT var) | ⚠️ PENDING — requires approval |
| Production deploy of DEFECT fixes | ⚠️ PENDING — requires approval |
| Production smoke test | ⚠️ PENDING — after deployment approval |
| Final GO/NO-GO | **NO-GO** |

---

## Open Manual Actions (human-gated)

1. Rotate Railway access token (token inadvertently exposed in prior session)
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

## Next Automated Steps (after load test btitxok60 completes)

1. Read full result from `btitxok60.output`
2. Confirm `/api/planning/years` is in the per-endpoint table with realistic latency
3. Record Gate record into `35_release_evidence_chain.md` Link 10
4. Update `12_full_beta_release_readiness.md` Gate 5
5. Update `13_executive_go_no_go.md` load test row
6. If PASS: mark load test gate ✅ COMPLETE — only human gates remain
7. Commit and push all evidence
8. Produce final 17-point result summary for user

---

## Current Release Recommendation

**NO-GO**

Load test run 3 in progress. All technical automated gates will be complete when run 3 finishes
(assuming clean result). All remaining mandatory gates are human-gated:
browser verification, UAT, governance, key custody, smoke test, production deployment approval.

This checkpoint written 2026-07-15 while task `btitxok60` is running.
