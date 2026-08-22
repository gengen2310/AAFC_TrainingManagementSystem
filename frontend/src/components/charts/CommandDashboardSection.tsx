import { useQuery } from "@tanstack/react-query";
import { dashboardApi } from "../../api";
import { Card, Loading } from "../ui";
import { ChartCard } from "./DashboardCharts";

// Wing/National Command Dashboard (Sections A: Immediate Training Readiness,
// B: Training Delivery Performance) -- mirrors connected-frontend's rich
// cmd-dash-wing/cmd-dash-national view (GET /api/dashboard/command), which
// previously had zero Planning Workspace consumer at all. Shared by
// WingOverview, NationalOverview, and Dashboard.tsx so all three land on the
// same underlying real-time readiness/risk data, not three divergent copies.
export function CommandDashboardSection({ window: win, wingId }: { window: "week" | "term" | "year"; wingId?: string }) {
  const commandQ = useQuery({
    queryKey: ["dashboard-command", win, wingId],
    queryFn: () => dashboardApi.command(win, wingId),
    staleTime: 2 * 60 * 1000,
  });

  if (commandQ.isLoading) return <Loading />;
  if (!commandQ.data || commandQ.data.error) return null;
  const d = commandQ.data;

  return (
    <>
      <Card title={`Command Dashboard — ${d.scope === "wing" ? "Wing" : "National"} (${d.period.label})`}>
        <p className="muted" style={{ fontSize: 'var(--fs-xs)', margin: 0 }}>
          {d.units_in_scope} unit(s) in scope · {d.data_confidence.units_reporting} reporting this period
          {d.data_confidence.completeness_pct != null && ` (${d.data_confidence.completeness_pct}% complete)`}
        </p>
      </Card>
      <Card title="A1 — Next parade night readiness">
        <ChartCard chart={d.sections.A.readiness_matrix} />
      </Card>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 4 }}>
        <Card title="A2 — Eight-week risk forecast">
          <ChartCard chart={d.sections.A.risk_forecast} />
        </Card>
        <Card title="A3 — Immediate issues requiring support">
          <ChartCard chart={d.sections.A.immediate_issues} />
        </Card>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 4 }}>
        <Card title="B1 — Training delivered each week">
          <ChartCard chart={d.sections.B.weekly_delivered} />
        </Card>
        <Card title="B2 — Delivery reliability trend">
          <ChartCard chart={d.sections.B.reliability_trend} />
        </Card>
        <Card title="B3 — Training Period outcomes by unit">
          <ChartCard chart={d.sections.B.outcomes_by_unit} />
        </Card>
        <Card title="B4 — Cancellation and non-delivery causes">
          <ChartCard chart={d.sections.B.cancellation_pareto} />
        </Card>
      </div>
    </>
  );
}
