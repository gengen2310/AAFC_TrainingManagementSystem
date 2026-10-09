// Main TMS module: authentication, session restore and scope presentation --
// two-step sign-in, account recovery, the display-only scope/permission model,
// the System Administrator scope selector and proxy/intervention mode.
// Extracted verbatim from connected-frontend/index.html (stabilisation Phase 4,
// C6). Top-level function declarations and side-effect-free let/const only;
// loaded as a classic script BEFORE the inline bootstrap, so everything here
// is defined before any page-load code runs. Statements with load-time
// effects stay in index.html in their original order. Parity is proven by
// tools/architecture/frontend_parity.mjs.

// ═══════════════════════════════════════════════════════════
//  AUTH  (two-step: identify account → enter access code)
//  No access codes or hashes are stored in the browser.
// ═══════════════════════════════════════════════════════════
let _authUserId=null;
let _aafcOrgs=null;   // [{code, name, squadrons:[{code,name,unit_type}]}]
let _authSqnName='';  // display name of the selected squadron/unit

const _AUTH_ROLES={
  squadron:[{v:'sqn_admin',l:'Admin'},{v:'sqn_general',l:'Viewer'}],
  wing:    [{v:'wing_admin',l:'Admin'},{v:'wing_viewer',l:'Viewer'}],
  national:[{v:'national_admin',l:'National Admin'},{v:'national_viewer',l:'National Viewer'},
            {v:'system_admin',l:'System Admin'},{v:'auditor',l:'Auditor'}],
};
// _ROLE_LABELS is defined later (global); use the global for the auth banner

async function _loadOrgs(){
  if(_aafcOrgs) return _aafcOrgs;
  try{ _aafcOrgs=(await api('/api/auth/organisations')).wings||[]; }
  catch(e){ _aafcOrgs=[]; }
  return _aafcOrgs;
}

function _populateWingSelect(type){
  const sel=document.getElementById('auth-wing-select');
  const orgs=_aafcOrgs||[];
  sel.innerHTML='<option value="">Select wing…</option>';
  // For wing-type login, only show wings that have squadrons? No — show all wings.
  orgs.forEach(w=>{
    const opt=document.createElement('option');
    opt.value=w.code;
    opt.textContent=w.name;
    sel.appendChild(opt);
  });
}

function onAuthWingChange(){
  const type=document.getElementById('auth-type').value;
  const wingCode=document.getElementById('auth-wing-select').value;
  const sqnWrap=document.getElementById('auth-sqn-wrap');
  const sqnSel=document.getElementById('auth-sqn-select');
  const identEl=document.getElementById('auth-ident');
  // For wing-type login the wing code IS the identifier
  if(type==='wing'){ identEl.value=wingCode; onAuthFieldChange(); return; }
  // Squadron type: populate squadron dropdown
  sqnSel.innerHTML='<option value="">Select squadron…</option>';
  identEl.value='';
  _authSqnName='';
  if(!wingCode){ sqnWrap.style.display='none'; onAuthFieldChange(); return; }
  const orgs=_aafcOrgs||[];
  const wing=orgs.find(w=>w.code===wingCode);
  const sqns=wing?wing.squadrons:[];
  if(sqns.length===0){
    const opt=document.createElement('option');
    opt.value=''; opt.disabled=true;
    opt.textContent='No squadrons configured for this wing yet';
    sqnSel.appendChild(opt);
  } else {
    sqns.forEach(s=>{
      const opt=document.createElement('option');
      opt.value=s.code;
      opt.textContent=s.name;
      sqnSel.appendChild(opt);
    });
  }
  sqnWrap.style.display='';
  onAuthFieldChange();
}

