# AAFC TMS — Review 2 Synthesis

**Review:** Post-Gap Human Workflow, Architecture and Design Review — Stage 2 (Superpowers)  
**Date:** 2026-08-16  
**Covers:** architecture-audit.md, api-duplication-register.md, data-model-audit.md, integration-audit.md, frontend-duplication-register.md

---

## Executive summary

The AAFC TMS v17.1 architecture is fundamentally sound. The two-frontend separation is principled and correctly implemented. Security architecture is correct. RBAC is server-enforced. Audit log is immutable. The soft-delete pattern is consistent and correct. The backend is the single source of truth for all data across both frontends.

No critical defects were found. Findings are distributed across three tiers:

- **HIGH (2 findings):** Significant reliability or discoverability failures requiring attention before broad rollout
- **MEDIUM (7 findings):** Data integrity and naming concerns worth addressing in the next implementation cycle
- **LOW / Technical debt (many):** Structural improvements that do not affect current functionality

---

## HIGH priority findings

### SYN-H01: Planning Workspace inaccessible in Safari and Firefox privacy modes

**Source:** integration-audit.md IA-R01, IA-R08  
**Impact:** A Training Officer using Safari (common on school-issued MacBooks/iPads) or Firefox with Enhanced Tracking Protection cannot complete the auth handoff from Main TMS to Planning Workspace. The PW opens but shows a login screen with no unit context.

**Root cause:** `SameSite=None` cookies are blocked by Safari's ITP and Firefox's ETP as third-party cookies. The cross-origin tab open from Main TMS to PW (different Railway subdomains) is treated as a cross-site navigation.

**Combined with IA-R08 (PW link conditionally absent from nav):** A Training Officer may not see the PW link at all in some configurations. If they do see and click it, they may arrive at an unauthenticated PW with no error explanation.

**Verified:** The `aafc_session` cookie is set with `SameSite=None; Secure` per architecture.md. This is the load-bearing configuration for the handoff. No fallback is implemented.

**What is needed (for implementation phase):**  
The most reliable fix is hash-fragment token handoff — when opening PW, the Main TMS adds the JWT as a URL hash (`/planning#tk=...`). PW reads the hash, stores the token, and clears the hash immediately. This works in all browsers without relying on cookies.

---

### SYN-H02: ParadeDate FK to PlanningNotice/PlanningConflict lacks explicit CASCADE

**Source:** data-model-audit.md DM-02, api-duplication-register.md AD-04; verified in code  
**Impact:** In PostgreSQL (production), deleting a `ParadeDate` that has associated `PlanningNotice` or `PlanningConflict` records will raise a database FK violation error. The endpoint at `DELETE /api/planning/parade-dates/{date_id}` currently does `db.delete(pd); db.commit()` with no cascade handling.

**Verified in code:**
- `PlanningNotice.parade_date_id` → `ForeignKey("parade_dates.id")` — no explicit `ondelete="CASCADE"`
- `PlanningConflict.parade_date_id` → `ForeignKey("parade_dates.id")` — same
- `delete_parade_date()` does a simple `db.delete(pd)` with no pre-deletion of related records

**What is NOT a problem:** The `ParadeDate.parade_night_id` link is stored as a plain `String(36)` (not a proper FK), so the linked `ParadeNight` and its sessions are preserved when a `ParadeDate` is deleted. Operational data is safe.

**What is needed:** Either:
1. Add pre-deletion of related `PlanningNotice` and `PlanningConflict` records in `delete_parade_date()`
2. Or add `ondelete="CASCADE"` to those FK columns (requires a new migration)

Option 1 is simpler and safer (explicit, auditable).

---

## MEDIUM priority findings

### SYN-M01: Naming — CurriculumPhase vs Training Stage

**Source:** data-model-audit.md DM-01  
Code uses `CurriculumPhase`, API uses `/curriculum/phases`, UI uses "Training Stage". These should align. "Training Stage" is the AAFC term; "Phase" is not AAFC language. This creates a translation tax for anyone maintaining the system.

**Recommended change:** Rename model to `TrainingStage`, API endpoint to `/curriculum/stages`. Frontend already uses "Stage" — no frontend change needed.

---

### SYN-M02: Naming — TrainingArea / location / Room inconsistency

**Source:** data-model-audit.md DM-03  
Three names for the same concept: `TrainingArea` (model), `locations` (PW API path), "Rooms" (user language, most common in UI). The PW API path `/api/planning/locations` is the most confusing — it implies locations (general) rather than training areas/rooms.

**Recommended change:** Rename PW API path from `/api/planning/locations` to `/api/planning/rooms`. Keep model name `TrainingArea` (AAFC official term). Frontend and nav label changes covered by Review 1 IA proposals.

---

### SYN-M03: Session cadet_group is free text with no enforcement

**Source:** data-model-audit.md DM-13; verified in code  
`Session.cadet_group` is `String(30)` with a comment listing valid values `(orientation/initial/junior/intermediate/senior)` but no DB constraint or Pydantic validator. If multiple entry paths use different values (e.g., "Senior" vs "senior" vs "Senior 2"), aggregation and filtering break.

**Verified:** The comment says `# orientation/initial/junior/intermediate/senior` — this is documentation only.

**Recommended change:** Add a Pydantic validator to the session create/update endpoints that coerces `cadet_group` to a lowercase enum set. No migration needed (existing data would be grandfathered; the validator only applies to new records).

