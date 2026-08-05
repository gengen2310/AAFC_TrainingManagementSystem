# UX Findings — AAFC TMS UI/UX Review

Audit date: 2026-08-06. Evidence: Playwright screenshots + source inspection.
Priority: P0=blocker, P1=high, P2=medium, P3=low/cosmetic.

---

## Navigation

### F-NAV-01 · P0 · Main TMS mobile navigation completely absent

**Finding**: At 390px viewport, the Main TMS sidebar disappears entirely. No hamburger button, no bottom tab bar, no slide-out drawer, no alternative navigation. Users are stranded on whichever page they loaded with no way to reach any other page.

**Evidence**: `sqn_admin_mobile_390_landing.png` — header visible, content visible, sidebar not rendered, no nav toggle control.

**Scope**: All roles, all pages, Main TMS only.

**Source**: `connected-frontend/index.html` — the sidebar `<div id="nav">` uses CSS that hides at small breakpoints but no mobile alternative is provided.

**Severity**: Functional blocker for mobile users. The app is unusable on phones without navigation.

---

### F-NAV-02 · P1 · Login flow asymmetry between the two frontends

**Finding**: Main TMS login is a 5-step multi-step form (Account Type → Wing → Squadron → Role → Access Code). Planning Workspace login is a single "Access code" field. Users who need to access both apps encounter two radically different login experiences, with no explanation of why they differ.

**Evidence**: `screenshots/main-tms/login_desktop_1440.png` vs `screenshots/planning-workspace/login_desktop_1440.png`.

**Notes**: The multi-step approach in Main TMS resolves the user_id before the code is entered (scoped brute-force defence). The single-field PW approach scans all access codes. Both are intentional security designs, but users see only the surface difference.

---

### F-NAV-03 · P2 · Cross-app navigation is asymmetric

**Finding**: Planning Workspace has a persistent "← Main TMS" link at the bottom of the sidebar. Main TMS has a "Planning Workspace ↗" link but it is conditionally shown and only appears for roles/scopes that have PW access. A sqn_admin in Main TMS may not immediately find how to reach the PW.

**Evidence**: `sqn_admin_desktop_1440_dashboard.png` (Main TMS) — no prominent "Open Planning Workspace" action visible above the fold on first load.

---

### F-NAV-04 · P3 · "Sign Out" capitalisation inconsistency

**Finding**: Main TMS uses "Sign Out" (both words capitalised). Planning Workspace uses "Sign out" (sentence case). Minor inconsistency; the AAFC style guide preference is unknown.

---

## Permission / data accuracy

### F-FUNC-01 · P1 · national_viewer shown Audit nav link but gets 403

**Finding**: The frontend includes "audit" in the `national` NAV_BY_SCOPE set. `national_viewer` has the `national` scope. When a `national_viewer` navigates to the Audit page, the backend returns 403 because `_AUDIT_READ_ROLES` (in `organisations.py:620`) does not include `national_viewer`.

**Evidence**: `capture_report.json` — `national_viewer` has 2× `/api/audit` → 403 network errors and 2× console errors. `national_viewer_desktop_1440_audit.png` — page renders without data.

**Root cause**: `NAV_BY_SCOPE.national` includes `'audit'` but `_AUDIT_READ_ROLES` = `{"auditor", "sqn_admin", "wing_admin", "national_admin", "system_admin"}`.

**Fix options**: (A) Add `national_viewer` to `_AUDIT_READ_ROLES` — grants read access. (B) Remove `audit` from `NAV_BY_SCOPE.national` and add a separate `national_admin` scope entry — hides the link from viewers.

---

## Content / data presentation

### F-CONT-01 · P1 · Wing Overview readiness table is extremely dense

**Finding**: The Wing Overview page (wing_admin/national_admin scope) renders a multi-squadron readiness table where each row is a squadron and columns include Sessions Planned, Curriculum, Facilitator, Facility, Equipment, Overall, Trend. At 1440px the text is very small and the table is difficult to read. At 390px mobile (no nav), the table is completely unusable.

