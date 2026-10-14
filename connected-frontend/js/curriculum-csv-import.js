// Main TMS module: Curriculum > Import CSV.
// Extracted verbatim from connected-frontend/index.html (stabilisation step 4:
// modularise the monolith by extraction, never by addition). Loaded as a
// classic script after the main inline script, so its top-level functions and
// constants share the page's global scope exactly as before: the modal's
// onclick handlers and its dependencies (openModal, API_BASE, tokenGet, esc,
// reloadAndRender) resolve unchanged.

// ════════════════════════════
//  CSV CURRICULUM IMPORT
// ════════════════════════════

// ── Target ownership picker ────────────────────────────────────────────────
// The backend requires an explicit target for Wing/Squadron imports (422
// otherwise, so nothing is ever orphaned or written to the wrong Wing). The
// picker supplies it: Wing level -> choose a Wing; Squadron level -> choose a
// Wing, then one of THAT Wing's Squadrons (a Squadron's Wing is authoritative).
// Preview states the target, and commit uses exactly the target that was
// previewed: changing the level, unit or file afterwards discards the preview.
// The markup is created here, not in index.html, so the monolith does not grow.
const _csvCurrUnits={wings:[],squadrons:[]};
let _csvCurrPreviewTarget=null;

function _csvCurrEnsurePicker(){
  if(document.getElementById('csv-curr-target'))return;
  const levelRow=document.getElementById('csv-curr-level').closest('.form-row');
  const row=document.createElement('div');
  row.className='form-row';
  row.id='csv-curr-target';
  row.innerHTML='<div class="form-group" id="csv-curr-wing-group" style="display:none">'
    +'<label for="csv-curr-wing">Wing *</label><select id="csv-curr-wing"></select></div>'
    +'<div class="form-group" id="csv-curr-squadron-group" style="display:none">'
    +'<label for="csv-curr-squadron">Squadron *</label><select id="csv-curr-squadron"></select></div>';
  levelRow.after(row);
  const summary=document.createElement('div');
  summary.id='csv-curr-target-summary';
  summary.style.cssText='font-weight:600;margin-bottom:6px';
  document.getElementById('csv-curr-preview').prepend(summary);
  document.getElementById('csv-curr-level').addEventListener('change',_csvCurrTargetChanged);
  document.getElementById('csv-curr-wing').addEventListener('change',()=>{_csvCurrFillSquadrons();_csvCurrTargetChanged();});
  document.getElementById('csv-curr-squadron').addEventListener('change',_csvCurrTargetChanged);
  document.getElementById('csv-curr-file').addEventListener('change',_csvCurrTargetChanged);
}

function _csvCurrFillWings(){
  const sel=document.getElementById('csv-curr-wing');
  sel.innerHTML='<option value="">— Choose Wing —</option>'+_csvCurrUnits.wings
    .map(w=>`<option value="${esc(w.wing_id)}">${esc(w.code)} — ${esc(w.name||'')}</option>`).join('');
}

function _csvCurrFillSquadrons(){
  const wingId=document.getElementById('csv-curr-wing').value;
  const sel=document.getElementById('csv-curr-squadron');
  const own=_csvCurrUnits.squadrons.filter(q=>wingId&&q.wing_id===wingId);
  sel.innerHTML='<option value="">'+(wingId?'— Choose Squadron —':'— Choose a Wing first —')+'</option>'+own
    .map(q=>`<option value="${esc(q.squadron_id)}" data-wing-id="${esc(q.wing_id)}">${esc(q.code)} — ${esc(q.name||'')}</option>`).join('');
}

function _csvCurrTargetChanged(){
  const level=document.getElementById('csv-curr-level').value;
  document.getElementById('csv-curr-wing-group').style.display=(level==='wing'||level==='squadron')?'':'none';
  document.getElementById('csv-curr-squadron-group').style.display=(level==='squadron')?'':'none';
  // Any change after a preview invalidates it.
  _csvCurrPreviewTarget=null;
  document.getElementById('csv-curr-preview').style.display='none';
  document.getElementById('csv-curr-commit-btn').style.display='none';
  document.getElementById('csv-curr-result').style.display='none';
  document.getElementById('csv-curr-msg').textContent='';
}

// The selected target, or {error} naming what is missing.
function _csvCurrTarget(){
  const level=document.getElementById('csv-curr-level').value;
  if(level==='national')return {level, label:'National curriculum'};
  const wingId=document.getElementById('csv-curr-wing').value;
  const wing=_csvCurrUnits.wings.find(w=>w.wing_id===wingId);
  if(!wing)return {error:'Choose the Wing this curriculum belongs to.'};
  if(level==='wing')return {level, wingId, label:`Wing ${wing.code} — ${wing.name||''}`};
  const sqnId=document.getElementById('csv-curr-squadron').value;
  const sqn=_csvCurrUnits.squadrons.find(q=>q.squadron_id===sqnId&&q.wing_id===wingId);
  if(!sqn)return {error:'Choose the Squadron this curriculum belongs to.'};
  return {level, squadronId:sqn.squadron_id, label:`Squadron ${sqn.code} — ${sqn.name||''} (Wing ${wing.code})`};
}

