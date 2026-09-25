import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// REM-96/REM-97: duplicate-facilitator detection must show enough of the
// existing facilitator's profile (rank, type, subject areas, status,
// last-updated) that a user can distinguish "same person, re-added by
// accident" from "different person, same name" before deciding what to do.
// The current workflow presents this in the dedicated "Possible Match" modal.

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

test("adding a same-named facilitator shows the existing one's rank, type and subject areas in the Possible Match workflow", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");

  const suffix = String(Date.now());
  const last = `Dup${suffix}`;
  const hdr = { Authorization: `Bearer ${await page.evaluate(() => sessionStorage.getItem("aafc_token"))}` };
  const base = LOCAL_API_BASE || "http://localhost:8000";

  const seedRes = await page.request.post(`${base}/api/facilitators`, {
    data: { first_name: "Alex", last_name: last, current_rank: "CUO", type: "Senior Cadet", subject_areas: ["Drill"] },
    headers: hdr,
  });
  expect(seedRes.ok()).toBe(true);
  const existingId = (await seedRes.json()).facilitator_id as string;

  await page.evaluate(() => (window as any).nav("facilitators"));
  await page.locator("button.btn.btn-dk.admin-el").filter({ hasText: "+ Add Facilitator" }).click();
  await expect(page.locator("#m-add-fac")).toBeVisible();
  await page.locator("#fac-first").fill("Alex");
  await page.locator("#fac-last").fill(last);
  await page.locator("#fac-rank").fill("CSGT");
  await page.locator("#fac-save-btn").click();

  // Duplicate detection now closes the Add modal and opens a dedicated
  // decision surface. Assert the information a user actually sees rather than
  // the retired inline #fac-dup-warn container.
  const match = page.getByRole("dialog", { name: "Possible Match" });
  await expect(match).toBeVisible({ timeout: 8000 });
  await expect(match).toContainText("CUO");
  await expect(match).toContainText("Senior Cadet");
  await expect(match).toContainText("Drill");
  await expect(match).toContainText("Active");
  await expect(match.getByRole("button", { name: "Use Existing Facilitator" })).toBeVisible();
  await expect(match.getByRole("button", { name: "Create a Different Person" })).toBeVisible();
  await expect(match.getByRole("button", { name: "Merge Records" })).toBeVisible();

  // Cancel leaves the existing profile untouched; no second duplicate record
  // is needed to verify REM-96/97.
  await match.getByRole("button", { name: "Cancel" }).click();
  await expect(match).toBeHidden({ timeout: 5000 });

  await page.request.delete(`${base}/api/facilitators/${existingId}`, { headers: hdr });
});
