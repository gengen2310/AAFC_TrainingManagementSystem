import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// WORK-13: Parade Night and Mission Backlog filter values must persist across
// page reloads. Filters are saved to sessionStorage keys 'aafc_pn_filters' and
// 'aafc_mission_filters' on every renderPN() / renderMissions() call, then
// restored via _restorePNFilters() / _restoreMissionFilters() inside bootApp().
// Because bootApp() is called from tryRestoreSession() on page reload (when a
// valid aafc_token remains in sessionStorage), the filter state survives a full
// browser refresh without re-login.

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

test.beforeAll(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");
});

async function loginSquadron(page: Page, code: string) {
  if (LOCAL_API_BASE) {
    await page.addInitScript((base) => {
      (window as any).AAFC_API_BASE = base;
    }, LOCAL_API_BASE);
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

test("WORK-13: Parade Night status filter persists across page reload", async ({ page }) => {
  // Verifies _savePNFilters() / _restorePNFilters() round-trip through sessionStorage.
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));

  await loginSquadron(page, "ADMIN703");

  // Navigate to Parade Nights and confirm the filter bar is ready.
  await page.evaluate(() => (window as any).nav("parade-nights"));
  await expect(page.locator("#pn-f-status")).toBeVisible({ timeout: 8000 });

  // Confirm default is "all", then change to "planned".
  expect(await page.locator("#pn-f-status").inputValue()).toBe("all");
  await page.locator("#pn-f-status").selectOption("planned");

  // Give renderPN() (triggered by onchange) a moment to write to sessionStorage.
  await page.waitForTimeout(300);

  // Verify the filter value is now in sessionStorage before reload.
  const saved = await page.evaluate(() => {
    try { return JSON.parse(sessionStorage.getItem("aafc_pn_filters") || "null"); }
    catch { return null; }
  });
  expect(saved?.sf).toBe("planned");

  // Full page reload — addInitScript re-runs; tryRestoreSession() reads aafc_token.
  await page.reload();

  // Wait for the auto-restored session to land on the training dashboard.
  await expect(page.locator(".ph-title", { hasText: "Training Dashboard" })).toBeVisible({ timeout: 12000 });

  // Navigate to Parade Nights — bootApp() already called _restorePNFilters()
  // which set pn-f-status to "planned" before renderAll() ran.
  await page.evaluate(() => (window as any).nav("parade-nights"));
  await expect(page.locator("#pn-f-status")).toBeVisible({ timeout: 8000 });

  expect(await page.locator("#pn-f-status").inputValue()).toBe("planned");
  expect(errors, `no uncaught JS errors: ${errors.join("; ")}`).toHaveLength(0);
});

test("WORK-13: Parade Night term filter persists across page reload", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));

  await loginSquadron(page, "ADMIN703");

  await page.evaluate(() => (window as any).nav("parade-nights"));
  await expect(page.locator("#pn-f-term")).toBeVisible({ timeout: 8000 });

  await page.locator("#pn-f-term").selectOption("T1");
  await page.waitForTimeout(300);

  const saved = await page.evaluate(() => {
    try { return JSON.parse(sessionStorage.getItem("aafc_pn_filters") || "null"); }
    catch { return null; }
  });
  expect(saved?.tf).toBe("T1");

  await page.reload();
  await expect(page.locator(".ph-title", { hasText: "Training Dashboard" })).toBeVisible({ timeout: 12000 });
  await page.evaluate(() => (window as any).nav("parade-nights"));
  await expect(page.locator("#pn-f-term")).toBeVisible({ timeout: 8000 });

  expect(await page.locator("#pn-f-term").inputValue()).toBe("T1");
  expect(errors, `no uncaught JS errors: ${errors.join("; ")}`).toHaveLength(0);
});
