import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { trainingApi } from "../api";
import { Empty, Loading, ErrorNote, Button } from "../components/ui";
import { StatusBadge } from "../components/status/StatusBadge";
import { ApiError } from "../api/client";
import type { SessionRow } from "../api/types";

// Detail of one parade night: sessions, publish/close (backend-validated), add session, set status.
export function ParadeNightDetailView({ id, canWrite }: { id: string; canWrite: boolean }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["parade-night", id], queryFn: () => trainingApi.paradeNight(id) });
  const [actionErr, setActionErr] = useState("");
  const [addOpen, setAddOpen] = useState(false);
  const [statusFor, setStatusFor] = useState<SessionRow | null>(null);

  const refetch = () => { qc.invalidateQueries({ queryKey: ["parade-night", id] }); qc.invalidateQueries({ queryKey: ["parade-nights"] }); };
  const publish = useMutation({ mutationFn: () => trainingApi.publish(id), onSuccess: () => { setActionErr(""); refetch(); }, onError: (e) => setActionErr(e instanceof ApiError ? e.friendly : "Publish failed.") });
  const close = useMutation({ mutationFn: () => trainingApi.close(id), onSuccess: () => { setActionErr(""); refetch(); }, onError: (e) => setActionErr(e instanceof ApiError ? e.friendly : "Close failed.") });
  const [bulkMsg, setBulkMsg] = useState("");
  const markRemainingDelivered = useMutation({
    mutationFn: () => trainingApi.markRemainingDelivered(id),
    onSuccess: (r) => { setActionErr(""); setBulkMsg(r.sessions_updated > 0 ? `${r.sessions_updated} session${r.sessions_updated !== 1 ? "s" : ""} marked delivered.` : "No remaining sessions to mark -- everything already has a status."); refetch(); },
    onError: (e) => setActionErr(e instanceof ApiError ? e.friendly : "Bulk update failed."),
  });

  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorNote error={q.error} />;
  const pn = q.data!;

  return (
    <div>
      <p><strong>{pn.date}</strong> · Term {pn.term ?? "—"} · {pn.start_time}–{pn.end_time} · <StatusBadge status={pn.published_status ? "published" : "draft"} /></p>
      <p className="muted">Readiness {pn.readiness.score} ({pn.readiness.band})</p>
      {pn.publish_blockers.length > 0 && (
        <div className="errnote" role="alert">Publish blockers: {pn.publish_blockers.join("; ")}</div>
      )}
      {actionErr && <div className="errnote" role="alert">{actionErr}</div>}
      {bulkMsg && <p className="muted" style={{ fontSize: 12 }}>{bulkMsg}</p>}

      <table>
        <caption className="vis-hidden">Sessions for this parade night</caption>
        <thead><tr><th>#</th><th>Phase</th><th>Item</th><th>Facilitator</th><th>Status</th>{canWrite && <th></th>}</tr></thead>
        <tbody>
          {pn.sessions.length === 0 ? <tr><td colSpan={canWrite ? 6 : 5}><Empty msg="No sessions yet." /></td></tr> :
            pn.sessions.sort((a, b) => a.period_number - b.period_number).map((s) => (
              <tr key={s.id}>
                <td>{s.period_number}</td><td>{s.phase_at_time ?? "—"}</td>
                <td>{s.curriculum_title_at_time ?? s.custom_title ?? "—"}</td>
                <td>{s.facilitator_display_name_at_time ?? "—"}</td>
                <td><StatusBadge status={s.status} /></td>
                {canWrite && <td><button className="btn out sm" onClick={() => setStatusFor(s)}>Set status</button></td>}
              </tr>))}
        </tbody>
      </table>

      {canWrite && (
        <div className="row-actions">
          <Button variant="out" onClick={() => setAddOpen(true)}>Add session</Button>
          <Button
            variant="out"
            onClick={() => { setBulkMsg(""); markRemainingDelivered.mutate(); }}
            disabled={markRemainingDelivered.isPending || pn.sessions.length === 0}
            title="Marks every session still Draft/Planned/Published as Delivered. Flag any exceptions (cancelled, not delivered, rescheduled) individually first -- this only fills in the rest."
          >
            {markRemainingDelivered.isPending ? "Marking…" : "Mark remaining delivered"}
          </Button>
          <Button onClick={() => publish.mutate()} disabled={publish.isPending}>Publish</Button>
          <Button variant="out" onClick={() => close.mutate()} disabled={close.isPending}>Close out</Button>
        </div>
      )}

      {addOpen && <AddSessionForm pnid={id} onClose={() => setAddOpen(false)} onDone={() => { setAddOpen(false); refetch(); }} />}
      {statusFor && <SetStatusForm session={statusFor} onClose={() => setStatusFor(null)} onDone={() => { setStatusFor(null); refetch(); }} />}
    </div>
  );
}

