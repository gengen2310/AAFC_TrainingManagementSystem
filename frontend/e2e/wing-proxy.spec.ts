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

// ── Wing proxy workflow ───────────────────────────────────────────────────────
// Requires seeded ADMIN7WG and backend on :8000.

test("wing admin can enter and exit proxy mode", async ({ page }) => {
  await page.goto("/");
  await loginPW(page, "ADMIN7WG");
  // WingOverview renders <h1>Wing Assurance</h1>
  await expect(page.getByRole("heading", { name: /wing assurance/i })).toBeVisible({ timeout: 10000 });
  // Select a squadron and enter proxy. Exact match: Block 8 added a second,
  // legitimate "Viewing squadron" selector (SquadronSelector) to the same nav
  // for read-only squadron browsing without proxy — /squadron/i now matches
  // both, so this must target the proxy-mode select specifically.
  await page.getByLabel("Squadron", { exact: true }).selectOption({ index: 1 });
  await page.getByPlaceholder(/reason/i).fill("Assisting squadron with planning");
  await page.getByRole("button", { name: /enter proxy/i }).click();
  await expect(page.getByText(/proxy mode active/i)).toBeVisible({ timeout: 5000 });
  // Exit proxy
  await page.getByRole("button", { name: /exit proxy/i }).click();
  await expect(page.getByRole("heading", { name: /wing assurance/i })).toBeVisible({ timeout: 5000 });
});

test("wing viewer cannot enter proxy mode", async ({ page }) => {
  await page.goto("/");
  await loginPW(page, "7WG2026");
  // WingOverview renders <h1>Wing Assurance</h1>
  await expect(page.getByRole("heading", { name: /wing assurance/i })).toBeVisible({ timeout: 10000 });
  // Wing viewer sees the proxy entry button but it must be disabled (not clickable)
  await expect(page.getByRole("button", { name: /enter proxy/i })).toBeDisabled();
});
