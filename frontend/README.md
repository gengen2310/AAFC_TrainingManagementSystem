# AAFC TMS — Planning Workspace (React + TypeScript + Vite)

`frontend/` is the specialised **Planning Workspace module** for the AAFC Training Management System. It is not the Main TMS frontend and it is not a migration-in-progress replacement for it.

The two browser surfaces are intentionally separate:

- `connected-frontend/` is the Main TMS SPA that beta users land on.
- `frontend/` is the React/Vite Planning Workspace, mounted at `/planning` and deployed separately.

Both use the same FastAPI backend, tenancy model and user session. The Planning Workspace must not grow a second login screen or a duplicate full TMS shell.

## Run locally

```bash
cd frontend
cp .env.example .env
npm install
npm run dev                   # http://localhost:5173
```

Start the backend first:

```bash
cd ../backend
python manage.py --seed
python manage.py --reload
```

## Scripts

```bash
npm run typecheck   # TypeScript typecheck
npm run test        # Vitest unit/component tests
npm run test:e2e    # Planning Workspace Playwright suite
npm run build       # production Vite build -> frontend/dist
npm run lint        # ESLint
```

## Deployed route contract

The authenticated React application owns `/planning` only. Authenticated catch-all routes redirect to `/planning`. An unauthenticated Planning Workspace load displays the hand-back state (`Session not found` / `Return to TMS`) rather than presenting a second login UI.

Planning functionality is rendered inside that module, including the year/night planning views, mission backlog and planning tools, scheduling/session editing, conflict indicators, class-aware planning, facilitator planning information and related planning workflows.

Standalone React routes from an earlier full-app design — for example `/dashboard`, `/cadets`, `/calendar`, `/resources`, `/reports`, `/facilitators`, `/parade-nights`, `/weekly-program`, `/wing-overview` and `/national-overview` — are not deployed application routes. Main TMS functionality remains owned by `connected-frontend/`.

## Session and API model

- Both frontends use the same FastAPI backend.
- `sessionStorage` plus `Authorization: Bearer <token>` is the primary browser-session mechanism.
- The secure `aafc_session` cookie is the fallback used for cross-origin/fresh-tab handoff, including opening Planning Workspace from Main TMS.
- The Planning Workspace does not collect an access code itself.
- The backend remains authoritative for authentication, RBAC, tenancy and write permissions; UI visibility is not a security boundary.
- No access codes or operational data should be persisted in `localStorage`.

The deployed services read the backend base URL from the `aafc-api-base` meta tag, rewritten by the service entrypoint from `AAFC_API_BASE`. Local Vite development may use `VITE_API_BASE_URL`/the local proxy as configured in the repository.

## Test ownership

Browser tests are split by product surface:

- `frontend/e2e/` tests only deployed Planning Workspace `/planning` behaviour and cross-interface session contracts.
- `frontend/e2e-connected/` is the authoritative Main TMS browser suite.
- Backend tests own API, RBAC, tenancy and domain contracts shared by both surfaces.

See `docs/release/planning-workspace-e2e-disposition.md` for the release-qualification disposition of obsolete full-app React E2E tests.
