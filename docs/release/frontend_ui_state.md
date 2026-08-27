# AAFC TMS — Authoritative Frontend UI State

**Purpose:** Canonical record of every nav item, page, and key action button present
in `connected-frontend/index.html` at the locked HEAD. Any future change that adds,
removes, renames, or hides an item listed here requires explicit authorisation
(record as `USER-AUTHORISED CHANGE` with reason). Any change that silently
removes an item without this record is a regression under
`.claude/rules/capability-preservation.md`.

**Locked at:** `de885f7` — *fix: use w.wing_id for email config input IDs (A11Y)*  
**Staging:** `de885f7` deployed 2026-08-21 (fingerprint 458c7d507b82a87c01dc6e8ac77947470ccf29c7)  
**Backend tests:** 1818 passed, 7 skipped  
**Playwright staging:** 136 passed, 44 skipped, 15 failed (all failures are pre-existing env-var gaps — `STAGING_SYSADMIN_CODE` not passed and `STAGING_NATIONAL_VIEWER_CODE` not set; zero product-behaviour failures)  
**Last updated:** 2026-08-17

---

## 1. Navigation sidebar — HTML structure (source of truth)

The sidebar is built statically in `index.html` (~line 854–884). Items hidden by
`style="display:none"` are shown/hidden at runtime by `applyNavScope()` and
`bootApp()` based on `effectiveScope()`.

```
OVERVIEW
  Getting Started         nav('getting-started')    always visible
  Dashboard               nav('dashboard')           always visible
  Training Calendar       nav('calendar')            always visible

PLAN TRAINING
  Curriculum              nav('curriculum')          always visible
  Activities              nav('activities')          always visible
  Parade Nights           nav('parade-nights')       always visible
  Weekly Program          nav('weekly-program')      always visible

PEOPLE AND RESOURCES
  Facilitators            nav('facilitators')        always visible
  Resources & Training Areas  nav('resources')       always visible

NEEDS ATTENTION
  Needs Attention         nav('action-items')        always visible

SETTINGS (id="admin-lbl", hidden until sqn scope + write role)
  Unit Settings           nav('settings')            admin-el
  Account Management      nav('accounts')            hidden until eligible scope

COMMAND (id="hq-lbl", hidden until wing/national/system_admin)
  Wing Overview           nav('wing-overview')       nav-scope
  Wing Activities         nav('wing-activities')     nav-scope
  Wing HQ Calendar        nav('wing-calendar')       nav-scope
  National Overview       nav('national')            nav-scope
  National Activities     nav('national-activities') nav-scope
  Audit                   nav('audit')               nav-scope

SYSTEM (id="nav-system-lbl", hidden until system_admin)
  System Console          nav('system-console')      system_admin only

HELP & REFERENCE
  Help & Reference        nav('help')                always visible
  Service Desk            nav('service-desk')        squadron/wing/national/system_admin

WORKSPACE (id="nav-lbl-pw", hidden by default; shown by bootApp())
  Planning Workspace ↗    nav-pw-link (external)     shown when S.pwUrl set AND
                                                     scope ∈ {squadron,wing,national,system_admin}
  Planning Workspace (unavailable)  nav-pw-unconfigured
                                                     shown when no S.pwUrl AND scope === 'squadron'
```

### Explicitly ABSENT from nav (removed — do not re-add without authorisation)

| Item | Removed | Reason |
|---|---|---|
| Planning (native page) | 2026-08-17 `2598177` | Reversal of native integration; PW remains external link |
| Programme Action Centre | 2026-08-17 `2598177` (Phase 2) | Consolidated into Needs Attention |
| Program Audit | 2026-08-17 `2598177` (Phase 2) | Low-usage admin view removed from pilot nav |

---

## 2. `NAV_BY_SCOPE` — pages allowed per scope

Source: `index.html` ~line 4563 (`const NAV_BY_SCOPE`).

