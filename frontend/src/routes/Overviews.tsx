import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { reportApi } from "../api";
import { Card, Empty, Loading, ErrorNote, Stat, Bar } from "../components/ui";
import { ComparisonTable, RankBars, ReadinessPanel, HeatmapGrid, GapHeatmap, type Column } from "../components/assurance";
import { DrilldownPanel } from "../components/DrilldownPanel";
import type { NationalCapability } from "../api/types";

// Wing-overview row shape (from GET /api/reports/wing-overview).
type SqnRow = {
  _id: string; squadron_id: string; code: string; short_name: string; parade_day: string | null;
  nights: number; published: number; sessions: number; delivered: number; pct: number;
  readiness: number | null; coverage_pct: number; not_delivered: number;
  no_future_plan: boolean; no_published_plan: boolean;
};

// Derived risk index (0-100) from REAL fields only. Labelled as derived so it is not mistaken
// for a backend metric. Higher = needs Wing attention sooner.
function squadronRisk(s: SqnRow): number {
  let r = 0;
  if (s.no_future_plan) r += 30;
  if (s.no_published_plan) r += 15;
  r += (100 - s.pct) * 0.15;                      // weak delivery
  r += (100 - s.coverage_pct) * 0.15;             // weak curriculum coverage
  r += s.not_delivered * 4;                       // not-delivered sessions
  r += s.readiness == null ? 8 : (100 - s.readiness) * 0.15;
  return Math.round(Math.min(100, r));
}

