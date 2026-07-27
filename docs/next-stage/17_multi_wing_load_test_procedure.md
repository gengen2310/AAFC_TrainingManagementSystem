# Phase 17 — Multi-Wing Load Test Procedure

**Scope:** 250 concurrent virtual users across two Wings (7WG + 1WG) against the staging environment.  
**Gate:** Required before claiming National-ready status.  
**Pass criteria:** P95 ≤ 2000ms, zero 5xx errors, both Wings active in the same run.

---

## Pre-conditions

1. Staging environment is running and healthy (`GET /api/health/ready` → `{"status":"ready"}`)
2. 7WG data is seeded (16 squadrons from `seed_all.py` — already present in staging)
3. **1WG synthetic data seeded** (see Step 1 below) — this is a STAGING-ONLY action
4. 1WG access codes captured and recorded in the run log (they are printed once at seed time)
5. No other load test or stress test is running against staging concurrently

---

## Step 1 — Seed the Second Wing in Staging

Run `second_wing_seed.py` against staging. This creates 1WG with 101/102 squadrons and four role accounts.

```bash
cd backend
source .venv/bin/activate

ENVIRONMENT=staging \
DATABASE_URL=<staging-postgres-url> \
WING2_CODE=1WG \
  python -m app.seeds.second_wing_seed
```

**Capture the output.** The access codes are printed exactly once:

```
=== SECOND WING SYNTHETIC ACCESS CODES ===
  [wing_admin]   1WG Wing Admin:  <WING2_ADMIN_CODE>
  [sqn_admin]    101 SQN Admin:   <SQN101_ADMIN_CODE>
  [sqn_general]  101 SQN General: <SQN101_GENERAL_CODE>
  [sqn_admin]    102 SQN Admin:   <SQN102_ADMIN_CODE>
==========================================
```

Record these codes in the run log. They are never retrievable again.

> **Safety:** The seed script refuses to run if `ENVIRONMENT=production`. It is idempotent — running it twice skips already-created entities.

---

## Step 2 — Verify Pre-test State

```bash
# Confirm both Wings are visible
curl -s https://aafc-tms-backend-staging.up.railway.app/api/health/ready | python3 -m json.tool
# Expected: "squadrons": 18 (or more)

curl -s https://aafc-tms-backend-staging.up.railway.app/api/auth/organisations | python3 -m json.tool
# Expected: both "7WG" and "1WG" in wings list
```

---

## Step 3 — Run the Load Test

```bash
cd /path/to/repo

export WING2_ADMIN_CODE=<captured above>
export SQN101_ADMIN_CODE=<captured above>
export SQN101_GENERAL_CODE=<captured above>
export SQN102_ADMIN_CODE=<captured above>

python backend/scripts/load_test_multi_wing.py \
  --users 250 \
  --duration-minutes 30 \
  --ramp-seconds 90
```

Default target: `https://aafc-tms-backend-staging.up.railway.app`  
Override: `BASE_URL=https://... python backend/scripts/load_test_multi_wing.py`

The test runs for approximately 31.5 minutes (90s ramp + 30min sustained).

---

## Step 4 — Interpret Results

At test completion the script prints a gate record:

```
  Gate record:
    Timestamp   : 2026-07-17T14:00:00Z
    Users       : 250
    Wings tested: 2
    Duration    : 1890s
    Requests    : XXXX
    P95 latency : XXXms
    5xx errors  : 0
    Result      : PASS
```

**PASS** requires all three criteria:
- P95 ≤ 2000ms
- Zero 5xx errors
- Wings tested ≥ 2

**CONDITIONAL PASS** is acceptable if P95 is within 2500ms and there are zero 5xx errors, with a documented explanation for the deviation.

---

## Step 5 — Record Evidence

Paste the gate record into the release evidence chain document
(`docs/beta/35_release_evidence_chain.md` or the equivalent for the next release).

```markdown
### Load Test 4 — Multi-Wing (250 users, 2 Wings)
- Date: 2026-07-XX
- Operator: <name>
- Result: PASS / CONDITIONAL PASS / FAIL
- P95: XXXms  |  5xx: 0  |  Wings: 2
- Gate record: [paste full block here]
```

---

## Rollback / Cleanup

The second Wing data in staging is synthetic and can be left in place for further testing.

To remove it (if needed for a clean-slate re-seed):

```sql
-- Connect to staging DB via psql or Supabase dashboard
-- Delete in dependency order:
DELETE FROM access_codes WHERE user_id IN (SELECT id FROM users WHERE wing_id = (SELECT id FROM wings WHERE code = '1WG'));
DELETE FROM users WHERE wing_id = (SELECT id FROM wings WHERE code = '1WG');
DELETE FROM squadrons WHERE wing_id = (SELECT id FROM wings WHERE code = '1WG');
DELETE FROM wings WHERE code = '1WG';
```

> Do NOT run these DELETE statements against production.

---

## Known Limitations

- The in-memory API rate limiter (`API_RATE_LIMIT=300/60s per IP`) will not trigger under this test since load is distributed across many users and the limiter is per-IP.  If the load test host has a single egress IP, consider increasing `API_RATE_LIMIT` on staging for the duration of the test or running from multiple IPs.
- The test uses the scan-all login path (no `/lookup` pre-step). Production login is two-step; the actual login latency in production will differ slightly.
