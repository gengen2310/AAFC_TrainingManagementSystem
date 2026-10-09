# Task register — production readiness 2026-10-09

Acceptance basis (user decision 2026-10-09): issue #70 exit criteria + the
`beta-release` gates. "Sections 1–19" were never provided, so GO/NO-GO is scoped
to these criteria only. States: NOT STARTED | IN PROGRESS | BLOCKED | VERIFIED | COMPLETE.

Checkpoint: branch `release/production-readiness-20261009`, last updated with the
commit that adds this file. Base `56ac1af` (#72) ← `34b1d4b` (#71) ← `f8a5dca` (#69).

| ID | Workstream | Pri | Owner | Depends | State | Commits | Evidence / next |
|---|---|---|---|---|---|---|---|
| S0 | Production guard hook | P0 | lead | — | VERIFIED | 17ffa44…4d9a28c | SECURITY_EVIDENCE; residual risk handed to owner |
| D1 | Maintenance backoff | P1 | lead | — | VERIFIED | 4d551a1 | DEFECT_REGISTER |
| D2–D4 | Parade-date edges | P2 | lead | — | VERIFIED | ff000c1 | DEFECT_REGISTER |
| D5 | Mixed-commit review note | P3 | lead | — | COMPLETE | — | reply on #71 |
| H1 | conftest double load | P2 | lead | — | VERIFIED | 7f414b3 | DEFECT_REGISTER |
| D6/C11 | Restore vs prod lag; verified restore | P0 | lead | merge | VERIFIED on branch | (on #69) 4473f0d a98f7ae | runs 37909713246, 37910351762; `main` scheduled pass pending merge |
| D7, D9 | Restore-test reporting/proof gaps | P2/P3 | lead | — | VERIFIED | 4473f0d, a98f7ae | MIGRATION_EVIDENCE |
| C3 | Router authz → permissions.py | P1 | subagent (worktree A) | — | NOT STARTED | | |
| C4 | One scope source of truth | P1 | subagent (worktree A) | C3 | NOT STARTED | | |
| C8 | Bound Service Desk tickets / accounts lists | P2 | lead | C4 | NOT STARTED | | |
| C5 | training.py / planning.py seams | P1 | subagent (worktree B) | C4 (planning.py) | NOT STARTED | | |
| C6/C7 | Main TMS off the monolith | P1 | subagent (worktree C) | — | NOT STARTED | | |
| C9 | N+1 evidence after C5 | P2 | lead | C5 | NOT STARTED | | |
| C10/C12 | National scale + drills on staging | P1 | lead | staging deploy | NOT STARTED | | needs synthetic-only staging check |
| C13 | Clean clone → deploy by another developer | P1 | subagent (docs only) | code done | NOT STARTED | | |
| C1/C2 | Containment + final PR + CI on exact SHA | P0 | lead | all | NOT STARTED | | merge needs owner |
| P6 | Adversarial release review | P0 | independent subagent | P5 | NOT STARTED | | |
