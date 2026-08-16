# AAFC TMS — API Duplication Register

**Review:** Post-Gap Human Workflow, Architecture and Design Review — Stage 2 (Superpowers)  
**Date:** 2026-08-16  
**Scope:** All ~212 backend API endpoints; identify duplicate, overlapping, and parallel paths to the same data  
**Method:** Analysis only — no changes

---

## Classification

- **Class 1 — Intentional parallel paths:** Two endpoints reach the same table but serve different contexts (different response shapes, different auth rules, different callers). Expected; document to prevent confusion.
- **Class 2 — Accidental duplication:** Two endpoints do the same thing for no architectural reason. Risk of divergence.
- **Class 3 — Near-duplicate with behavioural difference:** Looks like the same endpoint but has a subtle difference. High confusion risk.
- **Class 4 — Historical artifact:** An endpoint that exists for a legacy reason; may be safe to merge.

---

## Section 1: Session creation — two API paths (Class 1)

| | Main TMS path | PW path |
|---|---|---|
| **Endpoint** | `POST /api/sessions` | `POST /api/planning/parade-dates/{date_id}/sessions` |
| **Router** | `training.py` | `planning.py` |
| **Caller** | connected-frontend Night Builder | Planning Workspace right drawer |
| **Table** | `sessions` | `sessions` (same table) |
| **Input shape** | Includes `parade_night_id`, `period_number`, `status`, `curriculum_item_id`, `facilitator_id`, `room_id`, `cadet_group` | Includes `parade_date_id`, `period_number`, `cadet_group`, curriculum/facilitator/room in separate update call |
| **Key difference** | Takes a `parade_night_id` (operational entity); creates the session in the operational context | Takes a `parade_date_id` (planning entity); auto-links to the associated ParadeNight |
| **Created row** | Same `sessions` table row | Same `sessions` table row |

**Assessment:** This is Class 1 — intentional parallel paths serving different conceptual contexts. The PW creates sessions from the planning perspective (what is planned for a date), the Main TMS creates sessions from the operational perspective (what is happening tonight). Both write to the same table; the difference is in how the session is linked to its parent context.

**Risk:** The two paths use different permission helpers. If the Main TMS path is called by a wing_admin without Proxy active, the `require_can_write_squadron` check should block it. If the PW path uses a different helper with different proxy awareness, a security gap could exist.

**Action needed:** Verify both paths use `require_can_write_squadron` (proxy-aware). Confirmed via architecture.md rules. Low risk.

---

## Section 2: Training Areas / Rooms — two endpoints (Class 1)

| | Main TMS path | PW path |
|---|---|---|
| **Read** | `GET /api/training-areas` | `GET /api/planning/locations` |
| **Write** | `PATCH /api/training-areas/{id}` | `PATCH /api/planning/locations/{id}` |
| **Router** | `training.py` | `planning.py` |
| **Table** | `training_areas` | `training_areas` (same table) |
| **Response shape** | Full room record including capacity, type, archived | Subset for planning context |
| **Auth** | `require_can_view/write_squadron` | `require_can_view/write_squadron` |

**Assessment:** Class 1. These were historically separate models but are now unified in the same table. The PW exposes a planning-context view (used by the room picker in session creation). The Main TMS endpoint is the full management endpoint.

**Risk:** If a room is created via the PW endpoint and the Main TMS endpoint is used to list rooms, there could be a schema discrepancy in the response. Practically both map to the same table so this is low risk.

**Action needed:** None. Correct architecture.

---

## Section 3: Facilitators — two read endpoints (Class 1)

| | Main TMS path | PW path |
|---|---|---|
| **Read** | `GET /api/facilitators` | `GET /api/planning/facilitators` |
| **Response** | Full record with upcoming leave, subject areas, type, load stats | Subset for assignment picker; different shape |
| **Write** | Full CRUD via `training.py` | Leave management only via `planning.py` |
| **Table** | `facilitators` | `facilitators` (same) |

**Assessment:** Class 1. The PW facilitator endpoint exists because the PW needs a subset of facilitator data formatted for its planning context (assignment suggestions, leave overlay). The Main TMS endpoint is the management view.

