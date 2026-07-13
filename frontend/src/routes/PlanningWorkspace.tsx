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
import type { PlanningSession, AnchorEvent } from "../api/types";


export function PlanningWorkspace() {
  const { session } = useAuth();
  const qc = useQueryClient();

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
  const [bottomOpen, setBottomOpen] = useState(false);
  const [bottomTab, setBottomTab] = useState<BottomTab>("activities");
  const [layers, setLayers] = useState<LayerState>(defaultLayers);
  const [audience, setAudience] = useState<Set<string>>(new Set());
  const [priority, setPriority] = useState<Set<string>>(new Set());

  // ── Data queries ──────────────────────────────────────────────────────────────
  const { data: years, isLoading: yearsLoading } = useQuery({
    queryKey: ["planning-years"],
    queryFn: planningApi.years,
    staleTime: 5 * 60 * 1000,
  });

  // Validate/update the cached year_id once the years response arrives.
  useEffect(() => {
    if (!years) return;
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

  function handleDateClick(dateId: string, _date: string) {
    setSelectedDateId(dateId);
    setViewRange("parade-night");
  }

  function handleSessionClick(s: PlanningSession, dateId: string, date: string) {
    setDrawerItem({ type: "session", session: s, dateId, date, conflicts: [] });
  }

  async function handleSessionByIdClick(sessionId: string, dateId: string, date: string) {
    const s = await planningApi.getSession(sessionId);
    setDrawerItem({ type: "session", session: s, dateId, date, conflicts: [] });
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
  }

  function handleViewRangeChange(mode: ViewMode) {
    setViewRange(mode);
    if (mode !== "parade-night") setSelectedDateId(null);
  }

  // ── Canvas content ────────────────────────────────────────────────────────────
  function renderCanvas() {
    if (yearsLoading) return <div className="pw-loading">Loading planning years…</div>;
    if (!yearsLoading && years && years.length === 0) {
      return (
        <SetupPanel
          session={session}
          onYearCreated={() => qc.invalidateQueries({ queryKey: ["planning-years"] })}
        />
      );
    }
    if (!selectedYearId) {
      return (
        <div className="pw-empty">
          <span>No planning year available.</span>
          <span style={{ fontSize: 11 }}>Ask your wing or national admin to set up a planning year.</span>
        </div>
      );
    }

    // List view applies across all range types
    if (displayMode === "list" && viewRange !== "parade-night") {
      return (
        <ListView
          yearId={selectedYearId}
          viewRange={viewRange}
          customStart={customStart}
          customEnd={customEnd}
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
            <span style={{ fontSize: 11 }}>Switch to Year or 8-week view and click a parade date.</span>
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
            <span style={{ fontSize: 11 }}>Use the From and To inputs in the toolbar to set your range.</span>
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
      />

      {/* Year selector + quick actions */}
      {selectedYearId && (
        <div style={{ background: "var(--surface)", borderBottom: "1px solid var(--border)", padding: "4px 14px", display: "flex", gap: 8, alignItems: "center" }}>
          {yearOptions && (
            <>
              <span style={{ fontSize: 11, fontWeight: 700, color: "var(--muted-text)" }}>Year:</span>
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
            style={{ fontSize: 11, padding: "3px 10px" }}
            onClick={() => setDrawerItem({ type: "new-anchor", yearId: selectedYearId })}
          >
            + Anchor event
          </button>
        </div>
      )}

      {/* Main body: left + canvas + right */}
      <div className={`pw-body${drawerItem ? " right-open" : ""}`}>
        {/* Left panel */}
        <PlanningLeftPanel
          layers={layers}
          onLayerToggle={handleLayerToggle}
          audience={audience}
          onAudienceToggle={handleAudienceToggle}
          priority={priority}
          onPriorityToggle={handlePriorityToggle}
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
                fontSize: 11, fontWeight: 700, cursor: "pointer", zIndex: 20,
              }}
              onClick={() => setBottomOpen(true)}
            >
              Activities ▲
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
        />
      )}
    </div>
  );
}

export { PlanningWorkspace as PlanningWorkspaceRoute };
