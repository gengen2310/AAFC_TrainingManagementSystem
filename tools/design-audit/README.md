# Design gate measurement against a deployed environment

These measure apple-design gates on a **running** build, which is the only place
some of them are observable at all. Point them at staging:

```
cd tools/playwright-staging          # for its @playwright/test
STAGING_SQN_ADMIN_CODE=… node ../design-audit/g1-contrast-rendered.mjs
STAGING_SQN_ADMIN_CODE=… node ../design-audit/g5-hit-targets.mjs
STAGING_SQN_ADMIN_CODE=… node ../design-audit/g3-g11-text-and-names.mjs
STAGING_SQN_ADMIN_CODE=… node ../design-audit/g4-keyboard.mjs
```

They authenticate through the API rather than the sign-in form, and only read.

## Why these exist alongside scripts/css_audit.py

`css_audit.py` reads stylesheets. On this codebase it resolves 218 pairs and
leaves **717 unresolved**, because it cannot follow `color-mix()`, `data-theme`
blocks, or inline styles. The one real contrast failure found in the 2026-09-01
audit was in an inline `style="color:…"` — invisible to it by construction.

## Two measurement traps, both hit while writing these

**Backgrounds.** Resolving a background by walking up for the first opaque
`background-color` walks straight past a gradient, which lives in
`background-image` with a transparent `background-color`. That reported white
text on the navy `.pn-hdr` gradient as white-on-white, 1:1 — and produced 174
false failures out of 1035 nodes. Gradients now contribute every colour stop and
text is scored against the worst one. Corrected count: 1.

**Hit testing.** Probing with `elementFromPoint` and accepting a hit on an
*ancestor* counts a container as if it were the control. Tapping the container
does nothing, so an ancestor must not count. That flaw made 44 undersized
controls look like passes.

Both produce confident, plausible, wrong numbers. Sample-check anything these
report before quoting it.

## What these numbers do and do not cover (2026-09-01)

**Box size is the trustworthy figure.** Every visible control's width and
height are read with `getBoundingClientRect`, which needs no scrolling and no
hit-testing, so the count covers every control the page rendered. This is the
figure the control-scale work moved, and it now reads 0 below threshold on all
three profiles.

**The hit-test probe is now trustworthy, and it earns its place.** It was
reporting 38 failures on controls that measured well above the threshold, and
the honest reading at the time was "do not quote this as a defect count".
Diagnosing all 38 rather than dismissing them found three distinct causes:

- **11 were the harness occluding the app.** The debug bar is fixed to the
  bottom of the viewport and renders only on localhost (`index.html:6127`), so
  a local run had it covering whatever sat at the fold -- 8px into a nav item,
  two row buttons entirely. It exists on no deployed environment. The scripts
  now hide it before measuring.
- **10 were sub-pixel boundary resolution.** Probing at exactly `size/2 - 1`
  lands one pixel inside the edge, where rounding decides which of two adjacent
  elements answers. Ten flush-stacked `.tab-btn` controls failed there and
  passed two pixels further in. The strict probe still runs first; anything
  rescued is counted and printed as "passed only within 2px" so the allowance
  stays visible rather than being folded into the pass count.
- **1 was a real defect that no box measurement could have found.**
  `.yn-arrow::after` and `.yn-display::after` used `inset:-4px -6px`, extending
  each control's hit area 6px sideways into its neighbour, so the rightmost 6px
  of the Previous-year arrow activated the year display. The arrow measures a
  clean 44x44 the whole time. The extenders dated from when these controls were
  below the target size; once both carried 44px on their own box, the extenders
  added no reach and only overlapped. Removed.

That last one is the argument for keeping the probe: box size and reachability
are different questions, and only the second catches a control that is the
right size and still not fully clickable.

**Three viewport profiles, and the reason there are three.** The first version
ran two — Pixel 7 at 44px and desktop at 28px — and reported zero failures
while fourteen `.nav-item` controls sat at 41px. Nothing had measured a
desktop-width layout against the 44px touch floor: the phone profile collapses
the sidenav behind a hamburger so those controls never rendered, and the
desktop profile only ever asked for 28px. The gap was invisible from inside the
tool and was found by opening the app on a laptop. `Desktop (touch)` closes it.

The general lesson is worth more than the fix: **a measurement that never
renders a control reports it as passing.** Check coverage — how many controls
were judged — before believing a failure count.

## Coverage, and why it is printed next to every result (2026-09-01)

The app has 24 routable pages (`id="page-*"` in `connected-frontend/index.html`).
Before this date the scripts covered six, five, five and one respectively, and
none of them said so. Three separate defects shipped behind that silence:

| what shipped | why no gate saw it |
|---|---|
| 14 nav items at 214x41 | the 44px threshold only ever ran on a phone profile, where the sidenav is collapsed |
| Weekly Program unstyled on screen | `weekly-program` was in no page list |
| 7 controls below the floor | `activities`, `service-desk`, the login screen and the rich-text toolbar were in no page list |

Two more measurement bugs were found the same way:

- **`g3-g11` carried a second G5 implementation** that disagreed with
  `g5-hit-targets.mjs` — 8 "too small" against 0 — because it never received the
  checkbox exemption or the scroll-clipping fix. It has been removed. One gate,
  one implementation.
- **G4's escape-hatch check queried `.modal`**, but the id lives on `.modal-bg`,
  so it returned "no modal in DOM" every run and never pressed Escape. A check
  that always skips reads as a covered case.

Every script now prints how many pages it measured and names any that rendered
nothing, so a silent page has to announce itself. Several pages are role-gated
and will legitimately render nothing for a squadron admin — run under more than
one role to cover them.

### Current state, all 24 pages, local stack, sqn_admin

```
G1  contrast     0 failures of 2790 text nodes, 0 unresolved
G3  200% text    0 clipped elements, no horizontal overflow, 24/24 pages
G4  keyboard     182 controls reached, 0 without a focus indicator,
                 Enter navigates, Escape closes a modal
G5  hit targets  0 below threshold on all three profiles, 527 judged
G11 semantics    0 unnamed of 833 controls
    print        computed styles identical (print-parity.mjs)
```

The G5 hit-probe residual is 0. It was 38; all 38 were diagnosed rather than
dismissed, and the causes are recorded above -- 11 the harness occluding the
app, 10 sub-pixel edge resolution, 1 a genuine overlapping hit-area extender.
The "passed only within 2px" line reports how many controls needed the
sub-pixel allowance, so the tolerance stays visible.
