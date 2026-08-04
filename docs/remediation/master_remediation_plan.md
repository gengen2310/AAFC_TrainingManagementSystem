# AAFC TMS — Master Remediation Plan

Durable source of context for the "Complete System Remediation, Integration and
Workflow Program" instruction. Update this continuously so a future session can
resume without relying on chat history.

## Branch / baseline

- Branch: `remediation/2026-08-04-complete-system-remediation`, created from `main` @
  `ab1dd8d` (2026-08-04).
- `main` at branch-creation time: working tree clean, 0 unpushed commits, Alembic
  head `b99b8f07eded` (single linear head).
- Immediately prior work on `main` (this same session, commits `971c160`..`ab1dd8d`):
  the "TMS / Planning Workspace Integration" pass — session-restore-on-refresh fix,
  Parade Day 7-day support, Account Management hierarchy ordering, Activities
  Restore, Getting Started Holidays step, Calendar default-to-today + Holidays
  overlay, Planning Year rename/archive/restore UI + dependency-gated delete,
  Account/Wing/Squadron dependency-gated permanent delete, page Refresh controls,
  Planning Workspace reading canonical Activities. All deployed and verified on
  staging before this branch was created — see `docs/remediation/staging_verification_report.md`
  for the specific evidence and treat these as **already-closed** against several of
  this instruction's own sections (16, 19, 10, 8, 7, 4) rather than re-doing them.

## Not a blank slate

This repository has multiple prior remediation/QA passes already on record:
- `docs/release/qualification_gap_register.md` (2273 lines) — GAP-01 through GAP-29,
  spanning TRGO features, security (GAP-24 stored XSS, fixed+verified), production
  incidents (GAP-16 backup failure, GAP-18 wrong backup target DB, GAP-20/27 wrong
  URLs), and capacity work (GAP-28/29). Most are already marked addressed/fixed in
  that document — `master_gap_register.csv` below **carries these forward by
  reference**, not by re-deriving them from scratch.
- `docs/beta/00`–`37` — a 38-document "Operational Release Gate" suite (page/function
  inventory, authoritative data model, role/navigation rationalisation, code
  inventory, stress/resilience, feature freeze, release evidence chain, backup key
  custody, UAT plan).
- `docs/release/final_*.md` — a second full "Final System Assurance" pass (source
  inventory, data traceability, role/scope matrix, security/accessibility/database/
  performance assessments, accelerated release report).

Per this instruction's own rule (compare before/after, prove parity, no false
closure), every prior claim is a **lead to re-verify against current code**, not a
fact to cite blindly — but re-deriving 2000+ lines of prior, dated, evidence-backed
work from zero would itself violate the instruction's efficiency intent. Stage 1
below is where reconciliation against this prior art happens explicitly.

## Staged order (per instruction Section 25) — status

