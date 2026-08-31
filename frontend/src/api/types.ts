// Types mirror the backend response shapes exactly (read from the route handlers).
export interface SessionInfo {
  user_id: string; display_name: string; role: string;
  wing_id: string | null; wing_code: string | null;
  squadron_id: string | null; squadron_code: string | null;
  national_id: string | null;
  is_wing: boolean; is_national: boolean;
  proxy?: { mode: string; acting_squadron_id: string | null; acting_squadron_code: string | null; acting_squadron_name: string | null; acting_wing_id: string | null; proxy_session_id: string } | null;
}
export interface Squadron {
  squadron_id: string; wing_id: string; code: string; name: string; short_name: string;
  address: string | null; default_parade_day: string | null;
  default_start_time: string | null; default_end_time: string | null; default_session_count: number | null;
}
export interface Wing { wing_id: string; code: string; name: string; }
// REM-84: public pre-login org list (GET /api/auth/organisations) and the
// unit+role -> user_id resolver (POST /api/auth/lookup) that the real,
// secure production login path requires -- see auth.py's own LoginIn/lookup
// comments ("production always provides user_id via /lookup").
export interface LoginOrgSquadron { code: string; name: string; unit_type: string; }
export interface LoginOrgWing { code: string; name: string; squadrons: LoginOrgSquadron[]; }
export interface LoginOrganisations { wings: LoginOrgWing[]; }
export type LoginUnitType = "squadron" | "wing" | "national";
export interface UserRecord {
  user_id: string; display_name: string; role: string;
  wing_id: string | null; squadron_id: string | null; national_id: string | null;
  squadron_code: string | null; wing_code: string | null;
}
export interface AccountRecord {
  user_id: string; display_name: string; role: string; scope_type: string;
  wing_id: string | null; squadron_id: string | null; national_id: string | null;
  flight_id: string | null; squadron_code: string | null; wing_code: string | null;
  active_status: boolean; last_login_at: string | null;
  code_last_changed: string | null; code_changed_by: string | null;
  is_archived: boolean; archived_at: string | null; locked_until: string | null;
}
export interface AccountCreateResult extends AccountRecord {
  new_code: string; new_code_notice: string;
}
export interface Flight {
  flight_id: string; squadron_id: string; squadron_code: string | null;
  squadron_name: string | null; name: string; active_status: boolean;
  created_at: string | null;
}
export interface CurriculumItem {
  curriculum_id: string; code: string; title: string; phase: string; element: string;
  duration_minutes: number; core_status: string; learning_hub_url: string | null;
  recommended_term: string | null; session_count: number; progress: string;
}
export interface SessionRow {
  id: string; parade_night_id: string; squadron_id: string; period_number: number;
  status: string; phase_at_time: string | null; curriculum_item_id: string | null;
  curriculum_code_at_time: string | null; curriculum_title_at_time: string | null;
  custom_title: string | null; facilitator_id: string | null;
  facilitator_display_name_at_time: string | null; training_area_id: string | null;
  expected_attendance: number | null; actual_attendance: number | null;
  not_delivered_reason: string | null; rescheduled_to_date: string | null;
  // CLASS-06: which Training Class(es) this session targets (CLASS-03's
  // SessionAudience linkage), additive on GET /api/parade-nights.
  training_classes: { training_class_id: string; display_name: string }[];
  [k: string]: unknown;
}
export interface ParadeNight {
  parade_night_id: string; squadron_id: string; date: string; term: string | null;
  start_time: string | null; end_time: string | null; session_count: number;
  parade_type: string; published_status: boolean; readiness_score: number | null; closeout_status: string | null;
  timing_template_id: string | null;
}
export interface ParadeNightWithSessions extends ParadeNight { sessions: SessionRow[]; }
export interface ParadeNightDetail extends ParadeNightWithSessions {
  readiness: { score: number; band: string; deductions: { reason: string; points: number }[] };
  // REM-17 (original_instruction.md Section 15): the authoritative readiness
  // computation -- `readiness` above is the legacy score/band shape, hard-coded
  // to score=100 for a zero-session night by design (see services_readiness.py),
  // so it must never be shown unguarded. planning_status is the field that
  // actually distinguishes "not_planned" from a genuinely ready night.
  readiness_v2: {
    planning_status: "not_planned" | "partly_planned" | "planned" | "at_risk" | "blocked";
    sessions_total: number; sessions_ready: number; requirements_summary: string;
  };
  publish_blockers: string[];
}
export interface Facilitator {
  facilitator_id: string; first_name: string; last_name: string;
  current_rank: string | null; type: string; subject_areas: string[];
}
export interface FacilitatorStats {
  facilitator: { facilitator_id: string; name: string };
  counts: Record<string, number>; by_phase: Record<string, number>;
  load_score: number; sessions: SessionRow[];
}
export interface TrainingArea { training_area_id: string; name: string; type: string | null; capacity: number | null; [k: string]: unknown; }
export interface Equipment { equipment_id: string; name: string; type: string | null; quantity: number | null; [k: string]: unknown; }
export interface ClashResult { date: string; clashes: { type: string; resource_id: string }[]; }
export interface Cadet {
  cadet_id: string; service_number: string | null; rank: string | null;
  first_name: string; last_name: string; phase: string | null;
  attendance_percentage: number | null; sitrep_part_1_status: string | null;
  support_flag: boolean | null; support_notes?: string | null;
}
export interface CadetRiskFlag { cadet: string; reasons: string[]; }
// CLASS-09: individual Cadet<->Training Class membership, explicitly
// product-scope-confirmed before being built -- see the backend model's
// own docstring (models/training.py) for why this is conditional rather
// than a default. Enables a Cadet to hold concurrent Foundation (e.g.
// Senior 1) and Extension (e.g. Bronze CLP) membership at once.
export interface CadetClassMembership {
  membership_id: string; cadet_id: string; training_class_id: string;
  training_class_name: string | null; training_stage_id: string | null;
  start_date: string | null; end_date: string | null; active_status: boolean;
  source: string; version: number; created_at: string | null;
}
export interface TrainingClassSummary {
  training_class_id: string; squadron_id: string; training_year_id: string;
  training_stage_id: string; display_name: string; class_number: number;
  start_date: string | null; end_date: string | null; expected_count: number | null;
  notes: string | null; is_archived: boolean; version: number;
}
export interface AuditRow {
  audit_id: string; timestamp: string; role: string; action: string;
  object_type: string | null; object_id: string | null; reason: string | null; proxy_session_id: string | null;
}
export interface ActionItem {
  action_id: string; title: string; description: string | null; owner: string | null;
  due_date: string | null; status: string; severity: string | null; source: string | null;
}
// Reports
export interface SummaryReport { title: string; counts: Record<string, number>; total: number; decision: string; }
export interface ReadinessReport { title: string; parade_nights: { parade_night_id: string; date: string; score: number; band: string; deductions: { reason: string; points: number }[] }[]; decision: string; }
export interface CoverageReport { title: string; total: number; scheduled: number; delivered: number; coverage_pct: number; unscheduled: { code: string; title: string; phase: string }[]; decision: string; }
export interface FacLoadReport { title: string; facilitators: { name: string; facilitator_id: string | null; sessions: number; delivered: number; risk: string }[]; decision: string; }
export interface NotDeliveredReport { title: string; sessions: { id: string; curriculum_code_at_time: string | null; not_delivered_reason: string | null; status: string }[]; decision: string; }
export interface WingOverview { squadrons: WingSquadronRow[]; }
export interface WingSquadronRow {
  squadron_id: string; code: string; short_name: string; parade_day: string | null;
  nights: number; published: number; sessions: number; delivered: number; pct: number;
  readiness: number | null; no_future_plan: boolean; no_published_plan: boolean;
  coverage_pct: number; not_delivered: number;
}
export interface WingPhaseCoverage { phases: string[]; squadrons: { squadron_id: string; short_name: string; phase_pct: Record<string, number> }[]; }
export interface WingCapability {
  subjects: string[];
  squadrons: { squadron_id: string; code: string; short_name: string; subject_facilitators: Record<string, number> }[];
  wing_avg: Record<string, number>;
  squadron_count: number;
}
export interface NationalOverview { wings: { wing_id: string; code: string; name: string; squadrons: number; sessions: number; delivered: number; not_delivered: number; coverage_pct: number }[]; }
export interface NationalCapabilityWing {
  wing_id: string; code: string; name: string;
  squadrons: number; facilitator_total: number;
  subject_none_sqns: Record<string, number>;
  subject_distribution: Record<string, number>;
}
export interface NationalCapability { subjects: string[]; wings: NationalCapabilityWing[]; }

