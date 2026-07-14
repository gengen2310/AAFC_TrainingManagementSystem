# AAFC TMS — Role and Navigation Rationalisation

Phase 3/20 output. Derived from code analysis of `connected-frontend/index.html` (NAV_BY_SCOPE) and `frontend/src/auth/roleGuards.ts`.
Created: 2026-07-14.

---

## Role Hierarchy

| Role | Level | Description |
|---|---|---|
| `sqn_general` | Squadron | Standard squadron staff. Read/write operational data for own squadron only. Cannot manage accounts. |
| `sqn_admin` | Squadron | Squadron administrator. Full squadron access including account management and settings. |
| `wing_viewer` | Wing | Wing observer. Read-only across all squadrons in own wing. |
| `wing_admin` | Wing | Wing administrator. Read/write wing-level data; read-only view into squadron data. |
| `national_viewer` | National | National observer. Read-only across all wings and squadrons. |
| `national_admin` | National | National administrator. Write access to national-level data. |
| `auditor` | Cross-level | Dedicated read-only audit role. Access to audit log and cross-wing reports. |
| `system_admin` | System | Platform administrator. System console, maintenance, backup, all data access. |

---

## Navigation by Scope — Connected-Frontend

The `NAV_BY_SCOPE` object in `connected-frontend/index.html` defines which pages appear in the sidebar for each scope. After the final UI cleanup (commit `e25343b`), the planning pages (`_PLANNING_PAGES = []`) are no longer injected into any scope.

### Squadron Scope (`sqn_admin`, `sqn_general`)

| Nav item | Page ID | Who sees it | Notes |
|---|---|---|---|
| Dashboard | `dashboard` | Both | Default landing page |
| Calendar | `calendar` | Both | Parade night calendar |
| Parade Nights | `parade-nights` | Both | — |
| Weekly Program | `weekly-program` | Both | Printable program |
| Curriculum | `curriculum` | Both | — |
| Activities | `activities` | Both | CEA import hub (consolidated from Import Review) |
| Facilitators | `facilitators` | Both | — |
| Resources | `resources` | Both | Rooms and equipment |
| Reports | `reports` | Both | — |
| Action Items | `action-items` | Both | — |
| Planning Workspace | Embedded `/planning` | Both | React Planning Workspace iframe/module |
| Settings | `settings` | `sqn_admin` only | Squadron settings and timing templates |
| Accounts | `accounts` | `sqn_admin` only | User/access code management |

Retired from this scope (redirected if accessed programmatically):
- `planning-year` → `activities`
- `planning-missions` → `activities`
- `planning-builder` → `parade-nights`
- `planning-guide` → `dashboard`

### Wing Scope (`wing_admin`, `wing_viewer`)

| Nav item | Page ID | Notes |
|---|---|---|
| Wing Overview | `wing-overview` | Cross-squadron health summary |
| Wing Calendar | `wing-calendar` | Wing HQ event calendar |
| Curriculum Coverage | `curriculum-coverage` | Cross-squadron curriculum matrix |
| Training Balance | `training-balance` | Subject-area distribution |
| Facilitator Load | `facilitator-load` | Facilitator capacity across squadrons |
| Risk & Bottlenecks | `risk-bottlenecks` | Units requiring attention |
| Audit | `audit` | Immutable audit log (wing scope) |
| Reports | `reports` | Cross-wing reports |
| Accounts | `accounts` | `wing_admin` only — manage sqn accounts in wing |

### National Scope (`national_admin`, `national_viewer`)

| Nav item | Page ID | Notes |
|---|---|---|
| National | `national` | National cross-wing assurance overview |
| Audit | `audit` | National scope audit log |
| Reports | `reports` | National reports |
| Accounts | `accounts` | `national_admin` only — all accounts |

### Auditor Scope

| Nav item | Page ID | Notes |
|---|---|---|
| Audit | `audit` | Audit log (read-only) |
| Reports | `reports` | Cross-wing reports (read-only) |

### System Admin Scope

| Nav item | Page ID | Notes |
|---|---|---|
| System Console | `system-console` | Platform admin, health, maintenance, backup, restore, scope-map |
| Accounts | `accounts` | All accounts across all organisations |
| Audit | `audit` | Complete audit log |

---

## Navigation — React Planning Workspace (`frontend/src/auth/roleGuards.ts`)

The React app enforces role guards on each route. In the current deployment, the React app is only used as a module embedded at `/planning` within the connected-frontend. In module mode, the left sidebar is hidden and only the planning workspace is shown.

| Route | Allowed roles | Notes |
|---|---|---|
| `/dashboard` | All | Wing/national users see proxy-mode squadron selector |
| `/calendar` | All | — |
| `/parade-nights` | All | — |
| `/parade-nights/:id` | All | Detail view |
| `/weekly-program` | All | — |
| `/curriculum` | All | — |
| `/facilitators` | All | — |
| `/resources` | All | — |
| `/cadets` | `sqn_admin`, higher roles | `sqn_general` does NOT see cadets in the React app (distinct from connected-frontend where sqn_general sees parade nights, not cadets separately) |
| `/reports` | All | — |
| `/report-catalogue` | All | — |
| `/action-items` | All | — |
| `/imports` | `sqn_admin`, `wing_admin`, `national_admin`, `system_admin` | Admin-only |
| `/audit` | All (read-only for most) | — |
| `/admin` | `sqn_admin`, `wing_admin`, `national_admin`, `system_admin` | Admin-only |
| `/accounts` | `sqn_admin`, `wing_admin`, `national_admin`, `auditor`, `system_admin` | — |
| `/settings` | All | Access codes / personal settings |
| `/wing-overview` | `wing_admin`, `wing_viewer`, `national_admin`, `national_viewer`, `system_admin` | — |
| `/national-overview` | `national_admin`, `national_viewer`, `system_admin` | — |
| `/planning` | All authenticated | Planning Workspace (full module) |

---

## Scope Enforcement — Backend

The backend derives scope from the authenticated session. Frontend navigation gates are supplementary — the backend enforces the real restriction.

| Pattern | Implementation |
|---|---|
| Role check | `require_role(p, *roles)` in `permissions.py` |
| Squadron scope | `require_can_view_squadron(p, squadron_id)` — also checks wing membership |
| Write check | `require_can_write_squadron(p, squadron_id)` — blocks `wing_viewer`, `national_viewer`, `auditor` |
| Planning year scope | `_require_year_access(p, py, write)` in `planning.py` — `sqn_general` restricted to own squadron since commit `67e8f13` |
| System admin | `require_system_admin(p)` — system_admin only |

---

## Role Rationalisations Made in This Release

| Change | What was done | Commit |
|---|---|---|
| Retired 4 planning nav pages | Removed from `_PLANNING_PAGES`; `nav()` now redirects programmatic access | `e25343b` |
| `sqn_general` IDOR fix | Added `sqn_general` to own-sqn enforcement in `_require_year_access` | `67e8f13` |
| Removed `ph-sub` subtitles | 4 decorative subtitles removed from Curriculum, Activities, Facilitators, Resources pages | `e25343b` |
| Removed conflict/unscheduled chips | Simplified context bar; health detection logic retained | `e25343b` |

---

## Rationalisation Decisions (Deferred)

| Item | Reason deferred |
|---|---|
| Remove 5 hidden planning page HTML divs from index.html | Safe to remove; ~15KB saving. Not urgent; no navigation path exists. |
| `wing_viewer` write access alignment | wing_viewer is correctly blocked for writes; no change needed |
| Proxy mode for national/wing in React | Implemented and working; further UX polish is post-beta |
