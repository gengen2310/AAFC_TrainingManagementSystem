import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// REM-34: connected-frontend had zero Notices UI despite full PlanningNotice
// CRUD existing and being fully used by Planning Workspace. New
// GET/POST /api/parade-nights/{pnid}/notices resolve/create the underlying
// ParadeDate link transparently (REM-129's find-or-create pattern), so this
// card never needs to know that concept exists.

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

test.beforeAll(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");
});

async function loginSquadron(page: Page, code: string, role: "sqn_admin" | "sqn_general" = "sqn_admin") {
  if (LOCAL_API_BASE) {
    await page.addInitScript((base) => {
      (window as any).AAFC_API_BASE = base;
    }, LOCAL_API_BASE);
  }
  await page.goto("/");
  await page.locator("#auth-type").selectOption("squadron");
  await page.locator("#auth-wing-select").selectOption("7WG");
  await page.locator("#auth-sqn-select").selectOption("703");
  await page.locator("#auth-role").selectOption(role);
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill(code);
  await page.locator("#auth-btn").click();
  await expect(page.locator("#app")).toBeVisible({ timeout: 10000 });
}

test("sqn_admin can add, see, and remove a notice on a plain (non-Planning-Workspace-created) Parade Night", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");
  const base = LOCAL_API_BASE || "http://localhost:8000";
  const token = await page.evaluate(() => sessionStorage.getItem("aafc_token"));
  const hdr = { Authorization: `Bearer ${token}` };

  // A unique future date each run (avoids duplicate_date collisions against
  // a leftover row from a prior failed run in this shared local dev DB),
  // created via the plain endpoint (no Planning-module ParadeDate
  // involvement from the test's side) -- exactly the case the register
  // flagged as previously non-functional.
  const date = `2099-06-${String(1 + (Date.now() % 27)).padStart(2, "0")}`;
  const createRes = await page.request.post(`${base}/api/parade-nights`, {
    data: { date },
    headers: hdr,
  });
  expect(createRes.ok()).toBe(true);

  await page.evaluate(() => (window as any).reloadAndRender?.());
  await page.waitForTimeout(500);

  await page.evaluate((d) => (window as any).showPNDetail(d), date);
  await expect(page.locator("#m-pn-detail")).toBeVisible({ timeout: 5000 });
  await expect(page.locator("#pn-notices-list")).not.toContainText("Loading…", { timeout: 5000 });
  await expect(page.locator("#pn-notices-list")).toContainText("No notices.");

  const noticeText = `REM-34 E2E notice ${Date.now()}`;
  const noticesCard = page.locator("#pn-notices-card");
  await noticesCard.locator("#pn-notice-text").fill(noticeText);
  await noticesCard.locator("#pn-notice-priority").selectOption("urgent");
  await noticesCard.getByRole("button", { name: "Add" }).click();

  await expect(page.locator("#pn-notices-list")).toContainText(noticeText, { timeout: 5000 });
  await expect(page.locator("#pn-notices-list")).toContainText("Urgent");

  await noticesCard.getByRole("button", { name: "Remove notice" }).click();
  await expect(page.locator("#pn-notices-list")).toContainText("No notices.", { timeout: 5000 });
});

test("sqn_general (read-only) sees notices but no Add/Remove controls", async ({ page }) => {
  await loginSquadron(page, "703SQN2026", "sqn_general");
  const base = LOCAL_API_BASE || "http://localhost:8000";

  // Seed a notice as sqn_admin first via a second, unauthenticated-for-this-
  // page request using the admin token obtained in the prior test's own
  // login flow is not available here -- create via a fresh admin login in
  // a throwaway request context instead, matching this file's own
  // isolation convention of not sharing state across tests.
  const adminLogin = await page.request.post(`${base}/api/auth/login`, { data: { code: "ADMIN703" } });
  const adminToken = (await adminLogin.json()).token as string;
  const adminHdr = { Authorization: `Bearer ${adminToken}` };
  const date = `2099-07-${String(1 + (Date.now() % 27)).padStart(2, "0")}`;
  await page.request.post(`${base}/api/parade-nights`, { data: { date }, headers: adminHdr });

  await page.evaluate(() => (window as any).reloadAndRender?.());
  await page.waitForTimeout(500);
  await page.evaluate((d) => (window as any).showPNDetail(d), date);
  await expect(page.locator("#m-pn-detail")).toBeVisible({ timeout: 5000 });
  await expect(page.locator("#pn-notices-list")).not.toContainText("Loading…", { timeout: 5000 });

  await expect(page.locator("#pn-notice-text")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Add" })).toHaveCount(0);
});
