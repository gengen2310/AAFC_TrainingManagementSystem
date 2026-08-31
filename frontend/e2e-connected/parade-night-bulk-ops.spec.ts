import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// WORK-11: Copy parade night sessions
// WORK-12: Bulk cancel all sessions
// DEF-08: Programme items CSV export via streaming endpoint

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;
const BASE = LOCAL_API_BASE || "http://localhost:8000";
const EFFECTIVE_BASE = process.env.E2E_BACKEND_BASE_URL || BASE;

// IDs of parade nights created during this run — cleaned up in afterAll.
const _createdPnIds: string[] = [];

test.beforeAll(async () => {
  await resetBackendRateLimits(EFFECTIVE_BASE);
});

test.afterAll(async ({ request }) => {
  const lookup = await request.post(`${EFFECTIVE_BASE}/api/auth/lookup`, {
    data: { unit_type: "squadron", identifier: "703", role: "sqn_admin" },
  });
  if (!lookup.ok()) return;
  const userId = (await lookup.json()).user_id as string;
  const loginRes = await request.post(`${EFFECTIVE_BASE}/api/auth/login`, {
    data: { code: "ADMIN703", user_id: userId },
  });
  if (!loginRes.ok()) return;
  const body = await loginRes.json();
  const auth = { Authorization: `Bearer ${body.token || body.access_token}` };
  for (const pnId of _createdPnIds) {
    await request.delete(`${EFFECTIVE_BASE}/api/parade-nights/${pnId}`, { headers: auth });
  }
});

async function loginSquadron(page: Page, code = "ADMIN703") {
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
  await expect(page.locator("#app")).toBeVisible({ timeout: 10000 });
}

async function getAdminToken(page: Page): Promise<string> {
  const tok = await page.evaluate(() => sessionStorage.getItem("aafc_token") ?? "");
  return tok;
}

// ── WORK-11: Copy parade night sessions ─────────────────────────────────────

test("WORK-11: copy session modal opens from parade night card", async ({ page }) => {
  await loginSquadron(page);
  const token = await getAdminToken(page);
  const hdr = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  // Create two parade nights to copy between
  const srcDate = `2099-10-${String(1 + (Date.now() % 25)).padStart(2, "0")}`;
  const tgtDate = `2099-11-${String(1 + (Date.now() % 25)).padStart(2, "0")}`;
  const srcR1 = await page.request.post(`${BASE}/api/parade-nights`, { data: { date: srcDate }, headers: hdr });
  const tgtR1 = await page.request.post(`${BASE}/api/parade-nights`, { data: { date: tgtDate }, headers: hdr });
  if (srcR1.ok()) _createdPnIds.push((await srcR1.json()).parade_night_id);
  if (tgtR1.ok()) _createdPnIds.push((await tgtR1.json()).parade_night_id);

  await page.evaluate(() => (window as any).nav?.("parade-nights"));
  await page.waitForTimeout(1000);

  // The "Copy to…" button should exist on the source night's card
  const copyBtn = page.getByRole("button", { name: /copy to/i }).first();
  await expect(copyBtn).toBeVisible({ timeout: 8000 });
  await copyBtn.click();

  // Modal should open with a night selector
  const modal = page.locator("#m-copy-pn");
  await expect(modal).toBeVisible({ timeout: 5000 });
  await expect(modal.locator("select, [role='listbox']")).toBeAttached();
});

test("WORK-11: copy sessions API endpoint returns ok:true", async ({ page }) => {
  await loginSquadron(page);
  const token = await getAdminToken(page);
  const hdr = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const src = `2099-09-${String(2 + (Date.now() % 25)).padStart(2, "0")}`;
  const tgt = `2099-09-${String(3 + (Date.now() % 25)).padStart(2, "0")}`;
  const srcR = await page.request.post(`${BASE}/api/parade-nights`, { data: { date: src }, headers: hdr });
  const tgtR = await page.request.post(`${BASE}/api/parade-nights`, { data: { date: tgt }, headers: hdr });
  const srcId = (await srcR.json()).parade_night_id;
  const tgtId = (await tgtR.json()).parade_night_id;
  _createdPnIds.push(srcId, tgtId);

  // Add a session to source
  await page.request.post(`${BASE}/api/sessions`, {
    data: { parade_night_id: srcId, period_number: 1 },
    headers: hdr,
  });

  const copyR = await page.request.post(`${BASE}/api/parade-nights/${srcId}/copy-sessions-to/${tgtId}`, {
    headers: hdr,
  });
  expect(copyR.ok()).toBe(true);
  const body = await copyR.json();
  expect(body.ok).toBe(true);
  expect(typeof body.copied).toBe("number");
});

// ── WORK-12: Bulk cancel all sessions ───────────────────────────────────────

