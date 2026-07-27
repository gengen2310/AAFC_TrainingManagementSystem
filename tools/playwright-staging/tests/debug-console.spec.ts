import { test } from "@playwright/test";
import { ROLES, injectSession } from "./helpers/auth";

test("debug: what console errors and network failures occur during boot", async ({ page }) => {
  const errs: string[] = [];
  const netFails: string[] = [];

  page.on("console", m => {
    if (m.type() === "error") errs.push(m.text());
  });
  page.on("response", resp => {
    if (resp.status() >= 400) netFails.push(`${resp.status()} ${resp.url()}`);
  });

  const sqnAdmin = ROLES.find(r => r.role === "sqn_admin")!;
  await injectSession(page, sqnAdmin);
  await page.waitForTimeout(3000);

  console.log("Network failures:", JSON.stringify(netFails, null, 2));
  console.log("Console errors:", JSON.stringify(errs, null, 2));
});
