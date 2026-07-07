import type { SessionInfo } from "../../api/types";
import type { CommandCentreData, PlanningYear } from "../../api/types";

export type ViewMode = "year" | "term" | "8week" | "2week" | "parade-night";

interface Props {
  session: SessionInfo | null;
  year: PlanningYear | null;
  cc: CommandCentreData | null;
  viewMode: ViewMode;
  onModeChange: (m: ViewMode) => void;
}

const MODES: { key: ViewMode; label: string }[] = [
  { key: "year", label: "Year" },
  { key: "term", label: "Term" },
  { key: "8week", label: "8 Weeks" },
  { key: "2week", label: "2 Weeks" },
  { key: "parade-night", label: "Night" },
];

export function PlanningContextBar({ session, year, cc, viewMode, onModeChange }: Props) {
  const scopeLabel = session?.is_national
    ? "National HQ"
    : session?.is_wing
    ? `Wing ${session.wing_id ?? ""}`.trim()
    : session?.display_name ?? "Squadron";
  const roleLabel = session?.role?.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) ?? "—";

  const conflicts = cc?.active_conflicts?.length ?? 0;
  const unscheduled = cc?.unscheduled_required?.length ?? 0;
  const unreviewed = cc?.unreviewed_wing?.length ?? 0;
  const prepGaps = cc?.prep_gaps?.length ?? 0;

  const importLabel = cc?.recent_imports?.[0]
    ? `Data as at ${cc.recent_imports[0].created_at?.slice(0, 10) ?? "—"}`
    : "No imports";

  return (
    <div className="pw-ctx" role="banner" aria-label="Planning workspace context">
      <span className="pw-ctx-scope">{year ? `${year.name}` : "Training Planning Workspace"}</span>
      <span className="pw-ctx-sep">·</span>
      <span className="pw-ctx-year">{year?.year ?? new Date().getFullYear()} Training Year</span>
      <span className="pw-ctx-role" title={roleLabel}>{roleLabel} · {scopeLabel}</span>

      <div className="pw-ctx-health" aria-label="Planning health">
        {conflicts > 0 && (
          <span className="pw-health-chip err" title="Active conflicts">
            ⚠ {conflicts} conflict{conflicts !== 1 ? "s" : ""}
          </span>
        )}
        {prepGaps > 0 && (
          <span className="pw-health-chip warn" title="Upcoming events with no prep planned">
            ⏰ {prepGaps} prep gap{prepGaps !== 1 ? "s" : ""}
          </span>
        )}
        {unscheduled > 0 && (
          <span className="pw-health-chip warn" title="Required curriculum items not yet scheduled">
            📚 {unscheduled} unscheduled
          </span>
        )}
        {unreviewed > 0 && (
          <span className="pw-health-chip warn" title="Wing events not yet reviewed">
            👁 {unreviewed} unreviewed
          </span>
        )}
        {conflicts === 0 && unscheduled === 0 && unreviewed === 0 && prepGaps === 0 && cc && (
          <span className="pw-health-chip ok">✓ Planning healthy</span>
        )}
      </div>

      <div className="pw-ctx-modes" role="toolbar" aria-label="View mode">
        {MODES.map((m) => (
          <button
            key={m.key}
            className={`pw-mode-btn${viewMode === m.key ? " active" : ""}`}
            onClick={() => onModeChange(m.key)}
            aria-pressed={viewMode === m.key}
          >
            {m.label}
          </button>
        ))}
      </div>

      <span className="pw-ctx-import" title="Import freshness">{importLabel}</span>
    </div>
  );
}
