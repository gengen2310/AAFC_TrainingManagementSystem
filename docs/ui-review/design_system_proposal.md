# Design System Proposal — AAFC TMS

Audit date: 2026-08-06. This is a proposal; nothing here is implemented.
Per the audit mandate: no application changes until this report is reviewed.

---

## Current state: two divergent token sets, same brand palette

Both frontends derive from the AAFC Visual Identity Guide palette (hex values are identical) but use different token names and slightly different application rules.

| Concept | Main TMS token | PW token | Hex value |
|---|---|---|---|
| Dark navy (header, nav) | `--dark` | `--aafc-dark-blue` | `#002f65` |
| AAFC blue (accent) | `--blue` | `--aafc-blue` | `#51b0e3` |
| Royal blue (secondary) | `--royal` | (no equivalent) | `#004b8d` |
| Steel grey (body text) | `--steel` | `--aafc-steel` | `#455560` |
| Light grey (borders) | `--lgrey` | (mapped differently) | `#b0b7bb` |
| Page background | `--bg` | `--background` | `#f4f8fc` |
| Surface / card | `--surface` | `--surface` | `#ffffff` |

**Recommendation**: Do not merge or rename either side's tokens as part of this review — that is an explicit architectural decision (per `.claude/rules/architecture.md`). Document the mapping above so future cross-app consistency work has a clear reference.

---

## Component divergences observed

### Active nav item

| | Main TMS | Planning Workspace |
|---|---|---|
| Treatment | 3px left border (--blue) + blue text + light blue bg | Dark navy fill + white text |
| Metaphor | Selection indicator | Active tab fill |

Both are valid patterns. The border-indicator is the standard AAFC design; the filled approach is the React component's implementation. A shared design decision is needed before unification.

### Buttons

| | Main TMS | Planning Workspace |
|---|---|---|
| Border-radius | 8px | ~10px (appears rounder) |
| Primary colour | `--dark` (#002f65) fill | `--aafc-dark-blue` (#002f65) fill |
| Secondary colour | Outline / border | Outline / border |
| Danger | `--red` (#e51937) fill | Amber/red outline |

### Typography

Both use `'Montserrat', Arial, sans-serif`. Main TMS uses class-based size hierarchy. PW uses Tailwind-influenced utilities. No shared font scale exists.

---

## Structural gaps to address (design decisions, not code)

### 1. Mobile navigation pattern

Neither app has a mobile navigation solution. Options:

| Pattern | Pros | Cons |
|---|---|---|
| Hamburger → slide-in drawer | Familiar, fits existing sidebar structure | Adds JS, increases SPA complexity |
| Bottom tab bar (4-5 core tabs) | Native feel, thumb-reachable | Requires curating tabs per role/scope |
| Full-screen nav menu overlay | Simple to implement | Disrupts context |

**Recommendation for discussion**: Hamburger → slide-in drawer reusing the existing sidebar HTML. The sidebar already has all the correct nav items per scope; adding a toggle + CSS transition is the minimum change.

### 2. Semantic heading / landmark structure (Main TMS)

Every page in connected-frontend needs:
- A `<h1>` matching the visible page title
- `<nav>` wrapping the sidebar
- `<main>` wrapping the content area
- A skip-to-main-content link

This is a single-pass change across the single-file SPA. It does not change any visible rendering; it only adds semantic elements that currently exist as `<div>`.

### 3. Cross-app navigation prominence

Consider a persistent "Planning Workspace" entry point that is always visible to sqn_admin roles (not conditionally hidden). This mirrors the "← Main TMS" link in PW which is always shown.

---

## Tokens to define for shared reference (not to implement yet)

If a future shared token layer is approved, the following accessible contextual tokens already exist in Main TMS and should be mirrored in PW:

| Token | Value | Purpose |
|---|---|---|
| `--muted` | `#657380` | Secondary body text on light backgrounds (WCAG AA) |
| `--muted-text-on-light` | `#6e7275` | Replaces `--lgrey` when used as text colour |
| `--text-on-dark-muted` | `#7e9bbb` | Low-prominence text on dark navy |
| `--link-on-light` | `#004b8d` (--royal) | Accessible link colour on light bg (7.53:1) |
| `--status-text-danger` | `#d41733` | Danger text on page/table backgrounds (WCAG AA) |
