import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// Low-severity UI/UX fixes from the ADDENDUM UI/UX audit (2026-08-06):
// REM-92 (Weekly Program empty state) and REM-91 (System Console build
// fingerprint fallback for the unresolved local-dev placeholder).

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

test.beforeAll(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");
});

async function loginSquadron(page: Page, code: string, role: "sqn_admin" | "sqn_general" = "sqn_admin") {
  if (LOCAL_API_BASE) {
    await page.addInitScript((base) => {
      (window as any).AAFC_API_BASE = base;
    }, LOCAL_API_BASE);
  }
  await page.goto("/");
  await page.locator("#auth-type").selectOption("squadron");
  await page.locator("#auth-wing-select").selectOption("7WG");
  await page.locator("#auth-sqn-select").selectOption("703");
  await page.locator("#auth-role").selectOption(role);
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill(code);
  await page.locator("#auth-btn").click();
  await expect(page.locator("#app")).toBeVisible({ timeout: 10000 });
}

test("REM-92: Weekly Program shows guidance instead of a bare blank area before a parade night is chosen", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");
  await page.evaluate(() => (window as any).nav("weekly-program"));
  // Squadron 703 has seeded parade nights, so this exercises the "choose one"
  // branch specifically (the "no parade nights exist yet" branch is a
  // simple, low-risk conditional on the same data already used elsewhere on
  // this page -- verified via code review, not separately seeded here).
  await expect(page.locator("#wp-content")).toContainText(/choose a parade night/i, { timeout: 8000 });
});

test("REM-91: System Console shows a friendly build label, not the literal unresolved placeholder", async ({ page }) => {
  if (LOCAL_API_BASE) {
    await page.addInitScript((base) => {
      (window as any).AAFC_API_BASE = base;
    }, LOCAL_API_BASE);
  }
  await page.goto("/");
  await page.locator("#auth-type").selectOption("national");
  await page.locator("#auth-role").selectOption("system_admin");
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill("SYSADMIN2026");
  await page.locator("#auth-btn").click();
  await expect(page.locator("#app")).toBeVisible({ timeout: 10000 });
  await page.evaluate(() => (window as any).nav("system-console"));
  const commitEl = page.locator("#sc-build-commit");
  await expect(commitEl).toBeVisible({ timeout: 8000 });
  await expect(commitEl).not.toContainText("__APP_BUILD__");
  await expect(commitEl).toContainText("(local build)");
});
