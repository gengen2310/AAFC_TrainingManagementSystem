# AAFC TMS — Staging Deployment Guide (V17.1)

## Architecture

| Component    | Platform              | Plan  | Cost       |
|--------------|-----------------------|-------|------------|
| Backend API  | Render Web Service    | Free  | $0/mo      |
| Frontend SPA | Render Static Site    | Free  | $0/mo      |
| PostgreSQL   | Supabase              | Free  | $0/mo      |
| **Total**    |                       |       | **$0/mo**  |

> **Free-tier note:** Render's free web service spins down after 15 minutes of inactivity.
> The first request after sleep takes ~30 seconds (cold start). This is acceptable for staging.
> Upgrade to Render Starter ($7/mo) to eliminate spin-down.

### Commit

Branch: `deployment/staging-v17.1`  
Based on: `main` @ `79526d16f4d3beb6c7a3f2077c52d7017e4ad085`

---

## Step 1 — Provision Supabase PostgreSQL

1. Go to **https://supabase.com** → Sign up (free, no credit card)
2. Create a new project. Choose a region close to your users.
3. When the project is ready: **Settings → Database → Connection string → URI**
4. Copy the connection string. It looks like:
   ```
   postgresql://postgres:[PASSWORD]@db.[REF].supabase.co:5432/postgres
   ```
5. Keep this string — you will enter it in Render in Step 3.

> Supabase free tier: 500 MB database, 2 projects, no expiry.

---

## Step 2 — Connect GitHub to Render

1. Go to **https://render.com** → Sign up (free, no credit card)
2. Dashboard → **New → Blueprint**
3. Connect your GitHub account and select the repository:
   `gengen2310/AAFC_TrainingManagementSystem`
4. Choose branch: **`deployment/staging-v17.1`**
5. Render reads `render.yaml` automatically.

---

## Step 3 — Set environment variables

Render will prompt for two `sync: false` values:

| Variable              | Value to enter                              |
|-----------------------|---------------------------------------------|
| `DATABASE_URL`        | Supabase connection string from Step 1      |
| `CORS_ALLOWED_ORIGINS`| Enter **temporarily** as `https://placeholder.onrender.com` — update in Step 5 |

`JWT_SECRET` and `SECRET_KEY` are **auto-generated** by Render (`generateValue: true`).
They are never printed, never committed, and you do not need to set them.

Click **Apply** to begin deployment.

---

## Step 4 — Retrieve staging access codes

On first startup, the backend container runs `staging_seed.py`, which:
- Creates all org structure (National HQ, 7 Wing, 16 Squadrons)
- Generates strong random access codes (format: `XXXX-XXXX-XXXX-XXXX`)
- Prints them **once** to the deployment log
- Stores only hashes — the codes cannot be retrieved again

**To retrieve them:**
1. Render Dashboard → `aafc-tms-backend-staging` → **Logs**
2. Look for the section between `=== STAGING ACCESS CODES ===`
3. Copy the codes immediately and distribute securely (do not save to email/Slack)

If the codes were missed, rotate via `rotate_access_codes.py` (see Step 8).

---

## Step 5 — Wire the frontend to the backend

1. In Render Dashboard, find the deployed backend URL, e.g.:
   `https://aafc-tms-backend-staging.onrender.com`
2. In this repository, on branch `deployment/staging-v17.1`, edit:
   `connected-frontend/index.html` line 8:
   ```html
   <meta name="aafc-api-base" content="https://aafc-tms-backend-staging.onrender.com">
   ```
3. Also update `CORS_ALLOWED_ORIGINS` in Render:
   Render Dashboard → `aafc-tms-backend-staging` → Environment →
   set `CORS_ALLOWED_ORIGINS` to the **frontend** URL, e.g.:
   `https://aafc-tms-frontend-staging.onrender.com`
4. Push the meta tag change → both services redeploy automatically.

---

## Step 6 — Verify deployment

```bash
# Health check
curl https://aafc-tms-backend-staging.onrender.com/api/health/ready

# Expected: {"status":"ready","squadrons":16}

# Version
curl https://aafc-tms-backend-staging.onrender.com/
# Expected: {"version":"17.1.0",...}
```

