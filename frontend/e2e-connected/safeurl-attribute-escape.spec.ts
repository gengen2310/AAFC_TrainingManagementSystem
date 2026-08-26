import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// safeUrl() must escape, not just scheme-check.
//
// It rejected javascript:/data: correctly but returned String(u) unescaped, so a
// learning_hub_url of
//     https://example.invalid/x" onmouseover="…
// closed the href attribute and installed an event handler on the <a>. Both call
// sites are href="${safeUrl(...)}" (curriculum "Learning Hub" links), and
// learning_hub_url is settable by squadron and wing admins on curriculum items
// that inherit downward -- so this rendered in other users' browsers.
//
// Verified against deployed staging before the fix: the <a> came back carrying
// href, onmouseover, target, class, onclick -- onmouseover being the injected one.
//
// Sibling of REM-150: same attribute-context class, different helper. There the
// wrong helper was used at the call site; here the helper itself was incomplete.

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

declare function safeUrl(u: string): string;

const BREAKOUT = 'https://example.invalid/x" onmouseover="window.__urlXss=true';

test.beforeAll(async () => {
  await resetBackendRateLimits(
    process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000"
  );
});

async function openApp(page: Page) {
  if (LOCAL_API_BASE) {
    await page.addInitScript((base) => { (window as any).AAFC_API_BASE = base; }, LOCAL_API_BASE);
  }
  await page.goto("/");
  await expect(page.locator("#auth-code, #auth-type")).toHaveCount(2, { timeout: 10000 });
}

test("SAFEURL-01: a quote in a URL cannot break out of the href attribute", async ({ page }) => {
  await openApp(page);

  const r = await page.evaluate((payload) => {
    (window as any).__urlXss = false;
    const host = document.createElement("div");
    // exactly the shipped curriculum "Learning Hub" link template
    host.innerHTML = `<a href="${safeUrl(payload)}" target="_blank" class="lh-btn" onclick="event.stopPropagation()">Learning Hub</a>`;
    document.body.appendChild(host);
    const a = host.querySelector("a")!;
    const attrs = [...a.attributes].map((x) => x.name);
    const injected = a.getAttribute("onmouseover");
    const href = a.getAttribute("href");
    host.remove();
    return { attrs, injected, href };
  }, BREAKOUT);

  // No handler may be created by the URL's contents.
  expect(r.injected).toBeNull();
  expect(r.attrs).not.toContain("onmouseover");
  // The whole payload stays inside href rather than being truncated at the quote.
  expect(r.href).toContain("onmouseover");
});

test("SAFEURL-02: non-http(s) schemes are still rejected, and ordinary URLs still work", async ({ page }) => {
  await openApp(page);

  const r = await page.evaluate(() => ({
    js: safeUrl("javascript:window.__urlXss=true"),
    data: safeUrl("data:text/html,<script>1</script>"),
    plain: safeUrl("https://learninghub.example/course/1?a=1&b=2"),
    empty: safeUrl(""),
  }));

  expect(r.js).toBe("#");
  expect(r.data).toBe("#");
  // Empty input returns "" rather than "#": new URL("", location.href) resolves to
  // the current page, whose scheme passes the check. Pre-existing behaviour,
  // unchanged by the escaping fix, and unreachable in practice because both call
  // sites are guarded by `e.lh ? ... : ''`. Pinned so it is not "fixed" blindly.
  expect(r.empty).toBe("");
  // A normal URL survives; & is entity-escaped for the attribute and decodes on navigation.
  expect(r.plain).toContain("learninghub.example/course/1");
  expect(r.plain).toContain("a=1");
  // & is entity-escaped for the attribute; the browser decodes it on navigation.
  expect(r.plain).toContain("&amp;b=2");
});
