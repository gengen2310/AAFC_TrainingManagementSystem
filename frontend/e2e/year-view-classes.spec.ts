import { test, expect, type Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// CLASS-06 pt.3: Planning Workspace's Year view (the default landing view,
// ParadeNightBlock.tsx's standard/non-compact grid, shared by YearView,
// TermView, TwoWeekView, EightWeekView, and ListView) now shows each
// session's Training Class assignment inline, at a glance, without
// requiring a click into the single-night "Night" view (already covered
// by parade-night-grid-classes.spec.ts). Reads
// GET /api/planning/years/{id}/annual-program's new training_classes field.

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

test("Year view shows a session's real Training Class assignment without opening the Night view", async ({ page }) => {
  const hdr = await authHeader(page, ADMIN_CODE);
  const suffix = String(Date.now());

  const me = await (await page.request.get(`${API_BASE}/api/auth/me`, { headers: hdr })).json();
  const sqnId = me.session.squadron_id as string;

  // A dedicated test-only PlanningYear whose `year` matches the test
  // date's own calendar year -- get_annual_program() builds its 4 term
  // blocks from the PlanningYear's own `year` field (_WA_TERM_RANGES), so
  // a mismatched date falls outside every term block and never renders as
  // a block at all (the same lesson learned building
  // parade-night-grid-classes.spec.ts).
  const testYear = 2650 + (Date.now() % 50);
  const yearRes = await page.request.post(`${API_BASE}/api/planning/years`, {
    data: { year: testYear, name: `CLASS-06 Year View Test ${suffix}` }, headers: hdr,
  });
  expect(yearRes.ok()).toBe(true);
  const yearId = (await yearRes.json()).planning_year_id as string;

  const stageName = `CLASS-06-YV-${suffix}`;
  const stageRes = await page.request.post(`${API_BASE}/api/curriculum/phases`, {
    data: { name: stageName, display_name: stageName, scope_level: "squadron", squadron_id: sqnId },
    headers: hdr,
  });
  expect(stageRes.ok()).toBe(true);
  const stageId = (await stageRes.json()).phase_id as string;

  const className = `Year View Class ${suffix}`;
  const classRes = await page.request.post(`${API_BASE}/api/training-classes`, {
    data: { training_year_id: yearId, training_stage_id: stageId, display_name: className },
    headers: hdr,
  });
  expect(classRes.ok()).toBe(true);
  const classId = (await classRes.json()).training_class_id as string;

  // Term 3's real WA date range for this test year (_WA_TERM_RANGES).
  const pnDate = `${testYear}-08-06`;
  const pdRes = await page.request.post(`${API_BASE}/api/planning/years/${yearId}/parade-dates`, {
    data: { parade_date: pnDate }, headers: hdr,
  });
  expect(pdRes.ok()).toBe(true);
  const pnId = (await pdRes.json()).parade_night_id as string;
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
    // chip.
    await page.getByRole("button", { name: `CLASS-06 Year View Test ${suffix}` }).click();

    // Year view is the default -- the class name must be visible directly
    // in the calendar block, with no click required.
    const classLine = page.locator(".pw-nc-classes", { hasText: className });
    await expect(classLine).toBeVisible({ timeout: 10000 });
  } finally {
    await page.request.delete(`${API_BASE}/api/training-classes/${classId}`, { headers: hdr });
    const curYearRes = await page.request.get(`${API_BASE}/api/planning/years/${yearId}`, { headers: hdr });
    const curYear = await curYearRes.json();
    await page.request.patch(`${API_BASE}/api/planning/years/${yearId}`, {
      data: { active_status: false, version: curYear.version }, headers: hdr,
    });
  }
});
