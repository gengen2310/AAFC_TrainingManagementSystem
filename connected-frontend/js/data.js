// Main TMS module: application state (SQN_DATA, S) and data loading --
// loadData() and the view-shape adapters, the outcome-reason dialog, thin api
// wrappers and lookups.
// Extracted verbatim from connected-frontend/index.html (stabilisation Phase 4,
// C6). Top-level function declarations and side-effect-free let/const only;
// loaded as a classic script BEFORE the inline bootstrap, so everything here
// is defined before any page-load code runs. Statements with load-time
// effects stay in index.html in their original order. Parity is proven by
// tools/architecture/frontend_parity.mjs.

// ═══════════════════════════════════════════════════════════
//  SQUADRON DATA
// ═══════════════════════════════════════════════════════════
const SQN_DATA={
  "7WG":{name:"7 Wing HQ",short:"7WG",addr:"RAAF Base Pearce, Bullsbrook WA 6084",day:"Tuesday",start:"19:00",end:"22:00",sess:2},
  "701":{name:"701 Squadron — Bullsbrook",short:"701SQN",addr:"Great Northern Highway, Bullsbrook WA 6084",day:"Friday",start:"18:00",end:"22:00",sess:3},
  "702":{name:"702 Squadron — Cannington",short:"702SQN",addr:"Gate 3, 1-5 Station Street, Cannington WA 6107",day:"Wednesday",start:"18:00",end:"21:30",sess:3},
  "703":{name:"703 Squadron — City of Fremantle",short:"703SQN",addr:"Leeuwin Barracks, Riverside Road, East Fremantle WA 6158",day:"Friday",start:"18:00",end:"22:00",sess:3},
  "704":{name:"704 Squadron — Madeley",short:"704SQN",addr:"Kingsway Regional Sporting Complex, Madeley WA 6065",day:"Friday",start:"18:00",end:"22:00",sess:3},
  "705":{name:"705 Squadron — City of Albany",short:"705SQN",addr:"Corner Spencer St & Serpentine Road, Albany WA 6330",day:"Wednesday",start:"17:20",end:"21:15",sess:2},
  "707":{name:"707 Squadron — Mandurah",short:"707SQN",addr:"Coodanup Dve, Coodanup WA 6210",day:"Wednesday",start:"18:15",end:"22:00",sess:3},
  "708":{name:"708 Squadron — Rockingham",short:"708SQN",addr:"127 Dixon Road, Rockingham WA 6168",day:"Friday",start:"18:15",end:"22:00",sess:3},
  "709":{name:"709 Squadron — Kalgoorlie-Boulder",short:"709SQN",addr:"23 Cheetham Street, Kalgoorlie WA 6430",day:"Monday",start:"17:45",end:"21:30",sess:2},
  "710":{name:"710 Squadron — Bunbury",short:"710SQN",addr:"Cnr Wilson Rd & Proffit St, Bunbury WA 6230",day:"Friday",start:"18:00",end:"21:30",sess:2},
  "711":{name:"711 Squadron — City of Greater Geraldton",short:"711SQN",addr:"Geraldton Defence Depot, 189 Lester Avenue, Geraldton WA 6530",day:"Monday",start:"17:30",end:"21:00",sess:2},
  "712":{name:"712 Squadron — City of Belmont",short:"712SQN",addr:"Palmer Barracks, Beavis Drive, South Guildford WA 6055",day:"Wednesday",start:"17:45",end:"21:30",sess:3},
  "713":{name:"713 Squadron — Cannington",short:"713SQN",addr:"Cannington Exhibition Centre, Gate 3 Station Street, Cannington WA 6107",day:"Friday",start:"18:00",end:"22:30",sess:3},
  "714":{name:"714 Squadron — Karrakatta",short:"714SQN",addr:"Irwin Barracks, Stubbs Terrace, Karrakatta WA 6010",day:"Friday",start:"18:00",end:"22:00",sess:3},
  "715":{name:"715 Squadron — City of Belmont",short:"715SQN",addr:"Palmer Barracks, Beavis Drive, South Guildford WA 6055",day:"Friday",start:"18:30",end:"22:00",sess:3},
  "721":{name:"721 Squadron — Madeley",short:"721SQN",addr:"Cnr Hartman Drive & Sporting Drive, Madeley WA 6065",day:"Wednesday",start:"18:30",end:"21:30",sess:2},
  "723":{name:"723 Squadron — Joondalup",short:"723SQN",addr:"North Metropolitan TAFE Joondalup, 63 Mclarty Avenue, Joondalup WA 6027",day:"Wednesday",start:"18:30",end:"21:30",sess:2},
};

