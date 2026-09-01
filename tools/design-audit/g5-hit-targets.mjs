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
// EVERY routable page, not a hand-picked six. Twice now a control shipped
// below standard because the page it lived on was not in this list, and an
// unmeasured page is indistinguishable from a clean one in the output.
// Enumerated from the id="page-*" elements in connected-frontend/index.html.
//
// Several of these are role-gated and will render nothing for a squadron
// admin. That is fine and expected -- what matters is that the report SAYS
// a page contributed nothing, rather than quietly averaging it away as a
// pass. Run the suite under more than one role to cover the gated screens.
const PAGES=['accounts','action-centre','action-items','activities','audit','calendar',
             'curriculum','dashboard','facilitators','getting-started','help','long-range',
             'national','national-activities','parade-nights','program-audit','resources',
             'service-desk','settings','system-console','weekly-program','wing-activities',
             'wing-calendar','wing-overview'];

// THREE profiles, not two. The first version ran only the two obvious ones and
// had a hole big enough to hide fourteen controls: the 44px touch threshold was
// only ever applied to a PHONE viewport, where the sidenav is collapsed behind
// the hamburger and never renders. Desktop ran at the 28px pointer threshold,
// so the 41px .nav-item passed there. Nothing measured a desktop-width layout
// against 44px, so every desktop-only control was unjudged at the touch floor
// while the report read "0 failures". Found by opening the app on a laptop.
//
// The third profile closes it, and it is not hypothetical hardware: a
// touchscreen laptop, a Surface, or an iPad in landscape all render the wide
// layout AND get touched.
const DESKTOP_TOUCH = { ...devices['Desktop Chrome'], hasTouch: true, isMobile: false };
for (const [name, device, size] of [['Pixel 7 (touch)', devices['Pixel 7'], 44],
                                    ['Desktop (touch)', DESKTOP_TOUCH, 44],
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

  let judged=0, boxFail=0, hitFail=0, savedByHitArea=0, hitJudged=0, hitSkipped=0;
  const perPage=new Map();
  const off=new Map();
  // Box failures need their own register. They are the trustworthy metric, and
  // listing only hit-probe offenders meant a genuinely undersized control could
  // sit in the count with nothing naming it.
  const boxOff=new Map();
  for (const nav of PAGES) {
    await page.evaluate(n=>{if(typeof window.nav==='function')window.nav(n);},nav);
    await page.waitForTimeout(1200);
    // Weekly Program defaults to a single night; the per-night treatment only
    // exists when several are stacked, so select "All nights" before measuring.
    if (nav === 'weekly-program') {
      await page.evaluate(()=>{const s=document.getElementById('wp-sel');
        if(s){s.value=''; s.dispatchEvent(new Event('change',{bubbles:true}));}});
      await page.waitForTimeout(1500);
    }
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
        // What is actually touchable is the element's VISIBLE region: its own
        // rect intersected with the viewport AND with every scrollable
        // ancestor that clips it. The sidebar scrolls, so a 219x44 nav item
        // sitting half under its edge was probed at a point that landed on the
        // scroll container -- an ancestor, which correctly does not count as a
        // hit -- and fifteen perfectly reachable controls were reported as
        // failures. Clipping is a function of scroll position, not of design,
        // so it is skipped rather than failed.
        let vt=Math.max(r.top,0), vl=Math.max(r.left,0),
            vb=Math.min(r.bottom,innerHeight), vr=Math.min(r.right,innerWidth);
        for(let a=e.parentElement; a; a=a.parentElement){
          const as=getComputedStyle(a);
          if(as.overflow==='visible'&&as.overflowX==='visible'&&as.overflowY==='visible') continue;
          const ar=a.getBoundingClientRect();
          vt=Math.max(vt,ar.top); vl=Math.max(vl,ar.left);
          vb=Math.min(vb,ar.bottom); vr=Math.min(vr,ar.right);
        }
        // Judgeable only if the visible region is itself big enough to hold the
        // probe -- otherwise the answer describes the scroll offset, not the app.
        const fullyVisible = (vb-vt)>=size && (vr-vl)>=size;
        // Declared exemption, subtracted HERE rather than in the reader's head:
        // a checkbox/radio box is 18x18 by design and carries its 44px target
        // via the label wrapper. Reporting it as a failure means every quote of
        // this number needs a caveat nobody remembers to apply.
        if(e.type==='checkbox'||e.type==='radio')continue;
        const boxOk=r.width>=size&&r.height>=size;   // always judgeable: no scroll needed
        const cx=(vl+vr)/2, cy=(vt+vb)/2, h=size/2-1;   // centre of what is visible
        const hitOk=!fullyVisible ? null : [[cx,cy-h],[cx,cy+h],[cx-h,cy],[cx+h,cy]].every(([x,y])=>{
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
    perPage.set(nav, r.length);
    for(const c of r){
      if(!c.boxOk){ boxFail++;
        const bk=`${c.w}x${c.h}  ${nav}  ${c.label}`; boxOff.set(bk,(boxOff.get(bk)||0)+1); }
      if(c.hitOk===null){ hitSkipped++; continue; }        // clipped by an edge
      hitJudged++;
      if(!c.hitOk){ hitFail++; const k=`${c.w}x${c.h}  ${c.label}`; off.set(k,(off.get(k)||0)+1); }
      if(!c.boxOk && c.hitOk) savedByHitArea++;
    }
  }
  console.log(`\n══ ${name} — threshold ${size}px ══`);
  console.log(`   judged                       ${judged}`);
  const silent=[...perPage.entries()].filter(([,n])=>n===0).map(([p])=>p);
  console.log(`   pages measured               ${perPage.size}  (${perPage.size-silent.length} rendered controls)`);
  if(silent.length) console.log(`   rendered NOTHING for this role: ${silent.join(', ')}`);
  console.log(`   box below threshold          ${boxFail}`);
  if(boxFail) [...boxOff.entries()].sort((a,b)=>b[1]-a[1]).slice(0,12)
    .forEach(([k,n])=>console.log(`     ${String(n).padStart(2)}x  ${k}`));
  console.log(`   rescued by a larger hit area ${savedByHitArea}`);
  // Coverage is reported next to the result, because "0 failures" describes
  // what was measured and a reader hears it as describing the app.
  console.log(`   hit-tested                   ${hitJudged}  (${hitSkipped} skipped: clipped by a viewport edge)`);
  console.log(`   FAIL (not reachable at ${size}px) ${hitFail}   →  ${hitJudged?Math.round(100*hitFail/hitJudged):0}% of hit-tested`);
  console.log('   worst offenders:');
  [...off.entries()].sort((a,b)=>b[1]-a[1]).slice(0,8).forEach(([k,n])=>console.log(`     ${String(n).padStart(2)}x  ${k}`));
  await browser.close();
}
