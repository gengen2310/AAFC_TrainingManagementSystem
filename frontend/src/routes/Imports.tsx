import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { opsApi } from "../api";
import { Card, Empty, Button } from "../components/ui";
import { ApiError } from "../api/client";
import type { ImportPreview, ImportCommitResult } from "../api/types";

// Cadet CSV import: preview → review → commit → rollback. Commit is blocked until preview reviewed.
export function Imports() {
  const [csv, setCsv] = useState("");
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [committed, setCommitted] = useState<ImportCommitResult | null>(null);
  const [err, setErr] = useState("");

  const previewM = useMutation({
    mutationFn: () => opsApi.importPreview(csv),
    onSuccess: (d) => { setErr(""); setPreview(d); setCommitted(null); },
    onError: (e) => setErr(e instanceof ApiError ? e.friendly : "Preview failed."),
  });
  const commitM = useMutation({
    mutationFn: () => opsApi.importCommit(csv),
    onSuccess: (d) => { setErr(""); setCommitted(d); },
    onError: (e) => setErr(e instanceof ApiError ? e.friendly : "Commit failed."),
  });
  const rollbackM = useMutation({
    mutationFn: () => opsApi.importRollback(committed!.import_id),
    onSuccess: () => { setCommitted(null); setPreview(null); setCsv(""); },
    onError: (e) => setErr(e instanceof ApiError ? e.friendly : "Rollback failed."),
  });

  return (
    <div>
      <h1>Imports</h1>
      <Card title="Cadet CSV import">
        <p className="muted">Paste CSV with a header row. Cells beginning with = + - @ are neutralised to prevent spreadsheet formula injection.</p>
        <label htmlFor="csv" className="vis-hidden">CSV text</label>
        <textarea id="csv" rows={6} value={csv} onChange={(e) => { setCsv(e.target.value); setPreview(null); setCommitted(null); }}
          placeholder="first_name,last_name,service_number,rank,phase,attendance_percentage" />
        <div className="row-actions">
          <Button onClick={() => previewM.mutate()} disabled={!csv.trim() || previewM.isPending}>Preview</Button>
          <Button variant="out" onClick={() => commitM.mutate()} disabled={!preview || commitM.isPending}>Commit (requires preview)</Button>
        </div>
        {err && <div className="errnote" role="alert">{err}</div>}
      </Card>

      {preview && (
        <Card title={`Preview — ${preview.row_count} row(s)`}>
          <p className="muted">Detected columns: {Object.entries(preview.detected).filter(([, v]) => v).map(([k, v]) => `${k}→${v}`).join(", ") || "none auto-detected"}</p>
          {preview.preview.length === 0 ? <Empty msg="No rows." /> : (
            <table>
              <caption className="vis-hidden">Import preview</caption>
              <thead><tr>{preview.headers.map((h) => <th key={h}>{h}</th>)}</tr></thead>
              <tbody>{preview.preview.map((r, i) => <tr key={i}>{preview.headers.map((h) => <td key={h}>{r[h] ?? ""}</td>)}</tr>)}</tbody>
            </table>
          )}
        </Card>
      )}

      {committed && (
        <Card title="Committed">
          <p>Import <code>{committed.import_id}</code> — accepted {committed.accepted}, rejected {committed.rejected}.</p>
          <Button variant="danger" onClick={() => rollbackM.mutate()} disabled={rollbackM.isPending}>Roll back this import</Button>
        </Card>
      )}
    </div>
  );
}
