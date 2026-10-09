// Main TMS module: Timing Templates and one-night parade-night timing
// overrides.
// Extracted verbatim from connected-frontend/index.html (stabilisation Phase 4,
// C6). Top-level function declarations and side-effect-free let/const only;
// loaded as a classic script BEFORE the inline bootstrap, so everything here
// is defined before any page-load code runs. Statements with load-time
// effects stay in index.html in their original order. Parity is proven by
// tools/architecture/frontend_parity.mjs.

let _ttEditId=null, _ttBlocks=[], _pnOverridePnId=null;

const BLOCK_TYPE_OPTIONS=[
  {value:'arrival',         label:'Arrival'},
  {value:'admin',           label:'Admin'},
  {value:'parade',          label:'Parade'},
  {value:'briefing',        label:'Briefing'},
  {value:'training_period', label:'Training Period'},
  {value:'drinks_break',    label:'Drinks Break'},
  {value:'fatigue',         label:'Fatigue'},
  {value:'dismissal',       label:'Dismissal'},
  {value:'other',           label:'Other (custom name)'},
];

function ttBlockTypeLabel(bt,name){
  const MAP={arrival:'Arrival',admin:'Admin',parade:'Parade',briefing:'Briefing',
             training_period:'Training Period',drinks_break:'Drinks Break',
             fatigue:'Fatigue',dismissal:'Dismissal',other:''};
  return bt==='other'?esc(name||'Other'):(MAP[bt]||esc(bt));
}

function ttSyncBlockType(sel){
  const row=sel.closest('tr');
  const nameInput=row.querySelector('.tt-block-name');
  const ipCheck=row.querySelector('.tt-block-ip');
  const bt=sel.value;
  const opt=BLOCK_TYPE_OPTIONS.find(o=>o.value===bt);
  const label=opt?opt.label:'';
  const i=Array.from(row.parentNode.rows).indexOf(row);
  if(bt==='training_period'){
    if(nameInput&&(!nameInput.value||nameInput.value===nameInput.dataset.autoName)){
      nameInput.value='Training Period';
      nameInput.dataset.autoName='Training Period';
      if(i>=0) _ttBSet(i,'block_name','Training Period');
    }
    if(ipCheck){ipCheck.checked=true;ipCheck.disabled=true;}
  } else {
    if(nameInput&&(!nameInput.value||nameInput.value===nameInput.dataset.autoName)){
      const v=bt==='other'?'':label;
      nameInput.value=v;
      nameInput.dataset.autoName=v;
      if(i>=0) _ttBSet(i,'block_name',v);
    }
    if(ipCheck){ipCheck.checked=false;ipCheck.disabled=false;}
  }
}

function getEffectiveTemplate(date, sqnId){
  const tpls=(S.timingTemplates||[]).filter(t=>
    (!sqnId||t.squadron_id===sqnId)&&!t.is_archived&&t.active_status&&t.effective_from<=date
  ).sort((a,b)=>b.effective_from.localeCompare(a.effective_from));
  for(const t of tpls){ if(!t.effective_to||t.effective_to>=date) return t; }
  return null;
}

function renderTimingTemplates(){
  const el=document.getElementById('timing-templates-list');
  if(!el) return;
  const tpls=S.timingTemplates||[];
  if(!tpls.length){
    el.innerHTML='<div style="color:var(--muted);font-size:var(--fs-xs);padding:4px 0">No timing templates defined. Click "+ New Template" to create one.</div>';
    return;
  }
  const today=new Date().toISOString().slice(0,10);
  el.innerHTML=tpls.map(t=>{
    const isCurrent=t.active_status&&!t.is_archived&&t.effective_from<=today&&(!t.effective_to||t.effective_to>=today);
    const badge=isCurrent?'<span style="background:var(--ok);color:#fff;padding:1px 7px;border-radius:10px;font-size:var(--fs-2xs);margin-left:6px;font-weight:700">Current</span>':'';
    return `<div style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid var(--border)">
      <div style="flex:1;font-size:var(--fs-sm)"><span style="font-weight:600">${esc(t.name)}</span>${badge}
        <span style="color:var(--muted);font-size:var(--fs-xs);margin-left:8px">from ${t.effective_from}${t.effective_to?' to '+t.effective_to:''} · ${t.instructional_period_count||0} Training Period block${t.instructional_period_count===1?'':'s'}</span>
      </div>
      <button class="btn admin-el" style="font-size:var(--fs-xs);padding:2px 8px" onclick="openTimingTemplateModal('${esc(t.timing_template_id)}')">Edit</button>
    </div>`;
  }).join('');
}

