# Architecture

```
Client (React TS — later milestone; V8 vanilla frontend works interim)
        │  HTTPS, JWT in HTTP-only cookie / bearer
        ▼
Caddy/Nginx reverse proxy  ──►  FastAPI app (gunicorn + uvicorn workers)
                                   ├─ routers/      HTTP layer (auth, orgs, training, ops, health)
                                   ├─ dependencies  build Principal from JWT + live proxy state
                                   ├─ permissions   RBAC + tenant scoping (server-side)
                                   ├─ services      audit (append-only) + readiness engine
                                   ├─ models/       SQLAlchemy 2.x (UUID str PKs, soft delete,
                                   │                 *_at_time history, immutable audit)
                                   └─ seeds/        demo + stress data
                                   ▼
                          PostgreSQL (prod) / SQLite (demo)     Redis (rate-limit/cache/Celery — partial)
```

Boundaries: routers never re-implement tenancy; all scope decisions go through
`permissions.py`. Writes for wing/national actors require an active proxy/intervention
overlaid by `dependencies.get_principal`.
