import { api } from "./client";
import type {
  SessionInfo, Squadron, Wing, UserRecord, AccountRecord, AccountCreateResult, Flight,
  CurriculumItem, ParadeNightWithSessions, ParadeNightDetail,
  SessionRow, Facilitator, FacilitatorStats, TrainingArea, Equipment, ClashResult, Cadet,
  CadetRiskFlag, AuditRow, ActionItem, SummaryReport, ReadinessReport, CoverageReport,
  FacLoadReport, NotDeliveredReport, WingOverview, NationalOverview, NationalCapability,
  WingPhaseCoverage, WingCapability, WingCancellationTrend, WingNotDeliveredReport,
  ImportPreview, ImportCommitResult,
  PlanningYear, AnnualProgram, LongRangeView, WeeklyProgramData,
  MissionItem, PlanningLocation, PlanningFacilitator, LocalLesson,
  WingHQEvent, CommandCentreData, PlanningConflict, HolidayPeriod,
  NightSummariesResponse, PlanningFacilitatorLeave, FacilitatorLeaveResult,
  FacilitatorWorkload, EquipmentItem, AnchorEvent, PlanningSession,
  DashboardChartsResponse, CadetClassMembership, TrainingClassSummary,
  LoginOrganisations, LoginUnitType,
} from "./types";

/** Handles both legacy array shape `[...]` and current `{"conflicts":[...]}` shape. */
export function parseConflictsList(raw: unknown): PlanningConflict[] {
  if (Array.isArray(raw)) return raw as PlanningConflict[];
  if (raw !== null && typeof raw === "object" && "conflicts" in raw) {
    return (raw as { conflicts: PlanningConflict[] }).conflicts ?? [];
  }
  return [];
}

export const authApi = {
  // REM-84: user_id is optional for backward compatibility (Login Page tests /
  // any future direct-code callers), but every real login now supplies it via
  // lookup() first -- see auth.py's LoginIn/login(): omitting it hits the
  // "legacy scan-all path (used by tests; production always provides user_id
  // via /lookup)", which skips per-account lockout tracking entirely.
  login: (code: string, user_id?: string) =>
    api.post<{ token: string; session: SessionInfo }>("/api/auth/login", user_id ? { code, user_id } : { code }),
  lookup: (unit_type: LoginUnitType, identifier: string | undefined, role: string) =>
    api.post<{ user_id: string; display_name: string }>("/api/auth/lookup", { unit_type, identifier, role }),
  organisations: () => api.get<LoginOrganisations>("/api/auth/organisations"),
  me: () => api.get<{ session: SessionInfo }>("/api/auth/me"),
  logout: () => api.post<{ ok: boolean }>("/api/auth/logout"),
  refresh: () => api.post<{ token: string; session: SessionInfo }>("/api/auth/refresh"),
  changeCode: (user_id: string, new_code: string) => api.post<{ ok: boolean }>("/api/auth/change-code", { user_id, new_code }),
};

export const orgApi = {
  users: () => api.get<UserRecord[]>("/api/users"),
  wings: () => api.get<Wing[]>("/api/wings"),
  squadrons: () => api.get<Squadron[]>("/api/squadrons"),
  squadron: (id: string) => api.get<Squadron>(`/api/squadrons/${id}`),
  nationalOverview: () => api.get<{ national: string; wings: unknown[]; wing_count: number }>("/api/national/overview"),
  audit: (q: { object_type?: string; object_id?: string; limit?: number } = {}) => {
    const p = new URLSearchParams();
    if (q.object_type) p.set("object_type", q.object_type);
    if (q.object_id) p.set("object_id", q.object_id);
    if (q.limit) p.set("limit", String(q.limit));
    const qs = p.toString();
    return api.get<AuditRow[]>(`/api/audit${qs ? `?${qs}` : ""}`);
  },
  proxyCurrent: () => api.get<{ active: boolean; mode?: string; acting_squadron_id?: string }>("/api/proxy/current"),
  enterProxy: (squadron_id: string, reason: string) => api.post<{ ok: boolean; proxy: unknown }>(`/api/proxy/enter/${squadron_id}`, { reason }),
  exitProxy: () => api.post<{ ok: boolean }>("/api/proxy/exit"),
};

export interface CanonicalActivity {
  activity_id: string;
  source: string;
  owning_level: "national" | "wing" | "squadron";
  activity_name: string;
  activity_type: string | null;
  date_start: string;
  date_end: string | null;
  time_start: string | null;
  time_end: string | null;
  location: string | null;
  audience: string[];
  notes: string | null;
  is_archived: boolean;
  is_inherited: boolean;
  read_only: boolean;
}

