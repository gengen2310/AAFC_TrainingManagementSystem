// Main TMS module: Cadet Management -- roster, class membership, Training
// Records matrix, CEA member import and training-records export.
// Extracted verbatim from connected-frontend/index.html (stabilisation Phase 4,
// C6). Top-level function declarations and side-effect-free let/const only;
// loaded as a classic script BEFORE the inline bootstrap, so everything here
// is defined before any page-load code runs. Statements with load-time
// effects stay in index.html in their original order. Parity is proven by
// tools/architecture/frontend_parity.mjs.

// ═══════════════════════════════════════════════════════════
// CADETS — Roster management
// ═══════════════════════════════════════════════════════════
async function initCadetsPage(){
  // Populate class selector
  const sel=document.getElementById('cadets-class-select');
  if(!sel)return;
  sel.innerHTML='<option value="">— Select class —</option>';
  try{
    const years=await api('/api/planning/years');
    const yearList=Array.isArray(years)?years:(years.planning_years||[]);
    for(const yr of yearList){
      const classes=await api(`/api/training-classes?training_year_id=${yr.planning_year_id}`);
      const cl=Array.isArray(classes)?classes:(classes.training_classes||[]);
      for(const c of cl){
        const opt=document.createElement('option');
        opt.value=c.training_class_id||c.id;
        opt.textContent=esc(c.display_name)+(yr.year?` (${yr.year})`:'');
        sel.appendChild(opt);
      }
    }
  }catch(e){console.warn('initCadetsPage: class load failed',e);}
}

async function loadCadetRoster(){
  const sel=document.getElementById('cadets-class-select');
  const wrap=document.getElementById('cadets-roster-wrap');
  if(!sel||!wrap)return;
  const classId=sel.value;
  if(!classId){wrap.innerHTML='<p class="muted" style="font-size:var(--fs-sm)">Select a Training Class above to view cadets.</p>';return;}
  wrap.innerHTML='<p class="muted">Loading…</p>';
  try{
    const data=await api(`/api/training-classes/${classId}/roster`);
    const cadets=data.cadets||[];
    const className=data.class_name||'';
    document.getElementById('cadets-sub').textContent=className?`Roster for ${className}`:'Cadet Management';
    if(cadets.length===0){
      wrap.innerHTML='<p class="muted" style="font-size:var(--fs-sm)">No cadets in this class. Use <b>Add Cadet</b> to enrol cadets.</p>';
      return;
    }
    const canWrite=S.role!=='sqn_general';
    wrap.innerHTML=`<div class="tw"><table>
      <thead><tr>
        ${canWrite?'<th class="no-print" style="width:32px"><input type="checkbox" id="roster-check-all" onchange="(function(v){document.querySelectorAll(\'#cadets-roster-wrap .roster-row-check\').forEach(cb=>cb.checked=v);})(this.checked)"></th>':''}
        <th>CEA Number</th><th>Rank</th><th>Last Name</th><th>First Name</th><th>Status</th>
        ${canWrite?'<th class="no-print">Actions</th>':''}
      </tr></thead>
      <tbody>${cadets.map(c=>`<tr>
        ${canWrite?`<td class="no-print"><input type="checkbox" class="roster-row-check" data-cadet-id="${esc(c.cadet_id||c.id)}"></td>`:''}
        <td style="font-family:monospace;font-size:var(--fs-xs)">${esc(c.service_number||'')}</td>
        <td>${esc(c.rank||'')}</td>
        <td>${esc(c.last_name||'')}</td>
        <td>${esc(c.first_name||'')}</td>
        <td>${c.active_status?'Active':'Inactive'}</td>
        ${canWrite?`<td class="no-print"><button class="btn btn-danger btn-xs" onclick="removeCadetFromClass('${esc(classId)}','${esc(c.cadet_id||c.id)}',this)">Remove from Class</button></td>`:''}
      </tr>`).join('')}</tbody>
    </table></div>
    ${canWrite?`<div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap">
      <button class="btn btn-primary btn-sm" onclick="openAddCadetModal()">Add Cadet</button>
      <button class="btn btn-out btn-sm" onclick="bulkAddCadetsToClass('${esc(classId)}')">Add to Class</button>
      <button class="btn btn-out btn-sm" onclick="moveCadetsToClass('${esc(classId)}')">Move to Class</button>
    </div>`:''}`;
  }catch(e){wrap.innerHTML=`<p class="warn">${esc(apiErr(e))}</p>`;}
}