async function onAuthTypeChange(){
  const type=document.getElementById('auth-type').value;
  const wingWrap=document.getElementById('auth-wing-wrap');
  const sqnWrap=document.getElementById('auth-sqn-wrap');
  const identEl=document.getElementById('auth-ident');
  const roleWrap=document.getElementById('auth-role-wrap');
  const roleEl=document.getElementById('auth-role');
  document.getElementById('auth-err').style.display='none';
  // Reset downstream selectors
  document.getElementById('auth-wing-select').innerHTML='<option value="">Select wing…</option>';
  document.getElementById('auth-sqn-select').innerHTML='<option value="">Select squadron…</option>';
  identEl.value=''; _authSqnName='';
  roleEl.innerHTML='<option value="">Select…</option>';
  (_AUTH_ROLES[type]||[]).forEach(o=>{const opt=document.createElement('option');opt.value=o.v;opt.textContent=o.l;roleEl.appendChild(opt);});
  roleWrap.style.display=type?'':'none';
  if(type==='squadron'||type==='wing'){
    wingWrap.style.display='';
    sqnWrap.style.display='none';
    // Load org list if not cached yet
    await _loadOrgs();
    _populateWingSelect(type);
  } else {
    wingWrap.style.display='none';
    sqnWrap.style.display='none';
  }
  onAuthFieldChange();
}

function onAuthFieldChange(){
  const type=document.getElementById('auth-type').value;
  const ident=document.getElementById('auth-ident').value.trim();
  const role=document.getElementById('auth-role').value;
  const needsIdent=(type==='squadron'||type==='wing');
  // For squadron type also require a squadron selection
  const sqnOk=(type!=='squadron')||!!document.getElementById('auth-sqn-select').value;
  document.getElementById('auth-continue-btn').disabled=!(type&&role&&(!needsIdent||ident)&&sqnOk);
  // Track selected squadron name for better error messages
  if(type==='squadron'){
    const sqnSel=document.getElementById('auth-sqn-select');
    const sel=sqnSel.options[sqnSel.selectedIndex];
    _authSqnName=(sel&&sel.value)?sel.textContent:'';
    // Set identifier from squadron dropdown
    document.getElementById('auth-ident').value=sqnSel.value;
  }
}

async function doLookup(){
  const type=document.getElementById('auth-type').value;
  const ident=document.getElementById('auth-ident').value.trim();
  const role=document.getElementById('auth-role').value;
  const err=document.getElementById('auth-err');
  const btn=document.getElementById('auth-continue-btn');
  const prog=document.getElementById('auth-progress1');
  const bar=document.getElementById('auth-bar1');
  err.style.display='none';
  btn.disabled=true; btn.textContent='Looking up…';
  prog.style.display='block'; bar.style.width='60%';
  function _resetContinue(){prog.style.display='none';bar.style.width='0%';btn.disabled=false;btn.textContent='Next';}
  try{
    const body={unit_type:type,role};
    if(type!=='national') body.identifier=ident;
    const r=await api('/api/auth/lookup',{method:'POST',body:JSON.stringify(body)});
    _authUserId=r.user_id;
    let unitLabel;
    if(type==='squadron') unitLabel=_authSqnName||ident;
    else if(type==='wing'){
      const orgs=_aafcOrgs||[];
      const w=orgs.find(x=>x.code===ident);
      unitLabel=w?w.name:ident+' Wing';
    } else { unitLabel='National / System'; }
    document.getElementById('auth-acct-banner').textContent=unitLabel+' — '+(_ROLE_LABELS[role]||role);
    bar.style.width='100%';
    document.getElementById('auth-step1').style.display='none';
    document.getElementById('auth-step2').style.display='';
    document.getElementById('auth-code').value='';
    document.getElementById('auth-code').focus();
  }catch(e){
    _resetContinue();
    err.style.display='block';
    if(e.status===404){
      const unitName=_authSqnName||ident;
      err.textContent=unitName
        ?'No account exists for '+unitName+' yet. Contact the system administrator to create one.'
        :'No account found for that selection.';
    } else { err.textContent=apiErr(e); }
  }
}

// ── Account recovery ────────────────────────────────────────────────────────
// The backend answers forgot-code identically whatever happened, so this UI must
// too: it never reports whether an account matched, and it shows the same
// message on success and on failure. Saying "no account with that address" here
// would undo the enumeration resistance the endpoint is built around.
function _authPanels(show){
  ['auth-step1','auth-step2','auth-forgot','auth-reset'].forEach(function(id){
    const el=document.getElementById(id);
    if(el) el.style.display = (id===show) ? '' : 'none';
  });
  const err=document.getElementById('auth-err');
  if(err) err.style.display='none';
}

