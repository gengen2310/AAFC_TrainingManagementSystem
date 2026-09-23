# AAFC TMS UI Design-Compliance Report

Status: PASS — design remediation and the authenticated facilitator lifecycle gate are complete
Date: 2026-09-23
Scope: `connected-frontend/index.html` and `frontend/`

This report records the audit without copying the design contract. The contract remains
[DESIGN.md](../DESIGN.md).

## Areas audited

- Contract wording and repository guidance: `DESIGN.md`, `CLAUDE.md`, and the three applicable
  `.claude/rules/` files.
- Main TMS token declarations, navigation, component CSS, responsive rules, inline styles, and
  `esc()` use in `connected-frontend/index.html`.
- Planning Workspace token contexts and shared component/layout/planning styles.
- Existing Vitest, Playwright, axe, responsive, token-sync, and rendered design-audit coverage.
- React `dangerouslySetInnerHTML` usage and Main TMS `innerHTML` call sites requiring escaping review.

## Pre-remediation audit

| ID | Class | Finding | Evidence / scope | Disposition |
|---|---|---|---|---|
| AUD-01 | A | The opening of `DESIGN.md` said the document was descriptive, not prescriptive. | `DESIGN.md` opening paragraph | Fixed in this change. |
| AUD-02 | A | The closing section said the file was not a prescription for the Planning Workspace. | `DESIGN.md` “What this file is not” | Fixed in this change; separate token names remain allowed. |
| AUD-03 | A | Frontend agent rules did not require reading the canonical contract before UI changes. | `.claude/rules/frontend.md`, `architecture.md`, `capability-preservation.md`, `CLAUDE.md` | Fixed in this change. |
| AUD-04 | D | Planning status and conflict styles scattered literal tint/background/foreground colours instead of semantic theme tokens. | `frontend/src/styles/components.css` and `planning.css` | Tokenised where the semantic meaning is shared; unique print/decorative values remain exceptions. |
| AUD-05 | B/D | Planning Workspace had repeated hard-coded white and status foregrounds in dark-capable component rules. | `planning.css` and component rules | Replaced with foreground/tint tokens where the role is semantic. |
| AUD-06 | B | Focus treatments and theme token coverage require regression protection across light, dark, high-contrast, and `prefers-contrast: more`. | Existing CSS and theme blocks | Added lightweight static contract checks; rendered axe/responsive suites remain required. |
| AUD-07 | C | Both frontends intentionally use different token names and layouts; this is an architectural exception, not a reason to merge them. | `frontend/src/styles/tokens.css`, `connected-frontend/index.html` | Justified exception; canonical contract now states the boundary explicitly. |
| AUD-08 | D | Existing inline styles and one-off compact/print styles are numerous in the single-file Main TMS. | `connected-frontend/index.html` | Not rewritten wholesale; retained where local/print behavior is intentional and tracked as debt. |
| AUD-09 | B | User-controlled Main TMS HTML requires call-site review; React JSX is safe by default and no production `dangerouslySetInnerHTML` usage was found. | `index.html` `innerHTML` sites; `frontend/src` search | Existing `esc()` usage retained; no new unsafe sink introduced. |
| AUD-10 | B/C | Responsive and rendered accessibility checks already exist, including 390px overflow coverage, but require execution for this audit. | `frontend/e2e/responsive-viewports.spec.ts`, `frontend/e2e/accessibility.spec.ts`, design-audit tools | Execute after remediation; results recorded below. |

## Corrections made

- Made `DESIGN.md` an explicit mandatory contract while preserving the existing palette.
- Added canonical-contract references to all applicable agent instructions.
- Added semantic status/tint tokens to the shared light-token source and Planning Workspace theme
  contexts, then replaced repeated Planning Workspace status literals with those tokens.
- Added a lightweight contract checker for required wording, theme contexts, prohibited `html`
  pixel font sizing, and unsafe React HTML sinks.
- Made REM-111 cleanup deterministic: the test now archives only its uniquely named records
  through the authenticated API instead of opening the custom confirmation modal and sleeping.
- Added backend lifecycle regression coverage for active, archived, merged-source, canonical
  merged, and cross-squadron facilitator chart semantics.

## Justified exceptions

- Main TMS and Planning Workspace retain separate architectures and token naming conventions.
- Print-only CSS may use physical print units and neutral print colours.
- Decorative alpha overlays and gradient stops may remain literal when they are not semantic
  foreground/status tokens; they must still pass rendered contrast checks.
- Dense tables and planning canvases may scroll inside their bounded containers, but not widen the
  document at the tested phone widths.

