# AAFC TMS — Claude Code Project Configuration

## Project overview

AAFC Training Management System (TMS) — national connected pilot package.
FastAPI backend, single-file SPA frontend, SQLite for local demo, PostgreSQL for production.

## Working directory

Always work in:
```
/Users/jennydv/Desktop/AAFC_TMS_National_Connected_Pilot_Package_v10/
```

ZIP output goes to Desktop with the version number. Do not work in extracted ZIP folders.

## Key files

- `backend/app/main.py` — app entrypoint, router registration
- `backend/app/permissions.py` — RBAC Principal, require_* helpers
- `backend/app/routers/` — all API routers
- `backend/app/models/` — SQLAlchemy models
- `backend/alembic/versions/` — migrations (current head: `e7a9c2f4b8d1`)
- `connected-frontend/index.html` — single-file SPA (~400KB)
- `backend/app/seeds/seed_all.py` — demo seed data

## Run commands

```bash
# Backend
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Frontend (static file server)
cd connected-frontend
python3 -m http.server 8080
```

Or use `RUN_TMS_BACKEND_MAC.sh` and `RUN_TMS_CONNECTED_FRONTEND_MAC.sh`.

## Test commands

```bash
cd backend
source .venv/bin/activate
python -m pytest tests/ -q
```

Current baseline: 310 passed, 1 skipped.

## New migration

Next migration must set:
```python
down_revision = 'e7a9c2f4b8d1'
```

## Security invariants — never violate

- No access-code plaintext or hashes returned from any API
- No access codes, hashes, or seeded codes embedded in frontend JS
- No operational data in localStorage
- Backend is always the source of truth for role/scope
- system_admin is the highest role — all actions must be audited
- Do not allow arbitrary SQL, shell, or file execution via frontend
- CORS origins must be locked in production
- JWT_SECRET must be ≥32 chars and not a dev default in production
- Do not remove existing audit logging, tenancy, or access-code controls

## Packaging rules

```bash
cd /Users/jennydv/Desktop/AAFC_TMS_National_Connected_Pilot_Package_v10
zip -r /Users/jennydv/Desktop/AAFC_TMS_National_Connected_Pilot_Package_vXX.zip . \
  --exclude "*.pyc" --exclude "__pycache__/*" --exclude ".git/*" \
  --exclude "*.db" --exclude "*.db-shm" --exclude "*.db-wal" \
  --exclude ".DS_Store" --exclude "backend/.venv/*" --exclude "frontend/*"
```

ZIP must extract directly into package files — no nested version folder.

## Before packaging

1. Run `python -m pytest tests/ -q` — all tests must pass
2. Run security greps (see `.claude/rules/security.md`)
3. Verify browser rendering at `http://localhost:8080`
4. Update CHANGELOG.md
5. Run `bash scripts/pre_alpha_check.sh`

## Connected frontend testing

The tested client is always `http://localhost:8080` served from `connected-frontend/`.
Do not test from extracted ZIP folders.
Always verify browser rendering for frontend changes before reporting complete.

## Flight model

"Flight" = Squadron-equivalent specialist unit, not a sub-squadron grouping.
Hierarchy: NAT HQ → Wing → Squadron / Specialist Unit.
Do not create Flight tenancy.
