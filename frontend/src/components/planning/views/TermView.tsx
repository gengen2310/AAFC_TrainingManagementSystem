import { ErrorRemedy } from "../../ui";
import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { planningApi } from "../../../api";
import { friendlyMessage } from "../../../api/client";
import type { AnchorEvent, NightSummary, PlanningConflict, TrainingClassSummary } from "../../../api/types";
import { filterAnchors } from "../../../utils/planningFilters";
import { ParadeNightBlock, fromNightSummary } from "../ParadeNightBlock";
import { ActivityDetailBlock, anchorToDisplay } from "../ActivityDetailBlock";

const STALE_5MIN = 5 * 60 * 1000;

function fmtDay(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.getDate() + " " + d.toLocaleDateString("en-GB", { month: "short" });
}

function fmtTermRange(start: string, end: string): string {
  const sy = new Date(start + "T00:00:00").getFullYear();
  const ey = new Date(end + "T00:00:00").getFullYear();
  if (sy === ey) return `${fmtDay(start)} – ${fmtDay(end)} ${sy}`;
  return `${fmtDay(start)} ${sy} – ${fmtDay(end)} ${ey}`;
}

interface Props {
  yearId: string;
  onDateClick: (dateId: string, date: string) => void;
  onSessionClick?: (sessionId: string, dateId: string, date: string) => void;
  onEmptyCellClick?: (dateId: string, date: string, cadetGroup: string, period: number, trainingClassId?: string) => void;
  onAnchorClick?: (anchor: AnchorEvent) => void;
  layers?: { holidays?: boolean; wingHQEvents?: boolean };
  audience?: Set<string>;
  priority?: Set<string>;
  trainingClasses?: TrainingClassSummary[];
  focusClassId?: string | null;
  searchText?: string | null;
  tierFilter?: string | null;
  focusStageId?: string | null;
  classStageMap?: Record<string, string>;
  /** REM-39 residual: already fetched once, year-scoped, by the caller -- passed
   * through to fromNightSummary() so each session cell can show a real,
   * canonical (not client-heuristic) conflict indicator without a second fetch. */
  conflicts?: PlanningConflict[];
}

function anchorsOnDate(date: string, all: AnchorEvent[]): AnchorEvent[] {
  return all.filter(a => a.start_date <= date && date <= (a.end_date ?? a.start_date));
}

