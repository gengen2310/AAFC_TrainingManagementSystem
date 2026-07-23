import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "../auth/AuthProvider";
import { LoginPage } from "../auth/LoginPage";

describe("LoginPage", () => {
  it("shows only an access-code field, no code patterns", () => {
    const qc = new QueryClient();
    render(<QueryClientProvider client={qc}><AuthProvider><LoginPage /></AuthProvider></QueryClientProvider>);
    expect(screen.getByLabelText(/access code/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /log in/i })).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/SQN2026|ADMIN7WG|ADMINNATIONAL/);
  });
});
