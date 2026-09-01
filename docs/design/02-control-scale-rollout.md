# Control scale rollout — measured result

**Date:** 2026-09-01 · **Spec:** `docs/superpowers/specs/2026-09-01-touch-control-scale-design.md`
**Measured against:** a local stack (seeded backend + the built SPA), before any deploy.
**Not deployed.** Branch `design/touch-targets`; staging is untouched.

## Result

| gate | before | after |
|---|---|---|
| **G5 touch — controls below 44×44** | **83** | **0** |
| **G5 pointer — controls below 28×28** | 22 | **0** |
| G1 contrast | 1 fail of 1035 | **0 fail of 890** |
| G4 keyboard | 35 reached, 0 ringless | 33 reached, **0 ringless** |
| boundary-advisory borders | 37 | **29** |
| **component lab, per class** | — | **10/10 pass, 153 variants** |

All counts are **non-exempt**: `g5-hit-targets.mjs` now subtracts the
checkbox/radio exemption itself rather than leaving a caveat for whoever quotes
the number. Two independent measurements — the audit script and a separate
sweep of all five screens — agree at zero.

Verified non-vacuous: re-running the sweep with the threshold raised to 999px
returns controls (`skip-link 179×44`, `btn-hamburger 44×44`), so an empty result
means "nothing undersized", not "nothing measured".

## Three fixes the first pass missed

Found by sweeping all five screens for anything under 44×44 rather than trusting
the class list:

| control | was | issue |
|---|---|---|
| `.btn` | `41×44` | **Systemic.** `padding:0 16px` plus a short label ("Edit") gives 41px WIDTH. The rule says both axes; only height was enforced. Every short-labelled button in the app was narrow. |
| `.ht` | `14×14` | Dashboard help buttons, sized in `em` and never in any class list. |
| `.skip-link` | `41px` | Exempt from the COUNT because it is off-screen at rest — but it is a real control once focused, and 41 is short. Exemption from measurement is not exemption from the requirement. |

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

1. **Confirm the density cost against a realistic dataset.** The local seed
   carries 13 curriculum items against production's 214, so the draft's
   estimate — eight rows becoming six, a 25% reduction — remains unconfirmed.
   It is the cost that was accepted when the decision was made, so it deserves
   a real measurement before rollout.
2. **Re-run every gate against staging once deployed.**
