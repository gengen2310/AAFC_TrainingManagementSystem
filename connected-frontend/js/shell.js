// Main TMS module: application shell and navigation -- scope landing,
// maintenance banner polling, bootApp()/renderAll(), nav() and the mobile
// navigation drawer.
// Extracted verbatim from connected-frontend/index.html (stabilisation Phase 4,
// C6). Top-level function declarations and side-effect-free let/const only;
// loaded as a classic script BEFORE the inline bootstrap, so everything here
// is defined before any page-load code runs. Statements with load-time
// effects stay in index.html in their original order. Parity is proven by
// tools/architecture/frontend_parity.mjs.

// ═══════════════════════════════════════════════════════════
//  BOOT
// ═══════════════════════════════════════════════════════════
// Pages each scope may see. Backend still authorises every request.
// Pilot-visible planning pages. Remaining tabs (anchors, term, long-range, rooms, checks) are hidden from nav for this pilot.
// Pilot-visible planning pages. Remaining tabs (anchors, term, long-range, rooms, checks) are hidden from nav for this pilot.
const _PLANNING_PAGES=[];
const SCOPE_LANDING={squadron:'dashboard',wing:'wing-overview',national:'national',auditor:'audit',system_admin:'system-console'};
// In Proxy Mode (Wing) or Delegated Intervention (NAT HQ) the UI shows the EXACT SQN workspace
// for the acting squadron; the backend returns that squadron's data while proxy is active.
//
// System Administrator additionally has its own browsing scope (S.saScope, set via the
// sa-scope-bar selector) letting it inspect a specific Wing or Squadron's operational pages
// with NO Proxy/Intervention Mode required — viewing is unconditionally authorised for
// system_admin server-side (can_view_squadron/can_view_wing). Only protected writes still
// require Delegated Intervention (proxyActive()), exactly as for national_admin.
function effectiveScope(){
  const sc=getScopeType();
  if(sc==='system_admin'){
    if(proxyActive())return 'squadron';
    if(S.saScope&&S.saScope.level==='squadron')return 'squadron';
    if(S.saScope&&S.saScope.level==='wing')return 'wing';
    return 'system_admin';
  }
  return proxyActive() ? 'squadron' : sc;
}

function _showMaintenanceBanner(phase,title,msg){
  const b=document.getElementById('maint-banner');
  const ic=document.getElementById('maint-icon');
  const m=document.getElementById('maint-msg');
  if(!b)return;
  const isPending=phase==='pending';
  b.className='maint-banner show'+(isPending?' pending':'');
  if(ic)ic.textContent=isPending?'⚠️':'🔒';
  if(m){
    const t=title||(isPending?'Maintenance Starting':'Maintenance');
    const body=msg||(isPending?'Maintenance will begin shortly.':'System under maintenance.');
    m.textContent=t+' — '+body;
  }
}
function _hideMaintenanceBanner(){
  const b=document.getElementById('maint-banner'); if(b)b.className='maint-banner';
}
let _maintPollTimer=null;
function _scheduleMaintPoll(ms){
  if(_maintPollTimer)clearTimeout(_maintPollTimer);
  _maintPollTimer=setTimeout(_pollMaintenanceStatus,ms);
}
// DEF-12: proactively check maintenance mode so users already in session see the
// banner when write-block activates — not only when they attempt a write.
// MAINT-02: poll faster (5 s) during PENDING phase so users see the LOCKED
// transition promptly; back off to 90 s in normal/locked states.
async function _pollMaintenanceStatus(){
  if(!S.session)return; // not logged in
  try{
    const r=await fetch((API_BASE||'')+'/api/health/ui-config');
    if(!r.ok){_scheduleMaintPoll(90000);return;}
    const d=await r.json();
    const phase=d.maintenance_phase||'normal';
    if(phase==='pending'||phase==='locked'){
      _showMaintenanceBanner(phase,d.maintenance_title,d.maintenance_message||undefined);
      _scheduleMaintPoll(phase==='pending'?5000:90000);
    }else{
      _hideMaintenanceBanner();
      _scheduleMaintPoll(90000);
    }
  }catch(_){_scheduleMaintPoll(90000);}
}

function updateDebugBar(){
  const d=document.getElementById('debug-bar'); if(!d)return;
  const dev=['localhost','127.0.0.1'].some(h=>location.hostname.includes(h));
  if(!dev){ d.style.display='none'; return; }
  d.style.display='flex';
  const mode=proxyActive()?('<span class="warn">'+(proxyMode()==='delegated_intervention'?'INTERVENTION':'PROXY')+' active</span>'):'none';
  d.innerHTML=`<span>origin <b>${location.origin}</b></span><span>api <b>${API_BASE||'(same-origin)'}</b></span>`+
    `<span>role <b>${S.role||'—'}</b></span><span>scope <b>${getScopeType()}</b></span><span>mode ${mode}</span>`+
    `<span>health <b>${API_BASE||''}/api/health</b></span>`;
}

