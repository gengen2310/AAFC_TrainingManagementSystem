# Touch control scale — design

**Date:** 2026-09-01
**Status:** approved in brainstorming; awaiting spec review
**Branch:** `design/touch-targets` (isolated — must not be merged to `main`
while another session is working it)

## Problem

A gate audit of deployed staging (build `5a858df4`, `docs/design/01-staging-gate-audit.md`)
found G5 failing:

| profile | threshold | judged | fail |
|---|---|---|---|
| Pixel 7 | 44×44 touch | 83 | **78** |
| Desktop Chrome | 28×28 pointer | 187 | 27 |

The product owner has confirmed the interface **is used regularly on tablets**,
so the touch column is a real failure and not a theoretical one.

Three further facts shape the design:

1. **The failures come from nine CSS classes, not 78 elements.** `.btn`, `input`,
   `.tb-btn`, `.tab-btn`, `select`, `.lh-btn`, `.btn-lnk`, `.ff-ro` — and
   `.skip-link`, which is a measurement artefact (see Exceptions).
2. **`.btn` alone has five different heights** (28, 33, 35, 37, 39). There is no
   control scale to restore; there is one to establish.
3. **28px was deliberate.** It appears in `.btn`, `.btn-sm`, `.btn-xs`,
   `.lh-btn` and the compact-density override, and carries the comment
   `/* AUDIT-2026-08 G5: min-height alone left icon buttons 25px wide */`. A
   previous G5 pass settled on the pointer threshold. Touch was never in scope.
   The owner does not recall it as a density decision, so it is treated as
   unowned and re-derived here rather than defended.

There is no `@media (pointer: coarse)` anywhere in the file.

## Goals

- Every interactive control reaches 44×44 on both axes, on every device.
- One control scale, expressed in tokens, so the next control added has
  something to follow.
- Boundaries that identify a control meet WCAG 1.4.11 (3:1).
- Each control class is measured against the gates **in isolation, before**
  it reaches a screen.

## Non-goals

- Rebuilding controls that already pass. This is a scale change, not a
  component rewrite.
- The Planning Workspace (`frontend/`). Connected frontend only.
- Gates the audit did not measure: G2, G6, G8, G9, G10, G12.

## Decisions taken during brainstorming

| question | decision |
|---|---|
| Is touch real? | Yes — regularly used on tablets |
| Intent behind 28px | Not recalled; treat as unowned |
| Border contrast | Match what WCAG requires |
| Appetite | Rescale the design system properly |
| Compact density | **Retire entirely** |
| Table rows | Rows grow too — consistency wins |
| Trigger | One unconditional scale (see below) |
| Input height | 52px |
| Component lab | Permanent fixture in the repo |

### On the trigger

"Retire Compact" and "rows grow too" together imply a **single unconditional
scale**, which leaves a `pointer: coarse` query nothing to switch between. The
query is therefore **not** the delivery mechanism. It is reserved for places a
touch device needs *more* than the base — currently only `--ctl-gap` in dense
action groups, where adjacent targets need separation a mouse does not require.

## The control scale

```css
--ctl-min:       44px;   /* floor for ANY interactive control, BOTH axes */
--ctl-h:         44px;   /* default control height                      */
--ctl-h-lg:      52px;   /* text inputs, selects, textareas             */
--ctl-pad-x:     16px;   /* = --sp-md                                    */
--ctl-pad-x-sm:  12px;   /* = --sp-sm                                    */
--ctl-gap:        8px;   /* = --sp-xs — minimum gap between adjacent targets */
```

44 sits on the existing 4px spacing grid (`8/12/16/20/24`), so the touch floor
and the spacing rhythm agree without a parallel system.

### The governing rule

> A control variant may change padding, font-size, weight and colour.
> It may **never** reduce the hit size below `--ctl-min`.

This is what `.btn-xs` violated: a *visual* variant that also shrank the target
to 28×28. Under this rule it keeps its small type and tight padding and still
occupies 44×44 — small-looking, not small-to-touch.

### Class mapping

