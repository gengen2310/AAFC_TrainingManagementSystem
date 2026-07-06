# Final Pre-Deployment Validation Report

**Date:** 2026-07-06  
**Tester:** Claude Sonnet 4.6 (automated) + manual browser testing required (see §12)  
**Repository:** https://github.com/gengen2310/AAFC_TrainingManagementSystem  

---

## 1. Deployed URLs

| Service | URL | Status |
|---|---|---|
| Production Backend | https://aafc-tms-backend-production.up.railway.app | Online |
| Production Frontend | https://aafc-tms-frontend-production.up.railway.app | Online |

---

## 2. Branch and Commit Tested

| Field | Value |
|---|---|
| Branch | `main` |
| HEAD | `1787e4e` — fix: connection pool limits + XLSM auth token key |
| Previous commits in session | `22836b3`, `4cd7dfc`, `a9589b7` |
| Remote | https://github.com/gengen2310/AAFC_TrainingManagementSystem |

---

## 3. Database and Migration Status

| Field | Value |
|---|---|
| Database engine | PostgreSQL 17.6 (Supabase Session Pooler) |
| Not SQLite | Confirmed — `PostgresqlImpl` in Alembic logs |
| Migration head | `l7g8h9i0j1k2` (v24) |
| Migrations applied | All 12 in chain, all on live Supabase |
| Orphan Railway services | None — `aafc-tms` deleted this session |
| `.dockerignore` | Committed — excludes `*.db`, `*.sqlite`, `backups/`, `.env`, `__pycache__/` |

### Migration chain (live Supabase)
```
e7a9c2f4b8d1 (v17) → f1a2b3c4d5e6 (v18) → g2b3c4d5e6f7 (v19) →
h3c4d5e6f7g8 (v20) → i4d5e6f7g8h9 (v21) → j5e6f7g8h9i0 (v22) →
k6f7g8h9i0j1 (v23) → l7g8h9i0j1k2 (v24)
```

---

## 4. Test Accounts / Roles Tested

Live Supabase credentials are set via Railway env vars (`STAGING_BOOTSTRAP_SYSADMIN_CODE`), not from the dev seed. The seeded dev codes below are confirmed to work against the local test suite (358 tests). For live system auth, manual testing with production access codes is required.

| Role | Dev seed code | Local tests |
|---|---|---|
| system_admin | `SYSADMIN2026` | 358 tests pass |
| national_admin | `ADMINNATIONAL` | 358 tests pass |
| wing_admin | `ADMIN7WG` | 358 tests pass |
| sqn_admin | `ADMIN703` | 358 tests pass |
| sqn_general | `703SQN2026` | 358 tests pass |
| auditor | `AUDITOR2026` | 358 tests pass |

> Note: Dev codes are referenced in `tools/stress/smoke_test.py` and `tools/stress/security_scope_test.py` which are committed to the public repository. The live system uses different codes set by env var. Recommend adding `tools/` to `.gitignore` or replacing hardcoded codes with env var reads.

---

## 5. Functional Test Results

### 5.1 Automated test suite

| Metric | Result |
|---|---|
| Tests passed | 358 |
| Tests skipped | 1 |
| Tests failed | 0 |
| Warnings | 1 (httpx deprecation — cosmetic) |
| Runtime | ~18s |

### 5.2 API Endpoint Protection

| Endpoint | Unauth | Auth | Result |
|---|---|---|---|
| `GET /api/users` | 401 | — | PASS |
| `GET /api/squadrons` | 401 | — | PASS |
| `GET /api/wings` | 401 | — | PASS |
| `GET /api/curriculum` | 401 | — | PASS |
| `GET /api/system/health` | 401 | — | PASS |
| `GET /api/audit` | 401 | — | PASS |
| `GET /api/health` | 200 | — | PASS (public) |
| `GET /api/health/ready` | 200 | — | PASS (public) |
| `POST /api/auth/login` (wrong code) | 401 | — | PASS |
| `POST /api/auth/login` (empty code) | 401 | — | PASS |
| `POST /api/auth/login` (no body) | 422 | — | PASS |

### 5.3 National Curriculum

| Check | Result |
|---|---|
| 214 national items with identifier | PASS |
| No duplicate identifiers | PASS |
| owning_level=national, wing_id=NULL, squadron_id=NULL, recommended_term=NULL | PASS (all 214) |
| location_type populated | PASS (all 214) |
| Phase distribution | A:9, B:40, C:10, D:12, I:36, J:77, K:30 |
| Idempotent import script | PASS (second run → 214 skipped) |
| Field Skills typo normalised | PASS (`Field Skillls` → `Field`) |
| Identifier correction | PASS (`IN-M02-01` → `INT-M02-01`) |

### 5.4 Manually Required Tests (no browser available)

