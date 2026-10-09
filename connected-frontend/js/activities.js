// Main TMS module: Activities -- NATHQ/Wing/Squadron inheritance-aware tab, the
// squadron activities page, the CEA activity import modal, auto-generation and
// local overrides.
// Extracted verbatim from connected-frontend/index.html (stabilisation Phase 4,
// C6). Top-level function declarations and side-effect-free let/const only;
// loaded as a classic script BEFORE the inline bootstrap, so everything here
// is defined before any page-load code runs. Statements with load-time
// effects stay in index.html in their original order. Parity is proven by
// tools/architecture/frontend_parity.mjs.

// ═══════════════════════════════════════════════════════════
//  NATHQ / WING / SQUADRON ACTIVITIES (Phase 2 — inheritance-aware tab)
//  Reused across three hosts: the Squadron Activities page's "Inherited
//  Activities" card (act-tab-squadron), the new Wing Activities page
//  (act-tab-wing) and National Activities page (act-tab-national) — one
//  component, three mount points, matching the backend's own generic
//  scope_type design rather than three separate implementations.
// ═══════════════════════════════════════════════════════════
const _ACT_SOURCE_LABEL={national:'NATHQ',wing:'Wing',squadron:'Squadron',cea:'CEA',holiday:'Holiday'};
const _ACT_SOURCE_CLASS={national:'b-purple',wing:'b-blue',squadron:'b-ok',cea:'b-amber',holiday:'b-grey'};
let _actTabState={}; // containerId -> {scopeType, scopeId, items, view}
let _actEditId=null, _actEditContainerId=null;

function _actSourceBadge(item){
  const cls=_ACT_SOURCE_CLASS[item.source]||'b-grey';
  const lbl=_ACT_SOURCE_LABEL[item.source]||item.source||'—';
  return `<span class="badge ${cls}">${esc(lbl)}</span>`;
}

// `year` is optional and is passed ONLY by the squadron mount on the Activities
// page, which sits under the year bar. The Wing and National pages mount this
// same component and have no year bar, so they must keep seeing everything --
// narrowing them silently would be a capability regression, not a fix.
async function _actTabLoad(containerId, scopeType, scopeId, year){
  if(!scopeId){
    if(scopeType==='wing') scopeId=(S.role==='system_admin')?saBrowseWingId():(S.session&&S.session.wing_id);
    if(scopeType==='squadron') scopeId=S.currentSqnId||(S.session&&S.session.squadron_id);
  }
  const host=document.getElementById(containerId); if(!host)return;
  const prior=_actTabState[containerId]||{};
  const view=prior.view||'list';
  if(scopeType!=='national' && !scopeId){
    host.innerHTML=`<div class="card"><div class="muted">No ${esc(scopeType)} in scope.</div></div>`;
    return;
  }
  host.innerHTML='<div class="card"><div class="muted">Loading activities…</div></div>';
  let url=`/api/activities?scope_type=${scopeType}&view=${view}`;
  if(scopeId) url+='&scope_id='+encodeURIComponent(scopeId);
  // Without this the card shows the same rows whatever year is selected: pick
  // 2027 and last year's holidays stay on screen under the new year's heading.
  if(year) url+=`&date_from=${year}-01-01&date_end=${year}-12-31`;
  let d;
  try{ d=await api(url); }
  catch(e){ host.innerHTML=`<div class="card"><div class="sc-status-err">Could not load activities: ${esc(apiErr(e))}</div></div>`; return; }
  _actTabState[containerId]={scopeType, scopeId, year, items:d.items||[], view, truncated:d.truncated};
  _actTabRender(containerId);
}

function _actTabFilters(containerId, items){
  const typeEl=document.getElementById(containerId+'-f-type');
  const srcEl=document.getElementById(containerId+'-f-src');
  const qEl=document.getElementById(containerId+'-search');
  const typeF=typeEl?typeEl.value:'all';
  const srcF=srcEl?srcEl.value:'all';
  const q=(qEl?qEl.value:'').toLowerCase().trim();
  return items.filter(i=>{
    if(typeF!=='all' && i.activity_type!==typeF) return false;
    if(srcF!=='all' && i.source!==srcF) return false;
    if(q && !((i.activity_name||'').toLowerCase().includes(q) || (i.notes||'').toLowerCase().includes(q) || (i.location||'').toLowerCase().includes(q))) return false;
    return true;
  });
}

