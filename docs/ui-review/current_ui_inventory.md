# Current UI Inventory — AAFC TMS v17.1

Audit date: 2026-08-06. Source: live screenshots captured via Playwright (local dev servers).

## Two-frontend architecture

| Frontend | Source | Served | Port | Auth | Mobile nav |
|---|---|---|---|---|---|
| Main TMS | `connected-frontend/index.html` (~400KB SPA) | `python3 -m http.server` / nginx | 8080 | Multi-step (type→wing→sqn→role→code) | NONE — sidebar vanishes, no hamburger |
| Planning Workspace | `frontend/` (React/Vite) | Vite dev / Docker | 5173 | Single access-code field | Sidebar collapses, no hamburger |

---

## Main TMS — Pages by scope

### Squadron (sqn_admin / sqn_general)

| Page ID | Nav label | sqn_admin | sqn_general | Notes |
|---|---|---|---|---|
| getting-started | Getting Started | ✓ | ✓ | Setup checklist with Done/Pending badges and Go-to shortcut buttons |
| dashboard | Dashboard | ✓ | ✓ | Tonight/This Week readiness + 8-night grid + Term delivery charts |
| calendar | Calendar | ✓ | ✓ | Monthly grid, year selector, parade/holiday/activity legend |
| parade-nights | Parade Nights | ✓ | ✓ | Card-based session view; Add/Generate/Calendar/Weekly Program actions |
| weekly-program | Weekly Program | ✓ | ✓ | Parade night dropdown → printable program; empty until night selected |
| curriculum | Curriculum | ✓ | ✓ | Phase tabs, element/progress filters, Learning Hub links, session counts |
| activities | Activities | ✓ | ✓ | Squadron + inherited activities; holiday/NATHQ badges |
| facilitators | Facilitators | ✓ | ✓ | Status donut, workload bars, subject coverage, type breakdown, table |
| resources | Locations and Resources | ✓ | ✓ | Training locations and equipment |
| action-items | Needs Attention | ✓ | ✓ | Unscheduled curriculum + sessions without assignments |
| settings | Unit Settings | ✓ | — | Timing templates, unit config |
| accounts | Account Management | ✓ | — | User table + role badges + Flight groups + Reference Data |

### Wing (wing_admin / wing_viewer)

| Page ID | Nav label | wing_admin | wing_viewer | Notes |
|---|---|---|---|---|
| getting-started | Getting Started | ✓ | ✓ | |
| wing-overview | Wing Overview | ✓ | ✓ | Readiness table across all squadrons — very dense at 1440px |
| wing-activities | Wing Activities | ✓ | ✓ | Wing-level activities |
| wing-calendar | Wing HQ Calendar | ✓ | ✓ | Wing calendar view |
| curriculum | Curriculum | ✓ | ✓ | |
| audit | Audit | ✓ | ✓ | Immutable audit log table |
| accounts | Account Management | ✓ | — | |

### National (national_admin / national_viewer)

| Page ID | Nav label | national_admin | national_viewer | Notes |
|---|---|---|---|---|
| getting-started | Getting Started | ✓ | ✓ | |
| national | National Overview | ✓ | ✓ | Multi-wing training readiness dashboard |
| national-activities | National Activities | ✓ | ✓ | |
| wing-calendar | Wing HQ Calendar | ✓ | ✓ | |
| curriculum | Curriculum | ✓ | ✓ | |
| audit | Audit | ✓ | ✓ (nav shown) | **BUG**: backend returns 403 for national_viewer — see F-FUNC-01 |
| accounts | Account Management | ✓ | — | |

### Auditor

| Page ID | Nav label | Notes |
|---|---|---|
| audit | Audit | Full audit log |
| accounts | Account Management | |

### System Admin

| Page ID | Nav label | Notes |
|---|---|---|
| getting-started | Getting Started | |
| system-console | System Console | Build info, system overview, platform health, maintenance, backup |
| national | National Overview | Via sa-scope-bar (Viewing: dropdown) |
| national-activities | National Activities | |
| wing-activities | Wing Activities | Via sa-scope-bar |
| wing-calendar | Wing HQ Calendar | |
| curriculum | Curriculum | |
| audit | Audit | |
| accounts | Account Management | |

---

## Planning Workspace — Routes by role (dev mode, all routes accessible)

In deployed module mode, only `/planning` is reachable. Locally, all routes accessible.

| Route | sqn_admin | sqn_general | wing_admin | national_admin | auditor |
|---|---|---|---|---|---|
| / (Home) | ✓ | ✓ | | | |
| /dashboard | ✓ | ✓ | | | |
| /calendar | ✓ | ✓ | | | |
| /parade-nights | ✓ | ✓ | | | |
| /weekly-program | ✓ | ✓ | | | |
| /curriculum | ✓ | ✓ | | | |
| /facilitators | ✓ | ✓ | | | |
| /facilitator-schedule | ✓ | | | | |
| /resources | ✓ | ✓ | | | |
| /cadets | ✓ | ✓ | | | |
| /reports | ✓ | ✓ | | | |
| /report-catalogue | ✓ | | | | |
| /action-items | ✓ | ✓ | | | |
| /imports | ✓ | | | | |
| /audit | ✓ | | ✓ | ✓ | ✓ |
| /admin | ✓ | | | | |
| /accounts | ✓ | | ✓ | ✓ | ✓ |
| /settings | ✓ | | | | |
| /wing-overview | | | ✓ | | |
| /national-overview | | | ✓ | ✓ | |
| /planning | ✓ | ✓ | ✓ | ✓ | |

---

## Shared infrastructure

- Both frontends read backend URL from `<meta name="aafc-api-base">` tag
- Both store JWT in `sessionStorage` under key `'aafc_token'`
- Both share the same backend (`/api/*`) and the same role/scope system
- Cookie fallback (`aafc_session`) used when sessionStorage is empty (cross-origin tab handoff)
