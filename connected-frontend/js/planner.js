// Main TMS module: Training Planner -- planning years, mission table, year map,
// anchor events, term planner, night builder, long range, rooms & staff,
// planning checks.
// Extracted verbatim from connected-frontend/index.html (stabilisation Phase 4,
// C6). Top-level function declarations and side-effect-free let/const only;
// loaded as a classic script BEFORE the inline bootstrap, so everything here
// is defined before any page-load code runs. Statements with load-time
// effects stay in index.html in their original order. Parity is proven by
// tools/architecture/frontend_parity.mjs.

// ═══════════════════════════════════════════════════════════
//  TRAINING PLANNER MODULE
// ═══════════════════════════════════════════════════════════

// ── Module state ──
const P = {
  years: [],          // planning years for current user scope
  anchors: [],        // anchor events for selected year
  currentYearId: null,
  currentYearInt: null,
  currentDateId: null,  // planning date ID (from parade_dates table)
  currentPnId: null,    // real parade_night_id (from parade_nights table)
  _directPnId: null,    // set after parade night creation for auto-navigation
  locations: [],
  facilitators: [],
  builderSessions: [],
};

const _IMPORTANCE_LABELS = { must_attend:'Must Attend', key_event:'Key Event', optional:'Optional' };
const _EVENT_TYPE_LABELS = {
  ceremonial:'Ceremonial', fieldcraft:'Fieldcraft', adventure_training:'Adventure Training',
  dining_in:'Dining In', inspection:'Inspection', sport:'Sport', community:'Community',
  admin:'Admin', other:'Other'
};
const _CADET_GROUPS = ['orientation','initial','junior','intermediate','senior'];

// YR-3: choose the training year a unit is most likely to want on open.
// Preference order: the active year matching today's calendar year, then the
// nearest active year still ahead, then the most recent active year behind,
// then whatever exists. Previously this was "first active in a year-descending
// list", i.e. always the newest year created.
function _pickDefaultYear(list){
  const yrs=(list||[]).filter(Boolean);
  if(!yrs.length) return null;
  // Prefer the year the server marks 'current' (derived from wing-local timezone).
  // Falls back to calendar arithmetic for entries from older API responses.
  const cur=yrs.find(y=>y.state==='current');
  if(cur) return cur;
  const now=new Date().getFullYear();
  const exact=yrs.find(y=>parseInt(y.year,10)===now);
  if(exact) return exact;
  const ahead=yrs.filter(y=>y.state==='future'||parseInt(y.year,10)>now).sort((a,b)=>a.year-b.year);
  if(ahead.length) return ahead[0];
  const behind=yrs.filter(y=>y.state==='past'||parseInt(y.year,10)<now).sort((a,b)=>b.year-a.year);
  if(behind.length) return behind[0];
  return yrs[0];
}

// ── Populate year selects; auto-select active/first year and return its ID ──
function _ynPopulateYearSelects() {
  if (!P.years) return;
  // Wing admin: filter by selected squadron if filter is active
  const sqnFilterSel = document.getElementById('py-sqn-filter');
  const filterSqnId = sqnFilterSel ? sqnFilterSel.value : '';
  const visibleYears = filterSqnId
    ? P.years.filter(y=>y.unit_id===filterSqnId)
    : P.years;
  // YR-3: prefer the year actually being run today. The list arrives ordered
  // year DESC, so "first active" meant "highest year ever created" -- open a
  // year for a future season and the whole app silently jumped to it.
  // currentYearId null now has TWO meanings: nothing chosen yet, and "the year
  // the user chose has no row". Only the first should trigger a default, so
  // currentYearInt is what says a choice has been made. Without this, stepping
  // onto an unconfigured year was instantly undone by the default-picker.
  if(!P.currentYearId && !P.currentYearInt && visibleYears.length) {
    const active = _pickDefaultYear(visibleYears.filter(y=>y.planning_year_id));
    if(active) P.currentYearId = active.planning_year_id;
  }
  const selIds = [
    'mission-year-sel','py-select','anch-year-sel','term-year-sel',
    'builder-year-sel','lr-year-sel','checks-year-sel'
  ];
  const showUnitPrefix = ['wing_admin','national_admin','system_admin'].includes(S.role||'');
  selIds.forEach(sid=>{
    const el = document.getElementById(sid);
    if(!el) return;
    el.innerHTML = '<option value="">— select a year —</option>';
    // py-select respects squadron filter; other selectors show all
    const yrs = (sid==='py-select') ? visibleYears : P.years;
    yrs.forEach(y=>{
      const o = document.createElement('option');
      o.value = y.planning_year_id;
      const prefix = showUnitPrefix
        ? (y.unit_code ? `${y.unit_code} — ` : y.wing_code ? `${y.wing_code} — ` : '')
        : '';
      const _stag = y.state==='past'?' — record':y.state==='future'?' — upcoming':'';
      o.textContent = prefix + String(y.year) + _stag;
      el.appendChild(o);
    });
    if(P.currentYearId) el.value = P.currentYearId;
  });
  _renderPyActionBtns();
}

async function _loadPlanningYears() {
  try {
    await _ynFetchYears();
    if (document.getElementById('ynLabel')) ynInit();
    return P.currentYearId || null;
  } catch(e) { console.warn('planning years load failed', e); return null; }
}

// ── Planning Year rename/archive/restore -- wires the existing, previously-
// unused PATCH /api/planning/years/{id} into the UI, matching the confirm-
// dialog pattern already established for Wings/Squadrons/Accounts. ──
function _renderPyActionBtns(){
  const el=document.getElementById('py-action-btns'); if(!el)return;
  const y=(P.years||[]).find(x=>x.planning_year_id===P.currentYearId);
  if(!y){ el.innerHTML=''; return; }
  const canRemediate=['wing_admin','system_admin'].includes(S.role||'');
  el.innerHTML=
    `<button class="btn btn-out btn-xs" onclick="exportAnnualProgram()" title="Export annual program to Excel">Export Annual</button>`+
    `<button class="btn btn-out btn-xs" onclick="exportSchedule()" title="Export schedule to Excel">Export Schedule</button>`+
    (canRemediate
      ? (y.active_status
          ? `<button class="btn btn-out btn-xs plan-write-el" style="display:none;border-color:var(--red);color:var(--status-text-danger)" onclick="doArchivePlanningYear()">Archive</button>`
          : `<button class="btn btn-ok btn-xs plan-write-el" style="display:none" onclick="doRestorePlanningYear()">Restore</button>`)
      : '')+
    (canRemediate ? `<button class="btn btn-out btn-xs plan-write-el" style="display:none;border-color:var(--red);color:var(--status-text-danger)" onclick="doDeletePlanningYear()">Delete…</button>` : '');
  document.querySelectorAll('#py-action-btns .plan-write-el').forEach(b=>{b.style.display=canWritePlan()?'inline-flex':'none';});
}
async function doArchivePlanningYear(){
  const y=(P.years||[]).find(x=>x.planning_year_id===P.currentYearId);
  if(!y)return;
  confirmAction(`Archive the ${y.name||y.year} year? It disappears from active selectors. Historical records are preserved and it can be restored later.`,async()=>{
    try{
      await api('/api/planning/years/'+P.currentYearId,{method:'PATCH',body:JSON.stringify({active_status:false,version:y.version})});
      showToast('Year archived.');
      await _loadPlanningYears();
    }catch(e){ showToast('Could not archive: '+apiErr(e), true); }
  });
}
async function doRestorePlanningYear(){
  const y=(P.years||[]).find(x=>x.planning_year_id===P.currentYearId);
  if(!y)return;
  try{
    await api('/api/planning/years/'+P.currentYearId,{method:'PATCH',body:JSON.stringify({active_status:true,version:y.version})});
    showToast('Year restored.');
    await _loadPlanningYears();
  }catch(e){ showToast('Could not restore: '+apiErr(e), true); }
}

// Permanent delete -- only succeeds server-side when the Training Year has
// zero linked records of any kind (parade dates, holidays, notices, CEA
// data, etc.). Requires the exact name typed back before the call is made,
// on top of the server's own dependency gate.
async function doDeletePlanningYear(){
  const y=(P.years||[]).find(x=>x.planning_year_id===P.currentYearId);
  if(!y)return;
  const label=y.name||String(y.year);
  const typed=await promptText('Permanently delete year',`Type the year name to confirm`,{
    context:`This permanently deletes "${label}" — this cannot be undone. It will only succeed if the year has no linked records (parade dates, holidays, notices, etc.); otherwise use Archive instead.`,
    okLabel:'Delete permanently',danger:true,
    validate:v=>v!==label?`Type exactly: ${label}`:'',
  });
  if(!typed)return;
  if(typed.trim()!==label){ showToast('Name did not match — nothing was deleted.', true); return; }
  try{
    await api('/api/planning/years/'+P.currentYearId,{method:'DELETE'});
    showToast('Year permanently deleted.');
    P.currentYearId=null;
    await _loadPlanningYears();
    loadYearMap('');
  }catch(e){
    if(e && e.kind==='http' && e.status===409 && e.body && e.body.detail && e.body.detail.dependents){
      const dep=e.body.detail.dependents;
      const depList=Object.entries(dep).map(([k,v])=>`${_cap(k.replace(/_/g,' '))}: ${v}`).join(', ');
      confirmAction(`Cannot permanently delete — this year has linked records (${depList}). Archive it instead? (reversible, keeps history)`,()=>{
        doArchivePlanningYear();
      });
    } else {
      showToast('Could not delete: '+apiErr(e), true);
    }
  }
}

function _autoSelectFirstDate(selId, loadFnName) {
  const sel = document.getElementById(selId);
  if(sel && sel.options.length > 1 && !sel.value) {
    sel.value = sel.options[1].value;
    const fn = window[loadFnName];
    if(typeof fn === 'function') fn(sel.value);
  }
}

// ═══════════════════════════════════
//  TRAINING PLANNER — MISSION TABLE
// ═══════════════════════════════════

