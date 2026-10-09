// Main TMS module: Training Classes -- unit-settings list, CRUD, progress,
// custom training phases, split/merge.
// Extracted verbatim from connected-frontend/index.html (stabilisation Phase 4,
// C6). Top-level function declarations and side-effect-free let/const only;
// loaded as a classic script BEFORE the inline bootstrap, so everything here
// is defined before any page-load code runs. Statements with load-time
// effects stay in index.html in their original order. Parity is proven by
// tools/architecture/frontend_parity.mjs.

// ═══════════════════════════════════════════════════════════
//  TRAINING CLASSES IN UNIT SETTINGS
// ═══════════════════════════════════════════════════════════
async function _loadSettingsTrainingClasses(){
  const wrap=document.getElementById('settings-training-classes-wrap');
  if(!wrap)return;
  if(!['sqn_admin','sqn_general'].includes(S.role)){wrap.style.display='none';return;}
  wrap.style.display='block';
  const sel=document.getElementById('tc-year-sel');
  if(!sel)return;
  await _loadPlanningYears();
  sel.innerHTML='<option value="">— select year —</option>';
  (P.years||[]).forEach(y=>{
    const o=document.createElement('option');
    o.value=y.planning_year_id;
    o.textContent=(y.name||String(y.year))+(y.active_status?'':' (archived)');
    sel.appendChild(o);
  });
  const years=P.years||[];
  const selected=years.find(y=>y.planning_year_id===sel.value)
    ||years.find(y=>y.planning_year_id===P.currentYearId)
    ||years.find(y=>y.active_status)
    ||years[0];
  sel.value=selected?selected.planning_year_id:'';
  await _tcLoadForYear(sel.value);
}
function _tcLoadForYear(yearId){
  const card=document.getElementById('py-classes-card');
  if(!card)return;
  card.style.display='block';
  if(!yearId){
    const body=document.getElementById('py-classes-body');
    if(body)body.innerHTML='<p class="muted">Select a training year to view its classes.</p>';
    return Promise.resolve();
  }
  return _tcToggleShowArchived(yearId);
}

// ── Training Classes (CLASS-01/03/04/07) ─────────────────────────────────
// A Training Class is a Squadron-specific local group undertaking a Training
// Stage during a Training Year -- e.g. Senior 1 and Senior 2 both undertake
// the Senior Stage but are tracked, scheduled and progressed independently.
// First frontend surface for this backend capability -- list/create/edit/
// archive only; assigning a Class to a Session (SessionAudience) is not yet
// wired into the Parade Night Builder UI.

async function _populateTrainingClassStageSelect(selectId, selectedId){
  const sel=document.getElementById(selectId); if(!sel) return;
  try{
    const phases=await api('/api/curriculum/phases');
    sel.innerHTML='';
    (phases||[]).forEach(p=>{const o=new Option(p.display_name||p.name,p.phase_id);sel.appendChild(o);});
  }catch(_){ sel.innerHTML='<option value="">Could not load Training Stages</option>'; }
  if(selectedId && [...sel.options].some(o=>o.value===selectedId)) sel.value=selectedId;
}

// Keyed by training_class_id, refreshed on every render -- openEditTrainingClassModal
// looks the row up here by ID rather than having a full JSON object round-tripped
// through an inline onclick HTML attribute. JSON.stringify(c) embedded directly in
// an attribute is not attribute-escaped: a display_name containing a quote or a
// closing-tag-like sequence could break out of the attribute and inject markup --
// display_name is fully user-controlled free text. (Do not literally type the
// closing-script-tag sequence in this comment either -- an HTML parser ends a
// <script> block on that raw byte sequence anywhere in its content, comments and
// strings included, regardless of JS syntax; that exact mistake in an earlier
// draft of this comment silently truncated everything after it in the browser.)
let _tcById={};

