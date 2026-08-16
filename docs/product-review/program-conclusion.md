# AAFC TMS — Post-Gap Review Program: Conclusion

**Program:** Post-Gap Human Workflow, Architecture and Design Review  
**Date:** 2026-08-16  
**Stages:** 5 of 5 complete

---

## Program summary

All five review stages are complete. The program conducted a full-spectrum audit of the AAFC TMS v17.1 system — from user workflows to architecture, design, local implementation, and an independent deep review.

| Stage | Review | Findings |
|---|---|---|
| 1 | Grill Me — workflow, IA, product meaning | 8 documents; 10+ critical findability gaps |
| 2 | Superpowers — architecture, duplication, data, integration | 6 documents; 2 HIGH (Safari auth, ParadeDate cascade) |
| 3 | Frontend Design — visual hierarchy, a11y, typography | 3 documents + artifact; 4 HIGH contrast/accessibility issues |
| 4 | /review — local implementation review | Running in background |
| 5 | Ultrareview — independent five-agent deep review | 44 findings: 7 HIGH / 14 MEDIUM / 16 LOW |

---

## Critical findings requiring immediate action (before new user cohort)

These seven findings from Review 5 are the highest-priority items in the entire program:

| ID | File | Finding |
|---|---|---|
| R5-H01 | `ops.py:636` | sqn_general reads all audit events cross-squadron — role name typo `'sqn_viewer'` |
| R5-H02 | `auth.py:232` | 5-request DoS locks all system_admin/national_admin accounts simultaneously |
| R5-H03 | `training.py:290` | Stored XSS via unvalidated parade-night date field |
| R5-H04 | `useProxyGuard.ts:30` | Proxy exit race condition — wrong squadron data on navigation |
| R5-H05 | `roleGuards.ts:9` | sqn_general can access Audit log via direct URL |
| R5-H06 | `Accounts.tsx:243` | system_admin blocked from wing filter and wing account creation |
| R5-H07 | `training.py:991` | `cancel_all_sessions` non-atomic loop — permanent partial state on failure |

---

## High-priority findings from earlier reviews

These findings from Reviews 2–3 were confirmed independently by Review 5:

| ID | Source | Finding |
|---|---|---|
| SYN-H01 | Review 2 | Safari/Firefox blocks PW auth handoff (cookie SameSite issue) |
| SYN-H02 / R5-M03 | Reviews 2 + 5 | `delete_parade_date` crashes in PostgreSQL (FK children, no cascade) |
| DES-H01 | Review 3 | `--blue (#51b0e3)` fails contrast as text on light backgrounds |
| DES-H02 | Review 3 | Session status chips colour-only (WCAG 1.4.1) |
| DES-H03 | Review 3 | P0 vs P5 items visually indistinguishable |
| DES-H04 | Review 3 | `--lgrey` and `--warn on --warn-bg` fail contrast |

---

## Architecture and design verdicts (unchanged)

- **Architecture:** Fundamentally sound. Two-frontend separation is principled and correctly implemented. Security architecture is correct. RBAC is server-enforced. Audit log is immutable.
- **Design identity:** Strong institutional palette, correctly applied in navigation. Issues are token misuse and missing system definitions.
- **Test suite:** 1756 tests pass. Specific gaps identified (template cross-squadron isolation, `set_status` optimistic locking, `_check_maintenance_login_gate` behaviour).

---

## Recommended implementation sequence

### Block 1 — Security (fix this week)

1. `ops.py:636` — R5-H01: fix role name typo (`sqn_viewer` → `sqn_general`)
2. `auth.py:232` — R5-H02: remove `failed_attempts` increment from sibling accounts in fallback scan
3. `training.py + planning.py` — R5-H03: add ISO date validators; apply `esc()` at remaining onclick sites
4. `roleGuards.ts + App.tsx` — R5-H05: set `audit: false` for sqn_general; add route guard
5. `Accounts.tsx` — R5-H06: replace `session?.is_national` with `isNational(session)`

### Block 2 — Data integrity and operational reliability (before multi-wing rollout)

