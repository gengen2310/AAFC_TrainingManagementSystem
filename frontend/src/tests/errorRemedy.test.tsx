import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ErrorRemedy, ErrorNote } from "../components/ui";

// SESSION-04. The remedy line used to be hard-coded as "check your internet
// connection" under every error, including an expired session — two different
// causes in one message, only one true, and a remedy the user cannot act on.
// These pin the remedy to the actual cause.

const apiError = (status: number) => Object.assign(new Error("boom"), { status });
const networkError = () => Object.assign(new Error("offline"), { isNetwork: true });

describe("ErrorRemedy", () => {
  it("offers a way to sign in when the session has expired", () => {
    render(<ErrorRemedy error={apiError(401)} />);
    const link = screen.getByRole("link", { name: /sign in again/i });
    expect(link).toBeInTheDocument();
    expect(link.getAttribute("href")).toBeTruthy();
  });

  it("does not blame the connection for an expired session", () => {
    render(<ErrorRemedy error={apiError(401)} />);
    expect(screen.queryByText(/internet connection/i)).not.toBeInTheDocument();
  });

  it("explains that the Planning Workspace uses the TMS session", () => {
    render(<ErrorRemedy error={apiError(401)} />);
    expect(screen.getByText(/uses your TMS session/i)).toBeInTheDocument();
  });

  it("does suggest checking the connection for a real network failure", () => {
    render(<ErrorRemedy error={networkError()} />);
    expect(screen.getByText(/internet connection/i)).toBeInTheDocument();
  });

  it("stays silent when it has no useful advice", () => {
    const { container } = render(<ErrorRemedy error={apiError(500)} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("ErrorNote", () => {
  it("routes an expired session to sign-in rather than to the connection", () => {
    render(<ErrorNote error={apiError(401)} />);
    expect(screen.getByRole("link", { name: /sign in again/i })).toBeInTheDocument();
    expect(screen.queryByText(/Check your connection/i)).not.toBeInTheDocument();
  });

  it("keeps the connection advice for a network failure", () => {
    render(<ErrorNote error={networkError()} />);
    expect(screen.getByText(/Check your connection/i)).toBeInTheDocument();
  });

  it("adds no remedy at all to a server error", () => {
    render(<ErrorNote error={apiError(500)} />);
    expect(screen.queryByText(/Check your connection/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /sign in/i })).not.toBeInTheDocument();
  });
});