**Evidence**: `wing_admin_desktop_1440_wing-overview.png` — table renders at ~10px effective font size in the data cells.

---

### F-CONT-02 · P2 · `__APP_BUILD__` placeholder not resolved in System Console

**Finding**: System Console Build Information section shows `Commit: __APP_BUILD__`. The `RUN_TMS_CONNECTED_FRONTEND_MAC.sh` script is meant to substitute this placeholder with the actual commit SHA, but it was not replaced in the local dev session.

**Evidence**: `system_admin_desktop_1440_system-console.png`.

**Note**: The `aafc-api-base` meta tag WAS correctly set (`http://localhost:8000`), so the script ran partially. The `app-build` tag substitution appears to have been skipped.

---

### F-CONT-03 · P2 · Weekly Program empty state lacks guidance

**Finding**: The Weekly Program page shows only a dropdown ("— Choose a parade night —") with no other content. There is no explanation of what the Weekly Program is, why no parade night is pre-selected, or what to expect after selection. New users may find this confusing.

**Evidence**: `sqn_admin_desktop_1440_weekly-program.png`.

---

### F-CONT-04 · P2 · Calendar has no events in current period

**Finding**: The Training Calendar for August 2026 shows a completely empty grid. The fresh local SQLite database has parade nights in earlier terms (Jan–May 2026) but none in the current month. A new user seeing an empty calendar with no explanation may think the feature is broken.

**Evidence**: `sqn_admin_desktop_1440_calendar.png`.

**Note**: This is a data/demo-data issue, not a functional bug. The calendar correctly shows zero events when no events exist in the current month.

---

### F-CONT-05 · P3 · Debug bar exposed on all Main TMS pages

**Finding**: Every Main TMS page shows a dark debug bar at the bottom: `origin http://localhost:8080 api http://localhost:8000 role sqn_admin scope squadron mode none health http://localhost:8000/api/health`. This is intentional in dev/pilot mode but must be verified hidden in production builds (or explicitly documented as intended).

**Evidence**: All `main-tms/sqn_admin_*.png` screenshots.

---

## Design consistency

### F-DS-01 · P2 · Active nav treatment differs between Main TMS and Planning Workspace

**Finding**: In Main TMS, the active nav item has a `3px solid var(--blue)` left border + blue text + `#deeefa` background. In Planning Workspace, the active item has a dark navy filled background with white text. Both use the same brand palette but the interaction metaphor is different (border indicator vs filled block).

**Evidence**: Compare `sqn_admin_desktop_1440_dashboard.png` (Main TMS) vs `sqn_admin_desktop_1440_dashboard.png` (PW).

---

### F-DS-02 · P2 · Nav category label styling differs

**Finding**: Main TMS uses all-caps category labels in the sidebar (OVERVIEW, TRAINING, PEOPLE & RESOURCES, ADMIN). Planning Workspace also uses all-caps (OPERATIONS, CAPABILITY, ASSURANCE, ADMIN, ACCOUNT). Conventions are similar but category names differ — same section may be called "TRAINING" in Main TMS and "OPERATIONS" or "CAPABILITY" in PW.

---

### F-DS-03 · P3 · Button rounding inconsistency

**Finding**: Main TMS buttons have `border-radius: 8px`. Planning Workspace buttons appear slightly rounder (`border-radius: 10px` or more). Minor visual inconsistency across the two apps.

---

## Mobile experience summary

| Viewport | Main TMS | Planning Workspace |
|---|---|---|
| 390px nav | BROKEN — no hamburger, no mobile nav | Sidebar collapses, no hamburger (same pattern) |
| 390px header | Wraps to 3 lines, OK | Wraps to 4 lines with badges, OK |
| 390px content | Content readable, limited scrolling | Content readable, responsive columns |
| 390px data tables | Horizontal overflow, cells clipped | Tables scroll horizontally |
| Overall | Unusable (no nav) | Marginal (content works, nav missing) |
