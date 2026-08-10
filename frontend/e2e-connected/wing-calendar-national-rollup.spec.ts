import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// REM-13 Phase A: previously national_admin/system_admin could only view
// ONE wing's calendar at a time (a <select> picker, no true cross-wing
// rollup anywhere in the app -- confirmed missing by REM-73's own
// residual-limitation note). This suite covers the new "All Wings" option
// (backed by GET /api/wing-calendar/events with wing_id omitted) and the
// merged-in Activities (backed by the already-existing scope-aware
// /api/activities?scope_type=... endpoint, wired into this page for the
// first time).

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;
const base = LOCAL_API_BASE || "http://localhost:8000";

test.beforeEach(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");
});

async function loginNational(page: Page) {
  if (LOCAL_API_BASE) {
    await page.addInitScript((b) => { (window as any).AAFC_API_BASE = b; }, LOCAL_API_BASE);
  }
  await page.goto("/");
  await page.locator("#auth-type").selectOption("national");
  await page.locator("#auth-role").selectOption("national_admin");
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill("ADMINNATIONAL");
  await page.locator("#auth-btn").click();
  await expect(page.locator("#app")).toBeVisible({ timeout: 10000 });
}

async function loginWing(page: Page) {
  if (LOCAL_API_BASE) {
    await page.addInitScript((b) => { (window as any).AAFC_API_BASE = b; }, LOCAL_API_BASE);
  }
  await page.goto("/");
  await page.locator("#auth-type").selectOption("wing");
  await page.locator("#auth-wing-select").selectOption("7WG");
  await page.locator("#auth-role").selectOption("wing_admin");
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill("ADMIN7WG");
  await page.locator("#auth-btn").click();
  await expect(page.locator("#app")).toBeVisible({ timeout: 10000 });
}

async function authedRequest(page: Page) {
  const token = await page.evaluate(() => sessionStorage.getItem("aafc_token"));
  return { Authorization: `Bearer ${token}` };
}

async function ensureSecondWing(page: Page, hdr: Record<string, string>): Promise<string> {
  const list = await page.request.get(`${base}/api/wings`, { headers: hdr });
  const wings = await list.json();
  const existing = wings.find((w: any) => w.code === "9WG");
  if (existing) return existing.wing_id;
  const r = await page.request.post(`${base}/api/wings`, {
    data: { code: "9WG", name: "9 Wing E2E" }, headers: hdr,
  });
  expect(r.ok()).toBe(true);
  return (await r.json()).wing_id;
}

