import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// Wing HQ Calendar -- risk register asked for real Wing/National calendar
// GRID views ("not just table/list views"). Previously renderWingCalendar()
// only ever built a flat <table>; this suite covers the new month-grid
// default view plus the preserved table-view toggle.
const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

test.beforeAll(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");
});

async function loginWing(page: Page, code: string) {
  if (LOCAL_API_BASE) {
    await page.addInitScript((base) => { (window as any).AAFC_API_BASE = base; }, LOCAL_API_BASE);
  }
  await page.goto("/");
  await page.locator("#auth-type").selectOption("wing");
  await page.locator("#auth-wing-select").selectOption("7WG");
  await page.locator("#auth-role").selectOption("wing_admin");
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill(code);
  await page.locator("#auth-btn").click();
  await expect(page.locator("#cmd-dash-wing .ph-title", { hasText: "Training Dashboard" })).toBeVisible({ timeout: 10000 });
  await page.evaluate(() => (window as any).nav("wing-calendar"));
}

test("Wing Calendar defaults to grid view with a month navigator", async ({ page }) => {
  await loginWing(page, "ADMIN7WG");
  await expect(page.locator("#wc-view-grid-btn")).toHaveClass(/active/);
  await expect(page.locator("#wc-grid-month-label")).toBeVisible();
  await expect(page.locator(".cal-grid-table")).toBeVisible();
});

test("Toggling to Table view shows the preserved list, toggling back returns to grid", async ({ page }) => {
  await loginWing(page, "ADMIN7WG");
  await page.locator("#wc-view-table-btn").click();
  await expect(page.locator("#wc-view-table-btn")).toHaveClass(/active/);
  await expect(page.locator("#wc-grid-nav")).toBeHidden();
  await page.locator("#wc-view-grid-btn").click();
  await expect(page.locator("#wc-grid-nav")).toBeVisible();
});

test("A newly created event appears as a chip on its date in the grid", async ({ page }) => {
  await loginWing(page, "ADMIN7WG");
  const today = new Date();
  const iso = today.toISOString().slice(0, 10);
  const title = `E2E Grid Event ${Date.now()}`;

  await page.getByRole("button", { name: "+ New Event" }).click();
  await page.locator("#we-title").fill(title);
  await page.locator("#we-start").fill(iso);
  await page.getByRole("button", { name: "Save Event" }).click();
  await expect(page.locator(".cal-grid-evt", { hasText: title })).toBeVisible({ timeout: 8000 });
});

test("Month navigation moves to the adjacent month", async ({ page }) => {
  await loginWing(page, "ADMIN7WG");
  const before = await page.locator("#wc-grid-month-label").textContent();
  await page.getByRole("button", { name: "Next month" }).click();
  const after = await page.locator("#wc-grid-month-label").textContent();
  expect(after).not.toBe(before);
});
