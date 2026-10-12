# Task register — production readiness 2026-10-09

Acceptance basis (user decision 2026-10-09): issue #70 exit criteria + the
`beta-release` gates. "Sections 1–19" were never provided, so GO/NO-GO is scoped
to these criteria only. States: NOT STARTED | IN PROGRESS | BLOCKED | VERIFIED | COMPLETE.

Checkpoint: branch `release/production-readiness-20261009`. **Reconciled 2026-10-11**
against git (rows C3/C4/C6 were stale at NOT STARTED although merged on 10-09;
C8 work found unpushed in an orphaned worktree and pushed as `wt/c8-paging`). Base `56ac1af` (#72) ← `34b1d4b` (#71) ← `f8a5dca` (#69).

| ID | Workstream | Pri | Owner | Depends | State | Commits | Evidence / next |
|---|---|---|---|---|---|---|---|
| S0 | Production guard hook | P0 | lead | — | VERIFIED | 17ffa44…4d9a28c | SECURITY_EVIDENCE; residual risk handed to owner |
| D1 | Maintenance backoff | P1 | lead | — | VERIFIED | 4d551a1 | DEFECT_REGISTER |
| D2–D4 | Parade-date edges | P2 | lead | — | VERIFIED | ff000c1 | DEFECT_REGISTER |
| D5 | Mixed-commit review note | P3 | lead | — | COMPLETE | — | reply on #71 |
| H1 | conftest double load | P2 | lead | — | VERIFIED | 7f414b3 | DEFECT_REGISTER |
| D6/C11 | Restore vs prod lag; verified restore | P0 | lead | merge | VERIFIED on branch | (on #69) 4473f0d a98f7ae | runs 37909713246, 37910351762; `main` scheduled pass pending merge |
| D7, D9 | Restore-test reporting/proof gaps | P2/P3 | lead | — | VERIFIED | 4473f0d, a98f7ae | MIGRATION_EVIDENCE |
| C3 | Router authz → permissions.py | P1 | subagent (worktree A) | — | VERIFIED (pending P6) | merge `4cf62d7` | 43→7 direct role checks; `test_moved_role_gates.py`; remaining 7 classified in `role-check-classification.md` |
| C4 | One scope source of truth | P1 | subagent (worktree A) | C3 | VERIFIED (pending P6) | merge `4cf62d7` | inline scope 71→11; `test_scope_parity.py` 1344/1344 identical (14 principals incl. 2nd Wing, proxy, intervention) |
| C8 | Bound Service Desk tickets / accounts lists | P2 | lead | C4 | VERIFIED (pending P6) | merge `5d8aa57` (+`ff62d1b`) | tickets always paged + summary + Load more (3-browser spec); accounts opt-in paging, assignees by role; independent review: nothing blocking, 1 minor fixed |
| C5 | training.py / planning.py seams | P1 | subagent (worktree B) | C4 | VERIFIED (pending P6) | merge `0a37087` | 53 helpers verbatim (AST re-verified by lead) into 8 services; 82 GET routes × 8 principals parity; boundary test; router line ratchet (7542 / 5746) |
| C6/C7 | Main TMS off the monolith | P1 | subagent (worktree C) | — | IMPLEMENTED, verification pending | merge `b93bc12` | 28 `js/` modules; index.html 20,123→5,236 lines; `tools/architecture/frontend_parity.mjs`; 3-browser parity at final SHA pending |
| D10 | Custom-phase cross-Wing mutation (security) | P1 | lead | — | VERIFIED | `6ec3935`, `e2b68f1` | DEFECT_REGISTER D10; UI shows actions only where can_edit |
| D11–D18 | Defects found 2026-10-11 (XSS, Override link, CSRF, rate limit, export 500, NameError, curriculum CSV loss, CEA import) | P1–P2 | lead | — | VERIFIED | see DEFECT_REGISTER | each red-then-green; browser specs where user-visible |
| SEC | Security path coverage map + closure tests | P1 | lead + read-only agent | — | VERIFIED | `fccd7ab`, `0ad3ab5` | SECURITY_EVIDENCE "2026-10-11 security closure"; owner decisions S-A, S-B open |
| WF | Workflow coverage (curriculum CSV, CEA import, Override, Service Desk) | P2 | lead | — | VERIFIED | D17, D18, `0335cf8` | handoff TMS↔PW deferred to final matrix (needs PW server) |
| C9 | N+1 evidence after C5 | P2 | lead | C5 | VERIFIED | `6f38374` | 80/82 GETs constant under growth; plan-review/schedule export linear per night (bounded), pinned; optimise only if staging p95 breaches |
| C10/C12 | National scale + drills on staging | P1 | lead | staging deploy | NOT STARTED | | needs synthetic-only staging check |
| C13 | Clean clone → deploy by another developer | P1 | subagent (docs only) | code done | NOT STARTED | | |
| C1/C2 | Containment + final PR + CI on exact SHA | P0 | lead | all | NOT STARTED | | merge needs owner |
| P6 | Adversarial release review | P0 | independent subagent | P5 | NOT STARTED | | |

## Checkpoint 2026-10-11 (end of Phase 3), HEAD `0335cf8`

- Done since 10-09: D10–D18 fixed with regression tests; C5, C8, C9 merged; security
  coverage closure; workflow gaps closed (curriculum round-trip, CEA validation, D12).
- Full backend suite last run at `4994140`: 3287 passed, 12 skipped, 0 failed (rerun at freeze).
- Main TMS browser suite at `1623acb`: chromium 192/0/3, firefox+webkit 385/1/6 (1 = PW server
  absent locally). Rerun at freeze with PW running.
- Next: Phase 4 freeze → full suites at one SHA → staging deploy (DRY_RUN first) → rollback
  rehearsal → national scale 50/100/250 + drills → restore run → clean-clone (C13).
- Open owner decisions: S-A lockout semantics, S-B forgot-code timing, sqn_general record policy,
  Service Desk admin-note visibility, XLSM per-session Location/Room, merge of the final PR.