function _actTabRender(containerId){
  const st=_actTabState[containerId]; if(!st)return;
  const host=document.getElementById(containerId); if(!host)return;
  const filtered=_actTabFilters(containerId, st.items).sort((a,b)=>(a.date_start||'').localeCompare(b.date_start||''));
  const canManage=(st.scopeType==='national' && ['national_admin','system_admin'].includes(S.role))
    || (st.scopeType==='wing' && ['wing_admin','national_admin','system_admin'].includes(S.role))
    || (st.scopeType==='squadron' && false); // squadron-local creation already handled by the existing "+ Add Activity" button
  const createBtn=canManage?`<button class="btn btn-dk btn-sm no-print" onclick="_actOpenCreate('${containerId}')">+ New ${st.scopeType==='national'?'National':'Wing'} Activity</button>`:'';
  const viewBtns=['list','upcoming','historical','archived'].map(v=>
    `<button class="btn btn-xs ${st.view===v?'btn-dk':'btn-out'} no-print" onclick="_actSetView('${containerId}','${v}')">${v[0].toUpperCase()+v.slice(1)}</button>`).join(' ');

  let html=`<div class="card">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;flex-wrap:wrap">
      <h2 class="ctitle" style="margin-bottom:0">${st.scopeType==='squadron'?'Inherited Activities':'Activities'}</h2>
      ${createBtn}
    </div>
    <div class="fbar no-print" style="margin:10px 0">
      <select id="${containerId}-f-type" aria-label="Filter activities by type" onchange="_actTabRender('${containerId}')">
        <option value="all">All types</option>
        ${[...new Set(st.items.map(i=>i.activity_type).filter(Boolean))].map(t=>`<option value="${esc(t)}">${esc(t)}</option>`).join('')}
      </select>
      <select id="${containerId}-f-src" aria-label="Filter activities by source" onchange="_actTabRender('${containerId}')">
        <option value="all">All sources</option>
        ${[...new Set(st.items.map(i=>i.source))].map(s=>`<option value="${esc(s)}">${esc(_ACT_SOURCE_LABEL[s]||s)}</option>`).join('')}
      </select>
      <input id="${containerId}-search" placeholder="Search…" oninput="_actTabRender('${containerId}')" style="min-width:160px" aria-label="Search">
      <span style="margin-left:auto">${viewBtns}</span>
    </div>`;

  if(!filtered.length){
    html+=`<div class="muted" style="padding:14px;text-align:center">No activities${st.view!=='list'?' ('+st.view+')':''} found.</div>`;
  } else {
    html+=`<div class="tw"><table><thead><tr><th>Source</th><th>Activity</th><th>Date</th><th>Type</th><th>Location</th><th class="no-print"></th></tr></thead><tbody>`;
    filtered.forEach(i=>{
      html+=`<tr class="drow" onclick="_actShowDetail('${containerId}','${i.activity_id}')">
        <td>${_actSourceBadge(i)}</td>
        <td style="font-weight:700">${esc(i.activity_name)}${i.is_archived?' <span class="badge b-grey">Archived</span>':''}</td>
        <td style="white-space:nowrap">${fmtD(i.date_start)}${i.date_end&&i.date_end!==i.date_start?' – '+fmtD(i.date_end):''}</td>
        <td style="font-size:var(--fs-xs)">${esc(i.activity_type||'—')}</td>
        <td style="font-size:var(--fs-xs)"><span title="CEA event venue — not a training room">${esc(i.location||'—')}</span></td>
        <td class="no-print">${i.read_only?'<span class="muted" title="Owned by another scope — view only">🔒</span>':
          (st.view==='archived'?`<button class="btn btn-xs btn-ok" onclick="event.stopPropagation();_actRestore('${containerId}','${i.activity_id}')">Restore</button>`:'')}</td>
      </tr>`;
    });
    html+='</tbody></table></div>';
  }
  if(st.truncated) html+=`<div class="muted" style="font-size:var(--fs-2xs);margin-top:6px">Showing the first results — narrow your filters to see more.</div>`;
  html+=`</div><div id="${containerId}-detail"></div>`;
  host.innerHTML=html;
}

function _actSetView(containerId, view){
  _actTabState[containerId].view=view;
  const st=_actTabState[containerId];
  _actTabLoad(containerId, st.scopeType, st.scopeId, st.year);
}

function _actShowDetail(containerId, activityId){
  const st=_actTabState[containerId]; if(!st)return;
  const item=st.items.find(i=>i.activity_id===activityId); if(!item)return;
  const panel=document.getElementById(containerId+'-detail'); if(!panel)return;
  if(item.read_only){
    const ownerLabel=item.owning_org_label||_ACT_SOURCE_LABEL[item.source]||item.source;
    panel.innerHTML=`<div class="drill-panel show">
      <div class="drill-hdr"><div class="drill-title">${esc(item.activity_name)}</div><button class="modal-x" aria-label="Close" onclick="document.getElementById('${containerId}-detail').innerHTML=''">×</button></div>
      <div style="font-size:var(--fs-sm);color:var(--muted);margin-bottom:8px">Owned by ${esc(ownerLabel)} — read-only here. ${item.source==='squadron'||item.source==='wing'||item.source==='national'?'Edit it at the owning scope.':''}</div>
      <div class="sc-kv"><dt>Date</dt><dd>${fmtD(item.date_start)}${item.date_end&&item.date_end!==item.date_start?' – '+fmtD(item.date_end):''}</dd>
      <dt>Type</dt><dd>${esc(item.activity_type||'—')}</dd>
      <dt>Location</dt><dd>${esc(item.location||'—')}</dd>
      <dt>Notes</dt><dd>${esc(item.notes||'—')}</dd></div>
    </div>`;
    panel.scrollIntoView({behavior:'smooth',block:'nearest'});
    return;
  }
  _actEditId=item.activity_id; _actEditContainerId=containerId;
  panel.innerHTML=`<div class="drill-panel show">
    <div class="drill-hdr"><div class="drill-title">Edit — ${esc(item.activity_name)}</div><button class="modal-x" aria-label="Close" onclick="document.getElementById('${containerId}-detail').innerHTML=''">×</button></div>
    <div class="form-row">
      <div class="ff"><label for="${containerId}-e-name">Name</label><input id="${containerId}-e-name" value="${esc(item.activity_name)}"></div>
      <div class="ff"><label for="${containerId}-e-type">Type</label><input id="${containerId}-e-type" value="${esc(item.activity_type||'')}"></div>
    </div>
    <div class="form-row">
      <div class="ff"><label for="${containerId}-e-start">Start date</label><input type="date" id="${containerId}-e-start" value="${esc(item.date_start||'')}"></div>
      <div class="ff"><label for="${containerId}-e-end">End date</label><input type="date" id="${containerId}-e-end" value="${esc(item.date_end||'')}"></div>
    </div>
    <div class="ff"><label for="${containerId}-e-loc">Location</label><input id="${containerId}-e-loc" value="${esc(item.location||'')}"></div>
    <div class="ff"><label for="${containerId}-e-notes">Notes</label><textarea id="${containerId}-e-notes" rows="2">${esc(item.notes||'')}</textarea></div>
    <div style="display:flex;gap:8px;align-items:center;margin-top:8px">
      <button class="btn btn-dk btn-sm" onclick="_actSaveEdit()">Save</button>
      <button class="btn btn-out btn-sm" onclick="_actArchive('${containerId}','${item.activity_id}')">Archive</button>
      <span id="${containerId}-e-msg" style="font-size:var(--fs-xs);font-weight:700"></span>
    </div>
  </div>`;
  panel.scrollIntoView({behavior:'smooth',block:'nearest'});
}

