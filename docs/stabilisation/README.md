# TMS Stabilisation Programme — Predictable Before Clever

**Authorised:** 2026-10-03
**Working integration base:** PR #68 tip `9f24d42b61e1a8d775d5c4f0a24465d145fe0e85`
**Release candidate:** PR #69 (supersedes #67/#68). Status below last verified 2026-10-04 at `f8a5dca`.
**Canonical repository:** `gengen2310/AAFC_TrainingManagementSystem`

## Objective

Move the AAFC TMS from rapid feature construction into a stabilisation and maintainability phase without a big-bang rewrite.

The long-term risk is not PostgreSQL holding 10,000 cadets. It is architectural entropy: duplicated policy, very large source files, hidden coupling, and a large change blast radius.

Target path:

```
UI -> API/router -> central authorisation -> domain/service logic -> database
```

## Release principles

1. Predictability before new capability.
2. No major net-new feature programmes during stabilisation unless explicitly authorised.
3. Security, integrity, release blockers and already-authorised workflow completion remain in scope.
4. No rewrite. Refactor by seam and prove parity after each step.
5. Backend authorization is the security source of truth; frontend gating is presentation only.
6. Alembic is the schema source of truth.
7. Every defect fix gets a regression test.
8. Scale testing must combine hierarchy, concurrency, aggregation, imports and failure modes.
9. Maintainability is a release property: another developer must be able to trace, test and deploy a subsystem without undocumented knowledge.

## Protected baseline

At PR #68 tip:

- `connected-frontend/index.html`: **1,255,839 bytes**
- **20,273 newline-split entries** (the guard uses Python `splitlines()`, so the runtime count may be one lower when the file ends with a newline)
- **800 named JavaScript function declarations**
- **185 direct `p.role` checks** across backend router modules

These numbers are debt baselines, not targets. The guard allows them to decrease but blocks silent increases.

Current ratchet (`tools/architecture/architecture-baseline.json`, at `f8a5dca`):

