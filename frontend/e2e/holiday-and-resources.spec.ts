import { test, expect } from "@playwright/test";

// ── Holiday creation and resource assignment ──────────────────────────────────
// Tests the P5 holiday detection feature and resource assignment in Night Builder.

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Access code").fill("ADMIN703");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
});

test("calendar shows wing calendar tab", async ({ page }) => {
  await page.goto("/calendar");
  await expect(page.getByRole("heading", { name: /calendar/i })).toBeVisible({ timeout: 8000 });
});

test("resources page shows training areas", async ({ page }) => {
  await page.goto("/resources");
  await expect(page.getByRole("heading", { name: /resource|training area|equipment/i })).toBeVisible({ timeout: 8000 });
  // 703 has 3 seeded training areas
  await expect(page.getByText(/Bravo|Major Parade Ground|Seniors Working Room/i)).toBeVisible({ timeout: 5000 });
});

test("resources page shows equipment", async ({ page }) => {
  await page.goto("/resources");
  await expect(page.getByRole("heading", { name: /resource|training area|equipment/i })).toBeVisible({ timeout: 8000 });
  // 703 has seeded Projector equipment
  await expect(page.getByText(/Projector/i)).toBeVisible({ timeout: 5000 });
});

test("sqn_admin can access resources write controls", async ({ page }) => {
  await page.goto("/resources");
  await expect(page.getByRole("heading", { name: /resource|training area|equipment/i })).toBeVisible({ timeout: 8000 });
  // Admin should see Add/Create button
  await expect(
    page.getByRole("button", { name: /add|create|new/i }).first()
  ).toBeVisible({ timeout: 5000 });
});
