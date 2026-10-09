// Main TMS module: Parade Nights -- list, bulk actions, copy/templates, quick
// entry and session builder wizard, detail modal and matrix, notices,
// scheduling and quick edit.
// Extracted verbatim from connected-frontend/index.html (stabilisation Phase 4,
// C6). Top-level function declarations and side-effect-free let/const only;
// loaded as a classic script BEFORE the inline bootstrap, so everything here
// is defined before any page-load code runs. Statements with load-time
// effects stay in index.html in their original order. Parity is proven by
// tools/architecture/frontend_parity.mjs.

// ═══════════════════════════════════════════════════════════
//  PARADE NIGHTS
// ═══════════════════════════════════════════════════════════
function _savePNFilters(tf,sf,q){
  try{ sessionStorage.setItem('aafc_pn_filters',JSON.stringify({tf,sf,q})); }catch(_){}
}
// PN-3: which term is "now"? Derived from the data rather than hardcoded date
// ranges, so it stays correct whatever a squadron's term boundaries are.
// Prefers the next upcoming night; falls back to the most recent past one.
function _currentPNTerm(){
  const pns=((typeof S!=='undefined'&&S.pns)||[]).filter(p=>p.term);
  if(!pns.length)return null;
  const today=new Date().toISOString().slice(0,10);
  const upcoming=pns.filter(p=>p.date>=today).sort((a,b)=>a.date.localeCompare(b.date));
  if(upcoming.length)return upcoming[0].term;
  return pns.slice().sort((a,b)=>b.date.localeCompare(a.date))[0].term;
}
// PN-3: only a real user change persists. renderPN() is also called by
// renderAll() at boot, and when it saved unconditionally it stamped "all" into
// sessionStorage before the page was ever opened -- which then always beat the
// current-term default below.
function pnFilterChanged(){
  const te=document.getElementById('pn-f-term');
  const se=document.getElementById('pn-f-status');
  const qe=document.getElementById('pn-search');
  _savePNFilters(te?te.value:'all', se?se.value:'all', qe?qe.value:'');
  renderPN();
}
function _restorePNFilters(){
  try{
    const saved=JSON.parse(sessionStorage.getItem('aafc_pn_filters')||'null');
    if(!saved){
      // With no saved choice the page used to open on "all" -- every parade
      // night the squadron has ever had, expanded. Open on the current term
      // instead. A choice the user makes is saved above and still wins.
      const te0=document.getElementById('pn-f-term');
      const t=_currentPNTerm();
      if(te0&&t&&[...te0.options].some(o=>o.value===t))te0.value=t;
      return;
    }
    const te=document.getElementById('pn-f-term');
    const se=document.getElementById('pn-f-status');
    const qe=document.getElementById('pn-search');
    if(te&&saved.tf)te.value=saved.tf;
    if(se&&saved.sf)se.value=saved.sf;
    if(qe&&saved.q)qe.value=saved.q;
  }catch(_){}
}
// PN-3: reveal a card's secondary actions. Kept as a class toggle so the
// buttons stay in the DOM order they had, and aria-expanded tracks state.
function togglePNMore(btn,id){
  const box=document.getElementById('pnmore-'+id);
  if(!box)return;
  const open=box.classList.toggle('open');
  btn.setAttribute('aria-expanded',open?'true':'false');
  btn.textContent=open?'Less \u25b4':'More \u25be';
}
const _pnSelected=new Set();
function _pnToggle(id){
  if(_pnSelected.has(id))_pnSelected.delete(id);
  else _pnSelected.add(id);
  _pnBulkUpdate();
}
function _pnBulkUpdate(){
  const bar=document.getElementById('pn-bulk-bar');
  const n=_pnSelected.size;
  bar.style.display=n>0?'flex':'none';
  document.getElementById('pn-bulk-count').textContent=`${n} night${n!==1?'s':''} selected`;
}
function _pnClearSelection(){
  _pnSelected.clear();
  renderPN();
}
async function _pnBulkSetTerm(){
  const term=document.getElementById('pn-bulk-term').value;
  if(!term){showToast('Choose a term first.',true);return;}
  const ids=[..._pnSelected];
  if(!ids.length)return;
  confirmAction(`Set term to "${term}" on ${ids.length} parade night${ids.length!==1?'s':''}?`,async()=>{
    let ok=0,err=0;
    await Promise.all(ids.map(id=>
      api('/api/parade-nights/'+id,{method:'PATCH',body:JSON.stringify({term})})
        .then(()=>ok++).catch(()=>err++)
    ));
    showToast(`Term set on ${ok} night${ok!==1?'s':''}${err?` (${err} failed)`:'.'}`,(err>0));
    _pnSelected.clear();
    await reloadAndRender();
  });
}
async function _pnBulkArchive(){
  const ids=[..._pnSelected];
  if(!ids.length)return;
  confirmAction(`Archive ${ids.length} parade night${ids.length!==1?'s':''} and all their sessions? Records are preserved.`,async()=>{
    let ok=0,err=0;
    await Promise.all(ids.map(id=>
      api('/api/parade-nights/'+id,{method:'DELETE'})
        .then(()=>ok++).catch(()=>err++)
    ));
    showToast(`Archived ${ok} night${ok!==1?'s':''}${err?` (${err} failed)`:''}.`,(err>0));
    _pnSelected.clear();
    await reloadAndRender();
  });
}
function renderPN(){
  const tf=document.getElementById('pn-f-term').value;
  const sf=document.getElementById('pn-f-status').value;
  const q=(document.getElementById('pn-search').value||'').toLowerCase();
  const sorted=[...S.pns].sort((a,b)=>a.date.localeCompare(b.date));
  const filtered=sorted.filter(pn=>{
    if(tf!=='all'&&pn.term!==tf)return false;
    if(sf!=='all'&&!(pn.sessions||[]).some(s=>s.status===sf))return false;
    if(q&&!pn.date.includes(q)&&!(pn.notes||'').toLowerCase().includes(q)&&!(pn.sessions||[]).some(s=>(s.exp||'').toLowerCase().includes(q)||(s.facName||'').toLowerCase().includes(q)))return false;
    return true;
  });
  const el=document.getElementById('pn-list');
  if(!filtered.length){
    const isFiltered=tf!=='all'||sf!=='all'||q;
    const emptyMsg=isFiltered
      ?`No parade nights match the current filters. <button class="btn btn-xs btn-out" onclick="document.getElementById('pn-f-term').value='all';document.getElementById('pn-f-status').value='all';document.getElementById('pn-search').value='';try{sessionStorage.removeItem('aafc_pn_filters');}catch(_){}renderPN()">Clear filters</button>`
      :(canWriteSquadron()?'Select "+ Add Parade Night" above to create one.':'No parade nights scheduled.');
    el.innerHTML=`<div class="empty"><div class="et">No parade nights</div><div class="es">${emptyMsg}</div></div>`;
    return;
  }
  if(tf==='all'){
    const _TERM_LABELS={T1:'Term 1',T2:'Term 2',T3:'Term 3',T4:'Term 4'};
    const byTerm={};
    filtered.forEach(pn=>{const t=pn.term||'Other';(byTerm[t]=byTerm[t]||[]).push(pn);});
    el.innerHTML=Object.keys(byTerm).sort().map(t=>
      `<div class="pn-term-group"><div class="pn-term-hdr">${esc(_TERM_LABELS[t]||t)} <span class="muted" style="font-size:var(--fs-xs);font-weight:400">${byTerm[t].length} night${byTerm[t].length!==1?'s':''}</span></div>`+
      byTerm[t].map(pn=>buildPNCard(pn)).join('')+`</div>`
    ).join('');
  } else {
    el.innerHTML=filtered.map(pn=>buildPNCard(pn)).join('');
  }
}
function buildPNCard(pn){
  const allDel=(pn.sessions||[]).length>0&&(pn.sessions||[]).every(s=>s.status==='delivered');
  const tplName=pn.timing_template_name||((S.timingTemplates||[]).find(t=>t.timing_template_id===pn.timing_template_id)||{}).name||'';
  const tmplBadge=pn.timing_template_id?'<span class="badge b-blue" title="Timing template">'+esc(tplName)+'</span>':'<span class="badge b-grey" title="No timing template assigned">Legacy</span>';
  const sessCards=(pn.sessions||[]).map((s,i)=>`
    <div class="sess-card ${stCls(s.status)||(!s.exp?'unassigned':'')}" onclick="showPNDetail('${pn.date}')">
      <div class="sess-hdr"><span class="sess-num">Sess ${i+1}</span>${stBadge(s.status||'planned')}</div>
      <div class="sess-title">${s.exp?esc(s.exp):'<em style="color:var(--muted)">Lesson: Unassigned</em>'}</div>
      <div class="sess-info">${s.phase?phBadge(s.phase)+' ':''} ${s.facName?esc(s.facName):''} ${s.room?'· '+esc(s.room):''} ${s.trainingClasses&&s.trainingClasses.length?'· '+esc(s.trainingClasses.map(c=>c.display_name).join(', ')):''}</div>
      ${canWriteSquadron()?`<div class="sess-acts no-print" onclick="event.stopPropagation()">
        <button class="btn btn-xs btn-ok" onclick="qkSt('${pn.date}',${i},'delivered')" aria-label="Mark Session ${i+1} delivered">✓</button>
        <button class="btn btn-xs" style="background:#eef0f2;color:var(--steel)" onclick="qkSt('${pn.date}',${i},'not_delivered')" aria-label="Mark Session ${i+1} not delivered">${_ST_ICON.not_delivered}</button>
        <button class="btn btn-xs btn-red" onclick="qkSt('${pn.date}',${i},'cancelled')" aria-label="Cancel Session ${i+1}">✗</button>
        <button class="btn btn-xs btn-sky" onclick="quickEdit('${pn.date}',${i})" aria-label="Edit Session ${i+1}">✏</button>
      </div>`:''}
    </div>`).join('');
  return `<div class="pn-card" id="pncard-${esc(pn.id)}">
    <div class="pn-hdr">
      ${canWriteSquadron()?`<label class="no-print" style="display:flex;align-items:center;justify-content:center;min-width:var(--ctl-min);min-height:var(--ctl-min);padding-right:10px;cursor:pointer" onclick="event.stopPropagation()"><input type="checkbox" id="pnchk-${esc(pn.id)}" aria-label="Select parade night ${esc(fmtDL(pn.date))} for bulk actions" onchange="_pnToggle('${esc(pn.id)}')" style="width:16px;height:16px;cursor:pointer" ${_pnSelected.has(pn.id)?'checked':''}></label>`:''}
      <div><h2 class="pn-date">${fmtDL(pn.date)}</h2><div class="pn-meta">${esc(pn.term)} · ${(pn.sessions||[]).length} sessions${pn.notes?' · '+esc(pn.notes):''}</div><div style="margin-top:3px">${tmplBadge}</div></div>
      <div style="display:flex;gap:6px;align-items:center" class="no-print">
        ${allDel?stBadge('delivered'):stBadge('planned')}
        ${pn.published?'<span class="badge b-ok" title="Weekly Program published">Published</span>':''}
        <button class="btn btn-xs btn-sky" onclick="showPNDetail('${pn.date}')" title="Open this parade night to edit its sessions, facilitators, rooms and periods">Open / edit</button>
        ${canWriteSquadron()?`<button class="btn btn-xs btn-out" title="${tplName?'Change timing template (current: '+esc(tplName)+')':'Set timing template'}" onclick="openPNTimingOverrideModal('${esc(pn.id)}')">Timing…</button>`:''}
        ${canWriteSquadron()?`<button class="btn btn-xs btn-out" title="Copy sessions to another parade night" onclick="openCopyPNModal('${pn.date}')">Copy to…</button>`:''}
        ${canWriteSquadron()?`<button class="btn btn-xs btn-out" aria-expanded="false" aria-controls="pnmore-${esc(pn.id)}" title="More actions for ${esc(fmtDL(pn.date))}" onclick="togglePNMore(this,'${esc(pn.id)}')">More ▾</button>`:''}
        ${canWriteSquadron()?`<span class="pn-more" id="pnmore-${esc(pn.id)}">
          ${(pn.sessions||[]).length>0?`<button class="btn btn-xs btn-out" title="Save this night's sessions as a reusable template" onclick="doSaveAsTemplate('${esc(pn.id)}')">Save as Tpl</button>`:''}
          <button class="btn btn-xs btn-out" title="Apply a saved session template to this parade night" onclick="openApplyTemplateModal('${esc(pn.id)}')">Apply Tpl…</button>
          <button class="btn btn-xs btn-red" aria-label="Delete parade night ${esc(fmtDL(pn.date))}" onclick="delPN('${pn.date}')">×</button>
        </span>`:''}
      </div>
    </div>
    <div class="pn-body"><div class="sess-grid">${sessCards}</div></div>
  </div>`;
}
async function qkSt(date,i,st){
  const pn=S.pns.find(p=>p.date===date);
  const sess=pn&&pn.sessions[i];
  if(!sess||!sess.id){showToast('Could not update — this session could not be found. Refresh the page and try again.',true);return;}
  let reason=null;
  if(OUTCOME_REASON_REQUIRED[st]){
    reason=await collectOutcomeReason(st);
    if(reason===null)return; // cancelled the reason panel
  }
  try{ await apiSetSessionStatus(sess.id, st, reason); await reloadAndRender(); }
  catch(e){ showToast(apiErr(e),true); }
}
async function delPN(date){
  const pn=S.pns.find(p=>p.date===date);
  if(!pn||!pn.id){showToast('This parade night could not be found. Refresh the page and try again.',true);return;}
  confirmAction('Archive this parade night and all its sessions? They will no longer appear in active views, but records are preserved.',async()=>{
    try{ await api('/api/parade-nights/'+pn.id,{method:'DELETE'}); await reloadAndRender(); }
    catch(e){ showToast(apiErr(e),true); }
  });
}

