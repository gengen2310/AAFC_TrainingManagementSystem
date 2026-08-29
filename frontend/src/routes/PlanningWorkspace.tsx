import { useState, useEffect, useCallback } from "react";

// The YEAR NUMBER is what persists, not a row id. A year with no row is still a
// real year, so a UUID cannot express the selection -- and TMS hands over a year
// number, so storing an id here is what let the two applications disagree.
const PW_YEAR_KEY = "aafc_pw_year";
// The row id is cached only as a hint, so year-scoped queries can fire before
// the /years response arrives (the ~1.6s waterfall this file already avoids).
// It is always re-validated against /years, and never the source of truth.
const PW_YEAR_ID_HINT = "aafc_pw_year_id";

function readStoredYear(): number | null {
  const raw = localStorage.getItem(PW_YEAR_KEY);
  const n = raw ? parseInt(raw, 10) : NaN;
  return Number.isFinite(n) ? n : null;
}
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthProvider";
import { planningApi } from "../api";
import type { PlanningYear } from "../api/types";
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



// YR-3: choose the training year the unit is most likely to want on open.
// The API returns years ordered year-descending, so "first active" meant
// "newest year ever created" -- creating a year for a future season silently
// moved the whole workspace to it. Prefer the active year matching today, then
// the nearest active year ahead, then the most recent behind.
export function pickDefaultYear<T extends { year: number; active_status?: boolean }>(list: T[]): T | null {
  const yrs = (list ?? []).filter(Boolean);
  if (!yrs.length) return null;
  const act = yrs.filter(y => y.active_status);
  const pool = act.length ? act : yrs;
  const now = new Date().getFullYear();
  const exact = pool.find(y => Number(y.year) === now);
  if (exact) return exact;
  const ahead = pool.filter(y => Number(y.year) > now).sort((a, b) => a.year - b.year);
  if (ahead.length) return ahead[0];
  const behind = pool.filter(y => Number(y.year) < now).sort((a, b) => b.year - a.year);
  if (behind.length) return behind[0];
  return pool[0];
}

/**
 * Which body PW should render for the selected year. Pure, so the decision can
 * be tested without mounting the page -- and because the previous form of it
 * silently stopped being reachable.
 *
 *   "setup"       the year has no container and can still be planned
 *   "past-empty"  the year has no container and is history; setup must not be offered
 *   "workspace"   there is a container to show
 *   "loading"     the list has not resolved yet
 */
export function pwYearView(
  yearsLoaded: boolean,
  selectedYear: { year: number; materialised?: boolean; state?: string } | null,
  selectedYearId: string | null,
): "loading" | "setup" | "past-empty" | "workspace" {
  if (!yearsLoaded) return "loading";
  if (selectedYear && selectedYear.materialised === false) {
    return selectedYear.state === "past" ? "past-empty" : "setup";
  }
  if (!selectedYearId) return "loading";
  return "workspace";
}

/**
 * Which year PW should show, given what TMS handed over, what was stored, and
 * what the API returned. Pure, because this decision is exactly what let TMS
 * and PW disagree about the year, and it must be testable without a browser.
 *
 * Returns the year NUMBER plus the row id when one exists. The id may be null:
 * a year nobody has written to is still a real, selectable year.
 */
