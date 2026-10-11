// D10 follow-up (2026-10-11): the server now refuses a Squadron Admin's edits
// to Wing/national/system phases, so the Main TMS must not offer them. The
// list's can_edit flag (same rule as PATCH/DELETE) decides; an owned phase
// keeps both actions.
import { test, expect, Page } from "../e2e-fixtures";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;
const BACKEND_BASE =
  process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000";

test.beforeAll(async () => {
  await resetBackendRateLimits(BACKEND_BASE);
});

async function loginSquadronAdmin(page: Page) {
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
  await page.locator("#auth-code").fill("ADMIN703");
  await page.locator("#auth-btn").click();
  await expect(page.locator("#app")).toBeVisible({ timeout: 10000 });
}

test("Edit/Delete appear only on phases the user may change", async ({ page, request }) => {
  const sysLogin = await request.post(`${BACKEND_BASE}/api/auth/login`, { data: { code: "SYSADMIN2026" } });
  const sys = { Authorization: `Bearer ${(await sysLogin.json()).token}` };
  const tag = `${Date.now()}`;
  await loginSquadronAdmin(page);
  const me = await page.evaluate(() => (window as any).api("/api/auth/me"));
  const wingPhase = await (await request.post(`${BACKEND_BASE}/api/custom-training-phases`, {
    headers: sys,
    data: { name: `Wing phase ${tag}`, scope_type: "wing", scope_id: me.session.wing_id, applies_from: "2095-01-01" },
  })).json();
  const own = await page.evaluate((name) => (window as any).api("/api/custom-training-phases", {
    method: "POST", body: { name, scope_type: "squadron", applies_from: "2095-01-01" } }), `Own phase ${tag}`);
  try {
    await page.evaluate(() => {
      if (!document.getElementById("settings-custom-phases-list")) {
        const d = document.createElement("div");
        d.id = "settings-custom-phases-list";
        document.body.appendChild(d);
      }
    });
    await page.evaluate(() => (window as any).loadCustomPhases());
    const row = (name: string) => page.locator(".cp-row", { hasText: name });
    await expect(row(`Wing phase ${tag}`)).toHaveCount(1);
    await expect(row(`Wing phase ${tag}`).locator("button")).toHaveCount(0);
    await expect(row(`Own phase ${tag}`).locator("button")).toHaveCount(2);
  } finally {
    await request.delete(`${BACKEND_BASE}/api/custom-training-phases/${wingPhase.custom_phase_id}`, { headers: sys });
    await request.delete(`${BACKEND_BASE}/api/custom-training-phases/${own.custom_phase_id}`, { headers: sys });
  }
});
