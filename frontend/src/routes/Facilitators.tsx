import { useState, useRef, type KeyboardEvent, type ChangeEvent } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { trainingApi, reportApi } from "../api";
import { useToast } from "../components/Toast";
import { Card, Empty, Loading, ErrorNote, Button } from "../components/ui";
import { Modal } from "../components/Modal";
import { DrilldownPanel } from "../components/DrilldownPanel";
import { DecisionBadge } from "../components/status/StatusBadge";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthProvider";
import { canWriteSquadron } from "../auth/permissions";
import { useScopedSquadron } from "../layout/SquadronViewContext";
import { ImportFacilitatorsModal } from "../components/planning/ImportFacilitatorsModal";
import type { Facilitator } from "../api/types";

const RISK_LABEL: Record<string, string> = { ok: "OK", high: "High", overloaded: "Overloaded" };

export function Facilitators() {
  const { session } = useAuth();
  const qc = useQueryClient();
  const { needsSelection, squadronId, scoped } = useScopedSquadron();
  const q = useQuery({ queryKey: ["facilitators", squadronId], queryFn: () => trainingApi.facilitators(squadronId), enabled: scoped });
  const load = useQuery({ queryKey: ["fac-load", squadronId], queryFn: () => reportApi.facLoad(squadronId), enabled: scoped });
  const [adding, setAdding] = useState(false);
  const [importing, setImporting] = useState(false);
  const [tagsFor, setTagsFor] = useState<Facilitator | null>(null);
  const [editFor, setEditFor] = useState<Facilitator | null>(null);
  const [statsId, setStatsId] = useState<string | null>(null);
  const canWrite = canWriteSquadron(session);
  const { toast } = useToast();
  const archiveMut = useMutation({
    mutationFn: (id: string) => trainingApi.deleteFacilitator(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["facilitators"] }); toast("Facilitator archived."); },
  });
  if (needsSelection && !squadronId) return <Empty msg="Select a squadron above to view its facilitators." />;
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorNote error={q.error} />;
  return (
    <div>
      <h1>Facilitators</h1>
      <Card action={canWrite && (
        <div style={{ display: "flex", gap: 6 }}>
          <Button onClick={() => setImporting(true)} variant="out">Import CSV</Button>
          <Button onClick={() => setAdding(true)}>Add facilitator</Button>
        </div>
      )}>
        {(q.data ?? []).length === 0 ? <Empty msg="No facilitators yet." /> : (
          <table>
            <caption className="vis-hidden">Facilitators</caption>
            <thead><tr><th>Rank</th><th>Name</th><th>Type</th><th>Subjects</th><th></th></tr></thead>
            <tbody>{(q.data ?? []).map((f) => (
              <tr key={f.facilitator_id}>
                <td>{f.current_rank ?? "—"}</td>
                <td>{f.first_name} {f.last_name}</td>
                <td>{f.type}</td>
                <td>
                  {f.subject_areas.length > 0
                    ? <span className="tag-chip-list">{f.subject_areas.map((s) => <span key={s} className="tag-chip" style={{ marginRight: 3 }}>{s}</span>)}</span>
                    : "—"}
                </td>
                <td style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {canWrite && (
                    <>
                      <button className="btn out sm" onClick={() => setEditFor(f)}>Edit</button>
                      <button className="btn out sm" onClick={() => setTagsFor(f)}>Tags</button>
                      <button className="btn out sm danger" onClick={() => {
                        if (window.confirm(`Archive ${f.first_name} ${f.last_name}? This can be reversed from the connected TMS.`)) {
                          archiveMut.mutate(f.facilitator_id);
                        }
                      }}>Archive</button>
                    </>
                  )}
                  <button className="btn out sm" onClick={() => setStatsId(f.facilitator_id)}>Stats</button>
                </td>
              </tr>))}</tbody>
          </table>
        )}
        <p className="muted">Rank is shown point-in-time on historical sessions; updating a facilitator does not rewrite past session rank.</p>
      </Card>

      <Card title="Delivery statistics" action={load.data && <DecisionBadge decision={load.data.decision} />}>
        {load.isLoading ? <Loading /> : load.error ? <ErrorNote error={load.error} /> :
          (load.data!.facilitators.length === 0 ? <Empty msg="No session data yet." /> : (
            <table>
              <caption className="vis-hidden">Facilitator delivery statistics</caption>
              <thead><tr><th>Facilitator</th><th>Sessions</th><th>Delivered</th><th>Load risk</th></tr></thead>
              <tbody>{load.data!.facilitators.map((f) => (
                <tr key={f.name}>
                  <td>{f.name}</td>
                  <td>{f.sessions}</td>
                  <td>{f.delivered}</td>
                  <td><span className={`badge ${f.risk === "ok" ? "ok" : f.risk === "high" ? "warn" : "red"}`}>{RISK_LABEL[f.risk] ?? f.risk}</span></td>
                </tr>
              ))}</tbody>
            </table>
          ))}
      </Card>

      {adding && <AddFacModal onClose={() => setAdding(false)} onDone={() => { setAdding(false); qc.invalidateQueries({ queryKey: ["facilitators"] }); }} />}
      {importing && <ImportFacilitatorsModal onClose={() => setImporting(false)} onDone={() => { setImporting(false); qc.invalidateQueries({ queryKey: ["facilitators"] }); }} />}
      {tagsFor && <TagsModal fac={tagsFor} onClose={() => setTagsFor(null)} onDone={() => { setTagsFor(null); qc.invalidateQueries({ queryKey: ["facilitators"] }); }} />}
      {editFor && <EditFacModal fac={editFor} onClose={() => setEditFor(null)} onDone={() => { setEditFor(null); qc.invalidateQueries({ queryKey: ["facilitators"] }); }} />}
      {statsId && <FacStats id={statsId} onClose={() => setStatsId(null)} />}
    </div>
  );
}

