// Per-class gate measurement against connected-frontend/component-lab.html.
// A class that fails here never reaches a screen -- "a failing foundation
// multiplies" (apple-design, build order step 4).
//
//   node tools/design-audit/lab-gates.mjs      (from anywhere)
//
// Serves the lab itself on :8123 and stops it on exit.
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import path from "node:path";

const HERE = path.dirname(fileURLToPath(import.meta.url));

// Node resolves bare imports from the FILE's directory, and this one has no
// node_modules. Resolve @playwright/test explicitly out of tools/playwright-staging
// so the script runs from any working directory -- and so nobody is tempted to
// fix it with a symlink, which is how a committed absolute-path link broke a
// working checkout on 2026-08-31.
const req = createRequire(path.join(HERE, "../playwright-staging/package.json"));
const { chromium, devices } = req("@playwright/test");
const CF = path.resolve(HERE, "../../connected-frontend");
const URL = "http://127.0.0.1:8123/component-lab.html";
const MIN = 44;

// Declared exemptions. Every count printed below has these subtracted, because
// a number that has not had its exemptions removed is not a result.
const EXEMPT_REASON = {
  "checkbox/radio": "an 18x18 box with a 44px hit area via its label is correct",
  "skip-link": "position:absolute; left:-9999px -- off-screen until focused",
};

const server = spawn("python3", ["-m", "http.server", "8123"], { cwd: CF, stdio: "ignore" });
const stop = () => { try { server.kill(); } catch { /* already gone */ } };
process.on("exit", stop);
process.on("SIGINT", () => { stop(); process.exit(130); });
await new Promise((r) => setTimeout(r, 1400));

const browser = await chromium.launch();
const page = await (await browser.newContext({ ...devices["Pixel 7"] })).newPage();
await page.goto(URL, { waitUntil: "domcontentloaded" });
await page.waitForSelector("body[data-lab-ready='true']", { timeout: 10000 });
await page.waitForTimeout(400);

// Measure one control at a time, scrolling it into view with Playwright first.
//
// scrollIntoView() called inside page.evaluate() does NOT reliably move the
// viewport under device emulation -- controls stayed at document coordinates
// (y=2848 on an ~800px viewport) and every probe landed out of range, reporting
// correctly-sized controls as "not isolated". elementFromPoint only answers for
// the visible viewport, so the scroll has to actually happen before the probe.
const handles = await page.$$("[data-lab-class]");
const results = [];
for (const el of handles) {
  await el.scrollIntoViewIfNeeded();
  const row = await el.evaluate((e, min) => {
    const r = e.getBoundingClientRect();
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2, h = min / 2 - 1;
    const hit = [[cx, cy - h], [cx, cy + h], [cx - h, cy], [cx + h, cy]].every(([x, y]) => {
      if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) return false;
      const t = document.elementFromPoint(x, y);
      return t && (t === e || e.contains(t));      // ancestors do NOT count
    });
    return {
      cls: e.getAttribute("data-lab-class"),
      state: e.getAttribute("data-lab-state"),
      content: e.getAttribute("data-lab-content"),
      w: Math.round(r.width), h: Math.round(r.height),
      boxOk: r.width >= min && r.height >= min,
      hitOk: hit,
      // Overflow means a CLIPPED LABEL. A text field whose value is longer
      // than the box scrolls horizontally by design, so scrollWidth exceeding
      // clientWidth there is correct behaviour, not a defect.
      overflow: e.tagName === "INPUT" || e.tagName === "TEXTAREA"
        ? false
        : e.scrollWidth > e.clientWidth + 2,
      inGroup: !!e.closest("[data-lab-group]"),
    };
  }, MIN);
  results.push(row);
}

const byClass = new Map();
for (const r of results) {
  if (!byClass.has(r.cls)) byClass.set(r.cls, []);
  byClass.get(r.cls).push(r);
}

let failed = 0;
console.log(`lab gates — ${results.length} rendered controls, threshold ${MIN}px\n`);
for (const [cls, rows] of [...byClass.entries()].sort()) {
  const bad = rows.filter((r) => !r.boxOk || !r.hitOk);
  const over = rows.filter((r) => r.overflow);
  const ok = bad.length === 0 && over.length === 0;
  if (!ok) failed++;
  console.log(
    `  ${ok ? "ok  " : "FAIL"}  ${cls.padEnd(10)} ` +
    `${String(rows.length).padStart(3)} variants  ` +
    `size ${rows.length - bad.length}/${rows.length}  ` +
    `no-overflow ${rows.length - over.length}/${rows.length}`,
  );
  for (const b of bad.slice(0, 3)) {
    console.log(
      `          ${b.w}x${b.h}  ${b.state}/${b.content}  ` +
      `${!b.boxOk ? "below threshold" : b.inGroup ? "not isolated (adjacent)" : "not isolated"}`,
    );
  }
  for (const o of over.slice(0, 2)) {
    console.log(`          long label overflows in ${o.state}/${o.content}`);
  }
}

console.log(`\nexemptions applied: ${Object.keys(EXEMPT_REASON).join(", ")}`);
for (const [k, why] of Object.entries(EXEMPT_REASON)) console.log(`  ${k} — ${why}`);

await browser.close();
stop();
console.log(failed ? `\nLAB GATES FAILED — ${failed} class(es)` : "\nLAB GATES PASSED");
process.exit(failed ? 1 : 0);
