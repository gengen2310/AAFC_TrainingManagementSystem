# AAFC TMS v17.1 — interface audit

**Date:** 2026-08-21 · **Method:** `apple-design` skill (HIG as measurable engineering standard)
**Scope:** both deployed frontends — `connected-frontend/` (Main TMS) and `frontend/` (Planning Workspace)
**Type:** baseline audit. No code was changed. No redesign was performed.

> **CORRECTED 2026-08-22 — see `CORRECTION-2026-08-22.md`.** This document originally stated that
> the Planning Workspace `dark` and `hc` themes are unreachable. They are not: `AppShell.tsx`
> ships a cycling theme button and persists the choice to `localStorage`. All three themes are
> user-selectable. Every passage below marked ~~struck~~ is superseded by the correction; the
> dark theme carries **12 live failures of 19 elements probed**, and recommendation 7 is reversed
> — the themes must be fixed, not deleted. Gate verdicts are unchanged.

---

## Status

```
AAFC TMS v17.1 interface audit
  G1  Text contrast          FAIL — 6 confirmed (Main TMS); Planning WS fails in ALL 3 user-
                             selectable themes: light 6/19, dark 12/19, hc 5/19 (corrected 2026-08-22)
  G2  Non-colour states      PASS — status families carry text labels (partial coverage, see below)
  G3  Text enlargement       FAIL — 1492 of 1528 font-size specifications px-locked (97.6%)
  G4  Keyboard operability   FAIL — focus indicator 1.92:1–2.42:1 everywhere; 3:1 required
  G5  Hit targets            FAIL — 11 rules below 28px pointer; inline-styled controls at ~16px
  G6  Gesture alternatives   FAIL — Planning WS session move is drag-only (Main TMS passes)
  G7  Comprehensible copy    PASS — 0 raw exceptions echoed to UI, 1 TODO marker
  G8  Capability preservation N/A  — baseline audit, nothing removed
  G9  Feedback / save state  PASS — aria-live ×9, role=status ×10, role=alert ×32, toast ×52
  G10 Adaptive layout        PARTIAL — 6 width breakpoints present; measured only at 1512px
  G11 Semantics              FAIL — 6 icon-only buttons with no accessible name (Main TMS)
  G12 Data integrity         NOT ASSESSED — needs an authenticated session with real data
  Principles: Purpose 4 · Agency 3 · Responsibility 2 · Familiarity 4
              Flexibility 2 · Simplicity 4 · Craft 2 · Delight 3   (mean 3.00)
  Status: NOT COMPLETE — G1, G3, G4, G5, G6, G11 failing
```

The bar used here — all gates pass, no principle below 3, mean ≥ 4.0 — is **[DERIVED]**, chosen for this
audit. Apple does not publish a numeric pass mark.

---

## Coverage — what was and was not measured

State this before the results, because "0 failures" describes what was measured, not the artifact.

| Channel | Measured | Method |
|---|---|---|
| Main TMS `<style>` CSS (967 lines) | **yes** | `css_audit.py`, 189 pair-evaluations |
| Planning WS stylesheets (6 files) | **yes** | custom theme-aware resolver, 830 evaluations |
| Main TMS **inline `style="…"` (1,613 attributes)** | **no** | not reachable by stylesheet tooling |
| Planning WS **inline `style={{…}}` (841 props)** | **no** | not reachable by stylesheet tooling |
| Authenticated screens (dashboard, matrix, planner) | **no** | no backend/credentials in this session |
| Sign-in screen, live DOM | **yes** | Chrome, 1512×861, computed styles |
| Narrow viewports | **no** | window resize did not propagate to viewport |
| Screen-reader announcement | **no** | HUMAN VALIDATION PENDING |
| Task completion / first-click | **no** | HUMAN VALIDATION PENDING — needs participants |

**The inline-style channel is the largest gap.** 2,454 inline style declarations across the two
frontends were not contrast-checked, and the spot checks that were done there (below) found failures
at a higher rate than the stylesheets did. Treat every stylesheet "PASS" as scoped to the stylesheet.

