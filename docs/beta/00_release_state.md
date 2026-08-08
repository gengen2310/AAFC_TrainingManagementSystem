# AAFC TMS — Release State Checkpoint (SUPERSEDED)

**Superseded 2026-08-09.** The current living release-state document is
`docs/release/final_release_program_2026.md` (created for the "Final Remediation, Product
Hardening and Public-Release Program") — check there first for ground truth (HEAD, migration
head, test baseline, deployment fingerprints, progress log). Per this file's own rule ("stale
entries here are worse than none"), the 2026-07-14 snapshot below is being retired rather than
left to look current: production ENVIRONMENT/COOKIE_SAMESITE was resolved, the IDOR fixes
described below have long since merged to `main` and been superseded by further security work
(see `docs/remediation/master_gap_register.csv` QUAL-/REM- entries), and the backup/restore
"outstanding" items were completed and independently re-verified (see
`docs/release/final_release_program_2026.md` §7). The historical narrative is kept below for
provenance/audit trail only — do not treat any commit SHA, test count, or "not yet done" item
below as reflecting current state.

---

Living document. Update in place rather than appending — stale entries here are worse than none.
Last updated: 2026-07-14 (session covering staging provisioning, backup/restore redesign,
reconciliation with a parallel session's work on `main`, and the production
ENVIRONMENT/COOKIE_SAMESITE investigation).

## Production ENVIRONMENT / COOKIE_SAMESITE — investigation complete

Full findings, the behaviour table, and the empirical `SameSite` test results are in
`docs/beta/11_defect_register.md` (DEFECT-003, DEFECT-004) — not duplicated here. Summary: one
concrete live risk found and code-fixed (`bootstrap-staging` not rejecting in production, commit
`f303895`); the production `ENVIRONMENT=production` variable change itself is prepared and
verified safe but **not applied — needs your approval**. `COOKIE_SAMESITE=none` is confirmed
required by the architecture, not a misconfiguration — do not change it.

## ⚠️ Two Claude Code sessions worked this release in parallel — read this first

A separate session worked the same release-readiness mandate directly against `main` while this
session worked `release/beta-2026-07-14`. `main` advanced 18 commits past the point this branch
diverged from, including its own fix for the same IDOR vulnerabilities (commits `c8b665e`,
`e19e959`), migrations v35/v36, and substantial Planning Workspace frontend work. Discovered when
the production restore-test surfaced an Alembic revision (`x9y0z1a2b3c4`) absent from this branch's
history — traced to `origin/main`, not corruption. **Reconciled**: `origin/main` merged into
`release/beta-2026-07-14` (commit `906f59f`), conflicts resolved by comparing both fixes on their
merits (see `docs/beta/11_defect_register.md` DEFECT-001 for the facilitator-leave decision, and
below for what was adopted from `main`). Full detail on the resolution and its verification is in
commit `906f59f`'s message.

**Still outstanding — a live migration revision-ID collision**: while investigating, this session
found the *other* session's local uncommitted working tree contains
`backend/alembic/versions/w8x9y0z1a2b3_v35_program_type.py` (renames `curriculum_items.core_status`
values), reusing revision id `w8x9y0z1a2b3` — which `main` already uses for a *different* migration
(`v35_planning_notices_updated_by`, now merged into this branch too). **That other session must
rename their local migration's revision id (and update its `down_revision` to `x9y0z1a2b3c4`, the
new actual head) before committing it**, or Alembic will reject it as a duplicate revision. This
session did not touch that file — it remains stashed, untouched, in that session's own working
tree/stash for them to resolve. Flagging here so it's visible before anyone hits it blind.

## 100-user concurrent load test — NOT cleanly closed: two runs collided (2026-07-15)

**Do not treat this gate as ✅ complete from either run described below.** Full detail and defect
entry: `docs/beta/11_defect_register.md` DEFECT-010. Summary:

This session fixed two real bugs in `tools/stress/load_test_staging.py` (gitignored, local-only —
never committed) before trusting it: a wrong endpoint path (`/api/years` → `/api/planning/years`,
confirmed by curl against live staging) and a `Users: 0` always-zero reporting bug (`len(set())`
instead of the real `--users` value). Validated with a 10-user/30s smoke run (PASS) before committing
to the full run.

Then launched the full 100-user/45-min run (background task `bh2yppp8g`). It completed: 115,306
requests, **0 real 5xx**, 2,567 (2.2%) client-side read-timeouts, P95 548ms, max 17,562ms — PASS per
the script's own criteria.

