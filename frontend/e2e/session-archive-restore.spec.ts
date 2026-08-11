import { test, expect, type Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// REM-133 (5th instance): TrainingSession delete existed with no restore
// counterpart, and archived sessions were entirely invisible on the Night
// grid view (no way to even see one to restore it). Added a "Show archived
// sessions" toggle plus a Restore button, following the same pattern already
// proven for connected-frontend's Facilitator/Wing HQ Event/Curriculum Item.

const API_BASE = process.env.E2E_BACKEND_BASE_URL || "http://localhost:8000";

test.beforeAll(async () => {
  await resetBackendRateLimits(API_BASE);
});

const ADMIN_CODE = "ADMIN703";

async function authHeader(page: Page, code: string): Promise<Record<string, string>> {
  const r = await page.request.post(`${API_BASE}/api/auth/login`, { data: { code } });
  const token = (await r.json()).token as string;
  return { Authorization: `Bearer ${token}` };
}

test("an archived session is hidden from the Night grid, visible via Show archived sessions, and Restore brings it back", async ({ page }) => {
  const hdr = await authHeader(page, ADMIN_CODE);
  const suffix = String(Date.now());

  // Dedicated test-only year -- see parade-night-grid-classes.spec.ts's own
  // comment for why the year value must match the parade date's calendar
  // year and stay far outside the range any other suite file would use.
  const testYear = 2610 + (Date.now() % 50);
  const yearRes = await page.request.post(`${API_BASE}/api/planning/years`, {
    data: { year: testYear, name: `REM-133 Session Restore Test ${suffix}` }, headers: hdr,
  });
  expect(yearRes.ok()).toBe(true);
  const yearId = (await yearRes.json()).planning_year_id as string;

  const pnDate = new Date(testYear, 2, 1 + (Date.now() % 27)).toISOString().slice(0, 10);
  const pdRes = await page.request.post(`${API_BASE}/api/planning/years/${yearId}/parade-dates`, {
    data: { parade_date: pnDate }, headers: hdr,
  });
  expect(pdRes.ok()).toBe(true);
  const pdBody = await pdRes.json();
  const pnId = pdBody.parade_night_id as string;
  expect(pnId, "parade-dates create must auto-link a real ParadeNight").toBeTruthy();

  // SessionIn (training.py's POST /api/sessions) names this field
  // custom_title, not activity_title -- _real_session_out() (planning.py)
  // maps it to activity_title (curriculum_title_at_time or custom_title)
  // in the shape the Planning Workspace UI actually reads.
  const activityTitle = `REM-133 Archived Session ${suffix}`;
  const sessRes = await page.request.post(`${API_BASE}/api/sessions`, {
    data: { parade_night_id: pnId, period_number: 1, cadet_group: "senior", custom_title: activityTitle },
    headers: hdr,
  });
  expect(sessRes.ok()).toBe(true);
  const sessionId = (await sessRes.json()).session_id as string;

  const deleteRes = await page.request.delete(`${API_BASE}/api/planning/sessions/${sessionId}`, { headers: hdr });
  expect(deleteRes.ok()).toBe(true);

  try {
    await page.goto("/planning");
    await expect(page.getByRole("main", { name: /planning workspace/i })).toBeVisible({ timeout: 10000 });
    await page.getByRole("button", { name: `REM-133 Session Restore Test ${suffix}` }).click();

    const dateBlock = page.getByRole("button", { name: `Parade night ${pnDate}` });
    await expect(dateBlock).toBeVisible({ timeout: 10000 });
    await dateBlock.click();

    await expect(page.locator(".pn-grid")).toBeVisible({ timeout: 10000 });
    // Archived session must not appear as a live grid cell.
    await expect(page.locator(".pn-cell-title", { hasText: activityTitle })).toHaveCount(0);

    await page.getByRole("button", { name: "Show archived sessions" }).click();
    const row = page.locator("tr", { hasText: activityTitle });
    await expect(row).toBeVisible({ timeout: 5000 });

    await row.getByRole("button", { name: "Restore" }).click();
    // The archived table (this session was the only entry) collapses to the
    // empty state -- checked directly rather than "no <tr> contains the
    // title" (too broad: the restored session's own live grid row also
    // contains the title once the weekly-program query re-fetches).
    await expect(page.getByText("No archived sessions for this parade night.")).toBeVisible({ timeout: 5000 });

    // Restored session must now render as a live grid cell.
    await expect(page.locator(".pn-cell-title", { hasText: activityTitle })).toBeVisible({ timeout: 5000 });
  } finally {
    // Clean up -- archive the session and deactivate the year so nothing
    // lingers as an active PlanningYear for a future test run.
    await page.request.delete(`${API_BASE}/api/planning/sessions/${sessionId}`, { headers: hdr });
    const curYearRes = await page.request.get(`${API_BASE}/api/planning/years/${yearId}`, { headers: hdr });
    const curYear = await curYearRes.json();
    await page.request.patch(`${API_BASE}/api/planning/years/${yearId}`, {
      data: { active_status: false, version: curYear.version }, headers: hdr,
    });
  }
});
