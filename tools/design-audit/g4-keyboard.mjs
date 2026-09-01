// G4: can every primary workflow be reached by keyboard, and is focus visible?
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import nodePath from "node:path";
// Resolve @playwright/test out of tools/playwright-staging so these run from any
// working directory. Not a symlink: a committed absolute-path symlink broke a
// working checkout on 2026-08-31.
const __req = createRequire(nodePath.join(
  nodePath.dirname(fileURLToPath(import.meta.url)), "../playwright-staging/package.json"));
const { chromium, devices } = __req("@playwright/test");
// AUDIT_BASE lets these run against a local stack before anything is
// deployed -- the rollout has to be measured before it ships, not after.
const BASE=process.env.AUDIT_BASE || 'https://aafc-tms-frontend-staging.up.railway.app';
// AUDIT_CODE + AUDIT_ROLE let the same gate run under any role. Nine of the
// 24 pages render nothing for a squadron admin, so a single-role sweep
// measures them empty and reports the result as clean.
const CODE = process.env.AUDIT_CODE || process.env.STAGING_SQN_ADMIN_CODE;
const ROLE = process.env.AUDIT_ROLE || 'sqn_admin';
const browser=await chromium.launch();
const page=await (await browser.newContext({...devices['Desktop Chrome']})).newPage();
await page.goto(BASE,{waitUntil:'domcontentloaded'});
const api=await page.getAttribute('meta[name="aafc-api-base"]','content');
await page.evaluate(async ([api,code])=>{
  const r=await fetch(api+'/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code})});
  sessionStorage.setItem('aafc_token',(await r.json()).token);
},[api,CODE]);
await page.reload({waitUntil:'domcontentloaded'}); await page.waitForTimeout(3000);

// EVERY routable page. This used to tab 80 times on whatever page happened to
// load first and report a single number, so twenty-three screens' keyboard
// behaviour was never exercised -- and the report did not say so.
const PAGES=['accounts','action-centre','action-items','activities','audit','calendar',
             'curriculum','dashboard','facilitators','getting-started','help','long-range',
             'national','national-activities','parade-nights','program-audit','resources',
             'service-desk','settings','system-console','weekly-program','wing-activities',
             'wing-calendar','wing-overview'];

// 1. Tab order reaches controls, and each focused element shows a visible ring.
let reached=0, noRing=0; const seen=new Set(); const ringless=[];
const perPage=new Map();
for (const nav of PAGES){
 await page.evaluate(n=>{if(typeof window.nav==='function')window.nav(n);},nav);
 await page.waitForTimeout(900);
 await page.evaluate(()=>{document.body.focus?.(); if(document.activeElement) document.activeElement.blur();});
 const before=reached;
 for (let i=0;i<60;i++){
  await page.keyboard.press('Tab');
  const info=await page.evaluate(()=>{
    const e=document.activeElement;
    if(!e||e===document.body) return null;
    const s=getComputedStyle(e);
    const ring=(s.outlineStyle!=='none'&&parseFloat(s.outlineWidth)>0)
            || s.boxShadow!=='none'
            || (s.borderColor && parseFloat(s.borderWidth)>1);
    return {key:e.tagName+'|'+(e.getAttribute('aria-label')||e.textContent||'').trim().slice(0,24),
            ring, tag:e.tagName.toLowerCase()};
  });
  if(!info) continue;
  if(seen.has(info.key)) continue;
  seen.add(info.key); reached++;
  if(!info.ring){ noRing++; ringless.push(nav+': '+info.key); }
 }
 perPage.set(nav, reached-before);
}
console.log(`G4 [${ROLE}] tab traversal — distinct controls reached ${reached}`);
console.log(`      pages tabbed through: ${perPage.size}`);
const quiet=[...perPage.entries()].filter(([,n])=>n===0).map(([p])=>p);
if(quiet.length) console.log(`      reached NOTHING new on: ${quiet.join(', ')}`);
console.log(`      focused with no visible indicator: ${noRing}`);
ringless.slice(0,8).forEach(k=>console.log(`        ${k}`));

// 2. Primary workflow: reach and activate a nav item using only the keyboard.
const navOk = await page.evaluate(async () => {
  const item=[...document.querySelectorAll('.nav-item')].find(e=>e.textContent.trim()==='Parade Nights');
  if(!item) return 'nav item not found';
  item.focus();
  if(document.activeElement!==item) return 'nav item did not accept focus';
  item.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));
  await new Promise(r=>setTimeout(r,900));
  const pg=document.getElementById('page-parade-nights');
  return pg && getComputedStyle(pg).display!=='none' ? 'reached parade-nights by keyboard' : 'Enter did not navigate';
});
console.log(`      primary workflow: ${navOk}`);

// 3. Escape closes a modal (agency / recoverability).
const escOk = await page.evaluate(async () => {
  if (typeof window.openModal !== 'function') return 'no openModal() to test';
  // The id is on .modal-bg (the overlay); .modal is the inner box and mostly
  // carries no id, so querying .modal returned an empty list and this check
  // reported "no modal in DOM" every run without ever pressing Escape. A check
  // that always skips is worse than no check -- it reads as a covered case.
  const ids=[...document.querySelectorAll('.modal-bg')].map(m=>m.id).filter(Boolean);
  if(!ids.length) return 'no modal in DOM';
  window.openModal(ids[0]);
  await new Promise(r=>setTimeout(r,500));
  const shown=getComputedStyle(document.getElementById(ids[0])).display!=='none';
  document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
  await new Promise(r=>setTimeout(r,600));
  const hidden=getComputedStyle(document.getElementById(ids[0])).display==='none';
  return shown ? (hidden?'Escape closes a modal':'Escape did NOT close the modal') : 'modal did not open';
});
console.log(`      escape hatch:     ${escOk}`);
await browser.close();
