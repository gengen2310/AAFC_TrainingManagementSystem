// Main TMS module: Getting Started, Help & Reference, Getting Help, FAQ and the
// What Changed? feed.
// Extracted verbatim from connected-frontend/index.html (stabilisation Phase 4,
// C6). Top-level function declarations and side-effect-free let/const only;
// loaded as a classic script BEFORE the inline bootstrap, so everything here
// is defined before any page-load code runs. Statements with load-time
// effects stay in index.html in their original order. Parity is proven by
// tools/architecture/frontend_parity.mjs.

// ═══════════════════════════════════════════════════════════
//  GETTING STARTED (Phase 3.5) — thin view over GET /api/setup/status.
//  No parallel data-entry surface: every action is a link into the page
//  that already does the real work.
// ═══════════════════════════════════════════════════════════
async function loadGettingStarted(){
  const el=document.getElementById('gs-body'); if(!el)return;
  el.innerHTML='<p class="muted">Loading…</p>';
  try{
    const sqnId=(S.role==='system_admin')?saBrowseSquadronId():null;
    const url='/api/setup/status'+(sqnId?('?squadron_id='+encodeURIComponent(sqnId)):'');
    const d=await api(url);
    el.innerHTML=_renderGsSections(d);
  }catch(e){ el.innerHTML='<div class="alert a-red">'+esc(apiErr(e))+'</div>'; }
}
const _GS_LINK_LABEL={
  accounts:'Go to Account Management', facilitators:'Go to Facilitators', resources:'Go to Resources',
  settings:'Go to Unit Settings', activities:'Go to Activities', 'parade-nights':'Go to Parade Nights',
  curriculum:'Go to Curriculum',
};
function _gsStepRow(s){
  const badge=s.done?'<span class="badge b-ok">Done</span>':'<span class="badge b-grey">Pending</span>';
  const optionalTag=s.optional?' <span class="badge b-blue" title="Recommended, not required for setup to be considered complete">Optional</span>':'';
  const countTxt=(s.count===null||s.count===undefined)?'':` <span style="color:var(--muted);font-size:var(--fs-xs)">(${s.count}${s.key==='curriculum_coverage'?'%':''})</span>`;
  return `<div class="gs-step-row" data-step-key="${esc(s.key)}" style="display:flex;align-items:center;padding:10px 12px;border:1px solid var(--border);border-radius:8px;margin-bottom:6px;cursor:pointer" onclick="nav('${s.link_page}')">
    <div>${badge}${optionalTag} <span style="font-weight:700;margin-left:6px">${esc(s.label)}</span>${countTxt}</div>
  </div>`;
}
const _GS_NATIONAL_KEYS=['wings_created','squadrons_created'];
function _renderGsSections(d){
  let html='';
  if(d.complete){
    html+='<div class="alert a-ok">Setup looks complete — every checklist item below is done. This page stays here if you ever want to review it again.</div>';
  }
  if(d.national){
    html+='<div class="card"><h2 class="ctitle">National / Wing Setup</h2>'+
      (d.steps||[]).filter(s=>_GS_NATIONAL_KEYS.includes(s.key)).map(_gsStepRow).join('')+
      '</div>';
  }
  if(d.squadron){
    const sqnSteps=(d.steps||[]).filter(s=>!_GS_NATIONAL_KEYS.includes(s.key));
    const required=sqnSteps.filter(s=>!s.optional);
    const optional=sqnSteps.filter(s=>s.optional);
    const doneCount=required.filter(s=>s.done).length;
    html+=`<div class="card"><div class="card-head"><h2 class="ctitle" style="margin:0">Squadron setup — ${esc(d.squadron.squadron_code||'')}</h2>`+
      `<span class="muted" style="font-size:var(--fs-xs)">${doneCount} of ${required.length} done</span></div>`+
      required.map(_gsStepRow).join('')+
      '</div>';
    // Optional steps were filtered out entirely, which made _gsStepRow's
    // "Optional" badge dead code and hid both recommendations the backend
    // deliberately surfaces as guidance. Training classes in particular are
    // load-bearing: without one the Weekly Program has no column to print into.
    if(optional.length){
      html+='<div class="card" style="margin-top:12px"><h2 class="ctitle">Recommended</h2>'+
        '<p class="muted" style="font-size:var(--fs-xs);margin:0 0 10px">Not required for setup to count as complete, but most squadrons need these.</p>'+
        optional.map(_gsStepRow).join('')+
        '</div>';
    }
  }
  if(!d.national&&!d.squadron){
    html+='<div class="alert a-info">Select a Wing or Squadron to check setup status.</div>';
  }
  return html;
}

