# Router role checks: classification (2026-10-04)

The architecture guard counts direct `p.role ==/!=/in/not in` checks in
`backend/app/routers/`. This file classifies every remaining one, so the next
person can tell **intended** role-specific behaviour from debt, and knows what
has already been looked at.

Categories (from the stabilisation brief, section 14):

- **A, pure gate**: decides whether the request may proceed.
- **B, scope selection**: decides which data the request sees or targets.
- **C, response shaping**: decides which fields or rows are shown.
- **D, role-specific product rule**: a business rule that is about a role.

Only A moves into named central predicates by default. B moves when the same
semantics repeat. C and D stay where they are unless they repeat. Nothing is
centralised for appearance alone.

## Progress

| Date | Count | Change |
|---|---|---|
| PR #68 baseline | 185 | |
| #69 | 94 | Named predicates and central role sets |
| #71 | 82 | `may_view_cadet_records` / `may_record_session_outcomes`: 12 identical `sqn_general` gates in `training.py` |
| #71 | 68 | `wing_admin_outside_own_wing`: 14 sites (each keeps its own error). Ten of them had no cross-Wing denial test; `test_cross_wing_write_isolation.py` adds one per site. |
| #71 | 57 | `Principal.is_squadron`: 11 inline `("sqn_admin", "sqn_general")` scope tuples |
| #71 | 46 | Router-local role sets onto central predicates (verified set-equal); 3 duplicate constants removed |
| #71 | 43 | `sqn_admin_outside_own_squadron`: 3 sites |

Every step preserved the error contract and was checked by the full backend
suite. The rewrites to new predicates were mutation-checked (the predicate
disabled, the tests confirmed to fail).

## Remaining 43, by function

| Router · function | n | Cat. | Why it stays (or what would move it) |
|---|---|---|---|
| accounts · `change_scope` | 1 | B | A Squadron Admin's destination is fixed to their own Squadron. Single use. |
| accounts · `_can_write_flight` | 2 | A/B | Per-role branch: a Wing Admin by the Squadron's Wing, a Squadron Admin by Squadron. The branches differ, so a single predicate would hide them. |
| custom_phases · `create_custom_phase` | 2 | B | Forces `scope_id` (a Wing Admin is pinned to their own Wing; a System Admin may choose the national entity). |
| custom_phases · `_require_can_mutate` | 2 | A | Wing and national ownership (a Wing Admin may not mutate a national or system phase, and so on). Scope-type specific. |
| jobs · `get_job` | 1 | A | Owner or oversight role. `_OVERSIGHT_ROLES` is every role except the two Squadron roles. Could become `not p.is_squadron`, but "oversight" is the named concept; left as is. |
| organisations · `update_squadron` | 1 | D | Which Squadron fields a Squadron Admin may edit about their own unit. |
| organisations · `list_users` | 2 | B | Squadron and Wing filtering of the user list. |
| organisations · `enter_proxy` | 1 | A/D | A Wing Admin may only proxy into their own Wing; national roles get delegated intervention mode. |
| planning · `_require_year_access` | 3 | A/B | Year access by level. This is already the planning router's single access function. |
| planning · `create_planning_year` | 2 | B | Pins `unit_id` or `wing_id` to the creator's own scope. |
| planning · `create_location` | 1 | B | Pins `unit_id` to the Squadron Admin's Squadron. |
| search · `search_entities` | 4 | B/C | Search scope by level. `search._NATIONAL_ROLES` deliberately excludes `auditor`, which is handled on the next line. Candidates for `p.is_national` / `p.is_wing` only after the auditor branch is pinned by a test. |
| service_desk · `list_tickets` | 2 | A/B | `auditor` and `sqn_general` are refused (A); a Squadron Admin sees their own Squadron (B). |
| service_desk · `update_ticket` | 2 | D | Assignee eligibility: a Wing Admin may assign only to Wing Admins of their own Wing. A product rule about the assignee's role. |
| service_desk · `get_email_config` / `upsert_email_config` | 4 | B | Which notification-config scopes each admin level may read or write. |
| setup · `setup_status` | 1 | C | National-only counters in the setup report. |
| training · `list_cadets` | 1 | C | `can_sensitive`: who sees sensitive cadet fields. The set happens to equal `WRITE_ROLES`, but the concept is sensitive-data access, not "writer". Deliberately **not** rewritten to `is_writer`. |
| training · `list_faq` | 1 | C | Only a System Admin sees unpublished FAQ entries. |
| training · `_can_create_element` / `_can_create_phase` | 5 | A/B | National-scope creation is System Admin only. Squadron scope requires an active proxy for Wing and national roles, plus the Squadron Admin's own-Squadron check. That check (`squadron_id and squadron_id != p.squadron_id`) **differs** from `sqn_admin_outside_own_squadron` because a missing `squadron_id` is allowed here, so it was not merged. |
| training · `_visible_elements` / `_visible_phases` | 2 | B | A Wing Admin sees no Squadron-scope rows unless proxied. |
| training · `_can_create_tag` | 2 | A/B | Same pattern as `_can_create_phase`. |
| wing_calendar · `list_wing_events` | 1 | B | Non-national callers must name a Wing (400 `wing_id_required`). |

## Checked and confirmed intentional

- `custom_phases._NATIONAL_ROLES` omits `system_admin`. Intentional:
  `_visible_phases` handles `system_admin` first ("sees all") and never
  consults the set for it.
- `search._NATIONAL_ROLES` omits `auditor`. Handled by the separate
  `is_auditor` branch.

## Open product question (decided in one place now)

`permissions.may_view_cadet_records` refuses `sqn_general`, a read-only
Squadron role, cadet personal and training records. Whether that is intended
under the read-only policy is for the product owner. Changing it is a one-line
change there, plus the expectation in `test_sqn_general_record_policies.py`.
