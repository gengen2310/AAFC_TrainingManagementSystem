# AAFC TMS — Frontend Duplication Register

**Review:** Post-Gap Human Workflow, Architecture and Design Review — Stage 2 (Superpowers)  
**Date:** 2026-08-16  
**Scope:** All pages and features present in both Main TMS (connected-frontend) and Planning Workspace (frontend/); assess whether duplication is intentional, divergent, or problematic  
**Method:** Analysis only — no changes

---

## Classification

- **P — Parallel (intentional):** The same concept is present in both frontends because both frontends are full-featured apps sharing the same backend. Expected. No action needed.
- **D — Divergent (concern):** The same page exists in both frontends but has meaningfully different content, features, or data access. Users may get different information depending on which frontend they use.
- **G — Gap (Main TMS missing feature from PW):** PW has a feature that Main TMS does not, which may leave operational users unable to access it.
- **G2 — Gap (PW missing feature from Main TMS):** Main TMS has a feature PW does not.

---

## Section 1: Pages present in both frontends

### Dashboard

| Dimension | Main TMS | Planning Workspace | Classification |
|---|---|---|---|
| **Section A — Tonight & Next Nights** | ✓ | ✓ | P |
| **Delivery analytics (Section B)** | ✓ (bar charts, trend) | ✓ (key stats only) | D — PW has fewer charts |
| **Curriculum progress (Section C)** | ✓ | ✓ | P |
| **Staffing resilience (Section D)** | ✓ (deferred, button) | ✓ (integrated) | D — different access pattern |
| **Cadet risk summary** | ✗ | ✓ | G — Main TMS missing |
| **Squadron/Wing comparison** | ✓ (wing scope) | ✓ (wing scope) | P |
| **Period selector** | ✓ (week/term/year) | ✓ | P |
| **Drill-down panel** | ✓ (click bar) | ✓ | P |
| **Training decision badge** | ✗ | ✓ | G — Main TMS missing |

**Finding:** The PW Dashboard has two features Main TMS lacks: the cadet risk summary and the training decision badge. A Training Officer using only Main TMS misses these signals.

---

### Calendar

| Dimension | Main TMS | Planning Workspace | Classification |
|---|---|---|---|
| **Monthly calendar grid** | ✓ | ✓ | P |
| **Click date → parade night detail** | Partial (click label, not cell) | ✓ (modal) | D — PW provides richer click behaviour |
| **Year navigation** | Hardcoded 2025/2026/2027 | Dynamic | D — Main TMS limited |
| **Status colour legend** | ✓ | ✓ | P |

---

### Parade Nights

| Dimension | Main TMS | Planning Workspace | Classification |
|---|---|---|---|
| **List with filter/search** | ✓ | ✓ | P |
| **Parade Night detail (expand)** | ✓ | ✓ (modal) | P |
| **Add parade night** | ✓ (write roles) | ✓ (write roles) | P |
| **Session quick edit** | ✓ (Quick Edit modal) | ✓ (right drawer) | D — different UI pattern |
| **Guided session entry** | ✓ | ✗ | G2 — PW missing guided entry |
| **Save as template / apply template** | ✓ | ✗ | G2 — PW missing template management |
| **Generate parade nights** | ✓ (header button) | ✗ | G2 — PW missing |
| **Copy sessions to another night** | ✓ | ✗ | G2 — PW missing |
| **Bulk cancel sessions** | ✓ | ✗ | G2 — PW missing |
| **Facilitator suggestions** | ✓ (Quick Edit) | ✓ (right drawer) | P |
| **Resource clash indicator** | ✗ | ✓ (conflict panel) | G — Main TMS missing live conflict display |

**Key finding:** Session management is richer in Main TMS (templates, guided entry, bulk operations). Conflict awareness is richer in PW (live conflict panel). A Training Officer who plans in PW and manages operations in Main TMS may not see conflict indicators when they need them in operational context.

---

### Weekly Program

