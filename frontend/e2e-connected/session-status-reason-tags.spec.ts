import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

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

test.beforeEach(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");
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
  const testDate = new Date(2066, 5, 1 + (Date.now() % 300)).toISOString().slice(0, 10);
  const marker = `E2E-REASON-MARKER-${uniqueSuffix}`;
  const pnRes = await page.request.post(`${base}/api/parade-nights`, {
    data: { squadron_id: me.session.squadron_id, wing_id: me.session.wing_id, date: testDate, parade_type: "normal" },
    headers: hdr,
  });
  expect(pnRes.ok()).toBe(true);
  const pnId = (await pnRes.json()).parade_night_id as string;
  await page.request.patch(`${base}/api/parade-nights/${pnId}`, { data: { notes: marker }, headers: hdr });
  const sessRes = await page.request.post(`${base}/api/sessions`, {
    data: { parade_night_id: pnId, period_number: 1 }, headers: hdr,
  });
  expect(sessRes.ok()).toBe(true);
  return marker;
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

test.describe("Session Status Reason tags (REM-23 continuation)", () => {
  test("changing status to Cancelled opens the reason modal with the real governed reason list", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await loginSquadron(page, "ADMIN703");
    const hdr = { Authorization: `Bearer ${await page.evaluate(() => sessionStorage.getItem("aafc_token"))}` };
    const marker = await seedSession(page, hdr, String(Date.now()));

    await openQuickEditForFirstSession(page, marker);
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
    const marker = await seedSession(page, hdr, String(Date.now()) + "b");

    await openQuickEditForFirstSession(page, marker);
    await page.locator("#qe-st").selectOption("not_delivered");
    await page.getByRole("button", { name: "Save" }).click();
    await expect(page.locator("#m-outcome-reason")).toBeVisible({ timeout: 5000 });

    const reasonName = `E2E Custom Reason ${Date.now()}`;
    page.once("dialog", (d) => d.accept(reasonName));
    await page.locator("#or-reason").selectOption("__add_new__");
    await expect(page.locator("#or-reason")).toHaveValue(reasonName, { timeout: 5000 });

    // Cleanup.
    const tags = await (await page.request.get(`${base}/api/session-status-reason-tags`, { headers: hdr })).json();
    const created = tags.find((t: any) => t.display_name === reasonName);
    if (created) {
      await page.request.delete(`${base}/api/session-status-reason-tags/${created.tag_id}`, { headers: hdr });
    }
  });
});
