# Dashboard metric dictionary

Status: initial pass, 2026-08-09. Per §23/§97 (dashboard philosophy /
information-design review gate), every chart must answer QUESTION / PURPOSE /
POPULATION / PERIOD / NUMERATOR / DENOMINATOR / SOURCE / REFRESH / ACTION /
DRILL-DOWN / ACCESSIBLE ALTERNATIVE. `backend/app/routers/dashboard.py` has
~35 chart/metric builder functions — substantially more built out than a
first read of the addendum might suggest. This pass documents the
highest-traffic metrics in full; the rest are inventoried with a one-line
purpose so none are silently skipped, with the full-detail pass tracked as
follow-up (see gap register).

## Fully documented this pass

### Parade Night readiness (`_tonight_readiness`, `_upcoming_readiness`, `_session_to_readiness_dict`)

- **Question**: Is tonight's (or the next 8 nights') Parade Night ready to run?
- **Purpose**: Surface missing facilitators/rooms/content before the night,
  not after.
- **Population**: All Sessions for the relevant ParadeNight(s), for the
  caller's squadron scope.
- **Period**: Tonight / next 8 nights (two separate cards, same underlying
  function).
- **Numerator/denominator**: Sessions with facilitator+room+content assigned
  ÷ total Sessions for that night. **A night with zero planned Sessions is
  reported as `not_planned`, never as 100% ready** — confirmed in an earlier
  pass this program (see `docs/release/final_release_program_2026.md`) that
  both the backend (`dashboard.py`) and connected-frontend
  (`index.html:5672`, `:5713`) already guard `sessions_total===0` /
  `planning_status==='not_planned'` correctly. This was the subject of a
  user-reported "0% vs 100% contradiction" that could not be reproduced
  against current code — the working theory (not yet confirmed with the
  user) is a stale production build predating this fix; flagged, not
  silently assumed.
- **Source**: `ParadeNight`, `Session`, `Facilitator`, `TrainingArea` — live
  query per request, no cache.
- **Action**: drill into the specific night; "Resolve issues" links to the
  affected Sessions.

### Curriculum progress by phase (`_curriculum_progress`, `_phases_for_squadron`)

- **Question**: How much of each Training Stage's curriculum has been
  delivered?
- **Numerator/denominator**: delivered Sessions' curriculum items ÷
  applicable curriculum items, per phase.
- **Known limitation, confirmed CLASS-04 (addendum §43)**: this is currently
  computed per **Training Stage**, not per **Training Class** — there is no
  Training Class concept yet (`parallel-class-impact-analysis.md`), so a
  Squadron with 5 parallel Senior classes gets one blended Senior percentage
  today, which addendum §53/§54/§74/§75 explicitly prohibit once Training
  Class exists. Not fixable without the Training Class model landing first;
  tracked as CLASS-07.
- **Phase list source**: `_phases_for_squadron()` reads the governed
  `CurriculumPhase` scoped catalogue (fixed from a hardcoded 8-phase list
  earlier this program) — all applicable phases are represented, including
  zero-completion ones.

### Cancellation/non-delivery reasons (`_cancellation_reasons`, `_cancellation_pareto`)

- **Question**: Why is training not happening?
- **Chart type**: Pareto-style (matches addendum §28.6's requirement).
- **Known data-quality risk (addendum §28.6)**: "Unknown"/"Reason not
  recorded" must not become a normal operational category — needs
  verification this pass whether the frontend surfaces an actionable prompt
  when this category is non-trivial, or just displays it as an inert bar.
  **Not yet verified — tracked as a data-quality-register follow-up.**

## Inventoried, one-line purpose (needs full §23 documentation pass)

| Function | Purpose (one line) |
|---|---|
| `_weekly_outcomes` | Sessions by outcome status, current week |
| `_delivery_trend` | Delivered-Session trend over N weeks |
| `_curriculum_backlog` | Outstanding curriculum requirements (feeds Mission Backlog) |
| `_facilitator_workload` | Sessions per facilitator, current window |
| `_facilitator_status_distribution` | Facilitator active/leave/inactive counts |
| `_facilitator_repeated_gaps` | Facilitators with no assignment over N weeks (under-use signal) |
| `_facilitator_leave_impact` | Sessions affected by recorded facilitator leave |
| `_session_outcomes_distribution` | Delivered/cancelled/not-delivered mix |
| `_squadron_readiness` (Wing scope) | Per-squadron readiness comparison within a Wing |
| `_squadron_delivery_comparison` (Wing scope) | Per-squadron delivery trend comparison |
| `_wing_subject_area_gaps` | Subject areas with no available facilitator, Wing-wide |
| `_wing_readiness_comparison` | Wing-level readiness matrix |
| `_readiness_matrix` (command) | National/Wing readiness matrix, drill-down capable |
| `_risk_forecast` (command) | Deterministic forward-looking risk flags |
| `_immediate_issues` (command) | Consolidated command-level issue list |
| `_command_weekly_delivered` | National/Wing weekly delivered count |
| `_command_reliability_trend` | National/Wing reliability trend |
| `_outcomes_by_unit` (command) | Outcome mix per Wing/Squadron |
| `_facilitator_capability_dependency` | Concentration risk — how much delivery depends on few facilitators |
| `_subject_area_resilience` | Subject areas with only one qualified facilitator |
| `_facilitator_type_distribution` | Facilitator counts by type tag |
| `_long_term_delivery_trend` | Multi-term delivery trend (strategic horizon) |

## Cross-reference

Chart-level fault isolation (`_full_squadron_charts` wrapping each builder in
its own try/except so one failing chart cannot 500 the whole
`/api/dashboard/charts` response) and the matching frontend cleanup
(`index.html:5793`'s catch handler resetting every chart container, not just
2 of 7+) were identified as real gaps in this program's planning phase but
**not yet verified against current code in this pass** — the code may have
moved since that analysis. Re-verify before implementing (tracked in
ux-gap-register.md).