| Dimension | Main TMS | Planning Workspace | Classification |
|---|---|---|---|
| **Printable session table** | ✓ | ✓ | P |
| **Footer disclaimer** | ✗ | ✓ ("planning document only — not a system of record") | D — PW correctly disclaims the document |
| **Session filter** | ✓ | ✗ | G2 — PW missing filter |

---

### Curriculum

| Dimension | Main TMS | Planning Workspace | Classification |
|---|---|---|---|
| **Items list with phase tabs** | ✓ | ✓ | P |
| **Phase/element/progress filters** | ✓ | ✓ | P |
| **Matrix view** | ✓ | ✗ | G2 — PW curriculum is read-only, no matrix |
| **Add/edit curriculum** | ✓ (admin) | ✗ | G2 — PW is read-only for curriculum |
| **Import CSV/XLSM** | ✓ (admin) | ✗ | G2 — imports in PW are under /imports route |
| **Export XLSX/CSV** | ✓ | ✗ | G2 — PW missing curriculum export |
| **Learning Hub link** | ✓ | ✓ | P |
| **Session history drill-down** | ✓ | ✓ | P |

---

### Facilitators

| Dimension | Main TMS | Planning Workspace | Classification |
|---|---|---|---|
| **Facilitators table** | ✓ | ✓ | P |
| **Analytics charts (workload, coverage)** | ✓ | ✓ (different format) | D — both have charts, different presentation |
| **Add facilitator** | ✓ | ✓ | P |
| **Edit / archive** | ✓ | ✓ | P |
| **Stats drill-down** | ✓ | ✓ | P |
| **Import CSV** | ✓ | ✓ | P |
| **Facilitator schedule timeline** | ✗ | ✓ (/facilitator-schedule route) | G — Main TMS has no timeline view |
| **Leave management** | ✗ | ✓ (bottom drawer Facilitators tab) | G — Main TMS missing leave management |
| **Absorb (merge) facilitators** | ✓ | ✗ | G2 — PW missing facilitator merge |

**Finding:** The facilitator schedule timeline and leave management exist only in PW. A Training Officer who does not use PW cannot manage facilitator leave from Main TMS.

---

### Resources (Rooms and Equipment)

| Dimension | Main TMS | Planning Workspace | Classification |
|---|---|---|---|
| **Rooms list** | ✓ | ✓ (/resources + bottom drawer) | P |
| **Equipment list** | ✓ | ✓ (/resources + bottom drawer) | P |
| **Add room/equipment** | ✓ | ✓ | P |
| **Resource clash checker** | ✗ | ✓ | G — Main TMS missing clash checker |

---

### Needs Attention / Action Items

| Dimension | Main TMS | Planning Workspace | Classification |
|---|---|---|---|
| **P0-P4 exception items** | ✓ | ✓ | P |
| **P5 backlog items** | ✓ (mixed in) | ✓ (mixed in) | P |
| **Manual action item creation** | ✗ | ✓ (with Title, Owner, Due, Severity) | G — Main TMS missing manual item creation |
| **Close action item** | ✗ | ✓ | G — Main TMS missing close button |
| **What Changed? feed** | ✓ | ✗ | G2 — PW missing What Changed? |
| **Run exception checks** | ✓ | ✓ | P |

**Finding:** PW's Action Items page is richer (manual creation, close). Main TMS's Needs Attention page has "What Changed?" which PW lacks. These complement each other rather than duplicate.

---

### Audit Log

| Dimension | Main TMS | Planning Workspace | Classification |
|---|---|---|---|
| **Audit table** | ✓ | ✓ | P |
| **Filters (object type/ID/limit)** | ✓ (basic) | ✓ (object type, object ID, limit) | P |
| **Proxy indicator column** | ✓ | ✓ | P |
| **Role filter** | ✗ | ✗ | Missing in both |
| **Action filter** | ✗ | ✗ | Missing in both |
| **Date range filter** | ✗ | ✗ | Missing in both |

---

### Account Management