// Renders a coverage-percentage pill for a Training Class row. Reuses the
// exact colour thresholds already established for chart insights elsewhere
// in this file (green ok / amber warn / red danger) rather than inventing a
// new palette.
function _tcCoveragePill(pct){
  if(pct==null) return '<span class="muted">—</span>';
  const bg = pct>=80?'var(--ok-bg)':pct>=50?'var(--warn-bg)':'#fde8ea';
  const fg = pct>=80?'var(--ok-text)':pct>=50?'#7a5200':'var(--red)';
  return `<span style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:var(--fs-2xs);font-weight:700;background:${bg};color:${fg}">${pct}%</span>`;
}

async function _renderTrainingClasses(yearId){
  const el=document.getElementById('py-classes-body'); if(!el) return;
  const showArchived=(document.getElementById('tc-show-archived')||{}).checked;
  // Canonical labels and sort order for auto-created classes (training_stage_id=null, stage_code set)
  const _CODE_LABEL={ORI:'Orientation',INI:'Initial',JNR:'Junior',INT:'Intermediate',SNR:'Senior'};
  const _CODE_ORDER={ORI:1,INI:2,JNR:3,INT:4,SNR:5};
  try{
    const rows=await api(`/api/training-classes?training_year_id=${encodeURIComponent(yearId)}${showArchived?'&include_archived=true':''}`);
    _tcById={};
    rows.forEach(c=>{ _tcById[c.training_class_id]=c; });
    if(!rows.length){ el.innerHTML=`<p class="muted">No ${showArchived?'archived ':''}Training Classes${showArchived?'':' set up for this year yet'}.</p>`; return; }
    // Group by effective stage key. Auto-created classes have training_stage_id=null
    // but a stage_code ("ORI","INI","JNR","INT","SNR"); use "__CODE__" prefix to
    // distinguish from real UUIDs and keep them out of the progress-API calls below.
    const byGroup={};
    rows.forEach(c=>{
      const key=c.training_stage_id||('__'+(c.stage_code||'NONE')+'__');
      (byGroup[key]=byGroup[key]||[]).push(c);
    });
    const canWrite=canWriteSquadron();
    const sqnId=S.currentSqnId||(S.session&&S.session.squadron_id);
    // CLASS-04: fetch stage-level progress only for groups with a real stage ID.
    const progressByGroup={};
    const realStageIds=Object.keys(byGroup).filter(k=>!k.startsWith('__'));
    if(sqnId&&!showArchived){
      await Promise.all(realStageIds.map(async sid=>{
        try{ progressByGroup[sid]=await api(`/api/curriculum/phases/${sid}/class-progress?squadron_id=${encodeURIComponent(sqnId)}`); }
        catch(_){ progressByGroup[sid]=null; }
      }));
    }
    // Sort groups: real stages by first class's class_number, code groups by canonical order, ungrouped last.
    const groupKeys=Object.keys(byGroup).sort((a,b)=>{
      const oA=a.startsWith('__')?(a==='__NONE__'?9999:(_CODE_ORDER[a.slice(2,-2)]||999)):(byGroup[a][0].class_number||0);
      const oB=b.startsWith('__')?(b==='__NONE__'?9999:(_CODE_ORDER[b.slice(2,-2)]||999)):(byGroup[b][0].class_number||0);
      return oA-oB;
    });
    const stageName=k=>{
      if(!k.startsWith('__')) return (progressByGroup[k]&&progressByGroup[k].stage_name)||'Stage';
      const code=k.slice(2,-2);
      return code==='NONE'?'No Stage':(_CODE_LABEL[code]||code);
    };
    // Build per-class coverage map from stage progress responses
    const pctByClass={};
    Object.values(progressByGroup).forEach(sp=>{
      if(sp&&sp.classes) sp.classes.forEach(cp=>{ pctByClass[cp.training_class_id]=cp.coverage_pct; });
    });
    const hasMergeTarget=(c,grp)=>grp.some(o=>o.training_class_id!==c.training_class_id);
    const rowActions=(c,grp)=>{
      if(c.is_archived) return canWrite?`<button class="btn btn-xs btn-ok" onclick="doRestoreTrainingClass('${esc(c.training_class_id)}','${esc(yearId)}')">Restore</button>`:'';
      const tid=esc(c.training_class_id);
      let btns=`<button class="btn btn-xs" onclick="openTrainingClassProgressModal('${tid}')" style="margin-right:4px">View Progress</button>`;
      if(canWrite) btns+=`<button class="btn btn-xs" onclick="openEditTrainingClassModal('${tid}')" style="margin-right:4px">Edit</button>`;
      if(canWrite) btns+=`<button class="btn btn-xs" onclick="openSplitTrainingClassModal('${tid}')" style="margin-right:4px">Split</button>`;
      if(canWrite&&hasMergeTarget(c,grp)) btns+=`<button class="btn btn-xs" onclick="openMergeTrainingClassModal('${tid}')" style="margin-right:4px">Merge into…</button>`;
      if(canWrite) btns+=`<button class="btn btn-xs btn-danger" onclick="archiveTrainingClass('${tid}','${esc(yearId)}')">Archive</button>`;
      return btns;
    };
    const cols=showArchived?4:5;
    let html=`<table class="data-table"><thead><tr><th>Class</th><th>Code</th><th style="text-align:right">Expected</th>${showArchived?'':'<th>Progress</th>'}<th></th></tr></thead><tbody>`;
    groupKeys.forEach(key=>{
      const grp=byGroup[key];
      const label=stageName(key);
      const spct=(!showArchived&&!key.startsWith('__')&&progressByGroup[key])
        ?progressByGroup[key].coverage_pct:null;
      html+=`<tr class="tc-stage-header"><td colspan="${cols}"><span class="tc-stage-label">${esc(label)}</span>${spct!=null?' '+_tcCoveragePill(spct):''}</td></tr>`;
      grp.sort((a,b)=>(a.class_number||0)-(b.class_number||0)).forEach(c=>{
        const tid=esc(c.training_class_id);
        html+=`<tr${c.is_archived?' class="tc-archived"':''}>
          <td>${esc(c.display_name)}${c.is_archived?' <span class="badge b-grey">Archived</span>':''}</td>
          <td>${c.stage_code?`<span class="badge">${esc(c.stage_code)}</span>`:'<span class="muted">—</span>'}</td>
          <td style="text-align:right">${c.expected_count!=null?esc(String(c.expected_count)):'—'}</td>
          ${showArchived?'':`<td>${_tcCoveragePill(pctByClass[c.training_class_id])}</td>`}
          <td style="white-space:nowrap;text-align:right">
            ${rowActions(c,grp)}
          </td>
        </tr>`;
      });
    });
    html+=`</tbody></table>`;
    el.innerHTML=html;
  } catch(e){ el.innerHTML='<p class="muted">Could not load Training Classes. Refresh the page to try again.</p>'; }
}

