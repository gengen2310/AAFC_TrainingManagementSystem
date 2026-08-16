# AAFC TMS — Review 5 Synthesis (Ultrareview)

**Review:** Post-Gap Human Workflow, Architecture and Design Review — Stage 5 (Ultrareview)  
**Date:** 2026-08-16  
**Method:** Independent five-agent deep review — main ultrareview + Security/RBAC, Data Integrity, Test Coverage, Frontend Logic, and API Correctness sub-agents  
**Scope:** Full codebase — backend routers, models, services, auth, frontend (SPA + PW React app), test suite  
**Security constraint:** No credentials, DATABASE_URL, or access codes were printed

---

## Executive summary

The ultrareview found **44 distinct findings** across six dimensions. Seven are **HIGH** (require immediate attention before any new cohort of users onboards), twenty-one are **MEDIUM** (require fixing before broad rollout to multiple wings), and sixteen are **LOW** (technical debt with low immediate impact).

The highest-severity cluster is in **authentication and RBAC** — two HIGH security findings that could allow a sqn_general user to read squadron-wide admin audit logs, and an unauthenticated caller to lock out all system_admin accounts simultaneously in five HTTP requests.

The second critical cluster is the **Planning Workspace proxy exit** in the React frontend — a navigation race condition that can expose another squadron's data to a wing_admin.

No findings contradict the architectural soundness confirmed in Review 2. All HIGH findings are bounded, fixable bugs — not architectural flaws.

---

## HIGH priority findings

### R5-H01: `sqn_general` reads all audit events cross-squadron — typo in role guard

**File:** `backend/app/routers/ops.py` line 636  
**Root cause:** The recent-changes scoping filter tests `role in ('sqn_admin', 'sqn_viewer')`. `sqn_viewer` is not a valid role — the correct name is `sqn_general`. Every sqn_general user falls through to the unscopped else-branch (national/auditor/system_admin path) and receives every AuditLog entry system-wide: access-code resets, archive decisions, login events for all admin accounts across all squadrons and wings.  
**Fix:** Change `'sqn_viewer'` to `'sqn_general'` on line 636. Add a test.

---

### R5-H02: 5-request DoS locks every national_admin/system_admin simultaneously

**File:** `backend/app/routers/auth.py` lines 232–237  
**Root cause:** For accounts with no squadron or wing (`national_admin`, `system_admin`, `auditor`), `_scoped_fallback_scan` queries every other user of the same role and increments each one's `failed_attempts` on mismatch. The `/api/auth/lookup` endpoint is unauthenticated and returns `user_id` for any known role, providing the account IDs needed. An attacker sends 5 failed logins against one system_admin account → all sibling system_admin accounts reach the lockout threshold (5) and are locked for 24 hours.  
**Impact:** All administrative accounts (national_admin, system_admin, auditor) can be locked simultaneously from one IP with 5 requests.  
**Fix:** `_scoped_fallback_scan` must not increment `failed_attempts` on fallback users — it should only check whether the code matches (read-only scan). Per-account increment must only apply to the specific account being targeted.

---

### R5-H03: Stored XSS via unvalidated date field in parade-night models

**File:** `backend/app/routers/training.py` line 290; `backend/app/routers/planning.py` line 581; `connected-frontend/index.html` lines 7023, 7898–7921  
**Root cause:** `ParadeIn.date`, `ParadeNightUpdateIn.date`, and `ParadeDateIn.parade_date` are bare `str` fields with no ISO date validation. A sqn_admin can store an arbitrary string as a date. The connected-frontend renders API-supplied dates unescaped in 9+ onclick handlers. `script-src 'unsafe-inline'` in the CSP allows injected event-handler code to execute.  
**Fix:** Add ISO date validators to all three models (the `_validate_iso_date` helper already exists in `planning.py` — reuse it). Apply `esc()` at every remaining onclick site in the frontend.

---

### R5-H04: Planning Workspace proxy exit is a race condition — new page fetches under wrong squadron context

**Files:** `frontend/src/auth/useProxyGuard.ts` lines 30+; `frontend/src/auth/ProxyControls.tsx`  
**Root cause:** The navigation guard fires `exitProxy()` as non-blocking (by design, due to `BrowserRouter` limitations). The new page's React Query fetches execute before `exitProxy()` completes — returning the proxied squadron's data to the wing_admin's new view. Additionally, the navigation-exit path never calls `qc.invalidateQueries()`, unlike the manual "Exit proxy" button in `ProxyControls.tsx`, leaving stale proxy-scoped cache entries alive on the destination page.  
**Fix:** (a) After `exitProxy()` resolves, call `qc.invalidateQueries()` in `useProxyGuard`. (b) Consider blocking navigation until exit completes (can be approximated with a loading state).

