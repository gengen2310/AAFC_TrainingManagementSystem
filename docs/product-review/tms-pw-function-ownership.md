# TMS ↔ Planning Workspace — Function Ownership Matrix

**Branch:** main  
**HEAD SHA:** 6d45e22  
**Date recorded:** 2026-08-28  

Core principle from the integration brief:
> ONE TRAINING MANAGEMENT SYSTEM + ONE CANONICAL DATA MODEL + TWO COMPLEMENTARY WORKING SURFACES.

The question for each function is not "which app owns it" but "which surface is the
correct home for each *working mode*". Read-heavy setup belongs in TMS. Real-time
planning decisions belong in PW. Data created in either surface must be visible in both.

---

## Legend

| Symbol | Meaning |
|---|---|
| ✅ | Current home — correct |
| 🔄 | Exists here but duplicates; target for removal or redirect |
| ❌ | Missing — should exist here |
| ⚠️ | Exists here but needs redesign |

---

## Setup & Configuration (run once per year)

| Function | TMS | PW | Correct home | Brief §|
|---|---|---|---|---|
| Create / archive Training Year | ✅ | 🔄 (via /admin) | TMS | §13 |
| Create / manage Training Classes | ✅ | 🔄 (via /admin) | TMS | §14 |
| Assign Training Stage to Training Class | ⚠️ optional at HEAD | ❌ | TMS (enforced) | §15–16 |
| Define Parade Night Structure (timing blocks) | ⚠️ three separate cards | ❌ not shown | TMS (one merged card) | §8–12 |
| Create / manage Timing Templates | ✅ | ❌ not editable | TMS (create/edit); PW (read-only view) | §19–20 |
| Configure parade dates / calendar | ✅ | ✅ | Both (same data) | §13 |
| Configure Holiday Periods | ✅ | 🔄 | TMS | — |
| Manage Training Areas & capabilities | ✅ | ⚠️ shows area but not capabilities | TMS (edit); PW (read + filter) | §21–25 |
| Manage Curriculum Phases (Training Stages) | ✅ | 🔄 | TMS | §15 |
| Getting Started checklist | ✅ | ❌ | TMS | §7 |
| Custom Training Phase / Group | ⚠️ minimal model | ❌ | TMS (define); PW (surface in context) | §17–18 |

---

## Session & Program Planning (ongoing throughout year)

| Function | TMS | PW | Correct home | Brief §|
|---|---|---|---|---|
| View / navigate parade night schedule | ✅ | ✅ | Both | — |
| Schedule sessions on a parade night | ✅ | ✅ | Both (same backend) | — |
| Assign facilitator to session | ✅ | ✅ | Both | §35–40 |
| Assign training area to session | ✅ | ❌ not surfaced in PW | Both | §21–25 |
| Set session audience (TrainingClass) | ✅ | ❌ | Both | — |
| View Timing Template overlay on parade night | ❌ | ❌ | PW (planning canvas) | §19–20 |
| Change timing template for individual parade night | ❌ | ❌ | PW | §19–20 |
| Mission Backlog (unscheduled program items) | ❌ | ⚠️ bottom drawer only | PW (dedicated view) | §35–40 |
| Drag-to-schedule from backlog | ❌ | ⚠️ partial | PW | §35–40 |
| Activities log | ✅ | 🔄 (/activities) | TMS | §35 |
| Facilitator roster management | ✅ | 🔄 (/facilitators) | TMS (manage); PW (read for scheduling) | §37–40 |

---

## Review & Publishing

| Function | TMS | PW | Correct home | Brief §|
|---|---|---|---|---|
| Planning Checks (auto quality checks) | ⚠️ manual trigger, boolean only | ❌ | Both surfaces see results | §26–34 |
| Decision Guide (pre-planning questions) | ⚠️ boolean ✅/🔴 | ❌ | Replace with Plan Review | §26–34 |
| Plan Review (outcome statements: READY / WARNINGS / NOT READY / NOT ENOUGH INFO) | ❌ | ❌ | Auto-triggered, both surfaces | §26–34 |
| Publish Readiness | ❌ (conflated with checks) | ❌ | Separate explicit concept, PW primary | §31–34 |

