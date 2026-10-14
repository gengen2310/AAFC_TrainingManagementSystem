// D11 (2026-10-11): a value rendered into an inline handler's JavaScript must
// not be able to close its string literal. Reproduced before the fix with a
// custom training phase named  x');window.__pwned=1;('  -- clicking Edit ran
// the payload. After the fix the same click opens the edit modal with the
// exact name, and nothing else runs.
import { test, expect, Page } from "../e2e-fixtures";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;
const BACKEND_BASE =
  process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000";
const PAYLOAD = `x');window.__pwned=1;('"\\</b>`;

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

test("a phase name cannot break out of its inline Edit handler", async ({ page }) => {
  await loginSquadronAdmin(page);
  const made = await page.evaluate(
    async (name) =>
      (window as any).api("/api/custom-training-phases", {
        method: "POST",
        body: { name, scope_type: "squadron", applies_from: "2094-01-01" },
      }),
    PAYLOAD,
  );
  try {
    expect(made.name).toBe(PAYLOAD);
    await page.evaluate(() => {
      if (!document.getElementById("settings-custom-phases-list")) {
        const d = document.createElement("div");
        d.id = "settings-custom-phases-list";
        document.body.appendChild(d);
      }
    });
    await page.evaluate(() => (window as any).loadCustomPhases());
    await page.evaluate((id) => {
      const row = [...document.querySelectorAll(".cp-row")].find((r) =>
        r.querySelector("button")?.getAttribute("onclick")?.includes(id),
      );
      (row!.querySelector("button") as HTMLButtonElement).click();
    }, made.custom_phase_id);
    expect(await page.evaluate(() => (window as any).__pwned)).toBeUndefined();
    // The handler still works: the edit form carries the exact name.
    await expect(page.locator("#cp-edit-name-inp")).toHaveValue(PAYLOAD);
  } finally {
    await page.evaluate(
      async (id) => (window as any).api(`/api/custom-training-phases/${id}`, { method: "DELETE" }),
      made.custom_phase_id,
    );
  }
});