// Default codes (overridable per-squadron via settings)
// Access codes are never defined or stored in the client. Authentication is performed by the backend.


// ═══════════════════════════════════════════════════════════
//  STATE
// ═══════════════════════════════════════════════════════════
let S={sqn:null,isAdmin:false,isWing:false,isNational:false,isAuditor:false,session:null,role:null,scopeName:'',pns:[],facs:[],acts:[],rooms:[],equip:[],cfg:{},curr:[],reports:{},actionItems:[]};
let _calHolidayRequestId=0,_calHolidayStatus='';
let currTabFilter='all';
let editCurrCode=null,editFacId=null,editRoomId=null,editEquipId=null,editSessRef=null;

function uid(){return 'x'+Math.random().toString(36).substr(2,9);}

// ═══════════════════════════════════════════════════════════
//  DATA LOADING  (fetched from the backend; adapted to the view shapes)
// ═══════════════════════════════════════════════════════════
function _facName(s){return s.facilitator_display_name_at_time||'';}
// Wraps a background GET used by loadData() so a transient failure is
// recorded instead of silently swallowed. Previously nearly every fetch in
// loadData() used a bare `.catch(()=>fallback)` with zero error surfaced --
// a transient failure (especially right after a create/edit, when
// reloadAndRender() re-fetches everything) rendered the affected list
// silently empty/stale with no indication anything went wrong, reproducing
// "I added it and it's not there" with no error message anywhere. Tracks
// failures on S._loadFailures so a single consolidated warning can be shown
// once, after Promise.all settles, instead of one alert per failed call.
function _apiT(path,fallback,label){
  return api(path).catch(e=>{
    (S._loadFailures=S._loadFailures||[]).push(label||path);
    return fallback;
  });
}

