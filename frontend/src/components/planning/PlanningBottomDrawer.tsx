import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { planningApi } from "../../api";
import type {
  PlanningFacilitator, PlanningLocation,
  PlanningFacilitatorLeave, FacilitatorWorkload, EquipmentItem,
} from "../../api/types";
import type { DrawerItem } from "./PlanningRightDrawer";

export type BottomTab =
  | "backlog"
  | "facilitators"
  | "rooms"
  | "equipment"
  | "holidays"
  | "notices"
  | "activities"
  | "import-review";

interface Props {
  yearId: string | null;
  tab: BottomTab;
  onTabChange: (t: BottomTab) => void;
  onClose: () => void;
  facilitators: PlanningFacilitator[];
  locations: PlanningLocation[];
  onItemClick: (item: DrawerItem) => void;
}

const TABS: { key: BottomTab; label: string }[] = [
  { key: "backlog", label: "Mission Backlog" },
  { key: "facilitators", label: "Facilitators" },
  { key: "rooms", label: "Rooms" },
  { key: "equipment", label: "Equipment" },
  { key: "holidays", label: "Holidays" },
  { key: "notices", label: "Notices" },
  { key: "activities", label: "Activities" },
  { key: "import-review", label: "Import Review" },
];

// ─── Styles helpers ───────────────────────────────────────────────────────────

const inputSx: React.CSSProperties = {
  padding: "5px 8px", borderRadius: 6,
  border: "1.5px solid var(--border)", fontSize: 12, width: "100%",
};
const labelSx: React.CSSProperties = {
  fontSize: 12, fontWeight: 700,
  display: "flex", flexDirection: "column", gap: 4,
};

// ─── BacklogContent ───────────────────────────────────────────────────────────

function BacklogContent({ yearId, onItemClick }: { yearId: string; onItemClick: (item: DrawerItem) => void }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["planning-missions", yearId],
    queryFn: () => planningApi.missions(yearId, { status: "unscheduled" }),
  });

  if (isLoading) return <div className="pw-loading" style={{ padding: "20px" }}>Loading missions…</div>;
  if (error || !data) return <div className="pw-err">Failed to load missions.</div>;

  const unscheduled = data.missions.filter(m => !m.is_scheduled);

  if (unscheduled.length === 0) {
    return <div className="pw-empty" style={{ padding: "20px" }}>All required curriculum is scheduled.</div>;
  }

  return (
    <div className="pw-backlog-grid">
      {unscheduled.map((m) => (
        <div
          key={m.curriculum_id}
          className="pw-backlog-card"
          onClick={() => onItemClick({ type: "curriculum", curriculum: { curriculum_id: m.curriculum_id, code: m.code, title: m.title, phase: m.phase } })}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => e.key === "Enter" && onItemClick({ type: "curriculum", curriculum: { curriculum_id: m.curriculum_id, code: m.code, title: m.title, phase: m.phase } })}
        >
          <div className="pw-backlog-card-code">{m.code}</div>
          <div className="pw-backlog-card-title">{m.title}</div>
          <div className="pw-backlog-card-meta">
            Phase {m.phase}{m.element ? ` · ${m.element}` : ""}{m.recommended_term ? ` · Term ${m.recommended_term}` : ""}
          </div>
          {m.core_status === "core" && (
            <span style={{ fontSize: 10, fontWeight: 700, color: "var(--aafc-red)", marginTop: 2, display: "block" }}>CORE</span>
          )}
        </div>
      ))}
    </div>
  );
}

// ─── FacilitatorLeaveSection ──────────────────────────────────────────────────