async function _tcToggleShowArchived(yearId){
  await _renderTrainingClasses(yearId);
}
async function doRestoreTrainingClass(cid, yearId){
  try{
    await api(`/api/training-classes/${cid}/restore`,{method:'POST'});
    showToast('Training Class restored.');
    await _renderTrainingClasses(yearId);
  } catch(e){ showToast('Could not restore: '+apiErr(e), true); }
}

// CLASS-04 dedicated UI: which curriculum requirements this specific
// Training Class has delivered/planned/not started, reusing
// _class_curriculum_progress (training.py) via
// GET /api/training-classes/{id}/curriculum-progress -- no new backend
// calculation, addendum §44.
const _TCP_STATUS_STYLE={
  delivered:{bg:'var(--ok-bg)',fg:'var(--ok-text)'},
  delivered_with_issue:{bg:'var(--warn-bg)',fg:'#7a5200'},
  planned:{bg:'var(--accent-light)',fg:'var(--dark)'},
  not_delivered:{bg:'#fde8ea',fg:'var(--red)'},
  cancelled:{bg:'#fde8ea',fg:'var(--red)'},
  rescheduled:{bg:'#f1e8fd',fg:'#5b21b6'},
  not_started:{bg:'var(--surface-2)',fg:'var(--muted)'},
};
function _tcpStatusBadge(status){
  const st=_TCP_STATUS_STYLE[status]||_TCP_STATUS_STYLE.not_started;
  const label=(status||'not_started').replace(/_/g,' ');
  return `<span style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:var(--fs-2xs);font-weight:700;text-transform:capitalize;background:${st.bg};color:${st.fg}">${esc(label)}</span>`;
}
async function openTrainingClassProgressModal(trainingClassId){
  const c=_tcById[trainingClassId];
  document.getElementById('tcp-title').textContent=c?`${c.display_name} — Curriculum Progress`:'Curriculum Progress';
  document.getElementById('tcp-summary').innerHTML='<p class="muted">Loading…</p>';
  document.getElementById('tcp-body').innerHTML='';
  openModal('m-training-class-progress');
  try{
    const d=await api(`/api/training-classes/${trainingClassId}/curriculum-progress`);
    const s=d.summary||{};
    const total=s.total||0, delivered=s.delivered||0;
    const pct=total?Math.round(100*delivered/total):0;
    document.getElementById('tcp-summary').innerHTML=`
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px">
        <div style="flex:1;background:var(--lgrey);border-radius:6px;height:10px;overflow:hidden">
          <div style="width:${pct}%;background:var(--ok);height:100%"></div>
        </div>
        <strong>${pct}%</strong>
      </div>
      <div class="muted" style="font-size:var(--fs-xs)">
        ${delivered} of ${total} requirement${total===1?'':'s'} delivered
        &bull; Planned ${s.planned||0} &bull; Not delivered ${s.not_delivered||0}
        &bull; Cancelled ${s.cancelled||0} &bull; Not started ${s.not_started||0}
      </div>`;
    const reqs=d.requirements||[];
    document.getElementById('tcp-body').innerHTML=reqs.length?reqs.map(r=>`<tr>
      <td>${esc(r.code)}</td><td>${esc(r.title)}</td><td>${_tcpStatusBadge(r.status)}</td>
    </tr>`).join(''):'<tr><td colspan="3" class="muted" style="text-align:center;padding:14px">No curriculum items in this Stage yet.</td></tr>';
  } catch(e){
    document.getElementById('tcp-summary').innerHTML=`<p style="color:var(--error)">${esc(apiErr(e))}</p>`;
  }
}

