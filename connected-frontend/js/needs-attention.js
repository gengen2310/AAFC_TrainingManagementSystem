// Main TMS module: Needs Attention -- action items, exception checks and
// session-level outcome recording.
// Extracted verbatim from connected-frontend/index.html (stabilisation Phase 4,
// C6). Top-level function declarations and side-effect-free let/const only;
// loaded as a classic script BEFORE the inline bootstrap, so everything here
// is defined before any page-load code runs. Statements with load-time
// effects stay in index.html in their original order. Parity is proven by
// tools/architecture/frontend_parity.mjs.

// ═══════════════════════════════════════════════════════════
//  NEEDS ACTION
// ═══════════════════════════════════════════════════════════
function renderActions(){
  const today=new Date().toISOString().substring(0,10);
  const w=document.getElementById('run-checks-btn-wrap');
  if(w) w.style.display=canWriteSquadron()?'':'none';
  const items=[];

  // Priority 0-1: Backend action items (manual + automation, open only)
  (S.actionItems||[]).filter(a=>a.status==='open').forEach(a=>{
    items.push({
      pri: a.severity==='command_decision_required'?0:1,
      cat: a.source==='automation'?'Alert':'Task',
      title: a.title,
      detail: a.description||'',
      due: a.due||'',
      issue: a.severity==='command_decision_required'?'Decision required':'Action required',
      type: 'backend', id: a.id
    });
  });

  // Past planned sessions are intentionally not duplicated in this general
  // table.  The single authoritative workflow is the actionable
  // "Sessions Needing Outcome Entry" table immediately below it.

  // Priority 3: Cancelled/ND sessions with no reason
  allSess().filter(s=>s.date<today&&(s.status==='cancelled'||s.status==='not_delivered')&&
    !(s.cancelled_reason||s.not_delivered_reason||'').trim()).forEach(s=>{
    items.push({
      pri: 3, cat: 'Data',
      title: `Reason needed — ${s.exp||'unassigned'} (${fmtD(s.date,{day:'numeric',month:'short'})})`,
      detail: `${s.status==='cancelled'?'Cancelled':'Not delivered'} — no reason on record.`,
      due: s.date, issue: 'Reason not recorded',
      type: 'sess', date: s.date, si: s.si
    });
  });

  // Priority 4: Sessions with no curriculum assigned
  allSess().filter(s=>!s.exp).forEach(s=>{
    items.push({
      pri: 4, cat: 'Planning',
      title: `Unassigned session — ${fmtD(s.date,{day:'numeric',month:'short'})} S${s.si+1}`,
      detail: 'No curriculum item assigned.',
      due: s.date, issue: 'No curriculum assigned',
      type: 'sess', date: s.date, si: s.si
    });
  });

  // Priority 5: Required curriculum items not scheduled
  const schCodes=new Set(allSess().filter(s=>s.code).map(s=>s.code));
  allCurr().filter(e=>!schCodes.has(e.code)).forEach(e=>{
    items.push({
      pri: 5, cat: 'Backlog',
      title: e.title, detail: `${e.code} — ${e.phase||'—'}`,
      due: '', issue: 'Not scheduled',
      type: 'curr', code: e.code
    });
  });

  items.sort((a,b)=>a.pri-b.pri||(a.due<b.due?-1:a.due>b.due?1:0));

  // DES-H03: 4px left border stripe per priority tier — visual hierarchy for 80yr-old scan
  const _AI_STRIPE={0:'var(--red)',1:'var(--warn)',2:'var(--warn)',3:'var(--lgrey)',4:'var(--lgrey)'};
  const CAT_CLS={Alert:'b-red',Task:'b-amber',Outcome:'b-amber',Data:'b-amber',Planning:'b-blue',Backlog:'b-grey'};
  document.getElementById('action-tbody').innerHTML=items.length
    ?items.map(it=>{
      const stripe=_AI_STRIPE[it.pri];
      const rowStyle=stripe?`border-left:4px solid ${stripe}`:'border-left:4px solid transparent';
      const titleColor=it.pri>=5?'var(--text-2)':'var(--text)';
      return `<tr style="${rowStyle}">
      <td><span class="badge ${CAT_CLS[it.cat]||'b-grey'}" style="font-size:var(--fs-3xs)">${esc(it.cat)}</span></td>
      <td><div style="font-weight:700;font-size:var(--fs-sm);color:${titleColor}">${esc(it.title)}</div>
          <div style="font-size:var(--fs-2xs);color:var(--muted)">${esc(it.detail)}</div></td>
      <td style="font-size:var(--fs-xs);color:var(--muted);white-space:nowrap">${it.due?fmtD(it.due,{day:'numeric',month:'short',year:'numeric'}):'—'}</td>
      <td><span class="badge b-amber" style="font-size:var(--fs-3xs)">${esc(it.issue)}</span></td>
      <td class="no-print">
        ${it.type==='curr'?`<button class="btn btn-xs btn-sky" onclick="showCurrDetail('${esc(it.code)}')">View</button>`:''}
        ${it.type==='sess'&&canWriteSquadron()?`<button class="btn btn-xs btn-sky" onclick="quickEdit('${esc(it.date)}',${it.si})">Edit</button>`:''}
        ${it.type==='backend'&&it.id&&canWriteSquadron()?`<button class="btn btn-xs" onclick="_closeActionItem('${esc(it.id)}')">Done</button>`:''}
      </td>
    </tr>`;}).join('')
    :`<tr><td colspan="5"><div class="empty" style="padding:18px">
        <div class="et">No items require attention.</div>
        <div class="es">All curriculum items are scheduled and outcomes are recorded.</div>
      </div></td></tr>`;
}
async function _closeActionItem(id){
  confirmAction('Mark this action item as done?',async()=>{
    try{await apiCloseActionItem(id);await reloadAndRender();showToast('Item closed.');}
    catch(e){showToast(apiErr(e),true);}
  });
}
async function runExceptionChecks(){
  try{
    const r=await api('/api/exceptions/run-checks',{method:'POST'});
    await reloadAndRender();
    showToast(r.created>0?`${r.created} alert${r.created===1?'':'s'} added.`:'No new alerts — all sessions are staffed and have rooms.');
  }catch(e){showToast(apiErr(e),true);}
}

