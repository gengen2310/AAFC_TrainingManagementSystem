# AAFC TMS — Release Evidence Chain

Phase 3 (Operational Release Gate). Proves every link in the chain from git commit to browser.
Created: 2026-07-14.

---

## Purpose

This document provides traceability from source code to production deployment. It is the single reference that answers "what was shipped, when, and with what evidence?"

---

## Link 1 — Git Commit

| Field | Value |
|---|---|
| Branch | `release/beta-2026-07-14` |
| Release candidate commit | `d95e67d` |
| RC tag | `beta-2026-07-14-rc3` |
| Tag object | Annotated tag on `d95e67d` |
| Tag status | Pushed to origin: COMPLETE (2026-07-15) |
| Commit message | `fix: scope sqn_general out of /api/planning/years list (DEFECT-007)` |
| Prior RCs (superseded) | rc1 → `e918f3e`; rc2 → `e539d02` (useBlocker crash fix); rc3 = rc2 + DEFECT-007 |
| Cumulative changes in rc3 vs rc1 | Planning years sqn_general scope fix; useBlocker crash fix; 9 dead divs removed; nav simplified; IDOR fixes; 119 new backend tests; 35 Playwright E2E specs |
| Evidence file | `docs/beta/34_release_candidate_record.md` |

**DEFECT-001, DEFECT-003, DEFECT-005 fixes** are committed on this branch. They require a production deployment to take effect.

**DEFECT-007** (sqn_general planning years IDOR) — fixed in rc3 (`d95e67d`). Discovered 2026-07-15 during post-load integrity verification. sqn_general was able to read all squadrons' planning years; fix adds scope filter to match sqn_admin behaviour.

---

## Link 2 — Automated Tests

| Metric | Value |
|---|---|
| Test runner | pytest |
| Total tests | 543 |
| Test outcome | 543 passed, 1 skipped, 0 failures |
| Test files | `backend/tests/` — 23 test modules |
| Key regression tests | `test_lockout.py`, `test_planning_access.py`, `test_planning_idor.py` (incl. DEFECT-007), `test_audit.py`, `test_session_lifecycle.py` |
| `datetime.utcnow()` deprecations | 0 (fixed on this branch) |
| Playwright E2E | 35/35 passed (rc3, local backend) |
| Playwright staging | 3/35 pass via dev proxy — 32 blocked by intentional CORS restriction (staging backend refuses localhost origins); human browser verification required |
| Test run commit | `d95e67d` (rc3) |
| Test run timestamp | 2026-07-15 |

---

## Link 3 — Staging Deployment

| Field | Value |
|---|---|
| Staging environment ID | `77a45568` |
| Staging backend URL | `aafc-tms-backend-staging.up.railway.app` |
| Staging frontend URL | `aafc-tms-frontend-staging.up.railway.app` (connected-frontend) |
| Staging Planning Workspace | `aafc-tms-planning-workspace-preview-staging.up.railway.app` |
| Commit deployed to staging | `3cc7650` (release branch HEAD; RC code `e539d02` + docs update) |
| Staging backend deployment ID | `72b45f4b-17ab-48ba-acd1-dbfa1760b123` (current after R5 re-deploy: `ac20386b`) |
| Deployment timestamp | 2026-07-14T14:38–14:39Z (D2) |
| Deployment method | `railway deployment up ./backend --path-as-root --service aafc-tms-backend` |

Staging deployment confirmation: **COMPLETE (2026-07-14)**

---

## Link 4 — Database Migration

| Field | Value |
|---|---|
| Alembic head revision | `x9y0z1a2b3c4` (v36) |
| Migration applied in staging | CONFIRMED — deploy logs show "Migrations complete" with no errors (2026-07-14T14:39Z) |
| Migration applied in production | PENDING (requires production deployment) |
| Migration verification command | `GET /api/system/status` → `"alembic_revision": "x9y0z1a2b3c4"` |
| Staging migration status | COMPLETE (no-op at head; schema current) |
| Production migration status | PENDING |
| Evidence | Railway deploy logs D2 and R2: "Migrations complete" (D3/R4 steps) |

