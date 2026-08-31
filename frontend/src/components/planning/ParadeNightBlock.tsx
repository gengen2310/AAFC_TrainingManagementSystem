import { useState, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { planningApi } from "../../api";
import { friendlyMessage } from "../../api/client";
import { useToast } from "../Toast";
import type { NightSessionSummary, ParadeNotice, PlanningSession, PlanningFacilitator, PlanningConflict, TrainingClassSummary } from "../../api/types";

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
  // CLASS-21: curriculum core_status for Foundation/Extension PW filter.
  core_status?: string | null;
}

// Session-specific conflict types (carry a scheduled_session_id and produce
// a per-cell dot): "facilitator_double_booked", "room_double_booked",
// "facilitator_on_leave" (DEF-17: leave detection wired 2026-08-14).
// Night-level types (no session id, no dot): "empty_session",
// "holiday_conflict". See backend/app/models/planning.py CONFLICT_TYPES.
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
      core_status: s.core_status ?? null,
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
      core_status: s.core_status ?? null,
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

function getCellByClassId(
  sessions: DisplaySession[],
  classId: string,
  period: number,
): DisplaySession | null {
  return sessions.find(
    s => s.period === period &&
      (s.training_classes ?? []).some(c => c.training_class_id === classId),
  ) ?? null;
}

function trunc(text: string | null, max: number): string {
  if (!text) return "—";
  return text.length > max ? text.slice(0, max - 1) + "…" : text;
}

// ─── Inline notice add form ───────────────────────────────────────────────────

function AddNoticeForm({ dateId, onDone }: { dateId: string; onDone: () => void }) {
  const qc = useQueryClient();
  const { toast } = useToast();
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
      toast("Notice saved.");
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
        {err && <span style={{ fontSize: 'var(--fs-2xs)', color: "var(--aafc-red)", marginLeft: 6 }}>{err}</span>}
        <div style={{ marginLeft: "auto", display: "flex", gap: 4 }}>
          <button className="btn sm primary" style={{ fontSize: 'var(--fs-xs)', padding: "3px 8px" }} onClick={handleSave} disabled={saving}>
            {saving ? "…" : "Save"}
          </button>
          <button className="btn sm out" style={{ fontSize: 'var(--fs-xs)', padding: "3px 8px" }} onClick={onDone}>Cancel</button>
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
  /** When set, dims session cells that don't target this Training Class */
  focusClassId?: string | null;
  /** When set, dims session cells whose title and code don't contain the search text */
  searchText?: string | null;
  /** When set, dims sessions whose curriculum tier doesn't match: "foundation"|"extension" */
  tierFilter?: string | null;
  /** When set, dims sessions where no audience class belongs to this Training Stage */
  focusStageId?: string | null;
  /** Maps training_class_id → training_stage_id for stageDimmed evaluation */
  classStageMap?: Record<string, string>;
  /** When provided and non-empty, renders one row per TrainingClass instead of legacy BLOCK_GROUPS */
  trainingClasses?: TrainingClassSummary[];
  onHeaderClick: () => void;
  onSessionClick?: (session: DisplaySession) => void;
  onEmptyCellClick?: (cadetGroup: string, period: number, trainingClassId?: string) => void;
  /** DND-01: called when a session is drag-dropped onto an empty cell */
  onMoveSession?: (payload: DragSessionPayload, targetDateId: string, targetPeriod: number, targetCadetGroup: string) => Promise<void>;
  /** A11Y-G6: the session currently "picked up" for a keyboard move, if any.
   *  Held by the parent view so a move can cross blocks exactly as a drag can. */
  moveSource?: DragSessionPayload | null;
  /** A11Y-G6: pick a session up for a keyboard move (Enter/M on a session cell). */
  onPickUpSession?: (payload: DragSessionPayload) => void;
  /** A11Y-G6: abandon the current keyboard move (Escape). */
  onCancelMove?: () => void;
}

/** DND-01: minimal data transferred via the HTML5 drag API across components */
export interface DragSessionPayload {
  session_id: string;
  cadet_group: string | null;
  curriculum_id: string | null;
  facilitator_id: string | null;
  location_id: string | null;
  activity_title: string | null;
  status: string;
}

