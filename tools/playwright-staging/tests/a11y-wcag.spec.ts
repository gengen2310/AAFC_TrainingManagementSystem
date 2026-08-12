/**
 * A11Y-WCAG — Zoom, Reflow, and Color Contrast Tests
 *
 * Covers WCAG 2.2 success criteria not tested by A11Y-01 (which targets
 * select-name, label, and duplicate-id rules):
 *
 * - SC 1.4.10 Reflow: content at 320 CSS-pixel width must not require
 *   horizontal scrolling (tested by setting viewport to 320 px wide)
 * - SC 1.4.4 Resize Text: text must remain readable at 200% zoom
 *   (simulated via 640 px viewport on a 1280 px reference layout)
 * - SC 1.4.3 Contrast (Minimum): normal text ≥ 4.5:1, large text ≥ 3:1
 *   (tested via Axe color-contrast rule)
 *
 * Roles covered: system_admin (unauthenticated login form + post-login pages).
 * Wing/sqn admin contrast tests are identical in rendered colour tokens;
 * the login form and dashboard cover the full palette.
 *
 * Run command:
 *   STAGING_SYSADMIN_CODE=... npx playwright test a11y-wcag --project=chromium
 */

import { test, expect, Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const STAGING_URL = process.env.STAGING_URL ?? "https://aafc-tms-frontend-staging.up.railway.app";
const STAGING_WING_ID = process.env.STAGING_WING_ID ?? "7WG";

// Disable x-test-run header so staging CORS doesn't reject real-browser flows
test.use({ extraHTTPHeaders: {} });

// ── Helpers ───────────────────────────────────────────────────────────────

async function loginSysAdmin(page: Page) {
  const code = process.env.STAGING_SYSADMIN_CODE ?? "";
  if (!code) test.skip(true, "STAGING_SYSADMIN_CODE not set");

  await page.goto(STAGING_URL + "/");
  await page.waitForSelector("#auth-step1", { state: "visible", timeout: 20000 });
  await page.selectOption("#auth-type", "national");
  await page.waitForFunction(() => {
    const sel = document.querySelector<HTMLSelectElement>("#auth-role");
    return sel && sel.options.length > 1;
  }, { timeout: 5000 });
  await page.selectOption("#auth-role", "system_admin");
  await page.waitForSelector("#auth-continue-btn:not([disabled])", { timeout: 5000 });
  await page.click("#auth-continue-btn");
  await page.waitForSelector("#auth-step2", { state: "visible", timeout: 10000 });
  await page.fill("#auth-code", code);
  await page.click("#auth-btn");
  await page.waitForSelector("#auth-screen", { state: "hidden", timeout: 15000 });
}

async function navTo(page: Page, pageId: string) {
  await page.evaluate((id) => { (window as any).nav(id); }, pageId);
}

// ── SC 1.4.10 Reflow (320 px viewport) ───────────────────────────────────

test.describe("[A11Y-WCAG] SC 1.4.10 Reflow — 320 px viewport", () => {
  test.use({ viewport: { width: 320, height: 600 } });

  test("Login form — no horizontal overflow at 320 px", async ({ page }) => {
    await page.goto(STAGING_URL + "/");
    await page.waitForSelector("#auth-step1", { state: "visible", timeout: 20000 });

    const overflow = await page.evaluate(() => {
      const main = document.querySelector("main, #auth-screen, body") as HTMLElement;
      return { scrollWidth: main.scrollWidth, clientWidth: main.clientWidth };
    });
    expect(
      overflow.scrollWidth,
      `Login form introduces horizontal scroll at 320 px: scrollWidth=${overflow.scrollWidth} clientWidth=${overflow.clientWidth}`
    ).toBeLessThanOrEqual(overflow.clientWidth + 4); // 4 px tolerance for scrollbar rounding
    console.log(`  ✓ Login form: scrollWidth=${overflow.scrollWidth} clientWidth=${overflow.clientWidth}`);
  });

  test("Dashboard (system_admin) — main content no horizontal overflow at 320 px", async ({ page }) => {
    const code = process.env.STAGING_SYSADMIN_CODE ?? "";
    if (!code) test.skip(true, "STAGING_SYSADMIN_CODE not set");
    await loginSysAdmin(page);
    await navTo(page, "dashboard");
    await page.waitForSelector("#page-dashboard.active", { timeout: 10000 });

    const overflow = await page.evaluate(() => {
      const main = document.querySelector("main.main") as HTMLElement | null;
      if (!main) throw new Error("main.main not found — page may not have rendered");
      return { scrollWidth: main.scrollWidth, clientWidth: main.clientWidth };
    });
    expect(
      overflow.scrollWidth,
      `Dashboard main content scrolls horizontally at 320 px: scrollWidth=${overflow.scrollWidth}`
    ).toBeLessThanOrEqual(overflow.clientWidth + 4);
    console.log(`  ✓ Dashboard: main scrollWidth=${overflow.scrollWidth} clientWidth=${overflow.clientWidth}`);
  });

  test("Parade Nights (sqn_admin) — main content no horizontal overflow at 320 px", async ({ page }) => {
    const code = process.env.STAGING_SQN_ADMIN_CODE ?? "";
    if (!code) test.skip(true, "STAGING_SQN_ADMIN_CODE not set");

    await page.goto(STAGING_URL + "/");
    await page.waitForSelector("#auth-step1", { state: "visible", timeout: 20000 });
    await page.selectOption("#auth-type", "squadron");
    await page.waitForFunction(() => {
      const sel = document.querySelector<HTMLSelectElement>("#auth-wing-select");
      return sel && sel.options.length > 1;
    }, { timeout: 10000 });
    await page.selectOption("#auth-wing-select", STAGING_WING_ID);
    await page.waitForFunction(() => {
      const sel = document.querySelector<HTMLSelectElement>("#auth-sqn-select");
      return sel && sel.options.length > 1;
    }, { timeout: 10000 });
    const sqnValue = await page.evaluate(() => {
      const sel = document.querySelector<HTMLSelectElement>("#auth-sqn-select");
      const opt = sel && Array.from(sel.options).find(o => o.text.includes("703"));
      return opt ? opt.value : "";
    });
    if (!sqnValue) test.skip(true, "Squadron 703 not found in dropdown");
    await page.selectOption("#auth-sqn-select", sqnValue);
    await page.waitForFunction(() => {
      const sel = document.querySelector<HTMLSelectElement>("#auth-role");
      return sel && sel.options.length > 1;
    }, { timeout: 5000 });
    await page.selectOption("#auth-role", "sqn_admin");
    await page.click("#auth-continue-btn");
    await page.waitForSelector("#auth-step2", { state: "visible", timeout: 10000 });
    await page.fill("#auth-code", code);
    await page.click("#auth-btn");
    await page.waitForSelector("#auth-screen", { state: "hidden", timeout: 15000 });

    await navTo(page, "parade-nights");
    await page.waitForSelector("#page-parade-nights.active", { timeout: 10000 });

    const overflow = await page.evaluate(() => {
      const main = document.querySelector("main.main") as HTMLElement | null;
      if (!main) throw new Error("main.main not found — page may not have rendered");
      return { scrollWidth: main.scrollWidth, clientWidth: main.clientWidth };
    });
    expect(
      overflow.scrollWidth,
      `Parade Nights scrolls horizontally at 320 px: scrollWidth=${overflow.scrollWidth}`
    ).toBeLessThanOrEqual(overflow.clientWidth + 4);
    console.log(`  ✓ Parade Nights: main scrollWidth=${overflow.scrollWidth} clientWidth=${overflow.clientWidth}`);
  });
});

// ── SC 1.4.4 Resize Text — 200% zoom simulation (640 px viewport) ─────────

test.describe("[A11Y-WCAG] SC 1.4.4 Resize Text — 200% zoom (640 px)", () => {
  // WCAG 1.4.4: text must remain usable at 200% zoom. Playwright cannot set
  // browser zoom directly; the standard simulation is halving the reference
  // viewport width (1280 → 640 px) — equivalent to 200% zoom on a 1280 px display.
  test.use({ viewport: { width: 640, height: 900 } });

  test("Login form renders without content loss at 200% zoom", async ({ page }) => {
    await page.goto(STAGING_URL + "/");
    await page.waitForSelector("#auth-step1", { state: "visible", timeout: 20000 });

    // All key login form elements must still be visible
    await expect(page.locator("#auth-type")).toBeVisible();
    await expect(page.locator("#auth-continue-btn")).toBeVisible();
    await expect(page.locator('label[for="auth-type"]')).toBeVisible();
    console.log("  ✓ Login form: all controls visible at 640 px (200% zoom simulation)");
  });

  test("Dashboard content remains visible at 200% zoom — no clipped critical controls", async ({ page }) => {
    const code = process.env.STAGING_SYSADMIN_CODE ?? "";
    if (!code) test.skip(true, "STAGING_SYSADMIN_CODE not set");
    await loginSysAdmin(page);
    await navTo(page, "dashboard");
    await page.waitForSelector("#page-dashboard.active", { timeout: 10000 });

    // The dashboard title must be visible (not clipped off-screen)
    const titleVisible = await page.evaluate(() => {
      const el = document.querySelector(".ph-title") as HTMLElement;
      if (!el) return false;
      const rect = el.getBoundingClientRect();
      return rect.width > 0 && rect.height > 0 && rect.top >= 0;
    });
    expect(titleVisible, "Dashboard .ph-title must be visible at 640 px viewport").toBe(true);
    console.log("  ✓ Dashboard: .ph-title visible at 640 px (200% zoom simulation)");

    // No horizontal overflow in main content
    const overflow = await page.evaluate(() => {
      const main = document.querySelector("main.main") as HTMLElement | null;
      if (!main) throw new Error("main.main not found — page may not have rendered");
      return { scrollWidth: main.scrollWidth, clientWidth: main.clientWidth };
    });
    expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth + 4);
    console.log(`  ✓ Dashboard: no horizontal overflow at 640 px — scrollWidth=${overflow.scrollWidth}`);
  });
});

