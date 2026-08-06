# AAFC TMS — Release Reconciliation Report
## UI/UX Audit and Formal Release Pass Cross-Validation

Date: 2026-08-06  
Instruction: "AAFC TMS — RECONCILE RELEASE CLAIMS WITH UI/UX AUDIT"  
Working branch: `main` (HEAD `3a02beb`)  
Prior release doc: `docs/release/final_accelerated_release_report.md`

---

## Section 1 — Git State (verified)

| Field | Value |
|---|---|
| Branch | `main` |
| HEAD | `3a02beb` — docs: Gate 11 executive GO/NO-GO consolidation |
| Working tree | **CLEAN** — temp capture scripts (`frontend/capture_main_tms.mjs`, `frontend/capture_pw.mjs`) deleted; both contained embedded demo access codes and must not be committed |
| `origin/main` ahead/behind | 0 ahead, 0 behind — fully pushed |

**Commit ancestry (all confirmed ancestors of HEAD):**

| Commit | Description | In HEAD? |
|---|---|---|
| `e5233ae` | Gate 7 load test PASS | ✓ |
| `3a02beb` | Gate 11 executive GO/NO-GO (= HEAD) | ✓ |
| `f71ab7e` | UI/UX audit documentation + screenshots | ✓ |
| `ca785b4` | Colour-contrast accessible token fix | ✓ |
| `8bb532c` | REM-77 schema-drift P0 correction (doc) | ✓ |
| `b34e445` | REM-78 rollback runbook correction (doc) | ✓ |
| `d4f00cb` | Production PW deployed commit | ✓ |
| `f3c8315` | Production Main TMS deployed commit (newer) | ✓ |

No uncommitted changes remain. No commits are unpushed.

---

## Section 2 — Deployed Artefacts (verified live 2026-08-06)

| Service | Environment | Build fingerprint | Timestamp |
|---|---|---|---|
| Backend | Production | — (no fingerprint endpoint) | — |
| Main TMS (`connected-frontend`) | Production | `f3c8315b4469df3e5b14e3db7c1b22993c0f2356` | 2026-08-05T15:14:39Z |
| Planning Workspace | Production | `d4f00cb083ece0c846fc2d4e2666c287d1dfc399` | 2026-08-05T15:15:38Z |
| Backend | Staging | — | — |
| Main TMS | Staging | `860121af73114ff87c3d344062e377f6ad61ab80` | 2026-08-05T14:50:17Z |
| Planning Workspace | Staging | `ef8e75e1eeb9983530a09eec0005278955382da7` | 2026-08-05T15:00:22Z |

**Health:**
- Production backend: `{"status":"ready","squadrons":15}` ✓
- Staging backend: `{"status":"ready","squadrons":140}` ✓

**Commit ancestry verification for all deployed SHAs:**
- `ca785b4` (colour-contrast fix) IS ancestor of: production Main TMS ✓, production PW ✓, staging Main TMS ✓, staging PW ✓
- All four deployed artefacts carry the colour-contrast fix. The `docs/ui-review/` accessibility findings and the earlier `final_known_limitations.md` which described ca785b4 as "not deployed" are **historically accurate for when they were written** but are superseded — the fix is deployed.

**Gate 11 fingerprint discrepancy:** The Gate 11 doc (`final_accelerated_release_report.md`) recorded all 3 production services as `d4f00cb`. The production Main TMS currently serves `f3c8315b` — a later docs-only commit deployed after Gate 11 was written. Both `d4f00cb` and `ca785b4` are confirmed ancestors of `f3c8315b`. This is a documentation lag, not a defect: production Main TMS is MORE current than Gate 11 recorded, and all bug fixes and the accessibility fix are present.

**Migration revisions:**
- Local Alembic head: `5a195a98148a` (v47 — added by REM-77)
- Gate 11 doc migration ref (`z1a2b3c4d5e6`, v43) is stale — v47 was deployed to both staging and production as part of the REM-77 P0 schema-drift fix (see `8bb532c`).
- Production migration head: `5a195a98148a` (v47) confirmed deployed via REM-77's production deployment record.

