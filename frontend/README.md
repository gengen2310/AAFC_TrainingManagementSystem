# AAFC TMS — Frontend (React + TypeScript + Vite)

Production frontend for the AAFC Training Management System, V9 National Deployable Edition.
It talks to the FastAPI backend only. **The old standalone V8 HTML/localStorage prototype is
deprecated and is not the source of truth.**

## Run
```bash
cd frontend
cp .env.example .env          # VITE_API_BASE_URL=http://localhost:8000
npm install
npm run dev                   # http://localhost:5173 (proxies /api -> backend)
```
Start the backend first: `cd ../backend && python manage.py --seed && python manage.py --reload`.

## Scripts
```bash
npm run typecheck   # tsc --noEmit  (app source type-checks clean)
npm run test        # Vitest unit/component tests
npm run test:e2e    # Playwright E2E (needs backend + dev server running)
npm run build       # tsc -b && vite build  -> frontend/dist
npm run lint        # eslint
```

## Pages (15, all wired to the backend)
Dashboard · Calendar · Parade Nights (+ detail: publish/close, add session, set status) ·
Weekly Program (printable, A4 print CSS) · Curriculum (filters, Learning Hub links, session
drill-down) · Facilitators (add, stats) · Resources (training areas, equipment, clashes) ·
Cadets (sensitive support notes only when the backend returns them) · Reports (only implemented
reports; nothing fabricated) · Action Items (add/close, run exception checks) · Imports
(preview → commit → rollback; commit gated on preview) · Audit (read-only, filters) ·
Admin/Settings · Wing Overview · National Overview.

## Production (same-domain model — preferred)
Build with `npm run build` (→ `dist/`). In production, Caddy serves `dist/` at `/` and
reverse-proxies `/api/*` to the backend on the **same domain**, so set `VITE_API_BASE_URL=`
(empty) and the app calls relative `/api/...` paths — no cross-site CORS/cookie/CSRF setup needed.
The prod compose (`docker-compose.prod.yml`) mounts `frontend/dist` into Caddy at `/srv/frontend`
and the Caddyfile falls back to `index.html` so React Router refreshes work. Separate hosting
(Netlify/Vercel/Cloudflare/S3) is an advanced option only and needs careful CORS/cookie/CSRF/HTTPS.

## Auth & security
- Login posts `{ code }` to `/api/auth/login`; role/scope come from `/api/auth/me`.
- Cookie session preferred; bearer token fallback kept in `sessionStorage` for the session only and
  cleared on logout/401. No access codes or operational data in localStorage.
- The backend is the security authority; the frontend only hides/disables actions to reduce
  confusion, and surfaces `403 proxy_required` / `intervention_required` with a prompt to enter the
  right mode (with a reason). Wing Admin proxy enter/exit is in the sidebar.
- Status badges use icon + label + colour + border (never colour alone); three themes
  (light / dark / high-contrast); skip-link, ARIA labels, table captions.

## Honest status
App source (32 files, all 15 pages) **type-checks with 0 errors** against real React/Router/Query
types. `npm install` → `vite build` and the Playwright/Vitest/Axe runs were **not executed in the
original build sandbox** (install couldn't complete there); run them locally with the scripts above.
