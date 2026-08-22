# Frontend Rules — AAFC TMS

## SPA structure

- Single-file SPA: `connected-frontend/index.html`
- All CSS, HTML, and JS in one file — no build system, no bundler
- Serve with `python3 -m http.server 8080` from `connected-frontend/`
- Always test at `http://localhost:8080`, never from file:// or extracted ZIP

## Design tokens (AAFC VIG palette)

```css
--blue:   #51b0e3   /* AAFC blue — accent, active states, highlights */
--dark:   #002f65   /* AAFC dark blue — header, nav structure */
--royal:  #004b8d   /* Royal blue — secondary active states */
--steel:  #455560   /* Gunmetal grey — body text, secondary surfaces */
--lgrey:  #b0b7bb   /* Light grey — borders, table headers, quiet backgrounds */
--pale:   #7db2ce   /* Pale blue — subtle information backgrounds */
--red:    #e51937   /* Red — danger, errors, must-attend only */

--bg:           #f4f8fc  /* slight AAFC-blue tint on page background */
--surface:      #ffffff
--surface-2:    #f0f5fa
--border:       #d1dce8
--border-light: #e4edf5

--text:   #1e2d3d  /* deep navy-dark for primary text */
--text-2: #3a4a55
--muted:  #5c6a76

--ok:      #1a7f4b  --ok-bg:   #d4f0e3  --ok-text: #145f38
--warn:    #c97a00  --warn-bg: #fff3cd

--accent:       var(--blue)
--accent-light: #e0f0fa

--sh:  0 1px 4px rgba(0,47,101,.10)
--sh2: 0 4px 16px rgba(0,47,101,.14)
```

Font: `'Montserrat', Arial, sans-serif`

**Planning Workspace (`frontend/`) uses a different token naming convention**
(`--aafc-blue`, `--aafc-dark-blue`, `--surface`, `--muted-text`, plus dark/high-contrast
theme variants — see `frontend/src/styles/tokens.css`) built on the same underlying brand
hex values. This is a naming divergence, not a design-authority conflict — both trace back
to the same AAFC VIG palette. Per `.claude/rules/architecture.md`, do not silently merge the
two into one shared token source or rename either side's variables as a side effect of an
unrelated change; that is an explicit architectural decision to surface to the user, not a
default action.

## XSS prevention

- Always use `esc(str)` helper for user-supplied content inserted into innerHTML
- Never trust API response values as safe HTML
- Never use `eval()` or `new Function()`

## State and scope

