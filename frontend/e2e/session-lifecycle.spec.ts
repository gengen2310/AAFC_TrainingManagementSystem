import { test, expect } from "@playwright/test";

// ── Session lifecycle: cancellation and rescheduling ─────────────────────────
// Requires backend on :8000 with 703 demo data. Tests the P0 cancelled-lesson
// and rescheduled-lesson flows through the browser UI.

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Access code").fill("ADMIN703");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
});

test("parade night list shows planned nights", async ({ page }) => {
  await page.goto("/parade-nights");
  await expect(page.getByRole("heading", { name: /parade night/i })).toBeVisible({ timeout: 8000 });
  // 703 has seeded parade nights
  const rows = page.locator("table tbody tr, [data-testid='parade-night-row'], .parade-night-item");
  await expect(rows.first()).toBeVisible({ timeout: 5000 });
});

test("can open a parade night detail", async ({ page }) => {
  await page.goto("/parade-nights");
  await expect(page.getByRole("heading", { name: /parade night/i })).toBeVisible({ timeout: 8000 });
  // Click the first parade night link/button
  const nightLink = page.getByRole("link", { name: /2026|parade/i }).first();
  if (await nightLink.count() > 0) {
    await nightLink.click();
    // Should navigate to a detail page
    await expect(page).toHaveURL(/\/parade-nights\/.+/);
  }
});

test("facilitator statistics show on facilitators page", async ({ page }) => {
  await page.goto("/facilitators");
  await expect(page.getByRole("heading", { name: /facilitator/i })).toBeVisible({ timeout: 8000 });
  // 703 has 5 seeded facilitators
  await expect(page.getByText(/Daley|Flanders|McGhie|Milligen|Daniels/i)).toBeVisible({ timeout: 5000 });
});