Unresolved within what *was* measured: 163 of 830 Planning Workspace evaluations could not resolve a
background (135) or foreground (28) from CSS alone.

---

## G1 — Text contrast

### Main TMS — confirmed failures

`css_audit.py` emitted 189 rows → 93 distinct text pairs, 15 failing. Six of those 15 were manually
verified as tool false positives (`.btn-out:hover`, `.btn-red-out:hover`, `.dash-sec-hero .dash-sec-hdr`,
`.dash-sec-hero .dash-sec-sub` — the script mis-resolved `color:white` and treated a `linear-gradient`
stop as an opaque fill). Nine remain; one more (`.yn-display input`, white-on-white-overlay over the dark
header) is also a false positive on inspection.

| Ratio | Need | Selector | Pair | Note |
|---|---|---|---|---|
| **1.04:1** | 4.5 | `.ht` | `#455560` on `#555555` | help trigger, 9px, `prefers-contrast: more` only |
| **2.42:1** | 4.5 | `#page-service-desk .sd-filter-bar button.active` | `#fff` on `#51b0e3` | active filter |
| **2.50:1** | 4.5 | `.hm-empty` | `#999` on `#f0f0f0` | heatmap empty cell |
| **2.77:1** | 4.5 | `.cm-cell-delivered_with_issue` | `#c97a00` on `#d4f0e3` | amber text on green fill |
| **3.95:1** | 4.5 | `.fac-sugg-pill.conflict` | `#e51937` on `#fde8e8` | 9px bold conflict pill |
| **4.15:1** | 4.5 | `.yn-chip-active` | `#1a7f4b` on `#d4f0e3` | close miss |

Advisory, not counted as gate failures — WCAG 1.4.3 exempts inactive controls:
`.btn-auth:disabled` and `.btn-disabled`, both `#b0b7bb` on `#f4f8fc` = 1.90:1. Confirmed live in the
browser on the sign-in screen.

`.ht` is the worst single element in the audit: 1.04:1 contrast, a 14×14px hit area, and 9px type — it
fails G1, G5 and the type floor simultaneously.

`.cm-cell-delivered_with_issue` deserves a second look beyond the ratio: it puts **amber text on the
green "delivered" fill**. Colour is carrying a contradictory signal even where the text label is correct.

### Planning Workspace — 10 distinct failures in reachable themes

Measured across all four appearance contexts with a purpose-built resolver, because `css_audit.py`
cannot evaluate `color-mix(in srgb, …)` and was emitting unresolved pairs as 1.0:1 "failures".

| Context | Same-rule pairs | Failing | Reachable? |
|---|---|---|---|
| `light` | 54 | 7 | **yes** — hard-coded in `index.html` |
| `prefers-contrast: more` | 54 | 5 | **yes** — OS setting |
| `dark` | 50 | **17** | ~~no~~ **YES — theme button in `AppShell.tsx`** |
| `hc` | 54 | 5 | ~~no~~ **YES — theme button in `AppShell.tsx`** |

Worst reachable failures: `.banner.proxy` 1.57:1 (contrast-more), `.fts-leave-now-tag` 3.24:1,
`.fts-item.fts-warn` 3.36:1, `.fts-item.fts-red` 3.63:1, `.fts-item.fts-ok` 3.94:1,
`.pw-block-warnings` 4.34:1, `.hm-na` 4.43:1, `.pn-cell-inner.break-cell` 4.46:1.

`.banner.proxy` is the one to fix first regardless of ratio ordering — it is the banner that tells an
operator they are acting **as another user**. Browser-verified across all four reachable contexts on
2026-08-22: `dark` **1.22:1**, `hc` **1.57:1**, `prefers-contrast: more` **1.57:1**, and `light`
**4.51:1 — passing by 0.01**. The system's honesty about who you are is the least legible thing on
screen in three contexts out of four, with no margin in the fourth.

### A token migration that stopped at the stylesheet

`DESIGN.md` records `--muted: #657380; /* darkened from original #6b7a87 */` — a deliberate WCAG fix.
The **pre-fix literal `#6b7a87` is still hard-coded 35 times across `.tsx` files.**

