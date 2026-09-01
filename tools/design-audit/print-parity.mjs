// Print-output parity check for the Weekly Program.
//
// Moving rules out of @media print so they apply on screen is exactly the kind
// of change that silently alters the printout. This renders the page under
// print emulation and dumps the computed styles that decide what paper looks
// like, so "print is unchanged" is a diff rather than an assertion.
//
//   node tools/design-audit/print-parity.mjs > before.json
//   ...make the change...
//   node tools/design-audit/print-parity.mjs > after.json && diff before.json after.json
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import nodePath from "node:path";
const __req = createRequire(nodePath.join(
  nodePath.dirname(fileURLToPath(import.meta.url)), "../playwright-staging/package.json"));
const { chromium } = __req("@playwright/test");

const BASE = process.env.AUDIT_BASE || "http://127.0.0.1:8200/index.html";
const CODE = process.env.STAGING_SQN_ADMIN_CODE || "ADMIN703";

const browser = await chromium.launch();
const page = await (await browser.newContext()).newPage();
await page.goto(BASE, { waitUntil: "domcontentloaded" });
const api = await page.getAttribute('meta[name="aafc-api-base"]', "content");
await page.evaluate(async ([api, code]) => {
  const r = await fetch(api + "/api/auth/login", { method: "POST",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code }) });
  sessionStorage.setItem("aafc_token", (await r.json()).token);
}, [api, CODE]);
await page.reload({ waitUntil: "domcontentloaded" });
await page.waitForTimeout(3000);
await page.evaluate(() => { if (typeof window.nav === "function") window.nav("weekly-program"); });
await page.waitForTimeout(1500);
// all nights, so the per-night separation is actually in the DOM
await page.evaluate(() => {
  const s = document.getElementById("wp-sel");
  if (s) { s.value = ""; s.dispatchEvent(new Event("change", { bubbles: true })); }
});
await page.waitForTimeout(2000);

await page.emulateMedia({ media: "print" });
await page.waitForTimeout(300);

const PROPS = ["display","background-color","color","font-size","font-weight","font-style",
               "text-align","border-top-width","border-top-style","border-top-color",
               "padding-top","padding-bottom","margin-bottom","break-after","page-break-after",
               "border-collapse","table-layout","width","border-radius"];
const snap = await page.evaluate((props) => {
  const pick = (sel) => {
    const e = document.querySelector(sel);
    if (!e) return { selector: sel, present: false };
    const cs = getComputedStyle(e);
    const o = { selector: sel, present: true };
    for (const p of props) o[p] = cs.getPropertyValue(p);
    return o;
  };
  return [".print-pn-block", ".print-schedule-table", ".print-schedule-table td.group-header",
          ".print-schedule-table td.night-header", ".print-schedule-table th.group-header",
          ".print-schedule-table .class-header", ".print-schedule-table .non-period-row td",
          ".print-footer"].map(pick);
}, PROPS);

console.log(JSON.stringify(snap, null, 2));
await browser.close();