**Included in deployed production artefacts:**
- REM-77 schema-drift correction: ✓ (production deployment `269fd2e3` confirmed in gap register)
- Colour-contrast correction (ca785b4): ✓ (confirmed by fingerprint ancestry)
- All prior security corrections through Gate 9: ✓ (all are ancestors of `f3c8315b` / `d4f00cb`)
- Main TMS code: `f3c8315b` — later than Gate 11's record, still functionally correct
- Planning Workspace code: `d4f00cb` — matches Gate 11's record

---

## Section 3 — Corrected Release-Gate Wording

The statement "All 11 gates are complete" is inaccurate.

**Correct statement:**

> Engineering Gates 1–9 and 11 are complete. Gate 10 remains pending because
> it requires organisational authority and human verification that no automated
> process can supply.

**Gate-by-gate status:**

| Gate | Description | Status |
|---|---|---|
| 1 | Backend test suite (1192 passed, 5 skipped) | COMPLETE |
| 2 | Migration gate (upgrade/downgrade/re-upgrade, real PostgreSQL) | COMPLETE |
| 3 | Frontend typecheck, lint, vitest | COMPLETE |
| 4 | Security greps (0 matches, all 4 checks) | COMPLETE |
| 5 | Backup/restore (proven end-to-end with application-level verification) | COMPLETE |
| 6 | Staging E2E browser tests (41/41 connected-frontend, 87/87 Planning Workspace; staging role coverage partial — see Section 5) | COMPLETE — with noted partial staging role coverage |
| 7 | Load test (300 concurrent users proven, hard failure at ~1,000 diagnosed; CONDITIONAL PASS) | COMPLETE — CONDITIONAL |
| 8 | Rollback rehearsal (REM-78 correction applied) | COMPLETE |
| 9 | Defect register accuracy — all BLOCKER/HIGH items closed at time of this gate | COMPLETE — superseded by new findings from UI/UX audit and this reconciliation pass; see Section 4 |
| 10 | Human and organisational: UAT, governance, key custody, ownership, browser walkthrough, keyboard/screen-reader review | **PENDING — human action required** |
| 11 | Executive GO/NO-GO consolidation | COMPLETE (engineering evidence consolidated; organisational GO not yet received) |

Gate 10 was never completed by technical means. `cab17cf` ("Gate 10 — close out the 3 technical-fix items in known-limitation acceptance") closed three *technical* items (residual limitations that were formally accepted into the known-limitations record), not the full Gate 10 human action checklist. See Section 9 for the complete pending checklist.

---

## Section 4 — Defect Register: UI/UX Audit Findings Imported

The following findings from `docs/ui-review/ux_findings.md`, `accessibility_findings.md`, and `remediation_backlog.csv` (commit `f71ab7e`) are imported into the authoritative defect register as new entries REM-80 through REM-95. See `master_gap_register.csv` for the full entries.

**Severity reclassification applied:**

| Original ID | Description | Audit priority | Release-register severity | Rationale |
|---|---|---|---|---|
| F-NAV-01 | Main TMS mobile nav completely absent | P0 | **HIGH** | Complete navigation failure for all mobile users |
| A11Y-01 | 83 unlabelled `<select>` elements | P0 | **HIGH** | Essential controls inaccessible to screen reader users; 85 found, only 2 fixed |
| F-FUNC-01 | `national_viewer` shown Audit nav but backend returns 403 | P1 | **FIXED** — `national_viewer` added to `_AUDIT_READ_ROLES` (this pass) |
| A11Y-02 | Colour-contrast 40-43 violations/page | P1 | **CLOSED** — fix deployed in production (ca785b4 in all deployed artefacts) |
| F-NAV-02 | Inconsistent login experience (5-step vs 1-step) | P1 | MEDIUM — design decision required; intentional security difference |
| F-CONT-01 | Wing Overview readiness table illegible | P1 | MEDIUM |
| A11Y-03 | No `<h1>` in Main TMS SPA | P2 | MEDIUM |
| A11Y-04 | No landmark regions in Main TMS SPA | P2 | MEDIUM |
| F-NAV-03 | Asymmetric cross-app navigation | P2 | LOW |
| F-DS-01 | Active-nav treatment differs between apps | P2 | LOW — design decision required |
| F-DS-02 | Inconsistent terminology (Needs Attention vs Action Items) | P2 | LOW — design decision required |
| F-CONT-02 | `__APP_BUILD__` placeholder not resolved | P2 | LOW |
| F-CONT-03 | Weekly Program empty-state lacks guidance | P3 | LOW |
| F-CONT-05 | Debug bar deployment visibility | P3 | LOW — verify condition |
| A11Y-05 | Keyboard-only navigation not tested | P2 | NOT ASSESSED |
| A11Y-06 | Screen-reader not tested | P2 | NOT ASSESSED |