// ── SC 1.4.3 Contrast (color-contrast Axe rule) ───────────────────────────

test.describe("[A11Y-WCAG] SC 1.4.3 Color Contrast", () => {
  // The AAFC TMS palette was audited for WCAG AA compliance during development:
  // - --muted (#657380) was darkened from #6b7a87 (failed 4.13:1) to meet 4.5:1
  // - --muted-text-on-light (#6e7275) was computed against both --surface and --bg
  // - Brand --blue (#51b0e3) is not used as text on light backgrounds
  // Running Axe color-contrast as a hard assertion to catch future regressions.

  test("Login form — zero color-contrast violations (WCAG AA)", async ({ page }) => {
    await page.goto(STAGING_URL + "/");
    await page.waitForSelector("#auth-step1", { state: "visible", timeout: 20000 });

    const results = await new AxeBuilder({ page })
      .withRules(["color-contrast"])
      .analyze();

    if (results.violations.length > 0) {
      for (const v of results.violations) {
        for (const node of v.nodes) {
          console.log(`  [contrast] ${node.target}: ${node.html?.slice(0, 100)}`);
          for (const msg of node.any.slice(0, 2)) {
            console.log(`    ${msg.message}`);
          }
        }
      }
    }
    expect(
      results.violations,
      `Login form color-contrast violations: ${results.violations.map(v => v.id).join(", ")}`
    ).toHaveLength(0);
  });

  test("Dashboard (system_admin) — zero color-contrast violations (WCAG AA)", async ({ page }) => {
    const code = process.env.STAGING_SYSADMIN_CODE ?? "";
    if (!code) test.skip(true, "STAGING_SYSADMIN_CODE not set");
    await loginSysAdmin(page);
    await navTo(page, "dashboard");
    await page.waitForSelector("#page-dashboard.active", { timeout: 10000 });

    const results = await new AxeBuilder({ page })
      .withRules(["color-contrast"])
      .analyze();

    if (results.violations.length > 0) {
      for (const v of results.violations) {
        for (const node of v.nodes) {
          console.log(`  [contrast] ${node.target}: ${node.html?.slice(0, 100)}`);
          for (const msg of node.any.slice(0, 2)) {
            console.log(`    ${msg.message}`);
          }
        }
      }
    }
    expect(
      results.violations,
      `Dashboard color-contrast violations: ${results.violations.map(v => v.id).join(", ")}`
    ).toHaveLength(0);
  });

  test("System Console (system_admin) — zero color-contrast violations (WCAG AA)", async ({ page }) => {
    const code = process.env.STAGING_SYSADMIN_CODE ?? "";
    if (!code) test.skip(true, "STAGING_SYSADMIN_CODE not set");
    await loginSysAdmin(page);
    await navTo(page, "system-console");
    await page.waitForSelector("#page-system-console.active", { timeout: 10000 });

    const results = await new AxeBuilder({ page })
      .withRules(["color-contrast"])
      .analyze();

    if (results.violations.length > 0) {
      for (const v of results.violations) {
        for (const node of v.nodes.slice(0, 5)) {
          console.log(`  [contrast] ${node.target}: ${node.html?.slice(0, 100)}`);
        }
      }
    }
    expect(
      results.violations,
      `System Console color-contrast violations: ${results.violations.map(v => v.id).join(", ")}`
    ).toHaveLength(0);
  });

  test("Wing Overview (wing_admin) — zero color-contrast violations (WCAG AA)", async ({ page }) => {
    const code = process.env.STAGING_WING_ADMIN_CODE ?? "";
    if (!code) test.skip(true, "STAGING_WING_ADMIN_CODE not set");

    await page.goto(STAGING_URL + "/");
    await page.waitForSelector("#auth-step1", { state: "visible", timeout: 20000 });
    await page.selectOption("#auth-type", "wing");
    await page.waitForFunction(() => {
      const sel = document.querySelector<HTMLSelectElement>("#auth-wing-select");
      return sel && sel.options.length > 1;
    }, { timeout: 10000 });
    await page.selectOption("#auth-wing-select", STAGING_WING_ID);
    await page.waitForFunction(() => {
      const sel = document.querySelector<HTMLSelectElement>("#auth-role");
      return sel && sel.options.length > 1;
    }, { timeout: 5000 });
    await page.selectOption("#auth-role", "wing_admin");
    await page.click("#auth-continue-btn");
    await page.waitForSelector("#auth-step2", { state: "visible", timeout: 10000 });
    await page.fill("#auth-code", code);
    await page.click("#auth-btn");
    await page.waitForSelector("#auth-screen", { state: "hidden", timeout: 15000 });

    await page.waitForSelector("#page-wing-overview.active", { timeout: 10000 });

    const results = await new AxeBuilder({ page })
      .withRules(["color-contrast"])
      .analyze();

    if (results.violations.length > 0) {
      for (const v of results.violations) {
        for (const node of v.nodes.slice(0, 5)) {
          console.log(`  [contrast] ${node.target}: ${node.html?.slice(0, 100)}`);
        }
      }
    }
    expect(
      results.violations,
      `Wing Overview color-contrast violations: ${results.violations.map(v => v.id).join(", ")}`
    ).toHaveLength(0);
  });
});
