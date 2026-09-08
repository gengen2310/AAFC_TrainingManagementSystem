# Planning Workspace E2E disposition

## Architecture boundary

`frontend/` is the specialised Planning Workspace module. `frontend/src/App.tsx` exposes one authenticated application route, `/planning`, and redirects authenticated catch-all routes to it. Authentication is inherited from the shared TMS backend session. The full Training Management System remains `connected-frontend/`.

Release qualification therefore must not keep tests green by recreating a second React TMS shell. A browser test that asserts `/dashboard`, `/cadets`, `/calendar`, `/resources`, `/reports`, `/facilitators`, `/parade-nights`, `/weekly-program`, `/wing-overview` or `/national-overview` inside `frontend/` is testing a retired architecture rather than the deployed Planning Workspace.

## Removed stale specs

The following specs were removed from `frontend/e2e/` because their UI assertions target retired full-app routes. Their removal does not remove product functionality; the authoritative Main TMS or backend still owns those contracts.

| Removed Planning Workspace spec | Why stale | Authoritative coverage |
| --- | --- | --- |
| `dashboard.spec.ts` | React Dashboard route no longer exists | `e2e-connected/training-dashboard.spec.ts`, `e2e-connected/dashboard-element-progress.spec.ts`, backend dashboard tests |
| `command-dashboard.spec.ts` | Wing/National assurance pages are not PW routes | Main TMS dashboard/organisation E2E and `backend/tests/test_command_dashboard.py` |
| `cadet-class-membership.spec.ts` | Explicitly targeted full-app `/cadets` | Main TMS training-class/cadet workflows and backend membership tests |
| `cadet-class-membership-picker-grouping.spec.ts` | Picker lived on retired `/cadets` route | Main TMS class workflows and backend class-membership contracts |
| `facilitators.spec.ts` | Standalone React facilitator-management page retired | Main TMS facilitator E2E plus Planning Workspace facilitator drawer tests |
| `holiday-and-resources.spec.ts` | Standalone `/calendar` and `/resources` routes retired | Main TMS calendar/resource/equipment E2E and backend resource tests |
| `multi-wing-scope.spec.ts` | Standalone Wing/National overview routes retired | Main TMS national/wing views and backend multi-wing/RBAC tests |
| `parade-nights.spec.ts` | Standalone React parade-night CRUD page retired | Main TMS parade-night E2E and PW planning-grid/session specs |
| `reports.spec.ts` | Standalone React reports page retired | Main TMS dashboard/reporting E2E and `backend/tests/test_reports.py` |
| `weekly-program-classes.spec.ts` | File itself documented `/weekly-program` as full-app mode | `e2e-connected/weekly-program-classes.spec.ts` and PW planning-grid tests |
| `wing-proxy.spec.ts` | Wing Assurance/proxy shell is not a PW route | Main TMS organisational workflows plus backend planning-proxy RBAC tests |

## Retained Planning Workspace coverage

`frontend/e2e/` continues to own module-specific browser contracts: shared-session authentication, no second login UI, squadron scope selection, cross-interface logout/session invalidation, accessibility states, Mission Backlog, planning filters, parade-night grid/class rendering, conflicts, session lifecycle/move/archive/restore, facilitator leave handling, year-view behaviour and rollover visibility.

`navigation.spec.ts` was rewritten to prove the module boundary directly: unauthenticated deep links show the TMS hand-back state, authenticated entry resolves to `/planning`, and an old `/dashboard` deep link cannot resurrect the retired React shell.

## Release rule

A future feature belongs in `frontend/e2e/` only when it is rendered inside the deployed `/planning` module. Full TMS browser coverage belongs in `frontend/e2e-connected/`. Cross-surface behaviour should be tested at the interface boundary rather than duplicated in two application shells.
