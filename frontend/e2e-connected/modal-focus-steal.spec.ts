import { test, expect, Page } from "../e2e-fixtures";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// Root cause of the intermittent REM-111 CI failure (facilitator statistics):
// openModal() moves focus to the dialog's first field 200 ms after opening.
// If the user (or Playwright's fill) has ALREADY focused another field in that
// window, the timer stole focus mid-typing: "Regression" typed into Family
// Name landed in Current Rank, Family Name stayed empty, saveFac() refused
// ("Family name required") and the dialog never closed. Captured CI snapshot:
// Rank = "Regression", Family Name = "". The browser clock is virtual here, so
// the 200 ms timer fires deterministically -- no sleeps.

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

test.beforeEach(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");
});

async function login(page: Page) {
  if (LOCAL_API_BASE) await page.addInitScript((b) => { (window as any).AAFC_API_BASE = b; }, LOCAL_API_BASE);
  await page.goto("/");
  await page.locator("#auth-type").selectOption("squadron");
  await page.locator("#auth-wing-select").selectOption("7WG");
  await page.locator("#auth-sqn-select").selectOption("703");
  await page.locator("#auth-role").selectOption("sqn_admin");
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill("ADMIN703");
  await page.locator("#auth-btn").click();
  await expect(page.locator(".ph-title", { hasText: "Training Dashboard" })).toBeVisible({ timeout: 10000 });
}

test("a field focused right after a dialog opens keeps focus when the deferred auto-focus fires", async ({ page }) => {
  await login(page);
  await page.evaluate(() => (window as any).nav("facilitators"));
  await page.clock.install();
  await page.getByRole("button", { name: "+ Add Facilitator" }).click();
  await page.locator("#fac-last").focus();                 // the user is already typing here
  await page.clock.runFor(1000);                           // the 200 ms auto-focus timer fires
  await page.keyboard.type("Regression");
  await expect(page.locator("#fac-last")).toHaveValue("Regression");
  await expect(page.locator("#fac-rank")).toHaveValue("");
});

test("a dialog nobody has focused into still gets its first field focused", async ({ page }) => {
  await login(page);
  await page.evaluate(() => (window as any).nav("facilitators"));
  await page.clock.install();
  await page.getByRole("button", { name: "+ Add Facilitator" }).click();
  await page.clock.runFor(1000);
  await expect(page.locator("#fac-rank")).toBeFocused();
});
