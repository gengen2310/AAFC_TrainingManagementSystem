import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { reportApi, trainingApi, dashboardApi } from "../api";
import { Card, Stat, Empty, Loading, ErrorNote } from "../components/ui";
import { StatusBadge, DecisionBadge } from "../components/status/StatusBadge";
import { DrilldownPanel } from "../components/DrilldownPanel";
import { ChartCard } from "../components/charts/DashboardCharts";
import type { DashboardChart } from "../api/types";
import { useAuth } from "../auth/AuthProvider";
import { canViewCadets } from "../auth/permissions";
import { useScopedSquadron } from "../layout/SquadronViewContext";

// Chart-led Dashboard consuming the same backend chart endpoints
// (/api/dashboard/charts, /api/dashboard/charts/strategic) already used by
// connected-frontend's Main TMS Dashboard — Phase 4 of the master
// transformation plan. Tactical/operational charts load immediately;
// strategic (resilience) charts load on demand behind a button, matching
// the existing load-order pattern.

type Window = "week" | "term" | "year";

const SQUADRON_CHART_ORDER = [
  "weekly_outcomes", "delivery_trend", "session_outcomes", "cancellation_reasons",
  "curriculum_progress", "curriculum_backlog", "facilitator_workload",
];
const WING_CHART_ORDER = ["squadron_readiness", "squadron_delivery_comparison", "wing_subject_area_gaps"];
const NATIONAL_CHART_ORDER = ["wing_readiness", "wing_delivery_comparison"];
const STRATEGIC_CHART_ORDER = [
  "capability_dependency", "subject_area_resilience",
  "facilitator_status_distribution", "facilitator_repeated_gaps", "long_term_delivery_trend",
];

