import { test, expect, Page } from "@playwright/test";
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

test("Squadron admins can restore archived Flights from Account Management", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");
  const token = await page.evaluate(
    () => (window as any).tokenGet?.() ?? sessionStorage.getItem("aafc_token"),
  );
  const auth = { Authorization: `Bearer ${token}` };
  const meResponse = await page.request.get(`${BACKEND_BASE}/api/auth/me`, { headers: auth });
  expect(meResponse.ok()).toBe(true);
  const me = await meResponse.json();
  const flightName = `Restore workflow ${Date.now()}`;
  let flightId: string | null = null;

  try {
    const createResponse = await page.request.post(`${BACKEND_BASE}/api/flights`, {
      data: { name: flightName, squadron_id: me.session.squadron_id },
      headers: auth,
    });
    expect(createResponse.ok()).toBe(true);
    flightId = (await createResponse.json()).flight_id;

    const archiveResponse = await page.request.post(
      `${BACKEND_BASE}/api/flights/${flightId}/archive`,
      { headers: auth },
    );
    expect(archiveResponse.ok()).toBe(true);

    await page.evaluate(() => (window as any).nav("accounts"));
    const flightsCard = page.locator("#acct-flights-card");
    await expect(flightsCard).toBeVisible();
    await page.locator("#flights-show-archived").check();
    const archivedRow = page.locator("#flight-table tbody tr").filter({ hasText: flightName });
    await expect(archivedRow).toBeVisible();
    await archivedRow.getByRole("button", { name: "Restore" }).click();
    await expect(archivedRow).toHaveCount(0);

    await page.locator("#flights-show-archived").uncheck();
    await expect(
      page.locator("#flight-table tbody tr").filter({ hasText: flightName }),
    ).toBeVisible();
  } finally {
    if (flightId) {
      const flightsResponse = await page.request.get(
        `${BACKEND_BASE}/api/flights?include_archived=true&squadron_id=${encodeURIComponent(me.session.squadron_id)}`,
        { headers: auth },
      );
      expect(flightsResponse.ok()).toBe(true);
      const flights = await flightsResponse.json();
      const flight = flights.find((row: { flight_id: string }) => row.flight_id === flightId);
      if (flight && !flight.is_archived) {
        const cleanupResponse = await page.request.post(
          `${BACKEND_BASE}/api/flights/${flightId}/archive`,
          { headers: auth },
        );
        expect(cleanupResponse.ok()).toBe(true);
      }
    }
  }
});
