# Control scale rollout — measured result

**Date:** 2026-09-01 · **Spec:** `docs/superpowers/specs/2026-09-01-touch-control-scale-design.md`
**Measured against:** a local stack (seeded backend + the built SPA), before any deploy.
**Not deployed.** Branch `design/touch-targets`; staging is untouched.

## Result

| gate | before | after |
|---|---|---|
| **G5 touch — controls below 44×44** | **83** | **4** |
| G5 pointer — controls below 28×28 | 4 | 4 |
| G1 contrast | 1 fail of 1035 | **0 fail of 890** |
| G4 keyboard | 35 reached, 0 ringless | 33 reached, **0 ringless** |
| boundary-advisory borders | 37 | **29** |
| **component lab, per class** | — | **10/10 pass, 153 variants** |

The lab figure is the one that matters most: every control class passes hit,
size and overflow across resting / hover / focus / disabled / active and
short / long / numeric content. Disabled, hover, active and focus had never
been measured before it existed.

## The four residual touch failures

Named, not rounded away:

| control | size | status |
|---|---|---|
| toggle, ×2 | `18×44` | **real** — tall enough, 18px wide. Needs `min-width:var(--ctl-min)`. Not on the parade-nights screen; not yet located. |
| `Select parade night` checkbox | `16×16` | **exempt** — an 18px box with a 44px hit area via its label is correct, and that label wrapper now carries `--ctl-min`. |
| one further control | — | not individually identified |

The pointer count is unchanged at 4 because those four were never a height
problem — they are the same exempt checkbox class.

## What the rollout found that the spec did not

The spec said **nine classes**. That was wrong, and the error is instructive:
the inventory grouped controls by *the element's own first class name*, which
made three whole categories invisible.

| missed category | example | count |
|---|---|---|
| descendant selectors | `.fbar select, .fbar input` | 7 rules |
| `:has()` selectors | `label:has(> input[type=checkbox])` | 1 rule |
| inline styles in JS template strings | `style="…min-height:28px"` | 9 sites |

**20 further control rules**, found only by grepping the stylesheet for every
literal `min-height` under 44px after the nine were done.

One of them mattered more than the rest. `label:has(> input[type=checkbox])`
carried `min-height:28px` — it is the checkbox hit-area wrapper, the exact
mechanism the spec relies on when it exempts the 18×18 box. Shipping the
exemption without fixing that wrapper would have left checkboxes with **no**
compensating target, which is worse than where we started.

Every literal control height in the stylesheet is now a token: `grep -c
"min-height:28px"` returns 0.

## Density cost

Not measured. The curriculum list needs seeded curriculum rows at a tablet
viewport to compare fairly, and the local seed carries 13 items against
production's 214. The draft's estimate — eight rows becoming six, a 25%
reduction — stands as an estimate and is **not** confirmed here.

## Still to do

1. Locate and fix the `18×44` toggle (`min-width`).
2. Confirm the density cost against a realistic dataset.
3. Re-run every gate against staging once deployed.
