import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// REM-96/REM-97: the duplicate-facilitator 409 warning must show enough of
// the existing facilitator's profile (rank, type, subject areas, status,
// last-updated) that a user can tell "same person, re-added by accident"
// from "different person, same name" without leaving the Add Facilitator
// modal. REM-96 specifically asked for rank to appear in the warning text
// itself; REM-97 asked for the fuller profile card.

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

test("adding a same-named facilitator shows the existing one's rank, type and subject areas inline", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");

  const suffix = String(Date.now());
  const last = `Dup${suffix}`;

  // Seed the "existing" facilitator directly via API for a deterministic profile.
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

  const warn = page.locator("#fac-dup-warn");
  await expect(warn).toBeVisible({ timeout: 8000 });
  await expect(warn).toContainText("CUO"); // REM-96: rank in the warning text itself
  await expect(warn).toContainText("Senior Cadet"); // REM-97: profile card
  await expect(warn).toContainText("Drill");
  await expect(warn).toContainText("Active");

  await page.locator("#fac-save-anyway-btn").click();
  await expect(page.locator("#m-add-fac")).toBeHidden({ timeout: 8000 });

  // Cleanup both facilitators created by this test. Best-effort: a transient
  // hiccup on this GET must never fail the test after the real assertions
  // above have already passed -- this is tidy-up, not verification.
  try {
    await page.request.delete(`${base}/api/facilitators/${existingId}`, { headers: hdr });
    const facsRes = await page.request.get(`${base}/api/facilitators`, { headers: hdr });
    const facs = await facsRes.json();
    if (Array.isArray(facs)) {
      const created = facs.find((f: { first_name?: string; last_name?: string }) => f.last_name === last);
      if (created) await page.request.delete(`${base}/api/facilitators/${created.facilitator_id}`, { headers: hdr });
    }
  } catch {
    // best-effort cleanup only
  }
});
