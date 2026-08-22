# Fix log — interface audit remediation

Branch `fix/interface-audit-g1-g4`. Every ratio below is browser-measured against the real
stylesheets, before and after, at the same 19-element probe across all three selectable themes.

---

## FIX-01 · Dark-theme token cycle left `--ok`/`--warn` invalid

**Files:** `frontend/src/styles/tokens.css`
**Gate:** G1 · **Found:** while fixing FIX-02, not by the original audit

### Root cause

The base `:root` defines the semantic aliases in one direction:

```css
--warn:    #c97a00;        /* line 49 */
--warning: var(--warn);    /* line 90 */
```

`html[data-theme="dark"]` aliased them back the other way, and never redefined the other side:

```css
--ok:   var(--success);    /* line 109 — but --success is var(--ok) in base */
--warn: var(--warning);    /* line 110 — but --warning is var(--warn) in base */
```

That is a cycle. Per CSS Custom Properties §3, a cyclic custom property is **invalid at
computed-value time**, so in the dark theme `--ok`, `--warn`, `--success` and `--warning` all
computed to the empty string.

### User-visible effect

`.banner.proxy` — the banner that tells an operator they are acting on behalf of another unit —
declares `background: var(--warning)`. With the token invalid, `background` fell back to its
initial value:

```
dark, before:  .banner.proxy  background-color = rgba(0, 0, 0, 0)
```

**The proxy-mode banner had no background at all in dark theme.** `.fts-item.fts-ok` likewise lost
both its background and its `color: var(--success)`, falling back to the inherited body text
colour — rendering the "delivered" status chip identical to ordinary text.

### Fix

Explicit values in the dark block, lightened for dark surfaces in the same spirit as the
`--red: #ff6b6b` already there:

```css
--ok:   #3EAE77;   /* 6.12 / 6.61 / 5.63 :1 on --surface / --background / --surface-2 */
--warn: #D9982E;   /* 6.90 / 7.45 / 6.35 :1 */
```

The old `--ok: #1a7f4b` would have failed anyway had it resolved — 3.40 / 3.67 / 3.13:1.

### Verification

| | before | after |
|---|---|---|
| dark `--ok` / `--warn` / `--success` / `--warning` | all EMPTY | `#3EAE77` / `#D9982E` / `#3EAE77` / `#D9982E` |
| dark `.banner.proxy` background | `rgba(0,0,0,0)` | `rgb(217,152,46)` |
| dark `.fts-item.fts-ok` | inherited body text | 4.61:1 |
| light / hc token values | unchanged | unchanged |

---

## FIX-02 · Proxy banner illegible in three of four appearance contexts

**Files:** `frontend/src/styles/tokens.css`, `frontend/src/styles/layout.css`
**Gate:** G1 · **Audit item:** recommendation 1

### Root cause

`.banner.proxy` hard-coded its foreground: `color:#1D2733`. `--warn` is a mid amber in `light` and
`dark` but a **dark brown** (`#6a3800`) in `hc` and `prefers-contrast: more`. A single hard-coded
ink cannot serve both polarities.

| Context | `--warn` | `#1D2733` on it | `#ffffff` on it |
|---|---|---|---|
| light | `#c97a00` | 4.51 — passing by 0.01 | 3.35 |
| dark | `#D9982E` | 6.10 | 2.48 |
| hc | `#6a3800` | **1.57** | 9.64 |
| prefers-contrast: more | `#6a3800` | **1.57** | 9.64 |

### Fix

A per-theme `--on-warn` token, defined in all four contexts, and `.banner.proxy` uses it:

```css
.banner.proxy{background:var(--warning);color:var(--on-warn);}
```

Light also moves from `#1D2733` to `#101A26`, buying real margin instead of clearing the
threshold by 0.01.

### Verification — `.banner.proxy`

| Context | before | after |
|---|---|---|
| light | 4.51:1 | **5.23:1** |
| dark | no background at all | **7.08:1** |
| hc | 1.57:1 | **9.64:1** |
| prefers-contrast: more | 1.57:1 | **9.64:1** |

---

## Net effect, and one honest wrinkle

Failing elements out of the 19-element probe:

| Theme | before | after |
|---|---|---|
| light | 6 | 6 — no regression |
| dark | 12 | 11 |
| hc | 5 | 4 |

**The dark count only fell by one, and two chips got numerically worse.** That is expected and
worth stating plainly: `.fts-item.fts-warn` moved 4.01 → 2.78 and `.fts-leave-now-tag` 4.01 → 2.66.

Both hard-code `color:#a86600`. Previously their `color-mix()` background was invalid, so they
rendered transparent against the dark page — which happened to give 4.01:1 by accident. Now that
they have the amber background they were always meant to have, their hard-coded foreground is
revealed as wrong for it.

