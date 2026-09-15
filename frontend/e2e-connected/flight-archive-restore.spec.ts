import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// Product contract: local Squadron Flights / sub-squadron groupings were
// retired from the Main TMS UI. This regression test replaces the obsolete
// REM-108 archive/restore workflow, which attempted to call the shared
// Reference Data manager with an unsupported "flight" dataset and therefore
// exercised hidden legacy markup rather than a reachable user workflow.

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

test("retired local Squadron Flights are not exposed in Account Management configuration", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");
  await page.evaluate(() => (window as any).nav("accounts"));
  await page.getByRole("tab", { name: "Configuration" }).click();

  const configuration = page.getByRole("tabpanel", { name: "Configuration" });
  await expect(configuration).toBeVisible({ timeout: 5000 });

  // Current configuration contract is the six governed datasets. Flights are
  // intentionally not one of them and must not be resurrected by stale UI.
  await expect(configuration.getByRole("button", { name: /Manage Training Stages/i })).toBeVisible();
  await expect(configuration.getByRole("button", { name: /Manage Subject Areas/i })).toBeVisible();
  await expect(configuration.getByRole("button", { name: /Manage Session Status Reasons/i })).toBeVisible();
  await expect(configuration.getByRole("button", { name: /Manage Activity Types/i })).toBeVisible();
  await expect(configuration.getByRole("button", { name: /Manage Facilitator Types/i })).toBeVisible();
  await expect(configuration.getByRole("button", { name: /Manage Training Area Capabilities/i })).toBeVisible();

  await expect(configuration.getByText(/Local Squadron Flights/i)).toHaveCount(0);
  await expect(configuration.getByText(/sub-squadron groupings/i)).toHaveCount(0);
  await expect(configuration.getByRole("button", { name: /Manage Flights/i })).toHaveCount(0);
  await expect(configuration.getByText(/Organise Cadets into Flights/i)).toHaveCount(0);
});
