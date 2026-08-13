# Dashboard metric dictionary

**Status:** Complete pass — 2026-08-13  
**Source:** `backend/app/routers/dashboard.py` (2526 lines)  
**Standard:** §23 / §97 (dashboard philosophy / information-design review gate)

Every chart must answer: QUESTION / PURPOSE / POPULATION / PERIOD / NUMERATOR / DENOMINATOR / SOURCE / REFRESH / ACTION / DRILL-DOWN / ACCESSIBLE ALTERNATIVE.

---

## Key constants (module-level)

| Constant | Value | Used in |
|---|---|---|
| `_DELIVERED` | `{"delivered", "delivered_with_issue"}` | All delivery-rate calculations |
| `_TERMINAL` | `{"delivered", "delivered_with_issue", "not_delivered", "cancelled", "rescheduled"}` | Reliability denominators |
| `_UNKNOWN_PHASE_LABEL` | `"Missing phase (needs information)"` | Curriculum backlog grouping |
| `_REASON_NOT_RECORDED_LABEL` | `"Reason not recorded (needs information)"` | Cancellation Pareto |
| `_CLASS_BEHIND_THRESHOLD_PP` | `15` | Class-curriculum gap detection |

Date window `_date_window(window)`:
- `"week"` → ±7 days
- `"term"` → last 90 days to next 30 days (default)
- `"semester"` → last 182 days to next 30 days
- `"year"` → Jan 1 – Dec 31, current calendar year

---

## Section A — Squadron Operational Charts (`_full_squadron_charts`)

Pre-fetch strategy: two session sets are built by the caller.
- **Window set** (`sessions`/`pns`): date-filtered by the selected window. Used for: weekly outcomes, session outcomes, cancellation reasons, facilitator workload.
- **All-time set** (`all_sessions`/`all_pns`): no date filter. Used for: delivery trend, curriculum progress, element progress, class progress, curriculum backlog, facilitator workload gap detection, facilitator capability dependency.

---

### A1. Weekly Outcomes (`weekly_outcomes`)

| Field | Value |
|---|---|
| **Question** | How many sessions were delivered, cancelled, or missed each week? |
| **Purpose** | Show the week-by-week pattern of session outcomes so a Training Officer can see at a glance whether disruptions are isolated or recurring. |
| **Population** | All sessions in the window set whose parade night ID is in the known PN list. |
| **Period** | The selected window (default: term — last 90 days to next 30 days), grouped by ISO calendar week. |
| **Numerator** | Count of sessions in each status per week. |
| **Denominator** | None — raw counts, not a rate. |
| **Formula** | `status or "planned"` normalises null; sessions with an unknown PN are skipped. Status values bucketed: delivered, delivered_with_issue, not_delivered, cancelled, rescheduled, planned. |
| **Source tables** | `Session`, `ParadeNight` (pre-fetched). |
| **Refresh** | Per request, no cache. |
| **Insight trigger** | `sum(delivered + delivered_with_issue across all weeks)` reported as total. |
| **User action** | Drill into parade nights filtered by week. |
| **Drill-down** | Route: `parade-nights`. |
| **Accessible alternative** | Data table (every series value per ISO week). |
| **Chart type** | `stacked_bar` |
| **Known issues** | `rescheduled` and `delivered_with_issue` are named buckets but not yet colour-coded distinctively in the frontend — they are currently shown in the same stacked bar without visual differentiation from `planned`/`delivered`. |

---

### A2. Delivery Trend (`delivery_trend`)

| Field | Value |
|---|---|
| **Question** | Is training delivery getting more or less reliable over the past 12 weeks? |
| **Purpose** | Surface a trend line so command can assess whether corrective action is working, or a problem is worsening. |
| **Population** | All terminal-status sessions from the all-time set. Future PNs (date > today) are excluded. |
| **Period** | Rolling last 12 ISO calendar weeks from today. |
| **Numerator** | Count of sessions with status in `_DELIVERED` per week. |
| **Denominator** | Count of sessions with status in `_TERMINAL` per week. |
| **Formula** | `reliability_pct = round(numerator / denominator * 100)` if denominator > 0, else `None`. A week with no terminal sessions returns `reliability_pct: None` (not 0) — the point is omitted from the trend line rather than dragging the average down. |
| **Trend insight** | Requires ≥4 valid (non-None) weeks. Compares last-4 vs first-4 average. Improving if gap > +5 pp; declining if gap < −5 pp. |
| **Source tables** | `Session`, `ParadeNight` (pre-fetched; uses all-time set). |
| **Refresh** | Per request. |
| **Thresholds** | Green ≥ 80%, Amber ≥ 60%, Red < 60%. |
| **User action** | Review weeks below threshold; investigate cancelled/not-delivered causes. |
| **Drill-down** | Route: `parade-nights`. |
| **Accessible alternative** | Data table: week, reliability %, delivered count, terminal count. |
| **Chart type** | `line` |

---

### A3. Curriculum Backlog (`curriculum_backlog`)

