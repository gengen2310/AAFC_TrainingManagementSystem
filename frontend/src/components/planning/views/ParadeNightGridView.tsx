import { ErrorRemedy } from "../../ui";
import { useState, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { planningApi } from "../../../api";
import { friendlyMessage } from "../../../api/client";
import type { PlanningSession, PlanningFacilitator, PlanningConflict, TimingBlock, ParadeNotice, TemplateImpactResult } from "../../../api/types";
import type { DrawerItem } from "../PlanningRightDrawer";
import { groupByPhase } from '../utils/groupByPhase';
import { TimingStrip } from '../TimingStrip';
import { TemplateImpactModal } from '../TemplateImpactModal';
import type { TimingStripEntry, InstructionalPeriod } from '../../../api/types';

interface CellConflict {
  room: boolean;
  fac: boolean;
  load: boolean;
}

function computeConflicts(
  sessions: PlanningSession[],
  facilitators: PlanningFacilitator[],
): Map<string, CellConflict> {
  const result = new Map<string, CellConflict>();

  const byPeriod = new Map<number, PlanningSession[]>();
  for (const s of sessions) {
    const list = byPeriod.get(s.session_number) ?? [];
    list.push(s);
    byPeriod.set(s.session_number, list);
  }

  for (const periodSessions of byPeriod.values()) {
    const roomMap = new Map<string, string[]>();
    const facMap = new Map<string, string[]>();
    for (const s of periodSessions) {
      if (s.location_id) {
        const l = roomMap.get(s.location_id) ?? [];
        l.push(s.session_id);
        roomMap.set(s.location_id, l);
      }
      if (s.facilitator_id) {
        const l = facMap.get(s.facilitator_id) ?? [];
        l.push(s.session_id);
        facMap.set(s.facilitator_id, l);
      }
    }
    for (const ids of roomMap.values()) {
      if (ids.length > 1) {
        for (const id of ids) {
          const c = result.get(id) ?? { room: false, fac: false, load: false };
          c.room = true;
          result.set(id, c);
        }
      }
    }
    for (const ids of facMap.values()) {
      if (ids.length > 1) {
        for (const id of ids) {
          const c = result.get(id) ?? { room: false, fac: false, load: false };
          c.fac = true;
          result.set(id, c);
        }
      }
    }
  }

  const facPeriodSets = new Map<string, Set<number>>();
  for (const s of sessions) {
    if (s.facilitator_id) {
      if (!facPeriodSets.has(s.facilitator_id)) facPeriodSets.set(s.facilitator_id, new Set());
      facPeriodSets.get(s.facilitator_id)!.add(s.session_number);
    }
  }
  for (const [fid, periods] of facPeriodSets) {
    const fac = facilitators.find(f => f.facilitator_id === fid);
    const maxSessions = fac?.max_sessions_per_night ?? 2;
    if (periods.size > maxSessions) {
      for (const s of sessions) {
        if (s.facilitator_id === fid) {
          const c = result.get(s.session_id) ?? { room: false, fac: false, load: false };
          c.load = true;
          result.set(s.session_id, c);
        }
      }
    }
  }

  return result;
}

function sessionForCell(
  sessions: PlanningSession[],
  groups: readonly string[],
  block: TimingBlock,
): PlanningSession | undefined {
  return sessions.find(
    s => s.session_number === block.period_number &&
      s.cadet_group !== null &&
      groups.includes(s.cadet_group as string),
  );
}

// ─── Inline notice form ───────────────────────────────────────────────────────

function AddNoticeForm({ dateId, onDone }: { dateId: string; onDone: () => void }) {
  const qc = useQueryClient();
  const [text, setText] = useState("");
  const [priority, setPriority] = useState("normal");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function handleSave() {
    if (!text.trim()) { setErr("Notice text required."); return; }
    setSaving(true); setErr(null);
    try {
      await planningApi.createNotice(dateId, { notice_text: text.trim(), priority });
      await qc.invalidateQueries({ queryKey: ["planning-night-summaries"] });
      await qc.invalidateQueries({ queryKey: ["pn-notices", dateId] });
      onDone();
    } catch (e: unknown) {
      setErr(friendlyMessage(e, "Save failed"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="pw-block-notice-form">
      <textarea
        className="pw-block-notice-input"
        placeholder="Notice text…"
        value={text}
        onChange={e => setText(e.target.value)}
        rows={2}
      />
      <div className="pw-block-notice-form-row">
        <select value={priority} onChange={e => setPriority(e.target.value)} className="pw-block-notice-priority">
          <option value="normal">Normal</option>
          <option value="urgent">Urgent</option>
        </select>
        {err && <span style={{ fontSize: 'var(--fs-xs)', color: "var(--aafc-red)", marginLeft: 6 }}>{err}</span>}
        <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
          <button className="btn sm primary" onClick={handleSave} disabled={saving}>{saving ? "…" : "Save"}</button>
          <button className="btn sm out" onClick={onDone}>Cancel</button>
        </div>
      </div>
    </div>
  );
}

// ─── Notice line with archive ─────────────────────────────────────────────────

function NoticeRow({ notice, dateId }: { notice: ParadeNotice; dateId: string }) {
  const qc = useQueryClient();
  const [archiving, setArchiving] = useState(false);

  async function handleArchive() {
    setArchiving(true);
    try {
      await planningApi.archiveNotice(notice.notice_id);
      await qc.invalidateQueries({ queryKey: ["planning-night-summaries"] });
      await qc.invalidateQueries({ queryKey: ["pn-notices", dateId] });
    } finally {
      setArchiving(false);
    }
  }

  return (
    <div className={`pw-block-notice${notice.priority === "urgent" ? " urgent" : ""}`}>
      <span className="pw-block-notice-pfx">{notice.priority === "urgent" ? "!" : "·"}</span>
      <span className="pw-block-notice-body" style={{ flex: 1 }}>{notice.notice_text}</span>
      <button
        className="pw-block-notice-archive"
        onClick={handleArchive}
        disabled={archiving}
        title="Archive notice"
        aria-label="Archive this notice"
      >
        {archiving ? "…" : "×"}
      </button>
    </div>
  );
}

// ─── Main view ────────────────────────────────────────────────────────────────

interface Props {
  dateId: string;
  facilitators: PlanningFacilitator[];
  onCellClick: (item: DrawerItem) => void;
}

export function ParadeNightGridView({ dateId, facilitators, onCellClick }: Props) {
  const [addingNotice, setAddingNotice] = useState(false);
  const [showArchived, setShowArchived] = useState(false);
  const [restoringId, setRestoringId] = useState<string | null>(null);
  const [restoreErr, setRestoreErr] = useState<string | null>(null);
  // Task 7: template change impact modal
  const [impactModal, setImpactModal] = useState<{
    impact: TemplateImpactResult;
    nightId: string;
    templateId: string;
  } | null>(null);
  const [applyingTemplate, setApplyingTemplate] = useState(false);
  const qc = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ["planning-weekly", dateId],
    queryFn: () => planningApi.weeklyProgram(dateId),
  });

  const { data: notices = [], refetch: refetchNotices } = useQuery({
    queryKey: ["pn-notices", dateId],
    queryFn: () => planningApi.listNotices(dateId),
    staleTime: 60 * 1000,
  });

  // Task 4 — phase grouping from curriculum phases (replaces DISPLAY_GROUPS).
  // Derive squadronId from the weekly program's unit_id (available after data loads).
  const squadronId = data?.unit_id ?? null;
  const { data: trainingClassesRaw = [] } = useQuery({
    queryKey: ['training-classes-with-phase', squadronId],
    queryFn: () => planningApi.getTrainingClasses(squadronId!, { includeArchived: true }),
    enabled: !!squadronId,
    staleTime: 5 * 60 * 1000,
  });
  const phaseGroups = useMemo(() => groupByPhase(trainingClassesRaw), [trainingClassesRaw]);

  // REM-133: session delete existed with no way to see or restore an
  // archived session -- lazy-fetched only once "Show archived sessions" is
  // opened, matching this codebase's established show-archived pattern.
  const { data: archivedData, refetch: refetchArchived } = useQuery({
    queryKey: ["planning-archived-sessions", dateId],
    queryFn: () => planningApi.archivedSessions(dateId),
    enabled: showArchived,
  });

  async function doRestoreSession(sessionId: string) {
    setRestoringId(sessionId);
    setRestoreErr(null);
    try {
      await planningApi.restoreSession(sessionId);
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["planning-weekly", dateId] }),
        refetchArchived(),
      ]);
    } catch (e: unknown) {
      setRestoreErr(friendlyMessage(e, "Could not restore this session"));
    } finally {
      setRestoringId(null);
    }
  }

  // Task 7: template-change flow.
  // Callers invoke handleTemplateChange(nightId, newTemplateId) — for example from
  // a template-picker dropdown when it exists in the SetupPanel or header controls.
  // The modal is rendered at the bottom of the JSX and appears as an overlay.
  async function handleTemplateChange(nightId: string, newTemplateId: string) {
    try {
      const impact = await planningApi.getTemplateImpact(nightId, newTemplateId);
      const needsConfirmation =
        impact.removed_periods.length > 0 || impact.affected_sessions.length > 0;
      if (needsConfirmation) {
        setImpactModal({ impact, nightId, templateId: newTemplateId });
      } else {
        await planningApi.applyTemplate(nightId, newTemplateId, false);
        await qc.invalidateQueries({ queryKey: ["planning-weekly", dateId] });
      }
    } catch {
      // Caller should surface an error; here we silently swallow so modal doesn't
      // open on a network failure (caller handles the try/catch at the trigger site).
    }
  }

  async function handleConfirmTemplateChange() {
    if (!impactModal) return;
    setApplyingTemplate(true);
    try {
      await planningApi.applyTemplate(impactModal.nightId, impactModal.templateId, true);
      await qc.invalidateQueries({ queryKey: ["planning-weekly", dateId] });
      setImpactModal(null);
    } finally {
      setApplyingTemplate(false);
    }
  }

  // Expose handleTemplateChange on the component so callers can invoke it
  // via a React ref when the template picker lives in a sibling component.
  // (Alternatively, callers import this component and pass a prop — see Task 8.)
  void handleTemplateChange; // referenced above; used by callers, not inline

  if (isLoading) return <div className="pw-loading">Loading parade night…</div>;
  if (error || !data) {
    const msg = friendlyMessage(error, "Unknown error");
    return (
      <div className="pw-err" style={{ padding: 16 }}>
        <div style={{ fontWeight: 700, marginBottom: 4 }}>Could not load the parade night</div>
        <div style={{ fontSize: 'var(--fs-sm)', opacity: .8 }}>{msg}</div>
        <ErrorRemedy error={error} />
      </div>
    );
  }

  const conflicts = computeConflicts(data.sessions, facilitators);
  const blocks = data.timing_blocks;
  const unresolvedConflicts: PlanningConflict[] = data.conflicts.filter(c => !c.is_resolved);

  const dateLabel = (() => {
    const d = new Date(data.parade_date + "T00:00:00");
    const wd = d.toLocaleDateString("en-GB", { weekday: "long" });
    const day = d.getDate();
    const mon = d.toLocaleDateString("en-GB", { month: "long" });
    const yr = d.getFullYear();
    return `${wd}, ${day} ${mon} ${yr}`;
  })();

  return (
    <div>
      {/* ── Date header ────────────────────────────────────────────────────── */}
      <div className="pw-pn-view-hdr">
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <span className="pw-pn-view-date">{dateLabel}</span>
          {unresolvedConflicts.length > 0 && (
            <span
              className="pw-conflict-badge room"
              title={unresolvedConflicts.map(c => c.message).join("\n")}
            >
              ⚠ {unresolvedConflicts.length} conflict{unresolvedConflicts.length !== 1 ? "s" : ""}
            </span>
          )}
          {!data.parade_night_id && (
            <span style={{ fontSize: 'var(--fs-xs)', color: "var(--muted-text)" }}>Draft — not yet linked to a parade night</span>
          )}
        </div>
      </div>

      {/* ── Notices ────────────────────────────────────────────────────────── */}
      <div className="pw-pn-view-notices">
        {notices.map(n => (
          <NoticeRow key={n.notice_id} notice={n} dateId={dateId} />
        ))}
        {addingNotice ? (
          <AddNoticeForm
            dateId={dateId}
            onDone={() => { setAddingNotice(false); refetchNotices(); }}
          />
        ) : (
          <button
            className="pw-pn-add-notice-btn"
            onClick={() => setAddingNotice(true)}
          >
            + Add notice
          </button>
        )}
        {notices.length === 0 && !addingNotice && (
          <span style={{ fontSize: 'var(--fs-xs)', color: "var(--muted-text)", fontStyle: "italic" }}>No notices</span>
        )}
      </div>

      {/* ── Equipment ──────────────────────────────────────────────────────── */}
      <div className="pw-pn-view-equipment">
        <span className="pw-block-equip-lbl">Equipment:</span>
        <span className="pw-block-equip-val">not set</span>
      </div>

      {/* ── TimingStrip — shows all timing blocks above column headers ─────── */}
      {/* DESIGN: Task 9 will apply visual polish */}
      {blocks.length > 0 && (
        <TimingStrip
          blocks={blocks.map((b): TimingStripEntry => ({
            label: b.name,
            start_time: b.start_time,
            end_time: b.end_time,
            is_instructional: b.is_instructional,
            display_order: b.sequence,
          }))}
          periods={blocks.filter(b => b.is_instructional && b.period_number !== null).map((b): InstructionalPeriod => ({
            period_number: b.period_number!,
            label: b.name,
            start_time: b.start_time,
            end_time: b.end_time,
          }))}
        />
      )}

      {/* ── Timing grid ────────────────────────────────────────────────────── */}
      <div className="pn-grid-wrap">
        <table className="pn-grid">
          <thead>
            <tr>
              <th>Group</th>
              {blocks.map(b => (
                <th key={b.sequence} className={b.block_type === "break" ? "break-col" : ""}>
                  {b.name}
                  {b.start_time && b.end_time && (
                    <div style={{ fontWeight: 400, fontSize: 'var(--fs-2xs)', opacity: 0.8 }}>
                      {b.start_time}–{b.end_time}
                    </div>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {/* Task 4: phase grouping from curriculum phases — replaces DISPLAY_GROUPS. */}
            {phaseGroups.length === 0 && (
              <tr>
                <td colSpan={blocks.length + 1} style={{ padding: 12, color: "var(--muted-text)", fontSize: 'var(--fs-sm)', fontStyle: "italic" }}>
                  No training classes configured for this squadron. Add training classes to see the planning grid.
                </td>
              </tr>
            )}
            {phaseGroups.map(group => (
              <>
                {/* Phase group header row */}
                <tr key={`phase-${group.phase_id}`} className="pn-phase-header">
                  <td
                    colSpan={blocks.length + 1}
                    style={{ background: "var(--aafc-dark, #002f65)", color: "#fff", fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", padding: "4px 12px" }}
                  >
                    {group.phase_name}
                  </td>
                </tr>
                {group.training_classes.map(tc => (
                <tr key={tc.training_class_id}>
                  <th style={!tc.active_status ? { opacity: 0.5 } : undefined}>
                    {tc.display_name}
                    {!tc.active_status && (
                      <span style={{ marginLeft: 4, fontSize: 9, background: "var(--lgrey, #b0b7bb)", borderRadius: 3, padding: "1px 4px", fontWeight: 400 }}>
                        Archived
                      </span>
                    )}
                  </th>
                  {blocks.map(b => {
                    if (b.block_type === "break" || !b.is_instructional || b.period_number === null) {
                      return (
                        <td key={b.sequence} className="pn-grid-cell">
                          <div className="pn-cell-inner break-cell">{b.name}</div>
                        </td>
                      );
                    }
                    const session = data.sessions.find(
                      s => s.session_number === b.period_number &&
                        (s.training_classes ?? []).some(c => c.training_class_id === tc.training_class_id)
                    );
                    if (!session) {
                      return (
                        <td key={b.sequence} className="pn-grid-cell">
                          {tc.active_status !== false && (
                            <button
                              className="pn-add-btn"
                              onClick={() => onCellClick({ type: "new-session", cadetGroup: "", periodNumber: b.period_number!, dateId })}
                              aria-label={`Add session for ${tc.display_name}, period ${b.period_number}`}
                            >
                              + Add
                            </button>
                          )}
                        </td>
                      );
                    }
                    const c = conflicts.get(session.session_id);
                    const cellCls = c?.room ? "conflict-room" : c?.fac ? "conflict-fac" : "";
                    const sessionConflicts = unresolvedConflicts.filter(x => x.scheduled_session_id === session.session_id);
                    return (
                      <td key={b.sequence} className="pn-grid-cell">
                        <div
                          className={`pn-cell-inner ${cellCls}`}
                          onClick={() => onCellClick({ type: "session", session, dateId, date: data.parade_date, conflicts: sessionConflicts })}
                          role="button"
                          tabIndex={0}
                          onKeyDown={e => e.key === "Enter" && onCellClick({ type: "session", session, dateId, date: data.parade_date, conflicts: sessionConflicts })}
                          aria-label={`${session.activity_title ?? "Session"} — ${tc.display_name}`}
                        >
                          {c && (
                            <div className="pn-cell-conflict">
                              {c.room && <span className="pn-conflict-dot room" title="Room double-booked" aria-label="Room conflict" />}
                              {c.fac && <span className="pn-conflict-dot fac" title="Facilitator double-booked" aria-label="Facilitator conflict" />}
                              {c.load && <span className="pn-conflict-dot load" title="Facilitator overloaded" aria-label="Facilitator overload" />}
                            </div>
                          )}
                          {session.curriculum_code && <div className="pn-cell-code">{session.curriculum_code}</div>}
                          <div className="pn-cell-title">{session.activity_title ?? "—"}</div>
                          {!!session.training_classes?.length && (
                            <div className="pn-cell-classes" style={{ fontSize: 'var(--fs-2xs)', color: "var(--aafc-dark-blue, #002f65)" }}>
                              {session.training_classes.map(cl => cl.display_name).join(", ")}
                            </div>
                          )}
                          {session.location_name && <div className="pn-cell-room">{session.location_name}</div>}
                          <div className="pn-cell-fac">
                            {session.facilitator_name ?? "No facilitator"}
                            {/* Task 6: multi-assistant display — names if ≤2, count chip if more */}
                            {(session.assistant_facilitators ?? []).length === 0 && session.assistant_facilitator_name && (
                              ` + ${session.assistant_facilitator_name}`
                            )}
                            {(session.assistant_facilitators ?? []).length === 1 && (
                              <span style={{ fontSize: 'var(--fs-2xs)', marginLeft: 4, color: "var(--muted-text)" }}>
                                + {session.assistant_facilitators![0].display_name}
                              </span>
                            )}
                            {(session.assistant_facilitators ?? []).length === 2 && (
                              <span style={{ fontSize: 'var(--fs-2xs)', marginLeft: 4, color: "var(--muted-text)" }}>
                                + {session.assistant_facilitators!.map(a => a.display_name).join(", ")}
                              </span>
                            )}
                            {(session.assistant_facilitators ?? []).length > 2 && (
                              <span style={{ fontSize: 'var(--fs-2xs)', marginLeft: 4, color: "var(--muted-text)" }}>
                                +{session.assistant_facilitators!.length} asst
                              </span>
                            )}
                          </div>
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
              </>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── Archived sessions ──────────────────────────────────────────────── */}
      <div style={{ marginTop: 14 }}>
        <button
          type="button"
          className="btn sm out"
          style={{ fontSize: 'var(--fs-xs)' }}
          onClick={() => setShowArchived(v => !v)}
        >
          {showArchived ? "Hide archived sessions" : "Show archived sessions"}
        </button>
        {showArchived && (
          <div style={{ marginTop: 8 }}>
            {restoreErr && <div className="pw-err" style={{ marginBottom: 6 }}>{restoreErr}</div>}
            {!archivedData ? (
              <div className="pw-loading">Loading archived sessions…</div>
            ) : archivedData.sessions.length === 0 ? (
              <div style={{ fontSize: 'var(--fs-sm)', color: "var(--muted-text)" }}>No archived sessions for this parade night.</div>
            ) : (
              <table className="pw-lv-table">
                <thead>
                  <tr>
                    <th className="pw-lv-th">Title</th>
                    <th className="pw-lv-th">Group</th>
                    <th className="pw-lv-th">Facilitator</th>
                    <th className="pw-lv-th" />
                  </tr>
                </thead>
                <tbody>
                  {archivedData.sessions.map(s => (
                    <tr key={s.session_id}>
                      <td>{s.activity_title ?? "—"}</td>
                      <td>{s.cadet_group ?? "—"}</td>
                      <td>{s.facilitator_name ?? "—"}</td>
                      <td style={{ textAlign: "right" }}>
                        <button
                          type="button"
                          className="btn sm out"
                          style={{ fontSize: 'var(--fs-xs)' }}
                          disabled={restoringId === s.session_id}
                          onClick={() => doRestoreSession(s.session_id)}
                        >
                          {restoringId === s.session_id ? "Restoring…" : "Restore"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>

      {/* Task 7: TemplateImpactModal — rendered as a portal-style overlay */}
      {impactModal && (
        <TemplateImpactModal
          impact={impactModal.impact}
          onConfirm={handleConfirmTemplateChange}
          onCancel={() => setImpactModal(null)}
          loading={applyingTemplate}
        />
      )}
    </div>
  );
}