async function _actSaveEdit(){
  const c=_actEditContainerId, id=_actEditId;
  const msg=document.getElementById(c+'-e-msg');
  const body={
    activity_name:document.getElementById(c+'-e-name').value.trim(),
    activity_type:document.getElementById(c+'-e-type').value.trim()||null,
    date_start:document.getElementById(c+'-e-start').value||null,
    date_end:document.getElementById(c+'-e-end').value||null,
    location:document.getElementById(c+'-e-loc').value.trim()||null,
    notes:document.getElementById(c+'-e-notes').value.trim()||null,
  };
  try{
    await api('/api/activities/'+id,{method:'PATCH',body});
    if(msg)msg.textContent='Saved.';
    showToast('Activity saved.', false);
    const st=_actTabState[c];
    await _actTabLoad(c, st.scopeType, st.scopeId, st.year);
  }catch(e){ if(msg){msg.textContent=apiErr(e);msg.style.color='var(--red)';} else showToast(apiErr(e),true); }
}

async function _actArchive(containerId, activityId){
  confirmAction('Archive this activity? It disappears from active views but is preserved in history, and can be restored later.',async()=>{
    try{
      await api('/api/activities/'+activityId,{method:'DELETE'});
      showToast('Activity archived.', false);
      const st=_actTabState[containerId];
      await _actTabLoad(containerId, st.scopeType, st.scopeId, st.year);
    }catch(e){ showToast(apiErr(e),true); }
  });
}

async function _actRestore(containerId, activityId){
  confirmAction('Restore this activity? It will become active and visible again.',async()=>{
    try{
      await api('/api/activities/'+activityId+'/restore',{method:'POST'});
      showToast('Activity restored.', false);
      const st=_actTabState[containerId];
      await _actTabLoad(containerId, st.scopeType, st.scopeId, st.year);
    }catch(e){ showToast('Could not restore: '+apiErr(e), true); }
  });
}

function _actOpenCreate(containerId){
  const st=_actTabState[containerId]; if(!st)return;
  const panel=document.getElementById(containerId+'-detail'); if(!panel)return;
  panel.innerHTML=`<div class="drill-panel show">
    <div class="drill-hdr"><div class="drill-title">New ${st.scopeType==='national'?'National':'Wing'} Activity</div><button class="modal-x" aria-label="Close" onclick="document.getElementById('${containerId}-detail').innerHTML=''">×</button></div>
    <div class="form-row">
      <div class="ff"><label for="${containerId}-c-name">Name *</label><input id="${containerId}-c-name"></div>
      <div class="ff"><label for="${containerId}-c-type">Type</label><input id="${containerId}-c-type" placeholder="e.g. Camp, Ceremonial"></div>
    </div>
    <div class="form-row">
      <div class="ff"><label for="${containerId}-c-start">Start date *</label><input type="date" id="${containerId}-c-start"></div>
      <div class="ff"><label for="${containerId}-c-end">End date</label><input type="date" id="${containerId}-c-end"></div>
    </div>
    <div class="ff"><label for="${containerId}-c-loc">Location</label><input id="${containerId}-c-loc"></div>
    <div class="ff"><label for="${containerId}-c-notes">Notes</label><textarea id="${containerId}-c-notes" rows="2"></textarea></div>
    <div style="display:flex;gap:8px;align-items:center;margin-top:8px">
      <button class="btn btn-dk btn-sm" onclick="_actSaveCreate('${containerId}')">Create</button>
      <span id="${containerId}-c-msg" style="font-size:var(--fs-xs);font-weight:700;color:var(--red)"></span>
    </div>
    <div style="font-size:var(--fs-xs);color:var(--muted);margin-top:8px">This will immediately appear in every subordinate ${st.scopeType==='national'?'Wing and Squadron':'Squadron'}'s Activities list — no republish step needed.</div>
  </div>`;
  panel.scrollIntoView({behavior:'smooth',block:'nearest'});
}

