# Skill Provenance — AAFC TMS UI/UX Review

Captured: 2026-08-06. Each skill was inspected before installation.

## Skills Evaluated

| Skill | Package | Version | Licence | Credential access | Network access | Decision |
|---|---|---|---|---|---|---|
| Taste | `skills` (npm) | 1.5.22 | MIT | None | Read-only fetch | APPROVED |
| Impeccable | `npx impeccable` | — | Apache 2.0 | Reads/writes `.claude/settings.local.json` | None | APPROVED WITH CAUTION (see note) |
| Playwright CLI | `@playwright/cli` | 0.1.17 | Apache 2.0 | None | None | APPROVED (pre-installed as `@playwright/test` v1.62.1) |
| Awesome DESIGN.md | GitHub (reference) | — | MIT | None | Public GitHub read | REFERENCE ONLY |
| img2threejs | npm | — | MIT | None | None | NOT APPLICABLE (Three.js not authorised for this review) |

## Impeccable caution note

Impeccable modifies `.claude/settings.local.json`. That file contains a `permissions.allow` array with project-specific tool allow-lists. Installing Impeccable without first reading the file would overwrite those settings.

**Action taken**: Read `.claude/settings.local.json` before any Impeccable operation. Impeccable install was NOT run during this audit pass because no settings changes were required and the existing config must be preserved.

## Playwright usage

Playwright was used via `@playwright/test` (already installed in `frontend/node_modules`). No additional installation was required. Browser was Chromium via `chromium.launch({ headless: true })`. Screenshots were captured without interacting with any external service.

All captures ran against local dev servers only:
- Main TMS: `http://localhost:8080` (connected-frontend served by `python3 -m http.server 8080`)
- Planning Workspace: `http://localhost:5173` (Vite dev server)
- Backend: `http://localhost:8000` (uvicorn, SQLite local demo DB)

No staging or production system was accessed during this audit.