| Field | Value |
|---|---|
| **Question** | Which training areas have the most missed sessions that still need to be made up? |
| **Purpose** | Rank overdue curriculum areas so a Training Officer can prioritise which subjects to reschedule first. |
| **Population** | Sessions on past PNs (date < today) with status `not_delivered`, `cancelled`, or `rescheduled`. Uses all-time session set. |
| **Period** | All-time — cumulative missed sessions on any past PN. |
| **Numerator** | Count of missed sessions per phase. |
| **Denominator** | None — raw counts ranked. |
| **Formula** | Phase label from `s.phase_at_time or _UNKNOWN_PHASE_LABEL`. The `_UNKNOWN_PHASE_LABEL` bucket gets its own colour (`#8a93a6`) and `data_quality_gap: true`; real phases get `#e51937`. |
| **Source tables** | `Session`, `ParadeNight` (pre-fetched). |
| **Refresh** | Per request. |
| **Insight trigger** | Largest real-phase bucket name and count. "Unknown" phase group is excluded from the insight headline but shown in the chart. |
| **User action** | Click a phase bar to see which specific sessions were missed. |
| **Drill-down** | Route: `parade-nights`, filter: `status: not_delivered`. |
| **Accessible alternative** | Table sorted by count descending. |
| **Chart type** | `bar_horizontal` |
| **Data quality flag** | The `_UNKNOWN_PHASE_LABEL` bucket is shown with a distinct colour and labelled as a data quality gap. Operators should assign phases to unlabelled sessions. |

---

### A4. Curriculum Progress by Phase (`_curriculum_progress`)

| Field | Value |
|---|---|
| **Question** | How much of each Training Stage's curriculum has been delivered so far this year? |
| **Purpose** | Show stage-level curriculum coverage so the Training Officer can see which stages are on track and which are behind. |
| **Population** | All curriculum items applicable to this squadron (governed `CurriculumPhase` catalogue); all sessions linked to those items (all-time set). |
| **Period** | Cumulative. No date window — all sessions ever recorded. |
| **Numerator** | Count of curriculum items with a session in `_DELIVERED` status. |
| **Denominator** | Count of applicable curriculum items per phase. |
| **Formula** | `delivered / applicable * 100` per phase. `_phases_for_squadron()` uses the governed `CurriculumPhase` catalogue; falls back to `_PHASES` constant if empty. |
| **Known limitation** | CLASS-04 (addendum §53/§54): this is computed per Training Stage, not per Training Class. A squadron with 5 Senior classes gets one blended Senior percentage. Tracked as CLASS-08 (class-aware curriculum progress, now CLOSED as a backend endpoint; frontend rendering is CLASS-12/CLASS-13, both CLOSED). |
| **Source tables** | `CurriculumItem`, `Session`, `CurriculumPhase` (pre-fetched by `_full_squadron_charts`). |
| **Refresh** | Per request. |
| **User action** | See which stages are behind; drill to activities for that stage. |
| **Drill-down** | Route: `activities`. |
| **Accessible alternative** | Table: stage name, delivered count, applicable count, percentage. |
| **Chart type** | `stacked_bar_horizontal` |

---

### A5. Element Curriculum Progress (`_element_curriculum_progress`)

| Field | Value |
|---|---|
| **Question** | Across each curriculum element (subject area), how many sessions have been delivered vs. planned? |
| **Purpose** | Provide a cross-stage view by subject area (e.g. "Leadership", "Flying") so areas consistently being skipped are visible regardless of stage. |
| **Population** | All sessions and curriculum items whose `element` matches a governed `CurriculumElement` entry. |
| **Period** | Cumulative (all-time session set). |
| **Numerator** | Count of sessions per outcome status per element. |
| **Denominator** | Count of applicable curriculum items per element (`total_items`). |
| **Formula** | Raw stacked counts — not a percentage. `rescheduled` and other non-enumerated statuses fall through to the `planned` bucket. |
| **Empty catalogue** | If the governed element catalogue is empty, returns `data: []` with no fallback. |
| **Source tables** | `Session`, `CurriculumItem`, `CurriculumElement` (via `_elements_for_squadron()`; pre-fetched). |
| **Refresh** | Per request. |
| **User action** | Drill to activities filtered by element. |
| **Drill-down** | Route: `activities`, filter: `element`. |
| **Accessible alternative** | Table: element name, delivered, not_delivered, cancelled, planned, total items. |
| **Chart type** | `stacked_bar_horizontal` |

---

### A6. Training Class Curriculum Progress (`_class_curriculum_progress_summary`)

