// Main TMS module: Curriculum page -- tabs, archive/restore, item detail and
// class breakdown, create/edit/delete.
// Extracted verbatim from connected-frontend/index.html (stabilisation Phase 4,
// C6). Top-level function declarations and side-effect-free let/const only;
// loaded as a classic script BEFORE the inline bootstrap, so everything here
// is defined before any page-load code runs. Statements with load-time
// effects stay in index.html in their original order. Parity is proven by
// tools/architecture/frontend_parity.mjs.

// ═══════════════════════════════════════════════════════════
//  CURRICULUM
// ═══════════════════════════════════════════════════════════
function setCurrTab(ph,btn){
  currTabFilter=ph;
  document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  const fbar=document.getElementById('curr-fbar');
  if(fbar)fbar.style.display='';
  const cl=document.getElementById('curr-list');
  if(cl)cl.style.display='';
  renderCurr();
}

function deriveProgress(code){
  const arr=allSess().filter(s=>s.code===code).map(s=>s.status);
  if(!arr.length)return 'unscheduled';
  if(arr.some(s=>s==='delivered'))return 'delivered';
  if(arr.some(s=>s==='rescheduled'))return 'rescheduled';
  if(arr.some(s=>s==='cancelled'))return 'cancelled';
  if(arr.some(s=>s==='not_delivered'))return 'not_delivered';
  return 'planned';
}
const PH_BG={'A. Orientation':'#fff0f0','B. Initial':'#fffbf0','C. Junior':'#f0faf5','D. Intermediate':'#eef5ff','E. Senior':'#f5f0ff','I. Bronze':'#fff5ec','J. Silver':'#f5f5f5','K. Gold':'#faf7e8'};
const PH_BD={'A. Orientation':'#e51937','B. Initial':'#c97a00','C. Junior':'#1a7f4b','D. Intermediate':'#004b8d','E. Senior':'#7c3aed','I. Bronze':'#c97a00','J. Silver':'#666','K. Gold':'#b8860b'};

