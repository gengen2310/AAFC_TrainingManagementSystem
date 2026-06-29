import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AuthProvider } from "../auth/AuthProvider";
import { LoginPage } from "../auth/LoginPage";

describe("LoginPage", () => {
  it("shows only an access-code field, no code patterns", () => {
    render(<AuthProvider><LoginPage /></AuthProvider>);
    expect(screen.getByLabelText(/access code/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /log in/i })).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/SQN2026|ADMIN7WG|ADMINNATIONAL/);
  });
});