export interface TagRecord {
  tag_id: string;
  display_name: string;
  normalised_name: string;
  scope: "global" | "wing" | "squadron";
  wing_id: string | null;
  squadron_id: string | null;
  is_active: boolean;
}

export interface PhaseRecord {
  phase_id: string;
  name: string;
  display_name: string;
  scope_level: "system" | "national" | "wing" | "squadron";
  wing_id: string | null;
  squadron_id: string | null;
}

export const trainingApi = {
  // squadron_id (optional): lets a wing/national viewer see a specific squadron's
  // data without needing Proxy/Delegated Intervention Mode — see backend/app/
  // routers/training.py's _view_squadron_id (master transformation plan Block 8).
  curriculum: (squadron_id?: string) => api.get<{ items: CurriculumItem[] }>(`/api/curriculum${squadron_id ? `?squadron_id=${squadron_id}` : ""}`),
  curriculumSessions: (cid: string) => api.get<SessionRow[]>(`/api/curriculum/${cid}/sessions`),
  paradeNights: (squadron_id?: string) => api.get<ParadeNightWithSessions[]>(`/api/parade-nights${squadron_id ? `?squadron_id=${squadron_id}` : ""}`),
  paradeNight: (id: string) => api.get<ParadeNightDetail>(`/api/parade-nights/${id}`),
  createParadeNight: (b: { date: string; term?: string; session_count?: number; parade_type?: string }) =>
    api.post<{ ok: boolean; parade_night_id: string }>("/api/parade-nights", b),
  patchParadeNight: (id: string, b: { timing_template_id?: string | null }) =>
    api.patch<{ parade_night_id: string; timing_template_id: string | null }>(`/api/parade-nights/${id}`, b),
  publish: (id: string) => api.post<{ ok: boolean }>(`/api/parade-nights/${id}/publish`),
  close: (id: string) => api.post<{ ok: boolean }>(`/api/parade-nights/${id}/close`),
  // "Mark all delivered, then flag exceptions" bulk action (risk-register
  // data-entry UX ask): flag the few known exceptions individually first,
  // then bulk-clear everything else still draft/planned/published in one
  // action instead of clicking "Delivered" on every session.
  markRemainingDelivered: (id: string) =>
    api.post<{ ok: boolean; batch_id: string; sessions_updated: number; session_ids: string[] }>(
      `/api/parade-nights/${id}/mark-remaining-delivered`
    ),
  createSession: (b: Record<string, unknown>) => api.post<{ ok: boolean; session_id: string }>("/api/sessions", b),
  editSession: (id: string, b: Record<string, unknown>) => api.put<{ ok: boolean }>(`/api/sessions/${id}`, b),
  setStatus: (id: string, b: { status: string; reason?: string; rescheduled_to_date?: string; actual_attendance?: number }) =>
    api.post<{ ok: boolean }>(`/api/sessions/${id}/status`, b),
  facilitators: (squadron_id?: string) => api.get<Facilitator[]>(`/api/facilitators${squadron_id ? `?squadron_id=${squadron_id}` : ""}`),
  addFacilitator: (b: { first_name: string; last_name: string; current_rank?: string; type?: string; subject_areas?: string[]; confirm_duplicate?: boolean }) =>
    api.post<{ ok: boolean; facilitator_id: string }>("/api/facilitators", b),
  updateFacilitator: (id: string, b: { subject_areas?: string[]; type?: string; current_rank?: string; first_name?: string; last_name?: string }) =>
    api.patch<{ ok: boolean; facilitator_id: string; subject_areas: string[] }>(`/api/facilitators/${id}`, b),
  deleteFacilitator: (id: string) => api.delete<{ ok: boolean }>(`/api/facilitators/${id}`),
  restoreFacilitator: (id: string) => api.post<{ ok: boolean }>(`/api/facilitators/${id}/restore`, {}),
  facilitatorStats: (id: string) => api.get<FacilitatorStats>(`/api/facilitators/${id}/stats`),
  facilitatorImportTemplate: () => api.get<string>("/api/facilitators/import/template.csv"),
  importFacilitatorsCsv: (file: File, opts: { preview: boolean; confirmDuplicateRows?: number[] }) => {
    const form = new FormData();
    form.append("file", file);
    const params = new URLSearchParams({ preview: String(opts.preview) });
    if (opts.confirmDuplicateRows?.length) params.set("confirm_duplicate_rows", opts.confirmDuplicateRows.join(","));
    return api.postForm<{
      ok: boolean; preview: boolean;
      rows?: { row: number; action: string; message?: string; first_name: string | null; last_name: string }[];
      to_create?: number; duplicates?: number; errors: number;
      created?: number; skipped?: number; created_ids?: string[]; total?: number;
    }>(`/api/facilitators/import?${params}`, form);
  },
  // Canonical Activity records -- uses list_activities's inheritance-aware
  // scope_type=squadron path (backend/app/routers/training.py), not the
  // legacy no-scope_type path. The legacy path filters strictly on
  // Activity.squadron_id, which is always NULL for Wing/National-owned
  // Activity rows (see create_wing_activity/create_national_activity), so it
  // silently dropped every Wing/National activity from this view (found and
  // fixed in the remediation program's Stage 6, 2026-08-05). sources=activity
  // excludes the endpoint's own CEA/Holiday merge -- this drawer already
  // fetches those separately via ceaData/holidaysData, so merging them in
  // here too would duplicate rows.
  // The scope_type-aware path (opted into here via scope_type=squadron) returns
  // {items, total, truncated}, not a bare array -- unlike the legacy no-scope_type
  // path's plain list response. Unwrap .items here so every call site can keep
  // treating this as CanonicalActivity[] (found while adding e2e coverage for the
  // Getting Help section: an unhandled scope_type/legacy response-shape mismatch
  // was crashing the whole Activities tab for any squadron-scoped caller with
  // "tmsActivitiesData is not iterable").
  canonicalActivities: (squadronId: string) =>
    api.get<{ items: CanonicalActivity[]; total: number; truncated: boolean }>(
      `/api/activities?scope_type=squadron&scope_id=${squadronId}&sources=activity`
    ).then(r => r.items),
  // Activities tab "Getting Help" free text -- readable by any authenticated
  // role, editable by system_admin only (backend/app/routers/training.py).
  gettingHelp: () => api.get<{ content: string; updated_at: string | null }>("/api/activities/getting-help"),
  updateGettingHelp: (content: string) =>
    api.put<{ content: string; updated_at: string | null }>("/api/activities/getting-help", { content }),
  // Facilitator type reference data (backend/app/routers/training.py) -- connected-
  // frontend's Add Facilitator form already uses this; Planning Workspace's own
  // form previously had a hardcoded 4-option select whose values (officer/nco/
  // civcpersonal/guest) didn't even match the seeded display names (Staff/Officer/
  // NCO/Senior Cadet/Civilian), so a facilitator created there got a `type` no
  // dropdown anywhere could later recognise (Stage 8, 2026-08-05).
  facilitatorTypeTags: () => api.get<{ tag_id: string; display_name: string }[]>("/api/facilitator-type-tags"),
  createFacilitatorTypeTag: (display_name: string, scope: string) =>
    api.post<{ tag_id: string }>("/api/facilitator-type-tags", { display_name, scope }),
  archiveFacilitatorTypeTag: (tag_id: string) => api.delete<{ ok: boolean }>(`/api/facilitator-type-tags/${tag_id}`),
  // Subject-area tags -- same shape/scope model as facilitator-type tags (see
  // backend/app/routers/training.py's _tag_out / _can_create_tag).
  subjectAreaTags: () => api.get<TagRecord[]>("/api/subject-area-tags"),
  createSubjectAreaTag: (display_name: string, scope: string) =>
    api.post<{ tag_id: string }>("/api/subject-area-tags", { display_name, scope }),
  archiveSubjectAreaTag: (tag_id: string) => api.delete<{ ok: boolean }>(`/api/subject-area-tags/${tag_id}`),
  // Training-stage (CurriculumPhase) reference data -- same governed catalogue
  // used by the dashboard's Progress-by-Phase chart and curriculum item forms.
  phases: () => api.get<PhaseRecord[]>("/api/curriculum/phases"),
  createPhase: (name: string, scope_level: string) =>
    api.post<{ phase_id: string }>("/api/curriculum/phases", { name, display_name: name, scope_level }),
  archivePhase: (phase_id: string) => api.post<{ ok: boolean }>(`/api/curriculum/phases/${phase_id}/archive`),
  trainingAreas: (squadron_id?: string) => api.get<TrainingArea[]>(`/api/training-areas${squadron_id ? `?squadron_id=${squadron_id}` : ""}`),
  equipment: (squadron_id?: string) => api.get<Equipment[]>(`/api/equipment${squadron_id ? `?squadron_id=${squadron_id}` : ""}`),
  clashes: (date: string) => api.get<ClashResult>(`/api/resources/clashes?date=${date}`),
  cadets: () => api.get<Cadet[]>("/api/cadets"),
  cadetRisk: () => api.get<CadetRiskFlag[]>("/api/cadets/risk"),
  // CLASS-09: individual Cadet<->Training Class membership.
  cadetClassMemberships: (cadetId: string) =>
    api.get<CadetClassMembership[]>(`/api/cadets/${cadetId}/class-memberships`),
  addCadetClassMembership: (cadetId: string, body: { training_class_id: string; start_date?: string }) =>
    api.post<CadetClassMembership>(`/api/cadets/${cadetId}/class-memberships`, body),
  endCadetClassMembership: (membershipId: string, body: { end_date?: string; active_status?: boolean; client_version?: number }) =>
    api.patch<CadetClassMembership>(`/api/cadet-class-memberships/${membershipId}`, body),
  archiveCadetClassMembership: (membershipId: string) =>
    api.delete<{ ok: boolean }>(`/api/cadet-class-memberships/${membershipId}`),
  // Read-only list of active Training Classes for the caller's squadron --
  // just enough to populate the membership-assignment picker in Cadets.tsx.
  // Planning Workspace has no Training Class management UI of its own yet
  // (a separate, larger, already-tracked gap) -- this is not that.
  trainingClasses: (training_year_id?: string) =>
    api.get<TrainingClassSummary[]>(`/api/training-classes${training_year_id ? `?training_year_id=${training_year_id}` : ""}`),
};

