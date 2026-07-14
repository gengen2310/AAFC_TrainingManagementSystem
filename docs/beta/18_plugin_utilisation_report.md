# AAFC TMS — Plugin and Dependency Utilisation Report

Phase 18 output. All external dependencies assessed for active use, version risk, and replaceability.
Created: 2026-07-14.

---

## Backend Dependencies (`backend/requirements.txt`)

| Package | Version | Usage | Status |
|---|---|---|---|
| FastAPI | `>=0.110` | All routing, dependency injection, request/response models | Active; no known CVEs at capture |
| Uvicorn | — | ASGI server (dev); Gunicorn+UvicornWorker in production | Active |
| Gunicorn | — | Production process manager | Active |
| SQLAlchemy | `>=2.0` | ORM, migrations base | Active; 2.0 mapped_column style used throughout |
| Alembic | — | Database migrations (26 migration files) | Active |
| python-jose | — | JWT encode/decode (HS256) | Active |
| passlib + bcrypt | — | Access code hashing | Active |
| pydantic | `v2` | Request/response validation, Settings | Active; all schemas use Pydantic v2 model_ syntax |
| python-dotenv | — | `.env` file loading in dev | Active |
| openpyxl | — | XLSX export (facilitator workload, night summaries) and import | Active |
| httpx | — | Test client (via FastAPI `TestClient`) | Active; tests only |
| pytest | — | Test runner | Active; 503 tests |

No dependencies flagged as:
- Abandoned/unmaintained
- Known CVEs (at time of audit)
- Unused

---

## React Frontend Dependencies (`frontend/package.json`)

| Package | Usage | Status |
|---|---|---|
| React 18 | Core UI framework | Active |
| React DOM | DOM rendering | Active |
| React Router v6 | Client-side routing (all 22 routes) | Active |
| TanStack Query (React Query) v5 | All data fetching, caching, stale-time management | Active; all API calls via `useQuery`/`useMutation` |
| Vite | Build system (dev server + production build) | Active |
| TypeScript | Static type checking | Active; 0 errors at build |
| vite-plugin-singlefile | Single-file build mode (`npm run build:single`) for `make connected` → `connected-frontend/index.html` regeneration | Active (build mode only) |
| Vitest | Unit test runner (4 test files, 8 tests) | Active (minimal coverage) |
| @testing-library/react | Component test utilities | Active (Vitest setup) |

No dependencies flagged as unused. The following were considered for removal but retained:
- `vite-plugin-singlefile`: Required for `make connected` build; not active in normal Vite build
- Vitest: Low coverage but kept for future expansion

---

## Infrastructure Dependencies

| Tool | Where used | Status |
|---|---|---|
| Railway | Hosting platform (3 services × 2 environments) | Active |
| Railway PostgreSQL | Database (staging + production) | Active |
| GitHub Actions | CI/CD (backup + restore-test workflows) | Active; both workflows confirmed passing |
| GPG | Backup encryption | Active |
| nginx | Static file serving for `connected-frontend/` in Docker | Active |
| Docker | All 3 service deployments | Active |

---

## Unused or Retired Packages

None identified. All declared dependencies are actively called in the codebase.

---

## Dependency Risk Assessment

| Risk | Item | Mitigation |
|---|---|---|
| LOW | Python 3.13 + SQLite datetime adapter deprecation | Production uses PostgreSQL; no production impact |
| LOW | `python-jose` (JWT) — less actively maintained than `python-jwt` alternatives | HS256 usage is straightforward; migration path to PyJWT is simple if needed |
| LOW | Single-file SPA has no bundler or dependency management | Intentional design; no supply chain risk from npm for connected-frontend |
| NONE | Seeded dev codes in backend Python code | Codes are hashed in DB; seed files clearly marked dev-only; blocked from production by `ENVIRONMENT` check |

---

## Summary

All dependencies are active, appropriate for their use, and at no immediate version risk. No packages can be removed without breaking functionality. The dependency footprint is deliberately small.