export interface WingCancellationSqn {
  squadron_id: string; code: string; short_name: string;
  cancelled_sessions: number; cancelled_nights: number;
  reasons: { reason: string; count: number }[];
}
export interface WingCancellationTrend {
  title: string; decision: string;
  total_cancelled_sessions: number; total_cancelled_nights: number;
  squadrons: WingCancellationSqn[];
}

export interface WingNotDeliveredSqn {
  squadron_id: string; code: string; short_name: string;
  not_delivered_count: number;
  sessions: { id: string; curriculum_code_at_time: string | null; not_delivered_reason: string | null }[];
}
export interface WingNotDeliveredReport {
  title: string; decision: string; total_not_delivered: number;
  squadrons: WingNotDeliveredSqn[];
}
// Imports
export interface ImportPreview { headers: string[]; row_count: number; preview: Record<string, string>[]; detected: Record<string, string | null>; }
export interface ImportCommitResult { ok: boolean; import_id: string; accepted: number; rejected: number; }

// ─── Planning Workspace types ───────────────────────────────────────────────
export interface PlanningYear {
  // null when the year has no row yet. A Training Year is calendar context, so
  // a year nobody has written to is still a real, selectable year -- it simply
  // has nothing to point an id at. Typing this `string` was a lie the moment
  // the API started returning logical years.
  planning_year_id: string | null; unit_id: string | null; wing_id: string | null;
  year: number; name: string; active_status: boolean;
  state?: "past" | "current" | "future";
  materialised?: boolean;
  unit_code?: string | null; unit_name?: string | null; wing_code?: string | null;
}
export interface ParadeDate {
  parade_date_id: string; planning_year_id: string; unit_id: string | null;
  parade_date: string; parade_type: string; term: string | null;
  week_number: number | null; is_active: boolean;
  notes: string | null; parade_night_id: string | null;
}
export interface PlanningSession {
  session_id: string; parade_night_id: string; squadron_id: string;
  cadet_group: string | null; session_number: number; part_number: number | null;
  curriculum_id: string | null; curriculum_code: string | null;
  curriculum_title: string | null; element: string | null;
  activity_title: string | null;
  facilitator_id: string | null; facilitator_name: string | null;
  assistant_facilitator_id: string | null; assistant_facilitator_name: string | null;
  location_id: string | null; location_name: string | null;
  status: string; notes: string | null; is_combined: boolean;
  override_conflict: boolean; created_at: string | null;
  // CLASS-06: which Training Class(es) this session targets (CLASS-03's
  // SessionAudience linkage), additive on the weekly-program endpoint.
  training_classes?: { training_class_id: string; display_name: string }[];
  // CLASS-21: curriculum core_status for Foundation/Extension PW filter.
  core_status?: string | null;
}
export interface TimingBlock {
  sequence: number; name: string; block_type: string;
  start_time: string | null; end_time: string | null;
  duration_minutes: number; is_instructional: boolean; period_number: number | null;
}
export interface TimingTemplateFull {
  timing_template_id: string; squadron_id: string; name: string;
  effective_from: string; effective_to: string | null;
  is_default: boolean; active_status: boolean; notes: string | null;
  instructional_period_count: number;
}
export interface PlanningConflict {
  conflict_id: string; planning_year_id: string | null; parade_night_id: string | null;
  scheduled_session_id: string | null; conflict_type: string; severity: string;
  message: string; is_resolved: boolean; override_reason: string | null;
  created_at: string | null;
}
export interface WeeklyProgramData {
  parade_date_id: string; parade_night_id: string | null;
  parade_date: string; unit_id: string | null;
  timing_blocks: TimingBlock[]; sessions: PlanningSession[];
  conflicts: PlanningConflict[]; has_unresolved_conflicts: boolean;
}
export interface AnchorEvent {
  anchor_event_id: string; anchor_id?: string; planning_year_id: string; event_name: string;
  event_type: string | null; importance: string | null; importance_level: number | null;
  start_date: string; end_date: string | null;
  audience_orientation: boolean; audience_initial: boolean;
  audience_junior: boolean; audience_intermediate: boolean; audience_senior: boolean;
  audience_staff_only: boolean; audience_proficient: boolean; audience_first_years: boolean;
  nomination_end_date: string | null;
  unit_name: string | null;
  cea_activity_id: string | null;
  planning_impact: string | null; notes: string | null;
  owning_level?: string;
}
export interface HolidayPeriod {
  holiday_id: string; planning_year_id: string; name: string;
  start_date: string; end_date: string;
  holiday_type: string; affects_parade: boolean;
  jurisdiction: string | null; notes: string | null;
}
export interface AnnualProgramTerm {
  term: string; start_date: string; end_date: string;
  parade_dates: (ParadeDate & {
    session_count: number; filled_count: number; in_holiday: boolean;
    sessions_summary: NightSessionSummary[];
    conflict_count: number;
    notices: ParadeNotice[];
  })[];
  holidays: HolidayPeriod[];
  activities: AnchorEvent[];
}
export interface AnnualProgram {
  planning_year_id: string; year: number; terms: AnnualProgramTerm[];
}
export interface LongRangeRow {
  parade_date: ParadeDate; sessions: PlanningSession[];
  session_count: number; filled_slots: number; conflicts: PlanningConflict[];
}
export interface LongRangeView {
  planning_year_id: string; from_date: string; to_date: string;
  weeks: number; parade_dates: LongRangeRow[]; anchors: AnchorEvent[];
}
export interface MissionItem {
  curriculum_id: string; code: string; title: string;
  phase: string; element: string | null; recommended_term: string | null;
  part_count: number | null; duration_minutes: number;
  core_status: string; is_scheduled: boolean;
  has_cancelled: boolean; has_not_delivered: boolean; has_rescheduled: boolean; needs_reschedule: boolean;
  // Six-state model: unscheduled | planned | cancelled_awaiting_reschedule |
  // not_delivered_awaiting_reschedule | rescheduled | resolved.
  backlog_status: string;
  scheduled_count: number; instructor_suitability: string | null;
  // CLASS-05: per-Training-Class share of this same six-state model, one
  // entry per active Class belonging to this item's own Stage (empty if the
  // Stage has no Classes yet). unassigned_session_count counts this item's
  // scheduled sessions that have no Training Class audience assigned at all
  // -- expected/normal, since audience assignment is optional.
  class_breakdown: {
    training_class_id: string; display_name: string; scheduled_count: number;
    is_scheduled: boolean; has_cancelled: boolean; has_not_delivered: boolean;
    has_rescheduled: boolean; needs_reschedule: boolean; backlog_status: string;
  }[];
  unassigned_session_count: number;
  scheduled_sessions: {
    session_id: string; parade_date: string | null; parade_date_id: string | null; term: string | null;
    session_number: number; part_number: number | null; cadet_group: string | null;
    facilitator_id: string | null; facilitator_name: string | null;
    location_id: string | null; location_name: string | null; status: string;
    cancelled_reason: string | null; not_delivered_reason: string | null;
    rescheduled_to_date: string | null; outcome_note: string | null;
  }[];
}
export interface PlanningLocation {
  location_id: string; unit_id: string; name: string;
  location_type: string; capacity: number | null; active_status: boolean;
}
export interface PlanningFacilitator {
  facilitator_id: string; display_name: string; rank: string | null;
  type: string; subject_areas: string[]; max_sessions_per_night: number;
}
export interface LocalLesson {
  local_lesson_id: string; lesson_code: string; lesson_name: string;
  squadron_id: string | null; description: string | null;
  subject_area: string | null; default_duration_mins: number | null;
}
export interface WingHQEvent {
  event_id: string; wing_id: string; year: number; title: string;
  event_type: string; start_date: string; end_date: string | null;
  planning_importance: string; audience: string[] | null;
  location: string | null; notes: string | null;
  requires_squadron_action: boolean; is_planning_anchor: boolean;
  sqn_status: { status: string; notes: string | null } | null;
}
export interface CommandCentreData {
  planning_year_id: string | null;
  year: number | null;
  upcoming_anchors: AnchorEvent[];
  prep_gaps: { anchor_event_id: string; event_name: string; start_date: string; days_until: number }[];
  unreviewed_wing: { wing_event_id: string; title: string; start_date: string; days_until: number }[];
  active_conflicts: { conflict_id: string; type: string; message: string; parade_date: string | null }[];
  unscheduled_required: { curriculum_id: string; code: string; title: string; phase: string; needs_class_ids: string[] }[];
  training_classes: { training_class_id: string; display_name: string; training_stage_id: string; stage_name: string }[];
  recent_imports: { import_type: string; created_at: string | null }[];
  nights_missing_facilitator: number;
}