| Field | Value |
|---|---|
| **Question** | Which Training Classes are significantly behind their stage average? |
| **Purpose** | Surface individual class outliers that would be hidden in a blended stage average — the addendum §54 "never average class percentages" requirement. |
| **Population** | All non-archived Training Classes for the squadron, grouped by Training Stage. |
| **Period** | Cumulative. Uses `_class_curriculum_progress(db, c)` from `training.py` which reads all-time session/curriculum records. |
| **Stage-level numerator** | `sum(delivered)` across all classes in the stage. |
| **Stage-level denominator** | `sum(applicable)` across all classes in the stage. |
| **Formula** | `coverage_pct = round(100 * total_delivered / total_applicable)` if `total_applicable > 0`, else `None`. Per-class: same formula for that class's own delivered/applicable counts. |
| **Behind-class threshold** | `_CLASS_BEHIND_THRESHOLD_PP = 15`. A class is behind if `class_pct ≤ stage_pct − 15 pp` and both are not None. |
| **Source tables** | `TrainingClass` (queried directly); `Session`, `CurriculumItem` (via delegate `_class_curriculum_progress()`). |
| **Refresh** | Per request. |
| **Insight trigger** | Names of behind classes, with their percentage and the stage average. |
| **User action** | Click a stage bar to see all classes for that stage; click a class to open its curriculum detail. |
| **Drill-down** | Route: `training-classes`, filter: `stage_id`. |
| **Accessible alternative** | Table: stage name, class name, delivered, applicable, coverage %. |
| **Chart type** | `bar_with_drilldown` |

---

### A7. Session Outcomes Distribution (`_session_outcomes_distribution`)

| Field | Value |
|---|---|
| **Question** | What proportion of sessions in this period were delivered, cancelled, or missed? |
| **Purpose** | Give an at-a-glance summary of overall session health for the selected window. |
| **Population** | All sessions in the window set. |
| **Period** | Selected window (default: term). |
| **Numerator** | Count of sessions in each status. |
| **Denominator** | `total = sum(all status counts)`. |
| **Formula** | `pct = round(count / total * 100)` per status. Delivery pct = `(delivered + delivered_with_issue) / total * 100`. Zero-division guard: `if total else 0`. |
| **Thresholds** | ≥ 80% delivery: strong; ≥ 60%: some disruption; < 60%: review causes. |
| **Source tables** | `Session` (window-filtered pre-fetch). |
| **Refresh** | Per request. |
| **User action** | Drill into parade nights to see which sessions were not delivered. |
| **Drill-down** | Route: `parade-nights`. |
| **Accessible alternative** | Table: status, count, percentage. |
| **Chart type** | `donut` |

---

### A8. Cancellation / Non-Delivery Pareto (`_cancellation_pareto`)

| Field | Value |
|---|---|
| **Question** | What are the most common reasons training sessions were not delivered? |
| **Purpose** | Identify systemic causes (e.g. "No facilitator", "Activity conflict") so they can be addressed rather than just recorded. Pareto format (§28.6 requirement) puts the biggest problem first. |
| **Population** | All sessions with status `not_delivered` or `cancelled`. Uses window-filtered session set. |
| **Period** | Selected window. |
| **Numerator** | Count of sessions per cancellation reason. |
| **Denominator** | None — ranked count. |
| **Formula** | Reason from `s.cancellation_reason or _REASON_NOT_RECORDED_LABEL`. `_REASON_NOT_RECORDED_LABEL` gets its own colour and `data_quality_gap: True`. Sorted descending by count. |
| **Source tables** | `Session` (window-filtered pre-fetch). |
| **Refresh** | Per request. |
| **Insight trigger** | Largest reason-bucket name and count. "Unknown" reason is excluded from the headline. |
| **User action** | Identify the most common cause and implement a specific mitigation. |
| **Drill-down** | Route: `parade-nights`. |
| **Accessible alternative** | Table: reason, count. |
| **Chart type** | `bar_horizontal` (Pareto-ordered) |
| **Data quality flag** | `_REASON_NOT_RECORDED_LABEL` sessions are shown distinctly. Operators should record specific reasons. |

---

### A9. Facilitator Workload (`_facilitator_workload`)

| Field | Value |
|---|---|
| **Question** | How are sessions distributed across facilitators this period? Is any one person over-burdened? |
| **Purpose** | Surface concentration risk — when one person carries most of the load, the squadron is fragile. |
| **Population** | Sessions in the window set with a facilitator assigned (by `facilitator_id` or `facilitator_display_name_at_time`). |
| **Period** | Selected window. |
| **Numerator** | Count of sessions per facilitator per outcome status. |
| **Denominator** | None — raw counts. |
| **Formula** | Groups by `facilitator_id or display_name`. Status buckets: delivered, planned, not_delivered, cancelled. `rescheduled` and `delivered_with_issue` increment `total` but not a named bucket. Null status normalised to `"planned"`. |
| **Truncation** | Top 15 facilitators by `total`. |
| **Over-reliance insight** | If top facilitator's total / sum(all totals) > 40%: named warning. Requires ≥ 2 facilitators. |
| **Source tables** | `Session` (window-filtered pre-fetch). |
| **Refresh** | Per request. |
| **User action** | Identify overburdened facilitators and redistribute. |
| **Drill-down** | Route: `parade-nights`. |
| **Accessible alternative** | Table: facilitator name, delivered, planned, not_delivered, cancelled, total. |
| **Chart type** | `bar_horizontal` |

---

### A10. Facilitator Status Distribution (`_facilitator_status_distribution`)

