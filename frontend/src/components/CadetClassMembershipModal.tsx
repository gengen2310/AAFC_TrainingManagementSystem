import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { trainingApi } from "../api";
import { friendlyMessage } from "../api/client";
import { Modal } from "./Modal";
import { Loading, ErrorNote, Button } from "./ui";
import type { Cadet } from "../api/types";

// CLASS-09: manage one Cadet's Training Class membership(s). Explicitly
// product-scope-confirmed before being built -- see CadetClassMembership's
// own docstring (backend/app/models/training.py). Enables a Cadet to hold
// concurrent Foundation (e.g. Senior 1) and Extension (e.g. Bronze CLP)
// membership at once, which Cadet.phase's single free-text field cannot
// express -- Cadet.phase is left untouched by this modal.
export function CadetClassMembershipModal({ cadet, onClose }: { cadet: Cadet; onClose: () => void }) {
  const qc = useQueryClient();
  const [selectedClassId, setSelectedClassId] = useState("");
  const [classFilter, setClassFilter] = useState("");
  const [ending, setEnding] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const memberships = useQuery({
    queryKey: ["cadet-class-memberships", cadet.cadet_id],
    queryFn: () => trainingApi.cadetClassMemberships(cadet.cadet_id),
  });
  // Every active Training Class for the caller's squadron, regardless of
  // Training Year -- matches the same "picker shows every active class"
  // convention already established in connected-frontend's own Quick Edit
  // membership picker (CLASS-17), since a squadron can have more than one
  // active PlanningYear at once.
  const classes = useQuery({
    queryKey: ["training-classes-all"],
    queryFn: () => trainingApi.trainingClasses(),
  });
  // CLASS-08: a squadron can have many Training Classes across several
  // Stages -- the addendum's own named pattern for this ("group-by-stage,
  // filter, collapse, pin, search") is applied here as Stage-grouped
  // <optgroup>s plus a text filter, rather than one long flat <select>
  // (confirmed via direct testing: a real squadron's worth of accumulated
  // classes renders as a 100+ option flat list with no grouping at all
  // without this).
  const stages = useQuery({
    queryKey: ["training-stages-all"],
    queryFn: () => trainingApi.phases(),
  });

  async function handleAdd() {
    if (!selectedClassId) { setErr("Choose a Training Class first."); return; }
    setErr(null);
    setAdding(true);
    try {
      await trainingApi.addCadetClassMembership(cadet.cadet_id, { training_class_id: selectedClassId });
      setSelectedClassId("");
      await qc.invalidateQueries({ queryKey: ["cadet-class-memberships", cadet.cadet_id] });
    } catch (e: unknown) {
      setErr(friendlyMessage(e, "Could not add membership"));
    } finally {
      setAdding(false);
    }
  }

  async function handleEnd(membershipId: string, version: number) {
    setErr(null);
    setEnding(membershipId);
    try {
      await trainingApi.endCadetClassMembership(membershipId, {
        active_status: false,
        end_date: new Date().toISOString().slice(0, 10),
        client_version: version,
      });
      await qc.invalidateQueries({ queryKey: ["cadet-class-memberships", cadet.cadet_id] });
    } catch (e: unknown) {
      setErr(friendlyMessage(e, "Could not end membership"));
    } finally {
      setEnding(null);
    }
  }

  const active = (memberships.data ?? []).filter((m) => m.active_status);
  const alreadyIn = new Set(active.map((m) => m.training_class_id));
  const filterText = classFilter.trim().toLowerCase();
  const availableClasses = (classes.data ?? []).filter((c) =>
    !alreadyIn.has(c.training_class_id) &&
    (!filterText || c.display_name.toLowerCase().includes(filterText)),
  );
  const stageNameById = useMemo(() => {
    const m = new Map<string, string>();
    for (const s of stages.data ?? []) m.set(s.phase_id, s.display_name);
    return m;
  }, [stages.data]);
  const groupedByStage = useMemo(() => {
    // Keyed by training_stage_id, not display name -- Stage names are not
    // guaranteed unique (different scope levels, or duplicate squadron-level
    // stages, can legitimately share a display name), so a name-keyed React
    // list key caused stale/duplicate <optgroup> content under filtering
    // when two stages shared a name (found via the CLASS-08 e2e test).
    const groups = new Map<string, { stageId: string; stageName: string; classes: typeof availableClasses }>();
    for (const c of availableClasses) {
      const stageName = stageNameById.get(c.training_stage_id) ?? "Other";
      if (!groups.has(c.training_stage_id)) groups.set(c.training_stage_id, { stageId: c.training_stage_id, stageName, classes: [] });
      groups.get(c.training_stage_id)!.classes.push(c);
    }
    return [...groups.values()].sort((a, b) => a.stageName.localeCompare(b.stageName) || a.stageId.localeCompare(b.stageId));
  }, [availableClasses, stageNameById]);

  return (
    <Modal title={`${cadet.rank ?? ""} ${cadet.first_name} ${cadet.last_name} — Training Classes`} onClose={onClose}>
      <p className="muted" style={{ marginTop: 0 }}>
        A Cadet can belong to more than one Training Class at once (e.g. a Foundation
        Stage class and an Extension Stage class concurrently).
      </p>
      {memberships.isLoading ? <Loading /> : memberships.error ? <ErrorNote error={memberships.error} /> : (
        active.length === 0 ? <p className="muted">Not currently a member of any Training Class.</p> : (
          <ul className="cadet-class-membership-list">
            {active.map((m) => (
              <li key={m.membership_id} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                <span style={{ flex: 1 }}>{m.training_class_name ?? "Unknown class"}</span>
                <Button variant="out" onClick={() => handleEnd(m.membership_id, m.version)} disabled={ending === m.membership_id}>
                  {ending === m.membership_id ? "…" : "End membership"}
                </Button>
              </li>
            ))}
          </ul>
        )
      )}

      <div style={{ marginTop: 16, paddingTop: 12, borderTop: "1px solid var(--border)" }}>
        <label htmlFor="ccm-class-filter">Add to a Training Class</label>
        <div style={{ display: "flex", gap: 8, marginTop: 4, flexWrap: "wrap", alignItems: "center" }}>
          <input
            id="ccm-class-filter"
            type="search"
            placeholder="Filter by class name…"
            value={classFilter}
            onChange={(e) => { setClassFilter(e.target.value); setSelectedClassId(""); }}
            aria-label="Filter Training Classes by name"
            style={{ minWidth: 160 }}
          />
          <select
            id="ccm-class-select"
            value={selectedClassId}
            onChange={(e) => setSelectedClassId(e.target.value)}
            disabled={classes.isLoading || availableClasses.length === 0}
          >
            <option value="">— choose —</option>
            {groupedByStage.map((g) => (
              <optgroup key={g.stageId} label={g.stageName}>
                {g.classes.map((c) => (
                  <option key={c.training_class_id} value={c.training_class_id}>{c.display_name}</option>
                ))}
              </optgroup>
            ))}
          </select>
          <Button onClick={handleAdd} disabled={adding || !selectedClassId}>{adding ? "…" : "Add"}</Button>
        </div>
        {classFilter && availableClasses.length === 0 && (
          <p className="muted" style={{ marginBottom: 0 }}>No matching Training Classes.</p>
        )}
        {err && <p role="alert" style={{ color: "var(--danger, #b91c1c)" }}>{err}</p>}
      </div>
    </Modal>
  );
}
