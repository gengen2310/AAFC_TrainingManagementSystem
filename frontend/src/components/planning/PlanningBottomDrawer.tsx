import { useState, useMemo, useEffect } from "react";
import type { CSSProperties } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { planningApi, trainingApi, dashboardApi } from "../../api";
import { ApiError, friendlyMessage } from "../../api/client";
import { ImportFacilitatorsModal } from "./ImportFacilitatorsModal";
import { FacilitatorTimeline, type ZoomPreset } from "../charts/FacilitatorTimeline";
import { FacilitatorScheduleList } from "../charts/FacilitatorScheduleList";
import { Loading, ErrorNote } from "../ui";
import { getProgramType } from "../../utils/planningFilters";
import { useAuth } from "../../auth/AuthProvider";
import { isSystemAdmin } from "../../auth/permissions";
import { useConfirm } from "../ConfirmDialog";
import type {
  PlanningFacilitator, PlanningLocation,
  PlanningFacilitatorLeave, FacilitatorWorkload, EquipmentItem,
} from "../../api/types";
import type { DrawerItem } from "./PlanningRightDrawer";

export type BottomTab =
  | "backlog"
  | "facilitators"
  | "schedule"
  | "rooms"
  | "equipment"
  | "holidays"
  | "notices"
  | "activities";

interface Props {
  yearId: string | null;
  tab: BottomTab;
  onTabChange: (t: BottomTab) => void;
  onClose: () => void;
  facilitators: PlanningFacilitator[];
  locations: PlanningLocation[];
  onItemClick: (item: DrawerItem) => void;
  squadronId?: string;
}

const TABS: { key: BottomTab; label: string }[] = [
  { key: "activities", label: "Activities" },
  { key: "backlog", label: "Mission Backlog" },
  { key: "facilitators", label: "Facilitators" },
  { key: "schedule", label: "Schedule" },
  { key: "rooms", label: "Rooms" },
  { key: "equipment", label: "Equipment" },
  { key: "holidays", label: "Holidays" },
  { key: "notices", label: "Notices" },
];

// ─── Styles helpers ───────────────────────────────────────────────────────────

const inputSx: CSSProperties = {
  padding: "5px 8px", borderRadius: 6,
  border: "1.5px solid var(--border)", fontSize: 12, width: "100%",
};
const labelSx: CSSProperties = {
  fontSize: 12, fontWeight: 700,
  display: "flex", flexDirection: "column", gap: 4,
};

// ─── BacklogContent ───────────────────────────────────────────────────────────

type SortDir = "asc" | "desc";


const PROG_TYPE_STYLE: Record<string, CSSProperties> = {
  foundation: { fontSize: 9, fontWeight: 700, color: "#1A7F4B", background: "#d1fae5", padding: "1px 5px", borderRadius: 3, whiteSpace: "nowrap" },
  extension:  { fontSize: 9, fontWeight: 700, color: "#92400e", background: "#fef3c7", padding: "1px 5px", borderRadius: 3, whiteSpace: "nowrap" },
  optional:   { fontSize: 9, fontWeight: 700, color: "#6b7a87", background: "#f1f5f9", padding: "1px 5px", borderRadius: 3, whiteSpace: "nowrap" },
};

// CLASS-05: per-Training-Class chips in the backlog table, reusing the same
// six-state palette as the existing item-level Status column (kept as a
// separate style map rather than refactoring that column, to avoid touching
// already-shipped, already-tested rendering for an additive feature).
const CLASS_STATUS_STYLE: Record<string, CSSProperties> = {
  resolved: { color: "#fff", background: "var(--success, #1A7F4B)" },
  not_delivered_awaiting_reschedule: { color: "#fff", background: "#78909c" },
  cancelled_awaiting_reschedule: { color: "#fff", background: "var(--aafc-red)" },
  rescheduled: { color: "#fff", background: "var(--rescheduled, #7C3AED)" },
  planned: { color: "var(--success, #1A7F4B)", background: "#d1fae5" },
  unscheduled: { color: "var(--muted-text)", background: "var(--surface-2, #f1f5f9)" },
};
const CLASS_STATUS_LABEL: Record<string, string> = {
  resolved: "Resolved", not_delivered_awaiting_reschedule: "Not delivered",
  cancelled_awaiting_reschedule: "Cancelled", rescheduled: "Rescheduled",
  planned: "Scheduled", unscheduled: "Unscheduled",
};
function classChipStyle(status: string): CSSProperties {
  return {
    ...(CLASS_STATUS_STYLE[status] ?? CLASS_STATUS_STYLE.unscheduled),
    fontSize: 9, fontWeight: 700, padding: "1px 6px", borderRadius: 3, whiteSpace: "nowrap",
  };
}

const SUITABILITY_SHORT: Record<string, string> = {
  "Staff": "Staff",
  "Staff or Senior Cadet": "Staff / Sr Cdt",
  "Senior Cadet": "Sr Cdt",
  "Any Cadet": "Any Cdt",
};

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