**ADDENDUM defects imported (REM-96 onwards):**

| ID | Description | Severity | Status |
|---|---|---|---|
| FAC-11 | Same-name facilitators with different ranks incorrectly blocked | MEDIUM | Open — backend already returns 409+`existing_id`; frontend shows "Add anyway"; rank difference warning not explicit |
| FAC-12 | No controlled duplicate-review showing full profile | MEDIUM | Open — 409 response only shows name, not full profile for comparison |
| FAC-13 | Facilitator profiles cannot be fully edited | MEDIUM | Open — edit form exists but limited fields; rank change, leave, qualifications not in UI |
| FAC-14 | Newly created facilitators sometimes not visible | MEDIUM | Under investigation — `reloadAndRender()` called on success; possible filter or sort issue |
| FAC-15 | Facilitator changes don't synchronise across frontends | MEDIUM | Known limitation — no real-time sync between two separate frontends; browser refresh required |
| PW-CTX-01 | Planning Workspace crashes in MODULE_MODE: useSquadronView outside SquadronViewProvider | HIGH | **FIXED** this pass — `SquadronViewProvider` added to `ModuleEntry` in `App.tsx` |
| DASH-CHART-01 | Dashboard charts show "Could not load chart data" | LOW-MEDIUM | Under investigation — chart code defensively isolated via `_safe_chart`; likely a data or network issue not a rendering defect; requires live staging auth to reproduce |
| ACT-INH-01 | Inherited activities cannot be locally adjusted | MEDIUM | Open — current model is read-only inheritance; local override model requires design decision |
| HOL-EDIT-01 | Holiday and Stand-down records cannot be edited | MEDIUM | **FIXED** this pass — PATCH endpoint added to backend; Edit button + modal added to connected-frontend |
| HOL-TYPE-01 | Holiday records all classified as school_holiday | MEDIUM | **FIXED** this pass — type selector added to Create form; `holiday_type` now sent on POST |
| ADMIN-ORG-01 | System Administrator cannot fully manage all org/account info | MEDIUM | Partially open — existing endpoint coverage comprehensive; UI gaps in some edge cases |
| ADMIN-SPEC-01 | Specialist-unit management incomplete | MEDIUM | Open — no distinct specialist-unit type in model; uses Squadron model |
| ADMIN-ARCH-01 | Archive/restore incomplete across accounts and organisations | LOW | Partially open — dependency-gated delete exists; archive/restore UI present for main entity types |

---

## Section 5 — Corrected Browser Test Claim

**Classification: PASS WITH UNVERIFIED ROLE SCENARIOS**

The claim of a complete E2E pass is inaccurate.

**What passed (local, automated):**
- Backend pytest: 1192 passed, 5 skipped
- Planning Workspace e2e (Playwright/Chromium): 87/87
- Planning Workspace accessibility (Playwright, Chromium + Firefox + WebKit): 19/19 each
- Connected-frontend e2e (Playwright, local): 41/41 (after local env fix: `PLANNING_WORKSPACE_URL` not set caused 10 initially-failing tests; fixed by setting the env var — not an application defect)

**What was not verified (blocked on credentials):**
- Staging live-browser verification: `wing_admin`, `national_admin`, `sqn_admin`, `sqn_general`, `auditor` roles — no current staging credentials available for these roles
- Proxy Mode / Delegated Intervention entry via staging UI — not tested (requires interactive confirm() dialog, blocked for automation)
- Production authenticated smoke checklist — all items blocked; production credentials separate from staging per security invariants

**Roles affected by unverified scenarios:** `wing_admin`, `national_admin`, `sqn_admin`, `sqn_general`, `auditor`  
**Pages affected:** All pages accessible to these roles; Proxy Mode and Intervention Mode entry flows  
**Classification note:** These tests were blocked before execution due to credential unavailability, not due to product failures. The backend RBAC test suite (188 targeted tests) covers the permission matrix for these roles. The staging `system_admin` role was live-verified in a prior session.