export const reportApi = {
  summary: (squadron_id?: string) => api.get<SummaryReport>(`/api/reports/summary${squadron_id ? `?squadron_id=${squadron_id}` : ""}`),
  readiness: () => api.get<ReadinessReport>("/api/reports/readiness"),
  coverage: () => api.get<CoverageReport>("/api/reports/curriculum-coverage"),
  facLoad: (squadron_id?: string) => api.get<FacLoadReport>(`/api/reports/facilitator-load${squadron_id ? `?squadron_id=${squadron_id}` : ""}`),
  notDelivered: (squadron_id?: string) => api.get<NotDeliveredReport>(`/api/reports/not-delivered${squadron_id ? `?squadron_id=${squadron_id}` : ""}`),
  wingOverview: () => api.get<WingOverview>("/api/reports/wing-overview"),
  nationalOverview: () => api.get<NationalOverview>("/api/reports/national-overview"),
  nationalCapability: () => api.get<NationalCapability>("/api/reports/national-capability"),
  wingPhaseCoverage: () => api.get<WingPhaseCoverage>("/api/reports/wing-phase-coverage"),
  // Backend has computed this since before this program (ops.py's wing_capability)
  // but neither frontend rendered it -- connected-frontend fetched it and
  // silently discarded the response, Planning Workspace never fetched it at
  // all. Stage 9, 2026-08-05.
  wingCapability: () => api.get<WingCapability>("/api/reports/wing-capability"),
  wingCancellationTrend: () => api.get<WingCancellationTrend>("/api/reports/wing-cancellation-trend"),
  wingNotDelivered: () => api.get<WingNotDeliveredReport>("/api/reports/wing-not-delivered"),
};