export function resolveYearSelection(
  years: Pick<PlanningYear, "year" | "planning_year_id" | "active_status">[],
  requestedYear: number | null,
  storedYear: number | null,
): { year: number; id: string | null } | null {
  const idFor = (y: number) =>
    years.find(r => r.year === y)?.planning_year_id ?? null;

  // 1. An explicit handover wins, even for a year with no row. Falling through
  //    to the default here is what made PW show 2026 while TMS showed 2027.
  if (requestedYear != null && Number.isFinite(requestedYear)) {
    return { year: requestedYear, id: idFor(requestedYear) };
  }

  // 2. Keep the stored year while it is still on offer (or nothing is).
  if (storedYear != null) {
    const known = years.some(r => r.year === storedYear);
    if (known || years.length === 0) return { year: storedYear, id: idFor(storedYear) };
  }

  // 3. Otherwise fall back to the default year.
  const active = pickDefaultYear(years);
  return active ? { year: active.year, id: active.planning_year_id ?? null } : null;
}

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
  const [selectedYearNum, setSelectedYearNum] = useState<number | null>(readStoredYear);
  const [selectedYearId, setSelectedYearId] = useState<string | null>(
    () => localStorage.getItem(PW_YEAR_ID_HINT),
  );
  const [selectedDateId, setSelectedDateId] = useState<string | null>(null);

  const persistYear = useCallback((year: number, id: string | null) => {
    localStorage.setItem(PW_YEAR_KEY, String(year));
    if (id) localStorage.setItem(PW_YEAR_ID_HINT, id);
    else localStorage.removeItem(PW_YEAR_ID_HINT);
    setSelectedYearNum(year);
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
    queryFn: () => planningApi.years(resolvedSquadronId, true),
    enabled: scoped,
    staleTime: 5 * 60 * 1000,
  });

  // Validate/update the cached year_id once the years response arrives.
  useEffect(() => {
    if (!years) return;
    // Honor a year pre-selected by the TMS → PW handoff fragment (#t=...&y=YYYY)
    const reqYearStr = sessionStorage.getItem("aafc_requested_year");
    let requested: number | null = null;
    if (reqYearStr) {
      sessionStorage.removeItem("aafc_requested_year");
      const n = parseInt(reqYearStr, 10);
      requested = Number.isFinite(n) ? n : null;
    }
    const next = resolveYearSelection(years, requested, selectedYearNum);
    if (!next) return;
    if (next.year !== selectedYearNum || next.id !== selectedYearId) {
      persistYear(next.year, next.id);
    }
  }, [years]);

  const selectedYear = years?.find(y => y.year === selectedYearNum) ?? null;

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
    // The year is REAL even with no container -- only its configuration is
    // empty -- so never say it does not exist, and never send the user to an
    // admin for something they can do themselves. The decision lives in
    // pwYearView so it can be tested: its previous form gated on
    // `years.length === 0`, which stopped being reachable the moment this page
    // began listing logical years, silently orphaning SetupPanel.
    const view = pwYearView(!yearsLoading && !!years, selectedYear, selectedYearId);

    if (view === "loading") {
      return <div className="pw-loading">Loading planning years…</div>;
    }
    if (view === "past-empty" && selectedYear) {
      return (
        <div className="pw-empty">
          <span><strong>Read-only.</strong> {selectedYear.year} is complete.</span>
          <span style={{ fontSize: 'var(--fs-xs)' }}>
            Nothing was scheduled for {selectedYear.year}. To add records to a past
            year, a Wing administrator can open Delegated Intervention.
          </span>
        </div>
      );
    }
    if (view === "setup") {
      return (
        <SetupPanel
          session={session}
          squadronId={resolvedSquadronId}
          onYearCreated={() => qc.invalidateQueries({ queryKey: ["planning-years"] })}
        />
      );
    }
    // Unreachable once view === "workspace" -- pwYearView returns "loading"
    // without an id -- but the compiler cannot see through the helper, and the
    // queries below take a plain string.
    if (!selectedYearId) {
      return <div className="pw-loading">Loading planning year…</div>;
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

      {/* Year selector + quick actions.
          AUDIT-2026-08 G10 / WCAG 1.4.10 — flexWrap here is load-bearing. This row renders one
          chip per planning year and the action buttons ("+ Anchor event" and siblings) come
          AFTER them, so without wrapping a unit with many years pushes those actions off-screen.
          .pw-root is overflow:hidden, so they cannot be scrolled to at any viewport width.
          Measured at 1440px against 131 seeded years: 12,918px of content in a 1,195px box.
          A maxHeight cap was tried here and removed: capping the row pushed those same action
          buttons below its scroll fold, which is the defect this fix exists to prevent. Wrapping
          alone keeps every control reachable. A realistic unit has a handful of years; the 687px
          height only appears against seeded data with 131 of them. */}
      {selectedYearId && (
        <div style={{ background: "var(--surface)", borderBottom: "1px solid var(--border)", padding: "4px 14px", display: "flex", flexWrap: "wrap", gap: 8, rowGap: 6, alignItems: "center" }}>
          {yearOptions && (
            <>
              <span style={{ fontSize: 'var(--fs-xs)', fontWeight: 700, color: "var(--muted-text)" }}>Year:</span>
              {yearOptions.map(y => (
                <button
                  // Keyed and selected by the YEAR, not the row id: a year with no
                  // row has a null id, so two of them would collide as React keys
                  // and -- worse -- every row-less year would read as selected at
                  // once, because null === null.
                  key={y.year}
                  type="button"
                  // PW-A1: selection was carried by the "on" class alone. The filter
                  // chips beside these already expose aria-pressed; the year chips did
                  // not, so which of 63 years was selected was visual-only.
                  aria-pressed={selectedYearNum === y.year}
                  className={`pw-chip${selectedYearNum === y.year ? " on" : ""}`}
                  onClick={() => { persistYear(y.year, y.planning_year_id); setSelectedDateId(null); }}
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
          {/* Reported 2026-08-25: "the guided mode is very useful - but very hard
              to find it". It sat second in this row as a 12px outline button,
              indistinguishable from the maintenance action beside it. It is the
              primary way to set a year up, so it now leads the row, carries the
              primary style, and says what it does rather than naming itself. */}
          {canWriteSquadron(session) && (
            <button
              className="btn sm"
              style={{ fontSize: 'var(--fs-xs)', padding: "4px 12px", fontWeight: 600 }}
              onClick={() => setGuidedSetupOpen(true)}
              title="Generate this year's parade nights, terms and holidays step by step"
            >
              Set up this year — guided
            </button>
          )}
          {canWriteSquadron(session) && (
            <button
              className="btn sm out"
              style={{ fontSize: 'var(--fs-xs)', padding: "3px 10px" }}
              onClick={() => setUpdatingParadeDay(true)}
            >
              Update future parade nights…
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
