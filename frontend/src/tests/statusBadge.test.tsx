import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "../components/status/StatusBadge";

describe("StatusBadge", () => {
  it("shows a text label, not colour alone", () => {
    render(<StatusBadge status="not_delivered" />);
    expect(screen.getByText(/Not delivered/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Status: Not delivered/i)).toBeInTheDocument();
  });
  it("falls back gracefully for unknown status", () => {
    render(<StatusBadge status="weird_state" />);
    expect(screen.getByText(/weird state/i)).toBeInTheDocument();
  });
});
