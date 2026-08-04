# Environment Variable Inventory

Names and purpose only — no values recorded here or anywhere in this program, per
`.claude/rules/capability-preservation.md` §4 and `.claude/rules/security.md`.

## Backend (staging service, names pulled live 2026-08-04 via `railway variable list`)

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres connection string (Railway-managed) |
| `JWT_SECRET`, `SECRET_KEY` | Auth signing — must be ≥32 chars, unique per environment (CLAUDE.md invariant) |
| `ENVIRONMENT` | `production`/`staging`/`development` — drives `config.py`'s fail-closed `is_production` checks |
| `CORS_ALLOWED_ORIGINS` | Locked per-environment, no wildcard |
| `COOKIE_SECURE`, `COOKIE_SAMESITE` | `aafc_session` fallback-cookie flags — `SameSite=None` is load-bearing for cross-origin TMS→Planning-Workspace handoff, not a misconfiguration (`.claude/rules/architecture.md`) |
| `DB_POOL_SIZE`, `DB_POOL_MAX_OVERFLOW`, `GUNICORN_WORKERS` | Per-environment connection-pool sizing — subject of GAP-28/29's capacity investigation |
| `PLANNING_WORKSPACE_URL` | Feeds the `<meta name="aafc-api-base">`-adjacent link connected-frontend shows to open Planning Workspace |
| `LOG_LEVEL` | |
| `PORT` | Railway-injected |
| `RAILWAY_*` | Railway platform-injected (project/environment/service IDs, git SHA, domains) — read-only context, not application config |

## Frontends

- Both `connected-frontend/` and `frontend/` read their backend URL from a
  `<meta name="aafc-api-base">` tag, rewritten at container start by each
  service's own `docker-entrypoint.sh` from an `AAFC_API_BASE`-style env var —
  never hardcoded in source (CLAUDE.md).
- `frontend/`'s Vite build also reads `VITE_API_BASE_URL` (fallback) and
  `VITE_HASH_ROUTER` (routing mode) at build time.

## Known naming inconsistency flagged by the remediation instruction (Section 4)

Instruction Section 4 names `API_BASE` vs `AAFC_API_BASE` vs `BACKEND_URL` as a
hypothetical example of variable-name drift to check for. Verified: this codebase
consistently uses `AAFC_API_BASE`-family names feeding the single
`<meta name="aafc-api-base">` contract in both frontends — no such drift found on
this specific point. Broader duplicate/near-duplicate scan (frontend state keys,
sessionStorage keys, CSV headers, etc.) is still open — see `reference_key_inventory.md`.

## Not yet done

Full duplicate/near-duplicate/stale-reference scan across all four environments
(production, staging, and each frontend's build-time vars) — this pass only
enumerated staging backend's live variable names.
