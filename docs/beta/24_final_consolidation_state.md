# AAFC TMS — Final Consolidation State Capture

Document type: Phase 0 state capture for the final consolidation and release audit.
Created: 2026-07-14. Update in place; stale entries are worse than none.

---

## Repository

| Item | Value |
|---|---|
| Branch | `release/beta-2026-07-14` |
| HEAD (at Phase 0 capture) | `8ed7b85` — "docs: browser-level E2E verification" |
| HEAD (after Phase 0 fixes) | `67e8f13` — "fix: close sqn_general IDOR gap + utcnow deprecation" |
| Working tree | Clean |
| Stash | `stash@{0}` — large prior-session WIP (709 insertions, 20 files, "other-session-wip-v35-v36-frontend"). Not applied — conflicts with current state. Left for investigation. |
| Open worktrees | Orphan at `96f2781` (`worktree-agent-a384acc669dbfca9c`) — stale, not in active use |
| Alembic head (local) | `x9y0z1a2b3c4` (v36) |

---

## Deployments

### Staging (`77a45568-5c16-46c2-9065-d5d339208b0e`)

| Service | Status | Deployment ID | Commit trackable | URL |
|---|---|---|---|---|
| aafc-tms-backend | Online | `2ad00fec` | No (railway up upload) | `aafc-tms-backend-staging.up.railway.app` |
| aafc-tms-frontend | Online | `ce2420c3` | No | `aafc-tms-frontend-staging.up.railway.app` |
| aafc-tms-planning-workspace-preview | Online | `8f93e841` | No | `aafc-tms-planning-workspace-preview-staging.up.railway.app` |
| Postgres | Online | `e65ad729` | — | — |

Staging health: `{"status":"ready","squadrons":16}` ✓
Staging schema revision: `x9y0z1a2b3c4` (confirmed via application-level restore test run `29297143467`)

### Production (`571a8028-3640-4542-a4ab-7a1ee6b1f693`)

| Service | Status | Deployment ID | Notes |
|---|---|---|---|
| aafc-tms-backend | Online | `20405760` (2026-07-12T18:29Z) | IDOR partially unfixed; ENVIRONMENT=staging; no commit hash |
| aafc-tms-frontend | Online | `719cc4c8` (2026-07-11T22:56Z) | Pre-UI-cleanup; planning nav items still live |
| aafc-tms-planning-workspace-preview | Online (stale) | Deploy failed 2026-07-12 | Dockerfile fix on branch, not deployed |

Production schema revision: `x9y0z1a2b3c4` (confirmed via restore test run `29297143467`, row counts: wings=8, squadrons=16, users=39, audit_logs=441, curriculum_items=217, planning_years=10)

**Note**: Every production deployment was made via `railway up` from a local working tree (`meta.commitSha: null`). Deployed code cannot be traced to a specific git commit. Deployment IDs and timestamps are the authoritative record.

---

## Test Results (at capture)

| Suite | Result | Run |
|---|---|---|
| Backend (`python -m pytest tests/ -q`) | **490 passed, 1 skipped** | 2026-07-14, post-Phase-0-fixes |
| Frontend TypeScript (`npx tsc --noEmit`) | **0 errors** | 2026-07-14 |
| Frontend unit tests (Vitest) | 4 files, 8 tests, all pass | Previously verified |
| Playwright E2E | Not configured / no coverage | — |

---

## Alembic Migration State

| Environment | Schema revision | Source |
|---|---|---|
| Local | `x9y0z1a2b3c4` (v36) | `alembic heads` |
| Staging | `x9y0z1a2b3c4` | Application-level restore test |
| Production | `x9y0z1a2b3c4` | Restore test run `29297143467` |

All three environments match. Migration chain is linear (no branches in committed files).

---

## Defect Register (at capture)

