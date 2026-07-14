import { test, expect } from "@playwright/test";

// ── Auth flows ────────────────────────────────────────────────────────────────
// Targets the React Planning Workspace (port 5173).
// Backend must be running and seeded on port 8000 before these tests run.

test.describe("Login", () => {
  test("valid sqn_admin login reaches dashboard", async ({ page }) => {
    await page.goto("/");
    await page.getByLabel("Access code").fill("ADMIN703");
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
  });

  test("invalid code shows error alert and stays on login page", async ({ page }) => {
    await page.goto("/");
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
    await page.getByLabel("Access code").fill("ADMIN703");
    await page.getByRole("button", { name: "Log in" }).click();
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
    await page.getByLabel("Access code").fill("ADMIN703");
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
    // Clear the token to simulate expiry
    await page.evaluate(() => sessionStorage.removeItem("aafc_token"));
    await page.reload();
    // Should return to login
    await expect(page.getByRole("button", { name: "Log in" })).toBeVisible({ timeout: 5000 });
  });
});

test.describe("Role-based landing", () => {
  test("sqn_general user reaches dashboard", async ({ page }) => {
    await page.goto("/");
    await page.getByLabel("Access code").fill("703SQN2026");
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
  });

  test("wing_admin user reaches wing overview", async ({ page }) => {
    await page.goto("/");
    await page.getByLabel("Access code").fill("ADMIN7WG");
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page.getByRole("heading", { name: /wing overview/i })).toBeVisible({ timeout: 10000 });
  });

  test("national_admin user reaches national overview", async ({ page }) => {
    await page.goto("/");
    await page.getByLabel("Access code").fill("ADMINNATIONAL");
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page.getByRole("heading", { name: /national overview/i })).toBeVisible({ timeout: 10000 });
  });

  test("auditor user reaches audit log", async ({ page }) => {
    await page.goto("/");
    await page.getByLabel("Access code").fill("AUDITOR2026");
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page.getByRole("heading", { name: /audit/i })).toBeVisible({ timeout: 10000 });
  });
});
