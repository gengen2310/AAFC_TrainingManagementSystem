import { useState } from "react";
import type { CommandCentreData } from "../../api/types";

export interface LayerState {
  nationalHQ: boolean;
  wingHQEvents: boolean;      // "7WG HQ" — key unchanged so views still work
  aow: boolean;
  specialistFlights: boolean;
  unitActivity: boolean;      // own squadron activity
  allWGActivities: boolean;   // all other 7WG squadron activities
  holidays: boolean;          // key unchanged so YearView / TermView still work
  conflicts: boolean;         // "Warnings" — key unchanged so EightWeekView still works
  notes: boolean;             // "Notices"
}

export const defaultLayers: LayerState = {
  nationalHQ: true, wingHQEvents: true, aow: false, specialistFlights: false,
  unitActivity: true, allWGActivities: false,
  holidays: true, conflicts: true, notes: true,
};

const LAYER_DEFS: { key: keyof LayerState; label: string; color: string }[] = [
  { key: "nationalHQ",        label: "National HQ",        color: "#4A1080" },
  { key: "wingHQEvents",      label: "7WG HQ",             color: "#004B8D" },
  { key: "aow",               label: "AOW",                color: "#1A5276" },
  { key: "specialistFlights", label: "Specialist flights",  color: "#21618C" },
  { key: "unitActivity",      label: "Unit activity",       color: "#1A7F4B" },
  { key: "allWGActivities",   label: "All 7WG activities",  color: "#7C3AED" },
  { key: "holidays",          label: "Holidays",            color: "#C97A00" },
  { key: "conflicts",         label: "Warnings",            color: "#E51937" },
  { key: "notes",             label: "Notices",             color: "#B0B7BB" },
];

const LEGEND_ITEMS = [
  { color: "#E51937", label: "Room conflict",         sub: "Double-booked space"    },
  { color: "#F57C00", label: "Facilitator conflict",  sub: "Double-booked staff"    },
  { color: "#FFB300", label: "Workload warning",      sub: "Overloaded facilitator" },
  { color: "#B0B7BB", label: "Stand-down / empty",    sub: "No sessions planned"    },
];

const AUDIENCE_OPTIONS = ["All Cadets", "Staff", "Seniors", "Juniors", "First Years", "All Personnel"];
const PRIORITY_OPTIONS = ["Must Attend", "Key Event", "Home Parade", "Optional", "Noting"];

interface Props {
  layers: LayerState;
  onLayerToggle: (key: keyof LayerState) => void;
  audience: Set<string>;
  onAudienceToggle: (a: string) => void;
  priority: Set<string>;
  onPriorityToggle: (p: string) => void;
  focusClassId?: string | null;
  onClassFocus?: (classId: string | null) => void;
  searchText?: string;
  onSearchTextChange?: (text: string) => void;
  tierFilter?: string | null;
  onTierFilterChange?: (tier: string | null) => void;
  focusStageId?: string | null;
  onStageFocus?: (stageId: string | null) => void;
  cc: CommandCentreData | null;
  onBacklogItemClick: (type: string, id: string) => void;
  className?: string;
}