export const opsApi = {
  actionItems: () => api.get<ActionItem[]>("/api/action-items"),
  addActionItem: (b: { title: string; description?: string; owner?: string; due_date?: string; severity?: string }) =>
    api.post<{ ok: boolean; action_id: string }>("/api/action-items", b),
  closeActionItem: (id: string) => api.post<{ ok: boolean }>(`/api/action-items/${id}/close`),
  runChecks: () => api.post<{ created: number }>("/api/exceptions/run-checks"),
  importPreview: (csv_text: string, import_type = "cadets") => api.post<ImportPreview>("/api/import/preview", { csv_text, import_type }),
  importCommit: (csv_text: string, import_type = "cadets") => api.post<ImportCommitResult>("/api/import/commit", { csv_text, import_type }),
  importRollback: (import_id: string) => api.post<{ ok: boolean; archived: number }>("/api/import/rollback", { import_id }),
};

export const accountApi = {
  list: (params: { wing_id?: string; squadron_id?: string; flight_id?: string; include_archived?: boolean } = {}) => {
    const p = new URLSearchParams();
    if (params.wing_id) p.set("wing_id", params.wing_id);
    if (params.squadron_id) p.set("squadron_id", params.squadron_id);
    if (params.flight_id) p.set("flight_id", params.flight_id);
    if (params.include_archived) p.set("include_archived", "true");
    const qs = p.toString();
    return api.get<AccountRecord[]>(`/api/accounts${qs ? `?${qs}` : ""}`);
  },
  get: (uid: string) => api.get<AccountRecord>(`/api/accounts/${uid}`),
  create: (b: { display_name: string; role: string; wing_id?: string; squadron_id?: string; national_id?: string; flight_id?: string; new_code?: string }) =>
    api.post<AccountCreateResult>("/api/accounts", b),
  update: (uid: string, b: { display_name?: string; flight_id?: string }) =>
    api.patch<{ ok: boolean }>(`/api/accounts/${uid}`, b),
  resetCode: (uid: string, new_code?: string) =>
    api.post<{ ok: boolean; new_code: string; new_code_notice: string }>(`/api/accounts/${uid}/reset-code`, new_code ? { new_code } : {}),
  disable: (uid: string) => api.post<{ ok: boolean }>(`/api/accounts/${uid}/disable`),
  reactivate: (uid: string) => api.post<{ ok: boolean }>(`/api/accounts/${uid}/reactivate`),
  // Account Management parity fixes (REM-46, 2026-08-05) -- these already
  // existed in connected-frontend; Planning Workspace's Account Management
  // page never got them.
  changeRole: (uid: string, new_role: string) =>
    api.post<{ ok: boolean }>(`/api/accounts/${uid}/change-role`, { new_role }),
  archive: (uid: string, reason?: string) =>
    api.post<{ ok: boolean }>(`/api/accounts/${uid}/archive${reason ? `?reason=${encodeURIComponent(reason)}` : ""}`),
  restore: (uid: string) => api.post<{ ok: boolean }>(`/api/accounts/${uid}/restore`),
  remove: (uid: string) => api.delete<{ ok: boolean }>(`/api/accounts/${uid}`),
  unlock: (uid: string) => api.post<{ ok: boolean }>(`/api/accounts/${uid}/unlock`),
  flights: (squadron_id?: string) => {
    const qs = squadron_id ? `?squadron_id=${encodeURIComponent(squadron_id)}` : "";
    return api.get<Flight[]>(`/api/flights${qs}`);
  },
  createFlight: (b: { name: string; squadron_id: string }) =>
    api.post<Flight & { ok: boolean }>("/api/flights", b),
  renameFlight: (fid: string, b: { name?: string; active_status?: boolean }) =>
    api.patch<{ ok: boolean }>(`/api/flights/${fid}`, b),
  archiveFlight: (fid: string) => api.post<{ ok: boolean }>(`/api/flights/${fid}/archive`),
};

