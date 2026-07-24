/**
 * Accessibility automation (Gap #13 — Level C).
 *
 * Uses @axe-core/playwright to run WCAG 2.1 AA audits on every major
 * page/state in the app. Tests fail on any critical, serious, or moderate
 * violation; only informational-impact issues are reported without failing
 * the suite (see assertNoViolations below).
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
    (v) => v.impact === "critical" || v.impact === "serious" || v.impact === "moderate"
  );
  if (blocking.length > 0) {
    const summary = blocking
      .map((v: Record<string, unknown>) => `[${v.impact}] ${v.id}: ${v.description}`)
      .join("\n");
    throw new Error(`Accessibility violations (critical/serious/moderate):\n${summary}`);
  }
}

async function auditRoute(page: import("@playwright/test").Page, linkName: string, urlPart: string) {
  await page.getByRole("link", { name: linkName, exact: true }).click();
  await page.waitForURL(`**${urlPart}`);
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  assertNoViolations(results.violations);
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

// ── Widened coverage (Phase 7) ────────────────────────────────────────────
// Previously only Login, Dashboard, Parade Nights, Facilitators, and Reports
// were audited. These routes exist in App.tsx's full route table and are
// reachable via the sidenav for sqn_admin (isAdmin(session) === true, so
// Accounts/Admin/Imports are all visible — see roleGuards.ts).

test.describe("Accessibility — Calendar", () => {
  test("calendar has no critical/serious/moderate violations", async ({ page }) => {
    await loginAs(page, SQN_ADMIN);
    await auditRoute(page, "Calendar", "/calendar");
  });
});

test.describe("Accessibility — Curriculum", () => {
  test("curriculum has no critical/serious/moderate violations", async ({ page }) => {
    await loginAs(page, SQN_ADMIN);
    await auditRoute(page, "Curriculum", "/curriculum");
  });
});

test.describe("Accessibility — Weekly Program", () => {
  test("weekly program has no critical/serious/moderate violations", async ({ page }) => {
    await loginAs(page, SQN_ADMIN);
    await auditRoute(page, "Weekly Program", "/weekly-program");
  });
});

test.describe("Accessibility — Resources", () => {
  test("resources has no critical/serious/moderate violations", async ({ page }) => {
    await loginAs(page, SQN_ADMIN);
    await auditRoute(page, "Resources", "/resources");
  });
});

test.describe("Accessibility — Cadets", () => {
  test("cadets has no critical/serious/moderate violations", async ({ page }) => {
    await loginAs(page, SQN_ADMIN);
    await auditRoute(page, "Cadets", "/cadets");
  });
});

test.describe("Accessibility — Action Items", () => {
  test("action items has no critical/serious/moderate violations", async ({ page }) => {
    await loginAs(page, SQN_ADMIN);
    await auditRoute(page, "Action Items", "/action-items");
  });
});

test.describe("Accessibility — Report Catalogue", () => {
  test("report catalogue has no critical/serious/moderate violations", async ({ page }) => {
    await loginAs(page, SQN_ADMIN);
    await auditRoute(page, "Report Catalogue", "/report-catalogue");
  });
});

test.describe("Accessibility — Imports", () => {
  test("imports has no critical/serious/moderate violations", async ({ page }) => {
    await loginAs(page, SQN_ADMIN);
    await auditRoute(page, "Imports", "/imports");
  });
});

test.describe("Accessibility — Audit", () => {
  test("audit log has no critical/serious/moderate violations", async ({ page }) => {
    await loginAs(page, SQN_ADMIN);
    await auditRoute(page, "Audit", "/audit");
  });
});

test.describe("Accessibility — Account Management", () => {
  test("accounts has no critical/serious/moderate violations", async ({ page }) => {
    await loginAs(page, SQN_ADMIN);
    await auditRoute(page, "Account Management", "/accounts");
  });
});

test.describe("Accessibility — Admin", () => {
  test("admin / settings has no critical/serious/moderate violations", async ({ page }) => {
    await loginAs(page, SQN_ADMIN);
    await auditRoute(page, "Admin / Settings", "/admin");
  });
});

test.describe("Accessibility — Settings", () => {
  // No dedicated sidenav link — reached from within Admin, or directly by URL.
  test("settings has no critical/serious/moderate violations", async ({ page }) => {
    await loginAs(page, SQN_ADMIN);
    await page.goto("/settings");
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
    assertNoViolations(results.violations);
  });
});