export function ParadeNightBlock({
  dateId, date, weekNumber, term, notices = [],
  sessions, sessionCount, filledSlots, conflictCount = 0,
  inHoliday = false, compact = false, blockSize = "md", focusClassId, searchText, tierFilter,
  focusStageId, classStageMap, trainingClasses = [],
  onHeaderClick, onSessionClick, onEmptyCellClick, onMoveSession,
  moveSource = null, onPickUpSession, onCancelMove,
}: ParadeNightBlockProps) {
  const [addingNotice, setAddingNotice] = useState(false);
  // CLASS-23: per-block collapsed state. Collapsed shows only the header bar.
  const [collapsed, setCollapsed] = useState(false);
  // A11Y-G6: one payload builder for both drag and keyboard, so the two paths cannot drift.
  const buildPayload = (cell: DisplaySession): DragSessionPayload => ({
    session_id: cell.session_id,
    cadet_group: cell.cadet_group,
    curriculum_id: cell.source!.curriculum_id,
    facilitator_id: cell.source!.facilitator_id,
    location_id: cell.source!.location_id,
    activity_title: cell.source!.activity_title,
    status: cell.source!.status,
  });

  // DND-01: drop target cell key (format "{period}-{cadetGroup}") while drag is over this block.
  const [dropTargetKey, setDropTargetKey] = useState<string | null>(null);
  // Count of live drop-enter events to avoid flicker from child elements triggering dragLeave.
  const dropEnterCount = useRef(0);

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

  // Build unified grid rows — one per TrainingClass when configured, else legacy BLOCK_GROUPS.
  // GridRow abstracts the difference so the render loop is identical for both modes.
  type GridRow = {
    key: string;
    shortLabel: string;
    fullLabel: string;
    getCellFn: (period: number) => DisplaySession | null;
    emptyCellClickFn: (period: number) => void;
    dropKeySuffix: (period: number) => string;
  };
  const gridRows: GridRow[] = trainingClasses.length > 0
    ? trainingClasses.slice().sort((a, b) => a.sequence - b.sequence).map(tc => ({
        key: tc.training_class_id,
        shortLabel: tc.display_name,
        fullLabel: tc.display_name,
        getCellFn: (p: number) => getCellByClassId(sessions, tc.training_class_id, p),
        emptyCellClickFn: (p: number) => { if (onEmptyCellClick) onEmptyCellClick("", p, tc.training_class_id); else onHeaderClick(); },
        dropKeySuffix: (p: number) => `${p}-${tc.training_class_id}`,
      }))
    : BLOCK_GROUPS.map(g => ({
        key: g.key,
        shortLabel: g.label,
        fullLabel: g.fullLabel,
        getCellFn: (p: number) => getCell(sessions, g.cadetGroups, p),
        emptyCellClickFn: (p: number) => { if (onEmptyCellClick) onEmptyCellClick(g.cadetGroups[0], p); else onHeaderClick(); },
        dropKeySuffix: (p: number) => `${p}-${g.cadetGroups[0]}`,
      }));

  const totalCells = (sessionCount ?? 0) * gridRows.length;
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
        {/* CLASS-23: collapse toggle — stops propagation so header nav doesn't fire */}
        <button
          className="pw-block-collapse-btn"
          onClick={e => { e.stopPropagation(); setCollapsed(v => !v); }}
          onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.stopPropagation(); setCollapsed(v => !v); } }}
          aria-label={collapsed ? "Expand parade night" : "Collapse parade night"}
          aria-expanded={!collapsed}
          title={collapsed ? "Expand" : "Collapse"}
        >
          {collapsed ? "▶" : "▼"}
        </button>
      </div>

      {/* ── Collapsible body (CLASS-23) ─────────────────────────────────────── */}
      {!collapsed && <>

      {/* ── Notices band ────────────────────────────────────────────────────── */}
      <div className="pw-block-band">
        <div className="pw-block-band-hdr">
          <span>Notices</span>
          <button
            className="pw-block-add-notice-btn"
            style={{ fontSize: 'var(--fs-2xs)', background: "none", border: "1px solid var(--border)", borderRadius: 4, padding: "1px 6px", cursor: "pointer", color: "var(--muted-text)", fontWeight: 700 }}
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
          {gridRows.map(row => {
            const cells = BLOCK_PERIODS.map(p => row.getCellFn(p));
            const allEmpty = cells.every(c => c === null);
            return (
              // Mouse-only shortcut for the same action as the block header above
              // (which already has a real, focusable, keyboard-operable role="button")
              // — intentionally not a second tab stop for the identical action.
              // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions
              <div
                key={row.key}
                className={`pw-block-cg-row${allEmpty ? " all-empty" : ""}`}
                onClick={onHeaderClick}
              >
                <span className="pw-block-cg-lbl">{row.shortLabel}</span>
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
              {gridRows.map(row => (
                <tr key={row.key}>
                  <th>{row.fullLabel}</th>
                  {BLOCK_PERIODS.map(period => {
                    const cell = row.getCellFn(period);
                    if (!cell) {
                      const cellKey = row.dropKeySuffix(period);
                      const isDropTarget = dropTargetKey === cellKey;
                      // A11Y-G6: while a session is picked up, every empty cell is a keyboard
                      // drop target and Enter places rather than adds.
                      const isArmed = !!moveSource && !!onMoveSession;
                      const placeHere = () => {
                        if (!moveSource || !onMoveSession) return;
                        // _targetCadetGroup is unused by EightWeekView's handleMoveSession
                        // (it preserves payload.cadet_group), so passing "" is safe.
                        void onMoveSession(moveSource, dateId, period, "");
                      };
                      return (
                        <td
                          key={period}
                          className={`pw-night-cell empty${isDropTarget ? " dnd-over" : ""}${isArmed ? " pw-move-target" : ""}`}
                          style={isDropTarget ? { outline: "2px dashed var(--aafc-blue, #51b0e3)", background: "var(--surface-2, #f0f5fa)" } : undefined}
                          onClick={isArmed ? placeHere : () => row.emptyCellClickFn(period)}
                          role="button"
                          tabIndex={0}
                          onKeyDown={e => {
                            if (isArmed && e.key === "Escape") { e.preventDefault(); onCancelMove?.(); return; }
                            if (isArmed && (e.key === "Enter" || e.key === "m" || e.key === "M")) {
                              e.preventDefault(); e.stopPropagation(); placeHere(); return;
                            }
                            if (e.key === "Enter") row.emptyCellClickFn(period);
                          }}
                          aria-label={isArmed
                            ? `Empty slot, ${row.fullLabel} period ${period}. Press Enter to move ${moveSource?.activity_title ?? "the session"} here, or Escape to cancel.`
                            : (onEmptyCellClick ? `Empty slot, ${row.fullLabel} period ${period}. Press Enter to add a session.` : "No lesson — press Enter to open night detail")}
                          onDragEnter={onMoveSession ? e => { e.preventDefault(); dropEnterCount.current++; setDropTargetKey(cellKey); } : undefined}
                          onDragLeave={onMoveSession ? () => { dropEnterCount.current = Math.max(0, dropEnterCount.current - 1); if (dropEnterCount.current === 0) setDropTargetKey(null); } : undefined}
                          onDragOver={onMoveSession ? e => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; } : undefined}
                          onDrop={onMoveSession ? e => {
                            e.preventDefault();
                            setDropTargetKey(null);
                            dropEnterCount.current = 0;
                            const raw = e.dataTransfer.getData("application/json");
                            if (!raw) return;
                            let payload: DragSessionPayload;
                            try { payload = JSON.parse(raw) as DragSessionPayload; } catch { return; }
                            onMoveSession(payload, dateId, period, "");
                          } : undefined}
                        >
                          <div className="pw-night-cell-inner">
                            <span className="pw-nc-empty">{isDropTarget || isArmed ? "Move here" : "No lesson"}</span>
                          </div>
                        </td>
                      );
                    }
                    const classDimmed = focusClassId != null &&
                      !(cell.training_classes ?? []).some(c => c.training_class_id === focusClassId);
                    // CLASS-22: dim sessions where no audience class belongs to the focused stage.
                    const stageDimmed = !!focusStageId && !(cell.training_classes ?? []).some(
                      c => classStageMap?.[c.training_class_id] === focusStageId,
                    );
                    const q = searchText?.trim().toLowerCase();
                    const searchDimmed = !!q && !(
                      cell.title?.toLowerCase().includes(q) ||
                      cell.code?.toLowerCase().includes(q)
                    );
                    // CLASS-21: dim by curriculum tier (core_status from CurriculumItem).
                    const tierDimmed = !!tierFilter && (() => {
                      if (tierFilter === "foundation") return cell.core_status !== "core";
                      if (tierFilter === "extension")  return cell.core_status !== "additional";
                      return false;
                    })();
                    const isDimmed = classDimmed || stageDimmed || searchDimmed || tierDimmed;
                    const canDrag = !!onMoveSession && !!cell.source;
                    const isMoveSource = !!moveSource && moveSource.session_id === cell.session_id;
                    return (
                      <td
                        key={period}
                        className={`pw-night-cell${cell.conflict === "room" ? " conflict-room" : cell.conflict === "fac" ? " conflict-fac" : ""}${isMoveSource ? " pw-move-source" : ""}`}
                        style={isDimmed && !isMoveSource ? { opacity: 0.22 } : undefined}
                        draggable={canDrag}
                        onDragStart={canDrag ? e => {
                          e.stopPropagation();
                          e.dataTransfer.effectAllowed = "move";
                          e.dataTransfer.setData("application/json", JSON.stringify(buildPayload(cell)));
                        } : undefined}
                        onDragEnd={canDrag ? () => { setDropTargetKey(null); dropEnterCount.current = 0; } : undefined}
                        onClick={onSessionClick ? e => { e.stopPropagation(); onSessionClick(cell); } : onHeaderClick}
                        role="button"
                        tabIndex={0}
                        aria-keyshortcuts={canDrag ? "M" : undefined}
                        aria-label={canDrag
                          ? (isMoveSource
                              ? `${cell.title ?? "Session"} — picked up to move. Tab to an empty slot and press Enter to place it, or press Escape to cancel.`
                              : `${cell.title ?? "Session"}, ${row.fullLabel} period ${period}. Press Enter to open, or M to pick it up and move it.`)
                          : undefined}
                        onKeyDown={e => {
                          // A11Y-G6: keyboard equivalent of dragging. Drag is a pointer-only
                          // gesture, so every move it can perform must also be reachable here.
                          if (canDrag && (e.key === "m" || e.key === "M")) {
                            e.preventDefault(); e.stopPropagation();
                            if (isMoveSource) onCancelMove?.();
                            else onPickUpSession?.(buildPayload(cell));
                            return;
                          }
                          if (e.key === "Escape" && moveSource) {
                            e.preventDefault(); e.stopPropagation();
                            onCancelMove?.();
                            return;
                          }
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

      </>}{/* end CLASS-23 collapsible body */}
    </div>
  );
}