---

### R5-H05: sqn_general can access the Audit Log via direct URL — no route guard on `/audit`

**Files:** `frontend/src/auth/roleGuards.ts` line 9; `frontend/src/App.tsx`  
**Root cause:** `roleGuards.ts` returns `audit: true` for all roles including sqn_general. No route-level guard wraps the `/audit` route in `App.tsx`. A sqn_general user who navigates directly to `/audit` receives squadron-scoped audit entries including admin login events and access-code reset actions.  
**Fix:** Add `audit: false` for sqn_general in `roleGuards.ts` and add a `<RequireRole>` wrapper on the `/audit` route.

---

### R5-H06: system_admin blocked from wing filter and wing-scoped account creation — wrong session field

**Files:** `frontend/src/routes/Accounts.tsx` lines 243, 381  
**Root cause:** Both the wing-filter display condition and the "Create wing-scoped account" wing-selector `disabled` prop use `session?.is_national` (a backend boolean that is false for system_admin, who has no `national_id` FK). The correct test is `isNational(session)` (role-based helper), which returns true for system_admin. Result: system_admin cannot filter accounts by wing and cannot create wing_admin accounts through the UI.  
**Fix:** Replace `session?.is_national` with `isNational(session)` at lines 243 and 381; similarly `session?.is_wing` with `isWing(session)` at the parallel wing-filter condition.

---

### R5-H07: `cancel_all_sessions` commits inside a per-session loop — partial failure leaves irrecoverable inconsistent state

**File:** `backend/app/routers/training.py` line 991  
**Root cause:** The loop commits after each session individually. If any mid-loop commit fails (DB timeout, FK violation), sessions 1..N are permanently cancelled and sessions N+1..end remain in their prior state. The caller receives HTTP 500 with no indication of which sessions changed. There is no rollback.  
**Fix:** Move `db.commit()` to after the loop (one commit for all sessions), consistent with `edit_session` and `set_status`. Add the closed-night guard check (see R5-M06).

---

## MEDIUM priority findings

### R5-M01: Maintenance gate middleware trusts JWT role without checking token_version or active_status

**File:** `backend/app/main.py` line 225  
The maintenance_gate middleware reads `payload.get("role")` from the JWT without consulting the database. A revoked system_admin JWT bypasses maintenance mode blocks even after the account is disabled.

---

### R5-M02: Wing admin can PATCH/DELETE squadron planning year without Proxy Mode

**File:** `backend/app/routers/planning.py` lines 513–573  
`update_planning_year` and `delete_planning_year` use `_require_year_access(write=True)`, which for wing_admin checks only wing membership — not Proxy Mode. `create_planning_year` was explicitly fixed to require Proxy Mode for squadron-scoped years; the fix was not applied to update/delete.

---

### R5-M03: `delete_parade_date` no FK pre-flight — crashes in PostgreSQL if notices/conflicts exist

**File:** `backend/app/routers/planning.py` lines 1081–1095  
Confirmed in Review 2 (SYN-H02). Repeated here as it was independently confirmed with the additional detail that `AnchorPrepPlan.planned_parade_date_id` is also a FK child without cascade. Fix: delete `PlanningNotice`, `PlanningConflict`, and `AnchorPrepPlan` child rows before deleting the `ParadeDate`.

---

### R5-M04: Phantom audit entry persisted before failed `delete_parade_date` commit

**File:** `backend/app/routers/planning.py` lines 1092–1094  
`audit(db, ...)` commits the audit row before `db.delete(pd); db.commit()`. If the delete raises IntegrityError (Postgres FK), the audit row persists claiming a deletion that never happened. Fix: move the audit call to after the delete commits, consistent with `delete_planning_year`.

---

### R5-M05: `_check_maintenance_login_gate` tests row existence, not `value == "on"`

**File:** `backend/app/routers/auth.py` line 33  
`if not db.get(SystemSetting, "maintenance_mode"):` — an ORM object is always truthy. The bypass only fires when the row is absent. Fix: `row = db.get(...); if not row or row.value != "on": return`.

---

### R5-M06: `mark_remaining_delivered` and `cancel_all_sessions` don't check `closeout_status == "closed"`

