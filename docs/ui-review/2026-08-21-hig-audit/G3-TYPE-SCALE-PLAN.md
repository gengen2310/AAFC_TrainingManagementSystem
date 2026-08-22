# G3 — text enlargement: mechanism proved, migration planned

**Status: PASS** — browser-verified 2026-08-22. All 13 `--fs-*` tokens resolve at exactly ×2
at a 32px root (200% text scale). No horizontal overflow. Layout holds on the login page.
Dense authenticated grids not reachable without a live backend — re-run verification there
before closing G3 for the beta sign-off. Residual: 3 `pt` values in `@media print`
intentionally kept.

`print.css` keeps px deliberately — its two declarations are inside `@media print`, and print
output should not track a screen font preference.

## The defect

At audit time **1,492 of 1,528** font-size declarations across both frontends were px-locked
(97.6%). Verified live: doubling the browser's own font-size preference from 16px to 32px
changed the computed size of **nothing**. Page *zoom* still works, but WCAG SC 1.4.4 is about
**text** resize. With a base scale already at 11–12px, that is the accessibility floor.

## Mechanism — proved, not assumed

`rem` resolves against `html`. Nothing in either frontend sets a px font-size on `html`
(`base.css` sets it on `body`, which does not block `rem`), so `rem` scales with the user's
preference today. No JS, no media queries, no build step.

Measured after converting `components.css` and `base.css`:

| Element | source file | 16px root | 32px root | |
|---|---|---|---|---|
| `.btn` | components.css *(converted)* | 13px | 26px | **×2.00** |
| `.scope-pill` | components.css *(converted)* | 11px | 22px | **×2.00** |
| `.badge.warn` | components.css *(converted)* | 10px | 20px | **×2.00** |
| `.fts-item.fts-ok` | components.css *(converted)* | 11px | 22px | **×2.00** |
| `body` | base.css *(converted)* | 14px | 28px | **×2.00** |
| `.pn-grid thead th` | planning.css *(not yet)* | 11px | 11px | ×1.00 |
| `.pw-nc-empty` | planning.css *(not yet)* | 11px | 11px | ×1.00 |

The unconverted rows are the control: they prove the scaling comes from the conversion and
not from something else in the page.

## The scale

Derived from the sizes actually in use, not invented. 18 distinct sizes across 535
declarations in the Planning Workspace; ten steps cover **97%**.

```css
--fs-3xs: 0.5625rem;  /*  9px */    --fs-md:  0.875rem;   /* 14px */
--fs-2xs: 0.625rem;   /* 10px */    --fs-lg:  1rem;       /* 16px */
--fs-xs:  0.6875rem;  /* 11px */    --fs-xl:  1.125rem;   /* 18px */
--fs-sm:  0.75rem;    /* 12px */    --fs-2xl: 1.25rem;    /* 20px */
--fs-base:0.8125rem;  /* 13px */    --fs-3xl: 1.625rem;   /* 26px */
```

Every value is its existing px size over a 16px root, so **nothing changes at the default
setting**. The eight off-scale values (9.5, 10.5, 11.5, 12.5, 15, 17, 22, 32 — 16 declarations
between them) round to the nearest step; none is load-bearing.

**Invariant:** nothing may set a px `font-size` on `html`. That single line would silently
switch all of this off, and no test would fail.

## What is left

| Target | font-size declarations | Status |
|---|---|---|
| `planning.css` | 125 | **done** |
| `layout.css` | 4 | **done** |
| `print.css` | 2 | intentionally left px (`@media print`) |
| Planning Workspace `.tsx` `fontSize` props | 373 | **done** — 56c45f9 |
| Main TMS `<style>` | 158 | **done** — prior session + 28 straggler rem values tokenized |
| Main TMS inline / JS | 801 | **done** — template literals converted; 3 `pt` print kept |

## Corrections to this plan, from doing the work

**"13 fixed heights each need to become min-height" was wrong.** Only **4 of 13** bear text,
and one of those is `.pw-sr-only` (1×1, clipped by design). The other nine are dots, bars,
checkboxes and dividers, where a fixed px size is correct and should stay. The real count was
**3**: `.pn-add-btn`, `.pw-setup-step-num`, `.pw-help-btn`. The original figure came from
counting `height:\s*[0-9]+px` without asking whether the rule contained text.

**`aspect-ratio: 1` + `min-width` is a trap, not the fix.** Used on `.pw-setup-step-num`, it
made a bare (non-flex) instance resolve its width against the containing block and expand to
**1497×1497**. The correct tool is `em`: `width: 2.3em; height: 2.3em` makes the box track its
own glyph, so it grows with the text and stays circular, with no dependency on the parent's
display type. Both circles now double correctly (32→64, 26→52) in flex and block contexts alike.

## Measuring text scaling: set the root at load, never mutate it

Mutating `document.documentElement.style.fontSize` at runtime does **not** reliably re-resolve
`rem` inside a custom property in Chrome. `.pw-help-btn` measured a flat 13px at a 32px root
under runtime mutation — with exactly one matching rule, `--fs-base` correctly reading
`0.8125rem`, and no inline style — while `.btn`, using the identical token, scaled to 26px in
the same page.

Loaded fresh with `<html style="font-size:32px">`, `.pw-help-btn` is **26px** and its box
**52×52**. The rule was correct the whole time; the measurement was not. Two runtime readings
would have been reported as defects, and one nearly triggered a fix to working code.

**Verify with a page loaded at the target root size.** The runtime toggle is convenient and
occasionally lies, and it lies in the direction of inventing failures.

## Order, and why

1. ~~`layout.css` + `print.css`~~ — done.
2. ~~`planning.css` with a layout pass~~ — done. The layout pass mattered: three text-bearing
   fixed heights had to move to `em` sizing first, or the type would have clipped instead of
   scaling. The 17 `nowrap` rules turned out not to overflow at 200% in the components measured;
   re-check them on the dense authenticated grids, which were never reachable here.
3. ~~Planning Workspace `.tsx` props (373)~~ — done (56c45f9). 373 props converted via
   regex script; 1 fractional (11.5) and 2 SVG attributes fixed manually.
4. ~~Main TMS `<style>` block (158)~~ — done. Concurrent session converted the bulk;
   28 straggler bare-rem values rounded to nearest `--fs-*` token.
5. ~~Main TMS inline styles (801)~~ — done. Template literals converted; 3 `pt`
   declarations in `@media print` left intentionally.

The two frontends are deployed separately and must be converted separately; a fix applied to
one has three times now failed to reach the other.

## Coverage of these measurements

Measured at a 32px root set at load: every probed element scales ×2.00, `0` clipped, `0`
horizontal overflow, `scrollWidth == innerWidth`.

That is a result about a **probe page** carrying these components in isolation — not about the
application. The dense authenticated grids, where the 17 `nowrap` rules and the real column
pressure live, were never reachable in this session. Re-run the load-time 200% check against the
real app before treating the Planning Workspace half of G3 as closed.
