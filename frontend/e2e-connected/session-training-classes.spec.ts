import { test, expect, Page, firstFreeParadeDate } from "../e2e-fixtures";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";
import { selectConnectedPlanningYear } from "./year-context-helper";

// ── Session <-> Training Class audience UI (CLASS-03's first frontend
// consumer), wired into the real, live "Quick Edit" session flow
// (quickEdit()/saveSessEdit()/#m-sess-edit, reached from the Parade Nights
// page's card view via buildPNCard()'s own Edit button). A separate,
// similarly-named modal/function family (#m-edit-session, doSaveSession(),
// openEditSessionModalPn() and friends) was investigated first and found to
// have NO reachable trigger anywhere in the rendered page -- its target
// containers (#builder-card/#builder-grid) do not exist in any static or
// dynamically-inserted HTML in this file. Building into that would have
// delivered zero real capability; this suite verifies the real integration
// point instead.
//
// Real browser verification via this repo's own Playwright suite -- see
// training-classes.spec.ts's header comment for why (Claude-in-Chrome
// extension not available in this environment).

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

// IDs of resources created during this run — cleaned up in afterAll.
const _createdPnIds: string[] = [];
const _createdClassIds: string[] = [];
// Only years this file actually created (not ones reused via 409 existing_id).
const _createdYearIds: string[] = [];

// This file performs several setup/read/write API calls in every test. The
// development/test general limiter is process-wide, so reset per test rather
// than once per file; otherwise later cases can fail based on execution order
// instead of product behaviour.
test.beforeEach(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");
});

