import { test, expect } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// Wing/National Command Dashboard (Sections A/B) -- previously had zero
// Planning Workspace consumer at all (GET /api/dashboard/command). Now
// rendered on WingOverview/NationalOverview via the shared
// CommandDashboardSection component.
test.beforeAll(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || "http://localhost:8000");
});

test("wing_admin sees the Command Dashboard on Wing Assurance", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Access code").fill("ADMIN7WG");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.getByRole("heading", { name: /wing assurance/i })).toBeVisible({ timeout: 10000 });
  await expect(page.getByText(/Command Dashboard/i)).toBeVisible({ timeout: 10000 });
  await expect(page.getByText("A1 — Next parade night readiness")).toBeVisible();
  await expect(page.getByText("A2 — Eight-week risk forecast")).toBeVisible();
  await expect(page.getByText("B1 — Training delivered each week")).toBeVisible();
});

test("national_admin sees the Command Dashboard on National Assurance", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Access code").fill("ADMINNATIONAL");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.getByRole("heading", { name: /national assurance/i })).toBeVisible({ timeout: 10000 });
  await expect(page.getByText(/Command Dashboard/i)).toBeVisible({ timeout: 10000 });
  await expect(page.getByText("A3 — Immediate issues requiring support")).toBeVisible();
  await expect(page.getByText("B4 — Cancellation and non-delivery causes")).toBeVisible();
});

test("Purpose, measure & action info toggle expands chart narrative", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Access code").fill("ADMIN7WG");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.getByText(/Command Dashboard/i)).toBeVisible({ timeout: 10000 });
  const toggle = page.getByRole("button", { name: "Purpose, measure & action" }).first();
  await toggle.click();
  await expect(page.getByText("Purpose").first()).toBeVisible();
  await expect(page.getByText("Measure").first()).toBeVisible();
});
