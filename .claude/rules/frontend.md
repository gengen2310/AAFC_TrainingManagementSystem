# Frontend Rules — AAFC TMS

## SPA structure

- Single-file SPA: `connected-frontend/index.html`
- All CSS, HTML, and JS in one file — no build system, no bundler
- Serve with `python3 -m http.server 8080` from `connected-frontend/`
- Always test at `http://localhost:8080`, never from file:// or extracted ZIP

## Design tokens (AAFC VIG palette)

```css
--blue:   #51b0e3   /* AAFC blue */
--dark:   #002f65   /* AAFC dark blue */
--royal:  #004b8d
--steel:  #455560
--lgrey:  #b0b7bb
--red:    #e51937
--bg:     #f4f8fc
--border: #d1dce8
--text:   #1e2d3d
--muted:  #6b7a87
```

Font: `'Montserrat', Arial, sans-serif`

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
