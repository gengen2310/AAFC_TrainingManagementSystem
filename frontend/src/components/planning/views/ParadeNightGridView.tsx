import { useQuery } from "@tanstack/react-query";
import { planningApi } from "../../../api";
import type { PlanningSession, PlanningFacilitator, PlanningConflict, TimingBlock } from "../../../api/types";
import type { DrawerItem } from "../PlanningRightDrawer";

const DISPLAY_GROUPS = [
  { label: "Orientation & Initial", groups: ["orientation", "initial"] },
  { label: "Junior & Bronze CLP", groups: ["junior"] },
  { label: "Intermediate & Silver CLP", groups: ["intermediate"] },
  { label: "Senior & Gold CLP", groups: ["senior"] },
] as const;

interface CellConflict {
  room: boolean;
  fac: boolean;
  load: boolean;
}

function computeConflicts(
  sessions: PlanningSession[],
  facilitators: PlanningFacilitator[],
): Map<string, CellConflict> {
  const result = new Map<string, CellConflict>();

  const byPeriod = new Map<number, PlanningSession[]>();
  for (const s of sessions) {
    const list = byPeriod.get(s.session_number) ?? [];
    list.push(s);
    byPeriod.set(s.session_number, list);
  }

  for (const periodSessions of byPeriod.values()) {
    const roomMap = new Map<string, string[]>();
    const facMap = new Map<string, string[]>();
    for (const s of periodSessions) {
      if (s.location_id) {
        const l = roomMap.get(s.location_id) ?? [];
        l.push(s.session_id);
        roomMap.set(s.location_id, l);
      }
      if (s.facilitator_id) {
        const l = facMap.get(s.facilitator_id) ?? [];
        l.push(s.session_id);
        facMap.set(s.facilitator_id, l);
      }
    }
    for (const ids of roomMap.values()) {
      if (ids.length > 1) {
        for (const id of ids) {
          const c = result.get(id) ?? { room: false, fac: false, load: false };
          c.room = true;
          result.set(id, c);
        }
      }
    }
    for (const ids of facMap.values()) {
      if (ids.length > 1) {
        for (const id of ids) {
          const c = result.get(id) ?? { room: false, fac: false, load: false };
          c.fac = true;
          result.set(id, c);
        }
      }
    }
  }

  const facPeriodSets = new Map<string, Set<number>>();
  for (const s of sessions) {
    if (s.facilitator_id) {
      if (!facPeriodSets.has(s.facilitator_id)) facPeriodSets.set(s.facilitator_id, new Set());
      facPeriodSets.get(s.facilitator_id)!.add(s.session_number);
    }
  }
  for (const [fid, periods] of facPeriodSets) {
    const fac = facilitators.find(f => f.facilitator_id === fid);
    const maxSessions = fac?.max_sessions_per_night ?? 2;
    if (periods.size > maxSessions) {
      for (const s of sessions) {
        if (s.facilitator_id === fid) {
          const c = result.get(s.session_id) ?? { room: false, fac: false, load: false };
          c.load = true;
          result.set(s.session_id, c);
        }
      }
    }
  }

  return result;
}

function sessionForCell(
  sessions: PlanningSession[],
  groups: readonly string[],
  block: TimingBlock,
): PlanningSession | undefined {
  return sessions.find(
    s => s.session_number === block.period_number &&
      s.cadet_group !== null &&
      groups.includes(s.cadet_group as string),
  );
}

interface Props {
  dateId: string;
  facilitators: PlanningFacilitator[];
  onCellClick: (item: DrawerItem) => void;
}