// ── Tag chip input ─────────────────────────────────────────────────────────────
// Press Enter, Tab, or comma to add a tag. Backspace on empty input removes last tag.
const MAX_TAGS = 20;
const MAX_LEN = 80;

function TagInput({ tags, onChange, id, placeholder = "Type and press Enter or , to add…" }: {
  tags: string[];
  onChange: (tags: string[]) => void;
  id?: string;
  placeholder?: string;
}) {
  const [input, setInput] = useState("");
  const ref = useRef<HTMLInputElement>(null);

  const commit = (raw: string) => {
    const tag = raw.trim();
    if (!tag || tag.length > MAX_LEN || tags.length >= MAX_TAGS) return;
    if (!tags.some((t) => t.toLowerCase() === tag.toLowerCase())) {
      onChange([...tags, tag]);
    }
    setInput("");
  };

  const remove = (i: number) => onChange(tags.filter((_, idx) => idx !== i));

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === "Tab" || e.key === ",") {
      e.preventDefault();
      commit(input);
    } else if (e.key === "Backspace" && input === "") {
      remove(tags.length - 1);
    }
  };

  const onInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    const v = e.target.value;
    if (v.endsWith(",")) commit(v.slice(0, -1));
    else setInput(v);
  };

  const atMax = tags.length >= MAX_TAGS;

  return (
    // The onClick here only redirects focus to the real <input> already rendered below,
    // which is independently keyboard-reachable via Tab — adding a second, duplicate
    // keyboard-operable target on this wrapper would just confuse tab order.
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-noninteractive-element-interactions
    <div className="tag-input" role="group" aria-label="Subject area tags" onClick={() => ref.current?.focus()}>
      {tags.map((tag, i) => (
        <span key={tag} className="tag-chip">
          {tag}
          <button type="button" className="tag-remove" aria-label={`Remove ${tag}`}
            onClick={(e) => { e.stopPropagation(); remove(i); }}>×</button>
        </span>
      ))}
      {atMax
        ? <span className="muted" style={{ fontSize: 11 }}>Maximum {MAX_TAGS} tags reached</span>
        : <input ref={ref} id={id} value={input} onChange={onInputChange} onKeyDown={onKeyDown}
            onBlur={() => { if (input.trim()) commit(input); }}
            placeholder={tags.length === 0 ? placeholder : ""} />}
    </div>
  );
}

// ── Add facilitator modal ──────────────────────────────────────────────────────
// TRGO-07 (React-app parity): the backend blocks a same-name-in-squadron create
// with 409 possible_duplicate once, then requires an explicit confirm_duplicate
// resubmit -- previously this frontend had no way to send that second request,
// so a genuine same-name-different-person case was a dead end. TRGO-06 (React-
// app parity): the Add button now shows "Adding…" while pending, matching the
// save-in-progress feedback already present elsewhere (e.g. SessionForm).
// REM-96/REM-97: shape of the enriched fields app/routers/training.py's
// add_fac() 409 now returns alongside existing_facilitator_id -- everything
// needed for an informed same-vs-different-person decision, loaded in the
// same query that found the duplicate (no second fetch required).
interface DuplicateFacilitatorDetail {
  existing_rank?: string | null;
  existing_type?: string | null;
  existing_subject_areas?: string[];
  existing_active_status?: boolean;
  existing_updated_at?: string | null;
}

