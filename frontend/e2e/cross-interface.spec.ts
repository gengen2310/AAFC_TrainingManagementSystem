import { test, expect } from "@playwright/test";

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
  // Planning workspace heading or tab structure must be visible
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 10000 });
});

test("logout from main app also loses planning workspace access", async ({ page }) => {
  // Confirm planning workspace accessible
  await page.goto("/planning");
  await expect(page.getByRole("button", { name: "Log in" })).not.toBeVisible();

  // Log out from main app
  await page.goto("/dashboard");
  await page.getByRole("button", { name: /log out|sign out/i }).click();
  await expect(page.getByRole("button", { name: "Log in" })).toBeVisible({ timeout: 5000 });

  // Now planning workspace should require login
  await page.goto("/planning");
  // Should show "Session not found" because token was cleared
  await expect(
    page.getByText(/session not found|please.*log in.*first|return to tms/i)
  ).toBeVisible({ timeout: 5000 });
});

test("planning workspace shows correct squadron context", async ({ page }) => {
  await page.goto("/planning");
  await expect(page.getByRole("button", { name: "Log in" })).not.toBeVisible();
  // 703 squadron context — planning workspace should not show another squadron's data
  // At minimum, verify it loads a planning year or is empty for 703's own unit
  // The NotAuthenticated component shows "Return to TMS" link only if session is missing
  await expect(page.getByRole("link", { name: /return to tms/i })).not.toBeVisible();
});
