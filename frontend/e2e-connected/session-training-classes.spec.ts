import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

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

// Creates a real Training Class (year is incidental -- the picker shows
// every active class for the squadron regardless of year) and a real Parade
// Night + Session. Returns what a test needs to reach the Session via the
// real Parade Nights page.
async function seedClassAndSession(page: Page, token: string, uniqueSuffix: string) {
  const base = await apiBase();
  const auth = { Authorization: `Bearer ${token}` };

  const yearRes = await page.request.post(`${base}/api/planning/years`, {
    data: { year: 2064, name: `2064 Session-Class Test Year ${uniqueSuffix}` },
    headers: auth,
  });
  let yearId: string;
  if (yearRes.ok()) {
    yearId = (await yearRes.json()).planning_year_id as string;
  } else {
    const years = await (await page.request.get(`${base}/api/planning/years`, { headers: auth })).json();
    const existing = years.find((y: any) => y.year === 2064);
    if (!existing) throw new Error(`Could not create or find 2064 planning year: ${await yearRes.text()}`);
    yearId = existing.planning_year_id;
  }

  const phases = await (await page.request.get(`${base}/api/curriculum/phases`, { headers: auth })).json();
  const stageId = (phases.find((p: any) => p.name === "E. Senior") || phases[0]).phase_id as string;

  const className = `E2E Session Class ${uniqueSuffix}`;
  const classRes = await page.request.post(`${base}/api/training-classes`, {
    data: { training_year_id: yearId, training_stage_id: stageId, display_name: className },
    headers: auth,
  });
  expect(classRes.ok()).toBe(true);

  const me = await (await page.request.get(`${base}/api/auth/me`, { headers: auth })).json();
  const testDate = new Date(2065, 5, 1 + (Date.now() % 300)).toISOString().slice(0, 10);
  const marker = `E2E-MARKER-${uniqueSuffix}`;
  const pnRes = await page.request.post(`${base}/api/parade-nights`, {
    data: { squadron_id: me.session.squadron_id, wing_id: me.session.wing_id, date: testDate, parade_type: "normal" },
    headers: auth,
  });
  expect(pnRes.ok()).toBe(true);
  const pnId = (await pnRes.json()).parade_night_id as string;
  // buildPNCard renders pn.notes in its header (.pn-meta) -- a unique marker
  // there lets the test locate exactly this card in the list, rather than
  // relying on date-formatting or list-ordering assumptions that would be
  // fragile against a persistent (non-reseeded) backend or parallel test runs.
  const noteRes = await page.request.patch(`${base}/api/parade-nights/${pnId}`, {
    data: { notes: marker }, headers: auth,
  });
  expect(noteRes.ok()).toBe(true);

  const sessRes = await page.request.post(`${base}/api/sessions`, {
    data: { parade_night_id: pnId, period_number: 1 },
    headers: auth,
  });
  expect(sessRes.ok()).toBe(true);

  return { className, marker };
}

async function openQuickEditForFirstSession(page: Page, marker: string) {
  await page.evaluate(() => (window as any).reloadAndRender());
  await page.evaluate(() => (window as any).nav("parade-nights"));
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
    const { className, marker } = await seedClassAndSession(page, token, suffix);

    await openQuickEditForFirstSession(page, marker);
    const classesGroup = page.locator("#qe-classes-group");
    await expect(classesGroup).toBeVisible({ timeout: 8000 });
    const checkbox = page.locator("#qe-classes-list label").filter({ hasText: className });
    await expect(checkbox).toBeVisible();
    await expect(checkbox.locator("input.qe-class-chk")).not.toBeChecked();

    await checkbox.locator("input.qe-class-chk").check();
    await page.getByRole("button", { name: "Save" }).click();
    await expect(page.locator("#m-sess-edit")).toBeHidden({ timeout: 8000 });

    // Re-open and confirm the checkbox is now pre-checked -- proves the PUT
    // .../audience call actually persisted, not just that the UI accepted
    // the click.
    await openQuickEditForFirstSession(page, marker);
    await expect(page.locator("#qe-classes-group")).toBeVisible({ timeout: 8000 });
    const reopened = page.locator("#qe-classes-list label").filter({ hasText: className });
    await expect(reopened.locator("input.qe-class-chk")).toBeChecked();

    expect(errors, `no uncaught JS errors: ${errors.join("; ")}`).toHaveLength(0);
  });

  test("unchecking and saving clears the assignment", async ({ page }) => {
    await loginSquadron(page, "ADMIN703");
    const token = await page.evaluate(() => (window as any).tokenGet?.() ?? sessionStorage.getItem("aafc_token"));
    const suffix = String(Date.now()) + "b";
    const { className, marker } = await seedClassAndSession(page, token, suffix);

    await openQuickEditForFirstSession(page, marker);
    await expect(page.locator("#qe-classes-group")).toBeVisible({ timeout: 8000 });
    const checkbox = page.locator("#qe-classes-list label").filter({ hasText: className });
    await checkbox.locator("input.qe-class-chk").check();
    await page.getByRole("button", { name: "Save" }).click();
    await expect(page.locator("#m-sess-edit")).toBeHidden({ timeout: 8000 });

    await openQuickEditForFirstSession(page, marker);
    await expect(page.locator("#qe-classes-group")).toBeVisible({ timeout: 8000 });
    const reopened = page.locator("#qe-classes-list label").filter({ hasText: className });
    await expect(reopened.locator("input.qe-class-chk")).toBeChecked();
    await reopened.locator("input.qe-class-chk").uncheck();
    await page.getByRole("button", { name: "Save" }).click();
    await expect(page.locator("#m-sess-edit")).toBeHidden({ timeout: 8000 });

    await openQuickEditForFirstSession(page, marker);
    await expect(page.locator("#qe-classes-group")).toBeVisible({ timeout: 8000 });
    const finalCheckbox = page.locator("#qe-classes-list label").filter({ hasText: className });
    await expect(finalCheckbox.locator("input.qe-class-chk")).not.toBeChecked();
  });

  test("sqn_general (read-only) sees Quick Edit as disabled / not writable", async ({ page }) => {
    // Seed via a direct API token (never a real UI login as ADMIN703 on this
    // page) so the one real UI login this test performs -- as sqn_general --
    // starts from a page with no admin session already in sessionStorage.
    // A prior version of this test called loginSquadron(page, "ADMIN703")
    // first, then re-navigated to "/" and tried to log in again as
    // sqn_general on the SAME page; sessionStorage still held the admin
    // token, so the app auto-resumed the admin session instead of showing
    // a fresh login form, and the login-form selectors below timed out
    // waiting for elements that existed but were hidden behind the
    // already-authenticated Dashboard.
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
    await seedClassAndSession(page, token, suffix);

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

    await page.evaluate(() => (window as any).nav("parade-nights"));
    // canWriteSquadron() gates the Edit (quickEdit) button entirely for a
    // read-only role -- confirms this Session's audience cannot be changed
    // by sqn_general through the UI, matching every other write control in
    // this file.
    await expect(page.getByRole("button", { name: "Edit Session 1" })).toHaveCount(0);
  });
});
