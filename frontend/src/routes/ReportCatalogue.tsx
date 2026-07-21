import { Card } from "../components/ui";

// Honest report catalogue. We do NOT pretend the full ~60-report set exists.
// Each row states backend support, frontend support, priority, value and required role.
type Row = {
  name: string; backend: "yes" | "no" | "partial"; frontend: "yes" | "no";
  priority: "must" | "should" | "later"; value: string; role: string;
};
const ROWS: Row[] = [
  { name: "Training summary",              backend: "yes",     frontend: "yes", priority: "must",   value: "Status mix at a glance",                   role: "Squadron+" },
  { name: "Readiness",                     backend: "yes",     frontend: "yes", priority: "must",   value: "Next-parade readiness + deductions",        role: "Squadron+" },
  { name: "Curriculum coverage",           backend: "yes",     frontend: "yes", priority: "must",   value: "What is scheduled/delivered vs gaps",       role: "Squadron+" },
  { name: "Facilitator load",              backend: "yes",     frontend: "yes", priority: "must",   value: "Spot overloaded instructors",               role: "Squadron+" },
  { name: "Not delivered",                 backend: "yes",     frontend: "yes", priority: "must",   value: "Delivery failures + reasons",               role: "Squadron+" },
  { name: "Wing overview",                 backend: "yes",     frontend: "yes", priority: "must",   value: "Squadron readiness across a Wing",          role: "Wing+" },
  { name: "Wing phase-coverage heatmap",   backend: "yes",     frontend: "no",  priority: "must",   value: "Squadron × phase coverage matrix",          role: "Wing+" },
  { name: "Wing capability",               backend: "yes",     frontend: "no",  priority: "must",   value: "Facilitator subject-balance per squadron",  role: "Wing+" },
  { name: "National overview",             backend: "yes",     frontend: "yes", priority: "must",   value: "Wing rollup for HQ",                        role: "National" },
  { name: "National capability",           backend: "yes",     frontend: "no",  priority: "must",   value: "Wing-level facilitator capability summary", role: "National" },
  { name: "Program coverage (sqn/wing)",   backend: "yes",     frontend: "yes", priority: "should", value: "Cadet Program core vs extension",           role: "Squadron+" },
  { name: "Learning Hub missing-link",     backend: "yes",     frontend: "yes", priority: "should", value: "Find items with no LH link",                role: "Squadron+" },
  { name: "Cross-squadron not-delivered",  backend: "yes",     frontend: "no",  priority: "should", value: "Wing-wide delivery gaps",                   role: "Wing+" },
  { name: "Cancelled / rescheduled trend", backend: "yes",     frontend: "no",  priority: "should", value: "Repeat-cancellation pattern (endpoint: /reports/wing-cancellation-trend)", role: "Wing+" },
  { name: "National version-adoption",     backend: "no",      frontend: "no",  priority: "later",  value: "Program version uptake",                    role: "National" },
  { name: "Annual assurance pack",         backend: "no",      frontend: "no",  priority: "later",  value: "Year-end governance pack",                  role: "National" },
  { name: "Promotion pipeline",            backend: "partial",  frontend: "no",  priority: "later",  value: "Squadron→Wing→National promotions",         role: "Wing+" },
];

function flag(v: string) {
  const cls = v === "yes" ? "ok" : v === "partial" ? "warn" : "red";
  const label = v === "yes" ? "✓ yes" : v === "partial" ? "▲ partial" : v === "no" ? "✕ no" : v;
  return <span className={`badge ${cls}`}>{label}</span>;
}

export function ReportCatalogue() {
  const implemented = ROWS.filter((r) => r.backend === "yes" && r.frontend === "yes").length;
  return (
    <div>
      <h1>Report Catalogue</h1>
      <p className="muted">
        This is the honest state of the reporting catalogue. {implemented} reports are implemented
        end-to-end (backend query + frontend view + drill-down). Items marked "no" or "partial" are
        not built yet and are <strong>not</strong> shown elsewhere with fabricated data.
      </p>
      <Card title={`Catalogue (${ROWS.length} tracked, ${implemented} implemented)`}>
        <table>
          <caption className="vis-hidden">Report catalogue status</caption>
          <thead><tr><th>Report</th><th>Backend</th><th>Frontend</th><th>Priority</th><th>Required role</th><th>Operational value</th></tr></thead>
          <tbody>
            {ROWS.map((r) => (
              <tr key={r.name}>
                <td>{r.name}</td><td>{flag(r.backend)}</td><td>{flag(r.frontend ? "yes" : "no")}</td>
                <td><span className={`badge ${r.priority === "must" ? "red" : r.priority === "should" ? "warn" : "muted"}`}>{r.priority}-have</span></td>
                <td>{r.role}</td><td className="muted">{r.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <Card title="Why not all ~60 reports?">
        <p className="muted">
          The original specification lists roughly 60 reports. Building dead report links with no real
          query behind them would be misleading. Instead, reports are added on the same backend-query +
          drill-down pattern as the implemented seven, and this page tracks the remaining work with
          priority and operational value so the catalogue can be completed deliberately.
        </p>
      </Card>
    </div>
  );
}
