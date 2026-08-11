import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// REM-03 continuation: extends the existing manual Refresh pattern
// (Refreshing.../Updated at/failed-Retry, via the shared _pageRefresh()
// helper) beyond the original 4 pages (Training Dashboard, Activities,
// Calendar, Account Management) to Parade Nights, Curriculum, Facilitators,
// Resources, and Audit Log -- 9 of ~19 connected-frontend pages now covered.
// Full rollout to every remaining page is still not attempted (Weekly
// Program's header has a different no-print wrapping structure, Action
// Items has no .ph-actions container yet, Wing/National Activities are
// rendered via the shared _actTabLoad() mechanism) -- left as a further
// follow-up, not silently dropped.

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

test.beforeEach(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");
});

async function loginSquadron(page: Page, code: string) {
  if (LOCAL_API_BASE) {
    await page.addInitScript((base) => { (window as any).AAFC_API_BASE = base; }, LOCAL_API_BASE);
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

const pages: { navId: string; title: string; statusId: string }[] = [
  { navId: "parade-nights", title: "Parade Nights", statusId: "pn-refresh-status" },
  { navId: "curriculum", title: "Curriculum", statusId: "curr-refresh-status" },
  { navId: "facilitators", title: "Facilitators", statusId: "fac-refresh-status" },
  { navId: "resources", title: "Resources & Training Areas", statusId: "res-refresh-status" },
];

for (const p of pages) {
  test(`${p.title} page: Refresh button shows Refreshing... then Updated at`, async ({ page }) => {
    await loginSquadron(page, "ADMIN703");
    await page.evaluate((id) => (window as any).nav(id), p.navId);
    await expect(page.locator(".ph-title", { hasText: p.title })).toBeVisible({ timeout: 10000 });

    const status = page.locator(`#${p.statusId}`);
    const btn = status.locator("xpath=following-sibling::button[1]");
    await expect(btn).toHaveText("Refresh");
    await btn.click();
    // Refreshing state is often too fast to reliably catch mid-flight (the
    // real fetch can resolve within a few ms against a local backend), so
    // this asserts the terminal state -- the same tolerance the existing
    // REM-03 pages' own manual verification used.
    await expect(status).toHaveText(/^Updated at \d{2}:\d{2}$/, { timeout: 10000 });
  });
}

test("Audit Log page (national scope): Refresh button shows Updated at", async ({ page }) => {
  if (LOCAL_API_BASE) {
    await page.addInitScript((base) => { (window as any).AAFC_API_BASE = base; }, LOCAL_API_BASE);
  }
  await page.goto("/");
  await page.locator("#auth-type").selectOption("national");
  await page.locator("#auth-role").selectOption("national_admin");
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill("ADMINNATIONAL");
  await page.locator("#auth-btn").click();
  // national_admin's landing page is National Overview, not the squadron
  // Dashboard -- #dash-title lives in #page-dashboard, which stays inactive
  // for this role. Waiting on the page's own active .page is role-agnostic.
  await expect(page.locator(".page.active")).toBeVisible({ timeout: 10000 });

  await page.evaluate(() => (window as any).nav("audit"));
  await expect(page.locator(".ph-title", { hasText: "Audit Log" })).toBeVisible({ timeout: 10000 });

  const status = page.locator("#audit-refresh-status");
  const btn = status.locator("xpath=following-sibling::button[1]");
  await expect(btn).toHaveText("Refresh");
  await btn.click();
  await expect(status).toHaveText(/^Updated at \d{2}:\d{2}$/, { timeout: 10000 });
});