Fixing the cycle did not break these. It **un-masked a pre-existing defect** that the invalid
token was accidentally hiding. This is the third instance of the same root problem the audit
already named: hard-coded literals that bypass the token system and therefore cannot theme.
`#a86600` needs the same `--on-warn` treatment as the banner just got.

## Not yet done

- `.fts-item.fts-warn` / `.fts-leave-now-tag` hard-coded `#a86600` (dark 2.78 / 2.66)
- `.pw-block-warnings` background `#fff5f5` never remapped for dark — near-white chip on a dark page
- `.btn` / `.topbar` / `.pw-ctx` / `.pn-grid thead th` / `.brand` — `#ffffff` on `--primary`,
  which dark remaps to the *light* blue `#51b0e3` (2.42:1). This is the systemic dark-mode fault.
- `.btn.danger` 2.78:1, `.scope-pill` 1.09:1 in hc
- Everything in the Main TMS — untouched so far

---

## FIX-03 · The systemic dark-mode fault (`--primary`) + every remaining PW status colour

**Files:** `tokens.css`, `components.css`, `planning.css`, `layout.css`
**Gate:** G1 · **Audit items:** recommendations 3, 4, 7 · **Decision:** user chose the hybrid

### The fault

Dark remapped `--primary` to the *light* AAFC blue `#51b0e3` while foregrounds stayed `#fff`
— 2.42:1 across `.topbar`, `.brand`, `.btn`, `.pw-ctx`, `.pn-grid thead th`, `.pw-chip.on`,
`.skip-link`. Dark mode inverted the surface without inverting the foreground.

### Decision, and why the render changed it

Three options were rendered with the real stylesheets before choosing. The ratios alone would
have picked either extreme; the render disqualified both:

- **Navy everywhere** — the red `Delete` button becomes the most prominent element in the
  content area, out-ranking the primary action. Not a contrast failure; a *hierarchy inversion*,
  and invisible in the numbers.
- **Bright blue everywhere** — the `PERIOD` header band out-ranks the data it labels, and
  because the primary button is the same blue, nothing stands out at all.

**Hybrid, chosen:** `--primary` is the chrome surface; a separate `--emphasis` carries the bright
blue for controls that should draw the eye.

`--primary` in dark is the **VIG royal `#004b8d`**, not the `#143A63` shown in the mock-up.
`DESIGN.md` forbids introducing a hex that has not been VIG-verified, and royal also separates
better from the page (2.10:1 vs 1.40:1). One token reverts it if that call is wrong.

### The token model introduced

Every colour added is a **foreground role bound to a specific surface**, defined in all four
appearance contexts. This exists because component rules were hard-coding inks (`#a86600`,
`#1D2733`, `#002F65`, `#fff5f5`, `#F5F5F5`) that cannot follow a theme — the same root cause the
audit named for the 35 stray `#6b7a87` literals.

| Token | light | dark | hc / contrast-more |
|---|---|---|---|
| `--emphasis` / `--on-emphasis` | `--primary` / `#ffffff` | `#51b0e3` / `#101A26` | `--primary` / `#ffffff` |
| `--on-danger` | `#ffffff` | `#101A26` | `#ffffff` |
| `--on-accent` | `#002F65` | `#101A26` | `#ffffff` |
| `--on-warn` | `#101A26` | `#101A26` | `#ffffff` |
| `--muted-on-sunk` | `#5c6a76` | `#9fb2c6` | `#303030` / `#3a3a3a` |
| `--ok-on-tint` | `#166c40` | `#3EAE77` | `#004d24` |
| `--warn-on-tint` | `#8d5500` | `#D9982E` | `#6a3800` |
| `--danger-on-tint` | `#c3152f` | `#ff6b6b` | `#ad000e` |
| `--resch-on-tint` | `#6d2ed6` | `#df68ff` | `#44007a` |
| `--blue-on-tint` | `#004b8d` | `#51b0e3` | `#004b8d` |

`--muted-on-sunk` also closes the `--surface-2` gap the audit found: `--muted #657380` was
4.43:1 there. `#5c6a76` gives 5.07:1 — and happens to be the value already written in
`.claude/rules/frontend.md`, so the two now agree.

### Verification — browser-measured, 23 elements, transitions disabled

| Theme | before | after | tightest margin after |
|---|---|---|---|
| light | 6 failing | **0 of 23** | `.btn.danger` 4.64:1 |
| dark | 12 failing | **0 of 23** | `.fts-item.fts-ok` 4.61:1 |
| hc | 5 failing | **0 of 23** | `.fts-item.fts-red` 5.71:1 |

