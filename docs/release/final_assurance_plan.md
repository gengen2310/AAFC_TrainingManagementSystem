# AAFC TMS — Final System Assurance & Public Release Qualification

Living working document for the "FINAL SYSTEM ASSURANCE AND PUBLIC RELEASE QUALIFICATION"
engagement, approved by the user 2026-08-01 (exact phrase
`APPROVED — EXECUTE FINAL RELEASE ASSURANCE`), extended mid-engagement by explicit user
instruction to autonomously identify and fix issues/gaps found along the way without
stopping for per-item approval, while **production deployment and merging this branch to
`main` remain gated behind a separate, later, explicit authorisation** — that boundary is
not touched by the autonomy grant.

This is not a blank-slate audit. It builds directly on two prior passes already in this
repo: `docs/beta/00`–`51` (Operational Release Gate suite) and
`docs/release/qualification_gap_register.md` (GAP-01–GAP-21, now being extended with
GAP-18's full resolution as of this pass). Every prior claim is treated as a lead to
re-verify, not a fact to cite blindly.

## Baseline (Stage 0)

| Fact | Value |
|---|---|
| Working branch | `release/final-assurance-2026-08-01`, created from `main`@`2b582a7` |
| Local HEAD | `2b582a775a2d8c031c2f388e65911feb4807cbf8` |
| Ahead/behind `origin/main` | 14 ahead, 0 behind (this session's earlier Phase 1–3 work, not yet pushed) |
| Working tree | clean |
| Alembic head | single linear head `z1a2b3c4d5e6` (34 migrations) — `origin/main` computes an older head (`y8z9a0b1c2d3`, 33 migrations), missing commit `2ef0926` (NATHQ/Wing/Squadron Activity inheritance, Phase 2.1) — explains the one false-positive restore-test failure recorded under GAP-18 below |
| Repo scale | 375 tracked files; `backend/app/` 17,810 lines; `backend/tests/` 14,610 lines; `connected-frontend/index.html` 9,733 lines (single file, zero test/lint tooling — highest-risk untested surface); `frontend/src/` 12,631 lines |
| Railway project | `exemplary-emotion` / `f5d9524f-8a57-44ff-86b7-ab66aec00e73` |
| Environments | `production` (`571a8028-3640-4542-a4ab-7a1ee6b1f693`), `staging` (`77a45568-5c16-46c2-9065-d5d339208b0e`) |
| Services | `aafc-tms-backend` (`deb53faa-ca8d-4291-aa2e-9ff3029c50f8`), `aafc-tms-frontend` (`2b5e6359-2523-4209-be5b-bdf7f5273ec5`), `aafc-tms-planning-workspace-preview` (`253cf237-1836-43bc-9ee4-0e4eefd447b4`), `Postgres` (`96f1e5b4-5bf4-4803-9481-bb812ecdc905`, per-environment variable set) |
| GitHub repo | `gengen2310/AAFC_TrainingManagementSystem` |

### Contamination scan (Stage 0)

- No stray `" 2"`/copy files, no tracked `.DS_Store`, no duplicate Alembic revision IDs.
- `aafc_tms.db` (repo root and `backend/`) — confirmed correctly `.gitignore`d, **not**
  tracked (independently re-verified via `git ls-files` / `git check-ignore -v`; an
  earlier Explore agent's claim that one of these was "a 0-byte tracked file" was wrong
  — corrected here rather than propagated).
- Two stale worktrees found under `.claude/worktrees/` (`agent-a384acc669dbfca9c`,
  `agent-a50e74cd10ac5edf0`), dated 2026-07-14 and 2026-07-23. Both carry real
  **uncommitted** local changes (14 and 2 modified files respectively) from unrelated
  prior agent sessions, on their own branches, with no commits ahead of `origin/main`.
  **Left untouched** — not this engagement's work to discard, per the standing rule
  against destructive action on unfamiliar in-progress state.

## Stage 1 (started): GAP-18 re-verification — SEV1 finding, now resolved

Full write-up lives in `docs/release/qualification_gap_register.md` under GAP-18's
re-verification addendum. Summary:

- **Confirmed still fully open** before any action: production's real `DATABASE_URL`
  is Railway-internal; the daily backup secret (`PROD_DATABASE_BACKUP_URL`) still
  pointed at a Supabase host — a different physical database. Production now holds
  real data (`squadrons: 1`), making this materially more urgent than when first
  recorded (when production was empty).
- **Fixed**: repointed the secret at Railway's own already-provisioned
  `DATABASE_PUBLIC_URL` for the production Postgres service — the same database the
  backend actually serves from, reached via Railway's standard external-proxy
  mechanism. No credential created or rotated. Applied only after explicit user
  confirmation, since the environment's own safety classifier independently gated the
  `gh secret set` write.
- **Proven, not asserted**: a fresh backup + fresh restore-test run
  (`test-restore-postgresql.yml`) restored real production data —
  `squadrons: 1, wings: 1, users: 1, audit_logs: 13, curriculum_items: 214` — an exact
  match to production's independently-known live state, sharply different from the
  old (wrong-database) evidence. The restore-test's one remaining failure (migration
  head mismatch) was root-caused precisely to `origin/main` being 14 commits behind
  local and is not a real defect — see the register entry for the exact
  before/after head computation proving it.
- **Staging checked too, not assumed fine by analogy**: `backup-postgresql-staging.yml`
  still uses the legacy-named `SUPABASE_DB_URL` secret, but its own printed host
  fingerprint from a fresh dispatch (run `30711823611`) exactly matches staging's real
  `DATABASE_PUBLIC_URL` fingerprint, independently computed. No functional defect —
  only a stale secret name, already disclosed honestly in the workflow's own header
  comment.

Full source/function/API inventory complete: `final_source_inventory.md`,
`final_feature_inventory.md`, and `reports/final-assurance/{file,function,frontend-
function,connected-frontend-function,api}-inventory.csv`. Headline numbers: 341 tracked
files, 237 backend API endpoints (0 true duplicates after correcting for router
prefixes — one apparent duplicate was caught and disproved during this pass, see
`final_source_inventory.md`'s self-correction note), 57 SQLAlchemy model classes (was
estimated "~30" in the original plan — corrected), 641 backend functions/classes, 238
`frontend/src` definitions, 631 `connected-frontend` top-level definitions. Fresh
full test-suite run: **1002 passed, 5 skipped** (materially supersedes the stale "310
passed, 1 skipped" recorded in `.claude/rules/testing.md`). Spot-verified this
session's own previously-claimed shipped features (setup checklist, import preview,
drag-and-drop, Activity inheritance, GAP-21 system_admin scope bar) are genuinely
present in code, not just in commit messages.

## Skill-use register

| Skill | Task | Status |
|---|---|---|
| `beta-release` (project) | Cross-check against this repo's own established release-gate checklist | Referenced; formal cross-check pending Stage 14 |
| `use-railway` (plugin) | Environment verification, deployment IDs, variable changes (all `railway`/`gh` calls this pass) | Active, used in Stage 0/1 |
| `security-guidance` | OWASP-aligned review structure | Planned, Stage 9 |
| `42crunch-api-security-testing` | Live OpenAPI/BOLA/BFLA conformance scan against staging | Planned, Stages 4/9 |
| `supabase` (Postgres best practices) | Query-plan/index review, connection-pool sizing | Planned, Stage 8 |
| `superpowers` (systematic-debugging, code-review) | Structuring the line-by-line review and defect root-causing (already used to root-cause the migration-head false-positive) | Active |
| `context7` | Library/framework doc lookups as needed | As-needed, none yet required |
| `artifact-design` | Presenting the final release-candidate report | Planned, Stage 14 |
| Not used | `dataverse`, `aws-data-analytics`, `linear`, `github`, `ralph-loop`, `claude-md-management`, `coderabbit` | N/A to this stack/task |

## Stage status

| # | Stage | Status |
|---|---|---|
| 0 | Baseline, branch, contamination scan, skill register | Complete |
| 1 | GAP-18/GAP-16 re-verification + source/function/API inventory | Complete |
| 2 | Line-by-line code assurance + static analysis | In progress |
| 3–14 | — | Not started |

## Stage 2 progress

- **Backend** (`ruff check app/`): 1029 findings, large majority stylistic/idiomatic
  noise (469 `B008` are FastAPI's own `Depends(...)`-in-default-argument pattern —
  correct, not a defect; 239 `RUF100` unused-noqa; 112/55/33/21/3 are import-sort/
  unused-import/modernization style). Triaged the categories most likely to hide real
  bugs by hand:
  - `F841` (unused-variable, 6 instances) → 5 were genuine dead code (harmless); 1
    (`training.py`) was a real bug — see GAP-22 below.
  - `S110`/`S112` (bare `except: pass`/`continue`, 5 instances) → 2 fixed to log
    instead of silently swallowing (`ops.py` automation generator, `system.py`
    backup-download audit write); 3 reviewed and correctly left as-is (a DB health
    check, and two already-comment-documented intentional best-effort fallbacks).
  - `DTZ*` (naive-datetime usage, 38 instances) and `BLE001` (blind except, 25
    instances) — inventoried, not yet individually triaged; carried forward as
    Stage 2 remaining work.
- **`frontend/`** (Planning Workspace): `tsc --noEmit` clean (0 errors). `eslint`: 0
  errors, 17 warnings — all low-severity (react-refresh fast-refresh-only-exports
  style notices, a few unused locals, two `useMemo`/`useEffect` exhaustive-deps
  warnings in `Curriculum.tsx`/`PlanningWorkspace.tsx` worth a closer look in Stage 6
  since a missing effect dependency can cause stale-data UI bugs, but not confirmed
  as an actual defect yet).
- **`connected-frontend/`**: no lint/typecheck tooling exists for this file (plain JS,
  no build step) — confirmed at Stage 0 as the highest-risk untested surface; static
  analysis here isn't possible the same way, so it depends more heavily on Stage 2's
  manual line-by-line pass and Stage 11's browser-driven testing.
- **GAP-22 (P2, fixed)**: curriculum CSV import silently discarded the "Foundation or
  Extension" column — every row in a CSV import batch was forced to the same
  `core_status` regardless of what each row's own data said, and re-importing to
  correct it didn't work either. Full write-up in the gap register. Fixed, tested
  (new regression test, full suite 1003/5 passed clean), not yet deployed.

`BLE001` (blind-except, 24 sites) fully triaged: all reviewed individually, all
legitimate except GAP-23 (found and documented, deferred as P3).

**GAP-24 (P0/P1, fixed and live-verified)**: manual line-by-line review of
`connected-frontend/index.html` found a real, confirmed-exploitable stored XSS
reachable through multiple free-text fields (account display names, Flight names,
tag names, curriculum titles, room/equipment names, notes, reasons) — some via
attribute-breakout in inline `onclick` handlers, some via zero escaping at all.
Reproduced live end-to-end (created a malicious account through the real
authenticated API, loaded Account Management as system_admin, confirmed the
payload executed pre-fix and was inert post-fix via direct DOM/window-state
inspection) before and after the fix, using an isolated local copy so no
deployed environment was ever touched. Full write-up and fix details in the gap
register. This is the most severe finding of the engagement so far.

Manual line-by-line pass of `permissions.py`/`dependencies.py`/`security.py`
(the core RBAC/auth engine) also complete: no defects found. Correctly
algorithm-pinned JWT verification, correct token-version session revocation,
fail-closed defaults throughout, documented IDOR-prevention discipline in
`can_write_activity`.

Remaining Stage 2 work: `DTZ*` (naive-datetime, 38 sites) not yet triaged;
`connected-frontend/index.html`'s remaining ~9,800 lines beyond what's been
covered so far still need proportionally more manual attention since no static
tooling exists for that file. Given GAP-24's severity, recommend Stage 4
(role/scope/tenancy) and Stage 9 (security) move up in priority relative to the
original stage ordering.

Evidence for every stage records: what was checked, how, environment, role, input,
expected vs. actual, evidence location, Git SHA, and deployment ID where relevant, per
the instruction's own evidence standard. Raw CSVs/screenshots land under
`reports/final-assurance/`.
