# AAFC Training Management System (TMS)

Training planning and records for the AAFC, from a single Squadron up through
its Wing to National.

| Part | Folder | What it is |
|---|---|---|
| **Backend** | `backend/` | FastAPI + SQLAlchemy 2 + Alembic. It is the **security authority**: every permission is decided here. PostgreSQL in production; SQLite for local work and tests. |
| **Main TMS** | `connected-frontend/` | The primary staff application: a hand-maintained single-page app (`index.html` plus modules in `js/`), served by nginx. It is **not** generated from `frontend/`; never replace it with a build of `frontend/`. |
| **Planning Workspace** | `frontend/` | A separate React + Vite + TypeScript planning surface. |

Every command below was run on a fresh clone on 2026-10-04.

## Prerequisites

- **Python 3.13** (what CI uses) and **Node 20** (what CI uses; newer versions also work).
- Git. macOS or Linux shell; on Windows use WSL.

## Run it locally

Three terminals, from the repository root.

**1. Backend** (http://localhost:8000):

```bash
bash RUN_TMS_BACKEND_MAC.sh
```

On the first run this creates `backend/.venv`, installs `backend/requirements.txt`,
and seeds a demo SQLite database (`backend/aafc_tms.db`: one National HQ,
7 Wing, 16 Squadrons, demo accounts). It then serves with auto-reload, which
watches `backend/app` only. Check it with
`curl localhost:8000/api/health` → `{"status":"ok"}`.

**2. Main TMS** (http://localhost:8080):

```bash
bash RUN_TMS_CONNECTED_FRONTEND_MAC.sh
```

Serves a copy of `connected-frontend/` (`index.html` plus `js/`, the same files
the production image serves) with its API address pointed at the local backend.
Sign in as Squadron → 7WG → 703 → Squadron Admin, access code `ADMIN703`.

**3. Planning Workspace** (http://localhost:5173):

```bash
cd frontend
npm ci
npm run dev
```

The dev server proxies `/api` to `http://localhost:8000`.

**If port 8000 is taken**, a server you did not start will answer, which is
confusing. Check with `lsof -nP -iTCP:8000 -sTCP:LISTEN`. Then use another port
and point both frontends at it:

```bash
PORT=8002 bash RUN_TMS_BACKEND_MAC.sh
AAFC_API_BASE=http://localhost:8002 bash RUN_TMS_CONNECTED_FRONTEND_MAC.sh
cd frontend && VITE_API_BASE_URL=http://localhost:8002 npm run dev
```

Interactive API docs (`/docs`, `/openapi.json`) are **disabled** on purpose
(since v25). The API surface is described in `docs/api_reference.md`.

Demo access codes exist only in the seeded demo database. Never use them in a
real environment.

## Test

```bash
# Backend: about 2,670 tests, roughly 5-10 minutes; must end with 0 failed
cd backend && .venv/bin/python -m pytest -q

# Architecture ratchets (monolith size, router role checks, router imports)
python3 -m unittest discover -s tools/architecture -p "test_*.py"
python3 tools/architecture/guard.py

# Frontend
cd frontend
npm run typecheck && npx eslint . && npm run test && npm run build
```

Browser tests (Playwright) need the servers running; CI runs them on Chromium,
Firefox and WebKit (`.github/workflows/e2e-tests.yml` shows the exact setup).

## Rules that keep this system predictable

- The backend decides every permission. Frontend role checks are presentation only.
- Alembic is the only way the schema changes (`backend/alembic/versions`).
- Every bug fix carries a regression test. Do not weaken a test to make it pass.
- The Main TMS `index.html` may not grow (CI ratchet): extract code into
  `connected-frontend/js/` modules instead of adding to it.

## Where to read next

| Topic | Document |
|---|---|
| Stabilisation programme: status, evidence, exit criteria | `docs/stabilisation/README.md` |
| Permission model and the remaining role checks | `docs/stabilisation/role-check-classification.md`, `AAFC_TMS_Access_And_Scope_Model.md` |
| Backups, restore verification, key handling | `docs/backup_and_restore.md` |
| Staging deployment | `deployment/README-staging.md` |
| Production deployment (a separate release decision) | `scripts/deploy-production.sh` |
| National-scale load qualification | `docs/stabilisation/national-qualification.md` |
| Working rules for contributors and coding agents | `CLAUDE.md`, `AGENTS.md`, `.claude/rules/` |

`AAFC_TMS_Setup_Run_Rollout_Guide.md` is **historical** (June 2026). It
describes an earlier repository layout and is kept for reference only.
