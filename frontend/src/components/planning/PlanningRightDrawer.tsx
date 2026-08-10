import { useState, useEffect, useRef, useId, type KeyboardEvent } from "react";
import { useQueryClient, useQuery } from "@tanstack/react-query";
import { planningApi } from "../../api";
import { friendlyMessage } from "../../api/client";
import type { PlanningSession, PlanningFacilitator, PlanningLocation, PlanningConflict, WingHQEvent, MissionItem, AnchorEvent } from "../../api/types";
import { ActivityFullDetail, anchorToDisplay } from "./ActivityDetailBlock";
import { getProgramType } from "../../utils/planningFilters";

// ─── Drawer item discriminated union ──────────────────────────────────────────
export type DrawerItem =
  | { type: "session"; session: PlanningSession; dateId: string; date: string; conflicts: PlanningConflict[] }
  | { type: "session-by-id"; sessionId: string; dateId: string; date: string }
  | { type: "new-session"; cadetGroup: string; periodNumber: number; dateId: string }
  | { type: "wing-event"; event: WingHQEvent }
  | { type: "curriculum"; curriculum: { curriculum_id: string; code: string; title: string; phase: string } }
  | { type: "new-anchor"; yearId: string }
  | { type: "anchor"; anchor: AnchorEvent; yearId: string }
  | { type: "new-location"; location?: PlanningLocation };

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
  const [curriculumId, setCurriculumId] = useState<string | null>(existing?.curriculum_id ?? null);
  const [currSearch, setCurrSearch] = useState("");
  const [pickerOpen, setPickerOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const pickerRef = useRef<HTMLDivElement>(null);
  const listboxId = useId();
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
  const [overrideReason, setOverrideReason] = useState("");
  const [overridingId, setOverridingId] = useState<string | null>(null);
  const [overrideErr, setOverrideErr] = useState<string | null>(null);
  const [overrideSaving, setOverrideSaving] = useState(false);

  const { data: missionsData } = useQuery({
    queryKey: ["planning-missions", yearId],
    queryFn: () => planningApi.missions(yearId!),
    enabled: !!yearId,
  });

  const allMissions: MissionItem[] = missionsData?.missions ?? [];
  const linkedMission = curriculumId ? allMissions.find(m => m.curriculum_id === curriculumId) : null;
  const searchResults = currSearch.length >= 2
    ? allMissions.filter(m =>
        m.code.toLowerCase().includes(currSearch.toLowerCase()) ||
        m.title.toLowerCase().includes(currSearch.toLowerCase()),
      ).slice(0, 10)
    : [];

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (pickerRef.current && !pickerRef.current.contains(e.target as Node)) {
        setPickerOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  // Keep the highlighted option in range as the result set changes while typing.
  useEffect(() => { setHighlightedIndex(0); }, [currSearch]);

  function selectCurriculum(m: MissionItem) {
    setCurriculumId(m.curriculum_id);
    setTitle(m.title);
    setCurrSearch("");
    setPickerOpen(false);
  }

  // Real ARIA combobox keyboard interaction (was previously mouse-only — see
  // docs/beta/15_known_limitations.md AL-01). ArrowUp/Down move the highlighted
  // option, Enter selects it, Escape closes without selecting.
  function handleSearchKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (!pickerOpen || searchResults.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlightedIndex(i => Math.min(i + 1, searchResults.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightedIndex(i => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const m = searchResults[highlightedIndex];
      if (m) selectCurriculum(m);
    } else if (e.key === "Escape") {
      e.preventDefault();
      setPickerOpen(false);
    }
  }

  function clearCurriculum() {
    setCurriculumId(null);
    setCurrSearch("");
  }

  const conflicts = item.type === "session" ? item.conflicts : [];
  const dateId = item.type === "session" ? item.dateId : item.dateId;

  async function handleSave() {
    setSaving(true);
    setErr(null);
    try {
      if (isEdit && existing) {
        await planningApi.updateSession(existing.session_id, {
          curriculum_id: curriculumId ?? null,
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
          curriculum_id: curriculumId ?? undefined,
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
      setErr(friendlyMessage(e, "Save failed"));
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
      setErr(friendlyMessage(e, "Delete failed"));
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
      // REM-39 follow-up: also invalidate the year-wide conflicts list
      // PlanningWorkspace.tsx now fetches (previously only planning-weekly
      // existed, so overriding from any view other than the single-night
      // grid would leave stale unresolved-conflict indicators everywhere else).
      if (yearId) await qc.invalidateQueries({ queryKey: ["planning-conflicts", yearId] });
      setOverridingId(null);
      setOverrideReason("");
    } catch (e: unknown) {
      setOverrideErr(friendlyMessage(e, "Override failed"));
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
        <div ref={pickerRef} style={{ position: "relative", marginBottom: 10 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "var(--muted-text)", marginBottom: 4 }}>
            Curriculum link
          </div>
          {curriculumId && linkedMission ? (
            <div className="pw-curric-linked">
              <span className="pw-curric-code">{linkedMission.code}</span>
              <span style={{ flex: 1, fontSize: 12 }}>{linkedMission.title}</span>
              <button type="button" className="pw-curric-clear" onClick={clearCurriculum} aria-label="Unlink curriculum">✕</button>
            </div>
          ) : (
            <>
              <input
                role="combobox"
                aria-expanded={pickerOpen && searchResults.length > 0}
                aria-haspopup="listbox"
                aria-autocomplete="list"
                aria-controls={`${listboxId}-listbox`}
                aria-activedescendant={
                  pickerOpen && searchResults[highlightedIndex]
                    ? `${listboxId}-opt-${searchResults[highlightedIndex].curriculum_id}`
                    : undefined
                }
                placeholder="Search by code or title…"
                value={currSearch}
                onChange={e => { setCurrSearch(e.target.value); setPickerOpen(true); }}
                onFocus={() => setPickerOpen(true)}
                onKeyDown={handleSearchKeyDown}
                style={{ width: "100%", fontSize: 12, padding: "6px 9px", borderRadius: 6, border: "1.5px solid var(--border)" }}
              />
              {pickerOpen && searchResults.length > 0 && (
                <div className="pw-curric-dropdown" role="listbox" id={`${listboxId}-listbox`} aria-label="Curriculum search results">
                  {searchResults.map((m, i) => (
                    // onMouseDown (not onClick) is deliberate: it fires before the input's
                    // onBlur closes the dropdown. Real keyboard operability (Arrow keys,
                    // Enter, Escape) is handled by handleSearchKeyDown on the input above,
                    // via role="combobox"/aria-activedescendant — per the W3C ARIA APG
                    // combobox-list pattern, listbox options are deliberately NOT focusable
                    // (no tabIndex); the input owns focus throughout and the "virtually
                    // focused" option is only ever referenced, never actually focused. This
                    // is why interactive-supports-focus is also suppressed here, not just
                    // the click/keyboard-parity rules (see docs/beta/15_known_limitations.md
                    // AL-01, resolved).
                    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions, jsx-a11y/interactive-supports-focus
                    <div
                      key={m.curriculum_id}
                      id={`${listboxId}-opt-${m.curriculum_id}`}
                      role="option"
                      aria-selected={i === highlightedIndex}
                      className={`pw-curric-item${i === highlightedIndex ? " highlighted" : ""}`}
                      onMouseDown={() => selectCurriculum(m)}
                      onMouseEnter={() => setHighlightedIndex(i)}
                    >
                      <span className="pw-curric-code">{m.code}</span>
                      <span style={{ flex: 1 }}>{m.title}</span>
                      {m.is_scheduled && <span style={{ fontSize: 10, color: "var(--muted-text)" }}>scheduled</span>}
                    </div>
                  ))}
                </div>
              )}
              {pickerOpen && currSearch.length >= 2 && searchResults.length === 0 && (
                <div className="pw-curric-dropdown" style={{ padding: "10px 12px", color: "var(--muted-text)", fontSize: 12 }}>
                  No curriculum found
                </div>
              )}
            </>
          )}
        </div>
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
      setErr(friendlyMessage(e, "Review failed"));
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

// ─── Create anchor event form ─────────────────────────────────────────────────
const ANCHOR_TYPES = ["inspection", "competition", "training_weekend", "ceremonial", "admin", "other"] as const;
const ANCHOR_IMPORTANCE = ["mandatory", "key_event", "recommended", "optional"] as const;
const AUDIENCE_FIELDS: { key: string; label: string }[] = [
  { key: "audience_orientation", label: "Orientation" },
  { key: "audience_initial", label: "Initial" },
  { key: "audience_junior", label: "Junior" },
  { key: "audience_intermediate", label: "Intermediate" },
  { key: "audience_senior", label: "Senior" },
];

function CreateAnchorForm({ yearId, onClose }: { yearId: string; onClose: () => void }) {
  const qc = useQueryClient();
  const [eventName, setEventName] = useState("");
  const [eventType, setEventType] = useState<string>("other");
  const [importance, setImportance] = useState<string>("key_event");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [audience, setAudience] = useState({ audience_orientation: true, audience_initial: true, audience_junior: true, audience_intermediate: true, audience_senior: true });
  const [planningImpact, setPlanningImpact] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function handleSave() {
    if (!eventName.trim()) { setErr("Event name is required."); return; }
    if (!startDate) { setErr("Start date is required."); return; }
    setSaving(true); setErr(null);
    try {
      await planningApi.createAnchor(yearId, {
        event_name: eventName.trim(),
        event_type: eventType,
        importance,
        start_date: startDate,
        end_date: endDate || undefined,
        ...audience,
        planning_impact: planningImpact || undefined,
        notes: notes || undefined,
      });
      await qc.invalidateQueries({ queryKey: ["planning-annual"] });
      await qc.invalidateQueries({ queryKey: ["planning-cc"] });
      await qc.invalidateQueries({ queryKey: ["planning-long-range"] });
      onClose();
    } catch (e: unknown) {
      setErr(friendlyMessage(e, "Save failed"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="pw-drawer-form">
      <label>Event name *<input value={eventName} onChange={e => setEventName(e.target.value)} placeholder="e.g. Annual Inspection" /></label>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
        <label>Type
          <select value={eventType} onChange={e => setEventType(e.target.value)}>
            {ANCHOR_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
          </select>
        </label>
        <label>Importance
          <select value={importance} onChange={e => setImportance(e.target.value)}>
            {ANCHOR_IMPORTANCE.map(i => <option key={i} value={i}>{i.replace(/_/g, " ")}</option>)}
          </select>
        </label>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
        <label>Start date *<input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} /></label>
        <label>End date<input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} /></label>
      </div>
      <div>
        <div style={{ fontSize: 11, fontWeight: 700, color: "var(--muted-text)", marginBottom: 6 }}>Audience</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {AUDIENCE_FIELDS.map(({ key, label }) => (
            <label key={key} style={{ display: "flex", gap: 5, alignItems: "center", fontSize: 12, fontWeight: 400 }}>
              <input type="checkbox" checked={audience[key as keyof typeof audience]} onChange={e => setAudience(prev => ({ ...prev, [key]: e.target.checked }))} />
              {label}
            </label>
          ))}
        </div>
      </div>
      <label>Planning impact<input value={planningImpact} onChange={e => setPlanningImpact(e.target.value)} placeholder="e.g. No parade night that week" /></label>
      <label>Notes<textarea value={notes} onChange={e => setNotes(e.target.value)} placeholder="Additional context" /></label>
      {err && <div className="pw-err">{err}</div>}
      <div className="pw-drawer-actions" style={{ marginTop: 14 }}>
        <button className="btn primary" onClick={handleSave} disabled={saving}>{saving ? "Saving…" : "Add anchor event"}</button>
      </div>
    </div>
  );
}

// ─── Create / edit location form ───────────────────────────────────────────────
const LOCATION_TYPES = ["indoor", "outdoor", "gym", "classroom", "range", "hangar", "other"] as const;

function LocationForm({ location, onClose }: {
  location?: PlanningLocation;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [name, setName] = useState(location?.name ?? "");
  const [locType, setLocType] = useState(location?.location_type ?? "indoor");
  const [capacity, setCapacity] = useState(location?.capacity?.toString() ?? "");
  const [active, setActive] = useState(location?.active_status ?? true);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function handleSave() {
    if (!name.trim()) { setErr("Name is required."); return; }
    setSaving(true); setErr(null);
    try {
      if (location) {
        await planningApi.updateLocation(location.location_id, {
          name: name.trim(), location_type: locType,
          capacity: capacity ? Number(capacity) : undefined,
          active_status: active,
        });
      } else {
        await planningApi.createLocation({
          name: name.trim(), location_type: locType,
          capacity: capacity ? Number(capacity) : undefined,
        });
      }
      await qc.invalidateQueries({ queryKey: ["planning-locations"] });
      onClose();
    } catch (e: unknown) {
      setErr(friendlyMessage(e, "Save failed"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="pw-drawer-form">
      <label>Name *<input value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Main Classroom" /></label>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
        <label>Type
          <select value={locType} onChange={e => setLocType(e.target.value)}>
            {LOCATION_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </label>
        <label>Capacity<input type="number" min={1} value={capacity} onChange={e => setCapacity(e.target.value)} placeholder="—" /></label>
      </div>
      {location && (
        <label style={{ display: "flex", gap: 8, alignItems: "center", fontWeight: 400 }}>
          <input type="checkbox" checked={active} onChange={e => setActive(e.target.checked)} />
          Active
        </label>
      )}
      {err && <div className="pw-err">{err}</div>}
      <div className="pw-drawer-actions" style={{ marginTop: 14 }}>
        <button className="btn primary" onClick={handleSave} disabled={saving}>
          {saving ? "Saving…" : location ? "Save changes" : "Add location"}
        </button>
      </div>
    </div>
  );
}

// ─── Schedule from Backlog panel ──────────────────────────────────────────────

const CADET_GROUP_LABELS: Record<string, string> = {
  orientation: "Orientation",
  initial: "Initial",
  junior: "Junior",
  intermediate: "Intermediate",
  senior: "Senior",
};

function ScheduleFromBacklogPanel({
  curriculum, yearId, facilitators, locations, onClose,
}: {
  curriculum: { curriculum_id: string; code: string; title: string; phase: string };
  yearId: string;
  facilitators: PlanningFacilitator[];
  locations: PlanningLocation[];
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [dateId, setDateId] = useState("");
  const [period, setPeriod] = useState(1);
  const [cadetGroup, setCadetGroup] = useState("junior");
  const [facilitatorId, setFacilitatorId] = useState("");
  const [locationId, setLocationId] = useState("");
  const [partNumber, setPartNumber] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const { data: missionsData } = useQuery({
    queryKey: ["planning-missions", yearId],
    queryFn: () => planningApi.missions(yearId!),
    enabled: !!yearId,
  });
  const { data: nightData } = useQuery({
    queryKey: ["planning-night-summaries", yearId],
    queryFn: () => planningApi.nightSummaries(yearId!),
    enabled: !!yearId,
    staleTime: 2 * 60 * 1000,
  });

  const allMissions: MissionItem[] = missionsData?.missions ?? [];
  const mission = allMissions.find(m => m.curriculum_id === curriculum.curriculum_id);
  const summaries = nightData?.summaries ?? [];

  async function handleSave() {
    if (!dateId) { setErr("Select a parade night."); return; }
    setSaving(true); setErr(null);
    try {
      await planningApi.createSession(dateId, {
        cadet_group: cadetGroup,
        session_number: period,
        curriculum_id: curriculum.curriculum_id,
        facilitator_id: facilitatorId || undefined,
        location_id: locationId || undefined,
        part_number: partNumber ? Number(partNumber) : undefined,
        notes: notes || undefined,
      });
      await qc.invalidateQueries({ queryKey: ["planning-missions", yearId] });
      await qc.invalidateQueries({ queryKey: ["planning-night-summaries", yearId] });
      setSuccess(true);
    } catch (e: unknown) {
      setErr(friendlyMessage(e, "Save failed"));
    } finally {
      setSaving(false);
    }
  }

  if (success) {
    return (
      <div>
        <div style={{ color: "var(--success)", fontWeight: 700, fontSize: 14, marginBottom: 10 }}>
          Session scheduled successfully.
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn sm primary" onClick={() => { setSuccess(false); setDateId(""); }}>Schedule again</button>
          <button className="btn sm out" onClick={onClose}>Close</button>
        </div>
      </div>
    );
  }

  return (
    <div>
      {/* Mission detail */}
      <div className="pw-drawer-section">
        <div className="pw-drawer-label">Code</div>
        <div className="pw-drawer-value">{curriculum.code}</div>
      </div>
      <div className="pw-drawer-section">
        <div className="pw-drawer-label">Phase</div>
        <div className="pw-drawer-value">{curriculum.phase}</div>
      </div>
      {mission && (
        <>
          {mission.element && (
            <div className="pw-drawer-section">
              <div className="pw-drawer-label">Element</div>
              <div className="pw-drawer-value">{mission.element}</div>
            </div>
          )}
          <div className="pw-drawer-section">
            <div className="pw-drawer-label">Duration</div>
            <div className="pw-drawer-value">{mission.duration_minutes} min</div>
          </div>
          <div className="pw-drawer-section">
            <div className="pw-drawer-label">Program type</div>
            <div className="pw-drawer-value" style={{ textTransform: "capitalize" }}>
              {getProgramType(mission.phase)}
            </div>
          </div>
          {mission.instructor_suitability && (
            <div className="pw-drawer-section">
              <div className="pw-drawer-label">Instructor suitability</div>
              <div className="pw-drawer-value">{mission.instructor_suitability}</div>
            </div>
          )}
          {mission.part_count && mission.part_count > 1 && (
            <div className="pw-drawer-section">
              <div className="pw-drawer-label">Parts</div>
              <div className="pw-drawer-value">{mission.part_count} parts</div>
            </div>
          )}
          {mission.scheduled_sessions.length > 0 && (
            <div className="pw-drawer-section">
              <div className="pw-drawer-label" style={{ marginBottom: 4 }}>Already scheduled</div>
              {mission.scheduled_sessions.map(ss => (
                <div key={ss.session_id} style={{ fontSize: 11, marginBottom: 2, color: "var(--muted-text)" }}>
                  {ss.parade_date} · P{ss.session_number} · {ss.cadet_group ?? "—"}
                  {ss.facilitator_name ? ` · ${ss.facilitator_name}` : ""}
                </div>
              ))}
            </div>
          )}
        </>
      )}

      <div style={{ borderTop: "1px solid var(--border)", margin: "12px 0", paddingTop: 12 }}>
        <div style={{ fontSize: 11, fontWeight: 800, color: "var(--aafc-dark-blue)", marginBottom: 10 }}>
          Schedule this mission
        </div>
        <div className="pw-drawer-form">
          <label>
            Parade night *
            <select value={dateId} onChange={e => setDateId(e.target.value)}>
              <option value="">— Select night —</option>
              {summaries.map(s => (
                <option key={s.parade_date_id} value={s.parade_date_id}>
                  {s.parade_date}{s.term ? ` (${s.term})` : ""}
                </option>
              ))}
            </select>
          </label>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            <label>
              Period
              <select value={period} onChange={e => setPeriod(Number(e.target.value))}>
                <option value={1}>P1</option>
                <option value={2}>P2</option>
                <option value={3}>P3</option>
              </select>
            </label>
            {mission?.part_count && mission.part_count > 1 && (
              <label>
                Part #
                <input type="number" min={1} max={mission.part_count} value={partNumber}
                  onChange={e => setPartNumber(e.target.value)} placeholder="—" />
              </label>
            )}
          </div>
          <label>
            Cadet group
            <select value={cadetGroup} onChange={e => setCadetGroup(e.target.value)}>
              {Object.entries(CADET_GROUP_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </label>
          <label>
            Facilitator
            <select value={facilitatorId} onChange={e => setFacilitatorId(e.target.value)}>
              <option value="">— None —</option>
              {facilitators.map(f => (
                <option key={f.facilitator_id} value={f.facilitator_id}>{f.display_name}</option>
              ))}
            </select>
          </label>
          <label>
            Room / Location
            <select value={locationId} onChange={e => setLocationId(e.target.value)}>
              <option value="">— None —</option>
              {locations.map(l => (
                <option key={l.location_id} value={l.location_id}>{l.name}</option>
              ))}
            </select>
          </label>
          <label>
            Notes
            <textarea value={notes} onChange={e => setNotes(e.target.value)} placeholder="Optional notes" />
          </label>
        </div>
        {err && <div className="pw-err" style={{ marginTop: 8 }}>{err}</div>}
        <div className="pw-drawer-actions" style={{ marginTop: 14 }}>
          <button className="btn primary" onClick={handleSave} disabled={saving}>
            {saving ? "Scheduling…" : "Schedule session"}
          </button>
        </div>
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
    : item.type === "session-by-id" ? "Session"
    : item.type === "new-session" ? "Add Session"
    : item.type === "wing-event" ? item.event.title
    : item.type === "new-anchor" ? "New Anchor Event"
    : item.type === "anchor" ? item.anchor.event_name
    : item.type === "new-location" ? (item.location ? `Edit: ${item.location.name}` : "Add Location")
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
        {item.type === "session-by-id" && (
          <SessionByIdLoader sessionId={item.sessionId} dateId={item.dateId} date={item.date}
            facilitators={facilitators} locations={locations} yearId={yearId} onClose={onClose} />
        )}
        {item.type === "wing-event" && (
          <WingEventPanel event={item.event} onClose={onClose} />
        )}
        {item.type === "new-anchor" && (
          <CreateAnchorForm yearId={item.yearId} onClose={onClose} />
        )}
        {item.type === "anchor" && (
          <ActivityFullDetail activity={anchorToDisplay(item.anchor)} />
        )}
        {item.type === "new-location" && (
          <LocationForm location={item.location} onClose={onClose} />
        )}
        {item.type === "curriculum" && (
          <ScheduleFromBacklogPanel
            curriculum={item.curriculum}
            yearId={yearId!}
            facilitators={facilitators}
            locations={locations}
            onClose={onClose}
          />
        )}
      </div>
    </div>
  );
}

function SessionByIdLoader({ sessionId, dateId, date, facilitators, locations, yearId, onClose }: {
  sessionId: string; dateId: string; date: string;
  facilitators: PlanningFacilitator[]; locations: PlanningLocation[];
  yearId: string | null; onClose: () => void;
}) {
  const q = useQuery({
    queryKey: ["planning-session", sessionId],
    queryFn: () => planningApi.getSession(sessionId),
  });
  if (q.isLoading) return <p className="muted">Loading session…</p>;
  if (!q.data) return <p className="muted">Session not found.</p>;
  const item: DrawerItem = { type: "session", session: q.data, dateId, date, conflicts: [] };
  return <SessionForm item={item} facilitators={facilitators} locations={locations} yearId={yearId} onClose={onClose} />;
}