// ═══════════════════════════════════════════════════════════
// NEEDS ATTENTION — session-level outcome recording
// ═══════════════════════════════════════════════════════════
async function loadNeedsAttentionSessions(){
  const tbody=document.getElementById('needs-attention-session-tbody');
  if(!tbody)return;
  tbody.innerHTML='<tr><td colspan="6" class="muted">Loading…</td></tr>';
  try{
    const rows=await api('/api/sessions/needs-attention');
    if(!Array.isArray(rows)||rows.length===0){
      tbody.innerHTML='<tr><td colspan="6" class="muted" style="font-style:italic">No sessions require outcome entry.</td></tr>';
      return;
    }
    tbody.innerHTML=rows.map(r=>{
      const date=r.parade_night_date||'';
      const cls=(r.training_classes||[]).map(tc=>esc(tc.display_name)).join(', ')||'—';
      const status=r.status;
      const canWrite=S.role!=='sqn_general';
      const deliverBtn=canWrite?`<button class="btn btn-primary btn-sm" onclick="sessionDeliver('${esc(r.session_id)}',this)">Deliver</button>`:'';
      const cancelBtn=canWrite?`<button class="btn btn-danger btn-sm" style="margin-left:4px" onclick="sessionCancel('${esc(r.session_id)}',this)">Cancel</button>`:'';
      const rescheduleBtn=(status==='cancelled'&&canWrite)?`<button class="btn btn-secondary btn-sm" style="margin-left:4px" onclick="sessionReschedule('${esc(r.session_id)}',this)">Reschedule</button>`:'';
      const statusBadge=status==='cancelled'?`<span style="color:var(--warn-text);font-size:var(--fs-xs)">(cancelled)</span>`:'';  /* G1: --warn on white=3.29:1(fail); --warn-text=7.0:1(pass) */
      return `<tr>
        <td>${esc(date)}</td>
        <td>${esc(r.curriculum_code||'')} ${esc(r.curriculum_title||'')}</td>
        <td>${esc(String(r.period_number||''))}</td>
        <td>${cls}</td>
        <td>${statusBadge}</td>
        <td class="no-print">${deliverBtn}${cancelBtn}${rescheduleBtn}</td>
      </tr>`;
    }).join('');
  }catch(e){tbody.innerHTML=`<tr><td colspan="6" class="warn">${esc(apiErr(e))}</td></tr>`;}
}

async function sessionDeliver(sessionId,btn){
  const note=await promptText('Mark Delivered','Delivery note (required)',{okLabel:'Confirm Delivery'});
  if(!note||!note.trim())return;
  btn.disabled=true;
  try{
    await api(`/api/sessions/${sessionId}/deliver`,{method:'POST',body:JSON.stringify({delivery_note:note.trim()})});
    loadNeedsAttentionSessions();
  }catch(e){showToast(apiErr(e),true);btn.disabled=false;}
}

async function sessionCancel(sessionId,btn){
  const reason=await promptText('Cancel Session','Cancellation reason (required)',{okLabel:'Confirm Cancellation',danger:true});
  if(!reason||!reason.trim())return;
  btn.disabled=true;
  try{
    await api(`/api/sessions/${sessionId}/cancel`,{method:'POST',body:JSON.stringify({cancellation_reason:reason.trim()})});
    loadNeedsAttentionSessions();
  }catch(e){showToast(apiErr(e),true);btn.disabled=false;}
}

async function sessionReschedule(sessionId,btn){
  // Load available parade nights so the officer can pick by date, not by internal UUID
  let nights=[];
  try{
    const data=await api('/api/parade-nights');
    nights=(data.parade_nights||data||[]).filter(pn=>!pn.is_archived&&pn.date>=(new Date().toISOString().slice(0,10)));
  }catch(e){showToast(apiErr(e),true);return;}
  if(nights.length===0){showToast('No upcoming Parade Nights found. Please create a Parade Night first.',true);return;}
  const opts=nights.map((pn,i)=>`${i+1}: ${pn.date}${pn.term?' ('+pn.term+')':''}`).join('\n');
  const choice=await promptText('Reschedule Session',`Select a Parade Night (enter number):\n${opts}`,{okLabel:'Select'});
  if(!choice)return;
  const idx=parseInt(choice,10)-1;
  if(isNaN(idx)||idx<0||idx>=nights.length){showToast('Invalid selection.',true);return;}
  const pnid=nights[idx].id||nights[idx].parade_night_id;
  const period=await promptText('Reschedule Session','Period number',{defaultValue:'1',okLabel:'Confirm'});
  if(period===null)return;
  btn.disabled=true;
  try{
    await api(`/api/sessions/${sessionId}/reschedule`,{method:'POST',body:JSON.stringify({parade_night_id:pnid,period_number:parseInt(period)||1})});
    loadNeedsAttentionSessions();
  }catch(e){showToast(apiErr(e),true);btn.disabled=false;}
}
