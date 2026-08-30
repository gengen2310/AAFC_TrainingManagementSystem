# Master Final Gap Register

**Authority:** This document is the single authoritative engineering gap register for the Final Whole-System Reconciliation, Completion, Integration, Design Assurance, Ultrareview and Release-Candidate Program.

**verified_against_sha:** 7c342f9  
**register_created:** 2026-08-30  
**sources:** SRC-001 through SRC-020 (see docs/final/source-material/source-manifest.csv)

All implementation work for this program is governed by this register. Every gap resolved must update the `status` column in MASTER_FINAL_GAP_REGISTER.csv and record the commit SHA.

---

## Summary

| Severity | Count | Open | Closed |
|---|---|---|---|
| P0 — Critical (release blocker) | 1 | 1 | 0 |
| P1 — High (should fix before release) | 7 | 7 | 0 |
| P1 HUMAN_DECISION | 2 | 2 | 0 |
| P2 — Medium | 7 | 7 | 0 |
| P3 — Low | 3 | 3 | 0 |
| **Total open** | **20** | **20** | **0** |

### Previously resolved (not in open register)

These were verified CLOSED at programme baseline (HEAD 7c342f9) and are not tracked as open work:

| ID | Area | Resolution |
|---|---|---|
| R5-H01 | Auth/RBAC — `_check_maintenance_login_gate` off-by-one | Fixed: `mm_row.value != "on"` (auth.py:57) |
| R5-H02 | Training — `ParadeIn` date validator | Fixed: `@field_validator("date")` in training.py:280-306 |
| R5-H03 | Training — `closeout_status == "closed"` guards | Fixed: training.py:992,1038 |
| R5-H04 | Auth/PW — Proxy exit race condition | Fixed: `qc.invalidateQueries()` in useProxyGuard.ts (commit 7c342f9) |
| R5-H05 | RBAC — audit role missing from `_can_see` | Fixed: roleGuards.ts:11 |
| R5-H06 | RBAC — `isNational` missing system_admin | Fixed: roleGuards.ts — `isNational` includes system_admin |
| R5-H07 | Training — `_recompute()` not committing session changes | Fixed: training.py:658-670 |
| SYN-H02 | Backend — PostgreSQL FK cascade on parade date delete | Fixed: `delete_parade_date` pre-deletes FK children (planning.py:1286-1321) |
| R5-M02 | Planning — missing `require_can_write_squadron` on year update/delete | Fixed: planning.py:694-737 |
| R5-M05 | Auth — maintenance gate off-by-one | Fixed: auth.py:57 |
| R5-M06 | Training — bulk operations missing closeout guard | Fixed: training.py:992,1038 |
| R5-M07 | Training — `StatusIn` missing version field for optimistic locking | Fixed: StatusIn.version at training.py:625 |
| R5-M11 | Training — `create_session` hardcoded status "planned" | Fixed: `SessionCreateIn.status: str = "draft"`, body.status passed through |
| R5-M15 | Program — `visible_items_for` returns archived packages | Fixed: `is_archived == False` filter at services_program.py:23-24 |
| DES-H02 | Design — colour-only status chips (no text label) | Fixed: `.chip-code` class added at index.html:518-519 |
| K-010 | Getting Started — cadet roster step still in DOM | Fixed: step removed; test_setup_status.py:119 verifies key absent |

---

## Open Gaps

---

### SYN-H01 — Cross-origin session cookie (Safari PW handoff)

| Field | Value |
|---|---|
| **Gap ID** | SYN-H01 |
| **Severity** | P0 — Release blocker |
| **Area** | Auth / Cookie |
| **Interface** | Both frontends + config.py |
| **Requirements** | SRC-001 Part 79; SRC-010; `.claude/rules/architecture.md` |

**Current behaviour:** `COOKIE_SAMESITE` defaults to `"lax"` (config.py:50). Safari drops cross-origin cookies with SameSite=Lax on a GET navigation. Opening Planning Workspace from the main TMS nav loses the session cookie and forces re-login.

**Expected behaviour:** `COOKIE_SAMESITE=none` (with `COOKIE_SECURE=true`) in staging/production so Safari preserves the session cookie on cross-origin navigation to PW.

**Root cause:** Config reads from environment variable. Staging/production Railway variables have not been set to override the `lax` default. The architecture rules document explicitly states SameSite=None is load-bearing for the PW handoff.

**Risk:** All Safari users who navigate from main TMS to PW are silently logged out. Affects all roles.

