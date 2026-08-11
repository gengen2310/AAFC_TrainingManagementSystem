import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { opsApi } from "../api";
import { Card, Empty, Loading, ErrorNote, Button } from "../components/ui";
import { StatusBadge } from "../components/status/StatusBadge";
import { Modal } from "../components/Modal";
import { ApiError } from "../api/client";

export function ActionItems() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["action-items"], queryFn: opsApi.actionItems });
  const [adding, setAdding] = useState(false);
  const [msg, setMsg] = useState("");
  const close = useMutation({ mutationFn: (id: string) => opsApi.closeActionItem(id), onSuccess: () => qc.invalidateQueries({ queryKey: ["action-items"] }) });
  const checks = useMutation({ mutationFn: () => opsApi.runChecks(), onSuccess: (r) => { setMsg(`Exception checks created ${r.created} item(s).`); qc.invalidateQueries({ queryKey: ["action-items"] }); } });

  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorNote error={q.error} />;
  return (
    <div>
      <h1>Needs Attention</h1>
      <Card title="Open and closed items" action={<div className="row-actions"><Button variant="out" onClick={() => checks.mutate()} disabled={checks.isPending}>Run exception checks</Button><Button onClick={() => setAdding(true)}>New action item</Button></div>}>
        {msg && <div className="okmsg" role="status">{msg}</div>}
        {(q.data ?? []).length === 0 ? <Empty msg="No action items." /> : (
          <table>
            <caption className="vis-hidden">Action items</caption>
            <thead><tr><th>Title</th><th>Owner</th><th>Due</th><th>Severity</th><th>Status</th><th>Source</th><th></th></tr></thead>
            <tbody>{(q.data ?? []).map((a) => (
              <tr key={a.action_id}>
                <td>{a.title}</td><td>{a.owner ?? "—"}</td><td>{a.due_date ?? "—"}</td>
                <td>{a.severity ?? "—"}</td><td><StatusBadge status={a.status} /></td><td>{a.source ?? "—"}</td>
                <td>{a.status !== "closed" && <button className="btn out sm" onClick={() => close.mutate(a.action_id)}>Close</button>}</td>
              </tr>))}</tbody>
          </table>
        )}
      </Card>
      {adding && <AddActionModal onClose={() => setAdding(false)} onDone={() => { setAdding(false); qc.invalidateQueries({ queryKey: ["action-items"] }); }} />}
    </div>
  );
}

function AddActionModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [title, setTitle] = useState(""); const [owner, setOwner] = useState("");
  const [due, setDue] = useState(""); const [sev, setSev] = useState("action_required");
  const [err, setErr] = useState("");
  const m = useMutation({
    mutationFn: () => opsApi.addActionItem({ title, owner: owner || undefined, due_date: due || undefined, severity: sev }),
    onSuccess: onDone, onError: (e) => setErr(e instanceof ApiError ? e.friendly : "Could not add."),
  });
  return (
    <Modal title="New action item" onClose={onClose}>
      <div className="form">
        <label htmlFor="a-title">Title</label><input id="a-title" value={title} onChange={(e) => setTitle(e.target.value)} />
        <label htmlFor="a-owner">Owner</label><input id="a-owner" value={owner} onChange={(e) => setOwner(e.target.value)} />
        <label htmlFor="a-due">Due date</label><input id="a-due" type="date" value={due} onChange={(e) => setDue(e.target.value)} />
        <label htmlFor="a-sev">Severity</label>
        <select id="a-sev" value={sev} onChange={(e) => setSev(e.target.value)}>{["monitor", "action_required", "command_decision_required"].map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}</select>
        {err && <div className="err" role="alert">{err}</div>}
        <Button onClick={() => m.mutate()} disabled={!title || m.isPending}>Add</Button>
      </div>
    </Modal>
  );
}
