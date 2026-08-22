import type { AnchorEvent, CeaActivity } from "../../api/types";

// ── Unified display type ──────────────────────────────────────────────────────

export interface ActivityDisplay {
  id: string;
  activity_id: string | null;
  activity_type: string | null;
  source_type: string;
  source_label: string;
  activity_name: string;
  parent_unit: string | null;
  host_unit: string | null;
  nomination_start_date: string | null;
  nomination_end_date: string | null;
  activity_start_date: string | null;
  activity_end_date: string | null;
  start_time: string | null;
  end_time: string | null;
  location: string | null;
  activity_poc: string | null;
  importance: string | null;
  audience_staff_only: boolean;
  audience_seniors: boolean;
  audience_proficient: boolean;
  audience_first_years: boolean;
  audience_all_cadets: boolean;
  /** Pre-computed audience label override — set when source uses different audience categories */
  audience_override: string | null;
  classification_status: "classified" | "needs_review" | "irrelevant";
  planning_impact: string | null;
  notes: string | null;
}

// ── Adapter functions ─────────────────────────────────────────────────────────

function owningLevelLabel(level: string | null | undefined): string {
  const MAP: Record<string, string> = {
    national: "National HQ", wing: "7WG HQ", unit: "Unit activity", cea: "CEA",
  };
  return level ? (MAP[level] ?? level) : "Unit activity";
}

export function anchorToDisplay(a: AnchorEvent): ActivityDisplay {
  const allCadets =
    a.audience_orientation && a.audience_initial &&
    a.audience_junior && a.audience_intermediate && a.audience_senior &&
    !a.audience_staff_only;

  // Build human-readable audience label from the old-style rank-band flags
  let audienceOverride: string | null = null;
  if (a.audience_staff_only) {
    audienceOverride = "Staff only";
  } else if (allCadets) {
    audienceOverride = "All cadets";
  } else {
    const parts: string[] = [];
    if (a.audience_orientation || a.audience_initial) parts.push("First years");
    if (a.audience_junior)        parts.push("Junior");
    if (a.audience_intermediate)  parts.push("Intermediate");
    if (a.audience_senior)        parts.push("Seniors");
    if (parts.length > 0) audienceOverride = parts.join(", ");
  }

  return {
    id: a.anchor_event_id,
    activity_id: a.cea_activity_id ?? null,
    activity_type: a.event_type ?? null,
    source_type: "anchor",
    source_label: owningLevelLabel(a.owning_level),
    activity_name: a.event_name,
    parent_unit: null,
    host_unit: a.unit_name ?? null,
    nomination_start_date: null,
    nomination_end_date: a.nomination_end_date ?? null,
    activity_start_date: a.start_date,
    activity_end_date: a.end_date ?? null,
    start_time: null,
    end_time: null,
    location: null,
    activity_poc: null,
    importance: a.importance ?? null,
    audience_staff_only: a.audience_staff_only,
    audience_seniors: a.audience_senior,
    audience_proficient: a.audience_proficient,
    audience_first_years: a.audience_first_years || a.audience_orientation || a.audience_initial,
    audience_all_cadets: allCadets,
    audience_override: audienceOverride,
    classification_status: "classified",
    planning_impact: a.planning_impact ?? null,
    notes: a.notes ?? null,
  };
}

export function ceaToDisplay(a: CeaActivity): ActivityDisplay {
  const cs = a.classification_status as "classified" | "needs_review" | "irrelevant";
  return {
    id: a.id,
    activity_id: a.cea_activity_id,
    activity_type: a.activity_type,
    source_type: "cea",
    source_label: "CEA",
    activity_name: a.activity_name,
    parent_unit: a.parent_unit,
    host_unit: a.host_unit,
    nomination_start_date: a.nomination_start_date,
    nomination_end_date: a.nomination_end_date,
    activity_start_date: a.activity_start_date,
    activity_end_date: a.activity_end_date,
    start_time: a.start_time,
    end_time: a.end_time,
    location: a.location,
    activity_poc: a.activity_poc,
    importance: a.importance,
    audience_staff_only: a.audience_staff_only,
    audience_seniors: a.audience_seniors,
    audience_proficient: a.audience_proficient,
    audience_first_years: a.audience_first_years,
    audience_all_cadets: false,
    audience_override: null,
    classification_status: cs,
    planning_impact: null,
    notes: a.notes,
  };
}

// ── Formatting helpers ────────────────────────────────────────────────────────

