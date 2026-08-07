# AAFC TMS — Whole-System Adversarial Qualification Program Charter

Created: 2026-08-08. Program authorised following confirmation that:

**P0 OPERATIONAL DEFECTS FIXED — VERIFIED ON STAGING**

(REM-109, REM-110, REM-111, REM-112 — see `docs/remediation/master_gap_register.csv`, commits
`89cd192`, `2aff5b5`, `5011a8e`, `76d6723`. Backend at staging deployment with merge/absorb endpoint
live and verified; connected-frontend and Planning Workspace both current. Precondition re-verified
live immediately before this program started: `GET /api/health/ready` → `{"status":"ready"}`; PW
`SquadronSelector` fix and connected-frontend `loadFacilitatorStats()` fix both confirmed present in
current source at HEAD `76d6723`.)

---

## Honest scope statement (read this before anything else in this program)

The instruction that opened this program specifies 33 sections covering: a multi-agent engineering
team, a complete capability baseline, statement/branch/mutation-coverage analysis, a full domain and
data-model forensic audit, frontend-to-database data lineage for every dashboard number,
cross-frontend parity testing, staleness auditing, backend adversarial fuzz testing, concurrency/race
testing, an independent security review beyond `/security-review`, staged load testing up to 500
users, chaos testing, responsive/visual regression testing across 6 breakpoints, an information-
completeness audit of every page, a full UX/workflow redesign pass, civilian-friendly terminology
work, a personnel-information classification pass, visual design and visualisation review, animation
review, workflow performance-metrics measurement, a higher-command-experience redesign, an automated
data-contradiction/invariant test suite, realistic user-journey scenario tests (9 named scenarios),
database invariant tests, and a 10-phase gated release program (A through J) ending in a full
production release plan.

This is, without exaggeration, a multi-week to multi-month enterprise QA/architecture program for a
system of this size, normally staffed by a team of specialists. It is not something that can be
genuinely completed — with real evidence, not fabricated evidence — in a single working session, and
claiming otherwise would violate the program's own most important ground rule (§29: tests must fail
for the right reason; §15 of the original P0 rules: do not declare something verified from inspection
alone where the workflow can be exercised; the whole spirit of §32's acceptance standard is *evidence*,
not assertion).

**What this charter commits to instead**: execute the program honestly, in the phase order specified
(§31), starting with Phase A (discover and map, no application changes), producing real artifacts with
real evidence at each step, and reporting genuine status — including "not yet done" — rather than a
fabricated "complete" claim. Every session/turn of this program will end with either continued
in-progress status or, if a natural checkpoint is reached, an accurate partial-completion report. The
two closing lines defined in §33 (`WHOLE-SYSTEM QUALIFICATION COMPLETE — AWAITING PRODUCTION
AUTHORISATION` / `WHOLE-SYSTEM QUALIFICATION INCOMPLETE — REMEDIATION REQUIRED`) will only be used when
the acceptance standard in §32 is actually, verifiably met or when the program reaches a genuine
stopping point — not as a default end-of-turn sign-off.

## Agent team — what's actually available vs. what was requested

Inspected before creating anything (per §3's requirement to check current tooling and this repo's
existing `.claude/` configuration first):

