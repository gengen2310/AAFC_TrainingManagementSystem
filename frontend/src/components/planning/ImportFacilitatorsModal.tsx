import { useState, type ChangeEvent } from "react";
import { Modal } from "../Modal";
import { Button } from "../ui";
import { trainingApi } from "../../api";
import { ApiError } from "../../api/client";

// TRGO-05: governed bulk import. Preview shows per-row action (create/duplicate/
// duplicate_in_file/error) before anything is written; committing requires the
// caller to explicitly confirm any row they still want created despite a
// name match, same reasoning as the single-facilitator duplicate confirmation.
//
// Shared between the standalone Facilitators route (frontend/src/routes/
// Facilitators.tsx) and the Planning Workspace's own Facilitators drawer tab
// (components/planning/PlanningBottomDrawer.tsx) -- the latter is the only one
// actually reachable when this app is deployed in module mode (aafc-module-mode
// meta tag set by docker-entrypoint.sh), which the standalone route's own page
// router is entirely skipped under, so this must not be duplicated per caller.
type ImportRow = { row: number; action: string; message?: string; first_name: string | null; last_name: string };

export function ImportFacilitatorsModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<{ rows: ImportRow[]; to_create: number; duplicates: number; errors: number } | null>(null);
  const [confirmRows, setConfirmRows] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [done, setDone] = useState<{ created: number; skipped: number; errors: number } | null>(null);

  async function downloadTemplate() {
    try {
      const csv = await trainingApi.facilitatorImportTemplate();
      const blob = new Blob([csv], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = "facilitator_import_template.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setErr(e instanceof ApiError ? e.friendly : "Could not download the template.");
    }
  }

  function onFileChange(e: ChangeEvent<HTMLInputElement>) {
    setFile(e.target.files?.[0] ?? null);
    setPreview(null); setConfirmRows(new Set()); setErr("");
  }

  async function runPreview() {
    if (!file) return;
    setLoading(true); setErr("");
    try {
      const r = await trainingApi.importFacilitatorsCsv(file, { preview: true });
      setPreview({ rows: r.rows ?? [], to_create: r.to_create ?? 0, duplicates: r.duplicates ?? 0, errors: r.errors ?? 0 });
    } catch (e) {
      setErr(e instanceof ApiError ? e.friendly : "Could not preview this file.");
    } finally {
      setLoading(false);
    }
  }

  async function commit() {
    if (!file) return;
    setLoading(true); setErr("");
    try {
      const r = await trainingApi.importFacilitatorsCsv(file, { preview: false, confirmDuplicateRows: Array.from(confirmRows) });
      setDone({ created: r.created ?? 0, skipped: r.skipped ?? 0, errors: r.errors ?? 0 });
      onDone();
    } catch (e) {
      setErr(e instanceof ApiError ? e.friendly : "Could not import this file.");
    } finally {
      setLoading(false);
    }
  }

  function toggleConfirm(row: number) {
    setConfirmRows((prev) => {
      const next = new Set(prev);
      if (next.has(row)) next.delete(row); else next.add(row);
      return next;
    });
  }

  const actionLabel: Record<string, string> = {
    create: "Will be added",
    duplicate: "Matches an existing facilitator",
    duplicate_in_file: "Repeated in this file",
    error: "Row error",
  };

  if (done) {
    return (
      <Modal title="Facilitators imported" onClose={onClose}>
        <div className="form">
          <p>
            {done.created} facilitator{done.created === 1 ? "" : "s"} added.
            {done.skipped > 0 && ` ${done.skipped} skipped as duplicates.`}
            {done.errors > 0 && ` ${done.errors} row${done.errors === 1 ? "" : "s"} had an error and were not imported.`}
          </p>
          <Button onClick={onClose}>Close</Button>
        </div>
      </Modal>
    );
  }

  return (
    <Modal title="Import facilitators from CSV" onClose={onClose}>
      <div className="form">
        <p className="muted" style={{ fontSize: 12 }}>
          Upload a CSV with columns: rank, first_name, last_name, type, subject_areas (semicolon-separated), active_status.
          Nothing is written until you confirm.
        </p>
        <Button variant="out" onClick={downloadTemplate}>Download CSV template</Button>

        <label htmlFor="fac-import-file">CSV file</label>
        <input id="fac-import-file" type="file" accept=".csv,text/csv" onChange={onFileChange} />

        {file && !preview && (
          <Button onClick={runPreview} disabled={loading}>{loading ? "Loading preview…" : "Preview import"}</Button>
        )}

        {preview && (
          <>
            <p style={{ fontSize: 12 }}>
              <strong>{preview.to_create}</strong> to add.
              {preview.duplicates > 0 && <> <strong>{preview.duplicates}</strong> possible duplicate{preview.duplicates === 1 ? "" : "s"} — tick to import anyway.</>}
              {preview.errors > 0 && <> <strong>{preview.errors}</strong> row{preview.errors === 1 ? "" : "s"} with an error will be skipped.</>}
            </p>
            <div style={{ maxHeight: 260, overflowY: "auto", border: "1px solid var(--border)", borderRadius: 6 }}>
              <table style={{ width: "100%", fontSize: 12 }}>
                <thead><tr><th>Row</th><th>Name</th><th>Status</th><th>Import anyway</th></tr></thead>
                <tbody>
                  {preview.rows.map((r) => (
                    <tr key={r.row} style={r.action === "error" ? { color: "var(--muted-text)" } : undefined}>
                      <td>{r.row + 1}</td>
                      <td>{[r.first_name, r.last_name].filter(Boolean).join(" ") || "—"}</td>
                      <td>{actionLabel[r.action] ?? r.action}{r.message ? `: ${r.message}` : ""}</td>
                      <td>
                        {(r.action === "duplicate" || r.action === "duplicate_in_file") && (
                          <input type="checkbox" checked={confirmRows.has(r.row)}
                            onChange={() => toggleConfirm(r.row)}
                            aria-label={`Import row ${r.row + 1} anyway`} />
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {err && <div className="err" role="alert">{err}</div>}
        <div style={{ display: "flex", gap: 8 }}>
          <Button onClick={onClose} variant="out">Cancel</Button>
          {preview && (
            <Button onClick={commit} disabled={loading}>{loading ? "Importing…" : "Confirm import"}</Button>
          )}
        </div>
      </div>
    </Modal>
  );
}
