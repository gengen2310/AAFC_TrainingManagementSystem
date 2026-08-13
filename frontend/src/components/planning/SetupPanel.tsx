import { useState, useEffect } from "react";
import { planningApi, orgApi } from "../../api";
import { friendlyMessage } from "../../api/client";
import type { SessionInfo } from "../../api/types";

// Mon=0 .. Sun=6, matching connected-frontend's _DAY_NAME_TO_INT convention.
const _DAY_NAME_TO_INDEX: Record<string, number> = {
  Monday: 0, Tuesday: 1, Wednesday: 2, Thursday: 3, Friday: 4, Saturday: 5, Sunday: 6,
};

const JS_DOW = [1, 2, 3, 4, 5, 6, 0]; // Mon=0→JS1, ..., Sun=6→JS0

function previewDates(weekday: number, startDate: string, endDate: string, frequency: string): string[] {
  if (!startDate || !endDate) return [];
  const targetDay = JS_DOW[weekday];
  const end = new Date(endDate + "T00:00:00");
  const dates: string[] = [];

  if (frequency === "monthly") {
    // Mirror backend _compute_candidate_dates: daily iteration, include when
    // d.weekday() == weekday AND d.day <= 7 (first occurrence each month).
    const cur = new Date(startDate + "T00:00:00");
    while (cur <= end && dates.length < 60) {
      if (cur.getDay() === targetDay && cur.getDate() <= 7) {
        dates.push(cur.toISOString().slice(0, 10));
      }
      cur.setDate(cur.getDate() + 1);
    }
    return dates;
  }

  // weekly / fortnightly: advance to first matching weekday then step.
  const cur = new Date(startDate + "T00:00:00");
  while (cur.getDay() !== targetDay) cur.setDate(cur.getDate() + 1);
  const step = frequency === "fortnightly" ? 14 : 7;
  while (cur <= end && dates.length < 60) {
    dates.push(cur.toISOString().slice(0, 10));
    cur.setDate(cur.getDate() + step);
  }
  return dates;
}

function fmtDate(iso: string): string {
  return new Date(iso + "T00:00:00").toLocaleDateString("en-CA", { weekday: "short", month: "short", day: "numeric" });
}

const WEEKDAYS = [
  { value: 0, label: "Monday" },
  { value: 1, label: "Tuesday" },
  { value: 2, label: "Wednesday" },
  { value: 3, label: "Thursday" },
  { value: 4, label: "Friday" },
  { value: 5, label: "Saturday" },
  { value: 6, label: "Sunday" },
];

const FREQUENCIES = [
  { value: "weekly", label: "Weekly" },
  { value: "fortnightly", label: "Fortnightly (every 2 weeks)" },
  { value: "monthly", label: "Monthly" },
];

interface Props {
  session: SessionInfo | null;
  squadronId?: string;
  onYearCreated: () => void;
}

