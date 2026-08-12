# AAFC TMS — Report Catalogue (Tier 1 and Tier 2)

**Audience:** Squadron Administrators, Wing Administrators, National Administrators
**Gap register:** Gap #10 (incomplete report catalogue)
**Last updated:** 2026-08-12

---

## Tier Classification

| Tier | Scope | Released in |
|---|---|---|
| Tier 1 | Squadron-level reports (sqn_admin, sqn_viewer) | v17.1 — implemented |
| Tier 2 | Wing-level aggregate reports (wing_admin, wing_viewer) | v17.1 — implemented |
| Tier 3 | National roll-up reports (national_admin, national_viewer) | v17.1 — implemented; multi-Wing data pending Level B |

All reports are real-time (no caching layer); data reflects the current DB state at request time.

---

## Tier 1 — Squadron Reports

### T1-01 — Training Summary

| Field | Value |
|---|---|
| **Endpoint** | `GET /api/reports/summary` |
| **Users** | sqn_admin, sqn_viewer, wing_admin (proxy), system_admin |
| **Decision supported** | Are there sessions needing follow-up? |
| **Scope** | All sessions for the authenticated squadron (current training year) |
| **Period** | All-time (not year-filtered) — represents current operational state |
| **Source** | `ScheduledSession.status` |
| **Calculation** | Count sessions by status (delivered, not_delivered, planned, cancelled, etc.) |
| **Output** | Status count breakdown + total + decision signal |
| **Decision signals** | `no_action` (no not_delivered sessions), `monitor` (≥1 not_delivered) |
| **Drill-down** | Not implemented in v17.1 — summary only |
| **Export** | Not implemented |
| **Frontend location** | Dashboard → Training Summary card |
| **Performance target** | < 200ms P95 (synchronous, < 2000 sessions) |

---

### T1-02 — Next Parade Night Readiness

| Field | Value |
|---|---|
| **Endpoint** | `GET /api/reports/readiness` |
| **Users** | sqn_admin, sqn_viewer, wing_admin (proxy), system_admin |
| **Decision supported** | Is the squadron ready for upcoming parade nights? |
| **Scope** | Next 8 upcoming parade nights for the authenticated squadron |
| **Period** | Future only (today and beyond) |
| **Source** | `ParadeNight.date` + `ScheduledSession` records for each night |
| **Calculation** | `parade_night_readiness()` + `score_parade()` per night; lowest score drives decision |
| **Output** | Per-night readiness score (0–100), band, deductions, `planning_status`, `data_quality` |
| **Decision signals** | `no_action` (≥85), `action_required` (50–84), `command_decision_required` (<50) |
| **Drill-down** | Navigate to that parade night via `/activities` |
| **Export** | Not implemented |
| **Frontend location** | Dashboard → Readiness card |
| **Performance target** | < 300ms P95 (8 nights × per-session query) |

---

### T1-03 — Curriculum Coverage

| Field | Value |
|---|---|
| **Endpoint** | `GET /api/reports/curriculum-coverage` |
| **Users** | sqn_admin, sqn_viewer, wing_admin (proxy), system_admin |
| **Decision supported** | Which curriculum items have not been scheduled? Which have been delivered? |
| **Scope** | All National + squadron-scoped curriculum items vs. all sessions for the squadron |
| **Period** | All-time |
| **Source** | `CurriculumItem` + `ScheduledSession.curriculum_item_id` + `session.status` |
| **Calculation** | % of curriculum items that appear in ≥1 session (scheduled); separately % delivered |
| **Output** | `total`, `scheduled`, `delivered`, `coverage_pct`, list of unscheduled items |
| **Decision signals** | `no_action` (100%), `action_required` (70–99%), `command_decision_required` (<70%) |
| **Drill-down** | Not implemented — list of unscheduled item codes and titles included inline |
| **Export** | Not implemented |
| **Frontend location** | Dashboard → Curriculum Coverage card; Reports page → Curriculum Coverage section |
| **Performance target** | < 400ms P95 |

---

### T1-04 — Facilitator Load

| Field | Value |
|---|---|
| **Endpoint** | `GET /api/reports/facilitator-load` |
| **Users** | sqn_admin, sqn_viewer, wing_admin (proxy), system_admin |
| **Decision supported** | Are any facilitators overloaded? Is teaching load evenly distributed? |
| **Scope** | All sessions for the squadron with a facilitator assigned |
| **Period** | All-time |
| **Source** | `ScheduledSession.facilitator_display_name_at_time`, `session.status` |
| **Calculation** | Sessions per facilitator; delivered count; risk = overloaded (>10), high (>6), ok (≤6) |
| **Output** | Sorted facilitator list with session count, delivered count, risk flag |
| **Decision signals** | `action_required` (any overloaded/high), `no_action` (all ok) |
| **Drill-down** | Not implemented |
| **Export** | Not implemented |
| **Frontend location** | Dashboard → Facilitator Load card; Reports page |
| **Performance target** | < 300ms P95 |

---

### T1-05 — Not Delivered Sessions