async function openAddTrainingClassModal(){
  if(!P.currentYearId){ showToast('Select a year from the dropdown above before continuing.',true); return; }
  document.getElementById('tc-name-inp').value='';
  document.getElementById('tc-seq-inp').value='';
  document.getElementById('tc-add-msg').textContent='';
  const scEl=document.getElementById('tc-stage-code'); if(scEl) scEl.value='';
  await _populateTrainingClassStageSelect('tc-stage-inp');
  openModal('m-add-training-class');
}
async function doAddTrainingClass(){
  const msg=document.getElementById('tc-add-msg');
  if(!P.currentYearId){ msg.textContent='Select a year from the dropdown above to continue.'; return; }
  const training_stage_id=document.getElementById('tc-stage-inp').value;
  const display_name=document.getElementById('tc-name-inp').value.trim();
  const seqVal=document.getElementById('tc-seq-inp').value;
  if(!training_stage_id||!display_name){ msg.textContent='Training Stage and Display Name are required.'; return; }
  const stage_code=document.getElementById('tc-stage-code')?.value||null;
  try{
    await api('/api/training-classes',{method:'POST',body:{
      training_year_id:P.currentYearId, training_stage_id, display_name,
      sequence: seqVal?parseInt(seqVal,10):0,
      stage_code: stage_code||null,
    }});
    closeModal('m-add-training-class');
    await _renderTrainingClasses(P.currentYearId);
    showToast('Training Class added.');
  } catch(e){ msg.textContent=apiErr(e); }
}