| Field | Value |
|---|---|
| **Question** | How many facilitators are available, on leave, or unavailable right now? |
| **Purpose** | Immediate point-in-time headcount before a parade night or planning period. |
| **Population** | All facilitators in the squadron's list. |
| **Period** | Point-in-time as of today. Leave is active if `start_date ≤ today ≤ end_date`. |
| **Numerator** | Count of facilitators in each of three mutually exclusive states. |
| **Denominator** | Total facilitators. |
| **Formula** | Classification order: inactive (`not active_status`) → on leave → available. Mutually exclusive. Over-25% on-leave warning: `on_leave / total > 0.25`. |
| **Source tables** | `Facilitator`, `PlanningFacilitatorLeave` (pre-fetched). |
| **Refresh** | Per request. |
| **User action** | If too many on leave, arrange substitutes before the next night. |
| **Drill-down** | Route: `facilitators`. |
| **Accessible alternative** | Table: status label, count. |
| **Chart type** | `donut` |

---

### A11. Unstaffed Subject Areas — Facilitator Repeated Gaps (`_facilitator_repeated_gaps`)

| Field | Value |
|---|---|
| **Question** | Which subject areas have had the most unstaffed sessions in the past 8 weeks? |
| **Purpose** | Identify which curriculum subjects consistently cannot find a facilitator — signalling a chronic capability gap, not just a one-off conflict. |
| **Population** | Sessions with null `facilitator_id` and status in `("planned", "not_delivered")`, on PNs within the past 8 weeks. |
| **Period** | Rolling last 8 calendar weeks from today. |
| **Numerator** | Count of unstaffed sessions per subject label. |
| **Denominator** | None — ranked count. |
| **Label** | `element_at_time or curriculum_title_at_time or "Unclassified"`. |
| **Truncation** | Top 10 labels by count. |
| **Source tables** | `Session`, `ParadeNight` (pre-fetched; caller computes `pn_date_by_id` dict). |
| **Refresh** | Per request. |
| **User action** | Recruit a facilitator for the flagged subject area, or arrange a substitute. |
| **Drill-down** | Route: `parade-nights`, filter: `status: unstaffed`. |
| **Accessible alternative** | Table: subject area, unstaffed session count. |
| **Chart type** | `bar_horizontal` |

---

### A12. Facilitator Leave Impact (`_facilitator_leave_impact`)

| Field | Value |
|---|---|
| **Question** | Which facilitators have planned sessions that fall during their recorded leave? |
| **Purpose** | Give advance warning so substitutes can be arranged before the conflict hits. |
| **Population** | Facilitators with future leave (`end_date ≥ today`); planned sessions (`status = "planned"`) assigned to those facilitators, whose PN date falls within the leave period. |
| **Period** | Future only — from today forward. |
| **Numerator** | Count of planned sessions per facilitator during their upcoming leave. |
| **Denominator** | None. Only facilitators with count > 0 are shown. |
| **Name format** | `"{rank} {first_name} {last_name}"` — rank omitted if null. |
| **Truncation** | Top 15 by count. |
| **Source tables** | `Facilitator`, `PlanningFacilitatorLeave`, `ParadeNight`, `Session` (all pre-fetched). |
| **Refresh** | Per request. |
| **Insight trigger** | Highest-impact facilitator name and count, with action: "arrange a substitute." |
| **User action** | Arrange a substitute for the affected sessions. |
| **Drill-down** | Route: `facilitator-schedule`. |
| **Accessible alternative** | Table: facilitator name, sessions during leave. |
| **Chart type** | `bar_horizontal` |

---

### A13. Facilitator Capability Dependency (`_facilitator_capability_dependency`)

| Field | Value |
|---|---|
| **Question** | What percentage of all delivered sessions are attributable to the top few facilitators? |
| **Purpose** | Measure delivery concentration risk — if the top 3 facilitators carry >60% of delivery, the squadron is fragile. |
| **Population** | All delivered sessions (all-time) with a facilitator assigned. |
| **Period** | All-time cumulative. |
| **Numerator** | Count of delivered sessions per facilitator. |
| **Denominator** | Total delivered sessions across all facilitators. |
| **Formula** | `pct = round(count / total * 100)`. Cumulative percentage shown for each facilitator (Pareto-style). Top 10. |
| **Insight trigger** | If `sum(pct for top 3) > 60%`: over-reliance warning naming those three. |
| **Source tables** | `Session` (all-time pre-fetch). |
| **Refresh** | Per request. |
| **User action** | Build facilitator depth by training more in the flagged subject areas. |
| **Drill-down** | Route: `facilitators`. |
| **Accessible alternative** | Table: facilitator name, sessions delivered, % of total, cumulative %. |
| **Chart type** | `bar_horizontal` |

---

### A14. Subject Area Resilience (`_subject_area_resilience`)

