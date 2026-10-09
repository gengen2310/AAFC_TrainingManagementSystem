// Main TMS module: Facilitators -- list, archive/restore, tags, profile and
// leave, CSV import, save-state, duplicate disambiguation and merge.
// Extracted verbatim from connected-frontend/index.html (stabilisation Phase 4,
// C6). Top-level function declarations and side-effect-free let/const only;
// loaded as a classic script BEFORE the inline bootstrap, so everything here
// is defined before any page-load code runs. Statements with load-time
// effects stay in index.html in their original order. Parity is proven by
// tools/architecture/frontend_parity.mjs.

// ═══════════════════════════════════════════════════════════
//  FACILITATORS
// ═══════════════════════════════════════════════════════════
function _populateFacFilter(){
  const sel=document.getElementById('fac-filter'); if(!sel)return;
  const cur=sel.value;
  sel.innerHTML='<option value="">All subject areas</option>';
  SUBJECTS.forEach(s=>{const o=document.createElement('option');o.value=s.key;o.textContent=s.label;sel.appendChild(o);});
  const customTags=(S.subjectAreaTags||[]).filter(t=>!SUBJECTS.some(s=>s.label.toLowerCase()===t.display_name.toLowerCase()));
  if(customTags.length){
    const grp=document.createElement('optgroup');grp.label='Unit Tags';
    customTags.forEach(t=>{const o=document.createElement('option');o.value='tag:'+t.tag_id;o.textContent=t.display_name;grp.appendChild(o);});
    sel.appendChild(grp);
  }
  if(cur)sel.value=cur;
}
// REM-133: archive existed with no way to see or restore an archived
// facilitator -- follows the same "show archived" lazy-fetch pattern
// already used for Flights (_flightsToggleShowArchived/doRestoreFlight).
let _archivedFacList=null;
async function _facsToggleShowArchived(){
  const checked=(document.getElementById('fac-show-archived')||{}).checked;
  if(!checked){ renderFacs(); return; }
  try{
    // Same field mapping loadData() uses to build S.facs (id/rank/first/last/
    // type/areas) -- the raw API response uses facilitator_id/current_rank/
    // first_name/last_name/subject_areas, which renderFacs() does not read.
    _archivedFacList=(await api('/api/facilitators?include_archived=true')).filter(f=>f.is_archived).map(_mapArchivedFac);
  }catch(e){ showToast('Could not load archived facilitators: '+apiErr(e), true); }
  renderFacs();
}
function _mapArchivedFac(f){
  return {id:f.facilitator_id,rank:f.current_rank||'',first:f.first_name||'',last:f.last_name||'',type:f.type||'',areas:(f.subject_areas||[])};
}
async function doRestoreFacilitator(id, name){
  try{
    await api(`/api/facilitators/${id}/restore`,{method:'POST'});
    showToast(`'${name}' restored.`);
    await loadData();
    _archivedFacList=(await api('/api/facilitators?include_archived=true')).filter(f=>f.is_archived).map(_mapArchivedFac);
    renderFacs();
    loadFacilitatorStats();
  }catch(e){ showToast('Could not restore: '+apiErr(e), true); }
}
function renderFacs(){
  _populateFacFilter();
  const counts={};
  allSess().forEach(s=>{const k=s.facId||s.facName;if(!k)return;counts[k]=(counts[k]||0)+1;});
  const showArchived=(document.getElementById('fac-show-archived')||{}).checked;
  const source=showArchived?(_archivedFacList||[]):S.facs;
  const flt=S.facFilter||'';
  let list;
  if(!flt||showArchived){list=source;}
  else if(flt.startsWith('tag:')){
    const tagId=flt.slice(4);
    const tagName=(S.subjectAreaTags||[]).find(t=>t.tag_id===tagId);
    const matchName=tagName?tagName.display_name.toLowerCase():'';
    list=source.filter(f=>(f.areas||[]).some(a=>a.toLowerCase()===matchName));
  } else {
    list=source.filter(f=>(f.areas||[]).some(a=>subjectOf(a)===flt));
  }
  const q=(document.getElementById('fac-search')||{value:''}).value.trim().toLowerCase();
  if(q) list=list.filter(f=>(f.first||'').toLowerCase().includes(q)||(f.last||'').toLowerCase().includes(q)||(f.rank||'').toLowerCase().includes(q));
  document.getElementById('fac-tbody').innerHTML=list.length?list.map((f,i)=>{
    const k=f.id;const tot=counts[k]||0;
    const nameFor=`${f.first||''} ${f.last||''}`.trim()||'this facilitator';
    const rowAttrs=showArchived?' style="opacity:.6"':'';
    const clickAttr=showArchived?'':` onclick="showFacProfile('${f.id}')"`;
    return `<tr class="${showArchived?'':'clk-row'}"${rowAttrs}${clickAttr}>
      <td style="color:var(--muted);font-size:var(--fs-xs)">${i+1}</td>
      <td style="font-weight:700">${esc(f.rank||'—')}${showArchived?' <span class="badge b-grey">Archived</span>':''}</td>
      <td>${esc(f.first||'—')}</td>
      <td style="font-weight:700">${esc(f.last||'—')}</td>
      <td><span class="badge b-grey">${esc({Officer:'Officer',NCO:'WO/NCO','Senior Cadet':'Sr Cadet',Civilian:'Civilian',Staff:'Staff'}[f.type]||f.type||'—')}</span></td>
      <td>${(f.areas||[]).map(a=>elBadge(a)).join(' ')||'<span style="color:var(--muted);font-size:var(--fs-xs)">untagged</span>'}</td>
      <td style="text-align:center">${showArchived?'—':`<button class="btn-lnk" onclick="event.stopPropagation();showFacProfile('${f.id}')">${tot}</button>`}</td>
      <td class="no-print" onclick="event.stopPropagation()">
        ${showArchived
          ?(canWriteSquadron()?`<button class="btn btn-xs btn-ok" onclick="doRestoreFacilitator('${f.id}','${_jsAttr(nameFor)}')">Restore</button>`:'')
          :(canWriteSquadron()?`<button class="btn btn-xs btn-sky" onclick="tagFac('${f.id}')">Tags</button> <button class="btn btn-xs btn-sky" onclick="editFac('${f.id}')">Edit</button> <button class="btn btn-xs btn-out" onclick="openMergeFac('${f.id}')">Merge</button> <button class="btn btn-xs btn-red" aria-label="Archive facilitator" onclick="delFac('${f.id}')">×</button>`:'')}
      </td>
    </tr>`;
  }).join(''):`<tr><td colspan="8" style="color:var(--muted);text-align:center;padding:14px">No ${showArchived?'archived ':''}facilitators${(!showArchived&&flt)?' tagged in this subject area':''}${q?' match your search':''}.</td></tr>`;
}
// Backend-backed subject-area tagging (PATCH /api/facilitators/{id}; audited server-side).
const FAC_TAG_VOCAB=['Service Knowledge','Drill and Ceremonial','Field Skills','PDL','Community Engagement','Air & Space','Aviation','Space','Cyber','RPAS'];
let _tagFacId=null;
function tagFac(id){
  const f=S.facs.find(x=>x.id===id); if(!f)return;
  _tagFacId=id;
  const cur=(f.areas||[]);
  const name=[f.rank,f.first,f.last].filter(Boolean).join(' ');
  document.getElementById('m-tag-title').textContent='Subject Areas — '+name;
  document.getElementById('m-tag-msg').textContent='';
  // Build toggle chips: standard vocab + user-created API tags
  const apiTagNames=(S.subjectAreaTags||[]).map(t=>t.display_name);
  const allVocab=[...new Set([...FAC_TAG_VOCAB,...apiTagNames])];
  const el=document.getElementById('m-tag-checks');
  el.innerHTML=allVocab.map(v=>{
    const on=cur.includes(v);
    const isApiTag=apiTagNames.includes(v)&&!FAC_TAG_VOCAB.includes(v);
    return `<button type="button" onclick="toggleTagVocab(this,'${_jsAttr(v)}',${on?'false':'true'})"
      style="padding:4px 12px;border-radius:20px;font-size:var(--fs-xs);font-weight:700;cursor:pointer;
             border:1.5px solid var(--royal);background:${on?'var(--royal)':'white'};color:${on?'white':'var(--royal)'}${isApiTag?';border-style:dashed':''}"
      data-active="${on}" title="${isApiTag?'Unit-created tag':''}">${esc(v)}</button>`;
  }).join('');
  // Custom tags (not in any vocab) go in the text field
  const custom=cur.filter(t=>!allVocab.includes(t));
  document.getElementById('m-tag-custom').value=custom.join(', ');
  // Show tag creation section for sqn_admin
  const createSection=document.getElementById('m-tag-create-section');
  const createBtn=document.getElementById('m-tag-create-btn');
  if(createSection)createSection.style.display=canWriteSquadron()?'block':'none';
  if(createBtn)createBtn.style.display=canWriteSquadron()?'inline-flex':'none';
  openModal('m-tag-fac');
}
async function createAndAddTag(){
  const input=document.getElementById('m-tag-new-name'); if(!input)return;
  const name=input.value.trim(); if(!name)return;
  const msg=document.getElementById('m-tag-msg');
  msg.textContent='Creating…';
  try{
    const t=await api('/api/subject-area-tags',{method:'POST',body:JSON.stringify({display_name:name})});
    S.subjectAreaTags=[...(S.subjectAreaTags||[]),t];
    input.value='';
    tagFac(_tagFacId); // re-render modal with new tag
    msg.textContent='Tag "'+t.display_name+'" created.';
  }catch(e){
    msg.textContent=e.code==='tag_already_exists'?'That tag already exists.':'Could not create tag: '+apiErr(e);
  }
}
function toggleTagVocab(btn,val,makeActive){
  const active=makeActive==='true'||makeActive===true;
  btn.setAttribute('onclick',`toggleTagVocab(this,'${_jsAttr(val)}',${active?'false':'true'})`);
  btn.dataset.active=active?'true':'false';
  btn.style.background=active?'var(--royal)':'white';
  btn.style.color=active?'white':'var(--royal)';
}
async function saveTagFac(){
  const msg=document.getElementById('m-tag-msg');
  if(!_tagFacId){return;}
  const vocabTags=[...document.getElementById('m-tag-checks').querySelectorAll('button')]
    .filter(b=>b.dataset.active==='true').map(b=>b.textContent.trim());
  const customRaw=document.getElementById('m-tag-custom').value;
  const customTags=customRaw.split(',').map(t=>t.trim()).filter(Boolean);
  const allTags=[...new Set([...vocabTags,...customTags])];
  if(allTags.length>20){msg.textContent='Maximum 20 tags allowed.';return;}
  msg.textContent='Saving…';
  try{
    const r=await api('/api/facilitators/'+_tagFacId,{method:'PATCH',body:JSON.stringify({subject_areas:allTags})});
    // Apply the PATCH's own authoritative response to local state immediately,
    // rather than relying solely on reloadAndRender()'s full ~25-endpoint
    // loadData() cycle to catch up before the modal might be reopened for the
    // same facilitator -- under real network latency that full reload can take
    // over a second, and a user (or an automated test) re-opening the Tags
    // modal for this facilitator inside that window would see the pre-save
    // tag state. This closes the race by construction: correctness no longer
    // depends on loadData()'s timing for this specific save.
    const fac=S.facs.find(x=>x.id===_tagFacId);
    if(fac&&r&&Array.isArray(r.subject_areas)) fac.areas=r.subject_areas;
    showToast('Subject areas saved.');
    closeModal('m-tag-fac'); reloadAndRender();
  }catch(e){msg.textContent='Could not update: '+apiErr(e);}
}
function showFacProfile(id){
  const f=facById(id);if(!f)return;
  document.getElementById('fp-title').textContent=facDisplay(f)+' — Profile';
  const sess=allSess().filter(s=>s.facId===id||(!s.facId&&s.facName===facDisplay(f)));
  const sts={delivered:0,planned:0,not_delivered:0,cancelled:0,rescheduled:0};
  sess.forEach(s=>{if(sts[s.status]!==undefined)sts[s.status]++;});
  const phC={};sess.forEach(s=>{phC[s.phase]=(phC[s.phase]||0)+1;});
  document.getElementById('fp-body').innerHTML=`
    <div class="fac-ph">
      <div class="fac-av"></div>
      <div><h3>${esc(facDisplay(f))}</h3><p>${esc(f.type||'—')} · ${(f.areas||[]).map(a=>esc(EL_L[a]||a)).join(', ')}</p></div>
    </div>
    <div class="fac-sg">
      <div class="fac-st"><div class="fac-sv" style="color:var(--ok)">${sts.delivered}</div><div class="fac-sl">Delivered</div></div>
      <div class="fac-st"><div class="fac-sv">${sts.planned}</div><div class="fac-sl">Planned</div></div>
      <div class="fac-st"><div class="fac-sv" style="color:var(--steel)">${sts.not_delivered}</div><div class="fac-sl">Not Delivered</div></div>
      <div class="fac-st"><div class="fac-sv" style="color:var(--red)">${sts.cancelled}</div><div class="fac-sl">Cancelled</div></div>
      <div class="fac-st"><div class="fac-sv" style="color:var(--warn-text)">${sts.rescheduled}</div><div class="fac-sl">Rescheduled</div></div>
      <div class="fac-st"><div class="fac-sv">${sess.length}</div><div class="fac-sl">Total</div></div>
    </div>
    ${Object.keys(phC).length?`<h3 class="ctitle">Sessions by Phase</h3>
      ${Object.entries(phC).sort((a,b)=>b[1]-a[1]).map(([ph,n])=>`
      <div class="ph-row"><div class="ph-name">${PH_S[ph]||ph}</div>
        <div class="ph-bar"><div class="pbar"><div class="pfill" style="width:${Math.round(n/sess.length*100)}%"></div></div></div>
        <div class="ph-cnt">${n}</div>
      </div>`).join('')}`:''}
    <h3 class="ctitle" style="margin-top:14px;display:flex;align-items:center;justify-content:space-between">
      <span>Upcoming Leave (next 90 days)</span>
      ${canWriteSquadron()?`<button class="btn btn-xs btn-sky no-print" onclick="_showAddFacLeaveForm('${id}')">+ Add Leave</button>`:''}
    </h3>
    <div id="fac-leave-add-form"></div>
    ${f.leave&&f.leave.length?`
      <div class="tw"><table><thead><tr><th>From</th><th>To</th><th>Reason</th>${canWriteSquadron()?'<th class="no-print"></th>':''}</tr></thead>
      <tbody>${f.leave.map(lv=>`<tr>
        <td>${fmtD(lv.start_date,{day:'numeric',month:'short'})}</td>
        <td>${fmtD(lv.end_date,{day:'numeric',month:'short'})}</td>
        <td style="font-size:var(--fs-xs)">${esc(lv.reason||'—')}</td>
        ${canWriteSquadron()?`<td class="no-print"><button class="btn btn-xs btn-out" onclick="_deleteFacLeave('${lv.id}','${id}')">Remove</button></td>`:''}
      </tr>`).join('')}</tbody></table></div>`:'<div class="muted" style="font-size:var(--fs-xs)">No upcoming leave recorded.</div>'}
    <div style="margin-top:8px">
      <button class="btn-lnk" style="font-size:var(--fs-xs)" onclick="_showFacPastLeave('${id}', false)">Show past / removed leave</button>
    </div>
    <div id="fac-past-leave-section" style="display:none;margin-top:6px"></div>
    ${sess.length?`<h2 class="ctitle" style="margin-top:14px">Session History</h2>
      <div class="tw"><table><thead><tr><th>Date</th><th>S</th><th>Phase</th><th>Curriculum Item</th><th>Room</th><th>Status</th><th class="no-print">Action</th></tr></thead>
      <tbody>${sess.map(s=>`<tr>
        <td>${fmtD(s.date,{day:'numeric',month:'short'})}</td>
        <td style="color:var(--muted)">${s.si+1}</td>
        <td>${phBadge(s.phase)}</td>
        <td style="font-weight:700;font-size:var(--fs-sm)">${esc(s.exp||'—')}</td>
        <td style="font-size:var(--fs-xs)">${esc(s.room||'—')}</td>
        <td>${stBadge(s.status)}</td>
        <td class="no-print">${canWriteSquadron()?`<button class="btn btn-xs btn-sky" onclick="quickEdit('${s.date}',${s.si});closeModal('m-fac-profile')">Edit</button>`:'—'}</td>
      </tr>`).join('')}</tbody></table></div>`
    :'<div class="alert a-info">No sessions assigned yet.</div>'}`;
  openModal('m-fac-profile');
}
// Facilitator leave: backend already had full GET/POST/DELETE
// (/api/facilitators/{id}/leave, /api/facilitator-leave/{id}) with zero frontend UI to
// call any of it -- upcoming leave was readable but never addable/removable. Minimal,
// inline-in-modal form matching this file's existing pattern (e.g. the Parade Day
// propagation wizard's own body.innerHTML swap) rather than a separate modal.
function _showAddFacLeaveForm(facId){
  const el=document.getElementById('fac-leave-add-form');
  if(!el)return;
  const today=new Date().toISOString().slice(0,10);
  el.innerHTML=`<div class="form-row" style="margin-top:6px;align-items:flex-end">
    <div class="ff"><label for="fl-start">From</label><input type="date" id="fl-start" value="${today}"></div>
    <div class="ff"><label for="fl-end">To</label><input type="date" id="fl-end" value="${today}"></div>
    <div class="ff" style="flex:2"><label for="fl-reason">Reason (optional)</label><input id="fl-reason" placeholder="e.g. Annual leave"></div>
  </div>
  <div class="form-row" style="margin-top:4px">
    <div class="ff"><label for="fl-notes">Notes (optional)</label><input id="fl-notes" placeholder="Any additional notes"></div>
  </div>
  <div id="fl-msg" style="font-size:var(--fs-xs);margin:4px 0"></div>
  <div class="modal-actions" style="justify-content:flex-start">
    <button class="btn btn-primary btn-sm" onclick="_submitFacLeave('${facId}')">Save Leave</button>
    <button class="btn btn-secondary btn-sm" onclick="document.getElementById('fac-leave-add-form').innerHTML=''">Cancel</button>
  </div>`;
}
async function _submitFacLeave(facId){
  const start=document.getElementById('fl-start').value;
  const end=document.getElementById('fl-end').value;
  const reason=(document.getElementById('fl-reason').value||'').trim()||null;
  const notes=(document.getElementById('fl-notes').value||'').trim()||null;
  const msg=document.getElementById('fl-msg');
  if(!start||!end){ msg.textContent='Both dates are required.'; msg.style.color='var(--red)'; return; }
  if(start>end){ msg.textContent='End date must be on or after the start date.'; msg.style.color='var(--red)'; return; }
  msg.textContent='Saving…'; msg.style.color='var(--muted)';
  try{
    const r=await api('/api/planning/facilitators/'+facId+'/leave',{method:'POST',body:JSON.stringify({start_date:start,end_date:end,reason,notes})});
    document.getElementById('fac-leave-add-form').innerHTML='';
    await reloadAndRender();
    const affected=(r.affected_sessions||[]).length;
    showToast(affected
      ? `Leave added. ${affected} already-scheduled session(s) fall within this period — review Parade Nights for conflicts.`
      : 'Leave added.', affected>0);
    showFacProfile(facId);
  }catch(e){ msg.textContent=apiErr(e); msg.style.color='var(--red)'; }
}
async function _deleteFacLeave(leaveId,facId){
  try{
    await api('/api/planning/facilitator-leave/'+leaveId,{method:'DELETE'});
    await reloadAndRender();
    showToast('Leave removed.');
    showFacProfile(facId);
  }catch(e){ showToast('Could not remove leave: '+apiErr(e), true); }
}
async function _restoreFacLeave(leaveId,facId){
  try{
    await api('/api/planning/facilitator-leave/'+leaveId+'/restore',{method:'POST'});
    showToast('Leave record restored.');
    // Refresh the profile with archived view still visible
    await _showFacPastLeave(facId, true);
  }catch(e){ showToast('Could not restore leave: '+apiErr(e), true); }
}
let _facPastLeaveContainer=null;
async function _showFacPastLeave(facId, forceRefresh){
  const cont=document.getElementById('fac-past-leave-section');
  if(!cont)return;
  if(!forceRefresh&&cont.dataset.loaded){cont.style.display=cont.style.display==='none'?'block':'none';return;}
  cont.style.display='block';
  cont.dataset.loaded='1';
  cont.innerHTML='<div class="muted" style="font-size:var(--fs-xs);padding:4px 0">Loading past leave…</div>';
  try{
    const all=await api('/api/planning/facilitators/'+facId+'/leave?include_archived=true');
    const past=Array.isArray(all)?all.filter(lv=>lv.is_archived):[];
    if(!past.length){ cont.innerHTML='<div class="muted" style="font-size:var(--fs-xs)">No past or removed leave records.</div>'; return; }
    cont.innerHTML='<div class="tw"><table><thead><tr><th>From</th><th>To</th><th>Reason</th>'+(canWriteSquadron()?'<th class="no-print"></th>':'')+'</tr></thead><tbody>'+
      past.map(lv=>`<tr style="opacity:.7">
        <td>${fmtD(lv.start_date,{day:'numeric',month:'short'})}</td>
        <td>${fmtD(lv.end_date,{day:'numeric',month:'short'})}</td>
        <td style="font-size:var(--fs-xs)">${esc(lv.reason||'—')}</td>
        ${canWriteSquadron()?`<td class="no-print"><button class="btn btn-xs btn-ok" onclick="_restoreFacLeave('${lv.id}','${facId}')">Restore</button></td>`:''}
      </tr>`).join('')+
      '</tbody></table></div>';
  }catch(e){ cont.innerHTML='<div style="color:var(--red);font-size:var(--fs-xs)">'+esc(apiErr(e))+'</div>'; }
}
function _readFacAreas(){
  const areas=[];
  ['drill','air','field','pd','sc','sqn'].forEach(k=>{if(document.getElementById('fa-'+k)&&document.getElementById('fa-'+k).checked)areas.push({drill:'Drill',air:'Air_Space',field:'Field',pd:'Personal_Dev',sc:'Service_Community',sqn:'SQN_Affairs'}[k]);});
  return areas;
}
// ── Facilitator CSV Import (P1-IMPORT-02) ────────────────────────────────────
// Raw fetch (not api()) because multipart/form-data requires the browser to set
// Content-Type with its boundary string — api() always injects application/json.
// Same pattern as the CEA import already uses.
let _facImportRows=[];
let _facImportConfirmIdx=new Set();

