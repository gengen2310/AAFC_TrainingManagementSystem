import { useState, useEffect } from "react";
import { Modal } from "../Modal";
import { Button } from "../ui";
import { planningApi, trainingApi, orgApi } from "../../api";
import { ApiError } from "../../api/client";
import type { PlanningYear, TimingTemplateFull, CurriculumItem } from "../../api/types";

// TRGO-03: a guided year-setup flow reachable at any time (not just when a squadron
// has zero PlanningYears -- see SetupPanel.tsx for the original cold-start-only flow,
// left unchanged so its existing coverage/behaviour doesn't regress). Every step here
// is optional except creating/selecting the target year; each write goes through the
// same endpoints the rest of the app uses (rollover, timing-template apply-from-date,
// generate-parade-dates, create-session), so the same conflict detection, optimistic
// locking, and audit logging already enforced there applies here too -- nothing new
// is invented, this is a guided sequence over existing, validated actions.
//
// Bulk placement is a genuine second, non-drag-and-drop way to assign curriculum to
// slots (there is no drag-and-drop anywhere in this app today -- the existing method
// is already a keyboard-accessible click-to-open-form flow). This adds a multi-select
// "place one curriculum item across several open slots at once" method, reusing the
// exact create-session call the single-slot form uses.

type Step = "start" | "timing" | "dates" | "placement" | "done";
const CADET_GROUPS = ["orientation", "initial", "junior", "intermediate", "senior"] as const;
const PERIODS = [1, 2, 3, 4, 5, 6];

interface Props {
  years: PlanningYear[];
  squadronId?: string;
  onClose: () => void;
  onDone: () => void;
}

