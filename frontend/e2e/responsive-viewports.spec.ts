import { test, expect, type Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";
import { loginPW } from "../e2e-login-helper";

const BACKEND = process.env.E2E_BACKEND_BASE_URL || "http://localhost:8000";

const VIEWPORTS = [
  { width: 1440, height: 900 },
  { width: 1280, height: 800 },
  { width: 1024, height: 768 },
  { width: 768, height: 1024 },
  { width: 430, height: 932 },
  { width: 390, height: 844 },
  { width: 375, height: 812 },
] as const;

async function expectNoRootHorizontalOverflow(page: Page, width: number) {
  const metrics = await page.evaluate(() => ({
    viewportWidth: window.innerWidth,
    documentClientWidth: document.documentElement.clientWidth,
    documentScrollWidth: document.documentElement.scrollWidth,
    bodyScrollWidth: document.body.scrollWidth,
  }));

  expect(metrics.viewportWidth).toBe(width);
  expect(
    metrics.documentScrollWidth,
    `document overflow at ${width}px: scrollWidth=${metrics.documentScrollWidth}, clientWidth=${metrics.documentClientWidth}`,
  ).toBeLessThanOrEqual(metrics.documentClientWidth + 1);
  expect(
    metrics.bodyScrollWidth,
    `body overflow at ${width}px: scrollWidth=${metrics.bodyScrollWidth}, clientWidth=${metrics.documentClientWidth}`,
  ).toBeLessThanOrEqual(metrics.documentClientWidth + 1);
}

test.beforeEach(async () => {
  await resetBackendRateLimits(BACKEND);
});

test("authenticated /planning remains usable without page-level horizontal overflow at release viewports", async ({ page }) => {
  await loginPW(page, "ADMIN703");

  for (const viewport of VIEWPORTS) {
    await page.setViewportSize(viewport);
    await page.goto("/planning");

    const main = page.locator('[role="main"][aria-label="Planning workspace"]');
    await expect(main, `Planning Workspace main missing at ${viewport.width}px`).toBeVisible({ timeout: 10000 });
    await expectNoRootHorizontalOverflow(page, viewport.width);

    const box = await main.boundingBox();
    expect(box, `Planning Workspace main has no layout box at ${viewport.width}px`).not.toBeNull();
    expect(box!.x, `Planning Workspace main starts off-screen at ${viewport.width}px`).toBeGreaterThanOrEqual(-1);
    expect(
      box!.x + box!.width,
      `Planning Workspace main extends outside viewport at ${viewport.width}px`,
    ).toBeLessThanOrEqual(viewport.width + 1);
  }
});

test("unauthenticated handoff remains readable without page-level horizontal overflow at release viewports", async ({ page }) => {
  await page.goto("/");
  await page.evaluate(() => sessionStorage.clear());

  for (const viewport of VIEWPORTS) {
    await page.setViewportSize(viewport);
    await page.goto("/planning");

    await expect(page.getByRole("heading", { name: "Session not found" })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole("link", { name: "Return to TMS" })).toBeVisible();
    await expectNoRootHorizontalOverflow(page, viewport.width);
  }
});