| Colour | on `#ffffff` | on `--bg #f4f8fc` | on `--surface-2 #f0f5fa` |
|---|---|---|---|
| `#6b7a87` (old, still in 35 places) | 4.41 **FAIL** | 4.14 **FAIL** | 4.02 **FAIL** |
| `#657380` (`--muted`, current) | 4.86 PASS | 4.56 PASS | 4.43 **FAIL** |
| `#6e7275` (`--muted-text-on-light`) | 4.85 PASS | 4.55 PASS | 4.43 **FAIL** |

The second finding is subtler and matters more: `DESIGN.md` claims `--muted-text-on-light` is
"≥4.5:1 on both `--surface` and `--bg`". That claim is **true as written** — and both replacement
greys still fail on `--surface-2`, which the claim never covered. `.hm-na` and
`.pn-cell-inner.break-cell` are live instances of exactly that pairing.

---

## G3 — Text enlargement · the most consequential failure

| Source | font-size specifications | px-locked | relative |
|---|---|---|---|
| Main TMS `<style>` | 160 | 158 | 0 |
| Main TMS inline / JS | 829 | 801 | 28 |
| Planning WS stylesheets | 168 | 163 | 5 |
| Planning WS `.tsx` `fontSize` props | 371 | 370 | 0 |
| **Total** | **1,528** | **1,492 (97.6%)** | **33 (2.4%)** |

Verified live: doubling the UA default font size from 16px to 32px changed the computed size of
**0 of 6** probed elements. `body` stayed 14px, `.btn-auth` 12px, `.login-report-link` 11px.

Page *zoom* still works and scales everything. But WCAG SC 1.4.4 is about **text** resize, and a user
who sets their browser font size to 200% gets no enlargement anywhere in either frontend. Given the
base scale is already 11–12px, this is the accessibility floor rather than a preference.

This is one root cause with ~1,500 call sites. It is the largest single piece of work the audit found,
and it cannot be fixed screen by screen.

---

## G4 — Keyboard operability · the focus ring fails everywhere it lands

Both frontends define a global focus ring in AAFC blue `#51b0e3`. WCAG 2.2 SC 1.4.11 requires 3:1 for
a non-text indicator.

| Indicator | Surface | Ratio | Result |
|---|---|---|---|
| `#51b0e3` solid | `--surface #ffffff` | 2.42:1 | **FAIL** |
| `#51b0e3` solid | `--bg #f4f8fc` | 2.27:1 | **FAIL** |
| `#51b0e3` solid | `--surface-2 #f0f5fa` | 2.21:1 | **FAIL** |
| `#51b0e3` solid | `--dark #002f65` | 5.44:1 | PASS |
| `rgba(81,176,227,.4)` inset (nav) | nav top `#001b3d` | 2.23:1 | **FAIL** |
| `rgba(81,176,227,.4)` inset (nav) | nav bottom `#002550` | 2.17:1 | **FAIL** |
| `rgba(81,176,227,.4)` inset (nav) | nav active `#003a7a` | 1.92:1 | **FAIL** |

Focus is *present* on every surface and *sufficiently visible* on only one — the dark navy header.
That is nearly the inverse of where users actually tab.

Two rules also suppress the ring at a specificity the global `:focus-visible` cannot beat
(`.yn-display input` at 0-1-1 and `.tag-input input` at 0-1-1 both set `outline:none`, versus
`:focus-visible` at 0-1-0), so those two controls have no ring at all.

**Positives:** a working skip link ("Skip to main content", verified live), `@media (forced-colors:
active)` with `outline: 3px solid Highlight`, and `@media (prefers-reduced-motion: reduce)` in both
frontends. The keyboard *path* through authenticated workflows was not walked — that needs credentials.

---

## G5 — Hit targets

Thresholds are **[HIG]**: 44×44pt touch, 28×28pt pointer, measured on the hit area.

Of 87 interactive-looking CSS rules, 40 had a derivable height. **11 fall below the 28px pointer floor**
(the script flagged 13; 2 were `.btn-hamburger span`, the decorative bars inside a hamburger button
rather than the target itself, and are excluded):

