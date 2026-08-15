import { useMemo, useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { planningApi, trainingApi } from "../../../api";
import { friendlyMessage } from "../../../api/client";
import type { PlanningSession, PlanningFacilitator, AnchorEvent, NightSummary } from "../../../api/types";
import { filterAnchors } from "../../../utils/planningFilters";
import {
  ParadeNightBlock,
  fromPlanningSession,
  conflictMapFromPlanningConflicts,
  type DisplaySession,
  type DragSessionPayload,
} from "../ParadeNightBlock";
import { ActivityDetailBlock, anchorToDisplay } from "../ActivityDetailBlock";
import { useToast } from "../../Toast";

interface Props {
  yearId: string;
  weeks?: number;
  customStart?: string;
  customEnd?: string;
  facilitators: PlanningFacilitator[];
  onDateClick: (dateId: string, date: string) => void;
  onSessionClick: (session: PlanningSession, dateId: string, date: string) => void;
  onEmptyCellClick?: (dateId: string, date: string, cadetGroup: string, period: number) => void;
  onAnchorClick?: (anchor: AnchorEvent) => void;
  layers?: { conflicts?: boolean; wingHQEvents?: boolean };
  audience?: Set<string>;
  priority?: Set<string>;
  focusClassId?: string | null;
  searchText?: string | null;
  tierFilter?: string | null;
  focusStageId?: string | null;
  classStageMap?: Record<string, string>;
}

export function EightWeekView({
  yearId, weeks = 8, customStart, customEnd, facilitators,
  onDateClick, onSessionClick, onEmptyCellClick, onAnchorClick,
  layers, audience, priority, focusClassId, searchText, tierFilter,
  focusStageId, classStageMap,
}: Props) {
  const showConflicts = layers?.conflicts ?? true;
  const showAnchors = layers?.wingHQEvents ?? true;
  const qc = useQueryClient();
  const { toast } = useToast();

  // DND-01: move session handler — preserves all existing session fields and
  // updates only parade_night_id and period_number on the target cell.
  const handleMoveSession = useCallback(async (payload: DragSessionPayload, targetDateId: string, targetPeriod: number, _targetCadetGroup: string) => {
    try {
      await trainingApi.editSession(payload.session_id, {
        parade_night_id: targetDateId,
        period_number: targetPeriod,
        curriculum_item_id: payload.curriculum_id ?? null,
        cadet_group: payload.cadet_group ?? null,
        facilitator_id: payload.facilitator_id ?? null,
        training_area_id: payload.location_id ?? null,
        custom_title: payload.curriculum_id ? null : (payload.activity_title ?? null),
        status: payload.status,
      });
      await qc.invalidateQueries({ queryKey: ["planning-long-range"] });
      await qc.invalidateQueries({ queryKey: ["planning-night-summaries"] });
      toast("Session moved.");
    } catch (e) {
      toast(friendlyMessage(e, "Could not move session — it may have a conflict."));
    }
  }, [qc, toast]);

  const isCustom = !!(customStart && customEnd);

  const { data, isLoading, error } = useQuery({
    queryKey: ["planning-long-range", yearId, customStart ?? weeks, customEnd ?? ""],
    queryFn: () => planningApi.longRange(yearId, weeks, customStart, customEnd),
    enabled: !isCustom || customEnd! >= customStart!,
    staleTime: 5 * 60 * 1000,
  });

  const { data: nightData } = useQuery({
    queryKey: ["planning-night-summaries", yearId],
    queryFn: () => planningApi.nightSummaries(yearId),
    staleTime: 5 * 60 * 1000,
  });

  const nightSummaryMap = useMemo(
    () => new Map<string, NightSummary>(
      nightData?.summaries.map(s => [s.parade_date_id, s]) ?? [],
    ),
    [nightData],
  );

  if (isLoading) return <div className="pw-loading">Loading {weeks}-week programme…</div>;
  if (error || !data) {
    const msg = friendlyMessage(error, "Unknown error");
    return (
      <div className="pw-err" style={{ padding: 16 }}>
        <div style={{ fontWeight: 700, marginBottom: 4 }}>Could not load planning data</div>
        <div style={{ fontSize: 12, opacity: .8 }}>{msg}</div>
        <div style={{ fontSize: 11, marginTop: 6, color: "var(--muted-text)" }}>
          Check that the date range is valid, and that you have an internet connection.
        </div>
      </div>
    );
  }

  if (data.parade_dates.length === 0) {
    return (
      <div className="pw-empty">
        <span>No parade nights in the next {weeks} weeks.</span>
        <span style={{ fontSize: 11 }}>Ensure parade dates are set up in the annual program.</span>
      </div>
    );
  }

  const visibleAnchors = showAnchors
    ? filterAnchors(data.anchors, audience ?? new Set(), priority ?? new Set())
    : [];

  return (
    <div className="pw-8week">
      {visibleAnchors.length > 0 && (
        <div className="pw-anchor-strip" style={{ marginBottom: 12, display: "flex", flexWrap: "wrap", gap: 8 }}>
          {visibleAnchors.map((a, i) => (
            <div key={a.anchor_event_id ?? a.anchor_id ?? String(i)} style={{ minWidth: 220, maxWidth: 320, flex: "0 0 auto" }}>
              <ActivityDetailBlock
                activity={anchorToDisplay(a)}
                compact={false}
                onClick={onAnchorClick ? () => onAnchorClick(a) : undefined}
              />
            </div>
          ))}
        </div>
      )}

      {data.parade_dates.map(row => {
        const pd = row.parade_date;
        const night = nightSummaryMap.get(pd.parade_date_id);

        // REM-39 residual: canonical backend conflict data (row.conflicts,
        // already used below for unresolvedCount), not the client-side
        // heuristic -- matches YearView/TermView's own fromNightSummary path.
        const conflictMap = showConflicts
          ? conflictMapFromPlanningConflicts(row.conflicts)
          : undefined;
        const displaySessions = fromPlanningSession(row.sessions, conflictMap);
        const unresolvedCount = row.conflicts.filter(c => !c.is_resolved).length;

        function handleSessionClick(ds: DisplaySession) {
          if (ds.source) {
            onSessionClick(ds.source, pd.parade_date_id, pd.parade_date);
          } else {
            onDateClick(pd.parade_date_id, pd.parade_date);
          }
        }

        return (
          <ParadeNightBlock
            key={pd.parade_date_id}
            dateId={pd.parade_date_id}
            date={pd.parade_date}
            weekNumber={pd.week_number}
            term={pd.term}
            notices={night?.notices ?? []}
            sessions={displaySessions}
            sessionCount={row.session_count}
            filledSlots={row.filled_slots}
            conflictCount={unresolvedCount}
            inHoliday={false}
            compact={false}
            focusClassId={focusClassId}
            searchText={searchText}
            tierFilter={tierFilter}
            focusStageId={focusStageId}
            classStageMap={classStageMap}
            onHeaderClick={() => onDateClick(pd.parade_date_id, pd.parade_date)}
            onSessionClick={handleSessionClick}
            onEmptyCellClick={onEmptyCellClick
              ? (cg, period) => onEmptyCellClick(pd.parade_date_id, pd.parade_date, cg, period)
              : undefined}
            onMoveSession={handleMoveSession}
          />
        );
      })}
    </div>
  );
}
