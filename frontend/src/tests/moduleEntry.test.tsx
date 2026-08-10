import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { useScopedSquadron } from "../layout/SquadronViewContext";

// REM-101 (PW-CTX-01): App.tsx's module-mode entry (ModuleEntry, used when the
// Planning Workspace is opened as a standalone tab from Main TMS) previously
// rendered its routes WITHOUT a SquadronViewProvider, so any page calling
// useScopedSquadron()/useSquadronView() -- which the real PlanningWorkspace
// route does -- crashed with "useSquadronView must be used within
// SquadronViewProvider". The fix wraps ModuleEntry's <Routes> in
// SquadronViewProvider, matching full-app mode's own structure.
//
// MODULE_MODE is a module-level const read from the DOM
// (`document.querySelector('meta[name="aafc-module-mode"]')`) at the moment
// App.tsx is first imported. vi.hoisted() runs before any import statement
// (including this file's own), so the meta tag exists in time -- this avoids
// vi.resetModules() + a dynamic import(), which would create a SECOND
// SquadronViewContext module instance (a different React Context object)
// from the one this file's own top-level useScopedSquadron import already
// resolved, making the provider and hook mismatch for reasons unrelated to
// the actual bug being tested.
vi.hoisted(() => {
  document.head.innerHTML = `<meta name="aafc-module-mode" content="true">`;
  window.history.pushState({}, "", "/planning");
});

vi.mock("../auth/AuthProvider", () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
  useAuth: () => ({ session: { role: "sqn_admin", squadron_id: "sqn-1" }, loading: false, logout: vi.fn() }),
}));

// Stub the real route component with one that calls the real useScopedSquadron
// hook -- the exact hook the reported crash came from -- so this test fails
// with the original bug's own error if SquadronViewProvider is ever removed
// again, rather than just asserting on implementation details.
vi.mock("../routes/PlanningWorkspace", () => ({
  PlanningWorkspace: () => {
    const { scoped } = useScopedSquadron();
    return <div data-testid="pw-loaded">Planning Workspace loaded, scoped={String(scoped)}</div>;
  },
}));

describe("ModuleEntry (module mode)", () => {
  it("renders PlanningWorkspace without throwing 'useSquadronView must be used within SquadronViewProvider'", async () => {
    const { default: App } = await import("../App");
    render(<App />);
    await waitFor(() => expect(screen.getByTestId("pw-loaded")).toBeInTheDocument());
    expect(screen.getByText(/scoped=true/)).toBeInTheDocument();
  });
});