## Verification results

- Static contract guard: `python3 scripts/check_design_contract.py` — PASS.
- Shared-token name guard: `python3 scripts/check_token_sync.py` — PASS (49 shared names
  present; pre-existing Main TMS-only token additions are reported as informational extras).
- Whitespace guard: `git diff --check` — PASS.
- Planning Workspace unit tests: `npm test -- --run` — PASS, 21 files / 141 tests.
- Planning Workspace production build: `npm run build` — PASS; only the repository's existing
  Vite chunk-size warning was emitted.
- Planning Workspace single-file build: `npm run build:single` — PASS; the existing bundle-size
  warning profile is unchanged.
- Frontend typecheck: `npm run typecheck` — PASS.
- Frontend lint: `npm run lint` — PASS with warnings only; no blocking errors remain.
- Planning Workspace rendered Chromium checks:
  `e2e/accessibility.spec.ts` plus `e2e/responsive-viewports.spec.ts` — PASS, 8/8 on the
  final isolated rerun (a combined run had one transient backend 429, which passed after the
  documented rate-limit reset).
  This covered unauthenticated handoff, `sqn_admin`, `sqn_general`, higher-scope selection,
  help drawer, and 390/375/430/tablet/desktop widths.
- Main TMS rendered responsive check:
  `e2e-connected/responsive-viewports.spec.ts` — PASS, 2/2 after adding contained table
  overflow protection. The 390px and 375px authenticated dashboard states have no document
  overflow.
- Main TMS rendered accessibility and responsive checks:
  `e2e-connected/accessibility-hardening.spec.ts` plus `e2e-connected/responsive-viewports.spec.ts`
  — PASS, 17/17 on the final single-worker run.
- Backend dashboard lifecycle tests: `tests/test_dashboard_charts.py` — PASS, 57 passed.
- Backend tests: `python -m pytest tests/ -q --tb=short` — PASS, 2446 passed, 12 skipped,
  3969 warnings.
- REM-111 browser gate — PASS on run 1, PASS on consecutive run 2, and PASS after the
  separate facilitator-statistics test. The final isolated run completed in 4.2 seconds.
- Browser console: Planning Workspace unauthenticated handoff showed expected 401 responses and
  React Router upgrade warnings; no new runtime exception was observed. Main TMS authenticated
  responsive/accessibility workflows completed without a design-related console failure.

## Screenshots and browser workflows

Rendered browser verification was performed against the local Main TMS (`:8080`) and Planning
Workspace (`:5173`) servers. Workflows covered the unauthenticated state, authenticated
sqn-admin and read-only planning states, higher-scope squadron selection, help drawer, mobile
navigation, modal focus, Escape-to-close, visible focus rules, and responsive widths. No
screenshots were committed; the existing Playwright traces/error artifacts remain untracked test
output and are not part of the product change.

## Remaining design debt

- Main TMS is a large single-file SPA with historical inline styles and should be tokenised
  incrementally, not through a risky wholesale rewrite.
- Full authenticated role-by-role browser verification depends on the local seeded backend and
  available test credentials; any unavailable role/state is recorded rather than inferred.
- Historical inline styles and one-off compact/print styles remain incremental tokenisation debt.

## REM-111 root-cause record

The dashboard contract was correct: `/api/dashboard/charts` queries only non-archived
facilitators for the current squadron, and merge archives the source while retaining the
canonical target. The two extra active rows were test-created `ZZRem111A…` and
`ZZRem111C…` survivors. REM-111 called `delFac()` during cleanup, but `delFac()` uses the
custom `confirmAction()` modal; the test never clicked `#confirm-yes-btn`, so neither archive
callback ran. This was test isolation/cleanup, not a production counting defect.

The local diagnostic found the leaked rows by ID, name, squadron, and state. The two rows in
the failing run were active `ZZRem111A…` and active `ZZRem111C…` records in squadron 703;
the corresponding archived B/D source records were already excluded. All locally leaked
`ZZRem111*` artifacts from earlier failed runs were archived through the authenticated API,
preserving their rows and audit history; no unrelated facilitator data was changed.

The final test cleanup now uses the authenticated API directly for only its generated IDs,
then re-reads the chart baseline. Backend regression tests prove active rows count, archived
rows do not count, merged sources do not count, canonical targets do count, and squadron
scope is isolated.

## Final gate

**DESIGN COMPLIANCE: PASS** — all static, build, accessibility, responsive, typecheck,
unit-test, backend, and authenticated REM-111 lifecycle gates pass.
