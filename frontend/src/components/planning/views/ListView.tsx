import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { planningApi } from "../../../api";
import { friendlyMessage } from "../../../api/client";
import type { AnchorEvent, NightSummary, PlanningConflict } from "../../../api/types";
import { BLOCK_GROUPS, BLOCK_PERIODS, fromNightSummary } from "../ParadeNightBlock";
import type { DisplaySession } from "../ParadeNightBlock";
import { ActivityDetailBlock, anchorToDisplay } from "../ActivityDetailBlock";

function fmtHuman(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.getDate() + " " + d.toLocaleDateString("en-GB", { month: "short" });
}
function fmtHumanRange(start: string, end: string): string {
  const sy = new Date(start + "T00:00:00").getFullYear();
  const ey = new Date(end + "T00:00:00").getFullYear();
  return sy === ey
    ? `${fmtHuman(start)} – ${fmtHuman(end)} ${ey}`
    : `${fmtHuman(start)} ${sy} – ${fmtHuman(end)} ${ey}`;
}

export type ViewRange = "year" | "term" | "8week" | "2week" | "parade-night" | "custom";

interface Props {
  yearId: string;
  viewRange: ViewRange;
  customStart?: string;
  customEnd?: string;
  conflicts?: PlanningConflict[];
  onDateClick: (dateId: string, date: string) => void;
  onAnchorClick?: (anchor: AnchorEvent) => void;
}

const RANGE_LABELS: Record<ViewRange, string> = {
  year:           "All parade nights",
  term:           "Parade nights this term",
  "8week":        "Next 8 weeks",
  "2week":        "Next 2 weeks",
  "parade-night": "Parade night",
  custom:         "Custom range",
};

const GROUP_LABELS: Record<string, string> = {
  oi: "O&I", bronze: "Bronze", silver: "Silver", gold: "Gold",
};

function findCell(
  sessions: DisplaySession[],
  cadetGroups: readonly string[],
  period: number,
): DisplaySession | null {
  const hit = sessions.find(
    s => s.period === period &&
      s.cadet_group !== null &&
      (cadetGroups as string[]).includes(s.cadet_group as string),
  );
  return hit ?? sessions.find(s => s.period === period && s.cadet_group === null) ?? null;
}

function fmt(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  const day = d.getDate();
  const mon = d.toLocaleDateString("en-GB", { month: "short" });
  const wd = d.toLocaleDateString("en-GB", { weekday: "short" });
  return `${wd}, ${day} ${mon}`;
}

function filterActivitiesByRange(
  anchors: AnchorEvent[],
  viewRange: ViewRange,
  today: string,
  customStart?: string,
  customEnd?: string,
): AnchorEvent[] {
  if (viewRange === "year") return anchors;
  let rangeStart = today;
  let rangeEnd = today;

  if (viewRange === "2week") {
    const cut = new Date(); cut.setDate(cut.getDate() + 14);
    rangeEnd = cut.toISOString().slice(0, 10);
  } else if (viewRange === "8week") {
    const cut = new Date(); cut.setDate(cut.getDate() + 56);
    rangeEnd = cut.toISOString().slice(0, 10);
  } else if (viewRange === "custom" && customStart && customEnd) {
    rangeStart = customStart;
    rangeEnd = customEnd;
  } else {
    return anchors;
  }

  return anchors.filter(a => {
    const aEnd = a.end_date ?? a.start_date;
    return a.start_date <= rangeEnd && aEnd >= rangeStart;
  });
}

