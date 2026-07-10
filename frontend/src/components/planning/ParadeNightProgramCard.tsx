import type { NightSummary, ParadeNotice, AnchorEvent } from "../../api/types";
import { ParadeNightMiniGrid } from "./ParadeNightMiniGrid";

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

export function ParadeNightProgramCard({
  summary, anchors, compact = false, inHoliday = false, onClick, onAnchorClick,
}: Props) {
  const dateLabel = new Date(summary.parade_date + "T00:00:00").toLocaleDateString("en-CA", {
    weekday: compact ? "short" : "long",
    month: "short",
    day: "numeric",
  });

  const hasConflict = summary.conflict_count > 0;
  const notices: ParadeNotice[] = summary.notices ?? [];
  const firstNotice = notices[0] ?? null;
  const extraNotices = Math.max(0, notices.length - 1);
  const hasSessions = summary.sessions.length > 0;

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
      {/* Header */}
      <div className="pw-pn-card-hdr">
        <span className="pw-pn-card-date">{dateLabel}</span>
        {summary.week_number != null && (
          <span className="pw-pn-card-wk">Wk {summary.week_number}</span>
        )}
        {inHoliday && <span className="pw-pn-card-standdown">Stand-down</span>}
        {hasConflict && (
          <span className="pw-pn-card-err">
            {summary.conflict_count} conflict{summary.conflict_count !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      {/* First notice strip */}
      {firstNotice && (
        <div className={`pw-pn-card-notice${firstNotice.priority === "urgent" ? " urgent" : ""}`}>
          Notice: {firstNotice.notice_text.length > 72
            ? firstNotice.notice_text.slice(0, 70) + "…"
            : firstNotice.notice_text}
          {extraNotices > 0 && (
            <span className="pw-pn-notice-more"> +{extraNotices} more</span>
          )}
        </div>
      )}

      {/* Session mini-grid */}
      {hasSessions ? (
        <div className="pw-pn-card-body">
          <ParadeNightMiniGrid sessions={summary.sessions} compact={compact} />
        </div>
      ) : (
        <div className="pw-pn-card-nosess">No sessions planned</div>
      )}

      {/* Parade notes */}
      {(summary.notes || summary.parade_night_notes) && (
        <div className="pw-pn-card-note">
          {((summary.notes || summary.parade_night_notes) ?? "").length > 80
            ? (summary.notes || summary.parade_night_notes)!.slice(0, 78) + "…"
            : (summary.notes || summary.parade_night_notes)}
        </div>
      )}

      {/* Activity overlays */}
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
                onKeyDown={onAnchorClick ? (e) => { e.stopPropagation(); if (e.key === "Enter") onAnchorClick(a); } : undefined}
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
