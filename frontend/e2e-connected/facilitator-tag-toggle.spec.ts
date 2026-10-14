import { test, expect } from "../e2e-fixtures";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// R13 (2026-10-13): toggleTagVocab() rebuilt its own onclick with
// setAttribute() and _jsAttr(). setAttribute() is not HTML-decoded, so the
// HTML escaping reached the handler: from the second click, "Air & Space"
// arrived as "Air &amp; Space", then "Air &amp;amp; Space". Saving read the
// chip text, so no data was corrupted, but the handler's argument was wrong.
const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

test("a subject-area chip passes its exact name to the toggle on every click", async ({ page }) => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");
  if (LOCAL_API_BASE) await page.addInitScript((b) => { (window as any).AAFC_API_BASE = b; }, LOCAL_API_BASE);
  await page.goto("/");
  await page.locator("#auth-type").selectOption("squadron");
  await page.locator("#auth-wing-select").selectOption("7WG");
  await page.locator("#auth-sqn-select").selectOption("703");
  await page.locator("#auth-role").selectOption("sqn_admin");
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill("ADMIN703");
  await page.locator("#auth-btn").click();
  await expect(page.locator(".ph-title", { hasText: "Training Dashboard" })).toBeVisible({ timeout: 10000 });
  // eslint-disable-next-line no-undef
  await page.waitForFunction(() => ((S.facs || []) as unknown[]).length > 0);

  await page.evaluate(() => {
    // eslint-disable-next-line no-undef
    (window as any).tagFac((S.facs as { id: string }[])[0].id);
    const seen: string[] = [];
    (window as any).__tagVals = seen;
    const orig = (window as any).toggleTagVocab;
    (window as any).toggleTagVocab = (btn: HTMLElement, val: string, on: unknown) => { seen.push(val); return orig(btn, val, on); };
  });
  const chip = page.locator("#m-tag-checks button", { hasText: "Air & Space" });
  await expect(chip).toBeVisible();
  for (let i = 0; i < 3; i++) await chip.click();
  const vals = await page.evaluate(() => (window as any).__tagVals as string[]);
  expect(vals).toEqual(["Air & Space", "Air & Space", "Air & Space"]);
  await page.evaluate(() => (window as any).closeModal("m-tag-fac"));
});