function sourceBadge(e){
  if(e.owningLevel==='national')return '<span class="badge b-dark" style="font-size:var(--fs-2xs)">NAT HQ</span>';
  if(e.owningLevel==='wing'){
    // Look up wing code from S.wings (populated by loadData for all roles)
    const wg=(S.wings&&S.wings.find(w=>w.wing_id===e.wingId)||{code:'Wing'}).code;
    return `<span class="badge b-purple" style="font-size:var(--fs-2xs)">${esc(wg)}</span>`;
  }
  return '<span class="badge b-teal" style="font-size:var(--fs-3xs)">SQN</span>';
}
function canEditCurr(e){
  const role=S.role||'';
  if(e.owningLevel==='national')return ['national_admin','system_admin'].includes(role);
  if(e.owningLevel==='wing')return ['national_admin','system_admin','wing_admin'].includes(role);
  return canWriteSquadron()&&e.owned;
}
// REM-133: archive existed with no way to see or restore an archived
// curriculum item -- follows the same "show archived" lazy-fetch pattern
// already used for Facilitators (_facsToggleShowArchived/doRestoreFacilitator).
let _archivedCurrList=null;
async function _currToggleShowArchived(){
  const checked=(document.getElementById('curr-show-archived')||{}).checked;
  if(!checked){ renderCurr(); return; }
  try{
    _archivedCurrList=(await api('/api/curriculum?include_archived=true')).items.filter(i=>i.is_archived).map(_mapCurrItem);
  }catch(e){ showToast('Could not load archived curriculum items: '+apiErr(e), true); }
  renderCurr();
}
async function doRestoreCurrItem(id, title){
  try{
    await api(`/api/curriculum/${id}/restore`,{method:'POST'});
    showToast(`'${title}' restored.`);
    await reloadAndRender();
    _archivedCurrList=(await api('/api/curriculum?include_archived=true')).items.filter(i=>i.is_archived).map(_mapCurrItem);
    renderCurr();
  }catch(e){ showToast('Could not restore: '+apiErr(e), true); }
}
function renderCurr(){
  const showArchived=(document.getElementById('curr-show-archived')||{}).checked;
  const q=(document.getElementById('curr-search').value||'').toLowerCase();
  if(showArchived){
    const list=document.getElementById('curr-list');
    const items=(_archivedCurrList||[]).filter(e=>!q||e.title.toLowerCase().includes(q)||e.code.toLowerCase().includes(q));
    list.innerHTML=items.length?`<div class="tw"><table><thead><tr><th>Code</th><th>Title</th><th>Phase</th><th></th></tr></thead><tbody>${
      items.map(e=>`<tr>
        <td style="font-weight:700">${esc(e.code)} <span class="badge b-grey">Archived</span></td>
        <td>${esc(e.title)}</td>
        <td>${phBadge(e.phase)}</td>
        <td style="text-align:right">${canEditCurr(e)?`<button class="btn btn-xs btn-ok" onclick="doRestoreCurrItem('${e.id}','${_jsAttr(e.title)}')">Restore</button>`:''}</td>
      </tr>`).join('')
    }</tbody></table></div>`:`<div class="empty"><div class="et">No archived curriculum items</div><div class="es">${q?'No archived items match your search.':'Nothing archived yet.'}</div></div>`;
    return;
  }
  const elF=document.getElementById('curr-f-el').value;
  const pgF=document.getElementById('curr-f-prog').value;
  // TRGO-04: let an admin audit which curriculum items have no Learning
  // Hub link, instead of finding out one at a time while browsing.
  const noLhF=(document.getElementById('curr-f-nolh')||{}).checked;
  const filtered=allCurr().filter(e=>{
    if(currTabFilter!=='all'&&e.phase!==currTabFilter)return false;
    if(elF!=='all'&&e.el!==elF)return false;
    const dp=deriveProgress(e.code);
    if(pgF!=='all'&&dp!==pgF)return false;
    if(noLhF&&e.lh)return false;
    if(q&&!e.title.toLowerCase().includes(q)&&!e.code.toLowerCase().includes(q))return false;
    return true;
  });
  const list=document.getElementById('curr-list');
  if(!filtered.length){list.innerHTML=`<div class="empty"><div class="et">No curriculum items</div><div class="es">No items match the current filters. Adjust the filters above or add a new curriculum item.</div></div>`;return;}
  // Group by phase
  const groups={};filtered.forEach(e=>{if(!groups[e.phase])groups[e.phase]=[];groups[e.phase].push(e);});
  list.innerHTML=Object.entries(groups).map(([ph,items])=>`
    <div class="curr-card" style="border-color:${PH_BD[ph]||'var(--border)'}">
      <div class="curr-hdr" style="background:${PH_BG[ph]||'#f4f8fc'}" onclick="toggleCC(this)">
        <div style="display:flex;align-items:center;gap:8px">${phBadge(ph)}<span style="font-size:var(--fs-sm);font-weight:800;color:var(--dark)">${items.length} item${items.length!==1?'s':''}</span></div>
        <span style="font-size:var(--fs-xs);color:var(--muted)">▾</span>
      </div>
      <div class="curr-body open">
        ${items.map(e=>{
          const dp=deriveProgress(e.code);
          const sc=allSess().filter(s=>s.code===e.code).length;
          const editable=canEditCurr(e);
          return `<div class="exp-item" onclick="showCurrDetail('${e.code}')">
            <div style="flex:1;min-width:0">
              <div class="exp-code">${esc(e.code)} · ${e.hours}h · ${getProgramType(e.phase)} ${sourceBadge(e)}</div>
              <div class="exp-title">${esc(e.title)}</div>
              <div class="exp-meta">
                ${elBadge(e.el)}
                <span class="badge b-blue" style="font-size:var(--fs-2xs)">${esc(e.term||'—')}</span>
                ${stBadge(dp)}
                ${e.lh?`<a href="${safeUrl(e.lh)}" target="_blank" class="lh-btn" onclick="event.stopPropagation()">Learning Hub</a>`:''}
              </div>
              ${_currClassBreakdownHtml((S.classByCode||{})[e.code])}
            </div>
            <div class="exp-right">
              ${sc>0?`<button class="btn-lnk" style="font-size:var(--fs-2xs)" onclick="event.stopPropagation();drillCurr('${esc(e.code)}')">${sc} sess.</button>`:''}
              ${editable?`<button class="btn btn-xs btn-out" onclick="event.stopPropagation();editCurr('${esc(e.code)}')">Edit</button> <button class="btn btn-xs btn-red" aria-label="Delete curriculum item" onclick="event.stopPropagation();deleteCurrItem('${e.id}')">×</button>`:''}
            </div>
          </div>`;
        }).join('')}
      </div>
    </div>`).join('');
}
function toggleCC(hdr){const b=hdr.nextElementSibling;b.classList.toggle('open');hdr.querySelector('span:last-child').textContent=b.classList.contains('open')?'▾':'▸';}

