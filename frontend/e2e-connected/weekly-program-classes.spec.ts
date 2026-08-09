import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// CLASS-06 (connected-frontend side): the real, live Weekly Program page
// (renderWP(), reached via nav('weekly-program')) gets a new "Class"
// column. Confirmed via grep that this page -- NOT the similarly-named
// loadWeeklyProgram()/#pw-* code path -- is the one actually reachable:
// #pw-card/#pw-preview-section/etc have zero matches anywhere in this
// file's static or dynamically-generated HTML (the same dead-code pattern
// CLASS-18 documented). renderWP() reads session data from S.pns, itself
// populated from GET /api/parade-nights's new additive `training_classes`
// field on each embedded session.

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

test.beforeAll(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");
});

async function loginSquadron(page: Page, code: string) {
  if (LOCAL_API_BASE) {
    await page.addInitScript((base) => {
      (window as any).AAFC_API_BASE = base;
    }, LOCAL_API_BASE);
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

async function apiBase() {
  return process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000";
}

test("Weekly Program shows a session's real Training Class assignment in its own Class column", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await loginSquadron(page, "ADMIN703");
  const token = await page.evaluate(() => (window as any).tokenGet?.() ?? sessionStorage.getItem("aafc_token"));
  const base = await apiBase();
  const auth = { Authorization: `Bearer ${token}` };
  const suffix = String(Date.now());

  const me = await (await page.request.get(`${base}/api/auth/me`, { headers: auth })).json();
  const years = await (await page.request.get(`${base}/api/planning/years`, { headers: auth })).json();
  const yearId = years[0].planning_year_id as string;

  const stageName = `CLASS-06-WP-E2E-${suffix}`;
  const stageRes = await page.request.post(`${base}/api/curriculum/phases`, {
    data: { name: stageName, display_name: stageName, scope_level: "squadron", squadron_id: me.session.squadron_id },
    headers: auth,
  });
  expect(stageRes.ok()).toBe(true);
  const stageId = (await stageRes.json()).phase_id as string;

  const className = `WP E2E Class ${suffix}`;
  const classRes = await page.request.post(`${base}/api/training-classes`, {
    data: { training_year_id: yearId, training_stage_id: stageId, display_name: className },
    headers: auth,
  });
  expect(classRes.ok()).toBe(true);
  const classId = (await classRes.json()).training_class_id as string;

  const testDate = new Date(2065, 6, 1 + (Date.now() % 300)).toISOString().slice(0, 10);
  const pnRes = await page.request.post(`${base}/api/parade-nights`, {
    data: { squadron_id: me.session.squadron_id, wing_id: me.session.wing_id, date: testDate, parade_type: "normal" },
    headers: auth,
  });
  expect(pnRes.ok()).toBe(true);
  const pnId = (await pnRes.json()).parade_night_id as string;

  const sessRes = await page.request.post(`${base}/api/sessions`, {
    data: { parade_night_id: pnId, period_number: 1, cadet_group: "senior" },
    headers: auth,
  });
  expect(sessRes.ok()).toBe(true);
  const sid = (await sessRes.json()).session_id as string;

  const audRes = await page.request.put(`${base}/api/sessions/${sid}/audience`, {
    data: { training_class_ids: [classId] }, headers: auth,
  });
  expect(audRes.ok()).toBe(true);

  await page.evaluate(() => (window as any).reloadAndRender());
  await page.evaluate(() => (window as any).nav("weekly-program"));
  await expect(page.locator("#wp-sel")).toBeVisible({ timeout: 8000 });
  await page.locator("#wp-sel").selectOption(testDate);

  const row = page.locator("#wp-content table tr").filter({ hasText: "Sess 1" });
  await expect(row).toBeVisible({ timeout: 8000 });
  await expect(row).toContainText(className);

  expect(errors, `no uncaught JS errors: ${errors.join("; ")}`).toHaveLength(0);
});