async function openEditTrainingClassModal(trainingClassId){
  const c=_tcById[trainingClassId];
  if(!c){ showToast('Could not find that Training Class — try refreshing.',true); return; }
  document.getElementById('tc-edit-id').value=c.training_class_id;
  document.getElementById('tc-edit-version').value=c.version;
  document.getElementById('tc-edit-name-inp').value=c.display_name||'';
  document.getElementById('tc-edit-seq-inp').value=c.sequence||0;
  document.getElementById('tc-edit-msg').textContent='';
  const editStageCodeEl=document.getElementById('tc-edit-stage-code');
  if(editStageCodeEl) editStageCodeEl.value=c.stage_code||'';
  await _populateTrainingClassStageSelect('tc-edit-stage-inp', c.training_stage_id);
  openModal('m-edit-training-class');
}
async function doEditTrainingClass(){
  const msg=document.getElementById('tc-edit-msg');
  const cid=document.getElementById('tc-edit-id').value;
  const training_stage_id=document.getElementById('tc-edit-stage-inp').value;
  const display_name=document.getElementById('tc-edit-name-inp').value.trim();
  const seqVal=document.getElementById('tc-edit-seq-inp').value;
  const client_version=parseInt(document.getElementById('tc-edit-version').value,10);
  if(!training_stage_id||!display_name){ msg.textContent='Training Stage and Display Name are required.'; return; }
  const edit_stage_code=document.getElementById('tc-edit-stage-code')?.value||null;
  try{
    await api(`/api/training-classes/${cid}`,{method:'PATCH',body:{
      training_stage_id, display_name, sequence: seqVal?parseInt(seqVal,10):0, client_version,
      stage_code: edit_stage_code||null,
    }});
    closeModal('m-edit-training-class');
    await _renderTrainingClasses(P.currentYearId);
    showToast('Training Class updated.');
  } catch(e){
    if(e && e.status===409){ msg.textContent='This Training Class was changed elsewhere. Reopen it to see the latest version.'; }
    else msg.textContent=apiErr(e);
  }
}
async function archiveTrainingClass(cid, yearId){
  confirmAction('Archive this Training Class? It will no longer appear in active planning views, but its history is kept and it can be restored later.',async()=>{
    try{ await api(`/api/training-classes/${cid}`,{method:'DELETE'}); await _renderTrainingClasses(yearId); showToast('Training Class archived.'); }
    catch(e){ showToast(apiErr(e),true); }
  });
}

