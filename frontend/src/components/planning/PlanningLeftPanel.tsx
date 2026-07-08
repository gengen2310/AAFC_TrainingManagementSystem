import type { CommandCentreData } from "../../api/types";

export interface LayerState {
  wingHQEvents: boolean;
  squadronEvents: boolean;
  ceaActivities: boolean;
  paradeNights: boolean;
  curriculum: boolean;
  localLessons: boolean;
  holidays: boolean;
  conflicts: boolean;
  notes: boolean;
}

export const defaultLayers: LayerState = {
  wingHQEvents: true, squadronEvents: true, ceaActivities: true,
  paradeNights: true, curriculum: true, localLessons: true,
  holidays: true, conflicts: true, notes: false,
};

const LAYER_DEFS: { key: keyof LayerState; label: string; color: string }[] = [
  { key: "wingHQEvents", label: "Wing HQ events", color: "#004B8D" },
  { key: "squadronEvents", label: "Squadron events", color: "#1A7F4B" },
  { key: "ceaActivities", label: "CEA activities", color: "#7C3AED" },
  { key: "paradeNights", label: "Home parade nights", color: "#51B0E3" },
  { key: "curriculum", label: "Curriculum sessions", color: "#002F65" },
  { key: "localLessons", label: "Local lessons", color: "#455560" },
  { key: "holidays", label: "Holidays / stand-down", color: "#C97A00" },
  { key: "conflicts", label: "Conflicts", color: "#E51937" },
  { key: "notes", label: "Notes", color: "#B0B7BB" },
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
  cc: CommandCentreData | null;
  onBacklogItemClick: (type: string, id: string) => void;
}

export function PlanningLeftPanel({
  layers, onLayerToggle, audience, onAudienceToggle, priority, onPriorityToggle,
  cc, onBacklogItemClick,
}: Props) {
  const prepGaps = cc?.prep_gaps ?? [];
  const unscheduled = cc?.unscheduled_required ?? [];
  const activeConflicts = cc?.active_conflicts ?? [];
  const unreviewed = cc?.unreviewed_wing ?? [];
  const totalBacklog = prepGaps.length + unscheduled.length + activeConflicts.length + unreviewed.length;

  return (
    <div className="pw-left" aria-label="Planning filters and backlog">
      {/* Layers */}
      <div className="pw-section">
        <div className="pw-section-hdr">Layers</div>
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

      {/* Audience */}
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

      {/* Priority */}
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

      {/* Backlog */}
      <div className="pw-section">
        <div className="pw-section-hdr">
          Backlog {totalBacklog > 0 && <span style={{ color: "var(--aafc-red)", fontWeight: 900 }}>({totalBacklog})</span>}
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
                onClick={() => onBacklogItemClick("wing-event", e.wing_event_id)}
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
                onClick={() => onBacklogItemClick("anchor", g.anchor_event_id)}
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

        {unscheduled.length > 0 && (
          <>
            <div style={{ fontSize: 10, fontWeight: 700, color: "var(--muted-text)", padding: "4px 2px 2px" }}>
              UNSCHEDULED CURRICULUM
            </div>
            {unscheduled.slice(0, 5).map((u) => (
              <div
                key={u.curriculum_id}
                className="pw-backlog-item"
                onClick={() => onBacklogItemClick("curriculum", u.curriculum_id)}
              >
                <span className="pw-backlog-dot" style={{ background: "var(--aafc-gunmetal)" }} />
                <div>
                  <div className="pw-backlog-code">{u.code}</div>
                  <div style={{ fontSize: 11 }}>{u.title}</div>
                </div>
              </div>
            ))}
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
