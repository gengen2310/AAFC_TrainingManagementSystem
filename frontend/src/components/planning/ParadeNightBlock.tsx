import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { planningApi } from "../../api";
import { friendlyMessage } from "../../api/client";
import type { NightSessionSummary, ParadeNotice, PlanningSession, PlanningFacilitator, PlanningConflict } from "../../api/types";

// ─── Group / period constants ─────────────────────────────────────────────────

export const BLOCK_GROUPS = [
  { key: "oi",     label: "O&I",    fullLabel: "Ori & Initial",       cadetGroups: ["orientation", "initial"] },
  { key: "bronze", label: "Bronze", fullLabel: "Junior & Bronze CLP", cadetGroups: ["junior"] },
  { key: "silver", label: "Silver", fullLabel: "Inter. & Silver CLP", cadetGroups: ["intermediate"] },
  { key: "gold",   label: "Gold",   fullLabel: "Senior & Gold CLP",   cadetGroups: ["senior"] },
] as const;

export const BLOCK_PERIODS = [1, 2, 3] as const;

// ─── Normalised display session ───────────────────────────────────────────────

export interface DisplaySession {
  session_id: string;
  period: number;
  cadet_group: string | null;
  title: string | null;
  code: string | null;
  location: string | null;
  facilitator: string | null;
  assistant_facilitator?: string | null;
  conflict?: "room" | "fac" | "load" | null;
  source?: PlanningSession;
  // CLASS-06: which Training Class(es) this session targets. Optional --
  // fromPlanningSession()'s own source (PlanningSession) only carries this
  // field on the one endpoint (weekly-program) that was extended for it;
  // the other _real_session_out call sites were deliberately not touched.
  training_classes?: { training_class_id: string; display_name: string }[];
}

// REM-39 residual: real backend PlanningConflict.conflict_type values today
// are "facilitator_double_booked" / "room_double_booked" / "empty_session" /
// "holiday_conflict" (see backend/app/models/planning.py's CONFLICT_TYPES --
// several other declared types are not yet emitted by any code path). Only
// the first two are ever session-specific (carry a scheduled_session_id);
// the others describe the night as a whole, not one cell, so they never
// match here and correctly produce no per-cell dot.
function sessionConflictCategory(conflictType: string): DisplaySession["conflict"] {
  if (conflictType.includes("room")) return "room";
  if (conflictType.includes("facilitator")) return "fac";
  return null;
}

export function fromNightSummary(
  sessions: NightSessionSummary[],
  conflicts: PlanningConflict[] = [],
): DisplaySession[] {
  return sessions.map(s => {
    const hit = conflicts.find(c => c.scheduled_session_id === s.session_id && !c.is_resolved);
    return {
      session_id: s.session_id,
      period: s.period,
      cadet_group: s.cadet_group,
      title: s.title,
      code: s.curriculum_code,
      location: s.location,
      facilitator: s.facilitator,
      training_classes: s.training_classes,
      conflict: hit ? sessionConflictCategory(hit.conflict_type) : null,
    };
  });
}

export interface CellConflict { room: boolean; fac: boolean; load: boolean; }

// REM-39 residual: EightWeekView (and TwoWeekView/the custom-range view,
// which are the same component with different props) built its per-cell dot
// from computeConflicts() below -- a client-side heuristic re-derived from
// the currently-loaded session list -- instead of the canonical backend
// PlanningConflict/is_resolved data already available to it as row.conflicts
// (used correctly for the header's unresolved-count badge on the same row).
// The two can disagree: a conflict already overridden/resolved server-side
// could still show a heuristic dot, or a real conflict the heuristic doesn't
// model (e.g. cross-period) could go unshown. This mirrors fromNightSummary's
// own conflict lookup (YearView/TermView), just producing the CellConflict
// map shape fromPlanningSession expects instead of a flat array scan.
export function conflictMapFromPlanningConflicts(
  conflicts: PlanningConflict[],
): Map<string, CellConflict> {
  const result = new Map<string, CellConflict>();
  for (const c of conflicts) {
    if (c.is_resolved || !c.scheduled_session_id) continue;
    const cat = sessionConflictCategory(c.conflict_type);
    if (!cat) continue;
    const entry = result.get(c.scheduled_session_id) ?? { room: false, fac: false, load: false };
    if (cat === "room") entry.room = true;
    if (cat === "fac") entry.fac = true;
    result.set(c.scheduled_session_id, entry);
  }
  return result;
}

