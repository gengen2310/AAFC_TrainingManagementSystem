import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { trainingApi } from "../api";
import { Card, Empty, Loading, ErrorNote, Button } from "../components/ui";
import { StatusBadge } from "../components/status/StatusBadge";
import { Modal } from "../components/Modal";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthProvider";
import { canWriteSquadron } from "../auth/permissions";
import { ParadeNightDetailView } from "./ParadeNightDetail";
import { useScopedSquadron } from "../layout/SquadronViewContext";

export function ParadeNights() {
  const { session } = useAuth();
  const qc = useQueryClient();
  const { needsSelection, squadronId, scoped } = useScopedSquadron();
  const q = useQuery({ queryKey: ["parade-nights", squadronId], queryFn: () => trainingApi.paradeNights(squadronId), enabled: scoped });
  const [creating, setCreating] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);
  const canWrite = canWriteSquadron(session);

  if (needsSelection && !squadronId) return <div><h1>Parade Nights</h1><Empty msg="Select a squadron above to view its parade nights." /></div>;
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorNote error={q.error} />;

  return (
    <div>
      <h1>Parade Nights</h1>
      <Card title="All parade nights" action={canWrite && <Button onClick={() => setCreating(true)}>New parade night</Button>}>
        {(q.data ?? []).length === 0 ? <Empty msg="No parade nights yet." /> : (
          <table>
            <caption className="vis-hidden">Parade nights</caption>
            <thead><tr><th>Date</th><th>Term</th><th>Type</th><th>Sessions</th><th>Published</th><th>Readiness</th><th></th></tr></thead>
            <tbody>{(q.data ?? []).map((p) => (
              <tr key={p.parade_night_id}>
                <td>{p.date}</td><td>{p.term ?? "—"}</td><td>{p.parade_type}</td><td>{p.sessions.length}</td>
                <td><StatusBadge status={p.published_status ? "published" : "draft"} /></td>
                <td>{p.readiness_score ?? "—"}</td>
                <td><button className="btn out sm" onClick={() => setOpenId(p.parade_night_id)}>Open</button></td>
              </tr>))}</tbody>
          </table>
        )}
      </Card>
      {creating && <CreateParadeModal onClose={() => setCreating(false)} onDone={() => { setCreating(false); qc.invalidateQueries({ queryKey: ["parade-nights"] }); }} />}
      {openId && <Modal title="Parade night" onClose={() => setOpenId(null)}><ParadeNightDetailView id={openId} canWrite={canWrite} /></Modal>}
    </div>
  );
}

function CreateParadeModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [date, setDate] = useState("");
  const [term, setTerm] = useState("1");
  const [count, setCount] = useState("3");
  const [err, setErr] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});
  const m = useMutation({
    mutationFn: () => trainingApi.createParadeNight({ date, term: Number(term), session_count: Number(count) }),
    onSuccess: onDone,
    onError: (e) => {
      if (e instanceof ApiError) {
        const fe = e.fieldErrors;
        setFields(fe);
        // Show the generic banner only when there is no field-specific message to display.
        setErr(Object.keys(fe).length ? "" : e.friendly);
      } else { setErr("Could not create."); setFields({}); }
    },
  });
  return (
    <Modal title="New parade night" onClose={onClose}>
      <div className="form">
        <label htmlFor="pn-date">Date</label>
        <input id="pn-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} aria-invalid={!!fields.date} />
        {fields.date && <div className="field-err" role="alert">{fields.date}</div>}
        <label htmlFor="pn-term">Term</label>
        <input id="pn-term" type="number" min={1} max={4} value={term} onChange={(e) => setTerm(e.target.value)} aria-invalid={!!fields.term} />
        {fields.term && <div className="field-err" role="alert">{fields.term}</div>}
        <label htmlFor="pn-count">Session count</label>
        <input id="pn-count" type="number" min={1} max={6} value={count} onChange={(e) => setCount(e.target.value)} aria-invalid={!!fields.session_count} />
        {fields.session_count && <div className="field-err" role="alert">{fields.session_count}</div>}
        {err && <div className="err" role="alert">{err}</div>}
        <Button onClick={() => m.mutate()} disabled={!date || m.isPending}>Create</Button>
      </div>
    </Modal>
  );
}
