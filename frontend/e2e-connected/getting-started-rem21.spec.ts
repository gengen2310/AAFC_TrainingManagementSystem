import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// REM-21: expands the Getting Started guided workflow, backed by
// GET /api/setup/status (backend/app/routers/setup.py). The frontend page
// itself is entirely data-driven (_renderGsSections()/_gsStepRow() render
// whatever `steps` array the backend returns). The backend currently returns
// 14 squadron steps; "cadets_added" was removed 2026-08-28 and
// "flights_created" was removed 2026-08-25. The optional step is now
// training_classes_created ("Create training classes").

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

test.beforeEach(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");
});

async function loginSquadron(page: Page, code: string) {
  if (LOCAL_API_BASE) {
    await page.addInitScript((base) => { (window as any).AAFC_API_BASE = base; }, LOCAL_API_BASE);
  }
  await page.goto("/");
  await page.locator("#auth-type").selectOption("squadron");
  await page.locator("#auth-wing-select").selectOption("7WG");
  await page.locator("#auth-sqn-select").selectOption("703");
  await page.locator("#auth-role").selectOption("sqn_admin");
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill(code);
  await page.locator("#auth-btn").click();
  await expect(page.locator(".ph-title", { hasText: "Training Dashboard" })).toBeVisible({ timeout: 10000 });
}

test("Getting Started shows all 14 squadron steps with no console errors", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await loginSquadron(page, "ADMIN703");

  await page.evaluate(() => (window as any).nav("getting-started"));
  const body = page.locator("#gs-body");
  await expect(body).toBeVisible({ timeout: 10000 });
  await expect(body.getByText("Squadron Setup", { exact: false })).toBeVisible({ timeout: 10000 });

  // Representative sample from the current 14-step backend definition
  // (setup.py). Labels must match exactly what the backend returns.
  // "cadets_added" (2026-08-28) and "flights_created" (2026-08-25) were
  // deliberately removed from the checklist -- they must NOT appear here.
  for (const label of [
    "Create training classes",       // training_classes_created (optional)
    "Add facilitators",              // facilitators_added
    "Add equipment",                 // equipment_added
    "Set the squadron crest",        // crest_set
    "Classify activities by priority and audience",  // activities_classified
    "Review annual program anchor events",           // anchor_events_reviewed
    "Publish a parade night",        // parade_night_published
    "Schedule curriculum sessions",  // curriculum_coverage
  ]) {
    await expect(body.getByText(label, { exact: true })).toBeVisible();
  }

  expect(errors, `no uncaught JS errors: ${errors.join("; ")}`).toHaveLength(0);
});

test("Create training classes shows an Optional badge, distinguishing it from required steps", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");
  await page.evaluate(() => (window as any).nav("getting-started"));
  const body = page.locator("#gs-body");
  await expect(body).toBeVisible({ timeout: 10000 });

  // training_classes_created is the one optional step in the current
  // 14-step backend definition. "flights_created" was removed 2026-08-25.
  const classesRow = body.locator('[data-step-key="training_classes_created"]');
  await expect(classesRow.getByText("Optional", { exact: true })).toBeVisible();

  // A required step, by contrast, must NOT carry the Optional badge --
  // proves the badge is conditional on the backend's own `optional` flag,
  // not applied to every row.
  const crestRow = body.locator('[data-step-key="crest_set"]');
  await expect(crestRow.getByText("Optional", { exact: true })).toHaveCount(0);
});
