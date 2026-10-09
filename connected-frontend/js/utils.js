// Main TMS module: shared presentation utilities -- date/label/badge helpers,
// esc()/safeUrl(), the rich-text sanitiser and editor, parseServerTime().
// Extracted verbatim from connected-frontend/index.html (stabilisation Phase 4,
// C6). Top-level function declarations and side-effect-free let/const only;
// loaded as a classic script BEFORE the inline bootstrap, so everything here
// is defined before any page-load code runs. Statements with load-time
// effects stay in index.html in their original order. Parity is proven by
// tools/architecture/frontend_parity.mjs.

// Safe for embedding free-text (Wing/Squadron code -- no server-side charset
// restriction beyond strip+uppercase) inside a double-quoted inline onclick
// attribute: JS-escape first so the string decodes to a valid single-quoted
// JS literal, then HTML-escape so a literal " in the source can never break
// out of the onclick="..." attribute before the browser gets to decode it
// (that break-out, e.g. code = 'X" onmouseover="...', is exactly what plain
// .replace(/'/g,...)-only escaping elsewhere in this file does not stop).
function _jsAttr(str){
  return esc(String(str||'').replace(/\\/g,'\\\\').replace(/'/g,"\\'"));
}

// ═══════════════════════════════════════════════════════════
//  HELPERS
// ═══════════════════════════════════════════════════════════
const MONTHS=['January','February','March','April','May','June','July','August','September','October','November','December'];
const DAYS=['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
function fmtD(s,o){return s?new Date(s+'T00:00:00').toLocaleDateString('en-AU',o||{day:'numeric',month:'short',year:'numeric'}):'—';}
function fmtDL(s){return s?new Date(s+'T00:00:00').toLocaleDateString('en-AU',{weekday:'long',day:'numeric',month:'long',year:'numeric'}):'—';}
function today(){const d=new Date();d.setHours(0,0,0,0);return d;}

const EL_L={Drill:'Drill',Air_Space:'Air & Space',Field:'Field Skills',Personal_Dev:'Personal Dev',Service_Community:'Service & Comm',SQN_Affairs:'SQN Affairs'}
// E3: the backend sends element codes (Air_Space, Personal_Dev, SQN_Affairs) as
// chart labels. EL_L has mapped them to readable names all along but was only
// applied by elBadge() and the facilitator list, so the Dashboard printed the
// raw codes -- 7 of them on screen at once.
function _dLabel(v){
  const k=String(v==null?'':v);
  return (typeof EL_L!=='undefined'&&EL_L[k])?EL_L[k]:k;
};
const EL_C={Drill:'b-red',Air_Space:'b-blue',Field:'b-ok',Personal_Dev:'b-purple',Service_Community:'b-amber',SQN_Affairs:'b-teal'};
const PH_S={'A. Orientation':'Orientation','B. Initial':'Initial','C. Junior':'Junior','D. Intermediate':'Intermediate','E. Senior':'Senior','I. Bronze':'Bronze CLP','J. Silver':'Silver CLP','K. Gold':'Gold CLP'};
const PH_C={'A. Orientation':'ph-ori','B. Initial':'ph-ini','C. Junior':'ph-jun','D. Intermediate':'ph-int','E. Senior':'ph-sen','I. Bronze':'ph-bro','J. Silver':'ph-sil','K. Gold':'ph-gld'};

function elBadge(el){return `<span class="badge ${EL_C[el]||'b-grey'}">${esc(EL_L[el]||el)}</span>`;}
function phBadge(ph){return `<span class="badge ${PH_C[ph]||'b-grey'}">${esc(PH_S[ph]||ph)}</span>`;}
// Foundation/Extension/Optional derives from the phase letter prefix, not the
// ambiguous 2-valued core_status field -- mirrors frontend/src/utils/planningFilters.ts's
// getProgramType() so both apps classify the same curriculum item identically.
const _FOUNDATION_PREFIXES=new Set(['A','B','C','D','E']);
const _EXTENSION_PREFIXES=new Set(['I','J','K']);
function getProgramType(phase){
  const prefix=(phase||'').trim().charAt(0).toUpperCase();
  if(_FOUNDATION_PREFIXES.has(prefix))return'Foundation';
  if(_EXTENSION_PREFIXES.has(prefix))return'Extension';
  return'Optional';
}
const _PROGRAM_TYPE_CLASS={Foundation:'b-dark',Extension:'b-teal',Optional:'b-grey'};
// delivered_with_issue/cancelled_late (Stage 11, 2026-08-05): both valid
// backend statuses (VALID_STATUS, training.py) and already reachable via
// Planning Workspace, but connected-frontend previously had no label/class
// for either -- a session in one of these states rendered as a raw grey
// badge showing the literal snake_case string.
const _ST_LABEL={planned:'Planned',delivered:'Delivered',delivered_with_issue:'Delivered (issue)',
  cancelled:'Cancelled',cancelled_late:'Cancelled late',rescheduled:'Rescheduled',not_delivered:'Not Delivered'};
// Status icon, not colour alone (WCAG / colour-blind safe) -- mirrors
// Planning Workspace's StatusBadge.tsx icon set (Stage 11 follow-up).
const _ST_ICON={planned:'•',delivered:'✓',delivered_with_issue:'✓!',cancelled:'✕',
  cancelled_late:'✕',rescheduled:'↻',not_delivered:'▲'};
function stLabel(st){return _ST_LABEL[st]||st||'—';}
// DES-H02: 1-letter codes inside status chips — redundant non-colour indicator (WCAG SC 1.4.1)
const _ST_CODE={planned:'P',delivered:'D',delivered_with_issue:'D',cancelled:'C',cancelled_late:'C',rescheduled:'R',not_delivered:'N'};
function stBadge(st){
  const m={planned:'st-planned',delivered:'st-delivered',delivered_with_issue:'st-delivered_with_issue',
    cancelled:'st-cancelled',cancelled_late:'st-cancelled_late',rescheduled:'st-rescheduled',not_delivered:'st-not_delivered'};
  const code=_ST_CODE[st]||'';
  return `<span class="badge ${m[st]||'b-grey'}">${code?`<span class="chip-code">${code}</span>`:''}${stLabel(st)}</span>`;
}
function stCls(st){return {delivered:'delivered',delivered_with_issue:'delivered_with_issue',cancelled:'cancelled',cancelled_late:'cancelled_late',rescheduled:'rescheduled',not_delivered:'not_delivered'}[st]||'';}

function allSess(){
  const rows=[];
  S.pns.forEach(pn=>(pn.sessions||[]).forEach((s,i)=>rows.push({date:pn.date,term:pn.term,si:i,...s})));
  return rows;
}

/* ═══ Help & Reference ═══════════════════════════════════════════════════════
   Author content is the only HTML in the TMS that comes from another user, so
   it passes an allowlist here as well as on the server. Sanitising on save
   alone would leave anything stored before this landed unfiltered; sanitising
   on render alone would leave a bad value sitting in the database waiting for
   a consumer that forgets. Both, deliberately.
   The allowlist below must stay in step with backend/app/richtext.py.        */

const _RT_TAGS={P:1,BR:1,H2:1,H3:1,H4:1,STRONG:1,EM:1,U:1,UL:1,OL:1,LI:1,A:1,BLOCKQUOTE:1};
const _RT_ALIAS={B:'STRONG',I:'EM',STRIKE:'EM',H1:'H2',H5:'H4',H6:'H4',DIV:'P'};
const _RT_DROP={SCRIPT:1,STYLE:1,TEMPLATE:1,IFRAME:1,OBJECT:1,EMBED:1,SVG:1,MATH:1,NOSCRIPT:1,TITLE:1,HEAD:1};

function _rtSafeHref(v){
  if(!v)return null;
  const raw=String(v).trim();
  if(!raw)return null;
  // Browsers ignore whitespace and control characters inside a scheme, so
  // "java\tscript:" runs. Normalise before deciding.
  const flat=raw.replace(/[\s\x00-\x1f\x7f]/g,'').toLowerCase();
  if(flat.startsWith('//'))return null;      // protocol-relative: off-site
  if(flat.startsWith('/')||flat.startsWith('#'))return raw;
  if(/^(https?:|mailto:)/.test(flat))return raw;
  return null;
}
function _rtWalk(src,dest){
  Array.prototype.forEach.call(src.childNodes,function(n){
    if(n.nodeType===3){dest.appendChild(document.createTextNode(n.nodeValue));return;}
    if(n.nodeType!==1)return;
    const tag=n.tagName.toUpperCase();
    if(_RT_DROP[tag])return;                  // tag and its contents both go
    const name=_RT_ALIAS[tag]||tag;
    if(!_RT_TAGS[name]){_rtWalk(n,dest);return;}   // unwrap: text survives
    const el=document.createElement(name.toLowerCase());
    if(name==='A'){
      const href=_rtSafeHref(n.getAttribute('href'));
      if(href){
        el.setAttribute('href',href);
        if(/^https?:/i.test(href.replace(/[\s\x00-\x1f\x7f]/g,''))){
          el.setAttribute('rel','noopener noreferrer');
          el.setAttribute('target','_blank');
        }
      }
    }
    _rtWalk(n,el);
    dest.appendChild(el);
  });
}
function _rtSanitize(html){
  // DOMParser does not run scripts or load resources, so parsing is safe.
  const doc=new DOMParser().parseFromString('<body>'+(html||'')+'</body>','text/html');
  const holder=document.createElement('div');
  _rtWalk(doc.body,holder);
  return holder.innerHTML.trim();
}
function _rtRender(el,html,emptyMsg){
  if(!el)return;
  const clean=_rtSanitize(html);
  if(!clean){el.innerHTML='';el.appendChild(Object.assign(document.createElement('p'),{className:'rt-empty',textContent:emptyMsg||'Nothing here yet.'}));return;}
  el.innerHTML=clean;
}

/* ── Rich text editor ──────────────────────────────────────────────────────
   execCommand is deprecated but is the only formatting API every browser this
   app supports implements, and this file has no build step to bring in an
   editor library. Output goes through _rtSanitize before it is sent, so
   whatever execCommand emits is normalised to the allowlist either way.     */

const _RTE_BUTTONS=[
  {cmd:'bold',        label:'B',    title:'Bold',            style:'font-weight:800'},
  {cmd:'italic',      label:'I',    title:'Italic',          style:'font-style:italic'},
  {cmd:'underline',   label:'U',    title:'Underline',       style:'text-decoration:underline'},
  {sep:1},
  {block:'h2',        label:'H2',   title:'Heading'},
  {block:'h3',        label:'H3',   title:'Subheading'},
  {block:'p',         label:'Body', title:'Body text'},
  {sep:1},
  {cmd:'insertUnorderedList', label:'Bullets', title:'Bulleted list'},
  {cmd:'insertOrderedList',   label:'Numbers', title:'Numbered list'},
  {sep:1},
  {act:'link',        label:'Link',   title:'Add a link'},
  {cmd:'unlink',      label:'Unlink', title:'Remove link'},
  {sep:1},
  {cmd:'removeFormat',label:'Clear',  title:'Clear formatting'}
];
const _rteState={};

function _rteMount(mountId,html,placeholder){
  const mount=document.getElementById(mountId);
  if(!mount)return;
  mount.innerHTML='';

  const bar=document.createElement('div');
  bar.className='rte-bar';
  bar.setAttribute('role','toolbar');
  bar.setAttribute('aria-label','Text formatting');

  const area=document.createElement('div');
  area.className='rte-area';
  area.contentEditable='true';
  area.setAttribute('role','textbox');
  area.setAttribute('aria-multiline','true');
  area.setAttribute('aria-label','Content');
  area.setAttribute('data-placeholder',placeholder||'Start typing…');
  area.innerHTML=_rtSanitize(html)||'<p><br></p>';

  const linkRow=document.createElement('div');
  linkRow.style.cssText='display:none;gap:6px;margin-top:6px;align-items:center';
  const linkInp=document.createElement('input');
  linkInp.type='text';
  linkInp.placeholder='https://example.org or /planning';
  linkInp.setAttribute('aria-label','Link address');
  linkInp.style.cssText='flex:1;font-size:var(--fs-xs);padding:6px 8px;border:1px solid var(--border);border-radius:4px';
  const linkGo=Object.assign(document.createElement('button'),{type:'button',className:'btn btn-primary btn-sm',textContent:'Add link'});
  const linkNo=Object.assign(document.createElement('button'),{type:'button',className:'btn btn-secondary btn-sm',textContent:'Cancel'});
  linkRow.append(linkInp,linkGo,linkNo);

  let savedRange=null;
  const saveRange=function(){
    const sel=window.getSelection();
    if(sel&&sel.rangeCount&&area.contains(sel.anchorNode))savedRange=sel.getRangeAt(0).cloneRange();
  };
  const restoreRange=function(){
    if(!savedRange)return;
    const sel=window.getSelection();
    sel.removeAllRanges();
    sel.addRange(savedRange);
  };
  area.addEventListener('keyup',saveRange);
  area.addEventListener('mouseup',saveRange);

  const buttons=[];
  _RTE_BUTTONS.forEach(function(def){
    if(def.sep){const sp=document.createElement('span');sp.className='rte-sep';bar.appendChild(sp);return;}
    const b=document.createElement('button');
    b.type='button';
    b.className='rte-btn';
    b.textContent=def.label;
    b.title=def.title;
    b.setAttribute('aria-label',def.title);
    if(def.cmd)b.setAttribute('aria-pressed','false');
    if(def.style)b.style.cssText=def.style;
    // Keeps the caret in the editable when the button is clicked.
    b.addEventListener('mousedown',function(e){e.preventDefault();});
    b.addEventListener('click',function(){
      area.focus();
      if(def.act==='link'){
        saveRange();
        linkRow.style.display='flex';
        linkInp.value='';
        linkInp.focus();
        return;
      }
      if(def.block){document.execCommand('formatBlock',false,def.block);}
      else{document.execCommand(def.cmd,false,null);}
      syncState();
    });
    b.__def=def;
    buttons.push(b);
    bar.appendChild(b);
  });

  linkGo.addEventListener('click',function(){
    const href=_rtSafeHref(linkInp.value);
    if(!href){showToast('Enter a web address starting with https:// or a path starting with /',true);return;}
    area.focus();
    restoreRange();
    document.execCommand('createLink',false,href);
    linkRow.style.display='none';
    syncState();
  });
  linkNo.addEventListener('click',function(){linkRow.style.display='none';area.focus();});
  linkInp.addEventListener('keydown',function(e){
    if(e.key==='Enter'){e.preventDefault();linkGo.click();}
    if(e.key==='Escape'){e.preventDefault();linkNo.click();}
  });

  function syncState(){
    buttons.forEach(function(b){
      const def=b.__def;
      if(!def.cmd)return;
      let on=false;
      try{on=document.queryCommandState(def.cmd);}catch(_){on=false;}
      b.setAttribute('aria-pressed',on?'true':'false');
    });
  }
  area.addEventListener('keyup',syncState);
  area.addEventListener('mouseup',syncState);

  // Pasting from Word or a web page is the main way unwanted markup arrives.
  area.addEventListener('paste',function(e){
    e.preventDefault();
    const cb=e.clipboardData||window.clipboardData;
    const html=cb?cb.getData('text/html'):'';
    const text=cb?cb.getData('text/plain'):'';
    if(html){document.execCommand('insertHTML',false,_rtSanitize(html));}
    else{document.execCommand('insertText',false,text||'');}
  });

  mount.append(bar,area,linkRow);
  const hint=document.createElement('div');
  hint.className='rte-hint';
  hint.textContent='Formatting is limited to headings, bold, italic, underline, lists and links. Anything else is removed when you save.';
  mount.appendChild(hint);

  _rteState[mountId]=area;
  try{document.execCommand('styleWithCSS',false,false);}catch(_){}
}
function _rteValue(mountId){
  const area=_rteState[mountId];
  return area?_rtSanitize(area.innerHTML):'';
}

// ═══════════════════════════════════════════════════════════
//  TIMING TEMPLATES
// ═══════════════════════════════════════════════════════════
function esc(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');}
// Returns a value safe to drop straight into an href="..." attribute.
// Two jobs, and it used to do only the first: reject non-http(s) schemes
// (javascript:, data:) AND escape the result. Returning the raw string meant a
// learning_hub_url of  https://x/" onmouseover="...  closed the attribute and
// installed a handler on the <a>. Both call sites are href="${safeUrl(...)}",
// so escaping here is correct for every consumer; entities decode back to the
// original URL when the link is followed.
function safeUrl(u){try{const p=new URL(String(u||''),location.href).protocol;return(p==='https:'||p==='http:')?esc(String(u)):'#';}catch(e){return '#';}}
// Capitalise a raw lowercase enum value for display (e.g. severity "high" -> "High") --
// never use on a value that's already a proper label (e.g. from a *_LABEL map).
function _cap(s){s=String(s||'');return s?s.charAt(0).toUpperCase()+s.slice(1):s;}

/* The API returns naive UTC timestamps with no zone marker (2026-08-22T22:55:19).
   Date() reads those as LOCAL time, which is eight hours out in Perth and puts
   the value on the wrong day either side of midnight. Mark it as UTC, then let
   the browser render it in the reader's own timezone -- "raised today" should
   say today.
   Date-only values (2026-08-14) are left alone: they carry no time, and
   attaching one would reintroduce the same class of drift. */
function parseServerTime(v){
  if(!v)return null;
  const raw=String(v);
  if(/^\d{4}-\d{2}-\d{2}$/.test(raw))return new Date(raw+'T00:00:00');
  let iso=raw.replace(' ','T');
  if(!/[zZ]$|[+-]\d{2}:?\d{2}$/.test(iso))iso+='Z';
  const d=new Date(iso);
  return isNaN(d)?null:d;
}
