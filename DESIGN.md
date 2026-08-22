# AAFC TMS — Design System

This file records the current visual design language of the AAFC Training Management System.
It is descriptive (what currently exists), not prescriptive. Any changes to tokens, components,
or patterns require explicit review — see `docs/ui-review/design_system_proposal.md`.

---

## Brand authority

All design decisions trace back to the **AAFC Visual Identity Guide (VIG)**. The hex values
below are the VIG-specified palette. No hex value in either frontend may be changed without
verifying it against the VIG.

---

## Colour tokens

### Main TMS (`connected-frontend/index.html` `:root`)

```css
/* AAFC brand palette */
--blue:   #51b0e3;   /* AAFC blue — accent, active states, highlights */
--dark:   #002f65;   /* AAFC dark blue — header, nav structure */
--royal:  #004b8d;   /* Royal blue — secondary active states */
--steel:  #455560;   /* Gunmetal grey — body text, secondary surfaces */
--lgrey:  #b0b7bb;   /* Light grey — borders, table headers, quiet backgrounds */
--pale:   #7db2ce;   /* Pale blue — subtle information backgrounds */
--red:    #e51937;   /* Red — danger, errors, must-attend markers */

/* Surface and layout */
--bg:           #f4f8fc;   /* slight AAFC-blue tint on page background */
--surface:      #ffffff;
--surface-2:    #f0f5fa;
--border:       #d1dce8;
--border-light: #e4edf5;

/* Text hierarchy */
--text:   #1e2d3d;   /* deep navy-dark primary text */
--text-2: #3a4a55;
--ink-2:  #44506a;
--muted:  #5c6a76;   /* darkened twice: #6b7a87 -> #657380 -> #5c6a76, the last step to
                        clear 4.5:1 on sa-scope-bar's #eef4fa. Passes on every surface. */

/* Accessible contextual tokens (WCAG 2.2 AA — text use only) */
--muted-text-on-light: #6e7275;   /* ≥4.5:1 on both --surface and --bg */
--text-on-dark-muted:  #7e9bbb;   /* ≥4.5:1 on --dark */
--link-on-light:       var(--royal);   /* 7.53:1 on --accent-light */
--focus-ring:          var(--royal);   /* focus indicator; >=7.27:1 on every light surface.
                                          .topbar/.sidenav re-point it to var(--blue),
                                          which is >=4.60:1 on the dark chrome. One value
                                          cannot satisfy both — see the note below. */
--status-text-danger:  #d41733;   /* ≥4.5:1 on --surface and --bg */

/* Status colours */
--ok:      #1a7f4b;   --ok-bg:   #d4f0e3;   --ok-text: #145f38;
--warn:    #c97a00;   --warn-bg: #fff3cd;

/* Interactive */
--accent:       var(--blue);
--accent-light: #e0f0fa;

/* Shadows */
--sh:  0 1px 4px rgba(0,47,101,.10);
--sh2: 0 4px 16px rgba(0,47,101,.14);

/* Semantic aliases */
--primary: var(--dark);   --navy:   var(--dark);
--danger:  var(--red);    --line:   var(--border);
--rescheduled: #7c3aed;   --warn-text: #7a5200;

/* Navigation (dark chrome) */
--nav-active-bg:     rgba(81,176,227,.20);
--nav-active-border: #51b0e3;

/* Spacing — two scales coexist; --sp-* is the newer one used by the nav */
--sp-xs:8px;  --sp-sm:12px;  --sp-md:16px;  --sp-lg:20px;  --sp-xl:24px;
--space-05:4px;  --space-1:8px;   --space-1h:12px; --space-2:16px;
--space-2h:20px; --space-3:24px;  --space-4:32px;  --space-5:40px;  --space-6:48px;
--gap-cards:10px;

/* Type scale */
--text-xs:11px; --text-sm:13px; --text-base:15px;
--text-lg:17px; --text-xl:21px; --text-2xl:27px;

/* Radius */
--radius:6px;  --radius-lg:10px;
```

> **Two spacing scales and two type conventions exist side by side.** `--sp-*` and
> `--space-*` are both live, and most component rules still use literal px rather than
> either. Consolidating them is unfinished work, not a documented intent.

### Planning Workspace (`frontend/src/styles/tokens.css`)

Uses a parallel set with `--aafc-` prefix but same underlying hex values:

```css
--aafc-dark-blue: #002f65;    /* = --dark */
--aafc-blue:      #51b0e3;    /* = --blue */
--aafc-steel:     #455560;    /* = --steel */
```

**Three themes, all user-selectable.** `AppShell.tsx` ships a cycling Theme button
(`THEMES = ["light","dark","hc"]`) that sets `document.documentElement.dataset.theme`
and persists to `localStorage`. `tokens.css` therefore defines four appearance
contexts — `:root`, `html[data-theme="dark"]`, `html[data-theme="hc"]`, and
`@media (prefers-contrast: more)` — and **every foreground token must be defined in
all four**. A token defined in only some contexts computes to empty in the others.

**Foreground roles.** Each of these is a foreground bound to a specific surface. They
exist because component rules were hard-coding inks (`#a86600`, `#1D2733`, `#002F65`)
that cannot follow a theme switch. `-on-tint` means text on a `color-mix()` status
tint, not on a flat surface.

```css
--emphasis / --on-emphasis    /* surface + ink for emphasised controls */
--on-warn --on-danger --on-accent
--ok-on-tint --warn-on-tint --danger-on-tint --resch-on-tint --blue-on-tint
```

