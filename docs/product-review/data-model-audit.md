# AAFC TMS — Data Model Audit

**Review:** Post-Gap Human Workflow, Architecture and Design Review — Stage 2 (Superpowers)  
**Date:** 2026-08-16  
**Scope:** Domain model integrity, naming consistency, entity relationships, conceptual alignment with user language  
**Method:** Analysis only — no changes

---

## 1. Domain model map

The AAFC TMS domain model spans two conceptual layers:

```
PLANNING LAYER (future-tense, managed in PW)
─────────────────────────────────────────────────────────────────────
PlanningYear
  ├── ParadeDate             (one per parade)
  │    ├── Sessions          (planned sessions for this date)
  │    ├── PlanningNotice    (announcements / instructions)
  │    └── AnchorPrepPlan    (prep activities for anchors)
  ├── HolidayPeriod          (school holidays, stand-downs)
  ├── AnchorEvent            (major events: camps, competitions)
  │    └── AnchorPrepRule    (preparation rules for anchors)
  ├── PlanningFacilitatorLeave  (facilitator unavailability by date)
  ├── PlanningNotice         (year-level notices)
  ├── PlanningConflict       (detected scheduling conflicts)
  └── CeaActivity            (imported Central Event Authority data)

OPERATIONAL LAYER (present/past-tense, managed in Main TMS)
─────────────────────────────────────────────────────────────────────
ParadeNight                  (← linked to ParadeDate 1:1 at creation)
  ├── Sessions               (operational sessions with outcomes)
  │    ├── SessionStatusHistory  (audit trail of status changes)
  │    └── SessionAudience   (which Training Classes attended)
  └── (Notices are cross-layer: planning notices appear on operational nights)

CURRICULUM LAYER (managed by Wing/National admins)
─────────────────────────────────────────────────────────────────────
CurriculumItem
  ├── CurriculumPhase        (= "Training Stage" in UI)
  └── CurriculumElement      (Drill, Air & Space, Field Skills, etc.)

TRAINING CLASS LAYER (per year, per squadron)
─────────────────────────────────────────────────────────────────────
TrainingClass (linked to PlanningYear + Squadron + CurriculumPhase)
  └── CadetClassMembership   (Cadet ↔ TrainingClass link)

OPERATIONAL SUPPORT
─────────────────────────────────────────────────────────────────────
Facilitator                  (training staff)
  └── FacilitatorLeave       (= PlanningFacilitatorLeave — same entity)
TrainingArea                 (= "Room" in user language)
Equipment
Activity                     (AAFC events/activities)
AuditLog                     (immutable action log)
```

**Bridge entity:** `Session` exists in both layers. It is created in the planning context (PW) OR the operational context (Main TMS). The same `sessions` table record is used for both forward planning (what is planned) and outcome recording (what happened). The `status` field + `SessionStatusHistory` captures the lifecycle.

---

## 2. Naming inconsistencies

### DM-01: CurriculumPhase vs Training Stage

| | Code name | UI label |
|---|---|---|
| **Model** | `CurriculumPhase` | Training Stage |
| **Field** | `phase_id` | "Stage" |
| **API** | `/api/curriculum/phases` | — |
| **User language** | Never uses "Phase" | Always says "Training Stage" or "Stage" |

**Issue:** The domain model and API use "Phase" but the UI and user language use "Stage." This creates a cognitive gap for any developer reading the API documentation and then looking at the UI — they must mentally translate "Phase" → "Stage."

**AAFC context:** AAFC training uses "stages" (Orientation, Initial, Junior, Intermediate, Senior, Bronze CLP, Silver CLP, Gold CLP). "Phase" is not an AAFC term. "Phase" may have been a neutral placeholder during development before the domain terminology was confirmed.

**Risk:** If a developer adds a new field referencing `CurriculumPhase` and uses the word "phase" in a user-visible label, it will be inconsistent. Training Officers won't know what "phase" means.