async function _actSaveCreate(containerId){
  const st=_actTabState[containerId];
  const msg=document.getElementById(containerId+'-c-msg');
  const name=document.getElementById(containerId+'-c-name').value.trim();
  const start=document.getElementById(containerId+'-c-start').value;
  if(!name||!start){ if(msg)msg.textContent='Name and start date are required.'; return; }
  const body={
    activity_name:name,
    activity_type:document.getElementById(containerId+'-c-type').value.trim()||null,
    date_start:start,
    date_end:document.getElementById(containerId+'-c-end').value||null,
    location:document.getElementById(containerId+'-c-loc').value.trim()||null,
    notes:document.getElementById(containerId+'-c-notes').value.trim()||null,
  };
  const path=st.scopeType==='national'?'/api/activities/national':'/api/activities/wing';
  if(st.scopeType==='wing') body.wing_id=st.scopeId;
  try{
    await api(path,{method:'POST',body});
    showToast((st.scopeType==='national'?'National':'Wing')+' activity created.', false);
    await _actTabLoad(containerId, st.scopeType, st.scopeId, st.year);
  }catch(e){ if(msg){msg.textContent=apiErr(e);} else showToast(apiErr(e),true); }
}

// ═══════════════════════════════════════════════════════════
//  SQUADRON ACTIVITIES (existing local-only page)
// ═══════════════════════════════════════════════════════════
let _activitiesPageLoaded=false;
async function _loadActivitiesPage(){
  renderActs();
  _actTabLoad('act-tab-squadron','squadron',null,P.currentYearInt||null);
  // Ensure year nav is initialised — fetch years if not yet loaded,
  // otherwise just refresh the display (avoids a redundant API call).
  if (!P.years || !P.years.length) {
    await _loadPlanningYears();
  } else {
    ynInit();
  }
  if (P.currentYearId) {
    const _actYr = (P.years||[]).find(y=>y.planning_year_id===P.currentYearId)||{};
    const _actWid = _actYr.wing_id||(S.session&&S.session.wing_id)||'';
    _renderHolidays(P.currentYearId);
    _tcLoadForYear(P.currentYearId);
    loadMissions(P.currentYearId);
  } else {
    // The year is selected but has no row. Every year-scoped panel must clear:
    // leaving 2026's holidays or training classes under the heading 2027 is
    // worse than showing nothing, because it is quietly wrong.
    _renderHolidays(null);
    _tcLoadForYear(null);
    loadMissions(null);
    // Wing HQ events are keyed by the year NUMBER, not a planning-year row, so
    // they are still meaningful for a year nobody has configured.
    const _wid = (S.session && S.session.wing_id) || '';
  }
}

function openCeaImportModal(){
  if(!P.currentYearId){ showToast('Select a training year first.',true); return; }
  const lbl=document.getElementById('ceaImportYearLabel');
  if(lbl) lbl.textContent=esc(String(P.currentYearInt||'—'));
  _ceaRows=[]; _ceaExisting=[]; _ceaKeepIds=new Set();
  document.getElementById('ceaStep1').style.display='';
  document.getElementById('ceaStep2').style.display='none';
  document.getElementById('ceaStep3').style.display='none';
  document.getElementById('ceaUploadErr').textContent='';
  const fi=document.getElementById('ceaFileInput');
  if(fi) fi.value='';
  const btn=document.getElementById('ceaPreviewBtn');
  if(btn){ btn.disabled=true; btn.textContent='Preview import'; }
  openModal('m-cea-import');
}

function _parseCSV(str){
  const lines=str.split(/\r?\n/).filter(function(l){return l.trim();});
  if(!lines.length) return [];
  function splitLine(line){
    const vals=[]; let cur=''; let inQ=false;
    for(let i=0;i<line.length;i++){
      const ch=line[i];
      if(ch==='"'&&line[i+1]==='"'){cur+='"';i++;}
      else if(ch==='"'){inQ=!inQ;}
      else if(ch===','&&!inQ){vals.push(cur.trim());cur='';}
      else{cur+=ch;}
    }
    vals.push(cur.trim());
    return vals;
  }
  const headers=splitLine(lines[0]).map(function(h){return h.replace(/^"|"$/g,'');});
  return lines.slice(1).map(function(line){
    const vals=splitLine(line);
    const obj={};
    headers.forEach(function(h,i){obj[h]=(vals[i]||'').replace(/^"|"$/g,'');});
    return obj;
  });
}

function _ceaGetField(row,aliases){
  for(const k of aliases){ if(row[k]!==undefined&&row[k]!=='') return row[k]; }
  return '';
}