export interface NightSessionSummary {
  session_id: string;
  period: number;
  cadet_group: string | null;
  title: string | null;
  curriculum_code: string | null;
  facilitator: string | null;
  location: string | null;
  // CLASS-06: which Training Class(es) this session targets (CLASS-03's
  // SessionAudience linkage), additive on the annual-program endpoint.
  training_classes: { training_class_id: string; display_name: string }[];
  // CLASS-21: curriculum core_status for Foundation/Extension PW filter.
  core_status?: string | null;
}
export interface ParadeNotice {
  notice_id: string;
  parade_night_id: string;
  notice_text: string;
  audience: string | null;
  priority: string;
  created_by: string | null;
  is_archived: boolean;
  created_at: string | null;
  updated_at: string | null;
}
export interface NightSummary {
  parade_date_id: string;
  parade_date: string;
  parade_type: string;
  term: string | null;
  week_number: number | null;
  notes: string | null;
  parade_night_notes: string | null;
  parade_night_id: string | null;
  sessions: NightSessionSummary[];
  conflict_count: number;
  notices: ParadeNotice[];
}
export interface NightSummariesResponse {
  planning_year_id: string;
  summaries: NightSummary[];
}

export interface PlanningActivityRecord {
  id: string;
  planning_year_id: string | null;
  import_batch_id: string | null;
  owning_squadron_id: string | null;
  source_type: string;
  activity_id: string | null;
  activity_type: string | null;
  parent_unit: string | null;
  host_unit: string | null;
  activity_name: string;
  nomination_start_date: string | null;
  nomination_end_date: string | null;
  activity_start_date: string | null;
  activity_end_date: string | null;
  location: string | null;
  activity_poc: string | null;
  staff_only: boolean;
  seniors: boolean;
  proficient: boolean;
  first_years: boolean;
  activity_importance: string | null;
  is_reviewed: boolean;
  reviewed_by: string | null;
  reviewed_at: string | null;
  status: string;
  is_archived: boolean;
  is_hidden: boolean;
  local_notes: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface PlanningFacilitatorLeave {
  id: string;
  facilitator_id: string;
  planning_year_id: string | null;
  start_date: string;
  end_date: string;
  reason: string | null;
  notes: string | null;
  created_by: string | null;
  created_at: string | null;
  is_archived?: boolean;
}

export interface FacilitatorLeaveResult {
  ok: boolean;
  leave: PlanningFacilitatorLeave;
  affected_sessions: Array<{
    session_id: string;
    parade_date: string;
    session_number: number;
    cadet_group: string | null;
    title: string | null;
  }>;
}

export interface FacilitatorWorkload {
  total_scheduled: number;
  nights_with_sessions: number;
  avg_per_night: number;
  max_per_night: number;
  min_per_night: number;
  upcoming_sessions: Array<{
    session_id: string;
    parade_date: string;
    session_number: number;
    cadet_group: string | null;
    title: string | null;
    location_name: string | null;
  }>;
}

export interface EquipmentItem {
  equipment_id: string;
  name: string;
  type: string | null;
  quantity: number;
  available_quantity: number;
  condition: string | null;
  notes: string | null;
}

export interface CeaActivity {
  id: string;
  import_batch_id: string | null;
  planning_year_id: string | null;
  wing_id: string | null;
  unit_id: string | null;
  cea_activity_id: string | null;
  activity_type: string | null;
  status_name: string | null;
  parent_unit: string | null;
  host_unit: string | null;
  activity_name: string;
  nomination_start_date: string | null;
  nomination_end_date: string | null;
  activity_start_date: string | null;
  activity_end_date: string | null;
  start_time: string | null;
  end_time: string | null;
  location: string | null;
  activity_poc: string | null;
  notes: string | null;
  source_type: string;
  classification_status: string;
  importance: string | null;
  audience_staff_only: boolean;
  audience_seniors: boolean;
  audience_proficient: boolean;
  audience_first_years: boolean;
  classified_by: string | null;
  classified_at: string | null;
  is_removed_from_cea: boolean;
  is_archived: boolean;
  created_at: string | null;
  is_hidden_for_me: boolean;
  local_note: string | null;
}

export interface CeaImportBatch {
  id: string;
  imported_by: string;
  source_file_name: string | null;
  row_count: number;
  created_count: number;
  updated_count: number;
  duplicate_count: number;
  skipped_count: number;
  error_count: number;
  created_at: string | null;
}

export interface CeaImportResult {
  ok: boolean;
  batch_id: string;
  row_count: number;
  created: number;
  updated: number;
  duplicates: number;
  skipped: number;
  errors: number;
  preview: Array<{
    action: "create" | "update" | "duplicate";
    cea_activity_id: string | null;
    activity_name: string;
    activity_start_date: string | null;
    activity_end_date: string | null;
    host_unit: string | null;
    parent_unit: string | null;
    location: string | null;
    existing_id: string | null;
  }>;
}

// ─── Dashboard charts (GET /api/dashboard/charts, /api/dashboard/charts/strategic) ──
// Shared schema every chart_id follows — see backend/app/routers/dashboard.py.
export type ChartType =
  | "bar_horizontal" | "donut" | "line" | "stacked_bar" | "stacked_bar_horizontal"
  | "grouped_bar" | "heatmap" | "readiness_card" | "readiness_grid"
  | "readiness_matrix" | "risk_timeline" | "stacked_bar_horizontal_100" | "pareto" | "error";

export interface ChartSeriesSpec { key: string; label: string; color?: string; }
export interface ChartThresholds { green?: number; amber?: number; red?: number; }

export interface DashboardChart {
  chart_id: string;
  title?: string;
  explanation?: string;
  question?: string;
  chart_type: ChartType;
  data: unknown;
  insight?: string | null;
  empty_state?: string;
  drill_down?: { route?: string; filters?: Record<string, unknown> } | null;
  permission_scope?: string;
  x_axis?: string;
  y_axis?: string;
  series?: ChartSeriesSpec[];
  thresholds?: ChartThresholds;
  columns?: string[];
  error?: boolean;
  // Command Dashboard (Wing/National) narrative fields -- every Section A/B
  // chart exposes these via an info toggle (see connected-frontend's
  // training-dashboard.spec.ts "Purpose, Measure and Action").
  purpose?: string;
  measure?: string;
  assessment?: string;
  action?: string;
  weekly?: unknown;
  data_confidence?: { units_reporting?: number; units_expected?: number; completeness_pct?: number | null };
}

export interface DashboardChartsResponse {
  scope: "squadron" | "wing" | "national";
  window: string;
  charts: Record<string, DashboardChart>;
  error?: string;
}

// ─── Command Dashboard (Wing/National training readiness/delivery) ────────
export interface ReadinessMatrixCell {
  status: "ok" | "warning" | "critical" | "no_data";
  numerator: number | null;
  denominator: number | null;
  pct: number | null;
  warning: boolean;
  exception_reason: string | null;
  data_available: boolean;
}
export interface ReadinessMatrixRow {
  unit_id: string;
  label: string;
  name: string;
  status: "ok" | "warning" | "critical" | "no_data";
  sessions_planned: ReadinessMatrixCell;
  curriculum_allocated: ReadinessMatrixCell;
  facilitator_confirmed: ReadinessMatrixCell;
  facility_confirmed: ReadinessMatrixCell;
  equipment_confirmed: ReadinessMatrixCell;
  overall_readiness: ReadinessMatrixCell;
  trend: string;
  last_update: string | null;
  exception_reason: string | null;
}
export interface CommandDashboardResponse {
  scope: "wing" | "national";
  wing_id: string | null;
  wing_name: string | null;
  window: string;
  period: { label: string; start: string; end: string };
  generated_at: string;
  units_in_scope: number;
  data_confidence: { units_reporting: number; units_expected: number; completeness_pct: number | null };
  sections: {
    A: { readiness_matrix: DashboardChart; risk_forecast: DashboardChart; immediate_issues: DashboardChart };
    B: { weekly_delivered: DashboardChart; reliability_trend: DashboardChart; outcomes_by_unit: DashboardChart; cancellation_pareto: DashboardChart };
  };
  error?: string;
}

// ─── Facilitator Schedule Explorer (master transformation plan Block 9) ────
export interface FacilitatorScheduleFacilitator {
  facilitator_id: string;
  name: string;
  type: string;
  subject_areas: string[];
  on_leave_now: boolean;
}
export interface FacilitatorScheduleSessionItem {
  id: string;
  facilitator_id: string;
  kind: "session";
  date: string;
  label: string;
  status: string;
  parade_night_id: string;
  session_id: string;
}
export interface FacilitatorScheduleLeaveItem {
  id: string;
  facilitator_id: string;
  kind: "leave";
  start_date: string;
  end_date: string;
  label: string;
}
export type FacilitatorScheduleItem = FacilitatorScheduleSessionItem | FacilitatorScheduleLeaveItem;
export interface FacilitatorScheduleResponse {
  squadron_id: string | null;
  window: string;
  window_start: string;
  window_end: string;
  facilitators: FacilitatorScheduleFacilitator[];
  items: FacilitatorScheduleItem[];
}