Then run the test suite against the live staging URLs:

```bash
BASE=https://aafc-tms-backend-staging.onrender.com \
  python tools/stress/smoke_test.py

BASE=https://aafc-tms-backend-staging.onrender.com \
  python tools/stress/security_scope_test.py
```

---

## Step 7 — Database migrations

Migrations run automatically on every container start via `docker-entrypoint-staging.sh`:

```sh
alembic upgrade head
```

Expected output in logs:
```
Running Alembic migrations...
INFO  [alembic.runtime.migration] Running upgrade  -> ..., v17 system admin
INFO  [alembic.runtime.migration] Context impl PostgreSQLImpl.
```

The migration chain for V17.1:

```
b3e9f4c2a0d1  (v6 account management)
c4d8e1f3a0b2  (v8 timing templates)
e6f8a2d4c1b3  (v9 unit type wing/sqn CRUD)
175e1c6e12f7  (v9.1 cadet program jobs)
f3a1b5c9d7e2  (v11 TRGO planning)
a2c4e6f8b1d3  (v12 integration)
d1e3f5a7c9b0  (v14 training planner)
e7a9c2f4b8d1  (v17 system admin) ← HEAD
```

All migrations tested against an empty PostgreSQL database.

---

## Step 8 — Rotate access codes

If codes were lost from the logs or need rotating:

1. Render Dashboard → `aafc-tms-backend-staging` → **Shell** (requires Starter plan)
2. Run:
   ```bash
   cd /app
   python rotate_access_codes.py --out /tmp/new_codes.csv
   cat /tmp/new_codes.csv
   rm /tmp/new_codes.csv
   ```

On the free plan (no shell): deploy a temporary one-off service or upgrade to Starter.

---

## Rollback procedure

1. **Code rollback:** Revert the deployment branch to a previous commit and push.
   Render auto-redeploys.

2. **Database rollback:**
   ```bash
   # In the Render shell or as a one-off job:
   alembic downgrade -1
   ```
   Then redeploy the previous version.

3. **Full rollback:** Restore from Supabase point-in-time backup:
   Supabase Dashboard → Database → Backups → select a restore point.

---

## Monthly cost estimate

| Service          | Plan     | Cost    |
|------------------|----------|---------|
| Render backend   | Free     | $0      |
| Render frontend  | Free     | $0      |
| Supabase DB      | Free     | $0      |
| **Total**        |          | **$0**  |

**Paid upgrades (optional):**
| Service          | Plan      | Cost   | Benefit                        |
|------------------|-----------|--------|--------------------------------|
| Render backend   | Starter   | $7/mo  | No spin-down, more RAM         |
| Render PostgreSQL| Starter   | $7/mo  | Alternative to Supabase        |

---

## Automatic deployment behaviour

When any commit is pushed to `deployment/staging-v17.1`:
- Render automatically rebuilds and redeploys both services
- Zero-downtime deploy: new container starts before old one stops
- Migrations run on new container start before traffic is accepted

---

## Known gaps (staging vs. production)

| Gap                         | Staging state            | Production requirement          |
|-----------------------------|--------------------------|----------------------------------|
| Sleep on inactivity         | Yes (free plan)          | Upgrade to Render Starter        |
| TLS                         | Render-managed (free)    | Custom domain + TLS              |
| COOKIE_SAMESITE             | `lax`                    | `strict` for production          |
| Backup automation           | Supabase daily           | Point-in-time recovery confirmed |
| Log aggregation             | Render log stream        | CloudWatch / Loki in production  |
| Multi-worker                | 2 gunicorn workers       | 4+ in production                 |
| Rate limiter persistence    | In-memory (resets on restart) | Redis in production          |
| Real user data              | None — random codes only | After formal onboarding process  |

---

## Pull request

Once staging passes all tests, open a PR from `deployment/staging-v17.1` into `main`.
The PR documents all deployment configuration decisions for review before any
production promotion.
