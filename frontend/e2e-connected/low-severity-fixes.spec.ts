import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// Low-severity UI/UX fixes from the ADDENDUM UI/UX audit (2026-08-06):
// REM-92 (Weekly Program empty state) and REM-91 (System Console build
// fingerprint fallback for the unresolved local-dev placeholder).

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

test("REM-92: Weekly Program shows guidance instead of a bare blank area before a parade night is chosen", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");
  await page.evaluate(() => (window as any).nav("weekly-program"));
  // Squadron 703 has seeded parade nights, so this exercises the "choose one"
  // branch specifically (the "no parade nights exist yet" branch is a
  // simple, low-risk conditional on the same data already used elsewhere on
  // this page -- verified via code review, not separately seeded here).
  await expect(page.locator("#wp-content")).toContainText(/choose a parade night/i, { timeout: 8000 });
});

test("REM-91: System Console shows a friendly build label, not the literal unresolved placeholder", async ({ page }) => {
  if (LOCAL_API_BASE) {
    await page.addInitScript((base) => {
      (window as any).AAFC_API_BASE = base;
    }, LOCAL_API_BASE);
  }
  await page.goto("/");
  await page.locator("#auth-type").selectOption("national");
  await page.locator("#auth-role").selectOption("system_admin");
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill("SYSADMIN2026");
  await page.locator("#auth-btn").click();
  await expect(page.locator("#app")).toBeVisible({ timeout: 10000 });
  await page.evaluate(() => (window as any).nav("system-console"));
  const commitEl = page.locator("#sc-build-commit");
  await expect(commitEl).toBeVisible({ timeout: 8000 });
  await expect(commitEl).not.toContainText("__APP_BUILD__");
  await expect(commitEl).toContainText("(local build)");
});

test("WRITE-06: facilitator name fields use Defence Writing Manual's Given/Family name labelling", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");
  await page.evaluate(() => (window as any).nav("facilitators"));
  await expect(page.locator("#fac-tbody tr").first()).toBeVisible();
  // Table header labels.
  await expect(page.locator("thead").getByRole("columnheader", { name: "Given Name" })).toBeVisible();
  await expect(page.locator("thead").getByRole("columnheader", { name: "Family Name" })).toBeVisible();
  // Add Facilitator modal labels.
  await page.locator("button.btn.btn-dk.admin-el").filter({ hasText: "+ Add Facilitator" }).click();
  await expect(page.locator("#m-add-fac")).toBeVisible();
  await expect(page.locator("#m-add-fac")).toContainText("Given Name");
  await expect(page.locator("#m-add-fac")).toContainText("Family Name");
  await expect(page.locator("#m-add-fac")).not.toContainText("First Name");
  await expect(page.locator("#m-add-fac")).not.toContainText("Last Name");
});

test("WRITE-03: 'Saved at' timestamps use 24-hour time, not 12-hour am/pm", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");
  await page.evaluate(() => (window as any).nav("facilitators"));
  await expect(page.locator("#fac-tbody tr").first()).toBeVisible();
  await page.locator("button.btn.btn-dk.admin-el").filter({ hasText: "+ Add Facilitator" }).click();
  await expect(page.locator("#m-add-fac")).toBeVisible();
  const suffix = String(Date.now());
  await page.locator("#fac-first").fill(`WRITE03-${suffix}`);
  await page.locator("#fac-last").fill(`Time-${suffix}`);
  await page.locator("#fac-save-btn").click();
  await expect(page.locator("#m-add-fac")).toBeHidden({ timeout: 8000 });
  // #fac-save-state was set to "Saved at HH:MM" just before the modal closed --
  // read it from the toast instead, which carries the same "Facilitator added
  // at HH:MM." text and survives after the modal itself is gone.
  const toast = page.locator(".toast-region");
  await expect(toast).toContainText(/added at \d{2}:\d{2}\./i, { timeout: 5000 });
  await expect(toast).not.toContainText(/am\.|pm\./i);

  // Cleanup.
  const facs = await page.evaluate(async () => {
    const r = await (window as any).api("/api/facilitators");
    return r;
  });
  const created = facs.find((f: { last_name?: string }) => f.last_name === `Time-${suffix}`);
  if (created) {
    await page.request.delete(`${LOCAL_API_BASE || "http://localhost:8000"}/api/facilitators/${created.facilitator_id}`, {
      headers: { Authorization: `Bearer ${await page.evaluate(() => sessionStorage.getItem("aafc_token"))}` },
    });
  }
});