export function fromPlanningSession(
  sessions: PlanningSession[],
  conflictMap?: Map<string, CellConflict>,
): DisplaySession[] {
  return sessions.map(s => {
    const c = conflictMap?.get(s.session_id);
    const conflict: DisplaySession["conflict"] = c?.room ? "room" : c?.fac ? "fac" : c?.load ? "load" : null;
    return {
      session_id: s.session_id,
      period: s.session_number,
      cadet_group: s.cadet_group,
      title: s.activity_title,
      code: s.curriculum_code,
      location: s.location_name,
      facilitator: s.facilitator_name,
      assistant_facilitator: s.assistant_facilitator_name,
      conflict,
      source: s,
      training_classes: s.training_classes,
    };
  });
}

// No longer called from src/ as of the REM-39 residual fix above (its last
// caller, EightWeekView, switched to conflictMapFromPlanningConflicts) --
// kept rather than deleted because its "load" (facilitator-overload)
// detection has no backend/canonical equivalent (see REM-39's own residual
// note: the backend has never emitted a 'load' conflict_type at all), so
// this is the only place that logic exists. Room/fac double-booking
// detection here is now fully superseded by canonical data and should not
// be reintroduced as a source of truth if this function is revived.
export function computeConflicts(
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

// ─── Cell lookup ──────────────────────────────────────────────────────────────

function getCell(
  sessions: DisplaySession[],
  cadetGroups: readonly string[],
  period: number,
): DisplaySession | null {
  const hit = sessions.find(
    s => s.period === period &&
      s.cadet_group !== null &&
      (cadetGroups as readonly string[]).includes(s.cadet_group as string),
  );
  if (hit) return hit;
  return sessions.find(s => s.period === period && s.cadet_group === null) ?? null;
}

function trunc(text: string | null, max: number): string {
  if (!text) return "—";
  return text.length > max ? text.slice(0, max - 1) + "…" : text;
}

// ─── Inline notice add form ───────────────────────────────────────────────────

function AddNoticeForm({ dateId, onDone }: { dateId: string; onDone: () => void }) {
  const qc = useQueryClient();
  const [text, setText] = useState("");
  const [priority, setPriority] = useState("normal");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function handleSave() {
    if (!text.trim()) { setErr("Notice text is required."); return; }
    setSaving(true); setErr(null);
    try {
      await planningApi.createNotice(dateId, { notice_text: text.trim(), priority });
      await qc.invalidateQueries({ queryKey: ["planning-night-summaries"] });
      onDone();
    } catch (e: unknown) {
      setErr(friendlyMessage(e, "Failed to save notice"));
    } finally {
      setSaving(false);
    }
  }

  return (
    // Only stops this form's own clicks from bubbling to the parent block's click handler.
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions
    <div className="pw-block-notice-form" onClick={e => e.stopPropagation()}>
      <textarea
        className="pw-block-notice-input"
        placeholder="Notice text…"
        value={text}
        onChange={e => setText(e.target.value)}
        rows={2}
      />
      <div className="pw-block-notice-form-row">
        <select
          value={priority}
          onChange={e => setPriority(e.target.value)}
          className="pw-block-notice-priority"
        >
          <option value="normal">Normal</option>
          <option value="urgent">Urgent</option>
        </select>
        {err && <span style={{ fontSize: 10, color: "var(--aafc-red)", marginLeft: 6 }}>{err}</span>}
        <div style={{ marginLeft: "auto", display: "flex", gap: 4 }}>
          <button className="btn sm primary" style={{ fontSize: 11, padding: "3px 8px" }} onClick={handleSave} disabled={saving}>
            {saving ? "…" : "Save"}
          </button>
          <button className="btn sm out" style={{ fontSize: 11, padding: "3px 8px" }} onClick={onDone}>Cancel</button>
        </div>
      </div>
    </div>
  );
}

// ─── Main ParadeNightBlock component ─────────────────────────────────────────

interface ParadeNightBlockProps {
  dateId: string;
  date: string;
  weekNumber?: number | null;
  term?: string | null;
  notices?: ParadeNotice[];
  sessions: DisplaySession[];
  sessionCount?: number;
  filledSlots?: number;
  conflictCount?: number;
  inHoliday?: boolean;
  compact?: boolean;
  /** "sm" shrinks table cell min-widths so blocks fit in a multi-column year grid */
  blockSize?: "sm" | "md";
  onHeaderClick: () => void;
  onSessionClick?: (session: DisplaySession) => void;
  onEmptyCellClick?: (cadetGroup: string, period: number) => void;
}

export function ParadeNightBlock({
  dateId, date, weekNumber, term, notices = [],
  sessions, sessionCount, filledSlots, conflictCount = 0,
  inHoliday = false, compact = false, blockSize = "md",
  onHeaderClick, onSessionClick, onEmptyCellClick,
}: ParadeNightBlockProps) {
  const [addingNotice, setAddingNotice] = useState(false);

  const dateLabel = new Date(date + "T00:00:00").toLocaleDateString("en-CA", {
    weekday: compact ? "short" : "long",
    month: "short",
    day: "numeric",
  });

  const termLabel = term && weekNumber
    ? `${term} · Wk ${weekNumber}`
    : term
    ? term
    : weekNumber
    ? `Wk ${weekNumber}`
    : null;

  const totalCells = (sessionCount ?? 0) * BLOCK_GROUPS.length;
  const fillLabel = totalCells > 0
    ? `${filledSlots ?? 0} / ${totalCells} classes planned`
    : null;

  const blockCls = [
    "pw-block",
    compact ? "compact" : "standard",
    blockSize === "sm" ? "pw-block-sm" : "",
    inHoliday ? "holiday" : "",
    conflictCount > 0 ? "has-conflict" : "",
  ].filter(Boolean).join(" ");

  return (
    <div className={blockCls}>
      {/* ── Header — dark blue bar ──────────────────────────────────────────── */}
      <div
        className="pw-block-hdr"
        onClick={onHeaderClick}
        role="button"
        tabIndex={0}
        onKeyDown={e => e.key === "Enter" && onHeaderClick()}
        aria-label={`Parade night ${date}`}
      >
        <span className="pw-block-date">{dateLabel}</span>
        {inHoliday && <span className="pw-block-standdown">Stand-down</span>}
        {fillLabel && !compact && <span className="pw-block-fill">{fillLabel}</span>}
        {conflictCount > 0 && (
          <span
            className="pw-conflict-badge room"
            title={`${conflictCount} unresolved conflict${conflictCount !== 1 ? "s" : ""} (room, facilitator, or workload double-booking) — open this parade night to see and resolve each one`}
          >
            ⚠ {conflictCount}
          </span>
        )}
      </div>

      {/* ── Notices band ────────────────────────────────────────────────────── */}
      <div className="pw-block-band">
        <div className="pw-block-band-hdr">
          <span>Notices</span>
          <button
            className="pw-block-add-notice-btn"
            style={{ fontSize: 10, background: "none", border: "1px solid var(--border)", borderRadius: 4, padding: "1px 6px", cursor: "pointer", color: "var(--muted-text)", fontWeight: 700 }}
            onClick={e => { e.stopPropagation(); setAddingNotice(v => !v); }}
            aria-label="Add notice"
          >
            + Add
          </button>
        </div>
        <div className="pw-block-band-body">
          {notices.length === 0 && !addingNotice ? (
            <span className="pw-block-no-content">No notices</span>
          ) : (
            <div className="pw-block-notices">
              {notices.map((n, i) => (
                <div key={n.notice_id ?? String(i)} className={`pw-block-notice${n.priority === "urgent" ? " urgent" : ""}`}>
                  <span className="pw-block-notice-pfx">{n.priority === "urgent" ? "!" : "·"}</span>
                  <span className="pw-block-notice-body">{n.notice_text}</span>
                </div>
              ))}
              {addingNotice && (
                <AddNoticeForm dateId={dateId} onDone={() => setAddingNotice(false)} />
              )}
            </div>
          )}
        </div>
      </div>

      {/* ── Equipment band ──────────────────────────────────────────────────── */}
      <div className="pw-block-band">
        <div className="pw-block-band-hdr">Equipment</div>
        <div className="pw-block-band-body">
          <span className="pw-block-no-content">Not set</span>
        </div>
      </div>

      {/* ── Session grid ────────────────────────────────────────────────────── */}
      {compact ? (
        /* Compact mode: text rows */
        <div className="pw-block-compact-grid">
          {BLOCK_GROUPS.map(g => {
            const cells = BLOCK_PERIODS.map(p => getCell(sessions, g.cadetGroups, p));
            const allEmpty = cells.every(c => c === null);
            return (
              // Mouse-only shortcut for the same action as the block header above
              // (which already has a real, focusable, keyboard-operable role="button")
              // — intentionally not a second tab stop for the identical action.
              // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions
              <div
                key={g.key}
                className={`pw-block-cg-row${allEmpty ? " all-empty" : ""}`}
                onClick={onHeaderClick}
              >
                <span className="pw-block-cg-lbl">{g.label}</span>
                <span className="pw-block-cg-periods">
                  {cells.map((cell, i) => (
                    <span key={i} className={`pw-block-cg-cell${!cell ? " empty" : ""}${cell?.conflict ? ` c-${cell.conflict}` : ""}`}>
                      <span className="pw-block-cg-p">P{BLOCK_PERIODS[i]}</span>
                      {cell ? trunc(cell.title, 24) : "—"}
                    </span>
                  ))}
                </span>
              </div>
            );
          })}
        </div>
      ) : (
        /* Standard mode: full group × period table */
        <div style={{ overflowX: "auto" }}>
          <table className="pw-night-grid">
            <thead>
              <tr>
                <th className="pw-ng-grp-col">Group</th>
                {BLOCK_PERIODS.map(p => <th key={p}>P{p}</th>)}
              </tr>
            </thead>
            <tbody>
              {BLOCK_GROUPS.map(g => (
                <tr key={g.key}>
                  <th>{g.fullLabel}</th>
                  {BLOCK_PERIODS.map(period => {
                    const cell = getCell(sessions, g.cadetGroups, period);
                    if (!cell) {
                      const handleEmptyClick = onEmptyCellClick
                        ? () => onEmptyCellClick(g.cadetGroups[0], period)
                        : onHeaderClick;
                      return (
                        <td
                          key={period}
                          className="pw-night-cell empty"
                          onClick={handleEmptyClick}
                          role="button"
                          tabIndex={0}
                          onKeyDown={e => e.key === "Enter" && handleEmptyClick()}
                          aria-label={onEmptyCellClick ? "Click to add a session" : "No lesson — click to open night detail"}
                        >
                          <div className="pw-night-cell-inner">
                            <span className="pw-nc-empty">No lesson</span>
                          </div>
                        </td>
                      );
                    }
                    return (
                      <td
                        key={period}
                        className={`pw-night-cell${cell.conflict === "room" ? " conflict-room" : cell.conflict === "fac" ? " conflict-fac" : ""}`}
                        onClick={onSessionClick ? e => { e.stopPropagation(); onSessionClick(cell); } : onHeaderClick}
                        role="button"
                        tabIndex={0}
                        onKeyDown={e => {
                          if (e.key === "Enter") {
                            if (onSessionClick) { e.stopPropagation(); onSessionClick(cell); }
                            else onHeaderClick();
                          }
                        }}
                      >
                        <div className="pw-night-cell-inner">
                          {cell.conflict && (
                            <div className="pn-cell-conflict">
                              {cell.conflict === "room" && <span className="pn-conflict-dot room" title="Room double-booked" />}
                              {cell.conflict === "fac" && <span className="pn-conflict-dot fac" title="Facilitator double-booked" />}
                              {cell.conflict === "load" && <span className="pn-conflict-dot load" title="Facilitator overloaded" />}
                            </div>
                          )}
                          {cell.code && <div className="pw-nc-code">{cell.code}</div>}
                          <div className="pw-nc-title">{trunc(cell.title, 40)}</div>
                          {!!cell.training_classes?.length && (
                            <div className="pw-nc-detail pw-nc-classes">
                              {cell.training_classes.map(c => c.display_name).join(", ")}
                            </div>
                          )}
                          {cell.location && <div className="pw-nc-detail">{cell.location}</div>}
                          <div className="pw-nc-detail">{cell.facilitator ?? "No facilitator"}</div>
                          <div className="pw-nc-equip">Equip: not set</div>
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Warnings footer ──────────────────────────────────────────────────── */}
      {conflictCount > 0 && (
        <div className="pw-block-warnings">
          ⚠ {conflictCount} conflict{conflictCount !== 1 ? "s" : ""} — open night detail to resolve
        </div>
      )}
    </div>
  );
}