async function ceaPreview(){
  const fi=document.getElementById('ceaFileInput');
  if(!fi||!fi.files||!fi.files.length) return;
  const errEl=document.getElementById('ceaUploadErr');
  errEl.textContent='';
  const btn=document.getElementById('ceaPreviewBtn');
  btn.disabled=true; btn.textContent='Reading…';

  let text;
  try{
    text=await new Promise(function(resolve,reject){
      const r=new FileReader();
      r.onload=function(ev){resolve(ev.target.result);};
      r.onerror=function(){reject(new Error('Could not read file'));};
      r.readAsText(fi.files[0],'UTF-8');
    });
  } catch(e){
    errEl.textContent='Could not read file.';
    btn.disabled=false; btn.textContent='Preview import';
    return;
  }

  try{ _ceaRows=_parseCSV(text); }
  catch(e){ errEl.textContent='Parse error: '+apiErr(e); btn.disabled=false; btn.textContent='Preview import'; return; }

  if(!_ceaRows.length){ errEl.textContent='No rows found in file.'; btn.disabled=false; btn.textContent='Preview import'; return; }

  try{
    if(_ynNeedsSetup('import CEA activities')){ btn.disabled=false; btn.textContent='Preview import'; return; }
    const existing=await api('/api/planning/years/'+P.currentYearId+'/cea/activities');
    _ceaExisting=existing||[];
  } catch(e){ _ceaExisting=[]; }

  const ID_ALIASES=['ActivityID','cea_activity_id','ActivityId','SeqNr','CEA_ID'];
  const NAME_ALIASES=['ActivityName','activity_name','Name'];

  const existingById={};
  _ceaExisting.forEach(function(r){ if(r.cea_activity_id) existingById[r.cea_activity_id]=r; });

  _ceaKeepIds=new Set();

  const categorised=_ceaRows.map(function(row,i){
    const ceaId=_ceaGetField(row,ID_ALIASES);
    const name=_ceaGetField(row,NAME_ALIASES);
    const isUpdate=ceaId&&existingById[ceaId];
    return {row,ceaId,name,isUpdate:!!isUpdate,idx:i};
  });

  const newCount=categorised.filter(function(c){return !c.isUpdate;}).length;
  const updCount=categorised.filter(function(c){return c.isUpdate;}).length;

  let html='';
  if(newCount) html+='<p style="font-size:var(--fs-sm);color:var(--ok,#1a7f4b);font-weight:700;margin-bottom:6px">'+newCount+' new activities will be added</p>';
  if(updCount) html+='<p style="font-size:var(--fs-sm);color:var(--royal);font-weight:700;margin-bottom:6px">'+updCount+' existing activities — click to keep original</p>';

  html+='<div style="overflow-x:auto;max-height:300px;overflow-y:auto;border:1px solid var(--border);border-radius:6px">'
    +'<table class="yn-mgmt-table"><thead><tr><th>CEA ID</th><th>Name</th><th>CEA Location<br><small style="color:var(--muted,#5c6a76);font-weight:400">event venue — not a training room</small></th><th>Action</th></tr></thead><tbody>';

  categorised.forEach(function(c){
    const rowCls=c.isUpdate?'cea-row-update':'cea-row-new';
    const decision=c.isUpdate
      ?'<button class="cea-conflict-toggle replace" data-ceaid="'+esc(c.ceaId)+'" onclick="ceaToggleKeep(this)">Replace</button>'
      :'<span style="color:var(--ok,#1a7f4b);font-size:var(--fs-xs);font-weight:700">New</span>';
    const loc=_ceaGetField(c.row,['Location','location','Venue','venue','City','city']);
    html+='<tr class="'+rowCls+'">'
      +'<td style="font-size:var(--fs-xs);color:var(--muted)">'+esc(c.ceaId)+'</td>'
      +'<td style="font-weight:600">'+esc(c.name)+'</td>'
      +'<td style="font-size:var(--fs-xs);color:var(--muted)">'+esc(loc||'—')+'</td>'
      +'<td>'+decision+'</td>'
      +'</tr>';
  });

  html+='</tbody></table></div>';
  document.getElementById('ceaPreviewBody').innerHTML=html;
  document.getElementById('ceaImportCount').textContent=_ceaRows.length;
  document.getElementById('ceaStep1').style.display='none';
  document.getElementById('ceaStep2').style.display='';
  btn.disabled=false; btn.textContent='Preview import';
}

function ceaToggleKeep(btn){
  const ceaId=btn.getAttribute('data-ceaid');
  if(_ceaKeepIds.has(ceaId)){
    _ceaKeepIds.delete(ceaId);
    btn.textContent='Replace';
    btn.className='cea-conflict-toggle replace';
  } else {
    _ceaKeepIds.add(ceaId);
    btn.textContent='Keep existing';
    btn.className='cea-conflict-toggle keep';
  }
}

function ceaBackToUpload(){
  document.getElementById('ceaStep2').style.display='none';
  document.getElementById('ceaStep1').style.display='';
}