// ═══════════════════════════════════════════════════════════
//  HELP & REFERENCE PAGE
// ═══════════════════════════════════════════════════════════
async function _loadHelpPage(){
  // Reloads every visit. This used to be a one-shot guarded by _helpPageLoaded,
  // which was harmless while the page held a single static blob. It is not
  // harmless now: the FAQ is shared reference content that a system_admin is
  // expected to add to, and readers would not see a new question until they
  // reloaded the whole app. Two small requests on a page nobody navigates to in
  // a loop is the right trade.
  await _loadGettingHelp();
}

/* ── Getting help ────────────────────────────────────────────────────────── */

const _GH_DEFAULT=`
<h2>What is TMS?</h2>
<p>TMS (Training Management System) is the AAFC system for managing your squadron's records. Use TMS to:</p>
<ul>
  <li>Create and manage accounts</li>
  <li>Manage facilitators</li>
  <li>Manage training areas and equipment</li>
  <li>View reports and dashboards</li>
  <li>Configure squadron settings</li>
  <li>Manage curriculum and activities</li>
</ul>

<h2>What is Planning Workspace?</h2>
<p>Planning Workspace is the AAFC training planner. It is a separate screen, reached from the Planning link in the navigation bar, where you:</p>
<ul>
  <li>Create a year</li>
  <li>Generate parade night dates</li>
  <li>Schedule curriculum sessions</li>
  <li>Assign facilitators and rooms</li>
  <li>Record training outcomes</li>
  <li>Review Needs Attention</li>
</ul>
<p><strong>Use TMS</strong> to manage your organisation — accounts, facilities, activities.<br>
<strong>Use Planning Workspace</strong> to do the planning — schedule nights, assign curriculum, track delivery.</p>

<h2>Key terms</h2>
<h3>Year</h3>
<p>A container for all parade nights and training records for one academic year, typically July to June. Create a year before scheduling parade nights.</p>
<h3>Training Stage</h3>
<p>A national AAFC curriculum level — Initial, Junior, Intermediate, Senior, Bronze, Silver, or Gold. Each stage has a fixed set of required modules defined at the national level. Training Stages are the same for every squadron.</p>
<h3>Training Class</h3>
<p>A squadron-specific group of cadets completing a Training Stage during a year. Where a squadron has enough cadets, one Training Stage can have several classes running at the same time.</p>
<p>For example, a squadron with 30 senior cadets might create Senior 1 (15 cadets) and Senior 2 (15 cadets). Both classes follow the Senior Training Stage, but each has its own independent progress record. Senior 1 may have completed SEN-04 while Senior 2 has it planned. The system tracks them separately.</p>
<p>Why the distinction matters: a single Training Stage can have several classes, each at a different point in the curriculum. If the system treated them as one group, it could not tell you which class still needs a module, or which class to schedule next.</p>
<h3>Parade Night</h3>
<p>A scheduled training evening. Each parade night can hold several sessions across different time periods.</p>
<h3>Session</h3>
<p>One training block within a parade night, linked to a curriculum item, time period, facilitator, room, and one or more Training Classes.</p>
<p>A session can serve more than one Training Class. If Senior 1 and Senior 2 are doing the same module together, assign both classes to one session — they share the session, and the system records the delivery against each class separately.</p>
<h3>Activity</h3>
<p>A training event outside the standard parade night schedule — field days, camps, competitions, courses and similar. Activities appear in Planning Workspace as reference items and contribute actionable requirements to Needs Attention when they include curriculum delivery. Create and manage them in TMS under Activities. CEA (Cadet Enterprise Application) activities are imported from the national system.</p>
<h3>Needs Attention</h3>
<p>A consolidated list of curriculum requirements, conflicts, and outcomes that need follow-up. It identifies which Training Class needs an unscheduled module and provides the next action.</p>

<h2>Setting up for the first time</h2>
<p>Before using Planning Workspace, set the following up in TMS:</p>
<ol>
  <li>Squadron details — name, parade day, parade location</li>
  <li>At least one facilitator</li>
  <li>At least one training area</li>
  <li>A Training Class for each active Training Stage, for example Senior 1 for the Senior stage; add Senior 2 if you have two senior groups</li>
  <li>Activities, if you have camps, field days or courses this year</li>
</ol>
<p>Then open Planning Workspace. If no year exists, the setup panel appears automatically. Step through the guided setup to create your year and generate parade nights.</p>

<h2>Common tasks</h2>
<h3>Add a facilitator</h3>
<p>TMS → Facilitators → Add facilitator. Enter name, rank and type, then save.</p>
<h3>Add a training area</h3>
<p>TMS → Training Areas &amp; Equipment → Add training area. Enter name, type and capacity, then save.</p>
<h3>Set up Training Classes</h3>
<p>TMS → Year → Training Classes → Add Training Class. Choose the Training Stage and name the class, for example Senior 1. Repeat for each class. Each class tracks its own progress through the curriculum.</p>
<h3>Generate parade nights</h3>
<p>In Planning Workspace, select a year and use Guided year setup in the toolbar. Choose your parade weekday, start date, end date and frequency, then select Generate.</p>
<h3>Schedule a session</h3>
<p>In Planning Workspace, click any empty cell on a parade night. Select the curriculum item, Training Class, facilitator and room, then save.</p>
<h3>Record a training outcome</h3>
<p>In Planning Workspace, click the session after the parade night. Change status to Delivered, Cancelled or Not Delivered, add notes, then save.</p>
<h3>View reports</h3>
<p>TMS → Dashboard shows delivery rates, curriculum progress and facilitator readiness. Weekly Program, training summaries and Wing-level comparisons are under Reports.</p>
<h3>Add an activity</h3>
<p>TMS → Activities → Add activity. Enter the name, date and type, and assign curriculum items if they apply. Activities then appear as reference events in Planning Workspace.</p>

<h2>Getting support</h2>
<p>For help with TMS or Planning Workspace, contact your Wing SOCAD (Squadron Organisation and Cadet Administration) officer.</p>
<p>To report a technical issue, include:</p>
<ul>
  <li>Squadron name and number</li>
  <li>Your role</li>
  <li>What you were trying to do</li>
  <li>What happened, with the exact error message if there was one</li>
  <li>Approximate time</li>
  <li>Browser used</li>
</ul>`;

