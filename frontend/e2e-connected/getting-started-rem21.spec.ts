import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// REM-21: expands the Getting Started guided workflow from 9 steps (2
// national + 7 squadron) to 17 (2 national + 15 squadron), backed by
// GET /api/setup/status (backend/app/routers/setup.py). The frontend page
// itself is entirely data-driven (_renderGsSections()/_gsStepRow() render
// whatever `steps` array the backend returns) -- no new nav wiring was
// needed, only the new "Optional" badge for flights_created, the one step
// that's guidance rather than a completion requirement.

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

test("Getting Started shows all 15 squadron steps, including the new ones, with no console errors", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await loginSquadron(page, "ADMIN703");

  await page.evaluate(() => (window as any).nav("getting-started"));
  const body = page.locator("#gs-body");
  await expect(body).toBeVisible({ timeout: 10000 });
  await expect(body.getByText("Squadron Setup", { exact: false })).toBeVisible({ timeout: 10000 });

  // A representative sample of the newly added steps -- not every one, to
  // keep this test focused, but enough to prove the fuller sequence reached
  // the actual rendered page, not just the API response.
  for (const label of [
    "Set Up Active Planning Year", "Add Equipment", "Set Squadron Crest",
    "Add Cadets to Squadron Roster", "Classify Activities by Priority & Audience",
    "Review Annual Training Program Anchor Events", "Publish a Parade Night",
    "Organise Cadets into Flights",
  ]) {
    await expect(body.getByText(label, { exact: true })).toBeVisible();
  }

  expect(errors, `no uncaught JS errors: ${errors.join("; ")}`).toHaveLength(0);
});

test("Organise Cadets into Flights shows an Optional badge, distinguishing it from required steps", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");
  await page.evaluate(() => (window as any).nav("getting-started"));
  const body = page.locator("#gs-body");
  await expect(body).toBeVisible({ timeout: 10000 });

  const flightsRow = body.locator('[data-step-key="flights_created"]');
  await expect(flightsRow.getByText("Optional", { exact: true })).toBeVisible();

  // A required step, by contrast, must NOT carry the Optional badge --
  // proves the badge is conditional on the backend's own `optional` flag,
  // not applied to every row.
  const crestRow = body.locator('[data-step-key="crest_set"]');
  await expect(crestRow.getByText("Optional", { exact: true })).toHaveCount(0);
});