export function SetupPanel({ squadronId, onYearCreated }: Props) {
  const [step, setStep] = useState<"year" | "dates">("year");
  const [createdYearId, setCreatedYearId] = useState<string | null>(null);

  // Step 1 – create planning year
  const [yearNum, setYearNum] = useState(new Date().getFullYear());
  const [yearName, setYearName] = useState(`${new Date().getFullYear()}–${new Date().getFullYear() + 1} Training Year`);
  const [savingYear, setSavingYear] = useState(false);
  const [yearErr, setYearErr] = useState<string | null>(null);

  // Step 2 – generate parade dates
  const [weekday, setWeekday] = useState(3); // Thursday, until the squadron's own setting loads (below)
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [frequency, setFrequency] = useState("weekly");
  const [excludeHolidays, setExcludeHolidays] = useState(true);
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [savingDates, setSavingDates] = useState(false);
  const [datesErr, setDatesErr] = useState<string | null>(null);
  const [datesResult, setDatesResult] = useState<{ created: number; dates: string[] } | null>(null);

  // Seed the weekday picker from the Squadron's own Parade Day setting (Unit
  // Settings) -- previously this always hardcoded Thursday regardless of what
  // the squadron had actually configured, and this component never fetched
  // the squadron record at all.
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

  async function handleCreateYear() {
    if (!yearName.trim()) { setYearErr("Name is required."); return; }
    setSavingYear(true); setYearErr(null);
    try {
      const year = await planningApi.createYear({ year: yearNum, name: yearName.trim(), unit_id: squadronId });
      // createYear returns a PlanningYear — extract the ID from the response
      const id = (year as unknown as Record<string, unknown>).planning_year_id as string;
      setCreatedYearId(id);
      setStep("dates");
      onYearCreated();
    } catch (e: unknown) {
      setYearErr(friendlyMessage(e, "Failed to create planning year"));
    } finally {
      setSavingYear(false);
    }
  }

  async function handleGenerateDates() {
    if (!startDate || !endDate) { setDatesErr("Start and end dates are required."); return; }
    if (!createdYearId) return;
    setSavingDates(true); setDatesErr(null);
    try {
      const result = await planningApi.generateParadeDates(createdYearId, {
        weekday,
        start_date: startDate,
        end_date: endDate,
        frequency,
        exclude_holidays: excludeHolidays,
        ...(startTime ? { parade_start_time: startTime } : {}),
        ...(endTime ? { parade_end_time: endTime } : {}),
      });
      setDatesResult({ created: result.created, dates: result.dates });
      onYearCreated();
    } catch (e: unknown) {
      setDatesErr(friendlyMessage(e, "Failed to generate dates"));
    } finally {
      setSavingDates(false);
    }
  }

  return (
    <div className="pw-setup-panel">
      <div className="pw-setup-header">
        <h2>Set Up Planning Workspace</h2>
        <p>
          Planning Workspace is where you schedule parade nights, assign curriculum, and track training delivery.
          Before you can schedule training, you need a <strong>Training Year</strong>.
        </p>
        <p style={{ marginTop: 6 }}>
          A <strong>Training Year</strong> is a container for all your parade nights and training records for one academic year — typically July to June.
          Once you create one and generate your parade dates, the planning calendar appears.
        </p>
      </div>

      <div className="pw-setup-steps">
        {/* Step 1 */}
        <div className={`pw-setup-step${step === "year" ? " active" : step === "dates" ? " done" : ""}`}>
          <div className="pw-setup-step-num">{step === "dates" || datesResult ? "✓" : "1"}</div>
          <div className="pw-setup-step-body">
            <div className="pw-setup-step-title">Create Training Year</div>
            {step === "year" && (
              <div className="pw-drawer-form" style={{ maxWidth: 480 }}>
                <p style={{ fontSize: 12, color: "var(--muted-text)", margin: "0 0 12px" }}>
                  Name the training year. The name will appear on all reports and in the year selector.
                  Use a format like <em>2025–2026 Training Year</em>.
                </p>
                <div style={{ display: "grid", gridTemplateColumns: "120px 1fr", gap: 10 }}>
                  <label>
                    Year
                    <input
                      type="number"
                      value={yearNum}
                      min={2020}
                      max={2040}
                      onChange={e => {
                        const y = Number(e.target.value);
                        setYearNum(y);
                        setYearName(`${y}–${y + 1} Training Year`);
                      }}
                    />
                  </label>
                  <label>
                    Name
                    <input
                      value={yearName}
                      onChange={e => setYearName(e.target.value)}
                      placeholder="e.g. 2025–2026 Training Year"
                    />
                  </label>
                </div>
                {yearErr && <div className="pw-err">{yearErr}</div>}
                <div style={{ marginTop: 12 }}>
                  <button className="btn primary" onClick={handleCreateYear} disabled={savingYear}>
                    {savingYear ? "Creating…" : "Create planning year →"}
                  </button>
                </div>
              </div>
            )}
            {step === "dates" && (
              <div style={{ fontSize: 13, color: "var(--success)", fontWeight: 700 }}>
                ✓ Planning year created: {yearName}
              </div>
            )}
          </div>
        </div>

        {/* Step 2 */}
        <div className={`pw-setup-step${step === "dates" && !datesResult ? " active" : datesResult ? " done" : ""}`}>
          <div className="pw-setup-step-num">{datesResult ? "✓" : "2"}</div>
          <div className="pw-setup-step-body">
            <div className="pw-setup-step-title">Generate Parade Nights</div>
            {step === "dates" && !datesResult && (() => {
              const preview = previewDates(weekday, startDate, endDate, frequency);
              return (
                <div className="pw-drawer-form" style={{ maxWidth: 520 }}>
                  <p style={{ fontSize: 12, color: "var(--muted-text)", margin: "0 0 12px" }}>
                    Parade nights are the individual training evenings that make up your Training Year.
                    Choose your regular parade weekday, the dates your training runs between, and how often parades occur.
                    A preview of the dates appears below before you confirm.
                  </p>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                    <label>
                      Parade weekday
                      <select value={weekday} onChange={e => setWeekday(Number(e.target.value))}>
                        {WEEKDAYS.map(d => <option key={d.value} value={d.value}>{d.label}</option>)}
                      </select>
                    </label>
                    <label>
                      Frequency
                      <select value={frequency} onChange={e => setFrequency(e.target.value)}>
                        {FREQUENCIES.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
                      </select>
                    </label>
                    <label>
                      Start date
                      <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} />
                    </label>
                    <label>
                      End date
                      <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} />
                    </label>
                    <label>
                      Parade start time <span style={{ fontWeight: 400, color: "var(--muted-text)", fontSize: 11 }}>(optional)</span>
                      <input type="time" value={startTime} onChange={e => setStartTime(e.target.value)}
                        title="Overrides the squadron default parade start time" />
                    </label>
                    <label>
                      Parade end time <span style={{ fontWeight: 400, color: "var(--muted-text)", fontSize: 11 }}>(optional)</span>
                      <input type="time" value={endTime} onChange={e => setEndTime(e.target.value)}
                        title="Overrides the squadron default parade end time" />
                    </label>
                  </div>
                  <label style={{ display: "flex", gap: 8, alignItems: "center", fontWeight: 400, marginTop: 6 }}>
                    <input type="checkbox" checked={excludeHolidays} onChange={e => setExcludeHolidays(e.target.checked)} />
                    Exclude public holiday periods (deducted when holidays are configured)
                  </label>

                  {preview.length > 0 && (
                    <div style={{ marginTop: 12, padding: "10px 14px", background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 8 }}>
                      <div style={{ fontWeight: 700, fontSize: 12, marginBottom: 6 }}>
                        Preview — {preview.length} date{preview.length !== 1 ? "s" : ""}
                        {excludeHolidays && <span style={{ fontWeight: 400, color: "var(--muted-text)", marginLeft: 6 }}>(holidays excluded on save)</span>}
                      </div>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "3px 10px" }}>
                        {preview.map(d => (
                          <span key={d} style={{ fontSize: 11, color: "var(--text)", fontVariantNumeric: "tabular-nums" }}>{fmtDate(d)}</span>
                        ))}
                      </div>
                    </div>
                  )}

                  {datesErr && <div className="pw-err" style={{ marginTop: 6 }}>{datesErr}</div>}
                  <div style={{ marginTop: 12 }}>
                    <button className="btn primary" onClick={handleGenerateDates} disabled={savingDates || preview.length === 0}>
                      {savingDates ? "Generating…" : `Generate ${preview.length > 0 ? preview.length : ""} parade date${preview.length !== 1 ? "s" : ""} →`}
                    </button>
                  </div>
                </div>
              );
            })()}
            {datesResult && (
              <div>
                <div style={{ fontSize: 13, color: "var(--success)", fontWeight: 700 }}>
                  ✓ {datesResult.created} parade date{datesResult.created !== 1 ? "s" : ""} generated
                </div>
                {datesResult.dates.length > 0 && (
                  <div style={{ marginTop: 8, display: "flex", flexWrap: "wrap", gap: "3px 10px" }}>
                    {datesResult.dates.map(d => (
                      <span key={d} style={{ fontSize: 11, color: "var(--muted-text)", fontVariantNumeric: "tabular-nums" }}>{fmtDate(d)}</span>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {datesResult && (
        <div style={{ marginTop: 20, padding: "14px 18px", background: "var(--surface)", borderRadius: 10, border: "1.5px solid var(--border)" }}>
          <div style={{ fontWeight: 700, marginBottom: 6, color: "var(--success)" }}>Setup complete!</div>
          <div style={{ fontSize: 13, color: "var(--muted-text)", lineHeight: 1.6 }}>
            Your Training Year and parade nights are ready. The planning calendar will now show.
          </div>
          <div style={{ fontSize: 12, color: "var(--muted-text)", marginTop: 8, lineHeight: 1.6 }}>
            <strong>What to do next in TMS:</strong> add Facilitators, Training Areas, and Training Classes — then come back here to schedule curriculum sessions.
            Use the <strong>?</strong> button at the top of this page for step-by-step instructions.
          </div>
        </div>
      )}
    </div>
  );
}