**Implementation plan:**
1. Set `COOKIE_SAMESITE=none` in Railway staging environment variables.
2. Confirm `COOKIE_SECURE=true` is also set (required when SameSite=None).
3. No code change needed — `config.py` reads from env.
4. Verify via Playwright cross-origin test.

**Test plan:** POST /api/auth/login → inspect `Set-Cookie` header for `SameSite=None; Secure`. Playwright: login in Chrome → open PW in new tab → assert `/api/auth/me` returns 200.

**Migration needed:** N | **Design needed:** N | **Security review needed:** N

---

### K-004 — `capabilities` missing from PW location serialiser

| Field | Value |
|---|---|
| **Gap ID** | K-004 |
| **Severity** | P1 — High |
| **Area** | Planning Workspace / Backend |
| **Interface** | PW — Training Area picker |
| **Requirements** | SRC-001 Part 42; SRC-001 Parts 41-43 |

**Current behaviour:** `planning.py:_location_out()` (lines 318-333) returns the location object without the `capabilities` field. PW receives no capability data for training areas.

**Expected behaviour:** `capabilities` (JSON list of capability tags) must be present in the serialised location so PW can show capability badges and filter by capability.

**Root cause:** `_location_out()` was written before `capabilities` was added to `TrainingArea`. The serialiser was never updated.

**Evidence:** `planning.py:318-333` — `_location_out()` dict has no `capabilities` key. `models/training.py:226-250` — `TrainingArea.capabilities: Mapped[list | None] = mapped_column(JSON, nullable=True)` exists.

**Implementation plan:**
Add `"capabilities": loc.capabilities` to the dict returned by `_location_out()` at planning.py:318.

**Test plan:** Create `TrainingArea` with `capabilities=["projector","wheelchair"]`. Call `GET /api/planning/{year}/sessions`. Assert `location.capabilities == ["projector", "wheelchair"]`.

**Migration needed:** N | **Design needed:** N | **Security review needed:** N

---

### K-005 — `is_combined` hardcoded `False` in session serialiser

| Field | Value |
|---|---|
| **Gap ID** | K-005 |
| **Severity** | P1 — High |
| **Area** | Planning Workspace / Backend |
| **Interface** | PW — Session list |
| **Requirements** | SRC-001 Part 30; SRC-001 Parts 22-25 |

**Current behaviour:** `planning.py:_real_session_out()` line 385 hardcodes `"is_combined": False` regardless of how many `SessionAudience` rows the session has. PW always shows sessions as single-class.

**Expected behaviour:** `is_combined` must be `True` when a session has more than one non-archived `SessionAudience` row.

**Root cause:** Hardcoded placeholder never replaced with derived value.

**Evidence:** `planning.py:385` — `"is_combined": False,` (literal).

**Implementation plan:**
Replace line 385 with:
```python
"is_combined": sum(1 for a in s.audiences if not getattr(a, "is_archived", False)) > 1,
```
Requires `s.audiences` to be loaded (check eager-load strategy for `_real_session_out`).

**Test plan:** Session with 1 audience → `is_combined` False. Session with 2 audiences → `is_combined` True. Session with 2 where one is archived → `is_combined` False.

**Migration needed:** N | **Design needed:** N | **Security review needed:** N

---

### K-001 — 5 deselected tests in deploy gate

| Field | Value |
|---|---|
| **Gap ID** | K-001 |
| **Severity** | P1 — High |
| **Area** | Testing / Deploy Gate |
| **Interface** | scripts/deploy-staging.sh |
| **Requirements** | SRC-001 Part 104; SRC-008 |

**Current behaviour:** 5 tests are deselected in the staging deploy gate (deploy-staging.sh lines 715-731). They pass in isolation but fail in the full-suite run due to cross-test state contamination.

**Deselected tests and root causes:**

| Test | Root cause |
|---|---|
| `test_rate_limiting.py::test_login_spike_emits_security_log` | Log-dedup state contaminated by prior tests |
| `test_rate_limiting.py::test_login_spike_repeats_on_subsequent_multiples` | Same |
| `test_rate_limiting.py::test_5xx_spike_emits_security_log` | Same |
| `test_timing.py::test_bulk_schedules_match_single_endpoint_exactly` | Rate limiter exhausted (429) by 2000+ prior test calls |
| `test_year_context.py::test_year_listing_includes_future_years_with_no_row` | `ensure_year_context` materialises future-year rows as side-effect of other tests |

**Risk:** Security-relevant tests (rate limiting spike alerts) are excluded from the deploy gate. A regression in rate-limiting alerting would not be caught.