Two values were re-picked purely for margin after an initial pass technically passed:
`--resch-on-tint` light 4.53 → 5.55, and `.banner.proxy` light 4.51 → 5.23. A ratio that clears
the bar by 0.01 is not a pass worth keeping — the next token tweak breaks it.

### Two measurement artifacts worth recording

Both were caught before they reached this log, and both would have been reported as defects:

1. **`color(srgb …)` parsing.** `color-mix()` makes Chrome return `color(srgb 0.83 0.90 0.87)`,
   whose components are 0–1. A parser expecting 0–255 reads that as near-black and invents
   failures. `.nav-item.active` was briefly "1.59:1" for this reason.
2. **`transition: background .1s`.** `.pn-cell-inner` animates its background, so reading
   `getComputedStyle` right after switching `data-theme` catches the *outgoing* theme's colour.
   `.pn-cell-inner.break-cell` reported a phantom 1.98:1 through several attempts. Disabling
   transitions before measuring is now part of the probe.

**Any theme-switching contrast probe must disable transitions and handle `color(srgb …)`,
or it will manufacture failures that do not exist.**

## Still outstanding

- **Main TMS entirely untouched** — the focus ring (2.42:1 / 2.27:1 / 2.21:1), the six
  icon-only buttons, the ~16px inline-styled `▲`/`▼`/`✕` controls, and its 6 contrast failures.
- **The 35 `#6b7a87` literals** in `.tsx` — mechanical, token already exists.
- **G3 px-locked type** — unchanged, and still the programme-sized item.
- **G6** — the Planning Workspace session move is still drag-only.
- Elements outside the 23-element probe were not measured; coverage is the probe, not the app.

---

## FIX-04 · Main TMS — focus ring, six contrast failures, hit targets, icon labels

**File:** `connected-frontend/index.html` · **Gates:** G1, G4, G5, G11

### G4 — the focus ring needed a token, not a colour

No single value clears 3:1 on both light surfaces and the dark chrome:

| Candidate | min on light surfaces | min on dark chrome |
|---|---|---|
| `--blue #51b0e3` (was) | **2.00** | 4.60 |
| `--royal #004b8d` | 7.27 | **1.27** |
| `--dark #002f65` | 10.90 | **1.00** |

So `--focus-ring` defaults to `--royal`, and `.topbar,.sidenav` re-point it to `--blue`.
Browser-verified: `#004b8d` on a light surface, `#51b0e3` inside the chrome.

Also fixed: `.yn-display input` set `outline:none` at specificity 0-1-1, outranking the global
`:focus-visible` at 0-1-0 — that field had no ring at all. The three form-field `:focus` rules
swapped their border to `--blue` (2.42:1); they now use `--focus-ring`.

### G1 — all six confirmed failures

| Selector | before | after |
|---|---|---|
| `.ht` | 1.04 | **14.02** |
| `#page-service-desk .sd-filter-bar button.active` | 2.42 | **8.78** |
| `.hm-empty` | 2.50 | **5.60** |
| `.cm-cell-delivered_with_issue` | 2.77 | **6.72** |
| `.fac-sugg-pill.conflict` | 3.95 | **5.88** |
| `.yn-chip-active` | 4.15 | **6.38** |

`.cm-cell-delivered_with_issue` also had a semantic fault the ratio doesn't capture: amber text
on the **green "delivered" fill**, so the colour contradicted the status. It is now warn-tinted.

`.ht` needed the same treatment as the focus ring — `--border` becomes `#555555` under
`prefers-contrast` while `--steel` does not move, so no foreground worked in both. Moved to
`--surface`/`--text`, which passes in both.

### G5 — hit targets, all browser-measured

| Control | before | after |
|---|---|---|
| `.ht` | 14×14 | **30×30** effective (glyph still 14px, via a `::before` overlay) |
| `.chk-item input` | 13×13 | label row **772×28** — the label forwards the click |
| `.btn-icon` (new) | ~16px inline-styled | **28×28** |
| `.mode-banner button` | 23.4 | **95×28** |
| sd filter button | 24.8 | **60×28** |

The inline-styled `▲`/`▼`/`✕` controls now use a shared `.btn-icon` class instead of per-instance
`font-size:10px;padding:1px 4px`.

### G11 — 6 → 0 unlabelled icon buttons

Labels name the block rather than the row: `aria-label="Delete ${block_name}"`,
`"Move ${block_name} earlier"`. Four bare checkboxes in the same editors were also unlabelled
and now carry `aria-label`s.

---

## INCIDENT · concurrent session stashed this work mid-flight