**Recommendation (for approval):** Rename `CurriculumPhase` → `TrainingStage` in the code; update API endpoints from `/curriculum/phases` to `/curriculum/stages`. Frontend already uses "Stage" — this aligns the code with the UI and the AAFC domain.

---

### DM-02: ParadeDate vs ParadeNight — same event, two entities

| | Planning entity | Operational entity |
|---|---|---|
| **Name** | `ParadeDate` | `ParadeNight` |
| **User language** | Never used directly | "Parade Night" (user-facing) |
| **Purpose** | Forward planning container | Outcome recording container |
| **Linked** | Yes — 1:1 auto-link at creation | Yes — same real-world event |
| **Can diverge?** | If PW date is deleted but night still has historical sessions | Yes |

**Issue:** A Training Officer thinks of a "parade night" as a single thing. The system has two entities for it: a `ParadeDate` (what is planned for this night) and a `ParadeNight` (what happened this night). This is a deliberate architectural separation (planning vs operational), but it means a user action in one layer (deleting a parade date in PW) may have implications for the other layer (orphaned parade night in Main TMS).

**Risk:** The 1:1 link may not be enforced at the database level. If a `ParadeDate` is deleted with cascade to sessions but the linked `ParadeNight` is not deleted, the operational night becomes an orphan — visible in Main TMS with sessions but no planning context.

**Recommendation:** Verify that the `ParadeDate` delete endpoint validates or cascades the linked `ParadeNight` state. If not, add a check.

---

### DM-03: TrainingArea vs Room

| | Code name | User language |
|---|---|---|
| **Model** | `TrainingArea` | Room (what users say) |
| **API** | `/api/training-areas` | — |
| **PW API** | `/api/planning/locations` | Rooms |
| **UI label** | "Rooms / Training Areas" | "Room" |

**Issue:** Three different names for the same concept: `TrainingArea` (code), "locations" (PW API), "Rooms" (user language). This inconsistency makes the codebase harder to read and the user experience subtly confusing.

**AAFC context:** AAFC units use "training areas" officially, but colloquially call them "rooms." The UI currently says "Rooms / Training Areas" as a hybrid. The PW API says "locations" which is the most generic and least informative.

