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
--muted:  #6b7a87

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
- `getScopeType()` returns: `squadron | wing | national | auditor | system_admin`
- `NAV_BY_SCOPE` defines allowed pages per scope
- `applyNavScope()` shows/hides nav items based on current scope
- Do not store operational data in localStorage

## Navigation

- `nav(id)` activates a page by ID (`page-{id}`)
- Add a `nav('xxx')` call in `nav()` for new pages that need data loading
- New nav items must be added to `NAV_BY_SCOPE` for the correct scope(s)

## system_admin scope

- system_admin gets its own scope (`system_admin`) from `getScopeType()`
- System Console (`page-system-console`) is the landing page for system_admin
- System Console loads via `loadSystemConsole()` which calls individual section loaders
- Do not add operational Squadron/Wing pages to the system_admin scope

## API calls

- Use the `api(method, path, body)` helper — handles cookie auth and JSON
- Handle errors with `apiErr(e)` for user-visible messages
- Do not hard-code API base URL — `API_BASE` is resolved at runtime

## Visual review before packaging

For every frontend change:
1. Start backend and frontend servers
2. Login as the affected role
3. Visually verify the change
4. Check for console errors
5. Test the golden path and at least one edge case