Partway through the Main TMS edits the working tree reverted. Cause, from the reflog: **another
session is active in this repository** (there is also an agent worktree at
`.claude/worktrees/agent-a58bc0fe2a6135c10`). It committed to `fix/interface-audit-g1-g4`,
checked out `main`, fast-forward merged, and continued committing — stashing this session's
uncommitted changes as `year-ux ... (pre-deploy stash)` on the way.

Nothing was lost: `stash@{0}` and `stash@{1}` held the work and both applied cleanly. The stash
had, however, been taken **mid-edit** — the G4 focus-ring batch survived, the G1/G5/G11 batch did
not, and the difference was only visible by checking each edit individually rather than trusting
the restore.

**Lessons, both procedural:**

1. `git diff --stat` returning empty is a signal to stop and investigate, not a glitch. It was
   the first sign here.
2. After recovering from a stash, verify **each** expected change is present. A stash taken
   mid-session is a partial snapshot, and a restore that "succeeds" can still be incomplete.

The work is now also written to `recovered-patches/` as plain patch files, round-trip verified
against a clean tree. That is deliberate: patch files on disk survive anything another session
does to the index or the working tree.

**This work is still uncommitted.** Given a second session is actively stashing in this tree,
it should be committed to a branch promptly or it is liable to be swept up again.

---

## FIX-05 · The 35 `#6b7a87` literals, and the root cause behind them

**Files:** `tokens.css`, `components.css`, `planning.css`, 5 `.tsx` files
**Gate:** G1 · **Audit item:** recommendation 4

Swapping the literals for `var(--muted-text)` alone would **not** have fixed this.
`--muted-text` resolved to `#657380`, which fails on three of the five backgrounds the
literals actually sit on:

| Colour | `#ffffff` | `#f4f8fc` | `#f1f5f9` | `#f0f0f0` | `#f5f5f5` |
|---|---|---|---|---|---|
| `#6b7a87` (was) | 4.41 ✕ | 4.14 ✕ | 4.03 ✕ | 3.87 ✕ | 4.05 ✕ |
| `#657380` (`--muted`) | 4.86 ✓ | 4.56 ✓ | 4.44 ✕ | 4.27 ✕ | 4.46 ✕ |
| `#5c6a76` (now) | 5.56 ✓ | 5.21 ✓ | 5.07 ✓ | 4.88 ✓ | 5.10 ✓ |

The real finding is in `tools/playwright-staging/tests/a11y-wcag.spec.ts`: the Main TMS
darkened `--muted` **twice** — `#6b7a87` → `#657380` → `#5c6a76`, the second step to clear
4.5:1 on `sa-scope-bar`'s `#eef4fa`. The Planning Workspace only ever got the first step.

**The two-frontend asymmetry, third instance.** `min-height:28px`, then the theme work,
now this. Each time a fix landed on one side only. `.claude/rules/architecture.md` makes
the split deliberate, so this will keep recurring: any accessibility remediation here
needs applying twice, on purpose, as part of the same change.

Also removed `--muted-on-sunk`, introduced earlier on this branch and made redundant by
the darkening — it resolved identically to `--muted` in all four contexts. Two names for
one colour is how palettes drift.

Verified: no regression (light/dark/hc still 0 failing of 23), `--muted-text` now passes
on all six surfaces in use, `npm run build` passes.

---

## FIX-06 · `DESIGN.md` reconciled

**File:** `DESIGN.md` · **Audit item:** recommendation 6

Every documented `.nav-item` property was wrong, including its light/dark polarity, and
33 of 61 Main TMS tokens were undocumented. Both fixed; token coverage is now complete.

**The audit undercounted its own finding.** It reported "17 of 42". The grep behind that
required the token at line start, so tokens sharing a line (`--ok: …; --ok-bg: …;`) were
never seen. The true figure is **33 of 61**, and `AUDIT.md` now says so. This is the
method's own warning turned on itself: a number produced by a script is only as good as
that script's coverage, and "run a script" is not the same as "measured correctly".

`DESIGN.md` now also carries the rules this branch established, so they are not
re-broken: the focus-ring token and its two specificity traps, the requirement that every
foreground token be defined in all four appearance contexts, the no-self-aliasing rule
that caused the dark-theme cycle, and `--primary` being the chrome surface.

## Remaining after this branch

| Item | Gate | Size |
|---|---|---|
| Session move is drag-only in the Planning Workspace | G6 | small — the Main TMS `↑`/`↓` pattern already solves it |
| Text does not enlarge — 1,492 of 1,528 font-size specs px-locked | G3 | programme; ~1,500 call sites, both frontends separately |
| 2,454 inline style declarations never contrast-checked | — | coverage gap, not a clean result |
| Authenticated screens, narrow viewports, screen-reader, human testing | G10, G12 | unmeasured |