**Recommendation (for approval):** Standardise on "Room" in user-visible labels; keep "TrainingArea" in the code if preferred (it's the official AAFC term); rename the PW API from `/api/planning/locations` to `/api/planning/rooms` for consistency with training.py's `/api/training-areas`.

---

### DM-04: FacilitatorLeave vs PlanningFacilitatorLeave

From the domain model in the PW research:
- `PlanningFacilitatorLeave` is listed as a domain entity
- The API calls it `FacilitatorLeave` (at `/api/planning/facilitators/{id}/leave`)

**Issue:** Minor naming inconsistency between model name and API path. Low impact — internal only.

---

### DM-05: Mission Backlog — not a model, a computed view

"Mission Backlog" as shown in the UI is not a database entity — it is a computed view of curriculum items that have been assigned to a planning year but not yet scheduled in sessions.

**Issue:** This is fine architecturally. However, the user thinks of "Mission Backlog" as a first-class thing they manage. The fact that it is a derived view (not a stored entity) has implications:
- There is no "Mission Backlog ID" — each item is a curriculum-item-in-a-year record
- Filtering and sorting are done at query time
- If the underlying curriculum items or sessions change, the backlog automatically updates

**Positive assessment:** This is the correct pattern — the backlog is always live and accurate. It does not require a separate reconciliation step.

---

### DM-06: Session status lifecycle

The `Session` entity has a rich status lifecycle:

```
draft → planned → published → delivered
                           → not_delivered
                           → cancelled
                (from any state) → rescheduled
```

Plus `SessionStatusHistory` records every transition with: old status, new status, reason, who changed it, timestamp.

**Assessment:** This is a strong operational pattern. The concern is the interaction between:
- PW archive (`DELETE /api/planning/sessions/{id}`) — removes the session from planning view
- Main TMS cancel (`POST /api/sessions/{sid}/status` with `cancelled`) — records a historical cancellation

These are semantically different:
- Archive = "this session was never going to happen; remove from plan"
- Cancel = "this session was planned but did not happen; record why"

A session can be "archived in PW" and still appear as "cancelled" in Main TMS (because cancel is a status, not a deletion). The archive may or may not be visible in Main TMS depending on whether archived sessions are filtered out of the parade night view.

**Risk:** A Training Officer might cancel a session in Main TMS and still see it in PW as planned (because cancel is a Main TMS status update, not a PW archive). The two systems may show different views of the same night.

**Verification needed:** When a session is cancelled in Main TMS, does it disappear from the PW calendar view? Or does it appear with a cancellation badge?

---

## 3. Entity relationship integrity concerns

### DM-07: TrainingClass must belong to a PlanningYear

`TrainingClass` is linked to:
- `PlanningYear` (which year is this class for?)
- `Squadron` (which unit?)
- `CurriculumPhase`/`TrainingStage` (what stage are they at?)

**Assessment:** This is the correct model. Classes are year-specific (a "Junior 1 2025" class is not the same as "Junior 1 2026"). However:

**Risk:** When a new `PlanningYear` is created, existing classes are not automatically carried over. The year rollover endpoint (`POST /api/planning/years/{year_id}/rollover`) presumably handles this. Verify that the rollover also carries over classes and their curriculum assignments, not just parade dates.

---

### DM-08: CadetClassMembership — temporal model

`CadetClassMembership` has start/end dates. This allows a cadet to be in:
- Multiple classes simultaneously (e.g., Junior 1 and Specialist class)
- Different classes at different times during the year

**Assessment:** This is correct and handles real AAFC training scenarios. However:

**UI gap:** The user-facing UI shows class membership as a simple list without surfacing the temporal dimension clearly. A Training Officer may not know they can have overlapping memberships or change a cadet's class mid-year without affecting historical records.

---

### DM-09: Activity — scope inheritance model

`Activity` can be scoped at:
- `national` — visible to all
- `wing` — visible to all squadrons in that wing
- `squadron` — visible only to that squadron

Activities inherit downward: a national activity appears in wing and squadron views. A squadron can apply a "local override" to a national or wing activity.

**Assessment:** This is a well-designed multi-tenancy scope model. The `local-override` mechanism is the correct way to let a squadron customise a nationally-seeded activity without modifying the original.

**Risk:** If a squadron overrides a national activity and the national activity is then modified by national_admin, what happens to the override? The override fields take precedence, but the national fields that were not overridden would still update. This is correct but may surprise users.

---

### DM-10: AnchorEvent vs Activity — two event concepts

| | AnchorEvent | Activity |
|---|---|---|
| **Purpose** | Key dates that anchor planning (Annual camp, Pass-Out) | AAFC events the unit attends or runs |
| **Location** | PW layer | Main TMS + PW bottom drawer |
| **Scope** | Per-year, per-squadron | Scoped (national/wing/squadron) |
| **Managed by** | sqn_admin in PW | sqn_admin / wing_admin / national_admin |
| **Prep rules** | Yes (`AnchorPrepRule`) | No |
| **Conflict detection** | Yes (`PlanningConflict` when parade dates clash with anchors) | No |

**Issue:** An "Annual Camp" is both an Activity (in the AAFC activities sense) and an AnchorEvent (in the planning sense). A Training Officer who manages the camp as an Activity and also as an AnchorEvent is managing the same real-world event in two places.

**Is this a problem?** Partially. The Activity is the external/communications-facing record ("We are attending Annual Camp on 12-15 March"). The AnchorEvent is the internal-planning trigger ("There is a major event that affects preparation — I need to plan training around it and ensure certain preparation sessions happen beforehand"). These are different purposes. But:

- If a Training Officer creates "Annual Camp" as an Activity (visible to all) and separately as an AnchorEvent in PW, there is no link between them
- Changes to the Activity dates do not update the AnchorEvent dates
- Duplication of data entry is required for any event that serves both purposes

**Recommendation (for approval):** Consider allowing an AnchorEvent to be "linked" to an existing Activity rather than requiring separate entry. Or: surface a "Mark this activity as an anchor event" action on the Activities page.

---

## 4. Data integrity concerns

### DM-11: Facilitator record not linked to User account

`Facilitator` and `User` (account) are separate, unlinked entities. A facilitator is a person who delivers training; a user is a person who logs into the system.

**Consequence:** A Staff Cadet who is both an account holder (logs in as sqn_general) and a facilitator (delivers some training) has two separate records. Changes to one do not update the other. The system does not know these are the same person.

**Risk:** If the facilitator is promoted (rank change), the change must be made in both the User account and the Facilitator record. They can drift out of sync.

**Assessment:** This is acceptable for the current scope — the system does not claim to be an HR record. It is worth noting in the user guide.

---

### DM-12: Cadet record not linked to User account

Similarly, `Cadet` and `User` are separate. A cadet who later becomes a staff cadet is a Cadet record for attendance/class tracking and a User record for system access. They are not linked.

**Assessment:** Same as DM-11 — acceptable, worth documenting.

---

### DM-13: `sessions.cadet_group` — free text or enum?

The session creation includes a `cadet_group` field. From the API inventory this is used to classify the audience of a session. The relationship to `TrainingClass` is via `SessionAudience`, not via `cadet_group` directly.

**Question:** Is `cadet_group` a free-text field or a constrained enum? If free-text, different sessions may use different labels for the same group (e.g., "Senior 2", "Sr 2", "Senior Two"), making aggregation unreliable.

**Verification needed:** Check whether `cadet_group` is validated against `TrainingClass` names or is a separate free-text field.

---

## 5. Naming consistency summary

| User-facing term | Code/API term | Status |
|---|---|---|
| Training Stage | CurriculumPhase | ⚠ Inconsistent |
| Room | TrainingArea / location | ⚠ Inconsistent |
| Planning Year | PlanningYear | ✓ |
| Parade Night | ParadeNight (operational) / ParadeDate (planning) | ⚠ Split entity |
| Mission Backlog | Computed view (no model) | ✓ (by design) |
| Training Class | TrainingClass | ✓ |
| Facilitator | Facilitator | ✓ |
| Activity | Activity | ✓ |
| Curriculum Item | CurriculumItem | ✓ |
| Holiday | HolidayPeriod | Minor (acceptable) |
| Session | Session | ✓ |

---

## 6. Summary findings

| ID | Finding | Severity | Type |
|---|---|---|---|
| DM-01 | CurriculumPhase vs Training Stage — code/UI naming mismatch | MEDIUM | Naming |
| DM-02 | ParadeDate vs ParadeNight — cascade risk on delete | MEDIUM | Integrity |
| DM-03 | TrainingArea / location / Room — three names for one concept | MEDIUM | Naming |
| DM-04 | FacilitatorLeave naming minor inconsistency | LOW | Naming |
| DM-05 | Mission Backlog is computed view — positive design | N/A (strength) | — |
| DM-06 | Session archive (PW) vs cancel (Main TMS) — divergent visibility risk | MEDIUM | Integrity |
| DM-07 | Year rollover — verify class carryover | MEDIUM | Integrity |
| DM-08 | CadetClassMembership temporal model underexplained in UI | LOW | UX gap |
| DM-09 | Activity scope inheritance — override + update interaction | LOW | Integrity |
| DM-10 | AnchorEvent vs Activity — same real-world event, two records | LOW | Design |
| DM-11 | Facilitator not linked to User account | LOW | Design |
| DM-12 | Cadet not linked to User account | LOW | Design |
| DM-13 | `sessions.cadet_group` — may be free text | MEDIUM | Data quality |