export const healthApi = {
  health: () => api.get<{ status: string }>("/api/health"),
  ready: () => api.get<{ status: string }>("/api/health/ready"),
};

export const dashboardApi = {
  charts: (window: "week" | "term" | "year" = "term", squadron_id?: string) =>
    api.get<DashboardChartsResponse>(
      `/api/dashboard/charts?window=${window}${squadron_id ? `&squadron_id=${squadron_id}` : ""}`
    ),
  strategic: (window: "term" | "year" = "year") =>
    api.get<DashboardChartsResponse>(`/api/dashboard/charts/strategic?window=${window}`),
  // Wing/National Command Dashboard (Sections A/B) -- connected-frontend's
  // rich cmd-dash-wing/cmd-dash-national view; previously had no Planning
  // Workspace consumer at all (risk register: "wing/national/system admin
  // dashboards get full squadron-dashboard parity PLUS comparison").
  command: (window: "week" | "term" | "semester" | "year" = "term", wing_id?: string) =>
    api.get<import("./types").CommandDashboardResponse>(
      `/api/dashboard/command?window=${window}${wing_id ? `&wing_id=${wing_id}` : ""}`
    ),
  facilitatorSchedule: (window: "week" | "term" | "year" = "year", squadron_id?: string) =>
    api.get<import("./types").FacilitatorScheduleResponse>(
      `/api/dashboard/facilitator-schedule?window=${window}${squadron_id ? `&squadron_id=${squadron_id}` : ""}`
    ),
};

