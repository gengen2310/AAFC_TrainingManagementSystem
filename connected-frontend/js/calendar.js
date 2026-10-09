// Main TMS module: Training Calendar page.
// Extracted verbatim from connected-frontend/index.html (stabilisation Phase 4,
// C6). Top-level function declarations and side-effect-free let/const only;
// loaded as a classic script BEFORE the inline bootstrap, so everything here
// is defined before any page-load code runs. Statements with load-time
// effects stay in index.html in their original order. Parity is proven by
// tools/architecture/frontend_parity.mjs.

// ═══════════════════════════════════════════════════════════
//  CALENDAR
// ═══════════════════════════════════════════════════════════
async function _refreshCalendar(){
  // loadData() only resets calYear/calMonth in bootApp()'s own reset step,
  // not on a plain reload, so the currently-viewed month/year survives.
  await _pageRefresh('cal-refresh-status', async()=>{
    await loadData();
    renderCal();
    await _loadCalendarHolidayPeriods();
  });
}
// CAL-1: rebuild the calendar year list from what exists -- the training years
// plus every year that actually carries a parade night or activity. Always
// includes the year currently shown so the <select> can never render blank.
function _syncCalYearOptions(){
  const sel=document.getElementById('cal-yr');
  if(!sel) return;
  const yrs=new Set();
  const add=v=>{const n=parseInt(v,10); if(n>=1990&&n<=2999) yrs.add(n);};
  ((typeof P!=='undefined'&&P.years)||[]).forEach(y=>add(y&&y.year));
  ((typeof S!=='undefined'&&S.pns)||[]).forEach(x=>add(String(x.date||'').slice(0,4)));
  ((typeof S!=='undefined'&&S.acts)||[]).forEach(x=>add(String(x.date||'').slice(0,4)));
  add(new Date().getFullYear());
  add(calYear);
  const list=[...yrs].sort((a,b)=>a-b);
  sel.innerHTML=list.map(y=>`<option value="${y}">${y}</option>`).join('');
}

// CAL-2: the calendar opened on the wall-clock year even when the unit was
// planning a different training year, so a newly created year was never shown.
function _calDefaultYear(){
  const ty=(typeof P!=='undefined'&&P.currentYearInt)?parseInt(P.currentYearInt,10):null;
  return (ty&&ty>=1990&&ty<=2999)?ty:new Date().getFullYear();
}

async function _loadCalendarHolidayPeriods(){
  const requestId=++_calHolidayRequestId;
  const requestedYear=calYear;
  const planningYear=(P.years||[]).find(y=>Number(y.year)===requestedYear&&y.planning_year_id);
  S.holidays=[];
  _calHolidayStatus=planningYear
    ?`Loading Holiday Periods for ${requestedYear}…`
    :`No Training Year is set up for ${requestedYear}.`;
  renderCal();
  if(!planningYear)return;
  try{
    const rows=await api(`/api/planning/years/${encodeURIComponent(planningYear.planning_year_id)}/holidays`);
    if(requestId!==_calHolidayRequestId||requestedYear!==calYear)return;
    S.holidays=(rows||[]).map(h=>({id:h.holiday_id,name:h.name,start:h.start_date,end:h.end_date}));
    _calHolidayStatus=S.holidays.length
      ?`${S.holidays.length} Holiday Period${S.holidays.length===1?'':'s'} loaded for ${requestedYear}.`
      :`No Holiday Periods for ${requestedYear}.`;
  }catch(e){
    if(requestId!==_calHolidayRequestId||requestedYear!==calYear)return;
    S.holidays=[];
    _calHolidayStatus=`Could not load Holiday Periods for ${requestedYear}: ${apiErr(e)}`;
  }
  renderCal();
}

function _calSelectYear(value){
  const year=parseInt(value,10);
  if(!Number.isFinite(year))return;
  const changed=year!==calYear;
  calYear=year;
  renderCal();
  if(changed)_loadCalendarHolidayPeriods();
}

function renderCal(){
  _syncCalYearOptions();
  document.getElementById('cal-m').textContent=MONTHS[calMonth]+' '+calYear;
  document.getElementById('cal-yr').value=calYear;
  const holidayStatus=document.getElementById('cal-holiday-status');
  if(holidayStatus)holidayStatus.textContent=_calHolidayStatus;
  document.getElementById('cal-hdr').innerHTML=DAYS.map(d=>`<div class="cal-dn">${d}</div>`).join('');
  const first=new Date(calYear,calMonth,1),last=new Date(calYear,calMonth+1,0),td=today();
  let cells='';
  for(let i=0;i<first.getDay();i++){cells+=`<div class="cal-cell other"><div class="cal-dt">${new Date(calYear,calMonth,-first.getDay()+i+1).getDate()}</div></div>`;}
  for(let d=1;d<=last.getDate();d++){
    const ds=`${calYear}-${String(calMonth+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
    const pn=S.pns.find(p=>p.date===ds);
    const acts=S.acts.filter(a=>a.date===ds);
    const hol=(S.holidays||[]).find(h=>ds>=h.start&&ds<=h.end);
    const isT=new Date(calYear,calMonth,d).getTime()===td.getTime();
    let cls='cal-cell'+(pn?' parade':'')+(isT?' today':'')+(acts.length&&!pn?' act-day':'')+(hol?' holiday-day':'');
    let chips='';
    if(hol)chips+=`<span class="cal-chip" style="background:var(--warn-bg);color:var(--warn-text)" title="${esc(hol.name)}">${esc(hol.name.substring(0,16))}</span>`; /* DES-H04 */
    if(pn)(pn.sessions||[]).slice(0,3).forEach(s=>{
      // Status icon prefix, not color alone (WCAG / colour-blind safe) --
      // matches Planning Workspace's StatusBadge.tsx icon set (Stage 11
      // follow-up, 2026-08-05).
      const icon=_ST_ICON[s.status]||'';
      chips+=`<span class="cal-chip ${stCls(s.status)}" title="${esc(stLabel(s.status))}">${icon?icon+' ':''}${esc(PH_S[s.phase]||s.phase)}</span>`;
    });
    acts.slice(0,1).forEach(a=>chips+=`<span class="cal-chip act" title="${esc(a.name)}${a.owningOrgLabel?' — '+esc(a.owningOrgLabel):''}">${esc(a.name.substring(0,16))}</span>`);
    const oc=pn?`onclick="showPNDetail('${ds}')"`:canWriteSquadron()?`onclick="openWithDate('${ds}')"`:'';
    cells+=`<div class="${cls}" ${oc}><div class="cal-dt">${d}</div>${chips}</div>`;
  }
  let tail=(7-(first.getDay()+last.getDate())%7)%7;
  for(let i=1;i<=tail;i++)cells+=`<div class="cal-cell other"><div class="cal-dt">${i}</div></div>`;
  document.getElementById('cal-grid').innerHTML=cells;
}
function calMove(d){
  const oldYear=calYear;
  calMonth+=d;
  if(calMonth<0){calMonth=11;calYear--;}
  if(calMonth>11){calMonth=0;calYear++;}
  renderCal();
  if(calYear!==oldYear)_loadCalendarHolidayPeriods();
}
function openWithDate(ds){openAddPN(ds);}
