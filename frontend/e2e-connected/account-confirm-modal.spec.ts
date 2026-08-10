import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// REM-106: Account Management's Disable/Reactivate/Delete/Restore/Unlock
// (and System Console's Archive Wing/Squadron/Disable Maintenance) used
// native confirm() -- which blocks the page entirely under browser
// automation (documented in .claude/rules/frontend.md's "system_admin
// scope" note, requiring test authors to bypass the button and call the
// underlying api(...) directly instead of actually clicking through the
// UI). Replaced with a modal-based confirmAction() helper. This test
// proves the fix precisely: it registers NO page.on("dialog") handler at
// all -- if a native confirm() fired anywhere in this flow, the test
// would hang and time out. Exercises both Cancel (no-op) and Confirm
// (real effect) through the actual UI, not a bypass.

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

test.beforeAll(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");
});

async function loginNational(page: Page) {
  if (LOCAL_API_BASE) {
    await page.addInitScript((base) => {
      (window as any).AAFC_API_BASE = base;
    }, LOCAL_API_BASE);
  }
  await page.goto("/");
  await page.locator("#auth-type").selectOption("national");
  await page.locator("#auth-role").selectOption("national_admin");
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill("ADMINNATIONAL");
  await page.locator("#auth-btn").click();
  await expect(page.locator("#app")).toBeVisible({ timeout: 10000 });
}

test("Disable/Reactivate account: Cancel is a no-op, Confirm acts -- no native dialog ever blocks the flow", async ({ page }) => {
  await loginNational(page);
  const base = LOCAL_API_BASE || "http://localhost:8000";

  // Seed a throwaway squadron-scope account directly via API for a
  // deterministic target -- this test is about the confirm-modal UI
  // mechanics, not account creation itself.
  const token = await page.evaluate(() => sessionStorage.getItem("aafc_token"));
  const hdr = { Authorization: `Bearer ${token}` };
  const wings = await (await page.request.get(`${base}/api/wings`, { headers: hdr })).json();
  const wingId = wings[0]?.wing_id;
  const sqns = await (await page.request.get(`${base}/api/squadrons?wing_id=${wingId}`, { headers: hdr })).json();
  const squadronId = sqns[0]?.squadron_id;

  const suffix = String(Date.now());
  const displayName = `REM-106 Test ${suffix}`;
  const createRes = await page.request.post(`${base}/api/accounts`, {
    data: { display_name: displayName, role: "sqn_general", squadron_id: squadronId },
    headers: hdr,
  });
  expect(createRes.ok()).toBe(true);
  const userId = (await createRes.json()).user_id as string;

  await page.evaluate(() => (window as any).nav("accounts"));
  await page.waitForTimeout(500); // account list render

  const row = page.locator("tr", { hasText: displayName });
  await expect(row).toBeVisible({ timeout: 8000 });

  // Disable, then Cancel in the confirm modal -- account must remain active.
  await row.getByRole("button", { name: "Disable" }).click();
  await expect(page.locator("#m-confirm")).toBeVisible({ timeout: 3000 });
  await expect(page.locator("#confirm-msg")).toContainText(displayName);
  await page.locator("#m-confirm").getByRole("button", { name: "Cancel" }).click();
  await expect(page.locator("#m-confirm")).toBeHidden();
  await expect(row.getByRole("button", { name: "Disable" })).toBeVisible(); // still active

  // Disable, then Confirm -- account becomes inactive (button flips to Reactivate).
  await row.getByRole("button", { name: "Disable" }).click();
  await page.locator("#m-confirm").getByRole("button", { name: "Confirm" }).click();
  await expect(page.locator("#m-confirm")).toBeHidden();
  await expect(row.getByRole("button", { name: "Reactivate" })).toBeVisible({ timeout: 8000 });

  // Reactivate via the same modal.
  await row.getByRole("button", { name: "Reactivate" }).click();
  await page.locator("#m-confirm").getByRole("button", { name: "Confirm" }).click();
  await expect(row.getByRole("button", { name: "Disable" })).toBeVisible({ timeout: 8000 });

  // Cleanup: archive the throwaway account.
  await page.request.post(`${base}/api/accounts/${userId}/archive`, { headers: hdr });
});
