import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { LineChart } from "../components/charts/DashboardCharts";
import type { DashboardChart } from "../api/types";

// REM-17 (original_instruction.md Section 15): a week with no scheduled
// training must render as a gap in the delivery-trend line, never a
// misleading 0% point. The backend sends reliability_pct: null for those
// weeks specifically to preserve this distinction.

function chart(data: unknown): DashboardChart {
  return { chart_id: "delivery_trend", chart_type: "line", data } as DashboardChart;
}

describe("LineChart", () => {
  it("draws one continuous polyline when every week has a real value", () => {
    const { container } = render(
      <LineChart chart={chart([
        { label: "W1", reliability_pct: 80 },
        { label: "W2", reliability_pct: 90 },
        { label: "W3", reliability_pct: 70 },
      ])} />
    );
    const polylines = container.querySelectorAll("polyline");
    expect(polylines.length).toBe(1);
    // 3 weeks, all real -> 3 plotted points (circles)
    expect(container.querySelectorAll("circle").length).toBe(3);
  });

  it("breaks the line into segments around a no-scheduled-training week instead of plotting a false 0%", () => {
    const { container } = render(
      <LineChart chart={chart([
        { label: "W1", reliability_pct: 80 },
        { label: "W2", reliability_pct: null },
        { label: "W3", reliability_pct: 70 },
      ])} />
    );
    // Two separate polyline segments either side of the gap week, not one
    // continuous line running through a false zero.
    const polylines = container.querySelectorAll("polyline");
    expect(polylines.length).toBe(2);
    // Only the 2 real values get a plotted circle -- the null week gets none.
    expect(container.querySelectorAll("circle").length).toBe(2);
  });

  it("renders no polyline at all when every week has no scheduled training", () => {
    const { container } = render(
      <LineChart chart={chart([
        { label: "W1", reliability_pct: null },
        { label: "W2", reliability_pct: null },
      ])} />
    );
    expect(container.querySelectorAll("polyline").length).toBe(0);
    expect(container.querySelectorAll("circle").length).toBe(0);
  });
});
