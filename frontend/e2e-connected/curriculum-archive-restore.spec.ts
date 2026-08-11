import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// REM-133: Curriculum-item archive existed with no restore counterpart, and
// archived items were entirely invisible (no include_archived param, no way
// to even see one to restore it). Added a "Show archived" toggle (matching
// the existing Facilitator/Flight/Wing pattern) plus a Restore button.

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

// beforeEach, not beforeAll: each test here makes several setup api() calls
// and the general rate limiter is per-process, not per-test.
test.beforeEach(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");
});

async function loginSquadron(page: Page, code: string, role = "sqn_admin") {
  if (LOCAL_API_BASE) {
    await page.addInitScript((base) => { (window as any).AAFC_API_BASE = base; }, LOCAL_API_BASE);
  }
  await page.goto("/");
  await page.locator("#auth-type").selectOption("squadron");
  await page.locator("#auth-wing-select").selectOption("7WG");
  await page.locator("#auth-sqn-select").selectOption("703");
  await page.locator("#auth-role").selectOption(role);
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill(code);
  await page.locator("#auth-btn").click();
  await expect(page.locator(".ph-title", { hasText: "Training Dashboard" })).toBeVisible({ timeout: 10000 });
}

test("an archived curriculum item is hidden by default, visible via Show archived, and Restore brings it back", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");
  const base = LOCAL_API_BASE || "http://localhost:8000";
  const token = await page.evaluate(() => sessionStorage.getItem("aafc_token"));
  const hdr = { Authorization: `Bearer ${token}` };

  const title = `E2E REM-133 Curriculum ${Date.now()}`;
  const code = `E2EREM133-${Date.now()}`;
  const createRes = await page.request.post(`${base}/api/curriculum`, {
    data: { code, title, phase: "A. Orientation", duration_minutes: 60 },
    headers: hdr,
  });
  expect(createRes.ok()).toBe(true);
  const curriculumId = (await createRes.json()).curriculum_id as string;
  const archiveRes = await page.request.delete(`${base}/api/curriculum/${curriculumId}`, { headers: hdr });
  expect(archiveRes.ok()).toBe(true);

  await page.evaluate(() => (window as any).nav("curriculum"));
  await page.waitForTimeout(500);

  // Hidden by default.
  await expect(page.locator("#curr-list")).not.toContainText(title);

  // Visible with "Show archived" checked, flagged as archived.
  await page.locator("#curr-show-archived").check();
  const row = page.locator("#curr-list tr", { hasText: title });
  await expect(row).toBeVisible({ timeout: 5000 });
  await expect(row).toContainText("Archived");

  // Restore brings it back into the default (unchecked) view.
  await row.getByRole("button", { name: "Restore" }).click();
  await page.locator("#curr-show-archived").uncheck();
  await expect(page.locator("#curr-list", { hasText: title })).toBeVisible({ timeout: 5000 });

  // Cleanup.
  await page.request.delete(`${base}/api/curriculum/${curriculumId}`, { headers: hdr });
});

test("sqn_general (read-only) sees no Show archived control on Curriculum", async ({ page }) => {
  // A fresh login as sqn_general directly -- no need to also sign in as
  // sqn_admin first in this test (each Playwright test already gets its own
  // page/session; that flow is covered by the test above).
  await loginSquadron(page, "703SQN2026", "sqn_general");

  await page.evaluate(() => (window as any).nav("curriculum"));
  // sqn_general has no admin-el controls at all -- the "Show archived"
  // checkbox itself is admin-only, matching every other archive/restore
  // control in this codebase.
  await expect(page.locator("#curr-show-archived")).toBeHidden();
});