**Specific concern:** `GET /api/facilitators` includes leave data ("with upcoming leave") — so both endpoints include some leave context. Are they fetching the same leave records? If leave is created via the PW endpoint (`POST /api/planning/facilitators/{fac_id}/leave`) and then listed via the Main TMS endpoint — does the leave appear? If the Main TMS endpoint reads from the same `facilitator_leave` table, yes. Verify that leave created in PW is visible in the Main TMS facilitators view.

---

## Section 4: Parade Dates vs Parade Nights (Class 3 — near-duplicate with behavioural difference)

This is the most nuanced duplication in the API layer.

| | Planning entity | Operational entity |
|---|---|---|
| **Model** | `ParadeDate` | `ParadeNight` |
| **Endpoint (list)** | `GET /api/planning/years/{year_id}/parade-dates` | `GET /api/parade-nights` |
| **Endpoint (detail)** | `GET /api/planning/parade-dates/{date_id}/builder` | `GET /api/parade-nights/{pnid}` |
| **Purpose** | Forward planning: what is scheduled for this date | Operational: what happened / is happening at this night |
| **Session relationship** | Sessions linked via `parade_date_id` | Sessions linked via `parade_night_id` |
| **Created by** | PW year setup / generate dates | Same process auto-creates linked ParadeNight |
| **Status tracking** | Planning status (draft/published) | Operational status (planned/delivered/cancelled/closed) |

**Key finding:** A `ParadeDate` and its corresponding `ParadeNight` are the same real-world event but different database entities. When a `ParadeDate` is created in the PW, a `ParadeNight` is auto-created and linked. When a `ParadeNight` is closed in the Main TMS, its planning counterpart is not automatically updated.

**Risk:** If a `ParadeDate` is deleted in the PW (planning removed), does the corresponding `ParadeNight` in the Main TMS also get removed? If not, there is a dangling operational night with no planning counterpart. This is a data integrity concern, not just a duplication concern.

**Verification needed:** Check that the `DELETE /api/planning/parade-dates/{date_id}` endpoint handles the linked `ParadeNight` cascade or rejection.

---

## Section 5: Parade Night builder — two views (Class 1)

| | Main TMS path | PW path |
|---|---|---|
| **Endpoint** | `GET /api/parade-nights/{pnid}/builder` | `GET /api/planning/parade-dates/{date_id}/builder` |
| **Returns** | Timing blocks + session grid for a specific operational night | Timing blocks + session grid for a specific planning date |
| **Used by** | Main TMS night editing view | PW Parade Night view |

**Assessment:** Class 1. Two views of the same night from different contexts. The builder endpoint exists in both routers because each frontend needs the data structured for its own UI.

---

## Section 6: Session management — two PATCH paths (Class 1)

| | Main TMS | PW |
|---|---|---|
| **Update session** | `PUT /api/sessions/{sid}` | `PATCH /api/planning/sessions/{session_id}` |
| **Status transition** | `POST /api/sessions/{sid}/status` | No separate status endpoint in planning |
| **Archive** | Not a direct endpoint (sessions are cancelled/closed) | `DELETE /api/planning/sessions/{session_id}` |
| **Restore** | Not in training.py directly | `POST /api/planning/sessions/{session_id}/restore` |

**Key finding:** Session archive/restore is available via the PW API but not clearly surfaced in the Main TMS API. A session archived in PW (as a planning action — "remove this from the plan") can be restored in PW, but a session that is "cancelled" or "not delivered" in Main TMS uses a status transition, not an archive. These are two different concepts for a similar outcome:

- PW archive = "remove from the plan" (reversible, affects future sessions)
- Main TMS cancel/not-delivered = "record what happened" (historical record, not reversible in the same way)

This is a conceptual distinction, not an API bug. But it means a session can be in a state where it is "archived in PW" but has an operational status in Main TMS — or vice versa.

---

## Section 7: Notices — two endpoint families (Class 1)

| | Main TMS | PW |
|---|---|---|
| **Create** | `POST /api/parade-nights/{pnid}/notices` | `POST /api/planning/parade-dates/{date_id}/notices` |
| **Update** | Not in training.py | `PATCH /api/planning/notices/{notice_id}` |
| **Archive** | Not in training.py | `POST /api/planning/notices/{notice_id}/archive` |
| **Table** | `notices` (presumed same) | `notices` (same) |