| Height | Selector | Frontend |
|---|---|---|
| 13px | `.chk-item input` | Main TMS |
| 14px | `.ht` | Main TMS |
| 14px | `.pw-layer-row input[type="checkbox"]` | Planning WS |
| 20px | `.chip` | Planning WS |
| 21.4px | `.pw-chip` | Planning WS |
| 22.2px | `.tag-input input` | Planning WS |
| 23.4px | `.mode-banner button` | Main TMS |
| 24.8px | `#page-service-desk .sd-filter-bar button` | Main TMS |
| 24.8px | `.app[data-density="compact"] .btn:not(.btn.sm)` | Planning WS |
| 26.8px | `.btn.sm`, `.app[data-density="compact"] .nav-item` | Planning WS |

Worse in the **inline-style** channel, which no stylesheet tool sees — computed from the declared
values **[CALCULATED]**:

- `index.html:12827–12828` — `<button style="font-size:10px;padding:1px 4px">▲</button>` / `▼` ≈ **16px tall**
- `index.html:12830`, `:12967` — `<button style="font-size:10px;padding:1px 6px">✕</button>` ≈ **16px tall**, a *delete* control
- `index.html:2295` — `<button style="font-size:11px;padding:2px 8px">✕</button>` ≈ **19px tall**

Live on the sign-in screen, **4 of 4** rendered controls were below the 44px touch minimum
(skip-link 41px, select 40px, Next 39px, Report an Issue 28px); all 4 passed the 28px pointer minimum.

**A remediation asymmetry worth naming.** Main TMS `.btn-xs` and `body[data-density="compact"] .btn`
both carry `min-height:28px` — someone ran a hit-target pass. The Planning Workspace's equivalent,
`.app[data-density="compact"] .btn`, has no such guard and computes to 24.8px. The fix landed in one
frontend only. That is the running cost of the deliberate two-frontend architecture in `CLAUDE.md`,
and it will recur on every future fix unless remediations are explicitly applied twice.

---

## G6 — Gesture alternatives · split verdict

**Main TMS passes, and does it well.** Session reorder offers `↑`/`↓` buttons with real `aria-label`s
("Move Session 3 to the previous period"), the drag handle is correctly `aria-hidden="true"`, and
there is a source comment at `index.html:9744` stating drag is "never the only way to reorder."
That is the standard the rest of the codebase should be held to.

**Planning Workspace fails.** In `ParadeNightBlock.tsx`, the session cell is `draggable`, has
`role="button"`, `tabIndex={0}` and an `onKeyDown` handler — but Enter only *opens* the session
detail; it does not move it. `onMoveSession` has exactly one call site (`EightWeekView.tsx:180`) and
is reachable only through `onDrop`. **Moving a session in the Planning Workspace requires a mouse
drag.** There is no keyboard, menu, or button path.

---

## G11 — Semantics

6 icon-only `<button>`s in the Main TMS render a symbol with no `aria-label`, no `title`, and no text:
4 × `✕` (close/delete), 1 × `▲`, 1 × `▼`. The Planning Workspace has 0.

Note the irony: the `▲`/`▼` at `index.html:12827–12828` are the *keyboard alternative* to a drag
interaction — and they are themselves ~16px tall and unnamed.

Overall aria usage is otherwise healthy: 207 `aria-label` in Main TMS, 75 in Planning WS; no
unlabelled controls at all on the live sign-in screen.

---

## G2, G7, G9, G10 — what passed

**G2 (non-colour states) — PASS, partial coverage.** The compliance matrix renders
`_CM_STATUS_LABEL[cell.status]` as visible text in every cell, so status survives greyscale. Verified
for `cm-cell-*` and `cal-cell-*`; other status families were not enumerated.

**G7 (comprehensible language) — PASS.** 0 instances of an exception message piped into `innerHTML`,
1 TODO/FIXME marker in the whole file. Error copy is authored, not echoed.

**G9 (feedback and save state) — PASS, structural.** `aria-live` ×9, `role="status"` ×10,
`role="alert"` ×32, toast machinery ×52, "Saving"/"Saved" vocabulary ×99 across both frontends.
Whether the *right* things announce at the *right* time needs an authenticated walkthrough.

