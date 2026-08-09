import { test, expect, type Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// CLASS-06: the standalone /weekly-program route (WeeklyProgram.tsx,
// full-app mode -- distinct from Planning Workspace's own parade-night grid
// view and from connected-frontend's renderWP()) gets a new "Class" column.
// Reads its data from trainingApi.paradeNights() -> GET /api/parade-nights,
// the same endpoint extended for connected-frontend's Weekly Program page.

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

test("Weekly Program (/weekly-program) shows a session's real Training Class in its own Class column", async ({ page }) => {
  const hdr = await authHeader(page, ADMIN_CODE);
  const suffix = String(Date.now());

  const me = await (await page.request.get(`${API_BASE}/api/auth/me`, { headers: hdr })).json();
  const sqnId = me.session.squadron_id as string;
  const wingId = me.session.wing_id as string;

  const years = await (await page.request.get(`${API_BASE}/api/planning/years`, { headers: hdr })).json();
  const yearId = years[0].planning_year_id as string;

  const stageName = `CLASS-06-FULLAPP-${suffix}`;
  const stageRes = await page.request.post(`${API_BASE}/api/curriculum/phases`, {
    data: { name: stageName, display_name: stageName, scope_level: "squadron", squadron_id: sqnId },
    headers: hdr,
  });
  expect(stageRes.ok()).toBe(true);
  const stageId = (await stageRes.json()).phase_id as string;

  const className = `Full App WP Class ${suffix}`;
  const classRes = await page.request.post(`${API_BASE}/api/training-classes`, {
    data: { training_year_id: yearId, training_stage_id: stageId, display_name: className },
    headers: hdr,
  });
  expect(classRes.ok()).toBe(true);
  const classId = (await classRes.json()).training_class_id as string;

  const pnDate = new Date(2130, 2, 1 + (Date.now() % 300)).toISOString().slice(0, 10);
  const pnRes = await page.request.post(`${API_BASE}/api/parade-nights`, {
    data: { squadron_id: sqnId, wing_id: wingId, date: pnDate, parade_type: "normal" },
    headers: hdr,
  });
  expect(pnRes.ok()).toBe(true);
  const pnId = (await pnRes.json()).parade_night_id as string;

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

  // authHeader()'s login call above already set the aafc_session fallback
  // cookie in this page's own browser context -- goto() auto-resumes the
  // session, matching the pattern established in
  // mission-backlog-classes.spec.ts.
  await page.goto("/weekly-program");
  await expect(page.getByRole("heading", { name: "Weekly Program" })).toBeVisible({ timeout: 10000 });

  await page.locator("#wk-pn").selectOption(pnId);
  await expect(page.getByText("Class", { exact: true })).toBeVisible({ timeout: 8000 });

  const row = page.locator("table tr").filter({ hasText: className });
  await expect(row).toBeVisible({ timeout: 8000 });
});