const IMPORTANCE_LABELS: Record<string, string> = {
  must_attend:   "Must attend",
  key_event:     "Key event",
  weekly_parade: "Weekly parade",
  optional:      "Optional",
  noting:        "Noting",
  irrelevant:    "Irrelevant",
};

const IMPORTANCE_COLOR: Record<string, string> = {
  must_attend:   "#b91c1c",
  key_event:     "#002f65",
  weekly_parade: "#1a7f4b",
  optional:      "#1a5276",
  noting:        "var(--muted-text)",
  irrelevant:    "var(--muted-text)",
};

const EVENT_TYPE_LABELS: Record<string, string> = {
  ceremonial:          "Ceremonial",
  fieldcraft:          "Fieldcraft",
  adventure_training:  "Adventure training",
  dining_in:           "Dining-in",
  orientation_weekend: "Orientation weekend",
  community:           "Community",
  sport:               "Sport",
  admin:               "Admin",
  inspection:          "Inspection",
  other:               "Other",
};

function fmtDay(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.getDate() + " " + d.toLocaleDateString("en-GB", { month: "short" });
}

function fmtShortDate(iso: string | null | undefined): string {
  if (!iso) return "not set";
  return fmtDay(iso);
}

function fmtLongDate(iso: string | null | undefined): string {
  if (!iso) return "not set";
  const d = new Date(iso + "T00:00:00");
  return `${fmtDay(iso)} ${d.getFullYear()}`;
}

function fmtDateRange(
  start: string | null | undefined,
  end: string | null | undefined,
  startTime?: string | null,
  endTime?: string | null,
): string {
  if (!start) return "not set";
  const sy = new Date(start + "T00:00:00").getFullYear();
  const sLabel = fmtDay(start);
  const timePart = startTime
    ? ` ${startTime}${endTime ? `–${endTime}` : ""}`
    : "";
  if (!end || end === start) return `${sLabel} ${sy}${timePart}`;
  const ey = new Date(end + "T00:00:00").getFullYear();
  const eLabel = fmtDay(end);
  if (sy === ey) return `${sLabel} – ${eLabel} ${ey}${timePart}`;
  return `${sLabel} ${sy} – ${eLabel} ${ey}${timePart}`;
}

function audienceLabel(a: ActivityDisplay): string {
  if (a.classification_status === "needs_review") return "not reviewed";
  if (a.audience_override) return a.audience_override;
  if (a.audience_staff_only) return "Staff only";
  if (a.audience_all_cadets) return "All cadets";
  const parts: string[] = [];
  if (a.audience_seniors)     parts.push("Seniors");
  if (a.audience_proficient)  parts.push("Proficient");
  if (a.audience_first_years) parts.push("First years");
  return parts.length > 0 ? parts.join(", ") : "All cadets";
}

function impLabel(a: ActivityDisplay): string {
  if (a.classification_status === "needs_review") return "not reviewed";
  if (!a.importance) return "not set";
  return IMPORTANCE_LABELS[a.importance] ?? a.importance.replace(/_/g, " ");
}

function impColor(a: ActivityDisplay): string {
  if (!a.importance || a.classification_status === "needs_review") return "var(--muted-text)";
  return IMPORTANCE_COLOR[a.importance] ?? "var(--muted-text)";
}



function or(v: string | null | undefined): string {
  return v || "not set";
}

// ── Shared sub-components ─────────────────────────────────────────────────────

function Field({ label, value }: { label: string; value: string }) {
  const isNotSet = value === "not set" || value === "not reviewed";
  return (
    <div style={{ display: "flex", gap: 4, fontSize: 10, lineHeight: 1.4 }}>
      <span style={{ color: "var(--muted-text)", minWidth: 80, flexShrink: 0 }}>{label}</span>
      <span style={{ color: isNotSet ? "#aaa" : "var(--text)", fontStyle: isNotSet ? "italic" : undefined }}>
        {value}
      </span>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; bg: string; color: string }> = {
    classified:   { label: "Reviewed",      bg: "#e8f5e9", color: "#1a7f4b" },
    needs_review: { label: "Needs review",  bg: "#fff8e1", color: "#c97a00" },
    irrelevant:   { label: "Irrelevant",    bg: "#f5f5f5", color: "var(--muted-text)" },
  };
  const s = map[status] ?? { label: status, bg: "#f0f0f0", color: "var(--text)" };
  return (
    <span style={{
      fontSize: 9, fontWeight: 700, textTransform: "uppercase",
      background: s.bg, color: s.color, borderRadius: 3, padding: "1px 5px",
      whiteSpace: "nowrap",
    }}>
      {s.label}
    </span>
  );
}

