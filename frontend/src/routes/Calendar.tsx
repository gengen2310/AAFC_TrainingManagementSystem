import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { trainingApi } from "../api";
import { Card, Empty, Loading, ErrorNote } from "../components/ui";
import { StatusBadge } from "../components/status/StatusBadge";
import { Modal } from "../components/Modal";
import { ParadeNightDetailView } from "./ParadeNightDetail";
import { useAuth } from "../auth/AuthProvider";
import { canWriteSquadron } from "../auth/permissions";

// Calendar = parade nights grouped by month, with session-status chips. Click to open detail.
export function Calendar() {
  const { session } = useAuth();
  const q = useQuery({ queryKey: ["parade-nights"], queryFn: () => trainingApi.paradeNights() });
  const [openId, setOpenId] = useState<string | null>(null);
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorNote error={q.error} />;

  const byMonth: Record<string, typeof q.data> = {};
  for (const p of q.data ?? []) {
    const m = (p.date || "").slice(0, 7) || "Undated";
    (byMonth[m] ||= []).push(p);
  }
  const months = Object.keys(byMonth).sort();

  return (
    <div>
      <h1>Calendar</h1>
      {months.length === 0 ? <Empty msg="No parade nights to display." /> : months.map((m) => (
        <Card key={m} title={m}>
          <div className="cal-grid">
            {byMonth[m]!.map((p) => (
              <button key={p.parade_night_id} className="cal-cell" onClick={() => setOpenId(p.parade_night_id)}>
                <div className="cal-date">{p.date}</div>
                <StatusBadge status={p.published_status ? "published" : "draft"} />
                <div className="cal-sessions">{p.sessions.length} session{p.sessions.length === 1 ? "" : "s"}</div>
                <div className="cal-chips">{p.sessions.slice(0, 4).map((s) => <span key={s.id} className={`chip chip-${s.status}`} title={s.status}>{s.period_number}</span>)}</div>
              </button>))}
          </div>
        </Card>
      ))}
      {openId && <Modal title="Parade night" onClose={() => setOpenId(null)}><ParadeNightDetailView id={openId} canWrite={canWriteSquadron(session)} /></Modal>}
    </div>
  );
}
