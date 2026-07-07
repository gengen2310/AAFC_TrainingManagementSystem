import { useState, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { planningApi } from "../../api";
import type { PlanningSession, PlanningFacilitator, PlanningLocation, PlanningConflict, WingHQEvent } from "../../api/types";

// ─── Drawer item discriminated union ──────────────────────────────────────────
export type DrawerItem =
  | { type: "session"; session: PlanningSession; dateId: string; date: string; conflicts: PlanningConflict[] }
  | { type: "new-session"; cadetGroup: string; periodNumber: number; dateId: string }
  | { type: "wing-event"; event: WingHQEvent }
  | { type: "curriculum"; curriculum: { curriculum_id: string; code: string; title: string; phase: string } };

const CADET_GROUPS = ["orientation", "initial", "junior", "intermediate", "senior"] as const;

interface Props {
  item: DrawerItem | null;
  facilitators: PlanningFacilitator[];
  locations: PlanningLocation[];
  yearId: string | null;
  onClose: () => void;
}

// ─── Session edit / create form ────────────────────────────────────────────────
function SessionForm({
  item, facilitators, locations, yearId, onClose,
}: {
  item: Extract<DrawerItem, { type: "session" }> | Extract<DrawerItem, { type: "new-session" }>;
  facilitators: PlanningFacilitator[];
  locations: PlanningLocation[];
  yearId: string | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const isEdit = item.type === "session";
  const existing = isEdit ? item.session : null;

  const [title, setTitle] = useState(existing?.activity_title ?? "");
  const [cadetGroup, setCadetGroup] = useState(
    existing?.cadet_group ?? (item.type === "new-session" ? item.cadetGroup : "junior"),
  );
  const [periodNumber, setPeriodNumber] = useState(
    existing?.session_number ?? (item.type === "new-session" ? item.periodNumber : 1),
  );
  const [partNumber, setPartNumber] = useState(existing?.part_number?.toString() ?? "");
  const [facilitatorId, setFacilitatorId] = useState(existing?.facilitator_id ?? "");
  const [asstFacId, setAsstFacId] = useState(existing?.assistant_facilitator_id ?? "");
  const [locationId, setLocationId] = useState(existing?.location_id ?? "");
  const [notes, setNotes] = useState(existing?.notes ?? "");
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [overrideConflict, setOverrideConflict] = useState(false);
  const [overrideReason, setOverrideReason] = useState("");
  const [overridingId, setOverridingId] = useState<string | null>(null);
  const [overrideErr, setOverrideErr] = useState<string | null>(null);
  const [overrideSaving, setOverrideSaving] = useState(false);

  const conflicts = item.type === "session" ? item.conflicts : [];
  const dateId = item.type === "session" ? item.dateId : item.dateId;

  async function handleSave() {
    setSaving(true);
    setErr(null);
    try {
      if (isEdit && existing) {
        await planningApi.updateSession(existing.session_id, {
          activity_title: title || null,
          facilitator_id: facilitatorId || null,
          assistant_facilitator_id: asstFacId || null,
          location_id: locationId || null,
          cadet_group: cadetGroup || null,
          part_number: partNumber ? Number(partNumber) : null,
          notes: notes || null,
        });
      } else {
        await planningApi.createSession(dateId, {
          cadet_group: cadetGroup,
          session_number: periodNumber,
          activity_title: title || undefined,
          facilitator_id: facilitatorId || undefined,
          location_id: locationId || undefined,
          part_number: partNumber ? Number(partNumber) : undefined,
          notes: notes || undefined,
        });
      }
      await qc.invalidateQueries({ queryKey: ["planning-weekly", dateId] });
      await qc.invalidateQueries({ queryKey: ["planning-long-range"] });
      await qc.invalidateQueries({ queryKey: ["planning-annual"] });
      if (yearId) {
        await qc.invalidateQueries({ queryKey: ["planning-cc", yearId] });
      }
      onClose();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!existing) return;
    if (!window.confirm("Delete this session?")) return;
    setDeleting(true);
    try {
      await planningApi.deleteSession(existing.session_id);
      await qc.invalidateQueries({ queryKey: ["planning-weekly", dateId] });
      await qc.invalidateQueries({ queryKey: ["planning-long-range"] });
      await qc.invalidateQueries({ queryKey: ["planning-annual"] });
      onClose();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setDeleting(false);
    }
  }

  async function handleOverride(conflictId: string) {
    if (!overrideReason.trim()) { setOverrideErr("A reason is required to override a conflict."); return; }
    setOverrideSaving(true);
    setOverrideErr(null);
    try {
      await planningApi.overrideConflict(conflictId, overrideReason.trim());
      await qc.invalidateQueries({ queryKey: ["planning-weekly", dateId] });
      setOverridingId(null);
      setOverrideReason("");
    } catch (e: unknown) {
      setOverrideErr(e instanceof Error ? e.message : "Override failed");
    } finally {
      setOverrideSaving(false);
    }
  }

  return (
    <div>
      {conflicts.length > 0 && (
        <div style={{ marginBottom: 14 }}>
          {conflicts.map((c) => (
            <div key={c.conflict_id} className={`pw-conflict-alert ${c.severity === "critical" ? "err" : c.severity === "warning" ? "warn" : "soft"}`}>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 700 }}>
                  {c.severity === "critical" ? "🔴" : c.severity === "warning" ? "🟡" : "🟠"} {c.conflict_type.replace(/_/g, " ")}
                </div>
                <div>{c.message}</div>
                {!c.is_resolved && (
                  <div style={{ marginTop: 6 }}>
                    {overridingId === c.conflict_id ? (
                      <div>
                        <textarea
                          placeholder="Override reason (required — this is audited)"
                          value={overrideReason}
                          onChange={e => setOverrideReason(e.target.value)}
                          style={{ width: "100%", fontSize: 11, padding: "5px 7px", borderRadius: 6, border: "1.5px solid var(--border)", marginBottom: 4, resize: "vertical", minHeight: 50 }}
                        />
                        {overrideErr && <div className="pw-err" style={{ marginBottom: 4 }}>{overrideErr}</div>}
                        <div style={{ display: "flex", gap: 6 }}>
                          <button className="btn sm danger" onClick={() => handleOverride(c.conflict_id)} disabled={overrideSaving}>
                            {overrideSaving ? "Saving…" : "Confirm override"}
                          </button>
                          <button className="btn sm out" onClick={() => { setOverridingId(null); setOverrideReason(""); }}>Cancel</button>
                        </div>
                      </div>
                    ) : (
                      <button className="btn sm out" style={{ fontSize: 11 }} onClick={() => setOverridingId(c.conflict_id)}>
                        Override (with reason)
                      </button>
                    )}
                  </div>
                )}
                {c.is_resolved && <div style={{ fontSize: 10, color: "var(--success)", marginTop: 4 }}>✓ Overridden — {c.override_reason}</div>}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="pw-drawer-form">
        <label>
          Activity title
          <input value={title} onChange={e => setTitle(e.target.value)} placeholder="e.g. Navigation using compass" />
        </label>
        <label>
          Cadet group
          <select value={cadetGroup} onChange={e => setCadetGroup(e.target.value)}>
            {CADET_GROUPS.map(g => <option key={g} value={g}>{g}</option>)}
          </select>
        </label>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          <label>
            Session #
            <input type="number" min={1} max={4} value={periodNumber} onChange={e => setPeriodNumber(Number(e.target.value))} />
          </label>
          <label>
            Part # (optional)
            <input type="number" min={1} max={4} value={partNumber} onChange={e => setPartNumber(e.target.value)} placeholder="—" />
          </label>
        </div>
        <label>
          Lead facilitator
          <select value={facilitatorId} onChange={e => setFacilitatorId(e.target.value)}>
            <option value="">— None —</option>
            {facilitators.map(f => <option key={f.facilitator_id} value={f.facilitator_id}>{f.display_name}</option>)}
          </select>
        </label>
        <label>
          Assistant facilitator
          <select value={asstFacId} onChange={e => setAsstFacId(e.target.value)}>
            <option value="">— None —</option>
            {facilitators.map(f => <option key={f.facilitator_id} value={f.facilitator_id}>{f.display_name}</option>)}
          </select>
        </label>
        <label>
          Room / Location
          <select value={locationId} onChange={e => setLocationId(e.target.value)}>
            <option value="">— None —</option>
            {locations.map(l => <option key={l.location_id} value={l.location_id}>{l.name}</option>)}
          </select>
        </label>
        <label>
          Notes
          <textarea value={notes} onChange={e => setNotes(e.target.value)} placeholder="Optional delivery notes" />
        </label>
      </div>

      {err && <div className="pw-err" style={{ marginTop: 8 }}>{err}</div>}

      <div className="pw-drawer-actions" style={{ marginTop: 14 }}>
        <button className="btn primary" onClick={handleSave} disabled={saving}>
          {saving ? "Saving…" : isEdit ? "Save changes" : "Add session"}
        </button>
        {isEdit && (
          <button className="btn danger out sm" onClick={handleDelete} disabled={deleting}>
            {deleting ? "Deleting…" : "Delete session"}
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Wing event review panel ───────────────────────────────────────────────────
function WingEventPanel({ event, onClose }: { event: WingHQEvent; onClose: () => void }) {
  const qc = useQueryClient();
  const [saving, setSaving] = useState(false);
  const [reviewNotes, setReviewNotes] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const current = event.sqn_status;

  async function review(status: string) {
    setSaving(true);
    setErr(null);
    try {
      await planningApi.reviewWingEvent(event.event_id, status, reviewNotes || undefined);
      await qc.invalidateQueries({ queryKey: ["planning-cc"] });
      onClose();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Review failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <div className="pw-drawer-section">
        <div className="pw-badge-wing pw-badge-source" style={{ marginBottom: 8 }}>Wing HQ · Read-only</div>
        <div className="pw-drawer-label">Type</div>
        <div className="pw-drawer-value">{event.event_type}</div>
      </div>
      <div className="pw-drawer-section">
        <div className="pw-drawer-label">Dates</div>
        <div className="pw-drawer-value">{event.start_date}{event.end_date ? ` → ${event.end_date}` : ""}</div>
      </div>
      <div className="pw-drawer-section">
        <div className="pw-drawer-label">Importance</div>
        <div className="pw-drawer-value">{event.planning_importance}</div>
      </div>
      {event.audience && event.audience.length > 0 && (
        <div className="pw-drawer-section">
          <div className="pw-drawer-label">Audience</div>
          <div className="pw-drawer-value">{event.audience.join(", ")}</div>
        </div>
      )}
      {event.notes && (
        <div className="pw-drawer-section">
          <div className="pw-drawer-label">Notes</div>
          <div className="pw-drawer-value" style={{ fontSize: 12 }}>{event.notes}</div>
        </div>
      )}
      {current && (
        <div className="pw-drawer-section">
          <div className="pw-drawer-label">Your review status</div>
          <div className="pw-drawer-value" style={{ fontWeight: 700, textTransform: "capitalize" }}>{current.status}</div>
          {current.notes && <div style={{ fontSize: 11, color: "var(--muted-text)", marginTop: 2 }}>{current.notes}</div>}
        </div>
      )}
      <div className="pw-drawer-section">
        <div className="pw-drawer-label">Review notes (optional)</div>
        <textarea
          className="pw-drawer-form"
          value={reviewNotes}
          onChange={e => setReviewNotes(e.target.value)}
          placeholder="Notes for your review"
          style={{ width: "100%", fontSize: 12, padding: "7px 9px", borderRadius: 7, border: "1.5px solid var(--border)", resize: "vertical", minHeight: 50 }}
        />
      </div>
      {err && <div className="pw-err">{err}</div>}
      <div className="pw-review-status">
        <button className="btn sm primary" onClick={() => review("acknowledged")} disabled={saving}>Acknowledged</button>
        <button className="btn sm out" onClick={() => review("planning")} disabled={saving}>Planning</button>
        <button className="btn sm out" onClick={() => review("not_relevant")} disabled={saving}>Not Relevant</button>
      </div>
    </div>
  );
}

// ─── Main drawer ───────────────────────────────────────────────────────────────
export function PlanningRightDrawer({ item, facilitators, locations, yearId, onClose }: Props) {
  const [key, setKey] = useState(0);
  useEffect(() => { setKey(k => k + 1); }, [item]);

  if (!item) return null;

  const title =
    item.type === "session" ? (item.session.activity_title ?? "Session")
    : item.type === "new-session" ? "Add Session"
    : item.type === "wing-event" ? item.event.title
    : `${item.curriculum.code} — ${item.curriculum.title}`;

  return (
    <div className="pw-right" role="complementary" aria-label="Detail drawer">
      <div className="pw-drawer-hdr">
        <h3>{title}</h3>
        <button className="pw-drawer-close" onClick={onClose} aria-label="Close drawer">×</button>
      </div>
      <div className="pw-drawer-body" key={key}>
        {(item.type === "session" || item.type === "new-session") && (
          <SessionForm item={item} facilitators={facilitators} locations={locations} yearId={yearId} onClose={onClose} />
        )}
        {item.type === "wing-event" && (
          <WingEventPanel event={item.event} onClose={onClose} />
        )}
        {item.type === "curriculum" && (
          <div>
            <div className="pw-drawer-section">
              <div className="pw-drawer-label">Code</div>
              <div className="pw-drawer-value">{item.curriculum.code}</div>
            </div>
            <div className="pw-drawer-section">
              <div className="pw-drawer-label">Title</div>
              <div className="pw-drawer-value">{item.curriculum.title}</div>
            </div>
            <div className="pw-drawer-section">
              <div className="pw-drawer-label">Phase</div>
              <div className="pw-drawer-value">{item.curriculum.phase}</div>
            </div>
            <div className="pw-drawer-section">
              <div style={{ fontSize: 12, color: "var(--muted-text)" }}>
                Navigate to a parade night and click a cell to schedule this curriculum item.
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
