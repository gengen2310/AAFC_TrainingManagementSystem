# B-DS — Design System Spec

**Sub-project B, Phase 1 of 5**
Visual design system for the AAFC TMS Apple-metallic luxury redesign.
All decisions below were confirmed through visual companion review sessions.

---

## 1. Design direction

**Material language:** Official, calm, premium. Dark satin navy shell with white operational surfaces. The login frame IS the product identity — the rest of the app is functional and clear. Every spacing, size, and colour decision must be derivable from the token system; nothing is arbitrary.

**Target user:** Training officers, including users 80+ years old with limited tech background. Sufficient padding, airy data rows, unmissable active states, no decorative complexity.

**Character:** AAFC defence identity — not consumer-app playful, not enterprise-grey corporate. Precision over flair.

---

## 2. Colour tokens

Unchanged from existing AAFC VIG palette. Reproduced here for spec completeness.

```css
/* Brand */
--blue:   #51b0e3   /* AAFC blue — accent, active states, highlights */
--dark:   #002f65   /* AAFC dark blue — header, nav structure         */
--royal:  #004b8d   /* Royal blue — secondary active, ghost buttons   */
--steel:  #455560   /* Gunmetal grey — body text, secondary surfaces  */
--lgrey:  #b0b7bb   /* Light grey — borders, quiet backgrounds        */

/* Surfaces */
--bg:           #f4f8fc   /* page background — slight AAFC-blue tint */
--surface:      #ffffff
--surface-2:    #f0f5fa
--border:       #d1dce8
--border-light: #e4edf5

/* Text */
--text:   #1e2d3d
--text-2: #3a4a55
--muted:  #5c6a76

/* Semantic */
--ok:       #1a7f4b   --ok-bg:   #d4f0e3   --ok-text: #145f38
--warn:     #c97a00   --warn-bg: #fff3cd
--danger:   #e51937

/* Accent aliases */
--accent:       var(--blue)
--accent-light: #e0f0fa

/* Nav active wash */
--nav-active-bg: rgba(81,176,227,.20)
--nav-active-border: #51b0e3

/* Shadows */
--sh:  0 1px 4px rgba(0,47,101,.10)
--sh2: 0 4px 16px rgba(0,47,101,.14)
```

---

## 3. Typography

**Font family:** `'Montserrat', Arial, sans-serif` — single family across all weights.

**Tabular numerals (required on all data values):**
```css
font-variant-numeric: tabular-nums;
font-feature-settings: "tnum";
```

### Type scale

| Role | Size | Weight | Usage |
|------|------|--------|-------|
| Page heading | 14px | 800 | Content area `<h1>` — `color: var(--dark)` |
| Card value — large | 32px | 800 | Hero stat blocks |
| Card value — medium | 22px | 800 | Standard dashboard stats |
| Card value — small | 11px | 700 | Compact data |
| Body | 13px | 500 | General content, table cells (airy) |
| Body small | 12px | 500 | Table cells (balanced), secondary text |
| Label | 10px | 700 | `letter-spacing:.08em; text-transform:uppercase` — field labels, column headers |
| Label small | 9px | 700 | `letter-spacing:.07em; text-transform:uppercase` — badge text, stat labels |
| Caption | 10px | 600 | Nav footer, metadata |

---

## 4. Spacing system

All padding, gap, and margin values must snap to one of these tokens. Nothing picks an arbitrary value.

```css
--sp-xs:  8px    /* badge internals, icon padding, tight gutters    */
--sp-sm: 12px    /* small card internal padding, table cell vertical */
--sp-md: 16px    /* medium card padding, table cell horizontal       */
--sp-lg: 20px    /* large card padding, content area inset           */
--sp-xl: 24px    /* hero blocks, modal padding                       */

--gap-cards: 10px  /* grid gap between sibling cards                */
--radius:     6px  /* standard border-radius for cards and tables   */
--radius-lg: 10px  /* login card, modal                             */
```

**Alignment rule:** The content area uses `--sp-lg` (20px) padding on all four sides. Every element within — page heading, card grid, table — starts from that same left edge. No element may add extra left margin that breaks this alignment.

---

## 5. Elevation system — Cards

**Confirmed: Hairline + whisper** (option B from review session).

```css
/* Standard card */
.card {
  background: var(--surface);
  border: 1px solid var(--border);          /* #d1dce8 */
  border-radius: var(--radius);             /* 6px */
  box-shadow: 0 1px 3px rgba(0,47,101,.07); /* whisper lift */
}

/* Login card — larger radius, stronger shadow */
.card-login {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);          /* 10px */
  box-shadow:
    0 1px 3px rgba(0,47,101,.08),
    0 8px 32px rgba(0,0,0,.28);
}

/* Login top-edge accent stripe */
.card-login::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0; height: 3px;
  background: linear-gradient(90deg, #002f65, #004b8d 50%, #51b0e3);
  opacity: .7;
}
```