// ── Copy parade night sessions (WORK-11) ─────────────────────────────────────
let _copyPNSourceId=null;
function openCopyPNModal(sourceDate){
  const src=S.pns.find(p=>p.date===sourceDate);
  if(!src||!src.id){showToast('Parade night not found.',true);return;}
  _copyPNSourceId=src.id;
  const sel=document.getElementById('pn-copy-target');
  const others=S.pns.filter(p=>p.id!==src.id&&!p.is_archived)
    .sort((a,b)=>a.date.localeCompare(b.date));
  sel.innerHTML='<option value="">— Select a parade night —</option>'+
    others.map(p=>`<option value="${esc(p.id)}">${fmtD(p.date,{weekday:'short',day:'numeric',month:'short',year:'numeric'})} (${esc(p.term)})</option>`).join('');
  const errEl=document.getElementById('pn-copy-err');
  errEl.style.display='none'; errEl.textContent='';
  openModal('m-pn-copy-sessions');
}
async function doCopyPNSessions(){
  const targetId=document.getElementById('pn-copy-target').value;
  const errEl=document.getElementById('pn-copy-err');
  if(!targetId){errEl.textContent='Select a parade night.';errEl.style.display='block';return;}
  errEl.style.display='none';
  try{
    const r=await api(`/api/parade-nights/${_copyPNSourceId}/copy-sessions-to/${targetId}`,{method:'POST'});
    closeModal('m-pn-copy-sessions');
    const skippedNote=r.skipped>0?` (${r.skipped} period${r.skipped!==1?'s':''} already had sessions — not changed)`:'';
    showToast(`${r.copied} session${r.copied!==1?'s':''} copied.${skippedNote}`);
    await reloadAndRender();
  }catch(e){ errEl.textContent=apiErr(e); errEl.style.display='block'; }
}

// ── Parade Night Templates (WORK-17) ─────────────────────────────────────────
let _applyTplTargetId=null;

async function doSaveAsTemplate(pnId){
  const name=await promptText('Save as Template','Template name',{
    okLabel:'Save',
    context:'Give this session structure a name you can recognise next time (e.g. "Standard Wednesday Night").',
    validate:v=>v.trim().length>0?null:'A name is required.',
  });
  if(name===null)return;
  try{
    await api('/api/parade-nights/'+pnId+'/save-as-template',{method:'POST',body:JSON.stringify({name:name.trim()})});
    showToast('Template saved — use "Apply Tpl…" on any future night to reuse this structure.');
  }catch(e){ showToast(apiErr(e),true); }
}

async function openApplyTemplateModal(pnId){
  _applyTplTargetId=pnId;
  const listEl=document.getElementById('pn-tpl-list');
  const emptyEl=document.getElementById('pn-tpl-empty');
  const errEl=document.getElementById('pn-tpl-err');
  listEl.innerHTML='<div style="color:var(--muted);font-size:var(--fs-sm);padding:8px 0">Loading…</div>';
  emptyEl.style.display='none';
  errEl.style.display='none';
  openModal('m-pn-apply-template');
  try{
    const templates=await api('/api/parade-night-templates');
    if(!templates.length){
      listEl.innerHTML='';
      emptyEl.style.display='block';
      return;
    }
    listEl.innerHTML=templates.map(t=>`
      <div style="border:1px solid var(--border);border-radius:7px;padding:10px 12px;display:flex;align-items:center;gap:10px">
        <div style="flex:1;min-width:0">
          <div style="font-weight:700;font-size:var(--fs-base);color:var(--dark)">${esc(t.name)}</div>
          ${t.description?`<div style="font-size:var(--fs-xs);color:var(--muted);margin-top:2px">${esc(t.description)}</div>`:''}
          <div style="font-size:var(--fs-xs);color:var(--muted);margin-top:3px">${t.session_count} session${t.session_count!==1?'s':''} · Saved ${fmtD(t.created_at.substring(0,10))}</div>
        </div>
        <div style="display:flex;gap:6px;flex-shrink:0">
          <button class="btn btn-xs btn-primary" onclick="doApplyTemplate('${esc(t.id)}')">Apply</button>
          <button class="btn btn-xs btn-red-out" title="Delete this template" aria-label="Delete template ${esc(t.name||t.id)}" onclick="doArchiveTemplate('${esc(t.id)}',this)">×</button>
        </div>
      </div>`).join('');
  }catch(e){ listEl.innerHTML=''; errEl.textContent=apiErr(e); errEl.style.display='block'; }
}

async function doApplyTemplate(tid){
  if(!_applyTplTargetId)return;
  try{
    const r=await api(`/api/parade-night-templates/${tid}/apply/${_applyTplTargetId}`,{method:'POST'});
    closeModal('m-pn-apply-template');
    const skippedNote=r.skipped>0?` (${r.skipped} period${r.skipped!==1?'s':''} already had sessions — not changed)`:'';
    showToast(`Template applied — ${r.applied} session${r.applied!==1?'s':''} added.${skippedNote}`);
    await reloadAndRender();
  }catch(e){
    const errEl=document.getElementById('pn-tpl-err');
    errEl.textContent=apiErr(e); errEl.style.display='block';
  }
}

async function doArchiveTemplate(tid,btn){
  confirmAction('Delete this template? It will no longer be available.',async()=>{
    try{
      await api(`/api/parade-night-templates/${tid}`,{method:'DELETE'});
      btn.closest('div[style*="border:1px"]').remove();
      const listEl=document.getElementById('pn-tpl-list');
      if(!listEl.children.length) document.getElementById('pn-tpl-empty').style.display='block';
    }catch(e){ showToast(apiErr(e),true); }
  });
}

// ── Facilitator Suggestions (FAC-SUG-01) ─────────────────────────────────────
async function _loadFacSuggestions(sessId, date, period){
  const panel=document.getElementById('fac-sugg-panel');
  if(!panel||!sessId)return;
  panel.style.display='none';
  try{
    const url=`/api/sessions/${encodeURIComponent(sessId)}/facilitator-suggestions?parade_date=${encodeURIComponent(date||'')}&period=${encodeURIComponent(period||'')}`;
    const r=await api(url);
    const suggestions=(r.suggestions||[]).filter(s=>s.rank_label!=='UNAVAILABLE').slice(0,5);
    if(!suggestions.length||r.no_recommendation){
      // No useful data — leave panel hidden rather than showing noise
      return;
    }
    const _pillCls={'SUGGESTED':'suggested','AVAILABLE':'available','CONFLICT':'conflict','UNAVAILABLE':'unavailable'};
    panel.className='fac-sugg-panel';
    panel.innerHTML='<div class="fac-sugg-title">Facilitator suggestions</div>'+
      suggestions.map(s=>{
        const cls=_pillCls[s.rank_label]||'available';
        const allReasons=[...(s.reasons||[]),...(s.conflicts||[])];
        return `<div class="fac-sugg-item">
          <span class="fac-sugg-pill ${cls}">${esc(s.rank_label)}</span>
          <div>
            <div class="fac-sugg-name">${esc(s.display_name)}</div>
            <div class="fac-sugg-reasons">${allReasons.map(r=>esc(r)).join(' · ')}</div>
          </div>
        </div>`;
      }).join('');
    panel.style.display='block';
  }catch(_){
    // Non-critical — suggestion panel failure must not break session edit
  }
}

// ── Quick Entry (PN-WIZ-01 — simple session add) ──────────────────────────────
async function _qeSubmit(pnId, ds){
  const msgEl=document.getElementById('qe-msg');
  if(msgEl) msgEl.textContent='';
  const period=parseInt(document.getElementById('qe-period').value,10)||1;
  const currId=document.getElementById('qe-curr-sel').value;
  const facId=document.getElementById('qe-fac-sel').value;
  const roomId=document.getElementById('qe-room-sel').value;
  try{
    await api('/api/sessions',{method:'POST',body:JSON.stringify({
      parade_night_id:pnId,
      period_number:period,
      curriculum_item_id:currId||null,
      facilitator_id:facId||null,
      training_area_id:roomId||null,
    })});
    await reloadAndRender();
    showPNDetail(ds);
  }catch(e){
    if(msgEl) msgEl.textContent=apiErr(e);
  }
}

// ── Guided Session Builder Wizard (PN-WIZ-01) ─────────────────────────────────
let _wizState={pnId:null,date:null,step:1,classIds:[],currId:null,currTitle:null,period:1,facId:null,roomId:null,notes:''};

function _wizOpen(pnId, date){
  _wizState={pnId,date,step:1,classIds:[],currId:null,currTitle:null,period:1,facId:null,roomId:null,notes:''};
  _wizStep(1);
  openModal('m-sess-wizard');
}

function _wizCancel(){
  closeModal('m-sess-wizard');
}

function _wizStep(n){
  const MAX=6;
  _wizState.step=n;
  // Update step label and progress dots
  const isCheck=(n==='check');
  const stepNum=isCheck?MAX+1:n;
  document.getElementById('wiz-step-label').textContent=isCheck?'Check before saving':`Step ${n} of ${MAX}`;
  for(let i=1;i<=MAX;i++){
    const dot=document.getElementById('wdot-'+i);
    if(!dot)continue;
    dot.className='wiz-dot'+(isCheck||i<n?' done':i===n?' active':'');
  }
  const ckDot=document.getElementById('wdot-check');
  if(ckDot) ckDot.className='wiz-dot'+(isCheck?' active':'');
  // Show/hide step panels
  [1,2,3,4,5,6,'check'].forEach(s=>{
    const el=document.getElementById('wiz-step-'+(s==='check'?'check':s));
    if(el) el.style.display=(isCheck?s==='check':s===n)?'':'none';
  });
  // Back/Next/Save buttons
  const backBtn=document.getElementById('wiz-back-btn');
  const nextBtn=document.getElementById('wiz-next-btn');
  const saveBtn=document.getElementById('wiz-save-btn');
  if(backBtn) backBtn.style.display=(n===1&&!isCheck)?'none':'';
  if(nextBtn) nextBtn.style.display=isCheck?'none':'';
  if(saveBtn) saveBtn.style.display=isCheck?'':'none';
  // Step-specific setup
  if(n===1) _wizSetupStep1();
  if(n===2) _wizSetupStep2();
  if(n===4) _wizSetupStep4();
  if(n===5) _wizSetupStep5();
  if(isCheck) _wizSetupCheck();
  const msgEl=document.getElementById('wiz-msg');
  if(msgEl) msgEl.textContent='';
}

function _wizSetupStep1(){
  const pn=S.pns.find(p=>p.id===_wizState.pnId);
  const classes=pn?((pn.classes||[]).length?(pn.classes):(S.trainingClasses||[])):(S.trainingClasses||[]);
  const list=document.getElementById('wiz-classes-list');
  if(!list)return;
  if(!classes.length){
    list.innerHTML='<span class="muted" style="font-size:var(--fs-sm)">No Training Classes configured — you can skip this step.</span>';
    return;
  }
  list.innerHTML=classes.map(c=>{
    const sel=_wizState.classIds.includes(c.id||c.class_id);
    return `<label class="wiz-class-item"><input type="checkbox" value="${esc(c.id||c.class_id)}" ${sel?'checked':''} onchange="_wizToggleClass(this)"> <span>${esc(c.display_name||c.name||c.class_name||'')}</span></label>`;
  }).join('');
}

function _wizToggleClass(el){
  const id=el.value;
  if(el.checked) _wizState.classIds=[..._wizState.classIds,id];
  else _wizState.classIds=_wizState.classIds.filter(x=>x!==id);
}