async function loadData(){
  S._loadFailures=[];
  // effectiveScope() (not getScopeType()) so a system_admin currently browsing
  // a Wing/Squadron via the sa-scope-bar selector loads that Wing/Squadron's
  // operational data through the exact same branches wing_admin/sqn_admin use.
  const scope=effectiveScope();
  const _saWingId=saBrowseWingId(), _saSqnId=saBrowseSquadronId();
  const _sqnId=(S.session&&S.session.squadron_id)||_saSqnId;
  const _proxyWasActive=proxyActive();
  // system_admin has no home wing_id/squadron_id server-side — when browsing,
  // these explicit IDs must be passed so the backend's view-only (no DI
  // required) branches added for Defect 2 are actually reached.
  const _sqq=_saSqnId?('?squadron_id='+encodeURIComponent(_saSqnId)):'';
  const _wgq=_saWingId?('?wing_id='+encodeURIComponent(_saWingId)):'';

  // Fire all requests in parallel — no await until Promise.all below.
  const p_uicfg=fetch(API_BASE+'/api/health/ui-config').then(r=>r.json()).catch(()=>null);
  const p_tags=api('/api/subject-area-tags').catch(()=>[]);
  const p_factypes=api('/api/facilitator-type-tags').catch(()=>[]);
  const p_reasontags=api('/api/session-status-reason-tags').catch(()=>[]);
  const p_acttypes=api('/api/activity-type-tags').catch(()=>[]);
  const p_captags=api('/api/training-area-capability-tags').catch(()=>[]);
  const p_pns=_apiT('/api/parade-nights'+_sqq,null,'Parade Nights');
  const p_facs=_apiT('/api/facilitators'+_sqq,null,'Facilitators');
  const p_cur=_apiT('/api/curriculum'+_sqq,null,'Curriculum');
  const p_phases=_apiT('/api/curriculum/phases',null,'Curriculum phases');
  // Custom training phases are ad-hoc scheduling groups (Wing Band, Biathlon
  // Team). They had a full CRUD screen in Unit Setup and NOTHING read them --
  // reported 2026-08-25 as "did not show up in the Phase in TMS". Loaded here
  // so a session can be scheduled against one. Deliberately kept out of
  // /api/curriculum/phases: that list also backs the Training Class stage
  // picker, where training_stage_id is a FK to curriculum_phases.id, so a
  // custom phase offered there would violate it.
  const p_customph=api('/api/custom-training-phases').catch(()=>[]);
  const p_ta=_apiT('/api/training-areas',null,'Training Areas');
  const p_eq=_apiT('/api/equipment',null,'Equipment');
  const p_ai=_apiT('/api/action-items',null,'Action Items');
  // REM-13: the squadron Training Calendar previously used the legacy
  // no-scope-type /api/activities call, which returns only this squadron's
  // own local Activity rows -- no CEA imports, no inherited Wing/National
  // activities (the Wing HQ Calendar has had both via its own scope-aware
  // call since REM-13 Phase A). scope_type=squadron is a strict superset of
  // the legacy result (same local rows, via the same OR-branched visibility
  // filter used everywhere else) plus those two sources -- sources=activity,cea
  // deliberately excludes 'holiday' since holidays are already merged into
  // this page from a separate, dedicated fetch (S.holidays, Stage 6); merging
  // them again here would double-render every holiday as two overlapping chips.
  const p_acts=_sqnId
    ?_apiT('/api/activities?scope_type=squadron&scope_id='+encodeURIComponent(_sqnId)+'&sources=activity,cea',null,'Activities')
    :_apiT('/api/activities',null,'Activities');
  // Holidays for the Training Calendar overlay -- active planning year(s) for
  // this squadron, flattened across years (usually just one).
  const p_holidays=_sqnId?(async()=>{
    try{
      // include_unmaterialised: a selectable year with no row must appear in the
      // bar, or an unconfigured year is unreachable. Those rows carry
      // planning_year_id=null, so every consumer below filters on it.
      const years=await api('/api/planning/years?include_unmaterialised=true&unit_id='+encodeURIComponent(_sqnId));
      // CAL-1: this fetch already had the year list and threw it away, so P.years
      // stayed empty until the planning page happened to load. The Training
      // Calendar's year selector is built from it, which is why a newly created
      // year did not appear there.
      if(typeof P!=='undefined'){
        P.years=years||[];
        // YR-4: P.currentYearId was only ever set by _loadPlanningYears(), which
        // runs when the planning page opens. At boot it stayed null, so the
        // Dashboard showed "No active training year" while the unit had active
        // years, and the calendar had no training year to follow.
        if(!P.currentYearInt && P.years.length){
          // Default to the current year, which is derived server-side. Falling
          // back to _pickDefaultYear keeps older payloads working.
          const cur=P.years.find(y=>y.state==='current');
          const d=cur||(typeof _pickDefaultYear==='function'?_pickDefaultYear(P.years):null);
          if(d){ P.currentYearId=d.planning_year_id||null; P.currentYearInt=d.year; }
        }
      }
      // planning_year_id is null for a year with no row -- requesting
      // /years/null/holidays would 404 every boot.
      // Historical rows remain active so they can be selected from the year
      // bar, but they are not dashboard/calendar inputs. Fetching holidays for
      // every retained year made boot fan out into hundreds of requests and
      // allowed a stale load to overwrite the selected-year context. Keep the
      // operational set to the current/future years (plus an explicitly
      // selected past year, handled by its year-scoped page load).
      const activeIds=(years||[]).filter(y=>y.active_status&&y.planning_year_id &&
        (y.state !== 'past' || y.planning_year_id === P.currentYearId))
        .map(y=>y.planning_year_id);
      const lists=await Promise.all(activeIds.map(id=>api('/api/planning/years/'+id+'/holidays').catch(()=>[])));
      return lists.flat();
    }catch(_){ return []; }
  })():Promise.resolve([]);
  const p_proxy=api('/api/proxy/current').catch(()=>({active:false}));
  const p_sum=api('/api/reports/summary'+_sqq).catch(()=>null);
  const p_read=api('/api/reports/readiness'+_sqq).catch(()=>null);
  const p_cov=api('/api/reports/curriculum-coverage'+_sqq).catch(()=>null);
  const p_fload=api('/api/reports/facilitator-load'+_sqq).catch(()=>null);
  const p_ndel=api('/api/reports/not-delivered'+_sqq).catch(()=>null);
  const p_sqnData=_sqnId?_apiT('/api/squadrons/'+_sqnId,null,'Squadron settings'):Promise.resolve(null);
  const p_timing=(scope==='squadron'||_proxyWasActive)?api('/api/timing-templates'+_sqq).catch(()=>[]):Promise.resolve([]);
  // AUD-1: 'audit' is in NAV_BY_SCOPE for wing, national, auditor and
  // system_admin, and this fetch covered every one of those except wing. A
  // wing_admin or wing_viewer opened Audit and always saw "No audit entries",
  // while GET /api/audit returns 300 rows for exactly that role.
  // Reset first: this flag is per-load, and it survived a role change until
  // 2026-08-22 -- a role that CAN read the log inherited the previous role's
  // denial and would have shown the wrong empty-state message.
  S.auditDenied=false;
  // Squadron scope reads its own squadron's audit rows (backend-scoped); the
  // Audit nav entry is gated per role in applyNavScope().
  const p_audit=(scope==='squadron'||scope==='wing'||scope==='national'||scope==='auditor'||scope==='system_admin')
    ? api('/api/audit').catch(e=>{ S.auditDenied=(e&&e.status===403); return []; })
    : Promise.resolve([]);
  const p_wov=scope==='wing'?api('/api/reports/wing-overview'+_wgq).catch(()=>null):Promise.resolve(null);
  const p_wph=scope==='wing'?api('/api/reports/wing-phase-coverage'+_wgq).catch(()=>null):Promise.resolve(null);
  const p_wcap=scope==='wing'?api('/api/reports/wing-capability'+_wgq).catch(()=>null):Promise.resolve(null);
  const p_wcancel=scope==='wing'?api('/api/reports/wing-cancellation-trend').catch(()=>null):Promise.resolve(null);
  const p_wndel=scope==='wing'?api('/api/reports/wing-not-delivered').catch(()=>null):Promise.resolve(null);
  // ACC-3: sqn_admin also needs S.squadrons populated (their own squadron only) so
  // _populateCreateSqns() can pre-select and lock it in the create-account modal.
  // GET /api/squadrons for sqn_admin returns exactly [their own squadron] (organisations.py:281).
  const p_wsqns=(scope==='wing'||scope==='squadron')?api('/api/squadrons'+_wgq).catch(()=>[]):Promise.resolve([]);
  const p_nat=(scope==='national'||scope==='system_admin')?api('/api/national/overview').catch(()=>null):Promise.resolve(null);
  const p_natov=(scope==='national'||scope==='system_admin')?api('/api/reports/national-overview').catch(()=>null):Promise.resolve(null);
  const p_natcap=(scope==='national'||scope==='system_admin')?api('/api/reports/national-capability').catch(()=>null):Promise.resolve(null);
  const p_wings=(scope==='national'||scope==='system_admin')?api('/api/wings').catch(()=>[]):Promise.resolve([]);
  const p_nsqns=(scope==='national'||scope==='system_admin')?api('/api/squadrons').catch(()=>[]):Promise.resolve([]);

  const[
    uicfg,tags,factypes,
    pns,facs,cur,phases,ta,eq,ai,acts,holidays,proxy,
    repSum,repRead,repCov,repFload,repNdel,
    sqnData,timing,auditData,
    wov,wph,wcap,wcancel,wndel,wsqns,
    nat,natov,natcap,wings,nsqns,
    reasontags,acttypes,captags,
  ]=await Promise.all([
    p_uicfg,p_tags,p_factypes,
    p_pns,p_facs,p_cur,p_phases,p_ta,p_eq,p_ai,p_acts,p_holidays,p_proxy,
    p_sum,p_read,p_cov,p_fload,p_ndel,
    p_sqnData,p_timing,p_audit,
    p_wov,p_wph,p_wcap,p_wcancel,p_wndel,p_wsqns,
    p_nat,p_natov,p_natcap,p_wings,p_nsqns,
    p_reasontags,p_acttypes,p_captags,
  ]);

  // Set state from resolved results
  S.pns=(Array.isArray(pns)?pns:[]).map(pn=>({
    id:pn.parade_night_id, date:pn.date, term:pn.term, nsess:pn.session_count,
    // Found while adding Training Class UI (task #170): this previously read
    // pn.parade_type instead of pn.notes -- the actual notes text a user
    // types into the Parade Night Details panel (showPNDetail's pnd-notes
    // field) was saved correctly to the backend but never displayed back
    // anywhere that reads S.pns (the card list's .pn-meta line, the search
    // filter in renderPN(), and two other display locations), and the
    // separate Parade Night Type dropdown (showPNDetail's pnd-type select)
    // never correctly pre-selected the saved type either, since it read
    // pn.parade_type from this same mapped object where that key was never
    // actually populated.
    notes:pn.notes||'', parade_type:pn.parade_type||'normal',
    timing_template_id:pn.timing_template_id||null, timing_template_name:pn.timing_template_name||null,
    published:!!pn.published_status, closeout:pn.closeout_status,
    readiness:pn.readiness_score, version:pn.version,
    sessions:(pn.sessions||[]).sort((a,b)=>(a.period_number||0)-(b.period_number||0)).map(s=>({
      id:s.id, phase:s.phase_at_time||'', element:s.element_at_time||'', code:s.curriculum_code_at_time||'',
      timingBlockId:s.timing_block_id||null,   // TB-1: which printed-program period this session sits in
      exp:s.curriculum_title_at_time||s.custom_title||'', facId:s.facilitator_id||'',
      facName:_facName(s), room:s.training_area_name_at_time||'', status:s.status||'planned',
      period_number:s.period_number||1,
      // §10: 0..N assistant facilitators; user_id here is Facilitator.id (see _resolve_assistants)
      assistant_facilitators:s.assistant_facilitators||[],
      // CLASS-06: which Training Class(es) this session targets (CLASS-03's
      // audience linkage, GET /api/parade-nights's own additive field).
      trainingClasses:s.training_classes||[]
    }))
  }));
  const _parseAreas=a=>{if(!a)return[];if(Array.isArray(a))return a;if(typeof a==='string'){try{const r=JSON.parse(a);return Array.isArray(r)?r:[];}catch(_){return[];}}return[];};
  S.facs=(facs||[]).map(f=>({id:f.facilitator_id,rank:f.current_rank||'',first:f.first_name||'',last:f.last_name||'',type:f.type||'',areas:_parseAreas(f.subject_areas),leave:(f.upcoming_leave||[])}));
  S.curr=((cur&&cur.items)||[]).map(_mapCurrItem);
  // Governed phase catalogue (master transformation plan Block 10) — falls
  // back to the 8 built-in names if the endpoint is unreachable, same
  // fallback _populateCurrPhases() uses for the curriculum-item form.
  S.phases=(Array.isArray(phases)&&phases.length)?phases.map(p=>({name:p.name,displayName:p.display_name})):
    ['A. Orientation','B. Initial','C. Junior','D. Intermediate','E. Senior','I. Bronze','J. Silver','K. Gold'].map(n=>({name:n,displayName:n}));
  // Appended, not merged: S.phases feeds the SESSION phase pickers only, where the
  // value is a name string stored as Session.phase_at_time. The Training Class and
  // curriculum-item pickers call /api/curriculum/phases directly and are untouched.
  const _cph=await p_customph.catch(()=>[]);
  if(Array.isArray(_cph)&&_cph.length){
    S.customPhases=_cph.map(c=>({name:c.name,displayName:c.name+' (custom)'}));
    S.phases=S.phases.concat(S.customPhases);
  }else{ S.customPhases=[]; }
  // `capabilities` comes from REM-23 (Training Area Capability reference data) on
  // main; kept alongside the custom-phase load, which touches a different key.
  S.rooms=(ta||[]).map(r=>({id:r.training_area_id||r.id,name:r.name,capacity:r.capacity,type:r.type,notes:r.notes||'',capabilities:r.capabilities||[]}));
  S.equip=(eq||[]).map(x=>({id:x.equipment_id||x.id,name:x.name,qty:x.quantity||x.qty,notes:x.notes||''}));
  S.actionItems=(ai||[]).map(a=>({id:a.action_id,title:a.title,description:a.description,owner:a.owner,due:a.due_date,status:a.status,severity:a.severity,source:a.source}));
  // REM-13: scope_type=squadron responses are {items:[...]}; the legacy
  // no-scope-type fallback (only reached if _sqnId is unset) is a bare array.
  const _actsList=Array.isArray(acts)?acts:((acts&&acts.items)||[]);
  // REM-103: owningLevel/isInherited/localOverride/readOnly only ever come
  // from real Activity rows (_activity_out()) -- CEA/holiday synthetic items
  // (source:'cea'/'holiday') never carry them, correctly leaving these
  // undefined/false for those rows.
  S.acts=_actsList.map(a=>({id:a.activity_id,name:a.activity_name,date:a.date_start,dateEnd:a.date_end,timeStart:a.time_start,timeEnd:a.time_end,type:a.activity_type||'Optional',location:a.location||'',audience:a.audience||[],notes:a.notes||'',ceaSeqNr:a.cea_seq_nr||'',owningOrgLabel:a.owning_org_label||'',owningLevel:a.owning_level||null,isInherited:!!a.is_inherited,localOverride:a.local_override||null}));
  S.holidays=(holidays||[]).map(h=>({id:h.holiday_id,name:h.name,start:h.start_date,end:h.end_date}));
  S.proxy=proxy||{active:false};
  S.pwUrl=(uicfg&&uicfg.planning_workspace_url)||null;
  S.trainingYear=(uicfg&&uicfg.training_year)||new Date().getFullYear();
  S.subjectAreaTags=Array.isArray(tags)?tags.filter(t=>t.is_active):[];
  S.facilitatorTypeTags=Array.isArray(factypes)?factypes.filter(t=>t.is_active):[];
  _populateFacTypeSelect();
  S.sessionStatusReasonTags=Array.isArray(reasontags)?reasontags.filter(t=>t.is_active):[];
  _populateReasonSelect();
  S.activityTypeTags=Array.isArray(acttypes)?acttypes.filter(t=>t.is_active):[];
  _populateActivityTypeSelects();
  S.trainingAreaCapabilityTags=Array.isArray(captags)?captags.filter(t=>t.is_active):[];
  S.reports={summary:repSum,readiness:repRead,coverage:repCov,facload:repFload,notdelivered:repNdel};
  S.cfg={day:'',start:'',end:'',sess:3,dur:35,addr:'',crestUrl:''};
  if(sqnData){
    S.cfg={day:sqnData.default_parade_day||'',start:sqnData.default_start_time||'',end:sqnData.default_end_time||'',sess:sqnData.default_session_count||3,dur:35,addr:sqnData.address||'',crestUrl:sqnData.crest_url||'',unitType:sqnData.unit_type||'standard_squadron'};
    S.currentSqnId=sqnData.squadron_id;
  }
  S.timingTemplates=timing||[];
  S.audit=auditData||[];
  if(scope==='squadron'){
    S.squadrons=wsqns||[];
  }
  if(scope==='wing'){
    S.wing={squadrons:(wov&&wov.squadrons)||[]};
    S.wingPhase=wph||null;
    S.cap=wcap||null;
    S.wingCancel=wcancel||null;
    S.wingNdel=wndel||null;
    S.squadrons=wsqns||[];
  }
  if(scope==='national'||scope==='system_admin'){
    S.national=nat||null;
    S.nationalReport={wings:(natov&&natov.wings)||[]};
    S.natCap=natcap||null;
    S.wings=wings||[];
    S.squadrons=nsqns||[];
  }
  if(S._loadFailures&&S._loadFailures.length){
    showToast('Some information could not load. Refresh the page to try again. If the problem continues, contact your administrator.',true);
  }
  S._loadedAt=Date.now();
}
// Writes now go to the backend then re-load. save() is retained as a no-op so existing
// handlers that call it do not break; real persistence happens via the API helpers below.
function save(){ /* no-op: backend is the source of truth */ }
function reloadAndRender(){
  const run=_reloadRenderPromise.then(async()=>{
    try{ await loadData(); renderAll(); }
    catch(e){ showToast(apiErr(e),true); }
  });
  _reloadRenderPromise=run.catch(()=>{});
  return run;
}