function FacilitatorLeaveSection({
  fac_id, yearId,
}: { fac_id: string; yearId: string | null }) {
  const qc = useQueryClient();
  const [addingLeave, setAddingLeave] = useState(false);
  const [leaveStart, setLeaveStart] = useState("");
  const [leaveEnd, setLeaveEnd] = useState("");
  const [leaveReason, setLeaveReason] = useState("");
  const [leaveNotes, setLeaveNotes] = useState("");
  const [leaveSaving, setLeaveSaving] = useState(false);
  const [leaveErr, setLeaveErr] = useState<string | null>(null);
  const [leaveWarning, setLeaveWarning] = useState<string | null>(null);
  const [deletingLeaveId, setDeletingLeaveId] = useState<string | null>(null);

  const { data: leaveData, isLoading: leaveLoading } = useQuery({
    queryKey: ["fac-leave", fac_id],
    queryFn: () => planningApi.facilitatorLeave(fac_id),
  });

  const { data: workload, isLoading: workloadLoading } = useQuery({
    queryKey: ["fac-workload", yearId, fac_id],
    queryFn: () => planningApi.facilitatorWorkload(yearId!, fac_id),
    enabled: !!yearId,
  });

  async function handleAddLeave() {
    if (!leaveStart || !leaveEnd) { setLeaveErr("Start and end dates required."); return; }
    if (leaveEnd < leaveStart) { setLeaveErr("End must be on or after start."); return; }
    setLeaveSaving(true); setLeaveErr(null); setLeaveWarning(null);
    try {
      const res = await planningApi.addFacilitatorLeave(fac_id, {
        start_date: leaveStart, end_date: leaveEnd,
        reason: leaveReason || undefined, notes: leaveNotes || undefined,
      });
      await qc.invalidateQueries({ queryKey: ["fac-leave", fac_id] });
      if (res.affected_sessions.length > 0) {
        setLeaveWarning(
          `Leave added. Warning: ${res.affected_sessions.length} session(s) currently scheduled during this period for this facilitator.`
        );
      }
      setLeaveStart(""); setLeaveEnd(""); setLeaveReason(""); setLeaveNotes("");
      setAddingLeave(false);
    } catch (e: unknown) {
      setLeaveErr(e instanceof Error ? e.message : "Failed to add leave");
    } finally {
      setLeaveSaving(false);
    }
  }

  async function handleDeleteLeave(leave_id: string) {
    if (!window.confirm("Remove this leave period?")) return;
    setDeletingLeaveId(leave_id);
    try {
      await planningApi.deleteFacilitatorLeave(leave_id);
      await qc.invalidateQueries({ queryKey: ["fac-leave", fac_id] });
    } finally {
      setDeletingLeaveId(null);
    }
  }

  const leave: PlanningFacilitatorLeave[] = leaveData?.leave ?? [];
  const wl: FacilitatorWorkload | undefined = workload;

  return (
    <div style={{ padding: "10px 14px", background: "var(--surface-alt, #f8fafd)", borderTop: "1px solid var(--border)" }}>
      {/* Workload Stats */}
      {yearId && (
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "var(--aafc-dark-blue)", marginBottom: 6 }}>
            Workload (current year)
          </div>
          {workloadLoading ? (
            <div style={{ fontSize: 11, color: "var(--muted-text)" }}>Loading…</div>
          ) : wl ? (
            <div style={{ display: "flex", gap: 14, fontSize: 11, flexWrap: "wrap" }}>
              <span><strong>{wl.total_scheduled}</strong> sessions total</span>
              <span><strong>{wl.nights_with_sessions}</strong> nights</span>
              <span>avg <strong>{wl.avg_per_night}</strong>/night</span>
              <span>max <strong>{wl.max_per_night}</strong>, min <strong>{wl.min_per_night}</strong></span>
            </div>
          ) : (
            <div style={{ fontSize: 11, color: "var(--muted-text)" }}>No workload data.</div>
          )}

          {/* Upcoming sessions */}
          {wl && wl.upcoming_sessions.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <div style={{ fontSize: 11, fontWeight: 600, marginBottom: 4 }}>Upcoming sessions</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                {wl.upcoming_sessions.slice(0, 5).map(s => (
                  <div key={s.session_id} style={{ fontSize: 11, display: "flex", gap: 8, color: "var(--text)" }}>
                    <span style={{ color: "var(--aafc-dark-blue)", fontWeight: 600 }}>{s.parade_date}</span>
                    <span>{s.title ?? "—"}</span>
                    {s.cadet_group && <span style={{ color: "var(--muted-text)" }}>{s.cadet_group}</span>}
                    {s.location_name && <span style={{ color: "var(--muted-text)" }}>{s.location_name}</span>}
                  </div>
                ))}
                {wl.upcoming_sessions.length > 5 && (
                  <div style={{ fontSize: 10, color: "var(--muted-text)" }}>+{wl.upcoming_sessions.length - 5} more</div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Leave Periods */}
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "var(--aafc-dark-blue)" }}>Leave / Unavailability</div>
          {!addingLeave && (
            <button className="btn sm out" style={{ fontSize: 11, padding: "2px 8px" }} onClick={() => setAddingLeave(true)}>
              + Add Leave
            </button>
          )}
        </div>

        {leaveWarning && (
          <div style={{ fontSize: 11, color: "var(--warning)", background: "#fff8e6", border: "1px solid var(--warning)", borderRadius: 6, padding: "6px 10px", marginBottom: 6 }}>
            {leaveWarning}
          </div>
        )}

        {addingLeave && (
          <div style={{ background: "#fff", border: "1px solid var(--border)", borderRadius: 8, padding: "10px 12px", marginBottom: 8 }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 8 }}>
              <label style={labelSx}>
                Start *
                <input type="date" value={leaveStart} onChange={e => setLeaveStart(e.target.value)} style={inputSx} />
              </label>
              <label style={labelSx}>
                End *
                <input type="date" value={leaveEnd} onChange={e => setLeaveEnd(e.target.value)} style={inputSx} />
              </label>
              <label style={{ ...labelSx, gridColumn: "1/-1" }}>
                Reason
                <input value={leaveReason} onChange={e => setLeaveReason(e.target.value)} placeholder="e.g. Medical, Personal, Course" style={inputSx} />
              </label>
              <label style={{ ...labelSx, gridColumn: "1/-1" }}>
                Notes
                <input value={leaveNotes} onChange={e => setLeaveNotes(e.target.value)} placeholder="Optional additional notes" style={inputSx} />
              </label>
            </div>
            {leaveErr && <div style={{ color: "var(--aafc-red)", fontSize: 12, marginBottom: 6 }}>{leaveErr}</div>}
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn sm primary" onClick={handleAddLeave} disabled={leaveSaving}>
                {leaveSaving ? "Saving…" : "Add leave"}
              </button>
              <button className="btn sm out" onClick={() => { setAddingLeave(false); setLeaveErr(null); }}>Cancel</button>
            </div>
          </div>
        )}

        {leaveLoading ? (
          <div style={{ fontSize: 11, color: "var(--muted-text)" }}>Loading leave…</div>
        ) : leave.length === 0 ? (
          <div style={{ fontSize: 11, color: "var(--muted-text)" }}>No leave recorded.</div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {leave.map(l => (
              <div key={l.id} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 11, background: "#fff", border: "1px solid var(--border)", borderRadius: 6, padding: "5px 10px" }}>
                <span style={{ fontWeight: 600, color: "var(--aafc-dark-blue)" }}>
                  {l.start_date}{l.end_date !== l.start_date ? ` → ${l.end_date}` : ""}
                </span>
                {l.reason && <span style={{ color: "var(--muted-text)" }}>{l.reason}</span>}
                <button
                  className="btn sm out"
                  style={{ marginLeft: "auto", fontSize: 10, padding: "2px 7px", color: "var(--aafc-red)" }}
                  onClick={() => handleDeleteLeave(l.id)}
                  disabled={deletingLeaveId === l.id}
                >
                  {deletingLeaveId === l.id ? "…" : "Remove"}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── FacilitatorsContent ─────────────────────────────────────────────────────

function FacilitatorsContent({
  yearId,
  facilitators,
}: { yearId: string | null; facilitators: PlanningFacilitator[] }) {
  const qc = useQueryClient();
  const [selectedFacId, setSelectedFacId] = useState<string | null>(null);
  const [addingFac, setAddingFac] = useState(false);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [rank, setRank] = useState("");
  const [facType, setFacType] = useState("officer");
  const [subjectAreas, setSubjectAreas] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function handleAddFac() {
    if (!firstName.trim() || !lastName.trim()) { setErr("First and last name are required."); return; }
    setSaving(true); setErr(null);
    try {
      await planningApi.createFacilitator({
        first_name: firstName.trim(), last_name: lastName.trim(),
        current_rank: rank.trim() || undefined,
        type: facType || undefined,
        subject_areas: subjectAreas ? subjectAreas.split(",").map(s => s.trim()).filter(Boolean) : undefined,
      });
      await qc.invalidateQueries({ queryKey: ["planning-facilitators"] });
      setFirstName(""); setLastName(""); setRank(""); setFacType("officer"); setSubjectAreas("");
      setAddingFac(false);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed to create facilitator");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <div style={{ padding: "8px 14px 0", display: "flex", justifyContent: "flex-end" }}>
        {!addingFac && (
          <button className="btn sm primary" onClick={() => setAddingFac(true)}>+ Add Facilitator</button>
        )}
      </div>

      {addingFac && (
        <div style={{ padding: "10px 14px", background: "var(--surface)", borderBottom: "1px solid var(--border)" }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginBottom: 8 }}>
            <label style={labelSx}>
              First name *
              <input value={firstName} onChange={e => setFirstName(e.target.value)} style={inputSx} autoFocus />
            </label>
            <label style={labelSx}>
              Last name *
              <input value={lastName} onChange={e => setLastName(e.target.value)} style={inputSx} />
            </label>
            <label style={labelSx}>
              Rank
              <input value={rank} onChange={e => setRank(e.target.value)} placeholder="e.g. Capt, WO2" style={inputSx} />
            </label>
            <label style={labelSx}>
              Type
              <select value={facType} onChange={e => setFacType(e.target.value)} style={inputSx}>
                <option value="officer">Officer</option>
                <option value="nco">NCO</option>
                <option value="civcpersonal">Civ Instructor</option>
                <option value="guest">Guest</option>
              </select>
            </label>
            <label style={{ ...labelSx, gridColumn: "2 / -1" }}>
              Subject areas (comma-separated)
              <input value={subjectAreas} onChange={e => setSubjectAreas(e.target.value)} placeholder="e.g. Aviation, Leadership" style={inputSx} />
            </label>
          </div>
          {err && <div style={{ color: "var(--aafc-red)", fontSize: 12, marginBottom: 6 }}>{err}</div>}
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn sm primary" onClick={handleAddFac} disabled={saving}>{saving ? "Saving…" : "Add facilitator"}</button>
            <button className="btn sm out" onClick={() => { setAddingFac(false); setErr(null); }}>Cancel</button>
          </div>
        </div>
      )}

      {facilitators.length === 0 && !addingFac ? (
        <div className="pw-empty" style={{ padding: "20px" }}>No facilitators on record.</div>
      ) : (
        <>
          <table className="pw-fac-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Subject areas</th>
                <th>Max sessions/night</th>
              </tr>
            </thead>
            <tbody>
              {facilitators.map((f) => {
                const isSelected = selectedFacId === f.facilitator_id;
                return (
                  <tr
                    key={f.facilitator_id}
                    style={{ cursor: "pointer", background: isSelected ? "#EEF4FB" : undefined }}
                    onClick={() => setSelectedFacId(isSelected ? null : f.facilitator_id)}
                  >
                    <td style={{ fontWeight: 600, color: "var(--aafc-dark-blue)" }}>
                      {f.display_name}
                      {f.rank && <span style={{ fontWeight: 400, color: "var(--muted-text)", fontSize: 11, marginLeft: 4 }}>{f.rank}</span>}
                    </td>
                    <td style={{ textTransform: "capitalize" }}>{f.type}</td>
                    <td style={{ fontSize: 11 }}>{f.subject_areas.join(", ") || "—"}</td>
                    <td style={{ textAlign: "center" }}>{f.max_sessions_per_night}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {/* Expanded facilitator profile panel */}
          {selectedFacId && (
            <FacilitatorLeaveSection
              key={selectedFacId}
              fac_id={selectedFacId}
              yearId={yearId}
            />
          )}
        </>
      )}
    </div>
  );
}

// ─── RoomsContent ─────────────────────────────────────────────────────────────

function RoomsContent({ locations, onAddLocation, onEditLocation }: {
  locations: PlanningLocation[];
  onAddLocation: () => void;
  onEditLocation: (loc: PlanningLocation) => void;
}) {
  return (
    <div>
      <div style={{ padding: "8px 14px 0", display: "flex", justifyContent: "flex-end" }}>
        <button className="btn sm primary" onClick={onAddLocation}>+ Add Room</button>
      </div>
      {locations.length === 0 ? (
        <div className="pw-empty" style={{ padding: "20px" }}>No rooms on record. Add one to start assigning sessions to rooms.</div>
      ) : (
        <table className="pw-fac-table">
          <thead>
            <tr>
              <th>Room</th>
              <th>Type</th>
              <th>Capacity</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {locations.map((l) => (
              <tr key={l.location_id}>
                <td>{l.name}</td>
                <td style={{ textTransform: "capitalize" }}>{l.location_type}</td>
                <td style={{ textAlign: "center" }}>{l.capacity ?? "—"}</td>
                <td>
                  <span style={{ fontSize: 11, fontWeight: 700, color: l.active_status ? "var(--success)" : "var(--muted-text)" }}>
                    {l.active_status ? "Active" : "Inactive"}
                  </span>
                </td>
                <td>
                  <button className="btn sm out" style={{ fontSize: 11, padding: "3px 8px" }} onClick={() => onEditLocation(l)}>Edit</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ─── EquipmentContent ─────────────────────────────────────────────────────────

function EquipmentContent() {
  const qc = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [type, setType] = useState("");
  const [qty, setQty] = useState("");
  const [availQty, setAvailQty] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const { data: items = [], isLoading } = useQuery<EquipmentItem[]>({
    queryKey: ["planning-equipment"],
    queryFn: () => planningApi.listEquipment(),
  });

  function resetForm() {
    setName(""); setType(""); setQty(""); setAvailQty(""); setNotes("");
    setErr(null); setAdding(false);
  }

  async function handleAdd() {
    if (!name.trim()) { setErr("Name is required."); return; }
    setSaving(true); setErr(null);
    try {
      await planningApi.addEquipment({
        name: name.trim(),
        type: type.trim() || undefined,
        quantity: qty ? parseInt(qty, 10) : undefined,
        available_quantity: availQty ? parseInt(availQty, 10) : undefined,
        notes: notes.trim() || undefined,
      });
      await qc.invalidateQueries({ queryKey: ["planning-equipment"] });
      resetForm();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed to add equipment");
    } finally {
      setSaving(false);
    }
  }

  if (isLoading) return <div className="pw-loading" style={{ padding: "20px" }}>Loading equipment…</div>;

  return (
    <div>
      <div style={{ padding: "8px 14px 0", display: "flex", justifyContent: "flex-end" }}>
        {!adding && (
          <button className="btn sm primary" onClick={() => setAdding(true)}>+ Add Equipment</button>
        )}
      </div>

      {adding && (
        <div style={{ padding: "10px 14px", background: "var(--surface)", borderBottom: "1px solid var(--border)" }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 8, marginBottom: 8 }}>
            <label style={{ ...labelSx, gridColumn: "1 / 3" }}>
              Name *
              <input value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Projector" autoFocus style={inputSx} />
            </label>
            <label style={labelSx}>
              Type
              <input value={type} onChange={e => setType(e.target.value)} placeholder="e.g. AV" style={inputSx} />
            </label>
            <label style={labelSx}>
              Qty
              <input type="number" min="0" value={qty} onChange={e => setQty(e.target.value)} style={inputSx} />
            </label>
            <label style={labelSx}>
              Available qty
              <input type="number" min="0" value={availQty} onChange={e => setAvailQty(e.target.value)} style={inputSx} />
            </label>
            <label style={{ ...labelSx, gridColumn: "2 / -1" }}>
              Notes
              <input value={notes} onChange={e => setNotes(e.target.value)} style={inputSx} />
            </label>
          </div>
          {err && <div style={{ color: "var(--aafc-red)", fontSize: 12, marginBottom: 6 }}>{err}</div>}
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn sm primary" onClick={handleAdd} disabled={saving}>{saving ? "Saving…" : "Add equipment"}</button>
            <button className="btn sm out" onClick={resetForm}>Cancel</button>
          </div>
        </div>
      )}

      {items.length === 0 && !adding ? (
        <div className="pw-empty" style={{ padding: "20px" }}>No equipment on record.</div>
      ) : (
        <table className="pw-fac-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Qty</th>
              <th>Available</th>
              <th>Condition</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.equipment_id}>
                <td style={{ fontWeight: 600 }}>{item.name}</td>
                <td style={{ textTransform: "capitalize" }}>{item.type ?? "—"}</td>
                <td style={{ textAlign: "center" }}>{item.quantity}</td>
                <td style={{ textAlign: "center" }}>
                  <span style={{
                    fontWeight: 700,
                    color: item.available_quantity > 0 ? "var(--success)" : "var(--aafc-red)",
                  }}>
                    {item.available_quantity}
                  </span>
                </td>
                <td style={{ fontSize: 11, textTransform: "capitalize" }}>
                  {item.condition ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ─── HolidaysContent ──────────────────────────────────────────────────────────

const HOLIDAY_TYPES = [
  { value: "school_holiday", label: "School holiday" },
  { value: "statutory", label: "Statutory / public holiday" },
  { value: "civic", label: "Civic holiday" },
  { value: "training_stand_down", label: "Training stand-down" },
  { value: "other", label: "Other" },
];

function HolidaysContent({ yearId }: { yearId: string }) {
  const qc = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [holidayType, setHolidayType] = useState("school_holiday");
  const [affectsParade, setAffectsParade] = useState(true);
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const { data: holidays = [], isLoading } = useQuery({
    queryKey: ["planning-holidays", yearId],
    queryFn: () => planningApi.holidays(yearId),
  });

  function resetForm() {
    setName(""); setStartDate(""); setEndDate("");
    setHolidayType("school_holiday"); setAffectsParade(true);
    setNotes(""); setErr(null); setAdding(false);
  }

  async function handleAdd() {
    if (!name.trim()) { setErr("Name is required."); return; }
    if (!startDate || !endDate) { setErr("Start and end dates are required."); return; }
    if (endDate < startDate) { setErr("End date must be on or after start date."); return; }
    setSaving(true); setErr(null);
    try {
      await planningApi.createHoliday(yearId, {
        name: name.trim(), start_date: startDate, end_date: endDate,
        holiday_type: holidayType, affects_parade: affectsParade,
        notes: notes || undefined,
      });
      await qc.invalidateQueries({ queryKey: ["planning-holidays", yearId] });
      await qc.invalidateQueries({ queryKey: ["planning-annual"] });
      resetForm();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed to add holiday");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(holiday_id: string) {
    if (!window.confirm("Delete this holiday period?")) return;
    setDeletingId(holiday_id);
    try {
      await planningApi.deleteHoliday(holiday_id);
      await qc.invalidateQueries({ queryKey: ["planning-holidays", yearId] });
      await qc.invalidateQueries({ queryKey: ["planning-annual"] });
    } finally {
      setDeletingId(null);
    }
  }

  if (isLoading) return <div className="pw-loading" style={{ padding: "20px" }}>Loading holidays…</div>;

  return (
    <div>
      <div style={{ padding: "8px 14px 0", display: "flex", justifyContent: "flex-end" }}>
        {!adding && (
          <button className="btn sm primary" onClick={() => setAdding(true)}>+ Add Holiday Period</button>
        )}
      </div>

      {adding && (
        <div style={{ padding: "10px 14px", background: "var(--surface)", borderBottom: "1px solid var(--border)" }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginBottom: 8 }}>
            <label style={{ gridColumn: "1 / -1", fontSize: 12, fontWeight: 700, display: "flex", flexDirection: "column", gap: 4 }}>
              Name *
              <input
                value={name}
                onChange={e => setName(e.target.value)}
                placeholder="e.g. Spring Break"
                autoFocus
                style={{ fontWeight: 400, padding: "5px 8px", borderRadius: 6, border: "1.5px solid var(--border)", fontSize: 12 }}
              />
            </label>
            <label style={{ fontSize: 12, fontWeight: 700, display: "flex", flexDirection: "column", gap: 4 }}>
              Start *
              <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} style={{ padding: "5px 8px", borderRadius: 6, border: "1.5px solid var(--border)", fontSize: 12 }} />
            </label>
            <label style={{ fontSize: 12, fontWeight: 700, display: "flex", flexDirection: "column", gap: 4 }}>
              End *
              <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} style={{ padding: "5px 8px", borderRadius: 6, border: "1.5px solid var(--border)", fontSize: 12 }} />
            </label>
            <label style={{ fontSize: 12, fontWeight: 700, display: "flex", flexDirection: "column", gap: 4 }}>
              Type
              <select value={holidayType} onChange={e => setHolidayType(e.target.value)} style={{ padding: "5px 8px", borderRadius: 6, border: "1.5px solid var(--border)", fontSize: 12 }}>
                {HOLIDAY_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </label>
          </div>
          <label style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 12, marginBottom: 8 }}>
            <input type="checkbox" checked={affectsParade} onChange={e => setAffectsParade(e.target.checked)} />
            Affects parade nights (stand-down)
          </label>
          {err && <div style={{ color: "var(--aafc-red)", fontSize: 12, marginBottom: 6 }}>{err}</div>}
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn sm primary" onClick={handleAdd} disabled={saving}>
              {saving ? "Saving…" : "Add holiday"}
            </button>
            <button className="btn sm out" onClick={resetForm}>Cancel</button>
          </div>
        </div>
      )}

      {holidays.length === 0 && !adding ? (
        <div className="pw-empty" style={{ padding: "20px" }}>
          No holiday periods defined. Add one to mark stand-downs on the calendar.
        </div>
      ) : (
        <table className="pw-fac-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Dates</th>
              <th>Type</th>
              <th>Stand-down</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {holidays.map(h => (
              <tr key={h.holiday_id}>
                <td style={{ fontWeight: 600 }}>{h.name}</td>
                <td style={{ fontSize: 11 }}>
                  {h.start_date}{h.end_date !== h.start_date ? ` → ${h.end_date}` : ""}
                </td>
                <td style={{ fontSize: 11, textTransform: "capitalize" }}>
                  {h.holiday_type.replace(/_/g, " ")}
                </td>
                <td style={{ textAlign: "center" }}>
                  <span style={{ fontWeight: 700, color: h.affects_parade ? "var(--warning)" : "var(--muted-text)" }}>
                    {h.affects_parade ? "Yes" : "No"}
                  </span>
                </td>
                <td>
                  <button
                    className="btn sm out"
                    style={{ fontSize: 11, padding: "3px 8px", color: "var(--aafc-red)" }}
                    onClick={() => handleDelete(h.holiday_id)}
                    disabled={deletingId === h.holiday_id}
                  >
                    {deletingId === h.holiday_id ? "…" : "Delete"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ─── NoticesContent ───────────────────────────────────────────────────────────

function NoticesContent({ yearId }: { yearId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["planning-cc", yearId],
    queryFn: () => planningApi.commandCentre(yearId),
  });

  if (isLoading) return <div className="pw-loading" style={{ padding: "20px" }}>Loading notices…</div>;

  const anchors = data?.upcoming_anchors ?? [];
  if (anchors.length === 0) {
    return <div className="pw-empty" style={{ padding: "20px" }}>No upcoming key notices.</div>;
  }

  return (
    <div className="pw-backlog-grid">
      {anchors.map((a, i) => (
        <div key={a.anchor_event_id ?? a.anchor_id ?? String(i)} className="pw-backlog-card">
          <div className="pw-backlog-card-code">{a.event_type}</div>
          <div className="pw-backlog-card-title">{a.event_name}</div>
          <div className="pw-backlog-card-meta">
            {a.start_date}{a.end_date && a.end_date !== a.start_date ? ` → ${a.end_date}` : ""}
            {a.planning_impact && ` · ${a.planning_impact}`}
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── ActivitiesContent ────────────────────────────────────────────────────────

const IMPORTANCE_LABELS: Record<string, string> = {
  must_attend: "Must Attend",
  key_event: "Key Event",
  weekly_parade: "Weekly Parade",
  optional: "Optional",
  noting: "Noting",
  irrelevant: "Irrelevant",
};

const STATUS_COLORS: Record<string, string> = {
  classified: "var(--aafc-dark-blue)",
  needs_review: "var(--warning)",
  irrelevant: "var(--muted-text)",
};

function ClassifyModal({
  activity,
  onSave,
  onClose,
}: {
  activity: import("../../api/types").CeaActivity;
  onSave: () => void;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [importance, setImportance] = useState(activity.importance ?? "");
  const [staffOnly, setStaffOnly] = useState(activity.audience_staff_only);
  const [seniors, setSeniors] = useState(activity.audience_seniors);
  const [proficient, setProficient] = useState(activity.audience_proficient);
  const [firstYears, setFirstYears] = useState(activity.audience_first_years);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function handleSave() {
    setSaving(true); setErr(null);
    try {
      await planningApi.ceaClassify(activity.id, {
        importance: importance || undefined,
        audience_staff_only: staffOnly,
        audience_seniors: seniors,
        audience_proficient: proficient,
        audience_first_years: firstYears,
      });
      await qc.invalidateQueries({ queryKey: ["cea-activities"] });
      onSave();
      onClose();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.4)", zIndex: 900, display: "flex", alignItems: "center", justifyContent: "center" }} onClick={onClose}>
      <div style={{ background: "#fff", borderRadius: 10, padding: 24, width: 420, maxWidth: "95vw" }} onClick={e => e.stopPropagation()}>
        <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>Classify Activity</div>
        <div style={{ fontSize: 12, color: "var(--muted-text)", marginBottom: 16 }}>{activity.activity_name}</div>

        <label style={{ fontSize: 12, fontWeight: 700, display: "block", marginBottom: 4 }}>Importance</label>
        <select
          value={importance}
          onChange={e => setImportance(e.target.value)}
          style={{ width: "100%", padding: "5px 8px", borderRadius: 6, border: "1.5px solid var(--border)", fontSize: 12, marginBottom: 14 }}
        >
          <option value="">— select —</option>
          {Object.entries(IMPORTANCE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>

        <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 6 }}>Audience</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 16 }}>
          {([
            ["Staff Only", staffOnly, setStaffOnly],
            ["Seniors (CFSGT–CUO)", seniors, setSeniors],
            ["Proficient (LCDT & CCPLS)", proficient, setProficient],
            ["First Years", firstYears, setFirstYears],
          ] as [string, boolean, (v: boolean) => void][]).map(([label, val, setter]) => (
            <label key={label} style={{ display: "flex", gap: 8, fontSize: 12, alignItems: "center", cursor: "pointer" }}>
              <input type="checkbox" checked={val} onChange={e => setter(e.target.checked)} />
              {label}
            </label>
          ))}
        </div>

        {err && <div style={{ fontSize: 11, color: "var(--aafc-red)", marginBottom: 8 }}>{err}</div>}
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button className="btn sm out" style={{ fontSize: 12 }} onClick={onClose}>Cancel</button>
          <button className="btn sm primary" style={{ fontSize: 12 }} onClick={handleSave} disabled={saving}>
            {saving ? "Saving…" : "Save classification"}
          </button>
        </div>
      </div>
    </div>
  );
}

function ActivitiesContent({ yearId }: { yearId: string }) {
  const qc = useQueryClient();
  const [classifying, setClassifying] = useState<import("../../api/types").CeaActivity | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newStart, setNewStart] = useState("");
  const [newEnd, setNewEnd] = useState("");
  const [newLocation, setNewLocation] = useState("");
  const [newImportance, setNewImportance] = useState("");
  const [creating, setCreating] = useState(false);
  const [filterStatus, setFilterStatus] = useState<string>("all");

  const { data: activities = [], isLoading } = useQuery({
    queryKey: ["cea-activities", yearId],
    queryFn: () => planningApi.ceaActivities(yearId),
    staleTime: 2 * 60 * 1000,
  });

  async function handleCreate() {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await planningApi.createManualActivity(yearId, {
        activity_name: newName.trim(),
        activity_start_date: newStart || undefined,
        activity_end_date: newEnd || undefined,
        location: newLocation || undefined,
        importance: newImportance || undefined,
      });
      await qc.invalidateQueries({ queryKey: ["cea-activities"] });
      setNewName(""); setNewStart(""); setNewEnd(""); setNewLocation(""); setNewImportance("");
      setShowCreate(false);
    } finally {
      setCreating(false);
    }
  }

  const filtered = activities.filter(a =>
    filterStatus === "all" ? true : a.classification_status === filterStatus,
  );

  if (isLoading) return <div className="pw-loading" style={{ padding: "20px" }}>Loading activities…</div>;

  return (
    <div style={{ padding: "10px 14px" }}>
      {/* Header toolbar */}
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12, flexWrap: "wrap" }}>
        <div style={{ fontWeight: 700, fontSize: 13, color: "var(--aafc-dark-blue)" }}>
          Activities ({activities.length})
        </div>
        <div style={{ display: "flex", gap: 4 }}>
          {[["all", "All"], ["needs_review", "Needs review"], ["classified", "Classified"]].map(([k, l]) => (
            <button
              key={k}
              onClick={() => setFilterStatus(k)}
              style={{
                fontSize: 11, padding: "3px 8px", borderRadius: 4, border: "1px solid var(--border)",
                background: filterStatus === k ? "var(--aafc-dark-blue)" : "#fff",
                color: filterStatus === k ? "#fff" : "var(--text)",
                cursor: "pointer",
              }}
            >{l}</button>
          ))}
        </div>
        <div style={{ marginLeft: "auto" }}>
          <button className="btn sm primary" style={{ fontSize: 11 }} onClick={() => setShowCreate(v => !v)}>
            + Add manual activity
          </button>
        </div>
      </div>

      {/* Manual create form */}
      {showCreate && (
        <div style={{ background: "#f0f5ff", border: "1px solid var(--border)", borderRadius: 8, padding: 12, marginBottom: 12, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          <div style={{ gridColumn: "1/-1" }}>
            <label style={{ fontSize: 11, fontWeight: 700 }}>Activity name *</label>
            <input value={newName} onChange={e => setNewName(e.target.value)} style={{ width: "100%", padding: "4px 8px", borderRadius: 4, border: "1px solid var(--border)", fontSize: 12, marginTop: 2 }} />
          </div>
          <div>
            <label style={{ fontSize: 11, fontWeight: 700 }}>Start date</label>
            <input type="date" value={newStart} onChange={e => setNewStart(e.target.value)} style={{ width: "100%", padding: "4px 8px", borderRadius: 4, border: "1px solid var(--border)", fontSize: 12, marginTop: 2 }} />
          </div>
          <div>
            <label style={{ fontSize: 11, fontWeight: 700 }}>End date</label>
            <input type="date" value={newEnd} onChange={e => setNewEnd(e.target.value)} style={{ width: "100%", padding: "4px 8px", borderRadius: 4, border: "1px solid var(--border)", fontSize: 12, marginTop: 2 }} />
          </div>
          <div>
            <label style={{ fontSize: 11, fontWeight: 700 }}>Location</label>
            <input value={newLocation} onChange={e => setNewLocation(e.target.value)} style={{ width: "100%", padding: "4px 8px", borderRadius: 4, border: "1px solid var(--border)", fontSize: 12, marginTop: 2 }} />
          </div>
          <div>
            <label style={{ fontSize: 11, fontWeight: 700 }}>Importance</label>
            <select value={newImportance} onChange={e => setNewImportance(e.target.value)} style={{ width: "100%", padding: "4px 8px", borderRadius: 4, border: "1px solid var(--border)", fontSize: 12, marginTop: 2 }}>
              <option value="">— select —</option>
              {Object.entries(IMPORTANCE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          <div style={{ gridColumn: "1/-1", display: "flex", gap: 8, justifyContent: "flex-end" }}>
            <button className="btn sm out" style={{ fontSize: 11 }} onClick={() => setShowCreate(false)}>Cancel</button>
            <button className="btn sm primary" style={{ fontSize: 11 }} onClick={handleCreate} disabled={creating || !newName.trim()}>
              {creating ? "Saving…" : "Save activity"}
            </button>
          </div>
        </div>
      )}

      {/* Activities table */}
      {filtered.length === 0 ? (
        <div className="pw-empty" style={{ padding: "20px" }}>No activities. Import a CEA file or create a manual activity.</div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table className="pw-fac-table" style={{ fontSize: 11, minWidth: 900 }}>
            <thead>
              <tr>
                <th>CEA ID</th>
                <th>Activity name</th>
                <th>Start date</th>
                <th>End date</th>
                <th>Source</th>
                <th>Parent unit</th>
                <th>Host unit</th>
                <th>Location</th>
                <th>POC</th>
                <th>Importance</th>
                <th>Audience</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(a => (
                <tr key={a.id} style={{ background: a.is_removed_from_cea ? "#fff3cd" : undefined }}>
                  <td style={{ color: "var(--muted-text)" }}>{a.cea_activity_id ?? "—"}</td>
                  <td style={{ fontWeight: 600 }}>
                    {a.activity_name}
                    {a.is_removed_from_cea && (
                      <span style={{ marginLeft: 4, fontSize: 10, color: "var(--warning)", fontWeight: 700 }}>[Not in latest import]</span>
                    )}
                  </td>
                  <td>{a.activity_start_date ?? "—"}</td>
                  <td>{a.activity_end_date ?? "—"}</td>
                  <td style={{ textTransform: "capitalize" }}>{a.source_type}</td>
                  <td style={{ color: "var(--muted-text)" }}>{a.parent_unit ?? "—"}</td>
                  <td>{a.host_unit ?? "—"}</td>
                  <td style={{ color: "var(--muted-text)" }}>{a.location ?? "—"}</td>
                  <td style={{ color: "var(--muted-text)" }}>{a.activity_poc ?? "—"}</td>
                  <td>
                    {a.importance
                      ? <span style={{ fontWeight: 600, color: "var(--aafc-dark-blue)" }}>{IMPORTANCE_LABELS[a.importance] ?? a.importance}</span>
                      : <span style={{ color: "var(--muted-text)" }}>—</span>}
                  </td>
                  <td style={{ fontSize: 10 }}>
                    {[
                      a.audience_staff_only && "Staff",
                      a.audience_seniors && "Seniors",
                      a.audience_proficient && "Proficient",
                      a.audience_first_years && "1st Yr",
                    ].filter(Boolean).join(", ") || "—"}
                  </td>
                  <td>
                    <span style={{ fontSize: 10, fontWeight: 700, color: STATUS_COLORS[a.classification_status] ?? "var(--muted-text)" }}>
                      {a.classification_status === "needs_review" ? "Needs review" : a.classification_status === "classified" ? "Classified" : a.classification_status}
                    </span>
                  </td>
                  <td>
                    <button
                      className="btn sm out"
                      style={{ fontSize: 10, padding: "2px 6px" }}
                      onClick={() => setClassifying(a)}
                    >
                      Classify
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {classifying && (
        <ClassifyModal
          activity={classifying}
          onSave={() => qc.invalidateQueries({ queryKey: ["cea-activities"] })}
          onClose={() => setClassifying(null)}
        />
      )}
    </div>
  );
}

// ─── ImportReviewContent ──────────────────────────────────────────────────────

function ImportReviewContent({ yearId }: { yearId: string }) {
  const qc = useQueryClient();
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<import("../../api/types").CeaImportResult | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const { data: batchData, isLoading: batchLoading } = useQuery({
    queryKey: ["cea-batches", yearId],
    queryFn: () => planningApi.ceaBatches(yearId),
    staleTime: 2 * 60 * 1000,
  });

  const batches = batchData?.batches ?? [];

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true); setErr(null); setResult(null);
    try {
      const res = await planningApi.ceaImport(yearId, file);
      setResult(res);
      await qc.invalidateQueries({ queryKey: ["cea-activities"] });
      await qc.invalidateQueries({ queryKey: ["cea-batches"] });
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Import failed");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  return (
    <div style={{ padding: "10px 14px" }}>
      {/* Import section */}
      <div style={{ background: "#f0f5ff", border: "1px solid var(--border)", borderRadius: 8, padding: 12, marginBottom: 14 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--aafc-dark-blue)", marginBottom: 6 }}>
          Import CEA CSV file
        </div>
        <div style={{ fontSize: 11, color: "var(--muted-text)", marginBottom: 10 }}>
          Supports full CEA export (StatusName, ActivityID, ActivityTypeName…) and simple export (SeqNr, Name, Start date…).
          Duplicate detection by ActivityID or activity name + date.
          Removed activities marked, not deleted.
        </div>
        <label style={{ display: "inline-flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
          <input
            type="file"
            accept=".csv,.txt"
            style={{ display: "none" }}
            onChange={handleFileChange}
            disabled={uploading}
          />
          <span className="btn sm primary" style={{ fontSize: 11, pointerEvents: "none" }}>
            {uploading ? "Importing…" : "Choose CSV file"}
          </span>
          <span style={{ fontSize: 11, color: "var(--muted-text)" }}>
            {uploading ? "Processing…" : "No file selected"}
          </span>
        </label>
        {err && <div style={{ fontSize: 11, color: "var(--aafc-red)", marginTop: 8 }}>{err}</div>}
      </div>

      {/* Import result */}
      {result && (
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 8 }}>
            Import complete —{" "}
            <span style={{ color: "var(--aafc-dark-blue)" }}>{result.created} new</span>,{" "}
            <span style={{ color: "#1A7F4B" }}>{result.updated} updated</span>,{" "}
            <span style={{ color: "var(--warning)" }}>{result.duplicates} duplicates</span>,{" "}
            <span style={{ color: "var(--muted-text)" }}>{result.skipped} skipped</span>
            {result.errors > 0 && <span style={{ color: "var(--aafc-red)" }}>, {result.errors} errors</span>}
          </div>

          {result.preview.length > 0 && (
            <div style={{ overflowX: "auto" }}>
              <table className="pw-fac-table" style={{ fontSize: 11 }}>
                <thead>
                  <tr>
                    <th>Action</th>
                    <th>Activity name</th>
                    <th>Start date</th>
                    <th>Host unit</th>
                    <th>Location</th>
                  </tr>
                </thead>
                <tbody>
                  {result.preview.map((p, i) => (
                    <tr key={i} style={{
                      background: p.action === "create" ? "#f0fff4" : p.action === "update" ? "#fff8e6" : "#fff3f3",
                    }}>
                      <td>
                        <span style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase",
                          color: p.action === "create" ? "#1A7F4B" : p.action === "update" ? "var(--warning)" : "var(--aafc-red)" }}>
                          {p.action}
                        </span>
                      </td>
                      <td style={{ fontWeight: 600 }}>{p.activity_name}</td>
                      <td>{p.activity_start_date ?? "—"}</td>
                      <td style={{ color: "var(--muted-text)" }}>{p.host_unit ?? "—"}</td>
                      <td style={{ color: "var(--muted-text)" }}>{p.location ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {result.row_count > 50 && (
                <div style={{ fontSize: 11, color: "var(--muted-text)", padding: "4px 0" }}>
                  Showing first 50 rows of {result.row_count} total. Go to Activities tab to see all.
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Import history */}
      <div style={{ fontSize: 12, fontWeight: 700, color: "var(--aafc-dark-blue)", marginBottom: 8 }}>
        Import history
      </div>
      {batchLoading ? (
        <div className="pw-loading" style={{ padding: "10px 0" }}>Loading…</div>
      ) : batches.length === 0 ? (
        <div style={{ fontSize: 11, color: "var(--muted-text)" }}>No imports yet.</div>
      ) : (
        <table className="pw-fac-table" style={{ fontSize: 11 }}>
          <thead>
            <tr>
              <th>File</th>
              <th>Imported at</th>
              <th>Rows</th>
              <th>New</th>
              <th>Updated</th>
              <th>Dups</th>
              <th>Skipped</th>
              <th>Errors</th>
            </tr>
          </thead>
          <tbody>
            {batches.map(b => (
              <tr key={b.id}>
                <td style={{ maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis" }}>
                  {b.source_file_name ?? "—"}
                </td>
                <td style={{ color: "var(--muted-text)", whiteSpace: "nowrap" }}>
                  {b.created_at
                    ? new Date(b.created_at).toLocaleDateString("en-CA", { year: "numeric", month: "short", day: "numeric" })
                    : "—"}
                </td>
                <td style={{ textAlign: "center" }}>{b.row_count}</td>
                <td style={{ textAlign: "center", color: "#1A7F4B", fontWeight: 700 }}>{b.created_count}</td>
                <td style={{ textAlign: "center", color: "var(--warning)", fontWeight: 700 }}>{b.updated_count}</td>
                <td style={{ textAlign: "center" }}>{b.duplicate_count}</td>
                <td style={{ textAlign: "center" }}>{b.skipped_count}</td>
                <td style={{ textAlign: "center", color: b.error_count > 0 ? "var(--aafc-red)" : undefined }}>
                  {b.error_count}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ─── PlanningBottomDrawer ─────────────────────────────────────────────────────

export function PlanningBottomDrawer({ yearId, tab, onTabChange, onClose, facilitators, locations, onItemClick }: Props) {
  return (
    <div className="pw-bottom-bar" role="complementary" aria-label="Bottom planning drawer">
      <div className="pw-bottom-tabs">
        {TABS.map((t) => (
          <button
            key={t.key}
            className={`pw-btab${tab === t.key ? " active" : ""}`}
            onClick={() => onTabChange(t.key)}
            aria-pressed={tab === t.key}
          >
            {t.label}
          </button>
        ))}
        <button className="pw-btab-close" onClick={onClose} aria-label="Close bottom drawer">×</button>
      </div>
      <div className="pw-bottom-content">
        {tab === "backlog" && yearId && <BacklogContent yearId={yearId} onItemClick={onItemClick} />}
        {tab === "backlog" && !yearId && <div className="pw-empty">No planning year selected.</div>}

        {tab === "facilitators" && (
          <FacilitatorsContent yearId={yearId} facilitators={facilitators} />
        )}

        {tab === "rooms" && (
          <RoomsContent
            locations={locations}
            onAddLocation={() => { onItemClick({ type: "new-location" }); onClose(); }}
            onEditLocation={(loc) => { onItemClick({ type: "new-location", location: loc }); onClose(); }}
          />
        )}

        {tab === "equipment" && <EquipmentContent />}

        {tab === "holidays" && yearId && <HolidaysContent yearId={yearId} />}
        {tab === "holidays" && !yearId && <div className="pw-empty">No planning year selected.</div>}

        {tab === "notices" && yearId && <NoticesContent yearId={yearId} />}
        {tab === "notices" && !yearId && <div className="pw-empty">No planning year selected.</div>}

        {tab === "activities" && yearId && <ActivitiesContent yearId={yearId} />}
        {tab === "activities" && !yearId && <div className="pw-empty">No planning year selected.</div>}

        {tab === "import-review" && yearId && <ImportReviewContent yearId={yearId} />}
        {tab === "import-review" && !yearId && <div className="pw-empty">No planning year selected.</div>}
      </div>
    </div>
  );
}
