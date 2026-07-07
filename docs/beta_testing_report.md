# AAFC TMS — Beta Testing Report
**Version:** v17.1  
**Testing period:** 2026-07-07  
**Fixes deployed:** 2026-07-07 (commit `cc943d3`)  
**Environment:** Local isolated SQLite instance, port 8099, 16-squadron seed (all 7WG squadrons)  
**Test types:** Behavioral tests (18 tests), load ramp 10→25→50→75→100 users, sustained 30-minute load at 100 users  
**Status:** COMPLETE — B-01, B-02, B-03 RESOLVED

---

## Executive Summary

The system handles 100 concurrent simulated users with **zero errors** and sub-25ms p99 latency over a sustained 30-minute run. Performance is not a blocker.

Three correctness findings were identified — two HIGH and one MEDIUM. All three have been fixed and verified in production (commit `cc943d3`, deployed 2026-07-07). Four design-level warnings remain open for policy decisions; none are blockers.

**Recommendation:**
- **100-user beta launch: GO** — B-01, B-02, and B-03 are resolved. Remaining pre-launch checklist items are operational (user guide, admin briefing).
- **Full national rollout: HOLD** — production DB pool sizing (B-07) must be re-evaluated before scaling beyond 7WG; Supabase Session Pooler's 15-connection hard cap is a single-region bottleneck at national scale.

---

## 1. Load Test Results

### 1.1 Ramp test (10 → 25 → 50 → 75 → 100 users)

All ramp stages: **0% error rate**.

| Users | Median (ms) | p95 (ms) | p99 (ms) | RPS |
|-------|-------------|----------|----------|-----|
| 10    | 3           | 7        | 14       | ~27 |
| 25    | 3           | 7        | 14       | ~67 |
| 50    | 3           | 8        | 17       | ~101 |
| 75    | 3           | 9        | 20       | ~103 |
| 100   | 3           | 12       | 33       | ~106 |

### 1.2 Sustained test (100 users × 30 minutes)

| Metric | Value |
|--------|-------|
| Total requests | 120,518 |
| Failures | **0** (0.00%) |
| Throughput | 109.9 req/s |
| Median response | 4 ms |
| p95 | 13 ms |
| p99 | 25 ms |
| p99.9 | 54 ms |
| Max single request | 515 ms |
| DB connection errors | 0 |

**Per-endpoint highlights (sustained):**

| Endpoint | Median | p95 | p99 | Max |
|----------|--------|-----|-----|-----|
| GET /api/auth/me | 2–3ms | 6ms | 9ms | 37ms |
| GET /api/parade-nights | 8ms | 22ms | 33ms | 181ms |
| GET /api/curriculum | 3ms | 7ms | 12ms | 208ms |
| GET /api/reports/summary | 3ms | 6ms | 9ms | 36ms |
| GET /api/reports/wing-overview | 18ms | 40ms | 70ms | 224ms |
| GET /api/reports/national-capability | 15ms | 42ms | 64ms | 169ms |
| POST /api/auth/login | 7ms | 13ms | 19ms | 515ms |
| POST /api/auth/lookup | 2ms | 6ms | 10ms | 363ms |
| POST /api/parade-nights | 5ms | 10ms | 15ms | 34ms |

**Notes on max values:**
- The 515ms login outlier and 363ms lookup outlier occurred during initial ramp-up when all users authenticate cold simultaneously. These are isolated spikes, not steady-state behaviour.
- Bcrypt verification on `POST /api/auth/login` is the CPU-bound bottleneck during burst logins. At sustained load, login p99 is 19ms.
- Wing-overview and national-capability are the heaviest read queries (~18–42ms at p95). Both are acceptable.

**Testing environment caveat:** These results were measured on a local SQLite instance. Production uses PostgreSQL on Railway via the Supabase Session Pooler. See B-07 for the connection pool risk that does not appear in local testing.

---

## 2. Behavioral Test Results

**18 tests run. 10 pass, 4 warn, 4 flag findings (2 HIGH, 1 MEDIUM, 1 HIGH).**

---

### B-01 — ~~HIGH~~ RESOLVED: Identical JWTs for concurrent sessions on the same access code

