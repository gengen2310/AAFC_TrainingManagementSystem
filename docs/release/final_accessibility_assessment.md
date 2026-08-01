# Final Accessibility Assessment (Stage 7, WCAG 2.1/2.2 AA)

## `frontend/` (Planning Workspace) — real, existing coverage, re-run clean

`npx playwright test e2e/accessibility.spec.ts` — **19/19 passed**, covering
Login, Dashboard, Parade Nights (list + create modal), Facilitators, Reports,
`sqn_general` role, Calendar, Curriculum, Weekly Program, Resources, Cadets,
Action Items, Report Catalogue, Imports, Audit, Account Management, Admin/
Settings — zero critical/serious/moderate axe violations across all of them.

## `connected-frontend/` — no existing tooling, scanned live this pass (first time ever, per Stage 0's flag)

Injected a local `axe-core` bundle (from `frontend/node_modules`, not a CDN) into a
live, authenticated session (fresh local backend, isolated frontend copy, never a
deployed environment) and ran `axe.run()` against real rendered pages as `sqn_admin`.

### Dashboard

| Rule | Impact | Nodes |
|---|---|---|
| `color-contrast` | serious | 43 |
| `page-has-heading-one` | moderate | 1 |
| `region` | moderate | 6 |

### Curriculum

| Rule | Impact | Nodes |
|---|---|---|
| `color-contrast` | serious | 40 |
| `select-name` | **critical** | 2 — **fixed this pass** |
| `page-has-heading-one` | moderate | 1 |
| `region` | moderate | 6 |

## Fixed this pass: `select-name` (critical)

`#curr-f-el` and `#curr-f-prog` (the Curriculum page's element/progress filter
dropdowns) had no accessible name at all — no `<label for>`, no `aria-label`, no
`aria-labelledby` — meaning a screen-reader user has no way to know what either
control does. Added `aria-label` to both. Re-scanned live: violation confirmed
gone, zero other regressions (JS syntax re-checked with `node --check`).

**Scope check, not fixed**: grepped the whole file for every `<select id="...">`
lacking any of `aria-label`/`aria-labelledby`/an associated `<label for>` —
**85 matches**. Many are repeated template patterns for dynamically-generated rows
(e.g. `np-ph-${i}`, `d-fa-${i}` — one template, many rendered instances), so the
number of genuinely distinct controls needing a decision is smaller than 85, but
still substantial — this is a systemic gap across the whole file, not a handful of
one-offs. Fixed only the two directly confirmed by a live axe scan; the rest is
recorded here as real, sized-but-unquantified remaining work rather than either
ignored or rushed through with guessed labels (a wrong guessed label is arguably
worse than a missing one for a screen-reader user).

## Not fixed this pass, needs a stakeholder decision: `color-contrast`

Root-caused, not just observed. The specific failing combinations trace directly to
`.claude/rules/frontend.md`'s own documented AAFC VIG palette tokens:

| Foreground | Background | Ratio found | Required | Token match |
|---|---|---:|---:|---|
| `#738daa` | `#002f65` | 3.83 | 4.5 | close to `--pale`/`--dark` |
| `#ffffff` | `#51b0e3` | 2.42 | 4.5 | `--blue` used as a text background |
| `#b0b7bb` | `#ffffff` | 2.03 | 4.5 | **exactly `--lgrey`**, documented as "borders, table headers, quiet backgrounds" — being used as *text* colour, not its documented purpose |

The `--lgrey`/`--blue` failures aren't narrow misses — 2.03 and 2.42 against a 4.5
requirement are both well under half the needed ratio. This is systemic (40-43
elements per page, present on every page scanned) and traces to the brand palette
itself, not a one-off styling mistake. **Deliberately not changed this pass**: these
are official AAFC VIG (Visual Identity Guidelines) brand colours per
`.claude/rules/frontend.md` — adjusting them is a real design/branding decision with
organisational implications beyond code correctness, exactly the kind of change this
engagement's own operating rules say to surface rather than silently alter. Recorded
here with the precise failing combinations so whoever makes that call has the exact
numbers, not a vague "contrast is bad somewhere."

## Not fixed, lower-severity structural gaps

- `page-has-heading-one`: no `<h1>` anywhere in the single-page app — page titles
  are styled `<div>`/`<span>` text, not semantic headings. Affects every page.
- `region`: 6 elements per page not contained by a landmark region (`<main>`,
  `<nav>`, etc. — likely floating UI chrome outside the main layout regions).

Both are real, moderate-impact, whole-app structural gaps — a proper fix means
introducing a semantic heading/landmark structure across the single-file SPA, which
is a real (if smaller than the colour question) design/markup decision better
batched with Stage 6's Front-End Checklist pass than patched ad hoc here.

## Screen-reader / manual testing

Per the plan's stated substitute (no ability to literally operate VoiceOver): this
pass used automated axe-core scans + the structural findings above. Full
keyboard-only navigation traces were not completed this pass — flagged as
remaining Stage 7 work, not silently skipped.
