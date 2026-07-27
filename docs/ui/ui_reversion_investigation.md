# UI Reversion Investigation

**Date:** 2026-07-22  
**Investigator:** Claude Code (automated)  
**Status:** ROOT CAUSE CONFIRMED — see Summary below

---

## Summary

The staging application shows retired nav items and missing features because **all restore work was committed to a local-only branch that was never pushed to GitHub** and therefore never deployed to Railway staging.

| Area | Expected version | Current version | Difference | Root cause | Correction |
|---|---|---|---|---|---|
| Main TMS frontend (staging) | `feature/restore-planning-workspace` @ `c72b6c0` | `origin/main` @ `bc40777` (deployed 2026-07-14) | 70 commits missing; Planning Workspace nav absent; Generate Activities absent; Facilitator tags absent; Dashboard charts absent; Annual Program/Training Planner nav present | Local branch `feature/restore-planning-workspace` was never pushed to `origin` | Push branch to `origin`, create PR or push to staging branch, redeploy `aafc-tms-frontend` |
| Planning Workspace frontend (staging) | Current local `frontend/` source | Build `index-C4Pw7BDd.js` deployed 2026-07-14 `8f93e841` | Two subsequent deploys FAILED (2026-07-21 `4e0fff0b`, `11f0ffec`) — unknown cause; header counters status unknown in deployed build | PW service deploy failures; need investigation | Fix PW build config, redeploy |
| Backend (staging) | 705 tests passing locally | `ac20386b` deployed 2026-07-14 | Missing: `/api/dashboard/charts`, `/api/activities/generate`, `/api/subject-area-tags` | Same as frontend — local commits never pushed | Push and deploy backend alongside frontend |

---

## Evidence

### 1. Local branch state

```
Branch:  feature/restore-planning-workspace
HEAD:    c72b6c0  feat(dashboard): chart-led dashboard with API-driven chart rendering
Parent:  20bb99e  (origin/next-stage/v1-operational)
```

Local commits NOT on `origin/main`:

```
c72b6c0  feat(dashboard): chart-led dashboard with API-driven chart rendering
40d3bda  docs: update Beta User Guide
dd45bee  feat: staging deployment preflight guard
04e9ed3  feat: restore Annual Program DOM, Generate Activities, Dashboard graphs
220bd4c  feat: add activity generation endpoint
cb752a2  feat: restore Planning Workspace nav, Activities holiday, Parade Nights generator, Facilitator tags
48024db  feat: add SubjectAreaTag model, API, migration, PLANNING_WORKSPACE_URL config
```

Plus 63 more commits from `next-stage/v1-operational` that are also not on `origin/main`.

### 2. Staging deployed version

| Property | Value |
|---|---|
| Service | `aafc-tms-frontend` |
| Deployment ID | `ce2420c3-70f0-472d-8b86-f98448c70eb1` |
| Deployed | 2026-07-14 08:53 AWST |
| Source | `origin/main` @ `bc40777` |
| File size | 483,792 bytes (gzip transfer) |

Local `index.html` at `c72b6c0`: **500,998 bytes** — 17,206 bytes larger, confirming none of the restore commits are deployed.

### 3. Feature presence comparison

| Feature | Staging (deployed `bc40777`) | Local (`c72b6c0`) |
|---|---|---|
| Annual Program nav item | ✅ Present (18 occurrences) | ❌ Absent — removed in `acbcf54` |
| Training Planner nav item | ✅ Present (8 occurrences) | ❌ Absent — removed in `acbcf54` |
| Planning Workspace nav link | ❌ Absent | ✅ Present — added in `cb752a2` |
| Generate Activities | ❌ Absent | ✅ Present — added in `04e9ed3`/`220bd4c` |
| Facilitator tags | ❌ Absent | ✅ Present — added in `cb752a2`/`48024db` |
| Dashboard charts (API-driven) | ❌ Absent | ✅ Present — added in `c72b6c0` |
| loadDashCharts() | ❌ Absent | ✅ Present |
| Add Holiday button | ✅ Present | ✅ Present |
| Mission Backlog | — (Planning Workspace) | — (Planning Workspace) |

### 4. Remote branch inventory

| Branch | Commit | index.html size |
|---|---|---|
| `origin/main` | `bc40777` | 483,795 bytes ← **what staging is running** |
| `origin/next-stage/v1-operational` | `20bb99e` | 462,412 bytes |
| `feature/restore-planning-workspace` | `c72b6c0` | 500,998 bytes ← **local only, never pushed** |
| `origin/feature/planning-workspace` | `620c896` | 502,009 bytes |

### 5. Root cause classification

**This is NOT a reversion.** The changes were never deployed because:

1. `feature/restore-planning-workspace` was created from `next-stage/v1-operational` locally.
2. All 7 restore commits were made locally.
3. **The branch was never pushed to `origin`** (`git branch -r | grep restore` returns nothing).
4. Railway staging auto-deploys from `origin/main` (or a linked GitHub branch), which last deployed on 2026-07-14 and does not include any restore commits.
5. No `railway up` or GitHub push was performed that would have triggered a redeploy.

### 6. Planning Workspace deploy failures (2026-07-21)

Two PW deploys FAILED:
- `4e0fff0b` — 2026-07-21 17:17 AWST — FAILED
- `11f0ffec` — 2026-07-21 17:10 AWST — FAILED

Previous successful deploy `8f93e841` — 2026-07-14 08:53 AWST — still active.

Root cause of PW failures: unknown without Railway build logs. Likely a Node/Vite dependency or build script issue introduced in the worktree. The local PW source builds cleanly (`npm run build` passes).

### 7. Backend staging state

Backend staging (`ac20386b`, 2026-07-14) does NOT have:
- `GET /api/dashboard/charts` (added in `c72b6c0`)
- `GET /api/activities/generate` (added in `220bd4c`)
- `GET/POST /api/subject-area-tags` (added in `48024db`)
- Alembic migrations v37–v39 (subject area tags, dashboard schema)

---

## Correction Plan

1. Complete local UI cleanup (Phases 2–12 of the consolidation plan).
2. Push `feature/restore-planning-workspace` (or a clean merge branch) to `origin`.
3. Obtain explicit "DEPLOY TO STAGING <COMMIT_SHA>" approval.
4. Deploy `aafc-tms-frontend`, `aafc-tms-backend`, and `aafc-tms-planning-workspace-preview` to staging.
5. Verify deployed commit matches pushed commit.
6. Visual browser verification in private window.

---

## What was NOT the cause

- Not a Railway rollback (no rollback action was taken — deployment `ce2420c3` has been the only frontend deploy since 2026-07-14).
- Not a wrong-branch deploy (Railway deployed from the correct linked branch at the time; that branch just predates the restore work).
- Not a browser cache issue (the staging HTML file itself is the pre-restore version).
- Not a service-worker cache (the frontend uses nginx static serving, no service worker).
- Not a merge/cherry-pick omission (there was no merge attempt — the branch was never pushed at all).
- Not a later commit reintroducing retired UI (no commits on the deployed branch after 2026-07-14).

---

*Generated by automated investigation — 2026-07-22*