function removeCadetFromClass(classId,cadetId,btn){
  confirmAction('Remove this cadet from the class? The cadet record is not deleted.',async()=>{
    btn.disabled=true;
    try{
      await api(`/api/training-classes/${classId}/bulk-membership`,{method:'POST',body:JSON.stringify({action:'remove',cadet_ids:[cadetId]})});
      loadCadetRoster();
    }catch(e){showToast(apiErr(e),true);btn.disabled=false;}
  });
}

async function bulkAddCadetsToClass(classId){
  const ids=await promptText('Add Cadets to Class','Service numbers (comma-separated)',{okLabel:'Add'});
  if(!ids||!ids.trim())return;
  const snList=ids.split(',').map(s=>s.trim()).filter(Boolean);
  // Resolve service numbers to cadet IDs
  try{
    const allCadets=await api('/api/cadets');
    const cadetIds=snList.map(sn=>{
      const found=allCadets.find(c=>c.service_number===sn);
      return found?(found.cadet_id||found.id):null;
    }).filter(Boolean);
    if(cadetIds.length===0){showToast('No matching cadets found for the entered service numbers.',true);return;}
    await api(`/api/training-classes/${classId}/bulk-membership`,{method:'POST',body:JSON.stringify({action:'add',cadet_ids:cadetIds})});
    loadCadetRoster();
  }catch(e){showToast(apiErr(e),true);}
}

async function moveCadetsToClass(fromClassId){
  // Get cadets selected via checkboxes
  const checked=Array.from(document.querySelectorAll('#cadets-roster-wrap .roster-row-check:checked'));
  const cadetIds=checked.map(cb=>cb.dataset.cadetId).filter(Boolean);
  if(cadetIds.length===0){showToast('Select cadets to move using the row checkboxes first.',true);return;}

  // Load available classes for this squadron so the officer can pick by name
  let classes=[];
  try{
    const years=await api('/api/planning/years');
    const yearList=Array.isArray(years)?years:(years.planning_years||[]);
    for(const yr of yearList){
      const cls=await api(`/api/training-classes?training_year_id=${yr.planning_year_id}`);
      const cl=Array.isArray(cls)?cls:(cls.training_classes||[]);
      classes.push(...cl.filter(c=>(c.training_class_id||c.id)!==fromClassId));
    }
  }catch(e){showToast(apiErr(e),true);return;}
  if(classes.length===0){showToast('No other Training Classes available to move to.',true);return;}

  const opts=classes.map((c,i)=>`${i+1}: ${c.display_name}`).join('\n');
  const choice=await promptText('Move Cadets',`Select a target Training Class (enter number):\n${opts}`,{okLabel:'Select'});
  if(!choice)return;
  const idx=parseInt(choice,10)-1;
  if(isNaN(idx)||idx<0||idx>=classes.length){showToast('Invalid selection.',true);return;}
  const target_class_id=classes[idx].training_class_id||classes[idx].id;

  try{
    await api(`/api/training-classes/${fromClassId}/bulk-membership`,{method:'POST',body:JSON.stringify({action:'move',cadet_ids:cadetIds,target_class_id})});
    loadCadetRoster();
  }catch(e){showToast(apiErr(e),true);}
}

async function openAddCadetModal(){
  // Open a form to create a new Cadet record (not to add an existing one to a class).
  // Uses promptText() in place of native prompt() so the flow is keyboard-accessible
  // and compatible with browser automation (HARD-09).
  const sel=document.getElementById('cadets-class-select');
  const classId=sel?sel.value:'';
  const sn=await promptText('Add Cadet','CEA number (service number)',{okLabel:'Next'});
  if(!sn||!sn.trim())return;
  const rank=await promptText('Add Cadet','Rank (e.g. Cdt)',{defaultValue:'Cdt',okLabel:'Next'});
  if(rank===null)return;
  const firstName=await promptText('Add Cadet','First name',{okLabel:'Next'});
  if(!firstName||!firstName.trim())return;
  const lastName=await promptText('Add Cadet','Last name',{okLabel:'Create Cadet'});
  if(!lastName||!lastName.trim())return;
  try{
    const cadet=await api('/api/cadets',{method:'POST',body:JSON.stringify({service_number:sn.trim(),rank:rank||'Cdt',first_name:firstName.trim(),last_name:lastName.trim()})});
    const cadetId=cadet.cadet_id||cadet.id;
    if(classId&&cadetId){
      await api(`/api/training-classes/${classId}/bulk-membership`,{method:'POST',body:JSON.stringify({action:'add',cadet_ids:[cadetId]})});
    }
    await loadCadetRoster();
  }catch(e){showToast(apiErr(e),true);}
}

