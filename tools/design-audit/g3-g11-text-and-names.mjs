// apple-design gates. Runs against staging by default, or any AUDIT_BASE.
//   G3  200% text   — clipping / overlap / horizontal overflow
//   G11 semantics   — controls with no accessible name
// G5 is measured by g5-hit-targets.mjs; see the note below.
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import nodePath from "node:path";
// Resolve @playwright/test out of tools/playwright-staging so these run from any
// working directory. Not a symlink: a committed absolute-path symlink broke a
// working checkout on 2026-08-31.
const __req = createRequire(nodePath.join(
  nodePath.dirname(fileURLToPath(import.meta.url)), "../playwright-staging/package.json"));
const { chromium, devices } = __req("@playwright/test");

// AUDIT_BASE lets this run against a local stack before anything is deployed.
// The other scripts already took it; this one did not, which meant the G3 and
// G11 gates could only ever be run after a deploy.
const BASE = process.env.AUDIT_BASE || 'https://aafc-tms-frontend-staging.up.railway.app';
// AUDIT_CODE + AUDIT_ROLE let the same gate run under any role. Nine of the
// 24 pages render nothing for a squadron admin, so a single-role sweep
// measures them empty and reports the result as clean.
const CODE = process.env.AUDIT_CODE || process.env.STAGING_SQN_ADMIN_CODE;
const ROLE = process.env.AUDIT_ROLE || 'sqn_admin';
const SEL = 'button, a[href], input:not([type=hidden]), select, textarea, [role=button], [role=link], [tabindex]:not([tabindex="-1"])';
// EVERY routable page, enumerated from the id="page-*" elements in
// connected-frontend/index.html. Five of twenty-four was the coverage that let
// undersized controls and a print-only stylesheet ship unnoticed.
const PAGES = ['accounts','action-centre','action-items','activities','audit','calendar',
               'curriculum','dashboard','facilitators','getting-started','help','long-range',
               'national','national-activities','parade-nights','program-audit','resources',
               'service-desk','settings','system-console','weekly-program','wing-activities',
               'wing-calendar','wing-overview'];

async function session(device) {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ ...device });
  const page = await ctx.newPage();
  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  const api = await page.getAttribute('meta[name="aafc-api-base"]', 'content');
  await page.evaluate(async ([api, code]) => {
    const r = await fetch(api + '/api/auth/login', { method: 'POST',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ code }) });
    sessionStorage.setItem('aafc_token', (await r.json()).token);
  }, [api, CODE]);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3000);
  return { browser, page };
}

// G5 is NOT measured here. It used to be, with a second implementation that
// disagreed with tools/design-audit/g5-hit-targets.mjs -- 8 "too small" against
// that script's 0. The whole difference was two corrections this copy never
// received: the checkbox/radio exemption (an 18x18 box carries its target via
// the label), and skipping controls clipped by a scroll ancestor rather than
// scoring them unreachable.
//
// Two implementations of one gate that report different numbers are worse than
// one, because the disagreement discredits both. G5 lives in g5-hit-targets.mjs.

// ── G3 ───────────────────────────────────────────────────────────────────────
{
  const { browser, page } = await session(devices['Desktop Chrome']);
  console.log(`\nG3 [${ROLE}] text at 200%`);
  for (const nav of PAGES) {
    await page.evaluate(n => { if (typeof window.nav === 'function') window.nav(n); }, nav);
    await page.waitForTimeout(1000);
    const before = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }));
    await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
    await page.waitForTimeout(900);
    const after = await page.evaluate(() => {
      const d = document.documentElement;
      let clipped = 0;
      for (const e of document.querySelectorAll('button, a, h1, h2, h3, label, td, th, .card, .nav-item')) {
        const s = getComputedStyle(e);
        if (s.overflow === 'hidden' && e.scrollHeight > e.clientHeight + 2) clipped++;
      }
      return { sw: d.scrollWidth, cw: d.clientWidth, clipped };
    });
    await page.evaluate(() => { document.documentElement.style.fontSize = ''; });
    const overflow = after.sw > after.cw + 2;
    console.log(`      ${nav.padEnd(15)} h-overflow ${overflow ? 'YES  (' + (after.sw - after.cw) + 'px)' : 'no '}   clipped elements ${after.clipped}`);
  }
  await browser.close();
}

// ── G11 ──────────────────────────────────────────────────────────────────────
{
  const { browser, page } = await session(devices['Desktop Chrome']);
  console.log(`\nG11 [${ROLE}] controls with no accessible name`);
  let total = 0, unnamed = 0; const set = new Map();
  for (const nav of PAGES) {
    await page.evaluate(n => { if (typeof window.nav === 'function') window.nav(n); }, nav);
    await page.waitForTimeout(1000);
    const r = await page.evaluate(sel => {
      const vis = e => { const r=e.getBoundingClientRect(), s=getComputedStyle(e);
        return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'; };
      const out=[];
      for (const e of document.querySelectorAll(sel)) {
        if (!vis(e)) continue;
        const name = (e.getAttribute('aria-label') || e.getAttribute('title') ||
                      (e.labels && e.labels[0]?.textContent) || e.textContent || e.value || '').trim();
        out.push({ named: name.length > 0, tag: e.tagName.toLowerCase(),
                   cls: (e.className || '').toString().slice(0, 40) });
      }
      return out;
    }, SEL);
    total += r.length;
    r.filter(x => !x.named).forEach(x => { unnamed++; const k=`${x.tag}.${x.cls}`; set.set(k,(set.get(k)||0)+1); });
  }
  console.log(`      controls ${total}   unnamed ${unnamed}`);
  [...set.entries()].sort((a,b)=>b[1]-a[1]).slice(0,8).forEach(([k,n])=>console.log(`        ${String(n).padStart(3)}x  ${k}`));
  await browser.close();
}
