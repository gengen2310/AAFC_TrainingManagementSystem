import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { planningApi } from "../../../api";
import { filterAnchors } from "../../../utils/planningFilters";

interface Props {
  yearId: string;
  onDateClick: (dateId: string, date: string) => void;
  layers?: { holidays?: boolean; wingHQEvents?: boolean };
  audience?: Set<string>;
  priority?: Set<string>;
}

export function TermView({ yearId, onDateClick, layers, audience, priority }: Props) {
  const showHolidays = layers?.holidays ?? true;
  const showAnchors = layers?.wingHQEvents ?? true;
  const [termIndex, setTermIndex] = useState(0);

  const { data, isLoading, error } = useQuery({
    queryKey: ["planning-annual", yearId],
    queryFn: () => planningApi.annualProgram(yearId),
  });

  if (isLoading) return <div className="pw-loading">Loading term view…</div>;
  if (error || !data) return <div className="pw-err">Failed to load term data.</div>;

  const term = data.terms[termIndex];
  if (!term) return <div className="pw-empty">No terms found.</div>;

  return (
    <div>
      <div style={{ display: "flex", gap: 6, marginBottom: 14 }}>
        {data.terms.map((t, i) => (
          <button
            key={t.term}
            className={`pw-mode-btn${i === termIndex ? " active" : ""}`}
            style={{ border: "1.5px solid var(--border)", color: i === termIndex ? "#fff" : "var(--text)", background: i === termIndex ? "var(--aafc-dark-blue)" : "var(--surface)" }}
            onClick={() => setTermIndex(i)}
          >
            {t.term}
          </button>
        ))}
      </div>

      <div className="pw-term">
        <div className="pw-term-hdr">
          <span>{term.term}</span>
          <span style={{ fontSize: 11, fontWeight: 400 }}>
            {term.start_date} → {term.end_date} · {term.parade_dates.length} nights
          </span>
        </div>

        {showAnchors && (() => {
          const visible = filterAnchors(term.activities ?? [], audience ?? new Set(), priority ?? new Set());
          return visible.length > 0 ? (
            <div className="pw-anchor-strip" style={{ marginBottom: 10 }}>
              {visible.map((a, i) => (
                <span key={a.anchor_event_id ?? String(i)} className={`pw-anchor-pill ${a.importance ?? "optional"}`}>
                  {a.event_name} · {a.start_date}
                </span>
              ))}
            </div>
          ) : null;
        })()}

        <div className="pw-month-grid" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))" }}>
          {term.parade_dates.map((pd) => (
            <div
              key={pd.parade_date_id}
              className={`pw-date-cell${showHolidays && pd.in_holiday ? " holiday" : ""}`}
              role="button"
              tabIndex={0}
              onClick={() => onDateClick(pd.parade_date_id, pd.parade_date)}
              onKeyDown={(e) => e.key === "Enter" && onDateClick(pd.parade_date_id, pd.parade_date)}
            >
              <div className="pw-date-label">
                {new Date(pd.parade_date + "T00:00:00").toLocaleDateString("en-CA", {
                  weekday: "long", month: "short", day: "numeric",
                })}
              </div>
              <div className="pw-date-type">
                {pd.parade_type}{pd.week_number ? ` · Wk ${pd.week_number}` : ""}
              </div>
              {showHolidays && pd.in_holiday && <div style={{ fontSize: 10, color: "#C97A00", fontWeight: 700 }}>Stand-down</div>}
              <div className="pw-date-fill">
                <div style={{ fontSize: 10, color: "var(--muted-text)" }}>{pd.filled_count}/{pd.session_count} sessions filled</div>
                {pd.session_count > 0 && (
                  <div className="pw-fill-bar">
                    <div className="pw-fill-bar-inner" style={{ width: `${Math.round((pd.filled_count / pd.session_count) * 100)}%` }} />
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