let _ghStored='';

async function _loadGettingHelp(){
  const isAdmin=(S.role==='system_admin');
  const editBtn=document.getElementById('gh-edit-btn');
  if(editBtn)editBtn.style.display=isAdmin?'inline-flex':'none';
  const addBtn=document.getElementById('faq-add-btn');
  if(addBtn)addBtn.style.display=isAdmin?'inline-flex':'none';

  _helpRenderLinks();
  const stamp=document.getElementById('gh-updated');
  try{
    const r=await api('/api/activities/getting-help');
    _ghStored=(r&&r.content)||'';
    _rtRender(document.getElementById('gh-content-display'),_ghStored||_GH_DEFAULT);
    if(stamp){
      stamp.textContent=(_ghStored&&r&&r.updated_at)
        ? 'Last updated '+_fmtHelpStamp(r.updated_at)
        : 'Showing the standard guide. No local version has been saved.';
    }
  }catch(_){
    _ghStored='';
    _rtRender(document.getElementById('gh-content-display'),_GH_DEFAULT);
    if(stamp)stamp.textContent='Showing the standard guide.';
  }
  _loadFaq();
}
function _fmtHelpStamp(v){
  try{
    const d=parseServerTime(v);
    if(!d)return String(v||'');
    return d.toLocaleDateString(undefined,{day:'numeric',month:'short',year:'numeric'});
  }catch(_){return String(v);}
}
function _helpRenderLinks(){
  const box=document.getElementById('help-links');
  if(!box)return;
  // Only offer destinations this role can actually reach, so the card never
  // shows a link that lands on a blank page.
  const allowed=(typeof NAV_BY_SCOPE!=='undefined'&&NAV_BY_SCOPE[effectiveScope()])||[];
  const candidates=[
    {id:'getting-started',label:'Setup checklist',hint:'Work through your initial configuration'},
    {id:'service-desk',   label:'Service Desk',   hint:'Raise a ticket or track one you sent'},
    {id:'curriculum',     label:'Curriculum',     hint:'Browse stages, modules and elements'},
    {id:'activities',     label:'Activities',     hint:'Camps, field days and courses'}
  ].filter(function(c){return allowed.indexOf(c.id)!==-1;});

  box.innerHTML='';
  candidates.forEach(function(c){
    const b=document.createElement('button');
    b.type='button';
    b.className='btn btn-secondary';
    b.style.cssText='text-align:left;display:block;width:100%;padding:9px 11px;white-space:normal;line-height:1.35';  // .btn is nowrap, which clipped the hint
    b.onclick=function(){nav(c.id);};
    b.innerHTML='<span style="display:block;font-weight:600;font-size:var(--fs-xs)">'+esc(c.label)+
                '</span><span style="display:block;font-weight:400;font-size:var(--fs-2xs);color:var(--muted);margin-top:2px">'+esc(c.hint)+'</span>';
    box.appendChild(b);
  });
  if(!candidates.length){
    box.innerHTML='<div class="muted" style="font-size:var(--fs-2xs)">No further sections are available for your role.</div>';
  }
}
function openGettingHelpModal(){
  document.getElementById('gh-msg').textContent='';
  // Open on whatever is actually stored. If nothing is, start from the standard
  // guide so an admin edits real content rather than an empty box.
  _rteMount('gh-editor-mount',_ghStored||_GH_DEFAULT,'Write the guidance your squadrons should see…');
  openModal('m-getting-help');
}
async function doSaveGettingHelp(){
  const msgEl=document.getElementById('gh-msg');
  const content=_rteValue('gh-editor-mount');
  try{
    await api('/api/activities/getting-help',{method:'PUT',body:{content}});
    showToast('Getting help content saved.');
    closeModal('m-getting-help');
    await _loadGettingHelp();
  }catch(e){ msgEl.textContent=apiErr(e); }
}