| Scope | Pages |
|---|---|
| `squadron` | getting-started, dashboard, calendar, parade-nights, weekly-program, curriculum, activities, facilitators, resources, action-items, help, settings, accounts, **service-desk**, + `_PLANNING_PAGES` |
| `wing` | getting-started, wing-overview, wing-activities, wing-calendar, curriculum, audit, accounts, **service-desk**, + `_PLANNING_PAGES` |
| `national` | getting-started, national, national-activities, wing-calendar, curriculum, audit, accounts, **service-desk**, + `_PLANNING_PAGES` |
| `auditor` | audit, accounts, + `_PLANNING_PAGES` |
| `system_admin` | getting-started, system-console, national, national-activities, wing-activities, wing-calendar, curriculum, audit, accounts, **service-desk**, + `_PLANNING_PAGES` |

`_PLANNING_PAGES = []` — placeholder for future planning sub-pages; currently empty.

---

## 3. Pages and key action buttons

Extracted directly from source. "admin-el" = shown only when `canWriteSquadron()`.
"plan-write-el" = shown only when `canWritePlan()` (sqn_admin + wing_admin).

### page-getting-started — Getting Started
No header action buttons. Checklist rendered by `loadGettingStarted()` /
`_renderGsSections()`. Optional steps (e.g. "Organise Cadets into Flights") are
filtered out: `filter(s => !s.optional)`.

### page-dashboard — Dashboard
No header action buttons. Content: Tonight & This Week, Session Delivery analytics,
Curriculum Progress, Staffing Resilience (deferred). Loaded by `renderDash()`.

### page-calendar — Training Calendar
Header: `‹ ›` month navigation, `Refresh`. Loaded by `renderCal()`.

### page-parade-nights — Parade Nights
Header: `Refresh`, `+ Add Parade Night` (admin-el), `Generate Parade Nights`
(admin-el), `Calendar`, `Weekly Program`. Loaded by `renderPN()`.

### page-weekly-program — Weekly Program
No header action buttons. Loaded by `renderWP()`.

### page-curriculum — Curriculum
Header: `Refresh`, `+ Add Squadron Curriculum` (sqn admin-el), `+ Add Wing
Curriculum` (wing/nat admin), `+ Add National Curriculum` (nat admin), `Import CSV`,
`Export XLSX`, `Export CSV`. Tabs: All / By Stage / Matrix (squadron scope only).

### page-activities — Activities
Header: `Refresh`, `+ Add Activity` (admin-el), `Generate Activities`
(plan-write-el), `+ Add Holiday` (plan-write-el).  
Filter bar: type selector (All / Must Attend / Key Event / Optional / Holiday),
date range, term, search.  
Section: squadron activity tab (`act-tab-squadron`).

> **USER-AUTHORISED CHANGE (2026-08-27, REM-146):** Class Forecasts card
> (`#py-forecasts-card`) added after Holiday Periods, above the inherited
> activities section. Visible to squadron scope only; hidden automatically by
> `_loadClassForecasts()` for wing/national roles, empty years, or 403 responses.
> Backend endpoint `/api/planning/class-forecasts` and renderer pre-existed —
> this adds the HTML mount point to expose them.
>
> **USER-AUTHORISED CHANGE (2026-08-27, Wing Events Overlay):** Wing HQ Events
> card (`#py-wing-events-card`) added after Class Forecasts. Shown for squadron
> accounts that have a `wing_id`; hidden when no wing is associated or the API
> returns no events. Renderer `_loadAndRenderWingEventsOverlay()`, backend endpoint
> `/api/wing-calendar/squadron-overlay`, and importance filter already existed —
> this adds the HTML mount point and wires the call into `_loadActivitiesPage()`.

> **Lock:** `Generate Activities` and `+ Add Holiday` must remain in `#page-activities`.
> Tests `[Activities] Title … required buttons present`, `[Activities] Holiday create`,
> and `[Activities] Generate Activities modal` assert their presence. Removing them
> breaks three test groups × 3 browsers = 9 Playwright failures.

### page-facilitators — Facilitators
Header: `Refresh`, `+ Add Facilitator` (admin-el). Loaded by `loadFacilitatorStats()`.

### page-resources — Resources & Training Areas
Header: `Refresh`, `+ Add Room` (admin-el), `+ Add Equipment` (admin-el).

### page-action-items — Needs Attention
Header: `Run checks`, `Refresh`. Loaded by `loadRecentChanges()`.

