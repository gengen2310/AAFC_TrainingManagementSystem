# AAFC TMS — Frontend Design Audit

**Review:** Post-Gap Human Workflow, Architecture and Design Review — Stage 3 (Frontend Design)  
**Date:** 2026-08-16  
**Scope:** Main TMS (connected-frontend), Planning Workspace (frontend/), visual design, hierarchy, typography, colour, accessibility, print  
**Target user:** Squadron Training Officer (~80 years old, Year 10 English, no technology background, standard vision)  
**Method:** Code-based audit against WCAG 2.1 AA, design token system (`frontend.md`), and usability standards for older adult users  
**Status:** Findings and proposals — no code changes in this review

---

## Design identity

The AAFC TMS has a clear institutional colour palette rooted in the AAFC Visual Identity Guide:

| Token | Value | Role |
|---|---|---|
| `--dark` | `#002f65` | AAFC navy — header, navigation structure |
| `--blue` | `#51b0e3` | AAFC blue — accent, active states, highlights |
| `--royal` | `#004b8d` | Royal blue — secondary active |
| `--steel` | `#455560` | Gunmetal grey — body text, secondary surfaces |
| `--red` | `#e51937` | Danger / Must-attend only |
| `--ok` | `#1a7f4b` | Success / Delivered |
| `--warn` | `#c97a00` | Warning / Caution |

Background: `#f4f8fc` — a very light AAFC-blue tint  
Font: `Montserrat, Arial, sans-serif`

**Verdict on identity:** The palette is genuinely specific to AAFC — it could not be mistaken for a generic SaaS product. The navy/blue combination is strong and consistently applied. The institutional identity is a design asset, not a liability.

---

## Section 1: Typography

### T-01: Single font family, no weight differentiation between page roles

**Finding:** Montserrat is used throughout — headings, body text, labels, table headers, chart labels — at varying weights (400, 500, 600, 700). There is no distinct display face, no separate body face. The entire application speaks in one voice.

**For an 80-year-old user:** Montserrat at 400 weight can feel thin at smaller sizes. The geometric letterforms are modern but the lack of serifs may reduce readability for extended reading compared to a high-x-height body face.

**Impact:** Medium. Montserrat is legible and on-brand. The issue is not the face itself but how weight alone carries all hierarchy — a single weight jump from 400 to 600 must do the work that would normally be shared between size, weight, and contrast.

**Recommendation:** Maintain Montserrat for UI chrome (nav, labels, buttons, table headers). Consider adding a secondary face — a high-x-height humanist sans like `system-ui` or a readable variable font — for paragraph text. Even switching body paragraphs from Montserrat to the system font stack (`-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`) would reduce visual monotony and improve paragraph legibility at no additional CDN cost.

---

### T-02: Body text size — unclear from token system

**Finding:** The design token system does not define a base font size token. Visual inspection of the HTML and inline styles suggests the application uses browser-default sizing (16px) modified by class-based overrides. The "Compact" display mode reduces padding and spacing — it does not appear to reduce font size.

**For an 80-year-old user:** 16px is the minimum acceptable body text size for older adults. If any text is below 14px (labels, table headers, chart captions), it will be difficult to read without magnification.

**Risk areas from code reading:**
- Table cells (`.text-xs` or similar utility classes may apply below-16px sizes)
- Chart axis labels (canvas-rendered; size set programmatically)
- Status chip labels (short badge-style labels may be rendered small)
- Dropdown options in long selectors (Activities page has multiple dropdowns)

**Recommendation:** Establish a minimum text size of 16px for all readable content. Labels and captions may be 14px but no smaller. Document this as a design rule.

---

### T-03: Type scale — absent from design token system

**Finding:** The `frontend.md` rules define colour tokens but no typography scale tokens. There is no `--text-xs`, `--text-sm`, `--text-base`, `--text-lg`, etc. This means individual page sections define their own heading sizes, creating inconsistency across pages.