function showForgotCode(){
  _authPanels('auth-forgot');
  const n=document.getElementById('forgot-note'); if(n) n.textContent='';
  const f=document.getElementById('forgot-email'); if(f) f.focus();
}

function showAuthStep2(){ _authPanels('auth-step2'); }

async function doForgotCode(){
  const btn=document.getElementById('forgot-btn');
  const note=document.getElementById('forgot-note');
  const email=(document.getElementById('forgot-email')||{}).value||'';
  btn.disabled=true; btn.textContent='Sending…';
  try{
    await api('/api/auth/forgot-code',{method:'POST',body:{email:email.trim()}});
  }catch(_){ /* deliberately ignored: the outcome must not vary */ }
  btn.disabled=false; btn.textContent='Send recovery email';
  note.textContent='If an eligible account matches those details, recovery '
    + 'instructions have been sent. Check your email, then enter the recovery '
    + 'code below.';
  setTimeout(function(){
    _authPanels('auth-reset');
    const t=document.getElementById('reset-token'); if(t) t.focus();
  }, 2200);
}

// Named doRecoveryReset, not doResetCode: a doResetCode already exists further
// down this file for the admin "reset access code" modal. Function declarations
// hoist, so the later one silently won and this handler never ran -- the button
// did nothing and reported nothing.
async function doRecoveryReset(){
  const btn=document.getElementById('reset-btn');
  const note=document.getElementById('reset-note');
  const token=(document.getElementById('reset-token')||{}).value||'';
  const code=(document.getElementById('reset-new')||{}).value||'';
  if(code.trim().length<8){
    note.textContent='An access code must be at least 8 characters.';
    return;
  }
  btn.disabled=true; btn.textContent='Saving…';
  try{
    await api('/api/auth/reset-code',{method:'POST',
      body:{token:token.trim(),new_code:code.trim()}});
    note.textContent='Your access code has been changed. Sign in with it now.';
    setTimeout(function(){ _authPanels('auth-step2'); }, 1800);
  }catch(e){
    // One message for expired, consumed and unknown alike -- the backend does
    // not distinguish them and neither should this.
    note.textContent='That recovery code is not valid. Request a new one.';
  }
  btn.disabled=false; btn.textContent='Set new access code';
}

function showAuthStep1(){
  _authUserId=null; _authSqnName='';
  document.getElementById('auth-step2').style.display='none';
  document.getElementById('auth-step1').style.display='';
  document.getElementById('auth-err').style.display='none';
  document.getElementById('auth-code').value='';
  const btn=document.getElementById('auth-continue-btn');
  btn.disabled=false; btn.textContent='Next';
  document.getElementById('auth-progress1').style.display='none';
  document.getElementById('auth-bar1').style.width='0%';
  onAuthFieldChange();
}

async function completeRequiredCodeChange(session,currentCode){
  document.getElementById('auth-screen').style.display='none';
  document.getElementById('app').style.display='block';
  const next=await promptText(
    'Change temporary access code',
    'New access code',
    {
      context:'This is an initial or administrator-issued code. Choose your own access code before continuing.',
      okLabel:'Change access code',
      validate:(v)=>v.length<6?'Use at least 6 characters.':null,
    }
  );
  if(!next){
    await doLogout();
    return false;
  }
  try{
    await api('/api/auth/change-code',{
      method:'POST',
      body:{user_id:session.user_id,new_code:next,current_code:currentCode},
    });
    tokenClear();
    document.getElementById('app').style.display='none';
    document.getElementById('auth-screen').style.display='flex';
    _authPanels('auth-step2');
    document.getElementById('auth-code').value='';
    const err=document.getElementById('auth-err');
    err.style.display='block';
    err.textContent='Access code changed. Sign in again with your new code.';
    document.getElementById('auth-code').focus();
    return false;
  }catch(e){
    showToast(apiErr(e),true);
    await doLogout();
    return false;
  }
}