---

## Link 5 — Backend Health

| Field | Value |
|---|---|
| Health endpoint | `GET /api/health/ready` |
| Expected response | `{"status":"ready","squadrons":16}` |
| Staging health status | CONFIRMED — `{"status":"ready","squadrons":16}` at D1, D4, R3, R5 (2026-07-14) |
| Production health status | PENDING (after production deployment) |
| Last confirmed staging health | 2026-07-14T14:47Z (post-R5 re-deploy) |
| Verification method | `curl -s https://[env]-backend.up.railway.app/api/health/ready` |

---

## Link 6 — Frontend Health

| Interface | URL | Status |
|---|---|---|
| Connected TMS frontend (staging) | `aafc-tms-frontend-staging.up.railway.app` | CONFIRMED 200 (2026-07-14, D5) |
| Planning Workspace (staging) | `aafc-tms-planning-workspace-preview-staging.up.railway.app/planning` | CONFIRMED 200 (2026-07-14, D6) |
| Connected TMS frontend (production) | `aafc-tms-frontend-[production].up.railway.app` | PENDING browser verification |
| Planning Workspace (production) | `aafc-tms-planning-workspace-preview-[production].up.railway.app/planning` | PENDING |

Verification method: load each URL in Chrome; confirm HTML loads with status 200.

---

## Link 7 — Browser Verification

| Field | Value |
|---|---|
| Requirement | At least 2 squadron profiles verified across 2 roles in staging |
| Current status | PENDING — requires human tester with staging access |
| Full matrix | `docs/beta/26_squadron_verification_matrix.md` |
| Blocking for | Production deployment |

Minimum acceptable evidence before release:
- At least 1 sqn_admin login confirmed
- At least 1 sqn_general login confirmed
- Wing calendar visible for wing_admin
- National overview visible for national_admin

---

## Link 8 — Cross-Interface Data Verification

| Field | Value |
|---|---|
| Requirement | A training session created via connected TMS is visible in Planning Workspace, and vice versa |
| Test scope | At least 1 record round-trip per interface (UAT tasks 13–18 cover this) |
| Current status | PENDING — requires UAT |
| Evidence source | `docs/beta/38_user_acceptance_results.md` |

---

## Link 9 — Security Tests

| Test | Tool/Method | Status | Evidence |
|---|---|---|---|
| IDOR prevention (planning) | pytest `test_planning_idor.py` | ✅ COMPLETE | 543 passed at rc3 (d95e67d); TestSqnGeneralYearScope DEFECT-007 regression passes |
| IDOR prevention (parade-nights, ops) | pytest `test_planning_access.py` | ✅ COMPLETE | 543 passed at rc3 |
| Authentication lockout | pytest `test_lockout.py` | ✅ COMPLETE | 543 passed at rc3 |
| Role isolation | All role tests in 543-test suite | ✅ COMPLETE | 543 passed at rc3 |
| XSS input sanitisation | pytest (HTML encoding tests) | ✅ COMPLETE | 543 passed at rc3 |
| SQL injection | pytest (parameterised queries) | ✅ COMPLETE | No concatenated SQL; 543 passed |
| CORS origin whitelist | Code review | ✅ COMPLETE | Explicit origin list per environment; no `*`; localhost blocked in staging (confirmed by Playwright staging run) |
| Secrets scan (4 greps) | `grep -Rc` patterns from `.claude/rules/security.md` | ✅ COMPLETE | 0 matches |
| DEFECT-007 (sqn_general years IDOR) | Found 2026-07-15 in post-load staging check | ✅ FIXED in rc3 | `planning.py` list filter; 2 regression tests added |

---

## Link 10 — Performance Tests

### Load Test Run History