**File:** `backend/app/routers/training.py` line 929  
`update_parade_night` explicitly raises 409 when `closeout_status == "closed"` to protect historical records. Neither bulk endpoint checks this. A user can overwrite finalized session statuses on a closed parade night.

---

### R5-M07: `StatusIn` model has no `version` field — status transitions lack optimistic locking

**File:** `backend/app/routers/training.py` line 639  
`edit_session` calls `_check_version()` but `set_status` (POST `/sessions/{sid}/status`) does not. Concurrent calls can produce `SessionStatusHistory` rows with wrong `old_status`, silently corrupting the audit trail.

---

### R5-M08: `schedulable_only` parameter accepted but never read in `_can_see`

**File:** `backend/app/services_program.py` line 29  
The parameter is declared but the function body never uses it. `visible_items_for(schedulable_only=True)` returns identical results to `schedulable_only=False`, making the scheduling picker API contract silently broken.

---

### R5-M09: `coverage_for_squadron` can double-count when two program items share a curriculum code

**File:** `backend/app/services_program.py` line 85  
The ID-then-code fallback credits a session's curriculum code to both a national and a squadron-local item if they share the same code. Coverage metrics may over-report.

---

### R5-M10: `create_parade` discards `None` from `_find_or_create_parade_date_for_night` when no planning year

**File:** `backend/app/routers/training.py` line 401  
When a squadron has no active `PlanningYear`, the function returns None and `create_parade` continues silently. The parade night appears in Main TMS but is invisible to Planning Workspace (whose calendar views key on `ParadeDate` rows). HTTP 200 with no error.

---

### R5-M11: `create_session` in planning router hardcodes `status='planned'`, ignoring `body.status`

**File:** `backend/app/routers/planning.py` line 1655  
`SessionCreateIn` defaults `status` to `'draft'`. The session constructor ignores it and hardcodes `status='planned'`. Draft staging is effectively broken on the planning session creation path.

---

### R5-M12: `cancel_all_sessions` passes `body.notes` as `rescheduled_to_date` — notes silently discarded

**File:** `backend/app/routers/training.py` line 985  
Positional argument mismatch. The `notes` field submitted by the caller is never persisted.

---

### R5-M13: `retire_item` does not null-check `ProgramPackage` before calling `_require_owner`

**File:** `backend/app/routers/program.py` line 176  
If `db.get(ProgramPackage, it.package_id)` returns None, `_require_owner(p, k)` raises `AttributeError` (HTTP 500 instead of HTTP 404).

---

### R5-M14: `ParadeNightTimingOverride` unique constraint + `SoftDeleteMixin` — replacement blocked after archive

**File:** `backend/app/models/training.py` line 324  
`unique=True` on `parade_night_id` while using `SoftDeleteMixin` means archiving a timing override leaves the constraint in place. Creating a replacement for the same parade night raises a unique violation.

---

### R5-M15: `visible_items_for` doesn't check `ProgramPackage.is_archived` — retired packages remain schedulable

**File:** `backend/app/services_program.py` line 20  
Items from an archived package are returned as schedulable. Squadrons can schedule sessions against retired curriculum with no warning.

---

### R5-M16: `AnchorPrepPlan` has real FK to `anchor_events` but no cascade — orphaned on archive

**File:** `backend/app/models/planning.py` line 116  
Archiving an `AnchorEvent` leaves its `AnchorPrepPlan` rows with `is_archived=False` and no live parent, and a subsequent hard-delete of the event is blocked by these orphaned rows.

---

### R5-M17: `CadetClassMembership` not cascaded on Cadet archive — archived cadets inflate class counts

**File:** `backend/app/models/training.py` line 475  
Archived cadets remain as active members in Training Classes. Class member counts and planning reports include archived cadets.

---

### R5-M18: `list_wing_events` applies DB offset/limit before Python audience filtering — pagination broken

**File:** `backend/app/routers/wing_calendar.py` line 349  
The LIKE-based audience DB filter is imprecise for JSON arrays. Python re-filters after the page is applied, producing pages shorter than requested with no total-count header. The caller cannot determine whether more matching events exist.

---

### R5-M19: Scoped login path never calls `record_login_failure_db` — no IP-level throttle on targeted login

**File:** `backend/app/routers/auth.py` lines 143–157  
When `user_id` is provided (scoped path), the per-IP failure counter is never incremented. `/api/auth/login` is also exempt from the general rate limiter. An attacker with a valid `user_id` faces no IP throttle — only the per-account lockout (5 attempts / 24h) applies.