async function doLogin(){
  const code=document.getElementById('auth-code').value.trim();
  const err=document.getElementById('auth-err');
  const btn=document.getElementById('auth-btn');
  const prog=document.getElementById('auth-progress');
  const bar=document.getElementById('auth-progress-bar');

  err.style.display='none';
  if(!code){err.style.display='block';err.textContent='Enter your access code.';return;}

  btn.disabled=true; btn.textContent='Signing in…';
  prog.style.display='block'; bar.style.width='0%';
  let pct=0;
  const tick=setInterval(()=>{ pct=Math.min(pct+5,75); bar.style.width=pct+'%'; },100);

  function _resetForm(){
    clearInterval(tick);
    bar.style.width='0%'; prog.style.display='none';
    btn.disabled=false; btn.textContent='Sign In';
  }

  try{
    const out=await api('/api/auth/login',{method:'POST',body:JSON.stringify({user_id:_authUserId,code})});
    clearInterval(tick); bar.style.width='100%';
    tokenSet(out.token);
    S.session=out.session;
    applySession(out.session);
    if(out.session&&out.session.must_change_code){
      await completeRequiredCodeChange(out.session,code);
      return;
    }
    await loadData();
    bootApp();
  }catch(e){
    _resetForm();
    err.style.display='block';
    if(e.status===401){
      if(e.code==='invalid_user')
        err.textContent='Your account has been deactivated. Contact your Wing HQ.';
      else
        err.textContent='Incorrect access code. Check your code and try again.';
    }else if(e.status===429){
      err.textContent=e.msg||'Too many incorrect attempts. Access is temporarily locked.';
    }else{
      err.textContent=apiErr(e);
    }
  }
}
async function doLogout(){
  try{ await api('/api/auth/logout',{method:'POST'}); }catch(_){}
  tokenClear();
  S={sqn:null,isAdmin:false,isWing:false,session:null,pns:[],facs:[],acts:[],rooms:[],equip:[],cfg:{},curr:[],reports:{}};
  showAuthStep1();
  document.getElementById('auth-screen').style.display='flex';
  document.getElementById('app').style.display='none';
}

// Restore an existing session on page load/refresh instead of always dropping
// back to the login screen. A sessionStorage token surviving a refresh is the
// normal case; only a genuinely invalid/expired session (401) or an explicit
// "give up" after retry should ever show the login form again -- a transient
// network blip surfaces a Retry action instead (api()'s own GET-retry logic
// already absorbs the sub-second single-replica-redeploy gap before this
// ever runs).
async function tryRestoreSession(){
  const restoring=document.getElementById('auth-restoring');
  if(!tokenGet()){
    restoring.style.display='none';
    showAuthStep1();
    return;
  }
  try{
    const out=await api('/api/auth/me');
    S.session=out.session;
    applySession(out.session);
    if(out.session&&out.session.must_change_code){
      // A restored JWT is not enough to rotate credentials. The user must
      // re-enter the temporary/current access code so the change-code endpoint
      // can re-authenticate the credential itself.
      tokenClear();
      restoring.style.display='none';
      showAuthStep1();
      const err=document.getElementById('auth-err');
      err.style.display='block';
      err.textContent='Sign in again with your current access code to complete the required code change.';
      return;
    }
    await loadData();
    bootApp();
  }catch(e){
    if(e && e.kind==='network'){
      restoring.innerHTML='<div style="text-align:center;padding:18px 0">'
        +'<div class="sc-status-err" style="margin-bottom:10px">'+esc(apiErr(e))+'</div>'
        +'<button class="btn-auth" onclick="tryRestoreSession()">Retry</button></div>';
      return;
    }
    tokenClear();
    restoring.style.display='none';
    showAuthStep1();
  }
}
// Map the backend session to the UI's scope/role flags. Backend remains the security boundary.
function applySession(sess){
  S.session=sess;
  S.role=sess.role;
  S.isAdmin=['sqn_admin','wing_admin','national_admin','system_admin'].includes(sess.role);
  S.isWing=!!sess.is_wing;
  S.isNational=!!sess.is_national;
  S.isAuditor=sess.role==='auditor';
  S.sqn=sess.squadron_id||sess.wing_id||sess.national_id||'unit';
  S.scopeName=sess.display_name||(sess.is_national?'National HQ':sess.is_wing?'Wing HQ':'Squadron');
}

