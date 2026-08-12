import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { planningApi } from "../../../api";
import { friendlyMessage } from "../../../api/client";
import type { AnchorEvent, NightSummary, PlanningConflict } from "../../../api/types";
import { filterAnchors } from "../../../utils/planningFilters";
import { ParadeNightBlock, fromNightSummary } from "../ParadeNightBlock";
import { ActivityDetailBlock, anchorToDisplay } from "../ActivityDetailBlock";

const STALE_5MIN = 5 * 60 * 1000;

interface Props {
  yearId: string;
  onDateClick: (dateId: string, date: string) => void;
  onSessionClick?: (sessionId: string, dateId: string, date: string) => void;
  onEmptyCellClick?: (dateId: string, date: string, cadetGroup: string, period: number) => void;
  onAnchorClick?: (anchor: AnchorEvent) => void;
  layers?: { holidays?: boolean; wingHQEvents?: boolean };
  audience?: Set<string>;
  priority?: Set<string>;
  /** REM-39 residual: already fetched once, year-scoped, by the caller -- passed
   * through to fromNightSummary() so each session cell can show a real,
   * canonical (not client-heuristic) conflict indicator without a second fetch. */
  conflicts?: PlanningConflict[];
}

function fmtDay(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.getDate() + " " + d.toLocaleDateString("en-GB", { month: "short" });
}

function fmtYearRange(start: string, end: string): string {
  const sy = new Date(start + "T00:00:00").getFullYear();
  const ey = new Date(end + "T00:00:00").getFullYear();
  if (sy === ey) return `${fmtDay(start)} – ${fmtDay(end)} ${ey}`;
  return `${fmtDay(start)} ${sy} – ${fmtDay(end)} ${ey}`;
}

function anchorsOnDate(date: string, all: AnchorEvent[]): AnchorEvent[] {
  return all.filter(a => a.start_date <= date && date <= (a.end_date ?? a.start_date));
}

