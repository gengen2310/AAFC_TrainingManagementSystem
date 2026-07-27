import { useQuery } from "@tanstack/react-query";
import { reportApi } from "../api";
import { Card, Empty, Loading, ErrorNote, Bar } from "../components/ui";
import { DecisionBadge } from "../components/status/StatusBadge";
import { useAuth } from "../auth/AuthProvider";
import { isWing, isNational } from "../auth/permissions";

// Only implemented backend reports are shown. Training summary has moved to Dashboard.
export function Reports() {
  const { session } = useAuth();
  const coverage = useQuery({ queryKey: ["coverage"], queryFn: reportApi.coverage });
  const load = useQuery({ queryKey: ["fac-load"], queryFn: () => reportApi.facLoad() });
  const nd = useQuery({ queryKey: ["nd"], queryFn: () => reportApi.notDelivered() });

  return (
    <div>
      <h1>Training Reports</h1>

      <Card title="Curriculum coverage" action={coverage.data && <DecisionBadge decision={coverage.data.decision} />}>
        {coverage.isLoading ? <Loading /> : coverage.error ? <ErrorNote error={coverage.error} /> : (
          <div>
            <Bar pct={coverage.data!.coverage_pct} label="Curriculum coverage" />
            <p className="muted">{coverage.data!.scheduled}/{coverage.data!.total} scheduled · {coverage.data!.delivered} delivered.</p>
            {coverage.data!.unscheduled.length > 0 && (
              <details><summary>{coverage.data!.unscheduled.length} unscheduled items</summary>
                <table><thead><tr><th>Code</th><th>Title</th><th>Phase</th></tr></thead>
                  <tbody>{coverage.data!.unscheduled.map((i) => <tr key={i.code}><td>{i.code}</td><td>{i.title}</td><td>{i.phase}</td></tr>)}</tbody></table>
              </details>)}
          </div>
        )}
      </Card>

      <Card title="Facilitator load" action={load.data && <DecisionBadge decision={load.data.decision} />}>
        {load.isLoading ? <Loading /> : load.error ? <ErrorNote error={load.error} /> :
          (load.data!.facilitators.length === 0 ? <Empty msg="No facilitator load yet." /> : (
            <table><thead><tr><th>Facilitator</th><th>Sessions</th><th>Delivered</th><th>Risk</th></tr></thead>
              <tbody>{load.data!.facilitators.map((f) => <tr key={f.name}><td>{f.name}</td><td>{f.sessions}</td><td>{f.delivered}</td>
                <td><span className={`badge ${f.risk === "ok" ? "ok" : f.risk === "high" ? "warn" : "red"}`}>{f.risk}</span></td></tr>)}</tbody></table>
          ))}
      </Card>

      <Card title="Not delivered" action={nd.data && <DecisionBadge decision={nd.data.decision} />}>
        {nd.isLoading ? <Loading /> : nd.error ? <ErrorNote error={nd.error} /> :
          (nd.data!.sessions.length === 0 ? <Empty msg="No not-delivered sessions." /> : (
            <table><thead><tr><th>Code</th><th>Reason</th></tr></thead>
              <tbody>{nd.data!.sessions.map((s) => <tr key={s.id}><td>{s.curriculum_code_at_time ?? "—"}</td><td>{s.not_delivered_reason ?? "—"}</td></tr>)}</tbody></table>
          ))}
      </Card>

      {(isWing(session) || isNational(session)) && <p className="muted">Wing and National rollups are on the Wing Overview / National Overview pages.</p>}
      <Card title="Other reports">
        <p className="muted">Additional Cadet Program reports from the catalogue are implemented incrementally on the same
          backend-query + drill-down pattern. Reports that are not yet implemented are not shown here and never display fabricated data.</p>
      </Card>
    </div>
  );
}
