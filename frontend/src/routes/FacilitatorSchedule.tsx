import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { dashboardApi } from "../api";
import { Card, Empty, Loading, ErrorNote } from "../components/ui";
import { FacilitatorTimeline, type ZoomPreset } from "../components/charts/FacilitatorTimeline";
import { FacilitatorScheduleList } from "../components/charts/FacilitatorScheduleList";
import { useScopedSquadron } from "../layout/SquadronViewContext";

type View = "timeline" | "list";

// Facilitator Schedule Explorer (master transformation plan Block 9): who's
// available/working/on leave, what they're delivering, when — a grouped
// timeline with zoom presets, plus a mandatory accessible list view (see
// FacilitatorScheduleList.tsx). Squadron-scoped via the same useScopedSquadron
// pattern as every other squadron page introduced in Block 8, so Wing/National
// viewers reach this page through the same squadron selector, no proxy needed.
export function FacilitatorSchedule() {
  const { needsSelection, squadronId, scoped } = useScopedSquadron();
  const [zoom, setZoom] = useState<ZoomPreset>("term");
  const [view, setView] = useState<View>("timeline");
  const [subjectFilter, setSubjectFilter] = useState("");
  const [facFilter, setFacFilter] = useState("");

  const q = useQuery({
    queryKey: ["facilitator-schedule", zoom, squadronId],
    queryFn: () => dashboardApi.facilitatorSchedule(zoom === "week" ? "week" : "year", squadronId),
    enabled: scoped,
    staleTime: 2 * 60 * 1000,
  });

  const subjectAreas = useMemo(() => {
    const set = new Set<string>();
    (q.data?.facilitators ?? []).forEach((f) => f.subject_areas.forEach((s) => set.add(s)));
    return [...set].sort();
  }, [q.data]);

  const filteredFacilitators = (q.data?.facilitators ?? []).filter(
    (f) => (!subjectFilter || f.subject_areas.includes(subjectFilter)) && (!facFilter || f.facilitator_id === facFilter)
  );
  const filteredIds = new Set(filteredFacilitators.map((f) => f.facilitator_id));
  const filteredItems = (q.data?.items ?? []).filter((i) => filteredIds.has(i.facilitator_id));

  if (needsSelection && !squadronId) {
    return (
      <div>
        <h1>Facilitator Schedule</h1>
        <Empty msg="Select a squadron above to view its facilitator schedule." />
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: 8 }}>
        <h1>Facilitator Schedule</h1>
        <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          <label style={{ fontSize: 12, display: "flex", alignItems: "center", gap: 6 }}>
            Zoom
            <select value={zoom} onChange={(e) => setZoom(e.target.value as ZoomPreset)} style={{ fontSize: 12, padding: "4px 6px" }}>
              <option value="week">Week</option>
              <option value="month">Month</option>
              <option value="term">Term</option>
              <option value="year">Year</option>
            </select>
          </label>
          <div role="group" aria-label="View">
            <button
              type="button"
              className={`btn sm ${view === "timeline" ? "" : "out"}`}
              aria-pressed={view === "timeline"}
              onClick={() => setView("timeline")}
            >
              Timeline
            </button>{" "}
            <button
              type="button"
              className={`btn sm ${view === "list" ? "" : "out"}`}
              aria-pressed={view === "list"}
              onClick={() => setView("list")}
            >
              List (accessible)
            </button>
          </div>
        </div>
      </div>

      <Card title="Filters">
        <div className="filter-bar">
          <select value={subjectFilter} onChange={(e) => setSubjectFilter(e.target.value)} aria-label="Subject area">
            <option value="">All subject areas</option>
            {subjectAreas.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <select value={facFilter} onChange={(e) => setFacFilter(e.target.value)} aria-label="Facilitator">
            <option value="">All facilitators</option>
            {(q.data?.facilitators ?? []).map((f) => (
              <option key={f.facilitator_id} value={f.facilitator_id}>{f.name}</option>
            ))}
          </select>
        </div>
      </Card>

      {q.isLoading ? (
        <Loading />
      ) : q.error ? (
        <ErrorNote error={q.error} />
      ) : (
        <Card>
          {view === "timeline" ? (
            <FacilitatorTimeline facilitators={filteredFacilitators} items={filteredItems} zoomPreset={zoom} />
          ) : (
            <FacilitatorScheduleList facilitators={filteredFacilitators} items={filteredItems} />
          )}
        </Card>
      )}
    </div>
  );
}