function openFacImportModal(){
  document.getElementById('fac-import-file').value='';
  document.getElementById('fac-import-filename').textContent='';
  document.getElementById('fac-import-preview').style.display='none';
  document.getElementById('fac-import-result').style.display='none';
  document.getElementById('fac-import-confirm-btn').style.display='none';
  _facImportRows=[];
  _facImportConfirmIdx=new Set();
  openModal('m-fac-import');
}

function _facImportTemplate(){
  // The backend sets Content-Disposition:attachment; session cookie handles auth.
  const a=document.createElement('a');
  a.href=API_BASE+'/api/facilitators/import/template.csv';
  a.target='_blank'; a.rel='noopener'; a.click();
}

async function _facImportPreview(){
  const fi=document.getElementById('fac-import-file');
  if(!fi.files||!fi.files[0])return;
  document.getElementById('fac-import-filename').textContent=fi.files[0].name;
  document.getElementById('fac-import-preview').style.display='none';
  document.getElementById('fac-import-result').style.display='none';
  document.getElementById('fac-import-confirm-btn').style.display='none';
  _facImportRows=[];
  _facImportConfirmIdx=new Set();
  const fd=new FormData(); fd.append('file',fi.files[0]);
  try{
    const tok=tokenGet();
    const resp=await fetch(API_BASE+'/api/facilitators/import?preview=true',{
      method:'POST',headers:tok?{Authorization:'Bearer '+tok}:{},credentials:'include',body:fd,
    });
    if(!resp.ok){
      const err=await resp.json().catch(function(){return{};});
      const msg=(err.detail&&err.detail.message)||(typeof err.detail==='string'&&err.detail)||('Preview failed ('+resp.status+')');
      showToast(msg,true); return;
    }
    const data=await resp.json();
    _facImportRows=data.rows||[];
    _facImportRenderPreview(data);
  }catch(e){showToast(apiErr(e),true);}
}

