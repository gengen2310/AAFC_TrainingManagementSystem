import type { CSSProperties } from "react";
import type { DashboardChart } from "../../api/types";

// Chart-rendering components consuming the shared backend chart schema
// (chart_id/title/explanation/question/chart_type/data/insight/empty_state/drill_down).
// Mirrors the rendering approach already proven in connected-frontend's
// _chartHBar/_chartDonut/_chartLine/etc. (index.html), reimplemented natively
// for React rather than ported file-for-file, per the master transformation
// plan's Phase 4 (Planning Workspace Dashboard rebuild) and risk register
// guidance to port the *logic*, not the files.

const cardSx: CSSProperties = {
  background: "var(--surface)", border: "1px solid var(--border)",
  borderRadius: "var(--radius, 10px)", padding: "14px 16px", marginBottom: 12,
};
const titleSx: CSSProperties = { fontSize: 13, fontWeight: 700, color: "var(--text)", marginBottom: 2 };
const expSx: CSSProperties = { fontSize: 11, color: "var(--muted-text)", marginBottom: 10 };
const insightSx: CSSProperties = {
  fontSize: 11, color: "var(--aafc-dark-blue)", background: "var(--aafc-blue, #51B0E3)1a",
  border: "1px solid var(--border)", borderRadius: 6, padding: "6px 10px", marginTop: 10,
};
const emptySx: CSSProperties = { fontSize: 12, color: "var(--muted-text)", padding: "12px 4px" };

function EmptyState({ chart }: { chart: DashboardChart }) {
  return <div style={emptySx}>{chart.empty_state ?? "No data available."}</div>;
}

function rowsOf(chart: DashboardChart): Array<Record<string, unknown>> {
  return Array.isArray(chart.data) ? (chart.data as Array<Record<string, unknown>>) : [];
}

function numOf(row: Record<string, unknown>, key: string): number {
  const v = row[key];
  return typeof v === "number" ? v : 0;
}

function labelOf(row: Record<string, unknown>): string {
  return String(row.label ?? row.name ?? row.phase ?? "—");
}

function valueKeyFor(row: Record<string, unknown>): string {
  if ("readiness_pct" in row) return "readiness_pct";
  if ("delivered" in row) return "delivered";
  if ("count" in row) return "count";
  if ("sessions" in row) return "sessions";
  if ("value" in row) return "value";
  return "count";
}

function colorFor(row: Record<string, unknown>): string {
  if (typeof row.color === "string") return row.color;
  if (typeof row.readiness_pct === "number") {
    const p = row.readiness_pct;
    return p >= 80 ? "var(--success, #1A7F4B)" : p >= 60 ? "var(--warning, #C97A00)" : "var(--aafc-red, #E51937)";
  }
  if (row.risk === "ok") return "var(--success, #1A7F4B)";
  if (row.risk === "warn") return "var(--warning, #C97A00)";
  if (row.risk === "critical") return "var(--aafc-red, #E51937)";
  return "var(--aafc-royal-blue, #004B8D)";
}

