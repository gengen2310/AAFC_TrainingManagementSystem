/**
 * Planning Workspace accessibility qualification.
 *
 * The React frontend is a specialised /planning module, not the legacy full
 * TMS. Axe therefore audits the states this module actually owns: unauthenticated
 * handoff guidance, squadron planning, read-only planning, higher-scope context
 * selection, and the help drawer. Main-TMS route accessibility is covered by
 * the connected-frontend browser suite.
 */

import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";
import { loginPW } from "../e2e-login-helper";

const BACKEND = process.env.E2E_BACKEND_BASE_URL || "http://localhost:8000";

test.beforeAll(async () => {
  await resetBackendRateLimits(BACKEND);
});

function assertNoViolations(violations: Array<{ impact?: string | null; id?: string; description?: string }>) {
  const blocking = violations.filter(
    v => v.impact === "critical" || v.impact === "serious" || v.impact === "moderate",
  );
  if (blocking.length) {
    const summary = blocking
      .map(v => `[${v.impact}] ${v.id}: ${v.description}`)
      .join("\n");
    throw new Error(`Accessibility violations (critical/serious/moderate):\n${summary}`);
  }
}

async function audit(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  assertNoViolations(results.violations);
}

test("unauthenticated module handoff state has no blocking WCAG 2.1 AA violations", async ({ page }) => {
  await page.goto("/planning");
  await expect(page.getByRole("heading", { name: "Session not found" })).toBeVisible();
  await audit(page);
});

test("squadron-admin planning workspace has no blocking WCAG 2.1 AA violations", async ({ page }) => {
  await loginPW(page, "ADMIN703");
  await expect(page.getByRole("main", { name: /planning workspace/i })).toBeVisible();
  await audit(page);
});

test("read-only squadron planning workspace has no blocking WCAG 2.1 AA violations", async ({ page }) => {
  await loginPW(page, "703SQN2026");
  await expect(page.getByRole("main", { name: /planning workspace/i })).toBeVisible();
  await audit(page);
});

test("higher-scope squadron-selection state has no blocking WCAG 2.1 AA violations", async ({ page }) => {
  await loginPW(page, "ADMIN7WG");
  const selector = page.getByLabel("Viewing squadron");
  await expect(selector).toBeVisible();
  await expect(page.getByText(/select a squadron above to view its Planning Workspace/i)).toBeVisible();
  await audit(page);
});

test("higher-scope selected-squadron workspace has no blocking WCAG 2.1 AA violations", async ({ page }) => {
  await loginPW(page, "ADMIN7WG");
  const selector = page.getByLabel("Viewing squadron");
  // wingOverview fetch is async — wait for at least one real option (non-empty value)
  // before evaluating, same pattern as auth.spec.ts wing/national squadron-picker test.
  await expect.poll(
    () => selector.locator("option:not([value=''])").count(),
    { timeout: 15000, message: "squadron selector options did not load" },
  ).toBeGreaterThan(0);
  const values = await selector.locator("option").evaluateAll(options =>
    options.map(o => (o as HTMLOptionElement).value).filter(Boolean),
  );
  expect(values.length).toBeGreaterThan(0);
  await selector.selectOption(values[0]);
  // Selector unmounts after selection; verify empty-state is gone instead of
  // checking the now-detached element's value.
  await expect(page.getByText(/select a squadron above to view its Planning Workspace/i)).toHaveCount(0, { timeout: 10000 });
  await audit(page);
});

test("help drawer has no blocking WCAG 2.1 AA violations", async ({ page }) => {
  await loginPW(page, "ADMIN703");
  await page.getByRole("button", { name: "Open help panel" }).click();
  // Help content is intentionally discovered by the control rather than a
  // brittle heading string; the open state must be rendered before axe runs.
  await expect(page.getByRole("button", { name: /close/i }).first()).toBeVisible({ timeout: 5000 });
  await audit(page);
});