function _consumeTmsSetupHandoff(){
  const url=new URL(window.location.href);
  if(url.searchParams.get('aafc_page')!=='settings')return null;
  const year=Number(url.searchParams.get('aafc_training_year'));
  if(!Number.isInteger(year)||year<1990||year>2999)return null;
  url.searchParams.delete('aafc_page');
  url.searchParams.delete('aafc_training_year');
  window.history.replaceState(null,'',url.pathname+url.search+url.hash);
  const existing=(P.years||[]).find(y=>Number(y.year)===year&&y.active_status!==false);
  if(existing)return existing;
  // Remembered so the year survives the refetch Settings does on open; without
  // it the logical row vanished and the landing had no Set up action (T08).
  P._handoffYear=year;
  const logical=_ynLogicalYear(year);
  P.years=[...(P.years||[]).filter(y=>Number(y.year)!==year),logical];
  return logical;
}

function _ynLogicalYear(year){
  const now=new Date().getFullYear();
  return {year, planning_year_id:null, active_status:true, materialised:false,
          state:year<now?'past':year>now?'future':'current'};
}

function bootApp(){
  const info=getCurrentUnitInfo();
  const scope=effectiveScope();
  document.getElementById('auth-screen').style.display='none';
  document.getElementById('app').style.display='flex';
  document.getElementById('tb-unit').textContent=S.scopeName||info.name;
  const navUnitName=document.getElementById('nav-unit-name');
  if(navUnitName) navUnitName.textContent=S.scopeName||info.name;
  const navFooterScope=document.getElementById('nav-footer-scope');
  if(navFooterScope) navFooterScope.textContent=effectiveScope().replace('_',' ');
  const chip=document.getElementById('tb-chip');
  chip.textContent=info.short; chip.className='sqn-chip'+(S.isAdmin?' admin':'');
  updateScopeBanner(); updateModeBanner(); updateDebugBar();
  applyNavScope();
  // Planning Workspace link — visible for squadron/wing/national if URL is configured via API.
  const pwLink=document.getElementById('nav-pw-link'), pwLbl=document.getElementById('nav-lbl-pw');
  const pwUnconfigured=document.getElementById('nav-pw-unconfigured');
  const pwUrl=S.pwUrl;
  if(pwLink&&pwUrl){
    pwLink.href=pwUrl;
    // FF-01: Firefox ETP blocks SameSite=None cookie cross-origin so the PW
    // tab can't fall back to cookie auth. Pass the Bearer token in the URL
    // hash fragment instead — fragments are never sent to the server and are
    // cleared by the PW before any navigation so they don't persist in history.
    pwLink.addEventListener('click',function(e){
      const tok=sessionStorage.getItem('aafc_token');
      if(tok){
        e.preventDefault();
        openPlanningWorkspace();
      }
    },{once:false});
  }
  // sqn_general is read-only and has no Planning Workspace access (2026-09-28).
  const pwEligibleScope=['squadron','wing','national','system_admin'].includes(scope)&&S.role!=='sqn_general';
  const showPW=!!pwUrl&&pwEligibleScope;
  const showPWUnconfigured=!pwUrl&&pwEligibleScope;
  if(pwLink)pwLink.style.display=showPW?'flex':'none';
  if(pwUnconfigured)pwUnconfigured.style.display=showPWUnconfigured?'flex':'none';
  if(pwLbl)pwLbl.style.display=(showPW||showPWUnconfigured)?'block':'none';
  // §33: show PW deep-link button in Unit Settings header when PW is configured
  const settingsPwActions=document.getElementById('settings-pw-actions');
  if(settingsPwActions)settingsPwActions.style.display=showPW?'':'none';
  // Write controls: visible only where this role/scope can currently write; auditor/viewers read-only.
  const canWrite = scope==='squadron' ? canWriteSquadron() : false; // wing/national write only via proxy into a squadron
  // SET-1: this forced inline-flex onto every .admin-el, including whole
  // <div class="card admin-el"> containers -- which turned the card into a flex
  // row and laid its heading, description and list out side by side instead of
  // stacked. Buttons and inline labels still want inline-flex; a card wants its
  // own block layout back.
  document.querySelectorAll('.admin-el').forEach(el=>{
    const show=(canWrite||(scope!=='squadron'&&proxyActive()));
    if(!show){el.style.display='none';return;}
    // NAV-6: this used to force inline-flex on everything carrying .admin-el.
    // A .nav-item is a full-width row (.nav-item{display:flex}); inline-flex
    // shrank "Unit Setup" to its text -- 102px in a 220px sidebar -- so the rest
    // of the row was dead to the pointer while every other nav row was clickable
    // end to end. A .card wants block (SET-1). Everything else still wants
    // inline-flex.
    el.style.display = el.classList.contains('card')     ? 'block'
                     : el.classList.contains('nav-item') ? 'flex'
                     : 'inline-flex';
  });
  if(isReadOnly()){ document.body.classList.add('readonly'); document.querySelectorAll('.admin-el').forEach(el=>el.style.display='none'); }
  else { document.body.classList.remove('readonly'); }
  const recoveryCard=document.getElementById('settings-recovery-card');
  if(recoveryCard){
    recoveryCard.style.display=['system_admin','national_admin','wing_admin','sqn_admin'].includes(S.role)?'':'none';
  }
  // Planning-write controls: visible for sqn_admin + wing_admin (own calendar, no proxy needed).
  const canPlanWrite = canWritePlan();
  document.querySelectorAll('.plan-write-el').forEach(el=>{el.style.display=canPlanWrite?'inline-flex':'none';});
  // Wing admin squadron filter on Annual Program page
  const role=S.role||'';
  const isNatAdmin=['national_admin','system_admin'].includes(role);
  const isWingAdmin=['wing_admin'].includes(role);
  const pySqnFilterRow=document.getElementById('py-sqn-filter-row');
  if(pySqnFilterRow){
    pySqnFilterRow.style.display=(isWingAdmin&&!proxyActive())?'':'none';
    if(isWingAdmin&&!proxyActive()){
      const sqnSel=document.getElementById('py-sqn-filter');
      if(sqnSel){
        sqnSel.innerHTML='<option value="">— All squadrons —</option>';
        (S.wsqns||[]).forEach(sq=>{
          const o=document.createElement('option'); o.value=sq.squadron_id;
          o.textContent=`${sq.squadron_code||''} — ${sq.name||sq.squadron_id}`;
          sqnSel.appendChild(o);
        });
      }
    }
  }
  // Curriculum creation buttons: show based on current scope
  const isSqnAdmin=canWrite;
  const btnSqn=document.getElementById('btn-add-curr-sqn');
  const btnWing=document.getElementById('btn-add-curr-wing');
  const btnNat=document.getElementById('btn-add-curr-nat');
  if(!isReadOnly()){
    if(btnSqn) btnSqn.style.display=isSqnAdmin?'inline-flex':'none';
    if(btnWing) btnWing.style.display=(isWingAdmin||isNatAdmin)?'inline-flex':'none';
    if(btnNat) btnNat.style.display=isNatAdmin?'inline-flex':'none';
    document.querySelectorAll('.nat-admin-el').forEach(el=>{el.style.display=isNatAdmin?'inline-flex':'none';});
  }
  // Settings page mirrors unit config; access codes are never shown/editable here.
  const setVal=(id,v)=>{const e=document.getElementById(id);if(e)e.value=v;};
  setVal('s-sqn',S.scopeName||info.name); setVal('s-addr',S.cfg.addr||''); setVal('s-pday',S.cfg.day||'');
  setVal('s-start',S.cfg.start||''); setVal('s-end',S.cfg.end||'');
  _renderSessionStructureNote();
  setVal('s-crest',S.cfg.crestUrl||''); setVal('s-unit-type',S.cfg.unitType||'standard_squadron'); _renderCrestPreview();
  const _utSel = document.getElementById('s-unit-type');
  const _utNote = document.getElementById('s-unit-type-note');
  if (_utSel) _utSel.disabled = (S.role === 'sqn_admin');
  if (_utNote) _utNote.textContent = (S.role === 'sqn_admin') ? 'Set by wing or national admin' : '';
  renderTimingTemplates();
  const ccMsg=document.getElementById('cc-msg'); if(ccMsg)ccMsg.textContent='';
  calYear=_calDefaultYear();calMonth=new Date().getMonth();
  populateWPDD();
  _restorePNFilters();
  _restoreMissionFilters();
  renderAll();
  const handoffYear=_consumeTmsSetupHandoff();
  if(handoffYear && (NAV_BY_SCOPE[scope]||[]).includes('settings')){
    setCurrentYear(handoffYear,false);
    nav('settings');
  }else{
    if(handoffYear)showToast('Unit Setup is not available in this account scope.',true);
    nav(SCOPE_LANDING[scope]||'dashboard');
  }
}
function openPlanningWorkspace(){
  if(S&&S.role==='sqn_general')return; // no Planning Workspace access for read-only squadron users
  const pwUrl=S&&S.pwUrl; if(!pwUrl)return;
  const tok=sessionStorage.getItem('aafc_token');
  const yr=P&&P.currentYearInt?'&y='+P.currentYearInt:'';
  if(tok){window.open(pwUrl+'#t='+encodeURIComponent(tok)+yr,'_blank','noopener');}
  else{window.open(pwUrl,'_blank','noopener');}
}
function renderAll(){
  const scope=effectiveScope();
  if(scope==='system_admin'){
    // National operational data loaded by loadData; pre-render national views for navigation.
    renderNational(); renderAudit();
    return;
  }
  if(scope==='squadron'){ renderDash();renderPN();renderCurr();renderActs();renderFacs();renderRooms();renderActions(); }
  else { renderCurr(); }
  if(scope==='wing'){ renderWing(); }
  if(scope==='national'){ renderNational(); }
  if(scope==='wing'||scope==='national'||scope==='auditor'){ renderAudit(); }
  renderTimingTemplates();
}

