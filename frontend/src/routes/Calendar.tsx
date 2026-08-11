import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { trainingApi } from "../api";
import { Card, Empty, Loading, ErrorNote } from "../components/ui";
import { StatusBadge, statusLabel } from "../components/status/StatusBadge";
import { Modal } from "../components/Modal";
import { ParadeNightDetailView } from "./ParadeNightDetail";
import { useAuth } from "../auth/AuthProvider";
import { canWriteSquadron } from "../auth/permissions";
import { useScopedSquadron } from "../layout/SquadronViewContext";

// Calendar = parade nights grouped by month, with session-status chips. Click to open detail.
export function Calendar() {
  const { session } = useAuth();
  const { needsSelection, squadronId, scoped } = useScopedSquadron();
  const q = useQuery({ queryKey: ["parade-nights", squadronId], queryFn: () => trainingApi.paradeNights(squadronId), enabled: scoped });
  const [openId, setOpenId] = useState<string | null>(null);
  if (needsSelection && !squadronId) return <div><h1>Calendar</h1><Empty msg="Select a squadron above to view its calendar." /></div>;
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorNote error={q.error} />;

  const byMonth: Record<string, typeof q.data> = {};
  for (const p of q.data ?? []) {
    const m = (p.date || "").slice(0, 7) || "Undated";
    (byMonth[m] ||= []).push(p);
  }
  const months = Object.keys(byMonth).sort();
  const monthLabel = (m: string) =>
    m === "Undated" ? m : new Date(`${m}-01T00:00:00`).toLocaleDateString("en-AU", { month: "long", year: "numeric" });

  return (
    <div>
      <h1>Calendar</h1>
      {months.length === 0 ? <Empty msg="No parade nights to display." /> : months.map((m) => (
        <Card key={m} title={monthLabel(m)}>
          <div className="cal-grid">
            {byMonth[m]!.map((p) => (
              <button key={p.parade_night_id} className="cal-cell" onClick={() => setOpenId(p.parade_night_id)}>
                <div className="cal-date">{p.date}</div>
                <StatusBadge status={p.published_status ? "published" : "draft"} />
                <div className="cal-sessions">{p.sessions.length} session{p.sessions.length === 1 ? "" : "s"}</div>
                <div className="cal-chips">{p.sessions.slice(0, 4).map((s) => <span key={s.id} className={`chip chip-${s.status}`} title={statusLabel(s.status)}>{s.period_number}</span>)}</div>
              </button>))}
          </div>
        </Card>
      ))}
      {openId && <Modal title="Parade night" onClose={() => setOpenId(null)}><ParadeNightDetailView id={openId} canWrite={canWriteSquadron(session)} /></Modal>}
    </div>
  );
}