### Card size tiers

Cards must declare a tier. Padding and text scale are set by the tier — not by the individual card.

```css
/* Small */
.card-sm { padding: var(--sp-sm); }   /* 12px all sides */

/* Medium — standard dashboard stat */
.card-md { padding: var(--sp-md); }   /* 16px all sides */

/* Large — hero / primary metric */
.card-lg { padding: var(--sp-lg); }   /* 20px all sides */
```

---

## 6. Shell — Navigation sidebar

**Confirmed: Satin navy** (option B from review session).

```css
.sidebar {
  width: 156px;
  background: linear-gradient(180deg, #001b3d 0%, #002550 100%);
  border-right: 1px solid rgba(255,255,255,.06);
}

/* Right-edge 1px highlight — light catching the rim */
.sidebar::after {
  content: '';
  position: absolute;
  top: 0; right: 0; bottom: 0; width: 1px;
  background: linear-gradient(
    180deg,
    rgba(255,255,255,.08),
    rgba(255,255,255,.03) 60%,
    transparent
  );
}
```

### Logo bar

Unit name only — no role label, no wing, no badge.

```css
.logo-bar {
  padding: var(--sp-md) var(--sp-md) var(--sp-sm);
  border-bottom: 1px solid rgba(255,255,255,.07);
}
.unit-name {
  font-size: 13px;
  font-weight: 800;
  color: rgba(255,255,255,.9);
  letter-spacing: .01em;
}
```

### Nav items

```css
.nav-item {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 10px var(--sp-md);
  font-size: 11px;
  font-weight: 600;
  color: rgba(255,255,255,.48);
  letter-spacing: .01em;
}

.nav-item:hover:not(.active) {
  color: rgba(255,255,255,.72);
  background: rgba(255,255,255,.04);
}
```

### Nav active state

**Confirmed: Full-width fill + left stripe** (modified C from review session — no rounded right edge).

```css
.nav-item.active {
  color: #fff;
  background: var(--nav-active-bg);          /* rgba(81,176,227,.20) */
  border-left: 2.5px solid var(--nav-active-border); /* #51b0e3 */
  padding-left: calc(var(--sp-md) - 2.5px);
}
```

---

## 7. Button system

**Confirmed: Blue-tinted secondary** (option B from review session).

```css
/* ── Primary ── dark navy gradient, engineered depth */
.btn-primary {
  background: linear-gradient(180deg, #003a7a 0%, #002050 100%);
  color: #fff;
  border: 1px solid rgba(0,30,65,.2);
  box-shadow:
    0 1px 0 rgba(255,255,255,.10) inset,
    0 -1px 0 rgba(0,0,0,.20) inset,
    0 1px 3px rgba(0,30,65,.25);
}
.btn-primary:hover {
  background: linear-gradient(180deg, #004590 0%, #002a60 100%);
}
.btn-primary:active {
  background: linear-gradient(180deg, #001e42 0%, #00183a 100%);
  transform: translateY(1px);
}

/* ── Secondary ── blue tinted */
.btn-secondary {
  background: #f0f7ff;
  color: var(--dark);                   /* #002f65 */
  border: 1.5px solid #bee3f8;
  box-shadow: 0 1px 2px rgba(0,47,101,.06);
}

/* ── Ghost / text ── royal blue, no border */
.btn-ghost {
  background: transparent;
  color: var(--royal);                  /* #004b8d */
  border: 1px solid transparent;
  font-weight: 600;
}

/* ── Danger ── red gradient, same engineering as primary */
.btn-danger {
  background: linear-gradient(180deg, #c8102e 0%, #9a0b22 100%);
  color: #fff;
  border: 1px solid rgba(100,0,20,.3);
  box-shadow:
    0 1px 0 rgba(255,255,255,.08) inset,
    0 -1px 0 rgba(0,0,0,.20) inset,
    0 1px 3px rgba(150,0,30,.3);
}

/* ── Disabled ── same across all variants */
.btn-disabled {
  background: #f4f8fc;
  color: #b0b7bb;
  border: 1px solid var(--border);
  cursor: not-allowed;
  opacity: .7;
}

/* Shared button base */
.btn {
  padding: 10px 16px;
  border-radius: 5px;
  font-family: 'Montserrat', Arial, sans-serif;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: .04em;
  cursor: pointer;
  transition: background .12s, box-shadow .12s;
}
```