export function YearView({ yearId, onDateClick, onSessionClick, onEmptyCellClick, onAnchorClick, layers, audience, priority, conflicts = [] }: Props) {
  const showHolidays = layers?.holidays ?? true;
  const showAnchors  = layers?.wingHQEvents ?? true;

  const [collapsedTerms, setCollapsedTerms] = useState<Set<string>>(new Set());

  const { data, isLoading, error } = useQuery({
    queryKey: ["planning-annual", yearId],
    queryFn: () => planningApi.annualProgram(yearId),
    staleTime: STALE_5MIN,
  });

  // Session details, conflict counts, and notices are now embedded in the annual-program
  // response — no separate night-summaries call needed.
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

  function toggleTerm(termName: string) {
    setCollapsedTerms(prev => {
      const next = new Set(prev);
      next.has(termName) ? next.delete(termName) : next.add(termName);
      return next;
    });
  }

  if (isLoading) return <div className="pw-loading">Loading annual programme…</div>;
  if (error || !data) {
    const msg = friendlyMessage(error, "Unknown error");
    return (
      <div className="pw-err" style={{ padding: 16 }}>
        <div style={{ fontWeight: 700, marginBottom: 4 }}>Could not load the annual programme</div>
        <div style={{ fontSize: 12, opacity: .8 }}>{msg}</div>
        <div style={{ fontSize: 11, marginTop: 6, color: "var(--muted-text)" }}>
          Check that you have an internet connection, then reload the page.
        </div>
      </div>
    );
  }

  const totalActiveDates = data.terms.reduce(
    (sum, t) => sum + t.parade_dates.filter(pd => pd.is_active !== false).length,
    0,
  );

  if (totalActiveDates === 0) {
    return (
      <div className="pw-empty">
        <span>No parade nights set up for this planning year.</span>
        <span style={{ fontSize: 11 }}>
          Generate parade dates using the setup wizard, or add individual nights from the Year panel.
        </span>
      </div>
    );
  }

  // One unified CSS grid — term headers span all columns, blocks auto-place into columns.
  // This enforces equal-width blocks across all terms.
  return (
    <div className="pw-year-full-grid">
      {data.terms.map(term => {
        const isCollapsed = collapsedTerms.has(term.term);
        const visibleAnchors = showAnchors
          ? filterAnchors(term.activities ?? [], audience ?? new Set(), priority ?? new Set())
          : [];

        return (
          <div key={term.term} className="pw-year-term-section">

            {/* Full-width term header */}
            <div
              className="pw-year-term-hdr"
              onClick={() => toggleTerm(term.term)}
              role="button"
              tabIndex={0}
              aria-expanded={!isCollapsed}
              onKeyDown={e => e.key === "Enter" && toggleTerm(term.term)}
            >
              <div className="pw-year-term-label">
                <span className="pw-year-term-name">{term.term}</span>
                <span className="pw-year-term-meta">
                  {fmtYearRange(term.start_date, term.end_date)}
                </span>
                <span className="pw-year-term-count">
                  {term.parade_dates.length} parade night{term.parade_dates.length !== 1 ? "s" : ""}
                </span>
              </div>
              <span className="pw-year-term-toggle">{isCollapsed ? "▼ Show" : "▲ Hide"}</span>
            </div>

            {!isCollapsed && (
              <>
                {visibleAnchors.length > 0 && (
                  <div className="pw-anchor-strip pw-year-anchor-row">
                    {visibleAnchors.map((a, i) => (
                      <ActivityDetailBlock
                        key={a.anchor_event_id ?? String(i)}
                        activity={anchorToDisplay(a)}
                        compact
                        onClick={onAnchorClick ? () => onAnchorClick(a) : undefined}
                      />
                    ))}
                  </div>
                )}

                {/* Equal-width block grid for this term's parade nights */}
                <div className="pw-year-block-grid">
                  {term.parade_dates.filter(pd => pd.is_active !== false).length === 0 && (
                    <div style={{ padding: "14px 16px", fontSize: 13, color: "var(--muted-text)", fontStyle: "italic", gridColumn: "1 / -1" }}>
                      No parade nights scheduled for this term.
                    </div>
                  )}
                  {term.parade_dates.filter(pd => pd.is_active !== false).map(pd => {
                    const night = summaryMap.get(pd.parade_date_id);
                    const inHoliday = showHolidays && pd.in_holiday;
                    const dateAnchors = showAnchors
                      ? anchorsOnDate(pd.parade_date, term.activities ?? [])
                      : [];

                    if (night) {
                      return (
                        <div key={pd.parade_date_id} className="pw-year-block-wrap">
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
                            blockSize="sm"
                            onHeaderClick={() => onDateClick(pd.parade_date_id, pd.parade_date)}
                            onSessionClick={onSessionClick
                              ? (ds) => onSessionClick(ds.session_id, pd.parade_date_id, pd.parade_date)
                              : undefined}
                            onEmptyCellClick={onEmptyCellClick
                              ? (cg, period) => onEmptyCellClick(pd.parade_date_id, pd.parade_date, cg, period)
                              : undefined}
                          />
                          {dateAnchors.length > 0 && (
                            <div className="pw-anchor-strip" style={{ marginTop: 4 }}>
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

                    // Fallback block (summaryMap is always populated from annual-program)
                    return (
                      <div
                        key={pd.parade_date_id}
                        className={`pw-block standard pw-block-sm${inHoliday ? " holiday" : ""}`}
                        role="button"
                        tabIndex={0}
                        onClick={() => onDateClick(pd.parade_date_id, pd.parade_date)}
                        onKeyDown={e => e.key === "Enter" && onDateClick(pd.parade_date_id, pd.parade_date)}
                      >
                        <div className="pw-block-hdr" style={{ pointerEvents: "none" }}>
                          <span className="pw-block-date">
                            {(() => {
                              const d = new Date(pd.parade_date + "T00:00:00");
                              return `${d.toLocaleDateString("en-GB", { weekday: "short" })} ${d.getDate()} ${d.toLocaleDateString("en-GB", { month: "short" })}`;
                            })()}
                          </span>
                          {inHoliday && <span className="pw-block-standdown">Stand-down</span>}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </>
            )}
          </div>
        );
      })}
    </div>
  );
}