test("WORK-12: cancel all button is present in parade night detail", async ({ page }) => {
  await loginSquadron(page);
  const token = await getAdminToken(page);
  const hdr = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const date = `2099-08-${String(4 + (Date.now() % 23)).padStart(2, "0")}`;
  const pnR = await page.request.post(`${BASE}/api/parade-nights`, { data: { date }, headers: hdr });
  const pnId = (await pnR.json()).parade_night_id;
  _createdPnIds.push(pnId);
  await page.request.post(`${BASE}/api/sessions`, {
    data: { parade_night_id: pnId, period_number: 1 },
    headers: hdr,
  });

  await page.evaluate(() => (window as any).nav?.("parade-nights"));
  await page.waitForTimeout(1000);
  await page.evaluate((d) => (window as any).showPNDetail?.(d), date);

  const modal = page.locator("#m-pn-detail");
  await expect(modal).toBeVisible({ timeout: 8000 });

  // "Cancel all remaining" button should be present in the detail modal
  const cancelAllBtn = modal.getByRole("button", { name: /cancel all/i });
  await expect(cancelAllBtn).toBeVisible({ timeout: 5000 });
});

test("WORK-12: cancel-all API returns sessions_updated count", async ({ page }) => {
  await loginSquadron(page);
  const token = await getAdminToken(page);
  const hdr = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const date = `2099-08-${String(5 + (Date.now() % 23)).padStart(2, "0")}`;
  const pnR = await page.request.post(`${BASE}/api/parade-nights`, { data: { date }, headers: hdr });
  const pnId = (await pnR.json()).parade_night_id;
  _createdPnIds.push(pnId);
  await page.request.post(`${BASE}/api/sessions`, {
    data: { parade_night_id: pnId, period_number: 1 },
    headers: hdr,
  });
  await page.request.post(`${BASE}/api/sessions`, {
    data: { parade_night_id: pnId, period_number: 2 },
    headers: hdr,
  });

  const cancelR = await page.request.post(`${BASE}/api/parade-nights/${pnId}/cancel-all`, {
    data: { reason: "E2E test cancellation", notes: null },
    headers: hdr,
  });
  expect(cancelR.ok()).toBe(true);
  const body = await cancelR.json();
  expect(body.ok).toBe(true);
  expect(body.sessions_updated).toBe(2);
  expect(Array.isArray(body.session_ids)).toBe(true);
  expect(body.session_ids).toHaveLength(2);
});

// ── WORK-05: Override Parade Night Timing modal ─────────────────────────────

test("WORK-05: 'Timing…' button opens Override Parade Night Timing modal with mode toggle", async ({ page }) => {
  // WORK-05 wires openPNTimingOverrideModal() to the parade night card.
  // The modal must open and expose both the "Use existing template" and
  // "Custom blocks for this night" mode buttons.
  await loginSquadron(page);
  const token = await getAdminToken(page);
  const hdr = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  // Seed a parade night with a known date so we can find its card.
  const pnDate = `2099-12-${String(1 + (Date.now() % 28)).padStart(2, "0")}`;
  const pnR5 = await page.request.post(`${BASE}/api/parade-nights`, { data: { date: pnDate }, headers: hdr });
  if (pnR5.ok()) _createdPnIds.push((await pnR5.json()).parade_night_id);

  await page.evaluate(() => (window as any).nav?.("parade-nights"));

  // The "Timing…" button must appear on the seeded parade night's card.
  const timingBtn = page.getByRole("button", { name: /^Timing…$/ }).first();
  await expect(timingBtn).toBeVisible({ timeout: 10000 });
  await timingBtn.click();

  // Modal must open.
  const modal = page.locator("#m-pn-timing-override");
  await expect(modal).toBeVisible({ timeout: 5000 });

  // Both mode toggle buttons must be present.
  await expect(modal.getByRole("button", { name: /Use existing template/ })).toBeVisible();
  await expect(modal.getByRole("button", { name: /Custom blocks for this night/ })).toBeVisible();
});

// ── DEF-08: Programme items CSV export ──────────────────────────────────────

test("DEF-08: export CSV button calls streaming endpoint with auth header", async ({ page }) => {
  await loginSquadron(page);

  // Intercept the export request to verify it's called correctly
  let exportRequestMade = false;
  let exportHadAuth = false;
  await page.route("**/api/export/program-items.csv", async (route) => {
    exportRequestMade = true;
    const req = route.request();
    exportHadAuth = req.headers()["authorization"]?.startsWith("Bearer ") ?? false;
    // Respond with a minimal CSV to allow the fetch to complete
    await route.fulfill({
      status: 200,
      contentType: "text/csv",
      headers: { "Content-Disposition": 'attachment; filename="program-items.csv"' },
      body: "code,title\nTEST-01,Test Item\n",
    });
  });

  await page.evaluate(() => (window as any).nav?.("curriculum"));
  await page.waitForTimeout(1500);

  const exportBtn = page.getByRole("button", { name: "Export CSV" });
  await expect(exportBtn).toBeVisible({ timeout: 8000 });
  await exportBtn.click();

  // Wait for the intercepted request
  await page.waitForTimeout(1000);

  expect(exportRequestMade).toBe(true);
  expect(exportHadAuth).toBe(true);
});

test("DEF-08: streaming export endpoint returns CSV content for sqn_admin", async ({ page }) => {
  await loginSquadron(page);
  const token = await getAdminToken(page);

  const resp = await page.request.get(`${BASE}/api/export/program-items.csv`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(resp.ok()).toBe(true);
  expect(resp.headers()["content-type"]).toContain("text/csv");
  const body = await resp.text();
  // Must have a header row
  expect(body).toContain("code,title");
});
