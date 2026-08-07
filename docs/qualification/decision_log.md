# Decision Log — Whole-System Qualification Program

Judgment calls made during this program, with rationale, so later phases (and later readers) can
understand *why* a choice was made without re-deriving it. Append-only; do not edit past entries,
add corrections as new dated entries instead.

---

### 2026-08-08 — Scope and pacing

**Decision**: Treat the 33-section mission as a real, multi-session program executed honestly in
phase order, rather than attempting to fabricate full completion in one turn.

**Why**: The mission's own ground rules (§29 "tests must fail for the right reason", the P0 program's
§15 "do not declare a capability verified from source inspection alone where the workflow can be
exercised") are incompatible with claiming completion without genuine evidence. A program of this
size — statement/branch/mutation coverage, full domain forensic audit, staged load testing to 500
users, 9 named user-journey scenarios, a full visual redesign pass — cannot be genuinely completed
with real evidence in a single session.

**How to apply**: Every phase produces real artifacts with real evidence. Status is reported honestly
at natural checkpoints. The closing lines in §33 are reserved for when §32's acceptance standard is
actually met, not used as a default end-of-turn sign-off.

### 2026-08-08 — Agent team substitution

**Decision**: Use `Explore`/`general-purpose`/`code-reviewer` subagents for the read-heavy
reconnaissance roles (Systems Architect, Data Integrity Auditor at discovery stage, Security Reviewer
at discovery stage) instead of building 12 new custom `.claude/agents/` definitions.

**Why**: §3 requires inspecting current tooling and this repo's `.claude/` configuration before
creating new agents. No pre-built agents exist in this repo. The available generic agent types cover
the read-only investigation work the mission describes for these roles reasonably well; building 12
bespoke agent definitions before starting any actual investigation would spend a large fraction of
this program's budget on scaffolding rather than substance, for roles that (per §2's own text) are
meant to "propose" findings for this session to act on, not operate fully autonomously.

**How to apply**: Judgment-heavy phases (adversarial QA execution, UX redesign decisions, security
exploitation attempts, load-test execution and analysis) are performed directly by this session, not
delegated wholesale to a subagent, consistent with §2's explicit constraint that e.g. the Systems
Architect agent "does not redesign the project autonomously."

### 2026-08-08 — "Impeccable" / "Taste" skills not found

**Decision**: Proceed using `DESIGN.md` (present at repo root) for the visual/UX review phase; do not
fabricate or assume the existence of skills named "Impeccable" or "Taste".

**Why**: Neither is present in this repository's `.claude/` configuration or this session's available
skill listing. Guessing at their content or silently substituting something else without noting the
gap would misrepresent what was actually used.

**How to apply**: If these skills become available in a later session (e.g. installed by the user or
present in an updated plugin cache), re-run the relevant portion of Phase H against them and note the
addition here.

### 2026-08-08 — Table retirement and C-5 refactor both deferred (user decision)

**Decision**: After Phase C's dead-code cleanup (removing the last live references to
`ScheduledSession`/`PlanningLocation`), the user was asked whether to (1) drop the now-fully-unused
`scheduled_sessions`/`planning_locations` tables and model classes, and (2) take on C-5 (centralising
duplicated squadron-scope-derivation logic into `permissions.py`) now. User chose to defer both.

**Why**: Table/schema removal is exactly the class of change `capability-preservation.md` requires
explicit authorisation for — asking first rather than assuming "confirmed unused" is equivalent to
"authorised to remove" was the correct default. C-5 is a multi-router refactor of working code (not a
confirmed defect, marked P3/DESIGN by the architecture review) — deferring it keeps this pass's change
minimal and focused, consistent with ground rule 3 ("do not rewrite a working subsystem merely because
another architecture looks cleaner") and the overall program's long remaining scope (Phases D-J).

**How to apply**: Both remain open, documented items (`QUAL-002` residual risk; C-5 in
`02_architecture_review.md`'s Phase C feed table) for a future dedicated pass, not silently dropped.