async function ceaConfirm(){
  const fi=document.getElementById('ceaFileInput');
  if(!fi||!fi.files||!fi.files.length){ showToast('No file selected.',true); return; }
  const btn=document.getElementById('ceaImportBtn');
  if(btn){ btn.disabled=true; btn.innerHTML='Importing…'; }
  const formData=new FormData();
  formData.append('file',fi.files[0]);
  if(_ceaKeepIds.size) formData.append('keep_existing',Array.from(_ceaKeepIds).join(','));
  try{
    const tok=sessionStorage.getItem('aafc_token')||'';
    if(_ynNeedsSetup('import CEA activities')){ if(btn){btn.disabled=false;btn.innerHTML='Import';} return; }
    const resp=await fetch(API_BASE+'/api/planning/years/'+P.currentYearId+'/cea/import',{
      method:'POST',
      headers:tok?{Authorization:'Bearer '+tok}:{},
      credentials:'include',
      body:formData,
    });
    if(!resp.ok){
      const err=await resp.json().catch(function(){return {};});
      throw new Error((err.detail&&typeof err.detail==='string'?err.detail:'Import failed ('+resp.status+')'));
    }
    const result=await resp.json();
    const created=result.created||0, updated=result.updated||0, skipped=result.skipped||result.kept||0;
    document.getElementById('ceaResultBody').innerHTML=
      '<div style="font-size:var(--fs-md);font-weight:700;color:var(--ok,#1a7f4b);margin-bottom:8px">Import complete</div>'
      +'<p style="font-size:var(--fs-base)">'+created+' added &nbsp;·&nbsp; '+updated+' updated &nbsp;·&nbsp; '+skipped+' kept existing</p>';
    document.getElementById('ceaStep2').style.display='none';
    document.getElementById('ceaStep3').style.display='';
  } catch(e){
    if(btn){ btn.disabled=false; btn.innerHTML='Import all (<span id="ceaImportCount">'+_ceaRows.length+'</span>)'; }
    const errEl=document.getElementById('ceaPreviewBody');
    errEl.insertAdjacentHTML('afterbegin','<div style="color:#c01530;font-size:var(--fs-sm);font-weight:700;margin-bottom:8px">Import failed: '+esc(apiErr(e))+'</div>');
  }
}