function AddSessionForm({ pnid, onClose, onDone }: { pnid: string; onClose: () => void; onDone: () => void }) {
  const cur = useQuery({ queryKey: ["curriculum"], queryFn: () => trainingApi.curriculum() });
  const facs = useQuery({ queryKey: ["facilitators"], queryFn: () => trainingApi.facilitators() });
  const [period, setPeriod] = useState("1");
  const [item, setItem] = useState("");
  const [fac, setFac] = useState("");
  const [err, setErr] = useState("");
  const m = useMutation({
    mutationFn: () => trainingApi.createSession({ parade_night_id: pnid, period_number: Number(period),
      curriculum_item_id: item || null, facilitator_id: fac || null }),
    onSuccess: onDone, onError: (e) => setErr(e instanceof ApiError ? e.friendly : "Could not add session."),
  });
  return (
    <div className="inline-form">
      <h3>Add session</h3>
      <label htmlFor="s-period">Period</label>
      <input id="s-period" type="number" min={1} max={6} value={period} onChange={(e) => setPeriod(e.target.value)} />
      <label htmlFor="s-item">Curriculum item</label>
      <select id="s-item" value={item} onChange={(e) => setItem(e.target.value)}>
        <option value="">Custom / none</option>
        {(cur.data?.items ?? []).map((i) => <option key={i.curriculum_id} value={i.curriculum_id}>{i.code} — {i.title}</option>)}
      </select>
      <label htmlFor="s-fac">Facilitator</label>
      <select id="s-fac" value={fac} onChange={(e) => setFac(e.target.value)}>
        <option value="">Unassigned</option>
        {(facs.data ?? []).map((f) => <option key={f.facilitator_id} value={f.facilitator_id}>{f.current_rank} {f.first_name} {f.last_name}</option>)}
      </select>
      {err && <div className="err" role="alert">{err}</div>}
      <div className="row-actions"><Button onClick={() => m.mutate()} disabled={m.isPending}>Add</Button><Button variant="out" onClick={onClose}>Cancel</Button></div>
    </div>
  );
}

// Matches backend/app/routers/training.py's REASON_REQUIRED_STATUSES — a status
// change to any of these must carry a non-empty reason or the server rejects it.
const REASON_REQUIRED_STATUSES = new Set(["not_delivered", "cancelled", "cancelled_late", "delivered_with_issue"]);

// Structured reason choices, matching connected-frontend's equivalent outcome panel
// (see connected-frontend/index.html's #m-outcome-reason) — kept identical across
// both frontends so the same operational vocabulary is used everywhere.
const OUTCOME_REASONS = [
  "Facilitator unavailable", "Venue unavailable", "Equipment unavailable", "Weather",
  "Higher-priority activity", "Program changed", "Insufficient time", "Safety concern", "Other",
];

function SetStatusForm({ session, onClose, onDone }: { session: SessionRow; onClose: () => void; onDone: () => void }) {
  const [status, setStatus] = useState("delivered");
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [resched, setResched] = useState("");
  const [att, setAtt] = useState("");
  const [err, setErr] = useState("");
  const needsReason = REASON_REQUIRED_STATUSES.has(status);
  const fullReason = reason ? (note.trim() ? `${reason} — ${note.trim()}` : reason) : "";
  const m = useMutation({
    mutationFn: () => trainingApi.setStatus(session.id, { status, reason: fullReason || undefined,
      rescheduled_to_date: resched || undefined, actual_attendance: att ? Number(att) : undefined }),
    onSuccess: onDone, onError: (e) => setErr(e instanceof ApiError ? e.friendly : "Could not set status."),
  });
  return (
    <div className="inline-form">
      <h3>Set session status</h3>
      <label htmlFor="st-status">Status</label>
      <select id="st-status" value={status} onChange={(e) => setStatus(e.target.value)}>
        {["delivered", "delivered_with_issue", "not_delivered", "cancelled", "cancelled_late", "rescheduled", "planned"].map((s) =>
          <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
      </select>
      {needsReason && (<>
        <label htmlFor="st-reason">Reason (required)</label>
        <select id="st-reason" value={reason} onChange={(e) => setReason(e.target.value)} aria-required="true">
          <option value="">— Select a reason —</option>
          {OUTCOME_REASONS.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
        <label htmlFor="st-note">Additional notes (optional)</label>
        <input id="st-note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Any further detail…" />
      </>)}
      {status === "rescheduled" && (<><label htmlFor="st-res">Rescheduled to</label>
        <input id="st-res" type="date" value={resched} onChange={(e) => setResched(e.target.value)} /></>)}
      {(status === "delivered" || status === "delivered_with_issue") && (<><label htmlFor="st-att">Actual attendance</label>
        <input id="st-att" type="number" min={0} value={att} onChange={(e) => setAtt(e.target.value)} /></>)}
      {err && <div className="err" role="alert">{err}</div>}
      <div className="row-actions">
        <Button onClick={() => m.mutate()} disabled={m.isPending || (needsReason && !reason)}>Save status</Button>
        <Button variant="out" onClick={onClose}>Cancel</Button>
      </div>
    </div>
  );
}
