import { useQuery } from "@tanstack/react-query";
import { planningApi } from "../../../api";
import type { PlanningSession, PlanningFacilitator } from "../../../api/types";

interface Props {
  yearId: string;
  weeks?: 2 | 8;
  facilitators: PlanningFacilitator[];
  onDateClick: (dateId: string, date: string) => void;
  onSessionClick: (session: PlanningSession, dateId: string, date: string) => void;
  layers?: { conflicts?: boolean; wingHQEvents?: boolean };
}

function detectConflict(s: PlanningSession, siblings: PlanningSession[]): "room" | "fac" | null {
  const same = siblings.filter(x => x.session_id !== s.session_id && x.session_number === s.session_number);
  if (s.location_id && same.some(x => x.location_id === s.location_id)) return "room";
  if (s.facilitator_id && same.some(x => x.facilitator_id === s.facilitator_id)) return "fac";
  return null;
}

export function EightWeekView({ yearId, weeks = 8, facilitators, onDateClick, onSessionClick, layers }: Props) {
  const showConflicts = layers?.conflicts ?? true;
  const showAnchors = layers?.wingHQEvents ?? true;
  const { data, isLoading, error } = useQuery({
    queryKey: ["planning-long-range", yearId, weeks],
    queryFn: () => planningApi.longRange(yearId, weeks),
  });

  if (isLoading) return <div className="pw-loading">Loading {weeks}-week view…</div>;
  if (error || !data) return <div className="pw-err">Failed to load long-range view.</div>;

  if (data.parade_dates.length === 0) {
    return (
      <div className="pw-empty">
        <span>No parade nights in the next {weeks} weeks.</span>
        <span style={{ fontSize: 11 }}>Ensure parade dates are set up in the annual program.</span>
      </div>
    );
  }

  return (
    <div className="pw-8week">
      {showAnchors && data.anchors.length > 0 && (
        <div className="pw-anchor-strip" style={{ marginBottom: 8 }}>
          {data.anchors.map((a, i) => (
            <span key={a.anchor_event_id ?? a.anchor_id ?? String(i)} className={`pw-anchor-pill ${a.importance ?? "optional"}`}>
              {a.event_name} · {a.start_date}
            </span>
          ))}
        </div>
      )}

      {data.parade_dates.map((row) => {
        const pd = row.parade_date;
        const hasConflict = row.conflicts.some(c => !c.is_resolved);
        const facOverloaded = new Set<string>();
        const facPeriods = new Map<string, Set<number>>();
        for (const s of row.sessions) {
          if (s.facilitator_id) {
            if (!facPeriods.has(s.facilitator_id)) facPeriods.set(s.facilitator_id, new Set());
            facPeriods.get(s.facilitator_id)!.add(s.session_number);
          }
        }
        for (const [fid, periods] of facPeriods) {
          const fac = facilitators.find(f => f.facilitator_id === fid);
          if (periods.size > (fac?.max_sessions_per_night ?? 2)) facOverloaded.add(fid);
        }

        return (
          <div key={pd.parade_date_id} className="pw-week-card">
            <div className="pw-week-hdr" onClick={() => onDateClick(pd.parade_date_id, pd.parade_date)}>
              <span className="pw-week-date">
                {new Date(pd.parade_date + "T00:00:00").toLocaleDateString("en-CA", {
                  weekday: "long", month: "long", day: "numeric",
                })}
              </span>
              {pd.term && (
                <span className="pw-week-term">Term {pd.term}{pd.week_number ? ` · Wk ${pd.week_number}` : ""}</span>
              )}
              <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--muted-text)" }}>
                {row.filled_slots}/{row.session_count} filled
              </span>
              {showConflicts && hasConflict && <span className="pw-conflict-badge room">⚠ conflict</span>}
            </div>

            {row.sessions.length === 0 ? (
              <div style={{ padding: "10px 14px", fontSize: 11, color: "var(--muted-text)" }}>
                No sessions planned — click to open night
              </div>
            ) : (
              <div className="pw-week-sessions">
                {row.sessions.map((s) => {
                  const c = detectConflict(s, row.sessions);
                  const overload = s.facilitator_id ? facOverloaded.has(s.facilitator_id) : false;
                  return (
                    <div
                      key={s.session_id}
                      className={`pw-sess-mini${c === "room" ? " conflict-room" : c === "fac" ? " conflict-fac" : ""}`}
                      onClick={() => onSessionClick(s, pd.parade_date_id, pd.parade_date)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => e.key === "Enter" && onSessionClick(s, pd.parade_date_id, pd.parade_date)}
                    >
                      <div className="pw-sess-mini-period">
                        S{s.session_number}
                        {s.part_number ? `.${s.part_number}` : ""}
                        {s.cadet_group ? ` · ${s.cadet_group}` : ""}
                      </div>
                      <div className="pw-sess-mini-title">{s.activity_title ?? "—"}</div>
                      <div className="pw-sess-mini-fac">{s.facilitator_name ?? "No facilitator"}</div>
                      {showConflicts && c === "room" && <span className="pw-conflict-badge room">🔴 room</span>}
                      {showConflicts && c === "fac" && <span className="pw-conflict-badge fac">🟡 fac</span>}
                      {showConflicts && overload && <span className="pw-conflict-badge load">🟠 load</span>}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
