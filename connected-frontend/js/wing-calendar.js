// Main TMS module: Wing HQ Calendar -- grid/list views, event detail,
// create/edit/archive, and the Annual Program overlay.
// Extracted verbatim from connected-frontend/index.html (stabilisation Phase 4,
// C6). Top-level function declarations and side-effect-free let/const only;
// loaded as a classic script BEFORE the inline bootstrap, so everything here
// is defined before any page-load code runs. Statements with load-time
// effects stay in index.html in their original order. Parity is proven by
// tools/architecture/frontend_parity.mjs.

// ══════════════════════════════════════════
//  WING HQ CALENDAR
// ══════════════════════════════════════════

// State
let _wingCalEvents=[];
let _wingCalWingId=null;
// REM-133: archive existed with no way to see or restore an archived Wing HQ
// event -- separate lazily-fetched list, kept apart from _wingCalEvents
// (which also carries source:'activity' rows the grid view renders) so this
// only ever affects the table view, matching "+ New Event"'s own
// single-wing-only restriction.
let _wcArchivedEvents=[];
let _wcDetailEventId=null;
let _wcView='grid';

// ─── Importance badge / label ────────────────────────────────────────────────
const _WC_IMP_BADGE={
  must_attend:'badge-red', key_event:'b-blue', recommended:'b-ok',
  optional:'b-grey', home_parade:'b-grey', noting:'b-grey',
};
const _WC_IMP_LABEL={
  must_attend:'Must Attend', key_event:'Key Event', recommended:'Recommended',
  optional:'Optional', home_parade:'Home Parade', noting:'Noting',
};
const _WC_TYPE_LABEL={
  wing_event:'Wing Event', cadet_training:'Cadet Training', adult_training:'Adult Training',
  meeting:'Meeting', competition:'Competition', ceremony:'Ceremony', course:'Course',
  staff_activity:'Staff Activity', home_parade:'Home Parade', public_holiday:'Public Holiday',
  school_holiday:'School Holiday', noting:'Noting',
};