| Dimension | Main TMS | Planning Workspace | Classification |
|---|---|---|---|
| **Users table** | ✓ | ✓ | P |
| **Add/edit/disable/archive user** | ✓ | ✓ | P |
| **Reset access code** | ✓ | ✓ | P |
| **Flights management** | ✓ | ✓ | P |
| **Reference Data** | ✓ | ✓ | P |
| **Wings management** | ✓ (national scope) | ✓ | P |
| **Squadrons management** | ✓ (wing/national) | ✓ | P |
| **Batch archive** | ✗ | ✗ | Missing in both (API exists) |

---

### Wing Overview / Wing Assurance

| Dimension | Main TMS | Planning Workspace | Classification |
|---|---|---|---|
| **Squadron comparison tables** | ✓ | ✓ | P |
| **Command Dashboard (Sections A+B)** | ✓ | ✓ | P |
| **Phase coverage heatmap** | ✗ | ✓ | G — Main TMS missing heatmap |
| **Subject area coverage heatmap** | ✗ | ✓ | G — Main TMS missing heatmap |
| **Squadrons needing Wing support** | ✗ | ✓ | G — Main TMS missing |
| **Squadron risk scoring** | ✗ | ✓ | G — Main TMS missing |

**Finding:** PW's Wing Assurance is significantly richer than Main TMS's Wing Overview. A wing_admin who primarily uses Main TMS is missing the heatmaps and risk scoring.

---

### National Overview / National Assurance

| Dimension | Main TMS | Planning Workspace | Classification |
|---|---|---|---|
| **Wing comparison tables** | ✓ | ✓ | P |
| **Delivery / Capability view toggle** | ✗ | ✓ | G — Main TMS missing capability view |
| **Facilitator coverage gap heatmap** | ✗ | ✓ | G — Main TMS missing |
| **Session subject distribution** | ✗ | ✓ | G — Main TMS missing |

---

## Section 2: Pages only in Main TMS (G2 gaps in PW)

| Page | Content | Why PW doesn't have it |
|---|---|---|
| Activities (AAFC events + planning year) | Events, year setup, classes, dates | PW bottom drawer has Activities tab; year setup is PW-native |
| Wing HQ Calendar | Wing-level event calendar with grid/table view | PW has no equivalent wing calendar management |
| System Console | system_admin platform management | Not needed in PW — admin-only feature |
| Getting Started | Setup checklist | PW has guided setup wizard (GuidedYearSetupModal) — different approach |

---

## Section 3: Pages only in PW (G gaps in Main TMS)

| Page | Content | Impact |
|---|---|---|
| Planning Workspace canvas | The main PW planning tool | Not applicable — PW-native |
| Facilitator Schedule | Timeline view with leave overlay | Training Officers using Main TMS cannot see facilitator timeline |
| Cadets | Cadet roll, risk flags, class membership | Training Officers using Main TMS cannot see cadet risk |
| Imports | Generic bulk import with preview/rollback | Main TMS imports are feature-specific (curriculum, facilitators) |
| Reports | 17-type training report set | Main TMS has no equivalent reports page |
| Report Catalogue | Report coverage tracking | Internal tool — low impact |
| Unit Settings (PW) | Read-only scope view, no edit | Main TMS Unit Settings is the editable primary |

---

## Section 4: Code/pattern duplication within Main TMS

The connected-frontend is a single file. Within it:

### DUP-01: Modal patterns repeated

Every entity (Facilitators, Rooms, Equipment, Activities, Training Classes, etc.) has an "Add" modal and an "Edit" modal. Each is a custom HTML form with its own:
- Field definitions
- Validation logic
- Submit handler
- Success/error messaging

These follow a consistent pattern but are not abstracted into a reusable component. This is expected in a no-build-step single-file SPA — there is no component system. The duplication is visible but structural, not functional.

**Impact:** Adding a new entity type requires copying an existing modal and adapting it. Error-prone but manageable at current scale.

### DUP-02: Chart rendering repeated

Dashboard charts (delivery analytics, curriculum progress, etc.) and the Facilitators charts are both implemented as custom canvas or SVG rendering. The chart patterns are similar but not shared (no chart library abstraction).

**Impact:** Adding a new chart type requires writing new canvas/SVG code from scratch.

