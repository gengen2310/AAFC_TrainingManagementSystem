import type { NightSummary, NightSessionSummary, AnchorEvent } from "../../api/types";

function PeriodRow({ period, sessions, compact }: {
  period: number;
  sessions: NightSessionSummary[];
  compact: boolean;
}) {
  const ps = sessions.filter(s => s.period === period);
  if (ps.length === 0) {
    return (
      <div className="pw-pn-row">
        <span className="pw-pn-row-lbl">P{period}</span>
        <span className="pw-pn-row-none">No lesson</span>
      </div>
    );
  }
  const titles = [...new Set(ps.map(s => s.title).filter((t): t is string => !!t))];
  const facs   = [...new Set(ps.map(s => s.facilitator).filter((f): f is string => !!f))];
  const locs   = [...new Set(ps.map(s => s.location).filter((l): l is string => !!l))];

  const metaParts: string[] = [];
  if (locs.length) metaParts.push(locs.join(" / "));
  if (facs.length) metaParts.push(facs.join(" / "));

  return (
    <div className="pw-pn-row">
      <span className="pw-pn-row-lbl">P{period}</span>
      <div className="pw-pn-row-body">
        <span className="pw-pn-row-title">{titles.join(" / ") || "—"}</span>
        {(!compact || locs.length > 0) && metaParts.length > 0 && (
          <span className="pw-pn-row-meta">{metaParts.join(" · ")}</span>
        )}
      </div>
    </div>
  );
}

const SOURCE_LABEL: Record<string, string> = {
  national: "NATHQ",
  wing: "Wing",
  unit: "",
};

interface Props {
  summary: NightSummary;
  anchors?: AnchorEvent[];
  compact?: boolean;
  inHoliday?: boolean;
  onClick: () => void;
  onAnchorClick?: (anchor: AnchorEvent) => void;
}

export function ParadeNightSummaryCard({
  summary, anchors, compact = false, inHoliday = false, onClick, onAnchorClick,
}: Props) {
  const dateLabel = new Date(summary.parade_date + "T00:00:00").toLocaleDateString("en-CA", {
    weekday: compact ? "short" : "long",
    month: "short",
    day: "numeric",
  });

  const hasSessions = summary.sessions.length > 0;
  const noteText = summary.notes || summary.parade_night_notes;
  const hasConflict = summary.conflict_count > 0;
  const cardCls = [
    "pw-pn-card",
    compact ? "compact" : "full",
    hasConflict ? "conflict" : "",
    inHoliday ? "holiday" : "",
  ].filter(Boolean).join(" ");

  return (
    <div
      className={cardCls}
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => e.key === "Enter" && onClick()}
      aria-label={`Parade night ${summary.parade_date}`}
    >
      <div className="pw-pn-card-hdr">
        <span className="pw-pn-card-date">{dateLabel}</span>
        {summary.week_number != null && (
          <span className="pw-pn-card-wk">Wk {summary.week_number}</span>
        )}
        {inHoliday && <span className="pw-pn-card-standdown">Stand-down</span>}
        {hasConflict && (
          <span className="pw-pn-card-err">{summary.conflict_count}</span>
        )}
      </div>

      {hasSessions ? (
        <div className="pw-pn-card-periods">
          <PeriodRow period={1} sessions={summary.sessions} compact={compact} />
          <PeriodRow period={2} sessions={summary.sessions} compact={compact} />
          <PeriodRow period={3} sessions={summary.sessions} compact={compact} />
        </div>
      ) : (
        <div className="pw-pn-card-nosess">No sessions</div>
      )}

      {noteText && (
        <div className="pw-pn-card-note">
          Note: {noteText.length > 70 ? noteText.slice(0, 70) + "…" : noteText}
        </div>
      )}

      {anchors && anchors.length > 0 && (
        <div className="pw-pn-card-anchors">
          {anchors.map((a, i) => {
            const srcLabel = SOURCE_LABEL[a.owning_level ?? "unit"] ?? "";
            return (
              <span
                key={a.anchor_event_id ?? String(i)}
                className={`pw-anchor-pill ${a.importance ?? "optional"}${onAnchorClick ? " clickable" : ""}`}
                onClick={onAnchorClick ? (e) => { e.stopPropagation(); onAnchorClick(a); } : undefined}
                role={onAnchorClick ? "button" : undefined}
                tabIndex={onAnchorClick ? 0 : undefined}
                onKeyDown={onAnchorClick ? (e) => {
                  e.stopPropagation();
                  if (e.key === "Enter") onAnchorClick(a);
                } : undefined}
              >
                {srcLabel && <span className="pw-src-lbl">{srcLabel}</span>}
                {a.event_name}
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
}
