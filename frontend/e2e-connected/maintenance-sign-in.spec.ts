import { test, expect, Page } from "../e2e-fixtures";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// Maintenance audit (brief §43-45): during a locked window with block_logins
// OFF, people must still be able to sign in (writes stay blocked). Sign-in is
// POST /api/auth/lookup then /login; lookup was gated as a "write", so the UI
// sign-in failed for everyone -- system_admin included. Disposable local
// backend only; afterEach always turns maintenance off.

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;
const base = LOCAL_API_BASE || "http://localhost:8000";
let saHdr: Record<string, string> | null = null;

test.beforeEach(async () => { await resetBackendRateLimits(base); });

test.afterEach(async ({ request }) => {
  if (!saHdr) return;
  const r = await request.post(`${base}/api/system/maintenance/disable`, { headers: saHdr });
  saHdr = null;
  expect(r.status(), "maintenance disable").toBe(200);
});

async function uiLogin(page: Page, code: string) {
  if (LOCAL_API_BASE) await page.addInitScript((b) => { (window as any).AAFC_API_BASE = b; }, LOCAL_API_BASE);
  await page.goto("/");
  await page.locator("#auth-type").selectOption("squadron");
  await page.locator("#auth-wing-select").selectOption("7WG");
  await page.locator("#auth-sqn-select").selectOption("703");
  await page.locator("#auth-role").selectOption("sqn_admin");
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill(code);
  await page.locator("#auth-btn").click();
}

test("a squadron admin can sign in through the UI during locked maintenance (logins not blocked)", async ({ page, request }) => {
  const sa = await request.post(`${base}/api/auth/login`, { data: { code: "SYSADMIN2026" } });
  expect(sa.ok()).toBe(true);
  saHdr = { Authorization: `Bearer ${(await sa.json()).token}` };
  const en = await request.post(`${base}/api/system/maintenance/enable`, { headers: saHdr, data: {
    confirm: "ENABLE MAINTENANCE", message: "E2E maintenance window", drain_seconds: 0,
    block_reads: false, block_logins: false } });
  expect(en.status()).toBe(200);

  await uiLogin(page, "ADMIN703");
  await expect(page.locator("#app")).toBeVisible({ timeout: 10000 });
  await expect(page.locator("#auth-screen")).toBeHidden();
});
