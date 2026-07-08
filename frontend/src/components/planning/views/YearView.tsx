import { useQuery } from "@tanstack/react-query";
import { planningApi } from "../../../api";

interface Props {
  yearId: string;
  onDateClick: (dateId: string, date: string) => void;
}

export function YearView({ yearId, onDateClick }: Props) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["planning-annual", yearId],
    queryFn: () => planningApi.annualProgram(yearId),
  });

  if (isLoading) return <div className="pw-loading">Loading annual program…</div>;
  if (error || !data) return <div className="pw-err">Failed to load annual program.</div>;

  return (
    <div className="pw-year">
      {data.terms.map((term) => (
        <div key={term.term} className="pw-term">
          <div className="pw-term-hdr">
            <span>{term.term}</span>
            <span style={{ fontSize: 11, fontWeight: 400, color: "var(--muted-text)" }}>
              {term.start_date} → {term.end_date}
            </span>
          </div>

          {(term.activities ?? []).length > 0 && (
            <div className="pw-anchor-strip" style={{ marginBottom: 8 }}>
              {(term.activities ?? []).map((a, i) => (
                <span key={a.anchor_event_id ?? String(i)} className={`pw-anchor-pill ${a.importance ?? "optional"}`}>
                  {a.event_name}
                </span>
              ))}
            </div>
          )}

          <div className="pw-month-grid">
            {term.parade_dates.map((pd) => (
              <div
                key={pd.parade_date_id}
                className={`pw-date-cell${pd.in_holiday ? " holiday" : ""}`}
                role="button"
                tabIndex={0}
                onClick={() => onDateClick(pd.parade_date_id, pd.parade_date)}
                onKeyDown={(e) => e.key === "Enter" && onDateClick(pd.parade_date_id, pd.parade_date)}
                aria-label={`Parade date ${pd.parade_date}`}
              >
                <div className="pw-date-label">
                  {new Date(pd.parade_date + "T00:00:00").toLocaleDateString("en-CA", {
                    weekday: "short", month: "short", day: "numeric",
                  })}
                </div>
                <div className="pw-date-type">{pd.parade_type}</div>
                {pd.in_holiday && (
                  <div style={{ fontSize: 10, color: "#C97A00", fontWeight: 700 }}>Stand-down</div>
                )}
                <div className="pw-date-fill">
                  <div style={{ fontSize: 10, color: "var(--muted-text)" }}>
                    {pd.filled_count}/{pd.session_count} filled
                  </div>
                  {pd.session_count > 0 && (
                    <div className="pw-fill-bar">
                      <div
                        className="pw-fill-bar-inner"
                        style={{ width: `${Math.round((pd.filled_count / pd.session_count) * 100)}%` }}
                      />
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
