# Information Architecture — AAFC TMS UI/UX Review

Audit date: 2026-08-06.

---

## User journey: access the system

```
User arrives at Main TMS (localhost:8080 / deployed URL)
  └── Login screen
        ├── Step 1 — Account Type: Squadron / Wing / National
        │     ├── Squadron → Select Wing → Select Squadron → Select Role (Admin/Viewer)
        │     ├── Wing → Select Wing → Select Role (Admin/Viewer)
        │     └── National → Select Role (National Admin/Viewer/System Admin/Auditor)
        └── Step 2 — Enter access code → Sign In → [app boots]
```

**Planning Workspace** (localhost:5173 / deployed /planning):
```
User arrives at PW
  └── Login screen: single "Access code" field → Log in → [app boots]
```

**Cross-app handoff**:
- Main TMS → PW: "Planning Workspace ↗" link in Main TMS nav (conditionally visible)
- PW → Main TMS: "← Main TMS" persistent link in PW sidebar (always visible)
- Session: both apps share the same `aafc_token` in sessionStorage; the cookie fallback handles cross-origin tab opening

---

## Scope hierarchy and nav assignment

```
Role → getScopeType() → effectiveScope() → NAV_BY_SCOPE[scope] → visible pages

sqn_admin     → squadron → squadron (no proxy) → 12 pages
sqn_general   → squadron → squadron             → 12 pages (accounts hidden)
wing_admin    → wing     → wing (no proxy)      → 7 pages
wing_viewer   → wing     → wing                 → 7 pages (accounts hidden)
national_admin → national → national            → 7 pages
national_viewer → national → national           → 7 pages (accounts hidden, audit 403)
system_admin  → system_admin → system_admin or  → 9 pages base + wing/sqn via sa-scope-bar
              (when browsing wing/sqn via sa-scope-bar: effective scope switches)
auditor       → auditor  → auditor              → 2 pages
```

---

## Nav structure — Main TMS

```
OVERVIEW
  Getting Started        (all scopes)
  Dashboard              (squadron)
  Calendar               (squadron)

TRAINING
  Parade Nights          (squadron)
  Weekly Program         (squadron)
  Curriculum             (all scopes)
  Activities             (squadron)
  Needs Attention        (squadron)

PEOPLE & RESOURCES
  Facilitators           (squadron)
  Locations and Resources (squadron)

ADMIN                    [shown only if role has admin capability]
  Unit Settings          (sqn_admin)
  Account Management     (sqn_admin, wing_admin, national_admin, system_admin, auditor)

COMMAND                  [wing/national/system_admin scope only]
  Wing Overview          (wing)
  Wing Activities        (wing + system_admin)
  Wing HQ Calendar       (wing + national + system_admin)
  National Overview      (national + system_admin)
  National Activities    (national + system_admin)
  Audit                  (wing, national, auditor, system_admin — NOT national_viewer)

SYSTEM                   [system_admin only]
  System Console

Planning Workspace ↗     [link — conditionally visible]
```

---

## Nav structure — Planning Workspace

```
OPERATIONS
  Planning Workspace     (active when /planning route)
  Dashboard
  Calendar
  Parade Nights
  Weekly Program
  Curriculum

CAPABILITY
  Facilitators
  Facilitator Schedule
  Resources
  Cadets

ASSURANCE
  Reports
  Report Catalogue
  Action Items
  Imports
  Audit

ADMIN
  Account Management
  Admin / Settings

ACCOUNT
  Access Codes

← Main TMS              (persistent cross-app link)
```

---

## Page-level information hierarchy

### Main TMS page layout

```
┌─────────────────────────────────────────────────────────────────────┐
│ HEADER: "AAFC · Training Management" / role breadcrumb  [Print][SQN][Sign Out] │
├─────────────────────────────────────────────────────────────────────┤
│ SCOPE BAR: [SQUADRON] 703 Admin                                      │
├──────────────┬──────────────────────────────────────────────────────┤
│              │ Page Title (bold, ~24px)  Subtitle (muted, ~13px)    │
│  LEFT NAV    │ ─────────────────────────────────────────────────────│
│  (205px)     │ Page content (cards / tables / forms)                │
│              │                                                       │
│              │                                                       │
├──────────────┴──────────────────────────────────────────────────────┤
│ DEBUG BAR (dev only): origin / api / role / scope / mode / health   │
└─────────────────────────────────────────────────────────────────────┘
```

**Issues**:
- No `<h1>` — page titles are `<div>`/`<span>` elements styled to look like headings
- No `<main>` or `<nav>` landmark regions
- Debug bar extends to bottom of every page in dev mode
- Mobile: LEFT NAV disappears with no replacement

### Planning Workspace page layout

```
┌─────────────────────────────────────────────────────────────────────┐
│ HEADER: "AAFC · Training Management System"  [Squadron][sqn_admin][Theme][Sign out] │
├──────────────┬──────────────────────────────────────────────────────┤
│              │ Page Title (h1, bold, ~28px)                         │
│  LEFT NAV    │ ─────────────────────────────────────────────────────│
│  (216px)     │ Page content                                         │
│              │                                                       │
├──────────────┴──────────────────────────────────────────────────────┤
└─────────────────────────────────────────────────────────────────────┘
```

**Better**:
- PW uses semantic `<h1>` for page titles
- PW has a Theme toggle (light/dark)
- PW has no debug bar
- Mobile: sidebar collapses (same nav-missing issue) but content adapts better

---

## IA gaps identified

| Gap | Type | Impact |
|---|---|---|
| Mobile nav absent (both apps) | Structural | All mobile users cannot navigate |
| `national_viewer` → Audit 403 | Permission | Role can reach page but gets denied |
| Login multi-step (Main TMS) vs single (PW) | Consistency | User confusion when switching apps |
| "Planning Workspace" link conditionally visible | Discoverability | Users may not find cross-app entry |
| No `<h1>` / landmark regions (Main TMS) | Semantic / A11y | Screen readers cannot navigate by heading/landmark |
| Settings vs Admin / Settings naming | Consistency | "Unit Settings" (Main TMS) vs "Admin / Settings" (PW) for same concept |
| "Needs Attention" vs "Action Items" naming | Consistency | Same concept labelled differently in each app |