/** Horizontal ranked bar list — chart_type "bar_horizontal". */
export function HBarChart({ chart }: { chart: DashboardChart }) {
  const rows = rowsOf(chart);
  if (!rows.length) return <EmptyState chart={chart} />;
  const maxV = Math.max(...rows.map(r => numOf(r, valueKeyFor(r))), 1);
  return (
    <div>
      {rows.map((r, i) => {
        const key = valueKeyFor(r);
        const v = numOf(r, key);
        const w = Math.round((v / maxV) * 100);
        const display = key === "readiness_pct" ? `${v}%`
          : (typeof r.delivered === "number" && typeof r.total === "number") ? `${r.delivered} / ${r.total}`
          : String(v);
        return (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
            <div style={{ minWidth: 110, maxWidth: 140, fontSize: 11, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={labelOf(r)}>
              {labelOf(r)}
            </div>
            <div style={{ flex: 1, background: "var(--background, #f1f5f9)", borderRadius: 3, height: 10 }}>
              <div style={{ width: `${w}%`, height: "100%", background: colorFor(r), borderRadius: 3, transition: "width .3s" }} />
            </div>
            <div style={{ minWidth: 52, textAlign: "right", fontSize: 11, color: "var(--muted-text)" }}>{display}</div>
          </div>
        );
      })}
    </div>
  );
}

/** Donut with legend — chart_type "donut". */
export function DonutChart({ chart }: { chart: DashboardChart }) {
  const rows = rowsOf(chart);
  const total = rows.reduce((s, r) => s + numOf(r, "count"), 0);
  if (!rows.length || !total) return <EmptyState chart={chart} />;
  let offset = 0;
  const segments = rows.filter(r => numOf(r, "count") > 0).map(r => {
    const cnt = numOf(r, "count");
    const pct = (cnt / total) * 100;
    const seg = `${colorFor(r)} ${offset.toFixed(1)}% ${(offset + pct).toFixed(1)}%`;
    offset += pct;
    return seg;
  });
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
      <div
        role="img" aria-label={chart.title ?? "Distribution"}
        style={{
          width: 72, height: 72, borderRadius: "50%", flexShrink: 0,
          background: `conic-gradient(${segments.join(",")})`,
          display: "flex", alignItems: "center", justifyContent: "center",
        }}
      >
        <div style={{ width: 48, height: 48, borderRadius: "50%", background: "var(--surface)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14, fontWeight: 700 }}>
          {total}
        </div>
      </div>
      <div style={{ flex: 1 }}>
        {rows.filter(r => numOf(r, "count") > 0).map((r, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, marginBottom: 3 }}>
            <span style={{ width: 10, height: 10, borderRadius: "50%", background: colorFor(r), flexShrink: 0 }} />
            <span>{String(r.label ?? r.status ?? "—")}</span>
            <span style={{ marginLeft: "auto", color: "var(--muted-text)" }}>
              {numOf(r, "count")} <span style={{ fontSize: 9 }}>({Math.round((numOf(r, "count") / total) * 100)}%)</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Simple SVG line chart with optional threshold bands — chart_type "line". */
export function LineChart({ chart }: { chart: DashboardChart }) {
  const rows = rowsOf(chart);
  if (rows.length < 2) return <EmptyState chart={chart} />;
  const W = 420, H = 120, PAD = 24;
  const values = rows.map(r => numOf(r, "reliability_pct"));
  const maxV = 100, minV = 0;
  const stepX = (W - PAD * 2) / (rows.length - 1);
  const yFor = (v: number) => H - PAD - ((v - minV) / (maxV - minV)) * (H - PAD * 2);
  const points = values.map((v, i) => `${PAD + i * stepX},${yFor(v)}`).join(" ");
  const th = chart.thresholds;
  return (
    <div style={{ overflowX: "auto" }}>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", maxWidth: W, height: H }} role="img" aria-label={chart.title ?? "Trend"}>
        {th?.green != null && <line x1={PAD} x2={W - PAD} y1={yFor(th.green)} y2={yFor(th.green)} stroke="var(--success, #1A7F4B)" strokeDasharray="3,3" strokeWidth={1} />}
        {th?.amber != null && <line x1={PAD} x2={W - PAD} y1={yFor(th.amber)} y2={yFor(th.amber)} stroke="var(--warning, #C97A00)" strokeDasharray="3,3" strokeWidth={1} />}
        <polyline points={points} fill="none" stroke="var(--aafc-royal-blue, #004B8D)" strokeWidth={2} />
        {values.map((v, i) => <circle key={i} cx={PAD + i * stepX} cy={yFor(v)} r={2.5} fill="var(--aafc-royal-blue, #004B8D)" />)}
      </svg>
    </div>
  );
}

/** Stacked horizontal bar (e.g. curriculum progress by phase) — chart_type "stacked_bar_horizontal". */
export function StackedBarHChart({ chart }: { chart: DashboardChart }) {
  const rows = rowsOf(chart);
  const series = chart.series ?? [];
  if (!rows.length || !series.length) return <EmptyState chart={chart} />;
  return (
    <div>
      <div style={{ display: "flex", gap: 10, marginBottom: 8, flexWrap: "wrap" }}>
        {series.map(s => (
          <span key={s.key} style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 10 }}>
            <span style={{ width: 9, height: 9, background: s.color ?? "var(--aafc-royal-blue)", borderRadius: 2 }} />
            {s.label}
          </span>
        ))}
      </div>
      {rows.map((r, i) => {
        const total = series.reduce((s, sr) => s + numOf(r, sr.key), 0) || 1;
        return (
          <div key={i} style={{ marginBottom: 6 }}>
            <div style={{ fontSize: 10, color: "var(--muted-text)", marginBottom: 2 }}>{labelOf(r)}</div>
            <div style={{ display: "flex", height: 12, borderRadius: 3, overflow: "hidden", background: "var(--background)" }}>
              {series.map(s => {
                const v = numOf(r, s.key);
                if (!v) return null;
                return <div key={s.key} title={`${s.label}: ${v}`} style={{ width: `${(v / total) * 100}%`, background: s.color ?? "var(--aafc-royal-blue)" }} />;
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/** Grouped vertical bar — chart_type "grouped_bar". */
export function GroupedBarChart({ chart }: { chart: DashboardChart }) {
  const rows = rowsOf(chart);
  const series = chart.series ?? [];
  if (!rows.length || !series.length) return <EmptyState chart={chart} />;
  const maxV = Math.max(...rows.flatMap(r => series.map(s => numOf(r, s.key))), 1);
  return (
    <div>
      <div style={{ display: "flex", gap: 10, marginBottom: 8, flexWrap: "wrap" }}>
        {series.map(s => (
          <span key={s.key} style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 10 }}>
            <span style={{ width: 9, height: 9, background: s.color ?? "var(--aafc-royal-blue)", borderRadius: 2 }} />
            {s.label}
          </span>
        ))}
      </div>
      <div style={{ display: "flex", alignItems: "flex-end", gap: 12, overflowX: "auto", height: 90 }}>
        {rows.map((r, i) => (
          <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: "center", flexShrink: 0 }}>
            <div style={{ display: "flex", alignItems: "flex-end", gap: 2, height: 70 }}>
              {series.map(s => {
                const v = numOf(r, s.key);
                const h = Math.round((v / maxV) * 70);
                return <div key={s.key} title={`${s.label}: ${v}`} style={{ width: 10, height: h, background: s.color ?? "var(--aafc-royal-blue)", borderRadius: "2px 2px 0 0" }} />;
              })}
            </div>
            <div style={{ fontSize: 9, color: "var(--muted-text)", marginTop: 3, maxWidth: 60, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {labelOf(r)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Row × column heatmap — chart_type "heatmap". */
export function HeatmapChart({ chart }: { chart: DashboardChart }) {
  const rows = chart.data as Array<{ label: string; cells: Array<{ label: string; count: number; risk: string }> }> | undefined;
  if (!rows?.length) return <EmptyState chart={chart} />;
  const cols = rows[0]?.cells.map(c => c.label) ?? [];
  const riskColor = (risk: string) => risk === "ok" ? "#d1fae5" : risk === "warn" ? "#fef3c7" : risk === "critical" ? "#fee2e2" : "#f1f5f9";
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ fontSize: 10, borderCollapse: "separate", borderSpacing: 3 }}>
        <thead>
          <tr>
            <th></th>
            {cols.map(c => <th key={c} style={{ fontSize: 9, color: "var(--muted-text)", padding: "2px 4px", whiteSpace: "nowrap" }}>{c}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              <td style={{ fontSize: 10, fontWeight: 700, padding: "3px 8px", whiteSpace: "nowrap" }}>{row.label}</td>
              {row.cells.map((c, j) => (
                <td key={j} title={`${row.label} — ${c.label}: ${c.count}`} style={{ width: 30, height: 22, textAlign: "center", background: riskColor(c.risk), borderRadius: 3 }}>
                  {c.count || 0}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface TonightData {
  date: string; term: string | null; overall_pct: number;
  sessions_total: number; sessions_ready: number;
  fac_filled: number; fac_total: number; room_filled: number; room_total: number;
  sessions: Array<{ id: string; period: number | null; phase: string | null; title: string | null; facilitator: string | null; room: string | null; status: string; ready: boolean }>;
  issues: Array<{ type: string; severity: string; message: string; action: string }>;
}

/** Tonight's readiness card — chart_type "readiness_card". */
export function ReadinessCard({ chart }: { chart: DashboardChart }) {
  const d = chart.data as TonightData | null;
  if (!d) return <EmptyState chart={chart} />;
  const pct = d.overall_pct;
  const col = pct >= 80 ? "var(--success, #1A7F4B)" : pct >= 60 ? "var(--warning, #C97A00)" : "var(--aafc-red, #E51937)";
  const dateLabel = new Date(d.date + "T00:00:00").toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" });
  return (
    <div>
      <div style={{ fontSize: 11, color: "var(--muted-text)", marginBottom: 8 }}>{dateLabel}{d.term ? ` · Term ${d.term}` : ""}</div>
      <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
        <div style={{
          width: 68, height: 68, borderRadius: "50%", flexShrink: 0,
          background: `conic-gradient(${col} ${pct}%, var(--background, #e5e7eb) 0)`,
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <div style={{ width: 50, height: 50, borderRadius: "50%", background: "var(--surface)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14, fontWeight: 700, color: col }}>
            {pct}%
          </div>
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 10, fontWeight: 800, color: "var(--muted-text)", textTransform: "uppercase", letterSpacing: ".04em", marginBottom: 6 }}>Session Plan</div>
          {d.sessions.map(s => (
            <div key={s.id} style={{ display: "flex", gap: 6, fontSize: 11, marginBottom: 3 }}>
              <span style={{ minWidth: 40, color: "var(--muted-text)" }}>P{s.period ?? "—"}</span>
              <span style={{ flex: 1, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{s.title ?? "Unassigned"}</span>
              <span style={{ color: s.facilitator ? "var(--muted-text)" : "var(--aafc-red)" }}>{s.facilitator ?? "Unstaffed"}</span>
            </div>
          ))}
          {d.issues.length > 0 && (
            <div style={{ marginTop: 8 }}>
              {d.issues.map((iss, i) => (
                <div key={i} style={{ fontSize: 11, color: iss.severity === "high" ? "var(--aafc-red)" : "var(--warning, #C97A00)" }}>
                  ⚠ {iss.message}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

interface UpcomingRow { date: string; term: string | null; sessions_total: number; sessions_ready: number; unstaffed: number; readiness_pct: number; published: boolean; }

/** Grid of upcoming parade-night readiness cards — chart_type "readiness_grid". */
export function ReadinessGrid({ chart }: { chart: DashboardChart }) {
  const rows = (chart.data as UpcomingRow[] | undefined) ?? [];
  if (!rows.length) return <EmptyState chart={chart} />;
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: 8 }}>
      {rows.map((r, i) => {
        const col = r.readiness_pct >= 80 ? "var(--success, #1A7F4B)" : r.readiness_pct >= 60 ? "var(--warning, #C97A00)" : "var(--aafc-red, #E51937)";
        return (
          <div key={i} style={{ border: "1.5px solid var(--border)", borderRadius: 8, padding: 8 }}>
            <div style={{ fontSize: 10, fontWeight: 800 }}>
              {new Date(r.date + "T00:00:00").toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" })}
            </div>
            <div style={{ height: 4, background: "var(--background)", borderRadius: 2, margin: "5px 0" }}>
              <div style={{ width: `${r.readiness_pct}%`, height: "100%", background: col, borderRadius: 2 }} />
            </div>
            <div style={{ fontSize: 10, color: col, fontWeight: 700 }}>{r.readiness_pct}% ready</div>
            {r.unstaffed > 0 && <div style={{ fontSize: 9, color: "var(--warning, #C97A00)", fontWeight: 700 }}>⚠ {r.unstaffed} unstaffed</div>}
            <div style={{ fontSize: 9, color: "var(--muted-text)" }}>{r.sessions_total} sessions</div>
          </div>
        );
      })}
    </div>
  );
}

/** Renders any chart by chart_type, plus its title/explanation/insight wrapper. */
export function ChartCard({ chart, onDrillDown }: { chart: DashboardChart; onDrillDown?: (chart: DashboardChart) => void }) {
  const body = (() => {
    switch (chart.chart_type) {
      case "bar_horizontal": return <HBarChart chart={chart} />;
      case "donut": return <DonutChart chart={chart} />;
      case "line": return <LineChart chart={chart} />;
      case "stacked_bar_horizontal": return <StackedBarHChart chart={chart} />;
      case "stacked_bar":
      case "grouped_bar": return <GroupedBarChart chart={chart} />;
      case "heatmap": return <HeatmapChart chart={chart} />;
      case "readiness_card": return <ReadinessCard chart={chart} />;
      case "readiness_grid": return <ReadinessGrid chart={chart} />;
      default: return <EmptyState chart={chart} />;
    }
  })();
  const clickable = !!(onDrillDown && chart.drill_down);
  return (
    <div
      style={{ ...cardSx, cursor: clickable ? "pointer" : undefined }}
      onClick={clickable ? () => onDrillDown(chart) : undefined}
      role={clickable ? "button" : undefined}
      tabIndex={clickable ? 0 : undefined}
    >
      {chart.title && <div style={titleSx}>{chart.title}</div>}
      {chart.explanation && <div style={expSx}>{chart.explanation}</div>}
      {body}
      {chart.insight && <div style={insightSx}>{chart.insight}</div>}
    </div>
  );
}
