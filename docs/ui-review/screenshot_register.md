# Screenshot Register — AAFC TMS UI/UX Review

Captured: 2026-08-06 via Playwright/Chromium headless.
Servers: localhost:8080 (Main TMS), localhost:5173 (Planning Workspace), localhost:8000 (backend).
Auth: API-based token injection (lookup → login → sessionStorage.setItem).

## Naming convention

`{role}_{viewport}_{page_or_route}.png`

- Role: `sqn_admin`, `sqn_general`, `wing_admin`, `wing_viewer`, `national_admin`, `national_viewer`, `system_admin`, `auditor`
- Viewport: `desktop_1440` (1440×900), `mobile_390` (390×844)
- Page/route: page ID (Main TMS) or route slug (Planning Workspace)

## Main TMS captures

Directory: `screenshots/main-tms/`
Total: 135 screenshots

| File | Role | Page | Viewport |
|---|---|---|---|
| login_desktop_1440.png | none | login | desktop |
| login_mobile_390.png | none | login | mobile |
| sqn_admin_desktop_1440_landing.png | sqn_admin | dashboard (landing) | desktop |
| sqn_admin_desktop_1440_getting-started.png | sqn_admin | getting-started | desktop |
| sqn_admin_desktop_1440_dashboard.png | sqn_admin | dashboard | desktop |
| sqn_admin_desktop_1440_calendar.png | sqn_admin | calendar | desktop |
| sqn_admin_desktop_1440_parade-nights.png | sqn_admin | parade-nights | desktop |
| sqn_admin_desktop_1440_weekly-program.png | sqn_admin | weekly-program | desktop |
| sqn_admin_desktop_1440_curriculum.png | sqn_admin | curriculum | desktop |
| sqn_admin_desktop_1440_activities.png | sqn_admin | activities | desktop |
| sqn_admin_desktop_1440_facilitators.png | sqn_admin | facilitators | desktop |
| sqn_admin_desktop_1440_resources.png | sqn_admin | resources | desktop |
| sqn_admin_desktop_1440_action-items.png | sqn_admin | action-items | desktop |
| sqn_admin_desktop_1440_accounts.png | sqn_admin | accounts | desktop |
| sqn_admin_mobile_390_*.png | sqn_admin | all above | mobile |
| sqn_general_desktop_1440_*.png | sqn_general | 10 pages | desktop |
| sqn_general_mobile_390_*.png | sqn_general | 10 pages | mobile |
| wing_admin_desktop_1440_*.png | wing_admin | 7 pages | desktop |
| wing_admin_mobile_390_*.png | wing_admin | 7 pages | mobile |
| wing_viewer_desktop_1440_*.png | wing_viewer | 6 pages | desktop |
| wing_viewer_mobile_390_*.png | wing_viewer | 6 pages | mobile |
| national_admin_desktop_1440_*.png | national_admin | 7 pages | desktop |
| national_admin_mobile_390_*.png | national_admin | 7 pages | mobile |
| national_viewer_desktop_1440_*.png | national_viewer | 6 pages | desktop |
| national_viewer_mobile_390_*.png | national_viewer | 6 pages | mobile |
| system_admin_desktop_1440_*.png | system_admin | 9 pages | desktop |
| system_admin_mobile_390_*.png | system_admin | 9 pages | mobile |
| auditor_desktop_1440_*.png | auditor | 2 pages | desktop |
| auditor_mobile_390_*.png | auditor | 2 pages | mobile |

## Planning Workspace captures

Directory: `screenshots/planning-workspace/`
Total: 87 screenshots

| Role | Routes captured | Viewports |
|---|---|---|
| none (login) | login | desktop + mobile |
| sqn_admin | 19 routes | desktop + mobile |
| sqn_general | 12 routes | desktop + mobile |
| wing_admin | 5 routes | desktop + mobile |
| national_admin | 4 routes | desktop + mobile |
| auditor | 2 routes | desktop + mobile |

## Errors recorded

| Frontend | Role | Error | Status |
|---|---|---|---|
| Main TMS | national_viewer | GET /api/audit → 403 | Bug — nav shows Audit link but role denied |
| Main TMS | all | `__APP_BUILD__` not substituted | Cosmetic — placeholder visible in System Console |

## Machine context

- Node.js: v26.3.1
- Playwright: @playwright/test v1.62.1
- Chromium: headless, bundled with Playwright
- OS: macOS Darwin 25.4.0
- Backend: SQLite local demo (seed_all.py dataset — 16 sqns, 1 wing, full curriculum)
