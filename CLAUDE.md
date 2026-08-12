# AAFC TMS — Claude Code Project Configuration

## Project overview

AAFC Training Management System (TMS) — national connected pilot, v17.1.
FastAPI backend, PostgreSQL (Supabase-hosted) in deployed environments, SQLite for local dev/tests.
Two deployed frontends, both intentionally kept separate (see Frontend below).

## Working directory

This repo is the working directory — there is no separate extracted-ZIP or versioned-folder
convention for this package. Work directly in the git checkout.

## Repository layout

- `backend/app/main.py` — app entrypoint, router registration, lifespan (prod-config fail-closed check)
- `backend/app/config.py` — Settings; `is_production` is true only when `ENVIRONMENT` is `production`/`prod`
- `backend/app/permissions.py` — RBAC Principal, require_* helpers
- `backend/app/routers/` — all API routers
- `backend/app/models/` — SQLAlchemy models
- `backend/alembic/versions/` — migrations; check `alembic heads` for the current head, don't hardcode it here
- `backend/app/seeds/seed_all.py` — full demo/synthetic dataset (16 squadrons, Wing, National, curriculum). Calls `reset_db()` (drop+recreate via SQLAlchemy metadata, bypassing Alembic) — after running it against any Alembic-managed DB, run `alembic stamp head` or the `alembic_version` table will be gone.
- `backend/app/seeds/staging_seed.py` — minimal bootstrap: creates one `system_admin` from `STAGING_BOOTSTRAP_SYSADMIN_CODE` env var, idempotent, no full org data.
- `backend/docker-entrypoint-staging.sh` — container entrypoint: runs `alembic upgrade head`, then bootstrap seed if no system_admin exists, then gunicorn.
- `connected-frontend/` — legacy single-file SPA (`index.html`, ~400KB), served by its own Dockerfile/nginx. This is the TMS root frontend — **never replace it with the React app** (see below).
- `frontend/` — React + Vite + TypeScript "Planning Workspace". Also has a `--mode single` build (`npm run build:single`) that inlines everything into one file via `vite-plugin-singlefile`, used by `make connected` to regenerate `connected-frontend/index.html` from the React source — that mode's `outDir` is `dist-single`, the default `build` script's is `dist`. Don't conflate the two when touching build config.

## Frontend architecture — do not "simplify" this into one app

Two independently deployed frontends by design:
- `aafc-tms-frontend` service → `connected-frontend/` — the existing TMS root, plain HTML/CSS/JS, `esc()`-escaped innerHTML, `S` session state from `/api/auth/me`, `nav()`/`NAV_BY_SCOPE` routing.
- `aafc-tms-planning-workspace-preview` service → `frontend/` — React/Vite Planning Workspace, mounted at `/planning`.
Both read their backend URL from a `<meta name="aafc-api-base">` tag, overwritten at container start by `docker-entrypoint.sh` from the `AAFC_API_BASE` env var (see each service's Dockerfile). Do not deploy the React app as a replacement for the root frontend, and do not merge them into a single build — see `.claude/rules/architecture.md`.

## Run commands (local dev)

```bash
# Backend (SQLite auto-created on startup)
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000

# Legacy TMS frontend (static file server)
cd connected-frontend && python3 -m http.server 8080

# Planning Workspace (Vite dev server)
cd frontend && npm run dev
```

## Test commands

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/ -q
```

Baseline as of 2026-08-12 (commit afdc263): 1553 passed, 5 skipped — re-run and record the real pass/fail/skip count rather than trusting any number written here; it goes stale fast.

## Deployment

Railway project `exemplary-emotion`. Environments: `production` (live), `staging` (created 2026-07-12 for beta-readiness testing — synthetic data only, has its own Postgres, never points at the production database). Each environment has its own `DATABASE_URL`, `JWT_SECRET`, `SECRET_KEY`, `CORS_ALLOWED_ORIGINS` — never copy a secret value between environments by hand; use `railway variable set` per-environment.

Backup/restore: `.github/workflows/backup-postgresql.yml` (daily) and `test-restore-postgresql.yml` (weekly) target `SUPABASE_DB_URL` via GPG-encrypted artifacts — see `deployment/backup-dr.md` for the full runbook and key-rotation procedure before touching those secrets.

## New migration

Check the actual current head before branching a migration:
```bash
cd backend && source .venv/bin/activate && alembic heads
```
Never hardcode a specific `down_revision` value in this file — it will go stale the moment another migration lands.

## Security invariants — never violate

- No access-code plaintext or hashes returned from any API
- No access codes, hashes, or seeded codes embedded in any frontend JS
- No operational data in localStorage
- Backend is always the source of truth for role/scope
- system_admin is the highest role — all actions must be audited
- Do not allow arbitrary SQL, shell, or file execution via frontend
- CORS origins must be locked per-environment (no `*`, no localhost in deployed environments)
- JWT_SECRET/SECRET_KEY must be ≥32 chars, unique per environment, never a dev default in production
- Do not remove existing audit logging, tenancy, or access-code controls
- `ENVIRONMENT` must accurately reflect the deployment (`production`/`staging`/`development`) — `config.py`'s `is_production` and `validate_for_production()` fail-closed checks key off this value

## Capability preservation

See `.claude/rules/capability-preservation.md` for the non-negotiable rules on
preserving existing features/routes/endpoints/roles/data during any refactor or
remediation work, the required bug-resolution protocol, the "no false closure"
discipline, and data-safety/git-safety requirements. Applies to all work on this
repository, not only the remediation program it was written for.

## Before packaging/releasing

See `.claude/skills/beta-release/SKILL.md` for the full release-gate process. In short: full backend test suite must pass, security greps (`.claude/rules/security.md`) must return 0, both frontends must be verified in-browser, migrations must be verified against a disposable DB, and `docs/beta/` release-readiness docs must be current — not just written once and forgotten.

## Flight model

"Flight" = a sub-squadron grouping used for cadet organisation within a squadron (see `Flight` model, `flight_id` on `User`/`Cadet`), not a tenancy level. Tenancy hierarchy is National → Wing → Squadron only. Do not create Flight-level tenancy/scope checks.