// ─── Load Wing HQ Calendar page ──────────────────────────────────────────────
async function loadWingCalendar(){
  const body=document.getElementById('wc-body');
  if(!body) return;
  const year=document.getElementById('wc-year-sel')?.value||'2026';
  if(String(_wcGridDate.getFullYear())!==year){
    const curYear=new Date().getFullYear();
    _wcGridDate=new Date(+year, +year===curYear?new Date().getMonth():0, 1);
  }
  const isWingWrite=['wing_admin','national_admin','system_admin'].includes(S.role);
  const btn=document.getElementById('wc-create-btn');
  if(btn) btn.style.display=isWingWrite?'':'none';

  // Populate wing selector for national/system_admin, hide for wing_admin.
  // REM-13 Phase A: national_admin/system_admin also get an "All Wings" entry
  // -- previously they could only inspect one wing's calendar at a time, with
  // no true cross-wing rollup anywhere in the app.
  const wingSel=document.getElementById('wc-wing-sel');
  if(wingSel){
    const isNatOrSys=['national_admin','system_admin'].includes(S.role);
    wingSel.style.display=isNatOrSys?'':'none';
    if(isNatOrSys && wingSel.options.length<=1 && S.wings){
      wingSel.appendChild(new Option('All Wings','__all__'));
      S.wings.forEach(w=>{ const o=new Option(w.code||w.name,w.wing_id); wingSel.appendChild(o); });
    }
  }
  // Get wing_id from session (wing_admin has it in session; national/sys use selector)
  const wid=(S.session&&S.session.wing_id)||wingSel?.value||'';
  const allWings=wid==='__all__';
  // "+ New Event" needs one specific wing to attach the event to -- ambiguous
  // (and rejected server-side) while "All Wings" is selected.
  if(btn && allWings) btn.style.display='none';
  // REM-133: "Show archived" is scoped to a single wing (same restriction as
  // "+ New Event" above) -- restoring while "All Wings" is selected is
  // ambiguous about which wing's write authority applies.
  const showArchivedRow=document.getElementById('wc-show-archived-row');
  if(showArchivedRow) showArchivedRow.style.display=(isWingWrite&&!allWings)?'flex':'none';
  _wcArchivedEvents=[];
  const archivedChk=document.getElementById('wc-show-archived');
  if(archivedChk) archivedChk.checked=false;
  if(!wid){
    body.innerHTML='<p class="muted">No wing scope. Select a wing or log in as Wing Admin.</p>';
    return;
  }
  _wingCalWingId=wid;
  body.innerHTML='<p class="muted">Loading…</p>';
  try{
    const eventsUrl=allWings?`/api/wing-calendar/events?year=${year}`:`/api/wing-calendar/events?wing_id=${wid}&year=${year}`;
    const actsUrl=allWings?'/api/activities?scope_type=national':`/api/activities?scope_type=wing&scope_id=${wid}`;
    const [wingEvents,actsResp]=await Promise.all([
      api(eventsUrl),
      api(actsUrl).catch(()=>({items:[]})),
    ]);
    // Activities already have their own full national/wing scope-aware
    // backend (CEA + holiday merging, inheritance) -- previously never
    // wired into this page at all, so they were entirely invisible here.
    // Normalized into the same {id,title,start_date,end_date} shape
    // renderWingCalendarGrid() already expects, tagged source:'activity'
    // so the grid can render/click-handle them distinctly from real Wing
    // Events (different backing table -- see renderWingCalendarGrid()).
    const acts=(actsResp&&actsResp.items||[]).map(a=>({
      id:a.activity_id, title:a.activity_name,
      start_date:a.date_start, end_date:a.date_end||a.date_start,
      source:'activity', owning_org_label:a.owning_org_label, activity_type:a.activity_type,
    }));
    _wingCalEvents=wingEvents.map(e=>({...e,source:'wing_event'})).concat(acts);
    renderWingCalendar();
  }catch(e){ body.innerHTML=`<p class="muted">Could not load the Wing HQ Calendar: ${esc(apiErr(e))}</p>`; }
}

