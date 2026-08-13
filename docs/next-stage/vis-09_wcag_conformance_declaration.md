# WCAG 2.1 AA Conformance Declaration — AAFC TMS

**Status:** Partial conformance  
**Target:** WCAG 2.1 Level AA  
**Assessed:** 2026-08-13  
**Assessed by:** Development team (automated + structural review)  
**Evidence:** `docs/release/final_accessibility_assessment.md`

---

## Summary

AAFC TMS partially conforms to WCAG 2.1 Level AA. The Planning Workspace frontend passes automated axe-core scanning with zero critical or serious violations across all 19 covered pages. The connected frontend (Main TMS) passes automated colour-contrast and critical-control checks, but has known moderate structural gaps that are not yet resolved.

A full external audit with screen-reader testing has not been conducted. This declaration reflects automated and structural assessment only.

---

## Evidence

### Planning Workspace (`frontend/` — Planning Workspace at `/planning`)

| Check | Method | Result |
|---|---|---|
| axe-core automated scan | Playwright E2E (`e2e/accessibility.spec.ts`, 19 pages) | PASS — zero critical/serious/moderate violations |
| Colour contrast | axe-core | PASS |
| Keyboard focus visible | axe-core + structural review | PASS |
| Form labels | axe-core | PASS |
| Image alt text | axe-core | PASS |
| High-contrast media query (`prefers-contrast: more`) | Code inspection | PASS — token overrides implemented in `tokens.css` |
| Windows High Contrast Mode (`forced-colors: active`) | Code inspection | PASS — forced-color-adjust overrides present |

**Conclusion:** Planning Workspace — Level AA, no known automated violations.

### Connected Frontend (`connected-frontend/` — Main TMS at `/`)

| Check | Method | Result |
|---|---|---|
| Colour contrast (all critical text paths) | axe-core live scan (18 page-scans, local authenticated) | PASS — fixed in `ca785b4`, deployed in production `756e65e` |
| `select-name` on Curriculum filters | axe-core live scan | PASS — fixed (`aria-label` added) |
| `page-has-heading-one` | axe-core | **FAIL** — no `<h1>` element anywhere; headings are styled `<div>`/`<span>` |
| `region` landmark structure | axe-core | **FAIL** — 6 non-landmark elements per page |
| `select-name` (other form controls) | axe-core structural estimate | **PARTIAL** — approximately 85 `<select>` elements lack an accessible name; 2 fixed; remainder not yet addressed |
| High-contrast media query (`prefers-contrast: more`) | Code inspection | PASS — implemented after initial assessment |
| Windows High Contrast Mode | Code inspection | PASS — implemented after initial assessment |
| Keyboard-only navigation | Manual tracing | **NOT COMPLETED** — documented as remaining work (VIS-04) |
| Screen-reader testing | Manual / VoiceOver | **NOT COMPLETED** — automated axe-core substituted per assessment methodology |

**Conclusion:** Connected Frontend — partially conformant. Three categories of known gaps remain.

---

## Known Failures and Exceptions

### 1. Heading structure (`page-has-heading-one`, `<h1>`)

**WCAG criterion:** 1.3.1 Info and Relationships (Level A), 2.4.6 Headings and Labels (Level AA)  
**Impact:** Moderate  
**Scope:** All pages in connected-frontend  
**Description:** The single-file SPA uses styled `<div>` elements as visible headings rather than semantic `<h1>`–`<h6>` elements. Screen-reader users cannot use heading navigation to jump to page sections.  
**Remediation plan:** Introduce semantic heading structure across the SPA. This is a whole-file structural change; planned as part of the Phase 7 UX redesign.

### 2. Landmark regions

**WCAG criterion:** 1.3.6 Identify Purpose (Level AAA, informational; but `region` failures affect practical SR use), best practice  
**Impact:** Moderate  
**Scope:** Connected frontend, 6 elements per page  
**Description:** Floating UI elements (toast notifications, modals) are not contained within `<main>`, `<nav>`, or other landmark regions.  
**Remediation plan:** Refactor layout to wrap all content within appropriate landmarks. Planned with heading structure fix above.

### 3. Select elements without accessible names (~83 remaining)

**WCAG criterion:** 1.3.1 Info and Relationships, 4.1.2 Name, Role, Value (Level A)  
**Impact:** Serious (screen-reader users cannot determine what a dropdown controls)  
**Scope:** Connected frontend — dynamically generated row controls (`<select>` in table rows, filter bars, and parade-night builder forms)  
**Description:** Approximately 83 `<select>` elements lack an associated `<label for>`, `aria-label`, or `aria-labelledby`. These include template-generated controls where one pattern produces many rendered instances.  
**Remediation plan:** Systematic aria-label addition pass, starting with highest-frequency controls (parade night builder, session editor, curriculum filters). In progress under VIS-04.

---

## Acceptance Criteria for Full AA Declaration

A full WCAG 2.1 AA declaration requires all three of the following:

1. Connected frontend heading and landmark structure refactored (gap 1 and 2 above resolved)
2. All `<select>` elements with meaningful function have an accessible name (gap 3 resolved)
3. Keyboard-only workflow pass completed for all 12 high-frequency workflows (VIS-04)

Optional but recommended before National rollout:

4. External audit with screen-reader testing by a qualified assessor
5. Axe-core CI integration extended to cover connected-frontend pages automatically (currently only Planning Workspace is covered in CI)

---

## Test Infrastructure

| Component | Tool | Coverage | CI |
|---|---|---|---|
| Planning Workspace | axe-core via Playwright (`e2e/accessibility.spec.ts`) | 19 pages, all roles | Yes — runs on push |
| Connected Frontend | axe-core (manual injection, local) | 18 pages | No — manual only |

---

## Applicable Standards

| Standard | Version | Level |
|---|---|---|
| Web Content Accessibility Guidelines | 2.1 | AA (target) |
| EN 301 549 (European accessibility standard) | v3.2.1 | Referenced for Government of Australia obligations |
| WCAG 2.2 | 2.2 | Not assessed separately; 2.1 AA coverage addresses all 2.2 A/AA criteria except SC 2.4.11 (Focus Appearance, Level AA — not assessed) |

---

## Next Review Date

**2026-11-01** — or upon completion of Phase 7 UX redesign, whichever is earlier.

Resolved gaps should be re-documented in an updated version of this file.
