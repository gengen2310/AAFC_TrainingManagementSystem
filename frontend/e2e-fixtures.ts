// Shared Playwright `test` for both suites (e2e/ and e2e-connected/).
//
// Both frontends load a render-blocking Google Fonts stylesheet, so the page's
// `load` event -- which page.goto() waits for -- depends on a third-party CDN.
// When that CDN is slow from a CI runner, goto() times out even though our own
// server has already returned the page (CI WebKit, run 36514289633: static
// server served GET / with 200, then `load` never fired). This auto fixture
// passes the real fonts through when they arrive promptly, so layout assertions
// still see real Montserrat metrics, and serves an empty response only when the
// CDN exceeds `fontFetchTimeoutMs`.
import { test as base, expect } from "@playwright/test";
import type { APIRequestContext, Page } from "@playwright/test";

export { expect };
export type { Page };

/**
 * First YYYY-MM-DD in [from, to] (inclusive) that no non-archived parade night of
 * the caller's squadron already uses. Parade-night dates are unique per squadron
 * among non-archived nights (POST /api/parade-nights -> 409 duplicate_date), and
 * several specs share the same future years, so clock-derived days collided on
 * some runs (e.g. CI/local Firefox: 409 -> parade_night_id undefined -> 404).
 * `exclude` reserves dates the caller is about to use itself.
 */
export async function firstFreeParadeDate(
  request: APIRequestContext,
  apiBase: string,
  headers: Record<string, string>,
  from: string,
  to: string,
  exclude: string[] = [],
): Promise<string> {
  const res = await request.get(`${apiBase}/api/parade-nights`, { headers });
  expect(res.ok(), `list parade nights -> ${res.status()}`).toBe(true);
  const taken = new Set<string>([
    ...((await res.json()) as Array<{ date?: string }>).map((pn) => String(pn.date || "").slice(0, 10)),
    ...exclude,
  ]);
  for (let d = new Date(`${from}T00:00:00Z`); d <= new Date(`${to}T00:00:00Z`); d.setUTCDate(d.getUTCDate() + 1)) {
    const iso = d.toISOString().slice(0, 10);
    if (!taken.has(iso)) return iso;
  }
  throw new Error(`no free parade-night date between ${from} and ${to}`);
}

const GOOGLE_FONTS = /^https:\/\/fonts\.(googleapis|gstatic)\.com\//;

export const test = base.extend<{ fontFetchTimeoutMs: number; _externalFontsGuard: void }>({
  fontFetchTimeoutMs: [5000, { option: true }],
  _externalFontsGuard: [
    async ({ context, fontFetchTimeoutMs }, use) => {
      await context.route(GOOGLE_FONTS, async (route) => {
        try {
          const response = await route.fetch({ timeout: fontFetchTimeoutMs });
          await route.fulfill({ response });
        } catch {
          const css = route.request().resourceType() === "stylesheet";
          await route.fulfill({ status: 200, contentType: css ? "text/css" : "font/woff2", body: "" });
        }
      });
      await use();
    },
    { auto: true },
  ],
});