---

### SYN-M04: Session archive (PW) is correctly hidden in Main TMS

**Source:** api-duplication-register.md AD-06; verified in code  
This concern is RESOLVED by code reading. When a session is archived via PW (`DELETE /api/planning/sessions/{id}`), it sets `is_archived = True`. Main TMS queries consistently filter `Session.is_archived == False`. Archived sessions do not appear in Main TMS views.

**Status:** No action needed. Architecture is correct.

---

### SYN-M05: Sessions created in Main TMS appear correctly in PW

**Source:** integration-audit.md IA-R07; verified in code  
This concern is RESOLVED. The `Session` model links to `ParadeNight` via `parade_night_id`. The PW planning endpoint reaches sessions via `ParadeDate → ParadeNight → Sessions`. Sessions created in Main TMS (via `POST /api/sessions`) use the same `parade_night_id` FK and therefore appear in PW's planning views whenever the linked `ParadeDate` is fetched.

**Status:** No action needed. Architecture is correct.

---

### SYN-M06: Year rollover — verify class carryover

**Source:** data-model-audit.md DM-07  
`POST /api/planning/years/{year_id}/rollover` exists. Whether it carries over `TrainingClass` records to the new year needs verification. If it does not, Training Officers must manually recreate classes each year.

**Verification needed:** Inspect the rollover endpoint implementation in planning.py.

---

### SYN-M07: PW significantly richer than Main TMS for wing/national users

**Source:** frontend-duplication-register.md  
Wing Assurance in PW has phase coverage heatmaps, subject area heatmaps, and risk scoring not present in Main TMS Wing Overview. National Assurance in PW has a Capability view not in Main TMS. A wing_admin who uses only Main TMS misses strategic analytics.

**Assessment:** This is not a bug — PW has received more recent investment. However, it means the Main TMS is increasingly a second-class experience for wing/national users who don't adopt PW.

**Implication for rollout:** Wing and national users should be guided toward PW as the primary interface. The current two-frontend narrative should clarify which frontend is preferred for which role.

---

## LOW / Technical debt findings (summarised)

| Finding | Source | Notes |
|---|---|---|
| connected-frontend is a 400KB monolith | AC-01 | Manageable at current scale; concern if codebase grows significantly |
| Hardcoded year list in Training Calendar | AC-03 | 2-line fix; becomes a bug in 2028 |
| training.py is a monolithic router | AC-08 | ~90 endpoints in one file; organise when team grows |
| `make connected` couples frontend/ to connected-frontend/ | AC-09 | Document trigger conditions clearly |
| AnchorEvent and Activity cover same real-world event | DM-10 | Consider "link anchor to activity" feature |
| Facilitator not linked to User account | DM-11 | Acceptable; document in user guide |
| PW missing guided session entry | frontend-duplication | Main TMS guided entry not replicated in PW |
| PW missing What Changed? feed | frontend-duplication | Main TMS feature not in PW |
| Main TMS missing cadet risk summary | frontend-duplication | PW feature not in Main TMS |
| Main TMS missing facilitator leave management | frontend-duplication | PW-only; Training Officers must use PW |
| Audit log missing role/action/date filters | Both | Both frontends have limited audit filters |

---

## Architecture verdicts

| Area | Verdict |
|---|---|
| Two-frontend separation | ✓ CORRECT by design |
| Security architecture | ✓ SOUND |
| RBAC implementation | ✓ CORRECT |
| Data integrity (write) | ✓ CORRECT — soft-delete, archive/restore everywhere |
| Session entity bridge | ✓ CORRECT — single table, both frontends read same records |
| Audit log | ✓ CORRECT — immutable, write-only |
| Auth handoff (Main TMS → PW) | ⚠ MEDIUM — Safari/Firefox cookie block (SYN-H01) |
| ParadeDate delete | ⚠ HIGH — FK cascade missing in production (SYN-H02) |
| API duplication | ✓ INTENTIONAL — parallel paths serve different contexts |
| Naming consistency | ⚠ MEDIUM — CurriculumPhase, TrainingArea/location naming (SYN-M01, M02) |
| cadet_group field | ⚠ MEDIUM — no constraint (SYN-M03) |

---

## Recommended action sequence (for implementation phase)

**Tier 1 — Fix before broad rollout:**
1. **SYN-H02:** Add cascade handling to `delete_parade_date()` — delete associated `PlanningNotice` and `PlanningConflict` records before deleting the `ParadeDate`
2. **SYN-H01:** Implement hash-fragment token handoff for PW tab open, removing cookie dependency

**Tier 2 — Fix in next implementation cycle:**
3. **SYN-M01:** Rename `CurriculumPhase` → `TrainingStage` (migration + endpoint rename)
4. **SYN-M02:** Rename PW API path `/api/planning/locations` → `/api/planning/rooms`
5. **SYN-M03:** Add Pydantic validator for `cadet_group` (enum enforcement)
6. **SYN-M06:** Verify year rollover includes TrainingClass carryover
7. **AC-03:** Replace hardcoded year list with dynamic calculation

**Tier 3 — Technical debt (address when convenient):**
8. AnchorEvent ↔ Activity linkage consideration
9. Audit log filter improvements
10. Clarify `make connected` documentation in CLAUDE.md

