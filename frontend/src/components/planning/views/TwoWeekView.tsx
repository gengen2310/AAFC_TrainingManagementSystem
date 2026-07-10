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
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 800, color: "var(--aafc-dark-blue)" }}>
            Next 2 Parade Nights
          </div>
          <div style={{ fontSize: 11, color: "var(--muted-text)" }}>
            Staff-ready view · suitable for printing or screenshot
          </div>
        </div>
        <button
          className="btn sm out"
          style={{ marginLeft: "auto", fontSize: 11 }}
          onClick={() => window.print()}
        >
          Print
        </button>
      </div>
      <EightWeekView
        yearId={yearId}
        weeks={2}
        facilitators={facilitators}
        onDateClick={onDateClick}
        onSessionClick={onSessionClick}
      />
    </div>
  );
}