// ═══════════════════════════════════════════════════════════
//  SCOPE & PERMISSION MODEL  (display/UI only — the backend enforces every write)
// ═══════════════════════════════════════════════════════════
// Returns 'squadron' | 'wing' | 'national' | 'auditor'. National HQ is never a squadron.
function getScopeType(){
  if(!S.session)return 'squadron';
  if(S.session.role==='system_admin')return 'system_admin';
  if(S.session.role==='auditor')return 'auditor';
  if(S.session.is_national)return 'national';
  if(S.session.is_wing)return 'wing';
  return 'squadron';
}
// S.cfg (from backend) takes precedence over SQN_DATA for operational time fields.
// SQN_DATA provides display name/short and acts as fallback when S.cfg is unpopulated.
function getCurrentUnitInfo(){
  const meta=(typeof SQN_DATA!=='undefined'&&S.sqn)?SQN_DATA[S.sqn]:null;
  const sc=getScopeType();
  const short=meta?meta.short:sc==='national'?'NAT HQ':sc==='wing'?'WING':sc==='auditor'?'AUDIT':sc==='system_admin'?'SYS':'SQN';
  const name=meta?meta.name:S.scopeName||(S.session&&S.session.display_name)||
    (sc==='national'?'National HQ':sc==='wing'?'Wing HQ':sc==='auditor'?'Auditor (Read Only)':sc==='system_admin'?'System Admin':'AAFC Training System');
  const day=(S.cfg&&S.cfg.day)||(meta&&meta.day)||'';
  const start=(S.cfg&&S.cfg.start)||(meta&&meta.start)||'';
  const end=(S.cfg&&S.cfg.end)||(meta&&meta.end)||'';
  const sess=(S.cfg&&S.cfg.sess)||(meta&&meta.sess)||'';
  const addr=(S.cfg&&S.cfg.addr)||(meta&&meta.addr)||'';
  return {name, short, addr, day, start, end, sess};
}
function canRead(){ return !!S.session; }
function isReadOnly(){ const r=S.role; return S.isAuditor || r==='wing_viewer' || r==='national_viewer' || r==='sqn_general'; }
// Write capability is advisory for showing/hiding controls; the API is the real boundary.
function canWriteSquadron(){
  const r=S.role;
  if(r==='sqn_admin')return true;                          // own squadron
  if((r==='wing_admin')&&proxyActive())return true;        // via Proxy Mode
  if((r==='national_admin'||r==='system_admin')&&proxyActive())return true; // via Delegated Intervention
  return false;
}
function canWriteWing(){ return ['national_admin','system_admin'].includes(S.role); }
function canWriteNational(){ return ['national_admin','system_admin'].includes(S.role); }
// Planning-level write: sqn_admin + wing_admin can edit parade dates / holidays / planning years
// without needing proxy mode (they are managing their own unit's calendar, not squadron records).
function canWritePlan(){
  if(isReadOnly()) return false;
  const r=S.role||'';
  if(r==='wing_admin') return true;
  return canWriteSquadron();
}
function proxyActive(){ return !!(S.proxy && S.proxy.active); }
function proxyMode(){ return (S.proxy && S.proxy.mode) || null; } // 'proxy' | 'delegated_intervention'
// Wing admins must enter Proxy Mode before squadron writes; National admins use Delegated Intervention.
function isProxyRequired(){ return S.role==='wing_admin' && !proxyActive(); }
function isInterventionRequired(){ return ['national_admin','system_admin'].includes(S.role) && !proxyActive(); }

// ── System Administrator scope selector ──────────────────────────────────
function saBrowseWingId(){ return (S.role==='system_admin'&&S.saScope&&(S.saScope.level==='wing'||S.saScope.level==='squadron'))?S.saScope.wingId:null; }
function saBrowseSquadronId(){ return (S.role==='system_admin'&&S.saScope&&S.saScope.level==='squadron')?S.saScope.squadronId:null; }

