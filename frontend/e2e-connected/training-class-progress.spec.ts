import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// CLASS-04 dedicated UI: the Training Classes card on the Activities page
// gains a "Curriculum Progress" coverage pill per class (via the existing
// stage-level GET /api/curriculum/phases/{id}/class-progress endpoint) and
// a "View Progress" button opening a detail modal listing every
// requirement's own status (via GET /api/training-classes/{id}/curriculum-progress).
// Both reuse CLASS-04/07's existing _class_curriculum_progress computation
// -- no new backend calculation, addendum §44.

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

test.beforeAll(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");
});

// A pure Date.now()-derived offset (the pattern used elsewhere in this
// directory, e.g. session-training-classes.spec.ts) collided in practice
// here, twice: first because this file's own two tests seed a parade night
// a couple of seconds apart (fixed below with an in-process counter, which
// guarantees uniqueness *within* one run), and again because Date.now() % 300
// only has 300 possible values -- separate manual re-runs of this file a
// few seconds to minutes apart (as done repeatedly while developing this
// test) landed on the same value across *different* process invocations,
// where the in-process counter resets to 0 and can't help. A ~3000-value
// range (~8 years of distinct dates) makes that second kind of collision
// negligible without needing cross-run persisted state.
let _dayCounter = 0;

async function selectFirstYear(page: Page): Promise<string> {
  const yearSelect = page.locator("#py-select");
  await expect(yearSelect).toBeVisible();
  let firstRealValue = "";
  await expect(async () => {
    const options = await yearSelect.locator("option").all();
    expect(options.length).toBeGreaterThan(1);
    firstRealValue = (await options[1].getAttribute("value")) || "";
    expect(firstRealValue).not.toBe("");
  }).toPass({ timeout: 8000 });
  await yearSelect.selectOption(firstRealValue);
  await page.waitForTimeout(600);
  return firstRealValue;
}

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

// Seeds: a squadron-scoped Training Stage with 2 curriculum items, a
// Training Class, and one delivered Session (audience-linked to the class)
// against one of the two items -- giving a real, checkable 50% coverage.
async function seedHalfDeliveredClass(page: Page, token: string, yearId: string, suffix: string) {
  const base = await apiBase();
  const auth = { Authorization: `Bearer ${token}` };

  const stageName = `CLASS-04-UI-${suffix}`;
  const me = await (await page.request.get(`${base}/api/auth/me`, { headers: auth })).json();
  const sqnId = me.session.squadron_id as string;
  const wingId = me.session.wing_id as string;

  const stageRes = await page.request.post(`${base}/api/curriculum/phases`, {
    data: { name: stageName, display_name: stageName, scope_level: "squadron", squadron_id: sqnId },
    headers: auth,
  });
  expect(stageRes.ok()).toBe(true);
  const stageId = (await stageRes.json()).phase_id as string;

  const className = `CLASS-04 UI Test Class ${suffix}`;
  const classRes = await page.request.post(`${base}/api/training-classes`, {
    data: { training_year_id: yearId, training_stage_id: stageId, display_name: className },
    headers: auth,
  });
  expect(classRes.ok()).toBe(true);
  const classId = (await classRes.json()).training_class_id as string;

  const item1Res = await page.request.post(`${base}/api/curriculum`, {
    data: { code: `C04A${suffix.slice(-5)}`, title: "Delivered Item", phase: stageName,
            learning_hub_url: "https://example.invalid/c04-ui-test" },
    headers: auth,
  });
  expect(item1Res.ok()).toBe(true);
  const item1Id = (await item1Res.json()).curriculum_id as string;

  const item2Res = await page.request.post(`${base}/api/curriculum`, {
    data: { code: `C04B${suffix.slice(-5)}`, title: "Not Started Item", phase: stageName,
            learning_hub_url: "https://example.invalid/c04-ui-test" },
    headers: auth,
  });
  expect(item2Res.ok()).toBe(true);
  const item2Title = "Not Started Item"; // POST /api/curriculum doesn't echo the title back

  const dayOffset = (_dayCounter++) * 5 + (Date.now() % 3000);
  const testDate = new Date(2065, 8, 1 + dayOffset).toISOString().slice(0, 10);
  const pnRes = await page.request.post(`${base}/api/parade-nights`, {
    data: { squadron_id: sqnId, wing_id: wingId, date: testDate, parade_type: "normal" },
    headers: auth,
  });
  expect(pnRes.ok()).toBe(true);
  const pnId = (await pnRes.json()).parade_night_id as string;

  const sessRes = await page.request.post(`${base}/api/sessions`, {
    data: { parade_night_id: pnId, period_number: 1, cadet_group: "senior", curriculum_item_id: item1Id },
    headers: auth,
  });
  expect(sessRes.ok()).toBe(true);
  const sid = (await sessRes.json()).session_id as string;

  const editRes = await page.request.put(`${base}/api/sessions/${sid}`, {
    data: { parade_night_id: pnId, period_number: 1, cadet_group: "senior",
            curriculum_item_id: item1Id, status: "delivered" },
    headers: auth,
  });
  expect(editRes.ok()).toBe(true);

  const audRes = await page.request.put(`${base}/api/sessions/${sid}/audience`, {
    data: { training_class_ids: [classId] }, headers: auth,
  });
  expect(audRes.ok()).toBe(true);

  return { className, classId, item2Title };
}

