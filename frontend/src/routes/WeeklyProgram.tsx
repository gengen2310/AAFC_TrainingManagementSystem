import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { trainingApi } from "../api";
import { Empty, Loading, ErrorNote, Button } from "../components/ui";
import { StatusBadge } from "../components/status/StatusBadge";
import { useScopedSquadron } from "../layout/SquadronViewContext";

// Printable weekly program built from backend parade-night/session data. Print CSS hides nav.
export function WeeklyProgram() {
  const { needsSelection, squadronId, scoped } = useScopedSquadron();
  const q = useQuery({ queryKey: ["parade-nights", squadronId], queryFn: () => trainingApi.paradeNights(squadronId), enabled: scoped });
  const [selected, setSelected] = useState<string>("");
  if (needsSelection && !squadronId) return <div><h1>Weekly Program</h1><Empty msg="Select a squadron above to view its weekly program." /></div>;
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorNote error={q.error} />;
  const parades = q.data ?? [];
  const pn = parades.find((p) => p.parade_night_id === selected) ?? parades[0];

  return (
    <div className="weekly">
      <div className="no-print">
        <h1>Weekly Program</h1>
        <label htmlFor="wk-pn">Parade night</label>{" "}
        <select id="wk-pn" value={pn?.parade_night_id ?? ""} onChange={(e) => setSelected(e.target.value)}>
          {parades.map((p) => <option key={p.parade_night_id} value={p.parade_night_id}>{p.date}</option>)}
        </select>{" "}
        <Button onClick={() => window.print()}>Print</Button>
      </div>
      {!pn ? <Empty msg="No parade nights to print." /> : (
        <div className="print-sheet">
          <div className="print-head">
            <h2>Weekly Training Program</h2>
            <p>{pn.date} · Term {pn.term ?? "—"} · {pn.start_time}–{pn.end_time}</p>
          </div>
          <table>
            <caption>Sessions</caption>
            <thead><tr><th>Period</th><th>Phase</th><th>Item</th><th>Class</th><th>Facilitator</th><th>Status</th></tr></thead>
            <tbody>
              {pn.sessions.length === 0 ? <tr><td colSpan={6}>No sessions.</td></tr> :
                pn.sessions.sort((a, b) => a.period_number - b.period_number).map((s) => (
                  <tr key={s.id}><td>{s.period_number}</td><td>{s.phase_at_time ?? "—"}</td>
                    <td>{s.curriculum_title_at_time ?? s.custom_title ?? "—"}</td>
                    <td>{(s.training_classes ?? []).length ? s.training_classes.map((c) => c.display_name).join(", ") : "—"}</td>
                    <td>{s.facilitator_display_name_at_time ?? "—"}</td>
                    <td><StatusBadge status={s.status} /></td></tr>))}
            </tbody>
          </table>
          <p className="print-foot">AAFC Training Management System · planning document only — not a system of record.</p>
        </div>
      )}
    </div>
  );
}
