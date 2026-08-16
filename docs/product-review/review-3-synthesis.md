# AAFC TMS — Review 3 Synthesis

**Review:** Post-Gap Human Workflow, Architecture and Design Review — Stage 3 (Frontend Design)  
**Date:** 2026-08-16  
**Covers:** design-audit.md + design proposals artifact (visual before/after proposals)

---

## Executive summary

The AAFC TMS has a strong institutional visual identity — the navy/blue AAFC palette is distinctive and correctly applied in the navigation sidebar and header. The primary design concerns are not about the palette itself but about how the tokens are *applied outside their correct context* and what is *missing from the design system*.

No critical architectural design defects were found. The application is usable and looks professional. The findings below are changes that would materially improve usability for the target user — a Training Officer who may be 80 years old, with standard vision and no technology background.

---

## HIGH priority findings

### DES-H01: `--blue (#51b0e3)` must not be used as text on light backgrounds

**Finding:** C-01 in design-audit.md  
**Contrast ratio:** `#51b0e3` on white = **2.3:1** (WCAG AA requires 4.5:1 for normal text)  
**Impact:** Any link, active label, or body text in `--blue` on a light background is inaccessible for users with reduced contrast sensitivity. Common in the 65+ age group.  
**Fix:** Use `--royal (#004b8d)` for all interactive text on light backgrounds. Contrast: 8.4:1 ✓. Reserve `--blue` for fills on dark backgrounds (nav sidebar) and non-text accent elements.

---

### DES-H02: Session status chips convey status by colour only

**Finding:** C-02 in design-audit.md  
**Impact:** Fails WCAG SC 1.4.1 (colour not the only visual means of conveying information). Red-green colour blindness affects ~8% of men.  
**Fix:** Add a 1–2 character letter code inside each chip — D (Delivered), C (Cancelled), N (Not Delivered), P (Planned). The code is additive: no colours change, no chips are restructured.  
**Implementation effort:** Very small — a single `<span class="chip-code">D</span>` inside each chip element.

---

### DES-H03: P0 action items indistinguishable from P5 backlog items

**Finding:** C-06, ID-03 in design-audit.md  
**Impact:** A Training Officer scanning the Needs Attention page cannot identify the 3 genuinely urgent items buried among 40 planning backlog items. All items share the same visual weight.  
**Fix:** 4px left border stripe per priority tier:
- P0 command decisions → `--red` stripe
- P1–P2 automation alerts → `--warn` stripe  
- P3–P4 missing info → `--lgrey` stripe
- P5 backlog → no stripe; render in `--text-2` (visually quieter)

---

### DES-H04: `--lgrey` used as text and `--warn` on `--warn-bg` both fail contrast

**Finding:** A-01 in design-audit.md  
- `--lgrey (#b0b7bb)` on white = **2.0:1** — fails WCAG AA. Must never appear as text.
- `--warn (#c97a00)` on `--warn-bg (#fff3cd)` = **3.1:1** — fails for normal text weight.  
**Fix:** `--lgrey` = borders and background fill only. Warning banners must use `--text (#1e2d3d)` for body text, with `--warn` reserved for the icon/indicator only.

---

## MEDIUM priority findings

### DES-M01: No defined typography scale

No `--text-xs` through `--text-2xl` tokens exist. Every component defines its own font sizes independently. Proposed 5-level scale (12/14/16/18/22/28px) establishes a readable minimum of 16px for all body content. See design proposals artifact for the full scale.

---

### DES-M02: No spacing scale

No `--space-n` tokens. Every component hardcodes its own padding. Proposed 4px-base scale (4/8/12/16/20/24/32/40px) enables consistent rhythm and makes Compact/Comfortable mode a 3-line CSS override.

---

### DES-M03: Dashboard — Section A not visually dominant

Tonight's parade night detail should be the first thing the eye lands on. Currently, the heading and period selector precede it. Proposed: dark gradient hero card for Section A; delivery analytics (B), curriculum (C), staffing resilience (D) behind a "Show analytics" toggle disclosure. Primary use-case scroll depth: 0 (hero is above the fold).

---

### DES-M04: Navigation active state — colour shift only

