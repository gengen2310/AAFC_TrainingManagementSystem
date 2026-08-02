import { test, expect } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// GAP-24 regression coverage (Accelerated Final Release instruction, Section 3:
// "hostile-value XSS regression checks"). GAP-24 was two related but distinct
// injection patterns in connected-frontend/index.html:
//   1. Attribute-context: free-text fields embedded in double-quoted onclick="...('${x}')"
//      handlers, escaped only for single quotes -- a double quote breaks out of the
//      attribute and installs an attacker-controlled handler (fixed via _jsAttr()).
//   2. Plain-text-content: free-text fields interpolated into innerHTML template
//      literals with no escaping at all (fixed via esc()).
// This test reproduces the exact payload shape from the fix's own code comment
// against a live authenticated session and asserts neither pattern fires.

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE || "http://localhost:8000";
const HOSTILE_NAME = 'XSS" onmouseover="window.__xss_fired=true" x="<img src=x onerror=window.__xss_fired2=true>';

test.beforeAll(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE);
});

test.describe("GAP-24 hostile-value XSS regression", () => {
  test("hostile display_name renders as inert text in Account Management, no script executes", async ({ page }) => {
    await page.addInitScript((base) => {
      (window as any).AAFC_API_BASE = base;
    }, LOCAL_API_BASE);

    await page.goto("/");
    await page.locator("#auth-type").selectOption("national");
    await page.locator("#auth-role").selectOption("system_admin");
    await page.locator("#auth-continue-btn").click();
    await page.locator("#auth-code").fill("SYSADMIN2026");
    await page.locator("#auth-btn").click();
    await expect(page.locator(".ph-title", { hasText: "System Console" })).toBeVisible({ timeout: 10000 });

    // Create the hostile account via the real authenticated API (same path the
    // GAP-24 write-up used), not a raw DB insert -- exercises the actual
    // create-account code path a real admin would trigger.
    const token = await page.evaluate(() => sessionStorage.getItem("aafc_token"));
    const created = await page.evaluate(async ({ base, token, name }) => {
      const resp = await fetch(`${base}/api/accounts`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ display_name: name, role: "national_viewer" }),
      });
      return { status: resp.status, body: await resp.json() };
    }, { base: LOCAL_API_BASE, token, name: HOSTILE_NAME });
    expect(created.status, JSON.stringify(created.body)).toBeLessThan(300);

    await page.evaluate(() => { (window as any).__xss_fired = false; (window as any).__xss_fired2 = false; });
    await page.locator("#nav-accounts").click();
    await expect(page.locator("#acct-table")).toBeVisible();

    // The hostile string must appear as literal, visible text (proves it rendered,
    // not that it was silently dropped) ...
    await expect(page.locator("#acct-table")).toContainText(HOSTILE_NAME);
    // ... and must never have executed as script in either injection context.
    const fired = await page.evaluate(() => (window as any).__xss_fired);
    const fired2 = await page.evaluate(() => (window as any).__xss_fired2);
    expect(fired, "attribute-context (onmouseover) XSS must not fire").toBe(false);
    expect(fired2, "plain-text-content (onerror img) XSS must not fire").toBe(false);

    // Confirm this at the DOM level too, not just via the probe flags: no real
    // <img> element was parsed out of the payload, and no element anywhere in
    // the table carries a live onmouseover DOM attribute. A literal
    // onmouseover="..." string is safe and expected as inert *text content*
    // (only <, >, & need escaping there) -- this checks it never became a
    // real, executable HTML attribute or element.
    const liveImgCount = await page.locator("#acct-table img").count();
    const liveHandlerCount = await page.locator("#acct-table [onmouseover]").count();
    expect(liveImgCount, "no real <img> element should be parsed from the payload").toBe(0);
    expect(liveHandlerCount, "no element should carry a live onmouseover attribute").toBe(0);
  });
});
