# Skill register — production readiness 2026-10-09

| Skill | Source | Available | Relevant | Invoked | Supported | Outcome |
|---|---|---|---|---|---|---|
| beta-release | repo `.claude/skills/` (not callable; read directly) | yes | yes | discovery | gate structure, GO/NO-GO | gates mapped into plan |
| superpowers:using-git-worktrees | plugin | yes | yes | Phase 1 | isolated worktree off `56ac1af` | git fallback (native tool branches from wrong base) |
| update-config | built-in | yes | yes | S0 | hook in settings.json | hook + 52-case test |
| superpowers:systematic-debugging | plugin | yes | yes | D1, H1, D7 | root cause before fix | 3 root causes found |
| superpowers:test-driven-development | plugin | yes | yes | D1, D2–D4, H1 | failing test first | every fix had a seen-failing test |
| superpowers:dispatching-parallel-agents | plugin | yes | yes | Phase 3/4 | C3/C4, C5, C6 | pending |
| superpowers:requesting-code-review / code-review | plugin / built-in | yes | yes | per workstream close | — | pending |
| security-review | built-in | yes | yes | Phase 5 | full diff | pending |
| superpowers:verification-before-completion | plugin | yes | yes | each closure | — | pending |
| frontend-design + DESIGN.md | plugin + repo | yes | C8 UI only | — | — | pending |
| claude-in-chrome | built-in | yes | user-visible checks | — | — | pending |
| railway:use-railway, engineering:deploy-checklist | plugin | yes | staging deploy/rollback | — | — | pending |
| superpowers:finishing-a-development-branch | plugin | yes | Phase 7 | — | — | pending |
| simplify | built-in | yes | **no** — extractions must be verbatim | not invoked | — | — |
| /batch, /goal | — | **not installed** | — | — | — | — |
| superpowers:brainstorming | plugin | yes | **no** — scope fixed by issue #70 and user | not invoked | — | — |

## 2026-10-11/12 continuation

| Skill / capability | Invoked | Used for | Outcome |
|---|---|---|---|
| superpowers:test-driven-development | yes | D10–D23 | every fix had a seen-failing test (or a red proof against the pre-fix file) |
| systematic-debugging (method) | applied | D11 repro, D14 probe, D19/D20 drills, D21 (one hypothesis tested and disproved before the real cause), REM-111 race | root causes recorded in DEFECT_REGISTER |
| claude-in-chrome | yes | Service Desk visual check | **extension not connected** — fell back to Playwright screenshots (desktop + 390 px) |
| railway:use-railway | yes | staging identity, deployments, logs, Postgres backup | read-only until the authorised staging deploy |
| security-review | yes | full branch diff (`origin/main...HEAD`) | no finding ≥ 8; 1 below-threshold policy question (audit-summary IP visibility) |
| Explore / general-purpose subagents | yes | security coverage map, C8 review, C5 extraction (worktree), clean-clone walkthrough (C13), security review | each result independently re-verified by the lead (C5 AST re-check; security findings reproduced) |
| feature-dev:code-reviewer | yes | C8 diff | nothing blocking; 1 minor fixed |
| frontend-design | not invoked | — | no new UI surfaces; changes followed existing DESIGN.md tokens |
| engineering:deploy-checklist | not invoked | — | `deploy-staging.sh` gates + `rollback_runbook.md` used directly (the project's own checklist) |
| superpowers:finishing-a-development-branch | pending | final PR | Phase 5 |
