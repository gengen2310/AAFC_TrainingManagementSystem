import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { reportApi, trainingApi } from "../api";
import { Card, Stat, Empty, Loading, ErrorNote } from "../components/ui";
import { StatusBadge, DecisionBadge } from "../components/status/StatusBadge";
import { DrilldownPanel } from "../components/DrilldownPanel";
import { useAuth } from "../auth/AuthProvider";
import { canViewCadets } from "../auth/permissions";

export function Dashboard() {
  const { session } = useAuth();
  const summary = useQuery({ queryKey: ["summary"], queryFn: reportApi.summary });
  const readiness = useQuery({ queryKey: ["readiness"], queryFn: reportApi.readiness });
  const coverage = useQuery({ queryKey: ["coverage"], queryFn: reportApi.coverage });
  const parades = useQuery({ queryKey: ["parade-nights"], queryFn: () => trainingApi.paradeNights() });
  const risk = useQuery({ queryKey: ["cadet-risk"], queryFn: trainingApi.cadetRisk, enabled: canViewCadets(session) });
  const [drill, setDrill] = useState<string | null>(null);

  if (summary.isLoading) return <Loading />;
  if (summary.error) return <ErrorNote error={summary.error} />;
  if (!summary.data) return <ErrorNote error={new Error("Dashboard data unavailable. Please refresh.")} />;
  const c = summary.data.counts;
  const worstBand = readiness.data?.parade_nights?.[0]?.band ?? "—";
  const upcoming = (parades.data ?? []).filter((p) => !p.published_status || true).slice(0, 6);

  return (
    <div>
      <h1>Dashboard</h1>
      <div className="sg">
        <button className="stat-btn" onClick={() => setDrill("readiness")}><Stat label="Next-parade readiness" value={readiness.data?.parade_nights?.[0]?.score ?? "—"} hint={worstBand} /></button>
        <Stat label="Parade nights" value={(parades.data ?? []).length} />
        <button className="stat-btn" onClick={() => setDrill("delivered")}><Stat label="Delivered" value={c.delivered ?? 0} /></button>
        <button className="stat-btn" onClick={() => setDrill("not_delivered")}><Stat label="Not delivered" value={c.not_delivered ?? 0} /></button>
        <Stat label="Cancelled / resched." value={(c.cancelled ?? 0) + (c.rescheduled ?? 0)} />
        <button className="stat-btn" onClick={() => setDrill("coverage")}><Stat label="Curriculum coverage" value={`${coverage.data?.coverage_pct ?? 0}%`} /></button>
      </div>

      <Card title="Training decision">
        <DecisionBadge decision={summary.data!.decision} /> &nbsp;
        <span className="muted">Based on {summary.data!.total} sessions this training year.</span>
      </Card>

      <Card title="Upcoming parade nights">
        {upcoming.length === 0 ? <Empty msg="No parade nights yet. Create one from the Parade Nights page." /> : (
          <table>
            <caption className="vis-hidden">Upcoming parade nights</caption>
            <thead><tr><th>Date</th><th>Term</th><th>Sessions</th><th>Published</th><th>Readiness</th></tr></thead>
            <tbody>{upcoming.map((p) => (
              <tr key={p.parade_night_id}><td>{p.date}</td><td>{p.term ?? "—"}</td><td>{p.sessions.length}</td>
                <td><StatusBadge status={p.published_status ? "published" : "draft"} /></td>
                <td>{p.readiness_score ?? "—"}</td></tr>))}</tbody>
          </table>
        )}
      </Card>

      {canViewCadets(session) && (
        <Card title="Cadet risk summary">
          {(risk.data ?? []).length === 0 ? <Empty msg="No cadet risk flags." /> :
            <ul className="risk-list">{(risk.data ?? []).map((f, i) => (
              <li key={i}><strong>{f.cadet}</strong> — {f.reasons.join("; ")}</li>))}</ul>}
        </Card>
      )}

      {drill === "not_delivered" && <NotDeliveredDrill onClose={() => setDrill(null)} />}
      {drill === "coverage" && <CoverageDrill onClose={() => setDrill(null)} />}
      {drill === "readiness" && <ReadinessDrill onClose={() => setDrill(null)} />}
      {drill === "delivered" && <DrilldownPanel title="Delivered sessions" onClose={() => setDrill(null)}><p className="muted">Delivered count comes from session statuses. See Reports → Summary for the full breakdown.</p></DrilldownPanel>}
    </div>
  );
}

function NotDeliveredDrill({ onClose }: { onClose: () => void }) {
  const q = useQuery({ queryKey: ["nd"], queryFn: reportApi.notDelivered });
  return <DrilldownPanel title="Not delivered — records" onClose={onClose}>
    {q.isLoading ? <Loading /> : (q.data?.sessions.length ? (
      <table><thead><tr><th>Code</th><th>Reason</th></tr></thead>
        <tbody>{q.data!.sessions.map((s) => <tr key={s.id}><td>{s.curriculum_code_at_time ?? "—"}</td><td>{s.not_delivered_reason ?? "—"}</td></tr>)}</tbody></table>
    ) : <Empty msg="No not-delivered sessions." />)}
  </DrilldownPanel>;
}
function CoverageDrill({ onClose }: { onClose: () => void }) {
  const q = useQuery({ queryKey: ["coverage"], queryFn: reportApi.coverage });
  return <DrilldownPanel title="Curriculum coverage — unscheduled items" onClose={onClose}>
    {q.isLoading ? <Loading /> : (q.data?.unscheduled.length ? (
      <table><thead><tr><th>Code</th><th>Title</th><th>Phase</th></tr></thead>
        <tbody>{q.data!.unscheduled.map((i) => <tr key={i.code}><td>{i.code}</td><td>{i.title}</td><td>{i.phase}</td></tr>)}</tbody></table>
    ) : <Empty msg="All items scheduled." />)}
  </DrilldownPanel>;
}
function ReadinessDrill({ onClose }: { onClose: () => void }) {
  const q = useQuery({ queryKey: ["readiness"], queryFn: reportApi.readiness });
  return <DrilldownPanel title="Readiness — upcoming parade nights" onClose={onClose}>
    {q.isLoading ? <Loading /> : (q.data?.parade_nights.length ? (
      <table><thead><tr><th>Date</th><th>Score</th><th>Band</th><th>Deductions</th></tr></thead>
        <tbody>{q.data!.parade_nights.map((p) => <tr key={p.parade_night_id}><td>{p.date}</td><td>{p.score}</td><td>{p.band}</td>
          <td>{p.deductions.map((d) => d.reason).join("; ") || "—"}</td></tr>)}</tbody></table>
    ) : <Empty msg="No upcoming parade nights." />)}
  </DrilldownPanel>;
}
