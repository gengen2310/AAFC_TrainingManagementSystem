// apple-design gates against DEPLOYED STAGING.
//   G5  hit targets — separating "too small" from "too close together"
//   G3  200% text   — clipping / overlap / horizontal overflow
//   G11 semantics   — controls with no accessible name
import { chromium, devices } from '@playwright/test';

const BASE = 'https://aafc-tms-frontend-staging.up.railway.app';
const CODE = process.env.STAGING_SQN_ADMIN_CODE;
const SEL = 'button, a[href], input:not([type=hidden]), select, textarea, [role=button], [role=link], [tabindex]:not([tabindex="-1"])';
const PAGES = ['dashboard', 'parade-nights', 'curriculum', 'settings', 'facilitators'];

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

// ── G5 ───────────────────────────────────────────────────────────────────────
{
  const { browser, page } = await session(devices['Pixel 7']);
  let judged = 0, tooSmall = 0, tooClose = 0;
  const smallSet = new Map(), closeSet = new Map();
  for (const nav of PAGES) {
    await page.evaluate(n => { if (typeof window.nav === 'function') window.nav(n); }, nav);
    await page.waitForTimeout(1200);
    const r = await page.evaluate(({ sel, size }) => {
      const vis = e => { const r = e.getBoundingClientRect(), s = getComputedStyle(e);
        return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'&&s.opacity!=='0'; };
      const out = [];
      for (const e of document.querySelectorAll(sel)) {
        if (!vis(e)) continue;
        const r = e.getBoundingClientRect();
        if (r.bottom < 0 || r.top > innerHeight) continue;
        const boxOk = r.width >= size && r.height >= size;
        const cx=r.left+r.width/2, cy=r.top+r.height/2, h=size/2-1;
        const hitOk = [[cx,cy-h],[cx,cy+h],[cx-h,cy],[cx+h,cy]].every(([x,y])=>{
          if (x<0||y<0||x>innerWidth||y>innerHeight) return false;
          const t=document.elementFromPoint(x,y);
          return t && (t===e||e.contains(t)||t.contains(e));
        });
        out.push({ label:(e.getAttribute('aria-label')||e.textContent||e.value||'').trim().slice(0,28),
                   w:Math.round(r.width), h:Math.round(r.height), boxOk, hitOk });
      }
      return out;
    }, { sel: SEL, size: 44 });
    judged += r.length;
    for (const c of r) {
      if (!c.boxOk) { tooSmall++; const k=`${c.w}x${c.h}  ${c.label}`; smallSet.set(k,(smallSet.get(k)||0)+1); }
      else if (!c.hitOk) { tooClose++; const k=`${c.w}x${c.h}  ${c.label}`; closeSet.set(k,(closeSet.get(k)||0)+1); }
    }
  }
  console.log(`G5  Pixel 7, 44px — judged ${judged}`);
  console.log(`      too small (box < 44):        ${tooSmall}`);
  console.log(`      big enough but not isolated: ${tooClose}`);
  console.log(`      pass:                        ${judged - tooSmall - tooClose}`);
  console.log('      smallest offenders:');
  [...smallSet.entries()].sort((a,b)=>b[1]-a[1]).slice(0,8).forEach(([k,n])=>console.log(`        ${String(n).padStart(2)}x  ${k}`));
  await browser.close();
}

// ── G3 ───────────────────────────────────────────────────────────────────────
{
  const { browser, page } = await session(devices['Desktop Chrome']);
  console.log('\nG3  text at 200%');
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
  console.log('\nG11 controls with no accessible name');
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