// ═══════════════════════════════════════════════════════════
// TRAINING RECORDS — Matrix view
// ═══════════════════════════════════════════════════════════
async function initTrainingRecordsPage(){
  const sel=document.getElementById('tr-class-select');
  if(!sel)return;
  sel.innerHTML='<option value="">— Select class —</option>';
  try{
    const years=await api('/api/planning/years');
    const yearList=Array.isArray(years)?years:(years.planning_years||[]);
    for(const yr of yearList){
      const classes=await api(`/api/training-classes?training_year_id=${yr.planning_year_id}`);
      const cl=Array.isArray(classes)?classes:(classes.training_classes||[]);
      for(const c of cl){
        const opt=document.createElement('option');
        opt.value=c.training_class_id||c.id;
        opt.textContent=esc(c.display_name)+(yr.year?` (${yr.year})`:'');
        sel.appendChild(opt);
      }
    }
  }catch(e){console.warn('initTrainingRecordsPage: class load failed',e);}
}

async function loadTrainingRecords(){
  const sel=document.getElementById('tr-class-select');
  const wrap=document.getElementById('tr-matrix-wrap');
  if(!sel||!wrap)return;
  const classId=sel.value;
  if(!classId){wrap.innerHTML='<p class="muted" style="font-size:var(--fs-sm)">Select a Training Class above to view the training matrix.</p>';return;}
  wrap.innerHTML='<p class="muted">Loading…</p>';
  try{
    const data=await api(`/api/training-records?class_id=${classId}`);
    const items=data.curriculum_items||[];
    const rows=data.rows||[];
    if(items.length===0||rows.length===0){
      wrap.innerHTML='<p class="muted" style="font-size:var(--fs-sm)">No data available for this class.</p>';
      return;
    }
    // Build matrix header
    const headerCells=items.map(ci=>`<th style="font-size:var(--fs-2xs);max-width:80px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(ci.title)}">${esc(ci.code||ci.title)}</th>`).join('');
    // Build matrix rows
    const bodyRows=rows.map(r=>{
      const cells=items.map(ci=>{
        const cell=r.cells&&r.cells[ci.curriculum_item_id||ci.id];
        const status=cell&&cell.status;
        const date=cell&&(cell.completion_date||cell.parade_date);
        if(status==='completed'&&date){
          const fmt=_fmtDate(date);
          return `<td style="background:var(--ok-bg);color:var(--ok-text);text-align:center;font-size:var(--fs-2xs);font-weight:600" title="Completed ${esc(date)}" aria-label="Completed ${esc(fmt)}">${esc(fmt)}</td>`;
        }else if(status==='absent'){
          return `<td style="background:var(--warn-bg);color:var(--warn-text);text-align:center;font-size:var(--fs-2xs)">Absent</td>`;  /* G1: --warn on --warn-bg=2.98:1(fail); --warn-text=5.4:1(pass) */
        }else if(status==='not_completed'){
          return `<td style="text-align:center;color:var(--muted);font-size:var(--fs-2xs)">Not done</td>`;
        }else{
          return `<td style="text-align:center;color:var(--muted);font-size:var(--fs-2xs)">—</td>`;
        }
      }).join('');
      return `<tr>
        <td style="font-size:var(--fs-sm);white-space:nowrap"><a href="#" onclick="showCadetTrainingRecord('${esc(r.cadet_id)}');return false">${esc(r.rank||'')} ${esc(r.last_name||'')}</a></td>
        ${cells}
      </tr>`;
    }).join('');
    wrap.innerHTML=`<div class="tw" style="overflow-x:auto"><table style="font-size:var(--fs-sm)">
      <thead><tr><th style="min-width:120px">Cadet</th>${headerCells}</tr></thead>
      <tbody>${bodyRows}</tbody>
    </table></div>`;
  }catch(e){wrap.innerHTML=`<p class="warn">${esc(apiErr(e))}</p>`;}
}