function openTimingTemplateModal(tid){
  _ttEditId=tid||null; _ttBlocks=[];
  document.getElementById('timing-modal-title').textContent=tid?'Edit Timing Template':'New Timing Template';
  ['tt-name','tt-from','tt-to','tt-notes','tt-apply-from-date','tt-apply-from-reason'].forEach(id=>{const e=document.getElementById(id);if(e)e.value='';});
  const msgEl=document.getElementById('tt-msg'); if(msgEl)msgEl.textContent='';
  const warnEl=document.getElementById('tt-warnings'); if(warnEl)warnEl.textContent='';
  const applyWrap=document.getElementById('tt-apply-from-wrap');
  if(applyWrap)applyWrap.style.display=tid?'flex':'none';
  if(tid){
    const t=(S.timingTemplates||[]).find(x=>x.timing_template_id===tid);
    if(t){
      document.getElementById('tt-name').value=t.name||'';
      document.getElementById('tt-from').value=t.effective_from||'';
      document.getElementById('tt-to').value=t.effective_to||'';
      document.getElementById('tt-notes').value=t.notes||'';
      _ttBlocks=(t.blocks||[]).map(b=>({...b}));
    }
  }
  renderTTBlocks();
  openModal('m-timing');
}

function _ttDur(b){
  if(b.duration_minutes) return b.duration_minutes;
  if(b.start_time&&b.end_time){
    const [sh,sm]=b.start_time.split(':').map(Number);
    const [eh,em]=b.end_time.split(':').map(Number);
    const d=(eh*60+em)-(sh*60+sm);
    return d>0?d:null;
  }
  return null;
}

function _ttBlockRow(b,i){
  const typeOpts=BLOCK_TYPE_OPTIONS.map(o=>`<option value="${o.value}"${b.block_type===o.value?' selected':''}>${esc(o.label)}</option>`).join('');
  const dur=_ttDur(b);
  return `<tr>
    <td style="padding:3px 4px;color:var(--muted);white-space:nowrap">${i+1}</td>
    <td style="padding:2px 3px"><input class="tt-block-name" value="${esc(b.block_name||'')}" oninput="_ttBSet(${i},'block_name',this.value)" aria-label="Block name for period ${i+1}" style="width:100%;min-width:95px;font-size:var(--fs-xs)"></td>
    <td style="padding:2px 3px"><select onchange="_ttBSet(${i},'block_type',this.value);_ttBSet(${i},'is_instructional_period',this.value==='training_period');ttSyncBlockType(this)" aria-label="Block type for period ${i+1}" style="width:100%;font-size:var(--fs-xs)">${typeOpts}</select></td>
    <td style="padding:2px 3px"><input type="time" value="${b.start_time||''}" oninput="_ttBSet(${i},'start_time',this.value);renderTTBlocks()" aria-label="Start time for period ${i+1}" style="width:82px;font-size:var(--fs-xs)"></td>
    <td style="padding:2px 3px"><input type="time" value="${b.end_time||''}" oninput="_ttBSet(${i},'end_time',this.value);renderTTBlocks()" aria-label="End time for period ${i+1}" style="width:82px;font-size:var(--fs-xs)"></td>
    <td style="padding:2px 4px;text-align:center;font-size:var(--fs-xs);color:var(--muted)">${dur!=null?dur:''}</td>
    <td style="padding:2px 4px;text-align:center"><input class="tt-block-ip" type="checkbox"${b.is_instructional_period?' checked':''}${b.block_type==='training_period'?' disabled':''} onchange="_ttBSet(${i},'is_instructional_period',this.checked)" aria-label="Instructional period for ${esc(b.block_name||'period '+(i+1))}"></td>
    <td style="padding:2px 4px;text-align:center"><input type="checkbox"${b.is_optional?' checked':''} onchange="_ttBSet(${i},'is_optional',this.checked)" aria-label="Optional for ${esc(b.block_name||'period '+(i+1))}"></td>
    <td style="padding:2px 3px;text-align:center;white-space:nowrap">
      ${i>0?`<button class="btn btn-icon" onclick="_ttBMove(${i},-1)" aria-label="Move ${esc(b.block_name||'period '+(i+1))} earlier" title="Move earlier">▲</button>`:'<span style="display:inline-block;width:28px"></span>'}
      ${i<_ttBlocks.length-1?`<button class="btn btn-icon" onclick="_ttBMove(${i},1)" aria-label="Move ${esc(b.block_name||'period '+(i+1))} later" title="Move later">▼</button>`:'<span style="display:inline-block;width:28px"></span>'}
    </td>
    <td style="padding:2px 4px;text-align:center"><button class="btn btn-icon" style="color:var(--status-text-danger)" onclick="_ttBDel(${i})" aria-label="Delete ${esc(b.block_name||'period '+(i+1))}" title="Delete">✕</button></td>
  </tr>`;
}

