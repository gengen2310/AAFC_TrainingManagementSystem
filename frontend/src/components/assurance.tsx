import { useState, type ReactNode } from "react";

// ── Sortable comparison table (Wing: squadrons; National: wings) ──
export type Column<T> = {
  key: string;
  label: string;
  render?: (row: T) => ReactNode;
  sortVal?: (row: T) => number | string;
  align?: "left" | "right";
};

export function ComparisonTable<T extends { _id: string }>({ columns, rows, onRow, caption }: {
  columns: Column<T>[]; rows: T[]; onRow?: (row: T) => void; caption: string;
}) {
  const [sortKey, setSortKey] = useState<string>(columns[0]?.key ?? "");
  const [dir, setDir] = useState<1 | -1>(1);
  const col = columns.find((c) => c.key === sortKey);
  const sorted = [...rows].sort((a, b) => {
    if (!col?.sortVal) return 0;
    const va = col.sortVal(a), vb = col.sortVal(b);
    if (va < vb) return -1 * dir;
    if (va > vb) return 1 * dir;
    return 0;
  });
  const toggle = (k: string) => { if (k === sortKey) setDir((d) => (d === 1 ? -1 : 1)); else { setSortKey(k); setDir(1); } };
  return (
    <table className="cmp-table">
      <caption className="vis-hidden">{caption}</caption>
      <thead>
        <tr>{columns.map((c) => (
          <th key={c.key} style={{ textAlign: c.align ?? "left", cursor: c.sortVal ? "pointer" : "default" }}
              onClick={() => c.sortVal && toggle(c.key)} aria-sort={sortKey === c.key ? (dir === 1 ? "ascending" : "descending") : undefined}>
            {c.label}{sortKey === c.key ? (dir === 1 ? " ▲" : " ▼") : c.sortVal ? " ⇅" : ""}
          </th>))}
        </tr>
      </thead>
      <tbody>
        {sorted.map((r) => (
          <tr key={r._id} onClick={() => onRow?.(r)} style={{ cursor: onRow ? "pointer" : "default" }}>
            {columns.map((c) => <td key={c.key} style={{ textAlign: c.align ?? "left" }}>{c.render ? c.render(r) : String((r as Record<string, unknown>)[c.key] ?? "—")}</td>)}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ── Ranked horizontal bars (risk ranking, readiness ranking) ──
export function RankBars({ items, max = 100, invert }: {
  items: { id: string; label: string; value: number; sub?: string }[]; max?: number; invert?: boolean;
}) {
  const ranked = [...items].sort((a, b) => (invert ? a.value - b.value : b.value - a.value));
  return (
    <ul className="rank-bars">
      {ranked.map((it) => {
        const pct = Math.max(2, Math.min(100, (it.value / max) * 100));
        const tone = it.value >= max * 0.66 ? (invert ? "ok" : "red") : it.value >= max * 0.33 ? "warn" : (invert ? "red" : "ok");
        return (
          <li key={it.id}>
            <span className="rank-label">{it.label}{it.sub && <em className="muted"> · {it.sub}</em>}</span>
            <span className="rank-track"><span className={`rank-fill ${tone}`} style={{ width: `${pct}%` }} /></span>
            <span className="rank-val">{Math.round(it.value)}</span>
          </li>
        );
      })}
    </ul>
  );
}

// ── Traffic-light readiness panel ──
export function ReadinessPanel({ score }: { score: number | null }) {
  if (score == null) return <span className="badge muted">no plan</span>;
  const tone = score >= 75 ? "ok" : score >= 50 ? "warn" : "red";
  const label = score >= 75 ? "Ready" : score >= 50 ? "At risk" : "Not ready";
  return <span className={`badge ${tone}`} title={`Readiness ${score}/100`}>{label} · {score}</span>;
}

// ── Gap heatmap (wing × subject — sqns with zero facilitator coverage) ──
// Cells are coloured by severity: 0 sqns missing = green, < 34% missing = amber, >= 34% = red.
export function GapHeatmap({ rows, cols, label }: {
  rows: { id: string; label: string; values: Record<string, number>; total_sqns: number; fac_total: number }[];
  cols: { key: string; label: string }[];
  label: string;
}) {
  const tone = (v: number, total: number) => {
    if (total === 0) return "hm-na";
    const pct = (v / total) * 100;
    if (pct === 0) return "hm-ok";
    if (pct < 34) return "hm-warn";
    return "hm-red";
  };
  return (
    <div className="heatmap-wrap" tabIndex={0}>
      <table className="heatmap">
        <caption className="vis-hidden">{label}</caption>
        <thead>
          <tr>
            <th className="hm-corner">Wing</th>
            {cols.map((c) => <th key={c.key}>{c.label}</th>)}
            <th style={{ textAlign: "right" }}>Facs</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <th scope="row" className="hm-rowlabel">{r.label}</th>
              {cols.map((c) => {
                const v = r.values[c.key] ?? 0;
                return (
                  <td key={c.key} className={tone(v, r.total_sqns)}
                    title={v === 0
                      ? `${r.label}: all squadrons have ${c.label} coverage`
                      : `${r.label}: ${v} of ${r.total_sqns} sqns have no ${c.label} facilitator`}>
                    {v === 0 ? "✓" : `${v}/${r.total_sqns}`}
                  </td>
                );
              })}
              <td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{r.fac_total}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Heatmap grid (squadron × phase coverage) ──
// Cells are coloured by coverage %: red (<34) → amber (<67) → green. Real data only.
export function HeatmapGrid({ rows, cols, label }: {
  rows: { id: string; label: string; values: Record<string, number> }[];
  cols: { key: string; label: string }[];
  label: string;
}) {
  const tone = (v: number | undefined) => v == null ? "hm-na" : v >= 67 ? "hm-ok" : v >= 34 ? "hm-warn" : "hm-red";
  return (
    <div className="heatmap-wrap" tabIndex={0}>
      <table className="heatmap">
        <caption className="vis-hidden">{label}</caption>
        <thead>
          <tr><th className="hm-corner">Squadron</th>{cols.map((c) => <th key={c.key} title={c.label}>{c.label.replace(/^[A-Z]\.\s*/, "")}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <th scope="row" className="hm-rowlabel">{r.label}</th>
              {cols.map((c) => {
                const v = r.values[c.key];
                return <td key={c.key} className={tone(v)} title={`${r.label} · ${c.label}: ${v ?? "n/a"}%`}>{v == null ? "—" : v}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