export function WingOverview() {
  const q = useQuery({ queryKey: ["wing-overview"], queryFn: reportApi.wingOverview });
  const heat = useQuery({ queryKey: ["wing-phase-coverage"], queryFn: reportApi.wingPhaseCoverage });
  const cap = useQuery({ queryKey: ["wing-capability"], queryFn: reportApi.wingCapability });
  const [open, setOpen] = useState<SqnRow | null>(null);
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorNote error={q.error} />;
  const rows: SqnRow[] = (q.data?.squadrons ?? []).map((s) => ({ ...s, _id: s.squadron_id }));
  if (rows.length === 0) return <Empty msg="No squadrons in this Wing yet." />;

  const avgReadiness = Math.round(rows.filter((r) => r.readiness != null).reduce((a, r) => a + (r.readiness ?? 0), 0) / Math.max(1, rows.filter((r) => r.readiness != null).length));
  const atRisk = rows.filter((r) => squadronRisk(r) >= 50);
  const missing = rows.filter((r) => r.no_future_plan || r.no_published_plan);
  const totalDelivered = rows.reduce((a, r) => a + r.delivered, 0);
  const totalSessions = rows.reduce((a, r) => a + r.sessions, 0);
  const weakestCov = [...rows].sort((a, b) => a.coverage_pct - b.coverage_pct)[0];
  const mostND = [...rows].sort((a, b) => b.not_delivered - a.not_delivered)[0];

  const columns: Column<SqnRow>[] = [
    { key: "short_name", label: "Squadron", sortVal: (r) => r.short_name, render: (r) => <strong>{r.short_name}</strong> },
    { key: "parade_day", label: "Parade", sortVal: (r) => r.parade_day ?? "" },
    { key: "readiness", label: "Readiness", align: "right", sortVal: (r) => r.readiness ?? -1, render: (r) => <ReadinessPanel score={r.readiness} /> },
    { key: "pct", label: "Delivery", align: "right", sortVal: (r) => r.pct, render: (r) => <span style={{ display: "inline-flex", gap: 6, alignItems: "center" }}><Bar pct={r.pct} /> {r.pct}%</span> },
    { key: "coverage_pct", label: "Coverage", align: "right", sortVal: (r) => r.coverage_pct, render: (r) => <span style={{ display: "inline-flex", gap: 6, alignItems: "center" }}><Bar pct={r.coverage_pct} /> {r.coverage_pct}%</span> },
    { key: "not_delivered", label: "Not del.", align: "right", sortVal: (r) => r.not_delivered, render: (r) => r.not_delivered > 0 ? <span className="badge warn">{r.not_delivered}</span> : "0" },
    { key: "delivered", label: "Del/Sess", align: "right", sortVal: (r) => r.sessions, render: (r) => `${r.delivered}/${r.sessions}` },
    { key: "published", label: "Published", align: "right", sortVal: (r) => r.published },
    { key: "risk", label: "Risk", align: "right", sortVal: (r) => squadronRisk(r), render: (r) => { const v = squadronRisk(r); const t = v >= 50 ? "red" : v >= 25 ? "warn" : "ok"; return <span className={`badge ${t}`}>{v}</span>; } },
    { key: "flags", label: "Data", render: (r) => r.no_future_plan ? <span className="badge red">no future plan</span> : r.no_published_plan ? <span className="badge warn">unpublished</span> : <span className="badge ok">ok</span> },
  ];

  return (
    <div>
      <h1>Wing Assurance</h1>
      <p className="scope-note">Viewing Wing-level assurance data. Unit of analysis: squadron. Editing a squadron requires Proxy Mode with a reason.</p>

      <div className="sg">
        <Stat label="Squadrons" value={rows.length} />
        <Stat label="Avg readiness" value={isNaN(avgReadiness) ? "—" : avgReadiness} hint="of squadrons with a plan" />
        <Stat label="Squadrons at risk" value={atRisk.length} hint="derived risk ≥ 50" />
        <Stat label="Weakest coverage" value={weakestCov ? `${weakestCov.short_name}` : "—"} hint={weakestCov ? `${weakestCov.coverage_pct}% curriculum` : ""} />
        <Stat label="Most not-delivered" value={mostND && mostND.not_delivered > 0 ? mostND.short_name : "—"} hint={mostND && mostND.not_delivered > 0 ? `${mostND.not_delivered} sessions` : "none"} />
        <Stat label="Missing data" value={missing.length} hint="no future / unpublished plan" />
        <Stat label="Wing delivery" value={`${totalSessions ? Math.round(totalDelivered / totalSessions * 100) : 0}%`} hint={`${totalDelivered}/${totalSessions} sessions`} />
      </div>

      <div className="grid-2">
        <Card title="Squadron risk ranking (derived)">
          <RankBars items={rows.map((r) => ({ id: r._id, label: r.short_name, value: squadronRisk(r), sub: r.readiness == null ? "no plan" : `R${r.readiness}` }))} />
        </Card>
        <Card title="Readiness by squadron">
          <RankBars invert items={rows.map((r) => ({ id: r._id, label: r.short_name, value: r.readiness ?? 0, sub: `${r.pct}% delivered` }))} />
        </Card>
      </div>

      {heat.data && heat.data.squadrons.length > 0 && (
        <Card title="Phase coverage heatmap (squadron × phase)">
          <HeatmapGrid
            label="Squadron by phase curriculum coverage"
            cols={heat.data.phases.map((p) => ({ key: p, label: p }))}
            rows={heat.data.squadrons.map((s) => ({ id: s.squadron_id, label: s.short_name, values: s.phase_pct }))}
          />
          <p className="muted" style={{ marginTop: 8 }}>Each cell = % of that phase's curriculum items scheduled. Green ≥ 67, amber ≥ 34, red &lt; 34.</p>
        </Card>
      )}

      {cap.data && cap.data.squadrons.length > 0 && (
        <Card title="Facilitator subject-area coverage (squadron × subject)">
          <HeatmapGrid
            label="Squadron by subject facilitator count"
            cols={cap.data.subjects.map((s) => ({ key: s, label: SUBJECT_LABELS[s] ?? s }))}
            rows={cap.data.squadrons.map((s) => ({ id: s.squadron_id, label: s.short_name, values: s.subject_facilitators }))}
          />
          <p className="muted" style={{ marginTop: 8 }}>Each cell = number of facilitators in that squadron tagged for the subject. 0 = no coverage.</p>
        </Card>
      )}

      {missing.length > 0 && (
        <Card title={`Squadrons needing Wing support (${missing.length})`}>
          <ul className="risk-list">
            {missing.map((r) => <li key={r._id}><strong>{r.short_name}</strong> — {r.no_future_plan ? "no future parade nights planned" : "plan not published"}{r.readiness != null && `; readiness ${r.readiness}`}</li>)}
          </ul>
        </Card>
      )}

      <Card title="Squadron comparison (click a row to drill down)">
        <ComparisonTable columns={columns} rows={rows} caption="Wing squadron comparison" onRow={setOpen} />
      </Card>

      {open && (
        <DrilldownPanel title={`${open.short_name} — summary`} onClose={() => setOpen(null)}>
          <div className="sg">
            <Stat label="Readiness" value={open.readiness ?? "—"} />
            <Stat label="Delivery" value={`${open.pct}%`} hint={`${open.delivered}/${open.sessions}`} />
            <Stat label="Nights" value={open.nights} hint={`${open.published} published`} />
            <Stat label="Risk (derived)" value={squadronRisk(open)} />
          </div>
          <p className="muted">Parade day: {open.parade_day ?? "—"}. {open.no_future_plan ? "No future plan — Wing support recommended." : open.no_published_plan ? "Plan exists but is unpublished." : "On track."}</p>
          <p className="muted">To make changes for this squadron, enter Proxy Mode (a reason is recorded in the audit log).</p>
        </DrilldownPanel>
      )}
    </div>
  );
}

