# Final UI Root Cause — why requested changes were not visible on staging

Investigated 2026-07-23. Evidence below is from direct inspection of the live Railway services and
a byte-level diff against the actual local source — not inferred from git history alone.

---

## Summary

There are **two distinct, unrelated root causes**, not one:

1. **Deployment staleness.** `aafc-tms-frontend` (Main TMS, `connected-frontend/index.html`) and
   `aafc-tms-planning-workspace-preview` (React Planning Workspace) on staging are both running
   builds that predate real, already-implemented local commits. Nobody redeployed after that work
   landed.
2. **A missing environment variable.** The Planning Workspace nav link's visibility is gated by
   `PLANNING_WORKSPACE_URL` on the backend — that variable is **not set at all** on the staging
   backend service, so the link is permanently hidden regardless of what frontend build is deployed.

A third finding, not a "cause" but load-bearing for scoping the rest of this work: **several of the
requested changes (Annual Program retirement, Training Summary merge, parade night generator,
holiday management, Mission Backlog cleanup, dashboard chart redesign) do not exist in the local
source at all yet** — confirmed by diffing local source against deployed content and finding
identical occurrence counts for these specific terms. These are outstanding feature work, not a
deploy or configuration defect.

---

## 1. How these services are actually deployed

All three staging services were inspected via `railway status --json` (project
`f5d9524f-8a57-44ff-86b7-ab66aec00e73`, environment `staging`, id `77a45568-5c16-46c2-9065-d5d339208b0e`).

| Service | Service ID | Active deployment ID | Deployed at (UTC) | Builder | Dockerfile |
|---|---|---|---|---|---|
| `aafc-tms-backend` | `deb53faa-ca8d-4291-aa2e-9ff3029c50f8` | `674cbc7c-bfcf-475a-9f88-352b37a8f47a` | 2026-07-21T23:30:29Z | DOCKERFILE | `/Dockerfile` |
| `aafc-tms-frontend` | `2b5e6359-2523-4209-be5b-bdf7f5273ec5` | `3a7362f8-05cc-410f-a3b0-3f66d5a6603f` | 2026-07-21T23:30:36Z | DOCKERFILE | `/Dockerfile` |
| `aafc-tms-planning-workspace-preview` | `253cf237-1836-43bc-9ee4-0e4eefd447b4` | `8f93e841-6879-4226-9ff4-7e0b016fe11a` | **2026-07-14T00:53:22Z** | DOCKERFILE | `/Dockerfile` |

Every deployment across all three services (checked back through the full deployment history
already documented in `docs/beta/00_release_state.md`) has `meta.cliCaller: "claude_code"` and
`meta.commitSha: null`, `meta.branch: null`, `meta.repo: null`. **None of these services are
connected to GitHub for CI/CD.** Every deploy to date has been a manual `railway up`/`railway
deployment up` snapshot upload of a local directory — there is no automatic "push to branch X →
Railway rebuilds" pipeline. This matters for the fix: redeploying means literally re-running that
upload command from current local source, not just merging a PR.

`rootDirectory: null` in each deployment's own metadata is consistent with the established practice
(see `docs/beta/00_release_state.md`) of running `railway up`/`railway deployment up <dir>
--path-as-root --service <name>` **from inside** the relevant subdirectory (`backend/`,
`connected-frontend/`, `frontend/`) so that directory's own `Dockerfile` is uploaded as `/Dockerfile`
of the deploy root. There is no Railway-side "root directory" misconfiguration — the risk here is
entirely about *which local directory a human/agent happened to be in* when `railway up` was last
run for each service, and whether that was run again after later commits.

## 2. Proof `aafc-tms-frontend` is serving a stale build

Fetched the live page and diffed byte-for-byte against local `connected-frontend/index.html`
(excluding the `<meta name="aafc-api-base">` line, which is legitimately rewritten per-environment
by `docker-entrypoint.sh`):

```
curl -s https://aafc-tms-frontend-staging.up.railway.app/ -o /tmp/staging_index.html
diff <(grep -v aafc-api-base connected-frontend/index.html) <(grep -v aafc-api-base /tmp/staging_index.html)
```

Real, functional differences found (local has, deployed lacks):
- `<meta name="app-build" content="__APP_BUILD__">` — the build-fingerprint tag entirely absent from
  the deployed page (added in commit `0cc46ab`).
- The entire mobile hamburger-menu implementation: `.btn-hamburger`, `.nav-overlay`,
  `toggleMobileNav()`/`closeMobileNav()`, and the responsive `.sidenav` rules — deployed only has
  `.sidenav{display:none;}` with no mobile toggle at all (added in commit `483161e`).
- The System Console "Build Information" block that reads the `app-build` meta tag and displays
  commit/build time — absent from deployed (added in `0cc46ab`).
- An `api()` calling-convention difference: deployed still calls
  `api('GET','/api/dashboard/charts?'+params)` (explicit method argument); local has already been
  refactored to the newer `api('/api/dashboard/charts?'+params)` one-argument form.

**These are not cosmetic — commits `0cc46ab` (2026-07-22T04:17:28Z) and `483161e`
(2026-07-22T05:18:12Z) both post-date the frontend's last deploy (2026-07-21T23:30:36Z) by hours**,
and current `HEAD` (`e458495`, 2026-07-23T07:59:54Z) is further ahead still. **Conclusion: the
deployed build is real, working, older code — not a wrong-source or misconfigured-build problem.**
It simply has not been redeployed since.

