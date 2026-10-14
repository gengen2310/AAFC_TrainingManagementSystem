// D21 (2026-10-12): promptText() is one prompt at a time, and every way of
// closing it settles the caller. Before: a second call reset the open prompt's
// input (wiping typed text; WebKit triggers it from "+ Add new..." selects) and
// orphaned the first caller; a backdrop close left the caller pending forever.
import { test, expect, Page } from "../e2e-fixtures";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;
const BACKEND_BASE =
  process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000";

test.beforeAll(async () => {
  await resetBackendRateLimits(BACKEND_BASE);
});

async function login(page: Page) {
  if (LOCAL_API_BASE) {
    await page.addInitScript((base) => { (window as any).AAFC_API_BASE = base; }, LOCAL_API_BASE);
  }
  await page.goto("/");
  await page.locator("#auth-type").selectOption("squadron");
  await page.locator("#auth-wing-select").selectOption("7WG");
  await page.locator("#auth-sqn-select").selectOption("703");
  await page.locator("#auth-role").selectOption("sqn_admin");
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill("ADMIN703");
  await page.locator("#auth-btn").click();
  await expect(page.locator("#app")).toBeVisible({ timeout: 10000 });
}

test("a second promptText while one is open is refused and keeps the typed text", async ({ page }) => {
  await login(page);
  await page.evaluate(() => { (window as any).__first = (window as any).promptText("Name", "Name"); });
  await expect(page.locator("#m-text-input")).toBeVisible();
  await page.locator("#ti-input").fill("typed by the user");
  const second = await page.evaluate(() => (window as any).promptText("Name again", "Name"));
  expect(second).toBeNull();
  await expect(page.locator("#ti-input")).toHaveValue("typed by the user");
  await expect(page.locator("#ti-title")).toHaveText("Name");
  await page.locator("#ti-ok-btn").click();
  await expect(page.locator("#m-text-input")).toBeHidden();
  expect(await page.evaluate(() => (window as any).__first)).toBe("typed by the user");
});

test("closing the prompt from the backdrop cancels it, and the next prompt still works", async ({ page }) => {
  await login(page);
  await page.evaluate(() => { (window as any).__p = (window as any).promptText("One", "One"); });
  await expect(page.locator("#m-text-input")).toBeVisible();
  await page.locator("#m-text-input").click({ position: { x: 5, y: 5 } });   // the backdrop
  await expect(page.locator("#m-text-input")).toBeHidden();
  expect(await page.evaluate(() => (window as any).__p)).toBeNull();
  await page.evaluate(() => { (window as any).__q = (window as any).promptText("Two", "Two"); });
  await expect(page.locator("#m-text-input")).toBeVisible();
  await page.locator("#ti-input").fill("second prompt");
  await page.locator("#ti-ok-btn").click();
  expect(await page.evaluate(() => (window as any).__q)).toBe("second prompt");
});
