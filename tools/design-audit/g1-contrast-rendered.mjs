// G1 on the RENDERED page. The stylesheet scanner left 717 pairs unresolved
// because it cannot follow color-mix(), data-theme or inline styles. Computed
// style has no such problem: every visible text node is measured against the
// first non-transparent background painted behind it.
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
// EVERY routable page, enumerated from the id="page-*" elements in
// connected-frontend/index.html. A page absent from this list is not reported
// as unmeasured -- it is simply absent from the totals, which reads as clean.
const PAGES=['accounts','action-centre','action-items','activities','audit','calendar',
             'curriculum','dashboard','facilitators','getting-started','help','long-range',
             'national','national-activities','parade-nights','program-audit','resources',
             'service-desk','settings','system-console','weekly-program','wing-activities',
             'wing-calendar','wing-overview'];

const browser=await chromium.launch();
const page=await (await browser.newContext({...devices['Desktop Chrome']})).newPage();
await page.goto(BASE,{waitUntil:'domcontentloaded'});
const api=await page.getAttribute('meta[name="aafc-api-base"]','content');
await page.evaluate(async ([api,code])=>{
  const r=await fetch(api+'/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code})});
  sessionStorage.setItem('aafc_token',(await r.json()).token);
},[api,CODE]);
await page.reload({waitUntil:'domcontentloaded'}); await page.waitForTimeout(3000);

let measured=0, fail=0, unresolved=0;
const worst=new Map();
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
  const r=await page.evaluate(()=>{
    const parse=c=>{const m=c.match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)/);
      return m?{r:+m[1],g:+m[2],b:+m[3],a:m[4]===undefined?1:+m[4]}:null;};
    const lum=c=>{const f=v=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4);};
      return 0.2126*f(c.r)+0.7152*f(c.g)+0.0722*f(c.b);};
    const ratio=(a,b)=>{const L1=lum(a),L2=lum(b);return (Math.max(L1,L2)+0.05)/(Math.min(L1,L2)+0.05);};
    // The first ancestor that actually PAINTS something. A gradient lives in
    // background-image with a transparent background-color, so looking only at
    // background-color walks straight past it -- which reported white-on-white
    // 1:1 for white text on the navy .pn-hdr gradient. Gradients return every
    // colour stop; the caller scores against the worst one.
    const bgOf=el=>{
      let e=el;
      while(e&&e!==document.documentElement){
        const cs=getComputedStyle(e);
        const img=cs.backgroundImage;
        if(img&&img!=='none'){
          const stops=[...img.matchAll(/rgba?\([^)]+\)/g)].map(m=>parse(m[0])).filter(c=>c&&c.a>=0.95);
          if(stops.length) return stops;
        }
        const c=parse(cs.backgroundColor);
        if(c&&c.a>=0.95) return [c];
        e=e.parentElement;
      }
      const c=parse(getComputedStyle(document.body).backgroundColor);
      return [(c&&c.a>=0.95)?c:{r:255,g:255,b:255,a:1}];
    };
    const out=[];
    const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
    const seen=new Set();
    let n;
    while((n=walker.nextNode())){
      const t=(n.textContent||'').trim();
      if(t.length<2) continue;
      const el=n.parentElement; if(!el||seen.has(el)) continue; seen.add(el);
      const rect=el.getBoundingClientRect();
      if(rect.width<=0||rect.height<=0) continue;
      const s=getComputedStyle(el);
      if(s.visibility==='hidden'||s.display==='none'||s.opacity==='0') continue;
      const fg=parse(s.color); if(!fg){out.push({unresolved:true});continue;}
      const bgs=bgOf(el);
      const px=parseFloat(s.fontSize)||16;
      const bold=(parseInt(s.fontWeight,10)||400)>=700;
      const large=px>=24||(bold&&px>=18.66);
      const need=large?3.0:4.5;
      // worst stop wins: text over a gradient must pass at its hardest point
      const cr=Math.round(Math.min(...bgs.map(b=>ratio(fg,b)))*100)/100;
      out.push({cr,need,pass:cr>=need,px:Math.round(px),
                sel:el.tagName.toLowerCase()+(el.className?'.'+String(el.className).split(' ')[0]:''),
                text:t.slice(0,26)});
    }
    return out;
  });
  for(const c of r){
    if(c.unresolved){unresolved++;continue;}
    measured++;
    if(!c.pass){fail++;const k=`${c.cr}:1 need ${c.need}  ${c.sel}  "${c.text}"`;worst.set(k,(worst.get(k)||0)+1);}
  }
}
console.log(`G1 [${ROLE}] rendered — text nodes measured ${measured}, unresolved ${unresolved}`);
console.log(`   FAIL ${fail}  (${measured?Math.round(100*fail/measured):0}%)`);
console.log('   worst:');
[...worst.entries()].sort((a,b)=>parseFloat(a[0])-parseFloat(b[0])).slice(0,12)
  .forEach(([k,n])=>console.log(`     ${String(n).padStart(2)}x  ${k}`));
await browser.close();
