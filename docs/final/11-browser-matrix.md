# Part 91 — browser matrix

**Date:** 2026-08-30 · Chromium 1228 · Firefox 1532 · WebKit 2311 (Playwright 1.61.1)

## What was actually wrong

The traceability row said "Chromium only — Firefox and WebKit unrun". Half right.
Both `playwright.config.ts` (Planning Workspace, 25 specs) and
`playwright.connected.config.ts` (connected frontend, 44 specs) have **declared
chromium, firefox and webkit projects all along**, and all three browser binaries
are installed. The matrix was never missing. It had simply never been run, so
nobody knew what it would say.

Four connected-frontend specs were run across all three browsers against an
isolated backend and static server, so the run could not disturb anything else
on the machine.

## Result

| run | passed | failed | flaky |
|---|---|---|---|
| baseline, before fixes | 57 | **6** | — |
| after fixes, `--retries=1` | **60** | **0** | 3 |

**No browser-specific product defect was found.** The six baseline failures were
the same two tests failing identically on all three browsers — a
cross-browser-consistent problem, which is the opposite of what a matrix is
usually looking for.

## The two deterministic failures were tests that tested nothing

`VIS-04: pressing Enter / Space on a nav item` selected
`.nav-item[data-page='parade-nights']`. **The nav items have never had a
`data-page` attribute** — they are built as
`<div class="nav-item" role="link" tabindex="0" onclick="nav('parade-nights')">`.
The locator matched nothing, so the tests failed at the first `toBeVisible` and
had never once exercised the keyboard path they were written to protect.

The keyboard path itself is fine. A delegated handler activates any focused
`.nav-item` on Enter or Space, and once the selectors were repaired the tests
pass on all three browsers. The tests now select by role and accessible name
rather than an implementation hook, which also asserts the name (G11).

## One real accessibility defect, found on the way

`<div class="nav-items-wrap" role="link">` — the scrolling container for the
whole menu (`flex:1; overflow-y:auto`), announced to assistive technology as a
link. No `href`, no handler, no `tabindex`, no accessible name. A screen reader
met a nameless link wrapping the entire navigation.

The role is removed. The real links are the `.nav-item` children, which keep
theirs, and the surrounding `<nav class="sidenav">` already provides the
landmark.

## The finding that matters for CI

Three tests are **flaky on Firefox and WebKit** and pass on retry:

- `VIS-04: visible nav items have tabindex=0 after login` (races
  `applyNavScope()`, which sets tabindex after login resolves)
- `HARD-04: .btn:focus-visible outline rule is present in the stylesheet`
- `HARD-09: Escape key cancels the promptText() modal`

Repeated runs of the same spec produced a **different** failing set each time,
which is how they were identified as flaky rather than failing. None reproduced
on chromium.

That is the real cost of having run chromium only: the flakiness is not new, but
nothing had ever surfaced it. Turning the matrix on in CI without addressing
these three would produce a suite that fails intermittently for reasons
unrelated to the change under test — the fastest way to teach a team to ignore
a red build.

## Not covered

- **Four of 44 connected-frontend specs**, and none of the 25 Planning Workspace
  specs, were run across the matrix. This establishes that the matrix runs and
  what it finds; it is not a full three-browser pass.
- **Mobile projects.** `playwright.config.ts` declares desktop devices only; the
  deploy script references a `--project=mobile` (Pixel 7) that no config in the
  repository defines.
- **The three flaky tests are not fixed**, only identified. Each needs a
  condition to wait on rather than a longer timeout.