// ── ActivityDetailBlock — compact (year-view mini) or standard card ────────────

interface CardProps {
  activity: ActivityDisplay;
  compact?: boolean;
  onClick?: () => void;
}

export function ActivityDetailBlock({ activity: a, compact = false, onClick }: CardProps) {
  const iColor = impColor(a);

  if (compact) {
    // Compact card: all required operational fields, condensed layout
    const hostSrc = [
      a.host_unit ? `Host: ${a.host_unit}` : null,
      `Source: ${a.source_label}`,
    ].filter(Boolean).join(" · ");

    return (
      <div
        onClick={onClick}
        role={onClick ? "button" : undefined}
        tabIndex={onClick ? 0 : undefined}
        onKeyDown={onClick ? e => (e.key === "Enter" || e.key === " ") && onClick() : undefined}
        style={{
          background: "#fff",
          border: "1.5px solid var(--border)",
          borderLeft: `3px solid ${iColor}`,
          borderRadius: 5,
          padding: "6px 9px",
          cursor: onClick ? "pointer" : undefined,
          width: "100%",
          boxSizing: "border-box",
          marginBottom: 3,
        }}
        aria-label={`Activity: ${a.activity_name}`}
      >
        {/* Name */}
        <div style={{ fontSize: 11, fontWeight: 700, color: "var(--aafc-dark-blue)", lineHeight: 1.3, marginBottom: 2 }}>
          {a.activity_name}
        </div>

        {/* Dates */}
        <div style={{ fontSize: 10, color: "var(--text)", marginBottom: 1 }}>
          {fmtDateRange(a.activity_start_date, a.activity_end_date, a.start_time, a.end_time)}
        </div>

        {/* Host · Source */}
        <div style={{ fontSize: 10, color: "var(--muted-text)", marginBottom: 1 }}>{hostSrc}</div>

        {/* Location */}
        <div style={{ fontSize: 10, marginBottom: 1 }}>
          <span style={{ color: "var(--muted-text)" }}>Location: </span>
          <span style={{ fontStyle: a.location ? undefined : "italic", color: a.location ? "var(--text)" : "#aaa" }}>
            {or(a.location)}
          </span>
        </div>

        {/* Nomination close (if set) */}
        {a.nomination_end_date && (
          <div style={{ fontSize: 10, color: "var(--muted-text)", marginBottom: 1 }}>
            Nominations close: {fmtShortDate(a.nomination_end_date)}
          </div>
        )}

        {/* Status · Audience · Importance */}
        <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 4 }}>
          <StatusBadge status={a.classification_status} />
          <span style={{ fontSize: 9, color: "var(--muted-text)", background: "#f4f8fc", borderRadius: 3, padding: "1px 5px" }}>
            {audienceLabel(a)}
          </span>
          <span style={{
            fontSize: 9, fontWeight: 700, textTransform: "uppercase",
            color: iColor, background: `${iColor}18`, borderRadius: 3, padding: "1px 5px",
          }}>
            {impLabel(a)}
          </span>
        </div>
      </div>
    );
  }

  // Standard card — all fields, structured layout
  const typeFmt = a.activity_type
    ? (EVENT_TYPE_LABELS[a.activity_type] ?? a.activity_type.replace(/_/g, " "))
    : null;
  const dateRange = fmtDateRange(a.activity_start_date, a.activity_end_date, a.start_time, a.end_time);
  const nomRange  = (a.nomination_start_date || a.nomination_end_date)
    ? `${fmtShortDate(a.nomination_start_date)} – ${fmtShortDate(a.nomination_end_date)}`
    : null;

  return (
    <div
      onClick={onClick}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? e => (e.key === "Enter" || e.key === " ") && onClick() : undefined}
      style={{
        background: "#fff",
        border: "1.5px solid var(--border)",
        borderLeft: `4px solid ${iColor}`,
        borderRadius: 6,
        padding: "8px 11px",
        cursor: onClick ? "pointer" : undefined,
        width: "100%",
        boxSizing: "border-box",
        marginBottom: 5,
      }}
      aria-label={`Activity: ${a.activity_name}`}
    >
      {/* Name + status badge */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 6, marginBottom: 4 }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: "var(--aafc-dark-blue)", lineHeight: 1.3, flex: 1 }}>
          {a.activity_name}
        </div>
        <StatusBadge status={a.classification_status} />
      </div>

      {/* ID · Type */}
      {(a.activity_id || typeFmt) && (
        <div style={{ fontSize: 10, color: "var(--muted-text)", marginBottom: 3 }}>
          {a.activity_id && <span>ID: <strong style={{ color: "var(--text)" }}>{a.activity_id}</strong></span>}
          {a.activity_id && typeFmt && <span> · </span>}
          {typeFmt && <span>Type: {typeFmt}</span>}
        </div>
      )}

      {/* Host / Parent */}
      <div style={{ fontSize: 10, marginBottom: 3 }}>
        {a.host_unit
          ? <span>Host: <strong>{a.host_unit}</strong></span>
          : null}
        {a.host_unit && a.parent_unit
          ? <span style={{ color: "var(--muted-text)" }}> · </span>
          : null}
        {a.parent_unit
          ? <span style={{ color: "var(--muted-text)" }}>Parent: {a.parent_unit}</span>
          : null}
        {!a.host_unit && !a.parent_unit && (
          <span style={{ color: "var(--muted-text)" }}>Source: {a.source_label}</span>
        )}
      </div>

      {/* Dates */}
      <div style={{ fontSize: 10, marginBottom: 2 }}>
        <span style={{ color: "var(--muted-text)" }}>Activity: </span>
        <span>{dateRange}</span>
      </div>

      {/* Nomination dates */}
      {nomRange && (
        <div style={{ fontSize: 10, color: "var(--muted-text)", marginBottom: 2 }}>
          Nominations: {nomRange}
        </div>
      )}

      {/* Location */}
      <div style={{ fontSize: 10, marginBottom: 4 }}>
        <span style={{ color: "var(--muted-text)" }}>Location: </span>
        <span style={{
          fontStyle: a.location ? undefined : "italic",
          color: a.location ? "var(--text)" : "#aaa",
        }}>
          {or(a.location)}
        </span>
      </div>

      {/* POC (if available) */}
      {a.activity_poc && (
        <div style={{ fontSize: 10, color: "var(--muted-text)", marginBottom: 4 }}>
          POC: <span style={{ color: "var(--text)" }}>{a.activity_poc}</span>
        </div>
      )}

      {/* Footer chips */}
      <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
        <span style={{
          fontSize: 9, fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.3,
          color: iColor, background: `${iColor}18`, borderRadius: 3, padding: "1px 5px",
        }}>
          {impLabel(a)}
        </span>
        <span style={{
          fontSize: 9, color: "var(--muted-text)", background: "#f4f8fc", borderRadius: 3, padding: "1px 5px",
        }}>
          {audienceLabel(a)}
        </span>
        {(a.host_unit || a.parent_unit) && (
          <span style={{ fontSize: 9, color: "var(--muted-text)", background: "#f0f0f0", borderRadius: 3, padding: "1px 5px" }}>
            {a.source_label}
          </span>
        )}
      </div>
    </div>
  );
}