// ═══════════════════════════════════════════════════════════
//  NAVIGATION
// ═══════════════════════════════════════════════════════════
async function nav(id){
  closeMobileNav();
  const ceaRequested=id==='cea-import';
  if(ceaRequested)id='cadets';
  if(id==='planning-year'||id==='planning-anchors'||id==='planning-term'||id==='planning-missions')id='activities';
  if(id==='planning-builder'||id==='planning-rooms')id='parade-nights';
  if(id==='planning-guide'||id==='planning-longrange'||id==='planning-checks')id='dashboard';
  document.querySelectorAll('.page').forEach(p=>{p.classList.remove('active');p.setAttribute('aria-hidden','true');});
  document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));
  const pg=document.getElementById('page-'+id);if(pg){pg.classList.add('active');pg.removeAttribute('aria-hidden');}
  document.querySelectorAll('.nav-item').forEach(n=>n.removeAttribute('aria-current'));
  document.querySelectorAll('.nav-item').forEach(n=>{if((n.getAttribute('onclick')||'').includes("'"+id+"'")){n.classList.add('active');n.setAttribute('aria-current','page');}});
  if(id==='getting-started')loadGettingStarted();
  if(id==='calendar'){renderCal();await _loadCalendarHolidayPeriods();}
  if(id==='weekly-program'){populateWPDD();renderWP();}
  if(id==='activities'){await _loadActivitiesPage();}
  if(id==='facilitators')await loadFacilitatorStats();
  if(id==='curriculum'){
    _loadCurriculumClassBreakdown();
  }
  if(id==='parade-nights'){await reloadAndRender();return;}
  if(id==='dashboard')renderDash();
  if(id==='wing-overview'){renderWing();loadCommandDashboard('wing');}
  if(id==='national'){renderNational();loadCommandDashboard('national');}
  if(id==='wing-activities'){await _actTabLoad('act-tab-wing','wing', (S.role==='system_admin')?saBrowseWingId():null);}
  if(id==='national-activities'){await _actTabLoad('act-tab-national','national',null);}
  if(id==='audit')renderAudit();
  if(id==='settings'){await renderSettings();}
  if(id==='accounts')renderAccounts();
  if(id==='system-console')loadSystemConsole();
  if(id==='action-items'){await Promise.all([loadRecentChanges(),loadNeedsAttentionSessions()]);}
  if(id==='cadets')initCadetsPage();
  if(id==='training-records')initTrainingRecordsPage();
  if(ceaRequested){showCadetSubview('cea',document.getElementById('cadets-tab-cea'));}
  if(id==='help')_loadHelpPage();
  if(id==='service-desk')loadServiceDesk();
}

