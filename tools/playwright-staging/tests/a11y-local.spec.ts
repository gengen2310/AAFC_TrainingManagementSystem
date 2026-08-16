import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// A11Y-01 axe scan against local frontend (login page only, no backend session required).
// The page calls the production backend for /api/auth/me; on 401, shows #auth-step1.
// Start server: cd connected-frontend && python3 -m http.server 8181
//
// Skipped automatically when STAGING_SQN_ADMIN_CODE is set (indicates a staging
// suite run where localhost:8181 is not available).

const IS_STAGING = !!process.env.STAGING_SQN_ADMIN_CODE;

test.use({ baseURL: "http://localhost:8181" });

test("[A11Y] Auth form — zero select-name / label violations", async ({
  page,
}) => {
  test.skip(IS_STAGING, "Local-only test — localhost:8181 not available in staging suite");
  await page.goto("/");
  // auth-screen is visible immediately; auth-step1 appears after /api/auth/me 401
  // Production backend responds quickly; allow up to 15s for first network round-trip
  await page.waitForSelector("#auth-step1", { state: "visible", timeout: 15000 });

  const results = await new AxeBuilder({ page })
    .include("#auth-step1")
    .withRules([
      "label",
      "label-content-name-mismatch",
      "select-name",
      "form-field-multiple-labels",
      "duplicate-id",
      "duplicate-id-aria",
      "aria-allowed-attr",
      "aria-valid-attr-value",
    ])
    .analyze();

  const criticalOrSerious = results.violations.filter((v) =>
    ["critical", "serious"].includes(v.impact ?? "")
  );

  if (criticalOrSerious.length > 0) {
    console.log("VIOLATIONS:");
    for (const v of criticalOrSerious) {
      console.log(`  [${v.impact}] ${v.id}: ${v.description}`);
      for (const node of v.nodes) {
        console.log(`    Target: ${node.target}`);
        console.log(`    HTML: ${node.html}`);
      }
    }
  }

  expect(
    criticalOrSerious,
    `${criticalOrSerious.length} critical/serious axe violations on auth form`
  ).toHaveLength(0);
});

test("[A11Y] Full page — zero duplicate-id violations (static DOM)", async ({
  page,
}) => {
  test.skip(IS_STAGING, "Local-only test — localhost:8181 not available in staging suite");
  await page.goto("/");
  // Only need the page to load — don't require auth-step1 for duplicate-id check
  await page.waitForLoadState("networkidle", { timeout: 15000 });

  const results = await new AxeBuilder({ page })
    .withRules(["duplicate-id", "duplicate-id-aria"])
    .analyze();

  const violations = results.violations.filter((v) =>
    ["critical", "serious", "moderate"].includes(v.impact ?? "")
  );

  if (violations.length > 0) {
    console.log("DUPLICATE ID VIOLATIONS:");
    for (const v of violations) {
      console.log(`  [${v.impact}] ${v.id}: ${v.description}`);
      for (const node of v.nodes) {
        console.log(`    Target: ${node.target}`);
      }
    }
  }

  expect(violations, `${violations.length} duplicate-id violations`).toHaveLength(0);
});
