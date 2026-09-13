import { test, expect, type Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;
const BACKEND = process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000";

const VIEWPORTS = [
  { width: 1440, height: 900 },
  { width: 1280, height: 800 },
  { width: 1024, height: 768 },
  { width: 768, height: 1024 },
  { width: 430, height: 932 },
  { width: 390, height: 844 },
  { width: 375, height: 812 },
] as const;

async function setLocalApiBase(page: Page) {
  if (!LOCAL_API_BASE) return;
  await page.addInitScript((base) => {
    (window as any).AAFC_API_BASE = base;
  }, LOCAL_API_BASE);
}

async function loginSquadronAdmin(page: Page) {
  await setLocalApiBase(page);
  await page.goto("/");
  await page.locator("#auth-type").selectOption("squadron");
  await page.locator("#auth-wing-select").selectOption("7WG");
  await page.locator("#auth-sqn-select").selectOption("703");
  await page.locator("#auth-role").selectOption("sqn_admin");
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill("ADMIN703");
  await page.locator("#auth-btn").click();
  await expect(page.locator(".ph-title", { hasText: "Training Dashboard" })).toBeVisible({ timeout: 10000 });
}

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

test("Main TMS authentication flow fits every release viewport", async ({ page }) => {
  await setLocalApiBase(page);

  for (const viewport of VIEWPORTS) {
    await page.setViewportSize(viewport);
    await page.goto("/");

    await expect(page.locator("#auth-type")).toBeVisible({ timeout: 10000 });
    await expect(page.locator("#auth-continue-btn")).toBeVisible();
    await expectNoRootHorizontalOverflow(page, viewport.width);
  }
});

test("authenticated Main TMS dashboard remains within the page viewport at release widths", async ({ page }) => {
  await loginSquadronAdmin(page);

  for (const viewport of VIEWPORTS) {
    await page.setViewportSize(viewport);
    await page.evaluate("nav('dashboard')");

    await expect(page.locator(".ph-title", { hasText: "Training Dashboard" })).toBeVisible({ timeout: 10000 });
    await expectNoRootHorizontalOverflow(page, viewport.width);

    const titleBox = await page.locator(".ph-title", { hasText: "Training Dashboard" }).boundingBox();
    expect(titleBox, `dashboard title has no layout box at ${viewport.width}px`).not.toBeNull();
    expect(titleBox!.x, `dashboard title starts off-screen at ${viewport.width}px`).toBeGreaterThanOrEqual(-1);
    expect(
      titleBox!.x + titleBox!.width,
      `dashboard title extends outside viewport at ${viewport.width}px`,
    ).toBeLessThanOrEqual(viewport.width + 1);
  }
});
