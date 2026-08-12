# Gap 15 — Distributed Rate Limiting Assessment

**Gap:** Per-IP API rate limiting is in-memory per worker; login limiter is DB-backed.
**Level A verdict:** ADEQUATE at 7WG scale.
**Level B verdict:** ADEQUATE for ≤4 gunicorn workers; evaluate before scaling beyond that.
**Level C verdict:** Implement Redis-backed shared counter before multi-Wing rollout.

---

## 1. Current implementation

### 1.1 General API limiter (`check_api_rate`)

| Property | Value |
|---|---|
| Implementation | In-memory sliding window — `_api_hits: dict[str, list[float]]` in `security.py:101` |
| Scope | Per gunicorn worker (module-level dict, not shared across workers) |
| Limit | `API_RATE_LIMIT = 300` requests per `API_RATE_WINDOW_SEC = 60` s per IP |
| Coverage | All `POST /api/` and `GET /api/` endpoints not in `_RATE_LIMIT_EXEMPT` |
| Exempt | `/api/health/ready`, `/api/health`, `/api/system/reset-rate-limits` |
| OPTIONS exclusion | CORS preflight `OPTIONS` requests excluded (DEFECT-004 fix — `main.py:217`) |

### 1.2 Login limiter (`check_login_rate` / `check_login_rate_db`)

| Property | Value |
|---|---|
| Implementation | DB-backed (`IpLoginAttempt` table) — **shared across all workers** |
| Limit | `LOGIN_ATTEMPTS = 5` per `LOGIN_WINDOW_SEC = 300` s per IP |
| Coverage | `POST /api/auth/lookup` and `POST /api/auth/login` only |
| Lockout | Hard lockout after threshold; `reset_lockout` endpoint for system_admin |

---

## 2. Multi-worker / multi-replica analysis

### 2.1 Effective limit vs. worker count

Because `_api_hits` is module-level, each gunicorn worker holds its own counter.
Railway load-balances requests across workers round-robin (or least-connections),
so a single client's requests are distributed roughly evenly.

| Workers (`GUNICORN_WORKERS`) | Effective per-IP limit (req/60s) | Enforcement accuracy |
|---|---|---|
| 1 | 300 | Exact |
| 2 (current default) | ~600 | ±50% — each worker sees ~half the traffic |
| 4 | ~1 200 | ±75% — 4× the intended limit |
| 8 | ~2 400 | Limit effectively meaningless |

**Conclusion:** at `GUNICORN_WORKERS=2` (the Railway staging default), the general API
limiter is weakened by ~2×. A determined client can make ~600 API calls in 60 s
before any single worker trips the limit. This is still adequate at 7WG scale
(beta load test: 100 concurrent users, peak P95 = 548 ms) because:
- The 300 req/60 s budget per worker exceeds any single legitimate user's workload
- Real users browsing the app generate ~30–60 API calls per session, not 300+
- The login limiter (the higher-value target for automated attacks) IS shared

At 2 workers, the general API limiter provides protection against naive enumeration
bots but not against a client that distributes requests intentionally to saturate
multiple workers simultaneously.

### 2.2 Railway replica scaling

Railway does NOT currently auto-scale the backend replica count for this project
(confirmed: single instance per environment). If Railway were configured for
horizontal scaling (multiple replicas, each running 2 workers), the effective
limit degrades further: a 2-replica × 2-worker deployment gives 4× degradation
(effective limit: 1 200 req/60 s per IP).

### 2.3 Login limiter isolation

The DB-backed `IpLoginAttempt` limiter is **not affected** by worker count.
All workers and all replicas share the same Postgres table, so the 5-attempt
lockout is enforced exactly as configured regardless of deployment topology.
This is correct by design — login brute-force protection is the higher-priority
target and is already multi-worker safe.

---

## 3. Risk assessment

### 3.1 Threat model at 7WG (Level A)

| Threat | Impact | Exploitability | Verdict |
|---|---|---|---|
| Credential brute-force | High | Low — DB-backed login limiter enforces globally | MITIGATED |
| Automated data enumeration (all reports) | Medium | Medium — 600 req/60 s is still a practical throttle at 2 workers | ACCEPTABLE |
| Scraping cadet/session data via API | Medium | Medium | ACCEPTABLE |
| DoS via API flood | Low — Railway has network-level protections | Low | ACCEPTABLE |

**Overall at Level A:** Current implementation provides adequate protection.
The in-memory limiter prevents naive automated enumeration; the DB-backed
login limiter prevents brute-force. No change required before Level A go-live.