function _wizSetupStep2(){
  const search=(document.getElementById('wiz-curr-search')||{}).value||'';
  _wizRenderCurrList(search);
}

function _wizFilterCurr(){
  const search=(document.getElementById('wiz-curr-search')||{}).value||'';
  _wizRenderCurrList(search);
}

function _wizRenderCurrList(q){
  const list=document.getElementById('wiz-curr-list');
  if(!list)return;
  const items=(S.curr||[]).filter(c=>!q||c.title.toLowerCase().includes(q.toLowerCase())||c.code.toLowerCase().includes(q.toLowerCase()));
  if(!items.length){list.innerHTML='<span class="muted" style="font-size:var(--fs-sm)">No matching items.</span>';return;}
  list.innerHTML=items.map(c=>{
    const sel=_wizState.currId===c.id;
    return `<div class="wiz-curr-item${sel?' sel':''}" onclick="_wizSelectCurr('${esc(c.id)}','${_jsAttr(c.title)}')">${esc(c.code)} — ${esc(c.title)}</div>`;
  }).join('');
}

function _wizSelectCurr(id, title){
  _wizState.currId=id; _wizState.currTitle=title;
  _wizRenderCurrList((document.getElementById('wiz-curr-search')||{}).value||'');
}

function _wizSkipCurrChange(){
  const cb=document.getElementById('wiz-skip-curr');
  const inp=document.getElementById('wiz-custom-title');
  const list=document.getElementById('wiz-curr-list');
  const search=document.getElementById('wiz-curr-search');
  const skip=cb&&cb.checked;
  if(inp) inp.style.display=skip?'':'none';
  if(list) list.style.display=skip?'none':'';
  if(search) search.style.display=skip?'none':'';
  if(!skip){_wizState.currId=null;_wizState.currTitle=null;}
}

function _wizSetupStep4(){
  // Populate facilitator select
  const sel=document.getElementById('wiz-fac-sel');
  if(sel){
    sel.innerHTML='<option value="">— None —</option>'+(S.facs||[]).map(f=>`<option value="${esc(f.id)}" ${f.id===_wizState.facId?'selected':''}>${esc(facDisplay(f))}</option>`).join('');
  }
  // Load FAC-SUG-01 suggestions into wizard panel
  const panel=document.getElementById('wiz-fac-sugg');
  if(!panel)return;
  panel.style.display='none';
  const {date,period}=_wizState;
  if(!date)return;
  // Use an existing session on this PN as scope context for suggestions
  const pnForSugg=S.pns.find(p=>p.id===_wizState.pnId);
  const existSess=(pnForSugg&&pnForSugg.sessions)||[];
  const sidForSugg=existSess[0]?existSess[0].id||existSess[0].session_id:null;
  if(!sidForSugg)return; // No existing session to anchor scope — skip suggestions
  api(`/api/sessions/${encodeURIComponent(sidForSugg)}/facilitator-suggestions?parade_date=${encodeURIComponent(date||'')}&period=${encodeURIComponent(period||1)}`)
    .then(r=>{
      if(!r)return;
      const _pillCls={'SUGGESTED':'suggested','AVAILABLE':'available','CONFLICT':'conflict','UNAVAILABLE':'unavailable'};
      const suggs=(r.suggestions||[]).filter(s=>s.rank_label!=='UNAVAILABLE').slice(0,4);
      if(!suggs.length||r.no_recommendation)return;
      panel.innerHTML=`<div class="wiz-fac-sugg-title">Suggestions</div><div class="wiz-fac-pill-row">`+
        suggs.map(s=>{
          const cls=_pillCls[s.rank_label]||'available';
          return `<span class="fac-sugg-item" style="cursor:pointer" onclick="_wizPickFac('${esc(s.facilitator_id)}')" title="${esc((s.reasons||[]).join('; '))}">
            <span class="fac-sugg-pill ${cls}">${esc(s.rank_label)}</span>
            <span class="fac-sugg-name" style="font-size:var(--fs-sm)">${esc(s.display_name)}</span>
          </span>`;
        }).join('')+'</div>';
      panel.style.display='block';
    }).catch(()=>{});
}

function _wizPickFac(facId){
  _wizState.facId=facId;
  const sel=document.getElementById('wiz-fac-sel');
  if(sel) sel.value=facId;
}

function _wizSetupStep5(){
  const sel=document.getElementById('wiz-room-sel');
  if(sel){
    sel.innerHTML='<option value="">— None —</option>'+(S.rooms||[]).map(r=>`<option value="${esc(r.id)}" ${r.id===_wizState.roomId?'selected':''}>${esc(r.name)}</option>`).join('');
  }
}

function _wizSetupCheck(){
  // Collect any remaining edits from current step controls
  const period=parseInt((document.getElementById('wiz-period')||{}).value||'1',10);
  _wizState.period=period||1;
  const facSel=document.getElementById('wiz-fac-sel');
  if(facSel&&facSel.value) _wizState.facId=facSel.value;
  const roomSel=document.getElementById('wiz-room-sel');
  if(roomSel&&roomSel.value) _wizState.roomId=roomSel.value;
  const notes=(document.getElementById('wiz-notes')||{}).value||'';
  _wizState.notes=notes;
  // Custom title override
  const skipCurr=(document.getElementById('wiz-skip-curr')||{}).checked;
  if(skipCurr){
    const ct=(document.getElementById('wiz-custom-title')||{}).value||'';
    _wizState.currId=null; _wizState.currTitle=ct||null;
  }
  // Build summary
  const fac=_wizState.facId?((S.facs||[]).find(f=>f.id===_wizState.facId)):null;
  const room=_wizState.roomId?((S.rooms||[]).find(r=>r.id===_wizState.roomId)):null;
  const classNames=_wizState.classIds.map(id=>{
    const pn=S.pns.find(p=>p.id===_wizState.pnId);
    const allC=[...((pn&&pn.classes)||[]),...(S.trainingClasses||[])];
    const c=allC.find(x=>(x.id||x.class_id)===id);
    return c?(c.display_name||c.name||c.class_name||id):id;
  });
  const sumEl=document.getElementById('wiz-summary');
  if(sumEl){
    const rows=[
      {l:'Period',v:_wizState.period},
      {l:'Training Class',v:classNames.length?classNames.join(', '):'(none)'},
      {l:'Curriculum item',v:_wizState.currTitle||'(none / custom)'},
      {l:'Facilitator',v:fac?facDisplay(fac):'(none)'},
      {l:'Room',v:room?room.name:'(none)'},
      {l:'Notes',v:_wizState.notes||'(none)'},
    ];
    sumEl.innerHTML=rows.map(r=>`<div class="wiz-summary-row"><span class="wiz-summary-label">${esc(r.l)}</span><span class="wiz-summary-val">${esc(String(r.v))}</span></div>`).join('');
  }
  const conflEl=document.getElementById('wiz-conflicts');
  if(conflEl) conflEl.style.display='none';
}

function _wizNext(){
  const n=_wizState.step;
  const msgEl=document.getElementById('wiz-msg');
  if(msgEl) msgEl.textContent='';
  // Collect data from current step
  if(n===3){
    const period=parseInt((document.getElementById('wiz-period')||{}).value||'1',10);
    if(!period||period<1){if(msgEl)msgEl.textContent='Enter a valid period number.';return;}
    _wizState.period=period;
  }
  if(n===4){
    const facSel=document.getElementById('wiz-fac-sel');
    _wizState.facId=(facSel&&facSel.value)||null;
  }
  if(n===5){
    const roomSel=document.getElementById('wiz-room-sel');
    _wizState.roomId=(roomSel&&roomSel.value)||null;
  }
  if(n===6){
    const notes=(document.getElementById('wiz-notes')||{}).value||'';
    _wizState.notes=notes;
    _wizStep('check');
  } else {
    _wizStep(n+1);
  }
}

function _wizBack(){
  if(_wizState.step==='check'){_wizStep(6);return;}
  const n=_wizState.step;
  if(n>1) _wizStep(n-1);
}

async function _wizSave(){
  const msgEl=document.getElementById('wiz-msg');
  const saveBtn=document.getElementById('wiz-save-btn');
  if(msgEl) msgEl.textContent='';
  if(saveBtn){saveBtn.disabled=true;saveBtn.textContent='Saving…';}
  const skipCurr=(document.getElementById('wiz-skip-curr')||{}).checked;
  const customTitle=skipCurr?((document.getElementById('wiz-custom-title')||{}).value||null):null;
  try{
    const body={
      parade_night_id:_wizState.pnId,
      period_number:_wizState.period,
      curriculum_item_id:_wizState.currId||null,
      custom_title:customTitle||null,
      facilitator_id:_wizState.facId||null,
      training_area_id:_wizState.roomId||null,
    };
    const newSess=await api('/api/sessions',{method:'POST',body:JSON.stringify(body)});
    // Assign training classes if selected
    if(_wizState.classIds.length&&newSess){
      const sid=newSess.id||newSess.session_id;
      try{await api('/api/sessions/'+sid+'/audience',{method:'PUT',body:JSON.stringify({training_class_ids:_wizState.classIds})});}catch(_){}
    }
    closeModal('m-sess-wizard');
    await reloadAndRender();
    showPNDetail(_wizState.date);
  }catch(e){
    if(msgEl) msgEl.textContent=apiErr(e);
    if(saveBtn){saveBtn.disabled=false;saveBtn.textContent='Save Session';}
  }
}

// ── Bulk Apply Template (BULK-01) ────────────────────────────────────────────
async function openBulkApplyModal(){
  const ids=[..._pnSelected];
  if(!ids.length){showToast('Select at least one parade night first.',true);return;}
  const selEl=document.getElementById('bat-tpl-sel');
  const prevEl=document.getElementById('bat-preview');
  const msgEl=document.getElementById('bat-msg');
  const confirmBtn=document.getElementById('bat-confirm-btn');
  selEl.innerHTML='<option value="">— loading templates… —</option>';
  prevEl.style.display='none';
  msgEl.style.display='none';
  confirmBtn.style.display='none';
  openModal('m-bulk-apply-tpl');
  try{
    const templates=await api('/api/parade-night-templates');
    if(!templates.length){
      selEl.innerHTML='<option value="">— No templates saved yet —</option>';
    } else {
      selEl.innerHTML='<option value="">— choose a template —</option>'+
        templates.map(t=>`<option value="${esc(t.id)}">${esc(t.name)} (${t.session_count} session${t.session_count!==1?'s':''})</option>`).join('');
    }
  }catch(e){
    selEl.innerHTML='<option value="">— Error loading templates —</option>';
    msgEl.textContent=apiErr(e); msgEl.style.display='block';
  }
}

async function _bulkApplyPreview(){
  const tid=document.getElementById('bat-tpl-sel').value;
  const conflict=document.getElementById('bat-conflict-sel').value;
  const prevEl=document.getElementById('bat-preview');
  const msgEl=document.getElementById('bat-msg');
  const confirmBtn=document.getElementById('bat-confirm-btn');
  const confirmCount=document.getElementById('bat-confirm-count');
  msgEl.style.display='none';
  prevEl.style.display='none';
  confirmBtn.style.display='none';
  if(!tid){msgEl.textContent='Select a template first.';msgEl.style.display='block';return;}
  const ids=[..._pnSelected];
  try{
    const r=await api('/api/parade-nights/bulk-apply-template',{
      method:'POST',
      body:JSON.stringify({template_id:tid,parade_night_ids:ids,conflict_resolution:conflict,dry_run:true}),
    });
    prevEl.innerHTML=`<strong>Preview (${ids.length} night${ids.length!==1?'s':''} selected)</strong><br>`+
      `Nights to process: <strong>${r.nights_processed}</strong>`+
      (r.nights_skipped?` &middot; Nights skipped: <strong>${r.nights_skipped}</strong>`:'')+
      (r.conflict_nights?` &middot; Nights with existing sessions: <strong>${r.conflict_nights}</strong>`:'')+
      `<br>Sessions to add: <strong>${r.sessions_added}</strong>`+
      (r.sessions_skipped?` &middot; Period slots skipped: <strong>${r.sessions_skipped}</strong>`:'');
    prevEl.style.display='block';
    if(r.nights_processed>0){
      confirmCount.textContent=r.nights_processed;
      confirmBtn.style.display='';
    }
  }catch(e){ msgEl.textContent=apiErr(e); msgEl.style.display='block'; }
}

