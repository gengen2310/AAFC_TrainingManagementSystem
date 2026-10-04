import { test, expect, Page, APIRequestContext } from "../e2e-fixtures";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// Curriculum CSV import (Main TMS > Curriculum > Import CSV), driven through
// the real modal. Written BEFORE the import code was extracted out of the
// monolith into connected-frontend/js/, so it pins behaviour across that move;
// the target-scope tests pin the Wing/Squadron picker added afterwards.

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;
const base = LOCAL_API_BASE || "http://localhost:8000";

let owned: { hdr?: Record<string, string>; codes: string[]; sqnIds: string[] } = { codes: [], sqnIds: [] };

test.beforeEach(async () => { await resetBackendRateLimits(base); });

test.afterEach(async ({ request }) => {
  const { hdr, codes, sqnIds } = owned;
  owned = { codes: [], sqnIds: [] };
  if (!hdr) return;
  for (const code of codes) {
    for (const item of await itemsByCode(request, hdr, code, sqnIds)) {
      // Rows are keyed curriculum_id. A missing id must fail loudly: an
      // earlier draft read the wrong key, hit /undefined/archive (404) and
      // "cleaned up" nothing.
      expect(item.curriculum_id, `curriculum_id for ${code}`).toBeTruthy();
      // DELETE /api/curriculum/{id} is the (soft) archive. Squadron-owned items
      // are managed only by their own squadron (national admin gets 403 by
      // design), and these tests only ever target 703.
      const who = item.owning_level === "squadron" ? await sqnHeaders(request) : hdr;
      const r = await request.delete(`${base}/api/curriculum/${item.curriculum_id}`, { headers: who });
      expect([200, 204], `archive ${code} -> ${r.status()}`).toContain(r.status());
    }
  }
});

async function sqnHeaders(request: APIRequestContext) {
  const r = await request.post(`${base}/api/auth/login`, { data: { code: "ADMIN703" } });
  expect(r.ok()).toBe(true);
  return { Authorization: `Bearer ${(await r.json()).token}` };
}

async function natHeaders(request: APIRequestContext) {
  const r = await request.post(`${base}/api/auth/login`, { data: { code: "ADMINNATIONAL" } });
  expect(r.ok()).toBe(true);
  return { Authorization: `Bearer ${(await r.json()).token}` };
}

// National admins see national + every Wing's items; Squadron-owned items only
// when the squadron is named.
async function itemsByCode(request: APIRequestContext, hdr: Record<string, string>, code: string,
                           sqnIds: string[] = []) {
  const out: any[] = [];
  for (const q of ["", ...sqnIds.map((id) => `?squadron_id=${id}`)]) {
    const r = await request.get(`${base}/api/curriculum${q}`, { headers: hdr });
    expect(r.ok(), `GET /api/curriculum${q}`).toBe(true);
    const body = await r.json();
    const rows = Array.isArray(body) ? body : (body.items || []);
    for (const row of rows) if (row.code === code && !out.some((o) => o.curriculum_id === row.curriculum_id)) out.push(row);
  }
  return out;
}

async function unitIds(request: APIRequestContext, hdr: Record<string, string>) {
  const wings = await (await request.get(`${base}/api/wings`, { headers: hdr })).json();
  const sqns = await (await request.get(`${base}/api/squadrons`, { headers: hdr })).json();
  const wing = (wings as any[]).find((w) => w.code === "7WG");
  const sqn = (sqns as any[]).find((s) => s.code === "703");
  return { wingId: wing.wing_id as string, sqnId: sqn.squadron_id as string, sqnWingId: sqn.wing_id as string };
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

test("wing import: the picker names the Wing, preview shows it, and the item is owned by that Wing", async ({ page, request }) => {
  owned.hdr = await natHeaders(request);
  const { wingId } = await unitIds(request, owned.hdr);
  const code = `CSVW${String(Date.now()).slice(-6)}`;
  owned.codes.push(code);
  await loginNational(page);
  await openImport(page, code, "Wing CSV Item");
  await page.locator("#csv-curr-level").selectOption("wing");
  await expect(page.locator("#csv-curr-wing")).toBeVisible();
  await expect(page.locator("#csv-curr-squadron")).toBeHidden();
  await page.locator("#csv-curr-wing").selectOption(wingId);
  await page.locator("#csv-curr-preview-btn").click();
  await expect(page.locator("#csv-curr-target-summary")).toContainText("7WG");
  await page.locator("#csv-curr-commit-btn").click();
  await expect(page.locator("#csv-curr-result")).toContainText("1 created");
  const items = await itemsByCode(request, owned.hdr, code);
  expect(items.map((i) => [i.owning_level, i.wing_id])).toEqual([["wing", wingId]]);
});

test("squadron import: the Squadron list follows the chosen Wing and the item is owned by that Squadron", async ({ page, request }) => {
  owned.hdr = await natHeaders(request);
  const { sqnId, sqnWingId } = await unitIds(request, owned.hdr);
  owned.sqnIds.push(sqnId);
  const code = `CSVS${String(Date.now()).slice(-6)}`;
  owned.codes.push(code);
  await loginNational(page);
  await openImport(page, code, "Squadron CSV Item");
  await page.locator("#csv-curr-level").selectOption("squadron");
  await expect(page.locator("#csv-curr-wing")).toBeVisible();
  await expect(page.locator("#csv-curr-squadron")).toBeVisible();
  await page.locator("#csv-curr-wing").selectOption(sqnWingId);
  // Only Squadrons of the chosen Wing are offered.
  const offered = await page.locator("#csv-curr-squadron option[value]:not([value=''])").evaluateAll(
    (os) => os.map((o) => (o as HTMLOptionElement).dataset.wingId));
  expect(offered.length).toBeGreaterThan(0);
  expect(new Set(offered)).toEqual(new Set([sqnWingId]));
  await page.locator("#csv-curr-squadron").selectOption(sqnId);
  await page.locator("#csv-curr-preview-btn").click();
  await expect(page.locator("#csv-curr-target-summary")).toContainText("703");
  await page.locator("#csv-curr-commit-btn").click();
  await expect(page.locator("#csv-curr-result")).toContainText("1 created");
  const items = await itemsByCode(request, owned.hdr, code, [sqnId]);
  expect(items.map((i) => [i.owning_level, i.squadron_id])).toEqual([["squadron", sqnId]]);
});

test("a unit level without a chosen unit is caught before any request; changing the target after preview requires a new preview", async ({ page, request }) => {
  owned.hdr = await natHeaders(request);
  const { wingId } = await unitIds(request, owned.hdr);
  const code = `CSVX${String(Date.now()).slice(-6)}`;
  owned.codes.push(code);
  await loginNational(page);
  await openImport(page, code, "Guard CSV Item");
  let calls = 0;
  page.on("request", (r) => { if (r.url().includes("/api/curriculum/import-csv")) calls += 1; });
  await page.locator("#csv-curr-level").selectOption("wing");
  await page.locator("#csv-curr-preview-btn").click();
  await expect(page.locator("#csv-curr-msg")).toContainText("Choose the Wing");
  expect(calls).toBe(0);

  await page.locator("#csv-curr-wing").selectOption(wingId);
  await page.locator("#csv-curr-preview-btn").click();
  await expect(page.locator("#csv-curr-commit-btn")).toBeVisible();
  await page.locator("#csv-curr-level").selectOption("national");      // target changed after preview
  await expect(page.locator("#csv-curr-commit-btn")).toBeHidden();
  await expect(page.locator("#csv-curr-preview")).toBeHidden();
  expect(await itemsByCode(request, owned.hdr, code)).toEqual([]);       // nothing was written
});