| Field | Value |
|---|---|
| **Endpoint** | `GET /api/reports/not-delivered` |
| **Users** | sqn_admin, sqn_viewer, wing_admin (proxy), system_admin |
| **Decision supported** | Which sessions were not delivered and why? |
| **Scope** | All sessions for the squadron with `status = not_delivered` |
| **Period** | All-time |
| **Source** | `ScheduledSession.status`, `session.not_delivered_reason`, `curriculum_code_at_time` |
| **Output** | List of not-delivered sessions with curriculum code and reason |
| **Decision signals** | `action_required` (any not delivered), `no_action` (none) |
| **Drill-down** | Not implemented |
| **Export** | Not implemented |
| **Frontend location** | Reports page → Not Delivered section |
| **Performance target** | < 200ms P95 |

---

## Tier 2 — Wing Reports

These reports are scoped to a Wing and require `wing_viewer`, `wing_admin`, `national_viewer`, `national_admin`, or `system_admin` role.

### T2-01 — Wing Squadron Overview

| Field | Value |
|---|---|
| **Endpoint** | `GET /api/reports/wing-overview` |
| **Users** | wing_admin, wing_viewer, national_admin, national_viewer, system_admin |
| **Decision supported** | Which squadrons need Wing attention? What is the Wing's overall health? |
| **Scope** | All non-archived squadrons in the Wing |
| **Source** | `ParadeNight`, `ScheduledSession`, `CurriculumItem`, `parade_night_readiness()` |
| **Output** | Per-squadron: nights, published nights, sessions, delivered count, delivery %, readiness score, coverage %, not-delivered count |
| **Frontend location** | Wing Dashboard → Squadron table |

---

### T2-02 — Wing Phase Coverage Heatmap

| Field | Value |
|---|---|
| **Endpoint** | `GET /api/reports/wing-phase-coverage` |
| **Users** | wing_admin, wing_viewer, national_admin, national_viewer, system_admin |
| **Decision supported** | Which curriculum phases are under-represented across the Wing? |
| **Scope** | All squadrons in the Wing × all curriculum phases |
| **Output** | Phase list (ordered) + per-squadron coverage % per phase |
| **Frontend location** | Wing Dashboard → Phase Coverage heatmap |

---

### T2-03 — Wing Capability

| Field | Value |
|---|---|
| **Endpoint** | `GET /api/reports/wing-capability` |
| **Users** | wing_admin, wing_viewer, national_admin, national_viewer, system_admin |
| **Decision supported** | Does each squadron have facilitators across all 6 subject areas? |
| **Scope** | All squadrons in the Wing |
| **Source** | `Facilitator.subject_areas` mapped to 6 canonical subject keys (service, drill, field, lead, comm, stem) |
| **Output** | Per-squadron capability score, per-subject facilitator counts, upcoming session assignment gaps |
| **Frontend location** | Wing Dashboard → Capability section |

---

### T2-04 — Wing Cancellation Trend

| Field | Value |
|---|---|
| **Endpoint** | `GET /api/reports/wing-cancellation-trend` |
| **Users** | wing_admin, wing_viewer, national_admin, national_viewer, system_admin |
| **Decision supported** | Is the cancellation rate trending up? Which squadrons account for most cancellations? |
| **Scope** | All squadrons in the Wing |
| **Frontend location** | Not yet surfaced in main Wing Dashboard (endpoint exists, not yet wired to a card) |

---

### T2-05 — Wing Not Delivered

| Field | Value |
|---|---|
| **Endpoint** | `GET /api/reports/wing-not-delivered` |
| **Users** | wing_admin, wing_viewer, national_admin, national_viewer, system_admin |
| **Decision supported** | Which Wing squadrons have the most not-delivered sessions? |
| **Frontend location** | Not yet surfaced in main Wing Dashboard (endpoint exists, not yet wired to a card) |

---

## Tier 3 — National Reports

### T3-01 — National Overview

| Field | Value |
|---|---|
| **Endpoint** | `GET /api/reports/national-overview` |
| **Users** | national_admin, national_viewer, system_admin |
| **Decision supported** | What is the cross-Wing training health picture? |
| **Notes** | Multi-Wing data valid only after Level B (synthetic second Wing in staging); currently 7WG data only |

---

### T3-02 — National Capability

| Field | Value |
|---|---|
| **Endpoint** | `GET /api/reports/national-capability` |
| **Users** | national_admin, national_viewer, system_admin |
| **Decision supported** | Which Wings or squadrons lack facilitator coverage in key subject areas? |
| **Notes** | Same multi-Wing data caveat as T3-01 |

---

## Implementation Gaps (Tier 1 priorities)

| Gap | Priority | Notes |
|---|---|---|
| Export (PDF/CSV) for T1-01 through T1-05 | Tier 1 (V1) | Currently display-only; operators need to print/share |
| Date-range filter for T1-01, T1-03, T1-05 | Tier 1 (V1) | "Current year" vs "all-time" toggle |
| T2-04 and T2-05 wired to Wing Dashboard | Tier 2 (Level B) | Endpoints exist; need UI cards |
| Cross-Wing national reports with real multi-Wing data | Tier 3 (Level C) | Requires synthetic second Wing |
| Performance at Wing scale (250+ users) | Tier 2 (Level B) | Covered by 17_multi_wing_load_test_procedure.md |