// National-overview row shape (from GET /api/reports/national-overview).
type WingRow = {
  _id: string; wing_id: string; code: string; name: string;
  squadrons: number; sessions: number; delivered: number; not_delivered: number; coverage_pct: number;
};

function wingRisk(w: WingRow): number {
  if (!w.sessions) return 60;
  const ndRate = w.not_delivered / w.sessions;
  const delRate = w.delivered / w.sessions;
  return Math.round(Math.min(100, ndRate * 60 + (1 - delRate) * 40));
}

const SUBJECT_LABELS: Record<string, string> = {
  service: "Sqn Service", drill: "Drill", field: "Field",
  lead: "Leadership", comm: "Community", stem: "STEM/Air",
};

function CapabilityPanel({ data }: { data: NationalCapability }) {
  const { subjects, wings } = data;
  const cols = subjects.map((s) => ({ key: s, label: SUBJECT_LABELS[s] ?? s }));

  // national aggregate: total sqns with zero coverage per subject
  const nationalGaps: Record<string, number> = {};
  for (const s of subjects) {
    nationalGaps[s] = wings.reduce((a, w) => a + (w.subject_none_sqns[s] ?? 0), 0);
  }
  const worstSubj = [...subjects].sort((a, b) => (nationalGaps[b] ?? 0) - (nationalGaps[a] ?? 0))[0];
  const totalFacs = wings.reduce((a, w) => a + w.facilitator_total, 0);
  const totalSqns = wings.reduce((a, w) => a + w.squadrons, 0);
  const wingGapScore = (w: (typeof wings)[0]) =>
    subjects.reduce((a, s) => a + (w.subject_none_sqns[s] ?? 0), 0);
  const worstWing = [...wings].sort((a, b) => wingGapScore(b) - wingGapScore(a))[0];

  const gapRows = wings.map((w) => ({
    id: w.wing_id, label: w.code,
    values: w.subject_none_sqns, total_sqns: w.squadrons, fac_total: w.facilitator_total,
  }));
  const distRows = wings.map((w) => ({
    id: w.wing_id, label: w.code,
    values: w.subject_distribution,
  }));

  return (
    <>
      <div className="sg">
        <Stat label="Total facilitators" value={totalFacs} hint={`across ${totalSqns} squadrons`} />
        <Stat label="Worst-covered subject" value={SUBJECT_LABELS[worstSubj] ?? worstSubj}
          hint={`${nationalGaps[worstSubj] ?? 0} sqns nationally with no coverage`} />
        <Stat label="Wing most at-risk" value={worstWing?.code ?? "—"}
          hint={worstWing ? `${wingGapScore(worstWing)} total gap-sqns` : ""} />
      </div>

      <Card title="Facilitator coverage gaps (sqns with no tagged facilitator per subject)">
        <GapHeatmap rows={gapRows} cols={cols} label="Wing × subject coverage gaps" />
        <p className="muted" style={{ marginTop: 8 }}>
          ✓ = all squadrons in that wing have at least one facilitator tagged for the subject.
          Numbers show how many squadrons have zero coverage.
          Green = fully covered · amber = &lt;34% missing · red = ≥34% missing.
        </p>
      </Card>

      <Card title="Session subject distribution by wing (%)">
        <HeatmapGrid
          label="Wing × subject session distribution"
          cols={cols}
          rows={distRows}
        />
        <p className="muted" style={{ marginTop: 8 }}>
          % of all sessions in that wing that fall in each subject category (based on session element tags).
          0% indicates no sessions have been recorded in that subject.
        </p>
      </Card>
    </>
  );
}