The current active nav item uses a colour shift from muted white to `--blue`. While WCAG-adequate on the dark sidebar (7.8:1), it is subtle for older users. Proposed: 3px `--blue` left accent bar + bold weight + 15% blue background tint. Three visual signals, not one.

---

### DES-M05: Semantic card borders absent

All cards look identical regardless of urgency. Proposed: 4px left border stripe encoding semantic state (red = attention, amber = warning, grey = background, green = resolved, blue = informational). Additive — no layout changes required.

---

### DES-M06: Keyboard focus indicator not defined in design system

WCAG 2.1 SC 2.4.7 requires visible focus. No `:focus-visible` rule is defined in the system. Proposed global rule: `outline: 3px solid var(--blue); outline-offset: 2px`.

---

### DES-M07: Minimum touch target size not enforced

For users with reduced fine motor control, all interactive icon buttons must be at least 44×44px. Currently unverified across all inline icon buttons (edit, archive, stats icons in tables). Proposed: `.icon-btn { min-width: 44px; min-height: 44px; }` as a global rule.

---

## LOW / Technical debt (summarised)

| ID | Finding |
|---|---|
| T-01 | Single font family — Montserrat for chrome, system-ui for prose tables |
| SP-02 | Display Size preference should persist in localStorage |
| SP-03 | Wide tables need overflow-x: auto container |
| P-01 | Weekly Program print disclaimer missing from Main TMS |
| N-01 | PW bottom drawer label "Activities ▲" should be "Planning Tools ▲" |
| N-02 | No consistent page title / breadcrumb across all pages |

---

## Design system gaps (add to frontend.md)

Three additions to the design token system would eliminate most category-M findings without requiring any visual redesign:

1. **Typography scale** — `--text-xs` through `--text-2xl` (6 tokens)
2. **Spacing scale** — `--space-1` through `--space-10` (8 tokens)  
3. **Focus ring rule** — `:focus-visible` global CSS rule

These are additive; they do not change any existing colour or layout.

---

## Design verdict

| Area | Verdict |
|---|---|
| Institutional identity / palette | ✓ STRONG — correctly applied in nav sidebar |
| Primary text contrast | ✓ PASS — --text on all surfaces ≥ 13:1 |
| Accent colour as text | ⚠ HIGH — --blue fails on light backgrounds |
| Status chip accessibility | ⚠ HIGH — colour-only meaning |
| P0 vs P5 visual differentiation | ⚠ HIGH — no visual hierarchy between urgency tiers |
| Typography | ⚠ MEDIUM — no scale; no minimum enforced |
| Spacing | ⚠ MEDIUM — no scale; inconsistent rhythm |
| Component consistency | ✓ ACCEPTABLE — consistent pattern, no scale tokens |
| Navigation visual hierarchy | ⚠ MEDIUM — active state subtle |
| Information density (Dashboard) | ⚠ MEDIUM — Section A not dominant |
| Accessibility — focus ring | ⚠ MEDIUM — not defined |
| Print layout | ✓ PRESENT — disclaimer gap only |
| Dark theme support | ⚠ ABSENT — no dark theme in current system |

---

## Recommended action sequence

**Tier 1 — Fix before broad rollout (can be done in < 1 day):**
1. DES-H01: Replace `--blue` with `--royal` in all text/link contexts on light backgrounds
2. DES-H02: Add letter code to session status chips (D/C/N/P)
3. DES-H04: Restrict `--lgrey` to non-text uses; fix warn banner text colour
4. DES-H03: Add left border stripes to Needs Attention cards by priority tier

**Tier 2 — Add to token system (half day):**
5. DES-M01: Add typography scale tokens to CSS
6. DES-M02: Add spacing scale tokens to CSS
7. DES-M06: Add global `:focus-visible` focus ring rule
8. DES-M07: Add `.icon-btn { min-width: 44px; min-height: 44px; }` rule

**Tier 3 — Layout improvements (1–2 days):**
9. DES-M03: Dashboard Section A hero treatment
10. DES-M04: Navigation active state — three-signal treatment
11. DES-M05: Semantic card border stripes throughout

---

*Review 3 complete. Design proposals are shown as live rendered examples in the design proposals artifact. No code was changed in this review.*
