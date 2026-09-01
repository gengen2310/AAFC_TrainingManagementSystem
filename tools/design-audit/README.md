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

**The hit-test probe is measurement-limited and should not be quoted as a
gate result.** It fires `elementFromPoint` at four points around a control and
can only answer for controls currently on screen and unclipped. Residual
failures it reports are, on inspection, controls that measure well above the
threshold and that a live browser probes cleanly at all four points — the
headless run simply had them at a scroll position where the probe landed on a
scroll container. Treat a hit-test failure as "go and look", never as a defect
count.

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