| Metric | Baseline (#68) | Now |
|---|---|---|
| Main TMS bytes / lines / named functions | 1,255,839 / 20,273 / 800 | 1,248,133 / 20,123 / 788 |
| Direct router `p.role` checks | 185 | 43 (#71; classified in `role-check-classification.md`) |
| Router-to-router import edges | not detected (guard defect) | 0, enforced (ast-based, self-tested) |

## Work sequence

Each phase states its status, the evidence for it, and its exit criterion.
"Done" means the exit criterion holds, not that work was started.

### Phase 0 — Canonicalise and freeze — DONE (pending merge)

- `gengen2310/AAFC_TrainingManagementSystem` is canonical; `main` is the
  integration branch. Do not revive `gengen2310/aafc-tms` as a release source.
- #67 and #68 are closed as superseded; Git containment is recorded on #69.
  The old `stabilise/predictable-architecture-20261003` branch's content is in
  #69 (four commits by patch identity, the other seven redone in stronger form).
- Preserve the deployment fingerprint, migration, backup and rollback gates.

Exit: one release-candidate PR; CI guards run on every PR to `main`. Holds
once #69 is merged.

### Phase 1 — Architecture ratchets — DONE

CI blocks growth of the Main TMS monolith, router-local role checks and
router-to-router imports. The import check was found never to match anything
(doubled backslashes in a raw-string regex); it is now ast-based with unit
self-tests that CI runs. A deliberate baseline increase needs explicit review
in the same PR.

### Phase 2 — Centralise permission/scope policy — IN PROGRESS

Done: named predicates in `permissions.py` (`is_national_admin`,
`is_wing_writer`, `is_writer`, `is_read_only_role`, `require_write_role`,
`resolve_view_squadron_id`); router-local role constants removed; 185 -> 94
direct checks; #71 continues to 43 (`may_view_cadet_records`,
`may_record_session_outcomes`, `wing_admin_outside_own_wing`,
`sqn_admin_outside_own_squadron`, `Principal.is_squadron`, `has_known_role`).
Pinned by `test_role_predicates.py`, `test_role_matrix.py`,
`test_sqn_general_record_policies.py`, `test_wing_admin_scope_predicate.py`
and `test_cross_wing_write_isolation.py`.

Remaining: 43 checks, each classified with its reason in
`role-check-classification.md`. Most are scope selection or role-specific
product rules that stay where they are.

For every migrated rule: permission-unit tests; endpoint status/error
contracts unchanged unless a defect is separately approved; role/scope matrix
across sqn_general, sqn_admin, wing_viewer, wing_admin, national_viewer,
national_admin, auditor and system_admin; lower the baseline.

Exit: routers orchestrate requests; they do not invent authorization policy.

### Phase 3 — Extract backend domain services — STARTED

Done: router-to-router coupling removed through `services_timing`,
`services_curriculum_progress`, `services_data_quality`, `services_accounts`;
shared multi-worker state in `services_idempotency` and `services_rate_limit`.

Not done: the large routers are essentially unchanged in size (`training.py`
8,178 -> 8,128 lines, `planning.py` 6,372 -> 6,429, `dashboard.py`
3,051 -> 2,966). Next: pure computation and query seams in
`training.py`, `planning.py`, `dashboard.py` (conflict detection,
coverage/readiness, scope filters, aggregation, import validation). Do not
move HTTP models and business logic at the same time. Organise by domain, not a
`services.py` dumping ground.

Exit: large routers are substantially thinner and domain logic is
unit-testable without an HTTP request.

### Phase 4 — Modularise the connected frontend — STARTED (path proven)

Do **not** replace the Main TMS with the Planning Workspace.

Done: `connected-frontend/js/modal.js` (dialog core) and
`connected-frontend/js/curriculum-csv-import.js` extracted verbatim. Pattern:
classic `<script src>` (CSP `script-src 'self'` unchanged), copied by the
Dockerfile, every `js/*.js` must parse and be referenced
(`connectedFrontendParses.test.ts`), deploy scripts verify each served module's
sha256 against source. No generated artifact, so no second source of truth.

Extraction order for what remains: API/error helpers; auth/session/scope
presentation; shell/navigation; shared table/form utilities; Training
Program; Planning/Parade Nights/Weekly Program; Cadets; Accounts; Service
Desk; Administration/System Console; reports/imports/audit. Each extraction is
parity-only, with tests before and after, and must lower the baseline.

Exit: feature work no longer requires editing a 20k-line entry point.

### Phase 5 — Data/query scalability — LARGELY DONE

Done, each pinned by query-count tests: facilitator leave, Wing/National
freshness, long-range conflicts, session serialisation (term planner 28->72
became 11->11 queries as sessions grew), accounts (419 -> 21), Wing overview
(325 -> 23), National overview (149 -> 38). Overload deadlock between the
thread pool and connection pool fixed (per-worker request cap; 503 not 500).
Endpoint inventory: `bounded-responses.md`.

Remaining: Service Desk ticket list and the national accounts list are
unbounded (need UI paging); no index added without an observed query.

### Phase 6 — National qualification — DONE LOCALLY

`national-qualification.md`: 10,200 cadets / 60 Squadrons / 6 Wings; 50, 100,
250 realistic users p95 46/53/89 ms with 0 errors; saturated 121 req/s with 0
errors; maintenance, worker kill and database-outage drills. Earlier September
evidence (250 users / 30 min after the maintenance-gate event-loop fix) is
reproduced or improved.

Remaining: repeat on staging hardware before quoting a production capacity
number; bulk CEA import and attendance write bursts under load.

### Phase 7 — Sustainability gate — NOT YET MET

A release is structurally mature only when all of these hold:

- [x] clean clone -> documented local startup works (walked 2026-10-04 on a fresh clone; `README.md` written from it, every command run; the June setup guide labelled historical)
- [x] full automated suites pass (backend 2575/12 skipped; browser 3 engines)
- [x] migrations upgrade/rollback in rehearsal (SQLite + PostgreSQL 18)
- [x] backup restore demonstrated (restore run 37132802899, real production data)
- [ ] another developer can trace a representative request end-to-end
- [ ] permission policy has one authoritative backend path (Phase 2)
- [x] bug fixes carry regression tests
- [x] architecture ratchets at or below the prior release
- [ ] no critical subsystem needs undocumented product-owner knowledge

## Refactor PR contract

Each structural PR states: behaviour preserved; seam extracted or centralised;
tests proving parity; architecture-baseline numbers before/after; migration
impact (normally none); rollback method. Split a PR that mixes redesign with
extraction unless the two cannot safely be separated.
