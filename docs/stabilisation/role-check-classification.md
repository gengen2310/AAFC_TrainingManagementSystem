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
| 2026-10-09 | 7 | C3: pure gates -> named predicates in `permissions.py` (`is_oversight_role`, `may_move_account_to_another_squadron`, `may_change_unit_type`, `may_list_service_tickets`, `assi## Remaining 7, by function

| Router · function | n | Cat. | Why it stays |
|---|---|---|---|
| custom_phases · `create_custom_phase` | 1 | B | Pins `scope_id`: a Wing Admin is forced to their own Wing; a National/System Admin may name one. Data targeting, single use. |
| custom_phases · `_require_can_mutate` | 2 | A | Pure gate, **left in place on purpose**: it has a cross-Wing defect (see "Open defect" below). Moving it to `permissions.py` unchanged would present a defective rule as reviewed policy; move it together with the fix. |
| planning · `create_planning_year` | 2 | B | Pins `unit_id` / `wing_id` to the creator's scope (Squadron Admin: own Squadron; Wing Admin: own Wing, and a named unit must be in it, via `wing_admin_outside_own_wing`). |
| planning · `create_location` | 1 | B | Pins `unit_id` to the Squadron Admin's Squadron. |
| training · `list_cadets` | 1 | C | `can_sensitive`: who sees sensitive cadet fields. Equals `WRITE_ROLES` today, but the concept is sensitive-data access, not "writer". Deliberately not rewritten. |

## View scope: one source (C4, 2026-10-09)

"Which Squadrons / Wing may this principal see?" is answered in
`permissions.py` (view-scope section) and nowhere else in the routers:
`visible_squadron_ids`, `squadron_scope_clause`, `level_scope_clause`,
`wing_or_squadron_scope_clause`, `wing_scope_clause`, `wing_in_view`,
`may_view_account`, and `resolve_view_squadron_id(out_of_scope_as_none=)`.
They live in `permissions.py`, not a new `services_scope.py`, because that
module already owns `resolve_view_squadron_id` and states that all scope
decisions flow through it; a second module would split tenancy in two.

The guard counts `==` / `!=` comparisons against `p.wing_id`,
`p.squadron_id`, `p.acting_wing_id`, `p.acting_squadron_id` in routers
(`router_inline_scope_comparisons`): 71 at 8ecd2cd, **11** now.

| Router · function | n | Why it stays |
|---|---|---|
| custom_phases · `_visible_phases` | 3 | Custom-phase ownership (`scope_id` is a Wing or Squadron id), not Squadron visibility. Disagrees with `planning._phase_visible_to` (below); not unified. |
| planning · `_phase_visible_to` | 2 | Same concept, per row; same disagreement. |
| planning · `_curriculum_scope_query` | 2 | Curriculum inheritance (national -> Wing -> Squadron). The Squadron branch takes the Wing from the Squadron row, not from the principal. A different question from visibility. |
| planning · `list_cea_activities`, `set_cea_local_hide` | 2 | The caller's own Squadron's overlay rows (`ActivityLocalHide.unit_id`), only when the caller has a home Squadron. Targeting, not visibility. |
| planning · `command_centre` | 1 | The caller's own Squadron's Wing-event review status (`SquadronEventStatus`). Targeting. |
| planning · `create_planning_year` | 1 | `unit_id != p.squadron_id` inside the Wing Admin branch (B, above). |

### Call sites that deliberately still differ

- **Accounts lists.** `/api/accounts` shows a Wing account every user whose
  own `wing_id` is theirs **or** whose Squadron is in their Wing
  (`wing_or_squadron_scope_clause`). `/api/users` and the accounts section
  of `/api/search` match only the user's own `wing_id`
  (`level_scope_clause`). They differ for a Squadron account stored with no
  `wing_id`. Kept as found; a product decision.
- **Wings.** `wing_in_view` (and `GET /api/wings`, Wing-calendar reads) show
  a Squadron account its own Wing; `Principal.can_view_wing` refuses Squadron
  accounts any Wing-level record. Both kept.
- **Custom phases.** `custom_phases._visible_phases` shows a System Admin
  every phase; `planning._phase_visible_to` (which gates scheduling against a
  phase) shows Wing/Squadron phases only when their `scope_id` equals the
  caller's own Wing/Squadron, so a System Admin, or a National Admin in
  Delegated Intervention, cannot schedule against a phase they can list.
  With no resolvable national, `_above_wing_visible` shows every national
  phase while `_phase_visible_to` shows only pre-v61 (NULL `scope_id`) ones.
- **Acting-scope reference data.** `training.py` (curriculum, elements,
  phases, tags) and `ops.py` (planning-change feed) select by
  `p.acting_wing_id or p.wing_id`: proxy target first, not home scope. A
  different rule, used about 20 times; not routed through the home-scope
  helpers. A `Principal.active_wing_id` (twin of `active_squadron_id`) is
  the natural next step.

### Unrecognised roles

`planning` (years, locations, command-centre default year) and
`service_desk.list_tickets` had no `else` branch, so a principal with a role
outside `ROLES` was unfiltered. The helpers give it the narrowest
(own-Squadron) scope. Unreachable in practice (the API validates roles on
account create and update); recorded because it is a change on paper.

## Open defect (found 2026-10-09, not fixed here)

`custom_phases._require_can_mutate` constrains only `sqn_admin` on
Squadron phases, `wing_admin` on Wing phases and `national_admin` on
national phases. So a **Squadron Admin can rename any Wing's Wing-scoped
phase** and any national or system phase, and a **Wing Admin any national
or system phase** (rename observed; DELETE runs the same guard, by reading,
not exercised). Seen in the parity snapshot: 703's
Squadron Admin (7WG) renamed the second Wing's Wing phase (200), and the
second Wing's Squadron Admin renamed 7WG's (200). The docstring says
"sqn_admin may only mutate their own squadron's phases; wing_admin only
their own wing's". Fixing it changes status codes, so it needs its own
approved change with a regression test.

ta access, not "writer". Deliberately **not** rewritten to `is_writer`. |
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
