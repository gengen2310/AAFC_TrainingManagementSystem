import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// REM-107: unit_type has been a real field on Squadron (standard_squadron /
// specialist_squadron / specialist_flight / support_unit) since v9, with
// full create/edit/list support -- but Account Management's Units table had
// no way to filter the list down to just Specialist Units even though the
// backend already supports GET /api/squadrons?unit_type=. This adds the
// missing filter dropdown.

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

test.beforeEach(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");
});

async function loginNational(page: Page, code: string) {
  if (LOCAL_API_BASE) {
    await page.addInitScript((base) => { (window as any).AAFC_API_BASE = base; }, LOCAL_API_BASE);
  }
  await page.goto("/");
  await page.locator("#auth-type").selectOption("national");
  await page.locator("#auth-role").selectOption("system_admin");
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill(code);
  await page.locator("#auth-btn").click();
  await expect(page.getByText("System Overview")).toBeVisible({ timeout: 10000 });
}

test("Units table can be filtered to a single unit type, and a Specialist Flight created via the UI shows its type badge", async ({ page }) => {
  const uniqueCode = "RM107" + (Date.now() % 100000);

  await loginNational(page, "SYSADMIN2026");
  await page.evaluate(() => (window as any).nav("accounts"));
  await expect(page.locator("#acct-units-card")).toBeVisible({ timeout: 10000 });

  await page.locator("#sqn-create-btn").click();
  await page.locator("#csq-code").fill(uniqueCode);
  await page.locator("#csq-name").fill("REM-107 Filter Test Unit");
  await page.locator("#csq-wing").selectOption({ label: "7WG" });
  await page.locator("#csq-type").selectOption("specialist_flight");
  await page.locator("#m-create-sqn button", { hasText: "Create Unit" }).click();
  await expect(page.locator("#m-create-sqn")).not.toHaveClass(/active/, { timeout: 10000 });

  const row = page.locator("#units-table tr", { hasText: uniqueCode });
  await expect(row).toBeVisible({ timeout: 10000 });
  await expect(row.getByText("Specialist Flight")).toBeVisible();

  // Filtering to a different type hides the new unit.
  await page.locator("#units-type-filter").selectOption("support_unit");
  await expect(page.locator("#units-table tr", { hasText: uniqueCode })).toHaveCount(0);

  // Filtering to its own type shows it again.
  await page.locator("#units-type-filter").selectOption("specialist_flight");
  await expect(page.locator("#units-table tr", { hasText: uniqueCode })).toBeVisible();

  // "All Types" always shows it regardless of filter state.
  await page.locator("#units-type-filter").selectOption("all");
  await expect(page.locator("#units-table tr", { hasText: uniqueCode })).toBeVisible();
});
