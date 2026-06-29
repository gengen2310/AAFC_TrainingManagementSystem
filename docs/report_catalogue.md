# Report catalogue

## Implemented end-to-end (with decision status + drill-down)
- Training summary (status counts) — `/api/reports/summary`
- Next parade readiness (per-night score, band, deductions) — `/api/reports/readiness`
- Curriculum coverage (scheduled/delivered/unscheduled) — `/api/reports/curriculum-coverage`
- Facilitator load (with risk banding) — `/api/reports/facilitator-load`
- Not delivered — `/api/reports/not-delivered`
- Wing overview (per-squadron readiness/plan flags) — `/api/reports/wing-overview`
- National overview (per-wing rollup) — `/api/reports/national-overview`

## Pattern for the remaining ~50 spec reports (later milestones)
Each is a scoped query → decision status (no_action / monitor / action_required /
command_decision_required) → drill-down record list. The Squadron/Wing/National report lists
in the spec are organised the same way and reuse the readiness engine, session/curriculum
queries, and audit/import logs already present.
