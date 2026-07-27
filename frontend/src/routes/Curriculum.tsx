import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { trainingApi } from "../api";
import { Card, Empty, Loading, ErrorNote } from "../components/ui";
import { StatusBadge } from "../components/status/StatusBadge";
import { DrilldownPanel } from "../components/DrilldownPanel";
import { useScopedSquadron } from "../layout/SquadronViewContext";
import type { CurriculumItem } from "../api/types";

export function Curriculum() {
  const { needsSelection, squadronId, scoped } = useScopedSquadron();
  const q = useQuery({ queryKey: ["curriculum", squadronId], queryFn: () => trainingApi.curriculum(squadronId), enabled: scoped });
  const [phase, setPhase] = useState(""); const [element, setElement] = useState("");
  const [progress, setProgress] = useState(""); const [search, setSearch] = useState("");
  // TRGO-04 (React-app parity): connected-frontend already has a "Missing Learning
  // Hub link" filter (index.html curr-f-nolh checkbox) -- the React Curriculum page
  // had no equivalent, even though the underlying learning_hub_url field is the
  // same data on both frontends.
  const [noLearningHub, setNoLearningHub] = useState(false);
  const [drill, setDrill] = useState<CurriculumItem | null>(null);

  const items = q.data?.items ?? [];
  const phases = useMemo(() => [...new Set(items.map((i) => i.phase))].sort(), [items]);
  const elements = useMemo(() => [...new Set(items.map((i) => i.element).filter(Boolean))].sort(), [items]);
  const filtered = items.filter((i) =>
    (!phase || i.phase === phase) && (!element || i.element === element) &&
    (!progress || i.progress === progress) &&
    (!noLearningHub || !i.learning_hub_url) &&
    (!search || `${i.code} ${i.title}`.toLowerCase().includes(search.toLowerCase())));

  if (needsSelection && !squadronId) return <div><h1>Curriculum</h1><Empty msg="Select a squadron above to view its curriculum." /></div>;
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorNote error={q.error} />;

  // group by phase
  const groups: Record<string, CurriculumItem[]> = {};
  for (const i of filtered) (groups[i.phase] ||= []).push(i);

  return (
    <div>
      <h1>Curriculum</h1>
      <Card title="Filters">
        <div className="filter-bar">
          <select value={phase} onChange={(e) => setPhase(e.target.value)} aria-label="Phase"><option value="">All phases</option>{phases.map((p) => <option key={p}>{p}</option>)}</select>
          <select value={element} onChange={(e) => setElement(e.target.value)} aria-label="Element"><option value="">All elements</option>{elements.map((e) => <option key={e}>{e}</option>)}</select>
          <select value={progress} onChange={(e) => setProgress(e.target.value)} aria-label="Progress"><option value="">Any progress</option>{["not_started", "in_progress", "complete"].map((p) => <option key={p} value={p}>{p.replace(/_/g, " ")}</option>)}</select>
          <input placeholder="Search code or title" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Search curriculum" />
          <label style={{ display: "flex", gap: 6, alignItems: "center", fontWeight: 400 }}>
            <input type="checkbox" checked={noLearningHub} onChange={(e) => setNoLearningHub(e.target.checked)} />
            Missing Learning Hub link
          </label>
        </div>
      </Card>
      {Object.keys(groups).length === 0 ? <Empty msg="No curriculum items match." /> : Object.entries(groups).map(([ph, list]) => (
        <Card key={ph} title={ph}>
          <table>
            <caption className="vis-hidden">{ph} curriculum items</caption>
            <thead><tr><th>Code</th><th>Title</th><th>Element</th><th>Duration</th><th>Sessions</th><th>Progress</th><th>Learning Hub</th></tr></thead>
            <tbody>{list.map((i) => (
              <tr key={i.curriculum_id}>
                <td><button className="link-btn" onClick={() => setDrill(i)}>{i.code}</button></td>
                <td>{i.title}</td><td>{i.element}</td><td>{i.duration_minutes}m</td><td>{i.session_count}</td>
                <td><StatusBadge status={i.progress === "complete" ? "delivered" : i.progress === "in_progress" ? "planned" : "draft"} /></td>
                <td>{i.learning_hub_url ? <a className="lh" href={i.learning_hub_url} target="_blank" rel="noopener">↗ open</a> : <span className="muted">—</span>}</td>
              </tr>))}</tbody>
          </table>
        </Card>
      ))}
      {drill && <CurriculumDrill item={drill} onClose={() => setDrill(null)} />}
    </div>
  );
}

function CurriculumDrill({ item, onClose }: { item: CurriculumItem; onClose: () => void }) {
  const q = useQuery({ queryKey: ["cur-sessions", item.curriculum_id], queryFn: () => trainingApi.curriculumSessions(item.curriculum_id) });
  return (
    <DrilldownPanel title={`${item.code} — sessions`} onClose={onClose}>
      {item.learning_hub_url && <p><a className="lh" href={item.learning_hub_url} target="_blank" rel="noopener">↗ Learning Hub resource</a></p>}
      {q.isLoading ? <Loading /> : ((q.data ?? []).length ? (
        <table><thead><tr><th>Date item</th><th>Status</th></tr></thead>
          <tbody>{q.data!.map((s) => <tr key={s.id}><td>{s.curriculum_title_at_time ?? s.custom_title ?? "—"}</td><td><StatusBadge status={s.status} /></td></tr>)}</tbody></table>
      ) : <Empty msg="No sessions scheduled for this item yet." />)}
    </DrilldownPanel>
  );
}
