import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// REM-108: Flight archive existed with no restore counterpart, and archived
// flights were entirely invisible in the SA console (no way to even see one
// to restore it). Added a "Show archived" toggle (matching the existing
// Wings/Squadrons pattern) plus a Restore button.

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
  await expect(page.locator("#app")).toBeVisible({ timeout: 10000 });
}

test("an archived Flight is hidden by default, visible via Show archived, and Restore brings it back", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");
  const base = LOCAL_API_BASE || "http://localhost:8000";
  const token = await page.evaluate(() => sessionStorage.getItem("aafc_token"));
  const hdr = { Authorization: `Bearer ${token}` };
  const me = await (await page.request.get(`${base}/api/auth/me`, { headers: hdr })).json();
  const squadronId = me.session.squadron_id as string;

  const suffix = String(Date.now());
  const flightName = `REM-108 E2E ${suffix}`;
  const createRes = await page.request.post(`${base}/api/flights`, {
    data: { name: flightName, squadron_id: squadronId },
    headers: hdr,
  });
  expect(createRes.ok()).toBe(true);
  const flightId = (await createRes.json()).flight_id as string;
  const archiveRes = await page.request.post(`${base}/api/flights/${flightId}/archive`, { headers: hdr });
  expect(archiveRes.ok()).toBe(true);

  await page.evaluate(() => (window as any).nav("accounts"));
  await page.waitForTimeout(500);

  // Hidden by default.
  await expect(page.locator("#flight-table")).not.toContainText(flightName);

  // Visible with "Show archived" checked, flagged as archived.
  await page.locator("#flights-show-archived").check();
  const row = page.locator("#flight-table tr", { hasText: flightName });
  await expect(row).toBeVisible({ timeout: 5000 });
  await expect(row).toContainText("Archived");

  // Restore brings it back into the default (unchecked) view.
  await row.getByRole("button", { name: "Restore" }).click();
  await page.locator("#flights-show-archived").uncheck();
  await expect(page.locator("#flight-table tr", { hasText: flightName })).toBeVisible({ timeout: 5000 });

  // Cleanup.
  await page.request.post(`${base}/api/flights/${flightId}/archive`, { headers: hdr });
});
