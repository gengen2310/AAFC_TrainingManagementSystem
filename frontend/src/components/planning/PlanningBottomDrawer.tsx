import { useQuery } from "@tanstack/react-query";
import { planningApi } from "../../api";
import type { PlanningFacilitator, PlanningLocation } from "../../api/types";
import type { DrawerItem } from "./PlanningRightDrawer";

type BottomTab = "backlog" | "facilitators" | "rooms" | "notices";

interface Props {
  yearId: string | null;
  tab: BottomTab;
  onTabChange: (t: BottomTab) => void;
  onClose: () => void;
  facilitators: PlanningFacilitator[];
  locations: PlanningLocation[];
  onItemClick: (item: DrawerItem) => void;
}

const TABS: { key: BottomTab; label: string }[] = [
  { key: "backlog", label: "Mission Backlog" },
  { key: "facilitators", label: "Facilitators" },
  { key: "rooms", label: "Rooms" },
  { key: "notices", label: "Notices" },
];

function BacklogContent({ yearId, onItemClick }: { yearId: string; onItemClick: (item: DrawerItem) => void }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["planning-missions", yearId],
    queryFn: () => planningApi.missions(yearId, { status: "unscheduled" }),
  });

  if (isLoading) return <div className="pw-loading" style={{ padding: "20px" }}>Loading missions…</div>;
  if (error || !data) return <div className="pw-err">Failed to load missions.</div>;

  const unscheduled = data.missions.filter(m => !m.is_scheduled);

  if (unscheduled.length === 0) {
    return <div className="pw-empty" style={{ padding: "20px" }}>All required curriculum is scheduled.</div>;
  }

  return (
    <div className="pw-backlog-grid">
      {unscheduled.map((m) => (
        <div
          key={m.curriculum_id}
          className="pw-backlog-card"
          onClick={() => onItemClick({ type: "curriculum", curriculum: { curriculum_id: m.curriculum_id, code: m.code, title: m.title, phase: m.phase } })}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => e.key === "Enter" && onItemClick({ type: "curriculum", curriculum: { curriculum_id: m.curriculum_id, code: m.code, title: m.title, phase: m.phase } })}
        >
          <div className="pw-backlog-card-code">{m.code}</div>
          <div className="pw-backlog-card-title">{m.title}</div>
          <div className="pw-backlog-card-meta">
            Phase {m.phase}{m.element ? ` · ${m.element}` : ""}{m.recommended_term ? ` · Term ${m.recommended_term}` : ""}
          </div>
          {m.core_status === "core" && (
            <span style={{ fontSize: 10, fontWeight: 700, color: "var(--aafc-red)", marginTop: 2, display: "block" }}>CORE</span>
          )}
        </div>
      ))}
    </div>
  );
}

function FacilitatorsContent({ facilitators }: { facilitators: PlanningFacilitator[] }) {
  if (facilitators.length === 0) {
    return <div className="pw-empty" style={{ padding: "20px" }}>No facilitators on record.</div>;
  }
  return (
    <table className="pw-fac-table">
      <thead>
        <tr>
          <th>Name</th>
          <th>Type</th>
          <th>Subject areas</th>
          <th>Max sessions/night</th>
        </tr>
      </thead>
      <tbody>
        {facilitators.map((f) => (
          <tr key={f.facilitator_id}>
            <td>{f.display_name}</td>
            <td style={{ textTransform: "capitalize" }}>{f.type}</td>
            <td style={{ fontSize: 11 }}>{f.subject_areas.join(", ") || "—"}</td>
            <td style={{ textAlign: "center" }}>{f.max_sessions_per_night}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function RoomsContent({ locations, onAddLocation, onEditLocation }: {
  locations: PlanningLocation[];
  onAddLocation: () => void;
  onEditLocation: (loc: PlanningLocation) => void;
}) {
  return (
    <div>
      <div style={{ padding: "8px 14px 0", display: "flex", justifyContent: "flex-end" }}>
        <button className="btn sm primary" onClick={onAddLocation}>+ Add Room</button>
      </div>
      {locations.length === 0 ? (
        <div className="pw-empty" style={{ padding: "20px" }}>No rooms on record. Add one to start assigning sessions to rooms.</div>
      ) : (
        <table className="pw-fac-table">
          <thead>
            <tr>
              <th>Room</th>
              <th>Type</th>
              <th>Capacity</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {locations.map((l) => (
              <tr key={l.location_id}>
                <td>{l.name}</td>
                <td style={{ textTransform: "capitalize" }}>{l.location_type}</td>
                <td style={{ textAlign: "center" }}>{l.capacity ?? "—"}</td>
                <td>
                  <span style={{ fontSize: 11, fontWeight: 700, color: l.active_status ? "var(--success)" : "var(--muted-text)" }}>
                    {l.active_status ? "Active" : "Inactive"}
                  </span>
                </td>
                <td>
                  <button className="btn sm out" style={{ fontSize: 11, padding: "3px 8px" }} onClick={() => onEditLocation(l)}>Edit</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function NoticesContent({ yearId }: { yearId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["planning-cc", yearId],
    queryFn: () => planningApi.commandCentre(yearId),
  });

  if (isLoading) return <div className="pw-loading" style={{ padding: "20px" }}>Loading notices…</div>;

  const anchors = data?.upcoming_anchors ?? [];
  if (anchors.length === 0) {
    return <div className="pw-empty" style={{ padding: "20px" }}>No upcoming key notices.</div>;
  }

  return (
    <div className="pw-backlog-grid">
      {anchors.map((a, i) => (
        <div key={a.anchor_event_id ?? a.anchor_id ?? String(i)} className="pw-backlog-card">
          <div className="pw-backlog-card-code">{a.event_type}</div>
          <div className="pw-backlog-card-title">{a.event_name}</div>
          <div className="pw-backlog-card-meta">
            {a.start_date}{a.end_date && a.end_date !== a.start_date ? ` → ${a.end_date}` : ""}
            {a.planning_impact && ` · ${a.planning_impact}`}
          </div>
        </div>
      ))}
    </div>
  );
}

export function PlanningBottomDrawer({ yearId, tab, onTabChange, onClose, facilitators, locations, onItemClick }: Props) {
  return (
    <div className="pw-bottom-bar" role="complementary" aria-label="Bottom planning drawer">
      <div className="pw-bottom-tabs">
        {TABS.map((t) => (
          <button
            key={t.key}
            className={`pw-btab${tab === t.key ? " active" : ""}`}
            onClick={() => onTabChange(t.key)}
            aria-pressed={tab === t.key}
          >
            {t.label}
          </button>
        ))}
        <button className="pw-btab-close" onClick={onClose} aria-label="Close bottom drawer">×</button>
      </div>
      <div className="pw-bottom-content">
        {tab === "backlog" && yearId && <BacklogContent yearId={yearId} onItemClick={onItemClick} />}
        {tab === "backlog" && !yearId && <div className="pw-empty">No planning year selected.</div>}
        {tab === "facilitators" && <FacilitatorsContent facilitators={facilitators} />}
        {tab === "rooms" && (
          <RoomsContent
            locations={locations}
            onAddLocation={() => { onItemClick({ type: "new-location" }); onClose(); }}
            onEditLocation={(loc) => { onItemClick({ type: "new-location", location: loc }); onClose(); }}
          />
        )}
        {tab === "notices" && yearId && <NoticesContent yearId={yearId} />}
        {tab === "notices" && !yearId && <div className="pw-empty">No planning year selected.</div>}
      </div>
    </div>
  );
}