async function _bulkApplyConfirm(){
  const tid=document.getElementById('bat-tpl-sel').value;
  const conflict=document.getElementById('bat-conflict-sel').value;
  const msgEl=document.getElementById('bat-msg');
  const ids=[..._pnSelected];
  msgEl.style.display='none';
  try{
    const r=await api('/api/parade-nights/bulk-apply-template',{
      method:'POST',
      body:JSON.stringify({template_id:tid,parade_night_ids:ids,conflict_resolution:conflict,dry_run:false}),
    });
    closeModal('m-bulk-apply-tpl');
    _pnClearSelection();
    showToast(`Template applied — ${r.sessions_added} session${r.sessions_added!==1?'s':''} added across ${r.nights_processed} night${r.nights_processed!==1?'s':''}.`);
    await reloadAndRender();
  }catch(e){ msgEl.textContent=apiErr(e); msgEl.style.display='block'; }
}

// ADD PARADE NIGHT
// Creates the night and its time structure only.
// Sessions are planned into periods separately (one period can hold many concurrent sessions).

function _pnLoadTplOptions(date){
  const sel=document.getElementById('pn-tpl-sel');
  const msg=document.getElementById('pn-tpl-msg');
  if(!sel)return;
  if(!date){
    sel.innerHTML='<option value="">— select a date first —</option>';
    if(msg){msg.textContent='';msg.style.color='';}
    return;
  }
  // Mirror backend _effective_template: active, not archived, effective_from <= date,
  // effective_to is null or >= date. Sort most-recent effective_from first so the
  // auto-selected option matches what the backend would resolve.
  const templates=((typeof S!=='undefined'&&S.timingTemplates)||[])
    .filter(t=>t.active_status!==false&&!t.is_archived
               &&(t.effective_from||'')<=date
               &&(!t.effective_to||t.effective_to>=date))
    .sort((a,b)=>String(b.effective_from||'').localeCompare(String(a.effective_from||'')));
  if(!templates.length){
    sel.innerHTML='<option value="">No template covers this date</option>';
    if(msg){msg.textContent='Create a timing template in Unit Settings that covers '+date+'.';msg.style.color='var(--red)';}
    return;
  }
  sel.innerHTML=templates.map(t=>{
    const periods=(t.blocks||[]).filter(b=>b.is_instructional_period).length;
    return '<option value="'+esc(t.timing_template_id)+'">'+esc(t.name)+
           ' · '+periods+' period'+(periods===1?'':'s')+'</option>';
  }).join('');
  if(msg){msg.textContent='';msg.style.color='';}
}

function openAddPN(date){
  if(date)document.getElementById('pn-date').value=date;
  _pnLoadTplOptions(document.getElementById('pn-date').value);
  openModal('m-add-pn');
}

async function addPN(){
  const date=document.getElementById('pn-date').value;
  const term=document.getElementById('pn-term').value;
  const notes=document.getElementById('pn-notes').value;
  const tmplId=document.getElementById('pn-tpl-sel').value;
  if(!date){showToast('Select a date.',true);return;}
  if(!tmplId){showToast('Select a timing template for this parade night.',true);return;}
  if(S.pns.find(p=>p.date===date)){showToast('A parade night already exists on this date.',true);return;}
  try{
    await api('/api/parade-nights',{method:'POST',body:JSON.stringify({date,term,timing_template_id:tmplId,notes:notes||null,parade_type:'normal'})});
    await reloadAndRender();
    closeModal('m-add-pn');
    document.getElementById('pn-date').value='';
    document.getElementById('pn-notes').value='';
    showPNDetail(date);
  }catch(e){showToast(apiErr(e),true);}
}

// PN DETAIL MODAL
// TB-1: the printed Weekly Program lays sessions out by timing block, and
// nothing in either frontend could ever set one -- every session fell through to
// the "Unlinked periods" footnote. These are the blocks a night can offer:
// its template's Training Period blocks, in order.
function _effectiveTimingTemplate(){
  // The template in force today: the most recent one whose effective_from has
  // passed and whose effective_to (if any) has not. Mirrors _effective_template()
  // in backend/app/routers/timing.py -- if that changes, this must follow.
  const today=new Date().toISOString().slice(0,10);
  return ((typeof S!=='undefined'&&S.timingTemplates)||[])
    .filter(t=>t.active_status!==false && (t.effective_from||'') <= today
               && (!t.effective_to || t.effective_to >= today))
    .sort((a,b)=>String(b.effective_from||'').localeCompare(String(a.effective_from||'')))[0]||null;
}
function _renderSessionStructureNote(){
  const el=document.getElementById('s-sess-effect');
  if(!el)return;
  const tpl=_effectiveTimingTemplate();
  if(tpl){
    const periods=(tpl.blocks||[]).filter(b=>b.is_instructional_period).length;
    el.className='alert a-info';
    el.innerHTML='In effect now: <b>'+esc(tpl.name||'your timing template')+'</b> defines <b>'+
      periods+' training period'+(periods===1?'':'s')+'</b>. New parade nights use this template automatically.';
  }else{
    el.className='alert a-warn';
    el.innerHTML='<b>No timing template covers today.</b> A timing template is required to create new parade nights — add one below.';
  }
}

function _pnPeriodBlocks(pn){
  if(!pn||!pn.timing_template_id) return [];
  const tpl=((typeof S!=='undefined'&&S.timingTemplates)||[])
    .find(t=>t.timing_template_id===pn.timing_template_id);
  if(!tpl) return [];
  return (tpl.blocks||[])
    .filter(b=>b.is_instructional_period)
    .sort((a,b)=>(a.display_order||0)-(b.display_order||0));
}
function _pnPeriodLabel(b){
  const t=[b.start_time,b.end_time].filter(Boolean).join('\u2013');
  return (b.block_name||'Period')+(t?' \u00b7 '+t:'');
}

async function showPNDetail(ds){
  const pn=S.pns.find(p=>p.date===ds);if(!pn)return;
  document.getElementById('pn-det-title').textContent=fmtDL(ds);
  openModal('m-pn-detail');
  document.getElementById('pn-det-body').innerHTML='<div class="muted" style="padding:20px;text-align:center;font-size:var(--fs-sm)">Loading…</div>';
  let plan;
  try{plan=await api('/api/parade-nights/'+pn.id+'/planner');}
  catch(e){document.getElementById('pn-det-body').innerHTML='<div style="color:var(--red);padding:20px;font-size:var(--fs-sm)">'+esc(apiErr(e))+'</div>';return;}
  const pnd=plan.parade_night;
  const timing=plan.timing;
  const groups=plan.groups;
  const sessions=plan.sessions;
  // sessMap: "period:classId" → session  |  "period:custom:customPhaseId" → session
  const sessMap=new Map();
  for(const s of sessions){
    const p=s.period_number;if(p==null)continue;
    for(const a of(s.training_class_audiences||[])) sessMap.set(p+':'+a.training_class_id,s);
    for(const a of(s.custom_phase_audiences||[])) sessMap.set(p+':custom:'+a.custom_phase_id,s);
  }
  window._pnPlan={pnd,timing,groups,sessions,sessMap,ds};
  const instrPeriods=timing.instructional_periods||[];
  const tcGroups=groups.filter(g=>g.type==='training_phase'&&(g.classes||[]).length>0);
  const customGroups=groups.filter(g=>g.type==='custom_training');
  let html='';

  // ── Header strip ──────────────────────────────────────────────────────────
  const tmplName=timing.timing_template_name;
  html+=`<div style="border:1.5px solid var(--border);border-radius:8px;padding:10px 14px;margin-bottom:10px;background:var(--surface-2)">`;
  html+=`<div style="display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-bottom:${instrPeriods.length?'6':'0'}px">`;
  if(pnd.term) html+=`<span class="badge b-info">${esc(pnd.term)}</span>`;
  if(tmplName) html+=`<span style="font-size:var(--fs-xs);color:var(--muted)">Template:</span><span style="font-size:var(--fs-xs);font-weight:700;margin-left:4px">${esc(tmplName)}</span>`;
  html+=`</div>`;
  if(instrPeriods.length){
    html+=`<div style="display:flex;flex-wrap:wrap;gap:4px">`;
    for(const b of timing.blocks){
      const isInstr=b.is_instructional;
      const timeStr=b.start_time?` <span style="color:var(--muted);font-size:9px">${esc(b.start_time.slice(0,5))}</span>`:'';
      html+=`<span style="font-size:10px;padding:2px 7px;border-radius:10px;border:1px solid ${isInstr?'var(--blue)':'var(--border)'};color:${isInstr?'var(--blue)':'var(--muted)'}">${esc(b.block_label)}${timeStr}</span>`;
    }
    html+=`</div>`;
  }
  html+=`</div>`;

  // ── Legacy banner ─────────────────────────────────────────────────────────
  if(!pnd.timing_template_id){
    html+=`<div class="alert a-warn" style="margin-bottom:10px"><b>Legacy timing</b> — no Timing Template assigned to this Parade Night.`;
    if(canWriteSquadron()) html+=` <button class="btn btn-xs btn-sky" style="margin-left:8px" onclick="openPNTimingOverrideModal('${esc(pnd.parade_night_id)}')">Choose Timing Template</button>`;
    html+=`</div>`;
  }

  // ── Notes ─────────────────────────────────────────────────────────────────
  html+=`<div style="margin-bottom:10px">`;
  html+=`<label for="pnd-notes" style="font-size:var(--fs-xs);font-weight:700;color:var(--dark);text-transform:uppercase;letter-spacing:.08em">Notes <span class="save-ind" id="pnd-notes-status"></span></label>`;
  html+=`<input id="pnd-notes" value="${esc(pnd.notes||'')}" placeholder="Add notes for this parade night…" style="margin-top:4px" ${canWriteSquadron()?'':'disabled'}>`;
  html+=`</div>`;

  // ── Notices card ──────────────────────────────────────────────────────────
  // REM-34: kept deliberately simple (text + priority only) -- see loadPNNotices.
  html+=`<div id="pn-notices-card" style="border:1.5px solid var(--border);border-radius:8px;padding:12px;margin-bottom:10px">`;
  html+=`<div style="font-size:var(--fs-xs);font-weight:900;color:var(--dark);text-transform:uppercase;letter-spacing:.08em;margin-bottom:7px">Notices</div>`;
  html+=`<div id="pn-notices-list"><div class="muted" style="font-size:var(--fs-xs)">Loading…</div></div>`;
  if(canWriteSquadron()) html+=`<div style="margin-top:8px;display:flex;gap:6px;align-items:flex-start">
    <input id="pn-notice-text" placeholder="Notice text…" style="flex:1" maxlength="500" aria-label="New notice text">
    <select id="pn-notice-priority" aria-label="Notice priority" style="width:auto">
      <option value="normal">Normal</option>
      <option value="urgent">Urgent</option>
    </select>
    <button class="btn btn-xs btn-sky" onclick="addPNNotice('${esc(pnd.parade_night_id)}')">Add</button>
  </div>`;
  html+=`</div>`;

  // ── Timetable matrix ──────────────────────────────────────────────────────
  if(instrPeriods.length&&(tcGroups.length||customGroups.length)){
    html+=`<div style="overflow-x:auto;margin-bottom:10px">`;
    html+=`<table style="width:100%;border-collapse:collapse;font-size:var(--fs-xs)">`;
    html+=`<thead><tr><th style="text-align:left;padding:6px 8px;background:var(--surface-2);border:1px solid var(--border);min-width:140px">Training Class</th>`;
    for(const ip of instrPeriods){
      const timeStr=ip.start_time?`<div style="font-size:9px;color:var(--muted);font-weight:400">${esc(ip.start_time.slice(0,5))}</div>`:'';
      html+=`<th style="text-align:center;padding:6px 8px;background:var(--surface-2);border:1px solid var(--border);min-width:80px;font-weight:700">${esc(ip.block_label)}${timeStr}</th>`;
    }
    html+=`</tr></thead><tbody>`;
    for(const g of tcGroups){
      html+=`<tr><td colspan="${instrPeriods.length+1}" style="padding:4px 8px;background:var(--surface-2);border:1px solid var(--border);font-weight:700;color:var(--dark);font-size:10px;text-transform:uppercase;letter-spacing:.06em">${esc(g.name)}</td></tr>`;
      for(const cls of g.classes){
        html+=`<tr><td style="padding:5px 8px;border:1px solid var(--border);color:var(--text-2)">${esc(cls.display_name)}</td>`;
        for(const ip of instrPeriods) html+=_pnMatrixCell(pnd.parade_night_id,ds,ip.period_number,cls.training_class_id,null,sessMap.get(ip.period_number+':'+cls.training_class_id));
        html+=`</tr>`;
      }
    }
    for(const cg of customGroups){
      html+=`<tr><td style="padding:5px 8px;border:1px solid var(--border);color:var(--text-2);font-style:italic">${esc(cg.name)}</td>`;
      for(const ip of instrPeriods) html+=_pnMatrixCell(pnd.parade_night_id,ds,ip.period_number,null,cg.custom_phase_id,sessMap.get(ip.period_number+':custom:'+cg.custom_phase_id));
      html+=`</tr>`;
    }
    html+=`</tbody></table></div>`;
  }else if(instrPeriods.length&&!tcGroups.length&&!customGroups.length){
    html+=`<div class="alert a-info" style="margin-bottom:10px">No Training Classes are configured for this Parade Night date. Add Training Classes in Unit Setup → Training Classes to enable the planning matrix.</div>`;
  }

  // ── Inline cell editor (hidden until a cell is clicked) ───────────────────
  html+=`<div id="pn-cell-editor" style="display:none;border:1.5px solid var(--blue);border-radius:8px;padding:12px;margin-bottom:10px;background:var(--accent-light)"></div>`;

  // ── Operational buttons ───────────────────────────────────────────────────
  if(canWriteSquadron()){
    html+=`<div class="no-print" style="margin-top:10px;padding-top:10px;border-top:1px solid var(--border-light);display:flex;flex-wrap:wrap;gap:8px;align-items:center">`;
    if(sessions.length>0){
      html+=`<button class="btn btn-out" onclick="doMarkRemainingDelivered('${esc(ds)}')" title="Mark every Planned session as Delivered.">Mark remaining delivered</button>`;
      html+=`<button class="btn btn-red-out" onclick="doCancelAllSessions('${esc(ds)}')" title="Cancel every Planned session.">Cancel all remaining</button>`;
    }
    if(pnd.closeout_status!=='closed'){
      html+=`<button class="btn btn-xs btn-red-out" onclick="doClosePN('${esc(pnd.parade_night_id)}')" title="Closes this Parade Night once all outcomes are recorded.">Close Parade Night</button>`;
      html+=`<span style="font-size:var(--fs-xs);color:var(--muted);margin-left:4px">Locks the night once all outcomes are recorded.</span>`;
    }else{
      html+=`<span class="badge b-amber">Closed</span> <span style="font-size:var(--fs-xs);color:var(--muted)">This Parade Night is closed.</span>`;
    }
    html+=`</div>`;
  }

  document.getElementById('pn-det-body').innerHTML=html;

  // Wire autosave for notes
  const notesEl=document.getElementById('pnd-notes');
  if(notesEl&&canWriteSquadron()){
    notesEl.addEventListener('input',_mkAutoSave(async(val)=>{
      const livePn=S.pns.find(p=>p.id===pnd.parade_night_id);
      await api('/api/parade-nights/'+pnd.parade_night_id,{method:'PATCH',body:JSON.stringify({
        notes:val,version:livePn?livePn.version:undefined
      })});
      if(livePn)livePn.notes=val;
    },'pnd-notes-status'));
  }
  loadPNNotices(pnd.parade_night_id);
}

