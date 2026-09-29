import { test, expect, Page, firstFreeParadeDate } from "../e2e-fixtures";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";
import { selectConnectedPlanningYear } from "./year-context-helper";

// REM-23 continuation: #or-reason (the "reason required" modal shown when a
// session's status changes to cancelled/not_delivered/delivered_with_issue)
// used to be a hardcoded <option> list. It's now API-driven from
// /api/session-status-reason-tags -- the same governed reference-data
// pattern already proven for Subject Area and Facilitator Type -- with an
// inline "+ Add new reason…" affordance mirroring #fac-type's own.
//
// Reached via the real Quick Edit flow (quickEdit()/saveSessEdit()/
// #m-sess-edit), same integration point session-training-classes.spec.ts
// already established as the real, reachable one.

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;
const base = LOCAL_API_BASE || "http://localhost:8000";
const _createdPnIds: string[] = [];
// Only years this file actually created (not ones reused via 409 existing_id).
const _createdYearIds: string[] = [];

test.beforeEach(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");
});

test.afterAll(async ({ request }) => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");
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
  const hdr = { Authorization: `Bearer ${body.token || body.access_token}` };
  const ok = (r: { status(): number }, what: string) =>
    expect([200, 204, 404], `cleanup ${what} -> ${r.status()}`).toContain(r.status());
  for (const pnId of _createdPnIds) {
    ok(await request.delete(`${base}/api/parade-nights/${pnId}`, { headers: hdr }), `parade night ${pnId}`);
  }
  // Deactivate (not delete: dependents block deletion) every fixture year this
  // file created -- exact IDs only, never a broad "year >= N" sweep.
  for (const yearId of _createdYearIds) {
    const cur = await request.get(`${base}/api/planning/years/${yearId}`, { headers: hdr });
    ok(cur, `year lookup ${yearId}`);
    if (!cur.ok()) continue;
    ok(await request.patch(`${base}/api/planning/years/${yearId}`, {
      data: { active_status: false, version: (await cur.json()).version }, headers: hdr,
    }), `year deactivate ${yearId}`);
  }
});

