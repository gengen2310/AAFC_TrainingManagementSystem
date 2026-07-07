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
  WingHQEvent, CommandCentreData, PlanningConflict,
} from "./types";

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
  conflicts: (year_id: string) =>
    api.get<{ conflicts: PlanningConflict[] }>(`/api/planning/years/${year_id}/conflicts`),
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
};
