# MJ-8: v57→v59 Migration Round-Trip Evidence

**Date:** 2026-08-29  
**Branch:** main @ e0f2644  
**Alembic range:** e2f3a4b5c6d7 → fa57bc9d0e1a (v57) → b3e9c1f7a2d4 (v58) → e3693a06b1bd (v59)

---

## Forward: PostgreSQL (staging)

Staging environment: `77a45568-5c16-46c2-9065-d5d339208b0e` / Railway project `f5d9524f-8a57-44ff-86b7-ab66aec00e73`

**Pre-conditions fixed before deploy:**
- Two squadrons (`3c6894bb-...`, `dc114bde-...`) had `>1` row with `active_status=True`.
- Archived extras via direct SQL on `active_status` column (pre-Phase-A state).
- After fix: zero squadrons with `>1` active year (verified via `SELECT ... HAVING COUNT(*) > 1`).

**Deploy result (2026-08-28, deployment `5ecbed38`):**

```
INFO Running upgrade e2f3a4b5c6d7 -> fa57bc9d0e1a, v57 — wings.timezone
INFO Running upgrade fa57bc9d0e1a -> b3e9c1f7a2d4, v58 — planning_years.status + backfill
INFO Running upgrade b3e9c1f7a2d4 -> e3693a06b1bd, v59 — per-squadron unique index
```

**Post-deploy PostgreSQL schema (via `railway connect Postgres`):**

```sql
-- version
SELECT version_num FROM alembic_version;
-- e3693a06b1bd

-- status column
SELECT column_name FROM information_schema.columns
WHERE table_name = 'planning_years' AND column_name = 'status';
-- status

-- new index
SELECT indexname, indexdef FROM pg_indexes
WHERE tablename = 'planning_years' AND indexname = 'uq_planning_years_unit_active';
-- CREATE UNIQUE INDEX uq_planning_years_unit_active ON public.planning_years
-- USING btree (unit_id) WHERE ((status)::text = 'active'::text)

-- old index gone
SELECT indexname FROM pg_indexes
WHERE tablename = 'planning_years' AND indexname = 'uq_planning_years_unit_year_active';
-- (0 rows)
```

**Backend health:** HTTP 200 `/api/health/ready` immediately after deploy.

---

## Round-trip: SQLite (dev DB)

Alembic SQLite is the dev/test environment. `batch_alter_table` handles the DDL abstraction.

### Downgrade: e3693a06b1bd → e2f3a4b5c6d7

```
Running downgrade e3693a06b1bd -> b3e9c1f7a2d4, v59
Running downgrade b3e9c1f7a2d4 -> fa57bc9d0e1a, v58
Running downgrade fa57bc9d0e1a -> e2f3a4b5c6d7, v57
```

**Schema after downgrade:**
- columns: `[..., 'active_status', ...'version', ...]` — `status` column absent ✓
- indexes: `['ix_planning_years_unit_id', 'ix_planning_years_wing_id', 'uq_planning_years_unit_year_active']` — old per-year index restored ✓
- alembic_version: `e2f3a4b5c6d7` ✓

### Upgrade: e2f3a4b5c6d7 → e3693a06b1bd

```
Running upgrade e2f3a4b5c6d7 -> fa57bc9d0e1a, v57
Running upgrade fa57bc9d0e1a -> b3e9c1f7a2d4, v58
Running upgrade b3e9c1f7a2d4 -> e3693a06b1bd, v59
```

**Schema after upgrade:**
- columns: `[..., 'active_status', ..., 'status']` — `status` column present ✓
- indexes: `['ix_planning_years_unit_id', 'ix_planning_years_wing_id', 'uq_planning_years_unit_active']` — new per-squadron index present ✓
- alembic_version: `e3693a06b1bd` ✓

---

## Pre-flight behaviour

v59's `upgrade()` pre-flight queries `status = 'active'` (only reachable after v58 backfills it).  
If any squadron holds `>1` active year, `RuntimeError` is raised and the entire migration transaction rolls back (all three migrations are wrapped in a single `begin_transaction()` in `alembic/env.py`).

This was exercised on 2026-08-28: the first deploy attempt aborted with:
```
RuntimeError: Migration v59 aborted: the following squadrons hold more than one active
planning year: ['3c6894bb-...', 'dc114bde-...']
```
Confirming the pre-flight gate works correctly. After fixing the staging data, the second deploy succeeded.

---

## Test suite

Full suite run after round-trip (SQLite, dev env):

```
2029 passed, 7 skipped, 3327 warnings in 245.18s
```

No failures.
