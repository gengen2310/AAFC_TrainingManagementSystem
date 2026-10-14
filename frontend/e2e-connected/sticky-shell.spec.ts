import { test, expect } from "../e2e-fixtures";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// D27 (2026-10-13): the left navigation and the top bar scrolled away with the
// page although both are position:sticky. html AND body had overflow-x:hidden,
// which stops body's overflow propagating to the viewport, so body became a
// scroll container that never scrolls and sticky never engaged. The page is
// made tall here so the check does not depend on how much seed data exists.
const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

// Two logins per run, after a long suite: reset the backend's per-IP limiter
// first, as the other connected specs do.
test.beforeEach(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");
});

// Make the page tall and scroll it, robustly: the app may re-render .main
// (e.g. after entering Proxy Mode), which would drop a spacer added earlier,
// and html has scroll-behavior:smooth, so scroll instantly and wait until the
// page has really moved (CI webkit, 2026-10-13).
async function scrollPageTo(page: import("@playwright/test").Page, y: number) {
  await expect.poll(async () => page.evaluate((to) => {
    if (!document.getElementById("e2e-spacer")) {
      const spacer = document.createElement("div");
      spacer.id = "e2e-spacer";
      spacer.style.height = "8000px";
      document.querySelector(".main")!.appendChild(spacer);
    }
    window.scrollTo({ top: to, behavior: "instant" as ScrollBehavior });
    return window.scrollY;
  }, y), { timeout: 10000 }).toBeGreaterThan(y - 50);
}

test("the left navigation and top bar stay on screen however far the page scrolls", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 800 });
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

  for (const y of [1500, 5000]) {
    await scrollPageTo(page, y);
    const geo = await page.evaluate(() => {
      const r = (s: string) => (document.querySelector(s) as HTMLElement).getBoundingClientRect();
      return { scrolled: window.scrollY, topbar: r(".topbar").top, navTop: r(".sidenav").top,
               navBottom: r(".sidenav").bottom, viewport: window.innerHeight };
    });
    expect(geo.scrolled, "the page must actually have scrolled").toBeGreaterThan(1000);
    expect(geo.topbar, "top bar pinned to the top").toBe(0);
    expect(geo.navTop, "navigation starts just below the top bar").toBeCloseTo(52, 0);
    expect(geo.navBottom, "navigation reaches the bottom of the window").toBeCloseTo(geo.viewport, 0);
  }
  await expect(page.locator(".sidenav .nav-item").first()).toBeInViewport();
  const hScroll = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(hScroll, "no horizontal page scroll (what overflow-x:hidden was for)").toBeLessThanOrEqual(0);
});

// Owner decision 2026-10-13: while Proxy Mode / Delegated Intervention is
// active its warning banner stays pinned under the top bar, and the
// navigation sits below it (never hidden behind it). The plain scope banner
// still scrolls away.
test("the Proxy Mode warning stays pinned under the top bar, with the navigation below it", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 800 });
  if (LOCAL_API_BASE) await page.addInitScript((b) => { (window as any).AAFC_API_BASE = b; }, LOCAL_API_BASE);
  await page.goto("/");
  await page.locator("#auth-type").selectOption("wing");
  await page.locator("#auth-wing-select").selectOption("7WG");
  await page.locator("#auth-role").selectOption("wing_admin");
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill("ADMIN7WG");
  await page.locator("#auth-btn").click();
  await expect(page.locator("#cmd-dash-wing .ph-title", { hasText: "Training Dashboard" })).toBeVisible({ timeout: 10000 });

  // eslint-disable-next-line no-undef
  await page.waitForFunction(() => ((S.squadrons || []) as { code: string }[]).some((s) => s.code === "703"));
  const sqnId = await page.evaluate(() => {
    // eslint-disable-next-line no-undef
    return ((S.squadrons || []) as { squadron_id: string; code: string }[]).find((s) => s.code === "703")!.squadron_id;
  });
  await page.evaluate((id) => { (window as any).enterMode(id, "703 SQN"); }, sqnId);
  await page.locator("#ti-input").fill("E2E sticky banner check");
  await page.locator("#ti-ok-btn").click();
  const banner = page.locator("#mode-banner.show");
  await expect(banner).toBeVisible({ timeout: 10000 });
  try {
    await scrollPageTo(page, 3000);
    const geo = await page.evaluate(() => {
      const r = (s: string) => (document.querySelector(s) as HTMLElement).getBoundingClientRect();
      return { scrolled: window.scrollY, topbarBottom: r(".topbar").bottom, bannerTop: r("#mode-banner").top,
               bannerBottom: r("#mode-banner").bottom, navTop: r(".sidenav").top, navBottom: r(".sidenav").bottom,
               viewport: window.innerHeight };
    });
    expect(geo.scrolled).toBeGreaterThan(1000);
    expect(geo.bannerTop, "warning pinned directly under the top bar").toBeCloseTo(geo.topbarBottom, 0);
    expect(geo.navTop, "navigation starts below the warning, not behind it").toBeCloseTo(geo.bannerBottom, 0);
    expect(geo.navBottom, "navigation still reaches the bottom of the window").toBeCloseTo(geo.viewport, 0);
    await expect(page.locator("#mode-banner button", { hasText: "Exit mode" })).toBeInViewport();
  } finally {
    await page.evaluate(() => (window as any).exitMode());
  }
  await expect(page.locator(".mode-banner.show")).toHaveCount(0, { timeout: 10000 });
  await scrollPageTo(page, 3000);
  const navTop = await page.evaluate(() => (document.querySelector(".sidenav") as HTMLElement).getBoundingClientRect().top);
  expect(navTop, "after leaving the mode the navigation returns to just below the top bar").toBeCloseTo(52, 0);
});