// ── Matrix cell renderer ──────────────────────────────────────────────────────
function _pnMatrixCell(pnId,ds,period,classId,customPhaseId,sess){
  const canWrite=canWriteSquadron();
  const cArg=classId?`'${esc(classId)}'`:'null';
  const cpArg=customPhaseId?`'${esc(customPhaseId)}'`:'null';
  if(sess){
    const sc={planned:'var(--blue)',delivered:'var(--ok)',cancelled:'var(--red)',not_delivered:'var(--red)',delivered_with_issue:'var(--warn)',cancelled_late:'var(--red)',rescheduled:'var(--warn)'};
    const col=sc[sess.status]||'var(--muted)';
    const lb={planned:'Planned',delivered:'Delivered',cancelled:'Cancelled',not_delivered:'Not delivered',delivered_with_issue:'Delivered with issue',cancelled_late:'Cancelled late',rescheduled:'Rescheduled'}[sess.status]||String(sess.status||'Unknown').replace(/_/g,' ');
    const glyph={delivered:'✓',cancelled:'✗',not_delivered:'✗',delivered_with_issue:'!',cancelled_late:'✗',rescheduled:'↻'}[sess.status]||'';
    // Three content rows: Curriculum / Facilitator / Room. Status is secondary:
    // left-border colour encodes state; icon badge shown only for non-planned states.
    const curr=sess.curriculum_title_at_time||sess.custom_title||'';
    const fac=sess.facilitator_display_name_at_time||'';
    const room=sess.training_area_name_at_time||'';
    const hover=esc([`Status: ${lb}`,curr,fac,room].filter(Boolean).join(' · '));
    const badge=sess.status!=='planned'?`<div aria-hidden="true" style="font-size:9px;font-weight:700;color:${col};margin-top:1px">${glyph||esc(lb)}</div>`:'';
    const inner=`<div style="border-left:3px solid ${col};padding-left:3px" title="${hover}">
<span class="sr-only">Status: ${esc(lb)}</span>
<div style="font-size:9px;font-weight:600;color:var(--text-2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:88px">${curr?esc(curr):'<span style="color:var(--muted)">—</span>'}</div>
<div style="font-size:9px;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:88px">${fac?esc(fac):'—'}</div>
<div style="font-size:9px;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:88px">${room?esc(room):'—'}</div>
${badge}</div>`;
    if(canWrite) return `<td style="border:1px solid var(--border);padding:4px;vertical-align:top;cursor:pointer" onclick="_pnCellClick('${esc(pnId)}','${esc(ds)}',${period},${cArg},${cpArg},'${esc(sess.session_id)}')">${inner}</td>`;
    return `<td style="border:1px solid var(--border);padding:4px;vertical-align:top">${inner}</td>`;
  }
  if(canWrite) return `<td style="border:1px solid var(--border);padding:4px;text-align:center;cursor:pointer;opacity:.4" onclick="_pnCellClick('${esc(pnId)}','${esc(ds)}',${period},${cArg},${cpArg},null)"><div style="font-size:11px;color:var(--blue)">+</div></td>`;
  return `<td style="border:1px solid var(--border);padding:4px;text-align:center"><div style="font-size:10px;color:var(--lgrey)">—</div></td>`;
}

// ── Cell click: open inline editor pre-filled with period + class ─────────────
async function _pnCellClick(pnId,ds,period,classId,customPhaseId,sessionId){
  if(!canWriteSquadron())return;
  const editorEl=document.getElementById('pn-cell-editor');if(!editorEl)return;
  const plan=window._pnPlan;if(!plan)return;
  const sess=sessionId?plan.sessions.find(s=>s.session_id===sessionId):null;
  const currOpts=allCurr().map(e=>`<option value="${esc(e.title)}">${esc(e.code)} — ${esc(e.title)}</option>`).join('');
  const facOpts=(S.facs||[]).map(f=>`<option value="${esc(f.id)}">${esc(facDisplay(f))}</option>`).join('');
  const savedAssistantIds=new Set((sess&&Array.isArray(sess.assistant_facilitators)
    ?sess.assistant_facilitators.map(a=>a.user_id)
    :sess&&sess.assistant_facilitator_id?[sess.assistant_facilitator_id]:[]));
  const assistantOpts=(S.facs||[]).filter(f=>f.id!==(sess&&sess.facilitator_id))
    .map(f=>`<option value="${esc(f.id)}"${savedAssistantIds.has(f.id)?' selected':''}>${esc(facDisplay(f))}</option>`).join('')
    ||'<option disabled>— No other facilitators available —</option>';
  const roomOpts=S.rooms.map(r=>`<option value="${esc(r.name)}">${esc(r.name)}</option>`).join('');
  const phOpts=(S.phases||[]).map(p=>`<option value="${esc(p.name)}">${esc(PH_S[p.name]||p.displayName)}</option>`).join('');
  const stOpts=['planned','delivered','delivered_with_issue','cancelled','cancelled_late','rescheduled','not_delivered'].map(v=>`<option value="${v}" ${sess&&sess.status===v?'selected':''}>${{planned:'Planned',delivered:'Delivered',delivered_with_issue:'Delivered (issue)',cancelled:'Cancelled',cancelled_late:'Cancelled late',rescheduled:'Rescheduled',not_delivered:'Not Delivered'}[v]}</option>`).join('');
  const ip=(plan.timing.instructional_periods||[]).find(x=>x.period_number===period);
  const periodLabel=ip?(ip.block_label+(ip.start_time?` (${ip.start_time.slice(0,5)})`:'')):`Period ${period}`;
  let classLabel='';
  let derivedPhase=null;
  if(classId){
    const cl=plan.groups.flatMap(g=>g.classes||[]).find(c=>c.training_class_id===classId);
    if(cl){classLabel=cl.display_name; if(cl.stage_code)derivedPhase=sess?sess.phase_at_time||cl.stage_code:cl.stage_code;}
  } else if(customPhaseId){const cg=plan.groups.find(g=>g.custom_phase_id===customPhaseId);if(cg)classLabel=cg.name;}
  const cArg=classId?`'${esc(classId)}'`:'null';
  const cpArg=customPhaseId?`'${esc(customPhaseId)}'`:'null';
  const sessArg=sess?`'${esc(sess.session_id)}'`:'null';
  // Phase row is shown only when phase cannot be derived from the Training Class's stage_code.
  const phaseRow=derivedPhase
    ? `<input type="hidden" id="pce-ph" value="${esc(derivedPhase)}">`
    : `<div class="ff"><label for="pce-ph" style="font-size:var(--fs-xs)">Phase</label><select id="pce-ph" aria-label="Phase">${phOpts}</select></div>`;
  editorEl.innerHTML=`
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
      <div style="font-size:var(--fs-xs);font-weight:700;color:var(--dark)">${esc(periodLabel)} — ${esc(classLabel)}</div>
      <button class="btn btn-xs btn-out" onclick="document.getElementById('pn-cell-editor').style.display='none'">Dismiss</button>
    </div>
    <div class="form-row" style="margin-bottom:8px">
      ${phaseRow}
      <div class="ff"><label for="pce-st" style="font-size:var(--fs-xs)">Status</label><select id="pce-st" aria-label="Status">${stOpts}</select></div>
    </div>
    <div class="ff" style="margin-bottom:8px"><label for="pce-ex" style="font-size:var(--fs-xs)">Curriculum Item</label>
      <select id="pce-ex" aria-label="Curriculum item"><option value="">— Unassigned —</option>${currOpts}</select>
    </div>
    <div class="form-row" style="margin-bottom:8px">
      <div class="ff"><label for="pce-fa" style="font-size:var(--fs-xs)">Lead facilitator</label><select id="pce-fa" aria-label="Lead facilitator" onchange="_pnUpdateAssistantOptions()"><option value="">— None —</option>${facOpts}</select></div>
      <div class="ff"><label for="pce-rm" style="font-size:var(--fs-xs)">Room</label><select id="pce-rm" aria-label="Room"><option value="">— None —</option>${roomOpts}</select></div>
    </div>
    <div class="ff" style="margin-bottom:8px">
      <label for="pce-asst" style="font-size:var(--fs-xs)">Assistant facilitators (optional)</label>
      <select id="pce-asst" aria-describedby="pce-asst-help" multiple size="4">${assistantOpts}</select>
      <span id="pce-asst-help" class="muted" style="font-size:var(--fs-2xs)">Select one or more facilitators. The lead facilitator cannot also be an assistant.</span>
    </div>
    <div style="display:flex;gap:8px;align-items:center">
      <button class="btn btn-sm btn-dk" onclick="_pnCellSave('${esc(pnId)}','${esc(ds)}',${period},${cArg},${cpArg},${sessArg})">${sess?'Save Session':'Create Session'}</button>
      ${sess?`<button class="btn btn-sm btn-red-out" onclick="_pnCellDelete('${esc(sess.session_id)}','${esc(ds)}')">Delete</button>`:''}
      <span id="pce-err" style="font-size:var(--fs-xs);color:var(--red)"></span>
    </div>`;
    editorEl.style.display='';
    const phEl=document.getElementById('pce-ph');
    if(phEl&&phEl.tagName==='SELECT'){
      if(sess&&sess.phase_at_time&&![...phEl.options].some(o=>o.value===sess.phase_at_time)) phEl.appendChild(new Option(sess.phase_at_time+' (not in catalogue)',sess.phase_at_time));
      phEl.value=sess?sess.phase_at_time||'B. Initial':'B. Initial';
    }
    const exEl=document.getElementById('pce-ex');if(exEl)exEl.value=sess?sess.curriculum_title_at_time||sess.custom_title||'':'';
    const faEl=document.getElementById('pce-fa');if(faEl)faEl.value=sess?sess.facilitator_id||'':'';
    const rmEl=document.getElementById('pce-rm');if(rmEl)rmEl.value=sess?sess.training_area_name_at_time||'':'';
    editorEl.scrollIntoView({behavior:'smooth',block:'nearest'});
}