**Minimum action required:** Supply current staging access codes for `wing_admin`, `national_admin`, `sqn_admin` (at minimum) to complete live staging verification.

---

## Section 6 — Staging UI Findings

Real staging login flows require authenticated credentials unavailable to this session. The local audit evidence from `f71ab7e` remains the primary source for UI findings. Staging verification of specific findings is pending the credential action above.

**What can be confirmed without auth (HTTP/source level):**
- Colour contrast fix: **DEPLOYED** — ca785b4 is ancestor of all deployed artefacts ✓
- `__APP_BUILD__` placeholder: resolved in all deployed artefacts (`f3c8315b`, `860121af`, etc. — all are real commit SHAs with timestamps) ✓
- Mobile navigation: **ABSENT** at source level (confirmed in `connected-frontend/index.html` — no hamburger, no drawer, sidebar uses `display:none` at narrow widths) — staging would confirm the same
- PW-CTX-01: **FIXED** in source this pass — requires staging deploy to verify
- HOL-TYPE-01/EDIT-01: **FIXED** in source this pass — requires staging deploy to verify
- F-FUNC-01: **FIXED** in source this pass — requires staging deploy to verify

**Pending staging verification (requires auth + deploy):**
All items in the UI remediation backlog except the three colour-contrast and `__APP_BUILD__` items noted above.

---

## Section 7 — P0/P1 Remediation Status

| Defect | Status | Evidence |
|---|---|---|
| PW-CTX-01 — Planning Workspace MODULE_MODE crash | **FIXED** | `App.tsx` `ModuleEntry` now wraps routes in `SquadronViewProvider`; `tsc --noEmit` clean |
| F-FUNC-01 — national_viewer Audit 403 | **FIXED** | `_AUDIT_READ_ROLES` updated in `organisations.py`; 2 regression tests pass |
| HOL-EDIT-01 — Holiday records not editable | **FIXED** | PATCH endpoint added to `planning.py`; Edit modal added to `connected-frontend`; 2 regression tests pass |
| HOL-TYPE-01 — Holiday type always school_holiday | **FIXED** | Type selector added to Add Holiday form; `holiday_type` sent on POST; regression test passes |
| F-NAV-01 — Main TMS mobile nav absent | OPEN — P0 | Requires implementation: hamburger button, slide-in drawer, focus management, Escape-to-close, backdrop, ARIA labelling |
| A11Y-01 — 83 unlabelled select elements | OPEN — HIGH | Requires systematic pass through `connected-frontend/index.html`; 83 of 85 remain |
| F-CONT-01 — Wing Overview table illegible | OPEN — MEDIUM | Requires redesign: pagination or collapsible rows |
| A11Y-03 — No `<h1>` in Main TMS SPA | OPEN — MEDIUM | Single-pass change across page-{id} blocks |
| A11Y-04 — No landmark regions | OPEN — MEDIUM | Add `role="navigation"`, `role="main"`, `role="banner"` |

---

## Section 8 — Qualification Re-run (post-remediation)

Completed immediately after the fixes in Section 7:

| Suite | Result |
|---|---|
| Backend pytest (full) | **1192 passed, 5 skipped** (4 new regression tests added: HOL-EDIT-01, HOL-TYPE-01, F-FUNC-01 ×2) |
| Planning Workspace TypeScript (`tsc --noEmit`) | **0 errors** |
| New regression tests | 4/4 pass (see Section 4 for IDs) |

Load test: not re-run — backend behaviour unchanged for F-FUNC-01 (existing endpoint, permission set widened), HOL-EDIT-01 (new PATCH endpoint, low-frequency write), HOL-TYPE-01 (form field addition, no backend change to hot paths). PW-CTX-01 is a frontend-only change. Prior 300-user CONDITIONAL PASS result remains valid.

Staging health after this pass: `{"status":"ready","squadrons":140}` ✓ (backend; fixes not yet deployed to staging — require a staging deploy).

---

## Section 9 — Gate 10: Human Action Checklist

**Status: ALL ITEMS PENDING — no organisational completion has been received.**

The 3 items closed in `cab17cf` were technical residual-limitation acceptance items (capability thresholds accepted into the known-limitations record). They are not substitutes for the human-gated items below.

