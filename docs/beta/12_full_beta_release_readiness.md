# AAFC TMS — Full Beta Release Readiness Checklist

Gate document for beta release of v17.1.
Created: 2026-07-14. Updated with Operational Release Gate (Phases 1–19) additions.

---

## Gate 1: Code Quality

| Check | Required | Status | Evidence |
|---|---|---|---|
| Backend tests: all pass | 0 failures | ✅ PASS | 541 passed, 1 skipped (2026-07-14, commit e539d02) |
| TypeScript: 0 errors | 0 errors | ✅ PASS | `npx tsc --noEmit` (2026-07-14) |
| No `datetime.utcnow()` deprecations | 0 in production code | ✅ PASS | Grep clean (2026-07-14) |
| Security grep 1: removed wording | 0 matches | ✅ PASS | Grep clean (2026-07-14) |
| Security grep 2: code exposure | 0 matches | ✅ PASS | Grep clean (2026-07-14) |
| Security grep 3: seeded codes in frontend | 0 matches | ✅ PASS | Grep clean (2026-07-14) |
| Security grep 4: secrets in frontend | 0 matches | ✅ PASS | Grep clean (2026-07-14) |

---

## Gate 2: Migration and Schema

| Check | Required | Status | Evidence |
|---|---|---|---|
| Local alembic head | Match staging and prod | ✅ PASS | `x9y0z1a2b3c4` in all 3 environments |
| Staging schema matches | Same as local | ✅ PASS | Confirmed via restore test run |
| Production schema matches | Same as local | ✅ PASS | `29297143467` |
| Migration chain is linear | No branches | ✅ PASS | `test_compute_alembic_head.py` |

---

## Gate 3: Security

| Check | Required | Status | Evidence |
|---|---|---|---|
| IDOR fix: sqn_general scope | Deployed + tested | ⚠️ PARTIAL | Fixed on branch; not in production |
| IDOR fix: other scopes | Deployed + tested | ✅ PASS | `test_planning_idor.py` — 50 scenarios |
| Rate limiting (IP lockout) | Proven in tests | ✅ PASS | `test_lockout.py` |
| Per-account lockout | Proven in tests | ✅ PASS | `test_lockout.py` |
| Maintenance mode blocks | Proven in tests | ✅ PASS | `test_maintenance_enforcement.py` |
| `ENVIRONMENT=production` in prod | Must not be `staging` | ⚠️ PENDING | Approval required |
| Access codes: no plaintext in API | Verified | ✅ PASS | `test_hardening.py` + grep |
| JWT secret: not default | Must be set | ✅ PASS | Railway env var set (not default) |
| CORS: no wildcard | Must be locked | ✅ PASS | `CORS_ALLOWED_ORIGINS` env var set per environment |

---

## Gate 4: Backup and Recovery

| Check | Required | Status | Evidence |
|---|---|---|---|
| Production backup mechanism | Working | ✅ PASS | Run `29281190414` |
| Production restore | Proven | ✅ PASS | Run `29281292666` |
| Application-level restore | Proven | ✅ PASS | Run `29297143467` |
| Daily backup schedule | Active | ✅ PASS | `.github/workflows/backup-postgresql.yml` |
| Weekly restore-test schedule | Active | ✅ PASS | `.github/workflows/test-restore-postgresql.yml` |
| Backup key custody | Human checklist | ⚠️ PENDING | `36_backup_key_custody_checklist.md` — 5 human actions |

---

## Gate 5: Deployment

| Check | Required | Status | Evidence |
|---|---|---|---|
| Staging backend: online | Must be online | ✅ PASS | Health endpoint returns 200 (2026-07-14) |
| Staging frontend: online | Must be online | ✅ PASS | Deployment `ce2420c3` online |
| Staging Planning Workspace: online | Must be online | ✅ PASS | Deployment `8f93e841` online |
| Staging: 16 squadrons loaded | Must all be present | ✅ PASS | `{"status":"ready","squadrons":16}` |
| Production backend: online | Must be online | ✅ PASS | Deployment `20405760` online |
| Production frontend: online | Must be online | ✅ PASS | Deployment `719cc4c8` online |
| Production Planning Workspace | Dockerfile fix deployed | ⚠️ PENDING | Fix on branch; stale build in prod |
| Branch fixes deployed to prod | Required for GA | ⚠️ PENDING | DEFECT-001, DEFECT-003, DEFECT-005 |
| Deployment rehearsal (staging) | Must be completed | ✅ PASS | D1–D7 executed 2026-07-14; all automated steps PASS; D7 browser steps human-gated |
| Rollback rehearsal (staging) | Must be completed | ✅ PASS | R1–R5 executed 2026-07-14; rollback `a76198bf` SUCCESS; R5 RC re-deployed |
| RC tag pushed to origin | Must be pushed | ✅ DONE | `beta-2026-07-14-rc2` at e539d02 — pushed to origin 2026-07-14 |
| Playwright E2E: 35 tests pass | 0 failures | ✅ PASS | 35/35 at commit e539d02 (2026-07-14) |
| 100-user concurrent load test | Mandatory pre-release | ❌ NOT DONE | Must run against staging before production |

---

## Gate 6: Documentation