function _wcApplyTypeImpFilters(rows){
  const typeF=document.getElementById('wc-type-filter')?.value||'';
  const impF=document.getElementById('wc-imp-filter')?.value||'';
  if(typeF) rows=rows.filter(e=>e.event_type===typeF);
  if(impF)  rows=rows.filter(e=>e.planning_importance===impF);
  return rows;
}
function _wcFilteredRows(){
  return _wcApplyTypeImpFilters(_wingCalEvents);
}
function _wcSetView(mode){
  _wcView=mode;
  document.getElementById('wc-view-grid-btn')?.classList.toggle('active',mode==='grid');
  document.getElementById('wc-view-table-btn')?.classList.toggle('active',mode==='table');
  document.getElementById('wc-grid-nav').style.display=mode==='grid'?'flex':'none';
  renderWingCalendar();
}
function _wcShiftMonth(delta){
  _wcGridDate=new Date(_wcGridDate.getFullYear(),_wcGridDate.getMonth()+delta,1);
  const yr=String(_wcGridDate.getFullYear());
  const yrSel=document.getElementById('wc-year-sel');
  if(yrSel&&[...yrSel.options].some(o=>o.value===yr)&&yrSel.value!==yr){ yrSel.value=yr; loadWingCalendar(); return; }
  renderWingCalendar();
}
const _WC_IMP_COLOR={must_attend:'#e51937',key_event:'#004b8d',recommended:'#1a7f4b',optional:'#7a8590',home_parade:'#7a8590',noting:'#7a8590'};
function renderWingCalendarGrid(){
  const body=document.getElementById('wc-body');
  const rows=_wcFilteredRows();
  const y=_wcGridDate.getFullYear(), m=_wcGridDate.getMonth();
  const lbl=document.getElementById('wc-grid-month-label');
  if(lbl)lbl.textContent=_wcGridDate.toLocaleDateString('en-AU',{month:'long',year:'numeric'});

  const byDate={};
  rows.forEach(e=>{
    const start=new Date(e.start_date+'T00:00:00'), end=new Date((e.end_date||e.start_date)+'T00:00:00');
    for(let d=new Date(start); d<=end; d.setDate(d.getDate()+1)){
      const key=d.toISOString().slice(0,10);
      (byDate[key]=byDate[key]||[]).push(e);
    }
  });

  const firstOfMonth=new Date(y,m,1);
  const startOffset=(firstOfMonth.getDay()+6)%7; // Monday=0
  const gridStart=new Date(y,m,1-startOffset);
  const todayKey=new Date().toISOString().slice(0,10);
  const days=[];
  for(let i=0;i<42;i++){ const d=new Date(gridStart); d.setDate(gridStart.getDate()+i); days.push(d); }
  // Trim trailing all-empty rows beyond the 5th week if the 6th week is entirely next month
  const weeks=[]; for(let i=0;i<days.length;i+=7) weeks.push(days.slice(i,i+7));
  while(weeks.length>4 && weeks[weeks.length-1].every(d=>d.getMonth()!==m)) weeks.pop();

  const dayNames=['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
  body.innerHTML=`<table class="cal-grid-table">
    <thead><tr>${dayNames.map(n=>`<th>${n}</th>`).join('')}</tr></thead>
    <tbody>${weeks.map(week=>`<tr>${week.map(d=>{
      const key=d.toISOString().slice(0,10);
      const evts=byDate[key]||[];
      const outside=d.getMonth()!==m;
      const isToday=key===todayKey;
      const shown=evts.slice(0,3);
      const extra=evts.length-shown.length;
      // REM-13 Phase A: merged Activity chips (e.source==='activity') are a
      // different backing table than WingHQEvent -- their id would 404
      // against openWingEventDetail(), so they get no click handler at all
      // (same "info-only chip" convention renderCal()'s squadron grid
      // already uses for Activities) and a visually distinct dashed style
      // plus a wing label in the tooltip so a national "All Wings" view can
      // tell which wing/source each chip is from at a glance.
      return `<td class="cal-grid-cell${outside?' outside':''}${isToday?' today':''}">
        <div class="cal-grid-daynum">${d.getDate()}</div>
        ${shown.map(e=>e.source==='activity'
          ?`<span class="cal-grid-evt" style="background:#eef1f4;color:#455560;border:1px dashed #9aa5ad" title="${esc(e.title)}${e.owning_org_label?' — '+esc(e.owning_org_label):''} (Activity)">${esc(e.title)}</span>`
          :`<span class="cal-grid-evt" style="background:${_WC_IMP_COLOR[e.planning_importance]||'#7a8590'}" title="${esc(e.title)}${e.wing_code?' — '+esc(e.wing_code):''}" onclick="openWingEventDetail('${esc(e.id)}')">${esc(e.title)}</span>`
        ).join('')}
        ${extra>0?`<span class="cal-grid-more">+${extra} more</span>`:''}
      </td>`;
    }).join('')}</tr>`).join('')}</tbody>
  </table>`;
}
function renderWingCalendar(){
  const body=document.getElementById('wc-body');
  if(!body) return;
  const isWingWrite=['wing_admin','national_admin','system_admin'].includes(S.role);

  if(_wcView==='grid'){
    document.getElementById('wc-grid-nav').style.display='flex';
    renderWingCalendarGrid();
    if(!_wingCalEvents.length){
      body.innerHTML+=`<p class="muted" style="margin-top:10px">No Wing HQ events for this year yet. Use <strong>+ New Event</strong> to add one, or import from your Wing Master Schedule.</p>`;
    }
    return;
  }
  document.getElementById('wc-grid-nav').style.display='none';

  if(!_wingCalEvents.length){
    body.innerHTML='<p class="muted">No Wing HQ events for this year. Use <strong>+ New Event</strong> to add one, or import from your Wing Master Schedule.</p>';
    return;
  }
  const showingArchived=(document.getElementById('wc-show-archived')||{}).checked;
  const rows=_wcFilteredRows().concat(showingArchived?_wcApplyTypeImpFilters(_wcArchivedEvents):[]);
  if(!rows.length){
    body.innerHTML='<p class="muted">No events match the current filters.</p>';
    return;
  }

  body.innerHTML=`<table class="data-table"><thead><tr>
    <th>Date</th><th>Title</th><th>Type</th><th>Importance</th><th>Audience</th><th>Action?</th>
    ${isWingWrite?'<th></th>':''}
  </tr></thead><tbody>`+
  rows.map(e=>{
    const dateStr=e.start_date+(e.end_date&&e.end_date!==e.start_date?' – '+e.end_date:'');
    const aud=(e.audience||[]).join(', ')||'—';
    // REM-13 Phase A: merged Activity rows (e.source==='activity') are a
    // different backing table than WingHQEvent -- no click-through, no
    // Edit/Archive (those act on a wing-calendar event id), and the
    // WingHQEvent-only columns (type/importance/action-needed) degrade to
    // '—' instead of leaking the literal string "undefined" into the DOM.
    const isAct=e.source==='activity';
    // REM-133: an archived event is unreachable via _get_event_or_404 (see
    // that helper's own is_archived check backend-side), so it gets no
    // click-through either -- same convention as Activity rows above.
    const isArchived=!!e.is_archived;
    const clickable=!isAct&&!isArchived;
    return `<tr${clickable?' style="cursor:pointer" onclick="openWingEventDetail(\''+esc(e.id)+'\')"':(isArchived?' style="opacity:.6"':'')}>
      <td>${esc(dateStr)}</td>
      <td><strong>${esc(e.title)}</strong>${isAct?' <span class="badge b-grey" style="font-size:var(--fs-3xs)">Activity</span>':''}${isArchived?' <span class="badge b-grey" style="font-size:var(--fs-3xs)">Archived</span>':''}${e.location?`<br><span class="muted" style="font-size:var(--fs-2xs)">${esc(e.location)}</span>`:''}</td>
      <td>${isAct?'—':`<span class="badge b-grey" style="font-size:var(--fs-3xs)">${esc(_WC_TYPE_LABEL[e.event_type]||e.event_type)}</span>`}</td>
      <td>${isAct?'—':`<span class="badge ${_WC_IMP_BADGE[e.planning_importance]||'b-grey'}">${esc(_WC_IMP_LABEL[e.planning_importance]||e.planning_importance)}</span>`}</td>
      <td style="font-size:var(--fs-2xs)">${esc(aud)}</td>
      <td>${(!isAct&&!isArchived&&e.requires_squadron_action)?'<span class="badge b-amber">Action needed</span>':''}</td>
      ${isWingWrite?`<td>${isAct?'':(isArchived
        ?`<button class="btn-xs btn-ok" onclick="event.stopPropagation();doRestoreWingEvent('${esc(e.id)}','${_jsAttr(e.title||'')}')">Restore</button>`
        :`<button class="btn-xs btn-secondary" onclick="event.stopPropagation();editWingEvent('${esc(e.id)}')">Edit</button>
        <button class="btn-xs btn-danger" onclick="event.stopPropagation();archiveWingEvent('${esc(e.id)}')">Archive</button>`)}</td>`:''}
    </tr>`;
  }).join('')+
  `</tbody></table>`;
}

// ─── Wing Event Detail Modal ──────────────────────────────────────────────────
async function openWingEventDetail(eventId){
  _wcDetailEventId=eventId;
  const body=document.getElementById('we-detail-body');
  if(!body) return;
  body.innerHTML='<p class="muted">Loading…</p>';
  openModal('m-wing-event-detail');
  try{
    const e=await api(`/api/wing-calendar/events/${eventId}`);
    const dateStr=e.start_date+(e.end_date&&e.end_date!==e.start_date?' – '+e.end_date:'');
    const impBadge=`<span class="badge ${_WC_IMP_BADGE[e.planning_importance]||'b-grey'}">${esc(_WC_IMP_LABEL[e.planning_importance]||e.planning_importance)}</span>`;
    const typeBadge=`<span class="badge b-grey">${esc(_WC_TYPE_LABEL[e.event_type]||e.event_type)}</span>`;
    const wcWingCode=(S.session&&S.session.wing_code)||'Wing';
    const srcBadge=`<span class="badge" style="background:#ede9fe;color:#4c1d95">${esc(wcWingCode)} HQ Calendar</span>`;

    let curLinks='';
    if(e.curriculum_links&&e.curriculum_links.length){
      curLinks=`<div style="margin-top:10px"><div style="font-size:var(--fs-xs);font-weight:700;margin-bottom:4px">Linked Curriculum</div>`+
        e.curriculum_links.map(l=>`<div style="font-size:var(--fs-xs);padding:3px 0"><span class="badge b-grey">${esc(l.curriculum_code||'—')}</span> ${esc(l.curriculum_title||'')}</div>`).join('')+
        `</div>`;
    }
    let sqnStatus='';
    if(e.squadron_status){
      const ss=e.squadron_status;
      const ssCol={'reviewed':'badge-green','preparation_planned':'badge-green','not_applicable':'b-grey'}[ss.status]||'b-grey';
      sqnStatus=`<div style="margin-top:10px;padding:8px;background:var(--bg);border-radius:6px">
        <div style="font-size:var(--fs-xs);font-weight:700;margin-bottom:4px">Your Squadron's Status</div>
        <span class="badge ${ssCol}">${esc(_cap(ss.status.replace(/_/g,' ')))}</span>
        ${ss.notes?`<span style="font-size:var(--fs-xs);margin-left:6px">${esc(ss.notes)}</span>`:''}
      </div>`;
    }
    body.innerHTML=`
      <div style="margin-bottom:10px">${srcBadge} ${impBadge} ${typeBadge}</div>
      <div style="font-size:var(--fs-lg);font-weight:800;margin-bottom:8px">${esc(e.title)}</div>
      <div style="display:flex;gap:16px;font-size:var(--fs-sm);flex-wrap:wrap;margin-bottom:8px">
        <div><span class="muted">Date:</span> <strong>${esc(dateStr)}</strong></div>
        ${e.location?`<div><span class="muted">Location:</span> <strong>${esc(e.location)}</strong></div>`:''}
        ${e.start_time?`<div><span class="muted">Time:</span> <strong>${esc(e.start_time)}${e.end_time?' – '+esc(e.end_time):''}</strong></div>`:''}
        <div><span class="muted">Audience:</span> <strong>${esc((e.audience||[]).join(', ')||'—')}</strong></div>
      </div>
      ${e.description?`<p style="font-size:var(--fs-sm);margin-bottom:8px">${esc(e.description)}</p>`:''}
      ${e.notes?`<p style="font-size:var(--fs-xs);color:var(--steel);margin-bottom:8px">${esc(e.notes)}</p>`:''}
      ${e.requires_squadron_action?'<div class="alert a-warn" style="font-size:var(--fs-sm);margin-bottom:8px">This event requires squadron action. Mark your preparation status below.</div>':''}
      ${curLinks}${sqnStatus}`;

    const markBtn=document.getElementById('we-detail-mark-btn');
    const planBtn=document.getElementById('we-detail-plan-btn');
    const isSqnAdmin=['sqn_admin'].includes(S.role);
    if(markBtn) markBtn.style.display=isSqnAdmin&&(!e.squadron_status||e.squadron_status.status==='not_reviewed')?'':'none';
    if(planBtn) planBtn.style.display=isSqnAdmin?'':'none';
  }catch(ex){ body.innerHTML=`<p class="muted">Could not load this event's details: ${esc(apiErr(ex))}</p>`; }
}

async function markWingEventReviewed(){
  if(!_wcDetailEventId) return;
  try{
    await api(`/api/wing-calendar/events/${_wcDetailEventId}/squadron-status`,{
      method:'PATCH', body:{status:'reviewed'},
    });
    openWingEventDetail(_wcDetailEventId);
  }catch(e){ showToast(apiErr(e),true); }
}
async function markWingEventPlanned(){
  if(!_wcDetailEventId) return;
  try{
    await api(`/api/wing-calendar/events/${_wcDetailEventId}/squadron-status`,{
      method:'PATCH', body:{status:'preparation_planned'},
    });
    openWingEventDetail(_wcDetailEventId);
  }catch(e){ showToast(apiErr(e),true); }
}

// ─── Create / Edit Wing Event (wing_admin only) ──────────────────────────────
let _weEditId=null;

function openWingEventModal(existingEvent){
  _weEditId=existingEvent?existingEvent.id:null;
  document.getElementById('we-modal-title').textContent=existingEvent?'Edit Wing HQ Event':'New Wing HQ Event';
  document.getElementById('we-edit-id').value=_weEditId||'';
  document.getElementById('we-title').value=existingEvent?.title||'';
  document.getElementById('we-type').value=existingEvent?.event_type||'wing_event';
  document.getElementById('we-start').value=existingEvent?.start_date||'';
  document.getElementById('we-end').value=existingEvent?.end_date||'';
  document.getElementById('we-start-time').value=existingEvent?.start_time||'';
  document.getElementById('we-end-time').value=existingEvent?.end_time||'';
  document.getElementById('we-importance').value=existingEvent?.planning_importance||'key_event';
  document.getElementById('we-location').value=existingEvent?.location||'';
  document.getElementById('we-sqn-action').checked=existingEvent?.requires_squadron_action||false;
  document.getElementById('we-anchor').checked=existingEvent?.is_planning_anchor||false;
  document.getElementById('we-notes').value=existingEvent?.notes||'';
  // Audience checkboxes
  const audSet=new Set(existingEvent?.audience||[]);
  document.querySelectorAll('.we-aud').forEach(cb=>{ cb.checked=audSet.has(cb.value); });
  document.getElementById('we-msg').textContent='';
  openModal('m-wing-event');
}

async function editWingEvent(eventId){
  try{
    const e=await api(`/api/wing-calendar/events/${eventId}`);
    openWingEventModal(e);
  }catch(ex){ showToast(apiErr(ex),true); }
}

async function saveWingEvent(){
  const msg=document.getElementById('we-msg');
  const title=document.getElementById('we-title').value.trim();
  const start=document.getElementById('we-start').value;
  if(!title||!start){ msg.textContent='Title and Start Date are required.'; return; }

  const aud=[...document.querySelectorAll('.we-aud:checked')].map(c=>c.value);
  const body={
    title,
    event_type:document.getElementById('we-type').value,
    start_date:start,
    end_date:document.getElementById('we-end').value||null,
    start_time:document.getElementById('we-start-time').value||null,
    end_time:document.getElementById('we-end-time').value||null,
    planning_importance:document.getElementById('we-importance').value,
    location:document.getElementById('we-location').value||null,
    requires_squadron_action:document.getElementById('we-sqn-action').checked,
    is_planning_anchor:document.getElementById('we-anchor').checked,
    notes:document.getElementById('we-notes').value||null,
    audience:aud,
  };
  try{
    const isEditEvent=!!_weEditId;
    if(_weEditId){
      await api(`/api/wing-calendar/events/${_weEditId}`,{method:'PATCH',body});
    } else {
      const wid=_wingCalWingId||(S.session&&S.session.wing_id)||'';
      if(!wid){ msg.textContent='No wing scope.'; return; }
      await api(`/api/wing-calendar/events?wing_id=${wid}`,{method:'POST',body});
    }
    showToast(isEditEvent?'Event updated.':'Event created.');
    closeModal('m-wing-event');
    await loadWingCalendar();
  }catch(e){ msg.textContent=apiErr(e); }
}

async function archiveWingEvent(eventId){
  confirmAction('Archive this Wing HQ event? It will no longer appear in squadron overlays, but this can be undone from "Show archived".',async()=>{
    try{
      await api(`/api/wing-calendar/events/${eventId}/archive`,{method:'POST',body:{}});
      await loadWingCalendar();
    }catch(e){ showToast(apiErr(e),true); }
  });
}
async function _wcToggleShowArchived(){
  const checked=(document.getElementById('wc-show-archived')||{}).checked;
  if(!checked){ _wcArchivedEvents=[]; renderWingCalendar(); return; }
  if(!_wingCalWingId || _wingCalWingId==='__all__'){ renderWingCalendar(); return; }
  const year=document.getElementById('wc-year-sel')?.value||'2026';
  try{
    const all=await api(`/api/wing-calendar/events?wing_id=${_wingCalWingId}&year=${year}&include_archived=true`);
    _wcArchivedEvents=all.filter(e=>e.is_archived).map(e=>({...e,source:'wing_event'}));
  }catch(e){ showToast('Could not load archived events: '+apiErr(e), true); }
  renderWingCalendar();
}
async function doRestoreWingEvent(eventId, title){
  try{
    await api(`/api/wing-calendar/events/${eventId}/restore`,{method:'POST'});
    showToast(`'${title}' restored.`);
    // Refresh both lists directly rather than via loadWingCalendar() -- that
    // would reset the "Show archived" checkbox and lose the user's place.
    const year=document.getElementById('wc-year-sel')?.value||'2026';
    const [activeEvents,allEvents]=await Promise.all([
      api(`/api/wing-calendar/events?wing_id=${_wingCalWingId}&year=${year}`),
      api(`/api/wing-calendar/events?wing_id=${_wingCalWingId}&year=${year}&include_archived=true`),
    ]);
    const acts=_wingCalEvents.filter(e=>e.source==='activity');
    _wingCalEvents=activeEvents.map(e=>({...e,source:'wing_event'})).concat(acts);
    _wcArchivedEvents=allEvents.filter(e=>e.is_archived).map(e=>({...e,source:'wing_event'}));
    renderWingCalendar();
  }catch(e){ showToast('Could not restore: '+apiErr(e), true); }
}

// ─── Annual Program Wing HQ Events overlay ────────────────────────────────────
let _pyWingEvents=[];

async function _loadAndRenderWingEventsOverlay(wingId, year){
  const card=document.getElementById('py-wing-events-card');
  if(!card) return;
  if(!wingId){ card.style.display='none'; return; }
  try{
    _pyWingEvents=await api(`/api/wing-calendar/squadron-overlay?wing_id=${wingId}&year=${year}`);
    card.style.display='';
    _renderWingEventsOverlay();
  }catch(e){
    // Non-fatal: wing calendar may not have events yet
    card.style.display='none';
  }
}

function _renderWingEventsOverlay(){
  const body=document.getElementById('py-wing-events-body');
  if(!body) return;
  const impF=document.getElementById('py-we-imp-filter')?.value||'';
  let rows=_pyWingEvents;
  if(impF) rows=rows.filter(e=>e.planning_importance===impF);

  if(!rows.length){
    body.innerHTML='<p class="muted" style="font-size:var(--fs-xs)">No Wing HQ events for this year.</p>';
    return;
  }
  body.innerHTML=`<table class="data-table" style="font-size:var(--fs-xs)"><thead><tr>
    <th>Date</th><th>Title</th><th>Importance</th><th>Audience</th><th>Status</th><th></th>
  </tr></thead><tbody>`+
  rows.map(e=>{
    const ds=e.start_date+(e.end_date&&e.end_date!==e.start_date?' – '+e.end_date:'');
    const ss=e.squadron_status;
    const ssLabel=ss?_cap(ss.status.replace(/_/g,' ')):'Not reviewed';
    const ssCls={'reviewed':'badge-green','preparation_planned':'badge-green','not_applicable':'b-grey'}[ss?.status]||'b-grey';
    return `<tr>
      <td>${esc(ds)}</td>
      <td><strong>${esc(e.title)}</strong>${e.location?`<br><span class="muted">${esc(e.location)}</span>`:''}</td>
      <td><span class="badge ${_WC_IMP_BADGE[e.planning_importance]||'b-grey'}" style="font-size:var(--fs-3xs)">${esc(_WC_IMP_LABEL[e.planning_importance]||e.planning_importance)}</span></td>
      <td style="font-size:var(--fs-2xs)">${esc((e.audience||[]).join(', ')||'—')}</td>
      <td><span class="badge ${ssCls}" style="font-size:var(--fs-3xs)">${esc(ssLabel)}</span></td>
      <td><button class="btn-xs btn-secondary" onclick="openWingEventDetail('${esc(e.id)}')">Detail</button></td>
    </tr>`;
  }).join('')+
  `</tbody></table>`;
}
function _renderAnnualCalendar(ap){
  // Index wing events by date for the month grid
  const WE={};
  (ap.wing_events||[]).forEach(e=>{
    let cur=new Date((e.start_date||'')+'T00:00:00');
    const endD=new Date((e.end_date||e.start_date||'')+'T00:00:00');
    while(cur<=endD){
      const ds=cur.toISOString().slice(0,10);
      if(!WE[ds]) WE[ds]=[];
      WE[ds].push(e);
      cur.setDate(cur.getDate()+1);
    }
  });
  window._AP_DATA=window._AP_DATA||{};
  window._AP_DATA.WE=WE;

  // Call original but we patch _renderApMonth via WE global
  const result=_origRenderAnnualCalendar(ap);

  // After calendar rendered, add wing event legend entry
  return result.replace(
    '<span style="color:var(--muted)">Click any date for detail.</span>',
    '<span style="display:flex;align-items:center;gap:4px"><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#ede9fe;border:1px solid #c4b5fd"></span>Wing HQ event</span><span style="color:var(--muted)">Click any date for detail.</span>'
  );
}
function _apShowDateDetail(ds){
  _origApShowDateDetail(ds);
  const D=window._AP_DATA;
  if(!D||!D.WE) return;
  const we=D.WE[ds]||[];
  if(!we.length) return;
  const body=document.getElementById('ap-detail-body');
  if(!body) return;
  let h='<div style="margin-top:8px">';
  we.forEach(e=>{
    const bc=e.planning_importance==='must_attend'?'#7c3aed':e.planning_importance==='key_event'?'#8b5cf6':'#a78bfa';
    h+=`<div style="padding:6px 8px;border-left:3px solid ${bc};margin-bottom:5px;background:#f5f3ff;border-radius:0 4px 4px 0;cursor:pointer"
      onclick="openWingEventDetail('${esc(e.id)}')">
      <span class="badge" style="background:#ede9fe;color:#4c1d95;font-size:var(--fs-3xs)">${esc((S.session&&S.session.wing_code)||'Wing')} HQ</span>
      <strong style="font-size:var(--fs-xs);margin-left:4px">${esc(e.title)}</strong>
      <span class="badge ${_WC_IMP_BADGE[e.planning_importance]||'b-grey'}" style="font-size:var(--fs-3xs);margin-left:4px">${esc(_WC_IMP_LABEL[e.planning_importance]||e.planning_importance)}</span>
    </div>`;
  });
  h+='</div>';
  body.innerHTML+=h;
}