---

## FIX-07 · The inline-style channel — measured, and three real failures fixed

**Files:** `frontend/src/App.tsx`, `frontend/src/components/planning/PlanningBottomDrawer.tsx`
**Tool:** `inline-contrast.py` (new) · **Gate:** G1 · **Audit item:** the stated largest coverage gap

The audit called this "the largest gap": 2,454 inline style declarations that stylesheet
tooling cannot see and that were never contrast-checked. This closes it, and corrects the
size of the gap in the process.

### The exposure was far smaller than the raw count implied

| | connected-frontend | frontend/src |
|---|---|---|
| inline style declarations | 1,617 | 829 |
| with a resolvable literal foreground | **22** | **18** |
| no decidable colour (`var()`, gradient, translucent, or none) | 1,595 | 811 |

**~98% reference tokens or set no colour at all**, so they inherit the palette this branch
already fixed. "2,454 declarations unchecked" was true but misleading: the literal exposure
was 40 sites, not 2,454. Coverage figures describe what was *examined*, and a large one can
still hide a small real risk — or, as here, imply a large one that is not there.

### Findings

| Ratio | Site | Pair | Fixed to |
|---|---|---|---|
| **2.42:1** | `App.tsx:66` | `white` on `#51b0e3` | `var(--royal)` — 8.78:1 |
| **2.42:1** | `App.tsx:94` | `white` on `#51b0e3` | `var(--royal)` — 8.78:1 |
| **3.35:1** | `PlanningBottomDrawer.tsx:378` | `#fff` on `#78909c` | `var(--steel)` — 7.72:1 |

All three are the same mistake the stylesheet work kept finding: white text on the *light*
AAFC blue. Now: 0 paired failures, 0 fail-everywhere colours across both frontends.

15 sites remain **conditional** — a literal that passes on one surface family and fails on
the other (e.g. `#fff`, safe on the dark chrome, unsafe on light). None is decidable without
a rendered DOM. They are listed by the tool, not hidden.

### Two bugs in the tool, both of which faked a clean result

Recorded because a measuring instrument that reports "0 failures" while silently skipping its
input is worse than no instrument.

1. **React style objects are comma-separated, not semicolon-separated.** Parsing them as CSS
   text made `[^;]+` swallow `white, fontWeight: 700, fontSize: …` as one "colour", which
   then failed to parse and was skipped. Only 2 of 829 declarations resolved and it reported
   **0 paired failures** — while `App.tsx:66` sat there at 2.42:1. Fixed with a
   parenthesis-aware comma split, so `rgba(0,0,0,.5)` survives intact. Resolution went 2 → 18
   and the three real defects appeared.
2. **A single light-surface set.** White text failed against every surface and was reported as
   FAIL-ALL, when it is correct on the dark header and nav. Surfaces are now split into light
   and dark families; only a colour failing both is called definite.

The first bug was caught by testing the tool against a defect known to exist. That is the only
reason it was caught: every other signal said the code was clean.

## Gate status after this branch

| Gate | Before | After |
|---|---|---|
| G1 contrast | FAIL | stylesheet + inline channels measured, 0 known failures |
| G3 text enlargement | FAIL | **PASS** — 0 px font-size in either frontend (bar `@media print`) |
| G4 keyboard | FAIL | focus ring ≥3:1 on every surface via a scoped token |
| G5 hit targets | FAIL | all measured controls ≥28px |
| G6 gesture alternatives | FAIL | **PASS** — keyboard move, 7 tests |
| G11 semantics | FAIL | **PASS** — 0 unlabelled icon buttons |

Still unmeasured, and not claimable: the authenticated screens. Every result on this branch
comes from probe pages, the sign-in screen, and static analysis. G10 and G12 remain
unassessed, and the 15 conditional inline sites need a rendered check.

---

## FIX-08 · The authenticated screens — measured at last

**Setup:** local FastAPI backend on :8000 against the existing seeded SQLite DB, the SPA served
on :8080 from a `_local-test.html` copy whose `aafc-api-base` points at localhost. The tracked
`index.html` still points at production and was never altered; the copy is git-ignored.
Signed in through the real login handler (not a direct API call, which would not populate
`sessionStorage`) as `sqn_admin` at 703SQN.

Everything before this point in the audit was measured on probe pages and the sign-in screen.
This is the first time the application itself was measured.

### Result across 13 authenticated pages

| | before | after |
|---|---|---|
| text pairs measured | — | **509** |
| contrast failures | 1 | **0** |
| hit targets < 28px | **1,342** | **14** (12 real; 2 are the `.ht` pseudo-element overlay) |
| unlabelled controls | **275** | 31 |