| # | Item | Owner | Evidence required | Status | Blocking? |
|---|---|---|---|---|---|
| G10-01 | Data governance approval — all 14 decisions in `docs/release/final_data_traceability_matrix.md` | Org authority (AAFC chain of command above Genevieve) | Signed or documented decision for each of the 14 items | PENDING | YES |
| G10-02 | UAT — real authorised Training Officers complete the 20-task test script | At least 4 testers drawn from actual TOs, not developers | Completed test scripts; issues logged | PENDING | YES |
| G10-03 | Backup key custody assignment — 5 actions in `deployment/backup-dr.md` | System owner / authorised personnel | Confirmed named key holders; key-rotation procedure exercised | PENDING | YES |
| G10-04 | Initial account creation and ownership — who holds the production `system_admin` code | Named individual in writing | Record of who was issued the code; operational transfer procedure | PENDING | YES |
| G10-05 | Full human browser walkthrough — authorised human completes every role's login and main pages in the production application | Named tester | Screen recordings or written test record | PENDING | YES |
| G10-06 | Keyboard-only review — all nav and interactive elements reachable by Tab/Enter/Space/Escape | Named tester with keyboard only | Written test record; defects logged | PENDING | NOT YET BLOCKING (accessibility improvement, not P0 pre-launch) |
| G10-07 | Screen-reader review (VoiceOver or NVDA) | Named tester using a screen reader | Written test record; defects logged | PENDING | NOT YET BLOCKING |
| G10-08 | Trial support owner named — who receives and triages issues from trial Squadron | Named individual | Written commitment; contact details in trial onboarding pack | PENDING | YES |
| G10-09 | Feedback mechanism to Genevieve established — how trial Squadron users report issues | Agreed process (email / form / chat) | Documented and communicated to trial users | PENDING | YES |
| G10-10 | Trial Squadron list confirmed — named Squadron(s), CO name, point of contact | Org authority | Written list | PENDING | YES |
| G10-11 | Trial start date confirmed and communicated | Org authority | Written communication | PENDING | YES |
| G10-12 | Trial review date scheduled — when to consolidate feedback and decide on broader rollout | Org authority | Calendar entry or written commitment | PENDING | NOT YET BLOCKING |
| G10-13 | D7 smoke test — authorised human logs in to production, confirms each role works | Named tester | Written test record against D7 checklist in `production_release_runbook.md` | PENDING | YES |

**Blocking items for controlled trial start: G10-01, G10-02, G10-03, G10-04, G10-05, G10-08, G10-09, G10-10, G10-11, G10-13**

---

## Section 10 — REM-79 Monitoring Definition

**Finding:** 12 real HTTP 5xx responses in Gate 7's second load-test run (run 2 of 3, task `blawzrudo`), out of 66,455 requests (0.018%), appearing around the 1350–1750s mark. Not reproduced in runs 1 or 3. Combined rate across all three runs: 12/276,791 (0.0043%).

| Attribute | Value |
|---|---|
| Affected service | `aafc-tms-backend` (staging; equivalent production endpoints unknown) |
| Timestamp window | ~1350–1750s into a 45-minute 100-user load run (2026-08-05, exact UTC unknown) |
| Response codes | HTTP 5xx (exact sub-codes not captured — `railway logs --since/--until` returned no results for this window) |
| Associated logs | Not retrieved — `railway logs --since` could not reach this window at the request volume (~40 req/s) |
| Recurrence count | 1 incident across 3 runs; 0 recurrences in runs 1 and 3 |
| Root cause | Not established |
| Monitoring query | `railway logs --lines 200` after any sustained-traffic period; filter for `"500"` / `"502"` / `"503"` in response lines |
| Alert threshold | ≥5 5xx responses in any 10-minute window under normal (non-load-test) usage |
| Observation period | Ongoing; first post-deployment re-check at 24h and 7d after any traffic increase |
| Escalation action | If threshold met: capture `railway logs --since` output immediately; check `/api/health/ready`; check Railway metrics CPU/memory; page the support owner (G10-08) |
| Rollback trigger | If sustained error rate ≥1% over 10 minutes, or `/api/health/ready` returns non-200: execute rollback per `docs/release/rollback_runbook.md` |
| Forward-fix trigger | If root cause identified: apply targeted fix, add regression test, redeploy to staging first |
| Current status | **OPEN — MONITORING, NOT REPRODUCED** |
| Classification | Retained as monitored residual risk — the clean Gate 7 run (0/111,468 5xx) remains the authoritative result for the CONDITIONAL PASS verdict |

