import { useState, useEffect } from "react";
import { Modal } from "../Modal";
import { Button } from "../ui";
import { planningApi, orgApi } from "../../api";
import { ApiError } from "../../api/client";
import type { PlanningYear, TimingTemplateFull } from "../../api/types";

// TRGO-03: a guided year-setup flow reachable at any time (not just when a squadron
// has zero PlanningYears -- see SetupPanel.tsx for the original cold-start-only flow,
// left unchanged so its existing coverage/behaviour doesn't regress). Every step here
// is optional except creating/selecting the target year; each write goes through the
// same endpoints the rest of the app uses (copy-setup, timing-template apply-from-date,
// generate-parade-dates), so the same conflict detection, optimistic locking, and audit
// logging already enforced there applies here too.
//
// The former "placement" step (bulk curriculum scheduling via legacy cadet_group strings)
// was removed: it conflated Training Period with Session and used the deprecated cadet_group
// model incompatible with multi-class-per-stage squadrons. Curriculum planning now happens
// from the Planning Workspace once parade nights are set up.

type Step = "start" | "timing" | "dates" | "done";

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

  // Years that already have a row can be offered as a copy-from source.
  const materialised = years.filter(y => y.planning_year_id && y.year != null);
  const mostRecent = materialised.length > 0 ? materialised[materialised.length - 1] : null;

  // ── Step: start (materialise year; optionally copy class structure) ──────────
  const [copyClasses, setCopyClasses] = useState<boolean>(!!mostRecent);
  const thisYear = new Date().getFullYear();
  const [newYearNum, setNewYearNum] = useState(thisYear);

  async function runStart() {
    setLoading(true); setErr("");
    try {
      // Materialise the row. Name derives from the year integer (spec §6).
      const y = await planningApi.createYear({ year: newYearNum, name: String(newYearNum) });
      const id = (y as unknown as Record<string, unknown>).planning_year_id as string;
      setYearId(id);
      setYearLabel(String(newYearNum));
      if (copyClasses && mostRecent) {
        await planningApi.copySetup({ source_year: Number(mostRecent.year), target_year: newYearNum, copy_classes: true, copy_parade_pattern: false });
      }
      setDatesAlreadyDone(false);
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
          <p className="muted" style={{ fontSize: 'var(--fs-sm)' }}>
            You can keep refining timing and dates at any time from the Planning
            Workspace toolbar or by reopening this guided setup. Plan curriculum sessions
            from the Planning Workspace once your parade nights are set.
          </p>
          <Button onClick={() => { onDone(); onClose(); }}>Close</Button>
        </div>
      </Modal>
    );
  }

  return (
    <Modal title="Guided year setup" onClose={onClose}>
      <div className="form">
        <ol style={{ display: "flex", gap: 6, fontSize: 'var(--fs-xs)', listStyle: "none", padding: 0, margin: "0 0 10px" }}>
          {(["start", "timing", "dates"] as Step[]).map((s) => (
            <li key={s} style={{
              padding: "2px 8px", borderRadius: 999,
              background: s === step ? "var(--aafc-blue, #51b0e3)" : "var(--surface-2, #f0f5fa)",
              color: s === step ? "#fff" : "var(--muted-text)", fontWeight: 700,
            }}>{s}</li>
          ))}
        </ol>

        {step === "start" && (
          <>
            <p className="muted" style={{ fontSize: 'var(--fs-sm)' }}>
              Set up a training year, then optionally apply a timing template and generate
              parade dates. Plan curriculum from the Planning Workspace once dates are set.
            </p>
            <div style={{ marginTop: 8 }}>
              <label>Year
                <input type="number" min={2020} max={2040} value={newYearNum}
                  onChange={(e) => setNewYearNum(Number(e.target.value))}
                  style={{ marginLeft: 8, width: 100 }} />
              </label>
            </div>
            {mostRecent && (
              <label style={{ display: "flex", gap: 8, alignItems: "center", fontWeight: 400, marginTop: 10 }}>
                <input type="checkbox" checked={copyClasses} onChange={e => setCopyClasses(e.target.checked)} />
                Copy training class structure from {mostRecent.year}
              </label>
            )}
            <p className="muted" style={{ fontSize: 'var(--fs-2xs)', marginTop: 6 }}>
              Parade nights, sessions, and cadet records are never copied.
            </p>
            {err && <div className="err" role="alert">{err}</div>}
            <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
              <Button onClick={onClose} variant="out">Cancel</Button>
              <Button onClick={runStart} disabled={loading}>
                {loading ? "Setting up…" : "Set up " + newYearNum + " →"}
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
      <p className="muted" style={{ fontSize: 'var(--fs-sm)' }}>
        Apply a unit timing template so new parade nights from a chosen date onward use its
        period structure. Existing parade nights already created are never changed by this step.
      </p>
      {loadingList && <p style={{ fontSize: 'var(--fs-sm)' }}>Loading timing templates…</p>}
      {templates && templates.length === 0 && (
        <p style={{ fontSize: 'var(--fs-sm)' }}>
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
            <p style={{ fontSize: 'var(--fs-sm)', marginTop: 4 }}>
              <strong>{chosen.name}</strong> will become effective from {effectiveFrom} onward.
              Any currently open-ended template will be closed the day before.
            </p>
          )}
        </>
      )}
      {applied && (
        <p style={{ fontSize: 'var(--fs-base)', color: "var(--success)", fontWeight: 700 }}>
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

// ── Step: generate parade dates ──────────────────────────────────────────────────────────
function DatesStep({ yearId, squadronId, alreadyDone, onSkip, onDone }: {
  yearId: string; squadronId?: string; alreadyDone: boolean; onSkip: () => void; onDone: () => void;
}) {
  const [weekday, setWeekday] = useState(3); // Thursday, until the squadron's own setting loads (below)
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [frequency, setFrequency] = useState("weekly");
  const [excludeHolidays, setExcludeHolidays] = useState(true);
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
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
        ...(startTime ? { parade_start_time: startTime } : {}),
        ...(endTime ? { parade_end_time: endTime } : {}),
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
        <p style={{ fontSize: 'var(--fs-base)', color: "var(--success)", fontWeight: 700 }}>
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
      <p className="muted" style={{ fontSize: 'var(--fs-sm)' }}>Generate the recurring parade-night dates for this year.</p>
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
            <label>Parade start time <span className="muted" style={{ fontWeight: 400 }}>(optional)</span>
              <input type="time" value={startTime} onChange={(e) => setStartTime(e.target.value)}
                placeholder="HH:MM" title="Overrides the squadron default parade start time" />
            </label>
            <label>Parade end time <span className="muted" style={{ fontWeight: 400 }}>(optional)</span>
              <input type="time" value={endTime} onChange={(e) => setEndTime(e.target.value)}
                placeholder="HH:MM" title="Overrides the squadron default parade end time" />
            </label>
          </div>
          <label style={{ display: "flex", gap: 8, alignItems: "center", fontWeight: 400, marginTop: 6 }}>
            <input type="checkbox" checked={excludeHolidays} onChange={(e) => setExcludeHolidays(e.target.checked)} />
            Exclude public holiday periods
          </label>
        </>
      )}
      {result && (
        <p style={{ fontSize: 'var(--fs-base)', color: "var(--success)", fontWeight: 700 }}>
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