### 1,342 hit-target failures were five rules

The counts are per-rendered-element, so one rule in a table repeats per row. The actual work:

| Rule | Sites | Defect | Fix |
|---|---|---|---|
| `.btn-xs` | 895 | `min-height` was set, `min-width` was not — icon buttons rendered 25px wide | add `min-width:28px` |
| bulk-select checkbox | 244 | 16×16 in a 26×16 label; label carried a `title`, the input had no name | `aria-label`, 28×28 label |
| `.modal-x` / `.modal-close` | 66 | flex children of `.modal-hdr` shrinking to **6×13** | `flex-shrink:0` + `min-*` |
| `.lh-btn`, `.btn-lnk`, `.cal-nbtn` | 76 | 24px tall / 11px wide | `min-height`/`min-width:28px` |
| `.tb-btn` | 3/page | topbar at 24–25px — only exists once signed in | `min-height:28px` |

**The `.modal-x` regression was mine.** Moving those buttons from fixed px to `em` earlier on this
branch removed the implicit floor, and as flex children with `flex-shrink:1` they collapsed to
6×13. It was invisible until the app was driven authenticated: modals do not exist on the
sign-in screen. Fixed-size-to-`em` conversions need `flex-shrink:0` wherever the element is a
flex child.

### 9 CSS custom properties were referenced but never defined

`--error` (24 uses), `--warning`, `--amber`, `--bg-card`, `--bg-page`, `--bg2`, `--b2`,
`--hover`, `--red-bg` — **37 declarations, none with a fallback.** Every one computed to the
inherited value, so the styling silently did not apply: the Archive control was never actually
red, "error" text was never actually the error colour.

`css_audit.py` cannot see this. An unresolvable `var()` is skipped, not flagged — so a token
that does not exist looks exactly like a token it merely could not evaluate. **Add an
undefined-token check to any CSS audit; a missing definition is silent by design.**

Defined as aliases of the real palette. The two used as text colours map to `--warn-text` and
`--status-text-danger`, because raw `--warn` is 4.05:1 on white. Re-measured after: still 0
contrast failures, so activating 37 dormant declarations introduced nothing.

### Static enumeration still earned its place

Four `.cal-chip` variants put white on their fill: `not_delivered` 2.03:1, `delivered_with_issue`
3.10:1, `rescheduled` and `act` 3.35:1. The live sweep caught **one** — only that variant
appeared in the day's data. Enumerating the CSS found the other three. Live measurement proves
what renders; static enumeration covers what could render.

### Still open

- 12 real hit targets: 10 form inputs at 104×21, one `.btn` at 41×18, one select at 146×22
- 31 unlabelled inputs, mostly on Unit Setup, Curriculum and Activities
- Only the `sqn_admin` role was walked. `wing_admin`, `national_admin`, `auditor` and
  `system_admin` have their own pages and were not measured.
- G10 (adaptive layout) and G12 (data integrity) remain unassessed.

---

## FIX-09 · All five roles measured

Every earlier result covered `sqn_admin` only. Signed in as each role in turn through the
real login handler against the local backend.

| Role | Pages | Text pairs | Contrast | hit <28px | Unlabelled |
|---|---|---|---|---|---|
| `sqn_admin` (703SQN) | 13 | 478 | **0** | 0 | 13 |
| `wing_admin` (7WG) | 8 | 267 | **0** | 41 | 5 |
| `national_admin` | 8 | 263 | **0** | 51 | 5 |
| `system_admin` | 10 | 352 | **0** | 69 → 51 | 10 |
| `auditor` | 2 | 52 | **0** | 0 | 1 |
| **total** | **41 page-visits** | **1,412** | **0** | | |

**Contrast is clean across every role.** 1,412 text pairs, zero failures. Seven screens were
measured here for the first time in the whole audit: Wing Overview, Wing Activities, Wing HQ
Calendar, National Overview, National Activities, Audit, and System Console.

### One new fix

System Console rendered 18 inline-styled "Archive" buttons at **40×13** (`padding:1px 4px`,
`font-size:9px`). Now `.btn-icon` with `padding:2px 8px` — the same pattern as the reference-badge
archive control found earlier, in a different template.

### Proxy Mode was already active on the wing_admin account

Signing in as `wing_admin` showed the *squadron* nav, not the wing nav, and the debug bar read
`mode PROXY active`. `effectiveScope()` returns `squadron` while proxy is on, which is correct
behaviour — but it means **the wing pages are invisible until proxy is exited**, and a sweep that
did not check would have silently re-measured the squadron pages and reported them as wing.

