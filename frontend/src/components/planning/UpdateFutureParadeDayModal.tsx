import { useState } from "react";
import { Modal } from "../Modal";
import { Button } from "../ui";
import { planningApi } from "../../api";
import { ApiError } from "../../api/client";

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

// TRGO-01: explicit, auditable action to move future Parade Nights to a new
// day of the week. Squadron.default_parade_day only affects newly-generated
// dates -- it was never meant to (and does not) retroactively touch existing
// records. This is the missing "make it happen" workflow: preview the exact
// dates that would change, show conflicts, require a reason, then commit.
export function UpdateFutureParadeDayModal({ yearId, onClose, onDone }: {
  yearId: string; onClose: () => void; onDone: () => void;
}) {
  const [weekday, setWeekday] = useState(4); // Friday, a sensible default
  const [reason, setReason] = useState("");
  const [preview, setPreview] = useState<Awaited<ReturnType<typeof planningApi.updateFutureParadeDay>> | null>(null);
  const [excluded, setExcluded] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [done, setDone] = useState<{ updated: number; skipped: number } | null>(null);

  async function runPreview() {
    setLoading(true); setErr("");
    try {
      const r = await planningApi.updateFutureParadeDay(yearId, { new_weekday: weekday, preview: true });
      setPreview(r);
    } catch (e) {
      setErr(e instanceof ApiError ? e.friendly : "Could not preview the change.");
    } finally {
      setLoading(false);
    }
  }

  async function commit() {
    if (!reason.trim()) { setErr("A reason is required to update future parade nights."); return; }
    setLoading(true); setErr("");
    try {
      const r = await planningApi.updateFutureParadeDay(yearId, {
        new_weekday: weekday, preview: false, reason: reason.trim(),
        exclude_ids: Array.from(excluded),
      });
      setDone({ updated: r.updated ?? 0, skipped: r.skipped ?? 0 });
      onDone();
    } catch (e) {
      setErr(e instanceof ApiError ? e.friendly : "Could not update future parade nights.");
    } finally {
      setLoading(false);
    }
  }

  function toggleExclude(id: string) {
    setExcluded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  if (done) {
    return (
      <Modal title="Future parade nights updated" onClose={onClose}>
        <div className="form">
          <p>
            {done.updated} parade night{done.updated === 1 ? "" : "s"} moved to {WEEKDAYS[weekday]}.
            {done.skipped > 0 && ` ${done.skipped} skipped due to a conflict (unchanged).`}
          </p>
          <Button onClick={onClose}>Close</Button>
        </div>
      </Modal>
    );
  }

  return (
    <Modal title="Update future parade nights" onClose={onClose}>
      <div className="form">
        <p className="muted" style={{ fontSize: 12 }}>
          Moves upcoming standard parade nights to a new day of the week. Historical
          records and one-night exceptions are never changed by this action.
        </p>
        <label htmlFor="ufpd-weekday">New day</label>
        <select id="ufpd-weekday" value={weekday} onChange={(e) => { setWeekday(Number(e.target.value)); setPreview(null); }}>
          {WEEKDAYS.map((w, i) => <option key={w} value={i}>{w}</option>)}
        </select>

        {!preview && (
          <Button onClick={runPreview} disabled={loading}>{loading ? "Loading preview…" : "Preview changes"}</Button>
        )}

        {preview && (
          <>
            <p style={{ fontSize: 12 }}>
              <strong>{preview.to_update}</strong> parade night{preview.to_update === 1 ? "" : "s"} will move to {WEEKDAYS[weekday]}.
              {(preview.blocked ?? 0) > 0 && <> <strong>{preview.blocked}</strong> blocked by a conflict.</>}
              {preview.exceptions_preserved > 0 && <> {preview.exceptions_preserved} one-night exception{preview.exceptions_preserved === 1 ? "" : "s"} preserved automatically.</>}
            </p>
            {preview.changes && preview.changes.length > 0 && (
              <div style={{ maxHeight: 220, overflowY: "auto", border: "1px solid var(--border)", borderRadius: 6 }}>
                <table style={{ width: "100%", fontSize: 12 }}>
                  <thead><tr><th>Include</th><th>Current date</th><th>New date</th><th>Status</th></tr></thead>
                  <tbody>
                    {preview.changes.map((c) => (
                      <tr key={c.parade_date_id} style={c.blocked ? { color: "var(--muted-text)" } : undefined}>
                        <td>
                          {!c.blocked && (
                            <input type="checkbox" checked={!excluded.has(c.parade_date_id)}
                              onChange={() => toggleExclude(c.parade_date_id)}
                              aria-label={`Include ${c.old_date} in this change`} />
                          )}
                        </td>
                        <td>{c.old_date}</td>
                        <td>{c.new_date}{c.has_sessions ? " (has sessions)" : ""}</td>
                        <td>{c.blocked ? `Blocked: ${c.conflicts.join(", ")}` : "OK"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <label htmlFor="ufpd-reason">Reason (required)</label>
            <input id="ufpd-reason" value={reason} onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. Squadron changed parade night to Friday" />
          </>
        )}

        {err && <div className="err" role="alert">{err}</div>}
        <div style={{ display: "flex", gap: 8 }}>
          <Button onClick={onClose} variant="out">Cancel</Button>
          {preview && (preview.to_update ?? 0) > 0 && (
            <Button onClick={commit} disabled={loading || !reason.trim()}>
              {loading ? "Saving…" : "Confirm and update"}
            </Button>
          )}
        </div>
      </div>
    </Modal>
  );
}