/* ── FAQ ─────────────────────────────────────────────────────────────────── */

let _faqData={categories:[],total:0};
let _faqEditId=null;

async function _loadFaq(){
  try{
    _faqData=await api('/api/activities/faq');
  }catch(_){
    _faqData={categories:[],total:0};
  }
  _renderFaq();
}
function _renderFaq(){
  const box=document.getElementById('faq-body');
  if(!box)return;
  const isAdmin=(S.role==='system_admin');
  box.innerHTML='';

  // Keep the category suggestions in step with what already exists.
  const dl=document.getElementById('faq-cat-list');
  if(dl){
    dl.innerHTML='';
    (_faqData.categories||[]).forEach(function(g){
      const o=document.createElement('option');o.value=g.category;dl.appendChild(o);
    });
  }

  if(!(_faqData.categories||[]).length){
    box.innerHTML='<div class="muted" style="font-size:var(--fs-sm)">'+
      (isAdmin
        ? 'No questions yet. Select <strong>Add question</strong> to write the first one — everyone signed in will see it.'
        : 'No questions have been published yet.')+
      '</div>';
    return;
  }

  _faqData.categories.forEach(function(group){
    const wrap=document.createElement('div');
    wrap.className='faq-cat';
    const h=document.createElement('div');
    h.className='faq-cat-name';
    h.appendChild(document.createTextNode(group.category));
    wrap.appendChild(h);

    group.entries.forEach(function(entry){
      const d=document.createElement('details');
      d.className='faq-item';

      const sum=document.createElement('summary');
      const caret=document.createElement('span');
      caret.className='faq-caret';
      caret.setAttribute('aria-hidden','true');
      caret.textContent='▶';
      const q=document.createElement('span');
      q.className='faq-q';
      q.textContent=entry.question;
      sum.append(caret,q);
      if(!entry.is_published){
        const tag=document.createElement('span');
        tag.className='faq-draft';
        tag.textContent='Draft — only you can see this';
        sum.appendChild(tag);
      }

      const body=document.createElement('div');
      body.className='faq-a rt';
      _rtRender(body,entry.answer_html,'No answer has been written yet.');

      if(isAdmin){
        const tools=document.createElement('div');
        tools.className='faq-admin';
        const ed=Object.assign(document.createElement('button'),{type:'button',className:'btn btn-secondary btn-sm',textContent:'Edit'});
        ed.onclick=function(){openFaqModal(entry.id);};
        const del=Object.assign(document.createElement('button'),{type:'button',className:'btn btn-secondary btn-sm',textContent:'Delete'});
        del.onclick=function(){doDeleteFaq(entry.id,entry.question);};
        tools.append(ed,del);
        body.appendChild(tools);
      }

      d.append(sum,body);
      wrap.appendChild(d);
    });
    box.appendChild(wrap);
  });
}
function _faqFind(id){
  let hit=null;
  (_faqData.categories||[]).forEach(function(g){
    g.entries.forEach(function(e){if(e.id===id)hit=e;});
  });
  return hit;
}
function openFaqModal(id){
  _faqEditId=id||null;
  const entry=id?_faqFind(id):null;
  document.getElementById('m-faq-title').textContent=entry?'Edit question':'Add a question';
  document.getElementById('faq-cat-inp').value=entry?entry.category:'';
  document.getElementById('faq-q-inp').value=entry?entry.question:'';
  document.getElementById('faq-order-inp').value=entry?entry.sort_order:0;
  document.getElementById('faq-pub-inp').checked=entry?!!entry.is_published:true;
  document.getElementById('faq-msg').textContent='';
  _rteMount('faq-editor-mount',entry?entry.answer_html:'','Write the answer…');
  openModal('m-faq');
}
async function doSaveFaq(){
  const msgEl=document.getElementById('faq-msg');
  const question=(document.getElementById('faq-q-inp').value||'').trim();
  if(!question){msgEl.textContent='Enter the question people will be looking for.';return;}
  const body={
    category:(document.getElementById('faq-cat-inp').value||'').trim()||'General',
    question:question,
    answer_html:_rteValue('faq-editor-mount'),
    sort_order:parseInt(document.getElementById('faq-order-inp').value,10)||0,
    is_published:!!document.getElementById('faq-pub-inp').checked
  };
  try{
    if(_faqEditId){await api('/api/activities/faq/'+encodeURIComponent(_faqEditId),{method:'PUT',body:body});}
    else{await api('/api/activities/faq',{method:'POST',body:body});}
    showToast(_faqEditId?'Question updated.':'Question added.');
    closeModal('m-faq');
    _faqEditId=null;
    await _loadFaq();
  }catch(e){ msgEl.textContent=apiErr(e); }
}
function doDeleteFaq(id,question){
  // confirmAction(), not native confirm() -- a native dialog blocks the page
  // entirely under browser automation (see .claude/rules/frontend.md).
  confirmAction('Delete "'+question+'"? This removes it for everyone and cannot be undone.',
    async function(){
      try{
        await api('/api/activities/faq/'+encodeURIComponent(id),{method:'DELETE'});
        showToast('Question deleted.');
        await _loadFaq();
      }catch(e){ showToast(apiErr(e),true); }
    }, true);
}