It was not a state leak: `S.proxy` came from the server, not `sessionStorage`, and
`proxy_sessions` holds a matching active row that predates this session. Pre-existing test data.
Verified in the database before drawing any conclusion — the alternative read (proxy leaking
across a sign-out) would have been a serious security finding, and it would have been wrong.

### What remains

| Item | Count | Where |
|---|---|---|
| bare checkboxes below 28px | 49 | Account Management, all admin roles |
| `.seg-btn` below 28px | 2 | Wing HQ Calendar |
| unlabelled form fields | 5–10 per role | Account Management, Unit Setup, System Console |

The checkboxes are 18×18 after the earlier fix and sit in table cells with no wrapping label, so
the control itself is the whole target. Reaching 28px needs either a padded wrapper or a
`min-height` on the cell — a layout change per table, not a token change.

The unlabelled fields each need a real label naming their purpose. That is content work, not a
mechanical fix, and guessing names would be worse than leaving them listed.

### Coverage, stated plainly

This is one squadron (703), one wing (7WG), one browser, one viewport, at default text size, on
seeded synthetic data. Not covered: `national_viewer` and `wing_viewer`, modal dialogs and
drawers (only the pages behind nav items were visited), any flow behind a native
`confirm()`/`prompt()` — those block browser automation by design — narrow viewports, and every
form in an error or validation state.

---

## FIX-10 · Planning Workspace at narrow widths — one fix, one open defect

Measured in fixed-width iframes served from the Vite dev server (same origin, so the
harness can read each frame), signed in as `sqn_admin`. Widths 320 / 360 / 600 / 768 /
1024 / 1440.

### Fixed: the topbar had a hard ~555px minimum

`.topbar`'s right-hand cluster — scope pill, role pill, Theme, Size, Sign out — could not
wrap, so the bar stayed 555px wide however narrow the viewport got and **the page itself
scrolled sideways**. Same defect, same shape, as the Main TMS topbar fixed earlier.

| Width | topbar before | topbar after | body scrolls sideways |
|---|---|---|---|
| 320px | 555 | **326** | yes → yes (5px, see below) |
| 360px | 555 | **345** | **yes → no** |
| 600px | 585 | 585 | no |

At 320px a 5px overflow remains. Not chased: it is a border/padding rounding artefact an
order of magnitude smaller than the original 235px, and 320 is the floor of SC 1.4.10
rather than a supported target here.

### Open, and NOT fixed: ~11,700px of chips clipped and unreachable at every width

At 1440px — a comfortable desktop width, not a narrow one — 110 `button.pw-chip` controls
sit past the right edge. The row holding them is `display:flex; flex-wrap:nowrap;
overflow-x:visible`, 1,195px wide with a **12,918px scrollWidth**, inside `.pw-root`
which is `overflow:hidden`. So roughly 11,700px of real, visible, interactive buttons
cannot be reached by scrolling, wrapping, or any other means.

This is not a narrow-viewport bug. It reproduces at 320, 360, 600, 768, 1024 and 1440.

**Identified and fixed — see below.** The obvious candidate, `.pw-filter-chips`, already
sets `flex-wrap: wrap`; the offending row was a different, inline-styled container. Changing `.pw-root`'s `overflow` to force a scrollbar would be a
guess at the wrong level: `.pw-root` is the app shell (`height: calc(100vh - 48px)`,
panels scrolling internally), and loosening it risks the shell's own scroll behaviour.
Fixing the actual row is right; guessing which one is not.

Note the data: 131 chips is seeded test data ("REM-39 Conflict Test" repeated). A real
squadron would have fewer. The row is unbounded either way — nothing in the CSS stops it
growing past the viewport — so the defect is structural, not a data artefact.

### The Planning Workspace is a fixed-viewport app shell

`.pw-root` is `height: calc(100vh - 48px); overflow: hidden` with panels that scroll
internally, and the stylesheets carry media queries down to 768px and nothing below.
That is a deliberate desktop-application pattern, not an oversight. Making the dense
planning grid genuinely reflow to 320px is design work, not a CSS change, and is out of
scope for an audit remediation.

Verified after the change: 45 tests pass, build clean.


---

## FIX-11 · The unreachable chip row identified and fixed

`routes/PlanningWorkspace.tsx:437` — the **year selector**. It renders one `pw-chip` per
planning year in an inline-styled `display:flex` row with no wrap, and the row's action
buttons come **after** the chips in DOM order.

**The user-visible defect was never really the chips.** With enough years, `+ Anchor event`,
`Update future parade day` and `Guided year setup` are pushed past the right edge, and
`.pw-root` is `overflow:hidden`, so they cannot be scrolled to at any viewport width. Three
primary actions, silently unreachable.