function _facImportRenderPreview(data){
  const tbody=document.getElementById('fac-import-tbody');
  tbody.innerHTML='';
  _facImportRows.forEach(function(r){
    const isDup=r.action==='duplicate'||r.action==='duplicate_in_file';
    const badge=r.action==='create'?'<span class="badge b-ok">New</span>'
      :isDup?'<span class="badge b-amber">Exists</span>'
      :'<span class="badge b-red">Error</span>';
    const forceCell=isDup?'<input type="checkbox" aria-label="Force create despite duplicate" onchange="_facImportToggleDup('+r.row+')">':'';
    const msgCell=r.message?'<br><span style="color:var(--red);font-size:var(--fs-2xs)">'+esc(r.message)+'</span>':'';
    const areas=(r.subject_areas||[]).join(', ');
    const tr=document.createElement('tr');
    tr.innerHTML='<td>'+esc(r.current_rank||'')+'</td>'
      +'<td>'+esc((r.first_name?r.first_name+' ':'')+r.last_name)+'</td>'
      +'<td>'+esc(r.type||'')+'</td>'
      +'<td style="font-size:var(--fs-2xs)">'+esc(areas)+'</td>'
      +'<td>'+badge+msgCell+'</td>'
      +'<td>'+forceCell+'</td>';
    tbody.appendChild(tr);
  });
  const toCreate=data.to_create||0;
  document.getElementById('fac-import-summary').textContent=
    toCreate+' to create · '+(data.duplicates||0)+' duplicate(s) · '+(data.errors||0)+' error(s)';
  document.getElementById('fac-import-preview').style.display='';
  const btn=document.getElementById('fac-import-confirm-btn');
  if(toCreate>0){
    btn.textContent='Import '+toCreate+' facilitator'+(toCreate===1?'':'s');
    btn.disabled=false; btn.style.display='';
  } else {
    btn.style.display='none';
  }
}