test.describe("Wing HQ Calendar — national cross-wing rollup (REM-13 Phase A)", () => {
  test("All Wings option shows events from two different wings in one grid", async ({ page }) => {
    await loginNational(page);
    const hdr = await authedRequest(page);
    const wing9Id = await ensureSecondWing(page, hdr);

    const me = await (await page.request.get(`${base}/api/auth/me`, { headers: hdr })).json();
    const wingsRes = await page.request.get(`${base}/api/wings`, { headers: hdr });
    const wings = await wingsRes.json();
    const wing7Id = wings.find((w: any) => w.code === "7WG").wing_id;

    // A day within the currently-displayed month (no grid navigation
    // needed), spread across the month by the run's own timestamp so
    // repeated runs land on different days -- the grid caps each day cell
    // at 3 visible chips before collapsing into "+N more", so piling every
    // run's events onto the same single day (e.g. always "today") risks a
    // real chip silently existing but never being visible to assert on.
    const suffix = String(Date.now());
    const title7 = `E2E Rollup 7WG ${suffix}`;
    const title9 = `E2E Rollup 9WG ${suffix}`;
    const day = 3 + (Date.now() % 24); // spread across the 2nd-25th of the month
    const eventDate = `2026-08-${String(day).padStart(2, "0")}`;
    const r1 = await page.request.post(`${base}/api/wing-calendar/events?wing_id=${wing7Id}`, {
      data: { title: title7, event_type: "wing_event", start_date: eventDate, planning_importance: "key_event" },
      headers: hdr,
    });
    expect(r1.ok()).toBe(true);
    const r2 = await page.request.post(`${base}/api/wing-calendar/events?wing_id=${wing9Id}`, {
      data: { title: title9, event_type: "wing_event", start_date: eventDate, planning_importance: "key_event" },
      headers: hdr,
    });
    expect(r2.ok()).toBe(true);

    await page.evaluate(() => (window as any).nav("wing-calendar"));
    await expect(page.locator("#wc-wing-sel")).toBeVisible();
    await page.locator("#wc-wing-sel").selectOption({ label: "All Wings" });
    await page.waitForTimeout(600);

    await expect(page.locator(".cal-grid-evt", { hasText: title7 })).toBeVisible({ timeout: 8000 });
    await expect(page.locator(".cal-grid-evt", { hasText: title9 })).toBeVisible({ timeout: 8000 });

    // Cleanup.
    const events = await (await page.request.get(`${base}/api/wing-calendar/events`, { headers: hdr })).json();
    for (const e of events) {
      if (e.title === title7 || e.title === title9) {
        await page.request.post(`${base}/api/wing-calendar/events/${e.id}/archive`, { data: {}, headers: hdr });
      }
    }
  });

  test("A wing-scoped Activity appears as a distinct, non-clickable chip alongside real Wing Events", async ({ page }) => {
    await loginNational(page);
    const hdr = await authedRequest(page);
    const wingsRes = await page.request.get(`${base}/api/wings`, { headers: hdr });
    const wing7Id = (await wingsRes.json()).find((w: any) => w.code === "7WG").wing_id;

    // Seed as wing_admin, not national_admin -- national_admin writing to a
    // Wing's data requires Delegated Intervention Mode (a real, separate
    // permission gate, not something this test is exercising), while
    // wing_admin can write to their own wing directly.
    const wingLoginRes = await page.request.post(`${base}/api/auth/login`, { data: { code: "ADMIN7WG" } });
    const wingToken = (await wingLoginRes.json()).token;
    const wingHdr = { Authorization: `Bearer ${wingToken}` };

    const suffix = String(Date.now());
    const actTitle = `E2E Rollup Activity ${suffix}`;
    const day = 3 + (Date.now() % 24);
    const eventDate = `2026-08-${String(day).padStart(2, "0")}`;
    const actRes = await page.request.post(`${base}/api/activities/wing`, {
      data: { activity_name: actTitle, date_start: eventDate, activity_type: "training", wing_id: wing7Id },
      headers: wingHdr,
    });
    expect(actRes.ok()).toBe(true);

    await page.evaluate(() => (window as any).nav("wing-calendar"));
    await expect(page.locator("#wc-wing-sel")).toBeVisible();
    await page.locator("#wc-wing-sel").selectOption({ label: "7WG" });
    await page.waitForTimeout(600);

    const chip = page.locator(".cal-grid-evt", { hasText: actTitle });
    await expect(chip).toBeVisible({ timeout: 8000 });
    // Activity chips have no onclick handler -- clicking must not open the
    // Wing Event detail modal (which would 404 against an Activity id).
    await chip.click();
    await expect(page.locator("#m-wing-event-detail")).toBeHidden();

    // Cleanup.
    const acts = await (await page.request.get(`${base}/api/activities?scope_type=wing&scope_id=${wing7Id}`, { headers: hdr })).json();
    const created = acts.items.find((a: any) => a.activity_name === actTitle);
    if (created) {
      await page.request.delete(`${base}/api/activities/${created.activity_id}`, { headers: hdr });
    }
  });

  test("wing_admin's own view is unaffected: no All Wings option, same single-wing fetch as before", async ({ page }) => {
    await loginWing(page);
    await page.evaluate(() => (window as any).nav("wing-calendar"));
    await expect(page.locator("#wc-wing-sel")).toBeHidden();
    const options = await page.locator("#wc-wing-sel option").allTextContents();
    expect(options).not.toContain("All Wings");
    await expect(page.locator(".cal-grid-table")).toBeVisible();
  });
});
