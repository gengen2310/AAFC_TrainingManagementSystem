# Gate coverage, and four numbers that were wrong

**Date:** 2026-09-01 · **Target:** local stack (`connected-frontend` + backend on
`127.0.0.1:8100`) · **Scripts:** `tools/design-audit/`

This document exists because `01-staging-gate-audit.md` reported a set of PASSes
that were true about what was measured and misleading about the application. The
gates were sound; their coverage was not, and nothing in the output said so.

## What the earlier audit actually covered

| gate | screens it measured | screens that exist |
|---|---|---|
| G1 contrast | 5 | 24 |
| G3 / G11 | 5 | 24 |
| G4 keyboard | 1 | 24 |
| G5 hit targets | 5, and only ever at one threshold per device profile | 24 |

Three defects shipped behind that:

- **14 nav items at 214×41.** The 44px touch threshold ran only on a Pixel 7
  profile, where the sidenav is collapsed behind the hamburger, so those
  controls never rendered. The desktop profile only ever asked for 28px, which
  41 passes. Found by opening the app on a laptop.
- **Weekly Program unstyled on screen.** Every rule giving that table structure
  sat inside `@media print`; `weekly-program` was in no page list.
- **7 controls below the floor** on `activities`, `service-desk`, the login
  screen and the rich-text toolbar — none of which any gate had opened.

## Four wrong numbers, and why each was wrong

**1. "All `min-height:28px` literals migrated; grep returns 0."**
The grep matched only the unspaced spelling. Two rules wrote
`min-height: 28px` with a space and shipped at 28px. Now tested by matching on
property and value rather than one way of typing it, with no exception list.

**2. "0 hit-target failures" (G5, first pass).**
Correct for the six pages measured. Across all 24 there were seven more.
Coverage was the whole difference.

**3. "38 controls not reachable — measurement-limited, do not quote."**
Diagnosed rather than dismissed. 11 were the local debug bar (fixed to the
viewport bottom, renders only on localhost, `index.html:6127`) occluding the
app — a failure that exists only in the measuring rig. 10 were sub-pixel
boundary resolution at a probe point one pixel inside the edge. **1 was real:**
`.yn-arrow::after` and `.yn-display::after` used `inset:-4px -6px`, extending
each control's hit area 6px sideways into its neighbour, so the rightmost 6px
of the Previous-year arrow activated the year display. The arrow measures a
clean 44×44 throughout — no box measurement could ever have found it.

That extender was itself a fix that outlived its problem: it was added when
these controls were below the target size, and once both carried 44px on their
own box it added no reach and only overlapped.

**4. "G4 keyboard PASS — 33 controls reached."**
It tabbed 80 times on whatever page loaded first and never navigated. Across 24
pages it reaches 182. Separately, its escape-hatch check queried `.modal`, but
the id lives on `.modal-bg`, so it returned "no modal in DOM" every run and
never pressed Escape — a check that always skips, reported as a covered case.

## The common shape

Every one of these produced a confident result about something never examined:
an unlisted page, an unspaced spelling, a collapsed sidenav, a check that always
skipped, a second implementation of a gate that silently disagreed with the
first. None of them looked like a failure in the output; they looked like
success.

The fix in each case was the same — make the measurement report its own
coverage. Every script now prints how many pages it measured, names any that
rendered nothing, and prints how many controls needed the sub-pixel tolerance.

## Current state — every role, every page

Local stack, all 24 routable pages, one run per seeded role. `judged` and the
failure columns are the Desktop (touch) profile at the 44px threshold; the
Pixel 7 and pointer profiles were also run and are also clean.

| role | controls judged | box < 44 | unreachable | passed within 2px | G1 nodes | G1 fail | unresolved |
|---|---|---|---|---|---|---|---|
| sqn_admin | 527 | 0 | 0 | 10 | 2790 | 0 | 0 |
| sqn_general | 443 | 0 | 0 | 10 | 2491 | 0 | 0 |
| wing_admin | 431 | 0 | 0 | 9 | 3607 | 0 | 0 |
| wing_viewer | 386 | 0 | 0 | 9 | 2782 | 0 | 0 |
| national_admin | 439 | 0 | 0 | 9 | 3004 | 0 | 0 |
| national_viewer | 413 | 0 | 0 | 9 | 2510 | 0 | 0 |
| system_admin | 451 | 0 | 0 | 9 | 3348 | 0 | 0 |
| auditor | 291 | 0 | 0 | 9 | 2307 | 0 | 0 |

3381 control-measurements and 22,839 text nodes, no failures in either gate at
any role. The `passed within 2px` column is the sub-pixel edge allowance, held
separate on purpose: it is nine or ten flush-stacked `.tab-btn` controls, and if
that number starts climbing the tolerance is masking something.

Coverage note: the role matters. `wing_admin` alone brings up `+ Create Wing`
and `+ Create Squadron / Specialist` — controls no single-role run had ever
measured. The earlier audits were all `sqn_admin`, for whom nine of the 24 pages
render nothing at all.

## Standing limitations

- **Hit-testing cannot answer for controls clipped by a scroll ancestor or the
  viewport edge.** Those are skipped and the skip count is printed. They are not
  counted as passes.
- **Role coverage requires re-running per role.** Nine of the 24 pages render
  nothing for a squadron admin. `AUDIT_ROLE` / `AUDIT_CODE` exist for this; the
  seeded demo codes cover every role locally.
- **The 2px sub-pixel tolerance is an allowance, not a pass.** It is counted and
  printed separately so it cannot quietly widen.