function _facImportToggleDup(rowIdx){
  if(_facImportConfirmIdx.has(rowIdx))_facImportConfirmIdx.delete(rowIdx);
  else _facImportConfirmIdx.add(rowIdx);
  const autoCreate=_facImportRows.filter(function(r){return r.action==='create';}).length;
  const total=autoCreate+_facImportConfirmIdx.size;
  const btn=document.getElementById('fac-import-confirm-btn');
  if(total>0){
    btn.textContent='Import '+total+' facilitator'+(total===1?'':'s');
    btn.style.display='';
  } else {
    btn.style.display='none';
  }
}

async function _facImportConfirm(){
  const fi=document.getElementById('fac-import-file');
  if(!fi.files||!fi.files[0])return;
  const btn=document.getElementById('fac-import-confirm-btn');
  btn.disabled=true; btn.textContent='Importing…';
  const fd=new FormData(); fd.append('file',fi.files[0]);
  let url=API_BASE+'/api/facilitators/import?preview=false';
  if(_facImportConfirmIdx.size)url+='&confirm_duplicate_rows='+Array.from(_facImportConfirmIdx).join(',');
  try{
    const tok=tokenGet();
    const resp=await fetch(url,{
      method:'POST',headers:tok?{Authorization:'Bearer '+tok}:{},credentials:'include',body:fd,
    });
    if(!resp.ok){
      const err=await resp.json().catch(function(){return{};});
      const msg=(err.detail&&err.detail.message)||(typeof err.detail==='string'&&err.detail)||('Import failed ('+resp.status+')');
      btn.disabled=false; btn.textContent='Import';
      showToast(msg,true); return;
    }
    const data=await resp.json();
    document.getElementById('fac-import-preview').style.display='none';
    btn.style.display='none';
    const res=document.getElementById('fac-import-result');
    res.style.display='';
    res.innerHTML='<div class="alert a-ok">Imported <strong>'+data.created+'</strong> facilitator'+(data.created===1?'':'s')
      +(data.skipped?'. Skipped: '+data.skipped+'.':'')+(data.errors?' Errors: '+data.errors+'.':'')+'</div>';
    // Refresh facilitators page
    await loadData(); renderFacs(); if(typeof loadFacilitatorStats==='function')await loadFacilitatorStats();
  }catch(e){
    btn.disabled=false; btn.textContent='Import';
    showToast(apiErr(e),true);
  }
}
// ─────────────────────────────────────────────────────────────────────────────

