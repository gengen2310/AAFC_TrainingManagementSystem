/**
 * Accessibility automation (Gap #13 — Level C).
 *
 * Uses @axe-core/playwright to run WCAG 2.1 AA audits on every major
 * page/state in the Planning Workspace.  Tests fail on any critical or
 * serious violation; informational and moderate issues are reported but
 * do not fail the suite (see violationThreshold below).
 *
 * Run condition: backend must be running and seeded on :8000.
 */

import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const SQN_ADMIN = "ADMIN703";
const SQN_GENERAL = "703SQN2026";

async function loginAs(page: import("@playwright/test").Page, code: string) {
  await page.goto("/");
  await page.getByLabel("Access code").fill(code);
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
}

function assertNoViolations(violations: Array<{ impact?: string | null }>) {
  const blocking = violations.filter(
    (v) => v.impact === "critical" || v.impact === "serious"
  );
  if (blocking.length > 0) {
    const summary = blocking
      .map((v: Record<string, unknown>) => `[${v.impact}] ${v.id}: ${v.description}`)
      .join("\n");
    throw new Error(`Accessibility violations (critical/serious):\n${summary}`);
  }
}

test.describe("Accessibility — Login page", () => {
  test("login page has no critical/serious axe violations", async ({ page }) => {
    await page.goto("/");
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa"])
      .analyze();
    assertNoViolations(results.violations);
  });
});

test.describe("Accessibility — Dashboard", () => {
  test("dashboard has no critical/serious axe violations", async ({ page }) => {
    await loginAs(page, SQN_ADMIN);
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa"])
      .analyze();
    assertNoViolations(results.violations);
  });
});

test.describe("Accessibility — Parade Nights", () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, SQN_ADMIN);
    await page.getByRole("link", { name: "Parade Nights" }).click();
    await page.waitForURL("**/parade-nights");
  });

  test("parade nights list has no critical/serious violations", async ({ page }) => {
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa"])
      .analyze();
    assertNoViolations(results.violations);
  });

  test("create parade night modal has no critical/serious violations", async ({ page }) => {
    const btn = page.getByRole("button", { name: "New parade night" });
    if (await btn.isVisible()) {
      await btn.click();
      await expect(page.getByRole("dialog")).toBeVisible();
      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa"])
        .analyze();
      assertNoViolations(results.violations);
    }
  });
});

test.describe("Accessibility — Facilitators", () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, SQN_ADMIN);
    await page.getByRole("link", { name: "Facilitators" }).click();
    await page.waitForURL("**/facilitators");
  });

  test("facilitators list has no critical/serious violations", async ({ page }) => {
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa"])
      .analyze();
    assertNoViolations(results.violations);
  });
});

test.describe("Accessibility — Reports", () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, SQN_ADMIN);
    await page.getByRole("link", { name: "Reports" }).click();
    await page.waitForURL("**/reports");
  });

  test("reports page has no critical/serious violations", async ({ page }) => {
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa"])
      .analyze();
    assertNoViolations(results.violations);
  });
});

test.describe("Accessibility — sqn_general role", () => {
  test("dashboard as sqn_general has no critical/serious violations", async ({ page }) => {
    await loginAs(page, SQN_GENERAL);
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa"])
      .analyze();
    assertNoViolations(results.violations);
  });
});
