import type { NightSessionSummary } from "../../api/types";

export const GRID_GROUPS = [
  { key: "oi",     label: "O&I",    fullLabel: "Ori & Initial",       cadetGroups: ["orientation", "initial"] },
  { key: "bronze", label: "Bronze", fullLabel: "Junior & Bronze CLP", cadetGroups: ["junior"] },
  { key: "silver", label: "Silver", fullLabel: "Inter. & Silver CLP", cadetGroups: ["intermediate"] },
  { key: "gold",   label: "Gold",   fullLabel: "Senior & Gold CLP",   cadetGroups: ["senior"] },
] as const;

export const GRID_PERIODS = [1, 2, 3] as const;

export function getCell(
  sessions: NightSessionSummary[],
  cadetGroups: readonly string[],
  period: number,
): NightSessionSummary | null {
  // Group-specific session first
  const hit = sessions.find(
    s => s.period === period && s.cadet_group !== null && (cadetGroups as readonly string[]).includes(s.cadet_group as string),
  );
  if (hit) return hit;
  // Fall back to a combined (null cadet_group) session
  return sessions.find(s => s.period === period && !s.cadet_group) ?? null;
}

function trunc(text: string, max: number): string {
  return text.length > max ? text.slice(0, max - 1) + "…" : text;
}

interface Props {
  sessions: NightSessionSummary[];
  compact?: boolean;
  onCellClick?: (groupKey: string, period: number) => void;
}

export function ParadeNightMiniGrid({ sessions, compact = false, onCellClick }: Props) {
  if (compact) {
    return (
      <div className="pw-pn-compact-grid">
        {GRID_GROUPS.map((g) => {
          const cells = GRID_PERIODS.map((p) => getCell(sessions, g.cadetGroups, p));
          const allEmpty = cells.every((c) => c === null);
          return (
            <div key={g.key} className={`pw-pn-cg-row${allEmpty ? " all-empty" : ""}`}>
              <span className="pw-pn-cg-lbl">{g.label}</span>
              <div className="pw-pn-cg-periods">
                {cells.map((cell, i) => (
                  <span key={i} className={`pw-pn-cg-cell${!cell ? " no-lesson" : ""}`}>
                    <span className="pw-pn-cg-p">P{i + 1}</span>
                    {cell ? trunc(cell.title ?? "—", 24) : "—"}
                  </span>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    );
  }

  // Detailed table mode
  return (
    <div className="pw-pn-table-wrap">
      <table className="pw-pn-table">
        <thead>
          <tr>
            <th className="pw-pn-th-grp"></th>
            {GRID_PERIODS.map((p) => (
              <th key={p} className="pw-pn-th-period">P{p}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {GRID_GROUPS.map((g) => (
            <tr key={g.key}>
              <th className="pw-pn-th-row">{g.fullLabel}</th>
              {GRID_PERIODS.map((period) => {
                const cell = getCell(sessions, g.cadetGroups, period);
                const clickable = !!onCellClick;
                return (
                  <td
                    key={period}
                    className={`pw-pn-td${cell ? " filled" : " empty"}${clickable ? " clickable" : ""}`}
                    onClick={clickable ? (e) => { e.stopPropagation(); onCellClick!(g.key, period); } : undefined}
                    role={clickable ? "button" : undefined}
                    tabIndex={clickable ? 0 : undefined}
                    onKeyDown={clickable ? (e) => { if (e.key === "Enter") { e.stopPropagation(); onCellClick!(g.key, period); } } : undefined}
                  >
                    {cell ? (
                      <div className="pw-pn-td-inner">
                        <div className="pw-pn-td-title">{cell.title ?? "—"}</div>
                        {cell.location && <div className="pw-pn-td-meta">{cell.location}</div>}
                        {cell.facilitator && <div className="pw-pn-td-meta">{cell.facilitator}</div>}
                      </div>
                    ) : (
                      <div className="pw-pn-td-empty">
                        {clickable ? <span>+ Add</span> : <span>No lesson</span>}
                      </div>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