test.describe("Training Class curriculum progress UI (CLASS-04 dedicated UI)", () => {
  test("class row shows a real coverage percentage pill, and View Progress opens the requirement detail", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await loginSquadron(page, "ADMIN703");
    const token = await page.evaluate(() => (window as any).tokenGet?.() ?? sessionStorage.getItem("aafc_token"));
    const suffix = String(Date.now());

    await page.evaluate(() => (window as any).nav("activities"));
    const yearId = await selectFirstYear(page);

    const { className, item2Title } = await seedHalfDeliveredClass(page, token, yearId, suffix);

    // Re-select the year to force a fresh render including the new class.
    await page.locator("#py-select").selectOption(yearId);
    await page.waitForTimeout(600);

    const row = page.locator("#py-classes-body tr", { hasText: className });
    await expect(row).toBeVisible({ timeout: 8000 });
    await expect(row).toContainText("50%");

    await row.getByRole("button", { name: "View Progress" }).click();
    const modal = page.locator("#m-training-class-progress");
    await expect(modal).toBeVisible({ timeout: 5000 });
    await expect(modal.locator("#tcp-title")).toContainText(className);
    await expect(modal).toContainText("1 of 2 requirements delivered");
    await expect(modal).toContainText(item2Title);
    // Badge text content is lowercase ("not started"); CSS text-transform:
    // capitalize only affects rendering, not the actual DOM text content.
    await expect(modal.locator("#tcp-body")).toContainText("not started");

    await modal.getByRole("button", { name: "Close" }).click();
    await expect(modal).toBeHidden({ timeout: 5000 });

    expect(errors, `no uncaught JS errors: ${errors.join("; ")}`).toHaveLength(0);
  });

  test("sqn_general (read-only) can view progress but sees no write controls in the same row", async ({ page }) => {
    // Seed via a direct API token (never a real UI login as ADMIN703 on this
    // page) so the one real UI login this test performs -- as sqn_general --
    // starts from a page with no admin session already in sessionStorage.
    // See session-training-classes.spec.ts's own equivalent test for the
    // exact bug this avoids: a prior admin UI login leaves sessionStorage
    // holding the admin token, so a later re-login as a different role on
    // the same page silently auto-resumes the admin session instead of
    // showing a fresh login form.
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
    const suffix = String(Date.now()) + "b";

    const yearsRes = await page.request.get(`${base}/api/planning/years`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const yearId = (await yearsRes.json())[0].planning_year_id as string;
    const { className } = await seedHalfDeliveredClass(page, token, yearId, suffix);

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

    await page.evaluate(() => (window as any).nav("activities"));
    await selectFirstYear(page);
    const row = page.locator("#py-classes-body tr", { hasText: className });
    await expect(row).toBeVisible({ timeout: 8000 });
    await expect(row.getByRole("button", { name: "View Progress" })).toBeVisible();
    await expect(row.getByRole("button", { name: "Edit" })).toHaveCount(0);
    await expect(row.getByRole("button", { name: "Archive" })).toHaveCount(0);

    await row.getByRole("button", { name: "View Progress" }).click();
    await expect(page.locator("#m-training-class-progress")).toBeVisible({ timeout: 5000 });
  });
});