---

### R5-M20: `/imports` route in PW has no role guard — any authenticated user can reach it by URL

**File:** `frontend/src/App.tsx` line 193  
The nav item is hidden for non-admin roles but the route itself is unguarded. A `national_viewer` can navigate directly to `/imports` and interact with the import UI (backend 403 is the only real guard).

---

### R5-M21: Scoped login path skips IP rate-limit counter entirely

Duplicate/extension of R5-M19. The scoped login path is listed in `_RATE_LIMIT_EXEMPT` in `main.py` line 239, removing the general rate limit entirely for this path.

---

## LOW priority findings

### R5-L01: Public `/api/auth/lookup` enables unauthenticated account enumeration

**File:** `backend/app/routers/auth.py` lines 79–121  
No auth required. Returns `user_id` UUID and display name for any active account given unit type + role. Feeds the DoS chain in R5-H02. Consider rate-limiting this endpoint or requiring a unit-specific nonce.

---

### R5-L02: Access log JSON injection via `request.url.path`

**File:** `backend/app/main.py` lines 310–312  
Path is `%s`-substituted into a hand-built JSON log line without escaping. A crafted path breaks log structure or injects fabricated fields into security monitoring.

---

### R5-L03: `batch_archive_accounts` leaks raw SQLAlchemy exception messages

**File:** `backend/app/routers/accounts.py` line 836  
`"reason": str(e)` on IntegrityError exposes table names, constraint names, and values to wing_admin and national_admin callers.

---

### R5-L04: Scan-all login path bypasses per-account lockout counter

**File:** `backend/app/routers/auth.py` lines 162–170  
Legacy scan-all login path (no `user_id`) never increments per-account `failed_attempts`. Per-account lockout is unreachable via this path.

---

### R5-L05: `PlanningConflict.scheduled_session_id` is bare `String(36)` — `fk_dependents` misses it

**File:** `backend/app/models/planning.py` line 130  
Sessions can be deleted while `PlanningConflict` rows retain a dangling ID. No cleanup path exists.

---

### R5-L06: `SessionAudience` missing `UniqueConstraint` despite docstring promise

**File:** `backend/app/models/training.py` line 435  
Concurrent inserts of the same `(session_id, training_class_id)` pair both succeed — the idempotent-create contract is only enforced at the API level, not at the DB level.

---

### R5-L07: `parade_night_readiness` returns `legacy_score: 100` for zero-session parade night

**File:** `backend/app/services_readiness.py` line 121  
A parade night with no sessions scores as 100% ready. Dashboard "Ready" threshold queries (≥95) will include completely unplanned nights.

---

### R5-L08: `ParadeDate.parade_night_id` is bare `String(36)` — `fk_dependents` misses it (data integrity)

**File:** `backend/app/models/planning.py` line 55  
Confirmed in Review 2. `fk_dependents` does not see this non-FK field, so a `ParadeNight` can be hard-deleted while `ParadeDate` rows still reference it. Planning calendar shows dates pointing to non-existent nights.

---

### R5-L09: `list_parades` returns HTTP 200/[] for non-existent `squadron_id` — skips permission check

**File:** `backend/app/routers/training.py` line 299  
The `if s:` guard causes the permission call to be skipped entirely when `db.get(Squadron, sq_id)` returns None. Returns empty list instead of 404.

---

### R5-L10: No test verifies cross-squadron isolation for parade night templates

**File:** `backend/tests/test_pn_templates.py`  
All tests use a single squadron. A missing filter in the list endpoint would be undetected.

---

### R5-L11: `/api/cadets/risk` sqn_general role guard is an inline check with no test

**File:** `backend/app/routers/training.py` line 1511  
A role rename would silently remove this guard with no test failure.

---

### R5-L12: `get_term_planner` calls `db.get(ParadeNight)` twice per parade date; O(2N) queries overall

**File:** `backend/app/routers/planning.py` lines 1468, 1480  
Two separate findings; a single batch join would reduce to 2 queries for any term size.

---

### R5-L13: `list_parades` skips permission check for non-existent squadron — duplicate of R5-L09 at different severity

(Combined above.)

---

### R5-L14: `login.test.tsx` mock omits `proxy` field — proxy-state initialization after login untested

