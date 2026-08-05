# Accessibility Findings — AAFC TMS UI/UX Review

Audit date: 2026-08-06.
Prior assessment: `docs/release/final_accessibility_assessment.md` (Stage 7).
This document records the current state, referencing the prior assessment and adding observations from the current screenshot pass.

---

## Planning Workspace — Status: PASS (19/19 axe tests)

From `final_accessibility_assessment.md`: 19/19 Playwright axe tests pass. Zero critical/serious/moderate violations across all routes captured.

No regressions observed in 2026-08-06 screenshot pass.

---

## Main TMS (connected-frontend) — Status: PARTIAL

### A11Y-01 · Critical · 83 unlabeled `<select>` elements

**Impact**: Critical — screen reader users cannot identify filter/selector controls.

**Current state**: 85 `<select>` elements without accessible names found via grep. 2 were fixed in Stage 7 (`#curr-f-el`, `#curr-f-prog` on the Curriculum page — `aria-label` added). 83 remain.

**Note**: Many are repeated template patterns (e.g. `np-ph-${i}`, `d-fa-${i}`) — the number of distinct control *types* requiring labelling decisions is smaller than 83, but still systemic.

**Fix approach**: Audit each `<select>` pattern; add `aria-label` or `<label for>` per control type; re-scan to confirm.

---

### A11Y-02 · Serious · Color contrast — fixed locally, NOT deployed

**Impact**: Serious — 40-43 color-contrast violations per page as of the original scan.

**Current state**: Fix committed at local `ca785b4` (five new accessible tokens: `--muted`, `--muted-text-on-light`, `--text-on-dark-muted`, `--link-on-light`, `--status-text-danger`). Verified clean (0 violations) against local dev server. **Not deployed** to staging or production — both live environments still serve commit `699b01f` which predates the fix.

**Action required**: Deploy `ca785b4` (or rebase/cherry-pick) to staging; re-scan; then deploy to production.

---

### A11Y-03 · Moderate · No `<h1>` anywhere in the SPA

**Impact**: Moderate — screen reader users cannot locate the page title using heading navigation. NVDA/VoiceOver heading-jump commands find nothing.

**Current state**: All page titles in `connected-frontend/index.html` are rendered as `<div>` or `<span>` elements with visual heading styling. No `<h1>` exists on any page.

**Evidence**: System Console screenshot confirms the pattern: "System Console" is displayed in bold but is not a heading element.

**Fix approach**: Add `<h1 class="page-title">` to each `page-{id}` div's title element, with appropriate visual styling preserved via CSS reset. This is a whole-app change and should be done with a single pass.

---

### A11Y-04 · Moderate · No landmark regions

**Impact**: Moderate — screen reader users cannot skip to main content or navigate to the sidebar. The entire app is rendered without `<main>`, `<nav>`, `<aside>`, or `<header>` landmark elements.

**Current state**: The SPA uses `<div>` containers throughout. The sidebar nav is a `<div id="nav">`. The main content is a `<div id="main">`.

**Fix approach**: Add `role="navigation"` (or `<nav>`) to the sidebar, `role="main"` (or `<main>`) to the content area, and `role="banner"` (or `<header>`) to the app header. Add a "Skip to main content" link at the top of the document.

---

### A11Y-05 · Not assessed · Keyboard-only navigation

**Status**: Not completed in Stage 7 (documented as remaining work). Not completed in this pass (screenshot-based, not interactive).

**Required**: Full keyboard-only trace through each nav page — Tab order, focus visibility, Enter/Space activation of all interactive elements, Escape for modal dismissal.

---

### A11Y-06 · Not assessed · Screen reader (VoiceOver/NVDA)

**Status**: Not completed. No ability to run VoiceOver/NVDA in the automated capture environment. Recommended as manual follow-up.

---

## Summary table

| ID | Frontend | Issue | Impact | Status |
|---|---|---|---|---|
| A11Y-01 | Main TMS | 83 unlabeled `<select>` elements | Critical | Open (2/85 fixed) |
| A11Y-02 | Main TMS | Color contrast 40-43 violations/page | Serious | Fixed locally, not deployed |
| A11Y-03 | Main TMS | No `<h1>` anywhere in SPA | Moderate | Open |
| A11Y-04 | Main TMS | No landmark regions | Moderate | Open |
| A11Y-05 | Both | Keyboard-only navigation not tested | Unknown | Not assessed |
| A11Y-06 | Both | Screen reader not tested | Unknown | Not assessed |
| — | Planning Workspace | axe scan | — | 19/19 PASS |
