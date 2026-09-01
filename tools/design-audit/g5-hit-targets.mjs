// G5, corrected: a probe landing on an ANCESTOR is not a hit on the control.
// Only the element itself or a descendant counts (a ::after hit-area extender
// reports as the element itself, so those still pass — which is the point).
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
const CODE=process.env.STAGING_SQN_ADMIN_CODE;
const SEL='button, a[href], input:not([type=hidden]), select, textarea, [role=button], [role=link], [tabindex]:not([tabindex="-1"])';
const PAGES=['dashboard','parade-nights','curriculum','settings','facilitators'];

for (const [name, device, size] of [['Pixel 7 (touch)', devices['Pixel 7'], 44],
                                    ['Desktop (pointer)', devices['Desktop Chrome'], 28]]) {
  const browser=await chromium.launch();
  const page=await (await browser.newContext({...device})).newPage();
  await page.goto(BASE,{waitUntil:'domcontentloaded'});
  const api=await page.getAttribute('meta[name="aafc-api-base"]','content');
  await page.evaluate(async ([api,code])=>{
    const r=await fetch(api+'/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code})});
    sessionStorage.setItem('aafc_token',(await r.json()).token);
  },[api,CODE]);
  await page.reload({waitUntil:'domcontentloaded'}); await page.waitForTimeout(3000);

  let judged=0, boxFail=0, hitFail=0, savedByHitArea=0;
  const off=new Map();
  for (const nav of PAGES) {
    await page.evaluate(n=>{if(typeof window.nav==='function')window.nav(n);},nav);
    await page.waitForTimeout(1200);
    // SIZE is measured for every visible control -- getBoundingClientRect
    // returns dimensions regardless of scroll, so no scrolling is needed and
    // none is done. HIT-TESTING can only be answered for controls currently in
    // the viewport, because elementFromPoint does not see past the fold, so it
    // is reported as an explicitly smaller subset rather than mixed into the
    // size figure. Conflating the two made the hit-failure count EXCEED the
    // size-failure count, which is how the error announced itself.
    const r=await page.evaluate(({sel,size})=>{
      const vis=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);
        return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'&&s.opacity!=='0';};
      const out=[];
      for(const e of document.querySelectorAll(sel)){
        if(!vis(e))continue;
        const r=e.getBoundingClientRect();
        if(r.bottom<0||r.top>innerHeight||r.right<0||r.left>innerWidth)continue;  // off-screen: not judged
        const boxOk=r.width>=size&&r.height>=size;
        const cx=r.left+r.width/2, cy=r.top+r.height/2, h=size/2-1;
        const hitOk=[[cx,cy-h],[cx,cy+h],[cx-h,cy],[cx+h,cy]].every(([x,y])=>{
          if(x<0||y<0||x>innerWidth||y>innerHeight)return false;
          const t=document.elementFromPoint(x,y);
          return t && (t===e || e.contains(t));      // ancestors do NOT count
        });
        out.push({label:(e.getAttribute('aria-label')||e.textContent||e.value||'').trim().slice(0,28),
                  w:Math.round(r.width),h:Math.round(r.height),boxOk,hitOk});
      }
      return out;
    },{sel:SEL,size});
    judged+=r.length;
    for(const c of r){
      if(!c.boxOk) boxFail++;
      if(!c.hitOk){ hitFail++; const k=`${c.w}x${c.h}  ${c.label}`; off.set(k,(off.get(k)||0)+1); }
      if(!c.boxOk && c.hitOk) savedByHitArea++;
    }
  }
  console.log(`\n══ ${name} — threshold ${size}px ══`);
  console.log(`   judged                       ${judged}`);
  console.log(`   box below threshold          ${boxFail}`);
  console.log(`   rescued by a larger hit area ${savedByHitArea}`);
  console.log(`   FAIL (not reachable at ${size}px) ${hitFail}   →  ${judged?Math.round(100*hitFail/judged):0}%`);
  console.log('   worst offenders:');
  [...off.entries()].sort((a,b)=>b[1]-a[1]).slice(0,8).forEach(([k,n])=>console.log(`     ${String(n).padStart(2)}x  ${k}`));
  await browser.close();
}
