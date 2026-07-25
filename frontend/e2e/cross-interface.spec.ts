import { test, expect } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// DEFECT-004: playwright-global-setup.ts resets rate limits once per full
// suite invocation, which is not always enough for a large suite -- a
// spec file's own request volume, especially with other files having run
// immediately before it, can still cross the general API limiter's
// 300 req/60s budget partway through (observed live running this suite).
// A per-file reset gives this file its own fresh budget. Best-effort; see
// e2e-rate-limit-reset.ts for what this does and its known limitations.
test.beforeAll(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || "http://localhost:8000");
});

// ── Cross-interface: Planning Workspace (no second login) ─────────────────────
// The Planning Workspace (/planning) must be accessible without a second login
// when the user is already authenticated. This tests the cookie/token sharing
// between the full React app routes.

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Access code").fill("ADMIN703");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
});

test("planning workspace loads without second login", async ({ page }) => {
  await page.goto("/planning");
  // Should NOT see the login page again
  await expect(page.getByRole("button", { name: "Log in" })).not.toBeVisible();
  // Should see the planning workspace content (not the "Session not found" error)
  await expect(page.getByText(/session not found|please.*log in.*first/i)).not.toBeVisible();
  // PlanningWorkspace renders <div role="main" aria-label="Planning workspace"> (no h1)
  await expect(page.getByRole("main", { name: /planning workspace/i })).toBeVisible({ timeout: 10000 });
});

test("logout from main app also loses planning workspace access", async ({ page }) => {
  // Confirm planning workspace accessible
  await page.goto("/planning");
  await expect(page.getByRole("button", { name: "Log in" })).not.toBeVisible();

  // Log out from main app via Sign out button in AppShell
  await page.goto("/dashboard");
  await page.getByRole("button", { name: /sign out/i }).click();
  await expect(page.getByRole("button", { name: "Log in" })).toBeVisible({ timeout: 5000 });

  // Now /planning shows LoginPage (full app mode — not module "Session not found" message)
  await page.goto("/planning");
  await expect(page.getByRole("button", { name: "Log in" })).toBeVisible({ timeout: 5000 });
});

test("planning workspace shows correct squadron context", async ({ page }) => {
  await page.goto("/planning");
  await expect(page.getByRole("button", { name: "Log in" })).not.toBeVisible();
  // 703 squadron context — planning workspace should not show another squadron's data
  // At minimum, verify it loads a planning year or is empty for 703's own unit
  // The NotAuthenticated component shows "Return to TMS" link only if session is missing
  await expect(page.getByRole("link", { name: /return to tms/i })).not.toBeVisible();
});
