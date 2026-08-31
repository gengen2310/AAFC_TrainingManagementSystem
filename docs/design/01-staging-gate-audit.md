# apple-design gate audit — deployed staging

**Date:** 2026-09-01 · **Target:** `aafc-tms-frontend-staging.up.railway.app`,
build `5a858df4` · **Role:** `sqn_admin` · **Screens:** dashboard, parade-nights,
curriculum, settings, facilitators

Measured against the running build, not the source. Scripts in
`tools/design-audit/`. Every number below came from one of them.

```
Contrast (G1)         PASS — 1035 text nodes, 1 failure, now fixed
Text at 200% (G3)     PASS — 5/5 screens, no h-overflow, no clipping
Keyboard (G4)         PASS — 35 controls reached, 0 without a focus indicator
Hit targets (G5)      FAIL — 83 of 88 below 44×44 at touch; 27 of 187 at pointer
Semantics (G11)       PASS — 329 controls, 0 without an accessible name
Status                NOT COMPLETE — G5 failing
```

## G1 — contrast · PASS (after one fix)

1035 rendered text nodes, 0 unresolved. **One** failure:

| selector | ratio | required |
|---|---|---|
| `td.cls-num` (a coverage percentage) | **3.35:1** | 4.5 |

The colour was `--warn` (`#c97a00`), applied through an inline
`style="color:…"`. The codebase already knew this colour fails as text — the
token line says so: *"DES-H04: --warn fails 3.1:1; --warn-text passes"* — but
one function coloured both the progress **bar** (non-text, 3:1, fine at 3.35)
and the percentage **figure** (text, 4.5, not fine).

Split into `col()` for fills and `colText()` for text. Measured on white:

| token | as text | verdict |
|---|---|---|
| `--warn` `#c97a00` | 3.35:1 | fails — was in use |
| `--warn-text` `#7a5200` | 6.92:1 | now in use |
| `--ok` `#1a7f4b` | 5.02:1 | unchanged |
| `--red` `#e51937` | 4.64:1 | unchanged |
| `--muted` `#5c6a76` | 5.56:1 | unchanged |

**Why the stylesheet scan missed it.** `scripts/css_audit.py` resolves 218 pairs
and leaves **717 unresolved** — it cannot follow `color-mix()`, `data-theme`, or
inline styles. This failure was an inline style. A register that reports "0
failures" over the pairs it could build is not saying the interface passes.

## G3 — text at 200% · PASS

All five screens at `font-size: 200%`: no horizontal overflow, no clipped
elements. Coverage note: clipping is detected as `overflow:hidden` with content
taller than the box, which catches the common case and not every one.

## G4 — keyboard · PASS

35 distinct controls reached by Tab; **0** focused without a visible indicator.
A primary workflow completes on the keyboard alone: focus a nav item, press
Enter, land on the page. The Escape-closes-a-modal probe was inconclusive (no
modal in the DOM at that point); `e2e-connected/accessibility-hardening.spec.ts`
covers it as HARD-05/HARD-09.

## G5 — hit targets · **FAIL**

| profile | threshold | judged | fail | rate |
|---|---|---|---|---|
| Pixel 7 | 44×44 (touch) | 88 | **83** | 94% |
| Desktop Chrome | 28×28 (pointer) | 187 | 27 | 14% |

Not a handful of stragglers — **the interface is drawn to a ~28px control
scale**. That is a deliberate, coherent choice for a pointer, and it is below
the touch threshold nearly everywhere. Recurring examples:

```
179×41  Skip to main content        91×28  Search ⌘K
 76×28  Sign Out                    86×37  Refresh
 93×28  Learning Hub                18×28  on   (a toggle)
214×41  every sidenav item          28×28  Mark/Cancel/Edit session actions
```

`rescued by a larger hit area: 0` — nothing uses the `::after` inset trick the
year selector uses, so no control is bigger to the finger than it looks.

**This is a product decision, not a defect to patch.** Raising every control to
44px changes the density of a deliberately dense interface. The options are (a)
accept it and state that touch is unsupported, (b) raise targets only on the
touch breakpoint, (c) extend hit areas with `::after` and leave the visuals
alone. (c) preserves the density and is the smallest change, and is what the
year selector already does.

## G11 — semantics · PASS

329 controls across five screens, **0** without an accessible name.

## Not measured

- **G2 non-colour states, G6 gesture alternatives, G8 capability preservation,
  G9 feedback/save state, G10 adaptive layout, G12 data integrity** — need
  judgement or a comparison baseline, not a script.
- **The Planning Workspace.** All of the above is the connected frontend only.
- **Roles other than `sqn_admin`**, and any screen behind a modal.
- **Every human test.** No 5-second test, first-click test, or task-completion
  study has been run. **HUMAN VALIDATION PENDING.**

## Two measurement traps hit while writing this

Both produced confident, plausible, wrong numbers, and both were caught by
sample-checking a finding against the actual DOM:

1. **Gradients.** Resolving a background by walking up for the first opaque
   `background-color` walks past a gradient, which lives in `background-image`.
   White text on the navy `.pn-hdr` gradient scored as white-on-white, 1:1 —
   **174 false failures of 1035**. Corrected to 1.
2. **Ancestor hits.** Accepting `elementFromPoint` landing on an *ancestor*
   counts a container as the control. Tapping the container does nothing. That
   flaw turned 44 undersized controls into passes.

The first would have reported a crisis that did not exist; the second would have
under-reported a real one by half.