export function GuidedYearSetupModal({ years, squadronId, onClose, onDone }: Props) {
  const [step, setStep] = useState<Step>("start");
  const [yearId, setYearId] = useState<string | null>(null);
  const [yearLabel, setYearLabel] = useState<string>("");
  const [datesAlreadyDone, setDatesAlreadyDone] = useState(false);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const mostRecent = years.length > 0 ? years[years.length - 1] : null;

  // ── Step: start (create new year OR roll over from most recent) ──────────────
  const [method, setMethod] = useState<"new" | "rollover">(mostRecent ? "rollover" : "new");
  const thisYear = new Date().getFullYear();
  const [newYearNum, setNewYearNum] = useState(thisYear);
  const [newYearName, setNewYearName] = useState(`${thisYear}–${thisYear + 1} Training Year`);

  async function runStart() {
    setLoading(true); setErr("");
    try {
      if (method === "rollover" && mostRecent) {
        const r = await planningApi.rolloverYear(mostRecent.planning_year_id, {});
        setYearId(r.new_planning_year_id);
        setYearLabel(r.name);
        setDatesAlreadyDone(true);
      } else {
        const y = await planningApi.createYear({ year: newYearNum, name: newYearName.trim() });
        const id = (y as unknown as Record<string, unknown>).planning_year_id as string;
        setYearId(id);
        setYearLabel(newYearName.trim());
        setDatesAlreadyDone(false);
      }
      setStep("timing");
    } catch (e) {
      setErr(e instanceof ApiError ? e.friendly : "Could not set up the planning year.");
    } finally {
      setLoading(false);
    }
  }

  if (step === "done") {
    return (
      <Modal title="Guided year setup" onClose={() => { onDone(); onClose(); }}>
        <div className="form">
          <p><strong>Setup complete for {yearLabel}.</strong></p>
          <p className="muted" style={{ fontSize: 12 }}>
            You can keep refining timing, dates, and placements at any time from the Planning
            Workspace toolbar or by reopening this guided setup.
          </p>
          <Button onClick={() => { onDone(); onClose(); }}>Close</Button>
        </div>
      </Modal>
    );
  }

  return (
    <Modal title="Guided year setup" onClose={onClose}>
      <div className="form">
        <ol style={{ display: "flex", gap: 6, fontSize: 11, listStyle: "none", padding: 0, margin: "0 0 10px" }}>
          {(["start", "timing", "dates", "placement"] as Step[]).map((s) => (
            <li key={s} style={{
              padding: "2px 8px", borderRadius: 999,
              background: s === step ? "var(--aafc-blue, #51b0e3)" : "var(--surface-2, #f0f5fa)",
              color: s === step ? "#fff" : "var(--muted-text)", fontWeight: 700,
            }}>{s}</li>
          ))}
        </ol>

        {step === "start" && (
          <>
            <p className="muted" style={{ fontSize: 12 }}>
              Set up a new training year, then optionally apply a timing template, generate
              parade dates, and bulk-place curriculum onto open slots.
            </p>
            {mostRecent && (
              <div role="radiogroup" aria-label="Setup method" style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <label style={{ display: "flex", gap: 8, alignItems: "center", fontWeight: 400 }}>
                  <input type="radio" name="ys-method" checked={method === "rollover"} onChange={() => setMethod("rollover")} />
                  Roll over from {mostRecent.name} (copies holidays and the parade-date pattern; historical records are never changed)
                </label>
                <label style={{ display: "flex", gap: 8, alignItems: "center", fontWeight: 400 }}>
                  <input type="radio" name="ys-method" checked={method === "new"} onChange={() => setMethod("new")} />
                  Create a blank new planning year
                </label>
              </div>
            )}
            {method === "new" && (
              <div style={{ display: "grid", gridTemplateColumns: "120px 1fr", gap: 10, marginTop: 8 }}>
                <label>Year
                  <input type="number" min={2020} max={2040} value={newYearNum}
                    onChange={(e) => { const y = Number(e.target.value); setNewYearNum(y); setNewYearName(`${y}–${y + 1} Training Year`); }} />
                </label>
                <label>Name
                  <input value={newYearName} onChange={(e) => setNewYearName(e.target.value)} />
                </label>
              </div>
            )}
            {err && <div className="err" role="alert">{err}</div>}
            <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
              <Button onClick={onClose} variant="out">Cancel</Button>
              <Button onClick={runStart} disabled={loading || (method === "new" && !newYearName.trim())}>
                {loading ? "Setting up…" : "Continue →"}
              </Button>
            </div>
          </>
        )}

        {step === "timing" && yearId && (
          <TimingStep
            onSkip={() => setStep("dates")}
            onDone={() => setStep("dates")}
          />
        )}

        {step === "dates" && yearId && (
          <DatesStep
            yearId={yearId}
            squadronId={squadronId}
            alreadyDone={datesAlreadyDone}
            onSkip={() => setStep("placement")}
            onDone={() => setStep("placement")}
          />
        )}

        {step === "placement" && yearId && (
          <PlacementStep
            yearId={yearId}
            onSkip={() => setStep("done")}
            onDone={() => setStep("done")}
          />
        )}
      </div>
    </Modal>
  );
}

