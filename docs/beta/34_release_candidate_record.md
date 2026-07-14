# AAFC TMS — Release Candidate Record

Phase 2 (Operational Release Gate). Immutable record of the release candidate.
Created: 2026-07-14.

---

## Release Candidate

| Field | Value |
|---|---|
| Tag | `beta-2026-07-14-rc1` |
| Commit SHA | `e918f3e654179355fe100fda285452844bdcbea0` |
| Short SHA | `e918f3e` |
| Branch | `release/beta-2026-07-14` |
| Author | Jenny DV |
| Timestamp | 2026-07-14 |
| Description | "refactor: remove 9 dead planning page divs + simplify nav hook + fix ops N+1" |

---

## Intended Changes vs Baseline

Baseline: `main` branch, commit `96f2781`

| Commit | Description | Category |
|---|---|---|
| `f303895` | fix: bootstrap-staging used ad-hoc ENVIRONMENT check instead of settings.is_prod | Security fix |
| `4cf162e` | docs: ENVIRONMENT/COOKIE_SAMESITE investigation | Documentation |
| `f7c53c5` | docs: point to ENVIRONMENT/SameSite investigation | Documentation |
| `8ed7b85` | docs: browser-level E2E verification | Documentation |
| `e25343b` | ui: final nav/UI clean-up — retire 4 planning pages, remove tabs, chips, subtitles | UI rationalisation |
| `67e8f13` | fix: sqn_general IDOR gap + utcnow deprecations | Security fix |
| `28ae7a0` | test+docs: 17 new backend tests + Phase 0/1 docs | Test expansion |
| `2ecc2f4` | fix+docs: final consolidation audit phases 8-20 | Code fix + documentation |
| `e918f3e` | refactor: remove 9 dead HTML divs, simplify nav hook, fix ops N+1 | Dead code removal + performance |

---

## Migrations Included

No new migrations are introduced in this release candidate compared to `main`. Both share Alembic head `x9y0z1a2b3c4` (v36). All 3 environments (local, staging, production) are already at this revision.

---

## Changed Files (since branching from main)

Key changed files by category:

**Security fixes**:
- `backend/app/routers/planning.py` — sqn_general scope restriction in `_require_year_access`; utcnow fix
- `backend/app/routers/system.py` — bootstrap-staging ENVIRONMENT check via `settings.is_prod`

**UI rationalisation**:
- `connected-frontend/index.html` — retired 4 nav pages; removed 9 dead HTML divs; simplified nav hook; removed 2 drawer tabs, 2 health chips, 4 ph-sub subtitles

**React frontend**:
- `frontend/src/components/planning/PlanningBottomDrawer.tsx` — removed Training Planner and Import Review tabs
- `frontend/src/components/planning/PlanningContextBar.tsx` — removed conflicts/unscheduled chips

**Backend fixes**:
- `backend/app/routers/ops.py` — eliminated duplicate `_all_sessions()` call in `rep_coverage`
- `backend/tests/test_lockout.py` — datetime.utcnow() deprecation fix
- `backend/scripts/import_wing_hq_calendar.py` — datetime.utcnow() deprecation fix

**Tests**:
- `backend/tests/test_planning.py` — 17 new tests (sqn_general scope, xlsx exports, night-summaries, facilitator workload)

**Documentation**:
- `docs/beta/` — 13 new documents (Phases 0–20, 33)

---

## Pre-Tag Verification

| Check | Result |
|---|---|
| Working tree clean before tag | ✓ |
| No secret files staged | ✓ |
| No .env files staged | ✓ |
| No production dump staged | ✓ |
| No private keys staged | ✓ |
| Tests not being skipped | ✓ (1 skip is a pre-existing known test skip, not a suppression) |
| Backend tests | 503 passed, 1 skipped |
| TypeScript | 0 errors |
| Security greps (4 checks) | All 0 matches |

---

## Release Candidate Integrity

This tag is the single authoritative reference for the beta release.

**Do not test one commit and deploy another.**

If any post-freeze change is required:
1. Apply the fix to `release/beta-2026-07-14`
2. Re-run the full test suite
3. Move the tag: `git tag -f beta-2026-07-14-rc1 <new-commit>`
4. Push both the branch and the tag
5. Re-evaluate all affected release gates
6. Document the change in this record and in `33_feature_freeze.md`

---

## Deployment Instructions (staging → production)

The release candidate must be deployed from this exact commit. Deployment is via `railway up` from a clean checkout of `e918f3e`. The deployment sequence is defined in `41_deployment_rehearsal.md`.

**Production deployment requires explicit approval from the authorised project owner.** Record approval here before executing.

| Approval | Name | Date | Signature |
|---|---|---|---|
| Production deployment approval | ___________________ | ___________ | ___________ |