// ── Custom Training Phases CRUD (Task 10) ────────────────────────────────
async function loadCustomPhases(){
  const list=document.getElementById('settings-custom-phases-list');
  if(!list)return;
  try{
    const phases=await api('/api/custom-training-phases');
    if(!phases||!phases.length){
      list.innerHTML='<div class="yn-empty">No custom phases yet. Add one to label a period that sits outside the normal terms.</div>';
      return;
    }
    // Rendered as rows rather than a 5-column table: a phase is a name and a
    // date range, and the old table showed a raw scope_type enum in a badge and
    // unformatted ISO dates.
    list.innerHTML='<div class="cp-list">'+phases.map(function(ph){
      const from=ph.applies_from?fmtD(ph.applies_from,{day:'numeric',month:'short',year:'numeric'}):'';
      const to=ph.applies_to?fmtD(ph.applies_to,{day:'numeric',month:'short',year:'numeric'}):'';
      const range=to?(from+' \u2192 '+to):(from+' \u2192 open-ended');
      return '<div class="cp-row">'
        +'<div class="yn-year-body"><div class="cp-name">'+esc(ph.name)+'</div>'
        +'<div class="cp-range">'+esc(range)+'</div></div>'
        +'<div class="cp-acts">'
        +'<button class="btn btn-xs btn-out admin-el" onclick="cpOpenEdit(\''+esc(ph.custom_phase_id)+'\',\''+esc(ph.name)+'\',\''+esc(ph.applies_from||'')+'\',\''+esc(ph.applies_to||'')+'\')">Edit</button>'
        +'<button class="btn btn-xs btn-red admin-el" onclick="cpDelete(\''+esc(ph.custom_phase_id)+'\',\''+esc(ph.name)+'\')">Delete</button>'
        +'</div></div>';
    }).join('')+'</div>';
  }catch(e){
    list.innerHTML=`<p style="color:var(--red);font-size:var(--fs-xs)">${esc(apiErr(e))}</p>`;
  }
}
function cpOpenCreate(){
  document.getElementById('cp-name-inp').value='';
  document.getElementById('cp-from-inp').value='';
  document.getElementById('cp-to-inp').value='';
  document.getElementById('cp-add-msg').textContent='';
  openModal('m-add-custom-phase');
}
async function cpDoCreate(){
  const msg=document.getElementById('cp-add-msg');
  const name=document.getElementById('cp-name-inp').value.trim();
  const applies_from=document.getElementById('cp-from-inp').value;
  const applies_to=document.getElementById('cp-to-inp').value||null;
  if(!name){msg.textContent='Give the phase a name.';return;}
  if(!applies_from){msg.textContent='Enter the date the phase starts.';return;}
  try{
    await api('/api/custom-training-phases',{method:'POST',body:JSON.stringify({name,scope_type:'squadron',applies_from,applies_to})});
    closeModal('m-add-custom-phase');
    await loadCustomPhases();
    showToast('Custom phase added.');
  }catch(e){msg.textContent=apiErr(e);}
}
function cpOpenEdit(phaseId,name,appliesFrom,appliesTo){
  document.getElementById('cp-edit-id').value=phaseId;
  document.getElementById('cp-edit-name-inp').value=name||'';
  document.getElementById('cp-edit-from-inp').value=appliesFrom||'';
  document.getElementById('cp-edit-to-inp').value=appliesTo||'';
  document.getElementById('cp-edit-msg').textContent='';
  openModal('m-edit-custom-phase');
}
async function cpDoEdit(){
  const msg=document.getElementById('cp-edit-msg');
  const phaseId=document.getElementById('cp-edit-id').value;
  const name=document.getElementById('cp-edit-name-inp').value.trim();
  const applies_from=document.getElementById('cp-edit-from-inp').value;
  const applies_to=document.getElementById('cp-edit-to-inp').value||null;
  if(!name){msg.textContent='Give the phase a name.';return;}
  if(!applies_from){msg.textContent='Enter the date the phase starts.';return;}
  try{
    await api(`/api/custom-training-phases/${phaseId}`,{method:'PATCH',body:JSON.stringify({name,applies_from,applies_to})});
    closeModal('m-edit-custom-phase');
    await loadCustomPhases();
    showToast('Custom phase updated.');
  }catch(e){msg.textContent=apiErr(e);}
}
async function cpDelete(phaseId,phaseName){
  confirmAction(`Delete phase "${phaseName}"? This cannot be undone.`,async()=>{
    try{
      await api(`/api/custom-training-phases/${phaseId}`,{method:'DELETE'});
      await loadCustomPhases();
      showToast('Custom phase deleted.');
    }catch(e){showToast(apiErr(e),true);}
  },true);
}

// ── CLASS-10: Training Class split/merge ────────────────────────────────
// Split = create a new class (existing POST /training-classes) + move the
// selected cadets into it (POST .../reassign-members). Merge = move every
// active member of the source into an existing target
// (POST .../merge-into), which also archives the source. Both only ever
// move CadetClassMembership rows -- past Sessions/SessionAudience for every
// cadet involved are left completely untouched (addendum §62/§63); see the
// backend's own comment on reassign_class_members for why this deliberately
// isn't the Facilitator absorb()-style blind FK reassignment.

function _tcSameStageOptions(sourceId, stageId){
  return Object.values(_tcById).filter(c=>c.training_stage_id===stageId && c.training_class_id!==sourceId && !c.is_archived);
}

async function openSplitTrainingClassModal(sourceId){
  const c=_tcById[sourceId];
  if(!c){ showToast('Could not find that Training Class — try refreshing.',true); return; }
  document.getElementById('tcsplit-source-id').value=sourceId;
  document.getElementById('tcsplit-title').textContent=`Split "${c.display_name}"`;
  document.getElementById('tcsplit-name-inp').value='';
  document.getElementById('tcsplit-seq-inp').value='';
  document.getElementById('tcsplit-msg').textContent='';
  const membersEl=document.getElementById('tcsplit-members');
  membersEl.innerHTML='<p class="muted">Loading roster…</p>';
  openModal('m-split-training-class');
  try{
    const members=await api(`/api/training-classes/${sourceId}/members`);
    if(!members.length){
      membersEl.innerHTML='<p class="muted">This class has no cadets to move.</p>';
      return;
    }
    membersEl.innerHTML=members.map(m=>`
      <label style="display:flex;align-items:center;gap:6px;padding:3px 0;font-weight:400">
        <input type="checkbox" class="tcsplit-cadet-chk" value="${esc(m.cadet_id)}">
        ${esc(m.rank||'')} ${esc(m.first_name)} ${esc(m.last_name)}
      </label>`).join('');
  } catch(e){
    membersEl.innerHTML=`<p style="color:var(--error)">${esc(apiErr(e))}</p>`;
  }
}