export function NationalOverview() {
  const [view, setView] = useState<"delivery" | "capability">("delivery");
  const q = useQuery({ queryKey: ["national-overview"], queryFn: reportApi.nationalOverview });
  const capQ = useQuery({
    queryKey: ["national-capability"],
    queryFn: reportApi.nationalCapability,
    enabled: view === "capability",
  });
  const [open, setOpen] = useState<WingRow | null>(null);

  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorNote error={q.error} />;
  const rows: WingRow[] = (q.data?.wings ?? []).map((w) => ({ ...w, _id: w.wing_id }));
  if (rows.length === 0) return <Empty msg="No wings yet." />;

  const totalSqn = rows.reduce((a, w) => a + w.squadrons, 0);
  const totalSess = rows.reduce((a, w) => a + w.sessions, 0);
  const totalDel = rows.reduce((a, w) => a + w.delivered, 0);
  const totalND = rows.reduce((a, w) => a + w.not_delivered, 0);

  const columns: Column<WingRow>[] = [
    { key: "code", label: "Wing", sortVal: (r) => r.code, render: (r) => <span><strong>{r.code}</strong> {r.name}</span> },
    { key: "squadrons", label: "Squadrons", align: "right", sortVal: (r) => r.squadrons },
    { key: "sessions", label: "Sessions", align: "right", sortVal: (r) => r.sessions },
    { key: "delivered", label: "Delivery", align: "right", sortVal: (r) => r.sessions ? r.delivered / r.sessions : 0, render: (r) => { const p = r.sessions ? Math.round(r.delivered / r.sessions * 100) : 0; return <span style={{ display: "inline-flex", gap: 6, alignItems: "center" }}><Bar pct={p} /> {p}%</span>; } },
    { key: "coverage_pct", label: "Coverage", align: "right", sortVal: (r) => r.coverage_pct, render: (r) => <span style={{ display: "inline-flex", gap: 6, alignItems: "center" }}><Bar pct={r.coverage_pct} /> {r.coverage_pct}%</span> },
    { key: "not_delivered", label: "Not delivered", align: "right", sortVal: (r) => r.not_delivered, render: (r) => r.not_delivered > 0 ? <span className="badge warn">{r.not_delivered}</span> : "0" },
    { key: "risk", label: "Risk", align: "right", sortVal: (r) => wingRisk(r), render: (r) => { const v = wingRisk(r); const t = v >= 50 ? "red" : v >= 25 ? "warn" : "ok"; return <span className={`badge ${t}`}>{v}</span>; } },
  ];

  return (
    <div>
      <h1>National Assurance</h1>
      <p className="scope-note">Viewing National-level assurance data. Unit of analysis: wing. Editing a squadron requires Delegated Intervention with a reason.</p>

      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <button className={view === "delivery" ? "btn" : "btn out"} onClick={() => setView("delivery")}>Delivery</button>
        <button className={view === "capability" ? "btn" : "btn out"} onClick={() => setView("capability")}>Capability</button>
      </div>

      {view === "delivery" && (
        <>
          <div className="sg">
            <Stat label="Wings" value={rows.length} />
            <Stat label="Squadrons" value={totalSqn} />
            <Stat label="National delivery" value={`${totalSess ? Math.round(totalDel / totalSess * 100) : 0}%`} hint={`${totalDel}/${totalSess}`} />
            <Stat label="Lowest coverage" value={[...rows].sort((a, b) => a.coverage_pct - b.coverage_pct)[0]?.code ?? "—"} hint={`${[...rows].sort((a, b) => a.coverage_pct - b.coverage_pct)[0]?.coverage_pct ?? 0}% curriculum`} />
            <Stat label="Not delivered" value={totalND} hint="across all wings" />
          </div>

          <div className="grid-2">
            <Card title="Wing risk ranking (derived)">
              <RankBars items={rows.map((w) => ({ id: w._id, label: w.code, value: wingRisk(w), sub: `${w.squadrons} sqn` }))} />
            </Card>
            <Card title="Delivery by wing">
              <RankBars invert items={rows.map((w) => ({ id: w._id, label: w.code, value: w.sessions ? Math.round(w.delivered / w.sessions * 100) : 0, sub: `${w.not_delivered} ND` }))} />
            </Card>
          </div>

          <Card title="Wing comparison (click a row to drill down)">
            <ComparisonTable columns={columns} rows={rows} caption="National wing comparison" onRow={setOpen} />
          </Card>
        </>
      )}

      {view === "capability" && (
        <>
          {capQ.isLoading && <Loading />}
          {capQ.error && <ErrorNote error={capQ.error} />}
          {capQ.data && <CapabilityPanel data={capQ.data} />}
        </>
      )}

      {open && view === "delivery" && (
        <DrilldownPanel title={`${open.code} ${open.name} — summary`} onClose={() => setOpen(null)}>
          <div className="sg">
            <Stat label="Squadrons" value={open.squadrons} />
            <Stat label="Sessions" value={open.sessions} />
            <Stat label="Delivered" value={open.delivered} hint={`${open.sessions ? Math.round(open.delivered / open.sessions * 100) : 0}%`} />
            <Stat label="Not delivered" value={open.not_delivered} />
          </div>
          <p className="muted">Drill into this wing's squadrons via the Wing Assurance view (proxy/intervention required to edit).</p>
        </DrilldownPanel>
      )}
    </div>
  );
}