Measured at 1440px against 131 seeded years: row scrollWidth **12,918px** in a 1,195px box,
110 chips past the edge, all three actions off-screen.

Fix: `flexWrap: "wrap"` plus a `rowGap`.

| | before | after |
|---|---|---|
| row scrollWidth vs client | 12,918 / 1,195 | 1,267 / 1,267 |
| chips past the right edge | 110 | **0** |
| document elements past the edge | 110 | **0** |
| the three action buttons | all off-screen | **all on screen** |

### A refinement that made it worse, and was reverted

Wrapping 131 chips makes the row 687px tall, so a `maxHeight: 22vh` + `overflowY: auto` cap
was added to stop it eating the viewport. Re-measuring showed the cap pushed the same three
action buttons **below the row's scroll fold** — recreating the exact defect the fix existed
to remove, in the other axis.

Reverted. Wrapping alone keeps every control reachable, and the 687px height only appears
against seeded data with 131 planning years; a real unit has a handful.

Worth recording because the cap looked like an obvious improvement and was only exposed by
measuring after the change rather than reasoning about it. The bound belongs on the chips,
not on the row that also holds the actions — restructuring the JSX that way is the better
long-term shape, and was not attempted here.

---

## FIX-12 · Two remaining G5 hit-target gaps — `seg-btn` and Account Management bulk-select

**File:** `connected-frontend/index.html` · **Gate:** G5

### `.seg-btn` — Wing HQ Calendar view switcher

`.seg-btn` uses `font-size:var(--fs-sm)` (11px) and `padding:5px 12px`, giving a rendered height
of ~24px — below the 28px target. Added `min-height:28px`. Two elements ("Grid" / "Table" buttons
on the Wing HQ Calendar page), all admin roles that see Wing HQ.

### Account Management bulk-select checkboxes

49 bare `<input type="checkbox">` rendered inside `<td>` cells by `_renderAccountTable()` and its
select-all header. The global `input[type=checkbox]` rule sets `width:height:18px`; without a
wrapping label the effective pointer area is the checkbox itself (18×18). The same label-wrapper
pattern used in FIX-08 for the PW's bulk-select: a `<label>` with `display:flex; align-items:center;
justify-content:center; min-height:28px; min-width:28px` containing the checkbox. The checkbox's
own `aria-label` supersedes the label element's text content (empty), so the accessible name is
unchanged. Select-all header checkbox same treatment.

---

## FIX-13 · G11 unlabelled form fields — 16 inputs across main TMS frontend

**File:** `connected-frontend/index.html` · **Gate:** G11

Systematic enumeration of all inputs without a programmatically associated label (no `for`-linked
`<label>`, no `aria-label`, not nested inside a `<label>`). Hidden state inputs (`type="hidden"`,
`*-edit-id`) and inputs already inside a wrapping `<label>` were excluded.

| Input ID | Page / context | Fix |
|---|---|---|
| `s-start` | Unit Settings — Parade Time range | `aria-label="Parade start time"` |
| `s-end` | Unit Settings — Parade Time range | `aria-label="Parade end time"` |
| `user-dir-filter` | Unit Settings — User Directory search | `aria-label="Filter users by name, role, or unit"` |
| `acct-search` | Account Management — filter bar | `aria-label="Filter accounts by name, role, or unit"` |
| `sc-maint-drain` | System Console — Maintenance section | `for="sc-maint-drain"` on `<label>` |
| `sc-maint-confirm` | System Console — Maintenance section | `for="sc-maint-confirm"` on `<label>` |
| `tc-name-inp` | Add Training Class modal | `for="tc-name-inp"` on `<label>` |
| `tc-seq-inp` | Add Training Class modal | `for="tc-seq-inp"` on `<label>` |
| `tc-edit-name-inp` | Edit Training Class modal | `for="tc-edit-name-inp"` on `<label>` |
| `tc-edit-seq-inp` | Edit Training Class modal | `for="tc-edit-seq-inp"` on `<label>` |
| `cp-to-inp` | Add Custom Phase modal | `for="cp-to-inp"` on `<label>` |
| `cp-edit-to-inp` | Edit Custom Phase modal | `for="cp-edit-to-inp"` on `<label>` |
| `fac-rank` | Facilitator editor — rank field | `for="fac-rank"` on `<label>` |
| `tt-apply-from-date` | Timing Template — apply-from panel | `aria-label="Apply timing template from date"` |
| `tt-apply-from-reason` | Timing Template — apply-from panel | `aria-label="Reason for applying template from that date"` |
| `waz-effective` | Wing Archive Wizard | `for="waz-effective"` on `<label>` |
| `pnd-notes` | Parade Night Details panel | `for="pnd-notes"` on `<label>` |
