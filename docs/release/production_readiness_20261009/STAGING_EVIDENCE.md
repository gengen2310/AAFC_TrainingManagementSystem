# Staging evidence — production readiness 2026-10-09 (continued 2026-10-12)

Environment: Railway project `f5d9524f-…`, environment **staging** `77a45568-…` (production
`571a8028-…` explicitly not targeted; the deploy script verifies all IDs against an immutable
allow-list). Data is synthetic: 15 Wings (load-test codes LVW1–LVW10, ZZW1, TW1), 140 Squadrons,
1,249 users (38 active). No other session was using staging (Railway logs: only health probes
since the 2026-09-29 deploy).

## Pre-deploy state and backup

- Deployed before: `431d5f9` (2026-09-29), database at `7f61608fa538` (v69).
- `pg_dump -Fc` of the staging database before the release-candidate deploy:
  `staging-pre-rc.dump`, 8.3 MB, 77 table-data sections, sha256 `698d5549…` (kept in the
  session's job directory, mode 600; synthetic data). Used for the rollback rehearsal.

## Deploy of the release candidate

| Run | SHA | Result |
|---|---|---|
| dry run | `e2619f8` | preflight **29/29**: backend 3,350 passed / 12 skipped; single computed head; full chain 89/89 on PostgreSQL; staging login as system_admin |
| real #1 | `e2619f8` | backend deployed (`6cb4adb7`) and migrated to `63c110addb63`; **aborted** at the CRUD gate: 403 `origin_not_allowed` → **D24** (the deploy scripts' cookie calls carried no Origin) |
| real #2 | `a10632f` | **all hard gates passed**: backend `bbc4bdc5` (health, revision `63c110addb63`, session, tag create→list→archive), Main TMS `2c0e13c0` (fingerprint = `a10632f`, every `js/` module served with its sha256, Playwright Dashboard+Network and Mobile nav), Planning Workspace `45f7e04b` (fingerprint = `a10632f`, Playwright smoke); all three new deployments confirmed active |

## Rate limiting under the accurate limiter (D14) — owner decision

The full staging browser suite (`tools/playwright-staging`, 15 tests × chromium/firefox/mobile,
one worker) was refused with **429 `rate_limited`** from the first minutes. Cause: D14 made the
per-IP API limit (`API_RATE_LIMIT`, 300 requests / 60 s) count accurately; before D14 it
under-counted ~10× under concurrency, so in practice it was far looser than configured. The
bucket keys on the real client IP (staging `ip_api_requests`: `125.253.9.14` = this machine,
317 in the window), **not** on Railway's edge address, so there is no shared-bucket outage risk.

Capacity implication: national-scale pacing measured ~17.5 requests/min per active user, so
**about 17 staff sharing one public IP** (a unit's Wi-Fi) would reach the limit, and one fast
automated client reaches it alone. Choosing `API_RATE_LIMIT` (per environment) is a
security/capacity policy decision for the owner; recommended starting point: 1,200/60 s per
IP with the per-account limit unchanged. Not changed here.

The suite was therefore run per browser project with the System Admin rate-limit reset
(`POST /api/system/reset-rate-limits`, audited) between projects — results below.

## Browser E2E against live staging (beta gate 6), at `a10632f`

`tools/playwright-staging/tests/staging-verification.spec.ts` (15 tests: nav per role, Activities,
Parade Nights, PW, headings, Dashboard + CSP, Facilitators tag workflow, network hygiene),
against the live staging Main TMS and Planning Workspace.

| Run | chromium | firefox | mobile | Failures |
|---|---|---|---|---|
| per project after a rate-limit reset | 14 ✓, 4 ✗ | 14 ✓ (1 flaky), 3 ✗ | 14 ✓ (2 flaky), 3 ✗ | every failure = 429 `rate_limited` (incl. the UI's "Could not create tag: Too many requests") |
| the failing tests alone after a reset | 5/5 ✓ | 5/5 ✓ | 5/5 ✓ | none |

Every test therefore passed in every project; the only failures were the accurate per-IP limit
refusing one fast automated client (see "Rate limiting" above). **PASS** (with the capacity
decision recorded).

## Rollback rehearsal (beta gate 8), 2026-10-12 — runbook §1a option 2

| Step | Result |
|---|---|
| 1. restore pre-deploy backup with `pg_restore --clean` | **half-restored** (11 errors; `wings`/`users` not dropped; v70–v76 objects survived while `alembic_version` read v69) → **D25**, runbook corrected |
| 1'. restore into an empty schema (`DROP SCHEMA public CASCADE; CREATE SCHEMA public;` + `pg_restore`) | exit 0, 0 errors; `7f61608fa538`; 140 squadrons, 1,249 users; 0 v70–v76 objects |
| 2. `railway up` of the previous build `431d5f9` (backend, Main TMS, PW) from a clean checkout, staging IDs explicit, build commit stamped | all three serving `431d5f9` within ~1 minute of upload |
| 3. smoke against the restored database | health ready (commit `431d5f9`, 140 squadrons); `/api/system/migrations` = `7f61608fa538`; system_admin: me, accounts (40), service-desk tickets 200; sqn_admin: parade-nights, cadets, dashboard charts, planning years 200; Main TMS and PW 200 |
| 4. roll forward with `deploy-staging.sh` at `2ed9b12` | **all hard gates passed**: preflight (3,350 passed), DB re-migrated v69 → `63c110addb63`, CRUD, Main TMS + PW fingerprints = `2ed9b12`, Playwright smokes, new deployments active (backend `c1df7f25`, Main TMS `109a5233`, PW `9c9b013a`) |

## Load against staging (beta gate 7) — 15-user run (the 100-user run is below)

The gate's tool (`tools/stress/load_test_staging.py`, local-only) cycles 36 seeded accounts.
On staging only the codes of 5 accounts are known to work (system_admin, national_admin,
703 sqn_admin, 703 sqn_general, 7WG wing_admin); a sample of the others (`ADMIN723`,
`723SQN2026`, `7WG2026`) returned 401. Resetting synthetic accounts' codes would breach the
project's "do not alter credentials" rule, so a genuine 100-distinct-user run needs the
owner to supply staging load-test credentials (or authorise creating dedicated accounts).

Run instead (no configuration change), 2026-10-12, staging at `2ed9b12`: **15 users** spread
over the 5 verified accounts from one IP (inside the 300/60 s per-IP limit), realistic think
time 8–20 s, 10 minutes, Squadron/Wing/National read mix + idempotent parade-night PATCH.

| Requests | req/s | p50 | p95 | p99 | 5xx | Other |
|---|---|---|---|---|---|---|
| 670 | 1.1 | 652 ms | 1,272 ms | 1,482 ms | 0 | 2 × 409 (optimistic-version conflicts, correct) |

Per-endpoint p95 is nearly flat (`/api/auth/me` 672 ms vs National overview 805 ms, parade
nights 1,339 ms): latency is dominated by the network/TLS round trip from this client
(the driver opens a new connection per request), not by server time. Within the thresholds
(read p95 < 2 s, write p95 < 3 s, errors < 1%). Server capacity evidence remains the local
national-scale run (`docs/stabilisation/national-qualification.md`, 250 users, 0 errors).

## 100-user load on staging (beta gate 7 / B6) — PASS, 2026-10-13

- **Build:** `7d5808c`, deployed with `deploy-staging.sh`. Every gate passed: preflight suite 3,354 passed, module sha256 checks, fingerprints, Playwright gates and a new active deployment on all 3 services.
- **Configuration:** staging `API_RATE_LIMIT=1200`, matching the owner's production decision R1. The per-account limit uses the same setting.
- **Accounts (owner-authorised):** 95 dedicated accounts named "Load Test <sqn>-<nn>":
  - spread over the 15 squadrons that no automation signs in to (701, 702, 704, 705, 707–715, 721, 723); 32 are `sqn_admin`, 63 `sqn_general`;
  - each code was random and rotated through the forced first change, and held only in a local file readable by the operator alone;
  - 703, 7WG and the national roles were left alone, because lookup returns the newest account for a unit and role, which would have hijacked the deploy gates' and suites' sign-ins;
  - 3 Wing and 2 National virtual users used the real `ADMIN7WG` and `ADMINNATIONAL` accounts;
  - all 95 were archived afterwards, the code file was deleted, and the 701 lookup was confirmed to return the real "701 Admin" again.
- **Workload:** the same per-role read mix and 8–20 s think time as the 15-user run, plus an idempotent parade-night notes PATCH for Squadron Admins. Ramp-up was 60 s, followed by 15 minutes, all from one client IP.
- **Thresholds**, fixed in the execution plan before any run: error rate < 1 %, read p95 < 2 s, write p95 < 3 s.

| Users | Logins | Requests | Error rate | Read p95 | Write p95 | p50 | p99 | 429 / 5xx |
|---|---|---|---|---|---|---|---|---|
| 100 | 100/100 | 6,316 | **0.13 %** | **1.18 s** | **1.05 s** (55 writes) | 0.88 s | 2.20 s | 0 / 0 |

- **The 8 non-200 responses:**
  - 2 × 409: two load users in the same squadron saved the same parade night together, and optimistic locking correctly refused the second save;
  - 6 client-side connection failures (status 0): the client recorded no response, and the script didn't record the endpoint, so these are unexplained.
- **Slowest endpoints at p95:** `/api/accounts` 1.69 s, `/api/dashboard/charts` 1.22 s.
- **Comparison with the 15-user run:** overall p95 was 1.27 s there and 1.18 s here, so 6.7 times the users caused no visible slowdown. Most of the p50 is network round trip from the client to Railway.
- **R10 on the deployed build:** over 200 audit-summary rows, `sqn_general` saw 0 IP addresses and 0 user ids, while `sqn_admin` saw 182 and 200.