### 3.2 Threat model at Level B (multi-Wing)

With more Wings, more users, and potentially higher `GUNICORN_WORKERS`:

- If `GUNICORN_WORKERS` is increased to 4+ for throughput, the general API
  limiter degrades to 1 200+ req/60 s effective — insufficient to stop
  cross-Wing data enumeration by a compromised account.
- The IDOR and tenancy checks (server-side) remain the primary defence against
  cross-Wing access; rate limiting is a defence-in-depth layer, not the primary
  control.
- Recommendation: before increasing `GUNICORN_WORKERS` beyond 2, move
  `_api_hits` to a DB-backed implementation (same pattern as `IpLoginAttempt`)
  or provision Redis and switch to `Redis.INCR` / sliding window.

### 3.3 Per-account limiting (not implemented)

Current limiting is per-IP only. A single IP can be shared by many users
(NAT, VPN, school network). At 7WG scale this is acceptable — a school network
may have 30 cadets behind one IP, but 30 × 30 req/session = 900 req in a
60-minute session = 15 req/60 s, well within 600.

At National scale (140 squadrons, up to 1 000+ users behind shared IPs):
per-account limiting should be added. Implementation: a separate `_account_hits`
dict keyed by `user_id` (available from the JWT after `get_principal` in the
request dependency chain), or a `UserApiUsage` DB table.

---

## 4. Fix options

### Option A — DB-backed general rate limiter (recommended for Level B)

Extend the `check_login_rate_db` pattern to create a `IpApiRequest` table:

```python
class IpApiRequest(Base):
    __tablename__ = "ip_api_requests"
    ip = Column(String, primary_key=True)
    request_count = Column(Integer, default=0)
    window_start = Column(DateTime)
```

`check_api_rate` performs a single `SELECT + UPDATE` per request (same as
`check_login_rate_db`). At 300 req/60 s × 2 workers = 600 DB reads per IP
per minute; negligible compared to the existing DB load. Alembic migration
required; estimated effort: 1–2 hours.

**Trade-off:** adds one DB round-trip to every non-exempt API call. At 7WG
scale (P95 = 548 ms, majority not rate-limited) this adds ~1–2 ms per call.

### Option B — Redis-backed counter

Use `Redis.INCR` with `EXPIRE` for a true distributed atomic counter. Requires
Redis provisioned on Railway (additional Railway service, ~$5–10/month).
Implementation: replace `_api_hits` with `redis.incr(f"rl:{ip}", amount=1)` +
`redis.expire(f"rl:{ip}", API_RATE_WINDOW_SEC)`. Celery (already stubbed in
`dispatcher.py`) uses Redis for its broker — provisioning Redis would unblock
both rate limiting and the Celery background job queue (Gap 16).

**Trade-off:** external service dependency; network latency per request (~0.5 ms
on Railway internal network); monthly cost.

### Option C — Accept at Level B, implement at Level C (deferred)

Keep in-memory limiter with `GUNICORN_WORKERS ≤ 2`. Document the 2× degradation
as an accepted risk at Level B. Implement Option A or B before Level C
(National rollout) when worker count is expected to grow.

**Trade-off:** slightly weaker API enumeration throttle; fully acceptable risk
given server-side tenancy checks are the primary IDOR defence.

---

## 5. Recommendation

**Level A:** No change. Current implementation is adequate.

**Level B:** Cap `GUNICORN_WORKERS ≤ 2` in the Railway staging and production
environment variables until Option A (DB-backed) or B (Redis) is implemented.
Document this cap in the deployment runbook. **Before raising `GUNICORN_WORKERS`
beyond 2 in production, implement Option A.**

**Level C:** Implement Option A (DB-backed) as a prerequisite for National
rollout. Evaluate Option B if Celery/Redis is being provisioned for Gap 16
(background jobs) — the Redis provisioning cost is amortized across both gaps.

---

## 6. Current cap — operational instruction

Until Option A or B is implemented, `GUNICORN_WORKERS` must not exceed 2 in
production. The Railway environment variable `GUNICORN_WORKERS` is currently
unset (defaults to 2 in `docker-entrypoint-staging.sh:37`). **Do not set it
to a higher value without first implementing a shared rate limiter.**

This constraint should be added to the `docs/next-stage/25_support_runbook.md`
operator checklist under the scaling section.

---

## 7. Document history

| Date | Author | Change |
|---|---|---|
| 2026-08-12 | Claude Code (session fa4ea2d6) | Initial assessment |