async function showCadetTrainingRecord(cadetId){
  try{
    const data=await api(`/api/cadets/${cadetId}/training-record`);
    const name=`${data.rank||''} ${data.last_name||''}, ${data.first_name||''}`.trim();
    const service_number=data.service_number||'';
    const memberships=data.memberships||[];
    let html=`<b>${esc(name)}</b>`;
    if(service_number) html+=` <span style="font-family:monospace;font-size:var(--fs-xs);color:var(--muted)">${esc(service_number)}</span>`;
    html+=`<br>`;
    // Current and historical class memberships
    if(memberships.length){
      html+=`<p style="font-size:var(--fs-xs);color:var(--muted);margin:4px 0">Classes: ${memberships.map(m=>`${esc(m.display_name)}${m.active_status?' (active)':' (past)'}`).join(', ')}</p>`;
    }
    for(const phase of (data.phases||[])){
      html+=`<b style="font-size:var(--fs-sm)">${esc(phase.name)}</b><ul style="margin:4px 0 8px 16px;padding:0">`;
      for(const item of (phase.items||[])){
        const summary_completion_date=item.summary_completion_date;
        const dateStr=summary_completion_date
          ?`<span style="color:var(--ok-text)" aria-label="Completed ${esc(summary_completion_date)}">Completed ${esc(summary_completion_date)}</span>`
          :'<span style="color:var(--muted)">—</span>';
        html+=`<li style="font-size:var(--fs-xs);margin:2px 0">${esc(item.code||'')}${item.code?': ':''}${esc(item.title)} — ${dateStr}`;
        // Show all delivery attempts
        const attempts=item.attempts||[];
        if(attempts.length>0){
          html+=`<ul style="margin:2px 0 2px 12px">`;
          for(const a of attempts){
            html+=`<li style="font-size:var(--fs-2xs);color:var(--muted)">${esc(a.parade_night_date||'')} — ${esc(a.status||'')}${a.training_class?' · '+esc(a.training_class):''}</li>`;
          }
          html+=`</ul>`;
        }
        html+=`</li>`;
      }
      html+='</ul>';
    }
    // Show in a simple modal or alert
    const overlay=document.getElementById('modal-overlay');
    const body=document.getElementById('modal-body');
    if(overlay&&body){body.innerHTML=html;overlay.style.display='flex';}
    else{showToast(name+' — see browser console for full record.',false);}
  }catch(e){showToast(apiErr(e),true);}
}

// ═══════════════════════════════════════════════════════════
// CEA MEMBER IMPORT — preview / commit / rollback
// ═══════════════════════════════════════════════════════════
let _ceaBatchId=null;

function showCadetSubview(view, button){
  if(view==='cea'&&!canWritePlan()){
    view='roster';
    button=document.getElementById('cadets-tab-roster');
  }
  const roster=document.getElementById('cadets-roster-wrap');
  const cea=document.getElementById('cadets-cea-wrap');
  const source=document.getElementById('page-cea-import');
  if(!roster||!cea)return;
  document.querySelectorAll('#page-cadets [role="tab"]').forEach(tab=>{
    const active=tab===button;
    tab.classList.toggle('active',active);
    tab.setAttribute('aria-selected',String(active));
  });
  if(view==='cea'){
    if(source && source.parentElement!==cea){
      Array.from(source.children).forEach(child=>cea.appendChild(child));
    }
    roster.style.display='none';
    cea.style.display='';
    initCeaImportPage();
  }else{
    roster.style.display='';
    cea.style.display='none';
  }
}

function initCeaImportPage(){
  // Reset state when navigating to the page
  _ceaBatchId=null;
  document.getElementById('cea-preview-wrap').style.display='none';
  document.getElementById('cea-result-wrap').style.display='none';
  document.getElementById('cea-preview-status').textContent='';
  document.getElementById('cea-commit-status').textContent='';
  document.getElementById('cea-rollback-status').textContent='';
}

