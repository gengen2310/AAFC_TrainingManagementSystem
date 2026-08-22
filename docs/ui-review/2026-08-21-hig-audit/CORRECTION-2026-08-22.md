# Correction to the 2026-08-21 audit — the themes are reachable

**Issued:** 2026-08-22 · **Severity:** changes a finding's severity and reverses a recommendation

## What the audit got wrong

The audit stated that the Planning Workspace's `dark` and `hc` themes are unreachable —
"no code anywhere sets the attribute — no toggle, no `prefers-color-scheme` listener" — and
therefore classified their contrast failures as latent debt.

**That is wrong.** `frontend/src/layout/AppShell.tsx` ships a visible, cycling theme control:

```
frontend/src/layout/AppShell.tsx:14  const THEMES = ["light", "dark", "hc"] as const;
frontend/src/layout/AppShell.tsx:21  const applyTheme = (t: Theme) => { setTheme(t);
       localStorage.setItem("aafc_theme", t); document.documentElement.dataset.theme = t; };
frontend/src/layout/AppShell.tsx:44  <button ... onClick={() => applyTheme(THEMES[(THEMES.indexOf(theme)+1) % THEMES.length])}
```

All three themes are user-selectable from a header button, and the choice persists in
`localStorage` across sessions.

## Why the audit missed it

The check grepped for the attribute string `data-theme`. The code sets the theme through the
DOM `dataset.theme` property API, which never appears as that string in source. The grep
returned 0 for a correct reason, and the wrong conclusion was drawn from it.

**Method lesson:** a zero result from a string search is evidence about the string, not about
the behaviour. Any "nothing does X" claim needs a positive check of the mechanism — here,
loading the app and toggling — not just an absent match. Grep both `data-foo` and
`dataset.foo` when asking whether an attribute is ever set.

## Corrected measurements — browser-verified

Measured 2026-08-22 in Chrome against the real stylesheets (`tokens.css`, `components.css`,
`layout.css`, `planning.css`, `base.css`) with a 19-element probe, toggling
`document.documentElement.dataset.theme` exactly as `applyTheme` does. Light-theme results
reproduced the static resolver's numbers exactly, which cross-validates both.

| Theme | Elements probed | Failing | Reachable |
|---|---|---|---|
| `light` | 19 | 6 | yes — default |
| `dark` | 19 | **12** | **yes — theme button** |
| `hc` | 19 | 5 | **yes — theme button** |

### `dark` — 12 of 19 failing (live)

| Ratio | Need | Element | Pair |
|---|---|---|---|
| **1.22:1** | 4.5 | `.banner.proxy` | `#1d2733` on `#081426` |
| 1.80:1 | 4.5 | `.fts-item.fts-blue` | `#004b8d` on `#0d233e` |
| 2.42:1 | 4.5 | `.topbar`, `.brand`, `.btn`, `.pw-ctx`, `.pn-grid thead th` | `#ffffff` on `#51b0e3` |
| 2.59:1 | 4.5 | `.pw-block-warnings` | `#ff6b6b` on `#fff5f5` |
| 2.67:1 | 4.5 | `.fts-item.fts-purple` | `#7c3aed` on `#1f214c` |
| **2.78:1** | 4.5 | `.btn.danger` | `#ffffff` on `#ff6b6b` |
| 4.01:1 | 4.5 | `.fts-item.fts-warn`, `.fts-leave-now-tag` | `#a86600` on `#081426` |

Two new findings the static pass did not surface:

- **`.btn.danger` at 2.78:1** — the destructive-action button is among the least legible
  controls in dark mode.
- **`.pw-block-warnings` at 2.59:1** — its background `#fff5f5` is a light pink that was never
  remapped for dark, so a near-white chip sits on a dark page with red text on it.

### `.banner.proxy` fails in three of four reachable contexts

| Context | Ratio | Result |
|---|---|---|
| `light` | 4.51:1 | PASS — by 0.01 |
| `dark` | **1.22:1** | FAIL |
| `hc` | **1.57:1** | FAIL |
| `prefers-contrast: more` | **1.57:1** | FAIL |

The audit already ranked this first. It is worse than reported: the "you are acting as another
user" banner is illegible in every appearance context except the default one — and in that one it
clears 4.5:1 by **0.01**. There is no margin anywhere. Any future tweak to `--warning` breaks the
last context that still works.

## What changes in the recommendations

**Recommendation 7 is reversed.** The audit said "Delete or fix the dark/hc themes. Deleting is
legitimate and is the smaller change." Deleting is **not** legitimate — the themes are a shipped,
user-facing capability reached from a visible control, and `.claude/rules/capability-preservation.md`
forbids removing one without explicit user authorisation. They must be fixed.

**Priority changes.** The dark theme is a live user-facing defect, not latent debt. It moves from
step 7 to roughly step 3 — ahead of the token cleanup and the `DESIGN.md` reconciliation.

**The exceptions register entry is withdrawn.** The row reading "dark + hc themes, 22 failures —
no impact today" is void. There is impact today.

## What does not change

Gate verdicts G1 and G4 were already FAIL, so no gate flips. G3, G5, G6 and G11 are untouched by
this correction. The light-theme measurements and both frontends' stylesheet registers stand as
published — the live probe reproduced them exactly.
