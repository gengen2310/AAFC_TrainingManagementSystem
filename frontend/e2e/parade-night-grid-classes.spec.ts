import { test, expect, type Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// CLASS-06 follow-up (gap register CLASS-22's residual item): ParadeNightGridView.tsx
// (Planning Workspace's "Night" view, reached via Year view -> click a
// parade date) renders each grid cell's Training Class assignment inline.
// This is the one of Weekly Program's three real frontend consumers that
// did not get a dedicated e2e test when the rendering was first added --
// its underlying data (planningApi.weeklyProgram(dateId)'s training_classes
// field) was already covered by 6 backend tests, but the live UI path
// itself (Year view -> click a date -> Night view) was not exercised.

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

test("Planning Workspace Night view grid cell shows a session's real Training Class assignment", async ({ page }) => {
  const hdr = await authHeader(page, ADMIN_CODE);
  const suffix = String(Date.now());

  const me = await (await page.request.get(`${API_BASE}/api/auth/me`, { headers: hdr })).json();
  const sqnId = me.session.squadron_id as string;
  const wingId = me.session.wing_id as string;

  // A dedicated test-only PlanningYear rather than reusing years[0]: Year
  // view computes each date's term/week position from the PlanningYear's
  // own `year` field (see _term_for_date in the backend), so a date whose
  // actual calendar year doesn't match py.year can fall outside every
  // rendered term row and never appear as a clickable block at all --
  // confirmed directly (this is what happened on the first attempt at this
  // test, using years[0] with a deliberately far-future literal date). The
  // year value here matches the date's own year so term computation lines
  // up, and is far outside anything else in this suite (2610+) so it can
  // never tie with a leftover active year from an earlier run (REM-129).
  const testYear = 2610 + (Date.now() % 50);
  const yearRes = await page.request.post(`${API_BASE}/api/planning/years`, {
    data: { year: testYear, name: `CLASS-06 Grid Test ${suffix}` }, headers: hdr,
  });
  expect(yearRes.ok()).toBe(true);
  const yearId = (await yearRes.json()).planning_year_id as string;

  const stageName = `CLASS-06-GRID-${suffix}`;
  const stageRes = await page.request.post(`${API_BASE}/api/curriculum/phases`, {
    data: { name: stageName, display_name: stageName, scope_level: "squadron", squadron_id: sqnId },
    headers: hdr,
  });
  expect(stageRes.ok()).toBe(true);
  const stageId = (await stageRes.json()).phase_id as string;

  const className = `Grid View Class ${suffix}`;
  const classRes = await page.request.post(`${API_BASE}/api/training-classes`, {
    data: { training_year_id: yearId, training_stage_id: stageId, display_name: className },
    headers: hdr,
  });
  expect(classRes.ok()).toBe(true);
  const classId = (await classRes.json()).training_class_id as string;

  // A ParadeDate (not just a plain ParadeNight) is required for this date
  // to be clickable in Year view at all -- planningApi.weeklyProgram()
  // reads by parade_date_id, and Year view is built from
  // GET /api/planning/years/{id}/parade-dates. The date's own calendar
  // year matches testYear, per the comment above.
  const pnDate = new Date(testYear, 2, 1 + (Date.now() % 27)).toISOString().slice(0, 10);
  const pdRes = await page.request.post(`${API_BASE}/api/planning/years/${yearId}/parade-dates`, {
    data: { parade_date: pnDate }, headers: hdr,
  });
  expect(pdRes.ok()).toBe(true);
  const pdBody = await pdRes.json();
  const pnId = pdBody.parade_night_id as string;
  expect(pnId, "parade-dates create must auto-link a real ParadeNight").toBeTruthy();

  const sessRes = await page.request.post(`${API_BASE}/api/sessions`, {
    data: { parade_night_id: pnId, period_number: 1, cadet_group: "senior" },
    headers: hdr,
  });
  expect(sessRes.ok()).toBe(true);
  const sid = (await sessRes.json()).session_id as string;

  const audRes = await page.request.put(`${API_BASE}/api/sessions/${sid}/audience`, {
    data: { training_class_ids: [classId] }, headers: hdr,
  });
  expect(audRes.ok()).toBe(true);

  try {
    // authHeader()'s login call above already set the aafc_session fallback
    // cookie in this page's own browser context -- goto() auto-resumes the
    // session, matching the pattern established in the other CLASS-05/06
    // Planning Workspace tests.
    await page.goto("/planning");
    await expect(page.getByRole("main", { name: /planning workspace/i })).toBeVisible({ timeout: 10000 });

    // PlanningWorkspace.tsx auto-selects whichever active year happens to
    // come first in the API's own return order, not necessarily this
    // test's newly-created one -- select it explicitly via its own "Year:"
    // chip (same pattern as mission-backlog-classes.spec.ts).
    await page.getByRole("button", { name: `CLASS-06 Grid Test ${suffix}` }).click();

    // Year view is the default. Its clickable date header carries
    // aria-label="Parade night {date}" (ParadeNightBlock.tsx) for both the
    // populated and fallback block variants.
    const dateBlock = page.getByRole("button", { name: `Parade night ${pnDate}` });
    await expect(dateBlock).toBeVisible({ timeout: 10000 });
    await dateBlock.click();

    // Clicking a date switches viewRange to "parade-night", rendering
    // ParadeNightGridView.
    await expect(page.locator(".pn-grid")).toBeVisible({ timeout: 10000 });
    const cell = page.locator(".pn-cell-classes", { hasText: className });
    await expect(cell).toBeVisible({ timeout: 10000 });
  } finally {
    // Clean up -- archive the class + phase and deactivate the year so nothing
    // lingers as an active PlanningYear for a future test run.
    await page.request.delete(`${API_BASE}/api/training-classes/${classId}`, { headers: hdr });
    await page.request.post(`${API_BASE}/api/curriculum/phases/${stageId}/archive`, { headers: hdr });
    const curYearRes = await page.request.get(`${API_BASE}/api/planning/years/${yearId}`, { headers: hdr });
    const curYear = await curYearRes.json();
    await page.request.patch(`${API_BASE}/api/planning/years/${yearId}`, {
      data: { active_status: false, version: curYear.version }, headers: hdr,
    });
  }
});