// MBACK-01/CLASS-13: class breakdown per curriculum item — which Training
// Classes still need each module. Loaded on-demand when the curriculum page
// is visited; re-renders the page once data arrives.
function _currClassBreakdownHtml(bd){
  if(!bd||!bd.length) return '';
  return '<div style="display:flex;flex-wrap:wrap;gap:3px;margin-top:5px">'+bd.map(c=>{
    const s=c.backlog_status||'';
    const cl=s==='resolved'?'b-ok':
              (s==='not_delivered')?'b-red':
              (s==='unscheduled'||s==='cancelled')?'b-amber':'b-blue';
    const label=s==='resolved'?'✓ ':s==='not_delivered'?'✕ ':s==='unscheduled'?'– ':'';
    return `<span class="badge ${cl}" style="font-size:var(--fs-2xs)" title="${esc(c.display_name)}: ${esc(s)}">${label}${esc(c.display_name)}</span>`;
  }).join('')+'</div>';
}
async function _loadCurriculumClassBreakdown(){
  const sqnId=(S.session&&S.session.squadron_id)||(typeof saBrowseSquadronId==='function'?saBrowseSquadronId():null);
  if(!sqnId) return;
  try{
    let yearId=P&&P.currentYearId;
    if(!yearId){
      const years=await api('/api/planning/years?unit_id='+encodeURIComponent(sqnId)).catch(()=>[]);
      const active=(years||[]).find(y=>y.active_status);
      if(!active) return;
      yearId=active.planning_year_id;
    }
    const data=await api('/api/planning/years/'+yearId+'/missions').catch(()=>null);
    if(!data) return;
    const byCode={};
    (data.missions||[]).forEach(m=>{if(m.class_breakdown&&m.class_breakdown.length)byCode[m.code]=m.class_breakdown;});
    if(!Object.keys(byCode).length) return;
    S.classByCode=byCode;
    renderCurr();
  }catch(_){}
}

