import { useState } from "react";
import { planningApi } from "../../api";
import type { SessionInfo } from "../../api/types";

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
  onYearCreated: () => void;
}

export function SetupPanel({ onYearCreated }: Props) {
  const [step, setStep] = useState<"year" | "dates">("year");
  const [createdYearId, setCreatedYearId] = useState<string | null>(null);

  // Step 1 – create planning year
  const [yearNum, setYearNum] = useState(new Date().getFullYear());
  const [yearName, setYearName] = useState(`${new Date().getFullYear()}–${new Date().getFullYear() + 1} Training Year`);
  const [savingYear, setSavingYear] = useState(false);
  const [yearErr, setYearErr] = useState<string | null>(null);

  // Step 2 – generate parade dates
  const [weekday, setWeekday] = useState(3); // Thursday
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [frequency, setFrequency] = useState("weekly");
  const [excludeHolidays, setExcludeHolidays] = useState(true);
  const [savingDates, setSavingDates] = useState(false);
  const [datesErr, setDatesErr] = useState<string | null>(null);
  const [datesResult, setDatesResult] = useState<{ created: number; dates: string[] } | null>(null);

  async function handleCreateYear() {
    if (!yearName.trim()) { setYearErr("Name is required."); return; }
    setSavingYear(true); setYearErr(null);
    try {
      const year = await planningApi.createYear({ year: yearNum, name: yearName.trim() });
      // createYear returns a PlanningYear — extract the ID from the response
      const id = (year as unknown as Record<string, unknown>).planning_year_id as string;
      setCreatedYearId(id);
      setStep("dates");
      onYearCreated();
    } catch (e: unknown) {
      setYearErr(e instanceof Error ? e.message : "Failed to create planning year");
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
      });
      setDatesResult({ created: result.created, dates: result.dates });
      onYearCreated();
    } catch (e: unknown) {
      setDatesErr(e instanceof Error ? e.message : "Failed to generate dates");
    } finally {
      setSavingDates(false);
    }
  }

  return (
    <div className="pw-setup-panel">
      <div className="pw-setup-header">
        <h2>Set Up Planning Workspace</h2>
        <p>No planning year exists yet. Complete the steps below to get started.</p>
      </div>

      <div className="pw-setup-steps">
        {/* Step 1 */}
        <div className={`pw-setup-step${step === "year" ? " active" : step === "dates" ? " done" : ""}`}>
          <div className="pw-setup-step-num">{step === "dates" || datesResult ? "✓" : "1"}</div>
          <div className="pw-setup-step-body">
            <div className="pw-setup-step-title">Create Planning Year</div>
            {step === "year" && (
              <div className="pw-drawer-form" style={{ maxWidth: 480 }}>
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
            <div className="pw-setup-step-title">Generate Parade Dates</div>
            {step === "dates" && !datesResult && (
              <div className="pw-drawer-form" style={{ maxWidth: 480 }}>
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
                </div>
                <label style={{ display: "flex", gap: 8, alignItems: "center", fontWeight: 400, marginTop: 6 }}>
                  <input type="checkbox" checked={excludeHolidays} onChange={e => setExcludeHolidays(e.target.checked)} />
                  Exclude holiday periods
                </label>
                {datesErr && <div className="pw-err" style={{ marginTop: 6 }}>{datesErr}</div>}
                <div style={{ marginTop: 12 }}>
                  <button className="btn primary" onClick={handleGenerateDates} disabled={savingDates}>
                    {savingDates ? "Generating…" : "Generate parade dates →"}
                  </button>
                </div>
              </div>
            )}
            {datesResult && (
              <div style={{ fontSize: 13, color: "var(--success)", fontWeight: 700 }}>
                ✓ {datesResult.created} parade date{datesResult.created !== 1 ? "s" : ""} generated
              </div>
            )}
          </div>
        </div>
      </div>

      {datesResult && (
        <div style={{ marginTop: 20, padding: "14px 18px", background: "var(--surface)", borderRadius: 10, border: "1.5px solid var(--border)" }}>
          <div style={{ fontWeight: 700, marginBottom: 6, color: "var(--success)" }}>Setup complete!</div>
          <div style={{ fontSize: 13, color: "var(--muted-text)" }}>
            Reload the workspace to begin planning. You can add anchor events and sessions from the Year view.
          </div>
        </div>
      )}
    </div>
  );
}