export function ParadeNightGridView({ dateId, facilitators, onCellClick }: Props) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["planning-weekly", dateId],
    queryFn: () => planningApi.weeklyProgram(dateId),
  });

  if (isLoading) return <div className="pw-loading">Loading parade night…</div>;
  if (error || !data) return <div className="pw-err">Failed to load parade night data.</div>;

  const conflicts = computeConflicts(data.sessions, facilitators);
  const blocks = data.timing_blocks;
  const unresolvedConflicts: PlanningConflict[] = data.conflicts.filter(c => !c.is_resolved);

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10, flexWrap: "wrap" }}>
        <span style={{ fontSize: 14, fontWeight: 800, color: "var(--aafc-dark-blue)" }}>
          {new Date(data.parade_date + "T00:00:00").toLocaleDateString("en-CA", {
            weekday: "long", year: "numeric", month: "long", day: "numeric",
          })}
        </span>
        {unresolvedConflicts.length > 0 && (
          <span className="pw-conflict-badge room">
            ⚠ {unresolvedConflicts.length} conflict{unresolvedConflicts.length !== 1 ? "s" : ""}
          </span>
        )}
        {!data.parade_night_id && (
          <span style={{ fontSize: 11, color: "var(--muted-text)" }}>Draft — not yet linked to a parade night</span>
        )}
      </div>

      <div className="pn-grid-wrap">
        <table className="pn-grid">
          <thead>
            <tr>
              <th>Group</th>
              {blocks.map((b) => (
                <th key={b.sequence} className={b.block_type === "break" ? "break-col" : ""}>
                  {b.name}
                  {b.start_time && b.end_time && (
                    <div style={{ fontWeight: 400, fontSize: 10, opacity: 0.8 }}>
                      {b.start_time}–{b.end_time}
                    </div>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {DISPLAY_GROUPS.map((dg) => (
              <tr key={dg.label}>
                <th>{dg.label}</th>
                {blocks.map((b) => {
                  if (b.block_type === "break" || !b.is_instructional || b.period_number === null) {
                    return (
                      <td key={b.sequence} className="pn-grid-cell">
                        <div className="pn-cell-inner break-cell">{b.name}</div>
                      </td>
                    );
                  }

                  const session = sessionForCell(data.sessions, dg.groups, b);

                  if (!session) {
                    return (
                      <td key={b.sequence} className="pn-grid-cell">
                        <button
                          className="pn-add-btn"
                          onClick={() =>
                            onCellClick({
                              type: "new-session",
                              cadetGroup: dg.groups[0],
                              periodNumber: b.period_number!,
                              dateId,
                            })
                          }
                          aria-label={`Add session for ${dg.label}, period ${b.period_number}`}
                        >
                          + Add
                        </button>
                      </td>
                    );
                  }

                  const c = conflicts.get(session.session_id);
                  const cellCls = c?.room ? "conflict-room" : c?.fac ? "conflict-fac" : "";
                  const sessionConflicts = unresolvedConflicts.filter(
                    x => x.scheduled_session_id === session.session_id,
                  );

                  return (
                    <td key={b.sequence} className="pn-grid-cell">
                      <div
                        className={`pn-cell-inner ${cellCls}`}
                        onClick={() =>
                          onCellClick({
                            type: "session",
                            session,
                            dateId,
                            date: data.parade_date,
                            conflicts: sessionConflicts,
                          })
                        }
                        role="button"
                        tabIndex={0}
                        onKeyDown={(e) =>
                          e.key === "Enter" &&
                          onCellClick({ type: "session", session, dateId, date: data.parade_date, conflicts: sessionConflicts })
                        }
                        aria-label={`${session.activity_title ?? "Session"} — ${dg.label}`}
                      >
                        {c && (
                          <div className="pn-cell-conflict">
                            {c.room && <span className="pn-conflict-dot room" title="Room double-booked" aria-label="Room conflict" />}
                            {c.fac && <span className="pn-conflict-dot fac" title="Facilitator double-booked" aria-label="Facilitator conflict" />}
                            {c.load && <span className="pn-conflict-dot load" title="Facilitator overloaded" aria-label="Facilitator overload" />}
                          </div>
                        )}
                        {session.curriculum_code && (
                          <div className="pn-cell-code">{session.curriculum_code}</div>
                        )}
                        <div className="pn-cell-title">{session.activity_title ?? "—"}</div>
                        {session.location_name && (
                          <div className="pn-cell-room">{session.location_name}</div>
                        )}
                        <div className="pn-cell-fac">
                          {session.facilitator_name ?? "No facilitator"}
                          {session.assistant_facilitator_name && ` + ${session.assistant_facilitator_name}`}
                        </div>
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