---

## 8. Table system

**Confirmed: Airy density** (option C from review session).

```css
/* Table shell */
.tbl {
  width: 100%;
  border-collapse: collapse;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}

/* Column headers */
.tbl th {
  padding: var(--sp-xs) var(--sp-md);       /* 8px 16px */
  background: var(--surface-2);             /* #f0f5fa  */
  border-bottom: 1px solid var(--border);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--steel);
  text-align: left;
  white-space: nowrap;
}

/* Data cells — airy */
.tbl td {
  padding: var(--sp-sm) var(--sp-md);       /* 12px 16px */
  font-size: 13px;
  color: var(--text);
  font-weight: 500;
  border-bottom: 1px solid var(--border-light);
}
.tbl tr:last-child td { border-bottom: none; }

/* Numeric columns */
.tbl td.num {
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum";
}
```

**Alignment rule:** Table left edge must align with page heading and card grid left edge. The content area `--sp-lg` (20px) padding provides this — tables must not add extra margin.

### Status badges

```css
.badge {
  display: inline-block;
  border-radius: 3px;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: .06em;
  text-transform: uppercase;
  padding: 2px 6px;
}
.badge-ok   { background: var(--ok-bg);   color: var(--ok-text); }
.badge-warn { background: var(--warn-bg); color: var(--warn);    }
.badge-draft { background: var(--surface-2); color: var(--steel); }
```

---

## 9. Login screen

**Confirmed: White card, multi-step flow** (login-v4.html from review session).

### Flow
1. **Step 1** — Select account type (Squadron / Wing / National / System) → Wing (if applicable) → Unit (if applicable) → **Next**
2. **Step 2** — Summary banner (shows selection + `‹ Change selection` in `--blue`, no underline) → Access Code input → **Sign In**

### Background
```css
body.login {
  background: linear-gradient(160deg, #001e42 0%, #000e26 100%);
}
body.login::before {
  content: '';
  position: absolute; inset: 0;
  background: radial-gradient(ellipse at 50% 40%, rgba(81,176,227,.05) 0%, transparent 55%);
}
```

### AAFC badge (crest)
```css
.crest {
  width: 48px; height: 48px;
  border-radius: 8px;
  background: #f0f7ff;
  border: 1px solid var(--border);
  display: flex; align-items: center; justify-content: center;
  padding: 10px;  /* equal on all four sides */
}
```

### Org identity block
- `"AAFC"` — 11px / 800 / `#002f65` / `letter-spacing:.04em`
- `"Australian Air Force Cadets"` — 8px / 700 / `#455560` / `letter-spacing:.05em` / `white-space:nowrap` / uppercase
- `"Training Management System"` — 13px / 800 / `#001e42`
- Divider: `28px × 2px` / `#51b0e3` / `opacity:.6`

### Back link (Step 2)
```css
.acct-back {
  color: var(--blue);       /* #51b0e3 */
  font-size: 11px;
  font-weight: 600;
  text-decoration: none;    /* no underline */
  background: none;
  border: none;
  cursor: pointer;
}
/* Text: ‹ Change selection */
```

---

## 10. Motion

Snappy and functional. No theatrics. Animations reinforce action — they do not decorate.

```css
/* Standard transition for interactive state changes */
transition: background .12s, box-shadow .12s, color .12s, border-color .15s;

/* Focus ring */
:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px rgba(81,176,227,.18);
}

/* Avoid motion where user has reduced-motion preference */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { transition-duration: .01ms !important; }
}
```

---

## 11. Accessibility — older user rules

These rules apply to every component in B-Shell, B-Content, B-PW, and B-Help.

1. **Minimum tap/click target:** 40 × 40px. Padding over icon size.
2. **Minimum body text:** 13px (airy table rows, form inputs). Never below 11px for any interactive label.
3. **Active nav state must be unmissable** — confirmed fill + stripe treatment.
4. **No information conveyed by colour alone** — badges include a text label; status colours pair with text.
5. **Focus ring always visible** — `box-shadow: 0 0 0 3px rgba(81,176,227,.18)` on `:focus-visible`.
6. **Form labels always above fields**, never placeholder-only.
7. **Error messages in text** — never colour alone.

---

## 12. What this spec governs

This B-DS spec is the single source of truth for all downstream B phases:

| Phase | Scope |
|-------|-------|
| B-Shell | Global nav, topbar, login screen, responsive nav |
| B-Content | Dashboard, Activities, Cadets, Curriculum, Settings |
| B-PW | Planning Workspace redesign |
| B-Help | Help & Reference section |

No phase may introduce spacing values, colours, or component variants not defined here without first updating this spec.
