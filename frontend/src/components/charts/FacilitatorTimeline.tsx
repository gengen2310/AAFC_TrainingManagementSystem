import { useEffect, useRef } from "react";
import { Timeline } from "vis-timeline/standalone";
import { DataSet } from "vis-data/standalone";
import "vis-timeline/styles/vis-timeline-graph2d.min.css";
import type { FacilitatorScheduleFacilitator, FacilitatorScheduleItem } from "../../api/types";

// Grouped facilitator schedule timeline (master transformation plan Block 9 /
// addendum section CC). vis-timeline is the one library this codebase adopts
// (see Y.3 of the plan) — every other chart stays hand-rolled CSS/DOM. Its
// own keyboard/screen-reader support is weak, which is why this component is
// never the only way to see this data: FacilitatorScheduleList.tsx (rendered
// as a sibling, not a child) is the mandatory accessible fallback, not an
// afterthought.
//
// Status is never colour-alone: every item's visible label is prefixed with
// a status icon (see STATUS_ICON) in addition to the CSS colour class, and
// the same icon+colour pairing is what StatusBadge uses elsewhere in the app.
const STATUS_CLASS: Record<string, string> = {
  delivered: "fts-ok",
  delivered_with_issue: "fts-warn",
  not_delivered: "fts-warn",
  cancelled: "fts-red",
  cancelled_late: "fts-red",
  planned: "fts-blue",
  rescheduled: "fts-purple",
};
const STATUS_ICON: Record<string, string> = {
  delivered: "✓",
  delivered_with_issue: "✓!",
  not_delivered: "▲",
  cancelled: "✕",
  cancelled_late: "✕",
  planned: "•",
  rescheduled: "↻",
};

export type ZoomPreset = "week" | "month" | "term" | "year";

const ZOOM_DAYS: Record<ZoomPreset, number> = { week: 7, month: 31, term: 120, year: 365 };

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

export function FacilitatorTimeline({
  facilitators, items, zoomPreset,
}: {
  facilitators: FacilitatorScheduleFacilitator[];
  items: FacilitatorScheduleItem[];
  zoomPreset: ZoomPreset;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const timelineRef = useRef<Timeline | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const groups = new DataSet(
      facilitators.map((f) => ({
        id: f.facilitator_id,
        content: escapeHtml(f.name) + (f.on_leave_now ? ' <span class="fts-leave-now-tag">on leave now</span>' : ""),
      }))
    );
    const visItems = new DataSet(
      items.map((it) => {
        if (it.kind === "leave") {
          return {
            id: it.id,
            group: it.facilitator_id,
            start: it.start_date,
            end: it.end_date,
            content: `Leave: ${escapeHtml(it.label)}`,
            className: "fts-item fts-leave",
            type: "range" as const,
          };
        }
        const icon = STATUS_ICON[it.status] ?? "•";
        const cls = STATUS_CLASS[it.status] ?? "";
        return {
          id: it.id,
          group: it.facilitator_id,
          start: it.date,
          content: `${icon} ${escapeHtml(it.label)}`,
          className: `fts-item fts-session ${cls}`,
          type: "point" as const,
          title: `${it.label} — ${it.status.replace(/_/g, " ")}`,
        };
      })
    );

    const tl = new Timeline(containerRef.current, visItems, groups, {
      stack: false,
      orientation: "top",
      margin: { item: 10 },
      height: "520px",
      zoomable: true,
      moveable: true,
    });
    timelineRef.current = tl;
    return () => {
      tl.destroy();
      timelineRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [facilitators, items]);

  useEffect(() => {
    const tl = timelineRef.current;
    if (!tl) return;
    const days = ZOOM_DAYS[zoomPreset];
    const now = Date.now();
    const half = days * 24 * 60 * 60 * 1000 * 0.3;
    tl.setWindow(now - half, now + (days * 24 * 60 * 60 * 1000 - half));
  }, [zoomPreset, facilitators, items]);

  return (
    <div
      ref={containerRef}
      role="img"
      aria-label="Facilitator schedule timeline. Use the List view toggle above for a keyboard- and screen-reader-accessible version of this same data."
    />
  );
}
