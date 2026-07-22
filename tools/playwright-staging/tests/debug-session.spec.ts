import { test, expect } from "@playwright/test";
import { ROLES, injectSession, addApiProxy } from "./helpers/auth";

test("debug: injectSession boots the SPA and shows the app", async ({ page }) => {
  const sqnAdmin = ROLES.find((r) => r.role === "sqn_admin")!;
  await injectSession(page, sqnAdmin);

  // App must be visible
  await expect(page.locator("#app")).toBeVisible();
  // Nav items must be populated
  const sidenavText = await page.locator(".sidenav").innerText();
  console.log("Sidenav text:", sidenavText.substring(0, 200));
});

test("debug: addApiProxy allows browser to reach backend", async ({ page }) => {
  await addApiProxy(page);
  await page.goto("/");

  const result = await page.evaluate(async (backendUrl: string) => {
    try {
      const resp = await fetch(backendUrl + "/api/health/ready");
      const text = await resp.text();
      return { ok: resp.ok, status: resp.status, body: text };
    } catch (e: any) {
      return { ok: false, error: String(e) };
    }
  }, process.env.STAGING_API ?? "https://aafc-tms-backend-staging.up.railway.app");

  console.log("Proxied backend fetch result:", JSON.stringify(result));
  expect(result.ok).toBe(true);
});
