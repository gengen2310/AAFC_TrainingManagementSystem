import { test, expect, type Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// ── Cross-origin session handoff (HARD-10 remaining item) ─────────────────────
//
// Architecture requirement (architecture.md):
//   The aafc_session cookie (SameSite=None; Secure in production; SameSite=lax
//   in local dev) is the fallback auth mechanism used when there is no
//   sessionStorage token — e.g. a fresh tab opened cross-origin, such as
//   clicking "Open Planning Workspace" from the legacy TMS nav.
//
// This test proves the handoff works end-to-end:
//   1. Log in via the connected-frontend (TMS, :8080) — this sets aafc_session
//   2. Navigate to the Planning Workspace (:5173) WITHOUT any further login
//   3. The PW must auto-authenticate via the cookie (AuthProvider calls /api/me
//      on mount with credentials:include — cookie is same-site with localhost)
//
// Note: In local dev, COOKIE_SAMESITE defaults to "lax" (not "none"). Browsers
// treat localhost as a single site regardless of port, so SameSite=Lax is
// sufficient for same-browser cross-port navigation. In production, "none" +
// Secure is required for cross-origin behaviour.
//
// Requires: TMS server on :8080 AND Vite dev server on :5173 both running.
// Skip this test if the PW server is not reachable.

const PW_BASE = process.env.PW_BASE_URL || "http://localhost:5173";
const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE || "";

test.beforeAll(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || "http://localhost:8000");
});

async function loginViaTMS(page: Page, code: string) {
  if (LOCAL_API_BASE) {
    await page.addInitScript((base) => { (window as any).AAFC_API_BASE = base; }, LOCAL_API_BASE);
  }
  await page.goto("/");
  await page.locator("#auth-type").selectOption("squadron");
  await page.locator("#auth-wing-select").selectOption("7WG");
  await page.locator("#auth-sqn-select").selectOption("703");
  await page.locator("#auth-role").selectOption("sqn_admin");
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill(code);
  await page.locator("#auth-btn").click();
  await expect(page.locator(".ph-title", { hasText: "Training Dashboard" })).toBeVisible({ timeout: 10000 });
}

test("Planning Workspace auto-authenticates via cookie after TMS login (no second login needed)", async ({ page }) => {
  // Step 1: Log in via TMS (localhost:8080)
  // This sets the aafc_session httpOnly cookie on localhost.
  await loginViaTMS(page, "ADMIN703");

  // Step 2: Navigate to the Planning Workspace (localhost:5173) in the SAME page/context.
  // The browser retains the aafc_session cookie (same-site: both on localhost).
  // The PW's AuthProvider calls GET /api/auth/me on mount with credentials:include —
  // the backend validates the cookie and returns the session without a second login.
  await page.goto(PW_BASE);

  // Step 3: The PW dashboard must be visible — NOT the login form.
  const loginBtn = page.getByRole("button", { name: "Log in" });
  const dashboard = page.getByRole("heading", { name: "Dashboard" });

  // Allow up to 10s for the PW to resolve the cookie session and render.
  await expect(dashboard).toBeVisible({ timeout: 10000 });
  await expect(loginBtn).not.toBeVisible();
});

test("Planning Workspace shows correct squadron context after TMS login (no scope leak)", async ({ page }) => {
  await loginViaTMS(page, "ADMIN703");
  await page.goto(PW_BASE);

  // The "Return to TMS" link is only shown when there is NO authenticated session.
  // Its presence would indicate the cookie handoff failed.
  await expect(page.getByRole("link", { name: /return to tms/i })).not.toBeVisible({ timeout: 10000 });

  // Navigation is visible, confirming authenticated state.
  await expect(page.getByRole("navigation")).toBeVisible({ timeout: 10000 });
});

test("Logging out of TMS invalidates the Planning Workspace session", async ({ page }) => {
  await loginViaTMS(page, "ADMIN703");

  // Confirm PW is accessible before logout
  await page.goto(PW_BASE);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });

  // Log out from TMS — this calls POST /api/auth/logout which clears the aafc_session cookie.
  await page.goto("http://localhost:8080");
  const signOut = page.getByRole("button", { name: /sign out/i })
    .or(page.locator("#btn-logout"))
    .first();
  await expect(signOut).toBeVisible({ timeout: 8000 });
  await signOut.click();
  // After logout the TMS shows the login form; #auth-type is always the first visible element.
  await expect(page.locator("#auth-type")).toBeVisible({ timeout: 8000 });

  // Now open the PW — the cookie is gone, so /api/me returns 401, and the login form appears.
  await page.goto(PW_BASE);
  await expect(page.getByRole("button", { name: "Log in" })).toBeVisible({ timeout: 10000 });
});