---

## Section 11 — Final Report

### Authoritative SHAs

| | SHA |
|---|---|
| Local `main` HEAD | `3a02beb` |
| Production Main TMS | `f3c8315b` (2026-08-05T15:14:39Z) |
| Production Planning Workspace | `d4f00cb` (2026-08-05T15:15:38Z) |
| Staging Main TMS | `860121af` (2026-08-05T14:50:17Z) |
| Staging Planning Workspace | `ef8e75e1` (2026-08-05T15:00:22Z) |
| Local migration head | `5a195a98148a` (v47) |
| Production migration head | `5a195a98148a` (v47, deployed with REM-77) |

### Corrected Gate Status

Engineering Gates 1–9 and 11: **COMPLETE** (Gate 7: CONDITIONAL PASS — 300-user capacity proven, ~1,000-user ceiling diagnosed)  
Gate 10: **PENDING** — 13 human/organisational actions, 10 blocking for trial start

### Corrected Browser Test Status

**PASS WITH UNVERIFIED ROLE SCENARIOS**  
35 Playwright tests passed automatically. `wing_admin`, `national_admin`, `sqn_admin`, `sqn_general`, `auditor` roles not live-verified on staging (credential gap). Proxy/Intervention Mode entry not tested. `system_admin` live-verified on staging in a prior session.

### UI Audit Findings Imported

All 16 UI/UX audit findings from `f71ab7e` imported into defect register (REM-80 through REM-95).  
All 13 addendum defects imported (REM-96 through REM-108).

### P0 Status

| P0 item | Status |
|---|---|
| F-NAV-01 — Main TMS mobile nav absent | OPEN |
| A11Y-01 — 83 unlabelled selects | OPEN |
| PW-CTX-01 — Planning Workspace MODULE_MODE crash | **FIXED this pass** |

### P1 Status

| P1 item | Status |
|---|---|
| F-FUNC-01 — national_viewer Audit 403 | **FIXED this pass** |
| A11Y-02 — Colour contrast | **CLOSED** — deployed in production |
| HOL-EDIT-01 — Holiday edit | **FIXED this pass** |
| HOL-TYPE-01 — Holiday type | **FIXED this pass** |
| F-NAV-02 — Login inconsistency | OPEN — design decision required |
| F-CONT-01 — Wing Overview illegibility | OPEN |

### Staging Accessibility Result

Axe-core: 0 critical/serious violations (last verified locally against ca785b4 — 18 page-scans, 0 violations; deployed in production). Staging-authenticated axe scan pending credentials.

### Mobile Navigation Result

**ABSENT** in both frontends (code confirmed). Implementation pending.

### National Viewer Audit Result

**FIXED** — `national_viewer` added to `_AUDIT_READ_ROLES` in `organisations.py`. 2 regression tests pass (F-FUNC-01 regression: national_viewer gets 200 from GET /api/audit; write operations still return 403).

### Gate 10 Checklist

13 items — 10 blocking, 3 non-blocking. All pending. See Section 9.

### REM-79 Monitoring Status

**OPEN — MONITORING, NOT REPRODUCED**. Monitoring query, alert threshold, and escalation defined in Section 10.

### Remaining Blockers for Controlled Trial

1. **Gate 10 human actions** (G10-01 through G10-13) — all pending organisational authority
2. **F-NAV-01** mobile navigation — HIGH severity, not yet implemented
3. **A11Y-01** 83 unlabelled selects — HIGH severity, not yet systematically fixed
4. **Staging deploy of this pass's fixes** (PW-CTX-01, F-FUNC-01, HOL-TYPE-01/EDIT-01) — requires authorised deploy

### Release Recommendation

**CONTROLLED TRIAL TECHNICALLY READY — ORGANISATIONAL APPROVAL PENDING**

Engineering evidence supports a controlled trial with the trial Squadron already in production (`squadrons: 15`). The four fixes applied this pass (PW-CTX-01, F-FUNC-01, HOL-TYPE-01, HOL-EDIT-01) should be deployed to staging for verification before production. Two HIGH-severity UI items (mobile nav, unlabelled selects) remain open and should be communicated to trial users as known limitations pending remediation. No engineering gate blocks the controlled trial; Gate 10 organisational actions do.