**But**: the concurrent session was, unbeknownst to this session at launch time, running its *own*
independent 100-user/45-min run at essentially the same time (task `btitxok60`, per its checkpoint
`docs/beta/51`, expected window ~00:44–01:30Z that day). That run completed with 89,026 requests,
**1 real 5xx**, 9,937 (11.2%) read-timeouts, P95 548ms, max 17,381ms — **FAIL** (their own script's
"zero 5xx" criterion did not pass). Discovered by reading their still-current, not-yet-superseded
checkpoint doc, then confirmed by reading their raw output file directly
(`/private/tmp/claude-501/-Users-jennydv/fa4ea2d6-cc66-4422-b865-406dd21c7fe8/tasks/btitxok60.output`
— readable from this session's filesystem since both sessions share one machine/working directory).

**Why neither run counts as clean evidence**: both runs report an *identical* P95 (548ms) and
near-identical max latency (~17.4–17.6s) despite independently-generated traffic — strong evidence
the two runs actually overlapped, meaning real combined concurrent load was up to ~200 virtual
users, not the specified 100. The one real 5xx and elevated timeout rate in the other run may be an
artifact of that doubling, or may be a genuine capacity issue — cannot be determined from these two
contaminated runs. No load test process was running on the machine when this was discovered
(confirmed via `ps aux`), so a clean solo re-run is possible now.

**Resolved 2026-07-16 — clean result obtained**: after confirming via `ps aux` that no other
load-test process was running, launched a third, solo run (background task `bo8g2d7kc`, log
`docs/beta/evidence/load_test_100user_clean_rerun_2026-07-16.log`). Result: **106,151 requests, 0
real 5xx, 3,996 (3.8%) non-5xx failures, P95 830ms, max 17,657ms — PASS** on both mandated criteria.
Post-test `/api/health/ready` checks confirmed staging recovered to normal latency (~0.3–0.5s).
**This is the authoritative 100-user load test result for the release gate** — cite this run, not
either of the two contaminated ones above.

One genuine, non-contaminated finding from this clean run: `/api/auth/login` P95 was 1,967ms
(average 843ms) — far higher than every other endpoint (~260–280ms avg) and close to the 2,000ms
threshold, and the dominant source of the run's failures (connect/read timeouts, all on the login
endpoint). Each virtual user re-authenticates every workflow loop, so this reflects sustained
concurrent login load, not a one-off. Likely cause: the intentionally-expensive password hash
becoming a real contention point at 100 concurrent users. Not a gate failure (still under 2000ms,
zero 5xx) but flagged in `docs/beta/11_defect_register.md` (DEFECT-010) for post-beta attention.

Added a "check for a running load test / read the other session's checkpoint before starting" step
to `.claude/skills/beta-release/SKILL.md` so the collision doesn't recur.

## Two "open technical tasks" from the stale checkpoint are already answered elsewhere

`docs/beta/51_current_execution_checkpoint.md` (task 11: visual consistency, task 13: doc-phase
classification) marks both "NEEDS ASSESSMENT"/"NEEDS CLASSIFICATION" — but later docs from the same
doc suite already resolve them:
- Task 11 (visual consistency / shared design tokens): `docs/beta/33_feature_freeze.md` explicitly
  lists this as Task #11, a P2 item **deferred to post-beta**, not blocking. The checkpoint's
  "needs assessment" note appears to just not cross-reference this.
