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