**Run 1 (b4343awtj, 2026-07-14) — INVALID**: Wrong endpoint paths; 60,873 of 124,003 requests
were 404 (used `/api/dashboard`, `/api/planning/sessions`, `/api/planning/annual-program`).
Discarded. Performance baseline for 3 valid endpoints (login, me, parade-nights): P95 534ms.

**Run 2 (baw9zh1fw, 2026-07-14) — PARTIAL PASS**: 100 users, 46.2 min.
- Total requests: 124,892 | Successful: 105,165 | Non-5xx failures: 19,726 | 5xx: 1
- P95 latency: 530ms (PASS ≤ 2000ms) | 5xx: FAIL (1 SSL EOF, Railway infrastructure glitch)
- 5 endpoints called; 19,724 failures from `/api/years` (wrong path — correct is `/api/planning/years`)
- Valid endpoints proven: `/api/auth/login` (n=21,380, p95=619ms), `/api/auth/me` (p95=316ms),
  `/api/reports/summary` (p95=315ms), `/api/parade-nights` (p95=319ms) — all PASS
- Script corrected to `/api/planning/years` for Run 3

**Run 3 (btitxok60, 2026-07-15) — CONDITIONAL PASS**: 100 users, 46.3 min, corrected `/api/planning/years` path.
- Duration: 2777s | Total requests: 89,026 | Successful: 79,088 | Non-5xx failures: 9,937 | 5xx: 1
- P95 latency: 548ms (PASS ≤ 2000ms) | Max: 17,381ms (slow-but-successful responses during collapse)
- Gate record (script-generated, 2026-07-15T03:04:59Z):
  ```
  Timestamp   : 2026-07-15T03:04:59.004313+00:00
  Users       : 100
  Duration    : 2777s
  Requests    : 89026
  P95 latency : 548ms
  5xx errors  : 1
  Result      : FAIL (script exit code 1)
  ```

**Per-endpoint breakdown (run 3):**

| Endpoint | n | avg | P95 |
|---|---|---|---|
| `/api/auth/login` | 23,236 | 323ms | 626ms |
| `/api/auth/me` | 13,562 | 259ms | 333ms |
| `/api/parade-nights` | 26,114 | 294ms | 359ms |
| `/api/planning/years` | 12,552 | 285ms | 352ms |
| `/api/reports/summary` | 13,562 | 272ms | 338ms |

**All 5 endpoints confirmed. `/api/planning/years` proven: n=12,552, P95=352ms.**

**Throughput collapse analysis — REVISED, see Run 4/5 finding below**: At ~1797s (30 min into a
46-min run), request rate dropped from ~40 req/s to ~2 req/s. The 9,937 non-5xx failures are `Read
timed out (read timeout=15)` errors. The commit that first documented this (`43b880c`) attributed it
to "Railway staging hitting a connection/memory resource ceiling — a sudden external infrastructure
event, not a gradual application degradation." **That commit was made after `03cc7d5` (this same
branch) had already filed DEFECT-010, flagging that a second, independent 100-user run (Run 4,
`bh2yppp8g`) was launched from this session at essentially the same time as this one (Run 3) — but
`43b880c` doesn't consider or rule out that alternative before concluding "Railway ceiling."** See
the correction directly below; a later clean run (Run 5) disproves the "inherent Railway ceiling"
reading.

**1 5xx error**: Same SSL EOF pattern as run 2 (appeared at 866s, count never incremented again).
Still plausibly a transient TLS event — not contradicted by the correction below, which concerns the
throughput-collapse interpretation specifically, not this single error.

**CORRECTION (2026-07-16, this session)** — Run 3 and Run 4 (`bh2yppp8g`, this session, launched
without knowledge Run 3 was active) ran concurrently against the same staging backend:
- Both report an **identical P95 (548ms)** and near-identical max latency (17,381ms vs. 17,562ms)
  despite fully independent virtual-user pools and traffic generators — very unlikely by chance if
  the two runs didn't share the same backend contention.