export function TermView({ yearId, onDateClick, onSessionClick, onEmptyCellClick, onAnchorClick, layers, audience, priority, trainingClasses, focusClassId, searchText, tierFilter, focusStageId, classStageMap, conflicts = [] }: Props) {
  const showHolidays = layers?.holidays ?? true;
  const showAnchors  = layers?.wingHQEvents ?? true;
  const [termIndex, setTermIndex] = useState(0);

  const { data, isLoading, error } = useQuery({
    queryKey: ["planning-annual", yearId],
    queryFn: () => planningApi.annualProgram(yearId),
    staleTime: STALE_5MIN,
  });

  // Session details, conflict counts, and notices are embedded in annual-program data.
  const summaryMap = useMemo((): Map<string, NightSummary> => {
    if (!data) return new Map();
    return new Map(
      data.terms.flatMap(t => t.parade_dates).map(pd => [
        pd.parade_date_id,
        {
          parade_date_id: pd.parade_date_id,
          parade_date: pd.parade_date,
          parade_type: pd.parade_type ?? "standard",
          term: (pd as { term?: string | null }).term ?? null,
          week_number: pd.week_number ?? null,
          notes: pd.notes ?? null,
          parade_night_notes: null,
          parade_night_id: pd.parade_night_id ?? null,
          sessions: pd.sessions_summary ?? [],
          conflict_count: pd.conflict_count ?? 0,
          notices: pd.notices ?? [],
        } satisfies NightSummary,
      ]),
    );
  }, [data]);

  if (isLoading) return <div className="pw-loading">Loading term view…</div>;
  if (error || !data) {
    const msg = friendlyMessage(error, "Unknown error");
    return (
      <div className="pw-err" style={{ padding: 16 }}>
        <div style={{ fontWeight: 700, marginBottom: 4 }}>Could not load term data</div>
        <div style={{ fontSize: 'var(--fs-sm)', opacity: .8 }}>{msg}</div>
        <ErrorRemedy error={error} />
      </div>
    );
  }

  const term = data.terms[termIndex];
  if (!term) return <div className="pw-empty">No terms found.</div>;

  const visibleAnchors = showAnchors
    ? filterAnchors(term.activities ?? [], audience ?? new Set(), priority ?? new Set())
    : [];

  return (
    <div>
      {/* Term selector tabs */}
      <div style={{ display: "flex", gap: 6, marginBottom: 14 }}>
        {data.terms.map((t, i) => (
          <button
            key={t.term}
            className={`pw-mode-btn${i === termIndex ? " active" : ""}`}
            style={{
              border: "1.5px solid var(--border)",
              color: i === termIndex ? "#fff" : "var(--text)",
              background: i === termIndex ? "var(--aafc-dark-blue)" : "var(--surface)",
            }}
            onClick={() => setTermIndex(i)}
          >
            {t.term}
          </button>
        ))}
      </div>

      <div className="pw-term">
        <div className="pw-term-hdr">
          <span>{term.term}</span>
          <span style={{ fontSize: 'var(--fs-xs)', fontWeight: 400 }}>
            {fmtTermRange(term.start_date, term.end_date)} · {term.parade_dates.length} parade night{term.parade_dates.length !== 1 ? "s" : ""}
          </span>
        </div>

        {visibleAnchors.length > 0 && (
          <div className="pw-anchor-strip" style={{ marginBottom: 10 }}>
            {visibleAnchors.map((a, i) => (
              <ActivityDetailBlock
                key={a.anchor_event_id ?? String(i)}
                activity={anchorToDisplay(a)}
                compact={false}
                onClick={onAnchorClick ? () => onAnchorClick(a) : undefined}
              />
            ))}
          </div>
        )}

        <div className="pw-8week">
          {term.parade_dates.map(pd => {
            const night = summaryMap.get(pd.parade_date_id);
            const inHoliday = showHolidays && pd.in_holiday;
            const dateAnchors = showAnchors ? anchorsOnDate(pd.parade_date, term.activities ?? []) : [];

            if (night) {
              return (
                <div key={pd.parade_date_id}>
                  <ParadeNightBlock
                    dateId={pd.parade_date_id}
                    date={night.parade_date}
                    weekNumber={night.week_number}
                    term={night.term}
                    notices={night.notices}
                    sessions={fromNightSummary(night.sessions, conflicts)}
                    sessionCount={pd.session_count}
                    filledSlots={pd.filled_count}
                    conflictCount={night.conflict_count}
                    inHoliday={!!inHoliday}
                    compact={false}
                    focusClassId={focusClassId}
                    searchText={searchText}
                    tierFilter={tierFilter}
                    focusStageId={focusStageId}
                    classStageMap={classStageMap}
                    onHeaderClick={() => onDateClick(pd.parade_date_id, pd.parade_date)}
                    onSessionClick={onSessionClick
                      ? (ds) => onSessionClick(ds.session_id, pd.parade_date_id, pd.parade_date)
                      : undefined}
                    trainingClasses={trainingClasses}
                    onEmptyCellClick={onEmptyCellClick
                      ? (cg, period, tcId) => onEmptyCellClick(pd.parade_date_id, pd.parade_date, cg, period, tcId)
                      : undefined}
                  />
                  {dateAnchors.length > 0 && (
                    <div className="pw-anchor-strip" style={{ marginTop: 4, marginBottom: 2 }}>
                      {dateAnchors.map((a, i) => (
                        <ActivityDetailBlock
                          key={a.anchor_event_id ?? String(i)}
                          activity={anchorToDisplay(a)}
                          compact
                          onClick={onAnchorClick ? () => onAnchorClick(a) : undefined}
                        />
                      ))}
                    </div>
                  )}
                </div>
              );
            }

            return (
              <div
                key={pd.parade_date_id}
                className={`pw-block standard${inHoliday ? " holiday" : ""}`}
                role="button"
                tabIndex={0}
                onClick={() => onDateClick(pd.parade_date_id, pd.parade_date)}
                onKeyDown={e => e.key === "Enter" && onDateClick(pd.parade_date_id, pd.parade_date)}
              >
                <div className="pw-block-hdr" style={{ pointerEvents: "none" }}>
                  <span className="pw-block-date">
                    {(() => {
                      const d = new Date(pd.parade_date + "T00:00:00");
                      return `${d.toLocaleDateString("en-GB", { weekday: "long" })}, ${d.getDate()} ${d.toLocaleDateString("en-GB", { month: "short" })}`;
                    })()}
                  </span>
                  <span className="pw-block-fill">{pd.filled_count}/{pd.session_count}</span>
                  {inHoliday && <span className="pw-block-standdown">Stand-down</span>}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
