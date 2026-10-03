import { test, expect } from "../e2e-fixtures";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";
import { loginPW } from "../e2e-login-helper";

// Root cause of the intermittent WebKit CI failure in navigation.spec.ts
// ("Mission Backlog recommended terms"): the bottom drawer's content area had
// only a max-height, so the drawer grew when the Activities tab's data
// arrived and the tab bar jumped ~180 px UP (measured: y 556 -> 376). A click
// aimed at "Needs Attention" before the data landed hit the content instead,
// leaving Activities selected. The CI snapshot shows exactly that.
//
// Deterministic: the Activities requests are HELD until the tab position has
// been measured, then released -- no timing luck involved.

const BACKEND = process.env.E2E_BACKEND_BASE_URL || "http://localhost:8000";

test.beforeAll(async () => { await resetBackendRateLimits(BACKEND); });

test("the drawer's tab bar does not move when its tab content loads", async ({ page }) => {
  let release!: () => void;
  const gate = new Promise<void>((r) => { release = r; });
  await page.route(/\/api\/planning\/years\/[^/]+\/cea\//, async (route) => { await gate; await route.continue(); });

  await loginPW(page, "ADMIN703");
  await page.getByText("Planning Tools ▲").click();
  const tab = page.getByRole("button", { name: "Needs Attention", exact: true });
  await expect(tab).toBeVisible();
  const before = (await tab.boundingBox())!.y;

  const loaded = page.waitForResponse((r) => /\/cea\/activities/.test(r.url()));
  release();
  await loaded;
  await expect(page.getByText("CEA import history")).toBeVisible();
  const after = (await tab.boundingBox())!.y;
  expect(Math.abs(after - before), `tab bar moved from y=${before} to y=${after}`).toBeLessThanOrEqual(1);

  // And the click it protects now lands.
  await tab.click();
  await expect(tab).toHaveAttribute("aria-pressed", "true");
});
