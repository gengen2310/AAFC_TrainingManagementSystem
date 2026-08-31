// G4: can every primary workflow be reached by keyboard, and is focus visible?
import { chromium, devices } from '@playwright/test';
const BASE='https://aafc-tms-frontend-staging.up.railway.app';
const CODE=process.env.STAGING_SQN_ADMIN_CODE;
const browser=await chromium.launch();
const page=await (await browser.newContext({...devices['Desktop Chrome']})).newPage();
await page.goto(BASE,{waitUntil:'domcontentloaded'});
const api=await page.getAttribute('meta[name="aafc-api-base"]','content');
await page.evaluate(async ([api,code])=>{
  const r=await fetch(api+'/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code})});
  sessionStorage.setItem('aafc_token',(await r.json()).token);
},[api,CODE]);
await page.reload({waitUntil:'domcontentloaded'}); await page.waitForTimeout(3000);

// 1. Tab order reaches controls, and each focused element shows a visible ring.
let reached=0, noRing=0; const seen=new Set(); const ringless=[];
for (let i=0;i<80;i++){
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
  if(!info.ring){ noRing++; ringless.push(info.key); }
}
console.log(`G4  tab traversal — distinct controls reached ${reached}`);
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
  const ids=[...document.querySelectorAll('.modal')].map(m=>m.id).filter(Boolean);
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
