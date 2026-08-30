# 08 — Planning Workspace route disposition

Date: 2026-08-30 · Baseline `fecbcde` · Instruction Part 8

Part 8 says *"Do not mechanically delete them"* and requires each route to be
placed in category A–G. Reachability was proven before disposition, not
grepped.

## The finding that changes Part 8

`frontend/src/App.tsx:162` branches on `MODULE_MODE`. **In module mode the
entire route table is two entries:**

```jsx
<Route path="/planning" element={<PlanningWorkspace />} />
<Route path="*"        element={<Navigate to="/planning" replace />} />
```

The 20-route full application at `App.tsx:189-210` is only reachable when
`MODULE_MODE` is false.

**Both deployed environments run module mode.** Verified by fetching the served
HTML:

| environment | `aafc-module-mode` |
|---|---|
| staging PW | `content="true"` |
| production PW | `content="true"` |

Set by `frontend/docker-entrypoint.sh:19-23` from the Railway `MODULE_MODE`
environment variable.

**Therefore every duplicated management route is already unreachable to every
user in every deployed environment.** The duplication Part 8 describes is not a
live user-facing problem. Part 104's item 33 — *"no material duplicated PW
management workflow remains"* — is satisfied in the deployed product **today**.

## But it is latent, not eliminated

The separation is enforced by **one environment variable**, not by the code. If
`MODULE_MODE` is unset, removed, or forgotten on a new environment, the full
administration application returns immediately — including PW's own
`/accounts`, `/admin`, `/settings`, `/audit` and `/imports`.

That is a single point of failure for a product rule the instruction treats as
architectural.

## Disposition

Category C — *"route is unreachable in module mode"* — applies to all 20.

| route | duplicate of | category | disposition |
|---|---|---|---|
| `/accounts` | TMS Account Management | C | delete with the full-app branch |
| `/admin`, `/settings` | TMS org/unit settings | C | delete |
| `/audit` | TMS Audit Log | C | delete |
| `/imports` | TMS CEA import | C | delete |
| `/cadets` | TMS Cadets | C | delete |
| `/facilitators`, `/facilitator-schedule` | TMS Facilitators | C | delete; suitability already lives in the planning canvas |
| `/resources` | TMS Resources | C | delete |
| `/curriculum` | TMS Curriculum | C | delete |
| `/reports`, `/report-catalogue` | TMS Reports | C | delete |
| `/wing-overview`, `/national-overview` | TMS oversight | C | delete |
| `/dashboard`, `/calendar`, `/parade-nights`, `/weekly-program`, `/action-items` | TMS equivalents | C | delete |
| `/`  (`Home`) | n/a | C | delete |
| `/planning` | — | **A** | **KEEP — this is Planning Workspace** |

## Why this is a decision, not a mechanical edit

Deleting the full-app branch removes ~20 route components and everything only
they import. It is safe today because nothing reaches them. It is *irreversible
cheaply* if the full app is a deliberate future capability.

Two readings of the instruction pull in different directions:

- Part 8: *"route should be removed once parity is proven"* → delete.
- Part 2: *"The two frontends may remain separate deployed services"* and
  *"do not physically merge them"* → the full app is not what Part 2 protects,
  but the instruction never says the full app must go.

Recorded for decision rather than resolved unilaterally.