// ── Step: apply a timing template ─────────────────────────────────────────────
function TimingStep({ onSkip, onDone }: { onSkip: () => void; onDone: () => void }) {
  const [templates, setTemplates] = useState<TimingTemplateFull[] | null>(null);
  const [selected, setSelected] = useState<string>("");
  const [effectiveFrom, setEffectiveFrom] = useState(new Date().toISOString().slice(0, 10));
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingList, setLoadingList] = useState(false);
  const [err, setErr] = useState("");
  const [applied, setApplied] = useState<{ closed_previous_count: number } | null>(null);

  async function loadTemplates() {
    setLoadingList(true); setErr("");
    try {
      const list = await planningApi.listTimingTemplates();
      setTemplates(list);
      if (list.length > 0) setSelected(list.find((t) => t.is_default)?.timing_template_id ?? list[0].timing_template_id);
    } catch (e) {
      setErr(e instanceof ApiError ? e.friendly : "Could not load timing templates.");
    } finally {
      setLoadingList(false);
    }
  }

  async function apply() {
    if (!selected) return;
    setLoading(true); setErr("");
    try {
      const r = await planningApi.applyTimingTemplateFromDate(selected, {
        effective_from: effectiveFrom, reason: reason.trim() || undefined,
      });
      setApplied({ closed_previous_count: r.closed_previous_count });
    } catch (e) {
      setErr(e instanceof ApiError ? e.friendly : "Could not apply this timing template.");
    } finally {
      setLoading(false);
    }
  }

  if (templates === null && !loadingList) {
    void loadTemplates();
  }

  const chosen = templates?.find((t) => t.timing_template_id === selected) ?? null;

  return (
    <>
      <p className="muted" style={{ fontSize: 12 }}>
        Apply a unit timing template so new parade nights from a chosen date onward use its
        period structure. Existing parade nights already created are never changed by this step.
      </p>
      {loadingList && <p style={{ fontSize: 12 }}>Loading timing templates…</p>}
      {templates && templates.length === 0 && (
        <p style={{ fontSize: 12 }}>
          No timing templates exist yet for this squadron. Create one from Unit Settings,
          then reopen this step — or skip and continue without one.
        </p>
      )}
      {templates && templates.length > 0 && !applied && (
        <>
          <label htmlFor="ys-timing-template">Timing template</label>
          <select id="ys-timing-template" value={selected} onChange={(e) => setSelected(e.target.value)}>
            {templates.map((t) => (
              <option key={t.timing_template_id} value={t.timing_template_id}>
                {t.name} — {t.instructional_period_count} period{t.instructional_period_count === 1 ? "" : "s"}
                {t.is_default ? " (default)" : ""}
              </option>
            ))}
          </select>
          <label htmlFor="ys-timing-from">Apply from date</label>
          <input id="ys-timing-from" type="date" value={effectiveFrom} onChange={(e) => setEffectiveFrom(e.target.value)} />
          <label htmlFor="ys-timing-reason">Reason (optional)</label>
          <input id="ys-timing-reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Applying this year's standard timing" />
          {chosen && (
            <p style={{ fontSize: 12, marginTop: 4 }}>
              <strong>{chosen.name}</strong> will become effective from {effectiveFrom} onward.
              Any currently open-ended template will be closed the day before.
            </p>
          )}
        </>
      )}
      {applied && (
        <p style={{ fontSize: 13, color: "var(--success)", fontWeight: 700 }}>
          ✓ Applied. {applied.closed_previous_count > 0 && `${applied.closed_previous_count} previously open template(s) closed.`}
        </p>
      )}
      {err && <div className="err" role="alert">{err}</div>}
      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        <Button variant="out" onClick={onSkip}>Skip this step</Button>
        {templates && templates.length > 0 && !applied && (
          <Button onClick={apply} disabled={loading || !selected}>{loading ? "Applying…" : "Apply template"}</Button>
        )}
        {applied && <Button onClick={onDone}>Continue →</Button>}
      </div>
    </>
  );
}

// Mon=0 .. Sun=6, matching connected-frontend's _DAY_NAME_TO_INT convention.
const _DAY_NAME_TO_INDEX: Record<string, number> = {
  Monday: 0, Tuesday: 1, Wednesday: 2, Thursday: 3, Friday: 4, Saturday: 5, Sunday: 6,
};