| Field | Value |
|---|---|
| **Question** | For each curriculum subject area, how many active facilitators are qualified? |
| **Purpose** | Show which subject areas have single-point-of-failure risk (1 facilitator) or no coverage at all (0 facilitators). |
| **Population** | All active facilitators for the squadron. |
| **Period** | Point-in-time. |
| **Numerator** | Count of active facilitators with the subject area in their `subject_areas` list. |
| **Denominator** | None. |
| **Risk classification** | `critical` if count = 0; `warn` if count = 1; `ok` if count ≥ 2. |
| **Sort order** | Ascending by count (most critical first in horizontal bar). |
| **Insight** | Reports count of critical and warn subject areas. Critical (0 facilitators) takes headline priority. |
| **Source tables** | `Facilitator` (pre-fetched). |
| **Refresh** | Per request. |
| **User action** | Recruit or cross-train facilitators for critical/warn subject areas. |
| **Drill-down** | Route: `facilitators`. |
| **Accessible alternative** | Table: subject area, qualified facilitator count, risk level, facilitator names. |
| **Chart type** | `bar_horizontal` |

---

### A15. Facilitator Type Distribution (`_facilitator_type_distribution`)

| Field | Value |
|---|---|
| **Question** | What is the breakdown of facilitator types in the squadron? |
| **Purpose** | Show whether the facilitator pool is balanced across types (e.g. Officer, Civilian Instructor, Senior Cadet) or skewed toward one category. |
| **Population** | All active facilitators. |
| **Period** | Point-in-time. |
| **Numerator** | Count of active facilitators per `type` value (or `"Unspecified"` if null). |
| **Denominator** | None — raw counts. |
| **Insight** | None generated. |
| **Source tables** | `Facilitator` (pre-fetched). |
| **Refresh** | Per request. |
| **User action** | Identify type imbalances; recruit accordingly. |
| **Drill-down** | Route: `facilitators`. |
| **Accessible alternative** | Table: type, count. |
| **Chart type** | `bar_horizontal` |

---

### A16. Long-Term Delivery Trend (`_long_term_delivery_trend`)

| Field | Value |
|---|---|
| **Question** | What has delivery reliability looked like across the past 4 terms? |
| **Purpose** | Provide a multi-term strategic view beyond the 12-week tactical trend — is the squadron improving year-on-year? |
| **Population** | All terminal-status sessions across all-time records, grouped by `pn.term` string value. |
| **Period** | All-time, bucketed by term label (`pn.term`). Output sliced to the last `terms × 3` (default 12) term-buckets after alphabetical sort. |
| **Numerator** | Count of delivered sessions per term bucket. |
| **Denominator** | Count of terminal sessions per term bucket. |
| **Formula** | `reliability_pct = round(delivered / total * 100)` if total > 0, else `None`. |
| **Insight** | None generated. |
| **Source tables** | `Session`, `ParadeNight` (all-time pre-fetch). |
| **Refresh** | Per request. |
| **Known limitation** | PNs with `pn.term = null` are bucketed under `"Unknown"`. |
| **Drill-down** | Route: `parade-nights`. |
| **Accessible alternative** | Table: term label, reliability %, delivered count, terminal count. |
| **Chart type** | `line` |
| **Thresholds** | Green ≥ 80%, Amber ≥ 60%, Red < 60% (same as A2). |

---

## Section B — Wing Comparison Charts (`_wing_comparison_charts`)

---

### B1. Squadron Readiness (`_squadron_readiness`)

| Field | Value |
|---|---|
| **Question** | How does delivery reliability compare across squadrons in this Wing this period? |
| **Purpose** | Enable Wing Admin to see which squadrons need support, ranked objectively rather than by self-report. |
| **Population** | All non-archived squadrons in the wing; their sessions on PNs within the selected window. |
| **Period** | Parameterised window (default: term). |
| **Numerator** | Count of delivered sessions (`_DELIVERED`) per squadron. |
| **Denominator** | Count of terminal sessions (`_TERMINAL`) per squadron. |
| **Formula** | `readiness_pct = round(delivered / total * 100)` if total > 0, else `0`. Squadrons with no PNs in window get `readiness_pct: 0, total: 0`. |
| **Spread insight** | If best − worst > 20 pp: reports the best and worst squadron labels and their percentages. |
| **Source tables** | `Squadron`, `ParadeNight`, `Session` (queried directly). |
| **Refresh** | Per request. |
| **User action** | Offer support or oversight to lowest-ranking squadron. |
| **Drill-down** | Route: `parade-nights`, filter: `squadron_id`. |
| **Accessible alternative** | Table: squadron code, name, reliability %, delivered, terminal. |
| **Chart type** | `bar_horizontal` |

---

### B2. Squadron Delivery Comparison (`_squadron_delivery_comparison`)