function _pnUpdateAssistantOptions(){
  const sel=document.getElementById('pce-asst');
  if(!sel)return;
  const leadId=document.getElementById('pce-fa')?.value||'';
  const selected=new Set(Array.from(sel.selectedOptions).map(o=>o.value).filter(id=>id&&id!==leadId));
  const eligible=(S.facs||[]).filter(f=>f.id!==leadId);
  sel.innerHTML=eligible.length
    ?eligible.map(f=>`<option value="${esc(f.id)}">${esc(facDisplay(f))}</option>`).join('')
    :'<option disabled>— No other facilitators available —</option>';
  Array.from(sel.options).forEach(option=>{option.selected=selected.has(option.value);});
}

// ── Cell save: create or update a session from the inline editor ──────────────
async function _pnCellSave(pnId,ds,period,classId,customPhaseId,sessionId){
  const errEl=document.getElementById('pce-err');
  const phase=document.getElementById('pce-ph')?.value||'B. Initial';
  const expTitle=document.getElementById('pce-ex')?.value||'';
  const facId=document.getElementById('pce-fa')?.value||null;
  const roomName=document.getElementById('pce-rm')?.value||'';
  const newSt=document.getElementById('pce-st')?.value||'planned';
  const assistantIds=Array.from(document.getElementById('pce-asst')?.selectedOptions||[])
    .map(option=>option.value).filter(id=>id&&id!==facId);
  // Collect outcome reason if the status transition requires one
  let reason=null;
  if(sessionId){
    const plan=window._pnPlan;
    const oldSess=plan?plan.sessions.find(s=>s.session_id===sessionId):null;
    if(oldSess&&newSt!==oldSess.status&&OUTCOME_REASON_REQUIRED[newSt]){
      reason=await collectOutcomeReason(newSt);
      if(reason===null)return;
    }
  }
  if(errEl){errEl.textContent='Saving…';errEl.style.color='var(--muted)';}
  try{
    let sessId=sessionId;
    if(!sessId){
      const r=await api('/api/sessions',{method:'POST',body:JSON.stringify({parade_night_id:pnId,period_number:period,cadet_group:'senior'})});
      sessId=r.session_id||r.id;
    }
    const statusOverrides={status:newSt,assistant_facilitator_ids:assistantIds};
    if(reason)statusOverrides.reason=reason;
    const _ips=(window._pnPlan&&window._pnPlan.timing&&window._pnPlan.timing.instructional_periods)||[];
    const _tbId=(_ips.find(ip=>ip.period_number===period)||{}).timing_block_id||null;
    const body=_sessBuildBody({__pnId:pnId,period_number:period,phase,exp:expTitle,facId,room:roomName,timingBlockId:_tbId},statusOverrides);
    await api('/api/sessions/'+sessId,{method:'PUT',body:JSON.stringify(body)});
    await api('/api/planning/sessions/'+sessId,{method:'PATCH',body:JSON.stringify({assistant_facilitator_ids:assistantIds})});
    if(classId) await _saveSessionAudience(sessId,[classId],false);
    else if(customPhaseId){
      try{await api('/api/planning/sessions/'+sessId+'/custom-phase-audiences',{method:'POST',body:JSON.stringify({custom_phase_id:customPhaseId})});}
      catch(e2){if(!(e2&&e2.code==='already_linked')) throw e2;}
    }
    if(errEl)errEl.textContent='';
    document.getElementById('pn-cell-editor').style.display='none';
    await reloadAndRender();
    showPNDetail(ds);
  }catch(e){if(errEl){errEl.textContent=apiErr(e);errEl.style.color='var(--red)';}}
}

// ── Cell delete: archive a session (reversible via Planning Workspace) ────────
function _pnCellDelete(sessionId,ds){
  confirmAction('Delete this session? It can be restored from the Planning Workspace.',async()=>{
    try{
      await api('/api/planning/sessions/'+sessionId,{method:'DELETE'});
      document.getElementById('pn-cell-editor').style.display='none';
      await reloadAndRender();
      showPNDetail(ds);
    }catch(e){showToast(apiErr(e),true);}
  },true);
}

// ── (Legacy stubs — kept so old call-sites remain safe) ───────────────────────
// showPNDetail now reads directly from the planner endpoint; the following
// helpers are no longer called from the new UI but remain for any external
// callers that may not yet have been updated.
function _pnDetailLegacyHtml(){}
// REM-34: Parade Night Notices. Kept deliberately simple (text + priority
// only, no audience picker) -- matches this card's minimal-footprint intent;
// audience targeting already exists in the API (NightNoticeIn.audience) for
// a future pass if actually requested, not invented speculatively here.
async function loadPNNotices(pnid){
  const list=document.getElementById('pn-notices-list');
  if(!list)return; // modal was closed before this resolved
  try{
    const notices=await api('/api/parade-nights/'+pnid+'/notices');
    if(!notices.length){
      list.innerHTML='<div class="muted" style="font-size:var(--fs-xs)">No notices.</div>';
      return;
    }
    list.innerHTML=notices.map(n=>`
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;padding:6px 0;border-bottom:1px solid var(--border-light)">
        <div style="font-size:var(--fs-sm);flex:1">
          ${n.priority==='urgent'?'<span class="badge b-red">Urgent</span> ':''}${esc(n.notice_text)}
        </div>
        ${canWriteSquadron()?`<button class="btn btn-xs btn-out no-print" onclick="archivePNNotice('${pnid}','${n.notice_id}')" aria-label="Remove notice">Remove</button>`:''}
      </div>`).join('');
  }catch(e){
    list.innerHTML=`<div class="muted" style="font-size:var(--fs-xs);color:var(--red)">Could not load notices: ${esc(apiErr(e))}</div>`;
  }
}
async function addPNNotice(pnid){
  const textEl=document.getElementById('pn-notice-text');
  const text=(textEl?.value||'').trim();
  if(!text)return;
  const priority=document.getElementById('pn-notice-priority')?.value||'normal';
  try{
    await api('/api/parade-nights/'+pnid+'/notices',{method:'POST',body:{notice_text:text,priority}});
    if(textEl)textEl.value='';
    loadPNNotices(pnid);
  }catch(e){
    showToast(apiErr(e),true);
  }
}
async function archivePNNotice(pnid,noticeId){
  try{
    await api('/api/planning/notices/'+noticeId+'/archive',{method:'POST'});
    loadPNNotices(pnid);
  }catch(e){
    showToast(apiErr(e),true);
  }
}
// "Mark all delivered, then flag exceptions" bulk action (risk-register
// data-entry UX ask): flag the few known exceptions individually first (via
// the per-session Status dropdown above), then bulk-clear everything else
// still Planned/Published in one action instead of clicking through each
// session's Save Changes flow one at a time.
async function doClosePN(pnId){
  confirmAction(
    'Close this Parade Night?\n\nAll sessions must already be in a final status (Delivered, Cancelled, Not Delivered, etc.). Once closed, the date, term, timing and type cannot be changed.',
    async()=>{
      try{
        await apiClosePN(pnId);
        showToast('Parade Night closed.',false);
        await reloadAndRender();
        // Re-open the modal to show the closed banner
        const pn=S.pns.find(p=>p.id===pnId);
        if(pn) showPNDetail(pn.date);
        else closeModal('m-pn-detail');
      }catch(e){
        const d=e?.body?.detail;
        if(d?.error==='close_blocked'&&d?.blockers?.length){
          showToast('Cannot close: '+d.blockers.join('; '),true);
        }else{
          showToast(apiErr(e),true);
        }
      }
    }
  );
}
function _qaApplyAll(n){
  const fac=document.getElementById('qa-fac')?.value||'';
  const room=document.getElementById('qa-room')?.value||'';
  if(!fac&&!room){showToast('Select a facilitator or room to assign.',true);return;}
  for(let i=0;i<n;i++){
    if(fac){const el=document.getElementById('d-fa-'+i);if(el)el.value=fac;}
    if(room){const el=document.getElementById('d-rm-'+i);if(el)el.value=room;}
  }
  const parts=[];
  if(fac)parts.push('facilitator');
  if(room)parts.push('room');
  showToast(`${parts.join(' and ')} set on all sessions — click Save Changes to commit.`);
}
function _qaClearFacs(){
  let n=0;
  while(document.getElementById('d-fa-'+n)){document.getElementById('d-fa-'+n).value='';n++;}
  if(n>0)showToast(`Facilitator cleared from ${n} session${n!==1?'s':''} — click Save Changes to commit.`);
}
async function doMarkRemainingDelivered(ds){
  const pn=S.pns.find(p=>p.date===ds);if(!pn)return;
  try{
    const r=await api('/api/parade-nights/'+pn.id+'/mark-remaining-delivered',{method:'POST'});
    showToast(r.sessions_updated>0?`${r.sessions_updated} session${r.sessions_updated!==1?'s':''} marked delivered.`:'No remaining sessions to mark — everything already has a status.',false);
    await reloadAndRender(); showPNDetail(ds);
  }catch(e){ showToast(apiErr(e),true); }
}
async function doCancelAllSessions(ds){
  const pn=S.pns.find(p=>p.date===ds);if(!pn)return;
  const reason=await collectOutcomeReason('cancelled');
  if(reason===null)return;
  try{
    const r=await api('/api/parade-nights/'+pn.id+'/cancel-all',{method:'POST',body:JSON.stringify({reason,notes:null})});
    showToast(r.sessions_updated>0?`${r.sessions_updated} session${r.sessions_updated!==1?'s':''} cancelled.`:'No sessions to cancel — all sessions already have a final status.');
    await reloadAndRender(); showPNDetail(ds);
  }catch(e){ showToast(apiErr(e),true); }
}
async function savePNCoreDetails(ds){
  const pn=S.pns.find(p=>p.date===ds);if(!pn)return;
  const errEl=document.getElementById('pn-det-err');
  const body={
    term:document.getElementById('pnd-term')?.value||'',
    parade_type:document.getElementById('pnd-type')?.value||'normal',
    start_time:document.getElementById('pnd-start')?.value||'',
    end_time:document.getElementById('pnd-end')?.value||'',
    notes:document.getElementById('pnd-notes')?.value||'',
    version:pn.version,
  };
  try{
    await api('/api/parade-nights/'+pn.id,{method:'PATCH',body:JSON.stringify(body)});
    await reloadAndRender(); showPNDetail(ds);
    if(errEl)errEl.textContent='';
  }catch(e){
    // version_conflict: someone else saved a change to this Parade Night while this form
    // was open. Reloading fresh data before re-showing the edit form would silently
    // discard whatever the current user just typed -- warn instead and let them decide
    // (re-open the (now-refreshed) form themselves, or retype/overwrite deliberately).
    if(e&&e.code==='version_conflict'){
      if(errEl){
        errEl.innerHTML='Someone else updated this Parade Night while you were editing it. Your changes were <b>not</b> saved. Close and reopen this Parade Night to see the latest version before trying again.';
        errEl.style.color='var(--red)';
      }else{
        showToast('Another user updated this Parade Night while you were editing. Your changes were not saved — reopen it to see the latest version.',true);
      }
    }else if(errEl){errEl.textContent=apiErr(e);errEl.style.color='var(--red)';}else showToast(apiErr(e),true);
  }
}

// CLASS-03: Training Class pickers in the Parade Night detail modal — same
// concept as _populateQuickEditClasses but covers every session in one pass.
// Fetches available classes once (uses _tcById cache if already populated by
// the Training Year page, else falls back to a live API call), then loads each
// session's current audience (one request per session) and renders checkboxes.
// Groups are hidden until classes exist so a squadron with no Training Classes
// sees no extra blank rows.
async function _populatePnDetailClasses(pn){
  let classes=Object.values(_tcById).filter(c=>!c.is_archived);
  if(!classes.length){
    try{ classes=await api('/api/training-classes'); }
    catch(_){ return; }
  }
  if(!classes.length) return; // no classes configured — leave pickers hidden
  // Sort by class_number then display_name (canonical order — sequence field renamed to class_number in v44).
  classes.sort((a,b)=>(a.class_number||a.sequence||0)-(b.class_number||b.sequence||0)||(a.display_name||'').localeCompare(b.display_name||''));
  const sessions=pn.sessions||[];
  await Promise.all(sessions.map(async(s,i)=>{
    // Guard: if user closed the modal before audience fetches resolved, bail.
    if(!document.getElementById('m-pn-detail').classList.contains('active')) return;
    const grp=document.getElementById('d-tc-grp-'+i);
    const list=document.getElementById('d-tc-'+i);
    if(!grp||!list)return;
    let checkedIds=new Set((s.trainingClasses||[]).map(c=>c.training_class_id||c.id));
    if(s.id){
      try{
        const audience=await api(`/api/sessions/${s.id}/audience`);
        checkedIds=new Set((audience||[]).map(a=>a.training_class_id));
      }catch(_){}
    }
    if(!document.getElementById('m-pn-detail').classList.contains('active')) return;
    list.innerHTML=classes.map(c=>`<label style="display:flex;align-items:center;gap:6px;padding:3px 0;font-weight:400">
      <input type="checkbox" class="pnd-tc-chk" data-sess="${i}" value="${esc(c.training_class_id)}" ${checkedIds.has(c.training_class_id)?'checked':''}>
      ${esc(c.display_name)}
    </label>`).join('');
    list.dataset.loaded='true';
    grp.style.display='';
  }));
}

