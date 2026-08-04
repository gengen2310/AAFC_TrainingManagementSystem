# Role / Capability Matrix — Stage 0 starting point

Roles (confirmed, `backend/app/permissions.py`): `system_admin`, `national_admin`,
`national_viewer`, `wing_admin`, `wing_viewer`, `sqn_admin`, `sqn_general`,
`auditor`.

## Higher-command-retains-Squadron-capability principle (Section 5/18)

Not yet audited end-to-end against this instruction's specific claim ("they retain
the underlying Squadron views and functions; they gain broader visibility and
comparison"). Known, verified-this-session precedent: `system_admin`'s
`sa-scope-bar` mechanism already does exactly this for Wing/Squadron browsing —
`effectiveScope()` flips to `'wing'`/`'squadron'` and reuses the *exact same*
render paths `wing_admin`/`sqn_admin` use (`.claude/rules/frontend.md`, verified
live against staging in an earlier pass this session). Whether `wing_admin`/
`national_admin` get the equivalent for their own subordinate scopes is not yet
independently verified — pending credentials (REM-18).

## Permission helper families (from `.claude/rules/architecture.md`, restated here for this program's reference)

- `require_can_view_squadron` / `require_can_write_squadron` — tenancy-aware,
  proxy/delegated-intervention-aware. Use wherever a role might act through a
  proxy/delegation mechanism.
- `_require_year_access` (`planning.py`) — simpler, no proxy awareness. Only
  appropriate where the endpoint genuinely has no proxy/delegation concept.
- Swapping one for the other without checking which behaviour an endpoint needs is
  itself a real regression class (silently blocks legitimate delegated access, or
  adds unneeded complexity) — explicitly called out as a standing risk to avoid
  during this remediation.

## Read vs. write mode requirements (verified, `.claude/rules/frontend.md`)

Viewing never requires Proxy/Intervention Mode (`can_view_squadron`/`can_view_wing`
already grant unconditional read access server-side). Only **writes** require
Delegated Intervention (`national_admin`/`system_admin`) or Proxy Mode
(`wing_admin`). This is a load-bearing distinction — Section 18's "read-only
inspection does not require an acting mode; protected subordinate writes require
Proxy or Intervention where designed" matches current behaviour; not yet
re-verified against every single write endpoint added since.

## Not yet done

- Full per-role, per-page capability grid (this file currently records the
  *mechanism*, not an exhaustive capability-by-capability table).
- Live staging verification for `wing_admin`/`national_admin`/`sqn_admin`/
  `sqn_general`/`auditor` via their own login flow (credentials needed).
- 403 root-cause audit (REM-04) will feed directly back into this matrix once done.
