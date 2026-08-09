# Workflow map

Status: initial pass, 2026-08-09. Per §37 — for each high-frequency workflow,
record the current click/screen/field count as a baseline before any
efficiency work, so improvements can be measured rather than asserted.

This pass records which workflows exist and where, without yet doing the
full click-count instrumentation §37 asks for (that requires either live
browser walkthroughs or careful UI-code tracing per workflow — a larger,
separate pass). Recording the map now so the count work has a scaffold to
fill in, rather than starting both at once.

| Workflow | Main TMS entry point | Planning Workspace entry point | Click/field count baseline |
|---|---|---|---|
| Add Facilitator | Facilitators tab → Add | Not primary surface (PW mainly consumes, not authors, facilitators — needs confirmation) | Not yet measured |
| Create Training Year | Activities/Setup | `GuidedYearSetupModal.tsx` | Not yet measured |
| Generate Parade Nights | Activities → Generate Parade Nights modal (frequency/weekday/date range/preview) | Setup flow | Not yet measured |
| Add Activity | Activities tab → Add Holiday / Generate Activities | Activities panel | Not yet measured |
| Schedule Session | Parade Night detail → session card | Parade Night Builder (PW) | Not yet measured |
| Assign Facilitator | Session edit modal | Session edit in PW | Not yet measured |
| Assign Training Area | Session edit modal | Session edit in PW | Not yet measured |
| Record outcome | Session card → status change | Not primary PW surface | Not yet measured |
| Move Session | Not confirmed whether drag/drop exists in Main TMS | PW (React, more likely to support this) | Not yet measured |
| Publish Weekly Program | Not yet located | Not yet located | Not yet measured |
| Find curriculum | Curriculum tab, filters | Mission Backlog | Not yet measured |
| Create account | Account Management → Add | N/A (Main TMS only) | Not yet measured |

## Next step

Full instrumentation requires either: (a) live Playwright walkthroughs
counting actual clicks per workflow against staging, or (b) careful reading
of each modal/form's field count and step sequence in both frontends. Neither
was done in this pass — recorded honestly as not-yet-measured rather than
estimated, per this program's own "no false closure" discipline
(`.claude/rules/capability-preservation.md` §3).