export function PlanningLeftPanel({
  layers, onLayerToggle, audience, onAudienceToggle, priority, onPriorityToggle,
  focusClassId, onClassFocus, searchText, onSearchTextChange,
  tierFilter, onTierFilterChange,
  focusStageId, onStageFocus,
  cc, onBacklogItemClick, className,
}: Props) {
  const [legendOpen, setLegendOpen] = useState(true);
  const [backlogClassFilter, setBacklogClassFilter] = useState<string | null>(null);

  const prepGaps        = cc?.prep_gaps ?? [];
  const allUnscheduled  = cc?.unscheduled_required ?? [];
  const trainingClasses = cc?.training_classes ?? [];
  const activeConflicts = cc?.active_conflicts ?? [];
  const unreviewed      = cc?.unreviewed_wing ?? [];

  // Filter unscheduled curriculum items by selected training class
  const unscheduled = backlogClassFilter
    ? allUnscheduled.filter(u => u.needs_class_ids.includes(backlogClassFilter))
    : allUnscheduled;

  const totalBacklog    = prepGaps.length + allUnscheduled.length + activeConflicts.length + unreviewed.length;

  return (
    <div className={`pw-left${className ? ` ${className}` : ""}`} aria-label="Planning filters and backlog">

      {/* ── Filters (renamed from "Layers") ───────────────── */}
      <div className="pw-section">
        <div className="pw-section-hdr">Filters</div>
        {LAYER_DEFS.map(({ key, label, color }) => (
          <label key={key} className="pw-layer-row" title={`Toggle ${label}`}>
            <input
              type="checkbox"
              checked={layers[key]}
              onChange={() => onLayerToggle(key)}
              aria-label={`Show ${label}`}
            />
            <span className="pw-layer-dot" style={{ background: color }} aria-hidden />
            {label}
          </label>
        ))}
      </div>

      {/* ── Training Period search ───────────────────────── */}
      <div className="pw-section">
        <div className="pw-section-hdr">Training Period search</div>
        <input
          type="search"
          placeholder="Title or curriculum code…"
          value={searchText ?? ""}
          onChange={e => onSearchTextChange?.(e.target.value)}
          aria-label="Search training periods by title or curriculum code"
          style={{ width: "100%", boxSizing: "border-box", padding: "5px 8px", fontSize: 12, border: "1px solid var(--border)", borderRadius: 5, background: "var(--surface)", color: "var(--text)", outline: "none" }}
        />
        {!!searchText && (
          <button
            style={{ marginTop: 4, fontSize: 11, background: "none", border: "none", cursor: "pointer", color: "var(--muted-text)", padding: 0 }}
            onClick={() => onSearchTextChange?.("")}
            aria-label="Clear search"
          >
            × Clear
          </button>
        )}
      </div>

      {/* ── Training Period tier (Foundation / Extension) ────────────────── */}
      <div className="pw-section">
        <div className="pw-section-hdr">Training Period tier</div>
        <div className="pw-filter-chips">
          <button
            className={`pw-chip${!tierFilter ? " on" : ""}`}
            onClick={() => onTierFilterChange?.(null)}
            aria-pressed={!tierFilter}
          >
            All
          </button>
          <button
            className={`pw-chip${tierFilter === "foundation" ? " on" : ""}`}
            onClick={() => onTierFilterChange?.(tierFilter === "foundation" ? null : "foundation")}
            aria-pressed={tierFilter === "foundation"}
          >
            Foundation
          </button>
          <button
            className={`pw-chip${tierFilter === "extension" ? " on" : ""}`}
            onClick={() => onTierFilterChange?.(tierFilter === "extension" ? null : "extension")}
            aria-pressed={tierFilter === "extension"}
          >
            Extension
          </button>
        </div>
      </div>

      {/* ── Stage focus / Class focus (only shown when squadron has >1 class) ─ */}
      {trainingClasses.length > 1 && (() => {
        // Build stage → class grouping once; reused by both Stage focus and Class focus sections.
        const stageOrder: string[] = [];
        const byStage: Record<string, typeof trainingClasses> = {};
        for (const tc of trainingClasses) {
          const key = tc.stage_name ?? "Other";
          if (!byStage[key]) { byStage[key] = []; stageOrder.push(key); }
          byStage[key].push(tc);
        }
        const multiStage = stageOrder.length > 1;
        return (
          <>
            {/* CLASS-22: Stage focus — only shown when multiple Training Stages exist */}
            {multiStage && (
              <div className="pw-section">
                <div className="pw-section-hdr">Stage focus</div>
                <div className="pw-filter-chips">
                  <button
                    className={`pw-chip${!focusStageId ? " on" : ""}`}
                    onClick={() => onStageFocus?.(null)}
                    aria-pressed={!focusStageId}
                  >
                    All
                  </button>
                  {stageOrder.map(stageName => {
                    const stageId = byStage[stageName][0]?.training_stage_id ?? stageName;
                    return (
                      <button
                        key={stageId}
                        className={`pw-chip${focusStageId === stageId ? " on" : ""}`}
                        onClick={() => onStageFocus?.(focusStageId === stageId ? null : stageId)}
                        aria-pressed={focusStageId === stageId}
                      >
                        {stageName}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Class focus */}
            <div className="pw-section">
              <div className="pw-section-hdr">Class focus</div>
              <div className="pw-filter-chips">
                <button
                  className={`pw-chip${!focusClassId ? " on" : ""}`}
                  onClick={() => onClassFocus?.(null)}
                  aria-pressed={!focusClassId}
                >
                  All
                </button>
                {stageOrder.map(stage => (
                  <span key={stage}>
                    {multiStage && (
                      <span style={{ display: "block", fontSize: 9, fontWeight: 700, letterSpacing: ".08em", color: "var(--muted-text)", textTransform: "uppercase", marginTop: 5, marginBottom: 2 }}>
                        {stage}
                      </span>
                    )}
                    {byStage[stage].map(tc => (
                      <button
                        key={tc.training_class_id}
                        className={`pw-chip${focusClassId === tc.training_class_id ? " on" : ""}`}
                        onClick={() => onClassFocus?.(tc.training_class_id)}
                        aria-pressed={focusClassId === tc.training_class_id}
                      >
                        {tc.display_name}
                      </button>
                    ))}
                  </span>
                ))}
              </div>
            </div>
          </>
        );
      })()}

      {/* ── Audience ──────────────────────────────────────── */}
      <div className="pw-section">
        <div className="pw-section-hdr">Audience</div>
        <div className="pw-filter-chips">
          {AUDIENCE_OPTIONS.map((a) => (
            <button
              key={a}
              className={`pw-chip${audience.size === 0 || audience.has(a) ? " on" : ""}`}
              onClick={() => onAudienceToggle(a)}
              aria-pressed={audience.has(a)}
            >
              {a}
            </button>
          ))}
        </div>
      </div>

      {/* ── Priority ──────────────────────────────────────── */}
      <div className="pw-section">
        <div className="pw-section-hdr">Priority</div>
        <div className="pw-filter-chips">
          {PRIORITY_OPTIONS.map((p) => (
            <button
              key={p}
              className={`pw-chip${priority.size === 0 || priority.has(p) ? " on" : ""}`}
              onClick={() => onPriorityToggle(p)}
              aria-pressed={priority.has(p)}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* ── Warning Legend ────────────────────────────────── */}
      <div className="pw-section">
        <div
          className="pw-section-hdr pw-section-hdr-toggle"
          onClick={() => setLegendOpen(o => !o)}
          role="button"
          aria-expanded={legendOpen}
          tabIndex={0}
          onKeyDown={e => e.key === "Enter" && setLegendOpen(o => !o)}
        >
          Warning Legend
          <span className="pw-section-toggle-icon">{legendOpen ? "▲" : "▼"}</span>
        </div>
        {legendOpen && (
          <div className="pw-legend">
            {LEGEND_ITEMS.map(item => (
              <div key={item.label} className="pw-legend-row">
                <span className="pw-legend-dot" style={{ background: item.color }} aria-hidden />
                <div>
                  <div className="pw-legend-label">{item.label}</div>
                  <div className="pw-legend-sub">{item.sub}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Backlog ───────────────────────────────────────── */}
      <div className="pw-section">
        <div className="pw-section-hdr">
          Backlog{" "}
          {totalBacklog > 0 && (
            <span style={{ color: "var(--aafc-red)", fontWeight: 900 }}>({totalBacklog})</span>
          )}
        </div>

        {unreviewed.length > 0 && (
          <>
            <div style={{ fontSize: 10, fontWeight: 700, color: "var(--aafc-royal-blue)", padding: "4px 2px 2px" }}>
              UNREVIEWED WING EVENTS
            </div>
            {unreviewed.slice(0, 5).map((e) => (
              <div
                key={e.wing_event_id}
                className="pw-backlog-item"
                role="button"
                tabIndex={0}
                onClick={() => onBacklogItemClick("wing-event", e.wing_event_id)}
                onKeyDown={(ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); onBacklogItemClick("wing-event", e.wing_event_id); } }}
              >
                <span className="pw-backlog-dot" style={{ background: "#004B8D" }} />
                <div>
                  <div style={{ fontSize: 11, fontWeight: 700 }}>{e.title}</div>
                  <div className="pw-backlog-code">{e.start_date} · {e.days_until}d away</div>
                </div>
              </div>
            ))}
          </>
        )}

        {prepGaps.length > 0 && (
          <>
            <div style={{ fontSize: 10, fontWeight: 700, color: "var(--warning)", padding: "4px 2px 2px" }}>
              PREP GAPS
            </div>
            {prepGaps.slice(0, 5).map((g) => (
              <div
                key={g.anchor_event_id}
                className="pw-backlog-item"
                role="button"
                tabIndex={0}
                onClick={() => onBacklogItemClick("anchor", g.anchor_event_id)}
                onKeyDown={(ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); onBacklogItemClick("anchor", g.anchor_event_id); } }}
              >
                <span className="pw-backlog-dot" style={{ background: "var(--warning)" }} />
                <div>
                  <div style={{ fontSize: 11, fontWeight: 700 }}>{g.event_name}</div>
                  <div className="pw-backlog-code">{g.start_date} · no prep planned</div>
                </div>
              </div>
            ))}
          </>
        )}

        {allUnscheduled.length > 0 && (
          <>
            <div style={{ fontSize: 10, fontWeight: 700, color: "var(--muted-text)", padding: "4px 2px 2px" }}>
              UNSCHEDULED CURRICULUM
            </div>
            {trainingClasses.length > 1 && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 3, marginBottom: 4 }}>
                <button
                  className={`pw-chip${backlogClassFilter === null ? " on" : ""}`}
                  style={{ fontSize: 10, padding: "1px 6px" }}
                  onClick={() => setBacklogClassFilter(null)}
                  aria-pressed={backlogClassFilter === null}
                >
                  All
                </button>
                {trainingClasses.map(tc => (
                  <button
                    key={tc.training_class_id}
                    className={`pw-chip${backlogClassFilter === tc.training_class_id ? " on" : ""}`}
                    style={{ fontSize: 10, padding: "1px 6px" }}
                    onClick={() => setBacklogClassFilter(
                      backlogClassFilter === tc.training_class_id ? null : tc.training_class_id
                    )}
                    aria-pressed={backlogClassFilter === tc.training_class_id}
                  >
                    {tc.display_name}
                  </button>
                ))}
              </div>
            )}
            {unscheduled.slice(0, 5).map((u) => (
              <div
                key={u.curriculum_id}
                className="pw-backlog-item"
                role="button"
                tabIndex={0}
                onClick={() => onBacklogItemClick("curriculum", u.curriculum_id)}
                onKeyDown={(ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); onBacklogItemClick("curriculum", u.curriculum_id); } }}
              >
                <span className="pw-backlog-dot" style={{ background: "var(--aafc-gunmetal)" }} />
                <div>
                  <div className="pw-backlog-code">{u.code}</div>
                  <div style={{ fontSize: 11 }}>{u.title}</div>
                </div>
              </div>
            ))}
            {unscheduled.length === 0 && backlogClassFilter && (
              <div style={{ fontSize: 10, color: "var(--muted-text)", padding: "2px 4px" }}>
                No unscheduled curriculum for this class
              </div>
            )}
            {unscheduled.length > 5 && (
              <div style={{ fontSize: 10, color: "var(--muted-text)", padding: "2px 4px" }}>
                +{unscheduled.length - 5} more — open Mission Backlog below
              </div>
            )}
          </>
        )}

        {activeConflicts.length > 0 && (
          <>
            <div style={{ fontSize: 10, fontWeight: 700, color: "var(--aafc-red)", padding: "4px 2px 2px" }}>
              CONFLICTS
            </div>
            {activeConflicts.slice(0, 5).map((c) => (
              <div key={c.conflict_id} className="pw-backlog-item">
                <span className="pw-backlog-dot" style={{ background: "var(--aafc-red)" }} />
                <div>
                  <div style={{ fontSize: 11 }}>{c.message}</div>
                  {c.parade_date && <div className="pw-backlog-code">{c.parade_date}</div>}
                </div>
              </div>
            ))}
          </>
        )}

        {totalBacklog === 0 && (
          <div style={{ fontSize: 11, color: "var(--muted-text)", padding: "6px 2px" }}>
            No outstanding items
          </div>
        )}
      </div>
    </div>
  );
}