async function ceaPreview(){
  const csvText=(document.getElementById('cea-csv-input').value||'').trim();
  const statusEl=document.getElementById('cea-preview-status');
  if(!csvText){statusEl.style.color='var(--red)';statusEl.textContent='Paste a CEA export CSV first.';return;}
  statusEl.style.color='var(--muted)';statusEl.textContent='Previewing…';
  try{
    const data=await api('/api/import/cea-members/preview',{method:'POST',body:{csv_text:csvText,file_name:'manual-paste.csv'}});
    statusEl.style.color='var(--muted)';statusEl.textContent=`${data.row_count} rows parsed.`;
    _renderCeaPreview(data);
  }catch(e){
    let msg=apiErr(e);
    // Append received columns to missing-columns errors so the operator can see what the parser found
    if(e&&e.code==='missing_required_columns'&&e.body&&e.body.detail&&e.body.detail.received_columns){
      const got=(e.body.detail.received_columns||[]).join(', ')||'(none detected)';
      msg+=' Columns found: '+got+'.';
    }
    statusEl.style.color='var(--red)';statusEl.textContent=msg;
  }
}

function _renderCeaPreview(data){
  const wrap=document.getElementById('cea-preview-wrap');
  const tbody=document.getElementById('cea-preview-tbody');
  const badges=document.getElementById('cea-summary-badges');

  // Summary badges
  const badgeMap=[
    {key:'new_count',label:'NEW',color:'var(--ok-text)',bg:'var(--ok-bg)'},
    {key:'update_count',label:'UPDATE',color:'var(--warn-text)',bg:'var(--warn-bg)'},  /* G1: --warn on --warn-bg=2.98:1(fail); --warn-text=5.4:1(pass); mirrors ok_text/ok_bg pattern */
    {key:'unchanged_count',label:'UNCHANGED',color:'var(--muted)',bg:'var(--surface-2)'},
    {key:'error_count',label:'ERROR',color:'var(--red)',bg:'#fde8ec'},
  ];
  badges.innerHTML=badgeMap.filter(b=>data[b.key]>0).map(b=>
    `<span style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:var(--fs-xs);font-weight:700;background:${b.bg};color:${b.color}">${b.label}: ${data[b.key]}</span>`
  ).join('');

  // Row table
  const rows=data.rows||[];
  tbody.innerHTML=rows.map(r=>{
    const actionColor={NEW:'var(--ok-text)',UPDATE:'var(--warn)',UNCHANGED:'var(--muted)',ERROR:'var(--red)'}[r.action]||'var(--text)';
    const actionBg={NEW:'var(--ok-bg)',UPDATE:'var(--warn-bg)',UNCHANGED:'',ERROR:'#fde8ec'}[r.action]||'';
    return `<tr style="${actionBg?'background:'+actionBg:''}">
      <td style="font-size:var(--fs-xs);color:var(--muted)">${r.row||r.row_number||''}</td>
      <td style="font-family:monospace;font-size:var(--fs-xs)">${esc(r.service_number||r.id||'')}</td>
      <td style="font-size:var(--fs-xs)">${esc(r.rank||'')}</td>
      <td style="font-size:var(--fs-sm)">${esc(r.first_name||'')} ${esc(r.last_name||'')}</td>
      <td><span style="font-size:var(--fs-xs);font-weight:700;color:${actionColor}">${esc(r.action||'')}</span></td>
      <td style="font-size:var(--fs-xs);color:var(--muted)">${esc(r.detail||r.error||'')}</td>
    </tr>`;
  }).join('');

  // Show/hide commit button based on whether there's anything to commit
  const hasWork=(data.new_count||0)+(data.update_count||0)>0;
  document.getElementById('cea-commit-btn').disabled=!hasWork;
  wrap.style.display='';
  document.getElementById('cea-result-wrap').style.display='none';
  _ceaBatchId=null;
}

