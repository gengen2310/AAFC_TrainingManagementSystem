import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { trainingApi } from "../api";
import { Card, Empty, Loading, ErrorNote, Button } from "../components/ui";
import { usePagination, Pager } from "../components/Paginated";
import { CadetClassMembershipModal } from "../components/CadetClassMembershipModal";
import type { Cadet } from "../api/types";

// Cadets: sensitive support_notes only render when the backend returns them (admin-only + audited).
export function Cadets() {
  const cadets = useQuery({ queryKey: ["cadets"], queryFn: trainingApi.cadets });
  const risk = useQuery({ queryKey: ["cadet-risk"], queryFn: trainingApi.cadetRisk });
  const roll = cadets.data ?? [];
  const pg = usePagination(roll, 25);
  // CLASS-09: which Cadet's Training Class membership modal is open, if any.
  const [managingCadet, setManagingCadet] = useState<Cadet | null>(null);
  if (cadets.isLoading) return <Loading />;
  if (cadets.error) return <ErrorNote error={cadets.error} />;
  const showNotes = roll.some((c) => "support_notes" in c);
  return (
    <div>
      <h1>Cadets</h1>
      <p className="muted">Training coordination only. No medical, parent/carer, or contact data is stored. Support notes are admin-only and audited.</p>
      <Card title="Cadet risk">
        {risk.isLoading ? <Loading /> : (risk.data ?? []).length === 0 ? <Empty msg="No risk flags." /> :
          <ul className="risk-list">{(risk.data ?? []).map((f, i) => <li key={i}><strong>{f.cadet}</strong> — {f.reasons.join("; ")}</li>)}</ul>}
      </Card>
      <Card title="Cadet nominal roll">
        {roll.length === 0 ? <Empty msg="No cadets." /> : (
          <>
          <table>
            <caption className="vis-hidden">Cadet roll</caption>
            <thead><tr><th>SN</th><th>Rank</th><th>Name</th><th>Phase</th><th>Attendance</th><th>SITREP 1</th><th>Support</th>{showNotes && <th>Notes</th>}<th>Training Classes</th></tr></thead>
            <tbody>{pg.slice.map((c) => (
              <tr key={c.cadet_id}>
                <td>{c.service_number ?? "—"}</td><td>{c.rank ?? "—"}</td><td>{c.first_name} {c.last_name}</td>
                <td>{c.phase ?? "—"}</td><td>{c.attendance_percentage ?? "—"}%</td><td>{c.sitrep_part_1_status ?? "—"}</td>
                <td>{c.support_flag ? <span className="badge warn">▲ Flagged</span> : "—"}</td>
                {showNotes && <td className="sensitive">{c.support_notes ?? "—"}</td>}
                <td><Button variant="out" onClick={() => setManagingCadet(c)}>Manage</Button></td>
              </tr>))}</tbody>
          </table>
          <Pager page={pg.page} pageCount={pg.pageCount} total={pg.total} pageSize={pg.pageSize} onPage={pg.setPage} />
          </>
        )}
      </Card>
      {managingCadet && (
        <CadetClassMembershipModal cadet={managingCadet} onClose={() => setManagingCadet(null)} />
      )}
    </div>
  );
}