function _clearFacDupWarning(){
  const w=document.getElementById('fac-dup-warn'); if(w){w.style.display='none';w.textContent='';}
  const anyway=document.getElementById('fac-save-anyway-btn'); if(anyway)anyway.style.display='none';
}
// TRGO-07: the backend blocks a same-name-in-squadron create with 409
// possible_duplicate once, then requires an explicit confirm_duplicate resubmit
// (backend/app/routers/training.py add_fac). This surfaced only as a blocking
// alert() with no way to actually add a genuine same-name-different-person --
// a dead end. Now it shows an inline warning and an explicit "Add anyway" button
// that resubmits with confirm_duplicate:true, matching the same pattern already
// used in the React Planning Workspace's Facilitators page.
let _facIdemKey=null;
function _facSaveStateEl(){ return document.getElementById('fac-save-state'); }
function _setFacSaveState(text,color){
  const el=_facSaveStateEl(); if(!el)return;
  el.textContent=text; el.style.color=color||'var(--muted)';
}
function _resetFacSaveState(){ _facIdemKey=null; _setFacSaveState(''); }
function _markFacUnsaved(){ _setFacSaveState('Unsaved changes','var(--muted)'); }

function saveFac(confirmDuplicate){
  const rank=document.getElementById('fac-rank').value.trim();
  const first=document.getElementById('fac-first').value.trim();
  const last=document.getElementById('fac-last').value.trim();
  if(!last){showToast('Family name required.',true);return;}
  const areas=_readFacAreas();
  const type=document.getElementById('fac-type').value;
  const btn=document.getElementById('fac-save-btn');
  const btnLabel=btn?btn.textContent:'Save Profile';
  if(btn){btn.disabled=true;btn.textContent='Saving…';}
  const anywayBtn=document.getElementById('fac-save-anyway-btn');
  if(anywayBtn)anywayBtn.disabled=true;
  _setFacSaveState('Saving…','var(--muted)');
  const done=()=>{ if(btn){btn.disabled=false;btn.textContent=btnLabel;} if(anywayBtn)anywayBtn.disabled=false; };
  if(editFacId){
    const fid=editFacId; editFacId=null;
    api('/api/facilitators/'+fid,{method:'PATCH',body:JSON.stringify({first_name:first,last_name:last,current_rank:rank,type})})
      .then(()=>{
        const savedAt=new Date().toLocaleTimeString('en-AU',{hour:'2-digit',minute:'2-digit',hour12:false});
        _setFacSaveState('Saved at '+savedAt,'var(--ok)');
        // Synchronously update S.facs so renderFacs() reflects the edit immediately
        // without a background reloadAndRender() that would race with the next
        // waitForFreshCharts() listener in tests (REM-111 root-cause fix).
        const idx=(S.facs||[]).findIndex(function(f){return f.id===fid;});
        if(idx>=0) S.facs[idx]=Object.assign({},S.facs[idx],{rank:rank,first:first,last:last,type:type});
        renderFacs();
        closeModal('m-add-fac'); document.getElementById('fac-modal-title').textContent='+ Add Facilitator'; _clearFacDupWarning();
        showToast('Facilitator profile saved.', false);
        loadFacilitatorStats().catch(()=>{});
      })
      .catch(e=>{
        _setFacSaveState('Failed to save — Retry','var(--red)');
        showToast('Could not save: '+apiErr(e), true);
      })
      .finally(done);
    return;
  }
  // A retried click (or the client believing the previous request failed and
  // resubmitting) while the form is unchanged must not create a second
  // facilitator — reuse the same key until this attempt actually succeeds.
  if(!_facIdemKey){ _facIdemKey=(window.crypto&&crypto.randomUUID)?crypto.randomUUID():('fac-'+Date.now()+'-'+Math.random().toString(36).slice(2)); }
  api('/api/facilitators',{method:'POST',headers:{'Idempotency-Key':_facIdemKey},body:JSON.stringify({first_name:first,last_name:last,current_rank:rank,type,subject_areas:areas,confirm_duplicate:!!confirmDuplicate})})
    .then(function(res){
      const savedAt=new Date().toLocaleTimeString('en-AU',{hour:'2-digit',minute:'2-digit',hour12:false});
      _setFacSaveState('Saved at '+savedAt,'var(--ok)');
      // Synchronously add the new facilitator to S.facs so renderFacs() reflects
      // it immediately without a background reloadAndRender() race (REM-111 fix).
      _facIdemKey=null;
      if(res&&res.facilitator_id){
        if(!S.facs) S.facs=[];
        S.facs.push({id:res.facilitator_id,rank:rank,first:first,last:last,type:type,areas:areas,leave:[]});
      }
      // REM-99: a leftover search term in #fac-search (e.g. typed while checking
      // for an existing duplicate before adding) silently filtered the just-
      // created facilitator out of the re-rendered list -- renderFacs() applies
      // it unconditionally -- reproducing "created but not visible until hard
      // refresh" exactly (a refresh clears the input; the DOM value otherwise
      // persists indefinitely, since nothing else ever resets it). Clear it so
      // the new facilitator is guaranteed visible immediately.
      const facSearch=document.getElementById('fac-search'); if(facSearch)facSearch.value='';
      renderFacs();
      closeModal('m-add-fac'); document.getElementById('fac-modal-title').textContent='+ Add Facilitator'; _clearFacDupWarning();
      showToast('Facilitator added at '+savedAt+'.', false);
      loadFacilitatorStats().catch(()=>{});
    })
    .catch(e=>{
      if(e&&e.code==='possible_duplicate'&&!confirmDuplicate){
        const detail=(e.body&&e.body.detail)||{};
        _setFacSaveState('Possible match — see dialog','var(--warn)');
        _openFacDupModal(detail,{rank,first,last,type,areas});
      }else{
        _setFacSaveState('Failed to save — Retry','var(--red)');
        showToast('Could not save: '+apiErr(e), true);
      }
    })
    .finally(done);
}
// ── FAC-DUP-01: Duplicate Facilitator Disambiguation Modal ───────────────────
let _facDupDetail=null;  // 409 detail from backend (existing record info)
let _facDupPending=null; // pending form data {rank,first,last,type,areas}