| Field | Value |
|---|---|
| **Question** | What is the raw session count by outcome for each squadron this period? |
| **Purpose** | Complement B1 (percentage view) with raw counts — a small squadron at 100% reliability may still have few sessions; B2 shows absolute scale. |
| **Population** | Same as B1. |
| **Period** | Parameterised window. |
| **Numerator** | Raw counts: delivered, not_delivered, cancelled, planned per squadron. |
| **Denominator** | None — raw counts. |
| **Formula** | Uses `_DELIVERED = {"delivered", "delivered_with_issue"}` consistently with B1. |
| **Source tables** | `Squadron`, `ParadeNight`, `Session` (queried directly). |
| **Refresh** | Per request. |
| **User action** | Compare absolute session volumes alongside reliability rates. |
| **Drill-down** | Route: `parade-nights`. |
| **Accessible alternative** | Table: squadron code, name, delivered, not_delivered, cancelled, planned. |
| **Chart type** | `grouped_bar` |

---

### B3. Wing Subject Area Gaps (`_wing_subject_area_gaps`)

| Field | Value |
|---|---|
| **Question** | For each squadron × subject area combination in the Wing, is there adequate facilitator coverage? |
| **Purpose** | Show the Wing Admin where subject-area coverage gaps exist across squadrons, so wing-level facilitator support can be targeted. |
| **Population** | All active facilitators in the wing, segmented by squadron. |
| **Period** | Point-in-time. |
| **Numerator** | Count of active facilitators per squadron per subject area. |
| **Denominator** | None — threshold classification. |
| **Risk classification** | `critical` if count = 0; `warn` if count = 1 or 2; `ok` if count ≥ 3. |
| **Source tables** | `Squadron`, `Facilitator` (queried directly by wing_id and squadron_id). |
| **Refresh** | Per request. |
| **Insight trigger** | Count of critical cells (0 facilitators). |
| **User action** | Deploy wing-level facilitators to fill critical cells. |
| **Drill-down** | None (heatmap — individual cell = squadron + subject area combination). |
| **Accessible alternative** | Table: squadron, subject area, count, risk level. |
| **Chart type** | `heatmap` |

---

## Section C — Command / National Charts (`get_command_dashboard`)

Command charts are served by a single endpoint and split into two sections: Section A (readiness matrix + risk) and Section B (aggregated outcomes + trend).

---

### C1. Readiness Matrix (`_readiness_matrix`)

| Field | Value |
|---|---|
| **Question** | For each squadron (Wing scope) or Wing (National scope), what is the readiness status of the next upcoming Parade Night — across curriculum, facilitator, and room allocation? |
| **Purpose** | Give command a single at-a-glance table of readiness gaps before the next night, without requiring drill-in to each unit. |
| **Population** | Each child unit's next upcoming PN from today onwards. |
| **Period** | Forward-looking — only the next PN per unit (not a window). |
| **Columns** | sessions_planned, curriculum_allocated, facilitator_confirmed, facility_confirmed, equipment_confirmed (always no_data — not tracked), overall_readiness. |
| **Numerator per column** | Count of sessions meeting that column's requirement. |
| **Denominator per column** | `sessions_total` for that PN. |
| **Formula** | `_matrix_cell(n, d)`: if d > 0 and n = d → ok; n = 0 → critical; else → warning with `"{d-n} of {d} sessions missing {label}."`. `pct = round(n/d * 100)`. |
| **Not-planned guard** | If `planning_status == "not_planned"` (zero-session night), `overall_pct` is set to `None`, not 0 — preventing a zero-session night from appearing as 0% ready. |
| **Data confidence** | `{units_reporting, units_expected, completeness_pct}`. |
| **Source tables** | `ParadeNight`, `Session` (via `_next_unit_readiness()` → `parade_night_readiness()` from `services_readiness`). |
| **Refresh** | Per request. |
| **User action** | Click a critical/warning cell to drill into that unit's parade nights. |
| **Drill-down** | Route: `parade-nights`, filter: `squadron_id` or `wing_id` per unit. |
| **Accessible alternative** | Table: unit name, each column's n/d/pct/status. |
| **Chart type** | `readiness_matrix` |

---

### C2. Risk Forecast (`_risk_forecast`)

| Field | Value |
|---|---|
| **Question** | What specific readiness risks are forecast across all units in the next 8 weeks, and what category are they? |
| **Purpose** | Enable command to take pre-emptive action on upcoming risks before they become missed sessions. |
| **Population** | All PNs for all child units from today to today + 8 weeks. |
| **Period** | Next 8 calendar weeks (hard-coded). Severity: `high` if date ≤ today + 2 weeks, else `medium`. |
| **Risk categories** | `no_facilitator`, `no_facility`, `curriculum_not_allocated` (session-level); `activity_conflict`, `holiday_conflict` (PN-level). `equipment_unavailable` not tracked — listed in `data_confidence.categories_not_available`. |
| **Numerator** | `affected_sessions` count per risk item. Session-level: count of affected sessions in that PN. PN-level (activity_conflict, holiday_conflict): `len(pn_sessions)`. |
| **Output cap** | `data[:200]` — first 200 risk items sorted by date. |
| **Holiday filter** | Only `HolidayPeriod.affects_parade == True` periods are included. |
| **Source tables** | `ParadeNight`, `Session`, `Activity`, `HolidayPeriod`, `PlanningYear` (queried directly). |
| **Refresh** | Per request. |
| **Insight trigger** | Total risk item count and most common category. |
| **User action** | Take pre-emptive action per risk item's `action` field. |
| **Drill-down** | Route: `parade-nights`, filter: `date`. |
| **Accessible alternative** | Table: date, unit, risk category, severity, affected sessions, recommended action. |
| **Chart type** | `risk_timeline` (stacked bar by week + detail table) |

