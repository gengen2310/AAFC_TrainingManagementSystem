import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { orgApi } from "../api";
import { Card, Empty, Loading, ErrorNote, Button } from "../components/ui";

// Read-only audit log with filters. No edit/delete.
export function Audit() {
  const [objectType, setObjectType] = useState("");
  const [objectId, setObjectId] = useState("");
  const [limit, setLimit] = useState("100");
  const q = useQuery({
    queryKey: ["audit", objectType, objectId, limit],
    queryFn: () => orgApi.audit({ object_type: objectType || undefined, object_id: objectId || undefined, limit: Number(limit) }),
  });
  return (
    <div>
      <h1>Audit</h1>
      <Card title="Filters">
        <div className="filter-bar">
          <label htmlFor="au-type" className="vis-hidden">Object type</label>
          <input id="au-type" placeholder="object type (e.g. parade_night)" value={objectType} onChange={(e) => setObjectType(e.target.value)} />
          <label htmlFor="au-id" className="vis-hidden">Object id</label>
          <input id="au-id" placeholder="object id" value={objectId} onChange={(e) => setObjectId(e.target.value)} />
          <label htmlFor="au-lim" className="vis-hidden">Limit</label>
          <input id="au-lim" type="number" value={limit} onChange={(e) => setLimit(e.target.value)} style={{ width: 90 }} />
          <Button variant="out" onClick={() => q.refetch()}>Apply</Button>
        </div>
      </Card>
      <Card title="Audit log (read-only)">
        {q.isLoading ? <Loading /> : q.error ? <ErrorNote error={q.error} /> :
          (q.data ?? []).length === 0 ? <Empty msg="No audit rows." /> : (
            <table>
              <caption className="vis-hidden">Audit log</caption>
              <thead><tr><th>Time</th><th>Role</th><th>Action</th><th>Object</th><th>Reason</th><th>Proxy</th></tr></thead>
              <tbody>{(q.data ?? []).map((a) => (
                <tr key={a.audit_id}>
                  <td>{new Date(a.timestamp).toLocaleString()}</td><td>{a.role}</td><td>{a.action}</td>
                  <td>{a.object_type ?? "—"}{a.object_id ? ` (${a.object_id.slice(0, 8)})` : ""}</td>
                  <td>{a.reason ?? "—"}</td><td>{a.proxy_session_id ? "yes" : "—"}</td>
                </tr>))}</tbody>
            </table>
          )}
      </Card>
    </div>
  );
}
