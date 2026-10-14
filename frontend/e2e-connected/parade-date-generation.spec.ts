import { test, expect, Page } from "../e2e-fixtures";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// Generate Parade Nights preview, through the real modal. Preview only: it
// writes nothing, so no cleanup is needed.
//  - A skipped night in a fortnightly series must not move the rest of the
//    series (it used to: skipping 20 Feb gave 27 Feb, 12 Mar, ...).
//  - An unbounded request is refused with a message the user can act on
//    (it used to be a 500 after seconds of server CPU).

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

test.beforeEach(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");
});

async function openGenerator(page: Page) {
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
  await page.evaluate(() => (window as any).nav("parade-nights"));
  await page.getByRole("button", { name: "Generate Parade Nights" }).click();
  await expect(page.locator("#m-gen-dates")).toBeVisible();
}

test("a skipped fortnightly night does not shift the rest of the series", async ({ page }) => {
  await openGenerator(page);
  await page.locator("#gen-freq").selectOption("fortnightly");
  await page.locator("#gen-weekday").selectOption("2");              // Wednesday
  await page.locator("#gen-start").fill("2092-02-01");
  await page.locator("#gen-end").fill("2092-04-30");
  await page.locator("#gen-excl-dates").fill("2092-02-20");
  await page.locator("#gen-excl-hols").uncheck();
  await page.getByRole("button", { name: "Preview Parade Nights" }).click();
  const rows = page.locator("#gen-preview-area tbody tr");
  await expect(rows).toHaveCount(7);
  const cells = await rows.locator("td:first-child").allTextContents();
  expect(cells).toEqual(["2092-02-06", "2092-02-20", "2092-03-05", "2092-03-19", "2092-04-02", "2092-04-16", "2092-04-30"]);
  await expect(rows.nth(1)).toContainText("Explicitly skipped");
  await expect(page.locator("#gen-msg")).toHaveText("6 new dates of 7 in range.");
});

test("an unbounded range is refused with an actionable message, not a server error", async ({ page }) => {
  await openGenerator(page);
  await page.locator("#gen-freq").selectOption("daily");
  await page.locator("#gen-start").fill("2092-01-01");
  await page.locator("#gen-end").fill("2096-12-31");
  await page.getByRole("button", { name: "Preview Parade Nights" }).click();
  await expect(page.locator("#gen-msg")).toContainText("Shorten the date range");
  await expect(page.locator("#gen-preview-area")).toBeHidden();
});