function ceaCommit(){
  const csvText=(document.getElementById('cea-csv-input').value||'').trim();
  const statusEl=document.getElementById('cea-commit-status');
  if(!csvText){statusEl.style.color='var(--red)';statusEl.textContent='No CSV data to commit.';return;}
  confirmAction('Commit this import? Cadets will be created or updated in the database. You can rollback afterwards if needed.',async()=>{
    statusEl.style.color='var(--muted)';statusEl.textContent='Committing…';
    document.getElementById('cea-commit-btn').disabled=true;
    try{
      const data=await api('/api/import/cea-members/commit',{method:'POST',body:{csv_text:csvText,file_name:'manual-paste.csv'}});
      _ceaBatchId=data.batch_id||null;
      statusEl.textContent='';
      _renderCeaResult(data);
    }catch(e){statusEl.textContent='';document.getElementById('cea-commit-btn').disabled=false;statusEl.style.color='var(--red)';statusEl.textContent=apiErr(e);}
  });
}

function _renderCeaResult(data){
  const wrap=document.getElementById('cea-result-wrap');
  const body=document.getElementById('cea-result-body');
  const rollbackBtn=document.getElementById('cea-rollback-btn');
  body.innerHTML=`<p style="font-size:var(--fs-base)">
    Import complete:
    <strong>${data.new_count||data.new||0}</strong> created,
    <strong>${data.update_count||data.updated||0}</strong> updated,
    <strong>${data.unchanged||0}</strong> unchanged,
    <strong>${data.errors||0}</strong> errors.
    ${_ceaBatchId?`<span style="color:var(--muted);font-size:var(--fs-xs)">Batch ID: ${esc(_ceaBatchId)}</span>`:''}
  </p>`;
  rollbackBtn.style.display=_ceaBatchId?'':'none';
  document.getElementById('cea-preview-wrap').style.display='none';
  wrap.style.display='';
}

function ceaRollback(){
  const statusEl=document.getElementById('cea-rollback-status');
  if(!_ceaBatchId){statusEl.style.color='var(--red)';statusEl.textContent='No batch ID — cannot rollback.';return;}
  confirmAction('Rollback this import? Newly created cadets will be archived and updated cadets will have their previous rank/name restored.',async()=>{
    statusEl.style.color='var(--muted)';statusEl.textContent='Rolling back…';
    document.getElementById('cea-rollback-btn').disabled=true;
    try{
      const data=await api(`/api/import/cea-members/rollback?batch_id=${encodeURIComponent(_ceaBatchId)}`,{method:'POST'});
      statusEl.textContent='';
      const body=document.getElementById('cea-result-body');
      body.innerHTML+=`<p style="font-size:var(--fs-base);color:var(--ok-text)">
        Rollback complete: <strong>${data.new_archived||0}</strong> archived, <strong>${data.updated_restored||0}</strong> restored.
      </p>`;
      document.getElementById('cea-rollback-btn').style.display='none';
      _ceaBatchId=null;
    }catch(e){statusEl.textContent='';document.getElementById('cea-rollback-btn').disabled=false;statusEl.style.color='var(--red)';statusEl.textContent=apiErr(e);}
  },true);
}

function ceaReset(){
  _ceaBatchId=null;
  document.getElementById('cea-csv-input').value='';
  document.getElementById('cea-preview-wrap').style.display='none';
  document.getElementById('cea-result-wrap').style.display='none';
  document.getElementById('cea-preview-status').textContent='';
  document.getElementById('cea-commit-status').textContent='';
  document.getElementById('cea-rollback-status').textContent='';
}

async function exportTrainingRecords(){
  const sel=document.getElementById('tr-class-select');
  const classId=sel?sel.value:'';
  if(!classId){showToast('Select a Training Class first.',true);return;}
  const headers={'Content-Type':'application/json'};
  const t=tokenGet(); if(t)headers['Authorization']='Bearer '+t;
  try{
    const res=await fetch(API_BASE+'/api/training-records/export?class_id='+encodeURIComponent(classId),{headers,credentials:'include'});
    if(!res.ok){showToast('Export failed: '+(res.status),true);return;}
    const blob=await res.blob();
    const url=URL.createObjectURL(blob);
    const a=document.createElement('a');
    a.href=url; a.download='training-records.csv'; a.click();
    setTimeout(()=>URL.revokeObjectURL(url),10000);
  }catch(e){showToast(apiErr(e),true);}
}
