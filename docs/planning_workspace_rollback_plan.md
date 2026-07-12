# Planning Workspace — Rollback Plan (RC1)

## Frontend Preview Rollback

The Planning Workspace frontend runs as a **separate Railway service** (`aafc-tms-planning-workspace-preview`), completely independent of the old TMS frontend.

To roll back the Planning Workspace frontend:

1. Go to Railway dashboard → `exemplary-emotion` project → `aafc-tms-planning-workspace-preview` service.
2. Click **Deployments**.
3. Find the last known-good deployment (prior to the RC).
4. Click **Rollback** on that deployment.

Railway will redeploy the old frontend build within ~2 minutes.

Alternatively, use the CLI:
```sh
# List deployments (requires Railway dashboard for deployment IDs)
railway status
# Then redeploy a specific deployment via the dashboard
```

**Impact:** Only the Planning Workspace preview is affected. The old TMS remains fully operational.

---

## Backend Rollback Constraints

The backend (`aafc-tms-backend`) is **shared** between the old TMS and the Planning Workspace.

Rolling back the backend carries risk:

- Rolling back to a version before the current migration head will leave the database schema ahead of the code.
- SQLAlchemy model mismatches can cause 500 errors on any endpoint that reads the affected tables.
- **Never roll back past a migration without also running `alembic downgrade` to the matching revision.**

To roll back the backend:

1. Identify the deployment ID of the target version (from Railway dashboard).
2. Note which alembic revision that code expects as head.
3. Before rolling back the Railway deployment:
   - Connect to the production database.
   - Run `alembic downgrade <target_revision>` from the matching code version.
4. Then roll back the Railway deployment via the dashboard.

**Safe rollback target for RC1:** Any deployment that runs with migration head `w8x9y0z1a2b3` (v35) or earlier is safe to roll back to, provided you downgrade the DB to match.

**Current migration head (RC1 code):** `x9y0z1a2b3c4` (v36)

Migration `x9y0z1a2b3c4` adds nullable columns to `cea_import_batches` — this is fully reversible:
```sql
-- Manual downgrade if needed
ALTER TABLE cea_import_batches DROP COLUMN IF EXISTS created_by;
ALTER TABLE cea_import_batches DROP COLUMN IF EXISTS updated_by;
```

---

## Database Migration Considerations

All RC1 migrations are **additive and nullable** — no existing data is destroyed or altered.

| Migration | Change | Reversible? |
|-----------|--------|-------------|
| v34 | Creates `cea_import_batches`, `cea_activities`, `activity_local_hides` | Yes — drop tables |
| v35 | Adds `updated_by` to `planning_notices` | Yes — drop column |
| v36 | Adds `created_by`, `updated_by` to `cea_import_batches` | Yes — drop columns |

To fully remove CEA/activity data if rolling back before v34:
```sql
DROP TABLE IF EXISTS activity_local_hides;
DROP TABLE IF EXISTS cea_activities;
DROP TABLE IF EXISTS cea_import_batches;
```

**Warning:** Dropping these tables deletes all imported CEA activity data, classification decisions, and local hides. Export data first if needed.

---

## How to Disable the Old TMS Nav Link

The Planning Workspace link in the old TMS navigation is in:

`connected-frontend/` — the navigation or menu component

To hide the link:
1. Find the "Planning Workspace" navigation entry in `connected-frontend/`.
2. Comment out or remove the link.
3. Deploy `connected-frontend/` to `aafc-tms-frontend`.

This removes the entry point without affecting the Planning Workspace service itself.

Alternatively, if Railway environment variables control feature flags, set `PLANNING_WORKSPACE_ENABLED=false` (if such a flag exists).

---

## How to Preserve User Data

Before any rollback affecting the backend or database:

1. **Export CEA activities:**
   ```
   GET /api/planning/years/{year_id}/cea/activities
   ```
   Save the response JSON.

2. **Export planning sessions:**
   ```
   GET /api/planning/years/{year_id}/annual-program
   ```

3. **Export anchor events:**
   ```
   GET /api/planning/years/{year_id}/anchors
   ```

4. **Export holidays:**
   ```
   GET /api/planning/years/{year_id}/holidays
   ```

5. Take a database snapshot via the Railway database service (if using Railway Postgres) before any destructive operation.

---

## Rollback Decision Matrix

| Scenario | Action |
|----------|--------|
| Frontend visual regression only | Roll back `aafc-tms-planning-workspace-preview` only |
| Backend 500 errors on PW endpoints | Roll back backend, downgrade DB if needed |
| Backend 500 errors on old TMS endpoints | Roll back backend immediately |
| Data corruption suspected | Halt all writes, snapshot DB, investigate before rollback |
| CEA import data corrupted | Drop and re-import from source CSV |
| Cross-squadron data leakage | Halt, audit, do not roll back until scope is known |

---

*RC1 — Keep this document updated as the RC progresses.*