function _openFacDupModal(detail,pending){
  _facDupDetail=detail||{};
  _facDupPending=pending||{};
  const areas=(_facDupDetail.existing_subject_areas||[]).length
    ?_facDupDetail.existing_subject_areas.map(esc).join(', '):'—';
  const updated=_facDupDetail.existing_updated_at
    ?new Date(_facDupDetail.existing_updated_at).toLocaleDateString('en-AU',{day:'numeric',month:'short',year:'numeric'}):'—';
  const status=_facDupDetail.existing_active_status===false?'Archived':'Active';
  document.getElementById('fac-dup-existing-card').innerHTML=`
    <div style="margin-bottom:6px;font-size:var(--fs-sm);font-weight:700;color:var(--dark)">Existing record</div>
    <div style="padding:10px 12px;background:var(--surface-2);border-radius:6px;font-size:var(--fs-xs);display:grid;grid-template-columns:auto 1fr;gap:3px 12px;margin-bottom:10px">
      <span style="color:var(--muted)">Rank</span><span style="font-weight:700">${esc(_facDupDetail.existing_rank||'—')}</span>
      <span style="color:var(--muted)">Type</span><span>${esc(_facDupDetail.existing_type||'—')}</span>
      <span style="color:var(--muted)">Subject areas</span><span>${areas}</span>
      <span style="color:var(--muted)">Status</span><span>${esc(status)}</span>
      <span style="color:var(--muted)">Last updated</span><span>${esc(updated)}</span>
    </div>
    <div style="font-size:var(--fs-xs);color:var(--muted)">Rank does not determine identity — two people may share a name, and one person may change rank over time.</div>`;
  document.getElementById('fac-dup-merge-panel').style.display='none';
  document.getElementById('fac-dup-actions').style.display='';
  closeModal('m-add-fac'); openModal('m-fac-dup');
}