- Task 13 (beta doc "phases 19–22"): there is no separate 19–22 sub-scheme. Phase 19 = 14 known
  limitations documented (`15_known_limitations.md`); Phase 20 = the final consolidation/workflow/
  stress doc trio (`30`, `31`, `32`). Docs 33–51 are a *different* numbering track ("Operational
  Release Gate" phases 1–19, per `12_full_beta_release_readiness.md`'s own heading) — not a
  continuation of the 0–20 track. No gap found; nothing further to write for this task.

Re-run backend suite at current HEAD to confirm the 541-pass claim still holds: `541 passed, 1
skipped` — matches, gate 1 (backend tests) still green.

## Repository-native release-gate scaffolding added (2026-07-15)

`CLAUDE.md` referenced two files that didn't exist yet — created both:
- `.claude/rules/architecture.md` — the two-frontend split, session/auth mechanism, tenancy vs.
  Flight, and permission-helper selection rules, pulled from findings already proven empirically
  earlier in this release program (SameSite behaviour, proxy-aware vs. simple scope checks).
- `.claude/skills/beta-release/SKILL.md` — the release-gate checklist, mapping each gate to its
  evidence doc in `docs/beta/`, plus the non-negotiable rules and the "check for a concurrent
  session before starting destructive/long-running staging work" practice this session had to learn
  the hard way.

## Repository

| Item | Value |
|---|---|
| Branch | `release/beta-2026-07-14` (created 2026-07-13 from `main` @ `96f2781`) |
| HEAD | `6db4bf8` — "docs: mark DEFECT-002 (destructive reset_db) as fixed" |
| `main` HEAD (as of merge) | `bc40777` — merged into this branch at commit `906f59f`; `main` may have advanced further since |
| Working tree | Clean except untracked `.claude/worktrees/agent-a384acc669dbfca9c/` (stale leftover from a prior agent session, not investigated further, not touched) |
| Alembic head (this branch, post-merge) | `x9y0z1a2b3c4` (v36 — matches production's actual live schema revision) |
| Key commits on release branch (not yet on `main`) | `3cfda93` (CEA/notices/facilitator-leave/planning-activities feature), `051ba4d` (IDOR fix, since reconciled with `main`'s independent fix), `27f1902`–`d22fbbd` (backup/restore redesign), `9e7a179` (reset_db safety guard), `906f59f` (merge reconciliation with `origin/main`) |

## ⚠️ Deployment provenance is untraceable

Every existing production deployment (all 3 services) was pushed via `railway up` directly from a local working tree by a prior Claude Code session (`meta.cliCaller: "claude_code"`, `meta.commitSha: null`). **There is no git commit on record for what is actually running in production.** Do not infer deployed code from `git log` or from what's merged to `main` — the two can and do diverge. This session's staging deploys are the same mechanism (path-upload via `railway up`), so record deployment IDs/timestamps here, not just commit hashes, as the source of truth for "what's running."

## Production (environment `production`, id `571a8028-3640-4542-a4ab-7a1ee6b1f693`)

| Service | Service ID | Status | Deployment ID (active) | Deployed | Notes |
|---|---|---|---|---|---|
| aafc-tms-backend | `deb53faa-ca8d-4291-aa2e-9ff3029c50f8` | SUCCESS | `20405760-03aa-44af-8ed3-d2acbe3a438f` | 2026-07-12T18:29:18Z | See finding below — appears to already include CEA/notices/facilitator-leave routes |
| aafc-tms-frontend | `2b5e6359-2523-4209-be5b-bdf7f5273ec5` | SUCCESS | `719cc4c8-e963-4b48-8f99-435c4ed87ef2` | 2026-07-11T22:56:13Z | Legacy connected-frontend, unaffected by this session's work |
| aafc-tms-planning-workspace-preview | `253cf237-1836-43bc-9ee4-0e4eefd447b4` | **serving stale build** | active=`ee95c76f-ba55-4be8-a327-eadbc8a96700`; latest attempt `83cd4182` **FAILED** 2026-07-12T17:08:51Z | — | Root cause found and fixed this session (missing Dockerfile, Railpack was copying a `dist-single` dir that only exists in the `vite --mode single` build). Fix is on the release branch (`96584e9`), verified working in staging, **not yet deployed to production** — needs explicit approval per rule 13 |

**Finding — CEA/notices/facilitator-leave routes are already live on production**, despite that code only existing as uncommitted working-tree changes until this session committed it to the release branch. Proven via non-destructive, unauthenticated route-existence probes (no data read/written):

| Probe | Result | Interpretation |
|---|---|---|
| `GET /api/planning/totally-fake-route-xyz` | 404 | Baseline: nonexistent routes return 404 |
| `GET /api/planning/years/{uuid}/cea/activities` | 401 | Route exists, requires auth — matches new router code |
| `OPTIONS /api/planning/facilitator-leave/{uuid}` | `Allow: DELETE` | Matches `@router.delete("/facilitator-leave/{leave_id}")` exactly |
| `OPTIONS /api/planning/notices/{uuid}` | `Allow: PATCH` | Matches `@router.patch("/notices/{notice_id}")` exactly |

**Implication**: this is not "code pending release" — it is live in production right now, has never been through CI, was never covered by the committed test suite until this session, and its IDOR/tenancy behavior has not been independently verified. Phase J (IDOR regression testing) targets this as first priority, against both production (read-only probes only) and staging (full read/write testing).

**Also confirmed live on production** (not yet acted on — recorded as a defect, see below):
- `ENVIRONMENT=staging` (not `production`) on the production backend service — disables `config.py`'s `is_production`-gated fail-closed startup checks.
- `COOKIE_SAMESITE=none` (project's own `.claude/rules/deployment.md` specifies `strict`). Frontend/backend are on different Railway subdomains — changing this without testing could break cross-origin cookie auth. **Not changed yet — needs its own investigation phase before any change.**
- `/docs`, `/redoc`, `/openapi.json` are hardcoded disabled at the FastAPI app level (`docs_url=None` etc. in `main.py`), independent of `ENVIRONMENT` — so the `ENVIRONMENT` misconfiguration does NOT expose Swagger docs, narrowing that particular risk.

## Staging (environment `staging`, id `77a45568-5c16-46c2-9065-d5d339208b0e`) — created this session

Duplicated from production's service configs via `railway environment new staging --duplicate production`, then every secret/URL that would have pointed at production was overridden **before** first deploy (verified before deploying — see below).

| Service | Service ID | Status | Deployment ID | Deployed via |
|---|---|---|---|---|
| aafc-tms-backend | `deb53faa-ca8d-4291-aa2e-9ff3029c50f8` (same service ID, different environment) | SUCCESS | `84ece5df-c5c1-4f6c-ba01-c3e24b88ae10` | `railway up ./backend --path-as-root` from release branch @ `96584e9` (uncommitted-at-time-of-first-deploy state — redeploy after any further commits if exactness matters) |
| aafc-tms-frontend | `2b5e6359-2523-4209-be5b-bdf7f5273ec5` | SUCCESS | `c6a3e939-d8be-45d9-b6b5-da87cb04629b` | same |
| aafc-tms-planning-workspace-preview | `253cf237-1836-43bc-9ee4-0e4eefd447b4` | SUCCESS (2nd attempt) | 1st attempt `222673be` FAILED (pre-Dockerfix); 2nd `4523c2a2-fc20-40e0-9b0e-7cdb6c76da0f` SUCCESS | `railway up ./frontend --path-as-root`, after commit `96584e9` |
| Postgres | `96f1e5b4-5bf4-4803-9481-bb812ecdc905` | Online | — | `railway add --database postgres`, fresh, synthetic data only |

**Isolation verified before first deploy** (values read via `railway variable list --json`, never printed in full — only presence/absence and non-secret fields checked):
- `DATABASE_URL` → confirmed points at the new staging Postgres's Railway-internal host (`railway.internal`), confirmed does **not** contain `supabase` (i.e., not production's DB).
- `JWT_SECRET`, `SECRET_KEY` → freshly generated (`openssl rand -base64 48` each), distinct from production's, never displayed.
- `CORS_ALLOWED_ORIGINS` → set to the two `*-staging.up.railway.app` origins only.
- `AAFC_API_BASE` (on both frontend services) → overridden from a hardcoded production URL (this was the duplicated default — would have made staging frontends call the **production** backend if left unchanged) to the staging backend URL.
- `ENVIRONMENT=staging` (accurate for this environment, per `config.py`'s `is_production` check).

**⚠️ Known exposure, low severity**: the staging Postgres's auto-generated `POSTGRES_PASSWORD` appeared once in this session's tool output (a `railway environment config --json` dump I didn't fully suppress before reading). The database contains only synthetic seed data (see below), not yet used for anything sensitive. Recommend rotating it (`railway variable set POSTGRES_PASSWORD=<new> --service Postgres --environment staging` + restart) before this environment is used for anything beyond the current test cycle — not yet done.

## Staging database content

- Alembic: `alembic_version` = `v7w8x9y0z1a2` (head), confirmed via direct read against the staging Postgres over its public proxy URL. Ran cleanly on container start via `docker-entrypoint-staging.sh` (full migration chain from `175e1c6e12f7` through `v7w8x9y0z1a2` applied with no errors).
- Synthetic seed: `backend/app/seeds/seed_all.py` run twice (see idempotency note below). Row counts after seeding: squadrons=16, wings=1, national_entities=1, users=38, curriculum_items=13, facilitators=5, training_areas=3, parade_nights=39, cadets=3, flights=2.
- **No `system_admin` account exists yet** — `STAGING_BOOTSTRAP_SYSADMIN_CODE` was never set, so `staging_seed.py`'s bootstrap skipped. Login to staging as system_admin is not yet possible; squadron-level synthetic accounts from `seed_all.py` (`sqn_admin`/`sqn_general` per squadron) do exist.

### ⚠️ `seed_all.py` is destructive, not idempotent — this is a safety finding, not just a test result

`seed_all()` unconditionally calls `reset_db()` (`Base.metadata.drop_all()` then `create_all()`) before seeding. Re-running it a second time against staging did **not** create duplicates — but only because it destroys and rebuilds the entire dataset from scratch every time, not because of any upsert/idempotency logic. Row counts were identical after the second run (16 squadrons, not 32) purely because everything was deleted first.

**This is a live foot-gun**: if this script were ever invoked against a database containing real data (including by accident — e.g. copy-pasting a "reseed staging" command against the wrong `DATABASE_URL`), it would silently delete everything with no confirmation prompt and no environment guard. Recommend: gate `reset_db()` behind an explicit check that `settings.ENVIRONMENT` is not `production`/`staging-with-real-data`, or require an explicit `--i-am-sure` / confirmation env var before `seed_all.py` can run outside of a fresh local dev DB. Logged as a defect below — not yet fixed.

## Backup / restore (GitHub Actions)

| Secret | Status |
|---|---|
| `BACKUP_GPG_PRIVATE_KEY` | Set 2026-07-12T21:25:36Z (this session) |
| `BACKUP_GPG_PASSPHRASE` | Set 2026-07-12T21:25:37Z (this session) |
| `SUPABASE_DB_URL` | Set 2026-07-13T10:34:28Z (this session) — points at the **staging** Postgres public proxy URL, matching the workflow's own "AAFC TMS Staging" label; does not touch production |

Root cause of prior failures (confirmed): the committed public key (`.github/backup-public-key.asc`) had a matching private key only in a local GPG keyring on this machine, whose passphrase was never recorded anywhere accessible (not in the repo, not in any password manager we have access to). Rather than guess at a lost passphrase, generated a fresh keypair per `deployment/backup-dr.md`'s own key-rotation procedure (commit `3e9acd6`) — nothing was ever successfully encrypted with the old key, so nothing is lost by retiring it.

**Not yet done**: manual trigger of the backup workflow to prove it now succeeds end-to-end; the restore-test workflow; private-key offline custody (Phase D — explicitly requires stopping to ask before proceeding, not yet reached).

## Alembic

- Local repo head: `v7w8x9y0z1a2` (single chain, verified no branching across all 26 migration files).
- Staging DB: confirmed at head (see above).
- Production DB: not directly queried (avoiding any direct connection to the production database this session). Given production's backend has been serving traffic successfully with `/api/health/ready` responding and the CEA/notices/facilitator-leave routes already present, production's schema is very likely at or near `v7w8x9y0z1a2` as well, but this is inferred from route behavior, not confirmed by a direct schema read. Treat as unverified until read via a safe method (e.g., a system_admin-only diagnostic endpoint, if one exists, rather than a direct DB connection).

## Backend test baseline

422 tests collected (not yet executed this session — CLAUDE.md's previously-stated "310 passed, 1 skipped" is confirmed stale and has been removed from the rewritten CLAUDE.md rather than replaced with another number that will also go stale).

## Update — IDOR fix (2026-07-13, commit `051ba4d`)

Found and fixed a real BLOCKER during Phase J: `facilitator-leave`, `notices`, and `CEA` endpoints checked only role, never object ownership (squadron/wing). Full detail in `docs/beta/11_defect_register.md` (DEFECT-001). Fixed using the codebase's own existing scope helpers, 13 regression tests added (each proven to fail pre-fix via `git stash`, pass post-fix), full suite now 434 passed/1 skipped (was 421/1, zero regressions). Redeployed to staging (`deployment 06abdadd...`, SUCCESS) and live-verified over real HTTP: cross-squadron facilitator-leave read → 403, same-squadron → 200. **Not yet deployed to production** — that code path is confirmed still live and vulnerable there (see the route-probe finding above), pending explicit approval per rule 13.

## Outstanding from this checkpoint (not yet done)

- Run the full backend test suite and record real pass/fail/skip counts + coverage.
- IDOR/tenancy regression testing for CEA/notices/facilitator-leave (Phase J) — elevated priority given the live-production finding above.
- Backup workflow manual run + restore-test into a disposable DB (Phases E/F).
- Production `ENVIRONMENT`/`COOKIE_SAMESITE` investigation (Phase G) — investigate only, do not change without further sign-off.
- GPG private-key offline custody (Phase D) — will stop and ask before deleting any temporary key material.
- Rotate the staging Postgres password (incidental exposure noted above).
- Planning Workspace Dockerfile fix independent review (Phase K) before considering a production deploy of `96584e9`.
- Deploy the Dockerfile fix to production — **not authorized yet**, pending the above and explicit approval (rule 13).