| ID | Severity | Title | Status | Production |
|---|---|---|---|---|
| DEFECT-001 | BLOCKER | IDOR on facilitator-leave, notices, CEA + sqn_general gap | Fixed on branch + `sqn_general` gap fixed `67e8f13`; **not deployed to production** | Live IDOR partially closed by `main` commit, sqn_general gap live |
| DEFECT-002 | HIGH | seed_all.py unconditionally destructive | **Fixed** (`9e7a179`) | Irrelevant to production |
| DEFECT-003 | HIGH | Production ENVIRONMENT=staging | Code-fixed (`f303895`); variable change **pending approval** | `bootstrap-staging` endpoint reachable by system_admin |
| DEFECT-004 | N/A | COOKIE_SAMESITE=none | Resolved as correct by architecture | N/A |
| DEFECT-005 | HIGH | Planning Workspace Dockerfile missing | Fixed on branch; **not deployed to production** | Stale build served |
| DEFECT-006 | BLOCKER | Backup/restore never succeeded | **Resolved end-to-end** (run `29297143467`) | — |
| DEFECT-007 | LOW | Vitest executing Playwright specs | **Fixed** | — |
| DEFECT-008 | HIGH (process) | Migration revision-ID collision in stash | Stash not applied; collision is in WIP stash, not committed files | Not in production |

**Release blockers remaining**: DEFECT-001 (production deploy), DEFECT-003 (approval required), DEFECT-005 (production deploy)

---

## Code Inventory Summary

### Backend

| Item | Count |
|---|---|
| Router files | 13 |
| Endpoints (`@router.*`) | 206 |
| Model files | 6 |
| Migration files | 26 (v1–v36 sequential) |
| Test files | 11 |
| Test cases | 490 passing |

### Connected-frontend (`connected-frontend/index.html`)

| Item | Count |
|---|---|
| Total page divs (`id="page-*"`) | 30 |
| Navigable in at least one scope | 21 |
| Hidden/retired (in HTML, no nav path) | 9 |
| Nav scopes | 5 (squadron, wing, national, auditor, system_admin) |

### React Planning Workspace (`frontend/`)

| Item | Count |
|---|---|
| Source files (`.tsx`/`.ts`, excl. tests) | 58 |
| Registered routes | 22 |
| Planning components | 16 |
| API methods | ~60 (in `api/index.ts`) |

---

## Backup Status

| Item | Status | Evidence |
|---|---|---|
| Production backup mechanism | Proven working | Run `29281190414` — 432,758-byte dump |
| Production restore (PostgreSQL) | Proven | Run `29281292666` — schema + row counts verified |
| Production restore (application-level) | Proven | Run `29297143467` — 8 authenticated API reads succeeded |
| Daily backup schedule | Active | `.github/workflows/backup-postgresql.yml` |
| Weekly restore-test | Active | `.github/workflows/test-restore-postgresql.yml` |

---

## Outstanding Items at Phase 0 Capture

The following items require human action or are gated on approval:

1. **Production deploy approval** — DEFECT-001, DEFECT-003, DEFECT-005 all require a production deployment that must be explicitly approved before execution.
2. **Production ENVIRONMENT variable change** — Prepared, verified safe, awaiting approval. Change: set `ENVIRONMENT=production` on `aafc-tms-backend` in production environment.
3. **Squadron verification matrix (Phase 2)** — Requires browser login as each of 16 squadrons in staging. Machine cannot self-execute.
4. **Role navigation testing (Phase 3)** — Requires browser sessions per role.
5. **Load test (Phase 15)** — Requires staging load test runner (Locust or k6), schedule, and explicit approval to run against staging.
6. **Chaos testing (Phase 16)** — Requires Railway infrastructure access to simulate restarts, controlled network disruption.
7. **Visual consistency review (Phase 7)** — Requires browser review at multiple zoom levels.

Items that can be executed without human intervention are documented in `25_page_and_function_inventory.md` (Phase 1) and subsequent phase documents.
