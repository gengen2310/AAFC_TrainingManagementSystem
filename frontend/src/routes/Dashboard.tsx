import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { reportApi, trainingApi } from "../api";
import { Card, Stat, Empty, Loading, ErrorNote } from "../components/ui";
import { StatusBadge, DecisionBadge } from "../components/status/StatusBadge";
import { DrilldownPanel } from "../components/DrilldownPanel";
import { useAuth } from "../auth/AuthProvider";
import { canViewCadets } from "../auth/permissions";

const PHASE_ORDER = ["A. Orientation","B. Initial","C. Junior","D. Intermediate","E. Senior","I. Bronze","J. Silver","K. Gold"];

export function Dashboard() {
  const { session } = useAuth();
  const summary = useQuery({ queryKey: ["summary"], queryFn: reportApi.summary });
  const readiness = useQuery({ queryKey: ["readiness"], queryFn: reportApi.readiness });
  const coverage = useQuery({ queryKey: ["coverage"], queryFn: reportApi.coverage });
  const parades = useQuery({ queryKey: ["parade-nights"], queryFn: () => trainingApi.paradeNights() });
  const facLoad = useQuery({ queryKey: ["fac-load"], queryFn: reportApi.facLoad });
  const risk = useQuery({ queryKey: ["cadet-risk"], queryFn: trainingApi.cadetRisk, enabled: canViewCadets(session) });
  const [drill, setDrill] = useState<string | null>(null);

  if (summary.isLoading) return <Loading />;
  if (summary.error) return <ErrorNote error={summary.error} />;
  if (!summary.data) return <ErrorNote error={new Error("Dashboard data unavailable. Please refresh.")} />;
  const c = summary.data.counts;
  const worstBand = readiness.data?.parade_nights?.[0]?.band ?? "—";
  const today = new Date().toISOString().slice(0, 10);
  const upcoming = (parades.data ?? [])
    .filter((p) => p.date >= today)
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(0, 6);

  // Phase breakdown from all sessions across parade nights
  const allSessions = (parades.data ?? []).flatMap((p) => p.sessions);
  const phaseMap: Record<string, { total: number; delivered: number; not_delivered: number }> = {};
  for (const s of allSessions) {
    const ph = s.phase_at_time ?? "—";
    if (!phaseMap[ph]) phaseMap[ph] = { total: 0, delivered: 0, not_delivered: 0 };
    phaseMap[ph].total++;
    if (s.status === "delivered") phaseMap[ph].delivered++;
    if (s.status === "not_delivered") phaseMap[ph].not_delivered++;
  }
  const phaseKeys = [...PHASE_ORDER.filter((p) => phaseMap[p]), ...Object.keys(phaseMap).filter((p) => !PHASE_ORDER.includes(p)).sort()];

  // Facilitator session summary
  const facMap: Record<string, { name: string; delivered: number; planned: number; not_delivered: number; cancelled: number; total: number }> = {};
  for (const s of allSessions) {
    const key = s.facilitator_id ?? s.facilitator_display_name_at_time ?? "Unassigned";
    const name = s.facilitator_display_name_at_time ?? "Unassigned";
    if (!facMap[key]) facMap[key] = { name, delivered: 0, planned: 0, not_delivered: 0, cancelled: 0, total: 0 };
    facMap[key].total++;
    if (s.status === "delivered") facMap[key].delivered++;
    else if (s.status === "planned") facMap[key].planned++;
    else if (s.status === "not_delivered") facMap[key].not_delivered++;
    else if (s.status === "cancelled" || s.status === "cancelled_late") facMap[key].cancelled++;
  }
  const facRows = Object.values(facMap).sort((a, b) => b.total - a.total);

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

      <Card title="Training summary">
        <table>
          <caption className="vis-hidden">Sessions by status</caption>
          <thead><tr><th>Status</th><th>Count</th></tr></thead>
          <tbody>{Object.entries(c).map(([k, v]) => (
            <tr key={k}><td><StatusBadge status={k} /></td><td>{v as number}</td></tr>
          ))}</tbody>
        </table>
      </Card>

      {facLoad.data && facLoad.data.facilitators.length > 0 && (() => {
        const facs = facLoad.data!.facilitators;
        const atRisk = facs.filter((f) => f.risk !== "ok").length;
        return (
          <Card title="Facilitator readiness" action={<DecisionBadge decision={facLoad.data!.decision} />}>
            <p className="muted">
              {facs.length} facilitator{facs.length !== 1 ? "s" : ""} ·{" "}
              {atRisk > 0
                ? <><span className="badge warn">{atRisk} at risk</span> — see Facilitators page for details</>
                : <span className="badge ok">All within normal load</span>}
            </p>
          </Card>
        );
      })()}

      {phaseKeys.length > 0 && (
        <Card title="Progress by phase">
          <table>
            <caption className="vis-hidden">Sessions by phase</caption>
            <thead><tr><th>Phase</th><th>Delivered</th><th>Total</th><th>Completion</th><th>Not delivered</th></tr></thead>
            <tbody>{phaseKeys.map((ph) => {
              const g = phaseMap[ph];
              const pct = g.total ? Math.round(g.delivered / g.total * 100) : 0;
              return (
                <tr key={ph}>
                  <td>{ph}</td>
                  <td>{g.delivered}</td>
                  <td>{g.total}</td>
                  <td><span className={`badge ${pct >= 80 ? "ok" : pct >= 40 ? "warn" : "red"}`}>{pct}%</span></td>
                  <td>{g.not_delivered > 0 ? <span className="badge warn">{g.not_delivered} ND</span> : <span className="muted">—</span>}</td>
                </tr>
              );
            })}</tbody>
          </table>
        </Card>
      )}

      {facRows.length > 0 && (
        <Card title="Facilitator summary">
          <table>
            <caption className="vis-hidden">Sessions by facilitator</caption>
            <thead><tr><th>Facilitator</th><th>Delivered</th><th>Planned</th><th>Not del.</th><th>Cancelled</th><th>Total</th></tr></thead>
            <tbody>{facRows.map((f) => (
              <tr key={f.name}>
                <td style={{ fontWeight: 700 }}>{f.name}</td>
                <td>{f.delivered}</td>
                <td>{f.planned}</td>
                <td>{f.not_delivered > 0 ? <span className="badge warn">{f.not_delivered}</span> : 0}</td>
                <td>{f.cancelled > 0 ? <span className="badge red">{f.cancelled}</span> : 0}</td>
                <td style={{ fontWeight: 700 }}>{f.total}</td>
              </tr>
            ))}</tbody>
          </table>
        </Card>
      )}

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
      {drill === "delivered" && <DrilldownPanel title="Delivered sessions" onClose={() => setDrill(null)}><p className="muted">Delivered count comes from session statuses. See the Training summary card on this page for the full status breakdown.</p></DrilldownPanel>}
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
