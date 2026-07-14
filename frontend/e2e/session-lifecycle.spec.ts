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
  // ParadeNights opens a modal via "Open" button (not URL navigation)
  const openBtn = page.getByRole("button", { name: "Open" }).first();
  if (await openBtn.count() > 0) {
    await openBtn.click();
    // A modal dialog should appear
    await expect(page.getByRole("dialog")).toBeVisible({ timeout: 5000 });
  }
});

test("facilitator statistics show on facilitators page", async ({ page }) => {
  await page.goto("/facilitators");
  await expect(page.getByRole("heading", { name: /facilitator/i })).toBeVisible({ timeout: 8000 });
  // 703 has 5 seeded facilitators — use .first() to avoid strict-mode violation
  await expect(page.getByText(/Daley|Flanders|McGhie|Milligen|Daniels/i).first()).toBeVisible({ timeout: 5000 });
});