---

### C3. Immediate Issues (`_immediate_issues`)

| Field | Value |
|---|---|
| **Question** | Which units need the most command attention in the next 2 weeks — and why? |
| **Purpose** | Distil the 8-week risk forecast to actionable priorities for the next fortnight, ranked by total unresolved items. |
| **Population** | High-severity risk items from C2 (items where `severity = "high"`, i.e. PN date ≤ today + 2 weeks). |
| **Period** | Next 2 weeks (derived from C2 severity classification). |
| **Numerator** | Sum of `affected_sessions` per risk category per unit. |
| **Denominator** | None — ranked count. |
| **Source tables** | None — operates on pre-computed `_risk_forecast()["data"]` (no new DB queries). |
| **Refresh** | Per request (combined with C2 call). |
| **Insight trigger** | Unit with highest total unresolved items. |
| **User action** | Direct command attention / contact to the top-ranked unit. |
| **Drill-down** | Route: `parade-nights`, filter: `squadron_id` or `wing_id`. |
| **Accessible alternative** | Table: unit name, count per risk category, total. |
| **Chart type** | `stacked_bar_horizontal` |

---

### C4. Command Weekly Delivered (`_command_weekly_delivered`)

| Field | Value |
|---|---|
| **Question** | How many sessions were delivered (and what was the outcome mix) each week across all units in this command? |
| **Purpose** | Same question as A1, but aggregated across all subordinate units — not averaged. |
| **Population** | All sessions for all child units in the command scope and window. |
| **Period** | Selected window (default: term). |
| **Formula** | Identical to A1 (`_weekly_outcomes`). Summed across all units — sessions are aggregated before the function call, not averaged at the end. |
| **Source tables** | `ParadeNight`, `Session` (queried across all child units before function call). |
| **Refresh** | Per request. |
| **User action** | Review any weeks with a spike in cancelled or not-delivered sessions. |
| **Drill-down** | Route: `parade-nights`. |
| **Accessible alternative** | Table: week, outcome counts per status. |
| **Chart type** | `stacked_bar` |

---

### C5. Command Reliability Trend (`_command_reliability_trend`)

| Field | Value |
|---|---|
| **Question** | Is command-wide delivery reliability improving or declining over 12 weeks? |
| **Purpose** | Same as A2, but across all units — provides the systemic view to complement unit-level trends. |
| **Population** | All terminal-status sessions for all child units (past PNs only). |
| **Period** | Rolling last 12 ISO calendar weeks. |
| **Formula** | Identical to A2 (`_delivery_trend`). Aggregated across all units before call. |
| **Thresholds** | Green ≥ 80%, Amber ≥ 60%, Red < 60%. Threshold labels added as `threshold_labels` dict. |
| **Source tables** | `ParadeNight`, `Session` (queried across all child units before call). |
| **Refresh** | Per request. |
| **User action** | If declining: investigate which units are dragging the trend. |
| **Drill-down** | Route: `parade-nights`. |
| **Accessible alternative** | Table: week, reliability %, delivered count, terminal count. |
| **Chart type** | `line` |

---

### C6. Outcomes by Unit (`_outcomes_by_unit`)

| Field | Value |
|---|---|
| **Question** | How does each unit's outcome mix compare — what proportion of their sessions were delivered vs. missed? |
| **Purpose** | 100%-stacked comparison so units can be compared regardless of size — a small squadron and a large squadron are comparable on the same axis. |
| **Population** | Sessions on PNs within the window per unit (via `_unit_pns_and_sessions()`). |
| **Period** | Parameterised window. |
| **Numerator** | Count of sessions in each status per unit. |
| **Denominator** | `total = sum(all status counts)` per unit. |
| **Formula** | `pct = round(count / total * 100)` per status if total > 0, else 0. Statuses not in `(delivered, delivered_with_issue, cancelled, not_delivered)` → `outstanding`. This is a 100%-stacked chart — percentages are within each unit's own total, not cross-unit. |
| **Isolation insight** | Units with `(delivered + delivered_with_issue) < 60%` flagged as underperforming. If any: count reported. |
| **Source tables** | `ParadeNight`, `Session` (via `_unit_pns_and_sessions()`). |
| **Refresh** | Per request. |
| **User action** | Investigate units below 60% delivered. |
| **Drill-down** | Route: `parade-nights`, filter: `squadron_id` or `wing_id` per unit. |
| **Accessible alternative** | Table: unit name, delivered, not_delivered, cancelled, outstanding, total, delivery %. |
| **Chart type** | `stacked_bar_horizontal_100` |

---

## Section D — Wing Readiness Comparison (National scope)

---

### D1. Wing Readiness Comparison (`_wing_readiness_comparison`)