**Assessment:** Class 1. Notices are primarily a planning tool (PW) but surfaced in the operational view (Main TMS) as read-only overlays. The mismatch (Main TMS can create but not update/archive) is a functional gap: a notice created via the Main TMS API cannot be managed from Main TMS — only from PW.

**Practical risk:** Low — notices are currently a PW-first feature.

---

## Section 8: CEA Activities — two management paths (Class 1)

| | Main TMS path | PW path |
|---|---|---|
| **Import** | `POST /api/activities/import-cea` | `POST /api/planning/years/{year_id}/cea/import` |
| **List** | In main activities list | `GET /api/planning/years/{year_id}/cea/activities` |
| **Classify** | Not in training.py | `PATCH /api/planning/cea/{activity_id}/classify` |
| **Hide** | Not in training.py | `POST /api/planning/cea/{activity_id}/local-hide` |

**Assessment:** Class 1. CEA import exists in both. The Main TMS `import-cea` endpoint appears to be the original; the PW added a year-scoped import with richer management (classify, hide). Verify whether both import flows write to the same table and whether a CEA activity imported via Main TMS endpoint appears in the PW year-scoped view.

---

## Section 9: Activities — scope-segregated creates (Class 1)

Three separate create endpoints based on scope:
- `POST /api/activities` — squadron-scoped
- `POST /api/activities/wing` — wing-scoped
- `POST /api/activities/national` — national-scoped

**Assessment:** This is intentional scope segregation — not duplication. Different roles can create at different scope levels; read access aggregates all visible scopes. Correct pattern.

---

## Section 10: Proxy state — two query paths

| | |
|---|---|
| `GET /api/proxy/current` | Returns proxy state in organisations.py |
| `GET /api/auth/me` | Also returns proxy state as part of the user object |

**Assessment:** Class 3 — near-duplicate. Both endpoints return proxy/intervention state. The `/api/auth/me` call is the auth bootstrap; the `/api/proxy/current` call is for UI polling to detect state changes. Both are needed (different polling intervals, different callers) but the response shapes should be kept consistent.

---

## Section 11: Curriculum — multiple import endpoints (Class 3)

Three curriculum import endpoints exist:
- `POST /api/curriculum/import` — generic import
- `POST /api/curriculum/import-xlsm` — XLSM-specific import
- `POST /api/curriculum/import-csv` — CSV-specific import

**Assessment:** Class 3 — multiple similar endpoints for what could be one endpoint with a content-type discriminator. The three separate endpoints exist because the import logic differs per format. This is acceptable but should be tested to ensure all three call the same downstream processing and produce consistent output.

**Risk:** If the XLSM parser and the CSV parser produce different field mappings for the same curriculum item, data quality will vary by import method.

---

## Summary: All API duplications

| ID | Pair | Class | Risk | Action |
|---|---|---|---|---|
| AD-01 | Session create: training.py vs planning.py | 1 | LOW | Verify same permission helper |
| AD-02 | Training areas: training.py vs planning.py | 1 | LOW | None |
| AD-03 | Facilitators read: training.py vs planning.py | 1 | LOW | Verify leave visibility across both |
| AD-04 | ParadeDate vs ParadeNight | 3 | MEDIUM | Verify cascade on ParadeDate delete |
| AD-05 | Night builder: training.py vs planning.py | 1 | LOW | None |
| AD-06 | Session archive (PW) vs cancel/close (Main TMS) | 3 | LOW | Document conceptual distinction |
| AD-07 | Notices: Main TMS can create but not manage | 1 | LOW | Note functional gap |
| AD-08 | CEA import: two paths | 1 | LOW | Verify same target table |
| AD-09 | Proxy state: /api/proxy/current vs /api/auth/me | 3 | LOW | Keep response shapes consistent |
| AD-10 | Curriculum import: 3 format-specific endpoints | 3 | LOW | Verify consistent field mapping |

**No critical API duplication issues found.** The duplications are principally intentional parallel paths between the two frontend contexts. The medium-risk item (AD-04, ParadeDate cascade) deserves verification.

