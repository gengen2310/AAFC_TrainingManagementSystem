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
| 1 | Canonical domain map, API contracts, duplicate-model migration designs | NOT STARTED — three-agent research from the immediately-prior "TMS/Planning Workspace Integration" plan already covers *some* of this (Activity vs CeaActivity, TrainingArea vs PlanningLocation, ScheduledSession vs Session, ParadeDate vs ParadeNight) — see that research folded into `domain_model_inventory.md` below as a starting point, not re-run blind. |
| 2 | Auth hydration, refresh, error classification, stale-data invalidation | **PARTIALLY DONE** — session-restore-on-refresh and page-Refresh controls shipped and staging-verified (see above). API error classification (403 root-cause-per-route, distinguishing transport/401/403/404/409/422/429/5xx) NOT yet done. |
| 3 | Training Stage / Facilitator Type / Subject Area reference data | NOT STARTED |
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
