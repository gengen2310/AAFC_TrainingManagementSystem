import type { PlanningFacilitator, PlanningSession } from "../../../api/types";
import { EightWeekView } from "./EightWeekView";

interface Props {
  yearId: string;
  facilitators: PlanningFacilitator[];
  onDateClick: (dateId: string, date: string) => void;
  onSessionClick: (session: PlanningSession, dateId: string, date: string) => void;
}

export function TwoWeekView({ yearId, facilitators, onDateClick, onSessionClick }: Props) {
  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: "var(--aafc-dark-blue)" }}>
          Next 2 Parade Nights
        </span>
        <span style={{ fontSize: 11, color: "var(--muted-text)" }}>Detailed view — suitable for printing</span>
        <button
          className="btn sm out"
          style={{ marginLeft: "auto" }}
          onClick={() => window.print()}
        >
          Print
        </button>
      </div>
      <div className="pw-2week-grid">
        <EightWeekView
          yearId={yearId}
          weeks={2}
          facilitators={facilitators}
          onDateClick={onDateClick}
          onSessionClick={onSessionClick}
        />
      </div>
    </div>
  );
}