function saRenderScopeBar(){
  const bar=document.getElementById('sa-scope-bar'); if(!bar)return;
  if(S.role!=='system_admin'){ bar.style.display='none'; return; }
  bar.style.display='flex';
  if(!S.saScope)S.saScope={level:'national',wingId:null,squadronId:null};
  const wingSel=document.getElementById('sa-scope-wing'), sqnSel=document.getElementById('sa-scope-sqn'),
        diBtn=document.getElementById('sa-scope-di-btn'), hint=document.getElementById('sa-scope-hint');
  // Populate Wing dropdown from the cached org list (kept fresh by _refreshOrgCache()).
  const curWing=S.saScope.wingId||'';
  wingSel.innerHTML='<option value="">National (all Wings)</option>'+
    (S.wings||[]).map(w=>`<option value="${w.wing_id}"${w.wing_id===curWing?' selected':''}>${esc(w.code||w.name)} — ${esc(w.name)}</option>`).join('');
  if(S.saScope.level==='national'){
    sqnSel.style.display='none'; diBtn.style.display='none';
    hint.textContent='Read-only National overview.';
  } else {
    sqnSel.style.display='';
    const curSqn=S.saScope.squadronId||'';
    const sqnsInWing=(S.squadrons||[]).filter(s=>s.wing_id===S.saScope.wingId);
    sqnSel.innerHTML='<option value="">Wing overview (all units)</option>'+
      sqnsInWing.map(s=>`<option value="${s.squadron_id}"${s.squadron_id===curSqn?' selected':''}>${esc(s.code||s.name)} — ${esc(s.name)}</option>`).join('');
    if(S.saScope.level==='squadron'){
      diBtn.style.display=proxyActive()?'none':'';
      hint.textContent=proxyActive()?'Delegated Intervention active — writes enabled.':'Read-only. Enter Intervention Mode to make changes.';
    } else {
      diBtn.style.display='none';
      hint.textContent='Read-only Wing overview. Select a unit to view its operational pages.';
    }
  }
}

async function saSelectWing(wingId){
  if(proxyActive())await exitMode();
  S.saScope={level:wingId?'wing':'national',wingId:wingId||null,squadronId:null};
  try{ await loadData(); }catch(e){ showToast(apiErr(e),true); }
  updateScopeBanner(); updateModeBanner(); updateDebugBar(); bootApp();
}

async function saSelectSquadron(sqnId){
  if(proxyActive())await exitMode();
  S.saScope.level=sqnId?'squadron':'wing';
  S.saScope.squadronId=sqnId||null;
  try{ await loadData(); }catch(e){ showToast(apiErr(e),true); }
  updateScopeBanner(); updateModeBanner(); updateDebugBar(); bootApp();
}

function saEnterIntervention(){
  const sqnId=S.saScope&&S.saScope.squadronId; if(!sqnId)return;
  const sqn=(S.squadrons||[]).find(s=>s.squadron_id===sqnId);
  enterMode(sqnId, sqn?(sqn.short_name||sqn.code):sqnId);
}