// ── Step: generate parade dates (skipped/shown-as-done if rollover already copied them) ──
function DatesStep({ yearId, squadronId, alreadyDone, onSkip, onDone }: {
  yearId: string; squadronId?: string; alreadyDone: boolean; onSkip: () => void; onDone: () => void;
}) {
  const [weekday, setWeekday] = useState(3); // Thursday, until the squadron's own setting loads (below)
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [frequency, setFrequency] = useState("weekly");
  const [excludeHolidays, setExcludeHolidays] = useState(true);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [result, setResult] = useState<{ created: number } | null>(null);

  // Seed the weekday picker from the Squadron's own Parade Day setting (Unit
  // Settings) -- previously this always hardcoded Thursday regardless of
  // what the squadron had actually configured.
  useEffect(() => {
    if (!squadronId) return;
    let cancelled = false;
    orgApi.squadron(squadronId).then(sq => {
      if (cancelled) return;
      const idx = sq.default_parade_day ? _DAY_NAME_TO_INDEX[sq.default_parade_day] : undefined;
      if (idx !== undefined) setWeekday(idx);
    }).catch(() => { /* keep the Thursday default if the fetch fails */ });
    return () => { cancelled = true; };
  }, [squadronId]);

  async function generate() {
    if (!startDate || !endDate) { setErr("Start and end dates are required."); return; }
    setLoading(true); setErr("");
    try {
      const r = await planningApi.generateParadeDates(yearId, {
        weekday, start_date: startDate, end_date: endDate, frequency, exclude_holidays: excludeHolidays,
      });
      setResult({ created: r.created });
    } catch (e) {
      setErr(e instanceof ApiError ? e.friendly : "Could not generate parade dates.");
    } finally {
      setLoading(false);
    }
  }

  if (alreadyDone) {
    return (
      <>
        <p style={{ fontSize: 13, color: "var(--success)", fontWeight: 700 }}>
          ✓ Parade dates were copied automatically as part of the roll-over.
        </p>
        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
          <Button onClick={onDone}>Continue →</Button>
        </div>
      </>
    );
  }

  return (
    <>
      <p className="muted" style={{ fontSize: 12 }}>Generate the recurring parade-night dates for this year.</p>
      {!result && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <label>Parade weekday
              <select value={weekday} onChange={(e) => setWeekday(Number(e.target.value))}>
                {["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].map((w, i) => (
                  <option key={w} value={i}>{w}</option>
                ))}
              </select>
            </label>
            <label>Frequency
              <select value={frequency} onChange={(e) => setFrequency(e.target.value)}>
                <option value="weekly">Weekly</option>
                <option value="fortnightly">Fortnightly</option>
                <option value="monthly">Monthly</option>
              </select>
            </label>
            <label>Start date
              <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </label>
            <label>End date
              <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
            </label>
          </div>
          <label style={{ display: "flex", gap: 8, alignItems: "center", fontWeight: 400, marginTop: 6 }}>
            <input type="checkbox" checked={excludeHolidays} onChange={(e) => setExcludeHolidays(e.target.checked)} />
            Exclude public holiday periods
          </label>
        </>
      )}
      {result && (
        <p style={{ fontSize: 13, color: "var(--success)", fontWeight: 700 }}>
          ✓ {result.created} parade date{result.created === 1 ? "" : "s"} generated.
        </p>
      )}
      {err && <div className="err" role="alert">{err}</div>}
      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        <Button variant="out" onClick={onSkip}>Skip this step</Button>
        {!result && <Button onClick={generate} disabled={loading}>{loading ? "Generating…" : "Generate dates"}</Button>}
        {result && <Button onClick={onDone}>Continue →</Button>}
      </div>
    </>
  );
}

