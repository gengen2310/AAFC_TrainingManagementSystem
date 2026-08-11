import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// REM-133: Wing HQ Event archive existed with no restore counterpart, and
// archived events were entirely invisible (no include_archived param on
// list_wing_events, no way to even see one to restore it). Added a "Show
// archived" toggle (table view only) plus a Restore button.

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

test("an archived Wing HQ event is hidden by default, visible via Show archived in table view, and Restore brings it back", async ({ page }) => {
  await loginWing(page, "ADMIN7WG");
  const base = LOCAL_API_BASE || "http://localhost:8000";
  const token = await page.evaluate(() => sessionStorage.getItem("aafc_token"));
  const hdr = { Authorization: `Bearer ${token}` };
  const me = await (await page.request.get(`${base}/api/auth/me`, { headers: hdr })).json();
  const wingId = me.session.wing_id as string;

  const title = `E2E REM-133 Event ${Date.now()}`;
  const createRes = await page.request.post(`${base}/api/wing-calendar/events?wing_id=${wingId}`, {
    data: { title, event_type: "wing_event", start_date: "2026-10-05", planning_importance: "key_event" },
    headers: hdr,
  });
  expect(createRes.ok()).toBe(true);
  const eventId = (await createRes.json()).id as string;
  const archiveRes = await page.request.post(`${base}/api/wing-calendar/events/${eventId}/archive`, { headers: hdr });
  expect(archiveRes.ok()).toBe(true);

  await page.evaluate(() => (window as any).loadWingCalendar());
  // Switch to table view -- Show archived only applies there.
  await page.locator("#wc-view-table-btn").click();
  await page.waitForTimeout(300);

  await expect(page.locator("#wc-body")).not.toContainText(title);

  await page.locator("#wc-show-archived").check();
  const row = page.locator("#wc-body tr", { hasText: title });
  await expect(row).toBeVisible({ timeout: 5000 });
  await expect(row).toContainText("Archived");

  await row.getByRole("button", { name: "Restore" }).click();
  await expect(page.locator("#wc-body tr", { hasText: title }).getByRole("button", { name: "Restore" })).toHaveCount(0, { timeout: 5000 });
  await page.locator("#wc-show-archived").uncheck();
  await expect(page.locator("#wc-body tr", { hasText: title })).toBeVisible({ timeout: 5000 });

  // Cleanup.
  await page.request.post(`${base}/api/wing-calendar/events/${eventId}/archive`, { headers: hdr });
});

test("wing_viewer (read-only) sees no Show archived control on Wing HQ Calendar", async ({ page }) => {
  if (LOCAL_API_BASE) {
    await page.addInitScript((base) => { (window as any).AAFC_API_BASE = base; }, LOCAL_API_BASE);
  }
  await page.goto("/");
  await page.locator("#auth-type").selectOption("wing");
  await page.locator("#auth-wing-select").selectOption("7WG");
  await page.locator("#auth-role").selectOption("wing_viewer");
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill("7WG2026");
  await page.locator("#auth-btn").click();
  await expect(page.locator("#cmd-dash-wing .ph-title", { hasText: "Training Dashboard" })).toBeVisible({ timeout: 10000 });
  await page.evaluate(() => (window as any).nav("wing-calendar"));
  await page.locator("#wc-view-table-btn").click();
  await expect(page.locator("#wc-show-archived-row")).toBeHidden();
});
