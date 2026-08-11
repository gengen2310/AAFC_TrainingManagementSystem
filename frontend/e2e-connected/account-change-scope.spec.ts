import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// REM-05: Account Management previously had no way to move an account to a
// different Squadron/Wing -- only role and delete were built. The backend
// POST /api/accounts/{id}/change-scope endpoint and its own extensive test
// suite (backend/tests/test_accounts.py) cover the authority/validation
// logic exhaustively; this suite proves the actual connected-frontend UI
// (the new "Change Scope" button + modal in Account Management) wires up to
// it correctly end to end.

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;
const base = LOCAL_API_BASE || "http://localhost:8000";

test.beforeAll(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");
});

async function loginNational(page: Page) {
  if (LOCAL_API_BASE) {
    await page.addInitScript((b) => { (window as any).AAFC_API_BASE = b; }, LOCAL_API_BASE);
  }
  await page.goto("/");
  await page.locator("#auth-type").selectOption("national");
  await page.locator("#auth-role").selectOption("national_admin");
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill("ADMINNATIONAL");
  await page.locator("#auth-btn").click();
  await expect(page.locator("#app")).toBeVisible({ timeout: 10000 });
}

async function loginSquadron(page: Page, code: string) {
  if (LOCAL_API_BASE) {
    await page.addInitScript((b) => { (window as any).AAFC_API_BASE = b; }, LOCAL_API_BASE);
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

test("national_admin moves a Squadron account via Change Scope -- modal, save, table reflects the new unit", async ({ page }) => {
  await loginNational(page);
  const token = await page.evaluate(() => sessionStorage.getItem("aafc_token"));
  const hdr = { Authorization: `Bearer ${token}` };

  const sqns = await (await page.request.get(`${base}/api/squadrons`, { headers: hdr })).json();
  const sqn703 = sqns.find((s: any) => s.code === "703");
  const sqn704 = sqns.find((s: any) => s.code === "704");
  expect(sqn703 && sqn704, "seed must have both 703 and 704 squadrons").toBeTruthy();

  const suffix = String(Date.now());
  const displayName = `REM-05 Change Scope Test ${suffix}`;
  const createRes = await page.request.post(`${base}/api/accounts`, {
    data: { display_name: displayName, role: "sqn_general", squadron_id: sqn703.squadron_id },
    headers: hdr,
  });
  expect(createRes.ok()).toBe(true);
  const userId = (await createRes.json()).user_id as string;

  try {
    await page.evaluate(() => (window as any).nav("accounts"));
    await page.waitForTimeout(500);

    const row = page.locator("tr", { hasText: displayName });
    await expect(row).toBeVisible({ timeout: 8000 });
    await expect(row).toContainText("SQN 703");

    await row.getByRole("button", { name: "Change Scope" }).click();
    await expect(page.locator("#m-change-scope")).toBeVisible({ timeout: 5000 });
    await expect(page.locator("#cs-current")).toContainText("703");
    await expect(page.locator("#cs-sqn-row")).toBeVisible();
    await expect(page.locator("#cs-wing-row")).toBeHidden();

    await page.locator("#cs-sqn").selectOption({ label: "704" });
    await page.getByRole("button", { name: "Save Changes" }).click();

    await expect(page.locator("#m-change-scope")).toBeHidden({ timeout: 8000 });
    await expect(row).toContainText("SQN 704", { timeout: 8000 });
    await expect(row).not.toContainText("SQN 703");
  } finally {
    await page.request.post(`${base}/api/accounts/${userId}/archive`, { headers: hdr });
  }
});

test("sqn_admin never sees a Change Scope button (no valid destination exists for them)", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");
  await page.evaluate(() => (window as any).nav("accounts"));
  await page.waitForTimeout(500);
  await expect(page.locator("#acct-table")).toBeVisible({ timeout: 8000 });
  await expect(page.getByRole("button", { name: "Change Scope" })).toHaveCount(0);
});