let _pndOverrideAll=false;
async function savePNDetail(ds,cnt){
  const pn=S.pns.find(p=>p.date===ds);if(!pn)return;
  _pndOverrideAll=false;   // CONF-2: one decision per save, not per session
  const errEl=document.getElementById('pn-det-err');
  // Collect any required reasons up front, before writing anything — so a
  // cancelled reason panel never leaves an earlier session half-saved.
  const edits=[];
  for(let i=0;i<cnt;i++){
    const s=pn.sessions[i]; if(!s||!s.id)continue;
    const newSt=document.getElementById('d-st-'+i)?.value;
    let reason=null;
    if(newSt&&newSt!==s.status&&OUTCOME_REASON_REQUIRED[newSt]){
      reason=await collectOutcomeReason(newSt);
      if(reason===null){ if(errEl)errEl.textContent=''; return; } // user cancelled — nothing saved yet
    }
    edits.push({i,s,newSt,reason});
  }
  if(errEl){errEl.textContent='Saving…';errEl.style.color='var(--muted)';}
  try{
    for(const {i,s,newSt,reason} of edits){
      const expTitle=document.getElementById('d-ex-'+i)?.value||'';
      const facId=document.getElementById('d-fa-'+i)?.value||null;
      const roomName=document.getElementById('d-rm-'+i)?.value||'';
      const phase=document.getElementById('d-ph-'+i)?.value||s.phase||'B. Initial';
          // TB-1: send the program period. PUT replaces the session, so omitting
      // this cleared timing_block_id on every save -- latent until something
      // could set it.
      const tbEl=document.getElementById('d-tb-'+i);
      const body=_sessBuildBody({
        __pnId:pn.id, period_number:s.period_number||i+1,
        phase:phase, exp:expTitle, facId:facId, room:roomName,
        // this screen offers a period selector, so the DOM value wins over the
        // session's stored one
        timingBlockId: tbEl ? (tbEl.value||null) : (s.timingBlockId||null),
      }, (newSt&&newSt!==s.status) ? {status:newSt, reason:reason||null} : undefined);
      // Single atomic PUT: fields + status transition committed together server-side —
      // no partial-update window between a field save and a separate status save.
      //
      // CONF-2: a genuine double-booking used to end the save with an error and no
      // way forward, even though _sessMove() has offered "these clash — proceed
      // anyway?" for the move path all along. Ask once, then apply the same
      // decision to the rest of this save rather than prompting per session.
      if(_pndOverrideAll) body.override_conflict = true;
      try{
        await api('/api/sessions/'+s.id,{method:'PUT',body:JSON.stringify(body)});
      }catch(e){
        if(!(e && e.code==='resource_conflict')) throw e;
        const conflicts=(e.body&&e.body.detail&&e.body.detail.conflicts)||[];
        const proceed=await _showConflictPrompt(conflicts);
        if(!proceed){ if(errEl){errEl.textContent='Save stopped — nothing further was changed.';errEl.style.color='var(--red)';} return; }
        _pndOverrideAll = true;
        await api('/api/sessions/'+s.id,{method:'PUT',body:JSON.stringify(Object.assign({},body,{override_conflict:true}))});
      }
      // CLASS-03: save Training Class audience if the picker was loaded for this session.
      const tcList=document.getElementById('d-tc-'+i);
      if(tcList&&tcList.dataset.loaded==='true'){
        const checked=[...tcList.querySelectorAll('.pnd-tc-chk:checked')].map(c=>c.value);
        try{
          await _saveSessionAudience(s.id,checked,false);
        }catch(audienceErr){
          const detail=audienceErr&&audienceErr.body?.detail;
          if(detail&&detail.error==='class_conflict'&&Array.isArray(detail.conflicts)&&detail.conflicts.length){
            const names=detail.conflicts.map(c=>esc(c.training_class_name||c.training_class_id)).join(', ');
            if(errEl){
              errEl.innerHTML=`Session ${i+1}: scheduling conflict — ${names} `+
                `${detail.conflicts.length===1?'is':'are'} already in another session at this period. `+
                `<a href="#" style="font-weight:700;text-decoration:underline" `+
                `onclick="event.preventDefault();this.parentElement.textContent='Overriding…';`+
                `_saveSessionAudience('${esc(s.id)}',${JSON.stringify(checked)},true)`+
                `.then(()=>{reloadAndRender();closeModal('m-pn-detail');})`+
                `.catch(e2=>{this.parentElement.style.color='var(--red)';this.parentElement.textContent=apiErr(e2);})">Override</a>`;
              errEl.style.color='var(--warn)';
            }
            return;
          }
          throw audienceErr;
        }
      }
    }
    if(errEl)errEl.textContent='';
    await reloadAndRender(); closeModal('m-pn-detail');
  }catch(e){ if(errEl){errEl.textContent=apiErr(e);errEl.style.color='var(--red)';}else showToast(apiErr(e),true); }
}

// ── Accessible module scheduling (Phase 3.1): Move Up/Down + Move to a
// different Parade Night. Both funnel through _sessMove(), the same PUT +
// conflict-check path Phase 3.2's drag-and-drop will call too -- only the
// initiating gesture (click vs drag) differs, per the plan's explicit
// "accessible controls first, DnD is a progressive enhancement on the same
// path" design. ──
function _sessBuildBody(s,overrides){
  const ci=allCurr().find(c=>c.title===s.exp);
  const room=S.rooms.find(r=>r.name===s.room);
  return Object.assign({
    parade_night_id:s.__pnId, period_number:s.period_number,
    phase_at_time:s.phase||'B. Initial', curriculum_item_id:ci?ci.id:null,
    facilitator_id:s.facId||null, training_area_id:room?room.id:null,
    custom_title:s.exp&&!ci?s.exp:null,
    // TB-1: PUT replaces the whole session, and timing_block_id defaults to
    // null server-side. Omitting it here silently cleared a session's period
    // on every reorder or move.
    timing_block_id:s.timingBlockId||null,
  },overrides);
}

// Resolves true (move anyway) or false (cancelled) -- same Promise-based
// modal pattern as collectOutcomeReason().
let _scResolveFn=null;
function _showConflictPrompt(conflicts){
  return new Promise(resolve=>{
    _scResolveFn=resolve;
    const label=c=>c.type==='facilitator_clash'?'Facilitator':'Room';
    document.getElementById('sc-list').innerHTML=conflicts.map(c=>
      `<li>${label(c)} ${esc(c.resource_name||'')} is already booked in that period.</li>`).join('')
      ||'<li>Resource already booked in that period.</li>';
    openModal('m-sched-conflict');
  });
}
function _scResolve(v){ closeModal('m-sched-conflict'); if(_scResolveFn)_scResolveFn(v); _scResolveFn=null; }

// Attempts the move; on a 409 resource_conflict, prompts once and retries
// with override_conflict if the user confirms. Returns true on success
// (including a confirmed override), false if the user cancelled.
async function _sessMove(sessionId, body){
  try{
    await api('/api/sessions/'+sessionId,{method:'PUT',body:JSON.stringify(body)});
    return true;
  }catch(e){
    if(e&&e.code==='resource_conflict'){
      const conflicts=(e.body&&e.body.detail&&e.body.detail.conflicts)||[];
      const proceed=await _showConflictPrompt(conflicts);
      if(!proceed) return false;
      await api('/api/sessions/'+sessionId,{method:'PUT',body:JSON.stringify(Object.assign({},body,{override_conflict:true}))});
      return true;
    }
    throw e;
  }
}

async function _sessMoveUpDown(date,idx,dir){
  // Moves the session to the adjacent PERIOD (not a swap with whichever card
  // is visually next) -- a period can hold several parallel sessions (e.g.
  // one per cadet group/room), so "next card in the list" and "next period"
  // are not the same thing. The conflict check still catches a genuine
  // double-booking against whatever else is already in the target period.
  const pn=S.pns.find(p=>p.date===date); if(!pn)return;
  const s=(pn.sessions||[])[idx]; if(!s||!s.id)return;
  const newPeriod=(s.period_number||1)+(dir==='up'?-1:1);
  if(newPeriod<1)return;
  s.__pnId=pn.id;
  try{
    const ok=await _sessMove(s.id,_sessBuildBody(s,{period_number:newPeriod}));
    if(!ok)return; // user cancelled the conflict prompt — session unchanged
    await reloadAndRender();
    showPNDetail(date);
  }catch(e){ showToast(apiErr(e),true); }
}

async function _toggleSessHistory(sessId,idx){
  const el=document.getElementById('sess-hist-'+idx);
  if(!el)return;
  if(el.style.display!=='none'){ el.style.display='none'; return; }
  el.style.display='block'; el.textContent='Loading…';
  try{
    const rows=await api('/api/sessions/'+sessId+'/status-history');
    if(!rows.length){ el.textContent='No status changes recorded yet.'; return; }
    el.innerHTML=rows.map(r=>{
      const when=new Date(r.timestamp).toLocaleString('en-AU',{day:'2-digit',month:'short',year:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false});
      const change=r.old_status?`${r.old_status} → ${r.new_status}`:`Set to ${r.new_status}`;
      return `<div style="padding:3px 0;border-bottom:1px solid var(--border-light)"><b>${esc(change)}</b> · ${esc(when)}${r.reason?' · '+esc(r.reason):''}</div>`;
    }).join('');
  }catch(e){ el.textContent=apiErr(e); }
}
function _sessOpenMoveTo(date,idx){
  const pn=S.pns.find(p=>p.date===date); if(!pn)return;
  const s=(pn.sessions||[])[idx]; if(!s||!s.id)return;
  _sessMoveToRef={date,idx};
  const sel=document.getElementById('smt-pn');
  const others=[...S.pns].filter(p=>p.date!==date).sort((x,y)=>x.date.localeCompare(y.date));
  sel.innerHTML=others.map(p=>`<option value="${p.date}">${fmtDL(p.date)} (${esc(p.term)})</option>`).join('');
  document.getElementById('smt-period').value=s.period_number||idx+1;
  document.getElementById('smt-err').textContent='';
  openModal('m-sess-move-to');
}
function _sessMoveToCancel(){ closeModal('m-sess-move-to'); _sessMoveToRef=null; }
let _sessMoveToRef=null;
async function _sessMoveToConfirm(){
  if(!_sessMoveToRef)return;
  const {date,idx}=_sessMoveToRef;
  const pn=S.pns.find(p=>p.date===date); if(!pn)return;
  const s=(pn.sessions||[])[idx]; if(!s||!s.id)return;
  const targetDate=document.getElementById('smt-pn').value;
  const targetPn=S.pns.find(p=>p.date===targetDate);
  const period=parseInt(document.getElementById('smt-period').value,10)||1;
  const errEl=document.getElementById('smt-err');
  if(!targetPn){ errEl.textContent='Select a Parade Night to move to.'; return; }
  s.__pnId=targetPn.id;
  errEl.textContent='';
  try{
    const ok=await _sessMove(s.id,_sessBuildBody(s,{parade_night_id:targetPn.id,period_number:period}));
    if(!ok)return; // user cancelled the conflict prompt — session unchanged
    closeModal('m-sess-move-to'); _sessMoveToRef=null;
    await reloadAndRender();
    showToast('Session moved to '+fmtDL(targetDate)+'.');
  }catch(e){ errEl.textContent=apiErr(e); }
}