**Consequence:** Dashboard headings, Activities headings, Settings headings — each page may use slightly different heading sizes. Without a scale, any developer adding a new section must guess or copy nearby code.

**Recommendation:** Define a 5-level scale in CSS:
```css
--text-xs:   12px;  /* footnotes, meta labels — use sparingly */
--text-sm:   14px;  /* secondary labels, captions */
--text-base: 16px;  /* body text, table cells — minimum readable */
--text-lg:   18px;  /* section subheadings */
--text-xl:   22px;  /* page headings */
--text-2xl:  28px;  /* Dashboard stat numbers */
```

---

## Section 2: Colour system

### C-01: `--blue (#51b0e3)` — insufficient contrast as a text colour

**Finding:** `#51b0e3` (AAFC blue) is used as the accent colour, active states, links, and highlights. On a white background (`#ffffff`), its contrast ratio is approximately **2.3:1** — far below WCAG AA's 4.5:1 requirement for normal text and 3:1 for large text.

**Verified calculation:**
- `#51b0e3` on `#ffffff` → contrast ratio ≈ 2.3:1 (fails WCAG AA)
- `#51b0e3` on `#f4f8fc` (page background) → contrast ratio ≈ 2.1:1 (fails)
- `#51b0e3` on `#002f65` (nav background) → contrast ratio ≈ 7.8:1 (passes)

**Impact:** Any link, active nav indicator, or label text rendered in `#51b0e3` on a light background is inaccessible for users with reduced contrast sensitivity — common in the 65+ age group.

**Recommendation:** Never use `--blue` (`#51b0e3`) as body text or link colour on light backgrounds. Use it exclusively as:
- A fill colour on dark backgrounds (nav sidebar, where it passes)
- A border/outline accent
- A background tint (`--accent-light: #e0f0fa`)
- A large graphic element

For interactive text links and active labels on light backgrounds, use `--royal (#004b8d)` — contrast ratio on white ≈ **8.4:1** (passes WCAG AA and AAA).

---

### C-02: Status colour system — colour-only meaning

**Finding:** Sessions are represented on parade night cards and calendar cells as coloured chips indicating status:
- Green = Delivered (`--ok: #1a7f4b`)
- Red = Cancelled (`--red: #e51937`)
- Amber = Not Delivered (`--warn: #c97a00`)
- Blue = Planned
- Grey = Draft

For a user with colour blindness (red-green colour blindness affects ~8% of men), the Green/Red/Amber distinction is unreliable. For an 80-year-old user with reduced colour discrimination, these chips may appear as similar dark shapes.

**Impact:** High for accessibility. WCAG SC 1.4.1 requires that colour is not the only visual means of conveying information.

**Recommendation:** Add a 1-2 letter status abbreviation inside each chip:
- D (Delivered) — green
- C (Cancelled) — red
- N (Not Delivered) — amber
- P (Planned) — blue
- ✓ (Closed) — dark

These are small additions that make the chips readable without colour and also reduce the need to reference a legend.

---

### C-03: `--ok-bg (#d4f0e3)` and `--warn-bg (#fff3cd)` — insufficient contrast for text