async function _csvCurrLoadUnits(){
  try{
    const [wings,sqns]=await Promise.all([api('/api/wings'),api('/api/squadrons')]);
    _csvCurrUnits.wings=(Array.isArray(wings)?wings:[]).slice().sort((a,b)=>String(a.code).localeCompare(String(b.code)));
    _csvCurrUnits.squadrons=(Array.isArray(sqns)?sqns:[]).slice().sort((a,b)=>String(a.code).localeCompare(String(b.code),undefined,{numeric:true}));
  }catch(e){
    _csvCurrUnits.wings=[];_csvCurrUnits.squadrons=[];
    document.getElementById('csv-curr-msg').textContent='Could not load Wings and Squadrons: '+apiErr(e);
  }
  _csvCurrFillWings();
  _csvCurrFillSquadrons();
}

function openCsvCurrImport(){
  _csvCurrEnsurePicker();
  document.getElementById('csv-curr-level').value='national';
  _csvCurrTargetChanged();
  _csvCurrLoadUnits();
  document.getElementById('csv-curr-file').value='';
  document.getElementById('csv-curr-msg').textContent='';
  document.getElementById('csv-curr-preview').style.display='none';
  document.getElementById('csv-curr-result').style.display='none';
  document.getElementById('csv-curr-commit-btn').style.display='none';
  document.getElementById('csv-curr-preview-btn').style.display='inline-flex';
  openModal('m-csv-curr-import');
}
const _CSV_CURR_ACTION_CLR={created:'color:var(--ok);font-weight:600',updated:'color:var(--royal);font-weight:600',skipped:'color:var(--muted)',failed:'color:var(--error);font-weight:600'};
async function _csvCurrRequest(preview){
  const msg=document.getElementById('csv-curr-msg');
  const fileEl=document.getElementById('csv-curr-file');
  if(!fileEl.files||!fileEl.files[0]){ msg.textContent='Select a CSV file first.'; return null; }
  // Preview resolves the target; commit reuses exactly the previewed one.
  const target=preview?_csvCurrTarget():_csvCurrPreviewTarget;
  if(!target){ msg.textContent='Preview the import again before confirming.'; return null; }
  if(target.error){ msg.textContent=target.error; return null; }
  const q=new URLSearchParams({owning_level:target.level, preview:String(preview)});
  if(target.wingId)q.set('wing_id',target.wingId);
  if(target.squadronId)q.set('squadron_id',target.squadronId);
  msg.textContent=preview?'Parsing…':'Importing…';
  const form=new FormData();
  form.append('file',fileEl.files[0]);
  const res=await fetch(API_BASE+`/api/curriculum/import-csv?${q.toString()}`,{
    method:'POST',
    headers:{'Authorization':'Bearer '+tokenGet()},
    body:form,
  });
  const d=await res.json();
  if(!res.ok){ msg.textContent=d.detail?.message||d.detail?.error||'Request failed.'; return null; }
  msg.textContent='';
  if(preview)_csvCurrPreviewTarget=target;
  return d;
}
async function previewCsvCurr(){
  const d=await _csvCurrRequest(true);
  if(!d)return;
  const summary=`${d.created} to create · ${d.updated} to update · ${d.skipped} unchanged${d.failed?' · '+d.failed+' failed':''}`;
  document.getElementById('csv-curr-target-summary').textContent='Target: '+_csvCurrPreviewTarget.label;
  document.getElementById('csv-curr-summary').textContent=summary;
  document.getElementById('csv-curr-rows').innerHTML=(d.results||[]).map(r=>`<tr>
    <td style="padding:3px 8px;border-bottom:1px solid var(--border)">${esc(r.code||'')}</td>
    <td style="padding:3px 8px;border-bottom:1px solid var(--border)">${esc(r.title||'')}</td>
    <td style="padding:3px 8px;border-bottom:1px solid var(--border)">${esc(r.phase||'')}</td>
    <td style="padding:3px 8px;border-bottom:1px solid var(--border);${_CSV_CURR_ACTION_CLR[r.status]||''}">${esc(r.status||'')}${r.error?' — '+esc(r.error):''}</td>
  </tr>`).join('')||'<tr><td colspan="4" style="padding:8px;color:var(--muted)">No rows parsed.</td></tr>';
  document.getElementById('csv-curr-preview').style.display='';
  document.getElementById('csv-curr-commit-btn').style.display=(d.created+d.updated)>0?'inline-flex':'none';
  if(d.parse_errors&&d.parse_errors.length){
    document.getElementById('csv-curr-msg').innerHTML=`<span style="color:var(--warn-text)">${d.parse_errors.slice(0,5).map(e=>esc(e)).join('<br>')}</span>`;
  }
}
async function commitCsvCurr(){
  const d=await _csvCurrRequest(false);
  if(!d)return;
  const result=document.getElementById('csv-curr-result');
  result.innerHTML=`<div class="alert a-ok">Import complete: ${d.created} created, ${d.updated} updated, ${d.skipped} unchanged.${d.failed?' '+d.failed+' failed.':''}</div>`;
  result.style.display='block';
  document.getElementById('csv-curr-commit-btn').style.display='none';
  await reloadAndRender();
}
