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
--muted:  #657380;   /* WCAG AA on --bg and --surface; darkened from original #6b7a87 */

/* Accessible contextual tokens (WCAG 2.2 AA — text use only) */
--muted-text-on-light: #6e7275;   /* ≥4.5:1 on both --surface and --bg */
--text-on-dark-muted:  #7e9bbb;   /* ≥4.5:1 on --dark */
--link-on-light:       var(--royal);   /* 7.53:1 on --accent-light */
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
```

### Planning Workspace (`frontend/src/styles/tokens.css`)

Uses a parallel set with `--aafc-` prefix but same underlying hex values:

```css
--aafc-dark-blue: #002f65;    /* = --dark */
--aafc-blue:      #51b0e3;    /* = --blue */
--aafc-steel:     #455560;    /* = --steel */
/* ... light/dark theme variants also defined */
```

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
| Sidebar | 205px | Fixed, full height below header |
| Main content | calc(100% - 205px) | Padding 28px |
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

```css
.nav-item {
  padding: 8px 18px;
  font-size: 12.5px;
  font-weight: 500;
  color: var(--steel);
  border-left: 3px solid transparent;
}
.nav-item.active {
  background: #deeefa;
  color: var(--dark);
  border-left-color: var(--blue);
  font-weight: 700;
}
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
