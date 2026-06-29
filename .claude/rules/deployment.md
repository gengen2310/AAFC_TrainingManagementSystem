# Deployment Rules — AAFC TMS

## Local demo

1. Extract ZIP to a working directory
2. `cd backend && pip install -r requirements.txt` (or activate .venv)
3. `uvicorn app.main:app --reload --port 8000` — backend starts, creates SQLite DB, runs seeds
4. `cd connected-frontend && python3 -m http.server 8080`
5. Open `http://localhost:8080`
6. Login with demo codes (see local pilot guide)

Reset demo DB: `rm -f backend/aafc_tms.db && bash RUN_TMS_BACKEND_MAC.sh`

## Pre-packaging checklist

1. `python -m pytest tests/ -q` — all tests must pass
2. Security greps (see `.claude/rules/security.md`) — all must return 0
3. Browser test at `http://localhost:8080`
4. `bash scripts/pre_alpha_check.sh`
5. Update `CHANGELOG.md`

## ZIP packaging command

```bash
cd /Users/jennydv/Desktop/AAFC_TMS_National_Connected_Pilot_Package_v10
zip -r /Users/jennydv/Desktop/AAFC_TMS_National_Connected_Pilot_Package_vXX.zip . \
  --exclude "*.pyc" --exclude "__pycache__/*" --exclude ".git/*" \
  --exclude "*.db" --exclude "*.db-shm" --exclude "*.db-wal" \
  --exclude ".DS_Store" --exclude "backend/.venv/*" --exclude "frontend/*"
```

ZIP must extract directly into package files — no nested version folder.

## Production requirements (not yet completed for this package)

- Managed PostgreSQL database (not SQLite)
- HTTPS with valid TLS certificate
- `COOKIE_SECURE=true`, `COOKIE_SAMESITE=strict`
- `CORS_ALLOWED_ORIGINS` set to the real frontend origin only (no localhost)
- `JWT_SECRET` and `SECRET_KEY` set to cryptographically random values (≥32 chars)
- `ENVIRONMENT=production`
- Reverse proxy (nginx/Caddy) in front of uvicorn
- Backend behind private network — only reverse proxy exposed publicly
- Static frontend served from CDN or object storage behind HTTPS
- Regular automated PostgreSQL backups
- Log aggregation (stdout → Loki / CloudWatch)
- Alembic migrations run before each deployment: `alembic upgrade head`
- Health check endpoint: `GET /api/health/ready`

## Do not do in production

- Do not use SQLite as the production database
- Do not run seeds against production (seeds are for demo only)
- Do not use dev-default JWT secrets
- Do not allow localhost in CORS origins
- Do not expose `/docs` (Swagger UI) publicly in production
- Do not run the backend as root