- Run 4's own log also shows a throughput slowdown in its final ~4 minutes (from ~44 req/s down to
  ~10 req/s over its last 250s) — a smaller-magnitude version of the same pattern Run 3 shows, not
  the flat, constant rate Run 4 sustains everywhere else.
- **Run 5** (`bo8g2d7kc`, 2026-07-16) — a solo run confirmed via `ps aux` to have no concurrent
  load-test process running anywhere on the machine — ran the identical workload for the identical
  duration (46.3 min, 100 users) against the identical staging backend and showed **no throughput
  collapse anywhere in its timeline and 0 real 5xx errors** (full breakdown below). If a genuine,
  load-independent Railway staging resource ceiling caused Run 3's collapse, Run 5 should have hit it
  too — it didn't. **This is strong evidence the Run 3 collapse was caused by the accidental doubling
  of concurrent load (~200 combined virtual users) during the Run 3/Run 4 overlap, not an inherent
  ~30-minute Railway staging ceiling.** Filed as DEFECT-010, resolved 2026-07-16.

**Revised classification of Run 3: CONTAMINATED — do not cite as gate evidence.** Its raw numbers are
kept above for the record, but neither its P95 nor its "CONDITIONAL PASS" classification should be
treated as this release's load-test evidence. **Run 5, below, is the authoritative result.**

**Run 5 (bo8g2d7kc, 2026-07-16) — CLEAN, PASS — this is the authoritative gate evidence**:
- Confirmed via `ps aux | grep load_test_staging` that no other load-test process was active before
  starting.
- Duration: 2778s (46.3 min) | Total requests: 106,151 | Successful: 102,155 | Non-5xx failures:
  3,996 (3.8%) | 5xx: **0**
- P95 latency: 830ms (PASS ≤ 2000ms) | Max: 17,657ms
- Gate record:
  ```
  Timestamp   : 2026-07-16T07:00:44.093467+00:00
  Users       : 100
  Duration    : 2778s
  Requests    : 106151
  P95 latency : 830ms
  5xx errors  : 0
  Result      : PASS (script exit code 0)
  ```
- Per-endpoint: `/api/auth/login` n=21,339 avg=843ms **P95=1,967ms** (close to the 2,000ms
  threshold — see note below); `/api/auth/me` n=17,486 avg=261ms P95=266ms; `/api/parade-nights`
  n=33,663 avg=280ms P95=297ms; `/api/planning/years` n=16,177 avg=267ms P95=271ms;
  `/api/reports/summary` n=17,486 avg=260ms P95=267ms.
- Post-test health check: `/api/health/ready` returned in 0.3–0.5s across 3 checks, confirming
  staging recovered to normal (non-loaded) latency.
- **Non-contaminated observation, not a gate failure**: `/api/auth/login` P95 (1,967ms) and avg
  (843ms) are far higher than every other endpoint (~260–280ms avg) and the dominant source of this
  run's failures (connect/read timeouts). Each virtual user re-authenticates every workflow loop, so
  this is sustained concurrent login load, not a one-off — plausibly the intentionally-expensive
  password hash becoming a real contention point at 100 concurrent users. Worth a post-beta look
  (hash cost tuning, connection pool sizing for the auth path) if real beta traffic clusters logins
  the way this synthetic workflow does. Recorded in `docs/beta/11_defect_register.md` DEFECT-010.

### Performance Gate Record

| Criterion | Evidence (Run 5 — clean, authoritative) | Gate |
|---|---|---|
| P95 ≤ 2000ms | 830ms (all 5 endpoints; login P95 1,967ms is the closest to threshold) | ✅ PASS |
| Zero 5xx | 0 | ✅ PASS |
| All 5 workflow endpoints covered | All 5 confirmed | ✅ PASS |
| 100 concurrent users, 45+ minutes | 46.3 min, 100 users, 106,151 requests, confirmed solo (`ps aux`) | ✅ PASS |
| 16 squadrons represented | All 16 seeded roles in pool | ✅ PASS |
| Throughput stability | No collapse anywhere in the run | ✅ PASS |

