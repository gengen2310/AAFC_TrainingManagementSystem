import { test, expect, Page, APIRequestContext } from "../e2e-fixtures";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// Curriculum CSV import (Main TMS > Curriculum > Import CSV), driven through
// the real modal. Written BEFORE the import code was extracted out of the
// monolith into connected-frontend/js/, so it pins behaviour across that move;
// the target-scope tests pin the Wing/Squadron picker added afterwards.

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;
const base = LOCAL_API_BASE || "http://localhost:8000";

let owned: { hdr?: Record<string, string>; codes: string[] } = { codes: [] };

test.beforeEach(async () => { await resetBackendRateLimits(base); });

test.afterEach(async ({ request }) => {
  const { hdr, codes } = owned;
  owned = { codes: [] };
  if (!hdr) return;
  for (const code of codes) {
    for (const item of await itemsByCode(request, hdr, code)) {
      const r = await request.post(`${base}/api/curriculum/${item.curriculum_item_id || item.id}/archive`, { headers: hdr });
      expect([200, 204, 404, 409], `archive ${code} -> ${r.status()}`).toContain(r.status());
    }
  }
});

async function natHeaders(request: APIRequestContext) {
  const r = await request.post(`${base}/api/auth/login`, { data: { code: "ADMINNATIONAL" } });
  expect(r.ok()).toBe(true);
  return { Authorization: `Bearer ${(await r.json()).token}` };
}

async function itemsByCode(request: APIRequestContext, hdr: Record<string, string>, code: string) {
  const out: any[] = [];
  for (const path of ["/api/curriculum", "/api/curriculum/wing", "/api/curriculum/national"]) {
    const r = await request.get(`${base}${path}`, { headers: hdr });
    if (!r.ok()) continue;
    const body = await r.json();
    const rows = Array.isArray(body) ? body : (body.items || body.curriculum || []);
    for (const row of rows) if (row.code === code && !out.some((o) => (o.curriculum_item_id || o.id) === (row.curriculum_item_id || row.id))) out.push(row);
  }
  return out;
}

async function loginNational(page: Page) {
  if (LOCAL_API_BASE) await page.addInitScript((b) => { (window as any).AAFC_API_BASE = b; }, LOCAL_API_BASE);
  await page.goto("/");
  await page.locator("#auth-type").selectOption("national");
  await page.locator("#auth-role").selectOption("national_admin");
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill("ADMINNATIONAL");
  await page.locator("#auth-btn").click();
  await expect(page.locator("#app")).toBeVisible({ timeout: 10000 });
}

async function openImport(page: Page, code: string, title: string) {
  await page.evaluate(() => (window as any).nav("curriculum"));
  await page.getByRole("button", { name: "Import CSV" }).click();
  await expect(page.locator("#m-csv-curr-import")).toHaveClass(/active/);
  await page.locator("#csv-curr-file").setInputFiles({
    name: "curriculum.csv", mimeType: "text/csv",
    buffer: Buffer.from(`Training Phase,Experiential Code,Title\nB. Initial,${code},${title}\n`),
  });
}

test("national import: preview shows the row, confirm creates it", async ({ page, request }) => {
  owned.hdr = await natHeaders(request);
  const code = `CSVN${String(Date.now()).slice(-6)}`;
  owned.codes.push(code);
  await loginNational(page);
  await openImport(page, code, "National CSV Item");
  await page.locator("#csv-curr-level").selectOption("national");
  await page.locator("#csv-curr-preview-btn").click();
  await expect(page.locator("#csv-curr-summary")).toContainText("1 to create");
  await expect(page.locator("#csv-curr-rows")).toContainText(code);
  await page.locator("#csv-curr-commit-btn").click();
  await expect(page.locator("#csv-curr-result")).toContainText("1 created");
  const items = await itemsByCode(request, owned.hdr, code);
  expect(items.map((i) => i.owning_level)).toEqual(["national"]);
});
