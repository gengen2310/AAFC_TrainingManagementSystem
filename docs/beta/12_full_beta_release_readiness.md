# AAFC TMS — Full Beta Release Readiness Checklist

Gate document for beta release of v17.1.
Created: 2026-07-14. Updated in place as gates are cleared.

---

## Gate 1: Code Quality

| Check | Required | Status | Evidence |
|---|---|---|---|
| Backend tests: all pass | 0 failures | ✅ PASS | 503 passed, 1 skipped (2026-07-14) |
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
| `12_full_beta_release_readiness.md` | This document | ✅ Written |
| `13_executive_go_no_go.md` | GO/NO-GO decision | ✅ Written |

---

## Gate 7: Browser Verification (Human-Gated)

| Check | Required for beta | Status |
|---|---|---|
| Connected-frontend loads in browser | Must load | ⚠️ PENDING |
| Login as sqn_admin: squadron pages visible | Must work | ⚠️ PENDING |
| Login as sqn_general: planning nav items NOT visible | Must be absent | ⚠️ PENDING |
| Login as wing_admin: wing pages visible | Must work | ⚠️ PENDING |
| Login as system_admin: system console loads | Must work | ⚠️ PENDING |
| Planning Workspace loads at `/planning` | Must load | ⚠️ PENDING |
| Planning Workspace: 7 bottom tabs visible | Exact count | ⚠️ PENDING |
| No console errors on any page | 0 errors | ⚠️ PENDING |
| CEA import: file upload works | End-to-end | ⚠️ PENDING |
| Weekly program: printable output renders | Must render | ⚠️ PENDING |

---

## Gate Summary

| Gate | Status | Blocker |
|---|---|---|
| 1: Code Quality | ✅ PASS | — |
| 2: Migration and Schema | ✅ PASS | — |
| 3: Security | ⚠️ PARTIAL | DEFECT-001, DEFECT-003 awaiting deploy |
| 4: Backup and Recovery | ✅ PASS | — |
| 5: Deployment | ⚠️ PARTIAL | Branch fixes not in production; Planning Workspace stale |
| 6: Documentation | ⚠️ PARTIAL | `26_squadron_verification_matrix.md` blocked (browser) |
| 7: Browser Verification | ⚠️ PENDING | Human action required |

**Overall**: 3 of 7 gates fully cleared. The 4 partial/pending gates are all blocked by the same root cause: production deployment of branch fixes (DEFECT-001, DEFECT-003, DEFECT-005) + browser verification. Once those are actioned, gates 3, 5, 6, and 7 can be cleared.

**Recommendation**: Obtain approval for production deployment, deploy branch fixes, complete browser verification matrix, then sign off as release-ready.