**Dark theme cautions, both learned from real defects:**

1. Do not alias a semantic token back to its own alias. The base `:root` defines
   `--warning: var(--warn)`, so writing `--warn: var(--warning)` in the dark block
   creates a cycle. A cyclic custom property is **invalid at computed-value time**,
   which silently emptied `--ok/--warn/--success/--warning` and left the proxy-mode
   banner with no background at all.
2. `--primary` is the **chrome** surface and is `--royal #004b8d` in dark, not the
   bright `--blue`. Painting chrome in the bright blue put white text at 2.42:1 and
   made table headers out-rank the data beneath them.

---

## Typography

- **Family**: `'Montserrat', Arial, sans-serif` (both frontends)
- **Weights used**: 300, 400, 600, 700, 800, 900
- **Source**: Google Fonts (`fonts.googleapis.com/css2?family=Montserrat:...`)
- **Page titles**: bold, ~22-28px
- **Nav items**: 12.5px, weight 500
- **Body text**: ~13px
- **Table headers**: ~11px, uppercase, letter-spacing

---

## Layout

### Main TMS

| Zone | Width | Notes |
|---|---|---|
| Header | 100% | Fixed height, dark navy fill |
| Scope bar | 100% | Below header, light |
| Sidebar | 220px | Fixed, full height below header; dark navy gradient |
| Main content | calc(100% - 220px) | Padding 28px |
| Debug bar | 100% | Dev/pilot only |

### Planning Workspace

| Zone | Width | Notes |
|---|---|---|
| Header | 100% | Fixed, dark navy |
| Sidebar | 216px | Fixed, white |
| Main content | calc(100% - 216px) | Padding varies per page |

---

## Component patterns

### Navigation item (Main TMS)

The sidebar is **dark navy**, not light. This section previously documented a light
nav with dark text — every property in it was wrong. Verified against the source
2026-08-22.

```css
/* .sidenav — linear-gradient(180deg, #001b3d 0%, #002550 100%) */
.nav-item {
  padding: 11px var(--sp-md);       /* 16px */
  font-size: 12px;
  font-weight: 600;
  color: rgba(255,255,255,.9);
  border-left: 2.5px solid transparent;
}
.nav-item.active {
  background: var(--nav-active-bg);      /* rgba(81,176,227,.20) */
  color: #fff;
  border-left-color: var(--nav-active-border);   /* #51b0e3 */
  padding-left: calc(var(--sp-md) - 2.5px);
  font-weight: 700;
}
.nav-item:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px var(--focus-ring) inset;   /* --blue inside the chrome */
}
.nav-subitem { padding-left: 30px; font-size: 12px; font-weight: 500; color: var(--steel); }
```

### Navigation category label (Main TMS)

```css
.nav-section {
  text-transform: uppercase;
  font-size: 10px;
  letter-spacing: 0.08em;
  color: var(--muted);
  padding: 14px 18px 4px;
}
```

### Buttons

```css
/* Primary */
.btn-dk  { background: var(--dark); color: #fff; border-radius: 8px; }
/* Secondary */
.btn     { border: 1px solid var(--border); border-radius: 8px; }
/* Sky (action) */
.btn-sky { background: var(--accent-light); color: var(--royal); border-radius: 8px; }
/* Danger */
.btn-red { background: var(--red); color: #fff; border-radius: 8px; }
/* Small variant */
.btn-xs  { font-size: 11px; padding: 3px 8px; }
```

### Status badges

| Badge class | Colour | Use |
|---|---|---|
| `.badge-sqn` | Blue fill | Squadron scope indicator |
| `.badge-wing` | Green fill | Wing scope indicator |
| `.badge-nat` | Purple fill | National scope indicator |
| `.badge-sys` | Steel fill | System admin scope indicator |
| `.ok` / `.warn` / `.red` | Green/Amber/Red | Status indicators |

### Role badge (header scope chip)

Abbreviation chips in the header top-right: "SQN", "WING", "NAT HQ", "SYS". Colour matches scope badge colour. Padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700.

---

## Focus indicator

WCAG 2.2 SC 1.4.11 wants the focus ring at >=3:1 against the surface behind it. No single
value in this palette satisfies both the light surfaces and the dark chrome:

| Candidate | min on light surfaces | min on dark chrome |
|---|---|---|
| `--blue #51b0e3` | 2.00 | 4.60 |
| `--royal #004b8d` | 7.27 | 1.27 |
| `--dark #002f65` | 10.90 | 1.00 |

So the ring is a token — `--focus-ring`, defaulting to `--royal` — and `.topbar,.sidenav`
re-point it to `--blue`. Do not hard-code a ring colour in a component rule.

Two related traps, both previously live:

- A rule that sets `outline:none` at specificity 0-1-1 out-ranks the global
  `:focus-visible` at 0-1-0, removing the ring entirely. Pair any `outline:none` with a
  replacement in the same rule, or don't write it.
- Signalling focus by swapping a border to `--blue` is not sufficient: that is 2.42:1
  on white.

## XSS protection

All user-controlled content inserted into `innerHTML` must pass through `esc(str)`:

```js
function esc(s){
  return String(s||'')
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;');
}
```

Never bypass `esc()` for user-supplied content. The Planning Workspace uses React's JSX, which escapes by default — do not use `dangerouslySetInnerHTML` without review.

---

## What this file is not

- Not a Figma/Sketch spec
- Not a changelog of design decisions
- Not a prescription for the Planning Workspace (it has its own token set)
- Not authority to change any token value — changes require VIG verification and WCAG AA re-check
