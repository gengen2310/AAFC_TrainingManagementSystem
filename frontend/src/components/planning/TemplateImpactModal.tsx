// TemplateImpactModal.tsx — confirm before applying a timing template change.
// DESIGN: Task 9 will apply visual polish (frontend-design + apple-design skills).
import type { TemplateImpactResult } from '../../api/types';

interface Props {
  impact: TemplateImpactResult;
  onConfirm: () => void;
  onCancel: () => void;
  loading: boolean;
}

export function TemplateImpactModal({ impact, onConfirm, onCancel, loading }: Props) {
  const hasRemovals = impact.removed_periods.length > 0;
  const affectedWithData = impact.affected_sessions.filter(
    s => s.has_curriculum || s.has_facilitator
  );

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="tim-title"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 1000,
        background: "rgba(0,0,0,0.45)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          background: "var(--surface, #fff)",
          border: "1px solid var(--border, #d1dce8)",
          borderRadius: 10,
          padding: "24px 28px",
          maxWidth: 480,
          width: "100%",
          boxShadow: "var(--sh2, 0 4px 16px rgba(0,47,101,.14))",
        }}
      >
        <h2
          id="tim-title"
          style={{ margin: "0 0 8px", fontSize: 17, fontWeight: 700, color: "var(--text, #1e2d3d)" }}
        >
          Template Change Impact
        </h2>
        <p style={{ margin: "0 0 16px", fontSize: 'var(--fs-sm, 13px)', color: "var(--text-2, #3a4a55)" }}>
          Changing the timing template will affect this parade night's structure.
        </p>

        {/* Period summary */}
        <dl
          style={{
            display: "grid",
            gridTemplateColumns: "auto 1fr",
            gap: "6px 12px",
            fontSize: 'var(--fs-sm, 13px)',
            margin: "0 0 14px",
          }}
        >
          <dt style={{ fontWeight: 600, color: "var(--muted, #5c6a76)" }}>Periods kept</dt>
          <dd style={{ margin: 0 }}>
            {impact.retained_periods.length > 0 ? impact.retained_periods.join(', ') : 'None'}
          </dd>

          {impact.added_periods.length > 0 && (
            <>
              <dt style={{ fontWeight: 600, color: "var(--ok, #1a7f4b)" }}>New periods added</dt>
              <dd style={{ margin: 0, color: "var(--ok, #1a7f4b)" }}>
                {impact.added_periods.join(', ')}
              </dd>
            </>
          )}

          {hasRemovals && (
            <>
              <dt style={{ fontWeight: 600, color: "var(--aafc-red, #e51937)" }}>Periods removed</dt>
              <dd style={{ margin: 0, color: "var(--aafc-red, #e51937)" }}>
                {impact.removed_periods.join(', ')}
              </dd>
            </>
          )}
        </dl>

        {/* Affected sessions warning */}
        {affectedWithData.length > 0 && (
          <div
            role="alert"
            aria-live="polite"
            style={{
              background: "var(--warn-bg, #fff3cd)",
              border: "1px solid var(--warn, #c97a00)",
              borderRadius: 6,
              padding: "10px 12px",
              fontSize: 'var(--fs-sm, 13px)',
              marginBottom: 16,
            }}
          >
            <p style={{ margin: "0 0 8px", fontWeight: 600 }}>
              {affectedWithData.length} session{affectedWithData.length > 1 ? 's' : ''} on removed
              period{impact.removed_periods.length > 1 ? 's' : ''} have planned content.
              They will remain in the system but will no longer have an assigned period.
            </p>
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {affectedWithData.map(s => (
                <li key={s.session_id} style={{ marginBottom: 2 }}>
                  Period {s.period_number}
                  {s.has_curriculum ? ' — has curriculum' : ''}
                  {s.has_facilitator ? ' — has facilitator' : ''}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Action buttons */}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button
            type="button"
            className="btn out"
            onClick={onCancel}
            disabled={loading}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn primary"
            onClick={onConfirm}
            disabled={loading}
            aria-busy={loading}
          >
            {loading ? 'Applying…' : 'Confirm change'}
          </button>
        </div>
      </div>
    </div>
  );
}