**Test:** 5 sessions logged in simultaneously using the same `sqn_admin` access code.  
**Observed:** All 5 concurrent logins returned the **same JWT** (identical token string, not just same claims).  
**Root cause:** `create_token()` in `backend/app/security.py:45` constructs `{"sub": user_id, "iat": now, "exp": ...}`. When `iat` is the same second for multiple calls, the payload is byte-for-byte identical → HMAC-SHA256 produces an identical signature → identical token.

**Fix applied (commit `cc943d3`):** Added `"jti": str(uuid.uuid4())` to the `create_token()` payload in `backend/app/security.py`. Each login now produces a cryptographically unique token regardless of concurrent timing.

```python
# security.py — fixed
payload = {"sub": sub, "iat": now, "exp": now + timedelta(minutes=ttl),
           "jti": str(uuid.uuid4()), **extra}
```

**Production smoke test (2026-07-07):** 5 concurrent tokens verified distinct — 5/5 unique `jti` values confirmed.

**Policy note:** The shared-code model means two people logging in with the same code still get the same `sub` and `role` claims. The `jti` fix makes tokens unique at the session level but does not make individuals distinguishable within a shared account. That is addressed separately under B-05.

---

### B-02 — ~~HIGH~~ RESOLVED: Duplicate parade nights from concurrent creation

**Test:** 3 concurrent `POST /api/parade-nights` requests to the same squadron on the same date.  
**Observed:** All 3 returned HTTP 200. Inspection of the database found **6 duplicate records** for the target date (the test ran twice, creating 3+3 duplicates).  
**Root cause:** `backend/app/routers/training.py:207` — the `create_parade` endpoint performed no uniqueness check before inserting. No `UNIQUE` constraint existed on `(squadron_id, date)`.

**Fix applied (commit `cc943d3`):** Two-layer fix:

Layer 1 — application check in `create_parade()` returns 409 with `{"error": "duplicate_date", "existing_id": "..."}` for the common case.

Layer 2 — Alembic migration `o0j1k2l3m4n5` (v27) added a partial unique index to the production DB:
```sql
CREATE UNIQUE INDEX uq_parade_night_sqn_date_active
ON parade_nights (squadron_id, date)
WHERE is_archived = FALSE
```
The partial index covers only active records, so archiving a parade night and replacing it on the same date is still permitted.

**Production smoke test (2026-07-07):** Index confirmed present (`pg_indexes` query). Duplicate insert attempt raised `IntegrityError` at the DB level. Second `POST` to same date returns HTTP 409.

---

### B-03 — ~~MEDIUM~~ RESOLVED: Soft-deleted parade nights returned by direct ID lookup

**Test:** Created a parade night, noted its ID, deleted it (`DELETE /api/parade-nights/{id}` → sets `is_archived = True`), then fetched `GET /api/parade-nights/{id}`.  
**Observed:** HTTP 200, full record returned including all sessions. The list endpoint (`GET /api/parade-nights`) correctly excluded archived records.

**Root cause:** `backend/app/routers/training.py:197` — `db.get(ParadeNight, pnid)` bypassed the archive filter. The scope audit revealed the same gap in 5 additional endpoints.

**Fix applied (commit `cc943d3`):** Added `or <record>.is_archived` guard to all 6 affected endpoints in `training.py`:
- `GET /api/parade-nights/{id}`
- `POST /api/sessions` (parade night lookup)
- `PUT /api/sessions/{sid}`
- `POST /api/sessions/{sid}/status`
- `POST /api/parade-nights/{id}/publish`
- `POST /api/parade-nights/{id}/close`

All now return HTTP 404 for archived records.

**Production smoke test (2026-07-07):** Archived parade night confirmed to return 404 on direct GET; error detail `not_found` verified.

---

### B-04 — WARN: Silent last-write-wins on concurrent edits

**Test:** Two sessions fetched the same parade night, then both submitted `PATCH` updates with different content.  
**Observed:** Both succeeded (HTTP 200). The second write silently overwrote the first. No conflict error, no version field, no timestamp comparison.

**Assessment:** This is a design-level gap, not a code bug. At the current scale of one sqn_admin per squadron, write collisions are rare. The risk increases if multiple staff share a single sqn_admin code and work simultaneously.

**Options** (for future consideration, not a current blocker):
1. **Optimistic locking** — add a `version` integer to mutable entities; require clients to send it back; reject updates where version has changed.
2. **Last-write-wins with timestamp** — current behaviour, but surface the last-updated timestamp in UI so users can detect stale data.
3. **Accept the current behaviour** — appropriate if single-user-per-squadron is the operational norm.