// ─── HELP-05: What Changed? activity feed ────────────────────────────────────
const _RC_TYPE_LABEL = {
  parade_night:'Parade Night', session:'Session', session_audience:'Session Audience',
  session_outcome:'Outcome', scheduled_session:'Scheduled Session',
  planning_notice:'Notice', planning_year:'Year',
  training_class:'Training Class', class_membership:'Class Membership',
};
function _rcRelTime(iso){
  if(!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.round(diff/60000), h = Math.round(diff/3600000), d = Math.round(diff/86400000);
  if(m < 2) return 'Just now';
  if(m < 60) return `${m} min ago`;
  if(h < 24) return `${h} hr ago`;
  return `${d} day${d===1?'':'s'} ago`;
}
async function loadRecentChanges(){
  const el = document.getElementById('rc-feed'); if(!el) return;
  const days = (document.getElementById('rc-days')||{}).value || 7;
  el.innerHTML = '<span style="color:var(--muted)">Loading…</span>';
  try{
    const d = await api('/api/recent-changes?days='+days+'&limit=80');
    el.innerHTML = _renderRecentChanges(d);
  }catch(e){
    el.innerHTML = '<span style="color:var(--red)">Could not load activity feed. '+esc(apiErr(e))+'</span>';
  }
}
function _renderRecentChanges(d){
  if(!d||!d.changes||!d.changes.length)
    return '<div class="empty" style="padding:12px 0"><div class="et">No changes in this period.</div><div class="es">Nothing was updated in the selected window.</div></div>';
  return d.changes.map(c=>{
    const type = esc(_RC_TYPE_LABEL[c.object_type]||c.object_type);
    const lbl  = esc(c.label||c.action);
    const role = esc((c.role||'').replace(/_/g,' '));
    const rel  = esc(_rcRelTime(c.timestamp));
    const ts   = c.timestamp ? new Date(c.timestamp).toLocaleString('en-AU',{dateStyle:'short',timeStyle:'short'}) : '';
    return `<div style="display:flex;gap:10px;align-items:flex-start;padding:6px 0;border-bottom:1px solid var(--border-light)">
      <span style="min-width:100px;font-size:var(--fs-xs);color:var(--muted);white-space:nowrap;padding-top:1px" title="${esc(ts)}">${rel}</span>
      <span style="flex:1;font-size:var(--fs-base)"><strong>${lbl}</strong> &mdash; ${type}</span>
      <span style="font-size:var(--fs-xs);color:var(--muted);white-space:nowrap">${role}</span>
    </div>`;
  }).join('')
  + (d.count>=80 ? `<div style="font-size:var(--fs-xs);color:var(--muted);padding-top:6px">Showing 80 most recent changes. Narrow the date window to see earlier items.</div>` : '');
}