// ── Drag-and-drop (Phase 3.2): a progressive enhancement over the Move
// Up/Down/To controls above, never the only way to reorder -- it calls the
// identical _sessMove()/_sessBuildBody() path, dropping a card onto another
// simply means "take that card's period". The drag handle is aria-hidden
// since the accessible buttons already cover this same action for keyboard
// and screen-reader users. ──
let _dragSessionRef=null;
function _sessDragStart(e,date,idx){
  const pn=S.pns.find(p=>p.date===date); const s=pn&&(pn.sessions||[])[idx];
  if(!s||!s.id){ e.preventDefault(); return; }
  _dragSessionRef={date,idx};
  e.dataTransfer.effectAllowed='move';
  try{ e.dataTransfer.setData('text/plain', s.id); }catch(_){}
}
function _sessDragEnd(){
  _dragSessionRef=null;
  document.querySelectorAll('.dnd-valid,.dnd-invalid').forEach(el=>el.classList.remove('dnd-valid','dnd-invalid'));
}
// Client-side prediction only (mirrors the server's same-period/same-resource
// check) so the drop outline is instant; the server call after drop is still
// the real authority and will show the same conflict prompt Move Up/Down uses
// if this prediction and the live server state ever disagree.
function _sessWouldConflict(date,fromIdx,toIdx){
  const pn=S.pns.find(p=>p.date===date); if(!pn)return false;
  const sessions=pn.sessions||[];
  const from=sessions[fromIdx], to=sessions[toIdx];
  if(!from||!to||fromIdx===toIdx)return false;
  const targetPeriod=to.period_number||1;
  return sessions.some((sib,i)=>i!==fromIdx&&(sib.period_number||1)===targetPeriod&&
    ((from.facId&&sib.facId===from.facId)||(from.room&&sib.room===from.room)));
}
function _sessDragOver(e,date,idx){
  if(!_dragSessionRef||_dragSessionRef.date!==date)return;
  e.preventDefault();
  e.dataTransfer.dropEffect='move';
  const card=e.currentTarget;
  card.classList.remove('dnd-valid','dnd-invalid');
  card.classList.add(_sessWouldConflict(date,_dragSessionRef.idx,idx)?'dnd-invalid':'dnd-valid');
}
function _sessDragLeave(e){ e.currentTarget.classList.remove('dnd-valid','dnd-invalid'); }
async function _sessDrop(e,date,idx){
  e.preventDefault();
  e.currentTarget.classList.remove('dnd-valid','dnd-invalid');
  if(!_dragSessionRef||_dragSessionRef.date!==date){ _dragSessionRef=null; return; }
  const fromIdx=_dragSessionRef.idx; _dragSessionRef=null;
  if(fromIdx===idx)return;
  const pn=S.pns.find(p=>p.date===date); if(!pn)return;
  const from=(pn.sessions||[])[fromIdx], to=(pn.sessions||[])[idx];
  if(!from||!to||!from.id)return;
  from.__pnId=pn.id;
  try{
    const ok=await _sessMove(from.id,_sessBuildBody(from,{period_number:to.period_number||1}));
    if(!ok)return;
    await reloadAndRender();
    showPNDetail(date);
  }catch(err){ showToast(apiErr(err),true); }
}

// QUICK EDIT
async function quickEdit(date,idx){
  editSessRef={date,idx};
  const pn=S.pns.find(p=>p.date===date);if(!pn)return;
  const s=pn.sessions[idx];
  const currOpts=allCurr().map(e=>`<option value="${esc(e.title)}" ${e.title===s.exp?'selected':''}>${esc(e.code)} — ${esc(e.title)}</option>`).join('');
  const facOpts=S.facs.map(f=>`<option value="${f.id}" ${f.id===s.facId?'selected':''}>${facDisplay(f)}</option>`).join('');
  const roomOpts=S.rooms.map(r=>`<option value="${esc(r.name)}" ${r.name===s.room?'selected':''}>${esc(r.name)}</option>`).join('');
  const stOpts=['planned','delivered','delivered_with_issue','cancelled','cancelled_late','rescheduled','not_delivered'].map(v=>`<option value="${v}" ${v===s.status?'selected':''}>${{planned:'Planned',delivered:'Delivered',delivered_with_issue:'Delivered (issue)',cancelled:'Cancelled',cancelled_late:'Cancelled late',rescheduled:'Rescheduled',not_delivered:'Not Delivered'}[v]}</option>`).join('');
  const asstFacIds=new Set((s.assistant_facilitators||[]).map(a=>a.user_id));
  const asstFacHtml=S.facs.length<2?'':S.facs.map(f=>`<label style="display:flex;align-items:center;gap:6px;padding:3px 0;font-size:var(--fs-sm)">
      <input type="checkbox" class="qe-asst-chk" value="${esc(f.id)}" ${asstFacIds.has(f.id)?'checked':''}>
      ${esc(facDisplay(f))}</label>`).join('');
  document.getElementById('sess-edit-body').innerHTML=`
    <div class="ff"><label for="qe-st">Status</label><select id="qe-st" aria-label="Session status">${stOpts}</select></div>
    <div class="ff"><label for="qe-ex">Curriculum Item</label><select id="qe-ex"><option value="">— Unassigned —</option>${currOpts}</select></div>
    <div class="ff"><label for="qe-fa">Facilitator</label><div id="fac-sugg-panel" style="display:none"></div><select id="qe-fa"><option value="">— None —</option>${facOpts}</select></div>
    <div class="ff"><label for="qe-rm">Room</label><select id="qe-rm"><option value="">— None —</option>${roomOpts}</select></div>
    ${asstFacHtml?`<div class="ff" id="qe-asst-group">
      <label>Assistant Facilitators</label>
      <div id="qe-asst-list" style="max-height:120px;overflow-y:auto;border:1px solid var(--border);border-radius:6px;padding:8px">${asstFacHtml}</div>
    </div>`:''}
    <div class="ff" id="qe-classes-group" style="display:none">
      <label>Training Classes</label>
      <p class="muted" style="font-size:var(--fs-xs);margin:0 0 6px">
        Select the Training Class or classes for this Session. Leave all unchecked if Training Classes are not yet set up for this Squadron.
      </p>
      <div id="qe-classes-list" style="max-height:140px;overflow-y:auto;border:1px solid var(--border);border-radius:6px;padding:8px"></div>
    </div>`;
  openModal('m-sess-edit');
  // Awaited (not fire-and-forget) so a rapid re-open of this same modal --
  // e.g. Save, then immediately re-open the same session -- can never have
  // an earlier, still-in-flight populate call resolve after a later one and
  // clobber it with stale data.
  await _populateQuickEditClasses(s.id);
  // FAC-SUG-01: load suggestions non-blocking after modal is visible
  _loadFacSuggestions(s.id, pn.date, s.period_number);
}

// ── Session <-> Training Class audience (CLASS-03) ───────────────────────────
// A Session can target one or more Training Classes (addendum's combined-Session
// example: Senior 1 + Senior 2 doing the same Drill session together). Wired
// into the real, live "Quick Edit" flow (quickEdit()/saveSessEdit()/#m-sess-edit).
//
// Deliberately NOT scoped to "the active Training Year": a Squadron can have
// more than one active PlanningYear at once (no auto-deactivation on create),
// so guessing which one is "the" active year for a given Session would be
// unreliable. /api/training-classes without training_year_id already returns
// every active class for the caller's squadron across all years, which is
// what a Session-assignment picker actually needs.
async function _populateQuickEditClasses(sessionId){
  const group=document.getElementById('qe-classes-group');
  const list=document.getElementById('qe-classes-list');
  if(!group||!list) return;
  let classes=[];
  try{ classes=await api('/api/training-classes'); }
  catch(_){ group.style.display='none'; return; }
  if(!classes.length){ group.style.display='none'; return; }

  let checkedIds=new Set();
  if(sessionId){
    try{
      const audience=await api(`/api/sessions/${sessionId}/audience`);
      checkedIds=new Set((audience||[]).map(a=>a.training_class_id));
    }catch(_){ /* no existing audience -- leave unchecked */ }
  }

  // quickEdit() may have already been superseded by a later call (double-click,
  // or the user closed the modal before this async fetch resolved) -- editSessRef
  // is cleared by saveSessEdit()/closeModal-adjacent flows, so bail rather than
  // populate a checklist for a session the modal is no longer showing.
  if(!document.getElementById('m-sess-edit').classList.contains('active')) return;

  group.style.display='';
  list.innerHTML=classes.map(c=>`<label style="display:flex;align-items:center;gap:6px;padding:3px 0;font-size:var(--fs-sm)">
      <input type="checkbox" class="qe-class-chk" value="${esc(c.training_class_id)}" ${checkedIds.has(c.training_class_id)?'checked':''}>
      ${esc(c.display_name)}
    </label>`).join('');
}

async function _saveSessionAudience(sessionId, classIds, override){
  await api(`/api/sessions/${sessionId}/audience`,{
    method:'PUT',
    body:JSON.stringify({training_class_ids:classIds, override_conflict:!!override})
  });
}

async function saveSessEdit(){
  if(!editSessRef)return;
  const pn=S.pns.find(p=>p.date===editSessRef.date);if(!pn)return;
  const s=pn.sessions[editSessRef.idx];
  if(!s||!s.id){showToast('Could not save — this session no longer exists. Refresh the page and try again.',true);return;}
  const newSt=document.getElementById('qe-st').value;
  const expTitle=document.getElementById('qe-ex').value;
  const facId=document.getElementById('qe-fa').value||null;
  const roomName=document.getElementById('qe-rm').value;
  const sessErrEl=document.getElementById('sess-edit-err');
  // Collect the reason (if this transition needs one) BEFORE saving anything, so
  // cancelling the reason panel leaves the session completely untouched rather than
  // saving the field edits while silently dropping the status change.
  let reason=null;
  if(newSt!==s.status&&OUTCOME_REASON_REQUIRED[newSt]){
    reason=await collectOutcomeReason(newSt);
    if(reason===null)return;
  }
  if(sessErrEl){sessErrEl.textContent='Saving…';sessErrEl.style.color='var(--muted)';}
  try{
    // Built by _sessBuildBody() rather than by hand. This copy omitted
    // timing_block_id, and PUT replaces the whole session, so every quick edit
    // silently cleared the session's program period and dropped it out of the
    // printed Weekly Program. Two other copies of this object carried a comment
    // warning about exactly that; writing the warning twice did not stop the
    // third copy getting it wrong, which is why there is now only one.
    const asstChecked=[...document.querySelectorAll('.qe-asst-chk:checked')].map(c=>c.value);
    const body=_sessBuildBody({
      __pnId:pn.id, period_number:s.period_number||editSessRef.idx+1,
      phase:s.phase, exp:expTitle, facId:facId, room:roomName,
      timingBlockId:s.timingBlockId,
    }, Object.assign(
      (newSt!==s.status) ? {status:newSt, reason:reason||null} : {},
      // §10: always send assistant_facilitator_ids so clearing all is honoured
      {assistant_facilitator_ids:asstChecked}
    ));
    // Single atomic PUT — see savePNDetail()'s comment for why this replaced the
    // previous separate PUT-then-POST(/status) two-call sequence.
    await api('/api/sessions/'+s.id,{method:'PUT',body:JSON.stringify(body)});
    // Training Class audience (CLASS-03) -- save whatever is checked, even an
    // empty set (clearing all classes is a valid, deliberate choice). Only
    // when the group is visible: hidden means no classes exist for this
    // Squadron, so there is nothing meaningful to save.
    const classesGroup=document.getElementById('qe-classes-group');
    if(classesGroup && classesGroup.style.display!=='none'){
      const checked=[...document.querySelectorAll('.qe-class-chk:checked')].map(c=>c.value);
      try{
        await _saveSessionAudience(s.id,checked,false);
      }catch(audienceErr){
        const detail=audienceErr&&audienceErr.body?.detail;
        if(detail&&detail.error==='class_conflict'&&Array.isArray(detail.conflicts)&&detail.conflicts.length){
          const names=detail.conflicts.map(c=>esc(c.training_class_name||c.training_class_id)).join(', ');
          if(sessErrEl){
            sessErrEl.innerHTML=`Scheduling conflict: ${names} `+
              `${detail.conflicts.length===1?'is':'are'} already scheduled in another session at this period. `+
              `<a href="#" style="font-weight:700;text-decoration:underline" `+
              `onclick="event.preventDefault();this.parentElement.textContent='Overriding…';`+
              `_saveSessionAudience('${esc(s.id)}',${JSON.stringify(checked)},true)`+
              `.then(()=>{reloadAndRender();closeModal('m-sess-edit');editSessRef=null;})`+
              `.catch(e2=>{this.parentElement.style.color='var(--red)';this.parentElement.textContent=apiErr(e2);})">Override</a>`;
            sessErrEl.style.color='var(--warn)';
          }
          return;
        }
        throw audienceErr;
      }
    }
    if(sessErrEl)sessErrEl.textContent='';
    await reloadAndRender(); showToast('Session saved.'); closeModal('m-sess-edit'); editSessRef=null;
  }catch(e){
    if(sessErrEl){sessErrEl.textContent=apiErr(e);sessErrEl.style.color='var(--red)';}else showToast(apiErr(e),true);
  }
}