test.afterAll(async ({ request }) => {
  const base = process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000";
  await resetBackendRateLimits(base);
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
  const ok = (r: { status(): number }, what: string) =>
    expect([200, 204, 404], `cleanup ${what} -> ${r.status()}`).toContain(r.status());

  // Archive parade nights first (also archives their sessions).
  for (const pnId of _createdPnIds) {
    ok(await request.delete(`${base}/api/parade-nights/${pnId}`, { headers: auth }), `parade night ${pnId}`);
  }
  // Archive training classes.
  for (const classId of _createdClassIds) {
    ok(await request.delete(`${base}/api/training-classes/${classId}`, { headers: auth }), `training class ${classId}`);
  }
  // Deactivate (not delete: archived dependents block deletion) every year this
  // file created. The fixture year is randomised per test, so leaving them
  // active accumulated one active year per test across runs; Main TMS boot
  // fetches holidays per active year, and that growth tripped the API rate
  // limiter in later tests (silent 429 -> hidden Quick Edit class list).
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

// Creates a real Training Class (year is incidental -- the picker shows
// every active class for the squadron regardless of year) and a real Parade
// Night + Session. Returns what a test needs to reach the Session via the
// real Parade Nights page.
async function seedClassAndSession(page: Page, token: string, uniqueSuffix: string) {
  const base = await apiBase();
  const fixtureYear = 3000 + (Date.now() % 1000);
  const auth = { Authorization: `Bearer ${token}` };

  const yearRes = await page.request.post(`${base}/api/planning/years`, {
    data: { year: fixtureYear, name: `Session-Class Test Year ${uniqueSuffix}` },
    headers: auth,
  });
  let yearId: string;
  if (yearRes.ok()) {
    yearId = (await yearRes.json()).planning_year_id as string;
    _createdYearIds.push(yearId);
  } else {
    // 409 includes existing_id when year already exists — use it directly.
    const errBody = await yearRes.json().catch(() => null);
    if (errBody?.existing_id) {
      yearId = errBody.existing_id as string;
    } else {
      const yearsResp = await page.request.get(`${base}/api/planning/years`, { headers: auth });
      const years = await yearsResp.json();
      const yearsArr = Array.isArray(years) ? years : [];
      const existing = yearsArr.find((y: any) => y.year === fixtureYear);
      if (!existing) throw new Error(`Could not create or find planning year: ${JSON.stringify(errBody)}`);
      yearId = existing.planning_year_id;
    }
  }

  const phases = await (await page.request.get(`${base}/api/curriculum/phases`, { headers: auth })).json();
  const stageId = (phases.find((p: any) => p.name === "E. Senior") || phases[0]).phase_id as string;

  const className = `E2E Session Class ${uniqueSuffix}`;
  const classRes = await page.request.post(`${base}/api/training-classes`, {
    data: { training_year_id: yearId, training_stage_id: stageId, display_name: className },
    headers: auth,
  });
  expect(classRes.ok()).toBe(true);
  const classId = (await classRes.json()).training_class_id as string;
  _createdClassIds.push(classId);

  const me = await (await page.request.get(`${base}/api/auth/me`, { headers: auth })).json();
  const testDate = await firstFreeParadeDate(page.request, base, auth, `${fixtureYear}-06-01`, `${fixtureYear}-06-30`);
  const marker = `E2E-MARKER-${uniqueSuffix}`;
  const pnRes = await page.request.post(`${base}/api/parade-nights`, {
    data: { squadron_id: me.session.squadron_id, wing_id: me.session.wing_id, date: testDate, parade_type: "normal" },
    headers: auth,
  });
  expect(pnRes.ok()).toBe(true);
  const pnId = (await pnRes.json()).parade_night_id as string;
  _createdPnIds.push(pnId);
  // The backend auto-assigns a timing template. Strip it so fixture parade
  // nights behave as "legacy timing" (no template) — required for the
  // CLASS-17 "Legacy timing" assertion and consistent with the original test
  // intent of testing untemplateed nights.
  await page.request.patch(`${base}/api/parade-nights/${pnId}`, {
    data: { timing_template_id: null },
    headers: auth,
  });
  const noteRes = await page.request.patch(`${base}/api/parade-nights/${pnId}`, {
    data: { notes: marker }, headers: auth,
  });
  expect(noteRes.ok()).toBe(true);

  const sessRes = await page.request.post(`${base}/api/sessions`, {
    data: { parade_night_id: pnId, period_number: 1 },
    headers: auth,
  });
  expect(sessRes.ok()).toBe(true);

  return { className, marker, fixtureYear: yearId };
}

async function openQuickEditForFirstSession(page: Page, marker: string, planningYearId: string) {
  // nav('parade-nights') is async and awaits its own single reloadAndRender()
  // (loadData + renderAll, serialised through _reloadRenderPromise). Return its
  // promise so evaluate() waits for the load AND render to finish. The previous
  // version discarded the promise and waited on networkidle, which never waits
  // in this SPA (no navigation happens): the in-flight reload could re-render the
  // Parade Night list mid-click, so the "Edit Session 1" click never landed and
  // #m-sess-edit stayed hidden (CI Firefox, 2026-09-28). Do not add extra
  // reloadAndRender() calls here -- overlapping cycles trip the rate limiter.
  await page.evaluate(() => (window as any).nav("parade-nights"));
  await page.evaluate(() => {
    for (const [id, value] of [["pn-f-term", "all"], ["pn-f-status", "all"], ["pn-search", ""]] as const) {
      const el = document.getElementById(id) as HTMLInputElement | HTMLSelectElement | null;
      if (el) el.value = value;
    }
    (window as any).renderPN();
  });
  const card = page.locator(".pn-card").filter({ hasText: marker });
  await expect(card).toBeVisible({ timeout: 8000 });
  const editBtn = card.getByRole("button", { name: "Edit Session 1" });
  await expect(editBtn).toBeVisible();
  await editBtn.click();
  await expect(page.locator("#m-sess-edit")).toBeVisible();
}

test.describe("Session <-> Training Class assignment via Quick Edit", () => {
  test("the checklist appears, shows the real Training Class, and saving persists the selection", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await loginSquadron(page, "ADMIN703");
    const token = await page.evaluate(() => (window as any).tokenGet?.() ?? sessionStorage.getItem("aafc_token"));
    const suffix = String(Date.now());
    const { className, marker, fixtureYear } = await seedClassAndSession(page, token, suffix);

    await openQuickEditForFirstSession(page, marker, fixtureYear);
    const classesGroup = page.locator("#qe-classes-group");
    await expect(classesGroup).toBeVisible({ timeout: 8000 });
    const checkbox = page.locator("#qe-classes-list label").filter({ hasText: className });
    await expect(checkbox).toBeVisible();
    await expect(checkbox.locator("input.qe-class-chk")).not.toBeChecked();

    await checkbox.locator("input.qe-class-chk").check();
    await page.getByRole("button", { name: "Save" }).click();
    await expect(page.locator("#m-sess-edit")).toBeHidden({ timeout: 8000 });

    await openQuickEditForFirstSession(page, marker, fixtureYear);
    await expect(page.locator("#qe-classes-group")).toBeVisible({ timeout: 8000 });
    const reopened = page.locator("#qe-classes-list label").filter({ hasText: className });
    await expect(reopened.locator("input.qe-class-chk")).toBeChecked();

    expect(errors, `no uncaught JS errors: ${errors.join("; ")}`).toHaveLength(0);
  });

  test("unchecking and saving clears the assignment", async ({ page }) => {
    await loginSquadron(page, "ADMIN703");
    const token = await page.evaluate(() => (window as any).tokenGet?.() ?? sessionStorage.getItem("aafc_token"));
    const suffix = String(Date.now()) + "b";
    const { className, marker, fixtureYear } = await seedClassAndSession(page, token, suffix);

    await openQuickEditForFirstSession(page, marker, fixtureYear);
    await expect(page.locator("#qe-classes-group")).toBeVisible({ timeout: 8000 });
    const checkbox = page.locator("#qe-classes-list label").filter({ hasText: className });
    await checkbox.locator("input.qe-class-chk").check();
    await page.getByRole("button", { name: "Save" }).click();
    await expect(page.locator("#m-sess-edit")).toBeHidden({ timeout: 8000 });

    await openQuickEditForFirstSession(page, marker, fixtureYear);
    await expect(page.locator("#qe-classes-group")).toBeVisible({ timeout: 8000 });
    const reopened = page.locator("#qe-classes-list label").filter({ hasText: className });
    await expect(reopened.locator("input.qe-class-chk")).toBeChecked();
    await reopened.locator("input.qe-class-chk").uncheck();
    await page.getByRole("button", { name: "Save" }).click();
    await expect(page.locator("#m-sess-edit")).toBeHidden({ timeout: 8000 });

    await openQuickEditForFirstSession(page, marker, fixtureYear);
    await expect(page.locator("#qe-classes-group")).toBeVisible({ timeout: 8000 });
    const finalCheckbox = page.locator("#qe-classes-list label").filter({ hasText: className });
    await expect(finalCheckbox.locator("input.qe-class-chk")).not.toBeChecked();
  });

  test("sqn_general (read-only) sees Quick Edit as disabled / not writable", async ({ page }) => {
    const base = await apiBase();
    const lookup = await page.request.post(`${base}/api/auth/lookup`, {
      data: { unit_type: "squadron", identifier: "703", role: "sqn_admin" },
    });
    const userId = (await lookup.json()).user_id as string;
    const loginRes = await page.request.post(`${base}/api/auth/login`, {
      data: { code: "ADMIN703", user_id: userId },
    });
    const loginBody = await loginRes.json();
    const token = loginBody.token || loginBody.access_token;
    const suffix = String(Date.now()) + "c";
    const { marker, fixtureYear } = await seedClassAndSession(page, token, suffix);

    if (LOCAL_API_BASE) {
      await page.addInitScript((base) => {
        (window as any).AAFC_API_BASE = base;
      }, LOCAL_API_BASE);
    }
    await page.goto("/");
    await page.locator("#auth-type").selectOption("squadron");
    await page.locator("#auth-wing-select").selectOption("7WG");
    await page.locator("#auth-sqn-select").selectOption("703");
    await page.locator("#auth-role").selectOption("sqn_general");
    await page.locator("#auth-continue-btn").click();
    await page.locator("#auth-code").fill("703SQN2026");
    await page.locator("#auth-btn").click();
    await expect(page.locator(".ph-title", { hasText: "Training Dashboard" })).toBeVisible({ timeout: 10000 });

    await selectConnectedPlanningYear(page, fixtureYear);
    await page.evaluate("nav('parade-nights')");
    await page.evaluate("reloadAndRender()");
    await page.evaluate("document.getElementById('pn-f-term').value='all'; document.getElementById('pn-f-status').value='all'; document.getElementById('pn-search').value=''; renderPN()");
    const card = page.locator(".pn-card").filter({ hasText: marker });
    await expect(card).toBeVisible({ timeout: 8000 });
    await expect(card.getByRole("button", { name: "Edit Session 1" })).toHaveCount(0);
  });
});

// CLASS-17 (assignment via the Parade Night detail modal) was removed here: the
// detail modal no longer hosts Training Class checkboxes (#pnd-classes-*) since the
// September Parade Night detail rewrite. The capability survives in Quick Edit and
// is covered by "Session <-> Training Class assignment via Quick Edit" above.

test.describe("Training Class name in compact session card (CLASS-18)", () => {
  test("assigned class name appears in the .sess-info line of the parade night card", async ({ page }) => {
    await loginSquadron(page, "ADMIN703");
    const token = await page.evaluate(() => (window as any).tokenGet?.() ?? sessionStorage.getItem("aafc_token"));
    const suffix = String(Date.now()) + "card";
    const { className, marker, fixtureYear } = await seedClassAndSession(page, token, suffix);

    await openQuickEditForFirstSession(page, marker, fixtureYear);
    const cb = page.locator("#qe-classes-list label").filter({ hasText: className }).locator("input.qe-class-chk");
    await cb.check();
    await page.getByRole("button", { name: "Save" }).click();
    await expect(page.locator("#m-sess-edit")).toBeHidden({ timeout: 8000 });

    await page.evaluate(() => (window as any).reloadAndRender());
    await selectConnectedPlanningYear(page, fixtureYear);
    await page.evaluate("nav('parade-nights')");
    const card = page.locator(".pn-card").filter({ hasText: marker });
    const sessInfo = card.locator(".sess-info").first();
    await expect(sessInfo).toContainText(className, { timeout: 8000 });
  });
});