# Release decision — AAFC TMS production readiness

**Decision: NO-GO** (2026-10-12; updated 2026-10-13 after owner decisions R1, R2, R10 and the 100-user staging run). Every engineering gate that can be run without the owner has
been run and passes. The release is blocked only by owner actions and sign-offs (B1–B8), each
named below with the exact next step. **Production deployment is not authorised.**

Candidate: branch `release/production-readiness-20261009`; final SHA = the head of the release
PR to `main` (CI must be green on that exact SHA; see the PR). Production today: database v64
(`a4e9507a9c51`); target v76 (`63c110addb63`), 15 migrations.

## Acceptance matrix

| Category | Result | Evidence |
|---|---|---|
| Repository integrity | **PASS** | #67/#69/#71/#72 heads and `main` are ancestors; #68 content-contained (its only non-ancestor commit is empty) — TASK_REGISTER "Containment proof" |
| Functional completeness | **PASS** | full backend suite 3,350 passed / 0 failed; Main TMS E2E 202 × 3 browsers; PW E2E 42 × 3; workflow defects D12, D15–D18, D21, D26 fixed with regression tests |
| Role permissions | **PASS** | role/scope matrices incl. 112-case custom-phase matrix (D10 + create follow-up), scope parity 1,344/1,344, cross-Wing isolation suites |
| Security | **PASS** (open policy items in RISK_REGISTER) | D10, D11 (stored XSS), D13 (CSRF), D14 (limiter, proven on PostgreSQL) fixed; code security review: no finding ≥ 8 (to `ea12454`) + post-`ea12454` review; X-Forwarded-For spoofing refuted on staging |
| Main TMS | **PASS** | E2E chromium/firefox/webkit in CI; extraction parity (40 deliberate changes, none lost); staging browser suite |
| Planning Workspace | **PASS** | typecheck, 146 unit tests, build; E2E × 3 browsers; staging smoke |
| Integration (TMS ↔ PW) | **PASS** | handoff and cross-frontend specs in CI E2E; staging PW smoke |
| Backend architecture | **PASS** | C5: 53 helpers moved verbatim (AST-verified), 656 GET responses identical; boundary tests; router ratchets |
| Frontend architecture | **PASS** | 28 modules parse; parity proof; module sha256 verified on staging |
| Data scalability | **PASS** | bounded Service Desk list; accounts opt-in paging; C9 query-growth ratchet over 82 GETs |
| Database | **PASS** | single head; up/down/up on PostgreSQL 16 and SQLite; full chain on PostgreSQL in deploy preflight; lossy-downgrade policy documented |
| Disaster recovery | **PASS with risk** | restore drill on real production data at `0c0aadb` (run 38221096962: 23/23 checks, 9/9 app reads); staging restore → previous build → roll-forward rehearsed (D25 fixed); **R7**: not yet on PG 17 with an operator-held key |
| Reliability | **PASS** | drills under 100 users: worker kill, maintenance on/off, PostgreSQL outage — 0 × 500 after D19/D20 |
| National scale | **PASS** | local 10,200-cadet dataset: 50/100/250 users, 0 errors, p95 43–73 ms; **staging, 100 users on `7d5808c` (2026-10-13): 0.13 % errors, read p95 1.18 s, write p95 1.05 s, 0 × 429/5xx** — STAGING_EVIDENCE |
| Documentation | **PASS** | clean-clone walkthrough by a fresh agent (3,347 tests from the docs alone), 14 gaps fixed; request trace; production and rollback runbooks rewritten for v64 → v76 |
| CI | **PASS on the PR head** (re-check on the merge commit) | 28/28 checks green on `ce4a928` (2026-10-13). The previous head `8e5b833` had 3 failures; each was root-caused rather than re-run: product defect D26, a stale-baseline flaw in the REM-111 test, a fixture code collision |
| Reviews | **PASS** | independent adversarial review (NO-GO, 12 findings): 7 fixed or refuted, 5 are the owner items below |
| Governance / UAT | **BLOCKED** | `docs/beta/38` UAT not run; `46`, `47`, `36` unsigned |

## Blockers (owner actions), in order

| # | Action | Why | Where |
|---|---|---|---|
| B1 | Run UAT with real Training Officers per role; sign `docs/beta/38`, `46` (data governance), `47` (known limitations) | beta-release gate 10 | `docs/beta/37_user_acceptance_test_plan.md` |
| B2 | Decide backup custody: separate production key held outside GitHub, private artifact storage, an off-GitHub copy; sign `docs/beta/36` | R4 | RISK_REGISTER R4 |
| B3 | Rehearse decrypt → empty-schema restore → previous build on PostgreSQL 17 with the operator-held key | rollback for this release = restore (R5, R7) | rollback_runbook §1a |
| B4 | Owner chose **`API_RATE_LIMIT=1200`** per IP (2026-10-13; staging set and load-tested). Remaining: set it on production and confirm `CORS_ALLOWED_ORIGINS` holds both production frontends (the deploy script refuses otherwise) | R1, D13 | production_release_runbook §1 |
| B5 | Identify the build production really runs (Railway dashboard) and record it as the rollback target | R6 | production_release_runbook §1 |
| B6 | ~~Staging load-test accounts~~ — **DONE** 2026-10-13: owner authorised dedicated accounts; 100-user run PASSED; accounts archived | gate 7, R8 | STAGING_EVIDENCE |
| B7 | ~~Policy items~~ — **DONE** 2026-10-13: owner accepted R2 and R3, confirmed R9, changed R10 (fixed for sqn_general and national_viewer), confirmed R11 (UI note added) | security/product policy | RISK_REGISTER |
| B8 | Merge the release PR (merge commit), confirm CI green on the merge commit and the next scheduled restore test passes on `main` | containment, D6 | the release PR |

When B1–B8 are done and recorded, re-run the beta-release gate 11 consolidation; only then may
production deployment be requested, naming the exact merge commit, services, order (backend →
Main TMS → Planning Workspace) and rollback (§1a), with a backup < 6 h old.

## What changed in this release candidate (since `main` 15b0d29)

The stacked stabilisation work (#69 → #71 → #72: central permissions, view-scope source,
Main TMS modularisation, dashboard services, restore-workflow fix) plus, in this
continuation: D10–D25 (see DEFECT_REGISTER), C5 service extraction, C8 bounded lists,
C9 query ratchet, `migrate_or_hold.py`, hardened deploy scripts, and the documentation above.

## Deliberately left unchanged

Two-frontend architecture; National → Wing → Squadron tenancy; `sqn_general` record policy;
lockout semantics; forgot-code timing; the default per-IP limit value; XLSM per-session
Location/Room; the duplicate helpers listed in R13. Each is recorded, not silently decided.
