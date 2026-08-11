import { test, expect } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";
import { loginPW } from "../e2e-login-helper";

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

// ── Holiday creation and resource assignment ──────────────────────────────────
// Tests the P5 holiday detection feature and resource assignment in Night Builder.

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await loginPW(page, "ADMIN703");
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
});

test("calendar shows wing calendar tab", async ({ page }) => {
  await page.goto("/calendar");
  await expect(page.getByRole("heading", { name: /calendar/i })).toBeVisible({ timeout: 8000 });
});

test("resources page shows training areas", async ({ page }) => {
  await page.goto("/resources");
  await expect(page.getByRole("heading", { name: /resources/i })).toBeVisible({ timeout: 8000 });
  // 703 has 3 seeded training areas — use .first() to avoid strict-mode violation
  await expect(page.getByText(/Bravo|Major Parade Ground|Seniors Working Room/i).first()).toBeVisible({ timeout: 5000 });
});

test("resources page shows equipment", async ({ page }) => {
  await page.goto("/resources");
  await expect(page.getByRole("heading", { name: /resources/i })).toBeVisible({ timeout: 8000 });
  // 703 has seeded Projector equipment
  await expect(page.getByText(/Projector/i)).toBeVisible({ timeout: 5000 });
});

test("resources page shows all three sections", async ({ page }) => {
  await page.goto("/resources");
  await expect(page.getByRole("heading", { name: /resources/i })).toBeVisible({ timeout: 8000 });
  // All three resource cards must be present — use .first() to avoid strict mode
  // ("Training areas" appears in both the card title div and the table caption)
  await expect(page.getByText("Training areas").first()).toBeVisible();
  await expect(page.getByText("Equipment").first()).toBeVisible();
  await expect(page.getByText("Resource clashes").first()).toBeVisible();
});
