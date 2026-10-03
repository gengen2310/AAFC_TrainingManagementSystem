# TMS Stabilisation Programme — Predictable Before Clever

**Authorised:** 2026-10-03  
**Canonical branch:** `main`  
**Starting commit:** `431d5f92da6483f41c5917ebb847273b013c7b2d`

## Objective

Move the AAFC TMS from rapid feature construction into a stabilisation and
maintainability phase without changing user-visible behaviour unnecessarily.

The system is already capable of Squadron, Wing and National operation. The
dominant long-term risk is not PostgreSQL row count; it is architectural
entropy: duplicated policy, very large source files, hidden coupling, and a
large change blast radius.

The target request path is deliberately boring:

```
UI -> API/router -> central authorisation -> domain/service logic -> database
```

Audit/logging wraps privileged writes. Database shape is controlled by Alembic.

## Non-negotiable release principles

1. **Predictability first.** The same valid action against the same state must
   produce the same result. Failures must be explicit and recoverable.
2. **No major net-new feature programmes during stabilisation.** Security,
   integrity, release blockers, defects, and work required to complete an
   already-authorised workflow are permitted.
3. **No big-bang rewrite.** Existing behaviour is the contract. Refactor by
   seam, prove parity, then continue.
4. **Backend is the security authority.** Frontend role gating is usability
   only. Role/scope policy belongs in `backend/app/permissions.py` or a named
   permission service/helper.
5. **Alembic is the schema authority.** No production schema mutation outside
   reviewed migrations.
6. **Every fixed defect gets a regression test** at the lowest useful layer,
   plus E2E coverage when the failure was cross-surface or browser-specific.
7. **National scale is tested as concurrency + hierarchy + aggregation**, not
   merely by inserting more cadet rows.
8. **Maintainability is a release property.** Another competent developer must
   be able to trace, test, modify and deploy a subsystem without undocumented
   knowledge.

## Baseline that this programme protects

At the starting commit the connected Main TMS frontend is:

- `connected-frontend/index.html`: **1,243,184 bytes**
- **20,014 lines**
- **791 named JavaScript function declarations**
- approximately **1.22 million characters**

The backend also still contains a substantial amount of router-local role
branching. The initial automated baseline records **184 direct `p.role`
checks** across router modules. Some are data-scoping branches rather than
allow/deny decisions, so they are not blindly replaced. The ratchet prevents
the debt from increasing while it is reduced deliberately.

See `tools/architecture/architecture-baseline.json` and
`tools/architecture/guard.py`.

## Work sequence

### Phase 0 — Canonicalise and freeze

Status: **ACTIVE**

- `gengen2310/AAFC_TrainingManagementSystem` is the canonical repository.
- `main` is the integration/deployment branch.
- New work uses short-lived branches and PRs.
- Preserve the existing deployment fingerprint, migration, backup and
  rollback gates.
- Do not revive the older `gengen2310/aafc-tms` repository as a release
  source.

Exit: all active development references the canonical repository and CI guards
run on every PR to `main`.

### Phase 1 — Put architecture debt on ratchets

Status: **IMPLEMENTED IN THIS BRANCH**

- Main TMS monolith cannot silently grow.
- Router-local direct role-policy checks cannot increase.
- Any deliberate baseline increase requires explicit review in the same PR.

This does not claim the debt is solved. It prevents backsliding while
subsequent phases reduce it.

### Phase 2 — Centralise permission/scope policy

Status: **NEXT**

Work in small, behaviour-preserving slices:

1. pure allow/deny gates first;
2. repeated "visible Wing/Squadron IDs for this principal" derivation second;
3. domain-specific exceptions only after their tests pin current behaviour.

For every migrated rule:
- add/update permission-unit tests;
- keep endpoint status/error contracts unless a defect is separately approved;
- run role/scope matrix tests for Squadron general/admin, Wing viewer/admin,
  National viewer/admin, Auditor and System Admin;
- reduce the corresponding architecture baseline count.

Exit: routers orchestrate requests; they do not invent authorization policy.

### Phase 3 — Extract backend domain services

Status: **PLANNED**

Priority order is based on current size and change blast radius:

1. `training.py`
2. `planning.py`
3. `dashboard.py`

Start with pure computation and query-building seams: conflict detection,
coverage/readiness, scope-filter derivation, aggregation, import validation.
Do not move HTTP models and business logic simultaneously.

Exit: large routers are substantially thinner and domain logic is unit-testable
without an HTTP request.

### Phase 4 — Modularise the connected frontend

Status: **PLANNED**

Do **not** replace the Main TMS with the React Planning Workspace.

Preserve the existing deployed Main TMS behaviour while introducing a
maintainable source structure. The preferred end state is modular source that
can still produce a deterministic deployable artifact if the single-file
deployment constraint is retained.

Extraction order:

1. shell/navigation and runtime state
2. API/error helpers
3. auth/session/scope/permission presentation
4. shared dialog/table/form/render utilities
5. Training Program
6. Planning / Parade Nights / Weekly Program
7. Cadet Management
8. Accounts
9. Service Desk
10. Administration / System Console
11. Reports/imports/audit

Each extraction must be parity-only: no feature redesign in the same change.

Exit: feature work no longer requires editing a 20k-line entry point and the
architecture guard baseline approaches zero monolith debt.

### Phase 5 — Data/query scalability

Status: **PLANNED**

Profile before changing queries. Target:
- N+1 loops in Wing/National aggregation;
- unpaginated high-cardinality list endpoints;
- indexes used by hierarchy/year/status filters;
- connection-pool saturation;
- large import/report transactions;
- cache invalidation and repeated per-request reference-data reads.

Use representative datasets across multiple Wings and Squadrons.

### Phase 6 — National operational qualification

Status: **PLANNED**

Test realistic concurrent work, not only database volume:

- 10k+ cadets distributed across Wings/Squadrons;
- 50, 100 and 250 concurrent staff profiles;
- simultaneous Squadron writes and Wing/National reads;
- bulk CEA/curriculum/member imports;
- dashboard/report aggregation;
- account/service-desk/admin workflows;
- maintenance mode during traffic;
- backup + verified restore;
- worker restart and database-pool pressure.

Record p50/p95/p99, error rate, DB connections, slow queries, CPU/memory and
recovery behaviour. Existing September evidence showed the architecture can
sustain a 250-user/30-minute run after the maintenance-gate event-loop defect
was fixed; future runs must reproduce or improve that result on the current
release candidate.

### Phase 7 — Sustainability gate

A release is not considered structurally mature until:

- clean clone -> documented local startup works;
- full automated suites pass;
- migrations upgrade/rollback in rehearsal;
- backup restore is demonstrated;
- another developer can trace a representative request end-to-end;
- permission policy has one authoritative backend path;
- bug fixes carry regression tests;
- architecture ratchets are at or below the prior release;
- no critical subsystem requires undocumented product-owner knowledge to
  operate or deploy.

## Change discipline

A refactor PR must state:

- behaviour being preserved;
- seam being extracted/centralised;
- tests proving parity;
- architecture-baseline numbers before/after;
- migration impact (normally none for refactor-only changes);
- rollback method.

A PR that mixes behaviour redesign with structural extraction should be split
unless the two cannot safely be separated.