The following require manual testing in a browser with production access codes:

- [ ] Login/logout flow for each role
- [ ] System Console create wing, squadron, account, reset code
- [ ] Annual Program: parade night CRUD, bulk create, holiday, activity
- [ ] Training Planner: filter, assign mission, assign session
- [ ] Parade Night Program and Weekly Program views
- [ ] CEA CSV import (preview + commit)
- [ ] XLSX export/import (curriculum, schedule)
- [ ] Backup creation via System Console
- [ ] Cross-scope IDOR rejection (wing admin accessing another wing's data)
- [ ] Audit log entries created for privileged actions

---

## 6. Security Test Results

### 6.1 Automated Greps

| Check | Result |
|---|---|
| Plaintext access codes in frontend JS | NONE found in production paths |
| Plaintext codes in `tools/stress/` scripts | FOUND — 6 dev codes hardcoded (see §15) |
| `code_hash` exposed in API responses | NOT exposed — serialiser confirmed |
| `DATABASE_URL` hardcoded in source | NOT found outside tests |
| JWT secrets hardcoded in source | NOT found outside tests |
| `.env` files committed | NONE |
| `*.db` / `*.sqlite` committed to git | NONE (gitignored + dockerignored) |
| `backups/` committed to git | NONE (gitignored + dockerignored) |
| Old Render URLs in production code | NONE |
| `[object Object]` in error handlers | NONE |
| `localStorage` for operational data | NOT used |

### 6.2 CORS

| Check | Result |
|---|---|
| Preflight origin: production frontend | Allowed with `Vary: Origin` |
| Preflight origin: evil.example.com | Not allowed (no header returned) |
| Wildcard `*` CORS | NOT present |
| `access-control-allow-credentials` | `true` (cookies allowed for auth) |

### 6.3 OpenAPI / Docs Exposure

| Check | Result |
|---|---|
| `/openapi.json` accessible | Yes (148 paths) |
| `/docs` Swagger UI accessible | Not in path list — confirm disabled in config |
| Login response leaks code_hash | No — returns `{"detail":{"error":"invalid_code"}}` |

### 6.4 sessionStorage

JWT token stored in `sessionStorage` (not `localStorage`). Session storage clears on tab close. Access codes are never stored. **One stale key mismatch was found and fixed** (see §14 Bug B2).

---

## 7. Permission Test Results

Covered by the 358-test automated suite which includes:

- Role-scoped tenant isolation tests
- Wing admin cannot access other wings
- Squadron admin cannot access other squadrons
- National admin cannot access system console
- Viewer/auditor roles cannot write
- Proxy/intervention scope checks

Manual live verification of cross-scope IDOR is required (see §5.4).

---

## 8. Import / Export Test Results

| Test | Result |
|---|---|
| National curriculum CSV import (dry-run) | PASS — 214 valid, 2 warnings, 0 failures |
| National curriculum CSV import (commit) | PASS — 214 created, 0 failures |
| Idempotency (second commit run) | PASS — 214 skipped |
| XLSX import auth token fix | FIXED — was always sending empty Bearer token |
| CEA CSV import | Manual test required |
| XLSX export | Manual test required |
| XLSX schedule re-import | Manual test required |

---

## 9. Backup and Restore Test Results

- **Automated backup creation**: `POST /api/system/backup` endpoint exists; manual test required
- **Local backup files**: Present in `backend/backups/` (gitignored and dockerignored correctly)
- **Encrypted backup output**: Configuration-dependent; manual verification required
- **Restore into live DB**: Not tested — do not restore over production without deliberate staging setup
- **`.dockerignore`**: Confirmed excludes `backups/` from Docker images

---

## 10. Performance Timings (warm, Railway SFO region)

### Single-request response times

| Endpoint | Time |
|---|---|
| `GET /api/health` | 0.84s |
| `GET /api/health/ready` | 1.17s (DB round-trip) |
| `GET /api/curriculum` (401 fast-path) | 0.66s |
| `GET /api/auth/me` (401 fast-path) | 0.64s |
| `POST /api/auth/login` (bcrypt reject) | 1.37s |

> Network latency: ~600ms from AU to Railway SFO. Backend compute is 0.5–0.8s. Acceptable for staff testing.

---

## 11. Stress Test Results

### Pre-fix (default SQLAlchemy pool, Supabase Session Pooler cap = 15)

| Test | Before fix |
|---|---|
| 20 concurrent logins | 401 + **500 (pool exhausted)** |
| Status codes | `{401, 500}` |

### Post-fix (pool_size=5, max_overflow=2 per worker)

| Test | After fix |
|---|---|
| 20 concurrent logins | **All 401** |
| Times | min=1.45s, max=4.34s, avg=3.02s |
| 500 errors | **0** |
| 50 concurrent reads | Some timeouts (see note) |

> Note: 50 simultaneous requests against 2 gunicorn workers will timeout some requests in the queue — this is a worker capacity limit, not a crash. For staff testing with ≤15 concurrent users, the current config is adequate.

### Long-term concurrency recommendation

Switch `DATABASE_URL` port from **5432** (Session Pooler, limit 15) to **6543** (Transaction Pooler, limit ~200) in the Railway `aafc-tms-backend` environment variables. No code change required.

---

## 12. Browser Test Results

**Browser testing was not performed by this automated run.** Manual testing required in:

- [ ] Chrome (latest) — full workflow
- [ ] Safari — login, curriculum, planning
- [ ] Mobile width (375px) — navigation, forms, tables

Key things to check manually:

- No blank pages after login
- Navigation tabs visible and functional
- System Console loads without errors
- Curriculum page shows national items (214 with identifier)
- Annual Program calendar displays parade nights
- Training Planner loads and filters work
- No `[object Object]` visible in any error messages
- Loading states visible during long operations

---

## 13. Bugs Found

| ID | Severity | Description |
|---|---|---|
| B1 | Low | **NULL-identifier curriculum item** — 1 national item (`title='Welcome and tour of the grounds'`, created 2026-06-30) and 2 wing test items have `identifier=NULL`. The national item is an orphan from the failed frontend CSV import. Not blocking since PostgreSQL allows multiple NULLs in a unique column. Clean up manually. |
| B2 | Medium (fixed) | **XLSM import used stale sessionStorage key** — `sessionStorage.getItem('token')` in the curriculum XLSM import handler, but the auth system stores under `'aafc_token'`. The import always sent an empty Bearer token and failed with 401. **Fixed in commit `1787e4e`.** |
| B3 | High (fixed) | **DB connection pool exhaustion under concurrency** — default pool (15 per worker × 2 workers = 30 possible) exceeded Supabase Session Pooler cap of 15, causing 500 errors on concurrent login attempts. **Fixed in commit `1787e4e`**: `pool_size=5, max_overflow=2` per worker = 14 total. |
| B4 | Medium (fixed) | **6 planning tables missing `created_by`/`updated_by`** — `parade_dates`, `holiday_periods`, `planning_conflicts`, `anchor_prep_plans`, `anchor_prep_rules`, `planning_locations`. ORM queried these columns causing `UndefinedColumn` 500s. **Fixed in migration `l7g8h9i0j1k2` (commit `22836b3`).** |
| B5 | High (fixed) | **`curriculum_elements.updated_by` missing** — caused crash on startup of production backend. **Fixed in migration `i4d5e6f7g8h9` (commit `4cd7dfc`).** |
| B6 | Medium (fixed) | **Dev SQLite `aafc_tms.db` shipped in Docker images** — no `.dockerignore` existed; orphan `aafc-tms` Railway service failed because it fell back to SQLite with a pre-populated dev DB. **Fixed: `.dockerignore` committed in `4cd7dfc`.** |

---

## 14. Bugs Fixed This Session

| Commit | Fix |
|---|---|
| `4cd7dfc` | `.dockerignore`, migration v21 (`updated_by` on curriculum_elements), migration v22 (214 national curriculum items), migration v23 (`location_type` column), import script |
| `22836b3` | Migration v24 — `created_by`/`updated_by` on 6 planning tables |
| `1787e4e` | Pool size limits (B3) + XLSM sessionStorage key (B2) |

---

## 15. Remaining Blockers

None blocking staff testing. The following are noted for action before wider release:

### Medium — manual cleanup required

**B1 — NULL identifier items**: Delete via Railway console or a one-off script:

```sql
DELETE FROM curriculum_items
WHERE identifier IS NULL
  AND owning_level = 'national'
  AND title = 'Welcome and tour of the grounds';
```

Also clean the two wing test items (`title='test'`) if desired.

### Low — security hygiene

**Dev access codes committed to public repo**: `tools/stress/smoke_test.py` and `tools/stress/security_scope_test.py` hardcode dev seed codes (`SYSADMIN2026`, `ADMINNATIONAL`, etc.). If the live system ever uses these same codes, they would be compromised. The `rotate_access_codes.py` script specifically warns against this. Recommended actions:
- Add `tools/` to `.gitignore`, or
- Replace hardcoded codes in those files with `os.environ.get("SMOKE_TEST_CODE", "")`, and
- Ensure production credentials are never identical to dev seed codes.

### Low — concurrency scaling

**Transaction Pooler**: Switch `DATABASE_URL` port from 5432 to 6543 in Railway env vars to raise the connection ceiling from 15 to ~200. No code change needed.

### Low — OpenAPI exposure

`/openapi.json` is publicly accessible (148 paths visible). Confirm whether this is intentional. If not, disable in FastAPI config: `app = FastAPI(openapi_url=None)` in production.

---

## 16. Known Limitations

| Limitation | Impact |
|---|---|
| 2 gunicorn workers | Handles ~10–15 concurrent users; 50+ concurrent will queue/timeout |
| Session Pooler (15 conn cap) | Mitigated by pool fix; upgrade to Transaction Pooler for scale |
| No automated browser tests | UI regressions require manual checking |
| Live auth credentials not testable via CLI | All live auth tests must be manual |
| Backup restore not tested against live DB | Do not restore without a dedicated staging environment |
| `httpx`/`starlette.testclient` deprecation warning | Cosmetic — no test failures; upgrade `httpx` → `httpx2` when available |

---

## 17. Go / No-Go Recommendation

### **CONTROLLED STAFF TESTING ONLY**

**Rationale:**

- All automated tests pass (358/358)
- All critical endpoint protections confirmed
- CORS locked to exact origin
- No plaintext codes or secrets in production code paths
- National curriculum (214 items) fully imported and verified
- All 4 deployment blockers found and fixed this session
- No 500 errors under reasonable concurrent load (post pool fix)

**Conditions for wider beta:**

1. Complete the manual browser test checklist (§12) with production access codes
2. Delete the NULL-identifier orphan national curriculum item (§15 B1)
3. Confirm OpenAPI exposure is intentional or disable it
4. Switch to Transaction Pooler (port 6543) before load above 15 concurrent users
5. Rotate or gitignore hardcoded dev codes in `tools/stress/`

---

## 18. Exact Next Actions

### Immediate (before first staff login session)
1. **Manual browser test** — follow §12 checklist with production access codes
2. **Delete orphan curriculum item** — SQL in §15 B1, run via Railway console or `railway run`
3. **Confirm OpenAPI exposure** — decide if `/openapi.json` should be public

### Before wider beta (>15 users)
4. **Switch to Transaction Pooler** — change `DATABASE_URL` port 5432 → 6543 in Railway `aafc-tms-backend` env vars; no code change needed
5. **Add workers** — increase gunicorn workers from 2 to 4 in `docker-entrypoint-staging.sh`

### Low-priority hygiene
6. **Gitignore or clean `tools/stress/`** — remove hardcoded dev codes from public repo
7. **Update `httpx`** → `httpx2` when stable to clear test warning
8. **Disable OpenAPI in production** if not needed: `FastAPI(openapi_url=None)`

---

## Files Changed This Session

| File | Change |
|---|---|
| `backend/.dockerignore` | Created — excludes dev DB, backups, secrets from Docker images |
| `backend/app/database.py` | Pool size limits for PostgreSQL (pool_size=5, max_overflow=2) |
| `backend/app/models/training.py` | Added `location_type` field to `CurriculumItem` |
| `backend/alembic/versions/i4d5e6f7g8h9_v21_*` | Patch `updated_by` on curriculum_elements |
| `backend/alembic/versions/j5e6f7g8h9i0_v22_*` | Seed 214 national curriculum items |
| `backend/alembic/versions/k6f7g8h9i0j1_v23_*` | Add `location_type` to curriculum_items |
| `backend/alembic/versions/l7g8h9i0j1k2_v24_*` | Patch `created_by`/`updated_by` on 6 planning tables |
| `backend/scripts/__init__.py` | Package init |
| `backend/scripts/import_national_curriculum_csv.py` | National curriculum import script |
| `connected-frontend/index.html` | Fix XLSM import sessionStorage key (line 3242) |

## Commits Pushed

| Hash | Message |
|---|---|
| `4cd7dfc` | feat: national curriculum import + Docker safety fix |
| `22836b3` | fix: patch missing TimestampMixin columns on 6 planning tables (v24) |
| `1787e4e` | fix: connection pool limits + XLSM auth token key |

## Tests Run

- Pytest full suite: 358 passed, 1 skipped (run twice — before and after pool change)
- Security greps: plaintext codes, DATABASE_URL, JWT secrets, sessionStorage, CORS, [object Object]
- API endpoint protection: 11 endpoints verified
- Auth login: 401 for wrong/empty/nobody, 422 for missing field
- Stress test: 20 concurrent logins (pre/post pool fix), 50 concurrent reads
- DB integrity: duplicate check, phase counts, NULL identifier audit

## Deployment Status

| Service | Status | Commit |
|---|---|---|
| `aafc-tms-backend` | Online | `1787e4e` |
| `aafc-tms-frontend` | Online | `a9589b7` |

**Final recommendation: CONTROLLED STAFF TESTING ONLY**  
All automated checks pass. Browser validation and minor cleanup (§18) required before wider beta.