function showCurrDetail(code){
  const e=allCurr().find(x=>x.code===code);if(!e)return;
  const sess=allSess().filter(s=>s.code===code);
  document.getElementById('cd-title').textContent=e.title;
  document.getElementById('cd-body').innerHTML=`
    <div style="display:flex;gap:7px;flex-wrap:wrap;margin-bottom:12px">${phBadge(e.phase)} ${elBadge(e.el)} <span class="badge b-blue">${esc(e.term||'—')}</span> <span class="badge b-grey">${e.hours}h</span> <span class="badge ${_PROGRAM_TYPE_CLASS[getProgramType(e.phase)]}">${getProgramType(e.phase)}</span></div>
    ${e.lh?`<div style="margin-bottom:12px"><a href="${safeUrl(e.lh)}" target="_blank" class="lh-btn" style="font-size:var(--fs-sm)">View on Learning Hub ↗</a></div>`:''}
    <div style="font-size:var(--fs-xs);margin-bottom:12px"><b>Instructor:</b> ${esc(e.instr||'—')}</div>
    ${sess.length?`
      <div style="font-size:var(--fs-2xs);font-weight:800;color:var(--steel);text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px">Scheduled Sessions (${sess.length})</div>
      <div class="tw"><table><thead><tr><th>Date</th><th>Phase</th><th>Facilitator</th><th>Room</th><th>Status</th><th class="no-print">Action</th></tr></thead>
      <tbody>${sess.map(s=>`<tr>
        <td>${fmtD(s.date,{day:'numeric',month:'short'})}</td>
        <td>${phBadge(s.phase)}</td>
        <td style="font-size:var(--fs-xs)">${esc(s.facName||'—')}</td>
        <td style="font-size:var(--fs-xs)">${esc(s.room||'—')}</td>
        <td>${stBadge(s.status)}</td>
        <td class="no-print">${canWriteSquadron()?`<button class="btn btn-xs btn-sky" onclick="quickEdit('${s.date}',${s.si});closeModal('m-curr-detail')">Edit</button>`:'—'}</td>
      </tr>`).join('')}</tbody></table></div>`
    :`<div class="alert a-warn">Not yet assigned to any parade night. <button class="btn btn-xs btn-sky no-print" onclick="closeModal('m-curr-detail');openAddPN()">Schedule →</button></div>`}`;
  openModal('m-curr-detail');
}
function drillCurr(code){
  const e=allCurr().find(x=>x.code===code);
  const sess=allSess().filter(s=>s.code===code);
  showDrill('curr-drill','curr-drill-title','curr-drill-body',(e?e.title:code)+' — Sessions',sess);
}
let _currSaveEndpoint='/api/curriculum';
function _hideCurrWingRow(){document.getElementById('c-wing-row').style.display='none';}
function _showCurrWingRow(){
  const row=document.getElementById('c-wing-row');
  const sel=document.getElementById('c-wing-id');
  sel.innerHTML=(S.wings||[]).map(w=>`<option value="${esc(w.wing_id)}">${esc(w.code)} — ${esc(w.name)}</option>`).join('');
  row.style.display='';
}
function _resetCurrModal(){
  ['c-code','c-title','c-lh','c-identifier'].forEach(id=>{const el=document.getElementById(id);if(el)el.value='';});
  const partEl=document.getElementById('c-part');if(partEl)partEl.value='1';
  document.getElementById('c-hours').value=1;
  const termEl=document.getElementById('c-term');if(termEl)termEl.value='';
  const newEl=document.getElementById('c-el-new');if(newEl)newEl.style.display='none';
}
function _setCurrTermOptional(optional){
  const lbl=document.getElementById('c-term-optional');
  if(lbl)lbl.textContent=optional?' (optional)':'';
}
async function _populateCurrElements(){
  const sel=document.getElementById('c-el');if(!sel)return;
  try{
    const els=await api('/api/curriculum/elements');
    sel.innerHTML='<option value="">— select element —</option>';
    (els||[]).forEach(e=>{const o=new Option(e.display_name||e.name,e.name);sel.appendChild(o);});
    sel.innerHTML+='';
  }catch(_){
    // fallback to built-in list if API unavailable
    sel.innerHTML=`<option value="">— select element —</option>
      <option value="Air_Space">Air &amp; Space</option>
      <option value="Drill">Drill</option><option value="Field">Field Skills</option>
      <option value="Personal_Dev">Personal Dev / PDL</option>
      <option value="Service_Community">Service &amp; Community</option>
      <option value="SQN_Affairs">SQN Affairs</option>`;
  }
}
function openCreateElementInline(){
  const el=document.getElementById('c-el-new');
  if(el){el.style.display='block';document.getElementById('c-el-new-name').focus();}
}
async function doCreateElementInline(){
  const nameInput=document.getElementById('c-el-new-name');
  const msgEl=document.getElementById('c-el-new-msg');
  const name=(nameInput.value||'').trim();
  if(!name){msgEl.textContent='Element name is required.';return;}
  msgEl.textContent='';
  try{
    const r=await api('/api/curriculum/elements',{method:'POST',body:{
      name,display_name:name.replace(/_/g,' '),scope_level:'national'
    }});
    // Reload element list and select the new one
    await _populateCurrElements();
    const sel=document.getElementById('c-el');
    if(sel)sel.value=r.name||name;
    document.getElementById('c-el-new').style.display='none';
    nameInput.value='';
  }catch(e){msgEl.textContent=apiErr(e);}
}
// Master transformation plan Block 10: Phase was previously a hardcoded
// <select> baked into this file's HTML — no wing/squadron could ever add a
// custom phase, and national admins had no way to extend the list without a
// code change. This mirrors _populateCurrElements()'s governed-catalogue
// pattern exactly, including the same offline fallback to the 8 built-in
// names so the form still works if /api/curriculum/phases is unreachable.
async function _populateCurrPhases(){
  const sel=document.getElementById('c-phase');if(!sel)return;
  const prev=sel.value;
  try{
    const phases=await api('/api/curriculum/phases');
    sel.innerHTML='';
    (phases||[]).forEach(p=>{const o=new Option(p.display_name||p.name,p.name);sel.appendChild(o);});
  }catch(_){
    // fallback to built-in list if API unavailable
    sel.innerHTML=`<option value="A. Orientation">A. Orientation</option><option value="B. Initial">B. Initial</option>
      <option value="C. Junior">C. Junior</option><option value="D. Intermediate">D. Intermediate</option>
      <option value="E. Senior">E. Senior</option><option value="I. Bronze">I. Bronze</option>
      <option value="J. Silver">J. Silver</option><option value="K. Gold">K. Gold</option>`;
  }
  if(prev && [...sel.options].some(o=>o.value===prev)) sel.value=prev;
}
function openCreatePhaseInline(){
  const el=document.getElementById('c-phase-new');
  if(el){el.style.display='block';document.getElementById('c-phase-new-name').focus();}
}
async function doCreatePhaseInline(){
  const nameInput=document.getElementById('c-phase-new-name');
  const msgEl=document.getElementById('c-phase-new-msg');
  const name=(nameInput.value||'').trim();
  if(!name){msgEl.textContent='Phase name is required.';return;}
  msgEl.textContent='';
  // DEFECT-001 (general-release qualification): this used to always send
  // scope_level:'national', so a Squadron Admin's own "+ New" click always
  // hit the national-only check and returned "Access not permitted" — the
  // backend was correct (sqn_admin was never authorised to create a
  // NATIONAL phase), the bug was sending the wrong scope for the caller.
  // effectiveScope() already resolves 'squadron' for a wing/national admin
  // with an active Proxy/Delegated Intervention session, so this also
  // creates the phase in the correct acting squadron automatically.
  const es=effectiveScope();
  const scopeLevel = es==='squadron' ? 'squadron' : es==='wing' ? 'wing' : 'national';
  try{
    const r=await api('/api/curriculum/phases',{method:'POST',body:{
      name,display_name:name,scope_level:scopeLevel
    }});
    // Reload phase list and select the new one
    await _populateCurrPhases();
    const sel=document.getElementById('c-phase');
    if(sel)sel.value=r.name||name;
    document.getElementById('c-phase-new').style.display='none';
    nameInput.value='';
    // POST /curriculum/phases is idempotent on name+scope and returns the existing
    // row with existed:true. Nothing read that, so a second stage with a name
    // already in use silently selected the first one and looked like "you can only
    // create one training stage" (reported 2026-08-25).
    if(r&&r.existed){
      showToast('A training stage named "'+name+'" already exists at this level, so it was selected rather than created again.',true);
    }else{
      showToast('Training stage created.');
    }
  }catch(e){msgEl.textContent=apiErr(e);}
}
function openAddCurr(){
  editCurrCode=null;_currSaveEndpoint='/api/curriculum';_hideCurrWingRow();
  document.getElementById('curr-modal-title').textContent='+ Add Squadron Curriculum';
  _resetCurrModal();_setCurrTermOptional(false);_populateCurrElements();_populateCurrPhases();openModal('m-add-curr');
}
function openAddCurrWing(){
  editCurrCode=null;_currSaveEndpoint='/api/curriculum/wing';
  document.getElementById('curr-modal-title').textContent='+ Add Wing Curriculum';
  _resetCurrModal();_setCurrTermOptional(true);_populateCurrElements();_populateCurrPhases();
  if(S.isNational) _showCurrWingRow(); else _hideCurrWingRow();
  openModal('m-add-curr');
}
function openAddCurrNat(){
  editCurrCode=null;_currSaveEndpoint='/api/curriculum/national';_hideCurrWingRow();
  document.getElementById('curr-modal-title').textContent='+ Add National Curriculum';
  _resetCurrModal();_setCurrTermOptional(true);_populateCurrElements();_populateCurrPhases();openModal('m-add-curr');
}
async function editCurr(code){
  const e=S.curr.find(x=>x.code===code&&canEditCurr(x));if(!e){showToast('You do not have permission to edit this curriculum item.',true);return;}
  editCurrCode=code;
  // Set the correct save endpoint for the owning level
  if(e.owningLevel==='national') _currSaveEndpoint='/api/curriculum/national';
  else if(e.owningLevel==='wing') _currSaveEndpoint='/api/curriculum/wing';
  else _currSaveEndpoint='/api/curriculum';
  document.getElementById('curr-modal-title').textContent='Edit Curriculum Item';
  document.getElementById('c-code').value=e.code;document.getElementById('c-title').value=e.title;
  // Await both governed-catalogue populates before setting values — the
  // select must contain e.phase's/e.el's option before .value can select it
  // (previously phase was a hardcoded <select> that always had every option
  // present; now it's populated from /api/curriculum/phases, so this must
  // finish first, same as the existing element select already requires).
  await Promise.all([_populateCurrPhases(), _populateCurrElements()]);
  const phaseSel=document.getElementById('c-phase');
  // A historical item's phase may predate the governed catalogue (free-text
  // data is never retroactively rejected, per the catalogue's own design) —
  // add it as a one-off option rather than silently switching the item to
  // whatever option happens to be first when Save is clicked.
  if(e.phase && ![...phaseSel.options].some(o=>o.value===e.phase)){
    phaseSel.appendChild(new Option(e.phase+' (not in catalogue)', e.phase));
  }
  phaseSel.value=e.phase;document.getElementById('c-el').value=e.el||'';
  document.getElementById('c-term').value=e.term||'';document.getElementById('c-lh').value=e.lh||'';
  document.getElementById('c-hours').value=e.hours||1;
  const instrEl=document.getElementById('c-instr');if(instrEl)instrEl.value=e.instr||'Staff';
  openModal('m-add-curr');
}
async function saveCurr(){
  const code=document.getElementById('c-code').value.trim();
  const title=document.getElementById('c-title').value.trim();
  const identifierEl=document.getElementById('c-identifier');
  const identifier=identifierEl?identifierEl.value.trim()||null:null;
  const partEl=document.getElementById('c-part');
  const partNumber=partEl?parseInt(partEl.value||'1',10)||1:1;
  if(!code||!title){showToast('Code and title required.',true);return;}
  const payload={title,phase:document.getElementById('c-phase').value,
    element:document.getElementById('c-el').value||null,
    recommended_term:document.getElementById('c-term').value||null,
    learning_hub_url:document.getElementById('c-lh').value||null,
    duration_minutes:(+document.getElementById('c-hours').value||1)*60,
    identifier,part_number:partNumber};
  // TRGO-06: give visible saving feedback -- this save previously went
  // silent for the whole network round-trip with no indication anything
  // was happening, unlike the session-edit and planning-drawer save flows.
  const btn=document.getElementById('c-save-btn');
  const btnLabel=btn?btn.textContent:'Save';
  if(btn){btn.disabled=true;btn.textContent='Saving…';}
  try{
    if(editCurrCode){
      const existing=S.curr.find(e=>e.code===editCurrCode&&canEditCurr(e));
      if(!existing||!existing.id){showToast('Curriculum item not found — refresh and try again.',true);return;}
      await api('/api/curriculum/'+existing.id,{method:'PATCH',body:JSON.stringify(payload)});
    } else {
      // Uniqueness is by identifier (if set) or (code, part_number) — NOT code alone.
      const dup=allCurr().find(e=>identifier?e.identifier===identifier:(e.code===code&&(e.partNumber||1)===partNumber));
      if(dup){showToast('A curriculum item with this code already exists.',true);return;}
      if(_currSaveEndpoint==='/api/curriculum/wing'&&S.isNational){
        const wid=document.getElementById('c-wing-id').value;
        if(!wid){showToast('Select a Wing.',true);return;}
        payload.wing_id=wid;
      }
      await api(_currSaveEndpoint,{method:'POST',body:JSON.stringify({code,...payload})});
    }
    editCurrCode=null;
    await reloadAndRender(); closeModal('m-add-curr');
    document.getElementById('curr-modal-title').textContent='+ Add Curriculum Item';
  }catch(e){
    // Show human-readable error; 409 now includes a message field
    showToast(apiErr(e),true);
  }finally{
    if(btn){btn.disabled=false;btn.textContent=btnLabel;}
  }
}
async function deleteCurrItem(id){
  confirmAction('Archive this curriculum item? Sessions already linked are not affected, and this can be undone from "Show archived".',async()=>{
    try{ await api('/api/curriculum/'+id,{method:'DELETE'}); await reloadAndRender(); }
    catch(e){ showToast(apiErr(e),true); }
  });
}