**No fix required for beta launch.** Flag as a known design decision.

---

### B-05 — WARN: Shared access codes prevent per-person audit accountability

**Test:** Audit log entries from multiple simulated users sharing the same `sqn_admin` code were compared.  
**Observed:** All entries carry the same `user_id`. There is no session identifier or device fingerprint in the audit log. It is impossible to determine which individual made a given change.

**Assessment:** This is a deliberate design trade-off of the shared-code access model. The implication for a beta launch is:
- If a data integrity issue occurs during beta, post-hoc attribution is impossible within the system.
- For DFR/chain-of-command accountability, this gap may become relevant if TMS data is ever used in formal proceedings.

**Policy decision required:** Accept the accountability gap as inherent to the shared-code model, or implement individual login identifiers (e.g. cadet/staff ID + shared code) before national rollout.

**No fix required for beta launch.** Document as a known limitation in user-facing materials.

---

### B-06 — WARN: JWT remains valid after logout

**Test:** Captured token before logout; attempted authenticated request after logout.  
**Observed:** Token still accepted (HTTP 200) after client-side logout.

**Assessment:** This is the known F-07 finding carried forward from the alpha report. There is no server-side token revocation. Logout is client-side only (token discarded from memory).

**Risk at beta scale:** If a shared device (e.g. a squadron's shared tablet) is not properly logged out, the token remains valid until its TTL expires. The TTL window determines the exposure window.

**No fix required for beta launch** (consistent with alpha decision). Ensure user training materials include explicit shared-device logout guidance.

---

### B-07 — WARN: Production DB connection pool insufficient for national scale

**Assessment:** The local test used SQLite with no connection pool constraints, which masks a real production risk.

Production configuration (`backend/app/database.py`):
- `pool_size=5, max_overflow=2` → **7 connections per worker**
- 2 gunicorn workers → **14 total connections**
- Supabase Session Pooler hard cap: **15 connections**

At 100 concurrent users (the 7WG beta target), the pool operates at 93% of the hard cap with no headroom for connection pre-ping or administrative queries. Under the burst login pattern (all users authenticate simultaneously at parade night start), requests that arrive when all 14 connections are busy will queue against `pool_timeout=30s`. If 30 seconds elapse, `QueuePool limit of size 5 overflow 2 reached, connection timed out` is raised → HTTP 500.

The sustained test ran at ~110 req/s with 100 simulated users and 0 errors on SQLite because SQLite has no external connection pool. In production, the same workload may produce intermittent 500s during login bursts.

**For 100-user beta (7WG only):** Risk is manageable because:
- Real human users have slower inter-request cadence than the simulated burst users
- Login bursts are short (2–3 minutes at parade night start)
- `pool_timeout=30s` means requests queue rather than immediately fail

**For national rollout (all 8 wings, ~800 users):** Current pool configuration is inadequate. Options:
1. Upgrade Supabase plan for higher connection cap
2. Deploy PgBouncer as a connection multiplexer in front of Supabase
3. Reduce `pool_size` to 3, `max_overflow=1` to stay well within the 15-connection cap and rely on gunicorn's request queue instead

**No code fix required for beta launch.** Must be addressed before national rollout.

---

## 3. Open Questions — Answers

The beta testing spec identified six core open questions. Answers based on test results:

**Q1: Does the shared-code JWT behaviour create unintended session coupling?**  
Yes (B-01). Concurrent logins on the same code within the same second produce identical tokens. **Resolved** — `jti` UUID claim added; 5 concurrent tokens confirmed distinct in production.

**Q2: Can concurrent write operations create duplicate or corrupted records?**  
Yes (B-02). Three concurrent parade-night creates on the same date all succeeded, creating duplicates. **Resolved** — application 409 check plus DB partial unique index deployed; `IntegrityError` confirmed in production.

**Q3: Does the soft-delete pattern work correctly across all endpoints?**  
Partially (B-03). The list endpoint filtered correctly; 6 single-record endpoints did not. **Resolved** — `is_archived` guard added to all 6 affected endpoints; 404 confirmed in production.

**Q4: Are there conflict detection mechanisms for concurrent edits?**  
No (B-04). Last-write-wins silently. Documented as a design gap; not a launch blocker at 7WG beta scale.

**Q5: What is the real-world accountability gap from shared access codes?**  
Complete — there is no per-person attribution in the audit log under the current model (B-05). Policy decision required before national rollout.

**Q6: Does performance degrade under sustained load?**  
No degradation observed. p99 is stable at 25ms throughout the 30-minute run. The one performance risk is the production DB connection pool under burst login, which does not manifest in the local test (B-07).

---

## 4. Prioritised Recommendations

### ~~Must fix before beta launch~~ Resolved

| # | Finding | Fix | Status |
|---|---------|-----|--------|
| 1 | B-01 JWT uniqueness | Add `jti = uuid4()` to `create_token()` payload | ✅ Deployed & verified 2026-07-07 |
| 2 | B-02 Duplicate parade nights | 409 application check + partial unique index on `(squadron_id, date)` | ✅ Deployed & verified 2026-07-07 |
| 3 | B-03 Archived PN accessible | `is_archived` guard on all 6 affected single-record endpoints | ✅ Deployed & verified 2026-07-07 |

### Must address before national rollout (not a beta blocker)

| # | Finding | Action |
|---|---------|--------|
| 4 | B-07 DB pool | Evaluate Supabase plan upgrade or PgBouncer; or tune pool down to 3+1 |
| 5 | B-05 Audit accountability | Policy decision: accept gap or add individual identifier field to login |

### Accept as known limitations (document, no fix required)

| # | Finding | Rationale |
|---|---------|-----------|
| 6 | B-04 Concurrent edit conflict | Rare at single-admin-per-squadron scale; can revisit post-beta |
| 7 | B-06 JWT valid after logout | Consistent with F-07 decision; mitigated by short TTL and user training |

---

## 5. Go / No-Go Decision

### 100-user beta (7WG, ~100 real users across 16 squadrons)

**GO**

All three correctness blockers are resolved and verified in production. Performance is solid. Zero error rate under sustained load. Remaining warnings are documented risks at acceptable levels for a controlled beta with squadron supervision.

Pre-launch checklist:
- [x] B-01: `jti` claim added to `create_token()` — deployed 2026-07-07
- [x] B-02: Duplicate-date 409 guard + DB partial unique index — deployed 2026-07-07
- [x] B-03: `is_archived` guard on all 6 affected single-record endpoints — deployed 2026-07-07
- [ ] Prepare beta user guide noting shared-device logout requirement (B-06)
- [ ] Notify squadron admins that post-beta audit review is at the account level, not individual level (B-05)

### Full national rollout (all 8 wings, ~800 users)

**HOLD**

In addition to the above fixes, the following must be resolved before national rollout:

- **B-07 DB pool**: The 14-connection ceiling is 93% of the Supabase hard cap. At 8× the user count, burst login events (e.g. simultaneous parade night starts across wings in the same time zone) will exhaust the pool and produce intermittent 500s. A connection multiplexer or plan upgrade is required before this scale.
- **B-05 Accountability**: For a national deployment that may touch DFR records or formal training outcomes, the accountability gap from shared codes should be addressed as a policy matter. The recommended path is to present the gap to the national office and obtain written acceptance or a requirement for individual identifiers.

---

## Appendix A — Test Environment

| Parameter | Value |
|-----------|-------|
| OS | macOS (Darwin 25.4.0) |
| Backend | FastAPI 0.110+ / Python 3.13 / SQLite (local) |
| Locust version | latest (installed in `.venv`) |
| Test host | `http://127.0.0.1:8099` |
| Seed | 16 × 7WG squadrons, all roles, ~38 accounts |
| Behavioral tests | 18 tests across 5 suites (A–E) |
| Load ramp | 10 → 25 → 50 → 75 → 100 users, 1 min each |
| Sustained test | 100 users × 30 minutes |
| Results directory | `/scratchpad/results/` (local only, not committed) |

## Appendix B — Files Referenced

| File | Relevance |
|------|-----------|
| `backend/app/security.py:45–48` | `create_token()` — B-01 JWT determinism |
| `backend/app/routers/training.py:195–204` | `GET /api/parade-nights/{id}` — B-03 archive gap |
| `backend/app/routers/training.py:207–240` | `POST /api/parade-nights` — B-02 duplicate guard |
| `backend/app/database.py` | Pool configuration — B-07 |