async function doSplitTrainingClass(){
  const msg=document.getElementById('tcsplit-msg');
  const sourceId=document.getElementById('tcsplit-source-id').value;
  const source=_tcById[sourceId];
  const display_name=document.getElementById('tcsplit-name-inp').value.trim();
  const seqVal=document.getElementById('tcsplit-seq-inp').value;
  const cadetIds=[...document.querySelectorAll('.tcsplit-cadet-chk:checked')].map(el=>el.value);
  if(!display_name){ msg.textContent='New class name is required.'; return; }
  if(!cadetIds.length){ msg.textContent='Select at least one cadet to move into the new class.'; return; }
  try{
    const created=await api('/api/training-classes',{method:'POST',body:{
      training_year_id: source.training_year_id, training_stage_id: source.training_stage_id,
      display_name, sequence: seqVal?parseInt(seqVal,10):0,
    }});
    const r=await api(`/api/training-classes/${sourceId}/reassign-members`,{method:'POST',body:{
      cadet_ids:cadetIds, to_training_class_id:created.training_class_id,
    }});
    closeModal('m-split-training-class');
    await _renderTrainingClasses(P.currentYearId);
    const skippedNote=(r.skipped&&r.skipped.length)?` (${r.skipped.length} could not be moved -- refresh and retry.)`:'';
    showToast(`Split complete: ${r.moved.length} cadet(s) moved to "${display_name}."${skippedNote}`);
  } catch(e){ msg.textContent=apiErr(e); }
}

async function openMergeTrainingClassModal(sourceId){
  const c=_tcById[sourceId];
  if(!c){ showToast('Could not find that Training Class — try refreshing.',true); return; }
  document.getElementById('tcmerge-source-id').value=sourceId;
  document.getElementById('tcmerge-title').textContent=`Merge "${c.display_name}" into…`;
  document.getElementById('tcmerge-msg').textContent='';
  const targets=_tcSameStageOptions(sourceId, c.training_stage_id);
  const sel=document.getElementById('tcmerge-target-inp');
  if(!targets.length){
    sel.innerHTML='';
    document.getElementById('tcmerge-msg').textContent='No other Training Class in the same Stage and Year to merge into.';
  } else {
    sel.innerHTML=targets.map(t=>`<option value="${esc(t.training_class_id)}">${esc(t.display_name)}</option>`).join('');
  }
  openModal('m-merge-training-class');
}

function doMergeTrainingClass(){
  const sourceId=document.getElementById('tcmerge-source-id').value;
  const targetId=document.getElementById('tcmerge-target-inp').value;
  const source=_tcById[sourceId], target=_tcById[targetId];
  if(!targetId){ document.getElementById('tcmerge-msg').textContent='Choose a Training Class to merge into.'; return; }
  closeModal('m-merge-training-class');
  confirmAction(
    `Merge "${source.display_name}" into "${target.display_name}"? All cadets in "${source.display_name}" move to "${target.display_name}". "${source.display_name}" then archives — its history and past sessions are kept and can be restored later.`,
    async ()=>{
      try{
        const r=await api(`/api/training-classes/${sourceId}/merge-into`,{method:'POST',body:{target_training_class_id:targetId}});
        await _renderTrainingClasses(P.currentYearId);
        const skippedNote=(r.skipped&&r.skipped.length)?` (${r.skipped.length} could not be moved.)`:'';
        showToast(`Merged into "${target.display_name}": ${r.moved.length} cadet(s) moved.${skippedNote}`);
      } catch(e){ showToast('Could not merge: '+apiErr(e), true); }
    },
    true,
  );
}