function renderActs(){
  const td=today();
  const typeFilter=(document.getElementById('act-f-type')||{}).value||'all';
  const search=((document.getElementById('act-search')||{}).value||'').toLowerCase().trim();
  let list=[...S.acts].sort((a,b)=>a.date.localeCompare(b.date));
  if(typeFilter!=='all')list=list.filter(a=>a.type===typeFilter);
  if(search)list=list.filter(a=>(a.name||'').toLowerCase().includes(search)||(a.notes||'').toLowerCase().includes(search));
  document.getElementById('act-tbody').innerHTML=list.length?list.map((act)=>{
    const past=new Date(act.date+'T00:00:00')<td;
    const tb=act.type==='Must Attend'?'<span class="badge b-red">Must Attend</span>':act.type==='Key Event'?'<span class="badge b-blue">Key Event</span>':act.type==='Holiday'?'<span class="badge b-amber">Holiday</span>':'<span class="badge b-grey">Optional</span>';
    // REM-103: an inherited (Wing/National-owned) row may carry this
    // squadron's own local override -- shown alongside the unchanged source
    // values, never replacing them, matching "display source vs local value
    // side-by-side" from the addendum this row implements.
    const ov=act.localOverride;
    const ovBadge=ov?(ov.is_hidden?' <span class="badge b-grey" title="Marked not relevant to our squadron">Hidden locally</span>':' <span class="badge b-blue" title="Locally adjusted for our squadron">Adjusted</span>'):'';
    const effDate=(ov&&ov.local_date_start)||act.date;
    const dateCell=fmtD(effDate,{day:'numeric',month:'short',year:'numeric'})
      +(ov&&ov.local_date_start?` <span style="color:var(--muted);font-size:var(--fs-2xs)" title="Source date: ${esc(fmtD(act.date,{day:'numeric',month:'short',year:'numeric'}))}">(adjusted)</span>`:'');
    let actionsCell;
    if(act.isInherited){
      actionsCell=canWriteSquadron()
        ?`<button class="btn btn-xs btn-out" onclick="openActivityOverrideModal('${act.id}')">${ov?'Edit Adjustment':'Adjust'}</button>`
        :(ov?'<span style="font-size:var(--fs-2xs);color:var(--muted)">Locally adjusted</span>':'—');
    } else {
      actionsCell=canWriteSquadron()?`<button class="btn btn-xs btn-sky" onclick="editAct('${act.id}')">Edit</button> <button class="btn btn-xs btn-red" aria-label="Delete activity" onclick="delAct('${act.id}')">×</button>`:'—';
    }
    return `<tr ${past?'style="opacity:.58"':''}>
      <td style="font-weight:700">${esc(act.name)}${ovBadge}</td>
      <td style="white-space:nowrap">${dateCell}</td>
      <td>${tb}</td>
      <td style="font-size:var(--fs-xs)">${esc((act.audience||[]).join(', '))}</td>
      <td style="font-size:var(--fs-xs);color:var(--muted)">${esc((ov&&ov.local_notes)||act.notes||'')}</td>
      <td class="no-print">${actionsCell}</td>
    </tr>`;
  }).join(''):`<tr><td colspan="6" style="color:var(--muted);text-align:center;padding:14px">No activities${typeFilter!=='all'?' of this type':''}${search?' matching "'+esc(search)+'"':''}.</td></tr>`;
}
// ── Activity Auto-Generation ──────────────────────────────────────────────
function openGenerateActivitiesModal(){
  ['ga-name','ga-location','ga-notes','ga-excl'].forEach(id=>{const e=document.getElementById(id);if(e)e.value='';});
  document.getElementById('ga-start').value='';
  document.getElementById('ga-end').value='';
  document.getElementById('ga-time-start').value='';
  document.getElementById('ga-time-end').value='';
  document.getElementById('ga-recur').value='weekly';
  document.getElementById('ga-weekday').value='1';
  document.getElementById('ga-count').value='';
  document.getElementById('ga-type').value='Optional';
  document.getElementById('ga-preview-area').style.display='none';
  document.getElementById('ga-create-btn').style.display='none';
  document.getElementById('ga-msg').textContent='';
  _gaRecurChange();
  openModal('m-gen-acts');
}
function _gaRecurChange(){
  const r=document.getElementById('ga-recur').value;
  const wd=document.getElementById('ga-weekday-row');
  if(wd)wd.style.display=['weekly','fortnightly'].includes(r)?'':'none';
}
function _gaBody(previewOnly){
  const excl=(document.getElementById('ga-excl').value||'').split(',').map(s=>s.trim()).filter(Boolean);
  const count=parseInt(document.getElementById('ga-count').value)||null;
  const wd=document.getElementById('ga-weekday').value;
  const recur=document.getElementById('ga-recur').value;
  return {
    activity_name:document.getElementById('ga-name').value.trim(),
    activity_type:document.getElementById('ga-type').value,
    start_date:document.getElementById('ga-start').value,
    end_date:document.getElementById('ga-end').value,
    time_start:document.getElementById('ga-time-start').value||null,
    time_end:document.getElementById('ga-time-end').value||null,
    recurrence:recur,
    weekday:['weekly','fortnightly'].includes(recur)?parseInt(wd):null,
    excluded_dates:excl,
    repeat_count:count,
    location:document.getElementById('ga-location').value||null,
    notes:document.getElementById('ga-notes').value||null,
    planning_year_id:P&&P.currentYearId?P.currentYearId:null,
    preview_only:previewOnly,
  };
}
async function previewGenerateActivities(){
  const msg=document.getElementById('ga-msg');
  const body=_gaBody(true);
  if(!body.activity_name){msg.textContent='Activity name is required.';return;}
  if(!body.start_date||!body.end_date){msg.textContent='Start and end dates are required.';return;}
  if(body.start_date>body.end_date){msg.textContent='End date must be on or after start date.';return;}
  msg.textContent='Generating preview…';
  try{
    const r=await api('/api/activities/generate',{method:'POST',body});
    const pa=document.getElementById('ga-preview-area');
    const pb=document.getElementById('ga-preview-body');
    const ps=document.getElementById('ga-preview-summary');
    const cb=document.getElementById('ga-create-btn');
    ps.textContent=`${r.would_create} to create, ${r.would_skip} to skip`;
    pb.innerHTML=r.preview.map(row=>{
      const statusCls=row.status==='include'?'b-ok':'b-grey';
      const reasonTxt=row.reason==='duplicate'?`⚠ Duplicate (${row.existing_activity_id?'ID:'+row.existing_activity_id.slice(0,8):'exists'})`
                      :row.reason==='holiday'?`⚠ Holiday: ${esc(row.holiday_name||'')}`
                      :row.reason==='excluded'?'Excluded date':'';
      return `<tr style="${row.status==='skip'?'opacity:0.55':''}">
        <td>${esc(row.date)}</td>
        <td>${esc(row.start_time||'—')}</td>
        <td>${esc(row.finish_time||'—')}</td>
        <td><span class="badge ${statusCls}">${row.status==='include'?'Include':'Skip'}</span></td>
        <td style="font-size:var(--fs-2xs);color:var(--muted)">${reasonTxt}</td>
      </tr>`;
    }).join('');
    pa.style.display='';
    cb.style.display=r.would_create>0?'inline-flex':'none';
    msg.textContent='';
  }catch(e){msg.textContent='Preview failed: '+apiErr(e);}
}
async function commitGenerateActivities(){
  const msg=document.getElementById('ga-msg');
  const body=_gaBody(false);
  msg.textContent='Creating activities…';
  document.getElementById('ga-create-btn').disabled=true;
  try{
    const r=await api('/api/activities/generate',{method:'POST',body});
    closeModal('m-gen-acts');
    await reloadAndRender();
    showToast(`Done. ${r.created_count} activities created, ${r.skipped_count} skipped.`);
  }catch(e){
    msg.textContent='Creation failed: '+apiErr(e);
    document.getElementById('ga-create-btn').disabled=false;
  }
}