// Backend write helpers (used by the wired handlers).
async function apiSetSessionStatus(sessionId, status, reason){
  // Field name must be "reason" — StatusIn (backend/app/routers/training.py) has no
  // "not_delivered_reason" key, so sending that silently dropped the reason and made
  // every not_delivered quick-action 400 with reason_required_not_delivered.
  return api('/api/sessions/'+sessionId+'/status',{method:'POST',body:JSON.stringify({status, reason:reason||null})});
}

// ── Statuses that require a reason before saving, and their user-facing context text ──
const OUTCOME_REASON_REQUIRED={
  not_delivered:'This session was not delivered.',
  cancelled:'This session is being cancelled.',
  cancelled_late:'This session is being cancelled.',
  delivered_with_issue:'This session was delivered, but with an issue to record.'
};
let _orResolve=null;
// REM-23 continuation: #or-reason is now API-driven from
// Activity Type dropdowns (#act-type, #ga-type) — REM-23 part 3.
// Replaces hardcoded Must Attend/Key Event/Optional <option> list with
// API-governed tags. "+" Add new affordance for admins, same as #fac-type.
function _populateActivityTypeSelects(){
  const tags=(S.activityTypeTags||[]);
  const opts=tags.length
    ? tags.map(t=>`<option value="${esc(t.display_name)}">${esc(t.display_name)}</option>`).join('')
    : ['Must Attend','Key Event','Optional'].map(n=>`<option value="${esc(n)}">${esc(n)}</option>`).join('');
  const addOpt=canWriteSquadron()?'<option value="__add_new__">+ Add new type…</option>':'';
  ['act-type','ga-type'].forEach(id=>{
    const sel=document.getElementById(id); if(!sel)return;
    const prior=sel.value;
    sel.innerHTML=opts+addOpt;
    if(prior && [...sel.options].some(o=>o.value===prior)) sel.value=prior;
    else if(tags.length) sel.value=tags.find(t=>t.normalised_name==='optional')?.display_name||tags[0].display_name;
    else sel.value='Optional';
  });
}
async function _onActivityTypeChange(sel){
  if(sel.value!=='__add_new__')return;
  const name=await promptText('New activity type','Type name',{okLabel:'Create'});
  if(!name){ sel.value=S.activityTypeTags[0]?.display_name||'Optional'; return; }
  try{
    const t=await api('/api/activity-type-tags',{method:'POST',body:JSON.stringify({display_name:name})});
    S.activityTypeTags=[...(S.activityTypeTags||[]),t];
    _populateActivityTypeSelects();
    ['act-type','ga-type'].forEach(id=>{const s=document.getElementById(id);if(s)s.value=t.display_name;});
    showToast('Type "'+t.display_name+'" created.');
  }catch(e){
    showToast(e.code==='tag_already_exists'?'That type already exists.':'Could not create type: '+apiErr(e),true);
    sel.value=S.activityTypeTags[0]?.display_name||'Optional';
  }
}

