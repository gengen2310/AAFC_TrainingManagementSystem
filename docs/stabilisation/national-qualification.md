# National-scale qualification (2026-10-04)

Tooling: `backend/scripts/qualification/` (`seed_national_dataset.py`,
`national_load.py`). Both refuse anything but a local database/server.

## Environment (read the caveats)

- **Local, not Railway.** Apple-silicon laptop; PostgreSQL 18 (local, with
  `pg_stat_statements`, slow-query log ≥ 250 ms); backend from this branch with
  **2 worker processes** and the production pool (`DB_POOL_SIZE=5`,
  `DB_POOL_MAX_OVERFLOW=2`, 30 s timeout). Absolute latencies are indicative;
  scaling shape, failure behaviour and query counts are the transferable results.
- `uvicorn --workers 2` stood in for `gunicorn -k uvicorn.workers.UvicornWorker
  -w 2` (gunicorn is not in the shared virtualenv). Both give two independent
  worker processes with separate pools.
- `ENVIRONMENT=staging` (DB-backed rate limiters, production code paths). All
  virtual users share 127.0.0.1, so the per-IP API limit was raised
  (`API_RATE_LIMIT`); real users arrive from many addresses.

## Dataset

6 Wings, 60 Squadrons, **10,200 cadets** (+ class memberships), 900
facilitators, 2,400 parade nights, **14,400 sessions**, 300 classes,
600+ Service Desk tickets, 30,000 audit rows. Seeded through the real migration
chain (`alembic upgrade head`).

## Workload

Production sign-in (lookup → login), then role mix 60% sqn_admin (dashboard
charts, years, term planner, cadets, parade nights, weekly program, planning
edit PATCH with optimistic version), 15% sqn_general, 15% wing_admin (Wing
overview / phase coverage / not-delivered), 5% national (national overview,
accounts, Service Desk list, audit, 200-row curriculum import preview), 5%
public Service Desk submitters. "Realistic" think time 8–20 s between actions;
"aggressive" 0.5–2 s. 3 minutes per stage.

## Results (final code)

| Users | Pacing | req/s | p50 | p95 | p99 | Errors | DB conns max | CPU (2 workers) |
|---|---|---|---|---|---|---|---|---|
| 50 | realistic | 14 | 18 ms | 46 ms | 71 ms | 0 | 9 | 66% |
| 100 | realistic | 30 | 18 ms | 53 ms | 85 ms | 0 | 11 | 136% |
| 250 | realistic | 73 | 30 ms | 89 ms | 145 ms | 0 | 13 | 194% |
| 250 | aggressive | 121 | 1.5 s | 1.9 s | 2.1 s | 0 | 16 | 227% |

Server log across all final runs: 0 × 500, 0 queue timeouts, 0 pool
exhaustion. The 2 × 409 are correct optimistic-version conflicts. No SQL
statement exceeded 250 ms; the database is not the bottleneck — the two worker
processes are CPU-bound at saturation (~120 req/s here).

## Defects found and fixed by this qualification

| Finding | Evidence | Fix |
|---|---|---|
| **Pool/thread deadlock** under overload: sync dependency holds a DB connection while waiting for a thread; worker stayed wedged after load stopped | 1,504 pool timeouts, 178 × 500, 7 sessions "idle in transaction"; next low-load run 56% errors | per-worker request cap (`REQUEST_CONCURRENCY`, default pool size) with async queue + 503 `server_busy` |
| Overload reported as 500 `internal_error` | as above | pool `TimeoutError` → 503 + Retry-After |
| Database outage reported as 500 | 15 s outage → 466 × 500 | `OperationalError`/`DisconnectionError` → 503 `database_unavailable` |
| N+1: accounts list | 419 queries/request | batched context → 21 |
| N+1: Wing overview | 325 queries/request | batched → 23 |
| N+1: National overview (+ loaded all 14,400 sessions) | 149 queries, 0.61 s | GROUP BY + batched coverage → 38 queries, 0.22 s |
| N+1: term planner / long-range | 5 queries per session | batched session context → constant |

Saturated throughput rose from 82 to 121 req/s after the report fixes.

## Failure drills (100 realistic users)

| Event | Result |
|---|---|
| Maintenance enabled (20 s drain) | PENDING: writes continue (3 boundary 503s); LOCKED: all 103 writes 503, reads continue; 0 × 500 |
| Maintenance disabled | 2 writes 503 for up to 10 s on the other worker (per-worker cache TTL, documented) |
| Worker SIGKILL | 0 failed requests; the supervisor respawned the worker |
| PostgreSQL stopped 15 s | every request 503 `database_unavailable` (no internals exposed); pool recovered automatically, 0 errors after |

## Sizing guidance

- With realistic staff pacing, 250 concurrent users used ~60% of two workers'
  capacity locally. Scale workers before users approach saturation, keeping
  `workers × (DB_POOL_SIZE + DB_POOL_MAX_OVERFLOW)` under PostgreSQL
  `max_connections` (production default 100).
- Consider `DB_POOL_TIMEOUT` ≈ 10 s so pathological waits fail faster; the
  request cap already prevents the deadlock class.
- Re-run this qualification on staging hardware before declaring a national
  capacity number for production.

## Not covered (stated, not assumed)

- Railway CPU/network characteristics (local only).
- Bulk cadet import (CEA) under load, and attendance-entry write bursts.
- More than 2 workers; PgBouncer in front of PostgreSQL.