6. `useProxyGuard.ts` — R5-H04: add `qc.invalidateQueries()` on navigation exit
7. `training.py:991` — R5-H07: make `cancel_all_sessions` atomic
8. `planning.py:1081` — SYN-H02/R5-M03: pre-delete children in `delete_parade_date`; move audit after commit
9. `planning.py:513` — R5-M02: apply Proxy Mode check to `update_planning_year`/`delete_planning_year`
10. `auth.py:33` — R5-M05: fix `_check_maintenance_login_gate` to check `value == "on"`
11. `training.py:929` — R5-M06: add `closeout_status == "closed"` guard to bulk endpoints
12. `training.py:985` — R5-M12: fix `cancel_all_sessions` positional argument mismatch

### Block 3 — API correctness (next sprint)

13. R5-M07: Add `version` field to `StatusIn`; call `_check_version()` in `set_status`
14. R5-M08: Fix `schedulable_only` in `_can_see`
15. R5-M11: Remove hardcoded `status='planned'` in `create_session`
16. R5-M13: Add None check in `retire_item`
17. R5-M15: Filter archived packages in `visible_items_for`
18. R5-M18: Fix `list_wing_events` pagination order

### Block 4 — Design system (before broad rollout)

19. DES-H01: Replace `--blue` with `--royal` for all text on light backgrounds
20. DES-H02: Add letter codes to session status chips (D/C/N/P)
21. DES-H03: Add semantic left border stripes to Needs Attention cards
22. DES-H04: Fix `--warn` on `--warn-bg` text contrast
23. DES-M01/M02: Add typography and spacing scale tokens to CSS
24. DES-M06: Add global `:focus-visible` focus ring rule

### Block 5 — IA and discoverability (before AAFC-wide rollout)

25. IA-01–IA-08 from Review 1: Training Year as first-class nav; Activities page restructure
26. WF-01 from Review 1: Record outcomes workflow gap (−9 to −11 clicks vs expected)
27. CF-01–CF-11 from Review 1: Critical-path items ≥5 taps

---

## What is NOT required before rollout

The following items are confirmed as working correctly and do not require changes:

- Session entity bridge (sessions created in either frontend appear correctly in both)
- RBAC server enforcement (backend permission model is correct)
- Audit log immutability
- Soft-delete pattern consistency
- API duplication between frontends (intentional parallel paths)
- Two-frontend architecture (principled separation, correct implementation)

---

## Program output documents

All in `docs/product-review/`:

| Document | Review | Description |
|---|---|---|
| `human-workflow-map.md` | 1 | Phase-by-phase Training Officer work sequence |
| `function-purpose-register.md` | 1 | ~100 functions catalogued with recommendations |
| `navigation-audit.md` | 1 | Every nav item: expected vs actual |
| `findability-audit.md` | 1 | Click-depth audit; 11 critical-path items ≥5 taps |
| `workflow-effort-audit.md` | 1 | 20 workflows measured; 6 with gap ≥3 steps |
| `duplicate-function-register.md` | 1 | Type A/B/C/D/E classification |
| `recommended-information-architecture.md` | 1 | Proposed nav tree; Training Year as top-level |
| `primary-home-shortcut-map.md` | 1 | Every function mapped to proposed primary home |
| `architecture-audit.md` | 2 | 9 findings; architecture sound |
| `api-duplication-register.md` | 2 | 10 pairs; all Class 1 intentional |
| `data-model-audit.md` | 2 | 13 findings; DM-01/02/03/13 medium |
| `integration-audit.md` | 2 | 2 HIGH; Safari cookie, PW link visibility |
| `frontend-duplication-register.md` | 2 | Page-by-page comparison |
| `review-2-synthesis.md` | 2 | Executive summary; SYN-H01/H02 |
| `design-audit.md` | 3 | 9 sections; 19 findings |
| `review-3-synthesis.md` | 3 | 4 HIGH / 7 MEDIUM / 6 LOW + action sequence |
| `review-5-synthesis.md` | 5 | 44 findings: 7 HIGH / 14 MEDIUM / 16 LOW |
| `program-conclusion.md` | All | This document |
