import { test, expect } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";
import { loginPW } from "../e2e-login-helper";

const BACKEND = process.env.E2E_BACKEND_BASE_URL || "http://localhost:8000";

test.beforeAll(async () => {
  await resetBackendRateLimits(BACKEND);
});

/**
 * Cross-interface contract for the specialised Planning Workspace. The Main
 * TMS owns login/logout; PW consumes the same backend session and squadron
 * scope. These tests deliberately avoid the retired React dashboard/shell.
 */
test("shared TMS session opens Planning Workspace without any second-login controls", async ({ page }) => {
  await loginPW(page, "ADMIN703");

  await expect(page.getByRole("main", { name: /planning workspace/i })).toBeVisible();
  await expect(page.getByLabel("Access code")).toHaveCount(0);
  await expect(page.getByRole("button", { name: /log in/i })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Session not found" })).toHaveCount(0);
});

test("cookie fallback preserves the shared session after bearer state is removed", async ({ page }) => {
  await loginPW(page, "ADMIN703");

  // A fresh tab opened by Main TMS may have no sessionStorage token. Removing
  // the bearer token and reloading exercises the shared aafc_session fallback
  // rather than manufacturing a separate Planning Workspace login.
  await page.evaluate(() => sessionStorage.removeItem("aafc_token"));
  await page.reload();

  await expect(page.getByRole("main", { name: /planning workspace/i })).toBeVisible({ timeout: 10000 });
  await expect(page.getByRole("heading", { name: "Session not found" })).toHaveCount(0);
});

test("Planning Workspace reflects the authenticated squadron role context", async ({ page }) => {
  await loginPW(page, "ADMIN703");

  const banner = page.getByRole("banner", { name: "Planning workspace context" });
  await expect(banner).toBeVisible();
  await expect(banner).toContainText(/Sqn Admin/i);
  // Squadron-scoped users must not be offered the higher-scope context picker.
  await expect(page.getByLabel("Viewing squadron")).toHaveCount(0);
});

test("shared backend logout/revocation removes Planning Workspace access", async ({ page }) => {
  const { token } = await loginPW(page, "ADMIN703");

  const logout = await page.request.post(`${BACKEND}/api/auth/logout`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(logout.ok()).toBeTruthy();

  await page.evaluate(() => sessionStorage.removeItem("aafc_token"));
  await page.reload();

  await expect(page.getByRole("heading", { name: "Session not found" })).toBeVisible({ timeout: 10000 });
  await expect(page.getByRole("link", { name: "Return to TMS" })).toBeVisible();
  await expect(page.getByLabel("Access code")).toHaveCount(0);
});