function DuplicateProfileCard({ detail }: { detail: DuplicateFacilitatorDetail }) {
  const updated = detail.existing_updated_at ? new Date(detail.existing_updated_at).toLocaleDateString("en-AU", { day: "numeric", month: "short", year: "numeric" }) : "—";
  const areas = detail.existing_subject_areas?.length ? detail.existing_subject_areas.join(", ") : "—";
  return (
    <div style={{ marginTop: 6, padding: "8px 10px", background: "var(--surface-2, #f0f5fa)", borderRadius: 6, fontSize: 11.5, display: "grid", gridTemplateColumns: "auto 1fr", gap: "2px 10px" }}>
      <span style={{ color: "var(--muted-text, #6b7a87)" }}>Rank</span><span style={{ fontWeight: 700 }}>{detail.existing_rank || "—"}</span>
      <span style={{ color: "var(--muted-text, #6b7a87)" }}>Type</span><span>{detail.existing_type || "—"}</span>
      <span style={{ color: "var(--muted-text, #6b7a87)" }}>Subject areas</span><span>{areas}</span>
      <span style={{ color: "var(--muted-text, #6b7a87)" }}>Status</span><span>{detail.existing_active_status === false ? "Archived" : "Active"}</span>
      <span style={{ color: "var(--muted-text, #6b7a87)" }}>Last updated</span><span>{updated}</span>
    </div>
  );
}

const FAC_TYPES = ["Staff", "Officer", "NCO", "Senior Cadet", "Civilian"];

function AddFacModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [first, setFirst] = useState(""); const [last, setLast] = useState("");
  const [rank, setRank] = useState(""); const [type, setType] = useState("Staff");
  const [subjects, setSubjects] = useState<string[]>([]);
  const [err, setErr] = useState("");
  const [duplicateWarning, setDuplicateWarning] = useState<string | null>(null);
  const [duplicateDetail, setDuplicateDetail] = useState<DuplicateFacilitatorDetail | null>(null);
  const m = useMutation({
    mutationFn: (confirmDuplicate: boolean) => trainingApi.addFacilitator({
      first_name: first, last_name: last, current_rank: rank, type, subject_areas: subjects,
      confirm_duplicate: confirmDuplicate,
    }),
    onSuccess: onDone,
    onError: (e) => {
      if (e instanceof ApiError && e.code === "possible_duplicate") {
        setDuplicateWarning(e.friendly);
        setDuplicateDetail((e.data?.detail as DuplicateFacilitatorDetail) ?? null);
        setErr("");
      } else {
        setErr(e instanceof ApiError ? e.friendly : "Could not add.");
      }
    },
  });
  return (
    <Modal title="Add facilitator" onClose={onClose}>
      <div className="form">
        <label htmlFor="f-first">Given name</label><input id="f-first" value={first} onChange={(e) => { setFirst(e.target.value); setDuplicateWarning(null); }} />
        <label htmlFor="f-last">Family name</label><input id="f-last" value={last} onChange={(e) => { setLast(e.target.value); setDuplicateWarning(null); }} />
        <label htmlFor="f-rank">Current rank</label><input id="f-rank" value={rank} onChange={(e) => setRank(e.target.value)} />
        <label htmlFor="f-type">Type</label>
        <select id="f-type" value={type} onChange={(e) => setType(e.target.value)}>
          {FAC_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <label htmlFor="add-fac-subjects">Subject areas</label>
        <TagInput id="add-fac-subjects" tags={subjects} onChange={setSubjects} />
        <p className="muted" style={{ fontSize: 11, margin: "0 0 4px" }}>
          Press Enter or comma to add each tag · max {MAX_TAGS} tags · {MAX_LEN} chars each
        </p>
        {err && <div className="err" role="alert">{err}</div>}
        {duplicateWarning && (
          <div className="err" role="alert">
            {duplicateWarning} If this is a different person with the same name, you can add them anyway.
            {duplicateDetail && <DuplicateProfileCard detail={duplicateDetail} />}
          </div>
        )}
        <div style={{ display: "flex", gap: 8 }}>
          <Button onClick={() => m.mutate(false)} disabled={!first || !last || m.isPending}>
            {m.isPending ? "Adding…" : "Add"}
          </Button>
          {duplicateWarning && (
            <Button variant="out" onClick={() => m.mutate(true)} disabled={m.isPending}>
              {m.isPending ? "Adding…" : "Add anyway"}
            </Button>
          )}
        </div>
      </div>
    </Modal>
  );
}