// ─── Planning Workspace API ─────────────────────────────────────────────────
export const planningApi = {
  // unit_id (squadron): required for wing/national/system_admin sessions to see a
  // specific squadron's plan -- without it, list_planning_years falls back to
  // "every squadron in the wing" (wing_admin) or "every squadron nationwide, no
  // filter at all" (national_admin/system_admin), and PlanningWorkspace.tsx used
  // to auto-pick years[0] from that undifferentiated list (Stage 10, 2026-08-05).
  years: (unit_id?: string, includeUnmaterialised = false) => {
    const q = new URLSearchParams();
    if (unit_id) q.set("unit_id", unit_id);
    // Logical years are opt-in: consumers that build /years/{id}/... URLs from
    // this list must not be handed rows whose id is null.
    if (includeUnmaterialised) q.set("include_unmaterialised", "true");
    const qs = q.toString();
    return api.get<PlanningYear[]>(`/api/planning/years${qs ? `?${qs}` : ""}`);
  },
  commandCentre: (year_id?: string) =>
    api.get<CommandCentreData>(`/api/planning/command-centre${year_id ? `?year_id=${year_id}` : ""}`),
  annualProgram: (year_id: string) =>
    api.get<AnnualProgram>(`/api/planning/years/${year_id}/annual-program`),
  longRange: (year_id: string, weeks = 8, from_date?: string, end_date?: string) => {
    const p = new URLSearchParams({ weeks: String(weeks) });
    if (from_date) p.set("from_date", from_date);
    if (end_date) p.set("end_date", end_date);
    return api.get<LongRangeView>(`/api/planning/years/${year_id}/long-range?${p}`);
  },
  weeklyProgram: (date_id: string) =>
    api.get<WeeklyProgramData>(`/api/planning/parade-dates/${date_id}/weekly-program`),
  missions: (year_id: string, opts: {
    status?: string; phase?: string; search?: string; start_date?: string; end_date?: string;
  } = {}) => {
    const p = new URLSearchParams();
    if (opts.status) p.set("status", opts.status);
    if (opts.phase) p.set("phase", opts.phase);
    if (opts.search) p.set("search", opts.search);
    if (opts.start_date) p.set("start_date", opts.start_date);
    if (opts.end_date) p.set("end_date", opts.end_date);
    const qs = p.toString();
    return api.get<{ planning_year_id: string; year: number; total: number; scheduled_count: number; missions: MissionItem[] }>(
      `/api/planning/years/${year_id}/missions${qs ? `?${qs}` : ""}`
    );
  },
  locations: () => api.get<PlanningLocation[]>("/api/planning/locations"),
  facilitators: () => api.get<PlanningFacilitator[]>("/api/planning/facilitators"),
  localLessons: () => api.get<LocalLesson[]>("/api/planning/local-lessons"),
  holidays: (year_id: string) =>
    api.get<HolidayPeriod[]>(`/api/planning/years/${year_id}/holidays`),
  createHoliday: (year_id: string, body: {
    name: string; start_date: string; end_date: string;
    holiday_type?: string; affects_parade?: boolean;
    jurisdiction?: string; notes?: string;
  }) => api.post<HolidayPeriod>(`/api/planning/years/${year_id}/holidays`, body),
  deleteHoliday: (holiday_id: string) =>
    api.delete<{ ok: boolean }>(`/api/planning/holidays/${holiday_id}`),
  conflicts: (year_id: string) =>
    api.get<unknown>(`/api/planning/years/${year_id}/conflicts`).then(parseConflictsList),
  runChecks: (year_id: string) =>
    api.post<{ ok: boolean; conflicts_detected: number }>(`/api/planning/years/${year_id}/run-checks`, {}),
  createSession: (date_id: string, body: {
    cadet_group: string; session_number: number; curriculum_id?: string;
    activity_title?: string; facilitator_id?: string; location_id?: string;
    part_number?: number; notes?: string;
  }) => api.post<Record<string, unknown>>(`/api/planning/parade-dates/${date_id}/sessions`, body),
  getSession: (session_id: string) =>
    api.get<PlanningSession>(`/api/planning/sessions/${session_id}`),
  updateSession: (session_id: string, body: {
    curriculum_id?: string | null; activity_title?: string | null;
    facilitator_id?: string | null; assistant_facilitator_id?: string | null;
    location_id?: string | null; cadet_group?: string | null;
    part_number?: number | null; notes?: string | null;
  }) => api.patch<Record<string, unknown>>(`/api/planning/sessions/${session_id}`, body),
  deleteSession: (session_id: string) =>
    api.delete<{ ok: boolean }>(`/api/planning/sessions/${session_id}`),
  restoreSession: (session_id: string) =>
    api.post<{ ok: boolean }>(`/api/planning/sessions/${session_id}/restore`, {}),
  archivedSessions: (date_id: string) =>
    api.get<{ sessions: PlanningSession[] }>(`/api/planning/parade-dates/${date_id}/archived-sessions`),
  overrideConflict: (conflict_id: string, override_reason: string) =>
    api.post<{ ok: boolean }>(`/api/planning/conflicts/${conflict_id}/override`, { override_reason }),
  wingEvents: (wing_id: string, year: number, squadron_id?: string) => {
    const p = new URLSearchParams({ wing_id, year: String(year) });
    if (squadron_id) p.set("squadron_id", squadron_id);
    return api.get<WingHQEvent[]>(`/api/wing-calendar/squadron-overlay?${p}`);
  },
  reviewWingEvent: (event_id: string, status: string, notes?: string) =>
    api.patch<{ ok: boolean }>(`/api/wing-calendar/events/${event_id}/squadron-status`, { status, notes }),
  getWingEvent: (event_id: string) =>
    api.get<WingHQEvent>(`/api/wing-calendar/events/${event_id}`),
  createYear: (body: { year: number; name: string; unit_id?: string }) =>
    api.post<PlanningYear>("/api/planning/years", body),
  generateParadeDates: (year_id: string, body: {
    weekday: number; start_date: string; end_date?: string;
    parade_type?: string; exclude_holidays?: boolean;
    frequency?: string; max_repeats?: number; excluded_dates?: string[];
    parade_start_time?: string; parade_end_time?: string;
  }) => api.post<{ ok: boolean; created: number; linked: number; dates: string[] }>(
    `/api/planning/years/${year_id}/generate-parade-dates`, body,
  ),
  rolloverYear: (year_id: string, body: {
    target_year?: number; name?: string;
    copy_holidays?: boolean; carry_incomplete_sessions?: boolean;
    // CLASS-11: defaults true on the backend, same as the other copy_* flags
    // -- no UI toggle exists for any of them (GuidedYearSetupModal.tsx calls
    // this with an empty body), so this is exposed for completeness/type
    // accuracy rather than because a caller currently sets it.
    copy_training_classes?: boolean;
  }) => api.post<{
    ok: boolean; new_planning_year_id: string; year: number; name: string;
    holidays_copied: number; parade_dates_copied: number; incomplete_sessions_noted: number;
    training_classes_copied: number;
  }>(`/api/planning/years/${year_id}/rollover`, body),
  listTimingTemplates: (squadron_id?: string) =>
    api.get<import("./types").TimingTemplateFull[]>(`/api/timing-templates${squadron_id ? `?squadron_id=${squadron_id}` : ""}`),
  applyTimingTemplateFromDate: (template_id: string, body: { effective_from: string; reason?: string }) =>
    api.post<{ ok: boolean; effective_from: string; closed_previous_count: number }>(
      `/api/timing-templates/${template_id}/apply-from-date`, body,
    ),
  updateFutureParadeDay: (year_id: string, body: {
    new_weekday: number; from_date?: string; exclude_ids?: string[];
    reason?: string; preview?: boolean;
  }) => api.post<{
    ok: boolean; preview: boolean;
    changes?: { parade_date_id: string; old_date: string; new_date: string; term: string | null;
      week_number: number | null; has_sessions: boolean; conflicts: string[]; blocked: boolean }[];
    to_update?: number; blocked?: number;
    updated?: number; skipped?: number; exceptions_preserved: number;
  }>(`/api/planning/years/${year_id}/update-future-parade-day`, body),
  listAnchors: (year_id: string) =>
    api.get<AnchorEvent[]>(`/api/planning/years/${year_id}/anchors`),
  createAnchor: (year_id: string, body: {
    event_name: string; event_type?: string; importance?: string;
    start_date: string; end_date?: string;
    audience_orientation?: boolean; audience_initial?: boolean;
    audience_junior?: boolean; audience_intermediate?: boolean; audience_senior?: boolean;
    planning_impact?: string; notes?: string;
  }) => api.post<Record<string, unknown>>(`/api/planning/years/${year_id}/anchors`, body),
  createLocation: (body: { name: string; location_type?: string; capacity?: number; notes?: string }) =>
    api.post<PlanningLocation>("/api/planning/locations", body),
  updateLocation: (location_id: string, body: {
    name?: string; location_type?: string; capacity?: number;
    notes?: string; active_status?: boolean;
  }) => api.patch<PlanningLocation>(`/api/planning/locations/${location_id}`, body),

  // ── Night summaries ─────────────────────────────────────────────────────────
  nightSummaries: (year_id: string) =>
    api.get<NightSummariesResponse>(`/api/planning/years/${year_id}/night-summaries`),

  // ── Facilitator Leave ───────────────────────────────────────────────────────
  facilitatorLeave: (fac_id: string, includeArchived = false) =>
    api.get<{ leave: PlanningFacilitatorLeave[] }>(`/api/planning/facilitators/${fac_id}/leave${includeArchived ? "?include_archived=true" : ""}`),
  addFacilitatorLeave: (fac_id: string, body: { start_date: string; end_date: string; reason?: string; notes?: string }) =>
    api.post<FacilitatorLeaveResult>(`/api/planning/facilitators/${fac_id}/leave`, body),
  deleteFacilitatorLeave: (leave_id: string) =>
    api.delete<{ ok: boolean }>(`/api/planning/facilitator-leave/${leave_id}`),
  restoreFacilitatorLeave: (leave_id: string) =>
    api.post<{ ok: boolean }>(`/api/planning/facilitator-leave/${leave_id}/restore`, {}),

  // ── Facilitator Workload ────────────────────────────────────────────────────
  facilitatorWorkload: (year_id: string, fac_id: string) =>
    api.get<FacilitatorWorkload>(`/api/planning/years/${year_id}/facilitators/${fac_id}/workload`),

  // ── Facilitator create (via training endpoint) ──────────────────────────────
  createFacilitator: (body: { first_name: string; last_name: string; current_rank?: string; type?: string; subject_areas?: string[]; confirm_duplicate?: boolean }) =>
    api.post<{ ok: boolean; facilitator_id: string }>('/api/facilitators', body),

  // ── Equipment ───────────────────────────────────────────────────────────────
  listEquipment: () => api.get<EquipmentItem[]>('/api/equipment'),
  addEquipment: (body: { name: string; type?: string; quantity?: number; available_quantity?: number; notes?: string }) =>
    api.post<{ ok: boolean }>('/api/equipment', body),

  // ── Notices ─────────────────────────────────────────────────────────────────
  listNotices: (date_id: string) =>
    api.get<import("./types").ParadeNotice[]>(`/api/planning/parade-dates/${date_id}/notices`),
  createNotice: (date_id: string, body: { notice_text: string; priority?: string; audience?: string }) =>
    api.post<{ ok: boolean; notice_id: string }>(`/api/planning/parade-dates/${date_id}/notices`, body),
  updateNotice: (notice_id: string, body: { notice_text?: string; priority?: string; audience?: string }) =>
    api.patch<{ ok: boolean }>(`/api/planning/notices/${notice_id}`, body),
  archiveNotice: (notice_id: string) =>
    api.post<{ ok: boolean }>(`/api/planning/notices/${notice_id}/archive`, {}),

  // ── Anchors (update / delete) ────────────────────────────────────────────────
  updateAnchor: (anchor_id: string, body: Record<string, unknown>) =>
    api.patch<Record<string, unknown>>(`/api/planning/anchors/${anchor_id}`, body),
  deleteAnchor: (anchor_id: string) =>
    api.delete<{ ok: boolean }>(`/api/planning/anchors/${anchor_id}`),

  // ── CEA Activities ───────────────────────────────────────────────────────────
  ceaActivities: (year_id: string, status?: string) =>
    api.get<import("./types").CeaActivity[]>(
      `/api/planning/years/${year_id}/cea/activities${status ? `?status=${status}` : ""}`,
    ).then(r => (Array.isArray(r) ? r : (r as { activities: import("./types").CeaActivity[] }).activities)),
  ceaBatches: (year_id: string) =>
    api.get<{ batches: import("./types").CeaImportBatch[] }>(`/api/planning/years/${year_id}/cea/batches`),
  ceaImport: (year_id: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api.postForm<import("./types").CeaImportResult>(`/api/planning/years/${year_id}/cea/import`, form);
  },
  ceaClassify: (
    activity_id: string,
    body: { importance?: string; audience_staff_only?: boolean; audience_seniors?: boolean; audience_proficient?: boolean; audience_first_years?: boolean },
  ) => api.patch<{ ok: boolean }>(`/api/planning/cea/${activity_id}/classify`, body),
  ceaLocalHide: (activity_id: string, body: { is_hidden: boolean; local_note?: string }) =>
    api.post<{ ok: boolean }>(`/api/planning/cea/${activity_id}/local-hide`, body),
  createManualActivity: (year_id: string, body: Record<string, unknown>) =>
    api.post<{ ok: boolean; id: string }>(`/api/planning/years/${year_id}/cea/activities`, body),
};