// /api/session-status-reason-tags (same governed reference-data pattern as
// #fac-type/Facilitator Type) instead of a hardcoded <option> list. "Other"
// is always appended and is deliberately NOT part of the governed tag set
// -- a genuine non-governed catch-all, matching how Facilitator Type has
// no equivalent "Other" entry.
function _populateReasonSelect(){
  const sel=document.getElementById('or-reason'); if(!sel)return;
  const prior=sel.value;
  const tags=(S.sessionStatusReasonTags||[]);
  const opts=tags.length
    ? tags.map(t=>`<option value="${esc(t.display_name)}">${esc(t.display_name)}</option>`).join('')
    : ['Facilitator unavailable','Venue unavailable','Equipment unavailable','Weather','Insufficient numbers','Higher-priority activity','Program changed','Time lost','Safety concern','Administrative requirement']
        .map(n=>`<option value="${esc(n)}">${esc(n)}</option>`).join('');
  const addOpt=canWriteSquadron()?'<option value="__add_new__">+ Add new reason…</option>':'';
  sel.innerHTML='<option value="">— Select a reason —</option>'+opts+'<option value="Other">Other</option>'+addOpt;
  if(prior && [...sel.options].some(o=>o.value===prior)) sel.value=prior;
}
async function _onReasonChange(sel){
  if(sel.value!=='__add_new__')return;
  const name=await promptText('New reason','Reason name',{okLabel:'Create'});
  // Clear '__add_new__' before the API await so that when closeModal's deferred
  // el.focus() fires (setTimeout(0), after this microtask yields), sel.value is
  // already '' and any WebKit spurious 'change' event returns early here instead
  // of reopening #m-text-input.
  sel.value='';
  if(!name){ return; }
  try{
    const t=await api('/api/session-status-reason-tags',{method:'POST',body:JSON.stringify({display_name:name})});
    S.sessionStatusReasonTags=[...(S.sessionStatusReasonTags||[]),t];
    _populateReasonSelect();
    sel.value=t.display_name;
    showToast('Reason "'+t.display_name+'" created.');
  }catch(e){
    showToast(e.code==='tag_already_exists'?'That reason already exists.':'Could not create reason: '+apiErr(e), true);
    sel.value='';
  }
}
function collectOutcomeReason(status){
  return new Promise(resolve=>{
    _orResolve=resolve;
    document.getElementById('or-context').textContent=OUTCOME_REASON_REQUIRED[status]||'Enter a reason.';
    _populateReasonSelect();
    document.getElementById('or-reason').value='';
    document.getElementById('or-note').value='';
    document.getElementById('or-err').textContent='';
    openModal('m-outcome-reason');
    setTimeout(()=>document.getElementById('or-reason').focus(),30);
  });
}
function _orSave(){
  const reason=document.getElementById('or-reason').value;
  const note=document.getElementById('or-note').value.trim();
  if(!reason||reason==='__add_new__'){ document.getElementById('or-err').textContent='Select a reason to continue.'; return; }
  closeModal('m-outcome-reason');
  const full=note?reason+' — '+note:reason;
  if(_orResolve)_orResolve(full);
  _orResolve=null;
}
function _orCancel(){
  closeModal('m-outcome-reason');
  if(_orResolve)_orResolve(null);
  _orResolve=null;
}
async function apiPublishPN(pnId){ return api('/api/parade-nights/'+pnId+'/publish',{method:'POST'}); }
async function apiClosePN(pnId){ return api('/api/parade-nights/'+pnId+'/close',{method:'POST'}); }
async function apiAddActionItem(payload){ return api('/api/action-items',{method:'POST',body:JSON.stringify(payload)}); }
async function apiCloseActionItem(id){ return api('/api/action-items/'+id+'/close',{method:'POST'}); }
async function apiEnterProxy(sqnId, reason){ return api('/api/proxy/enter/'+sqnId,{method:'POST',body:JSON.stringify({reason})}); }
async function apiExitProxy(){ return api('/api/proxy/exit',{method:'POST'}); }

function key(k){return 'aafc_'+S.sqn+'_'+k;} // retained for any stray reference; no longer used for storage
function allCurr(){return S.curr||[];}
// REM-133: shared field mapping from the raw /api/curriculum response shape --
// used both for the normal (active-only) load and the archived-list fetch, so
// the two never drift apart the way S.facs/archived-facilitator mapping once did.
function _mapCurrItem(i){
  return {id:i.curriculum_id,code:i.code,identifier:i.identifier,partNumber:i.part_number,title:i.title,phase:i.phase,el:i.element,term:i.recommended_term,hours:Math.round((i.duration_minutes||0)/60),type:i.core_status,lh:i.learning_hub_url,progress:i.progress,sessions:i.session_count,owningLevel:i.owning_level,wingId:i.wing_id,owned:i.owning_level==='squadron',isArchived:!!i.is_archived};
}
function facById(id){return (S.facs||[]).find(f=>f.id===id);}
function facDisplay(f){if(!f)return '—';return [f.rank,f.first,f.last].filter(Boolean).join(' ');}
function roomById(id){return (S.rooms||[]).find(r=>r.id===id);}