// ── Step: bulk-place a curriculum item across multiple open slots ────────────
// Non-drag-and-drop placement method: pick a curriculum item + cadet group + period,
// find open (unoccupied) slots across a date range, multi-select which to fill, and
// create them all in one action. Every created session goes through the same
// POST .../sessions endpoint the single-slot click-to-open-form flow uses, so the
// same facilitator/room conflict detection, optimistic locking, and audit logging
// already enforced there applies automatically -- no parallel/bypassing write path.
function PlacementStep({ yearId, onSkip, onDone }: { yearId: string; onSkip: () => void; onDone: () => void }) {
  const [curriculumItems, setCurriculumItems] = useState<CurriculumItem[] | null>(null);
  const [curriculumId, setCurriculumId] = useState("");
  const [cadetGroup, setCadetGroup] = useState<typeof CADET_GROUPS[number]>("junior");
  const [period, setPeriod] = useState(1);
  const [rangeStart, setRangeStart] = useState("");
  const [rangeEnd, setRangeEnd] = useState("");
  const [slots, setSlots] = useState<{ dateId: string; date: string }[] | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [result, setResult] = useState<{ placed: number; failed: number } | null>(null);

  if (curriculumItems === null) {
    void trainingApi.curriculum().then((r) => setCurriculumItems(r.items)).catch(() => setCurriculumItems([]));
  }

  async function findSlots() {
    setLoading(true); setErr(""); setSlots(null); setSelected(new Set());
    try {
      const ns = await planningApi.nightSummaries(yearId);
      const inRange = ns.summaries.filter((n) =>
        (!rangeStart || n.parade_date >= rangeStart) && (!rangeEnd || n.parade_date <= rangeEnd));
      const open = inRange
        .filter((n) => !n.sessions.some((s) => s.period === period))
        .map((n) => ({ dateId: n.parade_date_id, date: n.parade_date }));
      setSlots(open);
      setSelected(new Set(open.map((s) => s.dateId)));
    } catch (e) {
      setErr(e instanceof ApiError ? e.friendly : "Could not look up open slots.");
    } finally {
      setLoading(false);
    }
  }

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  async function placeAll() {
    if (!curriculumId || selected.size === 0) return;
    setLoading(true); setErr("");
    let placed = 0, failed = 0;
    for (const dateId of selected) {
      try {
        await planningApi.createSession(dateId, {
          cadet_group: cadetGroup, session_number: period, curriculum_id: curriculumId,
        });
        placed++;
      } catch {
        failed++;
      }
    }
    setResult({ placed, failed });
    setLoading(false);
  }

  return (
    <>
      <p className="muted" style={{ fontSize: 12 }}>
        Place one curriculum item across several open slots at once — an alternative to
        placing sessions one at a time from the calendar view.
      </p>
      {!result && (
        <>
          <label htmlFor="ys-place-curric">Curriculum item</label>
          <select id="ys-place-curric" value={curriculumId} onChange={(e) => setCurriculumId(e.target.value)}>
            <option value="">Select…</option>
            {(curriculumItems ?? []).map((c) => (
              <option key={c.curriculum_id} value={c.curriculum_id}>{c.code} — {c.title}</option>
            ))}
          </select>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <label>Cadet group
              <select value={cadetGroup} onChange={(e) => setCadetGroup(e.target.value as typeof cadetGroup)}>
                {CADET_GROUPS.map((g) => <option key={g} value={g}>{g}</option>)}
              </select>
            </label>
            <label>Period
              <select value={period} onChange={(e) => setPeriod(Number(e.target.value))}>
                {PERIODS.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </label>
            <label>From date
              <input type="date" value={rangeStart} onChange={(e) => setRangeStart(e.target.value)} />
            </label>
            <label>To date
              <input type="date" value={rangeEnd} onChange={(e) => setRangeEnd(e.target.value)} />
            </label>
          </div>
          <div style={{ marginTop: 8 }}>
            <Button variant="out" onClick={findSlots} disabled={loading}>{loading ? "Searching…" : "Find open slots"}</Button>
          </div>

          {slots && slots.length === 0 && (
            <p style={{ fontSize: 12, marginTop: 8 }}>No open slots for period {period} in this range.</p>
          )}
          {slots && slots.length > 0 && (
            <div style={{ maxHeight: 200, overflowY: "auto", border: "1px solid var(--border)", borderRadius: 6, marginTop: 8 }}>
              <table style={{ width: "100%", fontSize: 12 }}>
                <thead><tr><th>Include</th><th>Date</th></tr></thead>
                <tbody>
                  {slots.map((s) => (
                    <tr key={s.dateId}>
                      <td>
                        <input type="checkbox" checked={selected.has(s.dateId)} onChange={() => toggle(s.dateId)}
                          aria-label={`Place on ${s.date}`} />
                      </td>
                      <td>{s.date}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
      {result && (
        <p style={{ fontSize: 13, fontWeight: 700, color: result.failed > 0 ? "var(--warn, #c97a00)" : "var(--success)" }}>
          ✓ {result.placed} session{result.placed === 1 ? "" : "s"} placed.
          {result.failed > 0 && ` ${result.failed} could not be placed (a conflict was detected — review them individually in the calendar view).`}
        </p>
      )}
      {err && <div className="err" role="alert">{err}</div>}
      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        <Button variant="out" onClick={onSkip}>Skip this step</Button>
        {!result && slots && slots.length > 0 && (
          <Button onClick={placeAll} disabled={loading || !curriculumId || selected.size === 0}>
            {loading ? "Placing…" : `Place on ${selected.size} slot${selected.size === 1 ? "" : "s"}`}
          </Button>
        )}
        {result && <Button onClick={onDone}>Finish →</Button>}
      </div>
    </>
  );
}
