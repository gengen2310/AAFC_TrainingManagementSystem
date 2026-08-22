import { useState, useEffect, useCallback } from "react";

const PW_YEAR_KEY = "aafc_pw_year_id";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthProvider";
import { planningApi } from "../api";
import { PlanningContextBar, type ViewMode, type DisplayMode } from "../components/planning/PlanningContextBar";
import { ListView } from "../components/planning/views/ListView";
import { PlanningLeftPanel, defaultLayers, type LayerState } from "../components/planning/PlanningLeftPanel";
import { PlanningRightDrawer, type DrawerItem } from "../components/planning/PlanningRightDrawer";
import { PlanningBottomDrawer, type BottomTab } from "../components/planning/PlanningBottomDrawer";
import { YearView } from "../components/planning/views/YearView";
import { TermView } from "../components/planning/views/TermView";
import { EightWeekView } from "../components/planning/views/EightWeekView";
import { TwoWeekView } from "../components/planning/views/TwoWeekView";
import { ParadeNightGridView } from "../components/planning/views/ParadeNightGridView";
import { SetupPanel } from "../components/planning/SetupPanel";
import { UpdateFutureParadeDayModal } from "../components/planning/UpdateFutureParadeDayModal";
import { GuidedYearSetupModal } from "../components/planning/GuidedYearSetupModal";
import { canWriteSquadron } from "../auth/permissions";
import { useScopedSquadron } from "../layout/SquadronViewContext";
import { SquadronSelector } from "../layout/SquadronSelector";
import { HelpDrawer } from "../components/HelpDrawer";
import type { PlanningSession, AnchorEvent } from "../api/types";