function BacklogContent({ yearId, onItemClick }: { yearId: string; onItemClick: (item: DrawerItem) => void }) {
  const queryClient = useQueryClient();
  const { confirm } = useConfirm();
  const [reschedulingId, setReschedulingId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [sortCol, setSortCol] = useState("phase");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [fPhase, setFPhase] = useState("");
  const [fElement, setFElement] = useState("");
  const [fSuitability, setFSuitability] = useState("");
  const [fStatus, setFStatus] = useState("unscheduled");
  const [fCore, setFCore] = useState("");
  const [fTerm, setFTerm] = useState("");
  const [fDateStart, setFDateStart] = useState("");
  const [fDateEnd, setFDateEnd] = useState("");

  const { data, isLoading, error } = useQuery({
    queryKey: ["planning-missions", yearId, "backlog"],
    queryFn: () => planningApi.missions(yearId),
    staleTime: 3 * 60 * 1000,
  });

  const opts = useMemo(() => {
    if (!data) return { phases: [], elements: [], suitabilities: [], terms: [] };
    const phases = [...new Set(data.missions.map(m => m.phase))].sort();
    const elements = [...new Set(data.missions.map(m => m.element).filter(Boolean))].sort() as string[];
    const suitabilities = [...new Set(data.missions.map(m => m.instructor_suitability).filter(Boolean))].sort() as string[];
    const terms = [...new Set(data.missions.map(m => m.recommended_term).filter(Boolean))].sort() as string[];
    return { phases, elements, suitabilities, terms };
  }, [data]);

  const displayed = useMemo(() => {
    if (!data) return [];
    const q = search.toLowerCase();
    let rows = data.missions.filter(m => {
      if (fPhase && m.phase !== fPhase) return false;
      if (fElement && m.element !== fElement) return false;
      if (fSuitability && m.instructor_suitability !== fSuitability) return false;
      if (fCore && getProgramType(m.phase) !== fCore) return false;
      if (fTerm && m.recommended_term !== fTerm) return false;
      if (fStatus === "scheduled" && !m.is_scheduled) return false;
      if (fStatus === "unscheduled" && m.is_scheduled) return false;
      // "Cancelled"/"Not delivered" mean "currently awaiting reschedule", not "has
      // ever had this status" — has_cancelled/has_not_delivered stay true forever
      // even once a mission is resolved, which previously made a resolved mission
      // still match these two filters alongside "Resolved", confusingly implying
      // it still needed action. Match backlog_status like the other four filters.
      if (fStatus === "cancelled" && m.backlog_status !== "cancelled_awaiting_reschedule") return false;
      if (fStatus === "not_delivered" && m.backlog_status !== "not_delivered_awaiting_reschedule") return false;
      if (fStatus === "rescheduled" && m.backlog_status !== "rescheduled") return false;
      if (fStatus === "resolved" && m.backlog_status !== "resolved") return false;
      if (fStatus === "planned" && m.backlog_status !== "planned") return false;
      if (q && !m.code.toLowerCase().includes(q) && !m.title.toLowerCase().includes(q)) return false;
      // TRGO-08: date-range filter. An unscheduled mission has no date to match
      // against and always needs attention, so it is never hidden by this filter
      // -- only scheduled missions are narrowed to those with a session in range.
      if ((fDateStart || fDateEnd) && m.is_scheduled) {
        const inRange = m.scheduled_sessions.some(s => {
          if (!s.parade_date) return false;
          if (fDateStart && s.parade_date < fDateStart) return false;
          if (fDateEnd && s.parade_date > fDateEnd) return false;
          return true;
        });
        if (!inRange) return false;
      }
      return true;
    });

    rows = [...rows].sort((a, b) => {
      let av: string | number = "";
      let bv: string | number = "";
      if (sortCol === "phase") { av = a.phase; bv = b.phase; }
      else if (sortCol === "code") { av = a.code; bv = b.code; }
      else if (sortCol === "title") { av = a.title; bv = b.title; }
      else if (sortCol === "element") { av = a.element ?? ""; bv = b.element ?? ""; }
      else if (sortCol === "suitability") { av = a.instructor_suitability ?? ""; bv = b.instructor_suitability ?? ""; }
      else if (sortCol === "duration") { av = a.duration_minutes; bv = b.duration_minutes; }
      else if (sortCol === "term") { av = a.recommended_term ?? ""; bv = b.recommended_term ?? ""; }
      else if (sortCol === "status") { av = a.is_scheduled ? 1 : 0; bv = b.is_scheduled ? 1 : 0; }
      else if (sortCol === "date") {
        av = a.scheduled_sessions[0]?.parade_date ?? "";
        bv = b.scheduled_sessions[0]?.parade_date ?? "";
      }
      const cmp = av < bv ? -1 : av > bv ? 1 : 0;
      return sortDir === "asc" ? cmp : -cmp;
    });
    return rows;
  }, [data, search, fPhase, fElement, fSuitability, fCore, fTerm, fStatus, fDateStart, fDateEnd, sortCol, sortDir]);

  function handleSort(col: string) {
    if (sortCol === col) setSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSortCol(col); setSortDir("asc"); }
  }

  function SortHdr({ col, label, style }: { col: string; label: string; style?: CSSProperties }) {
    const active = sortCol === col;
    return (
      <th
        onClick={() => handleSort(col)}
        style={{ cursor: "pointer", userSelect: "none", whiteSpace: "nowrap", ...style }}
      >
        {label}{active ? (sortDir === "asc" ? " ▲" : " ▼") : ""}
      </th>
    );
  }

  const selSx: CSSProperties = {
    fontSize: 11, padding: "2px 4px", borderRadius: 4,
    border: "1px solid var(--border)", width: "100%", background: "#fff",
  };

  if (isLoading) return <div className="pw-loading" style={{ padding: "20px" }}>Loading missions…</div>;
  if (error || !data) {
    const msg = friendlyMessage(error, "Unknown error");
    return (
      <div className="pw-err" style={{ padding: 16 }}>
        <div style={{ fontWeight: 700, marginBottom: 4 }}>Could not load the mission backlog</div>
        <div style={{ fontSize: 12, opacity: .8 }}>{msg}</div>
        <div style={{ fontSize: 11, marginTop: 6, color: "var(--muted-text)" }}>
          Check that you have an internet connection, then reload the page.
        </div>
      </div>
    );
  }

  const total = data.missions.length;
  const scheduledCount = data.scheduled_count;

  return (
    <div>
      {/* Toolbar */}
      <div style={{
        padding: "6px 14px", background: "var(--surface)", borderBottom: "1px solid var(--border)",
        display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap",
      }}>
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search code or title…"
          style={{ ...inputSx, width: 190 }}
        />
        <select value={fStatus} onChange={e => setFStatus(e.target.value)} style={{ ...inputSx, width: 130 }}>
          <option value="">All statuses</option>
          <option value="unscheduled">Unscheduled</option>
          <option value="scheduled">Scheduled</option>
          <option value="planned">Planned</option>
          <option value="cancelled">Cancelled</option>
          <option value="not_delivered">Not delivered</option>
          <option value="rescheduled">Rescheduled</option>
          <option value="resolved">Resolved</option>
        </select>
        <select value={fPhase} onChange={e => setFPhase(e.target.value)} style={{ ...inputSx, width: 150 }}>
          <option value="">All phases</option>
          {opts.phases.map(p => <option key={p} value={p}>{p}</option>)}
        </select>
        <select value={fElement} onChange={e => setFElement(e.target.value)} style={{ ...inputSx, width: 140 }}>
          <option value="">All elements</option>
          {opts.elements.map(e => <option key={e} value={e}>{e.replace(/_/g, " ")}</option>)}
        </select>
        <select value={fSuitability} onChange={e => setFSuitability(e.target.value)} style={{ ...inputSx, width: 140 }}>
          <option value="">All instructors</option>
          {opts.suitabilities.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={fCore} onChange={e => setFCore(e.target.value)} style={{ ...inputSx, width: 120 }}>
          <option value="">All types</option>
          <option value="foundation">Foundation</option>
          <option value="extension">Extension</option>
          <option value="optional">Optional</option>
        </select>
        {opts.terms.length > 0 && (
          <select value={fTerm} onChange={e => setFTerm(e.target.value)} style={{ ...inputSx, width: 110 }}>
            <option value="">All terms</option>
            {opts.terms.map(t => <option key={t} value={t}>Term {t}</option>)}
          </select>
        )}
        <label style={{ fontSize: 11, color: "var(--muted-text)", display: "flex", alignItems: "center", gap: 4 }}>
          From
          <input type="date" value={fDateStart} onChange={e => setFDateStart(e.target.value)} style={{ ...inputSx, width: 130 }} aria-label="Scheduled from date" />
        </label>
        <label style={{ fontSize: 11, color: "var(--muted-text)", display: "flex", alignItems: "center", gap: 4 }}>
          To
          <input type="date" value={fDateEnd} onChange={e => setFDateEnd(e.target.value)} style={{ ...inputSx, width: 130 }} aria-label="Scheduled to date" />
        </label>
        <button
          className="btn sm out"
          style={{ fontSize: 11, padding: "3px 8px", whiteSpace: "nowrap" }}
          onClick={() => { setSearch(""); setFPhase(""); setFElement(""); setFSuitability(""); setFCore(""); setFTerm(""); setFStatus("unscheduled"); setFDateStart(""); setFDateEnd(""); }}
        >
          Reset
        </button>
        <span style={{ fontSize: 11, color: "var(--muted-text)", marginLeft: "auto", whiteSpace: "nowrap" }}>
          {displayed.length} of {total} · {scheduledCount} scheduled
        </span>
      </div>

      {/* Table */}
      {displayed.length === 0 ? (
        <div className="pw-empty" style={{ padding: "20px" }}>
          {fStatus === "unscheduled" && data.missions.every(m => m.is_scheduled)
            ? "All curriculum is scheduled."
            : "No items match your filters."}
        </div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table className="pw-fac-table" style={{ fontSize: 11, minWidth: 1100 }}>
            <thead>
              <tr>
                <SortHdr col="code" label="Code" style={{ minWidth: 80 }} />
                <SortHdr col="title" label="Title" style={{ minWidth: 200 }} />
                <SortHdr col="phase" label="Phase" style={{ minWidth: 120 }} />
                <SortHdr col="element" label="Element" style={{ minWidth: 110 }} />
                <SortHdr col="suitability" label="Instructor" style={{ minWidth: 100 }} />
                <SortHdr col="duration" label="Dur." style={{ minWidth: 50 }} />
                <SortHdr col="term" label="Rec. Term" style={{ minWidth: 80 }} />
                <th style={{ minWidth: 80 }}>Type</th>
                <SortHdr col="status" label="Status" style={{ minWidth: 90 }} />
                <SortHdr col="date" label="Date" style={{ minWidth: 80 }} />
                <th style={{ minWidth: 50 }}>Period</th>
                <th style={{ minWidth: 90 }}>Group</th>
                <th style={{ minWidth: 110 }}>Facilitator</th>
                <th style={{ minWidth: 90 }}>Room</th>
                <th style={{ minWidth: 70 }}>Warnings</th>
                <th style={{ minWidth: 110 }}>Classes</th>
                <th style={{ minWidth: 80 }}></th>
              </tr>
            </thead>
            <tbody>
              {displayed.map(m => {
                const s0 = m.scheduled_sessions[0] ?? null;
                const extraSessions = m.scheduled_sessions.length - 1;
                const partCount = m.part_count ?? 1;
                const isPartial = m.is_scheduled && m.scheduled_count < partCount;

                const warnNoFac = m.is_scheduled && s0 && !s0.facilitator_id;
                const warnNoRoom = m.is_scheduled && s0 && !s0.location_id;
                const progType = getProgramType(m.phase);
                const warnCoreUnsched = !m.is_scheduled && progType === "foundation";

                return (
                  <tr key={m.curriculum_id}>
                    {/* Code */}
                    <td style={{ fontWeight: 700, color: "var(--aafc-dark-blue)", whiteSpace: "nowrap" }}>{m.code}</td>
                    {/* Title */}
                    <td style={{ maxWidth: 240 }}>{m.title}</td>
                    {/* Phase */}
                    <td style={{ color: "var(--muted-text)" }}>{m.phase}</td>
                    {/* Element */}
                    <td>{m.element ? m.element.replace(/_/g, " ") : "—"}</td>
                    {/* Instructor suitability */}
                    <td>{m.instructor_suitability ? (SUITABILITY_SHORT[m.instructor_suitability] ?? m.instructor_suitability) : "—"}</td>
                    {/* Duration */}
                    <td style={{ textAlign: "center", whiteSpace: "nowrap" }}>{m.duration_minutes}m</td>
                    {/* Rec. Term */}
                    <td style={{ textAlign: "center" }}>{m.recommended_term ?? "—"}</td>
                    {/* Type */}
                    <td style={{ textAlign: "center" }}>
                      <span style={PROG_TYPE_STYLE[progType]}>
                        {progType.toUpperCase()}
                      </span>
                    </td>
                    {/* Status — see backlog_status's six-state model (backend/app/routers/planning.py) */}
                    <td>
                      {m.backlog_status === "resolved" ? (
                        <span title={`Previously ${m.has_cancelled ? "cancelled" : "not delivered"}, now delivered.${s0?.outcome_note ? " " + s0.outcome_note : ""}`} style={{ color: "#fff", background: "var(--success, #1A7F4B)", fontWeight: 700, fontSize: 9, padding: "1px 6px", borderRadius: 3, whiteSpace: "nowrap" }}>
                          RESOLVED
                        </span>
                      ) : m.has_not_delivered ? (
                        <span title={[s0?.not_delivered_reason, s0?.outcome_note].filter(Boolean).join(" — ") || "No reason recorded"} style={{ color: "#fff", background: "#78909c", fontWeight: 700, fontSize: 9, padding: "1px 6px", borderRadius: 3, whiteSpace: "nowrap" }}>
                          NOT DELIVERED
                        </span>
                      ) : m.has_cancelled ? (
                        <span title={[s0?.cancelled_reason, s0?.outcome_note].filter(Boolean).join(" — ") || "No reason recorded"} style={{ color: "#fff", background: "var(--aafc-red)", fontWeight: 700, fontSize: 9, padding: "1px 6px", borderRadius: 3, whiteSpace: "nowrap" }}>
                          CANCELLED
                        </span>
                      ) : m.backlog_status === "rescheduled" ? (
                        <span title={s0?.rescheduled_to_date ? `Rescheduled to ${fmtDate(s0.rescheduled_to_date)}` : "Rescheduled"} style={{ color: "#fff", background: "var(--rescheduled, #7C3AED)", fontWeight: 700, fontSize: 9, padding: "1px 6px", borderRadius: 3, whiteSpace: "nowrap" }}>
                          RESCHEDULED
                        </span>
                      ) : !m.is_scheduled ? (
                        <span style={{ color: "var(--muted-text)", fontWeight: 600 }}>Unscheduled</span>
                      ) : isPartial ? (
                        <span style={{ color: "var(--warning, #d97706)", fontWeight: 600 }}>Partial {m.scheduled_count}/{partCount}</span>
                      ) : (
                        <span style={{ color: "var(--success, #1A7F4B)", fontWeight: 600 }}>
                          Scheduled{m.scheduled_count > 1 ? ` ×${m.scheduled_count}` : ""}
                        </span>
                      )}
                    </td>
                    {/* Date */}
                    <td style={{ whiteSpace: "nowrap" }}>
                      {s0 ? (
                        <span>
                          {fmtDate(s0.parade_date)}
                          {extraSessions > 0 && (
                            <span style={{ fontSize: 9, color: "var(--muted-text)", marginLeft: 3 }}>+{extraSessions}</span>
                          )}
                        </span>
                      ) : "—"}
                    </td>
                    {/* Period */}
                    <td style={{ textAlign: "center" }}>{s0 ? `P${s0.session_number}` : "—"}</td>
                    {/* Group */}
                    <td style={{ textTransform: "capitalize" }}>{s0?.cadet_group ?? "—"}</td>
                    {/* Facilitator */}
                    <td>
                      {s0?.facilitator_name ?? (s0 ? <span style={{ color: "var(--muted-text)" }}>None</span> : "—")}
                    </td>
                    {/* Room */}
                    <td>
                      {s0?.location_name ?? (s0 ? <span style={{ color: "var(--muted-text)" }}>—</span> : "—")}
                    </td>
                    {/* Warnings */}
                    <td>
                      {warnCoreUnsched && <span title="Foundation lesson not scheduled" style={{ color: "var(--aafc-red)", fontSize: 11 }}>⚠ Foundation</span>}
                      {warnNoFac && <span title="No facilitator assigned" style={{ color: "var(--warning, #d97706)", fontSize: 11 }}>⚠ Fac</span>}
                      {warnNoRoom && !warnCoreUnsched && <span title="No room assigned" style={{ color: "var(--muted-text)", fontSize: 11 }}>⚠ Room</span>}
                    </td>
                    {/* Classes — CLASS-05: per-Training-Class share of this mission's
                        six-state status, empty when this item's Stage has no active
                        Classes yet. */}
                    <td>
                      {m.class_breakdown.length === 0 ? (
                        <span style={{ color: "var(--muted-text)" }}>—</span>
                      ) : (
                        <div style={{ display: "flex", flexWrap: "wrap", gap: 3 }}>
                          {m.class_breakdown.map(cb => (
                            <span
                              key={cb.training_class_id}
                              title={`${cb.display_name}: ${CLASS_STATUS_LABEL[cb.backlog_status] ?? cb.backlog_status}${cb.scheduled_count ? ` (×${cb.scheduled_count})` : ""}`}
                              style={classChipStyle(cb.backlog_status)}
                            >
                              {cb.display_name}
                            </span>
                          ))}
                          {m.unassigned_session_count > 0 && (
                            <span
                              title={`${m.unassigned_session_count} scheduled session(s) with no Training Class assigned`}
                              style={{ fontSize: 9, color: "var(--muted-text)", fontStyle: "italic", whiteSpace: "nowrap" }}
                            >
                              +{m.unassigned_session_count} unassigned
                            </span>
                          )}
                        </div>
                      )}
                    </td>
                    {/* Actions */}
                    <td style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                      {s0 ? (
                        <button
                          className="btn sm out"
                          style={{ fontSize: 10, padding: "2px 7px" }}
                          onClick={async () => {
                            const full = await planningApi.getSession(s0.session_id);
                            onItemClick({
                              type: "session", session: full,
                              dateId: s0.parade_date_id ?? "", date: s0.parade_date ?? "",
                              conflicts: [],
                            });
                          }}
                        >
                          Edit
                        </button>
                      ) : (
                        <button
                          className="btn sm out"
                          style={{ fontSize: 10, padding: "2px 7px" }}
                          onClick={() => onItemClick({ type: "curriculum", curriculum: {
                            curriculum_id: m.curriculum_id,
                            code: m.code,
                            title: m.title,
                            phase: m.phase,
                          }})}
                        >
                          Schedule
                        </button>
                      )}
                      {m.needs_reschedule && m.backlog_status !== "resolved" && s0 && (
                        <button
                          className="btn sm out"
                          disabled={reschedulingId === s0.session_id}
                          style={{ fontSize: 10, padding: "2px 7px", borderColor: "var(--aafc-red)", color: "var(--aafc-red)" }}
                          title={s0.cancelled_reason ?? s0.not_delivered_reason ?? ""}
                          onClick={async () => {
                            if (!await confirm(
                              `This session was ${m.has_not_delivered ? "not delivered" : "cancelled"} on ${fmtDate(s0.parade_date)}. ` +
                              "Mark it as rescheduled and choose a new date now?",
                              { confirmLabel: "Mark rescheduled" }
                            )) return;
                            setReschedulingId(s0.session_id);
                            try {
                              await trainingApi.setStatus(s0.session_id, { status: "rescheduled" });
                              await queryClient.invalidateQueries({ queryKey: ["planning-missions", yearId] });
                              onItemClick({ type: "curriculum", curriculum: {
                                curriculum_id: m.curriculum_id,
                                code: m.code,
                                title: m.title,
                                phase: m.phase,
                              }});
                            } finally {
                              setReschedulingId(null);
                            }
                          }}
                        >
                          Reschedule
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── FacilitatorLeaveSection ──────────────────────────────────────────────────

function FacilitatorLeaveSection({
  fac_id, yearId,
}: { fac_id: string; yearId: string | null }) {
  const qc = useQueryClient();
  const { confirm } = useConfirm();
  const [addingLeave, setAddingLeave] = useState(false);
  const [leaveStart, setLeaveStart] = useState("");
  const [leaveEnd, setLeaveEnd] = useState("");
  const [leaveReason, setLeaveReason] = useState("");
  const [leaveNotes, setLeaveNotes] = useState("");
  const [leaveSaving, setLeaveSaving] = useState(false);
  const [leaveErr, setLeaveErr] = useState<string | null>(null);
  const [leaveWarning, setLeaveWarning] = useState<string | null>(null);
  const [deletingLeaveId, setDeletingLeaveId] = useState<string | null>(null);
  const [showArchivedLeave, setShowArchivedLeave] = useState(false);
  const [restoringLeaveId, setRestoringLeaveId] = useState<string | null>(null);
  const [restoreLeaveErr, setRestoreLeaveErr] = useState<string | null>(null);

  const { data: leaveData, isLoading: leaveLoading } = useQuery({
    queryKey: ["fac-leave", fac_id],
    queryFn: () => planningApi.facilitatorLeave(fac_id),
  });

  // REM-133: leave removal existed with no way to see or restore an
  // archived leave period -- lazy-fetched only once "Show archived" is
  // opened, matching this codebase's established show-archived pattern.
  const { data: archivedLeaveData, refetch: refetchArchivedLeave } = useQuery({
    queryKey: ["fac-leave-archived", fac_id],
    queryFn: () => planningApi.facilitatorLeave(fac_id, true),
    enabled: showArchivedLeave,
  });

  const { data: workload, isLoading: workloadLoading } = useQuery({
    queryKey: ["fac-workload", yearId, fac_id],
    queryFn: () => planningApi.facilitatorWorkload(yearId!, fac_id),
    enabled: !!yearId,
  });

  async function handleAddLeave() {
    if (!leaveStart || !leaveEnd) { setLeaveErr("Start and end dates required."); return; }
    if (leaveEnd < leaveStart) { setLeaveErr("End must be on or after start."); return; }
    setLeaveSaving(true); setLeaveErr(null); setLeaveWarning(null);
    try {
      const res = await planningApi.addFacilitatorLeave(fac_id, {
        start_date: leaveStart, end_date: leaveEnd,
        reason: leaveReason || undefined, notes: leaveNotes || undefined,
      });
      await qc.invalidateQueries({ queryKey: ["fac-leave", fac_id] });
      if (res.affected_sessions.length > 0) {
        setLeaveWarning(
          `Leave added. Warning: ${res.affected_sessions.length} session(s) currently scheduled during this period for this facilitator.`
        );
      }
      setLeaveStart(""); setLeaveEnd(""); setLeaveReason(""); setLeaveNotes("");
      setAddingLeave(false);
    } catch (e: unknown) {
      setLeaveErr(friendlyMessage(e, "Failed to add leave"));
    } finally {
      setLeaveSaving(false);
    }
  }

  async function handleDeleteLeave(leave_id: string) {
    if (!await confirm("Remove this leave period? It can be restored later from 'Show archived'.", { confirmLabel: "Remove" })) return;
    setDeletingLeaveId(leave_id);
    try {
      await planningApi.deleteFacilitatorLeave(leave_id);
      await qc.invalidateQueries({ queryKey: ["fac-leave", fac_id] });
    } finally {
      setDeletingLeaveId(null);
    }
  }

  async function handleRestoreLeave(leave_id: string) {
    setRestoringLeaveId(leave_id);
    setRestoreLeaveErr(null);
    try {
      await planningApi.restoreFacilitatorLeave(leave_id);
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["fac-leave", fac_id] }),
        refetchArchivedLeave(),
      ]);
    } catch (e: unknown) {
      setRestoreLeaveErr(friendlyMessage(e, "Could not restore this leave period"));
    } finally {
      setRestoringLeaveId(null);
    }
  }

  const leave: PlanningFacilitatorLeave[] = leaveData?.leave ?? [];
  const wl: FacilitatorWorkload | undefined = workload;

  return (
    <div style={{ padding: "10px 14px", background: "var(--surface-alt, #f8fafd)", borderTop: "1px solid var(--border)" }}>
      {/* Workload Stats */}
      {yearId && (
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "var(--aafc-dark-blue)", marginBottom: 6 }}>
            Workload (current year)
          </div>
          {workloadLoading ? (
            <div style={{ fontSize: 11, color: "var(--muted-text)" }}>Loading…</div>
          ) : wl ? (
            <div style={{ display: "flex", gap: 14, fontSize: 11, flexWrap: "wrap" }}>
              <span><strong>{wl.total_scheduled}</strong> sessions total</span>
              <span><strong>{wl.nights_with_sessions}</strong> nights</span>
              <span>avg <strong>{wl.avg_per_night}</strong>/night</span>
              <span>max <strong>{wl.max_per_night}</strong>, min <strong>{wl.min_per_night}</strong></span>
            </div>
          ) : (
            <div style={{ fontSize: 11, color: "var(--muted-text)" }}>No workload data.</div>
          )}

          {/* Upcoming sessions */}
          {wl && wl.upcoming_sessions.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <div style={{ fontSize: 11, fontWeight: 600, marginBottom: 4 }}>Upcoming sessions</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                {wl.upcoming_sessions.slice(0, 5).map(s => (
                  <div key={s.session_id} style={{ fontSize: 11, display: "flex", gap: 8, color: "var(--text)" }}>
                    <span style={{ color: "var(--aafc-dark-blue)", fontWeight: 600 }}>{s.parade_date}</span>
                    <span>{s.title ?? "—"}</span>
                    {s.cadet_group && <span style={{ color: "var(--muted-text)" }}>{s.cadet_group}</span>}
                    {s.location_name && <span style={{ color: "var(--muted-text)" }}>{s.location_name}</span>}
                  </div>
                ))}
                {wl.upcoming_sessions.length > 5 && (
                  <div style={{ fontSize: 10, color: "var(--muted-text)" }}>+{wl.upcoming_sessions.length - 5} more</div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Leave Periods */}
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "var(--aafc-dark-blue)" }}>Leave / Unavailability</div>
          <div style={{ display: "flex", gap: 6 }}>
            <button
              className="btn sm out"
              style={{ fontSize: 11, padding: "2px 8px" }}
              onClick={() => setShowArchivedLeave(v => !v)}
            >
              {showArchivedLeave ? "Hide archived" : "Show archived"}
            </button>
            {!addingLeave && (
              <button className="btn sm out" style={{ fontSize: 11, padding: "2px 8px" }} onClick={() => setAddingLeave(true)}>
                + Add Leave
              </button>
            )}
          </div>
        </div>

        {leaveWarning && (
          <div style={{ fontSize: 11, color: "var(--warning)", background: "#fff8e6", border: "1px solid var(--warning)", borderRadius: 6, padding: "6px 10px", marginBottom: 6 }}>
            {leaveWarning}
          </div>
        )}

        {addingLeave && (
          <div style={{ background: "#fff", border: "1px solid var(--border)", borderRadius: 8, padding: "10px 12px", marginBottom: 8 }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 8 }}>
              <label style={labelSx}>
                Start *
                <input type="date" value={leaveStart} onChange={e => setLeaveStart(e.target.value)} style={inputSx} />
              </label>
              <label style={labelSx}>
                End *
                <input type="date" value={leaveEnd} onChange={e => setLeaveEnd(e.target.value)} style={inputSx} />
              </label>
              <label style={{ ...labelSx, gridColumn: "1/-1" }}>
                Reason
                <input value={leaveReason} onChange={e => setLeaveReason(e.target.value)} placeholder="e.g. Medical, Personal, Course" style={inputSx} />
              </label>
              <label style={{ ...labelSx, gridColumn: "1/-1" }}>
                Notes
                <input value={leaveNotes} onChange={e => setLeaveNotes(e.target.value)} placeholder="Optional additional notes" style={inputSx} />
              </label>
            </div>
            {leaveErr && <div style={{ color: "var(--aafc-red)", fontSize: 11, marginBottom: 6 }}>{leaveErr}</div>}
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn sm primary" onClick={handleAddLeave} disabled={leaveSaving}>
                {leaveSaving ? "Saving…" : "Add leave"}
              </button>
              <button className="btn sm out" onClick={() => { setAddingLeave(false); setLeaveErr(null); }}>Cancel</button>
            </div>
          </div>
        )}

        {leaveLoading ? (
          <div style={{ fontSize: 11, color: "var(--muted-text)" }}>Loading leave…</div>
        ) : leave.length === 0 ? (
          <div style={{ fontSize: 11, color: "var(--muted-text)" }}>No leave recorded.</div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {leave.map(l => (
              <div key={l.id} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 11, background: "#fff", border: "1px solid var(--border)", borderRadius: 6, padding: "5px 10px" }}>
                <span style={{ fontWeight: 600, color: "var(--aafc-dark-blue)" }}>
                  {l.start_date}{l.end_date !== l.start_date ? ` → ${l.end_date}` : ""}
                </span>
                {l.reason && <span style={{ color: "var(--muted-text)" }}>{l.reason}</span>}
                <button
                  className="btn sm out"
                  style={{ marginLeft: "auto", fontSize: 10, padding: "2px 7px", color: "var(--aafc-red)" }}
                  onClick={() => handleDeleteLeave(l.id)}
                  disabled={deletingLeaveId === l.id}
                >
                  {deletingLeaveId === l.id ? "…" : "Remove"}
                </button>
              </div>
            ))}
          </div>
        )}

        {showArchivedLeave && (
          <div style={{ marginTop: 8 }}>
            {restoreLeaveErr && <div style={{ color: "var(--aafc-red)", fontSize: 11, marginBottom: 6 }}>{restoreLeaveErr}</div>}
            {!archivedLeaveData ? (
              <div style={{ fontSize: 11, color: "var(--muted-text)" }}>Loading archived leave…</div>
            ) : archivedLeaveData.leave.filter(l => l.is_archived).length === 0 ? (
              <div style={{ fontSize: 11, color: "var(--muted-text)" }}>No archived leave periods.</div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {archivedLeaveData.leave.filter(l => l.is_archived).map(l => (
                  <div key={l.id} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 11, background: "var(--surface-2, #eef2f7)", border: "1px solid var(--border)", borderRadius: 6, padding: "5px 10px", opacity: .75 }}>
                    <span style={{ fontWeight: 600, color: "var(--aafc-dark-blue)" }}>
                      {l.start_date}{l.end_date !== l.start_date ? ` → ${l.end_date}` : ""}
                    </span>
                    {l.reason && <span style={{ color: "var(--muted-text)" }}>{l.reason}</span>}
                    <span className="badge muted" style={{ fontSize: 10 }}>Archived</span>
                    <button
                      className="btn sm out"
                      style={{ marginLeft: "auto", fontSize: 10, padding: "2px 7px" }}
                      onClick={() => handleRestoreLeave(l.id)}
                      disabled={restoringLeaveId === l.id}
                    >
                      {restoringLeaveId === l.id ? "…" : "Restore"}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── ScheduleContent ──────────────────────────────────────────────────────────
// GAP-14 fix: the Facilitator Schedule Explorer (FacilitatorTimeline.tsx /
// FacilitatorScheduleList.tsx, GET /api/dashboard/facilitator-schedule) was
// fully built and tested but only registered on the standalone full-app route
// table (/facilitator-schedule) -- unreachable on the actually-deployed
// module-mode Planning Workspace service, the same root cause GAP-13 already
// found for the Facilitators CSV import. This wires the same components into
// the one surface that IS reachable in module mode: a Bottom Drawer tab.
// Squadron-scoped directly via the caller's own squadronId (the session's
// squadron for a squadron-role user) rather than useScopedSquadron's
// Wing/National selector context, which isn't wired into module mode.
function ScheduleContent({ squadronId }: { squadronId?: string }) {
  const [zoom, setZoom] = useState<ZoomPreset>("term");
  const [view, setView] = useState<"timeline" | "list">("timeline");

  const q = useQuery({
    queryKey: ["facilitator-schedule", zoom, squadronId],
    queryFn: () => dashboardApi.facilitatorSchedule(zoom === "week" ? "week" : "year", squadronId),
    staleTime: 2 * 60 * 1000,
  });

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8, marginBottom: 8 }}>
        <label style={{ fontSize: 12, display: "flex", alignItems: "center", gap: 6 }}>
          Zoom
          <select value={zoom} onChange={(e) => setZoom(e.target.value as ZoomPreset)} style={{ fontSize: 12, padding: "4px 6px" }}>
            <option value="week">Week</option>
            <option value="month">Month</option>
            <option value="term">Term</option>
            <option value="year">Year</option>
          </select>
        </label>
        <div role="group" aria-label="View">
          <button type="button" className={`btn sm ${view === "timeline" ? "" : "out"}`} aria-pressed={view === "timeline"} onClick={() => setView("timeline")}>Timeline</button>{" "}
          <button type="button" className={`btn sm ${view === "list" ? "" : "out"}`} aria-pressed={view === "list"} onClick={() => setView("list")}>List (accessible)</button>
        </div>
      </div>
      {q.isLoading ? (
        <Loading />
      ) : q.error ? (
        <ErrorNote error={q.error} />
      ) : view === "timeline" ? (
        <FacilitatorTimeline facilitators={q.data?.facilitators ?? []} items={q.data?.items ?? []} zoomPreset={zoom} />
      ) : (
        <FacilitatorScheduleList facilitators={q.data?.facilitators ?? []} items={q.data?.items ?? []} />
      )}
    </div>
  );
}

// ─── FacilitatorsContent ─────────────────────────────────────────────────────

function FacilitatorsContent({
  yearId,
  facilitators,
}: { yearId: string | null; facilitators: PlanningFacilitator[] }) {
  const qc = useQueryClient();
  const [selectedFacId, setSelectedFacId] = useState<string | null>(null);
  const [addingFac, setAddingFac] = useState(false);
  const [importingFac, setImportingFac] = useState(false);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [rank, setRank] = useState("");
  const [facType, setFacType] = useState("");
  const { data: facTypeTags = [] } = useQuery({
    queryKey: ["facilitator-type-tags"],
    queryFn: () => trainingApi.facilitatorTypeTags(),
    staleTime: 5 * 60 * 1000,
  });
  const [subjectAreas, setSubjectAreas] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [dupWarning, setDupWarning] = useState<string | null>(null);

  // TRGO-07 (drawer-tab parity): this form posts to the same POST /api/facilitators
  // endpoint as the standalone Add Facilitator modal, so it hits the same
  // 409 possible_duplicate check -- but until this fix it had no way to resubmit
  // with confirm_duplicate:true, so a genuine same-name-different-person case was
  // a dead end here too. This tab is the one actually reachable when the app is
  // deployed in module mode, so the fix belongs here, not only on the standalone
  // route's own copy of this form.
  async function handleAddFac(confirmDuplicate = false) {
    if (!firstName.trim() || !lastName.trim()) { setErr("Given name and family name are required."); return; }
    setSaving(true); setErr(null);
    try {
      await planningApi.createFacilitator({
        first_name: firstName.trim(), last_name: lastName.trim(),
        current_rank: rank.trim() || undefined,
        type: facType || undefined,
        subject_areas: subjectAreas ? subjectAreas.split(",").map(s => s.trim()).filter(Boolean) : undefined,
        confirm_duplicate: confirmDuplicate,
      });
      await qc.invalidateQueries({ queryKey: ["planning-facilitators"] });
      setFirstName(""); setLastName(""); setRank(""); setFacType(""); setSubjectAreas("");
      setAddingFac(false); setDupWarning(null);
    } catch (e: unknown) {
      if (e instanceof ApiError && e.code === "possible_duplicate") {
        setDupWarning(e.friendly);
      } else {
        setErr(friendlyMessage(e, "Failed to create facilitator"));
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <div style={{ padding: "8px 14px 0", display: "flex", justifyContent: "flex-end", gap: 6 }}>
        {!addingFac && (
          <>
            <button className="btn sm out" onClick={() => setImportingFac(true)}>Import CSV</button>
            <button className="btn sm primary" onClick={() => { setAddingFac(true); setDupWarning(null); setErr(null); }}>+ Add Facilitator</button>
          </>
        )}
      </div>
      {importingFac && (
        <ImportFacilitatorsModal
          onClose={() => setImportingFac(false)}
          onDone={() => { setImportingFac(false); qc.invalidateQueries({ queryKey: ["planning-facilitators"] }); }}
        />
      )}

      {addingFac && (
        <div style={{ padding: "10px 14px", background: "var(--surface)", borderBottom: "1px solid var(--border)" }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginBottom: 8 }}>
            <label style={labelSx}>
              Given name *
              <input value={firstName} onChange={e => { setFirstName(e.target.value); setDupWarning(null); }} style={inputSx} />
            </label>
            <label style={labelSx}>
              Family name *
              <input value={lastName} onChange={e => { setLastName(e.target.value); setDupWarning(null); }} style={inputSx} />
            </label>
            <label style={labelSx}>
              Rank
              <input value={rank} onChange={e => setRank(e.target.value)} placeholder="e.g. Capt, WO2" style={inputSx} />
            </label>
            <label style={labelSx}>
              Type
              <select value={facType} onChange={e => setFacType(e.target.value)} style={inputSx}>
                <option value="">— default (Staff) —</option>
                {facTypeTags.map(t => <option key={t.tag_id} value={t.display_name}>{t.display_name}</option>)}
              </select>
            </label>
            <label style={{ ...labelSx, gridColumn: "2 / -1" }}>
              Subject areas (comma-separated)
              <input value={subjectAreas} onChange={e => setSubjectAreas(e.target.value)} placeholder="e.g. Aviation, Leadership" style={inputSx} />
            </label>
          </div>
          {err && <div style={{ color: "var(--aafc-red)", fontSize: 12, marginBottom: 6 }}>{err}</div>}
          {dupWarning && (
            <div style={{ color: "var(--aafc-red)", fontSize: 12, marginBottom: 6 }}>
              {dupWarning} If this is a different person with the same name, you can add them anyway.
            </div>
          )}
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn sm primary" onClick={() => handleAddFac(false)} disabled={saving}>{saving ? "Saving…" : "Add facilitator"}</button>
            {dupWarning && (
              <button className="btn sm out" onClick={() => handleAddFac(true)} disabled={saving}>{saving ? "Saving…" : "Add anyway"}</button>
            )}
            <button className="btn sm out" onClick={() => { setAddingFac(false); setErr(null); setDupWarning(null); }}>Cancel</button>
          </div>
        </div>
      )}

      {facilitators.length === 0 && !addingFac ? (
        <div className="pw-empty" style={{ padding: "20px" }}>No facilitators on record.</div>
      ) : (
        <>
          <table className="pw-fac-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Subject areas</th>
                <th>Max sessions/night</th>
              </tr>
            </thead>
            <tbody>
              {facilitators.map((f) => {
                const isSelected = selectedFacId === f.facilitator_id;
                return (
                  <tr
                    key={f.facilitator_id}
                    style={{ cursor: "pointer", background: isSelected ? "#EEF4FB" : undefined }}
                    onClick={() => setSelectedFacId(isSelected ? null : f.facilitator_id)}
                  >
                    <td style={{ fontWeight: 600, color: "var(--aafc-dark-blue)" }}>
                      {f.display_name}
                      {f.rank && <span style={{ fontWeight: 400, color: "var(--muted-text)", fontSize: 11, marginLeft: 4 }}>{f.rank}</span>}
                    </td>
                    <td style={{ textTransform: "capitalize" }}>{f.type}</td>
                    <td style={{ fontSize: 11 }}>{f.subject_areas.join(", ") || "—"}</td>
                    <td style={{ textAlign: "center" }}>{f.max_sessions_per_night}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {/* Expanded facilitator profile panel */}
          {selectedFacId && (
            <FacilitatorLeaveSection
              key={selectedFacId}
              fac_id={selectedFacId}
              yearId={yearId}
            />
          )}
        </>
      )}
    </div>
  );
}

// ─── RoomsContent ─────────────────────────────────────────────────────────────

function RoomsContent({ locations, onAddLocation, onEditLocation }: {
  locations: PlanningLocation[];
  onAddLocation: () => void;
  onEditLocation: (loc: PlanningLocation) => void;
}) {
  return (
    <div>
      <div style={{ padding: "8px 14px 0", display: "flex", justifyContent: "flex-end" }}>
        <button className="btn sm primary" onClick={onAddLocation}>+ Add Room</button>
      </div>
      {locations.length === 0 ? (
        <div className="pw-empty" style={{ padding: "20px" }}>No rooms on record. Add one to start assigning sessions to rooms.</div>
      ) : (
        <table className="pw-fac-table">
          <thead>
            <tr>
              <th>Room</th>
              <th>Type</th>
              <th>Capacity</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {locations.map((l) => (
              <tr key={l.location_id}>
                <td>{l.name}</td>
                <td style={{ textTransform: "capitalize" }}>{l.location_type}</td>
                <td style={{ textAlign: "center" }}>{l.capacity ?? "—"}</td>
                <td>
                  <span style={{ fontSize: 11, fontWeight: 700, color: l.active_status ? "var(--success)" : "var(--muted-text)" }}>
                    {l.active_status ? "Active" : "Inactive"}
                  </span>
                </td>
                <td>
                  <button className="btn sm out" style={{ fontSize: 11, padding: "3px 8px" }} onClick={() => onEditLocation(l)}>Edit</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ─── EquipmentContent ─────────────────────────────────────────────────────────

function EquipmentContent() {
  const qc = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [type, setType] = useState("");
  const [qty, setQty] = useState("");
  const [availQty, setAvailQty] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const { data: items = [], isLoading } = useQuery<EquipmentItem[]>({
    queryKey: ["planning-equipment"],
    queryFn: () => planningApi.listEquipment(),
  });

  function resetForm() {
    setName(""); setType(""); setQty(""); setAvailQty(""); setNotes("");
    setErr(null); setAdding(false);
  }

  async function handleAdd() {
    if (!name.trim()) { setErr("Name is required."); return; }
    setSaving(true); setErr(null);
    try {
      await planningApi.addEquipment({
        name: name.trim(),
        type: type.trim() || undefined,
        quantity: qty ? parseInt(qty, 10) : undefined,
        available_quantity: availQty ? parseInt(availQty, 10) : undefined,
        notes: notes.trim() || undefined,
      });
      await qc.invalidateQueries({ queryKey: ["planning-equipment"] });
      resetForm();
    } catch (e: unknown) {
      setErr(friendlyMessage(e, "Failed to add equipment"));
    } finally {
      setSaving(false);
    }
  }

  if (isLoading) return <div className="pw-loading" style={{ padding: "20px" }}>Loading equipment…</div>;

  return (
    <div>
      <div style={{ padding: "8px 14px 0", display: "flex", justifyContent: "flex-end" }}>
        {!adding && (
          <button className="btn sm primary" onClick={() => setAdding(true)}>+ Add Equipment</button>
        )}
      </div>

      {adding && (
        <div style={{ padding: "10px 14px", background: "var(--surface)", borderBottom: "1px solid var(--border)" }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 8, marginBottom: 8 }}>
            <label style={{ ...labelSx, gridColumn: "1 / 3" }}>
              Name *
              <input value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Projector" style={inputSx} />
            </label>
            <label style={labelSx}>
              Type
              <input value={type} onChange={e => setType(e.target.value)} placeholder="e.g. AV" style={inputSx} />
            </label>
            <label style={labelSx}>
              Qty
              <input type="number" min="0" value={qty} onChange={e => setQty(e.target.value)} style={inputSx} />
            </label>
            <label style={labelSx}>
              Available qty
              <input type="number" min="0" value={availQty} onChange={e => setAvailQty(e.target.value)} style={inputSx} />
            </label>
            <label style={{ ...labelSx, gridColumn: "2 / -1" }}>
              Notes
              <input value={notes} onChange={e => setNotes(e.target.value)} style={inputSx} />
            </label>
          </div>
          {err && <div style={{ color: "var(--aafc-red)", fontSize: 12, marginBottom: 6 }}>{err}</div>}
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn sm primary" onClick={handleAdd} disabled={saving}>{saving ? "Saving…" : "Add equipment"}</button>
            <button className="btn sm out" onClick={resetForm}>Cancel</button>
          </div>
        </div>
      )}

      {items.length === 0 && !adding ? (
        <div className="pw-empty" style={{ padding: "20px" }}>No equipment on record.</div>
      ) : (
        <table className="pw-fac-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Qty</th>
              <th>Available</th>
              <th>Condition</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.equipment_id}>
                <td style={{ fontWeight: 600 }}>{item.name}</td>
                <td style={{ textTransform: "capitalize" }}>{item.type ?? "—"}</td>
                <td style={{ textAlign: "center" }}>{item.quantity}</td>
                <td style={{ textAlign: "center" }}>
                  <span style={{
                    fontWeight: 700,
                    color: item.available_quantity > 0 ? "var(--success)" : "var(--aafc-red)",
                  }}>
                    {item.available_quantity}
                  </span>
                </td>
                <td style={{ fontSize: 11, textTransform: "capitalize" }}>
                  {item.condition ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ─── HolidaysContent ──────────────────────────────────────────────────────────

const HOLIDAY_TYPES = [
  { value: "school_holiday", label: "School holiday" },
  { value: "statutory", label: "Statutory / public holiday" },
  { value: "civic", label: "Civic holiday" },
  { value: "training_stand_down", label: "Training stand-down" },
  { value: "other", label: "Other" },
];

function HolidaysContent({ yearId }: { yearId: string }) {
  const qc = useQueryClient();
  const { confirm } = useConfirm();
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [holidayType, setHolidayType] = useState("school_holiday");
  const [affectsParade, setAffectsParade] = useState(true);
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const { data: holidays = [], isLoading } = useQuery({
    queryKey: ["planning-holidays", yearId],
    queryFn: () => planningApi.holidays(yearId),
  });

  function resetForm() {
    setName(""); setStartDate(""); setEndDate("");
    setHolidayType("school_holiday"); setAffectsParade(true);
    setNotes(""); setErr(null); setAdding(false);
  }

  async function handleAdd() {
    if (!name.trim()) { setErr("Name is required."); return; }
    if (!startDate || !endDate) { setErr("Start and end dates are required."); return; }
    if (endDate < startDate) { setErr("End date must be on or after start date."); return; }
    setSaving(true); setErr(null);
    try {
      await planningApi.createHoliday(yearId, {
        name: name.trim(), start_date: startDate, end_date: endDate,
        holiday_type: holidayType, affects_parade: affectsParade,
        notes: notes || undefined,
      });
      await qc.invalidateQueries({ queryKey: ["planning-holidays", yearId] });
      await qc.invalidateQueries({ queryKey: ["planning-annual"] });
      resetForm();
    } catch (e: unknown) {
      setErr(friendlyMessage(e, "Failed to add holiday"));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(holiday_id: string) {
    if (!await confirm("Permanently delete this holiday period?", { confirmLabel: "Delete", danger: true })) return;
    setDeletingId(holiday_id);
    try {
      await planningApi.deleteHoliday(holiday_id);
      await qc.invalidateQueries({ queryKey: ["planning-holidays", yearId] });
      await qc.invalidateQueries({ queryKey: ["planning-annual"] });
    } finally {
      setDeletingId(null);
    }
  }

  if (isLoading) return <div className="pw-loading" style={{ padding: "20px" }}>Loading holidays…</div>;

  return (
    <div>
      <div style={{ padding: "8px 14px 0", display: "flex", justifyContent: "flex-end" }}>
        {!adding && (
          <button className="btn sm primary" onClick={() => setAdding(true)}>+ Add Holiday Period</button>
        )}
      </div>

      {adding && (
        <div style={{ padding: "10px 14px", background: "var(--surface)", borderBottom: "1px solid var(--border)" }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginBottom: 8 }}>
            <label style={{ gridColumn: "1 / -1", fontSize: 12, fontWeight: 700, display: "flex", flexDirection: "column", gap: 4 }}>
              Name *
              <input
                value={name}
                onChange={e => setName(e.target.value)}
                placeholder="e.g. Spring Break"
                style={{ fontWeight: 400, padding: "5px 8px", borderRadius: 6, border: "1.5px solid var(--border)", fontSize: 12 }}
              />
            </label>
            <label style={{ fontSize: 12, fontWeight: 700, display: "flex", flexDirection: "column", gap: 4 }}>
              Start *
              <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} style={{ padding: "5px 8px", borderRadius: 6, border: "1.5px solid var(--border)", fontSize: 12 }} />
            </label>
            <label style={{ fontSize: 12, fontWeight: 700, display: "flex", flexDirection: "column", gap: 4 }}>
              End *
              <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} style={{ padding: "5px 8px", borderRadius: 6, border: "1.5px solid var(--border)", fontSize: 12 }} />
            </label>
            <label style={{ fontSize: 12, fontWeight: 700, display: "flex", flexDirection: "column", gap: 4 }}>
              Type
              <select value={holidayType} onChange={e => setHolidayType(e.target.value)} style={{ padding: "5px 8px", borderRadius: 6, border: "1.5px solid var(--border)", fontSize: 12 }}>
                {HOLIDAY_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </label>
          </div>
          <label style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 12, marginBottom: 8 }}>
            <input type="checkbox" checked={affectsParade} onChange={e => setAffectsParade(e.target.checked)} />
            Affects parade nights (stand-down)
          </label>
          <label style={{ fontSize: 12, fontWeight: 700, display: "flex", flexDirection: "column", gap: 4, marginBottom: 8 }}>
            Notes (optional)
            <input
              value={notes}
              onChange={e => setNotes(e.target.value)}
              placeholder="e.g. State school holiday — check local gazette for exact dates"
              style={{ fontWeight: 400, padding: "5px 8px", borderRadius: 6, border: "1.5px solid var(--border)", fontSize: 12 }}
            />
          </label>
          {err && <div style={{ color: "var(--aafc-red)", fontSize: 12, marginBottom: 6 }}>{err}</div>}
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn sm primary" onClick={handleAdd} disabled={saving}>
              {saving ? "Saving…" : "Add holiday"}
            </button>
            <button className="btn sm out" onClick={resetForm}>Cancel</button>
          </div>
        </div>
      )}

      {holidays.length === 0 && !adding ? (
        <div className="pw-empty" style={{ padding: "20px" }}>
          No holiday periods defined. Add one to mark stand-downs on the calendar.
        </div>
      ) : (
        <table className="pw-fac-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Dates</th>
              <th>Type</th>
              <th>Stand-down</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {holidays.map(h => (
              <tr key={h.holiday_id}>
                <td style={{ fontWeight: 600 }}>{h.name}</td>
                <td style={{ fontSize: 11 }}>
                  {h.start_date}{h.end_date !== h.start_date ? ` → ${h.end_date}` : ""}
                </td>
                <td style={{ fontSize: 11, textTransform: "capitalize" }}>
                  {h.holiday_type.replace(/_/g, " ")}
                </td>
                <td style={{ textAlign: "center" }}>
                  <span style={{ fontWeight: 700, color: h.affects_parade ? "var(--warning)" : "var(--muted-text)" }}>
                    {h.affects_parade ? "Yes" : "No"}
                  </span>
                </td>
                <td>
                  <button
                    className="btn sm out"
                    style={{ fontSize: 11, padding: "3px 8px", color: "var(--aafc-red)" }}
                    onClick={() => handleDelete(h.holiday_id)}
                    disabled={deletingId === h.holiday_id}
                  >
                    {deletingId === h.holiday_id ? "…" : "Delete"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ─── NoticesContent ───────────────────────────────────────────────────────────

function NoticesContent({ yearId }: { yearId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["planning-cc", yearId],
    queryFn: () => planningApi.commandCentre(yearId),
  });

  if (isLoading) return <div className="pw-loading" style={{ padding: "20px" }}>Loading notices…</div>;

  const anchors = data?.upcoming_anchors ?? [];
  if (anchors.length === 0) {
    return <div className="pw-empty" style={{ padding: "20px" }}>No upcoming key notices.</div>;
  }

  return (
    <div className="pw-backlog-grid">
      {anchors.map((a, i) => (
        <div key={a.anchor_event_id ?? a.anchor_id ?? String(i)} className="pw-backlog-card">
          <div className="pw-backlog-card-code">{a.event_type}</div>
          <div className="pw-backlog-card-title">{a.event_name}</div>
          <div className="pw-backlog-card-meta">
            {a.start_date}{a.end_date && a.end_date !== a.start_date ? ` → ${a.end_date}` : ""}
            {a.planning_impact && ` · ${a.planning_impact}`}
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── ActivitiesContent ────────────────────────────────────────────────────────

const IMPORTANCE_LABELS: Record<string, string> = {
  must_attend: "Must Attend",
  key_event: "Key Event",
  weekly_parade: "Weekly Parade",
  optional: "Optional",
  noting: "Noting",
  irrelevant: "Irrelevant",
};

const STATUS_COLORS: Record<string, string> = {
  classified: "var(--aafc-dark-blue)",
  needs_review: "var(--warning)",
  irrelevant: "var(--muted-text)",
};

const SOURCE_COLORS: Record<string, string> = {
  cea: "#1A4D8F",
  manual: "#1A7F4B",
  anchor: "#7c3aed",
  holiday: "#b45309",
  tms_activity: "#455560",
};

const SOURCE_LABELS: Record<string, string> = {
  cea: "CEA",
  manual: "Manual",
  anchor: "Anchor",
  holiday: "Holiday",
  tms_activity: "Main TMS",
};

type UnifiedActivity = {
  id: string;
  source: "cea" | "manual" | "anchor" | "holiday" | "tms_activity";
  name: string;
  start_date: string | null;
  end_date: string | null;
  location: string | null;
  importance: string | null;
  classification_status: string | null;
  unit: string | null;
  extra: string | null;
  is_removed: boolean;
  is_hidden: boolean;
  local_note: string | null;
  raw_cea: import("../../api/types").CeaActivity | null;
  raw_anchor: import("../../api/types").AnchorEvent | null;
  raw_holiday: import("../../api/types").HolidayPeriod | null;
};

function ClassifyModal({
  activity,
  onSave,
  onClose,
}: {
  activity: import("../../api/types").CeaActivity;
  onSave: () => void;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [importance, setImportance] = useState(activity.importance ?? "");
  const [staffOnly, setStaffOnly] = useState(activity.audience_staff_only);
  const [seniors, setSeniors] = useState(activity.audience_seniors);
  const [proficient, setProficient] = useState(activity.audience_proficient);
  const [firstYears, setFirstYears] = useState(activity.audience_first_years);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function handleSave() {
    setSaving(true); setErr(null);
    try {
      await planningApi.ceaClassify(activity.id, {
        importance: importance || undefined,
        audience_staff_only: staffOnly,
        audience_seniors: seniors,
        audience_proficient: proficient,
        audience_first_years: firstYears,
      });
      await qc.invalidateQueries({ queryKey: ["cea-activities"] });
      onSave();
      onClose();
    } catch (e) {
      setErr(friendlyMessage(e, "Failed to save"));
    } finally {
      setSaving(false);
    }
  }

  return (
    // Backdrop click is a mouse-only convenience; Escape (above) and the Cancel button
    // below are the full keyboard-equivalent dismiss paths.
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.4)", zIndex: 900, display: "flex", alignItems: "center", justifyContent: "center" }} onClick={onClose}>
      {/* Only stops the backdrop's click-to-close from firing for clicks inside the dialog. */}
      {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions */}
      <div style={{ background: "#fff", borderRadius: 10, padding: 24, width: 420, maxWidth: "95vw" }} onClick={e => e.stopPropagation()}>
        <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>Classify Activity</div>
        <div style={{ fontSize: 12, color: "var(--muted-text)", marginBottom: 16 }}>{activity.activity_name}</div>

        <label htmlFor="classify-importance" style={{ fontSize: 12, fontWeight: 700, display: "block", marginBottom: 4 }}>Importance</label>
        <select
          id="classify-importance"
          value={importance}
          onChange={e => setImportance(e.target.value)}
          style={{ width: "100%", padding: "5px 8px", borderRadius: 6, border: "1.5px solid var(--border)", fontSize: 12, marginBottom: 14 }}
        >
          <option value="">— select —</option>
          {Object.entries(IMPORTANCE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>

        <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 6 }}>Audience</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 16 }}>
          {([
            ["Staff Only", staffOnly, setStaffOnly],
            ["Seniors (CFSGT–CUO)", seniors, setSeniors],
            ["Proficient (LCDT & CCPLS)", proficient, setProficient],
            ["First Years", firstYears, setFirstYears],
          ] as [string, boolean, (v: boolean) => void][]).map(([label, val, setter]) => (
            <label key={label} style={{ display: "flex", gap: 8, fontSize: 12, alignItems: "center", cursor: "pointer" }}>
              <input type="checkbox" checked={val} onChange={e => setter(e.target.checked)} />
              {label}
            </label>
          ))}
        </div>

        {err && <div style={{ fontSize: 11, color: "var(--aafc-red)", marginBottom: 8 }}>{err}</div>}
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button className="btn sm out" style={{ fontSize: 12 }} onClick={onClose}>Cancel</button>
          <button className="btn sm primary" style={{ fontSize: 12 }} onClick={handleSave} disabled={saving}>
            {saving ? "Saving…" : "Save classification"}
          </button>
        </div>
      </div>
    </div>
  );
}

// Activities tab "Getting Help" free text -- visible to every role, editable
// by system_admin only. Mirrors connected-frontend's equivalent card so both
// apps show identical content (backend/app/routers/training.py's
// GET/PUT /api/activities/getting-help, a single global SystemSetting row).
function GettingHelpSection() {
  const qc = useQueryClient();
  const { session } = useAuth();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<unknown>(null);

  const { data } = useQuery({
    queryKey: ["getting-help"],
    queryFn: () => trainingApi.gettingHelp(),
    staleTime: 60 * 1000,
  });

  const openEdit = () => {
    setDraft(data?.content ?? "");
    setErr(null);
    setEditing(true);
  };

  const save = async () => {
    setSaving(true);
    setErr(null);
    try {
      await trainingApi.updateGettingHelp(draft);
      await qc.invalidateQueries({ queryKey: ["getting-help"] });
      setEditing(false);
    } catch (e) {
      setErr(e);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 8 }}>
        <h4 style={{ margin: 0 }}>Getting Help</h4>
        {isSystemAdmin(session) && !editing && (
          <button className="btn sm out" onClick={openEdit}>Edit</button>
        )}
      </div>
      {editing ? (
        <div>
          <label style={labelSx}>
            Content
            <textarea value={draft} onChange={e => setDraft(e.target.value)} rows={6} style={{ ...inputSx, resize: "vertical" }} />
          </label>
          {err != null && <ErrorNote error={err} variant="action" />}
          <div style={{ display: "flex", gap: 8, marginTop: 10, justifyContent: "flex-end" }}>
            <button className="btn sm out" onClick={() => setEditing(false)} disabled={saving}>Cancel</button>
            <button className="btn sm primary" onClick={save} disabled={saving}>{saving ? "Saving…" : "Save"}</button>
          </div>
        </div>
      ) : (
        <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>
          {data?.content || "No help content added yet."}
        </p>
      )}
    </div>
  );
}

function ActivitiesContent({ yearId, squadronId }: { yearId: string; squadronId?: string }) {
  const qc = useQueryClient();
  const [classifying, setClassifying] = useState<import("../../api/types").CeaActivity | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [importResult, setImportResult] = useState<import("../../api/types").CeaImportResult | null>(null);
  const [importErr, setImportErr] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(false);

  const { data: batchData, isLoading: batchLoading } = useQuery({
    queryKey: ["cea-batches", yearId],
    queryFn: () => planningApi.ceaBatches(yearId),
    staleTime: 2 * 60 * 1000,
    enabled: showHistory,
  });
  const batches = batchData?.batches ?? [];
  // Filters
  const [fSource, setFSource] = useState("all");
  const [fStatus, setFStatus] = useState("all");
  const [fSearch, setFSearch] = useState("");
  const [fStart, setFStart] = useState("");
  const [fEnd, setFEnd] = useState("");
  const [fShowHidden, setFShowHidden] = useState(false);
  const [hidingId, setHidingId] = useState<string | null>(null);
  const [hideNote, setHideNote] = useState("");
  // Sort
  const [sortCol, setSortCol] = useState("start_date");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  // Create form
  const [newName, setNewName] = useState("");
  const [newStart, setNewStart] = useState("");
  const [newEnd, setNewEnd] = useState("");
  const [newLocation, setNewLocation] = useState("");
  const [newImportance, setNewImportance] = useState("");
  const [creating, setCreating] = useState(false);

  const { data: ceaData = [], isLoading: ceaLoading } = useQuery({
    queryKey: ["cea-activities", yearId],
    queryFn: () => planningApi.ceaActivities(yearId),
    staleTime: 2 * 60 * 1000,
  });

  const { data: anchorsData = [], isLoading: anchorsLoading } = useQuery({
    queryKey: ["planning-anchors", yearId],
    queryFn: () => planningApi.listAnchors(yearId),
    staleTime: 5 * 60 * 1000,
  });

  const { data: holidaysData = [], isLoading: holidaysLoading } = useQuery({
    queryKey: ["planning-holidays", yearId],
    queryFn: () => planningApi.holidays(yearId),
    staleTime: 5 * 60 * 1000,
  });

  // Canonical Activity records created in Main TMS (National/Wing/Squadron) --
  // read-only here; CEA import keeps owning CeaActivity as its own pipeline.
  // See trainingApi.canonicalActivities for why this closes the one real
  // cross-frontend visibility gap without a data migration.
  const { data: tmsActivitiesData = [], isLoading: tmsActivitiesLoading } = useQuery({
    queryKey: ["tms-canonical-activities", squadronId],
    queryFn: () => trainingApi.canonicalActivities(squadronId!),
    enabled: !!squadronId,
    staleTime: 2 * 60 * 1000,
  });

  const isLoading = ceaLoading || anchorsLoading || holidaysLoading || tmsActivitiesLoading;

  const unified = useMemo((): UnifiedActivity[] => {
    const rows: UnifiedActivity[] = [];
    for (const a of ceaData) {
      rows.push({
        id: a.id,
        source: a.source_type === "manual" ? "manual" : "cea",
        name: a.activity_name,
        start_date: a.activity_start_date,
        end_date: a.activity_end_date,
        location: a.location,
        importance: a.importance,
        classification_status: a.classification_status,
        unit: a.host_unit ?? a.parent_unit,
        extra: a.cea_activity_id,
        is_removed: a.is_removed_from_cea,
        is_hidden: a.is_hidden_for_me,
        local_note: a.local_note,
        raw_cea: a,
        raw_anchor: null,
        raw_holiday: null,
      });
    }
    for (const a of anchorsData) {
      rows.push({
        id: a.anchor_event_id,
        source: "anchor",
        name: a.event_name,
        start_date: a.start_date,
        end_date: a.end_date ?? null,
        location: null,
        importance: a.importance,
        classification_status: "classified",
        unit: a.unit_name,
        extra: a.event_type,
        is_removed: false,
        is_hidden: false,
        local_note: null,
        raw_cea: null,
        raw_anchor: a,
        raw_holiday: null,
      });
    }
    for (const h of holidaysData) {
      rows.push({
        id: h.holiday_id,
        source: "holiday",
        name: h.name,
        start_date: h.start_date,
        end_date: h.end_date,
        location: null,
        importance: null,
        classification_status: "classified",
        unit: null,
        extra: h.holiday_type.replace(/_/g, " "),
        is_removed: false,
        is_hidden: false,
        local_note: null,
        raw_cea: null,
        raw_anchor: null,
        raw_holiday: h,
      });
    }
    for (const a of tmsActivitiesData) {
      rows.push({
        id: a.activity_id,
        source: "tms_activity",
        name: a.activity_name,
        start_date: a.date_start,
        end_date: a.date_end,
        location: a.location,
        importance: null,
        classification_status: "classified",
        unit: a.owning_level === "national" ? "National" : a.owning_level === "wing" ? "Wing" : "Squadron",
        extra: a.activity_type,
        is_removed: false,
        is_hidden: false,
        local_note: null,
        raw_cea: null,
        raw_anchor: null,
        raw_holiday: null,
      });
    }
    return rows;
  }, [ceaData, anchorsData, holidaysData, tmsActivitiesData]);

  const filtered = useMemo(() => {
    const q = fSearch.toLowerCase();
    return [...unified]
      .filter(r => {
        // TRGO-02: hidden items are excluded by default -- local hide is a
        // "get this out of my way" action, not a delete, so it should not
        // require a special mode to reach, just an explicit toggle to reveal.
        if (r.is_hidden && !fShowHidden) return false;
        if (fSource !== "all" && r.source !== fSource) return false;
        if (fStatus === "needs_review" && r.classification_status !== "needs_review") return false;
        if (fStatus === "classified" && r.classification_status !== "classified") return false;
        if (fStart && r.start_date && r.start_date < fStart) return false;
        if (fEnd && r.start_date && r.start_date > fEnd) return false;
        if (q && !r.name.toLowerCase().includes(q) && !(r.unit ?? "").toLowerCase().includes(q)) return false;
        return true;
      })
      .sort((a, b) => {
        let av = "", bv = "";
        if (sortCol === "name") { av = a.name; bv = b.name; }
        else if (sortCol === "source") { av = a.source; bv = b.source; }
        else if (sortCol === "start_date") { av = a.start_date ?? ""; bv = b.start_date ?? ""; }
        else if (sortCol === "importance") { av = a.importance ?? ""; bv = b.importance ?? ""; }
        else if (sortCol === "status") { av = a.classification_status ?? ""; bv = b.classification_status ?? ""; }
        const cmp = av < bv ? -1 : av > bv ? 1 : 0;
        return sortDir === "asc" ? cmp : -cmp;
      });
  }, [unified, fSource, fStatus, fSearch, fStart, fEnd, fShowHidden, sortCol, sortDir]);

  function handleSort(col: string) {
    if (sortCol === col) setSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSortCol(col); setSortDir("asc"); }
  }

  function SortTh({ col, label, style }: { col: string; label: string; style?: CSSProperties }) {
    return (
      <th onClick={() => handleSort(col)} style={{ cursor: "pointer", userSelect: "none", whiteSpace: "nowrap", ...style }}>
        {label}{sortCol === col ? (sortDir === "asc" ? " ▲" : " ▼") : ""}
      </th>
    );
  }

  async function handleCreate() {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await planningApi.createManualActivity(yearId, {
        activity_name: newName.trim(),
        activity_start_date: newStart || undefined,
        activity_end_date: newEnd || undefined,
        location: newLocation || undefined,
        importance: newImportance || undefined,
      });
      await qc.invalidateQueries({ queryKey: ["cea-activities"] });
      setNewName(""); setNewStart(""); setNewEnd(""); setNewLocation(""); setNewImportance("");
      setShowCreate(false);
    } finally {
      setCreating(false);
    }
  }

  // TRGO-02: local hide/note -- a squadron-scoped overlay (ActivityLocalHide)
  // that never touches the shared CeaActivity source row.
  async function toggleHide(activity: import("../../api/types").CeaActivity, note?: string) {
    await planningApi.ceaLocalHide(activity.id, {
      is_hidden: !activity.is_hidden_for_me,
      local_note: note !== undefined ? note : (activity.local_note ?? undefined),
    });
    await qc.invalidateQueries({ queryKey: ["cea-activities", yearId] });
  }

  async function handleFileImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true); setImportErr(null); setImportResult(null);
    try {
      const res = await planningApi.ceaImport(yearId, file);
      setImportResult(res);
      await qc.invalidateQueries({ queryKey: ["cea-activities"] });
      await qc.invalidateQueries({ queryKey: ["cea-batches"] });
    } catch (ex) {
      setImportErr(friendlyMessage(ex, "Import failed"));
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  const needsReviewCount = unified.filter(r => r.classification_status === "needs_review").length;

  if (isLoading) return <div className="pw-loading" style={{ padding: "20px" }}>Loading activities…</div>;

  return (
    <div>
      {/* Toolbar */}
      <div style={{
        padding: "6px 14px", background: "var(--surface)", borderBottom: "1px solid var(--border)",
        display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap",
      }}>
        <input
          value={fSearch}
          onChange={e => setFSearch(e.target.value)}
          placeholder="Search name or unit…"
          style={{ ...inputSx, width: 180 }}
        />
        <select value={fSource} onChange={e => setFSource(e.target.value)} style={{ ...inputSx, width: 120 }}>
          <option value="all">All sources</option>
          <option value="cea">CEA</option>
          <option value="manual">Manual</option>
          <option value="anchor">Anchor</option>
          <option value="holiday">Holiday</option>
          <option value="tms_activity">Main TMS</option>
        </select>
        <select value={fStatus} onChange={e => setFStatus(e.target.value)} style={{ ...inputSx, width: 140 }}>
          <option value="all">All statuses</option>
          <option value="needs_review">Needs review{needsReviewCount > 0 ? ` (${needsReviewCount})` : ""}</option>
          <option value="classified">Classified</option>
        </select>
        <input
          type="date" value={fStart} onChange={e => setFStart(e.target.value)}
          title="From date" style={{ ...inputSx, width: 130 }}
        />
        <span style={{ fontSize: 11, color: "var(--muted-text)" }}>→</span>
        <input
          type="date" value={fEnd} onChange={e => setFEnd(e.target.value)}
          title="To date" style={{ ...inputSx, width: 130 }}
        />
        <button
          className="btn sm out" style={{ fontSize: 11, padding: "3px 8px" }}
          onClick={() => { setFSearch(""); setFSource("all"); setFStatus("all"); setFStart(""); setFEnd(""); }}
        >
          Reset
        </button>
        <label style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 11, color: "var(--muted-text)", cursor: "pointer", whiteSpace: "nowrap" }}>
          <input type="checkbox" checked={fShowHidden} onChange={e => setFShowHidden(e.target.checked)} />
          Show hidden
        </label>
        <span style={{ fontSize: 11, color: "var(--muted-text)", marginLeft: "auto", whiteSpace: "nowrap" }}>
          {filtered.length} of {unified.length}
        </span>
        <label style={{ display: "inline-flex", alignItems: "center", gap: 6, cursor: "pointer" }}>
          <input type="file" accept=".csv,.txt" style={{ display: "none" }} onChange={handleFileImport} disabled={uploading} />
          <span className="btn sm out" style={{ fontSize: 11, padding: "3px 9px", pointerEvents: "none", whiteSpace: "nowrap" }}>
            {uploading ? "Importing…" : "Import CEA"}
          </span>
        </label>
        <button className="btn sm primary" style={{ fontSize: 11, whiteSpace: "nowrap" }} onClick={() => setShowCreate(v => !v)}>
          + Add activity
        </button>
      </div>

      {/* Import result banner */}
      {importResult && (
        <div style={{ padding: "6px 14px", background: "#f0fff4", borderBottom: "1px solid var(--border)", fontSize: 11, display: "flex", gap: 14, alignItems: "center" }}>
          <span style={{ fontWeight: 700, color: "#1A7F4B" }}>Import complete</span>
          <span>{importResult.created} new</span>
          <span>{importResult.updated} updated</span>
          <span style={{ color: "var(--muted-text)" }}>{importResult.duplicates} duplicates · {importResult.skipped} skipped</span>
          {importResult.errors > 0 && <span style={{ color: "var(--aafc-red)" }}>{importResult.errors} errors</span>}
          <button onClick={() => setImportResult(null)} style={{ marginLeft: "auto", background: "none", border: "none", cursor: "pointer", fontSize: 14, color: "var(--muted-text)" }}>×</button>
        </div>
      )}
      {importErr && (
        <div style={{ padding: "6px 14px", background: "#fff0f0", borderBottom: "1px solid var(--border)", fontSize: 11, color: "var(--aafc-red)", display: "flex", alignItems: "center", gap: 8 }}>
          Import failed: {importErr}
          <button onClick={() => setImportErr(null)} style={{ marginLeft: "auto", background: "none", border: "none", cursor: "pointer", fontSize: 14 }}>×</button>
        </div>
      )}

      {/* Manual create form */}
      {showCreate && (
        <div style={{ padding: "10px 14px", background: "#f0f5ff", borderBottom: "1px solid var(--border)", display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 8 }}>
          <label style={{ gridColumn: "1 / 3", ...labelSx }}>
            Activity name *
            <input value={newName} onChange={e => setNewName(e.target.value)} style={{ ...inputSx, fontWeight: 400 }} />
          </label>
          <label style={labelSx}>
            Start date
            <input type="date" value={newStart} onChange={e => setNewStart(e.target.value)} style={inputSx} />
          </label>
          <label style={labelSx}>
            End date
            <input type="date" value={newEnd} onChange={e => setNewEnd(e.target.value)} style={inputSx} />
          </label>
          <label style={{ gridColumn: "1 / 3", ...labelSx }}>
            Location
            <input value={newLocation} onChange={e => setNewLocation(e.target.value)} style={inputSx} />
          </label>
          <label style={labelSx}>
            Importance
            <select value={newImportance} onChange={e => setNewImportance(e.target.value)} style={inputSx}>
              <option value="">— select —</option>
              {Object.entries(IMPORTANCE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
          <div style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
            <button className="btn sm primary" onClick={handleCreate} disabled={creating || !newName.trim()} style={{ fontSize: 11 }}>
              {creating ? "Saving…" : "Save"}
            </button>
            <button className="btn sm out" onClick={() => setShowCreate(false)} style={{ fontSize: 11 }}>Cancel</button>
          </div>
        </div>
      )}

      {/* Unified activities table */}
      {filtered.length === 0 ? (
        <div className="pw-empty" style={{ padding: "24px" }}>
          {unified.length === 0
            ? "No activities yet. Import a CEA file, add anchor events, or create a manual activity."
            : "No activities match your filters."}
        </div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table className="pw-fac-table" style={{ fontSize: 11, minWidth: 900 }}>
            <thead>
              <tr>
                <SortTh col="source" label="Source" style={{ minWidth: 70 }} />
                <SortTh col="name" label="Activity / Event" style={{ minWidth: 220 }} />
                <SortTh col="start_date" label="Start" style={{ minWidth: 90 }} />
                <th style={{ minWidth: 90 }}>End</th>
                <th style={{ minWidth: 130 }}>Unit</th>
                <th style={{ minWidth: 90 }}>Location</th>
                <th style={{ minWidth: 70 }}>Detail</th>
                <SortTh col="importance" label="Importance" style={{ minWidth: 100 }} />
                <SortTh col="status" label="Status" style={{ minWidth: 100 }} />
                <th style={{ minWidth: 70 }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(r => (
                <tr key={`${r.source}-${r.id}`} style={{ background: r.is_removed ? "#fff3cd" : r.is_hidden ? "#f4f5f7" : undefined, opacity: r.is_hidden ? 0.7 : 1 }}>
                  <td>
                    <span style={{
                      fontSize: 9, fontWeight: 700, padding: "2px 5px", borderRadius: 3,
                      background: SOURCE_COLORS[r.source] + "22",
                      color: SOURCE_COLORS[r.source],
                      border: `1px solid ${SOURCE_COLORS[r.source]}44`,
                      textTransform: "uppercase", letterSpacing: "0.04em",
                    }}>
                      {SOURCE_LABELS[r.source]}
                    </span>
                  </td>
                  <td style={{ fontWeight: 600, maxWidth: 260 }}>
                    {r.name}
                    {r.is_removed && (
                      <span style={{ marginLeft: 4, fontSize: 9, color: "var(--warning)", fontWeight: 700 }}>[Not in latest import]</span>
                    )}
                    {r.is_hidden && (
                      <span style={{ marginLeft: 4, fontSize: 9, color: "var(--muted-text)", fontWeight: 700 }}>[Hidden for your squadron]</span>
                    )}
                    {r.local_note && (
                      <div style={{ fontSize: 9, color: "var(--muted-text)", fontWeight: 400, fontStyle: "italic" }}>{r.local_note}</div>
                    )}
                  </td>
                  <td style={{ whiteSpace: "nowrap" }}>{r.start_date ?? "—"}</td>
                  <td style={{ whiteSpace: "nowrap", color: "var(--muted-text)" }}>{r.end_date ?? "—"}</td>
                  <td style={{ fontSize: 10, color: "var(--muted-text)", maxWidth: 150 }}>{r.unit ?? "—"}</td>
                  <td style={{ fontSize: 10, color: "var(--muted-text)" }}>{r.location ?? "—"}</td>
                  <td style={{ fontSize: 10, color: "var(--muted-text)", textTransform: "capitalize" }}>{r.extra ?? "—"}</td>
                  <td>
                    {r.importance
                      ? <span style={{ fontWeight: 600, color: "var(--aafc-dark-blue)", fontSize: 10 }}>{IMPORTANCE_LABELS[r.importance] ?? r.importance}</span>
                      : <span style={{ color: "var(--muted-text)" }}>—</span>}
                  </td>
                  <td>
                    {r.classification_status === "needs_review" ? (
                      <span style={{ fontSize: 10, fontWeight: 700, color: STATUS_COLORS.needs_review }}>Needs review</span>
                    ) : r.classification_status === "classified" ? (
                      <span style={{ fontSize: 10, fontWeight: 700, color: STATUS_COLORS.classified }}>Classified</span>
                    ) : (
                      <span style={{ fontSize: 10, color: "var(--muted-text)" }}>{r.classification_status ?? "—"}</span>
                    )}
                  </td>
                  <td style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                    {r.raw_cea && (
                      <button
                        className="btn sm out"
                        style={{ fontSize: 10, padding: "2px 6px" }}
                        onClick={() => setClassifying(r.raw_cea!)}
                      >
                        Classify
                      </button>
                    )}
                    {r.raw_cea && (
                      <button
                        className="btn sm out"
                        style={{ fontSize: 10, padding: "2px 6px" }}
                        onClick={() => {
                          if (r.is_hidden) { toggleHide(r.raw_cea!); }
                          else { setHidingId(r.id); setHideNote(r.local_note ?? ""); }
                        }}
                      >
                        {r.is_hidden ? "Unhide" : "Hide / note…"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* CEA import history — collapsed by default */}
      <div style={{ borderTop: "1px solid var(--border)", marginTop: 8 }}>
        <button
          style={{ display: "flex", alignItems: "center", gap: 6, width: "100%", padding: "7px 14px", background: "none", border: "none", cursor: "pointer", fontSize: 11, fontWeight: 700, color: "var(--aafc-dark-blue)", textAlign: "left" }}
          onClick={() => setShowHistory(v => !v)}
        >
          <span style={{ fontSize: 10 }}>{showHistory ? "▾" : "▸"}</span>
          CEA import history
        </button>
        {showHistory && (
          <div style={{ padding: "0 14px 10px" }}>
            {batchLoading ? (
              <div className="pw-loading" style={{ padding: "10px 0" }}>Loading…</div>
            ) : batches.length === 0 ? (
              <div style={{ fontSize: 11, color: "var(--muted-text)" }}>No imports yet.</div>
            ) : (
              <table className="pw-fac-table" style={{ fontSize: 11 }}>
                <thead>
                  <tr>
                    <th>File</th><th>Imported at</th><th>Rows</th>
                    <th>New</th><th>Updated</th><th>Dups</th><th>Skipped</th><th>Errors</th>
                  </tr>
                </thead>
                <tbody>
                  {batches.map(b => (
                    <tr key={b.id}>
                      <td style={{ maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis" }}>{b.source_file_name ?? "—"}</td>
                      <td style={{ color: "var(--muted-text)", whiteSpace: "nowrap" }}>
                        {b.created_at ? new Date(b.created_at).toLocaleDateString("en-CA", { year: "numeric", month: "short", day: "numeric" }) : "—"}
                      </td>
                      <td style={{ textAlign: "center" }}>{b.row_count}</td>
                      <td style={{ textAlign: "center", color: "#1A7F4B", fontWeight: 700 }}>{b.created_count}</td>
                      <td style={{ textAlign: "center", color: "var(--warning)", fontWeight: 700 }}>{b.updated_count}</td>
                      <td style={{ textAlign: "center" }}>{b.duplicate_count}</td>
                      <td style={{ textAlign: "center" }}>{b.skipped_count}</td>
                      <td style={{ textAlign: "center", color: b.error_count > 0 ? "var(--aafc-red)" : undefined }}>{b.error_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>

      {classifying && (
        <ClassifyModal
          activity={classifying}
          onSave={() => qc.invalidateQueries({ queryKey: ["cea-activities"] })}
          onClose={() => setClassifying(null)}
        />
      )}

      {hidingId && (() => {
        const target = unified.find(r => r.id === hidingId)?.raw_cea;
        if (!target) return null;
        return (
          <div className="pw-modal-overlay" role="dialog" aria-label="Hide activity for your squadron" style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.35)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 200 }}>
            <div style={{ background: "var(--surface)", borderRadius: 8, padding: 16, width: 360, boxShadow: "0 8px 24px rgba(0,0,0,0.2)" }}>
              <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 6 }}>Hide "{target.activity_name}" for your squadron</div>
              <p style={{ fontSize: 11, color: "var(--muted-text)", marginBottom: 8 }}>
                This only affects what your squadron sees -- the shared activity record is not changed, and other squadrons still see it normally.
              </p>
              <label style={labelSx}>
                Note (optional)
                <textarea value={hideNote} onChange={e => setHideNote(e.target.value)} rows={2} style={{ ...inputSx, resize: "vertical" }} />
              </label>
              <div style={{ display: "flex", gap: 8, marginTop: 10, justifyContent: "flex-end" }}>
                <button className="btn sm out" onClick={() => setHidingId(null)}>Cancel</button>
                <button
                  className="btn sm primary"
                  onClick={async () => {
                    await toggleHide(target, hideNote.trim() || undefined);
                    setHidingId(null);
                  }}
                >
                  Hide for my squadron
                </button>
              </div>
            </div>
          </div>
        );
      })()}

      <GettingHelpSection />
    </div>
  );
}


// ─── PlanningBottomDrawer ─────────────────────────────────────────────────────

export function PlanningBottomDrawer({ yearId, tab, onTabChange, onClose, facilitators, locations, onItemClick, squadronId }: Props) {
  return (
    <div className="pw-bottom-bar" role="complementary" aria-label="Bottom planning drawer">
      <div className="pw-bottom-tabs">
        {TABS.map((t) => (
          <button
            key={t.key}
            className={`pw-btab${tab === t.key ? " active" : ""}`}
            onClick={() => onTabChange(t.key)}
            aria-pressed={tab === t.key}
          >
            {t.label}
          </button>
        ))}
        <button className="pw-btab-close" onClick={onClose} aria-label="Close bottom drawer">×</button>
      </div>
      <div className="pw-bottom-content">
        {tab === "backlog" && yearId && <BacklogContent yearId={yearId} onItemClick={onItemClick} />}
        {tab === "backlog" && !yearId && <div className="pw-empty">No planning year selected.</div>}

        {tab === "facilitators" && (
          <FacilitatorsContent yearId={yearId} facilitators={facilitators} />
        )}

        {tab === "schedule" && <ScheduleContent squadronId={squadronId} />}

        {tab === "rooms" && (
          <RoomsContent
            locations={locations}
            onAddLocation={() => { onItemClick({ type: "new-location" }); onClose(); }}
            onEditLocation={(loc) => { onItemClick({ type: "new-location", location: loc }); onClose(); }}
          />
        )}

        {tab === "equipment" && <EquipmentContent />}

        {tab === "holidays" && yearId && <HolidaysContent yearId={yearId} />}
        {tab === "holidays" && !yearId && <div className="pw-empty">No planning year selected.</div>}

        {tab === "notices" && yearId && <NoticesContent yearId={yearId} />}
        {tab === "notices" && !yearId && <div className="pw-empty">No planning year selected.</div>}

        {tab === "activities" && yearId && <ActivitiesContent yearId={yearId} squadronId={squadronId} />}
        {tab === "activities" && !yearId && <div className="pw-empty">No planning year selected.</div>}
      </div>
    </div>
  );
}