const _missionState = { yearId: null, missions: [], facilitators: [], dates: [] };

async function loadMissions(yearId) {
  _missionState.yearId = yearId;
  const empty = document.getElementById('missions-empty');
  const filtersCard = document.getElementById('missions-filters-card');
  const tableCard = document.getElementById('missions-table-card');
  if(!yearId) {
    empty.style.display=''; filtersCard.style.display='none'; tableCard.style.display='none';
    return;
  }
  empty.style.display='none'; filtersCard.style.display=''; tableCard.style.display='';
  document.getElementById('missions-body').innerHTML='<p class="muted">Loading…</p>';
  try {
    const phase  = document.getElementById('mission-filter-phase').value;
    const status = document.getElementById('mission-filter-status').value;
    const search = document.getElementById('mission-search').value;
    let url = `/api/planning/years/${yearId}/missions`;
    const params = new URLSearchParams();
    if(phase)  params.set('phase', phase);
    if(status) params.set('status', status);
    if(search) params.set('search', search);
    if(params.toString()) url += '?' + params.toString();
    const data = await api(url);
    _missionState.missions = data.missions || [];
    // Also load facilitators and parade dates for assignment modal
    const [facs, dates] = await Promise.all([
      api(`/api/planning/facilitators`).catch(()=>[]),
      api(`/api/planning/years/${yearId}/parade-dates`).catch(()=>[]),
    ]);
    _missionState.facilitators = facs || [];
    _missionState.dates = (dates || []).filter(d=>d.is_active);
    document.getElementById('missions-count').textContent =
      `${data.scheduled_count} of ${data.total} scheduled`;
    // Populate Training Class filter from class_breakdown data across all missions
    const classSel = document.getElementById('mission-filter-class');
    if(classSel){
      const classMap={};
      (_missionState.missions).forEach(m=>(m.class_breakdown||[]).forEach(c=>{
        if(!classMap[c.training_class_id]) classMap[c.training_class_id]=c.display_name;
      }));
      const prevVal=classSel.value;
      classSel.innerHTML='<option value="">All Classes</option>'+
        Object.entries(classMap).map(([id,name])=>`<option value="${esc(id)}">${esc(name)}</option>`).join('');
      if(prevVal && classMap[prevVal]) classSel.value=prevVal;
    }
    renderMissions();
    _updateDebugPanel(null);
  } catch(e) {
    document.getElementById('missions-body').innerHTML = `<p class="muted">Error loading missions: ${esc(apiErr(e))}</p>`;
    _updateDebugPanel(apiErr(e));
  }
}

function _saveMissionFilters(phase,status,search,classFilter){
  try{ sessionStorage.setItem('aafc_mission_filters',JSON.stringify({phase,status,search,classFilter})); }catch(_){}
}
function _restoreMissionFilters(){
  try{
    const saved=JSON.parse(sessionStorage.getItem('aafc_mission_filters')||'null');
    if(!saved)return;
    const pe=document.getElementById('mission-filter-phase');
    const se=document.getElementById('mission-filter-status');
    const qe=document.getElementById('mission-search');
    const ce=document.getElementById('mission-filter-class');
    if(pe&&saved.phase)pe.value=saved.phase;
    if(se&&saved.status)se.value=saved.status;
    if(qe&&saved.search)qe.value=saved.search;
    if(ce&&saved.classFilter)ce.value=saved.classFilter;
  }catch(_){}
}
function renderMissions() {
  const body = document.getElementById('missions-body');
  const phase  = document.getElementById('mission-filter-phase').value;
  const status = document.getElementById('mission-filter-status').value;
  const search = (document.getElementById('mission-search').value||'').toLowerCase();
  const classFilter = (document.getElementById('mission-filter-class')||{}).value||'';
  _saveMissionFilters(phase,status,search,classFilter);
  const classSelectEl = document.getElementById('mission-filter-class');
  const className = classFilter && classSelectEl
    ? ((classSelectEl.options[classSelectEl.selectedIndex]||{}).text||'') : '';
  let rows = _missionState.missions.filter(m => {
    if(phase  && m.phase !== phase) return false;
    if(status === 'scheduled'   && !m.is_scheduled) return false;
    if(status === 'unscheduled' && m.is_scheduled)  return false;
    if(search && !m.code.toLowerCase().includes(search) && !m.title.toLowerCase().includes(search)) return false;
    if(classFilter){
      // Class-focused: show all missions tracked for this class (resolved included, dimmed below)
      return !!(m.class_breakdown||[]).find(c=>c.training_class_id===classFilter);
    }
    return true;
  });
  const canWrite = _canWrite();
  if(classFilter){
    // Sort: needs-action → scheduled → resolved
    const _classPriority = s => s==='unscheduled'||s==='cancelled'||s==='not_delivered'?0:s==='scheduled'?1:s==='resolved'?2:3;
    rows = rows.slice().sort((a,b)=>{
      const bdA=(a.class_breakdown||[]).find(c=>c.training_class_id===classFilter);
      const bdB=(b.class_breakdown||[]).find(c=>c.training_class_id===classFilter);
      return _classPriority(bdA?bdA.backlog_status:'') - _classPriority(bdB?bdB.backlog_status:'');
    });
    // Banner counts
    let nResolved=0,nScheduled=0,nAction=0;
    rows.forEach(m=>{
      const bd=(m.class_breakdown||[]).find(c=>c.training_class_id===classFilter);
      const s=bd?(bd.backlog_status||'unscheduled'):'unscheduled';
      if(s==='resolved') nResolved++; else if(s==='scheduled') nScheduled++; else nAction++;
    });
    const parts=[];
    if(nResolved) parts.push(`<span style="color:var(--muted)">${nResolved} resolved</span>`);
    if(nScheduled) parts.push(`<span style="color:var(--ok)">${nScheduled} scheduled</span>`);
    if(nAction) parts.push(`<span style="color:var(--red);font-weight:700">${nAction} need action</span>`);
    document.getElementById('missions-count').innerHTML = parts.join(' · ');
  } else {
    document.getElementById('missions-count').textContent =
      `${rows.filter(m=>m.is_scheduled).length} of ${rows.length} scheduled`;
  }
  if(!rows.length){
    body.innerHTML='<p class="muted">No missions match the selected filters.</p>';
    return;
  }
  if(classFilter){
    // Class-focused table: 6 columns + optional action
    body.innerHTML = `<div style="overflow-x:auto"><table class="data-table" style="min-width:680px">
      <thead><tr>
        <th>Code</th><th>Mission Title</th><th>Level</th><th>Rec. Term</th>
        <th>Class Status</th><th>Scheduled</th>
        ${canWrite?'<th></th>':''}
      </tr></thead><tbody>`+
      rows.map(m=>{
        const bd=(m.class_breakdown||[]).find(c=>c.training_class_id===classFilter);
        const classStatus=bd?(bd.backlog_status||'unscheduled'):'unscheduled';
        const isNeedsAction=classStatus==='unscheduled'||classStatus==='cancelled'||classStatus==='not_delivered';
        const isResolved=classStatus==='resolved';
        const rowStyle=isResolved?'opacity:0.45':'';
        const statusBadge=classStatus==='resolved'
          ?'<span class="badge badge-green">Resolved</span>'
          :classStatus==='scheduled'
          ?'<span class="badge badge-green">Scheduled</span>'
          :classStatus==='cancelled'
          ?'<span class="badge" style="background:var(--warn-bg);color:var(--warn-text)">Cancelled</span>'  /* G1: --warn on --warn-bg=2.98:1(fail); --warn-text=5.4:1(pass) */
          :classStatus==='not_delivered'
          ?'<span class="badge" style="background:#fee2e2;color:var(--red)">Not Delivered</span>'
          :'<span class="badge badge-grey">Unscheduled</span>';
        const sched=m.scheduled_sessions[0];
        const schedDate=sched?sched.parade_date:'';
        const schedSess=sched?`P${sched.session_number}`:'';
        const extraRows=m.scheduled_sessions.length>1
          ?`<br><span class="muted" style="font-size:var(--fs-sm)">+${m.scheduled_sessions.length-1} more</span>`:'';
        const schedCell=schedDate
          ?`${esc(schedDate)} ${esc(schedSess)}${extraRows}<br><button class="btn-xs btn-out no-print" style="font-size:var(--fs-3xs);margin-top:3px;padding:1px 5px" onclick="navToScheduledPN('${esc(schedDate)}')" title="Go to this parade night">↗ View PN</button>`
          :'<span class="muted">—</span>';
        return `<tr style="${rowStyle}">
          <td><code>${esc(m.code)}</code></td>
          <td>${esc(m.title)}</td>
          <td><span class="muted" style="font-size:var(--fs-base)">${esc(_phaseShort(m.phase))}</span></td>
          <td>${esc(m.recommended_term||'')}</td>
          <td>${statusBadge}</td>
          <td>${schedCell}</td>
          ${canWrite?`<td>${isNeedsAction?`<button class="btn-xs" onclick="openAssignModal('${esc(m.curriculum_id)}','${_jsAttr(m.title)}','${_jsAttr(m.code)}',${m.part_count||1})">Assign</button>`:'</td>'}`:''}
        </tr>`;
      }).join('')+
      `</tbody></table></div>`;
  } else {
    // Flat view: 8 columns (Suitability + Parts removed), class summary as text
    const hasClassData=rows.some(m=>(m.class_breakdown||[]).length>0);
    body.innerHTML=`<div style="overflow-x:auto"><table class="data-table" style="min-width:${hasClassData?'860px':'760px'}">
      <thead><tr>
        <th>Code</th><th>Mission Title</th><th>Level</th><th>Subject</th>
        <th>Rec. Term</th><th>Scheduled</th><th>Facilitator</th><th>Status</th>
        ${hasClassData?'<th>Training Classes</th>':''}
        ${canWrite?'<th></th>':''}
      </tr></thead><tbody>`+
      rows.map(m=>{
        const sched=m.scheduled_sessions[0];
        const schedDate=sched?sched.parade_date:'';
        const schedSess=sched?`P${sched.session_number}`:'';
        const facName=sched?(sched.facilitator_name||'—'):'—';
        const extraRows=m.scheduled_sessions.length>1
          ?`<br><span class="muted" style="font-size:var(--fs-sm)">+${m.scheduled_sessions.length-1} more</span>`:'';
        const badge=m.is_scheduled
          ?'<span class="badge badge-green">Scheduled</span>'
          :'<span class="badge badge-grey">Unscheduled</span>';
        let classTd='';
        if(hasClassData){
          const bd=m.class_breakdown||[];
          if(!bd.length){
            classTd='<td><span class="muted" style="font-size:var(--fs-sm)">—</span></td>';
          } else {
            const needsAction=bd.filter(c=>c.backlog_status==='unscheduled'||c.backlog_status==='cancelled'||c.backlog_status==='not_delivered');
            const allResolved=bd.every(c=>c.backlog_status==='resolved'||c.backlog_status==='scheduled');
            const summary=needsAction.length
              ?`<span style="font-size:var(--fs-xs);color:var(--red);font-weight:700">${needsAction.length} class${needsAction.length===1?'':'es'} need action</span>`
              :allResolved
              ?`<span style="font-size:var(--fs-xs);color:var(--muted)">All on track</span>`
              :`<span style="font-size:var(--fs-xs);color:var(--ok)">Scheduled</span>`;
            classTd=`<td>${summary}</td>`;
          }
        }
        return `<tr>
          <td><code>${esc(m.code)}</code></td>
          <td>${esc(m.title)}</td>
          <td><span class="muted" style="font-size:var(--fs-base)">${esc(_phaseShort(m.phase))}</span></td>
          <td>${esc(m.element||'')}</td>
          <td>${esc(m.recommended_term||'')}</td>
          <td>${esc(schedDate)} ${esc(schedSess)}${extraRows}${schedDate?`<br><button class="btn-xs btn-out no-print" style="font-size:var(--fs-3xs);margin-top:3px;padding:1px 5px" onclick="navToScheduledPN('${esc(schedDate)}')" title="Go to this parade night">↗ View PN</button>`:''}</td>
          <td style="font-size:var(--fs-base)">${esc(facName)}</td>
          <td>${badge}</td>
          ${classTd}
          ${canWrite?`<td><button class="btn-xs" onclick="openAssignModal('${esc(m.curriculum_id)}','${_jsAttr(m.title)}','${_jsAttr(m.code)}',${m.part_count||1})">Assign</button></td>`:''}
        </tr>`;
      }).join('')+
      `</tbody></table></div>`;
  }
}

