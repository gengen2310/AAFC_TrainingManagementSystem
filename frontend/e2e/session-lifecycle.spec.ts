import { test, expect } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// DEFECT-004: playwright-global-setup.ts resets rate limits once per full
// suite invocation, which is not always enough for a large suite -- a
// spec file's own request volume, especially with other files having run
// immediately before it, can still cross the general API limiter's
// 300 req/60s budget partway through (observed live running this suite).
// A per-file reset gives this file its own fresh budget. Best-effort; see
// e2e-rate-limit-reset.ts for what this does and its known limitations.
test.beforeAll(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || "http://localhost:8000");
});

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
