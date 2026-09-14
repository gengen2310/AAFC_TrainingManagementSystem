import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// REM-103: a squadron admin can locally adjust the date/time/notes of an
// inherited Wing/National activity, or mark it "not relevant to our
// squadron" -- without altering the source record other units see. Seeds
// the wing-owned activity via the real "+ New Wing Activity" UI (same
// pattern activities-inheritance.spec.ts uses), then drives the actual
// squadron-side "Adjust" modal through the rendered page.

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

test.beforeEach(async () => {
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
}

async function signOutIfLoggedIn(page: Page) {
  const signOut = page.locator(".tb-btn", { hasText: "Sign Out" });
  if (await signOut.isVisible().catch(() => false)) {
    await signOut.click();
    await expect(page.locator("#auth-type")).toBeVisible({ timeout: 10000 });
  }
}

async function loginSquadron(page: Page, code: string, role: "sqn_admin" | "sqn_general" = "sqn_admin") {
  await signOutIfLoggedIn(page);
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

test("Squadron admin can adjust, see, and clear a local override on an inherited Wing activity", async ({ page }) => {
  const uniqueName = "E2E REM-103 Wing Activity " + Date.now();

  await loginWing(page, "ADMIN7WG");
  await page.evaluate(() => (window as any).nav("wing-activities"));
  await expect(page.locator("#act-tab-wing .ctitle", { hasText: "Activities" })).toBeVisible({ timeout: 10000 });
  await page.locator("#act-tab-wing button", { hasText: "+ New Wing Activity" }).click();
  await page.locator("#act-tab-wing-c-name").fill(uniqueName);
  await page.locator("#act-tab-wing-c-start").fill("2026-11-10");
  await page.locator("#act-tab-wing-detail button", { hasText: "Create" }).click();
  await expect(page.locator("#act-tab-wing").getByText(uniqueName)).toBeVisible({ timeout: 10000 });

  await loginSquadron(page, "ADMIN703");
  await page.evaluate(() => (window as any).nav("activities"));
  const row = page.locator("#act-tbody tr", { hasText: uniqueName });
  await expect(row).toBeVisible({ timeout: 10000 });
  await expect(row.getByRole("button", { name: "Adjust" })).toBeVisible();
  await expect(row.getByRole("button", { name: "Edit" })).toHaveCount(0);

  await row.getByRole("button", { name: "Adjust" }).click();
  await expect(page.locator("#m-act-override")).toHaveClass(/active/);
  await expect(page.locator("#act-override-source")).toContainText("Source");

  await page.locator("#act-ov-date-start").fill("2026-11-12");
  await page.locator("#act-ov-notes").fill("Bring wet-weather gear");
  await page.locator("#m-act-override button", { hasText: "Save" }).click();
  await expect(page.locator("#m-act-override")).toBeHidden({ timeout: 10000 });

  const adjustedRow = page.locator("#act-tbody tr", { hasText: uniqueName });
  await expect(adjustedRow).toContainText("Adjusted");
  await expect(adjustedRow).toContainText("adjusted");
  await expect(adjustedRow.getByRole("button", { name: "Edit Adjustment" })).toBeVisible();

  // Clear uses the application's accessible confirmation modal, not a native
  // browser confirm(). Exercise the real confirmation workflow.
  await adjustedRow.getByRole("button", { name: "Edit Adjustment" }).click();
  await expect(page.locator("#act-override-clear-btn")).toBeVisible();
  await page.locator("#act-override-clear-btn").click();
  await expect(page.locator("#m-confirm")).toBeVisible({ timeout: 5000 });
  await page.locator("#confirm-yes-btn").click();
  await expect(page.locator("#m-confirm")).toBeHidden({ timeout: 5000 });
  await expect(page.locator("#m-act-override")).toBeHidden({ timeout: 10000 });

  const revertedRow = page.locator("#act-tbody tr", { hasText: uniqueName });
  await expect(revertedRow).toBeVisible({ timeout: 10000 });
  await expect(revertedRow).not.toContainText("Adjusted");
  await expect(revertedRow.getByRole("button", { name: "Adjust" })).toBeVisible();
});

test("Squadron viewer (read-only role) sees a locally adjusted activity but cannot open the Adjust modal", async ({ page }) => {
  const uniqueName = "E2E REM-103 Viewer Wing Activity " + Date.now();

  await loginWing(page, "ADMIN7WG");
  await page.evaluate(() => (window as any).nav("wing-activities"));
  await page.locator("#act-tab-wing button", { hasText: "+ New Wing Activity" }).click();
  await page.locator("#act-tab-wing-c-name").fill(uniqueName);
  await page.locator("#act-tab-wing-c-start").fill("2026-11-15");
  await page.locator("#act-tab-wing-detail button", { hasText: "Create" }).click();
  await expect(page.locator("#act-tab-wing").getByText(uniqueName)).toBeVisible({ timeout: 10000 });

  await loginSquadron(page, "703SQN2026", "sqn_general");
  await page.evaluate(() => (window as any).nav("activities"));
  const row = page.locator("#act-tbody tr", { hasText: uniqueName });
  await expect(row).toBeVisible({ timeout: 10000 });
  await expect(row.getByRole("button", { name: "Adjust" })).toHaveCount(0);
  await expect(row.getByRole("button", { name: "Edit Adjustment" })).toHaveCount(0);
});