function _facDupCancel(){
  closeModal('m-fac-dup');
  _clearFacDupWarning();
  openModal('m-add-fac');
}

function _facDupUseExisting(){
  const eid=_facDupDetail&&_facDupDetail.existing_facilitator_id;
  closeModal('m-fac-dup');
  closeModal('m-add-fac');
  document.getElementById('fac-modal-title').textContent='+ Add Facilitator';
  _clearFacDupWarning();
  _facDupDetail=null; _facDupPending=null;
  if(eid) showFacProfile(eid);
}

function _facDupCreateDifferent(){
  closeModal('m-fac-dup');
  _facDupDetail=null; _facDupPending=null;
  saveFac(true);
}

function _facDupShowMergePreview(){
  const eid=_facDupDetail&&_facDupDetail.existing_facilitator_id;
  if(!eid){showToast('Cannot identify existing record.',true);return;}
  const pending=_facDupPending||{};
  const panel=document.getElementById('fac-dup-merge-panel');
  panel.innerHTML=`
    <div class="alert a-info" style="margin-top:10px;font-size:var(--fs-xs)">
      <strong>Merge preview</strong><br>
      The existing record will be updated with the details you entered.<br>
      Rank: <strong>${esc(pending.rank||'unchanged')}</strong> &nbsp; Type: <strong>${esc(pending.type||'unchanged')}</strong><br>
      All historical sessions, outcomes, and leave records will remain linked to the existing record.<br>
      No sessions will be moved. This action updates profile fields only.
    </div>`;
  const foot=document.createElement('div');
  foot.style.cssText='display:flex;gap:8px;margin-top:10px';
  foot.innerHTML=`<button class="btn btn-out" onclick="document.getElementById('fac-dup-merge-panel').style.display='none';document.getElementById('fac-dup-actions').style.display=''">Back</button>
    <button class="btn btn-dk" onclick="_facDupConfirmMerge()">Confirm — Update existing record</button>`;
  panel.appendChild(foot);
  panel.style.display='';
  document.getElementById('fac-dup-actions').style.display='none';
}

async function _facDupConfirmMerge(){
  const eid=_facDupDetail&&_facDupDetail.existing_facilitator_id;
  if(!eid) return;
  const pending=_facDupPending||{};
  try{
    await api('/api/facilitators/'+eid,{method:'PATCH',body:JSON.stringify({
      first_name:pending.first, last_name:pending.last,
      current_rank:pending.rank||undefined, type:pending.type||undefined
    })});
    closeModal('m-fac-dup');
    closeModal('m-add-fac');
    document.getElementById('fac-modal-title').textContent='+ Add Facilitator';
    _clearFacDupWarning();
    _facDupDetail=null; _facDupPending=null;
    await reloadAndRender(); await loadFacilitatorStats();
    showToast('Existing Facilitator record updated.');
  }catch(e){showToast('Could not update: '+apiErr(e),true);}
}

// ── AUTO-01: Save-state model ─────────────────────────────────────────────
// _mkAutoSave(saveFn, statusElId) returns an oninput handler that:
//   1. Marks the field DIRTY immediately.
//   2. Debounces 1400 ms (no write on every keystroke).
//   3. On fire: sets SAVING, calls saveFn(currentValue), sets SAVED/FAILED.
//   4. Prevents duplicate concurrent writes via an in-flight flag.
//   5. Shows plain-English status in the element identified by statusElId.
//
// saveFn receives the current field value and must return a Promise.
// Class A (autosave): low-risk text/notes with a clean partial-update endpoint.
// Class B/C fields continue to use explicit Save buttons (unchanged).
function _mkAutoSave(saveFn, statusElId){
  let _timer=null;
  let _inflight=false;
  function _setStatus(cls,msg){
    const el=document.getElementById(statusElId); if(!el)return;
    el.className='save-ind'+(cls?' '+cls:'');
    el.textContent=msg;
  }
  return function onInput(e){
    _setStatus('','Unsaved');
    if(_timer)clearTimeout(_timer);
    _timer=setTimeout(async()=>{
      if(_inflight)return; // skip — a save is already in flight
      const val=e.target.value;
      _inflight=true;
      _setStatus('saving','Saving…');
      try{
        await saveFn(val);
        _setStatus('saved','Saved');
        setTimeout(()=>_setStatus('',''),3000);
      }catch(_e){
        _setStatus('failed','Could not save — Try again');
      }finally{
        _inflight=false;
      }
    },1400);
  };
}