**Implementation plan:**
- Rate limiting: add `reset_rate_limit_state()` fixture or `autouse` conftest cleanup that resets the dedup window between tests.
- Timing test: add per-test rate limiter reset or run before rate-exhausting tests.
- Year context: teardown that removes `ensure_year_context`-materialised rows or uses a dedicated DB fixture scope.
- Once all 5 pass in full-suite run: remove deselect lines from deploy-staging.sh.

**Test plan:** Run `python -m pytest tests/ -q` 3 consecutive times. All 5 tests must pass in each run.

**Migration needed:** N | **Design needed:** N | **Security review needed:** N

---

### DES-H01 — AAFC blue as text on light backgrounds (contrast)

| Field | Value |
|---|---|
| **Gap ID** | DES-H01 |
| **Severity** | P1 — High |
| **Area** | Design / Accessibility |
| **Interface** | connected-frontend/index.html |
| **Requirements** | SRC-001 Parts 87-96; SRC-007; WCAG 2.2 SC 1.4.3 |

**Current behaviour:** `--blue: #51b0e3`. On light backgrounds (`#f4f8fc` or `#ffffff`), contrast ratio is approximately 2.26–2.41:1. WCAG 2.2 SC 1.4.3 requires 4.5:1 (normal text) or 3:1 (large/bold text ≥18px regular or ≥14px bold).