### page-help — Help & Reference
Cards: Getting Started (→ `nav('getting-started')` button), Getting Help (admin-editable
free text, `Edit` button for system_admin only). Loaded by `_loadHelpPage()`.

### page-settings — Unit Settings
No header buttons. Cards: Timing Templates, Training Classes (sqn_admin only,
managed by `_loadSettingsTrainingClasses()`), Access Code. Loaded by `renderSettings()`.

### page-accounts — Account Management
Header: `Refresh`, `+ Add Account` (admin-el). Flights card hidden (`display:none`
unconditionally — removed from pilot). Loaded by `renderAccounts()`.

### page-service-desk — Service Desk  *(added E.2, 2026-08-21)*
Roles: squadron (sqn_admin, sqn_general), wing_admin, national_admin, system_admin.
- `sqn_general`: submit-only view — pre-selected squadron, form to create ticket only.
- `sqn_admin`/`wing_admin`/`national_admin`/`system_admin`: full ticket list with filters (status, category, wing, squadron), detail panel, status PATCH.
- System Console section: email notification config per scope (system, national, per-wing). Loaded by `scLoadSdEmailConfig()`.
- Key actions: `Submit Ticket`, `Save` (email config per scope), status change dropdown in detail panel.
- Loaded by `loadServiceDesk()` (ticket page) and `scLoadSdEmailConfig()` (System Console email config).

### page-wing-overview — Wing Overview
Wing dashboard, command centre. Loaded by `renderWing()` + `loadCommandDashboard('wing')`.

### page-wing-activities — Wing Activities
Activity list for wing scope. Loaded by `_actTabLoad('act-tab-wing', 'wing', ...)`.

### page-wing-calendar — Wing HQ Calendar
Wing-level calendar. No header buttons.

### page-national — National Overview
National dashboard. Loaded by `renderNational()` + `loadCommandDashboard('national')`.

### page-national-activities — National Activities
Activity list for national scope.

### page-audit — Audit Log
Header: `Refresh`. Loaded by `renderAudit()`.

### page-system-console — System Console
Header: `Refresh`. Loaded by `loadSystemConsole()`. system_admin only.

### page-action-centre — Programme Action Centre
Present in HTML (not removed), but absent from `NAV_BY_SCOPE` — unreachable by normal
navigation. Content: open action items, upcoming nights needing attention, sign-off queue.

### page-program-audit — Program Audit
Present in HTML, absent from `NAV_BY_SCOPE` — unreachable by normal navigation.

---

## 4. Planning Workspace — external link behaviour

`bootApp()` (~line 4794) controls the PW nav section:

```javascript
const pwEligibleScope = ['squadron','wing','national','system_admin'].includes(scope);
const showPW = !!pwUrl && pwEligibleScope;
const showPWUnconfigured = !pwUrl && pwEligibleScope;
if (pwLink) pwLink.style.display = showPW ? 'flex' : 'none';
if (pwUnconfigured) pwUnconfigured.style.display = showPWUnconfigured ? 'flex' : 'none';
if (pwLbl) pwLbl.style.display = (showPW || showPWUnconfigured) ? 'block' : 'none';
```

`S.pwUrl` is populated from `/api/auth/me` → `planning_workspace_url`. In staging/production
this is set via `PLANNING_WORKSPACE_URL` Railway env var on the backend service.

Firefox ETP workaround (FF-01): the click listener on `nav-pw-link` opens a new tab with
`#t=<bearer_token>` in the URL fragment so the PW can authenticate cross-origin without
relying on `SameSite=None` cookies. The PW clears the fragment immediately on load.

---

## 5. Legacy route redirects in `nav()`

Old Planning Workspace sub-page IDs redirect to current pages:

| Old ID | Redirects to |
|---|---|
| planning-year, planning-anchors, planning-term, planning-missions | activities |
| planning-builder, planning-rooms | parade-nights |
| planning-guide, planning-longrange, planning-checks | dashboard |

---

## 6. What this document does NOT cover

- Backend API routes and database tables — see `docs/product-review/capability_manifest_current.json`
- Role × endpoint permissions — see `docs/release/final_role_and_scope_matrix.md`
- Visual design tokens — see `.claude/rules/frontend.md`
- Security invariants — see `.claude/rules/security.md` and `CLAUDE.md`