### DUP-03: Table/filter patterns repeated

Parade Nights, Facilitators, Curriculum, Activities, Account Management — all use similar table + filter patterns. Each is a custom implementation.

**Impact:** If the table pattern needs updating (e.g., add keyboard navigation), it must be updated in every table independently.

---

## Section 5: Code/pattern duplication within PW (frontend/)

The React PW app uses component patterns but may have its own duplication:

### DUP-04: Dual state management patterns

The PW uses React state + custom hooks. The planning canvas has complex state (view range, selected year, selected date, open drawers, conflict state, backlog filters). This is likely well-managed with hooks, but:

- If multiple components independently fetch `GET /api/planning/years` (for example), there may be redundant API calls
- The large command-centre data fetch likely caches at the PW app level

**Impact:** Without seeing the full hook implementation, this is a potential but unconfirmed duplication. Low risk.

### DUP-05: PW replicates Main TMS operational pages

Dashboard, Calendar, Parade Nights, Weekly Program, Curriculum, Facilitators, Resources, Action Items, Account Management, Audit — all exist in PW's AppShell as full routes. This is a significant code investment in PW to replicate functionality that already exists in Main TMS.

**Reason for duplication:** PW runs in full-app mode for wing/national users who need to browse squadron data without leaving the PW environment. It is not a redundant reimplementation — it serves a different context (planning context vs operational context).

**Assessment:** Intentional. The cost is maintenance: any fix to a page in Main TMS must also be evaluated for the PW equivalent.

---

## Section 6: Summary

### Gap inventory (Main TMS missing PW features)

| Feature | In PW | In Main TMS | Impact |
|---|---|---|---|
| Cadet risk summary | ✓ | ✗ | Moderate |
| Training decision badge | ✓ | ✗ | Moderate |
| Resource clash live indicator | ✓ | ✗ | Moderate |
| Manual action item creation | ✓ | ✗ | Low |
| Close action item | ✓ | ✗ | Low |
| Facilitator schedule timeline | ✓ | ✗ | Moderate |
| Facilitator leave management | ✓ | ✗ | Moderate |
| Wing phase/subject heatmaps | ✓ | ✗ | Low (wing users) |
| National capability view | ✓ | ✗ | Low (national users) |
| Rich calendar cell click | ✓ | ✗ | Low |
| Reports page | ✓ | ✗ | Low |
| Footer disclaimer on Weekly Program | ✓ | ✗ | Very low |

### Gap inventory (PW missing Main TMS features)

| Feature | In Main TMS | In PW | Impact |
|---|---|---|---|
| Guided session entry | ✓ | ✗ | Low (expert users use PW) |
| Session template management | ✓ | ✗ | Low |
| Copy sessions to another night | ✓ | ✗ | Low |
| Bulk cancel sessions | ✓ | ✗ | Low |
| Facilitator absorb (merge) | ✓ | ✗ | Low |
| What Changed? feed | ✓ | ✗ | Low |
| Curriculum export | ✓ | ✗ | Low |
| Wing HQ Calendar management | ✓ | ✗ | Low (wing+ only) |

### Divergent implementations (same page, different content/behaviour)

| Page | Key divergence |
|---|---|
| Dashboard | PW has cadet risk + decision badge; Main TMS has deferred resilience charts |
| Calendar | Main TMS hardcoded years; PW dynamic |
| Parade Nights | Main TMS: templates, guided entry, bulk; PW: conflict display, richer session drawer |
| Weekly Program | PW has disclaimer; Main TMS has session filter |
| Facilitators | Different chart layouts; PW adds schedule/leave |
| Wing Overview | PW significantly richer with heatmaps and risk scores |

**Overall assessment:** The duplication is principally intentional (two-frontend architecture). The divergences indicate that PW has received more recent feature investment (richer analytics, conflict display, cadet risk). Main TMS retains operational advantages (templates, guided entry, bulk actions). Neither frontend is complete on its own — they are genuinely complementary. The key design risk is that users who use only one frontend miss features available in the other.

