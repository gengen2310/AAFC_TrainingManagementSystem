// Service Desk list pages from the server (C8, 2026-10-10). Every filter and
// count must stay correct when only the first page is loaded: the status filter
// runs on the server, the open count and unit list come from the summary, and
// "Load more" appends the next page.
import { test, expect, Page } from "../e2e-fixtures";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;
const BACKEND_BASE =
  process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000";

test.beforeAll(async () => {
  await resetBackendRateLimits(BACKEND_BASE);
});

async function loginSquadron(page: Page, code: string) {
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

test("Service Desk pages 100 at a time and keeps filters and counts true", async ({ page }) => {
  test.setTimeout(120000);
  await loginSquadron(page, "ADMIN703");
  const token = await page.evaluate(
    () => (window as any).tokenGet?.() ?? sessionStorage.getItem("aafc_token"),
  );
  const auth = { Authorization: `Bearer ${token}` };
  const me = await (await page.request.get(`${BACKEND_BASE}/api/auth/me`, { headers: auth })).json();
  const squadronId = me.session.squadron_id;

  // More than one page of this squadron's tickets.
  const tag = `paging-${Date.now()}`;
  for (let i = 0; i < 105; i++) {
    const r = await page.request.post(`${BACKEND_BASE}/api/service-desk/tickets`, {
      data: {
        rank: "Cdt", first_name: "Page", last_name: `T${i}`, email: "page@example.org",
        squadron_id: squadronId, category: "other", description: `${tag} ${i}`,
      },
    });
    expect(r.status(), await r.text()).toBe(201);
  }
  const listHeaders = (
    await page.request.get(`${BACKEND_BASE}/api/service-desk/tickets?limit=1`, { headers: auth })
  ).headers();
  const total = Number(listHeaders["x-total-count"]);
  expect(total).toBeGreaterThanOrEqual(105);
  const summary = await (
    await page.request.get(`${BACKEND_BASE}/api/service-desk/tickets/summary`, { headers: auth })
  ).json();

  await page.evaluate(() => (window as any).nav("service-desk"));
  const rows = page.locator("#sd-tbody tr[data-tid]");
  await expect(rows).toHaveCount(100);
  await expect(page.locator("#sd-count")).toHaveText(
    `${total} tickets (showing 100) · ${summary.open} open`,
  );

  // Load more appends the rest of the filtered list, then hides itself.
  const more = page.getByRole("button", { name: "Load more tickets" });
  await expect(more).toBeVisible();
  await more.click();
  await expect(rows).toHaveCount(Math.min(total, 200));
  if (total <= 200) await expect(more).toBeHidden();

  // A status filter is answered by the server over ALL tickets, not the loaded page.
  const resolved = Number(
    (await page.request.get(`${BACKEND_BASE}/api/service-desk/tickets?status=resolved&limit=1`, { headers: auth }))
      .headers()["x-total-count"],
  );
  await page.locator("#sd-filter-bar button", { hasText: "Resolved" }).click();
  await expect(page.locator("#sd-count")).toHaveText(
    new RegExp(`^${resolved} of ${summary.total} tickets`),
  );
  await expect(rows).toHaveCount(Math.min(resolved, 100));
});