**Expected behaviour:** Blue may only be used as text on dark backgrounds where it passes contrast. On light backgrounds, text must use `--dark` (#002f65, 21:1 on white) or `--royal` (#004b8d, ~7.3:1 on white).

**Known passing usages (blue text on dark bg):**
- `.tb-wm .r` (header separator "·") — on `--dark` (#002f65) → 5.56:1 ✓
- `.auth-back-btn` (auth page) — on dark auth background ✓

**Audit scope:** All `color:var(--blue)`, `color:var(--accent)`, `color:#51b0e3` usages in inline styles and rendered JS content.

**Implementation plan:**
1. Grep for all blue-as-text usages.
2. For each: determine background from CSS context.
3. If contrast < 3:1: replace color with `var(--royal)` or `var(--dark)`.
4. Do not change border, background-color, shadow, or SVG fill usages.

**Test plan:** After fix: compute contrast ratio for each changed element. Verify ≥ 4.5:1 (normal text) or ≥ 3:1 (large/bold text).

**Migration needed:** N | **Design needed:** Y | **Security review needed:** N

---

### DES-H03 — Touch target sizes

| Field | Value |
|---|---|
| **Gap ID** | DES-H03 |
| **Severity** | P1 — High |
| **Area** | Design / Accessibility |
| **Interface** | connected-frontend/index.html |
| **Requirements** | SRC-001 Part 94; WCAG 2.2 SC 2.5.8 |

**Current behaviour:** Some interactive controls (icon buttons in table rows, compact row actions, small nav items) may not meet the 44×44pt (HIG) or 24×24px (WCAG 2.2 minimum) touch target floor.

**Expected behaviour:** All interactive controls must have a minimum 44×44pt (HIG) activation area, or at minimum 24×24px with ≥ 4px spacing from adjacent targets (WCAG 2.2 SC 2.5.8 Enhanced Target Size exception).

**Implementation plan:**
1. Identify all interactive elements with visual size < 44×44pt.
2. Expand hit area using `min-width`/`min-height` with padding, without changing visual size if needed.
3. Focus areas: table row action buttons, parade night controls, compact nav items on mobile.

**Test plan:** CSS computed style check for min touch area. Manual touch test on iPad viewport (768px, `@media (pointer: coarse)`).

**Migration needed:** N | **Design needed:** Y | **Security review needed:** N

---

### DES-H04 — Minimum type size enforcement

| Field | Value |
|---|---|
| **Gap ID** | DES-H04 |
| **Severity** | P1 — High |
| **Area** | Design / Typography |
| **Interface** | connected-frontend/index.html |
| **Requirements** | SRC-001 Parts 87-96; SRC-007 |

**Current behaviour:** `--fs-4xs: 0.5rem` (8px). Some label/badge elements may use this. Project canonical minimums: labels 10px, badges 9px, UI chrome 12px.

**Expected behaviour:** No readable text element below 9px. `--fs-4xs` should only be used for decorative/non-informational content.

**Implementation plan:**
1. Grep for `--fs-4xs` usages. For each: determine if the text is readable/informational.
2. If informational: replace with `--fs-3xs` (9px) minimum.
3. Add comment `/* DECORATIVE ONLY — not for readable text */` to `--fs-4xs` token definition.

**Test plan:** After change: no readable text element uses `--fs-4xs`. Visual check at 100% zoom.

**Migration needed:** N | **Design needed:** N | **Security review needed:** N

---

### K-007 — `is_optional` / curriculum taxonomy (HUMAN DECISION)

| Field | Value |
|---|---|
| **Gap ID** | K-007 |
| **Severity** | P1 — HUMAN DECISION REQUIRED |
| **Area** | Curriculum / Planning |
| **Interface** | Planning Workspace + Backend |
| **Requirements** | SRC-001 Parts 33-38 |

**Current behaviour:** `CurriculumItem` has no `is_optional` field. Optional tier filter in PW curriculum view is a no-op. Comment at `planning.py:354` confirms this was deferred.

**Decision required:** Does the AAFC curriculum have a mandatory vs optional distinction at the item level? If yes: should `is_optional` be a per-item boolean or a tier/category? Who decides which items are optional?

**If yes, implementation plan:**
1. Migration: add `is_optional: bool = False` to `CurriculumItem`.
2. Backend: expose in curriculum API, allow write via update endpoint.
3. PW: wire optional filter to `is_optional`.

**Migration needed:** Y | **Design needed:** N | **Security review needed:** N

---

### K-009 — Stage catalogue expansion (HUMAN DECISION)

| Field | Value |
|---|---|
| **Gap ID** | K-009 |
| **Severity** | P1 — HUMAN DECISION REQUIRED |
| **Area** | Training Class / Stage |
| **Interface** | Backend + Connected Frontend + Planning Workspace |
| **Requirements** | SRC-001 Parts 26-28 |

**Current behaviour:** Stage catalogue was seeded with a basic set. SRC-001 Parts 26-28 define a richer stage taxonomy for Training Classes.

**Decision required:** What is the complete authoritative list of training stages per SRC-001 Parts 26-28? Which stages are missing from the current seed?

**If stages are missing, implementation plan:**
1. No migration needed if stages are lookup/reference data.
2. Update seed data with missing stage entries.
3. Verify via GET /api/training-classes/stages (or equivalent).

**Migration needed:** N | **Design needed:** N | **Security review needed:** N

---

### K-002 — Missing `docs/beta/test_isolation_known_issues.md`

**Current behaviour:** `scripts/deploy-staging.sh` references `docs/beta/test_isolation_known_issues.md` but this file does not exist.

**Implementation plan:** Create `docs/beta/test_isolation_known_issues.md` documenting the 5 isolation issues and root causes (see K-001). Or remove the stale reference from the deploy script.

**Migration needed:** N | **Design needed:** N | **Security review needed:** N

---

### K-003 — Stale Planning Workspace documentation

**Current behaviour:** `docs/product-review/tms-pw-current-state.md` and `tms-pw-function-ownership.md` are pre-Phase-B snapshots and do not reflect the current PW (24 React routes, parade night structure, planning phases).

**Implementation plan:** Regenerate both documents from `frontend/src/` current state, or add prominent `HISTORICAL SNAPSHOT — pre-Phase-B` header with date and a pointer to `docs/final/00-baseline.md`.

**Migration needed:** N | **Design needed:** N | **Security review needed:** N

---

### K-006 — `cadet_group` legacy consumers audit

**Current behaviour:** `cadet_group` (legacy string field on Session) is still used alongside `SessionAudience` (canonical relation). Some code paths may still read/write the legacy field directly.

**Implementation plan:** Grep `cadet_group` across all backend routers. Map each usage as: (a) read-only compatibility, (b) active write path. Replace write paths with `SessionAudience` writes. Consider data backfill for sessions that have `cadet_group` but no `SessionAudience` rows.

**Migration needed:** N (audit first; migration decision may follow) | **Design needed:** N | **Security review needed:** N

---

### K-008 — Nullable `stage_id` on sessions

**Current behaviour:** Some sessions may have null `stage_id` (via training class). A session with no training class has no stage, which may cause null errors in PW stage filter and omissions in stage-based reports.

**Implementation plan:** Query `SELECT COUNT(*) FROM sessions WHERE training_class_id IS NULL` in dev DB. If count > 0: assess whether test debris or real data. If real: decide whether to backfill or add NOT NULL constraint.

**Migration needed:** N (pending audit) | **Design needed:** N | **Security review needed:** N

---

### K-014 — Stale comment in `deploy-staging.sh:748`

**Current behaviour:** Line 748 contains comment referencing "v52 planning_year_unique_only_when_active". Current Alembic head is `439ed68a5796` (v60 merge).

**Implementation plan:** Edit deploy-staging.sh line 748 to remove or correct the stale migration reference.

**Migration needed:** N | **Design needed:** N | **Security review needed:** N

---

### R5-M13 — `retire_item` package `None` guard missing

**Current behaviour:** `program.py:retire_item` (lines 172-182) calls `_require_owner(p, k)` where `k = db.get(ProgramPackage, it.package_id)`. If `it.package_id` is null or the package was deleted, `k` is `None` and `_require_owner(p, None)` may AttributeError or bypass the permission check.

**Implementation plan:** After `k = db.get(ProgramPackage, it.package_id)`, add `if not k: raise HTTPException(404, detail={"error": "package_not_found"})`.

**Migration needed:** N | **Design needed:** N | **Security review needed:** N

---

### R5-M18 — `list_wing_events` pagination ordering with audience filter

**Current behaviour:** `wing_calendar.py:list_wing_events` uses SQL `order_by(start_date)` + `offset`/`limit` for unfiltered queries, but switches to fetch-all-then-Python-slice when an audience filter is set. This may produce inconsistent event ordering across pages.

**Implementation plan:** Review the dual-path pagination logic. Ensure `order_by` is applied consistently even in the Python-slice path. Consider adding a secondary sort key (`id`) for deterministic ordering when `start_date` is equal.

**Migration needed:** N | **Design needed:** N | **Security review needed:** N

---

### DES-M01 — Typography token application audit

**Current behaviour:** Type scale tokens are correctly defined. Individual component CSS may use incorrect tokens or hardcoded px values instead of the canonical token for the typographic role.

**Implementation plan:** Audit all `font-size` declarations in connected-frontend/index.html. Replace hardcoded px or incorrect token references with the canonical token (body 13px, UI chrome 12px, sub-text 11px, labels 10px, badges 9px).

**Migration needed:** N | **Design needed:** Y | **Security review needed:** N

---

### DES-M02 — Focus ring consistency audit

**Current behaviour:** `:focus-visible` is defined at line 178 (3px solid Highlight). Some form fields override `outline:none` with a border-color + box-shadow fallback (line 225). The box-shadow may not meet the 3:1 contrast threshold under WCAG 2.2.

**Implementation plan:** Audit all `outline:none` overrides. Verify each has a visible alternative that meets 3:1 contrast. Replace non-compliant alternatives with `outline: 3px solid var(--focus-ring)`.

**Migration needed:** N | **Design needed:** Y | **Security review needed:** N

---

### DES-M06 — `:focus-visible` coverage completeness

**Current behaviour:** `:focus-visible` is partially implemented. High-contrast media query override exists (line 210). Coverage may be incomplete for elements outside the main selector scope.

**Implementation plan:** Keyboard-tab through the full UI. For any focusable element that shows no focus indicator: add explicit `:focus-visible` rule.

**Migration needed:** N | **Design needed:** Y | **Security review needed:** N

---

## Status definitions

| Status | Meaning |
|---|---|
| OPEN | Not yet addressed |
| IN_PROGRESS | Implementation started but not complete |
| NEEDS_STAGING | Implementation complete and tested locally; awaiting staging verification |
| CLOSED | Fixed, tested, evidence recorded, staging verified |
| HUMAN_DECISION | Requires a product/domain decision before implementation can proceed |
| ACCEPTED_EXCEPTION | Known gap accepted with recorded justification; not planned for fix |

---

## Implementation order (recommended)

1. **SYN-H01** (P0) — Railway env var change, no code. Unblocks Safari testing.
2. **K-001** (P1) — Fix test isolation. Enables removal of deselections. Unblocks CI confidence.
3. **K-004** + **K-005** (P1) — PW serialiser fixes. Single file, trivial code changes.
4. **K-014** + **K-002** (P2) — Documentation fixes. 10-minute total.
5. **R5-M13** (P2) — Defensive guard. Single line.
6. **DES-H01** + **DES-H03** + **DES-H04** (P1) — Design audit pass. May be done with /apple-design.
7. **DES-M01** + **DES-M02** + **DES-M06** (P3) — Design polish pass.
8. **R5-M18** (P2) — Pagination review.
9. **K-006** + **K-008** (P2) — Data model audits.
10. **K-003** (P2) — Documentation regeneration.
11. **K-007** + **K-009** (HUMAN DECISION) — Await product input.