**Finding:** Status background colours used for banner/callout states:
- `--ok-bg: #d4f0e3` with `--ok-text: #145f38` → contrast ratio ≈ **5.6:1** (passes AA for normal text — acceptable)
- `--warn-bg: #fff3cd` with `--warn: #c97a00` → contrast ratio ≈ **3.1:1` (passes for large text only, fails for normal text)

The warn combination is used for warning banners and caution messages. If warning text uses `--warn (#c97a00)` on `--warn-bg (#fff3cd)`, it fails WCAG AA for normal-weight text.

**Recommendation:** Use `--text (#1e2d3d)` or `--steel (#455560)` for text on `--warn-bg`. Reserve `--warn` for the warning icon/indicator only.

---

### C-04: `--text (#1e2d3d)` — strong, passes all combinations

**Finding (positive):** Primary text colour `#1e2d3d` (deep navy-dark) on `#ffffff` → contrast ratio ≈ **14.5:1** (passes AAA). On `#f4f8fc` → ≈ **13.8:1**. The primary text colour is excellent.

**No action needed.**

---

### C-05: Nav sidebar — colour on dark background

**Finding:** Navigation uses `--dark (#002f65)` as background, `--blue (#51b0e3)` as active item colour (on dark), and white as item text.

- White on `--dark (#002f65)` → ≈ **14.8:1** (passes AAA) ✓
- `--blue (#51b0e3)` on `--dark (#002f65)` → ≈ **7.8:1` (passes AA) ✓

**No accessibility issue on the nav sidebar itself.** The problem is when these colours are used outside the nav context on light backgrounds (see C-01).

---

### C-06: Status priority visual weight — P0 must stand out

**Finding:** The Needs Attention page shows P0 (command decision), P1 (automation alert), P2 (outcome not recorded), P3 (missing reason), P4 (no curriculum), and P5 (backlog) items. From the code:

- P0: Command decision — presumably uses `--red` or high-urgency treatment
- P5: Backlog items — presumably lower visual weight

If P5 items are styled similarly to P0-P4 items but outnumber them significantly (potentially hundreds vs a handful), the entire list feels uniformly urgent and the genuinely critical items are invisible.

**Recommendation:** P0 items should use a distinct visual treatment — a left border stripe in `--red`, or a background tint — that makes them unmissable even when scrolling past dozens of P5 items. P5 items should be visually quieter: muted text, no border stripe, collapsed under a disclosure.

---

## Section 3: Visual hierarchy

### VH-01: Dashboard — Section A competes with page chrome

**Finding:** The Dashboard has a page heading, a period selector, Quick Actions buttons, and then Section A (Tonight & This Week). By the time the user reaches the most important section (what is happening at the next parade night), they have already processed several UI elements.

**For an 80-year-old user:** The most important question when opening the Dashboard should be immediately visible: "What is happening tonight and is it ready?" This should be the first thing the eye lands on — not the page header or action buttons.

**Recommendation:** Promote Section A to a visual "hero" position:
- Larger card, distinctly styled from the sections below
- Night date in large type (`--text-2xl`)
- Readiness indicator visually dominant
- Quick action for recording outcomes (when a past night has unrecorded outcomes) embedded in the hero, not in a separate section

---

### VH-02: Activities page — no visual separation between 8 areas

**Finding:** The Activities page places 8 conceptually distinct areas on one scrolling page without visual breaks:
1. Activities table
2. Getting Help block
3. Planning Year selector
4. Parade Dates card
5. Holidays card
6. Training Classes card
7. Mission Backlog card
8. Class Forecasts card

Each area is a card (`--surface`, `--sh`) but cards are visually identical — same background, same shadow, same border radius. There is no visual hierarchy between the "Activities" concept and the Planning Year sub-area below it, no clear section demarcation, and no visual cue that the user has transitioned from "Events management" to "Year setup."

**For an 80-year-old user:** Scrolling through what appears to be a continuous list of similar-looking cards, with no section headers or visual anchors, is cognitively demanding. The user cannot determine at a glance that there are multiple distinct sections on this page.

**Recommendation (aligned with IA-01 from Review 1):** The long-term fix is to move these areas to dedicated nav sections. For the interim, if the page must remain consolidated, add explicit section dividers with contrasting backgrounds: the "Planning Year" sub-area should begin with a clear section header (`--surface-2` background, strong heading) that signals "you are now in Annual Plan territory."

---

### VH-03: Navigation — active page indicator too subtle

**Finding (inferred from token system):** Active navigation items use `--blue (#51b0e3)` as an indicator on a `--dark (#002f65)` background. On the sidebar, this contrast is adequate (7.8:1). However, `--blue` is also used as the inactive icon/text colour, meaning the active indicator has only moderate visual differentiation from inactive items.

**For an 80-year-old user:** The question "which page am I on?" must be answered at a glance. If the active indicator is a subtle colour shift rather than a clear visual marker (e.g., a solid accent bar, a filled background chip, or a bold weight shift), users may not know where they are.

**Recommendation:** Active nav item should use a visually distinct treatment — a left accent bar (3px solid `--blue` or white) plus bold text weight — that is unambiguous. The inactive items should be lighter in weight to create stronger contrast with the active state.

---

### VH-04: Card hierarchy — all cards look the same

**Finding:** Cards throughout the application use a consistent `--surface` background with `--sh` box shadow. This consistency is a design strength — it creates visual unity. However, it also means that:
- Primary content cards (e.g., Parade Night detail) look the same as informational cards (e.g., Getting Help)
- Warning cards look similar to neutral cards until the internal indicator is read
- The user must read the card header to determine its purpose — there is no at-a-glance "this card needs your attention" signal

**Recommendation:** Introduce a semantic border treatment:
- Default card: `--border-light` border (current)
- Attention card (P0-P2 action items): 3px left border in `--red`
- Warning card (P3-P4 items): 3px left border in `--warn`  
- Success card: 3px left border in `--ok`
- Informational card: 3px left border in `--pale`

Left border stripes are cheap to implement and effective at conveying semantic meaning at a glance.

---

## Section 4: Spacing and layout

### SP-01: No defined spacing scale

**Finding:** Like the typography scale, the design token system has no spacing tokens. There is no `--space-1`, `--space-2`, etc. Spacing is applied inline with `padding: 12px 16px` or similar. Each component defines its own spacing.

**Consequence:** Visual rhythm is inconsistent across pages. Some sections feel tight; others have generous whitespace. Without a spacing scale, any new component a developer adds will be eye-matched rather than system-matched.

**Recommendation:** Define a 4px-base spacing scale:
```css
--space-1:  4px;
--space-2:  8px;
--space-3: 12px;
--space-4: 16px;
--space-5: 20px;
--space-6: 24px;
--space-8: 32px;
--space-10: 40px;
```
Apply consistently. Compact mode reduces spacing to the level below on the scale.

---

### SP-02: "Compact / Comfortable" — good concept, implementation unknown

**Finding:** Unit Settings → Display Size allows switching between Compact and Comfortable modes. This is a valuable accessibility feature — older users often benefit from Comfortable mode which provides larger click targets and more whitespace.

**Concern:** This setting is stored in unit settings (sqn_admin only) and may be session-scoped (based on the implementation note "browser-session only" in the prior code reading). If it is browser-session only, it resets when the tab is closed. An 80-year-old user who needs Comfortable mode must set it every session.

**Recommendation:** Persist the Display Size preference in `localStorage` (for this specific preference only — not operational data). Since it is a display preference with no security implications, client-side persistence is appropriate.

---

### SP-03: Wide tables — horizontal scroll risk

**Finding:** Multiple pages have wide tables: Facilitators (rank, name, type, subjects, sessions), Curriculum (code, title, element, parts, status, actions), Account Management (name, role, scope, unit, status, last login). On narrow screens or in windows that aren't full-width, these tables may overflow or crowd.

**Current state (from token system):** No `overflow-x: auto` container is mentioned in the design system. The CSS may handle this inline.

**For an 80-year-old user:** An 80-year-old is more likely to use a desktop/laptop at a lower screen resolution or with browser zoom applied. Both reduce the effective viewport width.

**Recommendation:** All data tables must be wrapped in `overflow-x: auto` containers. Critical columns (name, date, primary status) must be visible without horizontal scroll. Deferrable columns (notes, secondary metadata) can overflow horizontally.

---

## Section 5: Component consistency

### CC-01: Button hierarchy — primary / secondary / danger

**Finding (from code reading):** Action buttons throughout the application use variant styling to convey hierarchy. From context:
- Primary actions (Save, Confirm, Generate): filled `--blue` or `--dark` background
- Secondary actions (Cancel, Back): outline or ghost style
- Danger actions (Archive, Delete): filled `--red` or outline red

**Assessment:** This pattern is correct. The concern is consistency of application — does every confirm button across all modals use the same primary style? From the size of the codebase (400KB single file), maintaining this consistency manually is difficult.

**Specific concern from code:** The "Bulk Cancel" button on parade nights is a destructive action. It should use a danger style. If it uses the same style as "Publish" (which is constructive), users may not perceive the risk difference.

---

### CC-02: Modal consistency

**Finding:** The application has dozens of modals (Add Facilitator, Add Room, Add Holiday, Add Training Class, Quick Edit Session, Guided Session, Year Setup, Generate Dates, etc.). From reading the code, these all follow a similar template:
- Header with title and close button
- Body with form fields
- Footer with Cancel + Submit buttons

This consistency is good. The concern is the modal overlay — does it darken the background sufficiently to focus the user's attention? A light or absent overlay can leave an older user unsure whether the modal is part of the page or a separate element.

**Recommendation:** Modal overlay should be `rgba(0, 47, 101, 0.45)` (AAFC navy at medium opacity) — darker than a standard grey overlay, and on-brand.

---

### CC-03: Table header vs data cell differentiation

**Finding:** Tables throughout the application have header rows. These should be clearly distinguished from data rows through:
- Background colour difference (header: `--surface-2` or `--lgrey`)
- Font weight (header: 600, data: 400)
- Text colour (header: `--text-2` or `--muted`, data: `--text`)

From the design token system, these tokens exist. Whether every table applies them consistently is unknown without runtime inspection.

**For an 80-year-old user:** If headers and data rows look similar, the user may misread a header label as a piece of data. Clear distinction between "this row labels the columns" and "this row is data" is essential.

---

### CC-04: Input field sizing

**Finding:** Input fields, dropdowns, and text areas must have adequate touch targets. WCAG 2.5.5 specifies a minimum 44×44px touch target. On desktop this is less critical but for older users with reduced fine motor control, undersized fields are difficult to activate.

**Recommendation:** Minimum input height of 44px (achieved with appropriate vertical padding on a 16px input: `padding: 10px 12px`).

---

## Section 6: Information density

### ID-01: Dashboard — four sections, increasing information requirement

**Finding:** The Dashboard has four analytically distinct sections. A Training Officer checking "is tonight ready?" needs Section A (first ~300px of page). A Training Officer reviewing delivery trends needs Section B (next ~600px). Curriculum progress needs Section C. Strategic staffing view needs Section D, which is hidden behind a button.

The page asks the user to understand their information need before looking, and scroll to the appropriate depth.

**For an 80-year-old user:** Long vertical scroll to find relevant information is a significant usability burden. Users who don't know Section D exists will never find it.

**Recommendation:**
- Section A: Full width, visually dominant, above the fold on a standard 1080p screen
- Sections B and C: Tabbed or behind a "Show analytics" toggle — revealed by choice, not forced on load
- Section D: Accessible via a clear "Staffing overview" button (not a deferred load)
- Total page scroll depth should not exceed 2 screens for the primary use case (check tonight)

---

### ID-02: Planning Workspace — excellent progressive disclosure

**Finding (positive):** The PW uses progressive disclosure well:
- Main canvas shows what is needed for the current time range
- Right drawer opens only when a session is clicked (not always visible)
- Bottom drawer opens only when the user needs reference data
- Layer filters let users add/remove information density

This is the best-designed part of the application from an information density perspective. It makes a fundamentally complex task (term planning) feel manageable.

**No action needed.** This pattern should inform future Main TMS design decisions.

---

### ID-03: Needs Attention — operational and backlog items share the same density

**Finding:** As documented in Review 1 and Review 2, P5 (backlog items) and P0-P4 (operational items) share the same visual treatment and list space. The result is a page that may show 3 urgent items buried beneath 40 planning backlog items, all with the same visual weight.

**Visual fix (even before the IA restructure):**
- Give P0 items a distinct red left-border stripe
- Give P1-P2 items an amber left-border stripe
- Give P3-P4 items a neutral left-border strip
- Give P5 items no stripe and render in `--text-2` (softer) — they are background information, not action items

---

## Section 7: Accessibility

### A-01: Colour contrast failures — summary

| Text | Background | Contrast | WCAG AA | Action |
|---|---|---|---|---|
| `#51b0e3` (--blue) | `#ffffff` (white) | ~2.3:1 | FAIL | Never use blue as text on white |
| `#51b0e3` (--blue) | `#f4f8fc` (--bg) | ~2.1:1 | FAIL | Never use blue as text on page bg |
| `#c97a00` (--warn) | `#fff3cd` (--warn-bg) | ~3.1:1 | FAIL (normal) | Use dark text on warn-bg |
| `#1e2d3d` (--text) | `#ffffff` | ~14.5:1 | PASS | ✓ |
| `#3a4a55` (--text-2) | `#ffffff` | ~8.0:1 | PASS | ✓ |
| `#5c6a76` (--muted) | `#ffffff` | ~5.0:1 | PASS (borderline) | Monitor; don't make smaller |
| `#b0b7bb` (--lgrey) | `#ffffff` | ~2.0:1 | FAIL | Never use as text |
| White | `#002f65` (--dark nav) | ~14.8:1 | PASS | ✓ |
| `#51b0e3` | `#002f65` (--dark nav) | ~7.8:1 | PASS | ✓ (nav context only) |
| `#1a7f4b` (--ok) | `#d4f0e3` (--ok-bg) | ~5.6:1 | PASS | ✓ |
| `#145f38` (--ok-text) | `#d4f0e3` (--ok-bg) | ~7.6:1 | PASS | ✓ |

**Critical finding:** `--lgrey` (`#b0b7bb`) must NEVER be used as body text. It is a border/background colour only. If any labels, table headers, or secondary text use `--lgrey` as their colour, this is a WCAG failure.

---

### A-02: Colour-only status indicators on session chips

**Finding:** Detailed in C-02. The session chips on Parade Night cards use colour alone to indicate status. This fails WCAG SC 1.4.1.

**Severity:** HIGH for accessibility compliance.

---

### A-03: Focus indicators

**Finding:** WCAG 2.1 SC 2.4.7 requires a visible keyboard focus indicator. The design system does not define a `--focus-ring` token or document what the focus ring looks like.

**For an 80-year-old user:** Keyboard navigation may be preferred over mouse for users with reduced fine motor control. If the focus ring is the browser default (a thin dotted outline), it may be invisible on some backgrounds.

**Recommendation:** Add an explicit focus ring rule:
```css
:focus-visible {
  outline: 3px solid var(--blue);
  outline-offset: 2px;
  border-radius: 2px;
}
```
`--blue (#51b0e3)` is appropriate for the focus ring because it is visually distinct from the AAFC navy background and adequate as a non-text indicator (focus rings are exempt from the 4.5:1 text contrast requirement).

---

### A-04: Touch targets and click targets

**Finding:** For users with reduced dexterity (common in older adults), minimum 44×44px interaction targets are required (WCAG 2.5.5, Enhanced). At-risk elements:
- Table row action icons (edit, archive, stats) — typically small inline icon buttons
- Session period chips on parade night cards — may be click targets with small dimensions
- Dropdown arrows in compact mode
- The "pencil" icon for session quick edit

**Recommendation:** All interactive icon buttons must have a minimum 44×44px clickable area. This can be achieved with padding even if the icon itself is smaller:
```css
.icon-btn {
  min-width: 44px;
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
```

---

## Section 8: Print layout (Weekly Program)

### P-01: Print disclaimer present in PW but not Main TMS

**Finding (from frontend-duplication-register.md):** The PW's Weekly Program includes a footer: "AAFC TMS · planning document only — not a system of record." The Main TMS version does not include this disclaimer.

**Recommendation:** Add the disclaimer to Main TMS Weekly Program print layout. A Training Officer who hands out the printed program should know it represents a point-in-time snapshot.

---

### P-02: Print CSS quality — unknown without runtime test

**Finding:** The Weekly Program explicitly uses `window.print()` for printing. Print CSS must handle:
- Hiding navigation sidebar
- Hiding action buttons
- Showing all sessions without truncation
- Appropriate font size for print (typically 11-12pt)
- Page break control between sessions
- Squadron crest display

**From code context:** Print styles exist (the nav is hidden, layout adjusts). Whether the output is clean requires visual inspection.

**Recommendation:** Verify print output in at least two browsers (Chrome and Safari) with the squadron crest URL set. Test with a printer-friendly view before marking as complete.

---

## Section 9: Navigation visual design

### N-01: Planning Workspace bottom drawer label "Activities ▲"

**Finding (from duplicate-function-register.md):** The PW's bottom drawer toggle button is labelled "Activities ▲" but contains 8 tabs: Activities, Mission Backlog, Facilitators, Schedule, Rooms, Equipment, Holidays, Notices.

**Visual design issue:** The label creates false expectations. A user who sees "Activities" expects to see AAFC events — not facilitators or equipment. The disclosure icon (▲) also inverts when the drawer closes (▼), which is correct, but the label itself is the primary problem.

**Recommendation:** Rename to "Planning Tools ▲" or "Reference Panel ▲". Alternatively, show tab icons or abbreviated names: "☰ Activities · Backlog · Facilitators · Rooms" — a scrolling micro-label that hints at the drawer's contents.

---

### N-02: Breadcrumb / location indicator absent

**Finding:** The application has no breadcrumb and no page location indicator beyond the active nav item (which is visible only if the user looks at the left sidebar). For an 80-year-old user who may have clicked through several screens, "where am I?" is not always obvious.

**Recommendation:** Add a persistent page title in the main content area header that matches the nav label. The Dashboard already shows "Training Dashboard" — extend this pattern to all pages. Ensure the page title is `<h1>` semantically and visually prominent.

---

## Summary: Design findings by priority

### High — fix before broad rollout

| ID | Finding | Domain |
|---|---|---|
| C-01 | `--blue (#51b0e3)` fails contrast as text on light backgrounds | Colour/Accessibility |
| C-02 | Status chips are colour-only (session status) | Accessibility |
| C-06 | P0 action items not visually distinct from P5 backlog items | Visual hierarchy |
| A-01 | `--lgrey` must never be text colour; `--warn` on `--warn-bg` fails | Colour/Accessibility |
| A-02 | Session chip colour-only meaning (duplicate of C-02) | Accessibility |

### Medium — fix in next implementation cycle

| ID | Finding | Domain |
|---|---|---|
| T-01 | Single font family — no display/body distinction | Typography |
| T-02 | Body text minimum size not formally defined | Typography |
| T-03 | No typography scale tokens | Typography |
| SP-01 | No spacing scale tokens | Spacing |
| VH-01 | Dashboard Section A not visually dominant | Visual hierarchy |
| VH-02 | Activities page — no visual separation between 8 areas | Visual hierarchy |
| VH-03 | Nav active indicator too subtle | Visual hierarchy |
| VH-04 | All cards look identical regardless of semantic purpose | Visual hierarchy |
| A-03 | Focus ring not defined in design system | Accessibility |
| A-04 | Touch targets may be too small for older users | Accessibility |
| ID-01 | Dashboard scroll depth is too long for primary use case | Information density |
| SP-02 | Display Size preference should persist across sessions | UX |

### Low — technical debt

| ID | Finding | Domain |
|---|---|---|
| CC-01 | Button hierarchy — assumed correct, unverified at scale | Components |
| CC-02 | Modal overlay may be too light | Components |
| CC-04 | Input field sizing — assumed adequate, verify | Components |
| P-01 | Print disclaimer absent from Main TMS | Print |
| P-02 | Print CSS output unverified in all browsers | Print |
| N-01 | PW bottom drawer label "Activities ▲" is misleading | Navigation copy |
| N-02 | No breadcrumb / page location indicator | Navigation |
| SP-03 | Wide tables — horizontal scroll container needed | Layout |