- `S` is the session state object — populated from `/api/auth/me` on login
- `getScopeType()` returns the role-derived scope: `squadron | wing | national | auditor | system_admin` — this never changes based on what a user is currently browsing/acting on
- `effectiveScope()` returns the scope actually used for nav/rendering: same as `getScopeType()` for most roles, but flips to `squadron` while Proxy/Delegated Intervention is active, or to `wing`/`squadron` while system_admin is browsing via `S.saScope` (see "system_admin scope" below). Always use `effectiveScope()`, not `getScopeType()`, when deciding what data to fetch or which nav set to show.
- `NAV_BY_SCOPE` defines allowed pages per scope (keyed by `effectiveScope()`'s possible values)
- `applyNavScope()` shows/hides nav items based on `effectiveScope()`
- Do not store operational data in localStorage

## Navigation

- `nav(id)` activates a page by ID (`page-{id}`)
- Add a `nav('xxx')` call in `nav()` for new pages that need data loading
- New nav items must be added to `NAV_BY_SCOPE` for the correct scope(s)

## system_admin scope

- system_admin gets its own role-scope (`system_admin`) from `getScopeType()`; System
  Console (`page-system-console`) remains the default landing page and is always reachable
  from nav regardless of what system_admin is currently browsing (see `applyNavScope()`'s
  dedicated `system-console` override — a deliberate widen, not a narrowing filter like the
  other per-page overrides).
- System Console loads via `loadSystemConsole()` which calls individual section loaders.
- **system_admin does have operational Squadron/Wing pages** — this reverses the prior rule
  here, per explicit user instruction; see `docs/release/qualification_gap_register.md`
  GAP-21 for the full defect this fixed and the reasoning. Reachable via the
  `sa-scope-bar` widget (persistent header bar, rendered by `saRenderScopeBar()`, visible
  only for `S.role==='system_admin'`): a Wing `<select>` and a Squadron `<select>`, backed
  by `S.saScope = {level:'national'|'wing'|'squadron', wingId, squadronId}`.
  `saSelectWing()`/`saSelectSquadron()` update `S.saScope` and reboot the app; `effectiveScope()`
  consults `S.saScope` to return `'wing'`/`'squadron'` (reusing the exact same
  `NAV_BY_SCOPE.wing`/`NAV_BY_SCOPE.squadron` page sets and render functions wing_admin/
  sqn_admin use — a system_admin's Wing/Squadron Dashboard is not a separate
  implementation).
- **Viewing never requires Proxy/Intervention Mode** — `can_view_squadron`/
  `can_view_wing` already grant system_admin unconditional read access server-side, so
  browsing a Wing/Squadron via `sa-scope-bar` is a pure read (no reason prompt, no audit
  entry). Only **writes** require Delegated Intervention, entered via
  `saEnterIntervention()` → the existing `enterMode()`/`exitMode()` machinery shared with
  wing_admin's Proxy Mode (labelled "Delegated Intervention" vs "Proxy Mode" by role —
  see `enterMode()`). Do not wire a write-capable control to `sa-scope-bar`'s selection
  without also requiring Delegated Intervention to be active.
- `saBrowseWingId()`/`saBrowseSquadronId()` return the current browsing selection (or
  `null`) — use these, not `S.session.wing_id`/`squadron_id` (which are always `null` for
  system_admin), when a page's data-fetch needs an explicit `wing_id`/`squadron_id` query
  param for a system_admin caller.
- Any code path that mutates `S.wings`/`S.squadrons` (create/archive/restore) must go
  through the shared `_refreshOrgCache()` helper, which also re-renders `sa-scope-bar` —
  do not add a new Wing/Squadron create or archive flow that updates the cache without
  calling it, or the scope-selector will silently go stale (this was itself GAP-21's
  first follow-on defect).
- Native `alert()`/`confirm()`/`prompt()` dialogs used by System Console's archive/create
  handlers and by `enterMode()` block the page entirely under browser automation (Claude
  in Chrome, Playwright, etc.) — when testing these flows via an automated browser tool,
  call the underlying `api(...)` request directly instead of clicking the button, and
  replicate the handler's own post-call state refresh (see `enterMode()`/`saSelectWing()`
  for the exact sequence: update `S.proxy`/`S.saScope`, then `loadData(); renderAll();
  updateScopeBanner(); updateModeBanner(); updateDebugBar(); bootApp();`).

## API calls

- Use the `api(path, opts)` helper — handles cookie auth and JSON. **The signature is
  `api(path, opts = {})`, path first**, matching `fetch`; `opts` takes `method`, `body`
  (plain objects are auto-serialised), and `headers`. Writing `api('GET', path)` sends the
  request to the relative URL `GET` and silently fails — this had broken the Service Desk
  ticket list and ticket save until 2026-08-22. This correction has been lost twice to
  concurrent work in this shared checkout; if you see `api(method, path, body)` here
  again, check it against `async function api(` in connected-frontend/index.html before
  believing it.
- Handle errors with `apiErr(e)` for user-visible messages
- Do not hard-code API base URL — `API_BASE` is resolved at runtime

## Visual review before packaging

For every frontend change:
1. Start backend and frontend servers
2. Login as the affected role
3. Visually verify the change
4. Check for console errors
5. Test the golden path and at least one edge case
