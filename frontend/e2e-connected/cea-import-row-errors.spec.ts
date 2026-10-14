// D18 (2026-10-11): rows the CEA import refuses are listed with the reason in
// the Main TMS result, and the server's message (which quotes the bad value)
// is rendered as text. Uses the real import endpoint and the page's own
// result helper; the file-picker click flow itself is covered by UAT.
import { test, expect, Page } from "../e2e-fixtures";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;
const BACKEND_BASE =
  process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000";

test.beforeAll(async () => {
  await resetBackendRateLimits(BACKEND_BASE);
});

async function loginWingAdmin(page: Page) {
  if (LOCAL_API_BASE) {
    await page.addInitScript((base) => {
      (window as any).AAFC_API_BASE = base;
    }, LOCAL_API_BASE);
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

test("CEA import lists refused rows with their reason, as text", async ({ page, request }) => {
  const sqnLogin = await request.post(`${BACKEND_BASE}/api/auth/login`, { data: { code: "ADMIN703" } });
  const sqn = { Authorization: `Bearer ${(await sqnLogin.json()).token}` };
  const years = await (await request.get(`${BACKEND_BASE}/api/planning/years`, { headers: sqn })).json();
  const yearId = (Array.isArray(years) ? years : years.years)[0].planning_year_id;
  await loginWingAdmin(page);
  const result = await page.evaluate(async (yid) => {
    const csv = "ActivityID,Name,StartDate\nE2E-D18-OK,Fine Event,2099-09-01\n"
      + "E2E-D18-BAD,Broken Event,<img src=x onerror=window.__pwned=1>\n";
    const fd = new FormData();
    fd.append("file", new Blob([csv], { type: "text/csv" }), "cea.csv");
    // Same request the Main TMS import button sends (activities.js): fetch with
    // the app's API_BASE (a top-level binding, not a window property).
    const base = (0, eval)("API_BASE");
    const tok = sessionStorage.getItem("aafc_token") || "";
    const r = await fetch(base + `/api/planning/years/${yid}/cea/import`,
      { method: "POST", headers: tok ? { Authorization: "Bearer " + tok } : {}, credentials: "include", body: fd });
    return r.ok ? r.json() : { thrown: `${r.status} ${await r.text()}` };
  }, yearId);
  expect(result.thrown, "import threw").toBeUndefined();
  expect(result.row_errors).toHaveLength(1);
  await page.evaluate((errs) => {
    const d = document.createElement("div");
    d.id = "d18-probe";
    d.innerHTML = (window as any)._ceaRowErrorsHtml(errs);
    document.body.appendChild(d);
  }, result.row_errors);
  const alert = page.locator("#d18-probe [role=alert]");
  await expect(alert).toContainText("1 row not imported");
  await expect(alert).toContainText("Row 3: StartDate");
  await expect(alert).toContainText("<img src=x");          // shown as text...
  expect(await page.locator("#d18-probe img").count()).toBe(0);   // ...never as markup
  expect(await page.evaluate(() => (window as any).__pwned)).toBeUndefined();
});