| Field | Value |
|---|---|
| **Question** | How does delivery reliability compare across Wings at the national level? |
| **Purpose** | National-scope equivalent of B1 — allows National Admin to see which Wings need attention. |
| **Population** | All non-archived Wings; their PNs (queried by `ParadeNight.wing_id`) and sessions within the window. |
| **Period** | Parameterised window. |
| **Numerator** | Count of delivered sessions (`_DELIVERED`) per Wing. |
| **Denominator** | Count of terminal sessions (`_TERMINAL`) per Wing. |
| **Formula** | `pct = round(delivered / total * 100)` if total > 0, else 0. Wings with no squadrons are skipped entirely. Wings with squadrons but no PNs in window get `readiness_pct: 0, total: 0`. |
| **Source tables** | `Wing`, `ParadeNight`, `Session` (queried directly; PNs fetched by `wing_id`, not by collecting squadron IDs). |
| **Refresh** | Per request. |
| **User action** | Offer national-level support to the lowest-ranking Wing. |
| **Drill-down** | Route: `parade-nights`. |
| **Accessible alternative** | Table: Wing code, name, reliability %, delivered, terminal. |
| **Chart type** | `bar_horizontal` |

---

## Section E — Omitted / Not Tracked

| Item | Status | Reason |
|---|---|---|
| Equipment availability | Not tracked in risk forecast | Explicitly listed in `data_confidence.categories_not_available`. Equipment confirmation column in readiness matrix always returns `status: "no_data"`. |
| Individual cadet progress | Not a dashboard metric | Cadet-level data is not surfaced in any dashboard — only class and stage aggregates. |

---

## Cross-Reference: Function → Chart ID

| Function | `chart_id` | Section |
|---|---|---|
| `_weekly_outcomes` | `weekly_outcomes` | A1, C4 |
| `_delivery_trend` | `delivery_trend` | A2, C5 |
| `_curriculum_progress` | `curriculum_progress` | A4 |
| `_element_curriculum_progress` | `element_curriculum_progress` | A5 |
| `_class_curriculum_progress_summary` | `class_curriculum_progress` | A6 |
| `_curriculum_backlog` | `curriculum_backlog` | A3 |
| `_cancellation_pareto` | `cancellation_pareto` | A8 |
| `_facilitator_workload` | `facilitator_workload` | A9 |
| `_facilitator_status_distribution` | `facilitator_status_distribution` | A10 |
| `_facilitator_repeated_gaps` | `facilitator_repeated_gaps` | A11 |
| `_facilitator_leave_impact` | `facilitator_leave_impact` | A12 |
| `_facilitator_capability_dependency` | `capability_dependency` | A13 |
| `_subject_area_resilience` | `subject_area_resilience` | A14 |
| `_facilitator_type_distribution` | `facilitator_type_distribution` | A15 |
| `_long_term_delivery_trend` | `long_term_delivery_trend` | A16 |
| `_session_outcomes_distribution` | `session_outcomes` | A7 |
| `_squadron_readiness` | `squadron_readiness` | B1 |
| `_squadron_delivery_comparison` | `squadron_delivery_comparison` | B2 |
| `_wing_subject_area_gaps` | `wing_subject_area_gaps` | B3 |
| `_wing_readiness_comparison` | `wing_readiness` | D1 |
| `_readiness_matrix` | `readiness_matrix` | C1 |
| `_risk_forecast` | `risk_forecast` | C2 |
| `_immediate_issues` | `immediate_issues` | C3 |
| `_command_weekly_delivered` | `weekly_outcomes` | C4 |
| `_command_reliability_trend` | `delivery_trend` | C5 |
| `_outcomes_by_unit` | `outcomes_by_unit` | C6 |

---

## Issues Identified This Pass

These issues were found during the metric definition audit and require follow-up:

1. **A4 phase blending** — Curriculum progress is per Training Stage, not per Training Class. Tracked as CLASS-08 (backend CLOSED, frontend rendering via CLASS-12/CLASS-13 now CLOSED). The combined class view (A6) is the correct answer; A4 remains as a stage-level summary.

2. **A8 "Reason not recorded" actionability** — The Pareto chart surfaces cases where `cancellation_reason` is null. The frontend does not yet show an actionable prompt when this category is the largest bar. Tracked as a data-quality-register follow-up (see original dictionary note).

3. **C1 equipment column always no_data** — The `equipment_confirmed` column in the readiness matrix always returns `status: "no_data"`. This adds visual noise without actionable data. Recommend either removing the column from the UI or replacing it with a tracked metric (e.g. "all three requirements met = fully ready"). Severity: **low** (informational gap, not a data error).

4. **C4/C5 aggregation confirmed correct** — Command charts correctly sum session counts across all units before computing the rate, not average rates per unit. No action needed; documented for verification.

5. **B2 `delivered_with_issue` — confirmed correct** — `_squadron_delivery_comparison` (line 1119) uses `_DELIVERED = {"delivered", "delivered_with_issue"}` consistently with all other delivery functions. No inconsistency.
