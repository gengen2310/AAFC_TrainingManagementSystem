import { useQuery } from "@tanstack/react-query";
import { orgApi } from "../api";
import { Card, Empty, Loading, ErrorNote } from "../components/ui";
import { useAuth } from "../auth/AuthProvider";

// Admin / Settings: scope info + squadron list. Access-code reset is a backend-gated workflow
// (POST /api/auth/change-code) and is intentionally not a free-form code viewer.
export function Admin() {
  const { session } = useAuth();
  const squadrons = useQuery({ queryKey: ["squadrons"], queryFn: orgApi.squadrons });
  return (
    <div>
      <h1>Admin / Settings</h1>
      <Card title="Your scope">
        <ul>
          <li>Role: <strong>{session?.role}</strong></li>
          <li>Wing: {session?.wing_id ?? "—"}</li>
          <li>Squadron: {session?.squadron_id ?? "—"}</li>
        </ul>
      </Card>
      <Card title="Squadrons in scope">
        {squadrons.isLoading ? <Loading /> : squadrons.error ? <ErrorNote error={squadrons.error} /> :
          (squadrons.data ?? []).length === 0 ? <Empty msg="No squadrons in scope." /> : (
            <table><caption className="vis-hidden">Squadrons</caption>
              <thead><tr><th>Code</th><th>Name</th><th>Parade day</th><th>Start</th><th>End</th></tr></thead>
              <tbody>{(squadrons.data ?? []).map((s) => (
                <tr key={s.squadron_id}><td>{s.code}</td><td>{s.short_name}</td><td>{s.default_parade_day ?? "—"}</td>
                  <td>{s.default_start_time ?? "—"}</td><td>{s.default_end_time ?? "—"}</td></tr>))}</tbody></table>
          )}
      </Card>
      <Card title="Access codes">
        <p className="muted">Access codes are never displayed. Authorised admins reset a user's code via a backend
          workflow (change-code); the value is hashed server-side and is never returned to the UI.</p>
      </Card>
    </div>
  );
}
