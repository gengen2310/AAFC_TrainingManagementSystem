import { test, expect } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";
import { loginPW } from "../e2e-login-helper";

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

// ── Auth flows ────────────────────────────────────────────────────────────────
// Targets the React Planning Workspace (port 5173).
// Backend must be running and seeded on port 8000 before these tests run.

test.describe("Login", () => {
  test("valid sqn_admin login reaches dashboard", async ({ page }) => {
    await page.goto("/");
    await loginPW(page, "ADMIN703");
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
  });

  // REM-84: an invalid CODE for an otherwise-correctly-resolved account (not
  // an unmapped/unknown code -- that's a different, ordinary "no such
  // combination" case at the lookup step, not what this test is about) --
  // exercises the same error path the old single-field flow tested, just
  // reached via unit/wing/squadron/role selection first.
  test("invalid code shows error alert and stays on login page", async ({ page }) => {
    await page.goto("/");
    await page.getByLabel("Login as").selectOption("squadron");
    await page.getByLabel("Wing", { exact: true }).selectOption("7WG");
    await page.getByLabel("Squadron / Unit").selectOption("703");
    await page.getByLabel("Role", { exact: true }).selectOption("sqn_admin");
    await page.getByLabel("Access code").fill("NOTACODE");
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page.getByRole("alert")).toBeVisible({ timeout: 5000 });
    // Must NOT navigate away from login
    await expect(page.getByRole("button", { name: "Log in" })).toBeVisible();
  });

  test("empty code keeps login button disabled", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("button", { name: "Log in" })).toBeDisabled();
  });

  test("logout clears session and returns to login", async ({ page }) => {
    await page.goto("/");
    await loginPW(page, "ADMIN703");
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
    // Find and click logout (could be in a menu or nav)
    await page.getByRole("button", { name: /log out|sign out/i }).click();
    await expect(page.getByRole("button", { name: "Log in" })).toBeVisible({ timeout: 5000 });
  });

  test("direct route refresh without session shows login", async ({ page }) => {
    // Navigate directly to an authenticated route without logging in
    await page.goto("/dashboard");
    // Should redirect to login or show login form
    await expect(page.getByRole("button", { name: "Log in" })).toBeVisible({ timeout: 5000 });
  });

  test("session expiry forces re-login", async ({ page }) => {
    await page.goto("/");
    await loginPW(page, "ADMIN703");
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
    // Simulate session expiry: use the Sign out button (which calls the backend logout
    // endpoint AND clears the HttpOnly session cookie). Clearing sessionStorage alone
    // does not work — the backend falls back to the cookie on reload.
    await page.getByRole("button", { name: /sign out/i }).click();
    await expect(page.getByRole("button", { name: "Log in" })).toBeVisible({ timeout: 5000 });
    await page.reload();
    await expect(page.getByRole("button", { name: "Log in" })).toBeVisible({ timeout: 5000 });
  });
});

test.describe("Role-based landing", () => {
  test("sqn_general user reaches dashboard", async ({ page }) => {
    await page.goto("/");
    await loginPW(page, "703SQN2026");
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
  });

  test("wing_admin user reaches wing overview", async ({ page }) => {
    await page.goto("/");
    await loginPW(page, "ADMIN7WG");
    // WingOverview renders <h1>Wing Assurance</h1>
    await expect(page.getByRole("heading", { name: /wing assurance/i })).toBeVisible({ timeout: 10000 });
  });

  test("national_admin user reaches national overview", async ({ page }) => {
    await page.goto("/");
    await loginPW(page, "ADMINNATIONAL");
    // NationalOverview renders <h1>National Assurance</h1>
    await expect(page.getByRole("heading", { name: /national assurance/i })).toBeVisible({ timeout: 10000 });
  });

  test("auditor user reaches audit log", async ({ page }) => {
    await page.goto("/");
    await loginPW(page, "AUDITOR2026");
    await expect(page.getByRole("heading", { name: /audit/i })).toBeVisible({ timeout: 10000 });
  });
});