function renderTTBlocks(){
  const tbody=document.getElementById('tt-blocks-body');
  if(tbody) tbody.innerHTML=_ttBlocks.map((b,i)=>_ttBlockRow(b,i)).join('');
}

function _ttBSet(i,field,val){ if(_ttBlocks[i]) _ttBlocks[i][field]=val; }
function _ttBMove(i,dir){
  const ni=i+dir; if(ni<0||ni>=_ttBlocks.length) return;
  [_ttBlocks[i],_ttBlocks[ni]]=[_ttBlocks[ni],_ttBlocks[i]]; renderTTBlocks();
}
function _ttBDel(i){ _ttBlocks.splice(i,1); renderTTBlocks(); }

function ttAddBlock(){
  _ttBlocks.push({block_name:'Training Period',block_type:'training_period',is_instructional_period:true,is_optional:false,start_time:'',end_time:''});
  renderTTBlocks();
}

function ttQuickSetup(){
  const n=parseInt(document.getElementById('tt-quick-n')?.value||'3',10);
  if(isNaN(n)||n<1||n>10) return;
  const blocks=[
    {block_name:'Arrival',  block_type:'arrival',  is_instructional_period:false,is_optional:false,start_time:'',end_time:''},
    {block_name:'Admin',    block_type:'admin',    is_instructional_period:false,is_optional:false,start_time:'',end_time:''},
    {block_name:'Parade',   block_type:'parade',   is_instructional_period:false,is_optional:false,start_time:'',end_time:''},
    {block_name:'Briefing', block_type:'briefing', is_instructional_period:false,is_optional:false,start_time:'',end_time:''},
  ];
  for(let i=0;i<n;i++){
    blocks.push({block_name:n>1?`Training Period ${i+1}`:'Training Period',
                 block_type:'training_period',is_instructional_period:true,is_optional:false,start_time:'',end_time:''});
    if(i===0&&n>1){
      blocks.push({block_name:'Drinks Break',block_type:'drinks_break',
                   is_instructional_period:false,is_optional:false,start_time:'',end_time:''});
    }
  }
  blocks.push(
    {block_name:'Fatigue',   block_type:'fatigue',   is_instructional_period:false,is_optional:false,start_time:'',end_time:''},
    {block_name:'Parade',    block_type:'parade',    is_instructional_period:false,is_optional:false,start_time:'',end_time:''},
    {block_name:'Dismissal', block_type:'dismissal', is_instructional_period:false,is_optional:false,start_time:'',end_time:''}
  );
  _ttBlocks=blocks.map((b,i)=>({...b,display_order:i+1}));
  renderTTBlocks();
}

async function reloadTimingTemplates(){
  try{ S.timingTemplates=await api('/api/timing-templates'); }catch(_){ S.timingTemplates=[]; }
}

async function saveTimingTemplate(){
  const name=(document.getElementById('tt-name').value||'').trim();
  const effectiveFrom=document.getElementById('tt-from').value;
  const effectiveTo=document.getElementById('tt-to').value||null;
  const notes=(document.getElementById('tt-notes').value||'').trim()||null;
  const msgEl=document.getElementById('tt-msg');
  const setMsg=(t,ok)=>{ if(msgEl){ msgEl.textContent=t; msgEl.style.color=ok?'var(--ok)':'var(--red)'; } };
  if(!name){ setMsg('Template name is required.',false); return; }
  if(!effectiveFrom){ setMsg('Effective from date is required.',false); return; }
  const blocks=_ttBlocks.map((b,i)=>({
    display_order:i,
    block_name:b.block_name||('Block '+(i+1)),
    block_type:b.block_type||'other',
    is_instructional_period:!!b.is_instructional_period,
    is_optional:!!b.is_optional,
    start_time:b.start_time||null,
    end_time:b.end_time||null,
    duration_minutes:_ttDur(b)||null,
    period_number:b.period_number||null,
    notes:b.notes||null,
  }));
  setMsg('Saving…',true);
  try{
    let result;
    if(_ttEditId){
      result=await api('/api/timing-templates/'+_ttEditId,{method:'PATCH',body:JSON.stringify({name,effective_from:effectiveFrom,effective_to:effectiveTo,notes,blocks})});
    }else{
      result=await api('/api/timing-templates',{method:'POST',body:JSON.stringify({name,effective_from:effectiveFrom,effective_to:effectiveTo,notes,blocks})});
    }
    const warnEl=document.getElementById('tt-warnings');
    if(warnEl) warnEl.textContent=(result.warnings&&result.warnings.length)?'Warnings: '+result.warnings.join('; '):'';
    setMsg('✅ Template saved.',true);
    if(!_ttEditId){
      _ttEditId=result.timing_template_id;
      document.getElementById('timing-modal-title').textContent='Edit Timing Template';
      const applyWrap=document.getElementById('tt-apply-from-wrap');
      if(applyWrap) applyWrap.style.display='flex';
    }
    await reloadTimingTemplates();
    renderTimingTemplates();
  }catch(e){ setMsg(apiErr(e),false); }
}