function applyNavScope(){
  const scope=effectiveScope();
  const allowed=new Set(NAV_BY_SCOPE[scope]||NAV_BY_SCOPE.squadron);
  const settingsPage=document.getElementById('page-settings');
  document.querySelectorAll('.nav-item').forEach(n=>{
    const m=(n.getAttribute('onclick')||'').match(/nav\('([^']+)'\)/);
    const target=m?m[1]:null;
    let show=target&&allowed.has(target);
    // sqn_general sees Unit Settings read-only (2026-09-28 product decision).
    if(target==='settings')show=show&&['sqn_admin','sqn_general'].includes(S.role);
    // Audit visibility follows the centralized backend policy; wing_viewer
    // remains excluded while squadron roles are scoped to their own audit rows.
    if(target==='audit')show=show&&!['wing_viewer'].includes(S.role);
    if(target==='accounts')show=show&&['sqn_admin','sqn_general','wing_admin','wing_viewer','national_admin','national_viewer','system_admin','auditor'].includes(S.role);
    // system_admin's System Console must stay reachable regardless of which
    // Wing/Squadron it is currently browsing (effectiveScope() may be 'wing'/
    // 'squadron' while browsing, and neither of those NAV_BY_SCOPE lists
    // includes 'system-console' — this is a deliberate widen, not a narrowing
    // override like the others above).
    if(target==='system-console')show=(S.role==='system_admin');
    n.style.display=show?'flex':'none';
    n.setAttribute('tabindex',show?'0':'-1');
  });
  saRenderScopeBar();
  // System Console section label
  const sysLbl=document.getElementById('nav-system-lbl');
  if(sysLbl)sysLbl.style.display=S.role==='system_admin'?'block':'none';
  // Hide section labels whose items are all hidden (covers nav-lbl and nav-planning-hdr).
  document.querySelectorAll('.nav-lbl, .nav-planning-hdr').forEach(lbl=>{
    let el=lbl.nextElementSibling, anyVisible=false;
    while(el && !el.classList.contains('nav-lbl') && !el.classList.contains('nav-planning-hdr')){
      if(el.classList.contains('nav-item') && el.style.display!=='none') anyVisible=true;
      el=el.nextElementSibling;
    }
    lbl.style.display=anyVisible?'block':'none';
  });
}
function updateScopeBanner(){
  const scope=getScopeType(), sb=document.getElementById('scope-banner');
  if(!sb)return;
  sb.className='scope-banner sb-'+scope; sb.style.display='flex';
  const tag={squadron:'SQUADRON',wing:'WING',national:'NATIONAL HQ',auditor:'AUDITOR',system_admin:'SYSTEM'}[scope];
  document.getElementById('sb-tag').textContent=tag||scope.toUpperCase();
  let txt=S.scopeName||'';
  if(scope==='wing')txt=(S.scopeName||'Wing HQ')+' — oversight of '+((S.wing&&S.wing.squadrons.length)||((S.squadrons||[]).length)||'all')+' squadrons';
  else if(scope==='national')txt='National HQ — '+(((S.national&&S.national.wing_count)||((S.wings||[]).length))||'all')+' wings, all squadrons';
  else if(scope==='auditor')txt='Read-only assurance view';
  else if(scope==='system_admin')txt='System Administrator — platform access';
  else txt=S.scopeName||'Squadron';
  document.getElementById('sb-text').textContent=txt;
}

function updateModeBanner(){
  const mb=document.getElementById('mode-banner'); if(!mb)return;
  if(proxyActive()){
    const mode=proxyMode(); const acting=(S.proxy&&S.proxy.acting_squadron_id)||'';
    const sq=(S.squadrons||[]).find(x=>x.squadron_id===acting);
    const where=S.proxyLabel||(sq?(sq.short_name||sq.code):acting.slice(0,8));
    const who=mode==='delegated_intervention'?'NAT HQ':'Wing';
    mb.className='mode-banner show'+(mode==='delegated_intervention'?' intervention':'');
    const label=mode==='delegated_intervention'?'🛠️ Delegated Intervention Mode':'🛡️ Proxy Mode';
    const reason=S.proxyReason?(' · reason: '+S.proxyReason):'';
    document.getElementById('mode-text').textContent=`${label} — ${who} viewing ${where}${reason}`;
  } else { mb.className='mode-banner'; }
}


// ═══ PROXY / DELEGATED INTERVENTION ═══
async function enterMode(squadronId, label){
  const isNat=['national_admin','system_admin'].includes(S.role);
  const what=isNat?'Delegated Intervention':'Proxy Mode';
  const reason=await promptText(`Enter reason — ${what}`,'Reason (required, audited)',{
    context:`Acting on ${label||'this squadron'} requires a reason. It will appear in the audit log.`,
    okLabel:'Enter '+what,
  });
  if(!reason)return;
  S.proxyReason=reason; S.proxyLabel=label||'';
  try{
    await api('/api/proxy/enter/'+squadronId,{method:'POST',body:JSON.stringify({reason})});
    await loadData(); renderAll(); updateScopeBanner(); updateModeBanner(); updateDebugBar(); bootApp();
  }catch(e){ showToast(apiErr(e),true); }
}
async function exitMode(){
  try{ await api('/api/proxy/exit',{method:'POST'}); }catch(e){ showToast(apiErr(e),true); }
  try{ S.proxy=await api('/api/proxy/current'); }catch(_){ S.proxy={active:false}; }
  await loadData(); renderAll(); updateScopeBanner(); updateModeBanner(); updateDebugBar(); bootApp();
}
