import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// CLASS-06 (connected-frontend side): verify that the live Weekly Program
// surfaces the Training Class audience attached to a session. The Weekly
// Program now renders the governed stage/class grid rather than the retired
// generic "Sess 1 / Sess 2" row layout, so this test follows that current
// contract instead of asserting obsolete row labels.

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

// IDs of resources created during this run — cleaned up in afterAll.
const _createdPnIds: string[] = [];
const _createdClassIds: string[] = [];

test.beforeAll(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");
});

test.afterAll(async ({ request }) => {
  const base = process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000";
  const lookup = await request.post(`${base}/api/auth/lookup`, {
    data: { unit_type: "squadron", identifier: "703", role: "sqn_admin" },
  });
  if (!lookup.ok()) return;
  const userId = (await lookup.json()).user_id as string;
  const loginRes = await request.post(`${base}/api/auth/login`, {
    data: { code: "ADMIN703", user_id: userId },
  });
  if (!loginRes.ok()) return;
  const body = await loginRes.json();
  const auth = { Authorization: `Bearer ${body.token || body.access_token}` };

  for (const pnId of _createdPnIds) {
    await request.delete(`${base}/api/parade-nights/${pnId}`, { headers: auth });
  }
  for (const classId of _createdClassIds) {
    await request.delete(`${base}/api/training-classes/${classId}`, { headers: auth });
  }
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

test("Weekly Program shows a session's real Training Class assignment in the current class grid", async ({ page }) => {
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

  // The printed Weekly Program groups classes by the governed CurriculumPhase
  // matching the session cadet_group. A synthetic custom phase cannot match
  // cadet_group="senior" and therefore correctly renders outside the Senior
  // column. Use the real governed Senior stage so this fixture tests class
  // rendering rather than an impossible stage/group combination.
  const phasesRes = await page.request.get(`${base}/api/curriculum/phases`, { headers: auth });
  expect(phasesRes.ok()).toBe(true);
  const phases = await phasesRes.json() as Array<{ phase_id: string; name: string }>;
  const seniorStage = phases.find((p) => p.name === "E. Senior");
  expect(seniorStage, "governed E. Senior training stage must exist").toBeTruthy();

  const className = `WP E2E Class ${suffix}`;
  const classRes = await page.request.post(`${base}/api/training-classes`, {
    data: { training_year_id: yearId, training_stage_id: seniorStage!.phase_id, display_name: className },
    headers: auth,
  });
  expect(classRes.ok()).toBe(true);
  const classId = (await classRes.json()).training_class_id as string;
  _createdClassIds.push(classId);

  const testDate = new Date(2065, 6, 1 + (Date.now() % 300)).toISOString().slice(0, 10);
  const pnRes = await page.request.post(`${base}/api/parade-nights`, {
    data: { squadron_id: me.session.squadron_id, wing_id: me.session.wing_id, date: testDate, parade_type: "normal" },
    headers: auth,
  });
  expect(pnRes.ok()).toBe(true);
  const pnId = (await pnRes.json()).parade_night_id as string;
  _createdPnIds.push(pnId);

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
  // The test parade night is deliberately outside the active planning year to
  // avoid collisions, so clear the current-year filter before opening Weekly Program.
  await page.evaluate(() => { (window as any).P.currentYearId = null; });
  await page.evaluate(() => (window as any).nav("weekly-program"));
  await expect(page.locator("#wp-sel")).toBeVisible({ timeout: 8000 });
  await page.locator("#wp-f-term").selectOption("all");
  const exactNight = page.locator(`#wp-sel option[value="${testDate}"]`);
  await expect(exactNight).toHaveCount(1, { timeout: 8000 });
  await page.locator("#wp-sel").selectOption({ value: testDate });

  // Current contract: the selected night renders a stage/class grid. The
  // assigned Training Class must be visible in that rendered program; the old
  // "Sess 1" row label was removed by the timing-grid redesign and is not a
  // product requirement.
  const program = page.locator("#wp-content");
  await expect(program).toContainText(className, { timeout: 8000 });

  expect(errors, `no uncaught JS errors: ${errors.join("; ")}`).toHaveLength(0);
});

test("WORK-10: Publish Program button is visible to sqn_admin on the Weekly Program page", async ({ page }) => {
  // WORK-10: Main TMS publishWP() parity — sqn_admin must be able to publish
  // a weekly program from connected-frontend without switching to Planning Workspace.
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await loginSquadron(page, "ADMIN703");
  const token = await page.evaluate(() => (window as any).tokenGet?.() ?? sessionStorage.getItem("aafc_token"));
  const base = await apiBase();
  const auth = { Authorization: `Bearer ${token}` };

  // Create a parade night with a known date so we can select it in the Weekly Program picker.
  const me = await (await page.request.get(`${base}/api/auth/me`, { headers: auth })).json();
  const testDate = new Date(2068, 0, 15).toISOString().slice(0, 10); // 2068-01-15
  const pnRes = await page.request.post(`${base}/api/parade-nights`, {
    data: { squadron_id: me.session.squadron_id, wing_id: me.session.wing_id, date: testDate, parade_type: "normal" },
    headers: auth,
  });
  expect(pnRes.ok()).toBe(true);
  if (pnRes.ok()) _createdPnIds.push((await pnRes.json()).parade_night_id as string);

  await page.evaluate(() => (window as any).reloadAndRender());
  await page.evaluate(() => { (window as any).P.currentYearId = null; });
  await page.evaluate(() => (window as any).nav("weekly-program"));
  await expect(page.locator("#wp-sel")).toBeVisible({ timeout: 8000 });
  await page.locator("#wp-f-term").selectOption("all");
  const exactNight = page.locator(`#wp-sel option[value="${testDate}"]`);
  await expect(exactNight).toHaveCount(1, { timeout: 8000 });
  await page.locator("#wp-sel").selectOption({ value: testDate });

  // The "Publish night" button is visible and enabled once a night is selected.
  // Button text: "Publish night" (enabled when a single night is chosen).
  const publishBtn = page.locator("#wp-publish-btn");
  await expect(publishBtn).toBeVisible({ timeout: 5000 });
  await expect(publishBtn).toBeEnabled();

  expect(errors, `no uncaught JS errors: ${errors.join("; ")}`).toHaveLength(0);
});

// ── DEF-06 / Weekly Program wing_name header ─────────────────────────────────
// renderWP() must use session.wing_name (from /api/auth/me) in the parade night
// header rather than the previously hardcoded "7 Wing Australian Air Force Cadets".
// The wing_name for the 7WG seed is "7 Wing (Western Australia)".
test("Weekly Program header shows the Wing's real name from the session (not hardcoded 7WG text)", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await loginSquadron(page, "ADMIN703");
  const token = await page.evaluate(() => (window as any).tokenGet?.() ?? sessionStorage.getItem("aafc_token"));
  const base = await apiBase();
  const auth = { Authorization: `Bearer ${token}` };

  const me = await (await page.request.get(`${base}/api/auth/me`, { headers: auth })).json();
  // Verify the session carries wing_name as expected by the frontend fix.
  const wingName: string = me.session.wing_name;
  expect(wingName).toBeTruthy();
  expect(wingName).not.toBe("7 Wing Australian Air Force Cadets");

  // Create a parade night at a unique far-future date so the dropdown has a selectable option.
  const testDate = new Date(2072, 4, 21).toISOString().slice(0, 10); // 2072-05-21
  const pnRes = await page.request.post(`${base}/api/parade-nights`, {
    data: { squadron_id: me.session.squadron_id, wing_id: me.session.wing_id, date: testDate, parade_type: "normal" },
    headers: auth,
  });
  expect(pnRes.ok()).toBe(true);
  if (pnRes.ok()) _createdPnIds.push((await pnRes.json()).parade_night_id as string);

  await page.evaluate(() => (window as any).reloadAndRender());
  await page.evaluate(() => { (window as any).P.currentYearId = null; });
  await page.evaluate(() => (window as any).nav("weekly-program"));
  await expect(page.locator("#wp-sel")).toBeVisible({ timeout: 8000 });
  await page.locator("#wp-f-term").selectOption("all");
  const exactNight = page.locator(`#wp-sel option[value="${testDate}"]`);
  await expect(exactNight).toHaveCount(1, { timeout: 8000 });
  await page.locator("#wp-sel").selectOption({ value: testDate });

  // DEF-06: the night-sqn span in the table header must render the real wing_name
  // (from S.session.wing_name, populated from /api/auth/me). Wing name is appended
  // after the squadron name with an em-dash separator.
  const header = page.locator("#wp-content .night-sqn").first();
  await expect(header).toBeVisible({ timeout: 5000 });
  await expect(header).toContainText(wingName);

  // Guard: must NOT contain the old hardcoded string.
  const headerText = await header.textContent();
  expect(headerText).not.toContain("7 Wing Australian Air Force Cadets");

  expect(errors, `no uncaught JS errors: ${errors.join("; ")}`).toHaveLength(0);
});