- `.claude/agents/`: does not exist in this repository. No pre-built project-level specialist agents.
- `.claude/skills/`: one skill, `beta-release` (the 11-gate release process already used earlier in
  this program's history — not a qualification-specific skill).
- `.claude/rules/`: `architecture.md`, `backend.md`, `capability-preservation.md`, `deployment.md`,
  `frontend.md`, `security.md`, `testing.md` — all read and already governing this program's work.
- "Impeccable" and "Taste" (named in §2H/§21 as design-review preloads): not found as installed
  skills in this repository or its plugin cache at time of writing. Not fabricated or assumed —
  flagged here as unavailable rather than silently skipped. `DESIGN.md` exists at repo root and will
  be used directly for the UX/visual review phase (Phase H) instead.
- Available agent types in this environment (not custom-built, but real and usable now): `Explore`
  (read-only codebase search), `general-purpose` (broader multi-step investigation), `code-reviewer`
  variants, `Plan`. These map reasonably onto the read-heavy roles in §2 (Systems Architect, Data
  Integrity Auditor, Security Reviewer at the reconnaissance stage) — used as such below, not as a
  substitute for the deeper judgment-heavy phases (adversarial QA execution, UX redesign, load
  testing) which this session performs directly.
- No new custom skill was installed. Section 3's provenance checklist (`docs/qualification/
  skill_provenance.md`) is created but currently empty — nothing new has been installed to record.

This is not a workaround or a downgrade dressed up as compliance — it is the accurate state of the
tooling, recorded per the instruction's own requirement to inspect before creating.

---

## Phase plan (per §31) and current status

| Phase | Description | Status |
|---|---|---|
| A | Discover and map. No application changes. | **IN PROGRESS** |
| B | Correct trust/data defects | Not started |
| C | Correct architecture/integration defects | Not started |
| D | Strengthen tests | Not started |
| E | Adversarial security/reliability | Not started |
| F | Performance | Not started |
| G | Workflow optimisation | Not started |
| H | Visual redesign | Not started |
| I | Accessibility and human factors | Not started |
| J | Complete staging qualification | Not started |

Per §31: "Do not redesign while basic data correctness is unresolved." Phases G/H/I will not begin
until B/C/D find no unresolved P0/P1 trust or data-correctness defect.

## Documents in this program

| Document | Purpose | Status |
|---|---|---|
| `00_program_charter.md` | This document | Live |
| `01_capability_baseline.md` | Complete inventory of current capabilities | In progress |
| `02_architecture_review.md` | Systems Architect findings | Not started |
| `03_data_integrity_review.md` | Data Integrity Auditor findings | Not started |
| `04_backend_review.md` | Backend Engineer findings | Not started |
| `05_frontend_review.md` | Frontend Engineer findings | Not started |
| `06_security_review.md` | Security Reviewer findings | Not started |
| `07_performance_review.md` | Performance/Reliability findings | Not started |
| `08_adversarial_test_report.md` | Adversarial QA findings | Not started |
| `09_ux_review.md` | UX/Human-Factors findings | Not started |
| `10_visualisation_review.md` | Visualisation/Information-Design findings | Not started |
| `11_accessibility_review.md` | Accessibility findings | Not started |
| `12_cross_interface_parity.md` | Main TMS ↔ Planning Workspace parity | Not started |
| `13_personnel_information_review.md` | Personnel data classification | Not started |
| `14_release_evidence.md` | Final release evidence chain | Not started |
| `defect_register.csv` | Master defect register (never delete closed issues) | Created, empty |
| `data_relationship_inventory.csv` | Domain entity/relationship inventory | Not started |
| `capability_matrix.csv` | Capability → role → frontend → API → table → test trace | In progress |
| `api_contract_matrix.csv` | Every endpoint, method, auth, contract | Not started |
| `ui_data_lineage.csv` | Every dashboard number's full lineage | Not started |
| `test_coverage_matrix.csv` | Statement/branch/mutation coverage by module | Not started |
| `decision_log.md` | Judgment calls made during this program, with rationale | Live |
| `skill_provenance.md` | Any new skill installed, with provenance checklist | Created, empty |
| `capability_manifest_before.json` | Machine-readable capability snapshot, pre-program | In progress |

## Ground rules in effect (§1, carried forward from the P0 program's own discipline)

Same 15 rules as this program's own §1, plus the standing rules already in force from
`.claude/rules/capability-preservation.md` and `.claude/rules/architecture.md` (which this program's
rules are a superset of, not a replacement for). No conflict found between the two rule sets.

## Production control

No production deployment under this program. All destructive/high-load/chaos/fuzzing/security testing
is local or staging only. Production receives non-destructive verification only, and only where
explicitly performed and logged.
