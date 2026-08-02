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

## `color-contrast` — fixed in the post-deployment reconciliation pass

**Update**: the original release-blocker classification here (per this
reassessment's own instruction: *"This cannot be classified as a minor P3 solely
because the failing colours are derived from AAFC visual-identity tokens"*) was
correct, and the finding is now **fixed**, not merely documented as a design
question. Introduced contextual accessible tokens alongside the existing brand
palette (which is unchanged for its legitimate border/background/badge uses,
preserving the approved AAFC visual identity as instructed):

| New token | Replaces | Old ratio | New ratio |
|---|---|---:|---:|
| `--muted` (darkened in place: `#6b7a87`→`#657380`) | secondary text almost everywhere | 4.13-4.41:1 | ≥4.5:1 |
| `--muted-text-on-light` | `--lgrey` used as text | 2.03:1 | 4.55-4.85:1 |
| `--text-on-dark-muted` | low-opacity white on dark navy header | 3.83:1 | 4.57:1 |
| `--link-on-light` (= `--royal`) | `--accent`/`--blue` as link text on a pale background | 2.07:1 | 7.53:1 |
| `--status-text-danger` | `--red` as text directly on page/table backgrounds | 4.03-4.35:1 | 4.60-5.29:1 |

Every value was computed (WCAG relative-luminance formula, not eyeballed) against
every real background it appears on — several first-pass values only satisfied
one of two-or-three actual backgrounds and had to be recomputed after live
re-scanning caught the gap (documented in `connected-frontend/index.html`'s own
token comments). Also fixed: an `opacity:.4` de-emphasis technique for calendar
"other month" dates, which blended an already-accessible colour back down below
threshold — replaced with an explicit colour on the text itself.

**Verified live, not asserted — against a local server, per this file's own
established Stage 7 methodology** (see "no existing tooling, scanned live this
pass" above: "fresh local backend, isolated frontend copy, never a deployed
environment"): zero `color-contrast` violations across 18 page-scans (all 12
`sqn_admin`-scope pages, all 6 `wing_admin`-scope pages) after the fix. Full
connected-frontend e2e suite (24 tests, excluding the staging-only screenshot
utility) re-run clean, zero regressions.

**Correction (2026-08-02): this fix is NOT yet deployed to staging or
production.** An earlier version of this section stated it was "deployed to
staging and production, confirmed present in the live served asset at both" —
that was checked and found **false** while preparing this reconciliation pass's
final documents. Both `aafc-tms-frontend-staging` and
`aafc-tms-frontend-production`'s live `app-build` meta tags currently read
commit `699b01f...` (Stage 14's original release candidate), which
`git merge-base --is-ancestor 699b01f ca785b4` confirms **predates** this
fix's commit (`ca785b4`) — neither deployed environment is serving the fixed
CSS. The fix is committed on local `main` (verified via the local/e2e evidence
above) but has not been pushed live anywhere. Deploying it to staging for a
true live re-scan is a reasonable next step and does not touch production, but
per this pass's own standing boundary ("treat as post-deployment hardening,"
no further production deploys without fresh explicit authorization) it was not
done unilaterally — flagged here for the user's decision rather than deployed
silently.

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