async function ttApplyFromDate(){
  if(!_ttEditId) return;
  const d=document.getElementById('tt-apply-from-date').value;
  const reason=(document.getElementById('tt-apply-from-reason').value||'').trim();
  const msgEl=document.getElementById('tt-msg');
  const setMsg=(t,ok)=>{ if(msgEl){ msgEl.textContent=t; msgEl.style.color=ok?'var(--ok)':'var(--red)'; } };
  if(!d){ setMsg('Enter a date to apply from.',false); return; }
  setMsg('Applying…',true);
  try{
    const r=await api('/api/timing-templates/'+_ttEditId+'/apply-from-date',{method:'POST',body:JSON.stringify({effective_from:d,reason:reason||'Apply from date'})});
    setMsg('✅ Applied — future parade nights from '+r.effective_from+' will use this template.',true);
    await reloadTimingTemplates(); renderTimingTemplates();
  }catch(e){ setMsg(apiErr(e),false); }
}

// ── WORK-05: custom blocks for a one-night timing override ───────────────────
let _pnCbBlocks = [];
let _pnOrCurrentMode = 'template';
function _pnOrMode(mode) {
  _pnOrCurrentMode = mode;
  const isTpl = mode === 'template';
  document.getElementById('pn-or-tpl-section').style.display = isTpl ? '' : 'none';
  document.getElementById('pn-or-cus-section').style.display = isTpl ? 'none' : '';
  document.getElementById('pn-or-mode-tpl').style.background = isTpl ? 'var(--dark)' : 'var(--surface)';
  document.getElementById('pn-or-mode-tpl').style.color = isTpl ? '#fff' : 'var(--text)';
  document.getElementById('pn-or-mode-cus').style.background = isTpl ? 'var(--surface)' : 'var(--dark)';
  document.getElementById('pn-or-mode-cus').style.color = isTpl ? 'var(--text)' : '#fff';
}
function _pnCbBlockRow(b, i) {
  const typeOpts = BLOCK_TYPE_OPTIONS.map(o=>`<option value="${o.value}"${b.block_type===o.value?' selected':''}>${esc(o.label)}</option>`).join('');
  const sh = b.start_time && b.end_time ? (() => {
    const [sh,sm]=b.start_time.split(':').map(Number), [eh,em]=b.end_time.split(':').map(Number);
    const d=(eh*60+em)-(sh*60+sm); return d>0?String(d):'';
  })() : '';
  return `<tr>
    <td style="padding:2px 4px;color:var(--muted);font-size:var(--fs-xs)">${i+1}</td>
    <td style="padding:2px 3px"><input value="${esc(b.block_name)}" oninput="_pnCbSet(${i},'block_name',this.value)" aria-label="Block name for block ${i+1}" style="width:100px;font-size:var(--fs-xs)"></td>
    <td style="padding:2px 3px"><select aria-label="Block type for block ${i+1}" style="font-size:var(--fs-xs)" onchange="_pnCbSet(${i},'block_type',this.value);_pnCbSet(${i},'is_instructional_period',this.value==='training_period');renderPNCbBlocks()">${typeOpts}</select></td>
    <td style="padding:2px 3px"><input type="time" value="${b.start_time||''}" oninput="_pnCbSet(${i},'start_time',this.value);renderPNCbBlocks()" aria-label="Start time for block ${i+1}" style="width:82px;font-size:var(--fs-xs)"></td>
    <td style="padding:2px 3px"><input type="time" value="${b.end_time||''}" oninput="_pnCbSet(${i},'end_time',this.value);renderPNCbBlocks()" aria-label="End time for block ${i+1}" style="width:82px;font-size:var(--fs-xs)"></td>
    <td style="padding:2px 4px;text-align:center;font-size:var(--fs-xs);color:var(--muted)">${sh}</td>
    <td style="padding:2px 4px;text-align:center"><input type="checkbox"${b.is_instructional_period?' checked':''} onchange="_pnCbSet(${i},'is_instructional_period',this.checked)" aria-label="Instructional period for ${esc(b.block_name||'block '+(i+1))}"></td>
    <td style="padding:2px 4px;text-align:center"><input type="checkbox"${b.is_optional?' checked':''} onchange="_pnCbSet(${i},'is_optional',this.checked)" aria-label="Optional for ${esc(b.block_name||'block '+(i+1))}"></td>
    <td style="padding:2px 4px;text-align:center"><button class="btn btn-icon" style="color:var(--status-text-danger)" onclick="_pnCbDel(${i})" aria-label="Delete ${esc(b.block_name||'block '+(i+1))}" title="Delete">✕</button></td>
  </tr>`;
}
function renderPNCbBlocks() {
  const tb = document.getElementById('pn-cb-body');
  if (tb) tb.innerHTML = _pnCbBlocks.map((b,i)=>_pnCbBlockRow(b,i)).join('');
}
function _pnCbSet(i,f,v){ if(_pnCbBlocks[i]) _pnCbBlocks[i][f]=v; }
function _pnCbDel(i){ _pnCbBlocks.splice(i,1); renderPNCbBlocks(); }
function pnCbAddBlock(){
  _pnCbBlocks.push({block_name:'Training Period',block_type:'training_period',is_instructional_period:true,is_optional:false,start_time:'',end_time:''});
  renderPNCbBlocks();
}

