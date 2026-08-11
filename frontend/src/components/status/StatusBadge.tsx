// Status badge: icon + text label + colour + border. Never colour alone (WCAG / colour-blind safe).
const MAP: Record<string, { cls: string; icon: string; label: string }> = {
  delivered: { cls: "ok", icon: "✓", label: "Delivered" },
  delivered_with_issue: { cls: "warn", icon: "✓!", label: "Delivered (issue)" },
  not_delivered: { cls: "warn", icon: "▲", label: "Not delivered" },
  cancelled: { cls: "red", icon: "✕", label: "Cancelled" },
  cancelled_late: { cls: "red", icon: "✕", label: "Cancelled late" },
  planned: { cls: "blue", icon: "•", label: "Planned" },
  published: { cls: "blue", icon: "▣", label: "Published" },
  draft: { cls: "muted", icon: "○", label: "Draft" },
  rescheduled: { cls: "purple", icon: "↻", label: "Rescheduled" },
  requires_review: { cls: "warn", icon: "?", label: "Requires review" },
  closed: { cls: "muted", icon: "▪", label: "Closed" },
  open: { cls: "blue", icon: "•", label: "Open" },
  active_required: { cls: "red", icon: "▲", label: "Action required" },
};
export function statusLabel(status: string): string {
  return MAP[status]?.label ?? status.replace(/_/g, " ");
}
export function StatusBadge({ status }: { status: string }) {
  const s = MAP[status] ?? { cls: "muted", icon: "•", label: status.replace(/_/g, " ") };
  return <span className={`badge ${s.cls}`} aria-label={`Status: ${s.label}`}>{s.icon} {s.label}</span>;
}
export function DecisionBadge({ decision }: { decision: string }) {
  const map: Record<string, string> = { no_action: "ok", monitor: "blue", action_required: "warn", command_decision_required: "red" };
  return <span className={`badge ${map[decision] ?? "muted"}`}>{decision.replace(/_/g, " ")}</span>;
}