export function ListView({ yearId, viewRange, customStart, customEnd, conflicts = [], onDateClick, onAnchorClick }: Props) {
  const today = new Date().toISOString().slice(0, 10);

  const { data: nightData, isLoading: nightLoading, error: nightError } = useQuery({
    queryKey: ["planning-night-summaries", yearId],
    queryFn: () => planningApi.nightSummaries(yearId),
    staleTime: 2 * 60 * 1000,
  });

  const { data: anchorData, isLoading: anchorLoading, error: anchorError } = useQuery({
    queryKey: ["planning-anchors", yearId],
    queryFn: () => planningApi.listAnchors(yearId),
    staleTime: 2 * 60 * 1000,
  });

  const summaries = useMemo((): NightSummary[] => {
    if (!nightData?.summaries) return [];
    let list = [...nightData.summaries];

    if (viewRange === "2week") {
      const cutoff = new Date();
      cutoff.setDate(cutoff.getDate() + 14);
      list = list.filter(s => s.parade_date >= today && s.parade_date <= cutoff.toISOString().slice(0, 10));
    } else if (viewRange === "8week") {
      const cutoff = new Date();
      cutoff.setDate(cutoff.getDate() + 56);
      list = list.filter(s => s.parade_date >= today && s.parade_date <= cutoff.toISOString().slice(0, 10));
    } else if (viewRange === "custom" && customStart && customEnd) {
      list = list.filter(s => s.parade_date >= customStart && s.parade_date <= customEnd);
    }

    return list;
  }, [nightData, viewRange, customStart, customEnd, today]);

  const activities = useMemo((): AnchorEvent[] => {
    const raw: AnchorEvent[] = Array.isArray(anchorData) ? anchorData : [];
    return filterActivitiesByRange(raw, viewRange, today, customStart, customEnd)
      .sort((a, b) => a.start_date.localeCompare(b.start_date));
  }, [anchorData, viewRange, today, customStart, customEnd]);

  const isLoading = nightLoading || anchorLoading;
  if (isLoading) return <div className="pw-loading">Loading…</div>;

  const loadError = nightError || anchorError;
  if (loadError) {
    const msg = friendlyMessage(loadError, "Unknown error");
    return (
      <div className="pw-err" style={{ padding: 16 }}>
        <div style={{ fontWeight: 700, marginBottom: 4 }}>Could not load the parade night list</div>
        <div style={{ fontSize: 12, opacity: .8 }}>{msg}</div>
        <div style={{ fontSize: 11, marginTop: 6, color: "var(--muted-text)" }}>
          Check that you have an internet connection, then reload the page.
        </div>
      </div>
    );
  }

  const rangeLabel = viewRange === "custom" && customStart && customEnd
    ? fmtHumanRange(customStart, customEnd)
    : RANGE_LABELS[viewRange];

  return (
    <div className="pw-list-full">
      {/* Activities section */}
      {activities.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <div style={{
            fontSize: 13, fontWeight: 700, color: "var(--aafc-dark-blue)",
            borderBottom: "2px solid var(--aafc-dark-blue)", paddingBottom: 6, marginBottom: 12,
          }}>
            Activities — {rangeLabel}
            <span style={{ fontSize: 11, fontWeight: 400, color: "#6b7a87", marginLeft: 8 }}>
              {activities.length} activit{activities.length !== 1 ? "ies" : "y"}
            </span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
            {activities.map(a => (
              <ActivityDetailBlock
                key={a.anchor_event_id}
                activity={anchorToDisplay(a)}
                compact={false}
                onClick={onAnchorClick ? () => onAnchorClick(a) : undefined}
              />
            ))}
          </div>
        </div>
      )}

      {/* Parade nights section */}
      <div className="pw-list-full-header">
        <span className="pw-list-full-title">Parade nights — {rangeLabel}</span>
        <span className="pw-list-full-count">
          {summaries.length} parade night{summaries.length !== 1 ? "s" : ""}
        </span>
      </div>

      {summaries.length === 0 ? (
        <div className="pw-empty" style={{ margin: 0 }}>
          <span>No parade nights in this range.</span>
        </div>
      ) : (
        <div className="pw-lv-table-wrap">
          <table className="pw-lv-table">
            <thead>
              <tr>
                <th className="pw-lv-th" style={{ position: "sticky", left: 0, zIndex: 2 }}>Date</th>
                <th className="pw-lv-th">Status</th>
                <th className="pw-lv-th">Notices</th>
                {BLOCK_GROUPS.map(g => (
                  <th key={g.key} className="pw-lv-th" style={{ minWidth: 200 }}>
                    {GROUP_LABELS[g.key]}
                  </th>
                ))}
                <th className="pw-lv-th">Warnings</th>
                <th className="pw-lv-th">Actions</th>
              </tr>
            </thead>
            <tbody>
              {summaries.map(s => {
                const displaySessions = fromNightSummary(s.sessions, conflicts);
                const isStandDown = s.parade_type === "cancelled" || s.parade_type === "stand_down";

                return (
                  <tr key={s.parade_date_id}>
                    <td
                      className="pw-lv-td pw-lv-td-date"
                      style={{ position: "sticky", left: 0, background: "#fff", zIndex: 1 }}
                    >
                      {fmt(s.parade_date)}
                      {s.term && (
                        <div style={{ fontSize: 10, fontWeight: 400, color: "var(--muted-text)" }}>
                          {s.term}{s.week_number ? ` · Wk ${s.week_number}` : ""}
                        </div>
                      )}
                    </td>

                    <td className="pw-lv-td">
                      {isStandDown ? (
                        <span style={{ fontSize: 10, fontWeight: 700, color: "var(--muted-text)",
                          background: "#f0f0f0", borderRadius: 20, padding: "2px 8px" }}>
                          Stand-down
                        </span>
                      ) : (
                        <span style={{ fontSize: 10, fontWeight: 700, color: "var(--aafc-dark-blue)",
                          background: "#EEF4FB", borderRadius: 20, padding: "2px 8px" }}>
                          Planned
                        </span>
                      )}
                    </td>

                    <td className="pw-lv-td" style={{ maxWidth: 120 }}>
                      {s.notices.length === 0 ? (
                        <span style={{ color: "var(--muted-text)", fontSize: 10 }}>—</span>
                      ) : (
                        s.notices.map(n => (
                          <div key={n.notice_id} style={{
                            fontSize: 10, marginBottom: 2, overflow: "hidden",
                            textOverflow: "ellipsis", whiteSpace: "nowrap",
                            color: n.priority === "urgent" ? "var(--aafc-red)" : undefined,
                          }}>
                            {n.priority === "urgent" ? "! " : ""}{n.notice_text}
                          </div>
                        ))
                      )}
                    </td>

                    {BLOCK_GROUPS.map(g => (
                      <td key={g.key} className="pw-lv-td pw-lv-td-group">
                        {BLOCK_PERIODS.map((period, pi) => {
                          const cell = findCell(displaySessions, g.cadetGroups, period);
                          return (
                            <div
                              key={period}
                              className="pw-lv-period-row"
                              style={pi === BLOCK_PERIODS.length - 1 ? { borderBottom: "none" } : undefined}
                            >
                              <span className="pw-lv-p-num">P{period}</span>
                              {cell ? (
                                <div className="pw-lv-p-content">
                                  <span className="pw-lv-p-title">
                                    {cell.conflict === "room" && <span className="pn-conflict-dot room" style={{ marginRight: 4 }} title="Room double-booked" />}
                                    {cell.conflict === "fac" && <span className="pn-conflict-dot fac" style={{ marginRight: 4 }} title="Facilitator double-booked" />}
                                    {cell.title ?? "—"}
                                  </span>
                                  {(cell.location || cell.facilitator) && (
                                    <span className="pw-lv-p-detail">
                                      {[cell.location, cell.facilitator].filter(Boolean).join(" · ")}
                                    </span>
                                  )}
                                </div>
                              ) : (
                                <span className="pw-lv-empty-period">—</span>
                              )}
                            </div>
                          );
                        })}
                      </td>
                    ))}

                    <td className="pw-lv-td" style={{ textAlign: "center" }}>
                      {s.conflict_count > 0 ? (
                        <span
                          style={{ fontSize: 11, fontWeight: 700, color: "var(--warning)" }}
                          title={`${s.conflict_count} unresolved conflict${s.conflict_count !== 1 ? "s" : ""} (room, facilitator, or workload double-booking) — open this parade night to see and resolve each one`}
                        >
                          ⚠ {s.conflict_count}
                        </span>
                      ) : (
                        <span style={{ color: "var(--muted-text)", fontSize: 10 }}>—</span>
                      )}
                    </td>

                    <td className="pw-lv-td">
                      <button
                        className="btn sm out"
                        style={{ fontSize: 11, padding: "3px 8px" }}
                        onClick={() => onDateClick(s.parade_date_id, s.parade_date)}
                      >
                        Open
                      </button>
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
