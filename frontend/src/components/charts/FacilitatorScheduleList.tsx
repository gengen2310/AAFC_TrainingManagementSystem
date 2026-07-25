import { StatusBadge } from "../status/StatusBadge";
import { Empty } from "../ui";
import type { FacilitatorScheduleFacilitator, FacilitatorScheduleItem } from "../../api/types";

// The mandatory accessible fallback for FacilitatorTimeline.tsx (master
// transformation plan Block 9 / addendum Y.3's accepted tradeoff) — real
// table markup, native keyboard navigation, and StatusBadge's existing
// icon+colour+text convention, covering exactly the same data as the timeline.
function itemDate(i: FacilitatorScheduleItem): string {
  return i.kind === "session" ? i.date : i.start_date;
}

export function FacilitatorScheduleList({
  facilitators, items,
}: {
  facilitators: FacilitatorScheduleFacilitator[];
  items: FacilitatorScheduleItem[];
}) {
  if (facilitators.length === 0) return <Empty msg="No facilitators match these filters." />;
  return (
    <div>
      {facilitators.map((f) => {
        const own = items
          .filter((i) => i.facilitator_id === f.facilitator_id)
          .sort((a, b) => itemDate(a).localeCompare(itemDate(b)));
        return (
          <section key={f.facilitator_id} className="fts-list-fac">
            <h3>
              {f.name}
              {f.on_leave_now && <span className="badge warn" style={{ marginLeft: 8 }}>On leave now</span>}
            </h3>
            {own.length === 0 ? (
              <p className="muted">No sessions or leave recorded in this period.</p>
            ) : (
              <table>
                <caption className="vis-hidden">{f.name}&apos;s schedule</caption>
                <thead>
                  <tr><th>Date</th><th>Type</th><th>Details</th></tr>
                </thead>
                <tbody>
                  {own.map((i) =>
                    i.kind === "session" ? (
                      <tr key={i.id}>
                        <td>{i.date}</td>
                        <td>Session</td>
                        <td>{i.label} — <StatusBadge status={i.status} /></td>
                      </tr>
                    ) : (
                      <tr key={i.id}>
                        <td>{i.start_date} – {i.end_date}</td>
                        <td>Leave</td>
                        <td>{i.label}</td>
                      </tr>
                    )
                  )}
                </tbody>
              </table>
            )}
          </section>
        );
      })}
    </div>
  );
}