**G10 (adaptive layout) — PARTIAL.** 6 width breakpoints (600/680/768/769/860/1000px), correct
`viewport` meta, no horizontal overflow at 1512px. Narrow-viewport behaviour is unverified.

---

## Design-system integrity

### `DESIGN.md` materially misdescribes the shipped UI

`DESIGN.md` opens by declaring itself "descriptive (what currently exists)" and the authority against
which no hex may be changed. For the primary navigation, **every documented property is wrong**:

| Property | `DESIGN.md` says | Code actually is |
|---|---|---|
| Sidebar width | 205px | **220px** |
| `.nav-item` colour | `var(--steel)` — dark on light | **`rgba(255,255,255,.9)` — light on dark** |
| `.nav-item` background | (light nav) | **`linear-gradient(180deg,#001b3d,#002550)`** |
| `.nav-item` font-size | 12.5px | **12px** |
| `.nav-item` font-weight | 500 | **600** |
| `.nav-item` padding | `8px 18px` | **`11px var(--sp-md)`** |
| `.nav-item` border-left | 3px | **2.5px** |
| `.nav-item.active` background | `#deeefa` | **`var(--nav-active-bg)`** |
| `.nav-item.active` colour | `var(--dark)` | **`#fff`** |

The nav was rebuilt from light to dark and the document was never updated. 17 of 42 custom properties
defined in the Main TMS are absent from `DESIGN.md` entirely: `--danger --gap-cards --ink-2 --line
--nav-active-bg --nav-active-border --navy --ok-bg --ok-text --primary --radius --rescheduled --sp-xs
--space-05 --space-1 --text-xs --warn-bg`.

This is a Responsibility failure, not a tidiness one. `DESIGN.md` is the artefact a future contrast
check would be verified against, and it currently certifies a nav that no longer exists.

### Literal inventory (baseline)

Run `inventory.py` again after any remediation to show movement rather than asserting improvement.

| Category | Main TMS (distinct / occurrences) | Planning WS (distinct / occurrences) |
|---|---|---|
| colour | 168 / 345 | 156 / 439 |
| spacing | 88 / 290 | 234 / 614 |
| radius | 19 / 91 | 13 / 73 |
| font-size | 17 / 159 | 20 / 168 |
| shadow | 15 / 17 | 6 / 6 |
| z-index | 10 / 12 | 8 / 9 |
| duration | 7 / 31 | 5 / 21 |

Plus 49 distinct hex values across 188 occurrences inside `.tsx` files, bypassing `tokens.css` entirely.

### ~~An unreachable dark theme~~ → A reachable, broken dark theme

> **Corrected 2026-08-22.** The claim below that both themes are unreachable is **wrong**.
> `AppShell.tsx:14,21,44` ships `const THEMES = ["light","dark","hc"]` behind a cycling header
> button that sets `document.documentElement.dataset.theme` and persists to `localStorage`.
> The original check grepped for the attribute string `data-theme`; the code uses the DOM
> `dataset.theme` API, so the grep returned 0 for the wrong reason.

`tokens.css` defines complete `html[data-theme="dark"]` and `html[data-theme="hc"]` palettes.
`frontend/index.html` hard-codes `data-theme="light"` as the initial value, but the theme button
overwrites it at runtime — **all three themes are user-selectable and the choice persists.**

They are also broken. The dark theme carries **17 contrast failures**, driven by one systemic mistake:
`--primary`, `--navy` and `--aafc-dark-blue` are all remapped to `#51b0e3` (a *light* blue) while the
foregrounds stay `#fff`. Every surface built on `--primary` — `.topbar`, `.btn`, `.pw-chip.on`,
`.pn-grid thead th`, `.pw-block-hdr`, `.skip-link` and 6 more — lands on 2.42:1.

Dark mode inverts the surface without inverting the foreground. ~~Wiring up a theme toggle today
would ship 17 failures at once.~~ **The toggle already exists — these failures ship today.**
Browser-verified 2026-08-22: 12 of 19 probed elements fail in `dark`, including `.btn.danger`
(the destructive-action button) at 2.78:1 and `.banner.proxy` at 1.22:1.