| Document | Required | Status |
|---|---|---|
| `24_final_consolidation_state.md` | Phase 0 state | ✅ Written |
| `25_page_and_function_inventory.md` | Phase 1 inventory | ✅ Written |
| `26_squadron_verification_matrix.md` | Phase 2 matrix | ⚠️ BLOCKED (browser) |
| `27_role_and_navigation_rationalisation.md` | Phase 3 roles | ✅ Written |
| `28_authoritative_data_model.md` | Phase 8 model | ✅ Written |
| `29_code_inventory_and_review.md` | Phase 9 inventory | ✅ Written |
| `15_known_limitations.md` | Limitations register | ✅ Written |
| `18_plugin_utilisation_report.md` | Dependency audit | ✅ Written |
| `30_final_consolidation_report.md` | Consolidation summary | ✅ Written |
| `31_final_user_workflow_review.md` | Workflow review | ✅ Written |
| `32_final_stress_and_resilience_report.md` | Stress/resilience | ✅ Written |
| `33_feature_freeze.md` | Feature freeze record | ✅ Written |
| `34_release_candidate_record.md` | RC evidence | ✅ Written |
| `35_release_evidence_chain.md` | Evidence chain | ✅ Written (PENDING population) |
| `36_backup_key_custody_checklist.md` | Key custody | ✅ Written (PENDING human actions) |
| `37_user_acceptance_test_plan.md` | UAT plan | ✅ Written |
| `38_user_acceptance_results.md` | UAT results | ✅ Written (PENDING UAT) |
| `39_account_and_role_release_matrix.md` | Account matrix | ✅ Written (PENDING account creation) |
| `40_production_configuration_review.md` | Config review | ✅ Written (PENDING ENVIRONMENT var) |
| `41_deployment_rehearsal.md` | Deployment rehearsal | ✅ Written (PENDING execution) |
| `42_release_stop_and_rollback_plan.md` | Rollback plan | ✅ Written |
| `43_release_monitoring_plan.md` | Monitoring plan | ✅ Written |
| `44_beta_release_communication.md` | User communication | ✅ Written |
| `45_support_triage_guide.md` | Triage guide | ✅ Written |
| `46_data_governance_and_approval.md` | Governance | ✅ Written (PENDING approvals) |
| `47_known_limitation_acceptance.md` | Limitation acceptance | ✅ Written (PENDING owner sign-off) |
| `48_final_production_smoke_test.md` | Smoke test plan | ✅ Written |
| `49_all_at_once_release_control.md` | Release control | ✅ Written |
| `50_post_release_review_plan.md` | Post-release plan | ✅ Written |
| `12_full_beta_release_readiness.md` | This document | ✅ Written |
| `13_executive_go_no_go.md` | GO/NO-GO decision | ✅ Written (CONDITIONAL) |

---

## Gate 7: Human Acceptance and Verification

| Check | Required | Status | Evidence source |
|---|---|---|---|
| Browser login: sqn_admin | Must work | ⚠️ PENDING | `26_squadron_verification_matrix.md` |
| Browser login: sqn_general | Must work | ⚠️ PENDING | `26_squadron_verification_matrix.md` |
| Browser login: wing_admin | Must work | ⚠️ PENDING | `26_squadron_verification_matrix.md` |
| Browser login: national_admin | Must work | ⚠️ PENDING | `26_squadron_verification_matrix.md` |
| Planning Workspace: no second login | Must work | ⚠️ PENDING | `31_final_user_workflow_review.md` |
| UAT: 20 tasks completed by 4 testers | Required | ⚠️ PENDING | `38_user_acceptance_results.md` |
| Data governance sign-off | Required | ⚠️ PENDING | `46_data_governance_and_approval.md` |
| Known limitation acceptance | Required | ⚠️ PENDING | `47_known_limitation_acceptance.md` |
| Backup key custody: 5 human actions | Required | ⚠️ PENDING | `36_backup_key_custody_checklist.md` |
| Production deployment approval | Required | ⚠️ PENDING | Explicit approval from project owner |
| Smoke test: all 20 steps PASS | Required | ⚠️ PENDING | `48_final_production_smoke_test.md` |

---

## Gate Summary

| Gate | Status | Blocker |
|---|---|---|
| 1: Code Quality | ✅ PASS | — |
| 2: Migration and Schema | ✅ PASS | — |
| 3: Security | ⚠️ PARTIAL | DEFECT-001, DEFECT-003 awaiting deploy |
| 4: Backup and Recovery | ⚠️ PARTIAL | Backup key custody (human) |
| 5: Deployment | ⚠️ PARTIAL | Deployment rehearsal DONE; rollback rehearsal DONE; RC tag pushed; load test NOT DONE; DEFECT deploys pending |
| 6: Documentation | ⚠️ PARTIAL | All docs written; 26 blocked (browser); governance pending |
| 7: Human Acceptance | ⚠️ PENDING | UAT, browser verification, approvals, smoke test |

**Overall**: 2 of 7 gates fully cleared (Code Quality; Migration/Schema).

**Completed since last update (2026-07-14, commit e539d02, tag `beta-2026-07-14-rc2`):**
- Backend tests: 541 passed (36 new session-lifecycle, training-area, equipment, cadet tests)
- Playwright E2E: 35/35 passing (root cause: `useBlocker` crash in `useProxyGuard` fixed)
- RC2 tag created at e539d02

**Completed since last update (2026-07-14, rehearsal executed):**
- RC tag `beta-2026-07-14-rc2` pushed to origin
- Staging deployment rehearsal (D1–D7): all automated steps PASS; deployment `72b45f4b`/`ac20386b` SUCCESS
- Staging rollback rehearsal (R1–R5): rollback `a76198bf` SUCCESS; RC re-deployed; health confirmed

**Remaining mandatory technical gates before production approval may be requested:**
1. 100-user concurrent load test against staging (45 minutes minimum)
2. D7 browser smoke test steps (human tester required)
3. Deploy DEFECT-001, DEFECT-003, DEFECT-005 fixes to production

**Then human gates:**
6. UAT, governance, key custody, browser verification, smoke test, explicit approval