| Stage | Scope | Status |
|---|---|---|
| 0 | Ground rules, baseline, capability manifest, gap register, key/variable inventory | **IN PROGRESS** — branch created, `capability-preservation.md` written, capability manifest v1 (static-analysis pass) written, gap register seeded from prior art + new instruction sections, this plan document written. Key/variable inventory not yet done. |
| 1 | Canonical domain map, API contracts, duplicate-model migration designs | **DONE (research/design; no code changes — Stage 1 is a design stage)** — reconciled against `docs/beta/28_authoritative_data_model.md` and `docs/api_reference.md` (both real prior-pass docs, verified against current code rather than re-derived). **Major new finding**: `ProgramPackage`/`ProgramItem` (9 models, 14 live registered endpoints) is a complete, real backend system with zero references in either frontend and no join to `CurriculumItem` — strong evidence it's an early (v9.1, the *first* migration in the chain) design superseded by `CurriculumItem`, never removed. Flagged as REM-26, **needs explicit product confirmation before any action** — not touched. Migration designs for all 5 duplicate/near-duplicate pairs written to `data_migration_plan.md` in the Section-4 table format; only the two already-confirmed-dead ones (`ScheduledSession`, `PlanningLocation`) have a concrete recommended action (retirement, pending authorisation), the rest are genuinely blocked on product decisions, not engineering effort. |
| 2 | Auth hydration, refresh, error classification, stale-data invalidation | **DONE** — session-restore-on-refresh and page-Refresh controls (prior stage, staging-verified). Error classification: audited both frontends' error handling against the full classification list (transport/401/403/404/409/422/429/5xx/cancellation/invalid-response) — most already solid; fixed 3 real gaps (no cancellation classification, no 502/503/504 retry, no invalid-response detection; Planning Workspace additionally had *no retry at all*), 4 new passing tests. 403 root-cause audit: spot-checked every squadron/year-scoped write's permission-helper selection across ops.py/organisations.py/planning.py (training.py already had 27 confirmed-correct uses) — **no misapplication found, architecture is sound**; did not mass-rewrite the 61 bare-"forbidden" messages (low value at that scale, most are correct simple role gates). Stale-data invalidation on scope/year/Proxy change: **verified already correct** in both frontends (connected-frontend's full-reload pattern on scope-switch/Proxy-entry-exit; Planning Workspace's React-Query key-based refetch via `useScopedSquadron()`) — no code change needed. One residual, lower-priority item: neither frontend cancels the now-stale in-flight request early (discarded safely, not aborted) — not fixed, judged disproportionate effort for this stage. |
| 3 | Training Stage / Facilitator Type / Subject Area reference data | **PARTIALLY DONE** — Subject Area was already a real, working example of this exact pattern (found, not built). Replicated it for Facilitator Type: new `facilitator_type_tags` table (migration `abc97c354bbb`, additive, disposable-Postgres-verified), same endpoints/permission model, seeded with the *actual* short codes in use (found the hardcoded dropdown's values didn't match its own display text, and most real data uses "Staff" — not one of the 4 originally-hardcoded options; fixed a related latent bug as a side effect). Frontend `#fac-type` is now API-driven with inline type creation. 17 new tests, full suite 1066 passed. Training Stage deliberately deferred — entangled with the still-open REM-26 (`ProgramItem`) decision; building it now risks a third parallel system. Session Status Reason / Notice Type / Training Area Capability not started — same proven pattern ready to replicate. |
| 4 | Squadron Details, Timing Templates, Parade Night generation/editing | NOT STARTED (Parade Day 7-day fix already shipped; the rest — crest upload, full nightly-sequence blocks, generation UI audit — not started) |
| 5 | Parade Night cross-interface sync, Planning Year lifecycle | **PARTIALLY DONE** — Planning Year rename/archive/restore/delete shipped; Parade Night sync itself not yet re-verified against this instruction's specific 9-step integration test |
| 6 | Activities, CEA, Holidays, anchors, unified Calendar | **PARTIALLY DONE** — Activities Restore, Calendar default-date+Holidays overlay, and Planning Workspace reading canonical Activities shipped. CEA/Activity model consolidation, anchor prep rules, and the full unified multi-scope calendar projection NOT started. |
| 7 | Mission Backlog, status lifecycle, Long Range, Weekly Program, notices | NOT STARTED |
| 8 | Facilitators, Training Areas, Equipment, conflicts | NOT STARTED |
| 9 | Readiness, dashboards, charts, higher-level parity, Training Summary migration | NOT STARTED |
| 10 | Accounts, organisations, Proxy, Intervention, 403 corrections | **PARTIALLY DONE** — Account/Wing/Squadron dependency-gated permanent delete, role-change endpoint, and account ordering already shipped (this session, both the immediately-prior plan and the one before it). 403 root-cause corrections NOT done. |
| 11 | Learning Hub links, terminology, accessibility, visual consistency | NOT STARTED |
| 12 | Capacity, monitoring, complete regression, staging deployment, verification | ONGOING (every stage above is being staging-verified as it ships, not deferred to one final pass) |

## Working method going forward

- Every stage's changes get committed separately (small, coherent commits, one
  functional area each), tested (backend pytest + relevant frontend suite), and
  staging-verified before being marked STAGING VERIFIED in the gap register — not
  before.
- No item is silently dropped: anything descoped gets an explicit entry in the gap
  register with a reason, not a quiet omission.
- Continuing autonomously per user instruction (2026-08-04) — no per-stage approval
  gate, but every turn's real, verifiable progress is reported honestly rather than
  claiming full closure early.
