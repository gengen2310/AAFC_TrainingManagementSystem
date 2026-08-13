import { test, expect, type Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// WORK-08: "Move to another night" collapsible in PlanningRightDrawer.tsx
// (lines 430-469). The button must be visible whenever an existing session
// is open in the right drawer (isEdit = true). The test seeds a real
// parade date + session via API so it exercises the UI path without relying
// on pre-seeded data that may change between runs.

const API_BASE = process.env.E2E_BACKEND_BASE_URL || "http://localhost:8000";
const ADMIN_CODE = "ADMIN703";

test.beforeAll(async () => {
  await resetBackendRateLimits(API_BASE);
});

async function authHeader(page: Page, code: string): Promise<Record<string, string>> {
  const r = await page.request.post(`${API_BASE}/api/auth/login`, { data: { code } });
  const token = (await r.json()).token as string;
  return { Authorization: `Bearer ${token}` };
}

test("WORK-08: 'Move to another night' button is visible in Planning Workspace session drawer for sqn_admin", async ({ page }) => {
  const hdr = await authHeader(page, ADMIN_CODE);
  const suffix = String(Date.now());

  // Use a far-future year so the date's calendar year matches the planning year
  // (required for term computation in Year view — confirmed in parade-night-grid-classes.spec.ts).
  const testYear = 2620 + (Date.now() % 50);
  const yearRes = await page.request.post(`${API_BASE}/api/planning/years`, {
    data: { year: testYear, name: `WORK-08 Test ${suffix}` }, headers: hdr,
  });
  expect(yearRes.ok()).toBe(true);
  const yearId = (await yearRes.json()).planning_year_id as string;

  // POST /api/planning/years/{id}/parade-dates auto-links a real ParadeNight.
  const pnDate = new Date(testYear, 2, 1).toISOString().slice(0, 10);
  const pdRes = await page.request.post(`${API_BASE}/api/planning/years/${yearId}/parade-dates`, {
    data: { parade_date: pnDate }, headers: hdr,
  });
  expect(pdRes.ok()).toBe(true);
  const pnId = (await pdRes.json()).parade_night_id as string;
  expect(pnId, "parade-dates create must auto-link a real ParadeNight").toBeTruthy();

  // Add a session on period 1, senior group — this matches the first instructional
  // timing block so it appears in the Night view grid.
  const sessRes = await page.request.post(`${API_BASE}/api/sessions`, {
    data: { parade_night_id: pnId, period_number: 1, cadet_group: "senior" },
    headers: hdr,
  });
  expect(sessRes.ok()).toBe(true);

  try {
    // authHeader()'s login call set the aafc_session fallback cookie in this
    // page's browser context — goto() auto-resumes the session.
    await page.goto("/planning");
    await expect(page.getByRole("main", { name: /planning workspace/i })).toBeVisible({ timeout: 10000 });

    // Select the test year via its chip button.
    await page.getByRole("button", { name: `WORK-08 Test ${suffix}` }).click();

    // Click the parade date block to switch from Year view to Night view.
    const dateBlock = page.getByRole("button", { name: `Parade night ${pnDate}` });
    await expect(dateBlock).toBeVisible({ timeout: 10000 });
    await dateBlock.click();

    // Night view grid must be present.
    await expect(page.locator(".pn-grid")).toBeVisible({ timeout: 10000 });

    // Click the session cell (div.pn-cell-inner[role="button"]) to open the right drawer.
    // The cell renders with role="button" for keyboard accessibility (PlanningRightDrawer.tsx line 387).
    const sessionCell = page.locator(".pn-cell-inner[role='button']").first();
    await expect(sessionCell).toBeVisible({ timeout: 8000 });
    await sessionCell.click();

    // Right drawer must open (role="complementary", aria-label="Detail drawer").
    await expect(page.locator("[aria-label='Detail drawer']")).toBeVisible({ timeout: 5000 });

    // "Move to another night" must be present — rendered by SessionForm when
    // isEdit=true (item.type === "session", i.e. an existing session is open).
    // The button text includes a triangle prefix character but hasText does a
    // partial match so "Move to another night" is sufficient.
    await expect(page.locator("button", { hasText: "Move to another night" })).toBeVisible({ timeout: 3000 });
  } finally {
    // Deactivate the test year to avoid it appearing as an active year in future runs.
    const curYearRes = await page.request.get(`${API_BASE}/api/planning/years/${yearId}`, { headers: hdr });
    const curYear = await curYearRes.json();
    await page.request.patch(`${API_BASE}/api/planning/years/${yearId}`, {
      data: { active_status: false, version: curYear.version }, headers: hdr,
    });
  }
});
