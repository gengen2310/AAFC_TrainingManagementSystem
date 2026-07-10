import { api } from "./client";
import type {
  SessionInfo, Squadron, Wing, UserRecord, AccountRecord, AccountCreateResult, Flight,
  CurriculumItem, ParadeNightWithSessions, ParadeNightDetail,
  SessionRow, Facilitator, FacilitatorStats, TrainingArea, Equipment, ClashResult, Cadet,
  CadetRiskFlag, AuditRow, ActionItem, SummaryReport, ReadinessReport, CoverageReport,
  FacLoadReport, NotDeliveredReport, WingOverview, NationalOverview, NationalCapability,
  WingPhaseCoverage, ImportPreview, ImportCommitResult,
  PlanningYear, AnnualProgram, LongRangeView, WeeklyProgramData,
  MissionItem, PlanningLocation, PlanningFacilitator, LocalLesson,
  WingHQEvent, CommandCentreData, PlanningConflict, HolidayPeriod,
  NightSummariesResponse, PlanningFacilitatorLeave, FacilitatorLeaveResult,
  FacilitatorWorkload, EquipmentItem, AnchorEvent,
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
  login: (code: string) => api.post<{ token: string; session: SessionInfo }>("/api/auth/login", { code }),
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

export const trainingApi = {
  curriculum: () => api.get<{ items: CurriculumItem[] }>("/api/curriculum"),
  curriculumSessions: (cid: string) => api.get<SessionRow[]>(`/api/curriculum/${cid}/sessions`),
  paradeNights: (squadron_id?: string) => api.get<ParadeNightWithSessions[]>(`/api/parade-nights${squadron_id ? `?squadron_id=${squadron_id}` : ""}`),
  paradeNight: (id: string) => api.get<ParadeNightDetail>(`/api/parade-nights/${id}`),
  createParadeNight: (b: { date: string; term?: number; session_count?: number; parade_type?: string }) =>
    api.post<{ ok: boolean; parade_night_id: string }>("/api/parade-nights", b),
  publish: (id: string) => api.post<{ ok: boolean }>(`/api/parade-nights/${id}/publish`),
  close: (id: string) => api.post<{ ok: boolean }>(`/api/parade-nights/${id}/close`),
  createSession: (b: Record<string, unknown>) => api.post<{ ok: boolean; session_id: string }>("/api/sessions", b),
  editSession: (id: string, b: Record<string, unknown>) => api.put<{ ok: boolean }>(`/api/sessions/${id}`, b),
  setStatus: (id: string, b: { status: string; reason?: string; rescheduled_to_date?: string; actual_attendance?: number }) =>
    api.post<{ ok: boolean }>(`/api/sessions/${id}/status`, b),
  facilitators: () => api.get<Facilitator[]>("/api/facilitators"),
  addFacilitator: (b: { first_name: string; last_name: string; current_rank?: string; type?: string; subject_areas?: string[] }) =>
    api.post<{ ok: boolean; facilitator_id: string }>("/api/facilitators", b),
  updateFacilitator: (id: string, b: { subject_areas?: string[]; type?: string; current_rank?: string }) =>
    api.patch<{ ok: boolean; facilitator_id: string; subject_areas: string[] }>(`/api/facilitators/${id}`, b),
  facilitatorStats: (id: string) => api.get<FacilitatorStats>(`/api/facilitators/${id}/stats`),
  trainingAreas: () => api.get<TrainingArea[]>("/api/training-areas"),
  equipment: () => api.get<Equipment[]>("/api/equipment"),
  clashes: (date: string) => api.get<ClashResult>(`/api/resources/clashes?date=${date}`),
  cadets: () => api.get<Cadet[]>("/api/cadets"),
  cadetRisk: () => api.get<CadetRiskFlag[]>("/api/cadets/risk"),
};

export const reportApi = {
  summary: () => api.get<SummaryReport>("/api/reports/summary"),
  readiness: () => api.get<ReadinessReport>("/api/reports/readiness"),
  coverage: () => api.get<CoverageReport>("/api/reports/curriculum-coverage"),
  facLoad: () => api.get<FacLoadReport>("/api/reports/facilitator-load"),
  notDelivered: () => api.get<NotDeliveredReport>("/api/reports/not-delivered"),
  wingOverview: () => api.get<WingOverview>("/api/reports/wing-overview"),
  nationalOverview: () => api.get<NationalOverview>("/api/reports/national-overview"),
  nationalCapability: () => api.get<NationalCapability>("/api/reports/national-capability"),
  wingPhaseCoverage: () => api.get<WingPhaseCoverage>("/api/reports/wing-phase-coverage"),
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
  list: (params: { wing_id?: string; squadron_id?: string; flight_id?: string } = {}) => {
    const p = new URLSearchParams();
    if (params.wing_id) p.set("wing_id", params.wing_id);
    if (params.squadron_id) p.set("squadron_id", params.squadron_id);
    if (params.flight_id) p.set("flight_id", params.flight_id);
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

// ─── Planning Workspace API ─────────────────────────────────────────────────
export const planningApi = {
  years: () => api.get<PlanningYear[]>("/api/planning/years"),
  commandCentre: (year_id?: string) =>
    api.get<CommandCentreData>(`/api/planning/command-centre${year_id ? `?year_id=${year_id}` : ""}`),
  annualProgram: (year_id: string) =>
    api.get<AnnualProgram>(`/api/planning/years/${year_id}/annual-program`),
  longRange: (year_id: string, weeks = 8, from_date?: string) => {
    const p = new URLSearchParams({ weeks: String(weeks) });
    if (from_date) p.set("from_date", from_date);
    return api.get<LongRangeView>(`/api/planning/years/${year_id}/long-range?${p}`);
  },
  weeklyProgram: (date_id: string) =>
    api.get<WeeklyProgramData>(`/api/planning/parade-dates/${date_id}/weekly-program`),
  missions: (year_id: string, opts: { status?: string; phase?: string; search?: string } = {}) => {
    const p = new URLSearchParams();
    if (opts.status) p.set("status", opts.status);
    if (opts.phase) p.set("phase", opts.phase);
    if (opts.search) p.set("search", opts.search);
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
  updateSession: (session_id: string, body: {
    curriculum_id?: string | null; activity_title?: string | null;
    facilitator_id?: string | null; assistant_facilitator_id?: string | null;
    location_id?: string | null; cadet_group?: string | null;
    part_number?: number | null; notes?: string | null;
  }) => api.patch<Record<string, unknown>>(`/api/planning/sessions/${session_id}`, body),
  deleteSession: (session_id: string) =>
    api.delete<{ ok: boolean }>(`/api/planning/sessions/${session_id}`),
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
  createYear: (body: { year: number; name: string }) =>
    api.post<PlanningYear>("/api/planning/years", body),
  generateParadeDates: (year_id: string, body: {
    weekday: number; start_date: string; end_date?: string;
    parade_type?: string; exclude_holidays?: boolean;
    frequency?: string; max_repeats?: number; excluded_dates?: string[];
  }) => api.post<{ ok: boolean; created: number; linked: number; dates: string[] }>(
    `/api/planning/years/${year_id}/generate-parade-dates`, body,
  ),
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
  facilitatorLeave: (fac_id: string) =>
    api.get<{ leave: PlanningFacilitatorLeave[] }>(`/api/planning/facilitators/${fac_id}/leave`),
  addFacilitatorLeave: (fac_id: string, body: { start_date: string; end_date: string; reason?: string; notes?: string }) =>
    api.post<FacilitatorLeaveResult>(`/api/planning/facilitators/${fac_id}/leave`, body),
  deleteFacilitatorLeave: (leave_id: string) =>
    api.delete<{ ok: boolean }>(`/api/planning/facilitator-leave/${leave_id}`),

  // ── Facilitator Workload ────────────────────────────────────────────────────
  facilitatorWorkload: (year_id: string, fac_id: string) =>
    api.get<FacilitatorWorkload>(`/api/planning/years/${year_id}/facilitators/${fac_id}/workload`),

  // ── Facilitator create (via training endpoint) ──────────────────────────────
  createFacilitator: (body: { first_name: string; last_name: string; current_rank?: string; type?: string; subject_areas?: string[] }) =>
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