---

## Recommended order

Sequenced by blast radius, not by ratio.

1. **`.banner.proxy` (1.57:1)** — one-line fix; it is the "you are acting as someone else" indicator.
2. **Focus indicator** — pick a ring colour ≥3:1 on `#ffffff`/`#f4f8fc`/`#f0f5fa`; remove the two
   `outline:none` rules that outrank `:focus-visible`. One change, every keyboard user, both frontends.
3. **Planning Workspace drag alternative** — add a keyboard/menu path to `onMoveSession`. Copy the
   Main TMS `↑`/`↓` pattern, which already solves this correctly.
4. **The 35 `#6b7a87` literals** — mechanical; the correct token already exists. Then fix
   `--muted` on `--surface-2`, which both current greys still fail.
5. **Inline-styled controls** — `▲`/`▼`/`✕` to ≥28px with `aria-label`s. Closes G11 and part of G5.
6. **Reconcile `DESIGN.md`** with the shipped nav and the 14 undocumented tokens — cheap, and every
   later verification depends on it.
7. ~~**Delete or fix the dark/hc themes.** Deleting is legitimate and is the smaller change.~~
   **REVERSED 2026-08-22 — fix them, and sooner.** They are a shipped capability behind a visible
   control, so `.claude/rules/capability-preservation.md` forbids deletion without explicit
   authorisation. Live defect, not latent debt — belongs around step 3.
8. **G3 type scale** — the big one. Convert to a relative type scale. ~1,500 call sites; needs its
   own plan, and note the two frontends must be converted separately.

Items 1–6 are days. Item 8 is the programme.

---

## Exceptions register

| Rule | Location | Why | Impact | Status |
|---|---|---|---|---|
| G1 4.5:1 | `.btn-auth:disabled`, `.btn-disabled` @ 1.90:1 | WCAG 1.4.3 exempts inactive controls | Low — disabled state also carries `disabled` attribute | Permanent, allowed |
| ~~G1 / G4~~ | ~~dark + hc themes, 22 failures~~ | ~~unreachable~~ | ~~None today~~ | **WITHDRAWN 2026-08-22 — themes are reachable; there is impact today** |

## Human validation pending

Not run, and not inferrable from code: 5-second test, first-click testing, task-completion timings,
screen-reader walkthrough (VoiceOver/NVDA), and keyboard traversal of authenticated workflows.
No participant data is reported here because none was collected.

---

## Reproducing this audit

```bash
S=~/.claude/skills/apple-design/scripts
python3 - <<'PY'   # extract the SPA's <style> blocks first
import re,pathlib
h=pathlib.Path("connected-frontend/index.html").read_text(errors="replace")
pathlib.Path("/tmp/connected.css").write_text("\n\n".join(re.findall(r'<style[^>]*>(.*?)</style>',h,re.S|re.I)))
PY
python3 $S/css_audit.py /tmp/connected.css --format csv > contrast-register-main-tms.csv
python3 $S/inventory.py /tmp/connected.css --cluster
python3 $S/inventory.py frontend/src --cluster
python3 theme-aware-resolver.py      # 4 appearance contexts, resolves color-mix()
python3 hit-target-measure.py /tmp/connected.css
```

`css_audit.py` alone is not sufficient for the Planning Workspace: it cannot evaluate `color-mix()`
and does not enumerate `html[data-theme=…]` blocks, so it reports unresolved pairs as 1.0:1 failures
and silently omits two of the four appearance contexts. `theme-aware-resolver.py` handles both.

## Files

| File | Contents |
|---|---|
| `contrast-register-main-tms.csv` | 189 pair evaluations (Main TMS), `css_audit.py` |
| `contrast-register-both-frontends-merged.csv` | 295 evaluations, both frontends |
| `contrast-register-planning-workspace.csv` | 830 evaluations × 4 appearance contexts |
| `hit-targets-main-tms.csv` / `…-planning-workspace.csv` | derived control heights |
| `theme-aware-resolver.py` | `color-mix()` + multi-theme contrast resolver |
| `hit-target-measure.py` | hit-area derivation from CSS |