**File:** `frontend/src/tests/login.test.tsx` line 77  
The mocked session has no `proxy` field. `proxyActive` initialization path from login is untested.

---

## Summary by file

| File | Findings |
|---|---|
| `backend/app/routers/auth.py` | R5-H02, R5-M05, R5-M19, R5-M21, R5-L01, R5-L04 |
| `backend/app/routers/training.py` | R5-H03, R5-H07, R5-M06, R5-M07, R5-M10, R5-M12, R5-L09, R5-L11 |
| `backend/app/routers/planning.py` | R5-M02, R5-M03, R5-M04, R5-M11, R5-L12 |
| `backend/app/routers/ops.py` | R5-H01 |
| `backend/app/routers/accounts.py` | R5-L03 |
| `backend/app/routers/program.py` | R5-M13 |
| `backend/app/routers/wing_calendar.py` | R5-M18 |
| `backend/app/main.py` | R5-M01, R5-L02 |
| `backend/app/models/training.py` | R5-M14, R5-M17, R5-L06 |
| `backend/app/models/planning.py` | R5-M16, R5-L05, R5-L08 |
| `backend/app/services_program.py` | R5-M08, R5-M09, R5-M15 |
| `backend/app/services_readiness.py` | R5-L07 |
| `frontend/src/auth/useProxyGuard.ts` | R5-H04 |
| `frontend/src/auth/roleGuards.ts` | R5-H05 |
| `frontend/src/routes/Accounts.tsx` | R5-H06 |
| `frontend/src/App.tsx` | R5-M20, R5-L14 |
| `backend/tests/test_pn_templates.py` | R5-L10 |

---

## Action sequence

### Tier 1 — Fix before any new user cohort onboards (days)

1. **R5-H01:** Change `'sqn_viewer'` → `'sqn_general'` in `ops.py` line 636 + add test
2. **R5-H02:** Remove `failed_attempts` increment from `_scoped_fallback_scan` siblings
3. **R5-H03:** Add ISO date validators to `ParadeIn.date`, `ParadeNightUpdateIn.date`, `ParadeDateIn.parade_date`; apply `esc()` at remaining onclick sites
4. **R5-H04:** Add `qc.invalidateQueries()` in `useProxyGuard` exit path; add navigation loading gate
5. **R5-H05:** Set `audit: false` for sqn_general in `roleGuards.ts`; add route guard on `/audit`
6. **R5-H06:** Replace `session?.is_national` with `isNational(session)` at lines 243 and 381
7. **R5-H07:** Make `cancel_all_sessions` atomic — one commit after the loop; add closed-night guard

### Tier 2 — Fix before broad rollout to multiple wings (sprint)

8. **R5-M01:** Maintenance gate must check token_version + active_status via DB
9. **R5-M02:** Apply `require_can_write_squadron` (Proxy Mode) to `update_planning_year` and `delete_planning_year` for squadron-scoped years
10. **R5-M03/M04:** Fix `delete_parade_date` — pre-delete children, move audit after commit
11. **R5-M05:** Fix `_check_maintenance_login_gate` to check `value == "on"`
12. **R5-M06:** Add `closeout_status == "closed"` guard to bulk session endpoints
13. **R5-M07:** Add `version` field to `StatusIn`; call `_check_version()` in `set_status`
14. **R5-M08:** Fix `schedulable_only` to actually filter in `_can_see`
15. **R5-M11:** Remove hardcoded `status='planned'` in `create_session`; use `body.status`
16. **R5-M12:** Fix `cancel_all_sessions` positional argument — pass `reason` as `reason`, `notes` as `notes`
17. **R5-M13:** Add None check for `ProgramPackage` in `retire_item`
18. **R5-M14:** Resolve `ParadeNightTimingOverride` unique+SoftDelete conflict
19. **R5-M15:** Add `ProgramPackage.is_archived == False` check in `visible_items_for`
20. **R5-M16:** Add cascade/archive handling for `AnchorPrepPlan` on `AnchorEvent` archive
21. **R5-M20:** Add role guard to `/imports` route

### Tier 3 — Technical debt (backlog)

22. **R5-L01–L14:** Rate-limit `/api/auth/lookup`; fix log injection; fix `parade_night_readiness` zero-session score; add missing UniqueConstraint; add cross-squadron template tests; fix `get_term_planner` N+1; etc.

---

*Review 5 (ultrareview) complete. 44 findings. 7 HIGH, 14 MEDIUM, 16 LOW. No code was changed in this review.*
