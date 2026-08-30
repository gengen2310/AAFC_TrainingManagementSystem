# 00 — Baseline before finalisation

Date: 2026-08-30
Instruction: Final Whole-System Integration, Completion, Design and Ultrareview
Program, Part 4.

Every figure below is measured from the tree or the running environment at the
time of writing. Nothing is carried over from an earlier report — Part 95 exists
because those have been wrong before, and two of them were wrong again this week.

## Identity

| | |
|---|---|
| **BASELINE SHA** | `fecbcde792d7fadce8610bd8d9756dfc7914aade` |
| short | `fecbcde` — *Merge: v58 rehearsal findings* |
| committed | 2026-08-30T01:16:27+08:00 |
| branch | `main` |

## Open PRs and branches

**None open.** Everything relevant to this program is merged.

## Scale

| measure | value | method |
|---|---|---|
| API routes | **347** | `scripts/generate_capability_manifest.py` (introspects the app) |
| Tables | **71** | same |
| Mapped models | **71** | SQLAlchemy registry |
| Alembic head | **`c3a7f2e91b48`** (v59 account_recovery) | `alembic heads` |
| Migration files | **68** | count |
| connected-frontend pages | **24** | distinct `id="page-*"` |
| connected-frontend size | **19,431 lines**, one file, one inline `<script>` | count |
| PW React routes | **24** | `<Route>` count |
| Backend test files / functions | **112 / 1,837** | count |
| Vitest files | **14** | count |
| `e2e-connected` specs | **44** | count |
| `playwright-staging` specs | **7** | count |

Last measured suite results: backend **2054 passed, 10 skipped, 0 failed**;
vitest **78 passed**; `vite build` and `tsc --noEmit` clean; connected-frontend
parses.

## Environments

| | commit | behind main | DB revision |
|---|---|---|---|
| main | `fecbcde` | — | code head `c3a7f2e91b48` |
| **staging** | `df3fff6` | **4 commits** | `c3a7f2e91b48` — current |
| **production** | `860121a` | **878 commits** | **`f6a7b8c9d0e1` (v46)** |

Staging is 4 commits behind: it lacks the two v58 rehearsal fixes and the
documentation commits.

## KNOWN MIGRATION BLOCKER — production is 27 migrations behind

`f6a7b8c9d0e1` **is** present in the current chain, so production is not
orphaned. But a production deploy would apply **27 migrations**, not the two
this programme has been reasoning about:

```
v48 add_training_classes            v53 drop_inert_planning_tables      ← DROPS TABLES
v49 add_session_audience            v54 parade_date_parade_night_fk
v50 add_cadet_class_memberships     v55 schema_integrity_fixes
v46 session_status_reason_tags      v44 add_service_tickets
v47 complete_session_status_reasons v45 service_desk_enhancements
v48 activity_local_overrides        update_block_type_taxonomy
v51 timing_template_version         add_training_class_stage_code
v38 ip_api_requests_table           add_session_timing_block_id
v39 user_api_requests_table         create_custom_training_phases
v40 drop_dead_custom_phases_table   ← DROPS A TABLE
                                    unique_planning_year_per_unit       ← GUARDED
                                    create_faq_entries
                                    planning_year_unique_only_when_active
                                    v56 activity_type_and_area_capability_tags
                                    v57 wing_timezone
                                    v58 renumber_708_year
                                    v59 account_recovery
```

Three specific risks:

1. **`b4c1f7d92e08 unique_planning_year_per_unit` is guarded** and its guard
   inspects **all** rows including archived ones. Prior experience on staging:
   archiving duplicate planning years is *not* enough — duplicates must be fully
   deleted, dependents first. Production's duplicate state is **not yet
   measured**.
2. **Two migrations drop tables** (`v40`, `v53`). Neither has been rehearsed
   against production-shaped data.
3. **Only 1 of the 27 has been rehearsed.** Task 8's rehearsal covered `v58`
   forward, backward and refusing a wrong state. The other 26 have not been run
   against a PostgreSQL instance holding production's shape.

Part 93 requires forward/rollback/re-forward rehearsal on disposable
PostgreSQL. Against this chain that is a substantial piece of work in its own
right, and it is a **release blocker for production**, not for staging.

## Known failures and flakes

- **CI is billing-blocked repo-wide** — GitHub Actions runs fail before any job
  starts. All verification in this programme is local or staging.
- **`accessibility-hardening.spec.ts`: 3 of 15 fail** on `main` and did so
  before this programme's changes (verified by running the same file against
  `origin/main` at the time). Not a regression; not yet diagnosed.
- **Staging Playwright suite needs five role codes**; only two are configured,
  so 6 tests × 3 browsers fail at `auth.ts:24` before any network call. Harness
  gap, not a product defect.
- **`SMTP_HOST` is unset on staging**, so account recovery logs mail instead of
  sending. The recovery flow has never been exercised against a real mailbox.

## Known staging / production differences

- Production runs code from before the Training Year context model, the year
  selector, account recovery, and the Account Management wording fix.
- **708's container on production** is `year=2027` holding 15 parade dates all
  in 2026, named `2026 Training Year → 2027` — verified read-only 2026-08-30.
  This is exactly the state `v58` is guarded for.
- **Squadron 718 on production** has 0 planning years and 2 live parade nights
  linked to no parade date. Awaiting a human decision; not touched.
- Staging holds 15 wings and load-test years as far out as 3107; production has
  one wing.

## What this baseline does not yet contain

Parts 6 and 7 (requirement traceability, ownership matrix) are the next
artefacts and are not written yet. Part 3's canonical entity register is not
written yet. This document is Part 4 only.

---

## Programme Baseline — Reconciliation Session (SHA 7c342f9)

**verified_against_sha:** 7c342f9  
**verified_at:** 2026-08-30  
**scope:** Full repository — backend, connected-frontend, frontend (PW), scripts, docs  
**program:** Final Whole-System Reconciliation, Completion, Integration, Design Assurance, Ultrareview and Release-Candidate Program

### Repository

| Field | Value |
|---|---|
| Repository | gengen2310/AAFC_TrainingManagementSystem |
| Branch | main |
| HEAD (short) | 7c342f9 |
| Working tree | Clean |
| Open PRs | None |

### Alembic

| Field | Value |
|---|---|
| Alembic heads | 439ed68a5796 (single head — v60 merge: phase_b + account_recovery) |
| Head count | 1 |

### Backend

| Metric | Count |
|---|---|
| Tests collected | 2080 |
| Tests currently deselected in deploy gate | 5 |
| API routes (@router.get/post/put/patch/delete) | 344 |
| Database tables (__tablename__) | 70 |

### Known test failures (pre-existing, deselected in deploy gate)

1. `test_rate_limiting.py::test_login_spike_emits_security_log`
2. `test_rate_limiting.py::test_login_spike_repeats_on_subsequent_multiples`
3. `test_rate_limiting.py::test_5xx_spike_emits_security_log`
4. `test_timing.py::test_bulk_schedules_match_single_endpoint_exactly`
5. `test_year_context.py::test_year_listing_includes_future_years_with_no_row`

### Main TMS (connected-frontend)

| Metric | Count |
|---|---|
| Page IDs (page-*) | 46 |
| File | connected-frontend/index.html (~400KB single file) |

### Planning Workspace (frontend)

| Metric | Count |
|---|---|
| React routes in App.tsx | 24 |