| class | current | after |
|---|---|---|
| `.btn` | `padding:9px 16px; min-height:28px` | `min-height:var(--ctl-h); padding:0 var(--ctl-pad-x)` |
| `.btn-sm` | `padding:6px 12px; min-height:28px` | `min-height:var(--ctl-min); padding:0 var(--ctl-pad-x-sm); font-size:var(--fs-xs)` |
| `.btn-xs` | `padding:4px 9px; min-height:28px; min-width:28px` | `min-height:var(--ctl-min); min-width:var(--ctl-min); font-size:var(--fs-xs)` |
| `.tb-btn` | `padding:4px 12px; min-height:28px` | `min-height:var(--ctl-min); padding:0 var(--ctl-pad-x-sm)` |
| `.tab-btn` | `padding:8px 14px` (37px) | `min-height:var(--ctl-h); padding:0 var(--ctl-pad-x-sm)` |
| `.lh-btn` | `min-height:28px; padding:3px 8px` | `min-height:var(--ctl-min); min-width:var(--ctl-min)` |
| `.btn-lnk` | `padding:0 2px` (28px) | `min-height:var(--ctl-min); padding:0 var(--ctl-pad-x-sm)` |
| `input`, `select`, `textarea` | `min-height:28px` | `min-height:var(--ctl-h-lg)` |
| `.ff select/input/textarea` | `padding:9px 11px` | `min-height:var(--ctl-h-lg); padding:0 var(--ctl-pad-x-sm)` |
| `.ff-ro` | inherits (35px) | inherits `--ctl-h-lg` |

Ten heights collapse to two, plus a floor.

`input[type=checkbox]` and `input[type=radio]` are `18×18` and are **not**
resized — a checkbox's box is not its target. They receive a `--ctl-min` hit
area via the label wrapper instead (see Implementation notes).

### Adjacent targets

The desktop pass found **23 controls large enough but not isolated** — session
actions (`Mark delivered` / `Cancel` / `Edit`) sitting edge-to-edge, so a tap
near a boundary activates the neighbour. Size does not fix this; separation
does. Action groups get `gap: var(--ctl-gap)`.

## Component lab

`connected-frontend/component-lab.html` — one static file, no build, no
backend, permanent.

It renders every control class across every axis that can change its
measurement:

| axis | values |
|---|---|
| class | the ten above |
| state | resting, hover, focus-visible, disabled, active |
| content | short label, long label, icon-only, numeric |
| context | on `--surface`, on `--bg`, on the dark toolbar, inside a table row |

**It must not copy the SPA's CSS.** It links the same style block, so drift
presents as a visibly broken lab rather than a silently stale one. Since the SPA
is a single file with an inline `<style>`, the lab extracts that block at load
time via `fetch('index.html')` and injects it — no build step, no duplication.

`tools/design-audit/*.mjs` gain a `--url` argument so the existing scripts point
at the lab.

**Why this earns a permanent place:** every measurement taken so far covered only
states that happened to be on screen as `sqn_admin`. **Disabled, hover, active
and focus have never been measured at all**, though the contrast register lists
them as distinct appearance states. The lab makes them reachable.

## Retiring Display Size

Six deletions:

1. 10 CSS rules matching `body[data-density="compact"]`
2. The `#dens-card` block in Unit Setup
3. `_setDensity()` and its two boot-time calls
4. The `localStorage` write of `displayDensity`

The stale key remains inert in existing browsers; nothing reads it once the
attribute is gone. No cleanup code is added to delete something harmless.

**No test references density** — verified by grep across `frontend/e2e`,
`frontend/e2e-connected` and `backend/tests`.

**Consequence, on the record:** anyone currently on Compact receives the larger
scale at next load, with no way back. This is a **capability removal (G8)**,
taken deliberately by the product owner on 2026-09-01, because a setting that
can drive controls below the touch floor contradicts a single-scale system.

## Borders