async function loginSquadron(page: Page, code: string) {
  if (LOCAL_API_BASE) {
    await page.addInitScript((b) => { (window as any).AAFC_API_BASE = b; }, LOCAL_API_BASE);
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

async function seedSession(page: Page, hdr: Record<string, string>, uniqueSuffix: string) {
  const me = await (await page.request.get(`${base}/api/auth/me`, { headers: hdr })).json();
  const fixtureYear = 3000 + (Date.now() % 1000);
  const yearRes = await page.request.post(`${base}/api/planning/years`, {
    data: { year: fixtureYear, name: `${fixtureYear} Reason E2E ${uniqueSuffix}` },
    headers: hdr,
  });
  expect(yearRes.ok() || yearRes.status() === 409).toBe(true);
  const yearBody = await yearRes.json().catch(() => ({}));
  const planningYearId = (yearBody.planning_year_id || yearBody.existing_id) as string;
  if (yearRes.ok()) _createdYearIds.push(planningYearId);
  const testDate = await firstFreeParadeDate(page.request, base, hdr, `${fixtureYear}-01-01`, `${fixtureYear}-10-27`);
  const marker = `E2E-REASON-MARKER-${uniqueSuffix}`;
  const pnRes = await page.request.post(`${base}/api/parade-nights`, {
    data: { squadron_id: me.session.squadron_id, wing_id: me.session.wing_id, date: testDate, parade_type: "normal" },
    headers: hdr,
  });
  expect(pnRes.ok()).toBe(true);
  const pnId = (await pnRes.json()).parade_night_id as string;
  _createdPnIds.push(pnId);
  await page.request.patch(`${base}/api/parade-nights/${pnId}`, { data: { notes: marker }, headers: hdr });
  const sessRes = await page.request.post(`${base}/api/sessions`, {
    data: { parade_night_id: pnId, period_number: 1 }, headers: hdr,
  });
  expect(sessRes.ok()).toBe(true);
  return { marker, fixtureYear: planningYearId };
}

async function openQuickEditForFirstSession(page: Page, marker: string, planningYearId: string) {
  const backendBase = process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000";
  await page.evaluate(() => (window as any).reloadAndRender());
  await selectConnectedPlanningYear(page, planningYearId);
  // Reset before nav('parade-nights'): nav() calls reloadAndRender() for this
  // page (index.html line 6358), so a separate explicit reloadAndRender() after
  // it would double the burst. Reset here to give the single nav-reload a fresh
  // budget, keeping the combined count well under the 300 req/60s ceiling.
  await resetBackendRateLimits(backendBase);
  await page.evaluate("nav('parade-nights')");
  // nav('parade-nights') already calls reloadAndRender() — no second call needed.
  await page.evaluate("document.getElementById('pn-f-term').value='all'; document.getElementById('pn-f-status').value='all'; document.getElementById('pn-search').value=''; renderPN()");
  await expect.poll(() => page.locator(".pn-card").count(), { timeout: 10000 }).toBeGreaterThan(0);
  const card = page.locator(".pn-card").filter({ hasText: marker });
  await expect(card).toBeVisible({ timeout: 8000 });
  const editBtn = card.getByRole("button", { name: "Edit Session 1" });
  await expect(editBtn).toBeVisible();
  await editBtn.click();
  await expect(page.locator("#m-sess-edit")).toBeVisible();
  // Reset after loadSessEdit() so the test's save/create API calls
  // (saveSessEdit PATCH, POST session-status-reason-tags) have a fresh budget.
  await resetBackendRateLimits(backendBase);
}

test.describe("Session Status Reason tags (REM-23 continuation)", () => {
  test("changing status to Cancelled opens the reason modal with the real governed reason list", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await loginSquadron(page, "ADMIN703");
    const hdr = { Authorization: `Bearer ${await page.evaluate(() => sessionStorage.getItem("aafc_token"))}` };
    const { marker, fixtureYear } = await seedSession(page, hdr, String(Date.now()));

    // seedSession makes 5+ direct API calls and loginSquadron makes several more.
    // Reset here so loadData()'s /api/session-status-reason-tags request succeeds
    // inside openQuickEditForFirstSession's reloadAndRender() calls.
    await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");

    await openQuickEditForFirstSession(page, marker, fixtureYear);
    await page.locator("#qe-st").selectOption("cancelled");
    // The reason modal only opens as a blocking sub-step of saveSessEdit()
    // (see collectOutcomeReason()'s call site) -- not immediately on
    // changing the status select.
    await page.getByRole("button", { name: "Save" }).click();

    const dialog = page.locator("#m-outcome-reason");
    await expect(dialog).toBeVisible({ timeout: 5000 });
    const options = await page.locator("#or-reason option").allTextContents();
    expect(options).toContain("Weather");
    expect(options).toContain("Safety concern");
    expect(options).toContain("Other");
    expect(options).toContain("+ Add new reason…");

    await page.locator("#or-reason").selectOption("Weather");
    await page.getByRole("button", { name: "Save reason" }).click();
    await expect(dialog).toBeHidden({ timeout: 5000 });
    await expect(page.locator("#m-sess-edit")).toBeHidden({ timeout: 8000 });

    expect(errors, `no uncaught JS errors: ${errors.join("; ")}`).toHaveLength(0);
  });

  test("+ Add new reason creates a governed tag and it appears in the dropdown selected", async ({ page }) => {
    await loginSquadron(page, "ADMIN703");
    const hdr = { Authorization: `Bearer ${await page.evaluate(() => sessionStorage.getItem("aafc_token"))}` };
    const { marker, fixtureYear } = await seedSession(page, hdr, String(Date.now()) + "b");

    // Same budget exhaustion risk as the Cancelled test above -- reset so
    // loadData() can populate S.sessionStatusReasonTags successfully.
    await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");

    await openQuickEditForFirstSession(page, marker, fixtureYear);
    await page.locator("#qe-st").selectOption("not_delivered");
    await page.getByRole("button", { name: "Save" }).click();
    await expect(page.locator("#m-outcome-reason")).toBeVisible({ timeout: 5000 });

    // HARD-09 replaced native prompt() with the accessible promptText() modal.
    // Exercise that real UI instead of accepting a native browser dialog that
    // no longer exists.
    const reasonName = `E2E Custom Reason ${Date.now()}`;
    await page.locator("#or-reason").selectOption("__add_new__");
    const textModal = page.locator("#m-text-input");
    await expect(textModal).toBeVisible({ timeout: 5000 });
    await page.locator("#ti-input").fill(reasonName);
    await page.locator("#ti-ok-btn").click();
    await expect(textModal).toBeHidden({ timeout: 5000 });
    await expect(page.locator("#or-reason")).toHaveValue(reasonName, { timeout: 5000 });

    // Cleanup.
    const tags = await (await page.request.get(`${base}/api/session-status-reason-tags`, { headers: hdr })).json();
    const created = tags.find((t: any) => t.display_name === reasonName);
    if (created) {
      await page.request.delete(`${base}/api/session-status-reason-tags/${created.tag_id}`, { headers: hdr });
    }
  });
});