export function Dashboard() {
  const { session } = useAuth();
  const [win, setWin] = useState<Window>("term");
  const [drill, setDrill] = useState<string | null>(null);
  const [showStrategic, setShowStrategic] = useState(false);
  // Wing/National viewers get their comparison dashboard regardless of selection;
  // selecting a squadron (master transformation plan Block 8) layers that
  // squadron's own tactical/operational charts on top — it never blocks the page.
  const { squadronId } = useScopedSquadron();

  const chartsQ = useQuery({
    queryKey: ["dashboard-charts", win, squadronId],
    queryFn: () => dashboardApi.charts(win, squadronId),
    staleTime: 2 * 60 * 1000,
  });
  const strategicQ = useQuery({
    queryKey: ["dashboard-charts-strategic"],
    queryFn: () => dashboardApi.strategic("year"),
    enabled: showStrategic,
    staleTime: 5 * 60 * 1000,
  });
  const risk = useQuery({ queryKey: ["cadet-risk"], queryFn: trainingApi.cadetRisk, enabled: canViewCadets(session) });
  // Exact-value quick stats + named/dated records — retained alongside the charts above,
  // since a chart encodes a shape but these give the precise figures and identifiable
  // records the doctrine requires ("keep named people, exact sessions ... in drill-downs").
  const summary = useQuery({ queryKey: ["summary", squadronId], queryFn: () => reportApi.summary(squadronId) });
  const parades = useQuery({ queryKey: ["parade-nights", squadronId], queryFn: () => trainingApi.paradeNights(squadronId) });

  if (chartsQ.isLoading) return <Loading />;
  if (chartsQ.error) return <ErrorNote error={chartsQ.error} />;
  if (!chartsQ.data) return <ErrorNote error={new Error("Dashboard data unavailable. Please refresh.")} />;

  const scope = chartsQ.data.scope;
  const charts = chartsQ.data.charts;
  const strategicCharts = strategicQ.data?.charts ?? {};
  const chartRow = (id: string): DashboardChart | undefined => charts[id];
  // A squadron's tactical charts are present either because the caller IS
  // squadron-scoped, or because a Wing/National viewer selected one via the
  // squadron selector — "tonight" only ever appears in the squadron chart bundle.
  const viewingSquadron = scope === "squadron" || !!chartRow("tonight");

  const orderFor = scope === "wing" ? WING_CHART_ORDER : scope === "national" ? NATIONAL_CHART_ORDER : SQUADRON_CHART_ORDER;

  const today = new Date().toISOString().slice(0, 10);
  const upcoming = (parades.data ?? [])
    .filter((p) => p.date >= today)
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(0, 6);

  return (
    <div>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
        <h1>Dashboard</h1>
        <label style={{ fontSize: 12, display: "flex", alignItems: "center", gap: 6 }}>
          Period
          <select value={win} onChange={e => setWin(e.target.value as Window)} style={{ fontSize: 12, padding: "4px 6px" }}>
            <option value="week">This week</option>
            <option value="term">This term</option>
            <option value="year">This year</option>
          </select>
        </label>
      </div>

      {scope !== "squadron" && (
        <div style={{ margin: "0 0 12px" }}>
          <p className="muted" style={{ fontSize: 12 }}>
            {viewingSquadron
              ? "Showing the selected squadron's own Dashboard, plus your comparison charts below."
              : "Select a squadron from the nav to see its own tactical Dashboard here."}
          </p>
        </div>
      )}

      {viewingSquadron && summary.data && (
        <>
          <div className="sg">
            <Stat label="Parade nights" value={(parades.data ?? []).length} />
            <Stat label="Delivered" value={summary.data.counts.delivered ?? 0} />
            <button className="stat-btn" onClick={() => setDrill("not_delivered")}>
              <Stat label="Not delivered" value={summary.data.counts.not_delivered ?? 0} />
            </button>
            <Stat label="Cancelled / resched." value={(summary.data.counts.cancelled ?? 0) + (summary.data.counts.rescheduled ?? 0)} />
          </div>
          <Card title="Training decision">
            <DecisionBadge decision={summary.data.decision} /> &nbsp;
            <span className="muted">Based on {summary.data.total} sessions this training year.</span>
          </Card>
        </>
      )}

      {/* A — Tonight & upcoming readiness (tactical; squadron scope, or Wing/National with a squadron selected) */}
      {viewingSquadron && chartRow("tonight") && (
        <Card title="A — Tonight & this week">
          <ChartCard chart={chartRow("tonight")!} />
        </Card>
      )}
      {viewingSquadron && chartRow("upcoming_readiness") && (
        <Card title="Next 8 parade nights">
          <ChartCard chart={chartRow("upcoming_readiness")!} />
        </Card>
      )}

      {/* B1 — the selected squadron's own term charts, layered above the Wing/National
          comparison charts (master transformation plan Block 8: inherit, don't diverge) */}
      {viewingSquadron && scope !== "squadron" && (
        <Card title="Selected squadron — this term">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 4 }}>
            {SQUADRON_CHART_ORDER.map(id => chartRow(id) && (
              <ChartCard key={`sq-${id}`} chart={chartRow(id)!} />
            ))}
          </div>
        </Card>
      )}

      {/* B — Delivery / curriculum / comparison charts, scope-appropriate */}
      <Card title={scope === "squadron" ? "B — This term" : scope === "wing" ? "Squadron comparison" : "Wing comparison"}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 4 }}>
          {orderFor.map(id => chartRow(id) && (
            <ChartCard key={id} chart={chartRow(id)!} />
          ))}
        </div>
      </Card>

      {/* C — Strategic / resilience, deferred load. The backend's
          /charts/strategic endpoint has no "national" scope branch at all
          (see backend/app/routers/dashboard.py get_strategic_charts) — showing
          the button there would open an empty card, so it's hidden rather than
          offering an affordance that leads nowhere. */}
      {scope === "national" ? null : !showStrategic ? (
        <div style={{ margin: "12px 0" }}>
          <button className="btn out" onClick={() => setShowStrategic(true)}>Load Resilience Charts ↓</button>
        </div>
      ) : (
        <Card title="D — Staffing resilience & long-term trends">
          {strategicQ.isLoading ? <Loading /> : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 4 }}>
              {STRATEGIC_CHART_ORDER.map(id => strategicCharts[id] && (
                <ChartCard key={id} chart={strategicCharts[id]} />
              ))}
            </div>
          )}
        </Card>
      )}

      {viewingSquadron && (
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
      )}

      {canViewCadets(session) && (
        <Card title="Cadet risk summary">
          {(risk.data ?? []).length === 0 ? <Empty msg="No cadet risk flags." /> :
            <ul className="risk-list">{(risk.data ?? []).map((f, i) => (
              <li key={i}><strong>{f.cadet}</strong> — {f.reasons.join("; ")}</li>))}</ul>}
        </Card>
      )}

      {drill === "not_delivered" && <NotDeliveredDrill squadronId={squadronId} onClose={() => setDrill(null)} />}
    </div>
  );
}

function NotDeliveredDrill({ squadronId, onClose }: { squadronId?: string; onClose: () => void }) {
  const q = useQuery({ queryKey: ["nd", squadronId], queryFn: () => reportApi.notDelivered(squadronId) });
  return <DrilldownPanel title="Not delivered — records" onClose={onClose}>
    {q.isLoading ? <Loading /> : (q.data?.sessions.length ? (
      <table><thead><tr><th>Code</th><th>Reason</th></tr></thead>
        <tbody>{q.data!.sessions.map((s) => <tr key={s.id}><td>{s.curriculum_code_at_time ?? "—"}</td><td>{s.not_delivered_reason ?? "—"}</td></tr>)}</tbody></table>
    ) : <Empty msg="No not-delivered sessions." />)}
  </DrilldownPanel>;
}