**Gate status: ✅ COMPLETE — Run 5 (`bo8g2d7kc`, 2026-07-16) is clean, solo-confirmed, and passes
every mandated criterion. Runs 1–4 are superseded and must not be cited as this gate's evidence;
Run 3 in particular should not be read as "Railway staging ceiling" — see the correction above.**

---

## Link 11 — Rollback Rehearsal

| Field | Value |
|---|---|
| Rollback plan | `docs/beta/42_release_stop_and_rollback_plan.md` |
| Staging rollback rehearsal | COMPLETE — executed 2026-07-14; all automated steps PASS |
| Rehearsal report | `docs/beta/41_deployment_rehearsal.md` |
| Rollback commands verified | COMPLETE — Railway GraphQL `deploymentRedeploy` mutation confirmed working |
| Rollback deployment ID used | `a76198bf-b70b-41da-812d-ad4ad647f484` (rollback of `2ad00fec` → SUCCESS) |
| Post-rollback health | `{"status":"ready","squadrons":16}` PASS |
| D7 browser smoke steps | PENDING human tester execution |

---

## Link 12 — Final Approval

| Field | Value |
|---|---|
| GO/NO-GO gate document | `docs/beta/13_executive_go_no_go.md` |
| Current status | NO-GO (100-user load test not done; browser verification, UAT, governance pending) |
| Remaining gates to close | 100-user load test; browser verification; UAT; data governance; key custody; smoke test; production deployment approval |
| Final approval authority | Named person — PENDING |
| Approval method | ___________________  |
| Approval date | ___________  |

---

## Evidence Chain Summary

| Link | Description | Status |
|---|---|---|
| 1 | Git commit `d95e67d` / tag `beta-2026-07-14-rc3` | ✅ COMPLETE (pushed to origin 2026-07-15) |
| 2 | Backend: 543 tests pass; Playwright E2E: 35/35 pass (rc3, local) | ✅ COMPLETE on rc3 |
| 3 | Staging deployment of rc2 code (rc3 is non-perf security fix) | ✅ COMPLETE — deployment `ac20386b` SUCCESS 2026-07-14 |
| 4 | Database migration `x9y0z1a2b3c4` applied | ✅ COMPLETE — staging confirmed 2026-07-14 |
| 5 | Backend health `squadrons:16` | ✅ COMPLETE — confirmed post-load 2026-07-15 (412ms response) |
| 6 | Frontend HTML loading (staging) | ✅ COMPLETE — connected frontend + Planning Workspace: 200 |
| 7 | Browser login verification (2 squadrons, 2 roles) | ⚠️ PENDING human tester |
| 8 | Cross-interface data consistency | ⚠️ PENDING (UAT) |
| 9 | Security tests (IDOR, auth, role isolation, DEFECT-007/009) | ✅ COMPLETE — 543 pass at rc3; DEFECT-007 and DEFECT-009 (sqn_general years IDOR) found, fixed, regression tested |
| 10 | Performance / load test | ✅ COMPLETE — Run 5 (`bo8g2d7kc`, 2026-07-16), clean solo-confirmed run: 106,151 req, 0 real 5xx, P95 830ms. Runs 1–4 superseded/contaminated (DEFECT-010) — do not cite; Run 3's "Railway ceiling" reading is corrected above |
| 11 | Rollback rehearsal in staging | ✅ COMPLETE — D1–D7/R1–R5 executed 2026-07-14; all automated steps PASS |
| 12 | Final GO/NO-GO approval | ⚠️ PENDING |

**Links 1–6, 9, 10, and 11 are complete. Links 7, 8, 12 require human action.**

This document must be fully populated before the release is approved.
