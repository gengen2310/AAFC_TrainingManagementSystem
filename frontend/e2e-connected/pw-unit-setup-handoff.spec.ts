import { test, expect, Page } from "../e2e-fixtures";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// PR #65 review T08 (P2): Planning Workspace's "Open TMS Unit Setup" link for a
// year with no record lands on TMS with ?aafc_page=settings&aafc_training_year=Y.
// The landing page must offer a working "Set up Y" action -- a handoff that
// lands somewhere with no way to do the thing it promised is a dead end.

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;
const base = LOCAL_API_BASE || "http://localhost:8000";

let owned: { hdr?: Record<string, string>; yearId?: string } = {};

test.beforeEach(async () => { await resetBackendRateLimits(base); });

test.afterEach(async ({ request }) => {
  const { hdr, yearId } = owned;
  owned = {};
  if (!hdr || !yearId) return;
  // Delete (not deactivate) so the year is unmaterialised again for the next run.
  const r = await request.delete(`${base}/api/planning/years/${yearId}`, { headers: hdr });
  expect([200, 204, 404], `year delete -> ${r.status()}`).toContain(r.status());
});

async function loginVia(page: Page, path: string) {
  if (LOCAL_API_BASE) await page.addInitScript((b) => { (window as any).AAFC_API_BASE = b; }, LOCAL_API_BASE);
  await page.goto(path);
  await page.locator("#auth-type").selectOption("squadron");
  await page.locator("#auth-wing-select").selectOption("7WG");
  await page.locator("#auth-sqn-select").selectOption("703");
  await page.locator("#auth-role").selectOption("sqn_admin");
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill("ADMIN703");
  await page.locator("#auth-btn").click();
  await expect(page.locator("#app")).toBeVisible({ timeout: 10000 });
  return { Authorization: `Bearer ${await page.evaluate(() => sessionStorage.getItem("aafc_token"))}` };
}

test("handoff for a year with no record lands on a page whose Set up action creates it", async ({ page }) => {
  // A year with no record of any kind (active or archived). Far outside the
  // server's selectable window on purpose: the landing must keep the handed-off
  // year selectable through its own refetch, whatever the server lists.
  const login = await page.request.post(`${base}/api/auth/login`, { data: { code: "ADMIN703" } });
  const probeHdr = { Authorization: `Bearer ${(await login.json()).token}` };
  const listed = await (await page.request.get(`${base}/api/planning/years?include_unmaterialised=true`,
    { headers: probeHdr })).json();
  const taken = new Set((listed as any[]).map((y) => Number(y.year)));
  let year = 2900 + (Date.now() % 90);
  while (taken.has(year)) year = year >= 2998 ? 2900 : year + 1;

  const hdr = await loginVia(page, `/?aafc_page=settings&aafc_training_year=${year}`);
  owned.hdr = hdr;
  await expect(page.locator("#page-settings")).toHaveClass(/active/);

  const setUp = page.getByRole("button", { name: `Set up ${year}` });
  await expect(setUp).toBeVisible({ timeout: 8000 });
  await setUp.click();

  await expect.poll(async () => {
    const list = await (await page.request.get(`${base}/api/planning/years`, { headers: hdr })).json();
    const row = (Array.isArray(list) ? list : list.planning_years || []).find((y: any) => Number(y.year) === year);
    if (row) owned.yearId = row.planning_year_id;
    return Boolean(row);
  }, { timeout: 8000 }).toBe(true);
});