// ── ActivityFullDetail — drawer / expanded view ───────────────────────────────

function sectionHdr(title: string) {
  return (
    <div style={{
      fontSize: 11, fontWeight: 700, color: "var(--aafc-dark-blue)",
      borderBottom: "1.5px solid var(--border)", paddingBottom: 4,
      marginBottom: 6, marginTop: 14,
    }}>
      {title}
    </div>
  );
}

export function ActivityFullDetail({
  activity: a,
  canEdit = false,
  onHide,
  onAddNote,
}: {
  activity: ActivityDisplay;
  canEdit?: boolean;
  onHide?: () => void;
  onAddNote?: () => void;
}) {
  const typeFmt = a.activity_type
    ? (EVENT_TYPE_LABELS[a.activity_type] ?? a.activity_type.replace(/_/g, " "))
    : "not set";

  return (
    <div style={{ padding: "0 2px" }}>
      <div style={{ fontSize: 15, fontWeight: 700, color: "var(--aafc-dark-blue)", lineHeight: 1.3, marginBottom: 6 }}>
        {a.activity_name}
      </div>

      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 12 }}>
        <StatusBadge status={a.classification_status} />
        <span style={{ fontSize: 9, background: "#f0f0f0", color: "var(--muted-text)", borderRadius: 3, padding: "1px 5px", fontWeight: 700 }}>
          {a.source_label}
        </span>
        {!canEdit && (
          <span style={{ fontSize: 9, background: "#fff3cd", color: "#856404", borderRadius: 3, padding: "1px 5px", fontWeight: 700 }}>
            READ-ONLY
          </span>
        )}
      </div>

      {sectionHdr("Activity")}
      <Field label="Activity" value={a.activity_name} />
      <Field label="ID" value={or(a.activity_id)} />
      <Field label="Type" value={typeFmt} />
      <Field label="Source" value={a.source_label} />

      {sectionHdr("Organisation")}
      <Field label="Parent unit" value={or(a.parent_unit)} />
      <Field label="Host unit" value={or(a.host_unit)} />

      {sectionHdr("Dates")}
      <Field label="Nom. opens"  value={a.nomination_start_date ? fmtLongDate(a.nomination_start_date) : "not set"} />
      <Field label="Nom. closes" value={a.nomination_end_date  ? fmtLongDate(a.nomination_end_date)   : "not set"} />
      <Field label="Starts" value={
        a.activity_start_date
          ? `${fmtLongDate(a.activity_start_date)}${a.start_time ? ` ${a.start_time}` : ""}`
          : "not set"
      } />
      <Field label="Ends" value={
        a.activity_end_date
          ? `${fmtLongDate(a.activity_end_date)}${a.end_time ? ` ${a.end_time}` : ""}`
          : "not set"
      } />

      {sectionHdr("Location and contact")}
      <Field label="Location" value={or(a.location)} />
      <Field label="POC"      value={or(a.activity_poc)} />

      {sectionHdr("Classification")}
      <Field label="Importance" value={impLabel(a)} />
      <Field label="Audience"   value={audienceLabel(a)} />
      {a.planning_impact && <Field label="Impact" value={a.planning_impact} />}
      {a.notes && <Field label="Notes" value={a.notes} />}

      {(onHide || onAddNote) && (
        <>
          {sectionHdr("Local squadron context")}
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 4 }}>
            {onAddNote && (
              <button className="btn sm out" style={{ fontSize: 11 }} onClick={onAddNote}>
                Add local note
              </button>
            )}
            {onHide && (
              <button className="btn sm out" style={{ fontSize: 11 }} onClick={onHide}>
                Hide from local view
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}

// ── ActivityListRow — table row for list view ─────────────────────────────────

export function ActivityListRow({
  activity: a,
  onClick,
}: {
  activity: ActivityDisplay;
  onClick?: () => void;
}) {
  const typeFmt = a.activity_type
    ? (EVENT_TYPE_LABELS[a.activity_type] ?? a.activity_type.replace(/_/g, " "))
    : "—";

  return (
    <tr
      style={{ cursor: onClick ? "pointer" : undefined, verticalAlign: "top" }}
      onClick={onClick}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? e => e.key === "Enter" && onClick() : undefined}
    >
      <td style={{ fontSize: 10, color: "var(--muted-text)", whiteSpace: "nowrap" }}>{a.activity_id ?? "—"}</td>
      <td style={{ fontWeight: 700, fontSize: 11, minWidth: 160 }}>{a.activity_name}</td>
      <td style={{ fontSize: 10 }}>{a.host_unit ?? "—"}</td>
      <td style={{ fontSize: 10, color: "var(--muted-text)" }}>{a.parent_unit ?? "—"}</td>
      <td style={{ fontSize: 10, whiteSpace: "nowrap" }}>
        {a.activity_start_date ? fmtShortDate(a.activity_start_date) : "—"}
      </td>
      <td style={{ fontSize: 10, whiteSpace: "nowrap" }}>
        {a.activity_end_date && a.activity_end_date !== a.activity_start_date
          ? fmtShortDate(a.activity_end_date) : "—"}
      </td>
      <td style={{ fontSize: 10, whiteSpace: "nowrap" }}>
        {a.nomination_end_date ? fmtShortDate(a.nomination_end_date) : "—"}
      </td>
      <td style={{ fontSize: 10, color: "var(--muted-text)" }}>{a.location ?? "—"}</td>
      <td style={{ fontSize: 10, color: "var(--muted-text)" }}>{a.activity_poc ?? "—"}</td>
      <td>
        <span style={{
          fontSize: 9, fontWeight: 700, textTransform: "uppercase",
          color: impColor(a),
        }}>
          {a.importance ? (IMPORTANCE_LABELS[a.importance] ?? a.importance.replace(/_/g, " ")) : "—"}
        </span>
      </td>
      <td style={{ fontSize: 10 }}>{audienceLabel(a)}</td>
      <td><StatusBadge status={a.classification_status} /></td>
      <td style={{ fontSize: 10, color: "var(--muted-text)" }}>{typeFmt}</td>
      <td>
        <span style={{ fontSize: 9, background: "#f0f0f0", color: "var(--muted-text)", borderRadius: 3, padding: "1px 5px" }}>
          {a.source_label}
        </span>
      </td>
    </tr>
  );
}
