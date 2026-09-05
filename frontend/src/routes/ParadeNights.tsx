import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { trainingApi, planningApi } from "../api";
import { Card, Empty, Loading, ErrorNote, Button } from "../components/ui";
import { StatusBadge } from "../components/status/StatusBadge";
import { Modal } from "../components/Modal";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthProvider";
import { canWriteSquadron } from "../auth/permissions";
import { ParadeNightDetailView } from "./ParadeNightDetail";
import { useScopedSquadron } from "../layout/SquadronViewContext";

export function ParadeNights() {
  const { session } = useAuth();
  const qc = useQueryClient();
  const { needsSelection, squadronId, scoped } = useScopedSquadron();
  const q = useQuery({ queryKey: ["parade-nights", squadronId], queryFn: () => trainingApi.paradeNights(squadronId), enabled: scoped });
  const [creating, setCreating] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);
  const canWrite = canWriteSquadron(session);

  if (needsSelection && !squadronId) return <div><h1>Parade Nights</h1><Empty msg="Select a squadron above to view its parade nights." /></div>;
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorNote error={q.error} />;

  return (
    <div>
      <h1>Parade Nights</h1>
      <Card title="All parade nights" action={canWrite && <Button onClick={() => setCreating(true)}>New parade night</Button>}>
        {(q.data ?? []).length === 0 ? <Empty msg="No parade nights yet." /> : (
          <table>
            <caption className="vis-hidden">Parade nights</caption>
            <thead><tr><th>Date</th><th>Term</th><th>Type</th><th>Sessions</th><th>Published</th><th>Readiness</th><th></th></tr></thead>
            <tbody>{(q.data ?? []).map((p) => (
              <tr key={p.parade_night_id}>
                <td>{p.date}</td><td>{p.term ?? "—"}</td><td>{p.parade_type}</td><td>{p.sessions.length}</td>
                <td><StatusBadge status={p.published_status ? "published" : "draft"} /></td>
                {/* REM-17 (original_instruction.md Section 15): zero scheduled
                    sessions must read "Not planned", never a bare readiness
                    percentage (p.readiness_score is hard-coded to 100 for an
                    empty night by design -- see services_readiness.py). */}
                <td>{p.sessions.length === 0 ? "Not planned" : (p.readiness_score ?? "—")}</td>
                <td><button className="btn out sm" onClick={() => setOpenId(p.parade_night_id)}>Open</button></td>
              </tr>))}</tbody>
          </table>
        )}
      </Card>
      {creating && <CreateParadeModal squadronId={squadronId ?? null} onClose={() => setCreating(false)} onDone={() => { setCreating(false); qc.invalidateQueries({ queryKey: ["parade-nights"] }); }} />}
      {openId && <Modal title="Parade night" onClose={() => setOpenId(null)}><ParadeNightDetailView id={openId} canWrite={canWrite} /></Modal>}
    </div>
  );
}

// Task 8: simplified Create Parade Night form.
// Removed: session count (derived from timing template's instructional_period_count).
// Added: required timing template selector. On success, navigates to /planning.
function CreateParadeModal({
  squadronId,
  onClose,
  onDone,
}: {
  squadronId: string | null;
  onClose: () => void;
  onDone: () => void;
}) {
  const navigate = useNavigate();
  const [date, setDate] = useState("");
  const [term, setTerm] = useState("T1");
  const [timingTemplateId, setTimingTemplateId] = useState("");
  const [err, setErr] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});

  const { data: templates = [] } = useQuery({
    queryKey: ["timing-templates", squadronId],
    queryFn: () => planningApi.listTimingTemplates(squadronId ?? undefined),
    enabled: true,
    staleTime: 5 * 60 * 1000,
  });
  // Pre-select the default template once loaded.
  const defaultTpl = templates.find(t => t.is_default);
  const [initialized, setInitialized] = useState(false);
  if (!initialized && defaultTpl) {
    setTimingTemplateId(defaultTpl.timing_template_id);
    setInitialized(true);
  }

  const m = useMutation({
    mutationFn: () =>
      trainingApi.createParadeNight({
        date,
        term,
        ...(timingTemplateId ? { timing_template_id: timingTemplateId } : {}),
      }),
    onSuccess: (data) => {
      onDone();
      // Navigate to the planning workspace so the user can see the new night.
      // The planning workspace shows the relevant date once the weekly program loads.
      void data; // parade_night_id available if planning workspace accepts it in future
      navigate("/planning");
    },
    onError: (e) => {
      if (e instanceof ApiError) {
        const fe = e.fieldErrors;
        setFields(fe);
        setErr(Object.keys(fe).length ? "" : e.friendly);
      } else {
        setErr("Could not create.");
        setFields({});
      }
    },
  });

  const selectedTpl = templates.find(t => t.timing_template_id === timingTemplateId);

  return (
    <Modal title="New parade night" onClose={onClose}>
      <div className="form">
        <label htmlFor="pn-date">Date</label>
        <input
          id="pn-date"
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          aria-invalid={!!fields.date}
        />
        {fields.date && <div className="field-err" role="alert">{fields.date}</div>}

        <label htmlFor="pn-term">Term</label>
        <select
          id="pn-term"
          value={term}
          onChange={(e) => setTerm(e.target.value)}
          aria-invalid={!!fields.term}
        >
          <option value="T1">Term 1</option>
          <option value="T2">Term 2</option>
          <option value="T3">Term 3</option>
          <option value="T4">Term 4</option>
        </select>
        {fields.term && <div className="field-err" role="alert">{fields.term}</div>}

        <label htmlFor="pn-template">Timing template <span aria-hidden="true">*</span></label>
        <select
          id="pn-template"
          value={timingTemplateId}
          onChange={(e) => setTimingTemplateId(e.target.value)}
          aria-required="true"
          aria-invalid={!!fields.timing_template_id}
        >
          <option value="">— Select template —</option>
          {templates.map(t => (
            <option key={t.timing_template_id} value={t.timing_template_id}>
              {t.name}
              {t.is_default ? " (default)" : ""}
              {" — "}
              {t.instructional_period_count} period{t.instructional_period_count === 1 ? "" : "s"}
            </option>
          ))}
        </select>
        {fields.timing_template_id && (
          <div className="field-err" role="alert">{fields.timing_template_id}</div>
        )}
        {selectedTpl && (
          <div style={{ fontSize: 'var(--fs-xs, 11px)', color: "var(--muted, #5c6a76)", marginTop: 2 }}>
            {selectedTpl.instructional_period_count} instructional period{selectedTpl.instructional_period_count !== 1 ? "s" : ""}
          </div>
        )}

        {err && <div className="err" role="alert">{err}</div>}
        <Button
          onClick={() => m.mutate()}
          disabled={!date || !timingTemplateId || m.isPending}
        >
          {m.isPending ? "Creating…" : "Create"}
        </Button>
      </div>
    </Modal>
  );
}
