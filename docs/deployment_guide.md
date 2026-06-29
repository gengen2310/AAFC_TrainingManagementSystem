# AAFC TMS — Deployment Guide

## A. Local Demo Deployment

### 1. Extract package

```bash
unzip AAFC_TMS_National_Connected_Pilot_Package_vXX.zip -d aafc-tms
cd aafc-tms
```

The ZIP extracts directly into package files — there is no nested version folder.

### 2. Set up Python environment

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Start backend

```bash
# From project root:
bash RUN_TMS_BACKEND_MAC.sh

# Or manually:
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

The backend creates `backend/aafc_tms.db` and runs seed data on first start.

### 4. Start frontend

```bash
# From project root:
bash RUN_TMS_CONNECTED_FRONTEND_MAC.sh

# Or manually:
cd connected-frontend
python3 -m http.server 8080
```

### 5. Open in browser

```
http://localhost:8080
```

### 6. Smoke test

```bash
bash scripts/smoke_test_local.sh
# or
python tools/stress/smoke_test.py
```

### Reset demo database

```bash
rm -f backend/aafc_tms.db
bash RUN_TMS_BACKEND_MAC.sh
```

This destroys all data and re-seeds from scratch. Do not use on production.

### Demo access codes

See the local pilot guide (`AAFC_TMS_Pilot_Run_Guide.md`). Codes are not embedded in frontend JS.

---

## B. Staging Deployment

### Environment variables

Set the following before starting:

```bash
export ENVIRONMENT=staging
export DATABASE_URL=postgresql://user:pass@host:5432/aafc_tms
export JWT_SECRET=<random 64-char string>
export SECRET_KEY=<random 64-char string>
export COOKIE_SECURE=true
export COOKIE_SAMESITE=lax
export CORS_ALLOWED_ORIGINS=https://tms.staging.example.com
export FRONTEND_ORIGIN=https://tms.staging.example.com
```

### Database setup

```bash
cd backend
alembic upgrade head
```

If seeding is required for staging:
```bash
PYTHONPATH=. python -c "from app.seeds.seed_all import seed_all; seed_all()"
```

### Start backend

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

### Frontend hosting

Serve `connected-frontend/index.html` as a static file from your web server or CDN.

### Health check

```
GET /api/health/ready
```

Returns `{"status": "ready", "squadrons": N}` when the database is accessible.

### Rollback

1. Restore database backup from before deployment
2. `alembic downgrade -1` to revert the last migration
3. Redeploy the previous package version

---

## C. Production Architecture

The current local demo package is **not production-ready** without the changes listed here.

### Recommended stack

| Component | Recommended |
|---|---|
| Database | Managed PostgreSQL (RDS, Cloud SQL, Supabase) |
| Backend | uvicorn behind nginx or Caddy (reverse proxy) |
| Frontend | Static hosting — CDN, S3 + CloudFront, or Vercel |
| TLS | TLS 1.3 via reverse proxy |
| Secrets | Environment variables via secret manager (AWS Secrets Manager, Doppler) |
| Logs | stdout → log aggregator (CloudWatch, Loki, Datadog) |
| Backups | Managed PostgreSQL automated backups + point-in-time recovery |

### Required production settings

```bash
ENVIRONMENT=production
DATABASE_URL=postgresql://...  # NOT sqlite
JWT_SECRET=<≥64 char random>
SECRET_KEY=<≥64 char random>
COOKIE_SECURE=true
COOKIE_SAMESITE=strict
CORS_ALLOWED_ORIGINS=https://your-real-domain.com  # NOT localhost
```

The backend **refuses to start** in `ENVIRONMENT=production` with dev defaults, SQLite, or insecure CORS.

### Production pre-flight

- [ ] PostgreSQL database provisioned and accessible
- [ ] Alembic migrations run: `alembic upgrade head`
- [ ] HTTPS configured with valid TLS certificate
- [ ] CORS restricted to production frontend origin
- [ ] JWT_SECRET and SECRET_KEY are cryptographically random (≥64 chars)
- [ ] COOKIE_SECURE=true
- [ ] Backup strategy documented and tested
- [ ] Health check endpoint verified: `GET /api/health/ready`
- [ ] Smoke test completed: `python tools/stress/smoke_test.py`
- [ ] Access code reset procedure documented for users

### Production NOT supported in V17

- Arbitrary file upload for database restore via frontend
- Automated deployment via frontend package upload
- Multi-region or high-availability configuration

These require a proper DevOps pipeline and are out of scope for the local pilot package.

---

## D. Maintenance procedure

See `docs/maintenance_procedure.md`.

## E. Backup and restore

See `docs/backup_and_restore.md`.
