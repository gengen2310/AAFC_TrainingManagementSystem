# G3 — text enlargement: mechanism proved, migration planned

**Status:** pilot landed (`tokens.css`, `base.css`, `components.css`). The rest is planned,
not done. G3 remains **FAIL** until the migration completes.

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

| Target | font-size declarations | Risk |
|---|---|---|
| `planning.css` | 124 | **high** — 13 fixed `height`, 5 `min-height`, 17 `nowrap`, 13 `overflow:hidden` |
| `layout.css`, `print.css` | 6 | low |
| Planning Workspace `.tsx` `fontSize` props | 371 | medium — inline, invisible to CSS tooling |
| Main TMS `<style>` | 158 | medium |
| Main TMS inline / JS | 801 | **high** — inline, template-literal generated |

## Order, and why

1. `layout.css` + `print.css` — trivial, finishes the Planning Workspace stylesheets.
2. **`planning.css` with a layout pass, not just a find-and-replace.** This is where the work
   actually is. Converting the type without addressing the fixed heights and `nowrap` will
   produce clipping instead of scaling — a different failure, not a fix. Each of the 13 fixed
   heights needs to become `min-height`, and each `nowrap` justified or removed.
3. Planning Workspace `.tsx` props — mechanical once the scale exists; prefer moving them into
   CSS classes rather than swapping one inline literal for another.
4. Main TMS `<style>` block.
5. Main TMS inline styles — largest and riskiest, much of it generated inside template
   literals. Treat as its own piece of work.

The two frontends are deployed separately and must be converted separately; a fix applied to
one has three times now failed to reach the other.

## Coverage of the pilot measurement

The "0 clipped, 0 horizontal overflow at 200%" result is from a **synthetic probe page**
carrying the components in isolation. It is not a statement about the application. The
clipping risk is concentrated in `planning.css`, which is not converted yet, and the
authenticated screens where the dense grids live were never reachable in this session.

Re-run the 200% check against the real app after step 2, and treat that as the real answer.