let _editActId=null;
async function saveAct(){
  const name=document.getElementById('act-name').value.trim();
  const date=document.getElementById('act-date').value;
  if(!name||!date){showToast('Name and date required.',true);return;}
  const aud=[];
  ['ori','ini','jun','int','sen'].forEach(k=>{if(document.getElementById('aa-'+k).checked)aud.push({ori:'Orientation',ini:'Initial',jun:'Junior',int:'Intermediate',sen:'Senior'}[k]);});
  const payload={activity_name:name,date_start:date,activity_type:document.getElementById('act-type').value,audience:aud,notes:document.getElementById('act-notes').value||null};
  try{
    if(_editActId){ await api('/api/activities/'+_editActId,{method:'PATCH',body:JSON.stringify(payload)}); _editActId=null; }
    else { await api('/api/activities',{method:'POST',body:JSON.stringify(payload)}); }
    await reloadAndRender(); closeModal('m-add-act');
    document.getElementById('m-add-act-title')&&(document.getElementById('m-add-act-title').textContent='+ Add Activity');
  }catch(e){ showToast(apiErr(e),true); }
}
// Opening "+ Add Activity" must clear any state left by a previous editAct().
// _editActId was only ever cleared on a successful save, so Edit -> close ->
// "+ Add Activity" -> Save silently PATCHED the activity you had opened
// earlier instead of creating a new one, with the form still showing its
// values. Mirrors the reset the "+ Add Facilitator" button already does inline.
function openAddActModal(){
  _editActId=null;
  const t=document.getElementById('m-add-act-title'); if(t)t.textContent='+ Add Activity';
  document.getElementById('act-name').value='';
  document.getElementById('act-date').value='';
  document.getElementById('act-type').value='Optional';
  document.getElementById('act-notes').value='';
  ['ori','ini','jun','int','sen'].forEach(k=>{const el=document.getElementById('aa-'+k);if(el)el.checked=false;});
  openModal('m-add-act');
}
function editAct(id){
  const act=S.acts.find(a=>a.id===id); if(!act)return;
  _editActId=id;
  if(document.getElementById('m-add-act-title'))document.getElementById('m-add-act-title').textContent='Edit Activity';
  document.getElementById('act-name').value=act.name||'';
  document.getElementById('act-date').value=act.date||'';
  document.getElementById('act-type').value=act.type||'Optional';
  document.getElementById('act-notes').value=act.notes||'';
  const audMap={Orientation:'ori',Initial:'ini',Junior:'jun',Intermediate:'int',Senior:'sen'};
  ['ori','ini','jun','int','sen'].forEach(k=>{const el=document.getElementById('aa-'+k);if(el)el.checked=(act.audience||[]).some(a=>audMap[a]===k);});
  openModal('m-add-act');
}
async function delAct(id){
  confirmAction('Remove this activity? It will no longer appear in active views, but the record is preserved.',async()=>{
    try{ await api('/api/activities/'+id,{method:'DELETE'}); await reloadAndRender(); }
    catch(e){ showToast(apiErr(e),true); }
  });
}

// REM-103: squadron-local date/time/notes/relevance adjustment to an
// inherited (Wing/National-owned) Activity -- the source record itself is
// never touched, only PUT/DELETE /api/activities/{id}/local-override.
let _actOverrideId=null;
function openActivityOverrideModal(id){
  const act=S.acts.find(a=>a.id===id); if(!act)return;
  _actOverrideId=id;
  const ov=act.localOverride;
  document.getElementById('act-override-title').textContent=(ov?'Edit':'Adjust')+' for our squadron — '+act.name;
  document.getElementById('act-override-source').textContent='Source (from '+(act.owningOrgLabel||act.owningLevel||'the owning unit')+'): '
    +fmtD(act.date,{day:'numeric',month:'short',year:'numeric'})+(act.timeStart?' at '+act.timeStart:'')
    +(act.notes?' — "'+act.notes+'"':'');
  document.getElementById('act-ov-date-start').value=(ov&&ov.local_date_start)||'';
  document.getElementById('act-ov-date-end').value=(ov&&ov.local_date_end)||'';
  document.getElementById('act-ov-time-start').value=(ov&&ov.local_time_start)||'';
  document.getElementById('act-ov-time-end').value=(ov&&ov.local_time_end)||'';
  document.getElementById('act-ov-notes').value=(ov&&ov.local_notes)||'';
  document.getElementById('act-ov-hidden').checked=!!(ov&&ov.is_hidden);
  document.getElementById('act-override-clear-btn').style.display=ov?'':'none';
  document.getElementById('act-override-msg').style.display='none';
  openModal('m-act-override');
}
async function saveActivityLocalOverride(){
  const act=S.acts.find(a=>a.id===_actOverrideId); if(!act)return;
  const msg=document.getElementById('act-override-msg');
  msg.style.display='none';
  const body={
    local_date_start:document.getElementById('act-ov-date-start').value||null,
    local_date_end:document.getElementById('act-ov-date-end').value||null,
    local_time_start:document.getElementById('act-ov-time-start').value||null,
    local_time_end:document.getElementById('act-ov-time-end').value||null,
    local_notes:document.getElementById('act-ov-notes').value.trim()||null,
    is_hidden:document.getElementById('act-ov-hidden').checked,
  };
  if(act.localOverride)body.version=act.localOverride.version;
  try{
    await api('/api/activities/'+_actOverrideId+'/local-override',{method:'PUT',body});
    closeModal('m-act-override');
    await reloadAndRender();
    showToast('Local adjustment saved.');
  }catch(e){ msg.textContent=apiErr(e); msg.style.display=''; }
}
async function clearActivityLocalOverride(){
  confirmAction('Remove this local adjustment and revert to the source activity\'s own date/time/notes?',async()=>{
    closeModal('m-act-override'); // Optimistic close: decouple dismiss from API latency/failure.
    try{
      await api('/api/activities/'+_actOverrideId+'/local-override',{method:'DELETE'});
      const _clearedAct=S.acts.find(a=>a.id===_actOverrideId);
      if(_clearedAct) _clearedAct.localOverride=null;
      renderActs();
      showToast('Local adjustment cleared.');
      reloadAndRender(); // background refresh for all other data, no await
    }catch(e){ showToast(apiErr(e),true); }
  });
}