// ── Edit facilitator modal (name / rank / type) ────────────────────────────────
function EditFacModal({ fac, onClose, onDone }: { fac: Facilitator; onClose: () => void; onDone: () => void }) {
  const [first, setFirst] = useState(fac.first_name ?? "");
  const [last, setLast] = useState(fac.last_name ?? "");
  const [rank, setRank] = useState(fac.current_rank ?? "");
  const [type, setType] = useState(fac.type ?? "Staff");
  const [err, setErr] = useState("");
  const { toast } = useToast();
  const m = useMutation({
    mutationFn: () => trainingApi.updateFacilitator(fac.facilitator_id, { first_name: first, last_name: last, current_rank: rank, type }),
    onSuccess: () => { onDone(); toast("Facilitator updated."); },
    onError: (e) => setErr(e instanceof ApiError ? e.friendly : "Could not save."),
  });
  return (
    <Modal title="Edit facilitator" onClose={onClose}>
      <div className="form">
        <label htmlFor="ef-first">Given name</label><input id="ef-first" value={first} onChange={(e) => setFirst(e.target.value)} />
        <label htmlFor="ef-last">Family name</label><input id="ef-last" value={last} onChange={(e) => setLast(e.target.value)} />
        <label htmlFor="ef-rank">Current rank</label><input id="ef-rank" value={rank} onChange={(e) => setRank(e.target.value)} />
        <label htmlFor="ef-type">Type</label>
        <select id="ef-type" value={type} onChange={(e) => setType(e.target.value)}>
          {FAC_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        {err && <div className="err" role="alert">{err}</div>}
        <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
          <Button onClick={() => m.mutate()} disabled={!first || !last || m.isPending}>
            {m.isPending ? "Saving…" : "Save"}
          </Button>
          <Button variant="out" onClick={onClose}>Cancel</Button>
        </div>
      </div>
    </Modal>
  );
}

// ── Edit tags modal ────────────────────────────────────────────────────────────
function TagsModal({ fac, onClose, onDone }: { fac: Facilitator; onClose: () => void; onDone: () => void }) {
  const [subjects, setSubjects] = useState<string[]>(fac.subject_areas);
  const [err, setErr] = useState("");
  const m = useMutation({
    mutationFn: () => trainingApi.updateFacilitator(fac.facilitator_id, { subject_areas: subjects }),
    onSuccess: onDone,
    onError: (e) => setErr(e instanceof ApiError ? e.friendly : "Could not update tags."),
  });
  const name = [fac.current_rank, fac.first_name, fac.last_name].filter(Boolean).join(" ");
  return (
    <Modal title={`Subject areas — ${name}`} onClose={onClose}>
      <div className="form">
        <label htmlFor="edit-fac-subjects">Subject areas</label>
        <TagInput id="edit-fac-subjects" tags={subjects} onChange={(t) => { setSubjects(t); setErr(""); }} />
        <p className="muted" style={{ fontSize: 11, margin: "0 0 4px" }}>
          Press Enter or comma to add · Backspace removes last tag · max {MAX_TAGS} tags
        </p>
        {err && <div className="errnote" role="alert">{err}</div>}
        <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
          <Button onClick={() => m.mutate()} disabled={m.isPending}>
            {m.isPending ? "Saving…" : "Save tags"}
          </Button>
          <Button variant="out" onClick={onClose}>Cancel</Button>
        </div>
      </div>
    </Modal>
  );
}

// ── Facilitator stats drilldown ────────────────────────────────────────────────
function FacStats({ id, onClose }: { id: string; onClose: () => void }) {
  const q = useQuery({ queryKey: ["fac-stats", id], queryFn: () => trainingApi.facilitatorStats(id) });
  return (
    <DrilldownPanel title="Facilitator stats" onClose={onClose}>
      {q.isLoading ? <Loading /> : q.data ? (
        <div>
          <p><strong>{q.data.facilitator.name}</strong> · load score {q.data.load_score}</p>
          <h3>By status</h3>
          <ul>{Object.entries(q.data.counts).map(([k, v]) => <li key={k}>{k.replace(/_/g, " ")}: {v}</li>)}</ul>
          <h3>By phase</h3>
          <ul>{Object.entries(q.data.by_phase).map(([k, v]) => <li key={k}>{k}: {v}</li>)}</ul>
        </div>
      ) : <Empty msg="No stats." />}
    </DrilldownPanel>
  );
}
