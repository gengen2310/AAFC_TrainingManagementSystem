import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { planningApi } from "../../../api";
import type { AnchorEvent, NightSummary } from "../../../api/types";
import { filterAnchors } from "../../../utils/planningFilters";
import { ParadeNightBlock, fromNightSummary } from "../ParadeNightBlock";
import { ActivityDetailBlock, anchorToDisplay } from "../ActivityDetailBlock";

interface Props {
  yearId: string;
  onDateClick: (dateId: string, date: string) => void;
  onAnchorClick?: (anchor: AnchorEvent) => void;
  layers?: { holidays?: boolean; wingHQEvents?: boolean };
  audience?: Set<string>;
  priority?: Set<string>;
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

export function YearView({ yearId, onDateClick, onAnchorClick, layers, audience, priority }: Props) {
  const showHolidays = layers?.holidays ?? true;
  const showAnchors  = layers?.wingHQEvents ?? true;

  const [collapsedTerms, setCollapsedTerms] = useState<Set<string>>(new Set());

  const { data, isLoading, error } = useQuery({
    queryKey: ["planning-annual", yearId],
    queryFn: () => planningApi.annualProgram(yearId),
  });

  const { data: nightData, isLoading: summariesLoading, error: summariesError } = useQuery({
    queryKey: ["planning-night-summaries", yearId],
    queryFn: () => planningApi.nightSummaries(yearId),
    staleTime: 2 * 60 * 1000,
  });

  const summaryMap = useMemo(
    () => new Map<string, NightSummary>(
      nightData?.summaries.map(s => [s.parade_date_id, s]) ?? [],
    ),
    [nightData],
  );

  function toggleTerm(termName: string) {
    setCollapsedTerms(prev => {
      const next = new Set(prev);
      next.has(termName) ? next.delete(termName) : next.add(termName);
      return next;
    });
  }

  if (isLoading) return <div className="pw-loading">Loading annual programme…</div>;
  if (error || !data) return <div className="pw-err">Failed to load annual programme.</div>;

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
                            sessions={fromNightSummary(night.sessions)}
                            sessionCount={pd.session_count}
                            filledSlots={pd.filled_count}
                            conflictCount={night.conflict_count}
                            inHoliday={!!inHoliday}
                            compact={false}
                            blockSize="sm"
                            onHeaderClick={() => onDateClick(pd.parade_date_id, pd.parade_date)}
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

                    // Skeleton while summaries load
                    return (
                      <div
                        key={pd.parade_date_id}
                        className={`pw-block standard pw-block-sm skeleton${inHoliday ? " holiday" : ""}`}
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
                        <div style={{ padding: "6px 10px 8px", fontSize: 11, color: "var(--muted-text)", fontStyle: "italic" }}>
                          {!summariesLoading && summariesError ? "Data unavailable" : "Loading…"}
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
