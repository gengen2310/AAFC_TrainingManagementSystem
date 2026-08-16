import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "../auth/AuthProvider";
import { LoginPage } from "../auth/LoginPage";

// REM-84: LoginPage now collects unit type / wing / squadron / role before
// the access-code field, matching connected-frontend's own flow -- because
// resolving a user_id via /api/auth/lookup first is what puts a login on the
// backend's scoped, per-account-lockout path (auth.py's own comments: the
// no-user_id path is "used by tests; production always provides user_id via
// /lookup"). These tests exercise that real behaviour, not just the UI shape.

const ORGS_RESPONSE = {
  wings: [
    { code: "7WG", name: "7 Wing", squadrons: [{ code: "703", name: "703 Squadron", unit_type: "standard_squadron" }] },
  ],
};

function renderLogin() {
  const qc = new QueryClient();
  return render(<QueryClientProvider client={qc}><AuthProvider><LoginPage /></AuthProvider></QueryClientProvider>);
}

function selectOption(el: HTMLElement, value: string) {
  fireEvent.change(el, { target: { value } });
}

afterEach(() => vi.restoreAllMocks());

describe("LoginPage", () => {
  it("shows the unit-type selector first, and no hardcoded demo codes anywhere", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      JSON.stringify(ORGS_RESPONSE), { status: 200, headers: { "content-type": "application/json" } })));
    renderLogin();
    expect(await screen.findByLabelText(/login as/i)).toBeInTheDocument();
    // Access code field is not shown until unit/role selection completes.
    expect(screen.queryByLabelText(/access code/i)).not.toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/SQN2026|ADMIN7WG|ADMINNATIONAL/);
  });

  it("reveals wing -> squadron -> role -> code in sequence for a squadron login", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      JSON.stringify(ORGS_RESPONSE), { status: 200, headers: { "content-type": "application/json" } })));
    renderLogin();

    selectOption(await screen.findByLabelText(/login as/i), "squadron");
    await waitFor(() => expect(screen.getByLabelText(/^wing$/i)).toBeInTheDocument());
    expect(screen.queryByLabelText(/squadron \/ unit/i)).not.toBeInTheDocument();

    selectOption(screen.getByLabelText(/^wing$/i), "7WG");
    await waitFor(() => expect(screen.getByLabelText(/squadron \/ unit/i)).toBeInTheDocument());
    expect(screen.queryByLabelText(/^role$/i)).not.toBeInTheDocument();

    selectOption(screen.getByLabelText(/squadron \/ unit/i), "703");
    await waitFor(() => expect(screen.getByLabelText(/^role$/i)).toBeInTheDocument());
    expect(screen.queryByLabelText(/access code/i)).not.toBeInTheDocument();

    selectOption(screen.getByLabelText(/^role$/i), "sqn_admin");
    await waitFor(() => expect(screen.getByLabelText(/access code/i)).toBeInTheDocument());
  });

  it("calls lookup then login with the resolved user_id -- the real bug this fixes", async () => {
    const fetchMock = vi.fn((url: string, _init?: RequestInit) => {
      if (url.includes("/api/auth/organisations")) {
        return Promise.resolve(new Response(JSON.stringify(ORGS_RESPONSE),
          { status: 200, headers: { "content-type": "application/json" } }));
      }
      if (url.includes("/api/auth/lookup")) {
        return Promise.resolve(new Response(JSON.stringify({ user_id: "u-703-admin", display_name: "703 Admin" }),
          { status: 200, headers: { "content-type": "application/json" } }));
      }
      if (url.includes("/api/auth/login")) {
        return Promise.resolve(new Response(JSON.stringify({
          token: "t1",
          session: { user_id: "u-703-admin", display_name: "703 Admin", role: "sqn_admin",
                     wing_id: "w1", squadron_id: "s1", national_id: null, is_wing: false, is_national: false,
                     proxy: null }, // R5-L14: include proxy field so proxy-state init after login is testable
        }), { status: 200, headers: { "content-type": "application/json" } }));
      }
      return Promise.resolve(new Response("{}", { status: 200, headers: { "content-type": "application/json" } }));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderLogin();

    selectOption(await screen.findByLabelText(/login as/i), "squadron");
    selectOption(await screen.findByLabelText(/^wing$/i), "7WG");
    selectOption(await screen.findByLabelText(/squadron \/ unit/i), "703");
    selectOption(await screen.findByLabelText(/^role$/i), "sqn_admin");
    const codeInput = await screen.findByLabelText(/access code/i);
    fireEvent.change(codeInput, { target: { value: "TESTCODE1" } });
    fireEvent.click(screen.getByRole("button", { name: /log in/i }));

    await waitFor(() => {
      const lookupCall = fetchMock.mock.calls.find(([url]) => String(url).includes("/api/auth/lookup"));
      expect(lookupCall).toBeTruthy();
      const lookupBody = JSON.parse((lookupCall![1] as RequestInit).body as string);
      expect(lookupBody).toEqual({ unit_type: "squadron", identifier: "703", role: "sqn_admin" });

      const loginCall = fetchMock.mock.calls.find(([url]) => String(url).includes("/api/auth/login"));
      expect(loginCall).toBeTruthy();
      const loginBody = JSON.parse((loginCall![1] as RequestInit).body as string);
      // The actual bug this fix closes: user_id must be sent, putting the
      // request on the backend's scoped per-account-lockout path instead of
      // the legacy scan-all path.
      expect(loginBody).toEqual({ code: "TESTCODE1", user_id: "u-703-admin" });
    });
  });

  it("national login skips the wing/squadron steps entirely", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      JSON.stringify(ORGS_RESPONSE), { status: 200, headers: { "content-type": "application/json" } })));
    renderLogin();

    selectOption(await screen.findByLabelText(/login as/i), "national");
    await waitFor(() => expect(screen.getByLabelText(/^role$/i)).toBeInTheDocument());
    expect(screen.queryByLabelText(/^wing$/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/squadron \/ unit/i)).not.toBeInTheDocument();

    selectOption(screen.getByLabelText(/^role$/i), "national_admin");
    await waitFor(() => expect(screen.getByLabelText(/access code/i)).toBeInTheDocument());
  });
});