export function PlanningWorkspace() {
  const { session } = useAuth();
  const qc = useQueryClient();
  // wing_admin/national_admin/system_admin have no session.squadron_id of their
  // own -- without an explicit squadron pick, GET /api/planning/years falls back
  // to "every squadron in the wing" or "every squadron nationwide, no filter at
  // all", and this page used to silently auto-select years[0] from that
  // undifferentiated list with no indication of whose plan was showing (Stage
  // 10, 2026-08-05). resolvedSquadronId also feeds the bottom drawer's
  // canonical-Activities lookup (Stage 6), which previously only worked for
  // squadron-role sessions.
  const { needsSelection, squadronId: pickedSquadronId, scoped } = useScopedSquadron();
  const resolvedSquadronId = session?.squadron_id ?? pickedSquadronId;

  // Body class to remove .main padding/max-width
  useEffect(() => {
    document.body.classList.add("pw-active");
    return () => { document.body.classList.remove("pw-active"); };
  }, []);

  const [viewRange, setViewRange] = useState<ViewMode>("year");
  const [displayMode, setDisplayMode] = useState<DisplayMode>("calendar");
  const [customStart, setCustomStart] = useState("");
  const [customEnd, setCustomEnd] = useState("");
  // Initialise from localStorage so year-scoped queries fire immediately without waiting
  // for the /years response (eliminates ~1.6s waterfall on repeat visits).
  const [selectedYearId, setSelectedYearId] = useState<string | null>(
    () => localStorage.getItem(PW_YEAR_KEY),
  );
  const [selectedDateId, setSelectedDateId] = useState<string | null>(null);

  const persistYear = useCallback((id: string) => {
    localStorage.setItem(PW_YEAR_KEY, id);
    setSelectedYearId(id);
  }, []);
  const [drawerItem, setDrawerItem] = useState<DrawerItem | null>(null);
  const [updatingParadeDay, setUpdatingParadeDay] = useState(false);
  const [guidedSetupOpen, setGuidedSetupOpen] = useState(false);
  const [bottomOpen, setBottomOpen] = useState(false);
  const [bottomTab, setBottomTab] = useState<BottomTab>("activities");
  const [layers, setLayers] = useState<LayerState>(defaultLayers);
  const [audience, setAudience] = useState<Set<string>>(new Set());
  const [priority, setPriority] = useState<Set<string>>(new Set());
  const [focusClassId, setFocusClassId] = useState<string | null>(null);
  const [focusStageId, setFocusStageId] = useState<string | null>(null);
  const [searchText, setSearchText] = useState<string>("");
  const [tierFilter, setTierFilter] = useState<string | null>(null);
  // Mobile-only: left filter/backlog panel is off-canvas below 768px, toggled via the
  // hamburger button in the context bar. Ignored (has no visual effect) above that width.
  const [leftPanelOpen, setLeftPanelOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);

  useEffect(() => {
    if (!leftPanelOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setLeftPanelOpen(false); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [leftPanelOpen]);

  // ── Data queries ──────────────────────────────────────────────────────────────
  const { data: years, isLoading: yearsLoading } = useQuery({
    queryKey: ["planning-years", resolvedSquadronId],
    queryFn: () => planningApi.years(resolvedSquadronId),
    enabled: scoped,
    staleTime: 5 * 60 * 1000,
  });

  // Validate/update the cached year_id once the years response arrives.
  useEffect(() => {
    if (!years) return;
    // Honor a year pre-selected by the TMS → PW handoff fragment (#t=...&y=YYYY)
    const reqYearStr = sessionStorage.getItem("aafc_requested_year");
    if (reqYearStr) {
      sessionStorage.removeItem("aafc_requested_year");
      const reqYear = parseInt(reqYearStr, 10);
      const match = years.find(y => y.year === reqYear);
      if (match) { persistYear(match.planning_year_id); return; }
    }
    const active = years.find(y => y.active_status) ?? years[0];
    if (!active) return;
    if (active.planning_year_id !== selectedYearId) {
      persistYear(active.planning_year_id);
    }
  }, [years]);

  const selectedYear = years?.find(y => y.planning_year_id === selectedYearId) ?? null;

  const { data: cc } = useQuery({
    queryKey: ["planning-cc", selectedYearId],
    queryFn: () => planningApi.commandCentre(selectedYearId!),
    enabled: !!selectedYearId,
    staleTime: 2 * 60 * 1000,
  });

  // CLASS-22: map class_id → stage_id for stage focus dimming in ParadeNightBlock.
  const classStageMap: Record<string, string> = {};
  for (const tc of cc?.training_classes ?? []) {
    if (tc.training_stage_id) classStageMap[tc.training_class_id] = tc.training_stage_id;
  }

  // REM-39 follow-up: previously only ParadeNightGridView (the single-night
  // detail grid) ever received real conflict data -- Year/Term/8-Week/2-Week/
  // custom-range views (including the default landing view) hardcoded
  // conflicts:[] in handleSessionClick/handleSessionByIdClick below, so a
  // session could have a genuine unresolved PlanningConflict but show no
  // indicator and offer no override from the view most users land on first.
  // planningApi.conflicts() already existed with zero call sites; wiring it
  // in here closes the gap for every view without touching any of them.
  const { data: yearConflicts = [] } = useQuery({
    queryKey: ["planning-conflicts", selectedYearId],
    queryFn: () => planningApi.conflicts(selectedYearId!),
    enabled: !!selectedYearId,
    staleTime: 60 * 1000,
  });
  function conflictsForSession(sessionId: string) {
    return yearConflicts.filter(c => c.scheduled_session_id === sessionId && !c.is_resolved);
  }

  const { data: facilitators = [] } = useQuery({
    queryKey: ["planning-facilitators"],
    queryFn: planningApi.facilitators,
    staleTime: 10 * 60 * 1000,
  });

  const { data: locations = [] } = useQuery({
    queryKey: ["planning-locations"],
    queryFn: planningApi.locations,
    staleTime: 10 * 60 * 1000,
  });

  // ── Handlers ───────────────────────────────────────────────────────────────────
  function handleLayerToggle(key: keyof LayerState) {
    setLayers(prev => ({ ...prev, [key]: !prev[key] }));
  }

  function handleAudienceToggle(a: string) {
    setAudience(prev => {
      const next = new Set(prev);
      next.has(a) ? next.delete(a) : next.add(a);
      return next;
    });
  }

  function handlePriorityToggle(p: string) {
    setPriority(prev => {
      const next = new Set(prev);
      next.has(p) ? next.delete(p) : next.add(p);
      return next;
    });
  }

  function handleClassFocus(classId: string | null) {
    setFocusClassId(prev => (prev === classId ? null : classId));
  }

  function handleDateClick(dateId: string, _date: string) {
    setSelectedDateId(dateId);
    setViewRange("parade-night");
    setLeftPanelOpen(false);
  }

  function handleSessionClick(s: PlanningSession, dateId: string, date: string) {
    setDrawerItem({ type: "session", session: s, dateId, date, conflicts: conflictsForSession(s.session_id) });
  }

  async function handleSessionByIdClick(sessionId: string, dateId: string, date: string) {
    const s = await planningApi.getSession(sessionId);
    setDrawerItem({ type: "session", session: s, dateId, date, conflicts: conflictsForSession(sessionId) });
  }

  function handleEmptyCellClick(dateId: string, date: string, cadetGroup: string, period: number) {
    setDrawerItem({ type: "new-session", cadetGroup, periodNumber: period, dateId });
  }

  function handleAnchorClick(anchor: AnchorEvent) {
    if (!selectedYearId) return;
    setDrawerItem({ type: "anchor", anchor, yearId: selectedYearId });
  }

  async function handleBacklogItemClick(type: string, id: string) {
    if (type === "curriculum") {
      const cc_item = cc?.unscheduled_required.find(u => u.curriculum_id === id);
      if (cc_item) {
        setDrawerItem({ type: "curriculum", curriculum: cc_item });
      }
    } else if (type === "wing-event") {
      try {
        const event = await planningApi.getWingEvent(id);
        setDrawerItem({ type: "wing-event", event });
      } catch {
        // silently ignore — event may not be accessible
      }
    }
    setLeftPanelOpen(false);
  }

  function handleViewRangeChange(mode: ViewMode) {
    setViewRange(mode);
    if (mode !== "parade-night") setSelectedDateId(null);
  }

  // ── Canvas content ────────────────────────────────────────────────────────────
  function renderCanvas() {
    if (needsSelection && !pickedSquadronId) {
      // AppShell's own SquadronSelector (rendered in the nav sidebar) covers
      // full-app mode, but MODULE_MODE's ModuleEntry (App.tsx) never mounts
      // AppShell at all -- a wing/national user opening the standalone
      // Planning Workspace preview had no selector anywhere on the page,
      // despite this exact text telling them to use one "above". Render a
      // real, working selector inline so the message is always actionable
      // regardless of which shell the page is running in (PW-CTX-01 P0
      // incident, 2026-08-08).
      return (
        <div className="pw-empty">
          <div style={{ maxWidth: 280, margin: "0 auto" }}>
            <SquadronSelector />
          </div>
          <span>Select a squadron above to view its Planning Workspace.</span>
        </div>
      );
    }
    if (yearsLoading) return <div className="pw-loading">Loading planning years…</div>;
    if (!yearsLoading && years && years.length === 0) {
      return (
        <SetupPanel
          session={session}
          squadronId={resolvedSquadronId}
          onYearCreated={() => qc.invalidateQueries({ queryKey: ["planning-years"] })}
        />
      );
    }
    if (!selectedYearId) {
      return (
        <div className="pw-empty">
          <span>No planning year available.</span>
          <span style={{ fontSize: 'var(--fs-xs)' }}>Ask your wing or national admin to set up a planning year.</span>
        </div>
      );
    }
    // DEF-02: selectedYearId may be a stale localStorage value from a previous
    // environment or database reset. If years have loaded and the cached id is
    // not in the list, the useEffect above will pick the correct active year on
    // the next render cycle. Show loading rather than firing API calls with a
    // year_id that doesn't exist (which would return 404 and show an error flash).
    if (years && !selectedYear) {
      return <div className="pw-loading">Loading planning year…</div>;
    }

    // List view applies across all range types
    if (displayMode === "list" && viewRange !== "parade-night") {
      return (
        <ListView
          yearId={selectedYearId}
          viewRange={viewRange}
          customStart={customStart}
          customEnd={customEnd}
          conflicts={yearConflicts}
          onDateClick={handleDateClick}
          onAnchorClick={handleAnchorClick}
        />
      );
    }

    if (viewRange === "year") {
      return (
        <YearView
          yearId={selectedYearId}
          onDateClick={handleDateClick}
          onSessionClick={handleSessionByIdClick}
          onEmptyCellClick={handleEmptyCellClick}
          onAnchorClick={handleAnchorClick}
          layers={layers}
          audience={audience}
          priority={priority}
          conflicts={yearConflicts}
        />
      );
    }
    if (viewRange === "term") {
      return (
        <TermView
          yearId={selectedYearId}
          onDateClick={handleDateClick}
          onSessionClick={handleSessionByIdClick}
          onEmptyCellClick={handleEmptyCellClick}
          onAnchorClick={handleAnchorClick}
          layers={layers}
          audience={audience}
          priority={priority}
          focusClassId={focusClassId}
          searchText={searchText || null}
          tierFilter={tierFilter}
          focusStageId={focusStageId}
          classStageMap={classStageMap}
          conflicts={yearConflicts}
        />
      );
    }
    if (viewRange === "8week") {
      return (
        <EightWeekView
          yearId={selectedYearId}
          weeks={8}
          facilitators={facilitators}
          onDateClick={handleDateClick}
          onSessionClick={handleSessionClick}
          onEmptyCellClick={handleEmptyCellClick}
          onAnchorClick={handleAnchorClick}
          layers={layers}
          audience={audience}
          priority={priority}
          focusClassId={focusClassId}
          searchText={searchText || null}
          tierFilter={tierFilter}
          focusStageId={focusStageId}
          classStageMap={classStageMap}
        />
      );
    }
    if (viewRange === "2week") {
      return (
        <TwoWeekView
          yearId={selectedYearId}
          facilitators={facilitators}
          onDateClick={handleDateClick}
          onSessionClick={handleSessionClick}
        />
      );
    }
    if (viewRange === "parade-night") {
      if (!selectedDateId) {
        return (
          <div className="pw-empty">
            <span>No parade night selected.</span>
            <span style={{ fontSize: 'var(--fs-xs)' }}>Switch to Year or 8-week view and click a parade date.</span>
            <button className="btn sm out" onClick={() => setViewRange("year")}>Go to Year view</button>
          </div>
        );
      }
      return (
        <ParadeNightGridView
          dateId={selectedDateId}
          facilitators={facilitators}
          onCellClick={setDrawerItem}
        />
      );
    }
    if (viewRange === "custom") {
      if (!customStart || !customEnd) {
        return (
          <div className="pw-empty">
            <span>Select a date range above.</span>
            <span style={{ fontSize: 'var(--fs-xs)' }}>Use the From and To inputs in the toolbar to set your range.</span>
          </div>
        );
      }
      if (customEnd < customStart) {
        return (
          <div className="pw-empty pw-empty-warn">
            <span>End date must be after start date.</span>
          </div>
        );
      }
      return (
        <EightWeekView
          yearId={selectedYearId}
          customStart={customStart}
          customEnd={customEnd}
          facilitators={facilitators}
          onDateClick={handleDateClick}
          onSessionClick={handleSessionClick}
          onEmptyCellClick={handleEmptyCellClick}
          layers={layers}
          audience={audience}
          priority={priority}
          focusClassId={focusClassId}
          searchText={searchText || null}
          tierFilter={tierFilter}
          focusStageId={focusStageId}
          classStageMap={classStageMap}
        />
      );
    }
    return null;
  }

  // ── Year picker (shown when multiple years exist) ─────────────────────────────
  const yearOptions = years && years.length > 1 ? years : null;

  return (
    <div className="pw-root" role="main" aria-label="Planning workspace">
      {/* Context bar */}
      <PlanningContextBar
        session={session}
        year={selectedYear}
        cc={cc ?? null}
        viewRange={viewRange}
        displayMode={displayMode}
        customStart={customStart}
        customEnd={customEnd}
        onRangeChange={handleViewRangeChange}
        onDisplayModeChange={setDisplayMode}
        onCustomStartChange={setCustomStart}
        onCustomEndChange={setCustomEnd}
        onToggleLeftPanel={() => setLeftPanelOpen(o => !o)}
        onHelpOpen={() => setHelpOpen(true)}
      />

      {/* Year selector + quick actions */}
      {selectedYearId && (
        <div style={{ background: "var(--surface)", borderBottom: "1px solid var(--border)", padding: "4px 14px", display: "flex", gap: 8, alignItems: "center" }}>
          {yearOptions && (
            <>
              <span style={{ fontSize: 'var(--fs-xs)', fontWeight: 700, color: "var(--muted-text)" }}>Year:</span>
              {yearOptions.map(y => (
                <button
                  key={y.planning_year_id}
                  className={`pw-chip${selectedYearId === y.planning_year_id ? " on" : ""}`}
                  onClick={() => { persistYear(y.planning_year_id); setSelectedDateId(null); }}
                >
                  {y.name}
                </button>
              ))}
              <span style={{ width: 1, height: 18, background: "var(--border)", margin: "0 4px" }} />
            </>
          )}
          <button
            className="btn sm out"
            style={{ fontSize: 'var(--fs-xs)', padding: "3px 10px" }}
            onClick={() => setDrawerItem({ type: "new-anchor", yearId: selectedYearId })}
          >
            + Anchor event
          </button>
          {canWriteSquadron(session) && (
            <button
              className="btn sm out"
              style={{ fontSize: 'var(--fs-xs)', padding: "3px 10px" }}
              onClick={() => setUpdatingParadeDay(true)}
            >
              Update future parade nights…
            </button>
          )}
          {canWriteSquadron(session) && (
            <button
              className="btn sm out"
              style={{ fontSize: 'var(--fs-xs)', padding: "3px 10px" }}
              onClick={() => setGuidedSetupOpen(true)}
            >
              Guided year setup…
            </button>
          )}
        </div>
      )}
      {updatingParadeDay && selectedYearId && (
        <UpdateFutureParadeDayModal
          yearId={selectedYearId}
          onClose={() => setUpdatingParadeDay(false)}
          onDone={() => qc.invalidateQueries({ queryKey: ["planning-cc"] })}
        />
      )}
      {guidedSetupOpen && (
        <GuidedYearSetupModal
          years={years ?? []}
          squadronId={resolvedSquadronId ?? undefined}
          onClose={() => setGuidedSetupOpen(false)}
          onDone={() => {
            qc.invalidateQueries({ queryKey: ["planning-years"] });
            qc.invalidateQueries({ queryKey: ["planning-cc"] });
            qc.invalidateQueries({ queryKey: ["planning-night-summaries"] });
          }}
        />
      )}

      {/* Main body: left + canvas + right */}
      <div className={`pw-body${drawerItem ? " right-open" : ""}`}>
        {/* Mobile-only backdrop for the off-canvas left panel. Tap-to-close is a mouse-only
            convenience; Escape (above) and re-tapping the hamburger button are the full
            keyboard-equivalent close paths. */}
        {leftPanelOpen && (
          // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions
          <div className="pw-left-overlay" onClick={() => setLeftPanelOpen(false)} />
        )}

        {/* Left panel */}
        <PlanningLeftPanel
          className={leftPanelOpen ? "pw-left-open" : ""}
          layers={layers}
          onLayerToggle={handleLayerToggle}
          audience={audience}
          onAudienceToggle={handleAudienceToggle}
          priority={priority}
          onPriorityToggle={handlePriorityToggle}
          focusClassId={focusClassId}
          onClassFocus={handleClassFocus}
          searchText={searchText}
          onSearchTextChange={setSearchText}
          tierFilter={tierFilter}
          onTierFilterChange={setTierFilter}
          focusStageId={focusStageId}
          onStageFocus={setFocusStageId}
          cc={cc ?? null}
          onBacklogItemClick={handleBacklogItemClick}
        />

        {/* Main canvas */}
        <div className="pw-canvas">
          {renderCanvas()}

          {/* Bottom drawer toggle */}
          {!bottomOpen && (
            <button
              style={{
                position: "fixed", bottom: 0, left: "50%", transform: "translateX(-50%)",
                background: "var(--aafc-dark-blue)", color: "#fff", border: 0,
                padding: "5px 20px", borderRadius: "8px 8px 0 0",
                fontSize: 'var(--fs-xs)', fontWeight: 700, cursor: "pointer", zIndex: 20,
              }}
              onClick={() => setBottomOpen(true)}
            >
              Planning Tools ▲
            </button>
          )}
        </div>

        {/* Right drawer */}
        {drawerItem && (
          <PlanningRightDrawer
            item={drawerItem}
            facilitators={facilitators}
            locations={locations}
            yearId={selectedYearId}
            onClose={() => setDrawerItem(null)}
          />
        )}
      </div>

      {/* Help drawer */}
      {helpOpen && (
        <HelpDrawer onClose={() => setHelpOpen(false)} />
      )}

      {/* Bottom drawer */}
      {bottomOpen && (
        <PlanningBottomDrawer
          yearId={selectedYearId}
          tab={bottomTab}
          onTabChange={(t) => setBottomTab(t)}
          onClose={() => setBottomOpen(false)}
          facilitators={facilitators}
          locations={locations}
          onItemClick={(item) => { setDrawerItem(item); setBottomOpen(false); }}
          squadronId={resolvedSquadronId ?? undefined}
        />
      )}
    </div>
  );
}

export { PlanningWorkspace as PlanningWorkspaceRoute };
