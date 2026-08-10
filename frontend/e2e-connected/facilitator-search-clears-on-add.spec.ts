import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// REM-99 regression: a newly-created facilitator could appear "not visible"
// (matching the reported symptom, fixed only by a hard refresh) when the
// #fac-search box still held leftover text from a moment ago -- e.g. a user
// searching for a name to check for an existing duplicate before adding a
// new, differently-named facilitator. renderFacs() applies that search text
// unconditionally, silently filtering the just-created row out of the
// re-rendered list. A hard refresh "fixes" it only because it resets the
// input back to empty -- the real fix is to clear #fac-search on a
// successful create, so the new row is guaranteed visible without the user
// having to remember their own leftover search text.

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

test("a facilitator created while an unrelated search term is still in #fac-search is immediately visible", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");
  await page.evaluate(() => (window as any).nav("facilitators"));
  await expect(page.locator("#fac-tbody tr").first()).toBeVisible();

  const suffix = String(Date.now());
  const first = `E2E-REM99-${suffix}`;
  const last = `Regression-${suffix}`;

  // Simulate the real-world trigger: type a search term for something
  // unrelated (checking for a duplicate of a completely different name)
  // before opening Add Facilitator -- this must not survive a successful add.
  await page.locator("#fac-search").fill("ZZZ_no_such_facilitator_ZZZ");
  await expect(page.locator("#fac-tbody")).toContainText("No facilitators");

  await page.locator("button.btn.btn-dk.admin-el").filter({ hasText: "+ Add Facilitator" }).click();
  await expect(page.locator("#m-add-fac")).toBeVisible();
  await page.locator("#fac-first").fill(first);
  await page.locator("#fac-last").fill(last);
  await page.locator("#fac-rank").fill("CPL(AAFC)");
  await page.locator("#fac-save-btn").click();

  await expect(page.locator("#m-add-fac")).toBeHidden({ timeout: 8000 });
  // The old search term must be gone, and the new facilitator visible
  // without the user having to clear it themselves.
  await expect(page.locator("#fac-search")).toHaveValue("");
  await expect(page.locator("#fac-tbody")).toContainText(first);
  await expect(page.locator("#fac-tbody")).toContainText(last);

  // Cleanup: archive the row we just created (confirm() dialog auto-accepted).
  page.on("dialog", (d) => d.accept());
  const row = page.locator("#fac-tbody tr", { hasText: last });
  await row.getByRole("button", { name: "×" }).click();
});