// ─── nav() integration ────────────────────────────────────────────────────────
// loadWingCalendar() is called when nav('wing-calendar') fires via nav() switch

// ─── Mobile navigation drawer ─────────────────────────────────────────────────
function toggleMobileNav(){
  const isMobile=window.innerWidth<769;
  if(isMobile){
    const nav=document.querySelector('.sidenav');
    const overlay=document.getElementById('nav-overlay');
    const btn=document.getElementById('btn-hamburger');
    const isOpen=nav&&nav.classList.contains('nav-open');
    if(isOpen){ closeMobileNav(); }
    else {
      if(nav)nav.classList.add('nav-open');
      if(overlay)overlay.classList.add('nav-open');
      if(btn)btn.setAttribute('aria-expanded','true');
    }
  } else {
    // Desktop: toggle persistent collapsed state
    const collapsed=document.body.classList.toggle('nav-collapsed');
    try{ localStorage.setItem('navCollapsed', collapsed?'1':''); }catch(_){}
    const btn=document.getElementById('btn-hamburger');
    if(btn)btn.setAttribute('aria-expanded',collapsed?'false':'true');
  }
}
function closeMobileNav(){
  const nav=document.querySelector('.sidenav');
  const overlay=document.getElementById('nav-overlay');
  const btn=document.getElementById('btn-hamburger');
  if(nav)nav.classList.remove('nav-open');
  if(overlay)overlay.classList.remove('nav-open');
  if(btn)btn.setAttribute('aria-expanded','false');
}
