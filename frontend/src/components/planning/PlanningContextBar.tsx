import type { SessionInfo, CommandCentreData, PlanningYear } from "../../api/types";

export type ViewRange = "year" | "term" | "8week" | "2week" | "parade-night" | "custom";
export type DisplayMode = "calendar" | "list";

// Legacy alias so any callers that imported ViewMode still compile
export type ViewMode = ViewRange;

interface Props {
  session: SessionInfo | null;
  year: PlanningYear | null;
  cc: CommandCentreData | null;
  viewRange: ViewRange;
  displayMode: DisplayMode;
  customStart: string;
  customEnd: string;
  onRangeChange: (r: ViewRange) => void;
  onDisplayModeChange: (m: DisplayMode) => void;
  onCustomStartChange: (v: string) => void;
  onCustomEndChange: (v: string) => void;
  onToggleLeftPanel?: () => void;
}

const RANGES: { key: ViewRange; label: string }[] = [
  { key: "year",         label: "Year" },
  { key: "term",         label: "Term" },
  { key: "8week",        label: "8 wks" },
  { key: "2week",        label: "2 wks" },
  { key: "parade-night", label: "Night" },
  { key: "custom",       label: "Custom" },
];

export function PlanningContextBar({
  session, year,
  viewRange, displayMode, customStart, customEnd,
  onRangeChange, onDisplayModeChange, onCustomStartChange, onCustomEndChange,
  onToggleLeftPanel,
}: Props) {
  const scopeLabel = session?.is_national
    ? "NATHQ"
    : session?.is_wing
    ? `Wing ${session.wing_id ?? ""}`.trim()
    : session?.display_name ?? "Squadron";
  const roleLabel = session?.role
    ? session.role.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
    : "—";

  return (
    <div className="pw-ctx" role="banner" aria-label="Planning workspace context">
      {/* Mobile-only toggle for the left filter/backlog panel */}
      {onToggleLeftPanel && (
        <button
          className="pw-btn-hamburger"
          aria-label="Open filters and backlog panel"
          onClick={onToggleLeftPanel}
        >
          <span></span><span></span><span></span>
        </button>
      )}
      {/* Identity */}
      <span className="pw-ctx-scope">{year ? year.name : "Training Planning"}</span>
      <span className="pw-ctx-sep">·</span>
      <span className="pw-ctx-year">{year?.year ?? new Date().getFullYear()}</span>
      <span className="pw-ctx-role" title={roleLabel}>{roleLabel} · {scopeLabel}</span>

      {/* Range + display mode controls */}
      <div className="pw-ctx-range-wrap" role="toolbar" aria-label="Range and view mode">
        <span className="pw-ctx-range-lbl">Range</span>

        <div className="pw-ctx-modes">
          {RANGES.map((r) => (
            <button
              key={r.key}
              className={`pw-mode-btn${viewRange === r.key ? " active" : ""}`}
              onClick={() => onRangeChange(r.key)}
              aria-pressed={viewRange === r.key}
            >
              {r.label}
            </button>
          ))}
        </div>

        {/* Calendar / List toggle — hidden for parade-night (always calendar) */}
        {viewRange !== "parade-night" && (
          <div className="pw-ctx-display" role="group" aria-label="View type">
            <button
              className={`pw-display-btn${displayMode === "calendar" ? " active" : ""}`}
              onClick={() => onDisplayModeChange("calendar")}
              aria-pressed={displayMode === "calendar"}
            >
              Calendar
            </button>
            <button
              className={`pw-display-btn${displayMode === "list" ? " active" : ""}`}
              onClick={() => onDisplayModeChange("list")}
              aria-pressed={displayMode === "list"}
            >
              List
            </button>
          </div>
        )}

        {/* Custom date range inputs */}
        {viewRange === "custom" && (
          <div className="pw-ctx-custom">
            <label className="pw-ctx-custom-lbl" htmlFor="pw-ctx-custom-start">From</label>
            <input
              id="pw-ctx-custom-start"
              type="date"
              className="pw-ctx-date-input"
              value={customStart}
              onChange={e => onCustomStartChange(e.target.value)}
              aria-label="Custom range start date"
            />
            <label className="pw-ctx-custom-lbl" htmlFor="pw-ctx-custom-end">To</label>
            <input
              id="pw-ctx-custom-end"
              type="date"
              className="pw-ctx-date-input"
              value={customEnd}
              onChange={e => onCustomEndChange(e.target.value)}
              aria-label="Custom range end date"
            />
          </div>
        )}
      </div>

    </div>
  );
}