async function openPNTimingOverrideModal(pnid){
  _pnOverridePnId=pnid;
  const msgEl=document.getElementById('pn-override-msg'); if(msgEl) msgEl.textContent='';
  document.getElementById('pn-override-reason').value='';
  _pnCbBlocks=[];
  renderPNCbBlocks();
  _pnOrMode('template');
  const sel=document.getElementById('pn-override-tid');
  sel.innerHTML='';
  (S.timingTemplates||[]).forEach(t=>{
    const opt=new Option(t.name+' (from '+t.effective_from+')',t.timing_template_id);
    sel.appendChild(opt);
  });
  openModal('m-pn-timing-override');
}

async function savePNTimingOverride(){
  if(!_pnOverridePnId) return;
  const reason=(document.getElementById('pn-override-reason').value||'').trim();
  const msgEl=document.getElementById('pn-override-msg');
  const setMsg=(t,ok)=>{ if(msgEl){ msgEl.textContent=t; msgEl.style.color=ok?'var(--ok)':'var(--red)'; } };
  if(!reason){ setMsg('Enter a reason for this override before saving.',false); return; }
  setMsg('Saving…',true);
  try{
    if(_pnOrCurrentMode==='custom'){
      // WORK-05: create a one-off template then apply it as override
      if(!_pnCbBlocks.length){ setMsg('Add at least one block.',false); return; }
      const pn=(S.paradeNights||[]).find(x=>x.id===_pnOverridePnId);
      const dateLbl=pn?pn.date:'custom';
      const tpl=await api('/api/timing-templates',{method:'POST',body:JSON.stringify({
        name:'Custom — '+dateLbl, effective_from:dateLbl, notes:'Auto-created for one-night override (WORK-05)',
        blocks:_pnCbBlocks.map((b,i)=>({...b, sort_order:i})),
      })});
      await api('/api/parade-nights/'+_pnOverridePnId+'/timing-override',{method:'POST',body:JSON.stringify({timing_template_id:tpl.timing_template_id,reason})});
      await reloadTimingTemplates();
    } else {
      const tid=document.getElementById('pn-override-tid').value;
      await api('/api/parade-nights/'+_pnOverridePnId+'/timing-override',{method:'POST',body:JSON.stringify({timing_template_id:tid||null,reason})});
    }
    showToast('Timing override applied.');
    setMsg('✅ Override applied.',true);
    setTimeout(()=>closeModal('m-pn-timing-override'),1300);
  }catch(e){ setMsg(apiErr(e),false); }
}

async function removePNTimingOverride(){
  if(!_pnOverridePnId) return;
  const msgEl=document.getElementById('pn-override-msg');
  const setMsg=(t,ok)=>{ if(msgEl){ msgEl.textContent=t; msgEl.style.color=ok?'var(--ok)':'var(--red)'; } };
  setMsg('Removing…',true);
  try{
    await api('/api/parade-nights/'+_pnOverridePnId+'/timing-override',{method:'DELETE'});
    showToast('Timing override removed.');
    setMsg('✅ Override removed.',true);
    setTimeout(()=>closeModal('m-pn-timing-override'),1300);
  }catch(e){ setMsg(apiErr(e),false); }
}
