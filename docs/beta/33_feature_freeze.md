# AAFC TMS — Feature Freeze Record

Phase 1 (Operational Release Gate). Establishes the exact code boundary for the release candidate.
Created: 2026-07-14.

---

## Freeze Declaration

**Feature freeze is active** as of commit `2ecc2f4` on branch `release/beta-2026-07-14`.

| Item | Value |
|---|---|
| Freeze date/time | 2026-07-14 |
| Branch | `release/beta-2026-07-14` |
| Freeze commit | `2ecc2f4` — "fix+docs: final consolidation audit — phases 8-20 documentation suite" |
| Working tree at freeze | Clean |
| Backend tests at freeze | 503 passed, 1 skipped |
| TypeScript errors at freeze | 0 |

---

## Pre-Freeze Audit Results

### Uncommitted Files at Freeze
None. Working tree was clean before freeze.

### Unpushed Commits at Freeze
4 commits were ahead of origin at start of this phase. All 4 were pushed to `origin/release/beta-2026-07-14` as the first action of this phase.

### Open Migrations at Freeze
None pending. All 3 environments (local, staging, production) at Alembic head `x9y0z1a2b3c4` (v36).

Note: `stash@{0}` contains an uncommitted migration with a revision-ID collision (DEFECT-008). The stash is NOT applied and NOT part of this release. It must NOT be applied to the release branch.

### Temporary Debugging Code
None identified. `planner-debug-panel` (localhost-only debug overlay in Training Planner page) was part of the 9 dead HTML divs removed in this phase — it no longer exists in the file.

### Incomplete Frontend Work
None. All planned P0/P1 work is complete. The two pending P2 items (Task #10: canonical resource model, Task #11: visual consistency) are explicitly deferred to post-beta and do not affect current functionality.

### Placeholder or Mock Functions
None. All API methods call real backend endpoints. No mock data in production code paths.

### Worktrees
One orphan worktree at `96f2781` (`/Users/jennydv/Desktop/AAFC_TMS_National_Connected_Pilot_Package_v17_1_source/.claude/worktrees/agent-a384acc669dbfca9c`). This worktree is stale (pointing at an old commit) and not in active use. It contains no uncommitted changes relevant to this release.

---

## Post-Freeze Changes Made in This Phase

These changes were made after the freeze declaration commit and are included in the release candidate:

| Change | Reason | Affected gates | Test result |
|---|---|---|---|
| Remove 9 dead HTML page divs from `connected-frontend/index.html` (378 lines) | Dead code removal — no nav path to these pages; reduces file size, eliminates confusion | Phase 7 (visual), Phase 9 (code inventory) | 503 passed, 1 skipped |
| Simplify nav hook in `connected-frontend/index.html` (18 lines → 6 lines) | Dead case handlers for retired planning pages | Phase 9 (code inventory) | 503 passed, 1 skipped |
| Fix `rep_coverage` double call to `_all_sessions()` in `ops.py` | Performance — eliminates one redundant SQL query per curriculum-coverage report request | Phase 14 (performance) | 503 passed, 1 skipped |

---

## Open Blocker / High Defects at Freeze

| ID | Severity | Status | Why not blocking freeze |
|---|---|---|---|
| DEFECT-001 | BLOCKER | Fix on branch, not in production | Fix is committed and tested; production deploy is the pending action |
| DEFECT-003 | HIGH | Code fixed; Railway variable pending | Variable change requires approval; fix is ready |
| DEFECT-005 | HIGH | Fix on branch, not in production | Dockerfile fix committed and staging-verified; production deploy pending |
| DEFECT-008 | HIGH (process) | In stash, not in committed code | Stash is NOT part of the release candidate; does not affect freeze commit |

No defect in the freeze commit itself is unresolved. All open defects are production-deployment gaps (approved fixes exist on branch) or process issues in the stash.

---

## Accepted Medium / Low Defects

| Item | Severity | Acceptance rationale |
|---|---|---|
| Wing overview N+1 queries (16 sqn × 3 queries per request) | LOW | Acceptable at 16 squadrons; query count bounded; no user-facing failure |
| `TrainingArea` / `PlanningLocation` duplication | MEDIUM | Documented; workaround exists; post-beta merger planned |
| `facilitators` / `planning_facilitators` duplication | MEDIUM | Documented; workaround exists; post-beta merger planned |
| SQLite datetime adapter DeprecationWarning in tests | LOW | SQLite test-only; production uses PostgreSQL |
| No Playwright E2E coverage | LOW | Manual verification replaces automated browser tests for this release |
| `stash@{0}` unreviewed | INFO | Stash is local; does not affect deployed code |

---

## Permitted Changes After Freeze

Only the following categories may be added to the release candidate after this freeze:

- BLOCKER fixes (authentication bypass, cross-squadron data leak, data loss, corrupt database, unusable core workflow)
- HIGH-severity security fixes
- HIGH-severity data-integrity fixes
- Essential wording corrections (factually wrong user-facing text)
- Release documentation corrections (no code change)

Every post-freeze code change MUST:
1. State the reason (blocker/high/security/integrity/wording)
2. Identify which release gates are affected
3. Include a regression test
4. Be retested against the full test suite
5. Be recorded with the new commit SHA as a revised release candidate

After any post-freeze code change, the release candidate tag (`beta-2026-07-14-rc1`) MUST be moved to the new commit before production deployment.

---

## Freeze Enforcement

No merges from `main`, `feature/*`, or any other branch are permitted without:
- Full conflict resolution
- Full test suite pass
- Security review of changed files
- Gate re-evaluation

The stash (`stash@{0}`) must NOT be applied to this branch. It contains a migration revision-ID collision that would break the migration chain. Investigate and resolve stash conflicts independently before any future merge.
