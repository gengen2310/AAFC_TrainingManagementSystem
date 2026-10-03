# TMS Stabilisation Programme — Predictable Before Clever

**Authorised:** 2026-10-03  
**Working integration base:** PR #68 tip `9f24d42b61e1a8d775d5c4f0a24465d145fe0e85`  
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

## Work sequence

### 0. Canonicalise and freeze — ACTIVE
Use this repository and the current integration chain as the only release source. Do not revive the older `gengen2310/aafc-tms` repository. New work is short-lived branches/PRs.

### 1. Architecture ratchets — IMPLEMENTED HERE
CI blocks growth of the Main TMS monolith and router-local role-policy branching. Deliberate exceptions require an explicit baseline change and review.

### 2. Centralise permission/scope policy — STARTED HERE
Migrate pure allow/deny gates first, then repeated visible Wing/Squadron scope derivation. Preserve status/error contracts unless a separately approved defect requires a change. Reduce the ratchet after each migration.

### 3. Extract backend domain services — NEXT
Priority: `training.py`, `planning.py`, `dashboard.py`. Start with pure computation/query seams such as conflict detection, coverage/readiness, aggregation and import validation. Do not move HTTP schemas and business logic simultaneously.

### 4. Modularise connected frontend — NEXT
Do not replace the Main TMS with the Planning Workspace. Introduce maintainable modular source incrementally while preserving the deployed behaviour. If a generated single-file artifact remains a deployment requirement, generation must be deterministic and CI-verified. Extraction order: shell/navigation; API/error helpers; auth/session/scope; shared UI; Training Program; Planning; Cadets; Accounts; Service Desk; Administration; reports/imports/audit.

### 5. Data/query scalability — PLANNED
Profile N+1 loops, unpaginated high-cardinality endpoints, hierarchy/year/status indexes, connection-pool pressure, large import/report transactions and repeated reference-data queries.

### 6. National qualification — PLANNED
Use multi-Wing datasets with 10k+ cadets and 50/100/250 concurrent staff. Exercise simultaneous Squadron writes, Wing/National aggregation, bulk imports, Service Desk/admin workflows, maintenance mode, worker restart, backup and verified restore. Record p50/p95/p99, errors, pool usage, slow queries and recovery.

### 7. Sustainability gate — PLANNED
A release is structurally mature only when a clean clone starts from documentation, automated suites and migrations pass, backup restore is demonstrated, authorization has one authoritative backend path, architecture ratchets do not regress, and another developer can modify/deploy a subsystem without product-owner-only tribal knowledge.

## Refactor PR contract

Each structural PR states: behaviour preserved, seam extracted, tests proving parity, ratchet before/after, migration impact, and rollback method. Do not mix redesign with extraction unless they cannot safely be separated.