// Friendlier labels for the known seeded short codes -- custom types created
// via manageFacilitatorTypes() have no such mapping and just show their own
// display_name as-is, matching how Subject Area tags already behave.
const _FAC_TYPE_LABELS={Staff:'Staff',Officer:'Officer (AAFC)',NCO:'Warrant Officer / NCO (AAFC)','Senior Cadet':'Senior Cadet',Civilian:'Civilian Instructor'};
function _populateFacTypeSelect(){
  const sel=document.getElementById('fac-type'); if(!sel)return;
  const prior=sel.value;
  const tags=(S.facilitatorTypeTags||[]);
  const opts=tags.length
    ? tags.map(t=>`<option value="${esc(t.display_name)}">${esc(_FAC_TYPE_LABELS[t.display_name]||t.display_name)}</option>`).join('')
    : '<option value="Staff">Staff</option><option value="Officer">Officer (AAFC)</option><option value="NCO">Warrant Officer / NCO (AAFC)</option><option value="Senior Cadet">Senior Cadet</option><option value="Civilian">Civilian Instructor</option>';
  const addOpt=canWriteSquadron()?'<option value="__add_new__">+ Add new type…</option>':'';
  sel.innerHTML=opts+addOpt;
  if(prior && [...sel.options].some(o=>o.value===prior)) sel.value=prior;
}
async function _onFacTypeChange(sel){
  if(sel.value!=='__add_new__'){ _markFacUnsaved(); return; }
  const name=await promptText('New facilitator type','Type name',{okLabel:'Create'});
  if(!name){ sel.value=S.facilitatorTypeTags&&S.facilitatorTypeTags[0]?S.facilitatorTypeTags[0].display_name:'Staff'; return; }
  try{
    const t=await api('/api/facilitator-type-tags',{method:'POST',body:JSON.stringify({display_name:name})});
    S.facilitatorTypeTags=[...(S.facilitatorTypeTags||[]),t];
    _populateFacTypeSelect();
    sel.value=t.display_name;
    showToast('Facilitator type "'+t.display_name+'" created.');
  }catch(e){
    showToast(e.code==='tag_already_exists'?'That type already exists.':'Could not create type: '+apiErr(e), true);
    sel.value=S.facilitatorTypeTags&&S.facilitatorTypeTags[0]?S.facilitatorTypeTags[0].display_name:'Staff';
  }
  _markFacUnsaved();
}
function editFac(id){
  const f=facById(id);if(!f)return;editFacId=id;
  document.getElementById('fac-modal-title').textContent='Edit Facilitator';
  document.getElementById('fac-rank').value=f.rank||'';document.getElementById('fac-first').value=f.first||'';
  document.getElementById('fac-last').value=f.last||'';
  // "Staff" is now a real #fac-type option (backed by the seeded reference
  // tag of the same name) -- previously this remapped it to "Officer" since
  // no matching option existed, which meant saving a Staff record without
  // touching the dropdown silently rewrote it to Officer.
  document.getElementById('fac-type').value=f.type||'Staff';
  // Hide the checkbox area selector in edit mode — the Tags button is the
  // authoritative subject-area editor and supports the full tag vocabulary.
  // Sending checkbox values from here would silently clobber any tags set via
  // the extended vocab (e.g. "Air & Space" vs old "Air_Space" key).
  document.getElementById('fa-areas-create').style.display='none';
  document.getElementById('fa-areas-edit').style.display='';
  _clearFacDupWarning();
  _resetFacSaveState();
  openModal('m-add-fac');
}
async function delFac(id){
  confirmAction('Archive this facilitator? Past session records are preserved, and this can be undone from "Show archived".',async()=>{
    try{ await api('/api/facilitators/'+id,{method:'DELETE'}); await reloadAndRender(); await loadFacilitatorStats(); }
    catch(e){ showToast(apiErr(e),true); }
  });
}

let _mergeFacSourceId=null;
function openMergeFac(sourceId){
  const f=facById(sourceId);if(!f)return;
  _mergeFacSourceId=sourceId;
  const others=S.facs.filter(x=>x.id!==sourceId);
  if(!others.length){showToast('No other facilitators to merge into.',true);return;}
  document.getElementById('fac-merge-info').innerHTML='<strong>'+esc(facDisplay(f))+'</strong> will be archived. Select the facilitator to keep:';
  document.getElementById('fac-merge-target').innerHTML=others.map(x=>`<option value="${x.id}">${esc(facDisplay(x))}</option>`).join('');
  document.getElementById('fac-merge-state').textContent='';
  document.getElementById('fac-merge-btn').disabled=false;
  openModal('m-fac-merge');
}
async function doMergeFac(){
  if(!_mergeFacSourceId)return;
  const targetId=document.getElementById('fac-merge-target').value;if(!targetId)return;
  const btn=document.getElementById('fac-merge-btn');
  if(btn)btn.disabled=true;
  document.getElementById('fac-merge-state').textContent='Merging…';
  try{
    const r=await api('/api/facilitators/'+targetId+'/absorb',{method:'POST',body:JSON.stringify({source_id:_mergeFacSourceId})});
    closeModal('m-fac-merge');
    await reloadAndRender();
    await loadFacilitatorStats();
    showToast('Merged: '+(r.sessions_moved||0)+' session(s) re-attributed.',false);
  }catch(e){
    document.getElementById('fac-merge-state').textContent='';
    if(btn)btn.disabled=false;
    showToast('Merge failed: '+apiErr(e),true);
  }
}
