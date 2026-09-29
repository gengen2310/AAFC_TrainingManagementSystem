import { test, expect } from "../e2e-fixtures";

// Regression for CI run 36514289633 (WebKit): a slow Google Fonts CDN blocked
// the page `load` event, so page.goto() timed out although our server had
// already returned the page. Force the guard's fallback path and prove the app
// still loads and renders.
test.use({ fontFetchTimeoutMs: 1 });

test("a stalled Google Fonts CDN does not block Main TMS from loading", async ({ page }) => {
  await page.goto("/", { timeout: 15000 });
  await expect(page.locator("#auth-type")).toBeVisible();
});
