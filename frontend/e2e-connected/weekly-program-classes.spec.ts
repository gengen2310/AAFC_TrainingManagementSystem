import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";
import { selectConnectedPlanningYear } from "./year-context-helper";

// CLASS-06 (connected-frontend side): verify that the live Weekly Program
// surfaces the Training Class audience attached to a session. The Weekly
// Program now renders the governed stage/class grid rather than the retired
// generic "Sess 1 / Sess 2" row layout, so this test follows that current
// contract instead of asserting obsolete row labels.

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

// IDs of resources created during this run — cleaned up in afterAll.
const _createdPnIds: string[] = [];
const _createdClassIds: string[] = [];
const _createdSessionIds: string[] = [];
// Only years this file actually created (not ones reused via 409 existing_id).
const _createdYearIds: string[] = [];

test.beforeEach(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");
});

test.afterAll(async ({ request }) => {
  const base = process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000";
  const lookup = await request.post(`${base}/api/auth/lookup`, {
    data: { unit_type: "squadron", identifier: "703", role: "sqn_admin" },
  });
  expect(lookup.ok(), "afterAll cleanup: sqn_admin lookup failed").toBe(true);
  const userId = (await lookup.json()).user_id as string;
  const loginRes = await request.post(`${base}/api/auth/login`, {
    data: { code: "ADMIN703", user_id: userId },
  });
  expect(loginRes.ok(), "afterAll cleanup: sqn_admin login failed").toBe(true);
  const body = await loginRes.json();
  const auth = { Authorization: `Bearer ${body.token || body.access_token}` };
  // Exact-ID cleanup of resources this file created; 404 = already removed.
  const ok = (r: { status(): number }, what: string) =>
    expect([200, 204, 404], `cleanup ${what} -> ${r.status()}`).toContain(r.status());

  for (const sessionId of _createdSessionIds) {
    ok(await request.delete(`${base}/api/planning/sessions/${sessionId}`, { headers: auth }), `session ${sessionId}`);
  }
  for (const pnId of _createdPnIds) {
    ok(await request.delete(`${base}/api/parade-nights/${pnId}`, { headers: auth }), `parade night ${pnId}`);
  }
  for (const classId of _createdClassIds) {
    ok(await request.delete(`${base}/api/training-classes/${classId}`, { headers: auth }), `training class ${classId}`);
  }
  // Deactivate every fixture year this file created (randomised per test, so
  // leaving them active accumulated active years across runs and inflated
  // Main TMS's per-active-year boot requests until the rate limiter tripped).
  for (const yearId of _createdYearIds) {
    const cur = await request.get(`${base}/api/planning/years/${yearId}`, { headers: auth });
    ok(cur, `year lookup ${yearId}`);
    if (!cur.ok()) continue;
    ok(await request.patch(`${base}/api/planning/years/${yearId}`, {
      data: { active_status: false, version: (await cur.json()).version }, headers: auth,
    }), `year deactivate ${yearId}`);
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

  // Weekly Program is planning-year scoped. Materialise a dedicated test year
  // first, then create both the Training Class and Parade Night in that year.
  // The previous fixture created the class in years[0] (normally 2026) and the
  // parade night in 2065/2066, which is not a valid same-year user workflow.
  const fixtureYear = 4000 + (Date.now() % 1000);
  const yearRes = await page.request.post(`${base}/api/planning/years`, {
    data: { year: fixtureYear, name: `${fixtureYear} Weekly Program E2E` },
    headers: auth,
  });
  let yearId: string;
  if (yearRes.ok()) {
    yearId = (await yearRes.json()).planning_year_id as string;
    _createdYearIds.push(yearId);
  } else {
    const body = await yearRes.json().catch(() => null);
    if (body?.existing_id) {
      yearId = body.existing_id as string;
    } else {
      const yearsRes = await page.request.get(`${base}/api/planning/years`, { headers: auth });
      expect(yearsRes.ok()).toBe(true);
      const years = await yearsRes.json() as Array<{ year: number; planning_year_id: string }>;
      const existing = years.find((y) => Number(y.year) === fixtureYear);
      expect(existing, `planning year ${fixtureYear} must exist`).toBeTruthy();
      yearId = existing!.planning_year_id;
    }
  }

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
    // stage_code must be supplied so _wpPaint() can match this class to the
    // Senior/Gold column via WP_STAGE_GROUPS codes:['SNR'].  Without it the
    // class is stored with stage_code=null and never appears in the grid.
    data: { training_year_id: yearId, training_stage_id: seniorStage!.phase_id, display_name: className, stage_code: "SNR" },
    headers: auth,
  });
  expect(classRes.ok()).toBe(true);
  const classId = (await classRes.json()).training_class_id as string;
  _createdClassIds.push(classId);

  // Keep the generated date inside the selected planning year; JavaScript date
  // overflow would otherwise move late offsets into the following year.
  const testDate = new Date(fixtureYear, 5, 1 + (Date.now() % 28)).toISOString().slice(0, 10);
  const pnRes = await page.request.post(`${base}/api/parade-nights`, {
    data: { squadron_id: me.session.squadron_id, wing_id: me.session.wing_id, date: testDate, parade_type: "normal" },
    headers: auth,
  });
  expect(pnRes.ok()).toBe(true);
  const pnId = (await pnRes.json()).parade_night_id as string;
  _createdPnIds.push(pnId);

  // The class grid is keyed by timing-block identity, not period_number alone.
  // Resolve the real block from the planner payload just as the connected
  // session editor does, so this fixture represents a linked grid assignment.
  const plannerRes = await page.request.get(`${base}/api/parade-nights/${pnId}/planner`, { headers: auth });
  expect(plannerRes.ok()).toBe(true);
  const planner = await plannerRes.json();
  const firstPeriod = (planner.timing?.instructional_periods ?? [])
    .find((period: { period_number: number }) => period.period_number === 1);
  expect(firstPeriod?.timing_block_id, "period 1 must resolve to a timing block").toBeTruthy();

  const sessRes = await page.request.post(`${base}/api/sessions`, {
    data: {
      parade_night_id: pnId,
      period_number: 1,
      timing_block_id: firstPeriod.timing_block_id,
      cadet_group: "senior",
    },
    headers: auth,
  });
  expect(sessRes.ok()).toBe(true);
  const sid = (await sessRes.json()).session_id as string;

  const audRes = await page.request.put(`${base}/api/sessions/${sid}/audience`, {
    data: { training_class_ids: [classId] }, headers: auth,
  });
  expect(audRes.ok()).toBe(true);

  await selectConnectedPlanningYear(page, yearId);
  await page.evaluate(() => (window as any).nav("weekly-program"));
  await page.waitForLoadState("networkidle");
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

test("Parade Night editor saves multiple assistants and excludes the lead", async ({ page, request }) => {
  await loginSquadron(page, "ADMIN703");
  const token = await page.evaluate(() => sessionStorage.getItem("aafc_token"));
  const base = await apiBase();
  const auth = { Authorization: ["Bearer", token].join(" ") };
  const me = await (await request.get(`${base}/api/auth/me`, { headers: auth })).json();
  const years = await (await request.get(`${base}/api/planning/years`, { headers: auth })).json();
  const year = years.find((row: any) => row.state === "current" && row.active_status)
    || years.find((row: any) => row.active_status);
  expect(year?.planning_year_id).toBeTruthy();
  const classes = await (await request.get(
    `${base}/api/training-classes?training_year_id=${year.planning_year_id}`,
    { headers: auth },
  )).json();
  const trainingClass = classes.find((row: any) => !row.is_archived);
  expect(trainingClass?.training_class_id).toBeTruthy();

  // Parade-night dates are unique per squadron among non-archived nights (409
  // duplicate_date). A clock-derived day collided with seeded/leftover nights on
  // some runs; pick the first December date that GET /api/parade-nights (the
  // non-archived set) does not already use.
  const takenDates = new Set(
    ((await (await request.get(`${base}/api/parade-nights`, { headers: auth })).json()) as Array<{ date?: string }>)
      .map((pn) => String(pn.date || "").slice(0, 10)),
  );
  const testDate = Array.from({ length: 31 }, (_, i) =>
    new Date(Date.UTC(Number(year.year), 11, i + 1)).toISOString().slice(0, 10))
    .find((d) => !takenDates.has(d));
  expect(testDate, `no free December ${year.year} parade-night date for the fixture`).toBeTruthy();
  const pnRes = await request.post(`${base}/api/parade-nights`, {
    data: {
      squadron_id: me.session.squadron_id,
      wing_id: me.session.wing_id,
      date: testDate,
      parade_type: "normal",
    },
    headers: auth,
  });
  expect(pnRes.ok()).toBe(true);
  const pnId = (await pnRes.json()).parade_night_id as string;
  _createdPnIds.push(pnId);

  await selectConnectedPlanningYear(page, year.planning_year_id);
  await page.evaluate(async () => {
    await (window as any).nav("parade-nights");
  });
  await page.evaluate(async (date) => {
    await (window as any).showPNDetail(date);
  }, testDate);

  const facilitatorIds = await page.evaluate("S.facs.map(f => f.id)");
  expect(facilitatorIds.length).toBeGreaterThanOrEqual(3);
  await page.evaluate(async (args: { pnId: string; date: string; classId: string }) => {
    await (window as any)._pnCellClick(args.pnId, args.date, 1, args.classId, null, null);
  }, { pnId, date: testDate, classId: trainingClass.training_class_id });
  const editor = page.locator("#pn-cell-editor");
  await expect(editor).toBeVisible();
  await page.locator("#pce-fa").selectOption(facilitatorIds[0]);
  await expect(page.locator("#pce-fa")).toHaveValue(facilitatorIds[0]);
  const assistants = page.locator("#pce-asst");
  await expect(assistants.locator(`option[value="${facilitatorIds[0]}"]`)).toHaveCount(0);
  await assistants.selectOption([facilitatorIds[1], facilitatorIds[2]]);
  await page.getByRole("button", { name: "Create Session" }).click();
  await expect(editor).toBeHidden();

  const plannerRes = await request.get(`${base}/api/parade-nights/${pnId}/planner`, { headers: auth });
  expect(plannerRes.ok()).toBe(true);
  const planner = await plannerRes.json();
  const plannedSession = planner.sessions.find((row: any) => row.period_number === 1);
  expect(plannedSession).toBeTruthy();
  _createdSessionIds.push(plannedSession.session_id);
  const detailRes = await request.get(`${base}/api/training/sessions/${plannedSession.session_id}`, { headers: auth });
  expect(detailRes.ok()).toBe(true);
  const session = await detailRes.json();
  expect(session.facilitator_id).toBe(facilitatorIds[0]);
  expect(session.assistant_facilitators.map((assistant: any) => assistant.user_id).sort())
    .toEqual([facilitatorIds[1], facilitatorIds[2]].sort());
  expect(session.assistant_facilitators.map((assistant: any) => assistant.user_id))
    .not.toContain(session.facilitator_id);
  await expect(page.getByRole("cell", { name: /Status: Planned/ }).first()).toBeVisible();
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
  const years = await (await page.request.get(`${base}/api/planning/years`, { headers: auth })).json();
  const year = years.find((y: any) => y.state === "current") || years[0];
  const testDate = new Date(Number(year.year), 0, 15).toISOString().slice(0, 10);
  const pnRes = await page.request.post(`${base}/api/parade-nights`, {
    data: { squadron_id: me.session.squadron_id, wing_id: me.session.wing_id, date: testDate, parade_type: "normal" },
    headers: auth,
  });
  expect(pnRes.ok()).toBe(true);
  if (pnRes.ok()) _createdPnIds.push((await pnRes.json()).parade_night_id as string);

  await selectConnectedPlanningYear(page, year.planning_year_id);
  await page.evaluate(() => (window as any).reloadAndRender());
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
test("Weekly Program header resolves the Wing name from the scoped Squadron", async ({ page }) => {
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
  const years = await (await page.request.get(`${base}/api/planning/years`, { headers: auth })).json();
  const year = years.find((y: any) => y.state === "current") || years[0];
  const testDate = new Date(Number(year.year), 4, 21).toISOString().slice(0, 10);
  const pnRes = await page.request.post(`${base}/api/parade-nights`, {
    data: { squadron_id: me.session.squadron_id, wing_id: me.session.wing_id, date: testDate, parade_type: "normal" },
    headers: auth,
  });
  expect(pnRes.ok()).toBe(true);
  if (pnRes.ok()) _createdPnIds.push((await pnRes.json()).parade_night_id as string);

  await selectConnectedPlanningYear(page, year.planning_year_id);
  await page.evaluate(() => (window as any).reloadAndRender());
  const scopedSquadron = {
    squadron_id: me.session.squadron_id,
    wing_id: me.session.wing_id,
    wing_name: wingName,
  };
  await page.evaluate(
    `S.session.wing_name = null; S.currentSqnId = ${JSON.stringify(scopedSquadron.squadron_id)}; S.squadrons = [${JSON.stringify(scopedSquadron)}];`,
  );
  await page.evaluate(() => (window as any).nav("weekly-program"));
  await expect(page.locator("#wp-sel")).toBeVisible({ timeout: 8000 });
  await page.locator("#wp-f-term").selectOption("all");
  const exactNight = page.locator(`#wp-sel option[value="${testDate}"]`);
  await expect(exactNight).toHaveCount(1, { timeout: 8000 });
  await page.locator("#wp-sel").selectOption({ value: testDate });

  // DEF-06: base session has no wing name; effective squadron data supplies it.
  // The name is appended after the squadron name with an em-dash separator.
  const header = page.locator("#wp-content .night-sqn").first();
  await expect(header).toBeVisible({ timeout: 5000 });
  await expect(header).toContainText(wingName);

  // Guard: must NOT contain the old hardcoded string.
  const headerText = await header.textContent();
  expect(headerText).not.toContain("7 Wing Australian Air Force Cadets");

  expect(errors, `no uncaught JS errors: ${errors.join("; ")}`).toHaveLength(0);
});