# AGENTS.md — AAFC Training Management System

Automated-agent guide for the AAFC TMS repository. Complements CLAUDE.md
(the authoritative project overview) — read both before making changes.

## Environment setup

```bash
# Backend (Python 3.13, FastAPI, SQLAlchemy 2.0)
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Planning Workspace (React + Vite + TypeScript)
cd frontend
npm install
```

## Running tests

```bash
# Backend unit/integration suite — always run from backend/ with venv active
cd backend
source .venv/bin/activate
python -m pytest tests/ -q          # full suite, quiet
python -m pytest tests/ -q --tb=short   # with short tracebacks on failure
```

All tests must pass (0 failures) before committing. The session-scoped
conftest creates an in-memory SQLite DB; never mock it.

## TypeScript build

```bash
cd frontend
npm run build          # Vite production build (dist/)
npm run build:single   # Inline single-file build → dist-single/ (make connected)
```

Build must succeed with 0 errors. Chunk-size warnings are pre-existing and
not a blocking issue.

## Alembic migrations

```bash
cd backend
source .venv/bin/activate
alembic heads                    # check current head(s) before branching
alembic upgrade head             # apply all pending migrations
alembic revision --autogenerate -m "vN: description"  # generate new migration
```

Never hardcode a specific `down_revision` revision ID in this file — it
drifts. Always run `alembic heads` first and copy the output.

## Starting local servers

```bash
# Backend (port 8000)
cd backend && source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Legacy TMS frontend (port 8080)
cd connected-frontend && python3 -m http.server 8080

# Planning Workspace (Vite dev server)
cd frontend && npm run dev
```

## Security invariants — never violate

- No access-code plaintext or hashes returned from any API
- No access codes, hashes, or seeded codes embedded in any frontend JS
- No operational data in localStorage
- Backend is always the source of truth for role/scope
- system_admin is the highest role — all actions must be audited
- CORS origins must be locked per-environment (no `*`, no localhost in deployed environments)
- JWT_SECRET/SECRET_KEY must be ≥32 chars, unique per environment, never a dev default in production
- Do not remove existing audit logging, tenancy, or access-code controls
- `ENVIRONMENT` must accurately reflect the deployment

Run security greps before packaging (see `.claude/rules/security.md`):
```bash
grep -Rc -E "ADMIN703|ADMIN7WG|ADMINNATIONAL|SYSADMIN2026|plain_code|code_hash|access_code|localStorage" connected-frontend
grep -Rc -E "JWT_SECRET|SECRET_KEY|DATABASE_URL" connected-frontend
```
All must return 0 OR be confirmed as a documented false positive.

## Key architecture constraints

- Two frontends by design: `connected-frontend/` (legacy SPA) and `frontend/` (React).
  Never merge them or replace one with the other.
- Tenancy hierarchy: National → Wing → Squadron only. `Flight` is a sub-squadron
  UI grouping, not a tenancy level.
- Permission checks go through `backend/app/permissions.py` — never write ad-hoc
  role checks inline in routers.
- Use `batch_alter_table` for SQLite-compatible ALTER TABLE in Alembic migrations.
- All audit-log writes use `services.audit(db, p, ...)` — never remove them.

## Commit discipline

- Small, coherent commits per functional area.
- Each commit message identifies: functional area, behaviour changed, tests added.
- Do not combine unrelated fixes in one commit.
- Run `python -m pytest tests/ -q` and confirm 0 failures before pushing.

## Do not do

- Do not deploy production.
- Do not run seeds against the production database.
- Do not rewrite published history.
- Do not force-push to `main` or shared remote branches.
- Do not use `--no-verify` to bypass hooks.
- Do not drop or truncate any table in a deployed environment.
