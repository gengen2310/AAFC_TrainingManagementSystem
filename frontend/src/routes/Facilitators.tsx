import { useState, useRef, type KeyboardEvent, type ChangeEvent } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { trainingApi, reportApi } from "../api";
import { Card, Empty, Loading, ErrorNote, Button } from "../components/ui";
import { Modal } from "../components/Modal";
import { DrilldownPanel } from "../components/DrilldownPanel";
import { DecisionBadge } from "../components/status/StatusBadge";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthProvider";
import { canWriteSquadron } from "../auth/permissions";
import { useScopedSquadron } from "../layout/SquadronViewContext";
import type { Facilitator } from "../api/types";

export function Facilitators() {
  const { session } = useAuth();
  const qc = useQueryClient();
  const { needsSelection, squadronId, scoped } = useScopedSquadron();
  const q = useQuery({ queryKey: ["facilitators", squadronId], queryFn: () => trainingApi.facilitators(squadronId), enabled: scoped });
  const load = useQuery({ queryKey: ["fac-load", squadronId], queryFn: () => reportApi.facLoad(squadronId), enabled: scoped });
  const [adding, setAdding] = useState(false);
  const [tagsFor, setTagsFor] = useState<Facilitator | null>(null);
  const [statsId, setStatsId] = useState<string | null>(null);
  const canWrite = canWriteSquadron(session);
  if (needsSelection && !squadronId) return <Empty msg="Select a squadron above to view its facilitators." />;
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorNote error={q.error} />;
  return (
    <div>
      <h1>Facilitators</h1>
      <Card action={canWrite && <Button onClick={() => setAdding(true)}>Add facilitator</Button>}>
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
                    <button className="btn out sm" onClick={() => setTagsFor(f)}>Tags</button>
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
                  <td><span className={`badge ${f.risk === "ok" ? "ok" : f.risk === "high" ? "warn" : "red"}`}>{f.risk}</span></td>
                </tr>
              ))}</tbody>
            </table>
          ))}
      </Card>

      {adding && <AddFacModal onClose={() => setAdding(false)} onDone={() => { setAdding(false); qc.invalidateQueries({ queryKey: ["facilitators"] }); }} />}
      {tagsFor && <TagsModal fac={tagsFor} onClose={() => setTagsFor(null)} onDone={() => { setTagsFor(null); qc.invalidateQueries({ queryKey: ["facilitators"] }); }} />}
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
function AddFacModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [first, setFirst] = useState(""); const [last, setLast] = useState("");
  const [rank, setRank] = useState(""); const [subjects, setSubjects] = useState<string[]>([]);
  const [err, setErr] = useState("");
  const m = useMutation({
    mutationFn: () => trainingApi.addFacilitator({ first_name: first, last_name: last, current_rank: rank, subject_areas: subjects }),
    onSuccess: onDone, onError: (e) => setErr(e instanceof ApiError ? e.friendly : "Could not add."),
  });
  return (
    <Modal title="Add facilitator" onClose={onClose}>
      <div className="form">
        <label htmlFor="f-first">First name</label><input id="f-first" value={first} onChange={(e) => setFirst(e.target.value)} />
        <label htmlFor="f-last">Last name</label><input id="f-last" value={last} onChange={(e) => setLast(e.target.value)} />
        <label htmlFor="f-rank">Current rank</label><input id="f-rank" value={rank} onChange={(e) => setRank(e.target.value)} />
        <label htmlFor="add-fac-subjects">Subject areas</label>
        <TagInput id="add-fac-subjects" tags={subjects} onChange={setSubjects} />
        <p className="muted" style={{ fontSize: 11, margin: "0 0 4px" }}>
          Press Enter or comma to add each tag · max {MAX_TAGS} tags · {MAX_LEN} chars each
        </p>
        {err && <div className="err" role="alert">{err}</div>}
        <Button onClick={() => m.mutate()} disabled={!first || !last || m.isPending}>Add</Button>
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