// MBACK-06: per-class delivery summary export — pivots loaded mission data
// into one row per (Training Class × curriculum item), downloaded as CSV.
function exportPerClassDeliveryCSV() {
  const missions = _missionState && _missionState.missions;
  if (!missions || !missions.length) {
    showToast('Open Needs Attention first, then try the export again.', true);
    return;
  }
  // Collect all unique Training Classes across all missions.
  const classMap = {};
  missions.forEach(m => {
    (m.class_breakdown || []).forEach(c => {
      classMap[c.training_class_id] = c.display_name;
    });
  });
  if (!Object.keys(classMap).length) {
    showToast('No Training Classes are set up for this year. Add Training Classes under the Training Classes tab before exporting.', true);
    return;
  }
  const header = ['Class', 'Code', 'Title', 'Stage', 'Element', 'Recommended Term', 'Delivery Status', 'Sessions Scheduled'];
  const rows = [header];
  Object.entries(classMap).forEach(([classId, className]) => {
    missions.forEach(m => {
      const cb = (m.class_breakdown || []).find(c => c.training_class_id === classId);
      if (!cb) return;
      rows.push([className, m.code, m.title, m.phase || '', m.element || '',
        m.recommended_term || '', cb.backlog_status || 'unscheduled', String(cb.scheduled_count || 0)]);
    });
  });
  // Prefix formula-starting chars (=+-@) so spreadsheets can't execute injection.
  const q = f => { const s = String(f); return '"' + (/^[=+\-@\t\r]/.test(s) ? "'" + s : s).replace(/"/g, '""') + '"'; };
  const csv = rows.map(r => r.map(q).join(',')).join('\r\n');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([csv], {type: 'text/csv'}));
  a.download = 'per-class-delivery.csv';
  document.body.appendChild(a); a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(a.href);
  showToast('Per-class delivery CSV downloaded.', false);
}

// MBACK-04: jump directly from a Mission Backlog scheduled-date cell to the
// matching Parade Night — pre-fills the search filter and navigates.
function navToScheduledPN(date) {
  nav('parade-nights');
  setTimeout(() => {
    const inp = document.getElementById('pn-search');
    if (inp) { inp.value = date; renderPN(); }
  }, 100);
}

function _phaseShort(phase) {
  const map = {
    'A. Orientation':'ORI','B. Initial':'INL','C. Junior':'JNR',
    'D. Intermediate':'INT','E. Senior':'SNR','I. Bronze':'BCL',
    'J. Silver':'SCL','K. Gold':'GCL',
  };
  return map[phase] || (phase||'').split(' ').pop();
}

function _canWrite() {
  const r = S && S.role;
  return r && !['sqn_general','wing_viewer','national_viewer','auditor'].includes(r);
}

function _updateDebugPanel(lastError) {
  const panel = document.getElementById('planner-debug-panel');
  if(!panel) return;
  const isLocal = ['localhost','127.0.0.1'].some(h=>location.hostname.includes(h));
  if(!isLocal){ panel.style.display='none'; return; }
  panel.style.display='';
  const yr = P.years.find(y=>y.planning_year_id===_missionState.yearId);
  const rows = [
    ['Role', (S.role||'—')],
    ['Unit', (S.scopeName||'—')],
    ['Year', yr ? (yr.name||String(yr.year)) : (_missionState.yearId ? _missionState.yearId.slice(0,8)+'…' : 'none')],
    ['Missions loaded', String(_missionState.missions.length)],
    ['Parade dates loaded', String(_missionState.dates.length)],
    ['Annual program', P.annualProgramLoaded ? 'yes' : 'not yet'],
    ['Selected parade night', P.currentPnId ? P.currentPnId.slice(0,8)+'…' : 'none'],
  ];
  document.getElementById('planner-debug-content').innerHTML =
    rows.map(([k,v])=>`<div><span style="color:var(--muted)">${k}:</span> <strong>${esc(v)}</strong></div>`).join('');
  const errEl = document.getElementById('planner-debug-error');
  errEl.textContent = lastError ? `Last error: ${lastError}` : '';
}

// Mission assignment modal
let _assignCurriculumId = null;

function openAssignModal(curriculumId, title, code, partCount) {
  _assignCurriculumId = curriculumId;
  document.getElementById('assign-title').textContent = `${code} — ${title}`;
  // Populate parade date selector
  const dateSel = document.getElementById('assign-date-sel');
  dateSel.innerHTML = '<option value="">— select parade night —</option>';
  (_missionState.dates||[]).forEach(d=>{
    const o = document.createElement('option');
    o.value = d.parade_date_id;
    o.textContent = `${d.parade_date}${d.term?' ('+d.term+')':''}`;
    dateSel.appendChild(o);
  });
  // Part number
  const partRow = document.getElementById('assign-part-row');
  const partSel = document.getElementById('assign-part-sel');
  partSel.innerHTML = '';
  for(let i=1;i<=partCount;i++){
    const o = document.createElement('option');
    o.value = i; o.textContent = `Part ${i}`;
    partSel.appendChild(o);
  }
  partRow.style.display = partCount > 1 ? '' : 'none';
  // Populate facilitator selector
  const facSel = document.getElementById('assign-fac-sel');
  facSel.innerHTML = '<option value="">— none —</option>';
  (_missionState.facilitators||[]).forEach(f=>{
    const o = document.createElement('option');
    o.value = f.facilitator_id;
    o.textContent = f.display_name || f.last_name;
    facSel.appendChild(o);
  });
  document.getElementById('assign-msg').textContent = '';
  openModal('m-assign-mission');
}

async function doAssignMission() {
  const yearId     = _missionState.yearId;
  const dateId     = document.getElementById('assign-date-sel').value;
  const sessNum    = parseInt(document.getElementById('assign-sess-sel').value);
  const group      = document.getElementById('assign-group-sel').value;
  const partNum    = parseInt(document.getElementById('assign-part-sel').value)||1;
  const facId      = document.getElementById('assign-fac-sel').value || null;
  const msgEl      = document.getElementById('assign-msg');
  if(!dateId){ msgEl.textContent='Select a parade night.'; return; }
  if(!group){  msgEl.textContent='Select a cadet group.'; return; }
  if(!_assignCurriculumId){ msgEl.textContent='No mission selected.'; return; }
  try {
    await api(`/api/planning/years/${yearId}/assign-mission`, {
      method:'POST',
      body:{
        curriculum_id: _assignCurriculumId,
        parade_date_id: dateId,
        session_number: sessNum,
        cadet_group: group,
        part_number: partNum,
        facilitator_id: facId,
      },
    });
    closeModal('m-assign-mission');
    await loadMissions(yearId);
  } catch(e){ msgEl.textContent = apiErr(e); }
}

// ═══════════════
//  YEAR MAP
// ═══════════════

function openNewYearModal(){
  document.getElementById('py-year-inp').value = new Date().getFullYear();
  document.getElementById('py-name-inp').value = '';
  document.getElementById('py-msg').textContent = '';
  const unitRow = document.getElementById('py-unit-row');
  if(unitRow){
    const isWA = S.role==='wing_admin';
    unitRow.style.display = isWA ? '' : 'none';
    if(isWA){
      const unitSel = document.getElementById('py-unit-sel');
      if(unitSel){
        unitSel.innerHTML = '<option value="">— Wing-level year —</option>';
        (S.wsqns||[]).forEach(sq=>{
          const o=document.createElement('option'); o.value=sq.squadron_id;
          o.textContent=`${sq.squadron_code||''} — ${sq.name||sq.squadron_id}`;
          unitSel.appendChild(o);
        });
        // Pre-select the squadron currently in the filter if set
        const sqnFilter = document.getElementById('py-sqn-filter');
        if(sqnFilter && sqnFilter.value) unitSel.value = sqnFilter.value;
      }
    }
  }
  openModal('m-new-year');
}

async function doCreateYear(){
  const year = parseInt(document.getElementById('py-year-inp').value);
  const name = document.getElementById('py-name-inp').value.trim();
  if(!name || !year){ document.getElementById('py-msg').textContent='Year and Name are required.'; return; }
  const unitSel = document.getElementById('py-unit-sel');
  const unit_id = (unitSel && unitSel.style.display!=='none') ? (unitSel.value||undefined) : undefined;
  try {
    const body = {year, name};
    if(unit_id) body.unit_id = unit_id;
    await api('/api/planning/years',{method:'POST',body});
    closeModal('m-new-year');
    await _loadPlanningYears();
    const sel = document.getElementById('py-select');
    if(sel && P.years.length){ sel.value = P.years[0].planning_year_id; loadYearMap(P.years[0].planning_year_id); }
  } catch(e){ document.getElementById('py-msg').textContent = apiErr(e); }
}

async function loadYearMap(yearId){
  P.currentYearId = yearId;
  _renderPyActionBtns();
  const body = document.getElementById('py-map-body');
  const datesCard = document.getElementById('py-dates-card');
  const holCard = document.getElementById('py-holidays-card');
  const classesCard = document.getElementById('py-classes-card');
  const classesWrap = document.getElementById('settings-training-classes-wrap');
  const missionsCard = document.getElementById('py-missions-card');
  const ctxLbl = document.getElementById('py-ctx-label-sqn');
  if(!yearId){
    body.innerHTML='<p class="muted">Select a year above.</p>';
    datesCard.style.display='none'; holCard.style.display='none'; classesCard.style.display='none'; if(classesWrap) classesWrap.style.display='none';
    if(missionsCard) missionsCard.style.display='none';
    if(ctxLbl) ctxLbl.textContent='';
    return;
  }
  try {
    const yr = P.years.find(y=>y.planning_year_id===yearId) || {};
    if(ctxLbl){
      if(yr.unit_name) ctxLbl.textContent=`Viewing ${esc(yr.unit_name)}'s program`;
      else if(yr.wing_code) ctxLbl.textContent=`Wing ${esc(yr.wing_code)} program`;
      else ctxLbl.textContent='';
    }
    // Load annual program summary
    let annualHtml = '';
    try {
      const ap = await api(`/api/planning/years/${yearId}/annual-program`);
      const pct = ap.total_session_slots > 0 ? Math.round(ap.filled_session_slots/ap.total_session_slots*100) : 0;
      annualHtml = `<div style="display:flex;gap:20px;flex-wrap:wrap;margin-bottom:14px;align-items:center">
        <div><span class="muted">Year:</span> <strong>${esc(String(ap.year||''))}</strong></div>
        <div><span class="muted">Name:</span> <strong>${esc(ap.name||'')}</strong></div>
        <div><span class="muted">Status:</span> <span class="badge ${yr.active_status?'badge-green':'badge-grey'}">${yr.active_status?'Active':'Inactive'}</span></div>
        <div><span class="muted">Parade Nights:</span> <strong>${ap.active_parade_dates}</strong></div>
        <div><span class="muted">Sessions Scheduled:</span> <strong>${ap.filled_session_slots} / ${ap.total_session_slots} (${pct}%)</strong></div>
      </div>` + _renderAnnualCalendar(ap);
    } catch(e2) {
      annualHtml = `<div style="display:flex;gap:24px;flex-wrap:wrap">
        <div><span class="muted">Year:</span> <strong>${esc(String(yr.year||''))}</strong></div>
        <div><span class="muted">Name:</span> <strong>${esc(yr.name||'')}</strong></div>
        <div><span class="muted">Status:</span> <span class="badge ${yr.active_status?'badge-green':'badge-grey'}">${yr.active_status?'Active':'Inactive'}</span></div>
      </div>`;
    }
    body.innerHTML = annualHtml;
    P.annualProgramLoaded = true;
    datesCard.style.display=''; holCard.style.display=''; classesCard.style.display='';
    if(classesWrap){classesWrap.style.display='';const addBtn=classesWrap.querySelector('.plan-write-el');if(addBtn)addBtn.style.display=canWriteSquadron()?'inline-flex':'none';}
    if(missionsCard) missionsCard.style.display='';
    await Promise.all([_renderParadeDates(yearId), _renderHolidays(yearId), _renderTrainingClasses(yearId)]);
    loadMissions(yearId);
    const wid=yr.wing_id||(S.session&&S.session.wing_id)||'';
    if(wid){const wingYear=yr.year||new Date().getFullYear();await _loadAndRenderWingEventsOverlay(wid,wingYear);}
  } catch(e){ body.innerHTML = `<p class="muted">Error loading year: ${esc(apiErr(e))}</p>`; }
}

// Annual Program: full-year month calendar, built from live API data
function _renderAnnualCalendar(ap) {
  if(!ap || !ap.terms) return '';
  // Index parade dates, holidays and activities by date string
  const PD={}, HOL=[], ACT={};
  ap.terms.forEach(t=>{
    t.parade_dates.forEach(pd=>{ PD[pd.parade_date]=pd; });
    t.holidays.forEach(h=>{ HOL.push(h); });
    t.activities.forEach(a=>{ if(!ACT[a.start_date])ACT[a.start_date]=[]; ACT[a.start_date].push(a); });
  });
  window._AP_DATA={PD,HOL,ACT,ap};

  const legend=`<div style="display:flex;gap:14px;flex-wrap:wrap;margin-bottom:10px;font-size:var(--fs-2xs);color:var(--steel)">
    <span style="display:flex;align-items:center;gap:4px"><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#e6f3fc;border:1px solid var(--blue)"></span>Parade night</span>
    <span style="display:flex;align-items:center;gap:4px"><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#fff3cd;border:1px solid #ddb"></span>Holiday / stand-down</span>
    <span style="display:flex;align-items:center;gap:4px"><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#fde8e8;border:1px solid #f5a"></span>Must Attend</span>
    <span style="display:flex;align-items:center;gap:4px"><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#deeefa;border:1px solid var(--pale)"></span>Key event</span>
    <span style="color:var(--muted)">Click any date for detail.</span>
  </div>`;

  const MONTHS=['January','February','March','April','May','June','July','August','September','October','November','December'];
  let grid=`<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px">`;
  for(let m=0;m<12;m++) grid+=_renderApMonth(ap.year,m,PD,HOL,ACT,MONTHS[m]);
  grid+=`</div>`;

  const detailPanel=`<div id="ap-detail-panel" class="card" style="display:none;margin-top:12px">
    <div id="ap-detail-body"></div>
  </div>`;

  return legend+grid+detailPanel;
}

function _renderApMonth(year,mIdx,PD,HOL,ACT,mName){
  const DOW=['S','M','T','W','T','F','S'];
  const firstDow=new Date(year,mIdx,1).getDay();
  const lastD=new Date(year,mIdx+1,0).getDate();
  const today=new Date().toISOString().slice(0,10);
  let h=`<div style="background:white;border-radius:6px;border:1px solid var(--border);padding:8px">
    <div style="font-size:var(--fs-2xs);font-weight:800;color:var(--dark);margin-bottom:5px;letter-spacing:.02em">${mName}</div>
    <div style="display:grid;grid-template-columns:repeat(7,1fr);gap:1px">`;
  DOW.forEach(d=>{ h+=`<div style="text-align:center;font-size:var(--fs-3xs);font-weight:700;color:var(--muted);padding:2px 0">${d}</div>`; });
  for(let i=0;i<firstDow;i++) h+=`<div></div>`;
  for(let d=1;d<=lastD;d++){
    const ds=`${year}-${String(mIdx+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
    const pd=PD[ds];
    const hols=HOL.filter(x=>x.start_date<=ds&&x.end_date>=ds);
    const acts=ACT[ds]||[];
    const isToday=ds===today;
    let bg='',border='',txtCol='var(--muted)',cursor='default';
    if(pd&&!hols.length){bg='#e6f3fc';border='border:1px solid var(--blue);';txtCol='var(--dark)';cursor='pointer';}
    else if(pd&&hols.length){bg='#fff3cd';border='border:1px solid #ddb;';txtCol='var(--dark)';cursor='pointer';}
    else if(hols.length){bg='#fff7e8';border='border:1px solid #ddd060;';}
    else if(acts.length){
      if(acts[0].importance_level===1){bg='#fde8e8';border='border:1px solid #f5a5a5;';}
      else{bg='#deeefa';border='border:1px solid var(--pale);';}
      cursor='pointer';
    }
    let dot='';
    if(pd){
      const pct=pd.session_count>0?Math.floor(pd.filled_count/(pd.session_count*5)*100):0;
      const dc=pct>49?'#1a7f4b':pct>0?'#51b0e3':'#b0b7bb';
      dot=`<div style="width:4px;height:4px;border-radius:50%;background:${dc};margin:1px auto 0"></div>`;
    }
    const clickable=pd||acts.length;
    const title=(pd?`${pd.filled_count||0} sessions assigned`:'')+(hols.length?' · '+hols[0].name:'')+(acts.length?' · '+acts[0].event_name:'');
    h+=`<div style="border-radius:3px;${bg?'background:'+bg+';':''}${border}${isToday?'outline:2px solid var(--dark);outline-offset:-1px;':''}padding:2px 1px;cursor:${cursor};margin:1px;min-height:22px"
      ${clickable?`onclick="_apShowDateDetail('${ds}')"`:''}
      title="${esc(title)}">
      <div style="font-size:var(--fs-3xs);font-weight:${isToday?'800':'400'};color:${txtCol};text-align:center;line-height:1.5">${d}</div>
      ${dot}
    </div>`;
  }
  h+=`</div></div>`;
  return h;
}

function _apShowDateDetail(ds){
  const D=window._AP_DATA; if(!D) return;
  const panel=document.getElementById('ap-detail-panel');
  const body=document.getElementById('ap-detail-body');
  if(!panel||!body) return;
  const pd=D.PD[ds];
  const hols=D.HOL.filter(x=>x.start_date<=ds&&x.end_date>=ds);
  const acts=D.ACT[ds]||[];
  const DOW=['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
  const dow=DOW[new Date(ds).getDay()];
  let h=`<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px">
    <div>
      <div style="font-size:var(--fs-md);font-weight:800;color:var(--dark)">${dow}, ${ds}</div>`;
  hols.forEach(x=>{
    h+=`<div style="margin-top:3px"><span class="badge badge-amber">${esc(x.holiday_type||'Holiday')}</span> <span style="font-size:var(--fs-xs)">${esc(x.name)}</span>
      <span class="muted" style="font-size:var(--fs-2xs)"> ${esc(x.start_date)}${x.end_date!==x.start_date?' – '+esc(x.end_date):''}</span></div>`;
  });
  h+=`</div><button class="btn btn-xs btn-secondary" onclick="document.getElementById('ap-detail-panel').style.display='none'">Close</button></div>`;
  if(pd){
    const slots=(pd.session_count||3)*5;
    const filled=pd.filled_count||0;
    const pct=slots>0?Math.round(filled/slots*100):0;
    const fillBadge=pct>50?'<span class="badge badge-green">'+pct+'% allocated</span>':pct>0?'<span class="badge badge-amber">'+pct+'% allocated</span>':'<span class="badge badge-grey">No sessions assigned</span>';
    h+=`<div style="margin-top:6px;padding:10px;background:var(--bg);border-radius:6px">
      <div style="font-size:var(--fs-xs);font-weight:700;color:var(--dark);margin-bottom:6px">Parade Night</div>
      <div style="display:flex;gap:14px;font-size:var(--fs-xs);flex-wrap:wrap;align-items:center">
        <div><span class="muted">Sessions assigned:</span> <strong>${filled}</strong> of <strong>${slots}</strong> slots</div>
        ${fillBadge}
        ${pd.in_holiday?'<span class="badge badge-amber">In holiday period</span>':''}
      </div>
    </div>`;
  }
  if(acts.length){
    h+=`<div style="margin-top:8px">`;
    acts.forEach(a=>{
      const bc=a.importance_level===1?'var(--red)':a.importance_level===2?'var(--royal)':'var(--lgrey)';
      const badge=a.importance_level===1?'<span class="badge badge-red">Must Attend</span>':
        a.importance_level===2?'<span class="badge" style="background:#deeefa;color:var(--dark)">Key Event</span>':
        '<span class="badge badge-grey">Activity</span>';
      h+=`<div style="padding:6px 8px;border-left:3px solid ${bc};margin-bottom:5px">
        ${badge} <strong style="font-size:var(--fs-xs)">${esc(a.event_name)}</strong>
        ${a.unit_name?`<span class="muted" style="font-size:var(--fs-2xs)"> · ${esc(a.unit_name)}</span>`:''}
      </div>`;
    });
    h+=`</div>`;
  }
  if(!pd&&!acts.length&&!hols.length){
    h+=`<p class="muted" style="font-size:var(--fs-xs);margin-top:4px">No scheduled events on this date.</p>`;
  }
  body.innerHTML=h;
  panel.style.display='';
  panel.scrollIntoView({behavior:'smooth',block:'nearest'});
}

async function _renderParadeDates(yearId){
  const el = document.getElementById('py-dates-body');
  try {
    const rows = await api(`/api/planning/years/${yearId}/parade-dates`);
    if(!rows.length){ el.innerHTML='<p class="muted">No parade dates yet. Use Auto-Generate or Add Date.</p>'; return; }
    el.innerHTML = `<div style="overflow-x:auto"><table class="data-table"><thead><tr><th>Date</th><th>Day</th><th>Type</th><th>Holiday?</th><th></th></tr></thead><tbody>`+
      rows.map(d=>`<tr>
        <td>${esc(d.parade_date)}</td>
        <td>${_dayName(d.parade_date)}</td>
        <td>${esc(d.parade_type)}</td>
        <td>${d.in_holiday ? '<span class="badge badge-yellow">Holiday</span>' : ''}</td>
        <td><button class="btn-xs btn-danger" onclick="deleteParadeDate('${esc(d.parade_date_id)}','${esc(yearId)}')">Remove</button></td>
      </tr>`).join('')+
      `</tbody></table></div>`;
  } catch(e){ el.innerHTML='<p class="muted">Could not load parade dates. Refresh the page to try again.</p>'; }
}

async function _renderHolidays(yearId){
  const el = document.getElementById('py-holidays-body');
  if (!el) return;
  if (!yearId){
    // A year with no row has no holidays, and asking for them would build
    // /api/planning/years/null/holidays. Say so rather than leaving the
    // previous year's list sitting under a different year number.
    el.innerHTML = '<p class="muted">No holiday periods added yet.</p>';
    return;
  }
  try {
    const rows = await api(`/api/planning/years/${yearId}/holidays`);
    if(!rows.length){ el.innerHTML='<p class="muted">No holiday periods added yet.</p>'; return; }
    const canWrite=canWriteSquadron();
    el.innerHTML = `<div style="overflow-x:auto"><table class="data-table"><thead><tr><th>Name</th><th>Type</th><th>Start</th><th>End</th><th>Affects Parade</th><th></th></tr></thead><tbody>`+
      rows.map(h=>`<tr>
        <td>${esc(h.name)}</td>
        <td>${esc(_HOL_TYPE_LABELS[h.holiday_type]||h.holiday_type||'—')}</td>
        <td>${esc(h.start_date)}</td>
        <td>${esc(h.end_date)}</td>
        <td>${h.affects_parade?'Yes':'No'}</td>
        <td style="white-space:nowrap">${canWrite?`<button class="btn-xs" onclick='openEditHolidayModal(${JSON.stringify(h)})' style="margin-right:4px">Edit</button>`:''}${canWrite?`<button class="btn-xs btn-danger" onclick="deleteHoliday('${esc(h.holiday_id)}','${esc(yearId)}')">Remove</button>`:''}</td>
      </tr>`).join('')+
      `</tbody></table></div>`;
  } catch(e){ el.innerHTML='<p class="muted">Could not load holiday periods. Refresh the page to try again.</p>'; }
}

function _dayName(iso){ try{ const d=new Date(iso+'T00:00:00'); return ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'][d.getDay()]; }catch(e){ return ''; } }

function openAddDateModal(){
  document.getElementById('pd-date-inp').value='';
  document.getElementById('pd-type-inp').value='standard';
  document.getElementById('pd-notes-inp').value='';
  document.getElementById('pd-msg').textContent='';
  openModal('m-add-pd');
}
async function doAddParadeDate(){
  const d = document.getElementById('pd-date-inp').value;
  if(!d){ document.getElementById('pd-msg').textContent='Date is required.'; return; }
  try {
    await api(`/api/planning/years/${P.currentYearId}/parade-dates`,{
      method:'POST', body:{parade_date:d, parade_type:document.getElementById('pd-type-inp').value,
        notes:document.getElementById('pd-notes-inp').value||null}
    });
    closeModal('m-add-pd'); await _renderParadeDates(P.currentYearId);
  } catch(e){ document.getElementById('pd-msg').textContent=apiErr(e); }
}
async function deleteParadeDate(pdId, yearId){
  confirmAction('Permanently remove this parade date? This cannot be undone.',async()=>{
    try { await api(`/api/planning/parade-dates/${pdId}`,{method:'DELETE'}); await _renderParadeDates(yearId); }
    catch(e){ showToast(apiErr(e),true); }
  },true);
}

function openGenerateDatesModal(){
  // Seed from the Squadron's own Parade Day setting (Unit Settings) --
  // previously this always hardcoded Friday regardless of what the squadron
  // had actually configured, so changing the setting had no visible effect
  // on this modal at all.
  const _defDay=_DAY_NAME_TO_INT[S.cfg&&S.cfg.day];
  document.getElementById('gen-weekday').value=(_defDay!==undefined?_defDay:4);
  document.getElementById('gen-start').value='';
  document.getElementById('gen-end').value='';
  document.getElementById('gen-excl-hols').checked=true;
  document.getElementById('gen-msg').textContent='';
  openModal('m-gen-dates');
}
function _buildGenBody(){
  const weekday=parseInt(document.getElementById('gen-weekday').value);
  const start=document.getElementById('gen-start').value;
  const end=document.getElementById('gen-end').value||null;
  const maxREl=document.getElementById('gen-max-repeats');
  const maxR=maxREl&&maxREl.value?parseInt(maxREl.value)||null:null;
  const freq=(document.getElementById('gen-freq')&&document.getElementById('gen-freq').value)||'weekly';
  const exclRaw=(document.getElementById('gen-excl-dates')&&document.getElementById('gen-excl-dates').value)||'';
  const excluded_dates=exclRaw.split(/[\s,]+/).map(s=>s.trim()).filter(s=>/^\d{4}-\d{2}-\d{2}$/.test(s));
  const excHols=document.getElementById('gen-excl-hols').checked;
  const startTime=(document.getElementById('gen-start-time')&&document.getElementById('gen-start-time').value)||null;
  const endTime=(document.getElementById('gen-end-time')&&document.getElementById('gen-end-time').value)||null;
  return{weekday,start_date:start,end_date:end,frequency:freq,exclude_holidays:excHols,excluded_dates,max_repeats:maxR,
    parade_start_time:startTime,parade_end_time:endTime};
}
async function previewGenerateDates(){
  const msg=document.getElementById('gen-msg');
  const area=document.getElementById('gen-preview-area');
  if(!P.currentYearId){ msg.textContent='Select a year from the dropdown above to continue.'; return; }
  const b=_buildGenBody();
  if(!b.start_date){ msg.textContent='Start date is required.'; return; }
  if(!b.end_date&&!b.max_repeats){ msg.textContent='Provide an end date or number of repeats.'; return; }
  msg.textContent='Loading preview…';
  area.style.display='none';
  try{
    const r=await api(`/api/planning/years/${P.currentYearId}/preview-parade-dates`,{method:'POST',body:b});
    msg.textContent=`${r.new_count} new date${r.new_count!==1?'s':''} of ${r.total} in range.`;
    // REM-10: preview-parade-dates now classifies every date the recurrence
    // pattern touches, not just the ones that would be created, so holiday
    // conflicts and explicit skips are visible instead of silently vanishing.
    const _STATUS_LABEL={will_create:'New',already_exists:'Exists',holiday_conflict:'Holiday conflict — skipped',explicitly_skipped:'Explicitly skipped'};
    const _STATUS_BADGE={will_create:'b-ok',already_exists:'b-grey',holiday_conflict:'b-amber',explicitly_skipped:'b-grey'};
    area.innerHTML='<table style="width:100%;font-size:var(--fs-sm)"><thead><tr><th>Date</th><th>Status</th></tr></thead><tbody>'+
      (r.dates||[]).map(d=>`<tr><td>${esc(d.date)}</td><td><span class="badge ${_STATUS_BADGE[d.status]||'b-grey'}">${esc(_STATUS_LABEL[d.status]||d.status)}</span></td></tr>`).join('')+
      '</tbody></table>';
    area.style.display='block';
  }catch(e){ msg.textContent=apiErr(e); }
}
async function doGenerateDates(){
  const msg=document.getElementById('gen-msg');
  if(!P.currentYearId){ msg.textContent='Select a year from the dropdown above to continue.'; return; }
  const b=_buildGenBody();
  if(!b.start_date){ msg.textContent='Start date is required.'; return; }
  if(!b.end_date&&!b.max_repeats){ msg.textContent='Provide an end date or number of repeats.'; return; }
  try {
    const r = await api(`/api/planning/years/${P.currentYearId}/generate-parade-dates`,{method:'POST',body:b});
    closeModal('m-gen-dates');
    showToast(`Generated ${r.created} new parade date${r.created!==1?'s':''}.`);
    await _renderParadeDates(P.currentYearId);
  } catch(e){ msg.textContent=apiErr(e); }
}

const _HOL_TYPE_LABELS={'school_holiday':'School Holiday','public_holiday':'Public Holiday','statutory_holiday':'Statutory Holiday','squadron_stand_down':'Squadron Stand-Down','wing_stand_down':'Wing Stand-Down','national_stand_down':'National Stand-Down','local_closure':'Local Closure','training_pause':'Training Pause','other':'Other'};
function openAddHolidayModal(){
  ['hol-name-inp','hol-start-inp','hol-end-inp'].forEach(id=>document.getElementById(id).value='');
  document.getElementById('hol-type-inp').value='school_holiday';
  document.getElementById('hol-affects-inp').checked=true;
  document.getElementById('hol-msg').textContent='';
  openModal('m-add-holiday');
}
async function doAddHoliday(){
  const hm=document.getElementById('hol-msg');
  if(!P.currentYearId){ hm.textContent='Select a year first.'; return; }
  const name = document.getElementById('hol-name-inp').value.trim();
  const start = document.getElementById('hol-start-inp').value;
  const end = document.getElementById('hol-end-inp').value;
  const holiday_type = document.getElementById('hol-type-inp').value;
  if(!name||!start||!end){ hm.textContent='All fields required.'; return; }
  try {
    await api(`/api/planning/years/${P.currentYearId}/holidays`,{
      method:'POST', body:{ name, start_date:start, end_date:end, holiday_type,
        affects_parade: document.getElementById('hol-affects-inp').checked }
    });
    closeModal('m-add-holiday'); await _renderHolidays(P.currentYearId);
  } catch(e){ hm.textContent=apiErr(e); }
}
function openEditHolidayModal(h){
  document.getElementById('hol-edit-id').value=h.holiday_id;
  document.getElementById('hol-edit-name').value=h.name||'';
  document.getElementById('hol-edit-type').value=h.holiday_type||'school_holiday';
  document.getElementById('hol-edit-start').value=h.start_date||'';
  document.getElementById('hol-edit-end').value=h.end_date||'';
  document.getElementById('hol-edit-affects').checked=!!h.affects_parade;
  document.getElementById('hol-edit-msg').textContent='';
  openModal('m-edit-holiday');
}
async function doEditHoliday(){
  const hm=document.getElementById('hol-edit-msg');
  const hId=document.getElementById('hol-edit-id').value;
  const name=document.getElementById('hol-edit-name').value.trim();
  const start=document.getElementById('hol-edit-start').value;
  const end=document.getElementById('hol-edit-end').value;
  const holiday_type=document.getElementById('hol-edit-type').value;
  if(!name||!start||!end){ hm.textContent='All fields required.'; return; }
  try {
    await api(`/api/planning/holidays/${hId}`,{method:'PATCH',body:{name,start_date:start,end_date:end,holiday_type,affects_parade:document.getElementById('hol-edit-affects').checked}});
    closeModal('m-edit-holiday'); await _renderHolidays(P.currentYearId);
  } catch(e){ hm.textContent=apiErr(e); }
}
async function deleteHoliday(hId, yearId){
  confirmAction('Permanently remove this holiday period? This cannot be undone.',async()=>{
    try { await api(`/api/planning/holidays/${hId}`,{method:'DELETE'}); await _renderHolidays(yearId); }
    catch(e){ showToast(apiErr(e),true); }
  },true);
}

// ═══════════════
//  ANCHOR EVENTS
// ═══════════════

async function loadAnchors(yearId){
  P.currentYearId = yearId;
  const el = document.getElementById('anchors-body');
  if(!yearId){ el.innerHTML='<p class="muted">Select a year above.</p>'; return; }
  try {
    const showArchived=(document.getElementById('anch-show-archived')||{}).checked;
    const url=`/api/planning/years/${yearId}/anchors`+(showArchived?'?include_archived=true':'');
    P.anchors = await api(url);
    renderAnchors();
  } catch(e){ el.innerHTML=`<p class="muted">Could not load anchor events: ${esc(apiErr(e))}</p>`; }
}

function renderAnchors(){
  const el = document.getElementById('anchors-body');
  const imp = (document.getElementById('anch-filter-importance')||{}).value||'';
  const typ = (document.getElementById('anch-filter-type')||{}).value||'';
  const showArchived=(document.getElementById('anch-show-archived')||{}).checked;
  let rows = P.anchors;
  if(!showArchived) rows = rows.filter(a=>!a.is_archived);
  if(imp) rows = rows.filter(a=>a.importance===imp);
  if(typ) rows = rows.filter(a=>a.event_type===typ);
  if(!rows.length){ el.innerHTML=`<p class="muted">No ${showArchived?'archived ':''}anchor events found.</p>`; return; }
  el.innerHTML = `<table class="data-table"><thead><tr><th>Event</th><th>Type</th><th>Importance</th><th>Start Date</th><th>End Date</th><th>Audience</th><th></th></tr></thead><tbody>`+
    rows.map(a=>`<tr${a.is_archived?' style="opacity:.6"':''}>
      <td><strong>${esc(a.event_name)}</strong>${a.is_archived?' <span class="badge b-grey">Archived</span>':''}</td>
      <td>${esc(_EVENT_TYPE_LABELS[a.event_type]||a.event_type)}</td>
      <td><span class="badge ${_importanceBadge(a.importance)}">${esc(_IMPORTANCE_LABELS[a.importance]||a.importance)}</span></td>
      <td>${esc(a.start_date)}</td>
      <td>${esc(a.end_date||'—')}</td>
      <td>${_audienceBadges(a.audience)}</td>
      <td>
        ${a.is_archived
          ?`<button class="btn btn-xs btn-ok" onclick="doRestoreAnchor('${esc(a.anchor_event_id)}','${_jsAttr(a.event_name)}')">Restore</button>`
          :`<button class="btn-xs btn-danger" onclick="deleteAnchor('${esc(a.anchor_event_id)}')">Archive</button>`}
      </td>
    </tr>`).join('')+
    `</tbody></table>`;
}

async function doRestoreAnchor(anchorId, name){
  try{
    await api(`/api/planning/anchors/${anchorId}/restore`,{method:'POST'});
    showToast(`'${name}' restored.`);
    await loadAnchors(P.currentYearId);
  }catch(e){ showToast('Could not restore: '+apiErr(e), true); }
}

function _importanceBadge(imp){ return imp==='must_attend'?'badge-red':imp==='key_event'?'badge-blue':'badge-grey'; }
function _audienceBadges(aud){
  if(!aud) return '';
  return ['orientation','initial','junior','intermediate','senior'].filter(g=>aud[g]).map(g=>`<span class="badge badge-teal">${g.substring(0,3)}</span>`).join(' ');
}

function openAddAnchorModal(){
  if(!P.currentYearId){ showToast('Select a year from the dropdown above before continuing.',true); return; }
  ['anch-name-inp','anch-start-inp','anch-end-inp','anch-impact-inp','anch-readiness-inp'].forEach(id=>document.getElementById(id).value='');
  document.getElementById('anch-type-inp').value='other';
  document.getElementById('anch-imp-inp').value='key_event';
  document.getElementById('anch-msg').textContent='';
  openModal('m-add-anchor');
}
async function doAddAnchor(){
  const name=document.getElementById('anch-name-inp').value.trim();
  const start=document.getElementById('anch-start-inp').value;
  if(!name||!start){ document.getElementById('anch-msg').textContent='Event name and start date are required.'; return; }
  try {
    const r = await api(`/api/planning/years/${P.currentYearId}/anchors`,{
      method:'POST', body:{
        event_name:name,
        event_type:document.getElementById('anch-type-inp').value,
        importance:document.getElementById('anch-imp-inp').value,
        start_date:start,
        end_date:document.getElementById('anch-end-inp').value||null,
        planning_impact:document.getElementById('anch-impact-inp').value||null,
        readiness_requirements:document.getElementById('anch-readiness-inp').value||null,
      }
    });
    closeModal('m-add-anchor');
    P.anchors.push(r); renderAnchors();
  } catch(e){ document.getElementById('anch-msg').textContent=apiErr(e); }
}
async function deleteAnchor(anchorId){
  confirmAction('Archive this anchor event? It will no longer appear in planning.',async()=>{
    try { await api(`/api/planning/anchors/${anchorId}`,{method:'DELETE'}); await loadAnchors(P.currentYearId); }
    catch(e){ showToast(apiErr(e),true); }
  });
}

// ═══════════════
//  TERM PLANNER
// ═══════════════

async function loadTermPlanner(yearId, term){
  const body = document.getElementById('term-body');
  const summ = document.getElementById('term-summary-row');
  if(!yearId){ body.innerHTML='<p class="muted">Select a year above.</p>'; summ.innerHTML=''; return; }
  try {
    const params = term ? `?term=${term}` : '';
    const d = await api(`/api/planning/years/${yearId}/term-planner${params}`);
    summ.innerHTML=`
      <div class="stat-chip"><span>${d.parade_count}</span><small>Parade Nights</small></div>
      <div class="stat-chip"><span>${d.sessions_filled}</span><small>Sessions Filled</small></div>
      <div class="stat-chip"><span>${d.sessions_remaining}</span><small>Remaining</small></div>
    `;
    if(!d.parade_dates.length){ body.innerHTML='<p class="muted">No parade dates in this period.</p>'; return; }
    body.innerHTML = d.parade_dates.map(pd=>{
      const sessions = d.sessions_by_parade_date[pd.parade_date_id]||[];
      const byGroup = {};
      sessions.forEach(s=>{ byGroup[s.cadet_group]=byGroup[s.cadet_group]||[]; byGroup[s.cadet_group].push(s); });
      return `<div style="margin-bottom:16px;padding:10px;background:var(--bg-card);border-radius:8px;border:1px solid var(--border)">
        <div style="display:flex;gap:12px;align-items:center;margin-bottom:6px">
          <strong>${esc(pd.parade_date)}</strong>
          <span class="muted">${_dayName(pd.parade_date)}</span>
          ${pd.in_holiday?'<span class="badge badge-yellow">Holiday</span>':''}
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:6px">
          ${_CADET_GROUPS.map(grp=>{
            const grpSessions = byGroup[grp]||[];
            return `<div style="min-width:120px;padding:4px 8px;background:var(--bg-page);border-radius:4px;border:1px solid var(--border)">
              <span class="muted" style="font-size:var(--fs-xs);text-transform:uppercase">${grp}</span><br>
              ${grpSessions.length ? grpSessions.map(s=>`<span style="font-size:var(--fs-base)">${esc(s.activity_title||'—')}</span>`).join('<br>') : '<span class="muted" style="font-size:var(--fs-base)">unscheduled</span>'}
            </div>`;
          }).join('')}
        </div>
      </div>`;
    }).join('');
  } catch(e){ body.innerHTML=`<p class="muted">Could not load the term planner: ${esc(apiErr(e))}</p>`; }
}

// ═══════════════
//  NIGHT BUILDER
// ═══════════════

async function loadBuilderDates(yearId){
  const sel = document.getElementById('builder-date-sel');
  sel.innerHTML='<option value="">— select night —</option>';
  if(!yearId) return;
  try {
    const rows = await api(`/api/planning/years/${yearId}/parade-dates`);
    rows.forEach(d=>{
      const o=document.createElement('option');
      o.value=d.parade_date_id;
      o.textContent=`${d.parade_date} (${_dayName(d.parade_date)})${d.parade_night_id?'':' ⚠️'}`;
      sel.appendChild(o);
    });
  } catch(e){
    console.warn('builder dates load failed',e);
    // A <select> can't show a headline/reason block -- a disabled option
    // naming the failure is the equivalent of this program's usual
    // WHAT-HAPPENED/NEXT-STEP structure for this specific control type.
    sel.innerHTML=`<option value="">Could not load parade nights — ${esc(apiErr(e))}</option>`;
  }
}

async function _loadDirectPnSelector(){
  const sel = document.getElementById('builder-direct-pn-sel');
  if(!sel) return;
  sel.innerHTML='<option value="">— jump to any parade night —</option>';
  try {
    const pns = await api('/api/parade-nights');
    (pns||[]).forEach(pn=>{
      const o=document.createElement('option');
      o.value=pn.parade_night_id; o.textContent=`${pn.date} (${_dayName(pn.date)}) — ${pn.term||''}`;
      sel.appendChild(o);
    });
  } catch(e){ console.warn('direct pn load failed',e); }
}
// ═══════════════
//  WEEKLY PROGRAM
// ═══════════════

async function loadPWDates(yearId){
  const sel = document.getElementById('pw-date-sel');
  if(!sel) return; // element removed with standalone Weekly Program page
  sel.innerHTML='<option value="">— select night —</option>';
  if(!yearId) return;
  try {
    const rows = await api(`/api/planning/years/${yearId}/parade-dates`);
    rows.forEach(d=>{
      const o=document.createElement('option');
      o.value=d.parade_date_id; o.textContent=`${d.parade_date} (${_dayName(d.parade_date)})`;
      sel.appendChild(o);
    });
  } catch(e){ sel.innerHTML=`<option value="">Could not load parade nights — ${esc(apiErr(e))}</option>`; }
}

async function loadWeeklyProgram(dateId){
  const card = document.getElementById('pw-card');
  const empty = document.getElementById('pw-empty');
  const hdr = document.getElementById('pw-header-row');
  const body = document.getElementById('pw-body');
  const pwSection=document.getElementById('pw-preview-section');
  if(!dateId){ card.style.display='none'; if(empty)empty.style.display=''; if(pwSection)pwSection.style.display='none'; return; }
  if(pwSection) pwSection.style.display='';
  try {
    const d = await api(`/api/planning/parade-dates/${dateId}/weekly-program`);
    if(hdr) hdr.innerHTML=`<strong>${esc(d.parade_date)}</strong> &nbsp;
      ${d.has_unresolved_conflicts?'<span class="badge badge-red">Conflicts</span>':'<span class="badge badge-green">Ready</span>'}`;
    const byGroupSession = {};
    (d.sessions||[]).forEach(s=>{ byGroupSession[`${s.cadet_group}:${s.session_number}`]=s; });
    const maxSess = (d.sessions||[]).reduce((m,s)=>Math.max(m,s.session_number),3);
    const instrBlocks=(d.timing_blocks||[]).filter(b=>b.is_instructional||b.is_instructional_period);
    let html=`<table class="data-table"><thead><tr><th>Period</th>`;
    _CADET_GROUPS.forEach(g=>html+=`<th style="text-transform:capitalize">${g}</th>`);
    html+=`</tr></thead><tbody>`;
    for(let sn=1; sn<=maxSess; sn++){
      const block=instrBlocks[sn-1];
      html+=`<tr><td>${sn}${block?`<div style="font-size:var(--fs-sm);color:var(--muted)">${esc(block.start_time)}–${esc(block.end_time)}</div>`:''}</td>`;
      _CADET_GROUPS.forEach(grp=>{
        const s = byGroupSession[`${grp}:${sn}`];
        html+=`<td>${s?`<strong>${esc(s.activity_title||s.curriculum_code||'—')}</strong>${s.facilitator_name?`<div style="font-size:var(--fs-sm);color:var(--muted)">${esc(s.facilitator_name)}</div>`:''}`:
          '<span class="muted">—</span>'}</td>`;
      });
      html+=`</tr>`;
    }
    html+=`</tbody></table>`;
    body.innerHTML=html;
    card.style.display=''; if(empty)empty.style.display='none';
  } catch(e){ if(empty)empty.innerHTML=`<p class="muted">Error loading weekly program: ${esc(apiErr(e))}</p>`; card.style.display='none'; if(empty)empty.style.display=''; }
}

// ═══════════════
//  LONG RANGE
// ═══════════════
// Deliberately unreachable in this frontend, not dead/incomplete code:
// _PLANNING_PAGES is empty for this pilot ("Remaining tabs (anchors, term,
// long-range, rooms, checks) are hidden from nav for this pilot" -- see that
// constant's own comment), so there is no id="page-long-range" container and
// nothing calls loadLongRange(). The real Long Range view lives in Planning
// Workspace (the "Planning Workspace ↗" nav link routes there) and reads the
// same GET /api/planning/years/{id}/long-range endpoint this function also
// calls. Confirmed during remediation Stage 7 research, 2026-08-05 -- kept
// here rather than deleted in case a future pilot phase re-enables this tab.
async function loadLongRange(yearId){
  const card = document.getElementById('lr-card');
  const empty = document.getElementById('lr-empty');
  if(!yearId){ card.style.display='none'; empty.style.display=''; return; }
  const weeks = document.getElementById('lr-weeks-sel').value||'8';
  try {
    const d = await api(`/api/planning/years/${yearId}/long-range?weeks=${weeks}`);
    // Anchors strip
    const anchRow = document.getElementById('lr-anchors-row');
    if(d.anchors.length){
      anchRow.innerHTML=`<strong>Activities in view:</strong> `+
        d.anchors.map(a=>`<span class="badge ${_importanceBadge(a.importance)}" style="margin:2px">${esc(a.event_name)} (${esc(a.start_date)})</span>`).join(' ');
    } else { anchRow.innerHTML='<span class="muted">No anchor events in this window.</span>'; }
    // Main grid
    if(!d.parade_dates.length){
      document.getElementById('lr-body').innerHTML='<div class="empty"><div class="et">No parade dates in this range</div><div class="es">Generate parade dates for your year to see them here. <a href="#" onclick="nav(\'activities\');return false">Go to Activities</a>.</div></div>';
      card.style.display=''; empty.style.display='none'; return;
    }
    let html='';
    d.parade_dates.forEach(row=>{
      const pd=row.parade_date;
      const conflicts=row.conflicts||[];
      const sessions=row.sessions||[];
      const groups={};
      sessions.forEach(s=>{ groups[s.cadet_group]=(groups[s.cadet_group]||[]); groups[s.cadet_group].push(s); });
      const filled=Object.values(groups).reduce((t,g)=>t+g.length,0);
      html+=`<div style="padding:10px 12px;border-radius:8px;border:1px solid var(--border);margin-bottom:10px;background:var(--bg-card)">
        <div style="display:flex;gap:12px;align-items:center;margin-bottom:6px">
          <strong>${esc(pd.parade_date)}</strong> <span class="muted">${_dayName(pd.parade_date)}</span>
          ${conflicts.length?`<span class="badge badge-red">${conflicts.length} conflict${conflicts.length!==1?'s':''}</span>`:''}
          <span class="muted" style="font-size:var(--fs-base)">${filled}/${_CADET_GROUPS.length*3} slots</span>
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:4px">
          ${_CADET_GROUPS.map(grp=>{
            const gs=groups[grp]||[];
            return `<span style="padding:2px 8px;border-radius:4px;font-size:var(--fs-sm);background:${gs.length?'var(--accent-light, #e8f5e9)':'var(--bg-page)'}">
              ${grp.substring(0,3)}: ${gs.length?esc(gs[0].activity_title||'…'):'—'}
            </span>`;
          }).join('')}
        </div>
      </div>`;
    });
    document.getElementById('lr-body').innerHTML=html;
    card.style.display=''; empty.style.display='none';
  } catch(e){ empty.innerHTML=`<p class="muted">Could not load the long-range view: ${esc(apiErr(e))}</p>`; card.style.display='none'; empty.style.display=''; }
}

// ═══════════════
//  ROOMS & STAFF
// ═══════════════

async function loadLocations(){
  const el = document.getElementById('locations-body');
  el.innerHTML='<p class="muted">Loading…</p>';
  try {
    // Use real training-areas (primary) and supplement with planning-only locations
    const taResp = await api('/api/training-areas').catch(()=>[]);
    const planLocs = await api('/api/planning/locations').catch(()=>[]);
    const realRooms = (taResp||[]).map(r=>({id:r.id,name:r.name,location_type:'training-area',capacity:r.capacity,active_status:true,source:'real'}));
    const planRoomsOnly = (planLocs||[]).filter(l=>!realRooms.find(r=>r.name===l.name));
    const allLocs = [...realRooms, ...planRoomsOnly.map(l=>({...l,source:'planning'}))];
    P.locations = allLocs;
    if(!allLocs.length){
      el.innerHTML='<div class="empty"><div class="et">No locations added</div><div class="es">Add training areas on the <a href="#" onclick="nav(\'resources\');return false">Resources & Training Areas page</a> (squadron scope) or add a planning-specific location below.</div></div>';
      return;
    }
    el.innerHTML=`<div style="overflow-x:auto"><table class="data-table"><thead><tr><th>Name</th><th>Type</th><th>Capacity</th><th>Source</th></tr></thead><tbody>`+
      allLocs.map(l=>`<tr>
        <td>${esc(l.name)}</td>
        <td>${l.location_type?esc(_cap(l.location_type.replace(/-/g,' '))):'—'}</td>
        <td>${l.capacity!=null?l.capacity:'—'}</td>
        <td><span class="badge ${l.source==='real'?'badge-green':'badge-grey'}">${l.source==='real'?'Training Area':'Planning Only'}</span></td>
      </tr>`).join('')+
      `</tbody></table></div>`;
  } catch(e){ el.innerHTML=`<p class="muted">Could not load locations: ${esc(apiErr(e))}</p>`; }
}

async function loadPlanningFacilitators(){
  const el = document.getElementById('planning-fac-body');
  el.innerHTML='<p class="muted">Loading…</p>';
  try {
    // Use real facilitators endpoint
    const facs = S.facs && S.facs.length ? S.facs : await api('/api/facilitators').catch(()=>[]);
    P.facilitators = (facs||[]).map(f=>({
      facilitator_id: f.id||f.facilitator_id,
      display_name: facDisplay ? facDisplay(f) : `${f.current_rank||''} ${f.last_name||''}`.trim(),
      type: f.type,
      subject_areas: f.areas||f.subject_areas||[],
      max_sessions_per_night: f.max_sessions_per_night||'—',
      unit_id: f.squadron_id,
    }));
    if(!P.facilitators.length){
      el.innerHTML='<div class="empty"><div class="et">No facilitators found</div><div class="es">Add facilitators on the <a href="#" onclick="nav(\'facilitators\');return false">Facilitators page</a> first.</div></div>';
      return;
    }
    el.innerHTML=`<table class="data-table"><thead><tr><th>Name</th><th>Type</th><th>Subject Areas</th><th>Max / Night</th></tr></thead><tbody>`+
      P.facilitators.map(f=>`<tr>
        <td>${esc(f.display_name)}</td>
        <td>${esc(f.type||'—')}</td>
        <td>${(f.subject_areas||[]).map(s=>`<span class="badge badge-teal">${esc(s)}</span>`).join(' ')||'—'}</td>
        <td>${f.max_sessions_per_night}</td>
      </tr>`).join('')+
      `</tbody></table>`;
  } catch(e){ el.innerHTML=`<p class="muted">Could not load facilitators: ${esc(apiErr(e))}</p>`; }
}

function openAddLocationModal(){
  ['loc-name-inp','loc-notes-inp'].forEach(id=>document.getElementById(id).value='');
  document.getElementById('loc-type-inp').value='indoor';
  document.getElementById('loc-cap-inp').value='';
  document.getElementById('loc-msg').textContent='';
  openModal('m-add-location');
}
async function doAddLocation(){
  const name=document.getElementById('loc-name-inp').value.trim();
  if(!name){ document.getElementById('loc-msg').textContent='Name is required.'; return; }
  const cap=document.getElementById('loc-cap-inp').value;
  try {
    await api('/api/planning/locations',{method:'POST',body:{
      name, location_type:document.getElementById('loc-type-inp').value,
      capacity: cap ? parseInt(cap) : null,
      notes: document.getElementById('loc-notes-inp').value||null,
    }});
    closeModal('m-add-location'); await loadLocations();
  } catch(e){ document.getElementById('loc-msg').textContent=apiErr(e); }
}

// ═══════════════
//  PLANNING CHECKS
// ═══════════════

async function loadPlanningChecks(yearId){
  P.currentYearId=yearId;
  const card=document.getElementById('checks-card');
  const empty=document.getElementById('checks-empty');
  const sel=document.getElementById('checks-year-sel');
  if(sel&&yearId)sel.value=yearId;
  if(!yearId){ card.style.display='none'; empty.style.display=''; return; }
  try {
    const [guide, conflicts] = await Promise.all([
      api(`/api/planning/years/${yearId}/decision-guide`),
      api(`/api/planning/years/${yearId}/conflicts`),
    ]);
    _renderDecisionGuide(guide.checks);
    _renderConflicts(conflicts, yearId);
    card.style.display=''; empty.style.display='none';
  } catch(e){ empty.innerHTML=`<p class="muted">Could not load the decision guide and conflicts: ${esc(apiErr(e))}</p>`; card.style.display='none'; empty.style.display=''; }
}

function _renderDecisionGuide(checks){
  const el=document.getElementById('checks-guide-body');
  el.innerHTML=`<h3>Decision Guide</h3>`+
    checks.map(c=>`<div style="display:flex;align-items:flex-start;gap:10px;padding:8px 0;border-bottom:1px solid var(--border)">
      <span style="font-size:var(--fs-2xl)">${c.result?'🔴':'✅'}</span>
      <div>
        <strong>${esc(c.question)}</strong><br>
        ${c.detail&&c.detail.length?`<span class="muted" style="font-size:var(--fs-md)">${c.detail.map(esc).join(', ')}</span><br>`:''}
        ${c.action?`<span style="color:var(--warning);font-size:var(--fs-md)">${esc(c.action)}</span>`:''}
      </div>
    </div>`).join('');
}

function _renderConflicts(conflicts, yearId){
  const el=document.getElementById('checks-conflicts-body');
  if(!conflicts.length){ el.innerHTML='<p class="muted">No unresolved conflicts.</p>'; return; }
  el.innerHTML=`<table class="data-table"><thead><tr><th>Severity</th><th>Type</th><th>Message</th><th></th></tr></thead><tbody>`+
    conflicts.map(c=>`<tr>
      <td><span class="badge ${c.severity==='critical'?'badge-red':'badge-yellow'}">${esc(_cap(c.severity))}</span></td>
      <td>${esc(_cap(c.conflict_type.replace(/_/g,' ')))}</td>
      <td>${esc(c.message)}</td>
      <td><button class="btn-xs btn-secondary" onclick="promptOverrideConflict('${esc(c.conflict_id)}','${esc(yearId)}')">Override</button></td>
    </tr>`).join('')+
    `</tbody></table>`;
}

async function runAllChecks(){
  if(!P.currentYearId){ showToast('Select a year from the dropdown above before continuing.',true); return; }
  try {
    const r=await api(`/api/planning/years/${P.currentYearId}/run-checks`,{method:'POST'});
    await loadPlanningChecks(P.currentYearId);
    showToast(`Checks complete. ${r.conflicts_detected} conflict${r.conflicts_detected!==1?'s':''} detected.`);
  } catch(e){ showToast(apiErr(e),true); }
}

async function promptOverrideConflict(cId, yearId){
  const reason=await promptText('Override conflict','Reason (required)',{
    context:'State why this conflict is being overridden. This is recorded in the audit log.',
    okLabel:'Override',
  });
  if(!reason)return;
  try {
    await api(`/api/planning/conflicts/${cId}/override`,{method:'POST',body:{override_reason:reason.trim()}});
    await loadPlanningChecks(yearId);
  } catch(e){ showToast(apiErr(e),true); }
}