---

## Curriculum & Program

| Function | TMS | PW | Correct home | Brief §|
|---|---|---|---|---|
| Browse Cadet Program items | ✅ | 🔄 (/curriculum) | TMS | §43 |
| View program coverage | ✅ | 🔄 (/reports) | TMS | §43 |
| Schedule program items (session planning) | ✅ | ✅ (via backlog) | Both | §35 |
| Learning Hub links | ✅ | ❌ | TMS | — |
| Program promotion (sqn → wing → national) | ✅ | ❌ | TMS | — |

---

## Accounts & Access

| Function | TMS | PW | Correct home | Brief §|
|---|---|---|---|---|
| Account management | ✅ | 🔄 (/accounts) | TMS | §43 |
| Access code management | ✅ | 🔄 | TMS | §43 |
| Role / scope administration | ✅ | 🔄 (/admin) | TMS | §43 |

---

## Reporting & Audit

| Function | TMS | PW | Correct home | Brief §|
|---|---|---|---|---|
| Audit log | ✅ | 🔄 (/audit) | TMS | §43 |
| Reports / report catalogue | ✅ | 🔄 (/reports, /report-catalogue) | TMS | §43 |
| Cadet roster | ✅ | 🔄 (/cadets) | TMS | §43 |
| Imports | ✅ | 🔄 (/imports) | TMS | §43 |

---

## Navigation & Context

| Function | TMS | PW | Correct home | Brief §|
|---|---|---|---|---|
| Open PW from TMS (context-preserving) | ⚠️ passes token+year only | — | TMS → PW with year + squadron | §42 |
| Return from PW to TMS (context-preserving) | — | ❌ no back link | PW → TMS same page | §42 |
| Year selector in PW | ❌ (year comes from hash) | ⚠️ implied but not explicit | PW must show active year; no re-selection needed if context passed | §13 |
| Training Class selector in PW | ❌ | ❌ | PW must reflect TMS-defined classes without re-entry | §14 |

---

## Summary: PW routes to audit (Section 43)

These PW routes duplicate TMS with no planning-specific value. Each should be audited for
removal or redirection:

| PW Route | Duplicates | Disposition |
|---|---|---|
| `/dashboard` | TMS dashboard | Audit → redirect or remove |
| `/curriculum` | TMS curriculum | Redirect to TMS |
| `/facilitators` | TMS facilitators | Keep read-only roster for scheduling context; remove management actions |
| `/resources` | TMS resources | Keep for area availability view; surface capabilities |
| `/cadets` | TMS cadet roster | Redirect to TMS |
| `/reports` | TMS reports | Redirect to TMS |
| `/report-catalogue` | TMS reports | Redirect to TMS |
| `/action-items` | TMS action items | Redirect to TMS |
| `/imports` | TMS imports | Redirect to TMS |
| `/audit` | TMS audit | Redirect to TMS |
| `/admin` | TMS settings | Redirect to TMS |
| `/accounts` | TMS accounts | Redirect to TMS |
| `/settings` | TMS settings | Redirect to TMS |
| `/wing-overview` | TMS wing-overview | Redirect to TMS |
| `/national-overview` | TMS national | Redirect to TMS |

Routes that should stay in PW:
- `/planning` — planning canvas (primary PW surface)
- `/calendar` — planning calendar view
- `/parade-nights` — PW parade night list (planning context)
- `/weekly-program` — planning weekly view
- `/facilitator-schedule` — scheduling-specific view, no TMS equivalent

---

*Update this matrix as each section of the integration brief is completed.*  
*See also: `tms-pw-current-state.md` for model/route inventory.*