## 3. Proof `aafc-tms-planning-workspace-preview` is even more stale

```
curl -s https://aafc-tms-planning-workspace-preview-staging.up.railway.app/planning
```
returns HTTP 200 with asset `index-C4Pw7BDd.js`. A fresh local production build of `frontend/`
(`npm run build`) produces `index-DlB1Jy9I.js` — a different content hash, confirming the deployed
bundle is not current. Combined with the 2026-07-14 deployment timestamp (9 days stale relative to
the frontend/backend's own 2026-07-21 deploys, and 9+ days relative to current `HEAD`), this service
has not tracked any of the intervening work at all.

## 4. Why the Planning Workspace nav link specifically disappeared

This is **independent of the staleness above** — it would happen even on a freshly deployed
frontend. Traced the actual code path:

- `connected-frontend/index.html:555` — the nav link exists in the DOM unconditionally:
  `<a class="nav-item-ext" id="nav-pw-link" ... style="display:none">Planning Workspace ↗</a>`
- `connected-frontend/index.html:3033` — `S.pwUrl = (uicfg && uicfg.planning_workspace_url) || null`,
  where `uicfg` is fetched from `GET /api/health/ui-config`.
- `backend/app/routers/health.py` (`ui_config()`) returns
  `"planning_workspace_url": settings.PLANNING_WORKSPACE_URL or None`.
- `backend/app/config.py:54` — `PLANNING_WORKSPACE_URL: str = ""` (empty by default).
- `connected-frontend/index.html:3178-3182` — the link's `display` is only ever set to `flex`
  when `pwUrl` is truthy **and** scope is squadron/wing/national; otherwise it stays `none` forever.

Checked the actual staging backend's environment variables directly:

```
railway variables --service aafc-tms-backend --environment staging --kv
```

**`PLANNING_WORKSPACE_URL` is not present in the output at all.** It was never set on this service.
Railway does auto-provide `RAILWAY_SERVICE_AAFC_TMS_PLANNING_WORKSPACE_PREVIEW_URL` (an
auto-generated service-reference variable containing the bare hostname) — but nothing wires that
into the `PLANNING_WORKSPACE_URL` variable the application code actually reads. **Root cause: a
required, non-secret environment variable was never configured on this service** (most plausibly:
it was set at some point on a different service, environment, or prior incarnation of the backend
service, and never carried forward — the exact history isn't reconstructable from Railway's API, but
the present-day absence is directly confirmed).

## 5. Requested changes that are genuinely not implemented yet (not a deploy issue)

Diffed marker occurrence counts between local `connected-frontend/index.html` and the live staging
page — identical counts mean the gap exists in source itself, not in what's deployed:

| Term | Local count | Deployed count |
|---|---|---|
| Annual Program | 4 | 4 |
| Training Summary | 2 | 2 |
| Parade Night Program | 1 | 1 |
| Training Planner | 2 | 2 |
| Mission Backlog | 0 | 0 |
| Planner Help | 0 | 0 |
| Import Review | 0 | 0 |

None of these have been retired, merged, or renamed in local source. This is real outstanding
feature/cleanup work (mission brief sections 2–15, 17, 19), addressed separately below — it is not
explained by, and will not be fixed by, redeploying the current `HEAD`.

## 6. Root causes, mapped to the brief's own checklist (section 0)

- ❌ Wrong frontend directory edited — no, `connected-frontend/index.html` is the correct, actively
  edited source for the Main TMS; confirmed by matching titles/structure.
- ❌ Wrong branch deployed — not applicable; deploys are manual snapshot uploads with no branch
  concept recorded, so "wrong branch" doesn't apply the way it would to a git-connected service.
- ❌ Incorrect Railway root directory — not evidenced; Dockerfile paths and builders are consistent
  with the established per-service `--path-as-root` convention.
- ✅ **Changes were committed but never built/deployed** — confirmed for `aafc-tms-frontend` (stale
  by ~2 days / multiple feature commits) and severely for `aafc-tms-planning-workspace-preview`
  (stale by 9 days).
- ✅ **Planning Workspace environment variable was removed/never set** — confirmed:
  `PLANNING_WORKSPACE_URL` absent on the staging backend.
- ➖ Frontend/backend version incompatibility — not found; the stale frontend still talks to the
  same API shapes it always has for the endpoints it calls (the `api('GET', ...)` vs `api(...)`
  difference is a caller-side convention change, not a breaking backend change).

## Fix plan (implemented in this pass, see `docs/ui/` and commit history for detail)

1. Set `PLANNING_WORKSPACE_URL` on the staging backend to the Planning Workspace preview's `/planning`
   URL.
2. Redeploy `aafc-tms-backend`, `aafc-tms-frontend`, and `aafc-tms-planning-workspace-preview` to
   staging from current `HEAD` so the already-implemented improvements (mobile nav, build fingerprint,
   dashboard API fixes) actually reach users.
3. Implement the genuinely-missing feature/retirement work identified in §5, scoped and reported
   honestly against the brief's 30-point final response template — see the final response for exactly
   what was completed, partially completed, or deferred, with reasons.