| token | value | on `#fff` | uses | after |
|---|---|---|---|---|
| `--border` | `#d1dce8` | 1.39:1 | 147 | `#7d8ea8` — **3.33:1** on white, **3.12:1** on `--bg` |
| `--border-light` | `#e4edf5` | 1.18:1 | 22 | unchanged |

`#7d8ea8` is the first measured candidate clearing 3:1 against *both* surfaces
the app paints on (`#ffffff` and `#f4f8fc`).

`--border-light` is left alone deliberately. WCAG 1.4.11 covers *"visual
information required to identify user interface components and states"* and
excludes purely decorative graphics. `--border-light` is hairline dividers and
the `.faq-cat-name::after` rule — decoration, exempt by the standard's own
scope. Darkening it would be stylistic, not compliance.

The high-contrast overrides at `--border:#555555` / `--border-light:#777777`
already exceed 3:1 and are unchanged.

## Verification

Nothing rolls out to a screen until its class passes in the lab.

**Per class, in the lab:**

| gate | method |
|---|---|
| G5 | `g5-hit-targets.mjs` — 44×44 both axes, hit-tested, ancestors not counted |
| G1 | `g1-contrast-rendered.mjs` — gradient-aware, every state |
| G4 | focus ring present and visible in `focus-visible` |
| G3 | 200% text — no clipping, no overflow |
| — | long label does not overflow or truncate the target |

**Then, on a screen:**

- Re-run the full audit against local, then staging after deploy.
- G1, G3, G4, G11 must not regress from their current PASS.

**Targets, stated so they cannot be quietly missed.** The raw audit counts
include items this spec declares exempt, so the goal is not "0 failures" — it is
zero *non-exempt* failures, with every exemption named:

| | judged | fail now | exempt | target |
|---|---|---|---|---|
| Touch (44px) | 88 | 83 | 5 skip-link + checkbox/radio boxes | **0 non-exempt** |
| Pointer (28px) | 187 | 27 | 5 skip-link | **0 non-exempt** |

Of the 27 pointer failures, only **4 controls are genuinely below 28px**. The
rest are large enough and still not reachable at their edges — 5 nav items at
`219×41` among them. Those are **adjacency and overlay**, which `--ctl-gap` and
the lab's `focus`/`hover` states address; raising heights alone would not move
them. Any pointer failure remaining after the scale change must be re-diagnosed
as spacing or stacking, not assumed to be size.

A reported count that has not had its exemptions subtracted is not a result.
- Backend suite and `frontend` vitest unchanged (78 tests) — this is CSS and
  markup only, no behaviour change.

## Exceptions

| item | why it is not a failure |
|---|---|
| `.skip-link` (5 counted) | `position:absolute; left:-9999px` — off-screen until focused. My audit's visibility filter excluded elements off-screen *vertically* but not *horizontally*, so it was judged and failed on all five pages. Corrected count: **78**, not 83. |
| `input[type=checkbox/radio]` | An 18×18 box with a 44px hit area via its label is correct; growing the box itself would be wrong. These appear inside the 83 raw touch failures (the `input` class spans heights 16–39) and must be subtracted before any result is quoted. |
| `--border-light` (22 uses) | Decorative dividers, outside WCAG 1.4.11's scope. |

## Risks

| risk | mitigation |
|---|---|
| A 44px rhythm shows ~⅓ fewer table rows | Accepted explicitly by the owner ("rows grow too — consistency wins"). Measured before/after row counts recorded at rollout. |
| Retiring Compact removes a preference | Recorded above as a deliberate G8 removal, dated and attributed. |
| Darker borders make the UI harsher | Confined to `--border`; decorative hairlines untouched. Reversible in one token. |
| The lab drifts from the SPA | It reads the SPA's own style block rather than copying it. |
| Another session is working `main` | All work stays on `design/touch-targets`. No push to `main` without the owner saying so. |

## Out of scope

- The Planning Workspace.
- G2, G6, G8, G9, G10, G12 — they need judgement or a baseline, not a script.
- The three flaky Firefox/WebKit tests (`docs/final/11-browser-matrix.md`).
- The 60 remaining schema-parity divergences.
