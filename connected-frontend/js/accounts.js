// Main TMS module: Account Management -- accounts table, reference data,
// Wings/Units/Flights, create/edit/reset/disable, bulk and organisation archive
// wizards.
// Extracted verbatim from connected-frontend/index.html (stabilisation Phase 4,
// C6). Top-level function declarations and side-effect-free let/const only;
// loaded as a classic script BEFORE the inline bootstrap, so everything here
// is defined before any page-load code runs. Statements with load-time
// effects stay in index.html in their original order. Parity is proven by
// tools/architecture/frontend_parity.mjs.

// ═══════════════════════════════════════════════════════════
//  ACCOUNT MANAGEMENT
// ═══════════════════════════════════════════════════════════
const _ACCT_WRITE_ROLES=['sqn_admin','wing_admin','national_admin','system_admin'];
const _ROLE_LABELS={sqn_general:'SQN General',sqn_admin:'SQN Admin',wing_viewer:'Wing Viewer',wing_admin:'Wing Admin',
  national_viewer:'NAT Viewer',national_admin:'NAT Admin',system_admin:'System Admin',auditor:'Auditor'};
const _ROLE_CLS={sqn_general:'b-blue',sqn_admin:'b-blue',wing_viewer:'b-ok',wing_admin:'b-ok',
  national_viewer:'b-amber',national_admin:'b-amber',system_admin:'b-amber',auditor:'b-grey'};
const _SCOPE_CLS={squadron:'b-blue',wing:'b-ok',national:'b-amber'};
const _SCOPE_LABELS={squadron:'SQN',wing:'Wing',national:'NAT HQ'};

// Mirrors backend _CREATE_AUTHORITY / _scope_type (app/routers/accounts.py) --
// UI convenience only for populating the role picker; the server is always
// the authoritative check on POST /accounts/{id}/change-role.
const _ROLE_ASSIGN_AUTHORITY={
  system_admin:['system_admin','national_admin','national_viewer','wing_admin','wing_viewer','sqn_admin','sqn_general','auditor'],
  national_admin:['national_admin','national_viewer','wing_admin','wing_viewer','sqn_admin','sqn_general','auditor'],
  wing_admin:['wing_viewer','sqn_admin','sqn_general'],
  sqn_admin:['sqn_general'],
};
const _NATIONAL_SCOPE_ROLES=['national_admin','national_viewer','system_admin','auditor'];
const _WING_SCOPE_ROLES=['wing_viewer','wing_admin'];
function _roleScopeType(role){
  if(_NATIONAL_SCOPE_ROLES.includes(role)) return 'national';
  if(_WING_SCOPE_ROLES.includes(role)) return 'wing';
  return 'squadron';
}

function _acctWingChanged(){
  const wingSel=document.getElementById('acct-filter-wing');
  const sqnSel=document.getElementById('acct-filter-sqn');
  if(sqnSel){
    const wingId=wingSel?wingSel.value:'';
    // Rebuild squadron options filtered to the selected wing
    sqnSel.innerHTML='<option value="">All Squadrons</option>';
    const src=(S.squadrons||[]).filter(s=>!wingId||s.wing_id===wingId);
    src.forEach(s=>{ const o=new Option((s.code||s.short_name||s.name),s.squadron_id); sqnSel.appendChild(o); });
  }
  renderAccounts();
}

async function renderAccounts(){
  const canWrite=_ACCT_WRITE_ROLES.includes(S.role);
  document.querySelectorAll('.acct-write-el').forEach(el=>el.style.display=canWrite?'':'none');

  // Populate wing/sqn filter dropdowns for nat/wing admins
  const wingSel=document.getElementById('acct-filter-wing');
  const sqnSel=document.getElementById('acct-filter-sqn');
  if(S.isNational && wingSel){
    wingSel.style.display='';
    if(wingSel.options.length<=1 && S.wings){
      S.wings.forEach(w=>{ const o=new Option(w.code||w.name,w.wing_id); wingSel.appendChild(o); });
    }
  }
  if((S.isNational||S.isWing) && sqnSel){
    sqnSel.style.display='';
    if(sqnSel.options.length<=1){
      const src=S.squadrons||[];
      src.forEach(s=>{ const o=new Option((s.code||s.short_name||s.name),s.squadron_id); sqnSel.appendChild(o); });
    }
  }

  // Flights card: show for sqn_admin / wing_admin / nat_admin
  const flightCard=document.getElementById('acct-flights-card');
  if(flightCard){ flightCard.style.display=canWrite?'':'none'; }
  const fbtn=document.getElementById('flight-create-btn');
  if(fbtn) fbtn.style.display=canWrite?'':'none';
  const cbtn=document.getElementById('acct-create-btn');
  if(cbtn) cbtn.style.display=canWrite?'':'none';
  const showArchivedRow=document.getElementById('acct-show-archived-row');
  if(showArchivedRow) showArchivedRow.style.display=canWrite?'flex':'none';

  // Units card: show for wing_admin / nat_admin / system_admin
  const isNatAdmin=['national_admin','system_admin'].includes(S.role);
  const isWingAdmin=S.role==='wing_admin';
  const unitsCard=document.getElementById('acct-units-card');
  if(unitsCard) unitsCard.style.display=(isNatAdmin||isWingAdmin)?'':'none';
  const wingCreateBtn=document.getElementById('wing-create-btn');
  if(wingCreateBtn) wingCreateBtn.style.display=isNatAdmin?'':'none';
  const sqnCreateBtn=document.getElementById('sqn-create-btn');
  if(sqnCreateBtn) sqnCreateBtn.style.display=(isNatAdmin||isWingAdmin)?'':'none';
  // Wings card: NAT HQ admin / system_admin only (matches archive_wing's own require_system_or_nat_admin)
  const wingsCard=document.getElementById('acct-wings-card');
  if(wingsCard) wingsCard.style.display=isNatAdmin?'':'none';
  const wingCreateBtn2=document.getElementById('wing-create-btn-2');
  if(wingCreateBtn2) wingCreateBtn2.style.display=isNatAdmin?'':'none';
  _renderWingsTable();
  _renderUnitsTable();

  // Load accounts — pass active filter values as query params so backend scope is exercised
  try{
    const wFilt=(document.getElementById('acct-filter-wing')||{value:''}).value;
    const sFilt=(document.getElementById('acct-filter-sqn')||{value:''}).value;
    const showArchived=(document.getElementById('acct-show-archived')||{checked:false}).checked;
    let acctUrl='/api/accounts';
    const qp=[];
    if(wFilt) qp.push('wing_id='+encodeURIComponent(wFilt));
    if(sFilt) qp.push('squadron_id='+encodeURIComponent(sFilt));
    if(showArchived) qp.push('include_archived=true');
    if(qp.length) acctUrl+='?'+qp.join('&');
    S.accountList=await api(acctUrl);
  } catch(_){ S.accountList=[]; }

  // Load flights
  try{
    S.flightList=await api('/api/flights');
  } catch(_){ S.flightList=[]; }

  _renderAccountTable();
  _renderFlightTable();
  const refCard=document.getElementById('acct-refdata-card');
  if(refCard){ refCard.style.display=canWrite?'':'none'; if(canWrite)_renderRefData(); }
  // Same gate on the tab itself -- an empty Configuration tab is worse than none.
  const cfgTab=document.getElementById('acct-tab-config');
  if(cfgTab){
    cfgTab.style.display=canWrite?'':'none';
    if(!canWrite && cfgTab.classList.contains('active'))
      setAcctTab('accounts',document.getElementById('acct-tab-accounts'));
  }
}

// ── Reference Data (Training Stages / Facilitator Types / Subject Areas) ──
// "Respective to their scope" (risk-register submission) -- each admin role
// creates at its own natural scope: sqn_admin -> squadron, wing_admin ->
// wing, national_admin/system_admin -> global. Backed by the already-governed
// /api/curriculum/phases, /api/subject-area-tags, /api/facilitator-type-tags
// endpoints (see backend/app/routers/training.py's _can_create_tag /
// _can_create_phase for the full scope/proxy rules this UI intentionally
// simplifies down to the common case).
function _naturalRefScope(){
  if(S.role==='sqn_admin')return'squadron';
  if(S.role==='wing_admin')return'wing';
  if(S.role==='national_admin'||S.role==='system_admin')return'global';
  return null;
}
const _REFDATA_TYPES=[
  {key:'phase',group:'training',label:'Training Stages',listUrl:'/api/curriculum/phases',createUrl:'/api/curriculum/phases',
   archiveUrl:id=>`/api/curriculum/phases/${id}/archive`,archiveMethod:'POST',
   idField:'phase_id',nameField:'display_name',scopeField:'scope_level',ownScopeName:s=>s==='global'?'national':s},
  {key:'factype',group:'people',label:'Facilitator Types',listUrl:'/api/facilitator-type-tags',createUrl:'/api/facilitator-type-tags',
   archiveUrl:id=>`/api/facilitator-type-tags/${id}`,archiveMethod:'DELETE',
   restoreUrl:id=>`/api/facilitator-type-tags/${id}/restore`,
   idField:'tag_id',nameField:'display_name',scopeField:'scope',ownScopeName:s=>s},
  {key:'subjarea',group:'training',label:'Subject Areas',listUrl:'/api/subject-area-tags',createUrl:'/api/subject-area-tags',
   archiveUrl:id=>`/api/subject-area-tags/${id}`,archiveMethod:'DELETE',
   restoreUrl:id=>`/api/subject-area-tags/${id}/restore`,
   idField:'tag_id',nameField:'display_name',scopeField:'scope',ownScopeName:s=>s},
  {key:'reason',group:'training',label:'Session Status Reasons',listUrl:'/api/session-status-reason-tags',createUrl:'/api/session-status-reason-tags',
   archiveUrl:id=>`/api/session-status-reason-tags/${id}`,archiveMethod:'DELETE',
   restoreUrl:id=>`/api/session-status-reason-tags/${id}/restore`,
   idField:'tag_id',nameField:'display_name',scopeField:'scope',ownScopeName:s=>s},
  {key:'acttype',group:'training',label:'Activity Types',listUrl:'/api/activity-type-tags',createUrl:'/api/activity-type-tags',
   archiveUrl:id=>`/api/activity-type-tags/${id}`,archiveMethod:'DELETE',
   restoreUrl:id=>`/api/activity-type-tags/${id}/restore`,
   idField:'tag_id',nameField:'display_name',scopeField:'scope',ownScopeName:s=>s},
  {key:'roomcap',group:'resource',label:'Training Area Capabilities',listUrl:'/api/training-area-capability-tags',createUrl:'/api/training-area-capability-tags',
   archiveUrl:id=>`/api/training-area-capability-tags/${id}`,archiveMethod:'DELETE',
   restoreUrl:id=>`/api/training-area-capability-tags/${id}/restore`,
   idField:'tag_id',nameField:'display_name',scopeField:'scope',ownScopeName:s=>s},
];
// Account Management tabs. Scoped deliberately: setCurrTab clears
// .active on every .tab-btn in the document, so an unscoped copy here would make
// the Curriculum tabs and these fight each other.
function setAcctTab(key,btn){
  const bar=document.getElementById('acct-tabs');
  if(bar)bar.querySelectorAll('.tab-btn').forEach(b=>{
    b.classList.remove('active');
    b.setAttribute('aria-selected','false');
  });
  if(btn){ btn.classList.add('active'); btn.setAttribute('aria-selected','true'); }
  const panes={accounts:'acct-pane-accounts',config:'acct-pane-config'};
  Object.entries(panes).forEach(([k,id])=>{
    const el=document.getElementById(id);
    if(el)el.style.display=(k===key)?'':'none';
  });
  // The Configuration tab is only meaningful to a user who can write reference
  // data; renderAccounts() already gates the card itself on canWrite.
  if(key==='config')_renderRefData();
}

const _REFDATA_GROUPS=[
  {key:'training',label:'Training Configuration'},
  {key:'people',  label:'People Configuration'},
  {key:'resource',label:'Resource Configuration'},
];

// The card used to stack all six editors, producing the same
// tags -> input -> "+ Add" -> "Show archived" block six times down one page.
// It now shows a summary row per dataset and opens the editor in a modal.
// The editor markup itself is unchanged and still carries the same
// refdata-*-${key} ids, so every function below keeps working as-is.
function _refDataRowHtml(t,counts){
  const c=counts||{};
  const detail=(c.active==null)
    ? '<span class="muted" style="font-size:var(--fs-2xs)">counting…</span>'
    : `<span style="font-size:var(--fs-2xs);color:var(--muted)">${c.active} active${c.archived?` · ${c.archived} archived`:''}</span>`;
  return `<div style="display:flex;align-items:center;gap:10px;padding:8px 10px;border:1px solid var(--border-light);border-radius:6px;background:var(--surface)">
    <div style="flex:1;min-width:0">
      <div style="font-size:var(--fs-xs);font-weight:700;color:var(--text)">${esc(t.label)}</div>
      <div id="refdata-count-${t.key}">${detail}</div>
    </div>
    <button class="btn btn-out btn-sm" onclick="openRefDataManager('${_jsAttr(t.key)}')" aria-label="Manage ${esc(t.label)}">Manage</button>
  </div>`;
}

async function _renderRefData(){
  const natScope=_naturalRefScope();
  const lbl=document.getElementById('refdata-scope-label');
  if(lbl)lbl.textContent=natScope==='global'?'national':natScope;
  if(!natScope)return;
  const wrap=document.getElementById('refdata-sections');
  if(!wrap)return;
  wrap.innerHTML=_REFDATA_GROUPS.map(g=>{
    const types=_REFDATA_TYPES.filter(t=>t.group===g.key);
    if(!types.length)return '';
    return `<div>
      <div style="font-size:var(--fs-2xs);font-weight:800;color:var(--steel);text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px">${esc(g.label)}</div>
      <div style="display:grid;gap:6px">${types.map(t=>_refDataRowHtml(t,null)).join('')}</div>
    </div>`;
  }).join('');
  await Promise.all(_REFDATA_TYPES.map(t=>_refDataCounts(t)));
}

// Counts for the summary row. Types with a restoreUrl support ?include_archived,
// so active and archived are both real numbers; the rest report active only.
async function _refDataCounts(t){
  const el=document.getElementById(`refdata-count-${t.key}`);
  if(!el)return;
  try{
    const items=await api(t.restoreUrl?`${t.listUrl}?include_archived=true`:t.listUrl);
    const archived=t.restoreUrl?items.filter(i=>i.is_active===false).length:0;
    el.innerHTML=`<span style="font-size:var(--fs-2xs);color:var(--muted)">${items.length-archived} active${archived?` · ${archived} archived`:''}</span>`;
  }catch(_){ el.innerHTML='<span class="muted" style="font-size:var(--fs-2xs)">Could not load.</span>'; }
}

// Opens the shared modal for one dataset. The body is the per-type editor that
// used to sit inline on the card -- same ids, same handlers, same escaping.
function openRefDataManager(key){
  const t=_REFDATA_TYPES.find(x=>x.key===key); if(!t)return;
  const title=document.getElementById('refdata-modal-title');
  if(title)title.textContent=t.label;
  const body=document.getElementById('refdata-modal-body');
  if(!body)return;
  body.innerHTML=`
    <div id="refdata-list-${t.key}" style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px"><span class="muted" style="font-size:var(--fs-xs)">Loading…</span></div>
    <div style="display:flex;gap:6px">
      <input id="refdata-new-${t.key}" placeholder="New ${esc(t.label.replace(/s$/,''))} name…" style="flex:1;min-width:160px;padding:6px 9px;border:1px solid var(--border);border-radius:5px;font-size:var(--fs-xs)">
      <button id="refdata-add-${t.key}" class="btn btn-sky btn-sm" onclick="_addRefItem('${_jsAttr(t.key)}')">+ Add</button>
    </div>
    <p id="refdata-msg-${t.key}" style="color:var(--error);font-size:var(--fs-xs);margin:6px 0 0"></p>
    ${t.restoreUrl?`<label style="display:inline-flex;align-items:center;gap:5px;font-size:var(--fs-2xs);font-weight:400;text-transform:none;letter-spacing:0;margin-top:10px;color:var(--muted)"><input type="checkbox" id="refdata-show-archived-${t.key}" onchange="_loadRefByKey('${_jsAttr(t.key)}')"> Show archived</label>`:''}
  `;
  openModal('m-refdata');
  _loadRefList(t);
}

// Closing refreshes the summary counts, so the card reflects what you just did.
function closeRefDataManager(){
  closeModal('m-refdata');
  _REFDATA_TYPES.forEach(t=>_refDataCounts(t));
}

async function _loadRefList(t){
  const el=document.getElementById(`refdata-list-${t.key}`);
  if(!el)return;
  const natScope=_naturalRefScope();
  const showArchived=t.restoreUrl&&(document.getElementById(`refdata-show-archived-${t.key}`)?.checked);
  const url=showArchived?`${t.listUrl}?include_archived=true`:t.listUrl;
  try{
    const items=await api(url);
    if(!items.length){ el.innerHTML='<span class="muted" style="font-size:var(--fs-xs)">None yet.</span>'; return; }
    el.innerHTML=items.map(it=>{
      const scope=it[t.scopeField];
      const scopeName=t.ownScopeName(scope);
      const mine=scopeName===natScope && (
        natScope==='global' ||
        (natScope==='wing' && it.wing_id===((S.session||{}).wing_id)) ||
        (natScope==='squadron' && it.squadron_id===((S.session||{}).squadron_id))
      );
      const isArchived=t.restoreUrl&&it.is_active===false;
      if(isArchived){
        return `<span class="badge b-grey" style="display:inline-flex;align-items:center;gap:5px;opacity:.55">${esc(it[t.nameField])} <em style="font-style:normal;opacity:.6;font-size:var(--fs-3xs)">${esc(scopeName)}</em><em style="font-style:normal;font-size:var(--fs-3xs);color:var(--steel)">Archived</em>${mine?` <button onclick="_restoreRefItem('${t.key}','${it[t.idField]}')" style="border:none;background:none;cursor:pointer;color:var(--ok);font-size:var(--fs-xs);padding:0" title="Restore">↩</button>`:''}</span>`;
      }
      return `<span class="badge b-grey" style="display:inline-flex;align-items:center;gap:5px">${esc(it[t.nameField])} <em style="font-style:normal;opacity:.6;font-size:var(--fs-3xs)">${esc(scopeName)}</em>${mine?` <button class="btn-icon" onclick="_archiveRefItem('${t.key}','${it[t.idField]}')" style="border:none;background:none;cursor:pointer;color:var(--status-text-danger);flex-shrink:0" aria-label="Archive ${esc(it[t.nameField])}" title="Archive">×</button>`:''}</span>`;
    }).join('');
  }catch(_){ el.innerHTML='<span class="muted" style="font-size:var(--fs-xs)">Could not load.</span>'; }
}
function _loadRefByKey(key){ const t=_REFDATA_TYPES.find(x=>x.key===key); if(t)_loadRefList(t); }
async function _addRefItem(key){
  const t=_REFDATA_TYPES.find(x=>x.key===key); if(!t)return;
  const input=document.getElementById(`refdata-new-${key}`);
  const msgEl=document.getElementById(`refdata-msg-${key}`);
  const name=(input.value||'').trim();
  if(!name){ msgEl.textContent='Name is required.'; return; }
  msgEl.textContent='';
  const natScope=_naturalRefScope();
  const body=t.key==='phase'
    ? {name,display_name:name,scope_level:natScope==='global'?'national':natScope}
    : {display_name:name,scope:natScope};
  try{
    await api(t.createUrl,{method:'POST',body});
    input.value='';
    await _loadRefList(t);
  }catch(e){ msgEl.textContent=apiErr(e); }
}
async function _archiveRefItem(key,id){
  const t=_REFDATA_TYPES.find(x=>x.key===key); if(!t)return;
  confirmAction('Archive this item? It will no longer appear in pickers, but existing records are unaffected.',async()=>{
    try{
      await api(t.archiveUrl(id),{method:t.archiveMethod});
      await _loadRefList(t);
    }catch(e){ showToast(apiErr(e),true); }
  });
}
async function _restoreRefItem(key,id){
  const t=_REFDATA_TYPES.find(x=>x.key===key); if(!t||!t.restoreUrl)return;
  confirmAction('Restore this item? It will appear in pickers again.',async()=>{
    try{
      await api(t.restoreUrl(id),{method:'POST'});
      await _loadRefList(t);
    }catch(e){ showToast(apiErr(e),true); }
  });
}

// Bulk archive: wing_admin/national_admin/system_admin only (matches the
// plan's permission matrix -- sqn_admin keeps single-account actions but not
// the bulk wizard, since a squadron rarely has enough accounts to warrant it
// and the plan deliberately keeps that surface wing/national-scoped).
const _ACCT_BULK_ROLES=['wing_admin','national_admin','system_admin'];
function _acctCanBulk(){ return _ACCT_BULK_ROLES.includes(S.role); }

// Organisational-hierarchy ordering for Account Management (System Admin >
// National > Wing > Squadron, numeric unit code ascending, Admin > Viewer/
// General > Auditor within each unit, display name as a final stable
// tiebreak) -- replaces the prior implicit creation-date order from the API.
const _ACCT_ORG_RANK={system_admin:0,national_admin:1,national_viewer:1,auditor:1,wing_admin:2,wing_viewer:2,sqn_admin:3,sqn_general:3};
const _ACCT_ROLE_TIER={system_admin:0,national_admin:0,wing_admin:0,sqn_admin:0,national_viewer:1,wing_viewer:1,sqn_general:1,auditor:2};
function _acctNumCode(code){ const m=/\d+/.exec(code||''); return m?parseInt(m[0],10):Number.MAX_SAFE_INTEGER; }
function _acctSortKey(u){
  const orgRank=_ACCT_ORG_RANK[u.role]!==undefined?_ACCT_ORG_RANK[u.role]:4;
  const codeNum=orgRank===2?_acctNumCode(u.wing_code):orgRank===3?_acctNumCode(u.squadron_code):0;
  const roleTier=_ACCT_ROLE_TIER[u.role]!==undefined?_ACCT_ROLE_TIER[u.role]:3;
  const hasFlight=u.flight_id?1:0; // Flight-assigned accounts sort after their squadron's non-Flight accounts
  return [orgRank,codeNum,roleTier,hasFlight,(u.display_name||'').toLowerCase()];
}
function _acctSortRows(rows){
  return rows.slice().sort((a,b)=>{
    const ka=_acctSortKey(a), kb=_acctSortKey(b);
    for(let i=0;i<ka.length;i++){ if(ka[i]<kb[i])return -1; if(ka[i]>kb[i])return 1; }
    return 0;
  });
}

function _renderAccountTable(){
  const el=document.getElementById('acct-table'); if(!el)return;
  const flt=(document.getElementById('acct-search')||{value:''}).value.toLowerCase();
  const wingFilt=(document.getElementById('acct-filter-wing')||{value:''}).value;
  const sqnFilt=(document.getElementById('acct-filter-sqn')||{value:''}).value;
  const canWrite=_ACCT_WRITE_ROLES.includes(S.role);
  const canBulk=_acctCanBulk();
  if(!S.acctSelected) S.acctSelected=new Set();

  let rows=(S.accountList||[]).filter(u=>{
    if(wingFilt && u.wing_id!==wingFilt && u.scope_type!=='wing') return false;
    if(sqnFilt && u.squadron_id!==sqnFilt) return false;
    if(!flt) return true;
    return (u.display_name||'').toLowerCase().includes(flt)||
      (u.role||'').includes(flt)||
      (u.squadron_code||'').toLowerCase().includes(flt)||
      (u.wing_code||'').toLowerCase().includes(flt)||
      (u.scope_type||'').includes(flt);
  });
  rows=_acctSortRows(rows);

  if(!rows.length){
    el.innerHTML='<div style="color:var(--muted);font-size:var(--fs-xs);padding:8px 0">'+(!(S.accountList||[]).length?'No accounts in scope.':'No accounts match the filter.')+'</div>';
    return;
  }

  // Selections that have scrolled out of the current filter/list stay in the
  // Set (so switching a filter and back doesn't lose them) but should not
  // count toward "select all" state or the visible floating-bar total below.
  const myUid=S.session&&S.session.user_id;
  const selectableRows=rows.filter(u=>u.user_id!==myUid && !u.is_archived);
  const visibleSelectedCount=selectableRows.filter(u=>S.acctSelected.has(u.user_id)).length;
  const allVisibleSelected=selectableRows.length>0 && visibleSelectedCount===selectableRows.length;

  const unit=u=>{
    if(u.squadron_code) return 'SQN '+u.squadron_code;
    if(u.wing_code) return 'Wing '+u.wing_code;
    if(u.scope_type==='national') return 'NAT HQ';
    return '—';
  };

  const isLocked=u=>u.locked_until&&new Date(u.locked_until)>new Date();
  const statusBadge=u=>{
    if(u.is_archived) return '<span class="badge b-grey">Archived</span>';
    const active=u.active_status!==false?'<span class="badge b-ok">Active</span>':'<span class="badge b-red">Disabled</span>';
    const lock=isLocked(u)?'<span class="badge b-red" style="margin-left:3px">Locked</span>':'';
    return active+lock;
  };
  const lastLogin=u=>u.last_login_at?new Date(u.last_login_at).toLocaleDateString('en-AU',{day:'numeric',month:'short',year:'numeric'}):'Never';
  const lastChanged=u=>(u.code_last_changed||u.code_last_changed_at)?new Date(u.code_last_changed||u.code_last_changed_at).toLocaleDateString('en-AU',{day:'numeric',month:'short'}):'—';

  const actions=u=>{
    if(!canWrite) return '';
    const dn=_jsAttr(u.display_name||'');
    if(u.is_archived){
      return `<button class="btn btn-xs btn-ok" onclick="doRestoreAccount('${u.user_id}','${dn}')">Restore</button> `+
        `<button class="btn btn-xs btn-out" style="border-color:var(--red);color:var(--status-text-danger)" onclick="doPermanentlyDeleteAccount('${u.user_id}','${dn}')">Delete Permanently…</button>`;
    }
    const resetBtn=u.user_id===myUid?'':`<button class="btn btn-xs btn-sky" onclick="openAccountResetCode('${u.user_id}','${dn}')" title="Reset access code">Reset access code</button>`;
    const unlockBtn=isLocked(u)?`<button class="btn btn-xs btn-ok" onclick="doUnlockAccount('${u.user_id}','${dn}')">Unlock</button>`:'';
    const toggleBtn=u.active_status!==false
      ? `<button class="btn btn-xs" style="border-color:var(--red);color:var(--status-text-danger)" onclick="doDisableAccount('${u.user_id}','${dn}')">Disable</button>`
      : `<button class="btn btn-xs btn-ok" onclick="doReactivateAccount('${u.user_id}','${dn}')">Reactivate</button>`;
    const editBtn=`<button class="btn btn-xs" onclick="openEditAccountModal('${u.user_id}')">Edit</button>`;
    // REM-05: only Squadron/Wing-scoped accounts have a scope to move (National-
    // scope accounts 422 scope_change_not_applicable server-side). Hidden for
    // sqn_admin actors and for self -- both are unconditionally rejected
    // server-side too (out_of_scope / cannot_change_own_scope); hiding here is
    // UI convenience only, same framing as the role picker's own authority map.
    const changeScopeBtn=(u.scope_type!=='national'&&u.user_id!==myUid&&S.role!=='sqn_admin')
      ? `<button class="btn btn-xs" onclick="openChangeScopeModal('${u.user_id}')">Change Scope</button>` : '';
    // Labelled Archive, not Delete. It calls /archive, and the archived rows
    // carry a separate "Delete Permanently…" -- so calling this one "Delete"
    // made the same word mean two different things depending on the row, which
    // is precisely the archive/delete confusion the design rules out.
    const deleteBtn=u.user_id===myUid?'':`<button class="btn btn-xs btn-out" onclick="doArchiveAccount('${u.user_id}','${dn}')" title="Revokes access; reversible via Show archived → Restore">Archive</button>`;
    return `<div style="display:flex;gap:4px;flex-wrap:wrap">${editBtn}${changeScopeBtn}${resetBtn}${unlockBtn}${toggleBtn}${deleteBtn}</div>`;
  };

  /* AUDIT-2026-08 G5: wrap bare checkboxes in a label so the click area meets 28px [HIG] */
  const selCol=canBulk?`<th class="no-print" style="width:30px"><label style="display:flex;align-items:center;justify-content:center;min-height:var(--ctl-min);min-width:var(--ctl-min);cursor:pointer"><input type="checkbox" id="acct-select-all" ${allVisibleSelected?'checked':''} onchange="_acctToggleAll(this.checked)" aria-label="Select all accounts matching the current filter"></label></th>`:'';
  el.innerHTML='<div class="tw"><table><thead><tr>'+selCol+'<th>Name</th><th>Role</th><th>Scope</th><th>Unit</th><th>Status</th><th>Last Login</th><th>Code Last Changed</th>'+(canWrite?'<th class="no-print">Actions</th>':'')+'</tr></thead><tbody>'+
    rows.map(u=>{
      const isMe=u.user_id===myUid;
      const cb=canBulk?`<td class="no-print">${(isMe||u.is_archived)?'':`<label style="display:flex;align-items:center;justify-content:center;min-height:var(--ctl-min);min-width:var(--ctl-min);cursor:pointer"><input type="checkbox" ${S.acctSelected.has(u.user_id)?'checked':''} onchange="_acctToggleOne('${u.user_id}',this.checked)" aria-label="Select ${esc(u.display_name||'')}"></label>`}</td>`:'';
      return `<tr>${cb}
      <td style="font-weight:700">${esc(u.display_name||'—')}</td>
      <td><span class="badge ${_ROLE_CLS[u.role]||'b-grey'}">${esc(_ROLE_LABELS[u.role]||u.role)}</span></td>
      <td><span class="badge ${_SCOPE_CLS[u.scope_type]||'b-grey'}">${esc(_SCOPE_LABELS[u.scope_type]||u.scope_type||'—')}</span></td>
      <td style="font-size:var(--fs-xs);color:var(--muted)">${unit(u)}</td>
      <td>${statusBadge(u)}</td>
      <td style="font-size:var(--fs-xs)">${lastLogin(u)}</td>
      <td style="font-size:var(--fs-xs)">${lastChanged(u)}</td>
      ${canWrite?`<td class="no-print">${actions(u)}</td>`:''}
    </tr>`;}).join('')+
    '</tbody></table></div>'+
    (canBulk?_acctSelectionBarHtml():'');
}

function _acctSelectionBarHtml(){
  const n=S.acctSelected.size;
  if(!n) return '';
  return `<div class="no-print" style="position:sticky;bottom:0;margin-top:8px;padding:8px 12px;background:var(--dark);color:#fff;border-radius:8px;display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap">
    <span style="font-size:var(--fs-sm);font-weight:700">${n} account${n===1?'':'s'} selected</span>
    <div style="display:flex;gap:6px">
      <button class="btn btn-xs" style="background:#fff;color:var(--dark)" onclick="_acctOpenWizard()">Bulk Archive</button>
      <button class="btn btn-xs btn-out" style="border-color:#fff;color:#fff" onclick="_acctClearSelection()">Clear</button>
    </div>
  </div>`;
}

function _acctToggleOne(uid,checked){
  if(!S.acctSelected) S.acctSelected=new Set();
  if(checked) S.acctSelected.add(uid); else S.acctSelected.delete(uid);
  _renderAccountTable();
}
function _acctToggleAll(checked){
  if(!S.acctSelected) S.acctSelected=new Set();
  const myUid=S.session&&S.session.user_id;
  const flt=(document.getElementById('acct-search')||{value:''}).value.toLowerCase();
  const wingFilt=(document.getElementById('acct-filter-wing')||{value:''}).value;
  const sqnFilt=(document.getElementById('acct-filter-sqn')||{value:''}).value;
  const visible=(S.accountList||[]).filter(u=>{
    if(u.user_id===myUid || u.is_archived) return false;
    if(wingFilt && u.wing_id!==wingFilt && u.scope_type!=='wing') return false;
    if(sqnFilt && u.squadron_id!==sqnFilt) return false;
    if(!flt) return true;
    return (u.display_name||'').toLowerCase().includes(flt)||(u.role||'').includes(flt)||
      (u.squadron_code||'').toLowerCase().includes(flt)||(u.wing_code||'').toLowerCase().includes(flt)||
      (u.scope_type||'').includes(flt);
  });
  visible.forEach(u=>{ if(checked) S.acctSelected.add(u.user_id); else S.acctSelected.delete(u.user_id); });
  _renderAccountTable();
}
function _acctClearSelection(){ S.acctSelected=new Set(); _renderAccountTable(); }

// REM-108: Flight archive existed with no way to see or restore an archived
// one -- follows the exact same "show archived" lazy-fetch pattern already
// used for Wings/Squadrons (_orgToggleShowArchived/_orgArchivedWings above).
let _archivedFlightList=null;
async function _flightsToggleShowArchived(){
  const checked=document.getElementById('flights-show-archived').checked;
  if(!checked){ _renderFlightTable(); return; }
  try{
    _archivedFlightList=(await api('/api/flights?include_archived=true')).filter(f=>f.is_archived);
  }catch(e){ showToast('Could not load archived flights: '+apiErr(e), true); }
  _renderFlightTable();
}
async function doRestoreFlight(flightId, name){
  try{
    await api(`/api/flights/${flightId}/restore`,{method:'POST'});
    showToast(`Flight '${name}' restored.`);
    S.flightList=await api('/api/flights');
    _archivedFlightList=(await api('/api/flights?include_archived=true')).filter(f=>f.is_archived);
    _renderFlightTable();
  }catch(e){ showToast('Could not restore: '+apiErr(e), true); }
}
function _renderFlightTable(){
  const el=document.getElementById('flight-table'); if(!el)return;
  const canWrite=_ACCT_WRITE_ROLES.includes(S.role);
  const showArchived=(document.getElementById('flights-show-archived')||{}).checked;
  const flights=showArchived?(_archivedFlightList||[]):(S.flightList||[]);
  if(!flights.length){ el.innerHTML=`<div style="color:var(--muted);font-size:var(--fs-xs);padding:8px 0">No ${showArchived?'archived ':''}flights${showArchived?'':' defined'}.</div>`; return; }

  const renameBtn=f=>`<button class="btn btn-xs" onclick="openRenameFlightModal('${f.flight_id}','${_jsAttr(f.name||'')}')">Rename</button>`;
  const archiveBtn=f=>`<button class="btn btn-xs" style="border-color:var(--red);color:var(--status-text-danger)" onclick="doArchiveFlight('${f.flight_id}','${_jsAttr(f.name||'')}')">Archive</button>`;
  const restoreBtn=f=>`<button class="btn btn-xs btn-ok" onclick="doRestoreFlight('${f.flight_id}','${_jsAttr(f.name||'')}')">Restore</button>`;
  const actionsCell=f=>f.is_archived?restoreBtn(f):(renameBtn(f)+archiveBtn(f));

  el.innerHTML='<div class="tw"><table><thead><tr><th>Flight Name</th><th>Squadron</th><th>Members</th>'+(canWrite?'<th class="no-print"></th>':'')+'</tr></thead><tbody>'+
    flights.map(f=>`<tr${f.is_archived?' style="opacity:.6"':''}>
      <td style="font-weight:700">${esc(f.name)}${f.is_archived?' <span class="badge b-grey">Archived</span>':''}</td>
      <td style="font-size:var(--fs-xs);color:var(--muted)">${esc(f.squadron_code||f.squadron_name||'—')}</td>
      <td style="font-size:var(--fs-xs)">${f.member_count??'—'}</td>
      ${canWrite?`<td class="no-print" style="display:flex;gap:4px">${actionsCell(f)}</td>`:''}
    </tr>`).join('')+
    '</tbody></table></div>';
}

// ── Wings management ──────
let _orgArchivedWings=null, _orgArchivedSqns=null; // fetched lazily, separate from
// S.wings/S.squadrons (which stay active-only for every other feature that reads them)
async function _orgToggleShowArchived(kind){
  const checked=document.getElementById(kind==='wing'?'wings-show-archived':'units-show-archived').checked;
  if(!checked){ _renderWingsTable(); _renderUnitsTable(); return; }
  try{
    if(kind==='wing') _orgArchivedWings=await api('/api/wings?include_archived=true');
    else _orgArchivedSqns=await api('/api/squadrons?include_archived=true');
  }catch(e){ showToast('Could not load archived: '+apiErr(e), true); }
  _renderWingsTable(); _renderUnitsTable();
}
function _renderWingsTable(){
  const el=document.getElementById('wings-table'); if(!el)return;
  const showArchived=(document.getElementById('wings-show-archived')||{}).checked;
  const wings=showArchived?(_orgArchivedWings||[]):(S.wings||[]);
  const isNatAdmin=['national_admin','system_admin'].includes(S.role);
  if(!wings.length){ el.innerHTML='<div style="color:var(--muted);font-size:var(--fs-xs);padding:8px 0">No Wings found.</div>'; return; }
  const sqnCount=wid=>(S.squadrons||[]).filter(s=>s.wing_id===wid).length;
  const actionsCell=w=>{
    if(!isNatAdmin) return '';
    if(w.is_archived) return `<button class="btn btn-xs btn-ok" onclick="doRestoreWing('${w.wing_id}','${_jsAttr(w.code)}')">Restore</button> `+
      `<button class="btn btn-xs btn-out" style="border-color:var(--red);color:var(--status-text-danger)" onclick="doPermanentlyDeleteWing('${w.wing_id}','${_jsAttr(w.code)}')">Delete Permanently…</button>`;
    return `<button class="btn btn-xs btn-dk" onclick="_openRenameOrgModal('wing','${w.wing_id}','${_jsAttr(w.name||w.code)}','${_jsAttr(w.short_name||'')}')">Rename</button> `+
      `<button class="btn btn-xs btn-out" style="border-color:var(--red);color:var(--status-text-danger)" onclick="_orgOpenWizard('wing','${w.wing_id}','${_jsAttr(w.code)}')" title="Archives the Wing — reversible">Delete</button>`;
  };
  el.innerHTML='<div class="tw"><table><thead><tr><th>Code</th><th>Name</th><th>Squadrons</th>'+(isNatAdmin?'<th class="no-print"></th>':'')+'</tr></thead><tbody>'+
    wings.map(w=>`<tr${w.is_archived?' style="opacity:.6"':''}>
      <td style="font-weight:700">${esc(w.code)}${w.is_archived?' <span class="badge b-grey">Archived</span>':''}</td>
      <td style="font-size:var(--fs-xs)">${esc(w.name||w.short_name||'')}</td>
      <td style="font-size:var(--fs-xs);color:var(--muted)">${sqnCount(w.wing_id)}</td>
      ${isNatAdmin?`<td class="no-print" style="display:flex;gap:4px;flex-wrap:wrap">${actionsCell(w)}</td>`:''}
    </tr>`).join('')+
    '</tbody></table></div>';
}

// ── Units management (Squadrons / Specialist Units) ──────
const _UNIT_TYPE_LABELS={standard_squadron:'Standard Squadron',specialist_squadron:'Specialist Squadron',specialist_flight:'Specialist Flight',support_unit:'Support Unit'};

function _renderUnitsTable(){
  const el=document.getElementById('units-table'); if(!el)return;
  const showArchived=(document.getElementById('units-show-archived')||{}).checked;
  const typeFilter=(document.getElementById('units-type-filter')||{}).value||'all';
  let sqns=showArchived?(_orgArchivedSqns||[]):(S.squadrons||[]);
  if(typeFilter!=='all') sqns=sqns.filter(s=>s.unit_type===typeFilter);
  const wings=S.wings||[];
  const isNatAdmin=['national_admin','system_admin'].includes(S.role);
  const isWingAdmin=S.role==='wing_admin';
  const canArchive=s=>isNatAdmin||(isWingAdmin&&s.wing_id===(S.session&&S.session.wing_id));
  const wName=wid=>{ const w=wings.find(x=>x.wing_id===wid); return w?w.code||w.name:wid||'—'; };
  if(!sqns.length){ el.innerHTML='<div style="color:var(--muted);font-size:var(--fs-xs);padding:8px 0">No units found.</div>'; return; }
  const actionsCell=s=>{
    if(!canArchive(s)) return '';
    if(s.is_archived) return `<button class="btn btn-xs btn-ok" onclick="doRestoreSquadron('${s.squadron_id}','${_jsAttr(s.code)}')">Restore</button> `+
      `<button class="btn btn-xs btn-out" style="border-color:var(--red);color:var(--status-text-danger)" onclick="doPermanentlyDeleteSquadron('${s.squadron_id}','${_jsAttr(s.code)}')">Delete Permanently…</button>`;
    return `<button class="btn btn-xs btn-dk" onclick="_openRenameOrgModal('squadron','${s.squadron_id}','${_jsAttr(s.name||s.code)}','${_jsAttr(s.short_name||'')}')">Rename</button> `+
      `<button class="btn btn-xs btn-dk" onclick="_openEditUnitTypeModal('${s.squadron_id}','${_jsAttr(s.unit_type||'standard_squadron')}','${_jsAttr(s.name||s.code)}')">Edit Type</button> `+
      `<button class="btn btn-xs btn-out" style="border-color:var(--red);color:var(--status-text-danger)" onclick="_orgOpenWizard('squadron','${s.squadron_id}','${_jsAttr(s.code)}')" title="Archives the unit — reversible">Delete</button>`;
  };
  el.innerHTML='<div class="tw"><table><thead><tr><th>Code</th><th>Name</th><th>Type</th><th>Wing</th>'+((isNatAdmin||isWingAdmin)?'<th class="no-print"></th>':'')+'</tr></thead><tbody>'+
    sqns.map(s=>`<tr${s.is_archived?' style="opacity:.6"':''}>
      <td style="font-weight:700">${esc(s.code)}${s.is_archived?' <span class="badge b-grey">Archived</span>':''}</td>
      <td style="font-size:var(--fs-xs)">${esc(s.name||s.short_name||'')}</td>
      <td style="font-size:var(--fs-xs)"><span class="badge b-blue" style="font-size:var(--fs-2xs)">${esc(_UNIT_TYPE_LABELS[s.unit_type]||s.unit_type||'Squadron')}</span></td>
      <td style="font-size:var(--fs-xs);color:var(--muted)">${esc(wName(s.wing_id))}</td>
      ${(isNatAdmin||isWingAdmin)?`<td class="no-print" style="display:flex;gap:4px;flex-wrap:wrap">${actionsCell(s)}</td>`:''}
    </tr>`).join('')+
    '</tbody></table></div>';
}

let _editUnitTypeSqnId=null;
function _openEditUnitTypeModal(sqnId, currentType, name){
  _editUnitTypeSqnId=sqnId;
  const nameEl=document.getElementById('edit-unit-type-name');
  if(nameEl) nameEl.textContent=name||sqnId;
  const sel=document.getElementById('edit-unit-type-sel');
  if(sel) sel.value=currentType||'standard_squadron';
  const msg=document.getElementById('edit-unit-type-msg');
  if(msg) msg.textContent='';
  openModal('m-edit-unit-type');
}
async function _saveUnitType(){
  if(!_editUnitTypeSqnId) return;
  const sel=document.getElementById('edit-unit-type-sel');
  const msg=document.getElementById('edit-unit-type-msg');
  const unitType=(sel&&sel.value)||'standard_squadron';
  if(msg){msg.textContent='Saving…';msg.style.color='var(--muted)';}
  try{
    await api('/api/squadrons/'+_editUnitTypeSqnId,{method:'PATCH',body:JSON.stringify({unit_type:unitType})});
    closeModal('m-edit-unit-type');
    await _refreshOrgCache();
    _renderUnitsTable();
    showToast('Unit type updated.');
  }catch(e){
    if(msg){msg.textContent=apiErr(e);msg.style.color='var(--red)';}
  }
}

// ── Rename Wing / Squadron ──────────────────────────────────────────────────
let _renameOrgType=null, _renameOrgId=null;
function _openRenameOrgModal(type, id, currentName, currentShort){
  _renameOrgType=type; _renameOrgId=id;
  const titleEl=document.getElementById('rename-org-title');
  if(titleEl) titleEl.textContent='Rename '+(type==='wing'?'Wing':'Unit');
  const nameEl=document.getElementById('rename-org-name');
  if(nameEl){ nameEl.value=currentName||''; }
  const shortEl=document.getElementById('rename-org-short');
  if(shortEl){ shortEl.value=currentShort||''; shortEl.placeholder='Abbreviation (leave blank to keep current)'; }
  const msg=document.getElementById('rename-org-msg');
  if(msg) msg.textContent='';
  openModal('m-rename-org');
}
async function _saveOrgRename(){
  if(!_renameOrgId||!_renameOrgType) return;
  const nameEl=document.getElementById('rename-org-name');
  const shortEl=document.getElementById('rename-org-short');
  const msg=document.getElementById('rename-org-msg');
  const name=(nameEl&&nameEl.value.trim())||'';
  const short=(shortEl&&shortEl.value.trim())||'';
  if(!name){ if(msg){msg.textContent='Give the phase a name.';msg.style.color='var(--red)';} return; }
  if(msg){msg.textContent='Saving…';msg.style.color='var(--muted)';}
  const path=_renameOrgType==='wing'?`/api/wings/${_renameOrgId}`:`/api/squadrons/${_renameOrgId}`;
  const body={name};
  if(short) body.short_name=short;
  try{
    await api(path,{method:'PATCH',body:JSON.stringify(body)});
    closeModal('m-rename-org');
    await _refreshOrgCache();
    if(_renameOrgType==='wing') _renderWingsTable(); else _renderUnitsTable();
    showToast('Renamed successfully.');
  }catch(e){
    if(msg){msg.textContent=apiErr(e);msg.style.color='var(--red)';}
  }
}

async function doRestoreWing(wingId, wingCode){
  try{
    await api(`/api/wings/${wingId}/restore`,{method:'POST'});
    showToast(`Wing '${wingCode}' restored.`);
    _orgArchivedWings=await api('/api/wings?include_archived=true');
    await _refreshOrgCache();
    _renderWingsTable();
  }catch(e){ showToast('Could not restore: '+apiErr(e), true); }
}
async function doPermanentlyDeleteWing(wingId, wingCode){
  const typed=await promptText('Permanently delete Wing',`Type the Wing code to confirm`,{
    context:`This permanently deletes Wing '${wingCode}' — this cannot be undone. It will only succeed if the Wing has no linked records; otherwise it stays archived.`,
    okLabel:'Delete permanently',danger:true,
    validate:v=>v!==wingCode?`Type exactly: ${wingCode}`:'',
  });
  if(!typed)return;
  if(typed.trim()!==wingCode){ showToast('Code did not match — nothing was deleted.', true); return; }
  try{
    await api(`/api/wings/${wingId}`,{method:'DELETE'});
    showToast(`Wing '${wingCode}' permanently deleted.`);
    _orgArchivedWings=await api('/api/wings?include_archived=true');
    _renderWingsTable();
  }catch(e){
    if(e && e.kind==='http' && e.status===409 && e.body && e.body.detail && e.body.detail.dependents){
      const dep=Object.entries(e.body.detail.dependents).map(([k,v])=>`${k}: ${v}`).join(', ');
      showToast(`Cannot permanently delete — linked records exist (${dep}). It remains archived.`, true);
    } else { showToast('Could not delete: '+apiErr(e), true); }
  }
}
async function doRestoreSquadron(sqnId, sqnCode){
  try{
    await api(`/api/squadrons/${sqnId}/restore`,{method:'POST'});
    showToast(`Unit '${sqnCode}' restored.`);
    _orgArchivedSqns=await api('/api/squadrons?include_archived=true');
    await _refreshOrgCache();
    _renderUnitsTable();
  }catch(e){ showToast('Could not restore: '+apiErr(e), true); }
}
async function doPermanentlyDeleteSquadron(sqnId, sqnCode){
  const typed=await promptText('Permanently delete unit',`Type the unit code to confirm`,{
    context:`This permanently deletes unit '${sqnCode}' — this cannot be undone. It will only succeed if the unit has no linked records; otherwise it stays archived.`,
    okLabel:'Delete permanently',danger:true,
    validate:v=>v!==sqnCode?`Type exactly: ${sqnCode}`:'',
  });
  if(!typed)return;
  if(typed.trim()!==sqnCode){ showToast('Code did not match — nothing was deleted.', true); return; }
  try{
    await api(`/api/squadrons/${sqnId}`,{method:'DELETE'});
    showToast(`Unit '${sqnCode}' permanently deleted.`);
    _orgArchivedSqns=await api('/api/squadrons?include_archived=true');
    _renderUnitsTable();
  }catch(e){
    if(e && e.kind==='http' && e.status===409 && e.body && e.body.detail && e.body.detail.dependents){
      const dep=Object.entries(e.body.detail.dependents).map(([k,v])=>`${k}: ${v}`).join(', ');
      showToast(`Cannot permanently delete — linked records exist (${dep}). It remains archived.`, true);
    } else { showToast('Could not delete: '+apiErr(e), true); }
  }
}

function openCreateWingModal(){
  ['cw-code','cw-name','cw-short'].forEach(id=>{const e=document.getElementById(id);if(e)e.value='';});
  document.getElementById('cw-msg').textContent='';
  openModal('m-create-wing');
}

async function doCreateWing(){
  const code=(document.getElementById('cw-code').value||'').trim().toUpperCase();
  const name=document.getElementById('cw-name').value.trim();
  const short=(document.getElementById('cw-short').value||code).trim();
  const msg=document.getElementById('cw-msg');
  msg.textContent='';
  if(!code||!name){msg.textContent='Wing Code and Full Name required.';return;}
  try{
    await api('/api/wings',{method:'POST',body:JSON.stringify({code,name,short_name:short||code})});
    // Reload wings list
    try{S.wings=await api('/api/wings');}catch(_){}
    closeModal('m-create-wing');
    await renderAccounts();
    showToast(`Wing ${code} created.`);
  }catch(e){msg.textContent=apiErr(e);}
}

async function openCreateSqnModal(){
  const isNatAdmin=['national_admin','system_admin'].includes(S.role);
  const isWingAdmin=S.role==='wing_admin';
  // Ensure wings are loaded (may not be if loadData ran before login completed)
  if(!S.wings||!S.wings.length){ try{S.wings=await api('/api/wings');}catch(_){} }
  // Populate wing selector
  const wingEl=document.getElementById('csq-wing');
  if(wingEl){
    wingEl.innerHTML='<option value="">— select wing —</option>';
    (S.wings||[]).forEach(w=>{ const o=new Option(w.code||w.name,w.wing_id); wingEl.appendChild(o); });
    if(isWingAdmin&&S.session&&S.session.wing_id){
      wingEl.value=S.session.wing_id; wingEl.disabled=true;
    } else { wingEl.disabled=false; }
  }
  ['csq-code','csq-name','csq-short'].forEach(id=>{const e=document.getElementById(id);if(e)e.value='';});
  document.getElementById('csq-msg').textContent='';
  openModal('m-create-sqn');
}

async function doCreateSqn(){
  const wingId=document.getElementById('csq-wing').value;
  const code=(document.getElementById('csq-code').value||'').trim().toUpperCase();
  const name=document.getElementById('csq-name').value.trim();
  const short=(document.getElementById('csq-short').value||code).trim();
  const unitType=document.getElementById('csq-type').value;
  const msg=document.getElementById('csq-msg');
  msg.textContent='';
  if(!wingId){msg.textContent='Select a Wing.';return;}
  if(!code||!name){msg.textContent='Unit Code and Full Name required.';return;}
  try{
    const newSqn=await api('/api/squadrons',{method:'POST',body:JSON.stringify({wing_id:wingId,code,name,short_name:short||code,unit_type:unitType})});
    // Reload squadrons
    try{S.squadrons=await api('/api/squadrons');}catch(_){}
    closeModal('m-create-sqn');
    await renderAccounts();
    const label=_UNIT_TYPE_LABELS[unitType]||'Unit';
    confirmAction(`${label} ${code} created. Create an account for ${code} now?`,()=>{
      openCreateAccountModal(newSqn&&newSqn.squadron_id);
    });
  }catch(e){msg.textContent=apiErr(e);}
}

// ── Create Account modal ──────────────────────────────────
const _CREATE_ROLE_OPTIONS={
  system_admin:  ['wing_viewer','wing_admin','sqn_general','sqn_admin','national_viewer','national_admin','auditor','system_admin'],
  national_admin:['wing_viewer','wing_admin','sqn_general','sqn_admin','national_viewer','national_admin','auditor'],
  wing_admin:    ['sqn_general','sqn_admin','wing_viewer'],
  sqn_admin:     ['sqn_general'],
};
const _ROLES_NAT_SCOPE=['national_viewer','national_admin','auditor','system_admin'];
const _ROLES_WING_SCOPE=['wing_viewer','wing_admin'];
const _ROLES_SQN_SCOPE=['sqn_general','sqn_admin'];

async function openCreateAccountModal(preselectedSqnId){
  // ACC-1: for a sqn_admin nothing had ever populated S.squadrons, so the
  // squadron select rendered with its placeholder alone and the form was
  // impossible to complete. GET /api/squadrons returns exactly the units the
  // caller may act on (1 for a sqn_admin, 16 for a wing_admin).
  if(!Array.isArray(S.squadrons) || !S.squadrons.length){
    try{ S.squadrons = await api('/api/squadrons'); }
    catch(e){ showToast('Could not load squadron options: '+apiErr(e),true); return; }
  }
  if(!Array.isArray(S.wings) || !S.wings.length){
    try{ S.wings = await api('/api/wings'); }
    catch(e){ showToast('Could not load wing options: '+apiErr(e),true); return; }
  }
  // ACC-3: sqn_admin's session does not populate S.wings, so the wing dropdown
  // rendered empty and the pre-select/lock for their own wing silently failed.
  if(!Array.isArray(S.wings) || !S.wings.length){
    try{ S.wings = await api('/api/wings'); }catch(_){ S.wings = S.wings||[]; }
  }
  document.getElementById('ca-name').value='';
  document.getElementById('ca-role').value='';
  document.getElementById('ca-msg').textContent='';
  document.getElementById('ca-wing-row').style.display='none';
  document.getElementById('ca-sqn-row').style.display='none';
  document.getElementById('ca-fixed-scope').style.display='none';
  document.getElementById('ca-manual-code-row').style.display='none';

  // Populate role dropdown based on caller's authority
  const roleSel=document.getElementById('ca-role');
  roleSel.dataset.scope='';
  roleSel.innerHTML='<option value="">— select role —</option>';
  const allowed=_CREATE_ROLE_OPTIONS[S.role]||[];
  allowed.forEach(r=>{ const o=document.createElement('option'); o.value=r; o.textContent=_ROLE_LABELS[r]||r; roleSel.appendChild(o); });

  // Pre-populate wing/sqn dropdowns
  _populateCreateWings();
  const wingFilter=S.isWing&&S.session&&S.session.wing_id?S.session.wing_id:null;
  _populateCreateSqns(wingFilter);

  // Pre-select squadron when called from combined unit+account workflow
  if(preselectedSqnId){
    const sqnSel=document.getElementById('ca-sqn');
    if(sqnSel) sqnSel.value=preselectedSqnId;
  }

  document.querySelector('[name="ca-code-mode"][value="auto"]').checked=true;
  document.getElementById('ca-manual-code').value='';
  document.getElementById('ca-recovery-email').value='';
  document.getElementById('ca-recovery-row').style.display='none';
  document.getElementById('ca-recovery-required').style.display='none';
  openModal('m-create-account');
}

function _populateCreateWings(){
  const sel=document.getElementById('ca-wing'); sel.innerHTML='<option value="">— select wing —</option>';
  (S.wings||[]).forEach(w=>{ const o=new Option(w.code||w.name,w.wing_id); sel.appendChild(o); });
  // Wing admin and sqn_admin: pre-select and lock own wing
  if((S.isWing || S.role==='sqn_admin') && S.session && S.session.wing_id){
    sel.value=S.session.wing_id; sel.disabled=true;
  } else { sel.disabled=false; }
}

function _populateCreateSqns(wingId){
  const sel=document.getElementById('ca-sqn'); sel.innerHTML='<option value="">— select squadron —</option>';
  const src=(S.squadrons||[]).filter(s=>!wingId||s.wing_id===wingId);
  src.forEach(s=>{ const o=new Option(s.code||s.short_name||s.name, s.squadron_id); sel.appendChild(o); });
  // ACC-2: sqn_admin gets its own squadron pre-selected and locked. This used to
  // compare S.sqn against code/short_name -- but S.sqn holds the squadron UUID,
  // not a code, so it never matched and nothing was ever pre-selected.
  const ownId = (S.session && S.session.squadron_id) || null;
  if(S.role==='sqn_admin' && ownId){
    const own=(S.squadrons||[]).find(x=>x.squadron_id===ownId);
    if(own){ sel.value=own.squadron_id; sel.disabled=true; }
    else { sel.disabled=false; }
  } else { sel.disabled=false; }
}

function onCreateAccountRoleChange(){
  const roleSel=document.getElementById('ca-role');
  const role=roleSel.value;
  const nextScope=_roleScopeType(role);
  const previousScope=roleSel.dataset.scope;
  if(previousScope&&previousScope!==nextScope){
    if(previousScope==='national'||nextScope==='national'){
      document.getElementById('ca-wing').value='';
      document.getElementById('ca-sqn').value='';
    }else if(nextScope==='wing'){
      document.getElementById('ca-sqn').value='';
    }
  }
  roleSel.dataset.scope=nextScope;
  const wingRow=document.getElementById('ca-wing-row');
  const sqnRow=document.getElementById('ca-sqn-row');
  const fixed=document.getElementById('ca-fixed-scope');
  const fixedSquadron=S.role==='sqn_admin' && _ROLES_SQN_SCOPE.includes(role);
  wingRow.style.display=fixedSquadron?'none':(_ROLES_WING_SCOPE.includes(role)||_ROLES_SQN_SCOPE.includes(role)?'':'none');
  sqnRow.style.display=fixedSquadron?'none':(_ROLES_SQN_SCOPE.includes(role)?'':'none');
  if(fixedSquadron){
    const sqn=(S.squadrons||[]).find(s=>s.squadron_id===(S.session&&S.session.squadron_id));
    const wing=(S.wings||[]).find(w=>w.wing_id===sqn?.wing_id);
    fixed.textContent=`Scope: ${sqn?.code||sqn?.short_name||sqn?.name||'your Squadron'}${wing?` — ${wing.code||wing.name}`:''}`;
    fixed.style.display='';
  }
  const recoveryRoles=['system_admin','national_admin','wing_admin','sqn_admin'];
  const recoveryRow=document.getElementById('ca-recovery-row');
  const recoveryRequired=document.getElementById('ca-recovery-required');
  if(recoveryRow) recoveryRow.style.display=recoveryRoles.includes(role)?'':'none';
  if(recoveryRequired) recoveryRequired.style.display=role==='system_admin'?'inline':'none';

  // Wing admin: when role is sqn-scope, filter sqn list by wing
  if(_ROLES_SQN_SCOPE.includes(role)&&S.isWing&&S.session&&S.session.wing_id){
    _populateCreateSqns(S.session.wing_id);
  }
}

function onCreateAccountWingChange(){
  const wingId=document.getElementById('ca-wing').value;
  _populateCreateSqns(wingId||null);
}

function onCreateAccountSqnChange(){
  // No-op: squadron selection has no downstream effects in this modal.
  // Defined to satisfy the onchange reference on the ca-sqn select element.
}

function onCodeModeChange(){
  const manual=document.querySelector('[name="ca-code-mode"]:checked').value==='manual';
  document.getElementById('ca-manual-code-row').style.display=manual?'':'none';
}

async function doCreateAccount(){
  const msg=document.getElementById('ca-msg');
  const name=(document.getElementById('ca-name').value||'').trim();
  const role=document.getElementById('ca-role').value;
  if(!name){ msg.textContent='Display name is required.'; return; }
  if(!role){ msg.textContent='Select a role.'; return; }

  const payload={display_name:name, role};
  const fixedSquadron=S.role==='sqn_admin' && _ROLES_SQN_SCOPE.includes(role);
  if(_ROLES_WING_SCOPE.includes(role)||_ROLES_SQN_SCOPE.includes(role)){
    const ownSqn=(S.squadrons||[]).find(s=>s.squadron_id===(S.session&&S.session.squadron_id));
    const wid=(fixedSquadron?ownSqn?.wing_id:document.getElementById('ca-wing').value)||undefined;
    if(!wid){ msg.textContent='Select a Wing.'; return; }
    payload.wing_id=wid;
  }
  if(_ROLES_SQN_SCOPE.includes(role)){
    const sid=(fixedSquadron?(S.session&&S.session.squadron_id):document.getElementById('ca-sqn').value)||undefined;
    if(!sid){ msg.textContent='Select a Squadron or Specialist Unit.'; return; }
    payload.squadron_id=sid;
  }
  if(['system_admin','national_admin','wing_admin','sqn_admin'].includes(role)){
    const recovery=(document.getElementById('ca-recovery-email').value||'').trim();
    if(role==='system_admin'&&!recovery){ msg.textContent='A recovery email is required for System Administrator accounts.'; return; }
    if(recovery) payload.recovery_email=recovery;
  }
  const codeMode=document.querySelector('[name="ca-code-mode"]:checked').value;
  if(codeMode==='manual'){
    const mc=(document.getElementById('ca-manual-code').value||'').trim();
    if(mc.length<6){ msg.textContent='Code must be at least 6 characters.'; return; }
    payload.new_code=mc;
  }

  msg.textContent='Creating…'; msg.style.color='var(--muted)';
  try{
    const r=await api('/api/accounts',{method:'POST',body:JSON.stringify(payload)});
    closeModal('m-create-account');
    // Show the one-time code
    _showNewCodeModal(r.new_code, name);
    // Reload account list
    S.accountList=null; renderAccounts();
  }catch(e){ msg.textContent=apiErr(e); msg.style.color='var(--red)'; }
}

// ── New Code Display (one-time) ───────────────────────────
let _pendingNewCode=null;
function _showNewCodeModal(code, forName){
  _pendingNewCode=code;
  document.getElementById('m-new-code-value').textContent=code||'—';
  document.getElementById('m-new-code-for').textContent=forName||'';
  document.getElementById('m-new-code-copy-msg').textContent='';
  openModal('m-new-code');
}
function closeNewCodeModal(){
  _pendingNewCode=null;
  document.getElementById('m-new-code-value').textContent='—';
  closeModal('m-new-code');
}
function copyNewCode(){
  const c=_pendingNewCode||document.getElementById('m-new-code-value').textContent;
  if(!c||c==='—')return;
  navigator.clipboard.writeText(c).then(()=>{
    document.getElementById('m-new-code-copy-msg').textContent='Copied!';
  }).catch(()=>{
    document.getElementById('m-new-code-copy-msg').textContent='Select and copy manually.';
  });
}

// ── Reset Code (accounts endpoint) ───────────────────────
let _resetAccountId=null, _resetAccountName=null;
function openAccountResetCode(userId, displayName){
  _resetAccountId=userId; _resetAccountName=displayName;
  document.getElementById('m-acct-reset-title').textContent='Reset access code — '+displayName;
  document.getElementById('m-acct-reset-msg').textContent='';
  document.getElementById('rc-manual-row').style.display='none';
  document.querySelector('[name="rc-mode"][value="auto"]').checked=true;
  openModal('m-acct-reset-code');
}
function onResetCodeModeChange(){
  const manual=document.querySelector('[name="rc-mode"]:checked').value==='manual';
  document.getElementById('rc-manual-row').style.display=manual?'':'none';
}
async function doAccountResetCode(){
  const msg=document.getElementById('m-acct-reset-msg');
  const mode=document.querySelector('[name="rc-mode"]:checked').value;
  const payload={};
  if(mode==='manual'){
    const mc=(document.getElementById('rc-manual-code').value||'').trim();
    if(mc.length<6){ msg.textContent='Code must be at least 6 characters.'; return; }
    payload.new_code=mc;
  }
  msg.textContent='Resetting…'; msg.style.color='var(--muted)';
  try{
    const r=await api('/api/accounts/'+_resetAccountId+'/reset-code',{method:'POST',body:JSON.stringify(payload)});
    closeModal('m-acct-reset-code');
    _showNewCodeModal(r.new_code, _resetAccountName);
  }catch(e){ msg.textContent=apiErr(e); msg.style.color='var(--red)'; }
}

// ── Disable / Reactivate ──────────────────────────────────
function doDisableAccount(userId, displayName){
  confirmAction('Disable account for '+displayName+'? They will not be able to sign in.', async()=>{
    try{
      await api('/api/accounts/'+userId+'/disable',{method:'POST'});
      S.accountList=null; renderAccounts();
    }catch(e){ showToast('Could not disable: '+apiErr(e), true); }
  }, true);
}
function doReactivateAccount(userId, displayName){
  confirmAction('Reactivate account for '+displayName+'?', async()=>{
    try{
      await api('/api/accounts/'+userId+'/reactivate',{method:'POST'});
      S.accountList=null; renderAccounts();
    }catch(e){ showToast('Could not reactivate: '+apiErr(e), true); }
  });
}
function doArchiveAccount(userId, displayName){
  confirmAction('Archive the account for '+displayName+'?\n\nAccess is revoked immediately and the account leaves the active list. This is reversible — tick "Show archived", then Restore.', async()=>{
    try{
      await api('/api/accounts/'+userId+'/archive',{method:'POST'});
      S.accountList=null; renderAccounts();
      showToast('Archived '+displayName+'.');
    }catch(e){ showToast('Could not archive: '+apiErr(e), true); }
  }, true);
}
async function doPermanentlyDeleteAccount(userId, displayName){
  const typed=await promptText('Permanently delete account',`Type the account name to confirm`,{
    context:`This permanently deletes the account for "${displayName}" — this cannot be undone. It will only succeed if the account has never logged in and has no audit history of its own actions; otherwise it stays archived.`,
    okLabel:'Delete permanently',danger:true,
    validate:v=>v!==displayName?`Type exactly: ${displayName}`:'',
  });
  if(!typed)return;
  if(typed.trim()!==displayName){ showToast('Name did not match — nothing was deleted.', true); return; }
  try{
    await api('/api/accounts/'+userId,{method:'DELETE'});
    showToast('Account for '+displayName+' permanently deleted.');
    S.accountList=null; renderAccounts();
  }catch(e){
    if(e && e.kind==='http' && e.status===409 && e.body && e.body.detail && e.body.detail.dependents){
      const dep=Object.entries(e.body.detail.dependents).map(([k,v])=>`${k}: ${v}`).join(', ');
      showToast(`Cannot permanently delete — history exists (${dep}). It remains archived.`, true);
    } else { showToast('Could not delete: '+apiErr(e), true); }
  }
}
function doRestoreAccount(userId, displayName){
  confirmAction('Restore account for '+displayName+'? It will become active again immediately.', async()=>{
    try{
      await api('/api/accounts/'+userId+'/restore',{method:'POST'});
      S.accountList=null; renderAccounts();
      showToast('Restored '+displayName+'.');
    }catch(e){ showToast('Could not restore: '+apiErr(e), true); }
  });
}
function doUnlockAccount(userId, displayName){
  confirmAction('Unlock account for '+displayName+'? This will clear the login lockout so they can sign in again.', async()=>{
    try{
      await api('/api/accounts/'+userId+'/unlock',{method:'POST'});
      S.accountList=null; renderAccounts();
    }catch(e){ showToast('Could not unlock: '+apiErr(e), true); }
  });
}

// ── Bulk Archive Wizard (5-step: Selection Review → Impact Assessment →
// Required Decisions → Confirmation → Result). One modal, body/foot rebuilt
// per step by _wizRender()/_wizRenderFoot() rather than five separate
// modals, so step state (reason, confirmation checkbox, in-flight results)
// survives Back/Continue navigation within the same wizard session. ──
function _acctOpenWizard(){
  const ids=[...S.acctSelected];
  if(!ids.length) return;
  const byId=new Map((S.accountList||[]).map(u=>[u.user_id,u]));
  const accounts=ids.map(id=>byId.get(id)).filter(Boolean);
  S.wiz={step:1, accounts, reason:'', confirmRevocation:false, effectiveAt:'', results:null, summary:null, batchId:null, batchAudit:null};
  openModal('m-archive-wizard');
  _wizRender();
}

function _wizClose(){
  closeModal('m-archive-wizard');
  S.wiz=null;
}

function _wizRemove(uid){
  if(!S.wiz) return;
  S.wiz.accounts=S.wiz.accounts.filter(u=>u.user_id!==uid);
  S.acctSelected.delete(uid);
  _wizRender();
}

function _wizBack(){ if(S.wiz && S.wiz.step>1){ S.wiz.step--; _wizRender(); } }
function _wizNext(){ if(S.wiz && S.wiz.step<4){ S.wiz.step++; _wizRender(); } }
function _wizReasonInput(v){ if(S.wiz){ S.wiz.reason=v; _wizRenderFoot(); } }
function _wizConfirmToggle(v){ if(S.wiz){ S.wiz.confirmRevocation=v; _wizRenderFoot(); } }
function _wizEffectiveInput(v){ if(S.wiz){ S.wiz.effectiveAt=v; } }
function _wizReasonValid(){ return S.wiz && (S.wiz.reason||'').trim().length>=10; }
function _wizStep3Valid(){ return _wizReasonValid() && S.wiz && S.wiz.confirmRevocation; }

async function _wizSubmit(){
  if(!S.wiz || !_wizStep3Valid()) return;
  const foot=document.getElementById('waz-foot');
  if(foot) foot.querySelectorAll('button').forEach(b=>b.disabled=true);
  try{
    const body={
      account_ids:S.wiz.accounts.map(u=>u.user_id),
      reason:S.wiz.reason.trim(),
      confirm_session_revocation:true,
    };
    if(S.wiz.effectiveAt) body.effective_at=S.wiz.effectiveAt;
    const r=await api('/api/accounts/batch-archive',{method:'POST',body:JSON.stringify(body)});
    S.wiz.results=r.results; S.wiz.summary=r.summary; S.wiz.batchId=r.batch_id;
    S.wiz.step=5;
    S.acctSelected=new Set();
    S.accountList=null;
    _wizRender();
    renderAccounts();
    showToast(`Archived ${r.summary.archived} of ${body.account_ids.length} selected account(s).`, r.summary.failed>0);
  }catch(e){
    showToast('Bulk archive failed: '+apiErr(e), true);
    _wizRender();
  }
}

async function _wizViewBatchAudit(){
  if(!S.wiz || !S.wiz.batchId) return;
  try{
    S.wiz.batchAudit=await api('/api/audit?batch_id='+encodeURIComponent(S.wiz.batchId));
  }catch(_){ S.wiz.batchAudit=[]; }
  _wizRender();
}

const _WIZ_RESULT_BADGE={archived:'b-ok',already_archived:'b-grey',skipped:'b-amber',failed:'b-red'};
const _WIZ_RESULT_LABEL={archived:'Archived',already_archived:'Already archived',skipped:'Skipped',failed:'Failed'};
const _WIZ_SKIP_REASON={
  cannot_archive_self:'You cannot archive your own account.',
  last_active_system_admin:'Would remove the last active System Administrator.',
  out_of_scope:'Outside your management authority.',
};

function _wizRender(){
  if(!S.wiz) return;
  const body=document.getElementById('waz-body');
  const title=document.getElementById('waz-title');
  if(!body) return;
  const w=S.wiz;
  const n=w.accounts.length;

  if(w.step===1){
    title.textContent='Step 1 of 5 — Selection Review';
    body.innerHTML=`<p style="font-size:var(--fs-sm);color:var(--muted);margin:0 0 10px">Confirm the accounts to archive. Remove any that should not be included before continuing.</p>
      <div class="tw" style="max-height:280px;overflow:auto"><table><thead><tr><th>Name</th><th>Role</th><th>Unit</th><th class="no-print"></th></tr></thead><tbody>
      ${w.accounts.map(u=>`<tr>
        <td style="font-weight:700">${esc(u.display_name||'—')}</td>
        <td><span class="badge ${_ROLE_CLS[u.role]||'b-grey'}">${esc(_ROLE_LABELS[u.role]||u.role)}</span></td>
        <td style="font-size:var(--fs-xs);color:var(--muted)">${esc(u.squadron_code?('SQN '+u.squadron_code):(u.wing_code?('Wing '+u.wing_code):(u.scope_type==='national'?'NAT HQ':'—')))}</td>
        <td class="no-print"><button class="btn btn-xs btn-out" onclick="_wizRemove('${u.user_id}')">Remove</button></td>
      </tr>`).join('')}
      </tbody></table></div>
      <div style="font-size:var(--fs-xs);margin-top:8px;color:var(--muted)">${n} account${n===1?'':'s'} selected.</div>`;
  } else if(w.step===2){
    title.textContent='Step 2 of 5 — Impact Assessment';
    body.innerHTML=`
      <div class="alert a-warn" style="font-size:var(--fs-sm);margin-bottom:8px">Archiving immediately revokes sign-in for ${n} account${n===1?'':'s'} and deactivates their access code${n===1?'':'s'}. This is reversible — archived accounts can be restored at any time from the same page.</div>
      <div class="alert a-info" style="font-size:var(--fs-sm)">If any selected account is the last active System Administrator, or is outside your management authority, that one account is skipped (with a visible reason) — the rest of the batch still proceeds. No account is silently dropped.</div>`;
  } else if(w.step===3){
    title.textContent='Step 3 of 5 — Required Decisions';
    body.innerHTML=`
      <div class="ff"><label for="waz-reason">Reason (required, minimum 10 characters)</label>
        <textarea id="waz-reason" rows="3" oninput="_wizReasonInput(this.value)" placeholder="e.g. End-of-year account cleanup — cadets who have left the unit">${esc(w.reason||'')}</textarea>
      </div>
      <div class="ff"><label for="waz-effective">Effective date (optional — audit record only; archiving happens immediately, there is no scheduled/deferred archiving)</label>
        <input type="date" id="waz-effective" value="${esc(w.effectiveAt||'')}" onchange="_wizEffectiveInput(this.value)">
      </div>
      <label style="display:flex;align-items:flex-start;gap:8px;font-size:var(--fs-sm);margin-top:10px;cursor:pointer">
        <input type="checkbox" id="waz-confirm" ${w.confirmRevocation?'checked':''} onchange="_wizConfirmToggle(this.checked)" style="margin-top:2px">
        <span>I confirm that active sessions for these accounts will be revoked immediately.</span>
      </label>`;
  } else if(w.step===4){
    title.textContent='Step 4 of 5 — Confirmation';
    body.innerHTML=`
      <p style="font-size:var(--fs-sm)">You are about to archive <strong>${n}</strong> account${n===1?'':'s'}.</p>
      <div style="font-size:var(--fs-xs);color:var(--muted);white-space:pre-wrap;border:1px solid var(--border);border-radius:6px;padding:8px 10px;margin:8px 0"><strong>Reason:</strong> ${esc(w.reason.trim())}</div>
      <p style="font-size:var(--fs-xs);color:var(--muted)">This takes effect immediately on confirmation and is recorded in the Audit Log under one correlated batch.</p>`;
  } else if(w.step===5){
    title.textContent='Step 5 of 5 — Result';
    const results=w.results||[];
    body.innerHTML=`
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;font-size:var(--fs-xs)">
        <span class="badge b-ok">${w.summary.archived} archived</span>
        <span class="badge b-grey">${w.summary.already_archived} already archived</span>
        <span class="badge b-amber">${w.summary.skipped} skipped</span>
        <span class="badge b-red">${w.summary.failed} failed</span>
      </div>
      <div class="tw" style="max-height:240px;overflow:auto"><table><thead><tr><th>Name</th><th>Role</th><th>Result</th></tr></thead><tbody>
      ${results.map(r=>`<tr>
        <td style="font-weight:700">${esc(r.display_name||r.account_id)}</td>
        <td>${r.role?`<span class="badge ${_ROLE_CLS[r.role]||'b-grey'}">${esc(_ROLE_LABELS[r.role]||r.role)}</span>`:'—'}</td>
        <td><span class="badge ${_WIZ_RESULT_BADGE[r.result]||'b-grey'}">${esc(_WIZ_RESULT_LABEL[r.result]||r.result)}</span>${r.reason&&_WIZ_SKIP_REASON[r.reason]?` <span style="font-size:var(--fs-2xs);color:var(--muted)">${esc(_WIZ_SKIP_REASON[r.reason])}</span>`:''}</td>
      </tr>`).join('')}
      </tbody></table></div>
      <div style="margin-top:10px">
        ${w.batchAudit?`<div class="tw" style="max-height:180px;overflow:auto;margin-top:6px"><table><thead><tr><th>Time</th><th>Action</th><th>Object</th></tr></thead><tbody>
          ${w.batchAudit.map(a=>`<tr><td style="font-size:var(--fs-xs);white-space:nowrap">${(a.timestamp||'').replace('T',' ').slice(0,16)}</td><td style="font-size:var(--fs-xs)">${esc(a.action||'')}</td><td style="font-size:var(--fs-xs);color:var(--muted)">${esc(a.object_type||'')}</td></tr>`).join('')}
        </tbody></table></div>`
        :`<button class="btn btn-xs btn-out" onclick="_wizViewBatchAudit()">View batch audit (${esc(w.batchId||'')})</button>`}
      </div>`;
  }
  _wizRenderFoot();
}

function _wizRenderFoot(){
  if(!S.wiz) return;
  const foot=document.getElementById('waz-foot');
  if(!foot) return;
  const w=S.wiz;
  if(w.step===1){
    foot.innerHTML=`<button class="btn btn-out" onclick="_wizClose()">Cancel</button>
      <button class="btn btn-dk" ${w.accounts.length?'':'disabled'} onclick="_wizNext()">Continue</button>`;
  } else if(w.step===2){
    foot.innerHTML=`<button class="btn btn-out" onclick="_wizBack()">Back</button>
      <button class="btn btn-dk" onclick="_wizNext()">Continue</button>`;
  } else if(w.step===3){
    foot.innerHTML=`<button class="btn btn-out" onclick="_wizBack()">Back</button>
      <button class="btn btn-dk" ${_wizStep3Valid()?'':'disabled'} onclick="_wizNext()">Continue</button>`;
  } else if(w.step===4){
    foot.innerHTML=`<button class="btn btn-out" onclick="_wizBack()">Back</button>
      <button class="btn btn-dk" onclick="_wizSubmit()">Confirm &amp; Archive</button>`;
  } else if(w.step===5){
    foot.innerHTML=`<button class="btn btn-dk" onclick="_wizClose()">Done</button>`;
  }
}

// ── Organisation (Wing/Squadron) Archive Wizard ──────────────────────────
// Same 5-step shell as the account wizard. archive_wing/archive_squadron
// take no reason parameter and are called unchanged (see architecture.md --
// the wizard wraps the existing endpoints, it does not modify their
// contract), so Step 3 here is a confirmation gate only, no reason field.
const _ORG_KIND_LABEL={wing:'Wing',squadron:'Squadron'};

function _orgOpenWizard(kind,id,label){
  S.owz={kind,id,label,step:1,impact:null,nestedSelected:new Set(),confirmArchive:false,result:null,error:null};
  openModal('m-org-archive-wizard');
  _owzRender();
}
function _owzClose(){ closeModal('m-org-archive-wizard'); S.owz=null; }
function _owzBack(){ if(S.owz && S.owz.step>1){ S.owz.step--; _owzRender(); } }

async function _owzNext(){
  if(!S.owz) return;
  if(S.owz.step===1){ S.owz.step=2; await _owzLoadImpact(); return; }
  S.owz.step++; _owzRender();
}

async function _owzLoadImpact(){
  const w=S.owz; if(!w) return;
  const path=w.kind==='wing'?`/api/wings/${w.id}/archive-impact`:`/api/squadrons/${w.id}/archive-impact`;
  try{
    w.impact=await api(path);
  }catch(e){
    w.impact={can_archive:false,hard_blockers:[{type:'error',message:apiErr(e)}],soft_warnings:[],active_accounts:[],subordinate_orgs:[],historical_record_counts:{}};
  }
  w.nestedSelected=new Set();
  _owzRender();
}

function _owzNestedToggle(uid,checked){
  if(!S.owz) return;
  if(checked) S.owz.nestedSelected.add(uid); else S.owz.nestedSelected.delete(uid);
  _owzRenderFoot();
  const btn=document.getElementById('owz-nested-archive-btn');
  if(btn) btn.disabled=S.owz.nestedSelected.size===0;
}

async function _owzArchiveNestedAccounts(){
  const w=S.owz; if(!w || !w.nestedSelected.size) return;
  try{
    await api('/api/accounts/batch-archive',{method:'POST',body:JSON.stringify({
      account_ids:[...w.nestedSelected],
      reason:`Archived as part of ${_ORG_KIND_LABEL[w.kind]} archival: ${w.label}`,
      confirm_session_revocation:true,
    })});
    showToast('Archived selected account(s). Re-checking impact…');
  }catch(e){ showToast('Could not archive selected accounts: '+apiErr(e), true); }
  await _owzLoadImpact();
}

function _owzConfirmToggle(v){ if(S.owz){ S.owz.confirmArchive=v; _owzRenderFoot(); } }

async function _owzSubmit(){
  const w=S.owz; if(!w || !w.confirmArchive) return;
  const foot=document.getElementById('owz-foot');
  if(foot) foot.querySelectorAll('button').forEach(b=>b.disabled=true);
  const path=w.kind==='wing'?`/api/wings/${w.id}/archive`:`/api/squadrons/${w.id}/archive`;
  try{
    await api(path,{method:'POST'});
    w.result='ok';
    S.accountList=null; S.wings=null; S.squadrons=null;
    try{ S.wings=await api('/api/wings'); }catch(_){}
    try{ S.squadrons=await api('/api/squadrons'); }catch(_){}
    showToast(`${_ORG_KIND_LABEL[w.kind]} ${w.label} archived.`);
  }catch(e){
    w.result='error'; w.error=apiErr(e);
    showToast('Archive failed: '+apiErr(e), true);
  }
  w.step=5;
  _owzRender();
  renderAccounts();
}

function _owzRender(){
  if(!S.owz) return;
  const body=document.getElementById('owz-body');
  const title=document.getElementById('owz-title');
  if(!body) return;
  const w=S.owz;
  const kindLabel=_ORG_KIND_LABEL[w.kind];

  if(w.step===1){
    title.textContent=`Step 1 of 5 — Confirm ${kindLabel}`;
    body.innerHTML=`<p style="font-size:var(--fs-sm)">You are starting an archive workflow for:</p>
      <div style="font-size:var(--fs-md);font-weight:700;border:1px solid var(--border);border-radius:6px;padding:8px 10px;margin:8px 0">${esc(kindLabel)}: ${esc(w.label)}</div>
      <p style="font-size:var(--fs-xs);color:var(--muted)">The next step checks whether anything currently blocks archiving this ${kindLabel.toLowerCase()}.</p>`;
  } else if(w.step===2){
    title.textContent='Step 2 of 5 — Impact Assessment';
    if(!w.impact){
      body.innerHTML='<p class="muted" style="font-size:var(--fs-sm)">Loading impact assessment…</p>';
    } else {
      const hb=w.impact.hard_blockers||[], sw=w.impact.soft_warnings||[];
      let blockersHtml='';
      if(hb.length){
        blockersHtml=`<div class="alert a-warn" style="font-size:var(--fs-sm);margin-bottom:8px">
          ${hb.map(b=>esc(b.message||b.type)).join('<br>')}
        </div>`;
        if(w.kind==='squadron' && (w.impact.active_accounts||[]).length){
          blockersHtml+=`<div style="font-size:var(--fs-xs);font-weight:700;margin:8px 0 4px">Select accounts to archive now to clear this block:</div>
            <div class="tw" style="max-height:180px;overflow:auto"><table><thead><tr><th></th><th>Name</th><th>Role</th></tr></thead><tbody>
            ${w.impact.active_accounts.map(a=>`<tr>
              <td><input type="checkbox" onchange="_owzNestedToggle('${a.user_id}',this.checked)" aria-label="Select ${esc(a.display_name||'')}"></td>
              <td style="font-weight:700">${esc(a.display_name||'—')}</td>
              <td><span class="badge ${_ROLE_CLS[a.role]||'b-grey'}">${esc(_ROLE_LABELS[a.role]||a.role)}</span></td>
            </tr>`).join('')}
            </tbody></table></div>
            <button class="btn btn-xs btn-dk" id="owz-nested-archive-btn" style="margin-top:6px" disabled onclick="_owzArchiveNestedAccounts()">Archive selected accounts now</button>`;
        } else if(w.kind==='wing' && (w.impact.subordinate_orgs||[]).length){
          blockersHtml+=`<div style="font-size:var(--fs-xs);color:var(--muted);margin-top:6px">Archive these Squadrons / Specialist Units individually first (Squadrons / Specialist Units table below):<br>${w.impact.subordinate_orgs.map(s=>esc(s.code)).join(', ')}</div>`;
        }
      } else {
        blockersHtml='<div class="alert a-info" style="font-size:var(--fs-sm);margin-bottom:8px">No blocking conditions. This '+kindLabel.toLowerCase()+' can be archived.</div>';
      }
      const warningsHtml=sw.length?`<div style="font-size:var(--fs-xs);margin-top:8px"><strong>Also note:</strong><ul style="margin:4px 0 0 18px;padding:0">${sw.map(x=>`<li>${esc(x.message||x.type)}</li>`).join('')}</ul></div>`:'';
      body.innerHTML=blockersHtml+warningsHtml;
    }
  } else if(w.step===3){
    title.textContent='Step 3 of 5 — Required Decisions';
    body.innerHTML=`<label style="display:flex;align-items:flex-start;gap:8px;font-size:var(--fs-sm);cursor:pointer">
        <input type="checkbox" ${w.confirmArchive?'checked':''} onchange="_owzConfirmToggle(this.checked)" style="margin-top:2px">
        <span>I understand this will archive ${esc(kindLabel)} ${esc(w.label)} and remove it from active use. This is reversible via Restore.</span>
      </label>`;
  } else if(w.step===4){
    title.textContent='Step 4 of 5 — Confirmation';
    body.innerHTML=`<p style="font-size:var(--fs-sm)">You are about to archive <strong>${esc(kindLabel)}: ${esc(w.label)}</strong>.</p>
      <p style="font-size:var(--fs-xs);color:var(--muted)">This takes effect immediately on confirmation and is recorded in the Audit Log.</p>`;
  } else if(w.step===5){
    title.textContent='Step 5 of 5 — Result';
    body.innerHTML=w.result==='ok'
      ? `<div class="alert a-info" style="font-size:var(--fs-sm)">${esc(kindLabel)} ${esc(w.label)} archived.</div>`
      : `<div class="alert a-warn" style="font-size:var(--fs-sm)">Could not archive. Refresh the page and try again, or contact your administrator.</div>`;
  }
  _owzRenderFoot();
}

function _owzRenderFoot(){
  if(!S.owz) return;
  const foot=document.getElementById('owz-foot');
  if(!foot) return;
  const w=S.owz;
  if(w.step===1){
    foot.innerHTML=`<button class="btn btn-out" onclick="_owzClose()">Cancel</button>
      <button class="btn btn-dk" onclick="_owzNext()">Continue</button>`;
  } else if(w.step===2){
    const canContinue=w.impact && (w.impact.hard_blockers||[]).length===0;
    foot.innerHTML=`<button class="btn btn-out" onclick="_owzClose()">Cancel</button>
      <button class="btn btn-out" onclick="_owzLoadImpact()">Re-check</button>
      <button class="btn btn-dk" ${canContinue?'':'disabled'} onclick="_owzNext()">Continue</button>`;
  } else if(w.step===3){
    foot.innerHTML=`<button class="btn btn-out" onclick="_owzBack()">Back</button>
      <button class="btn btn-dk" ${w.confirmArchive?'':'disabled'} onclick="_owzNext()">Continue</button>`;
  } else if(w.step===4){
    foot.innerHTML=`<button class="btn btn-out" onclick="_owzBack()">Back</button>
      <button class="btn btn-dk" onclick="_owzSubmit()">Confirm &amp; Archive</button>`;
  } else if(w.step===5){
    foot.innerHTML=`<button class="btn btn-dk" onclick="_owzClose()">Done</button>`;
  }
}

// ── Flights ───────────────────────────────────────────────
function openCreateFlightModal(){
  document.getElementById('cf-name').value='';
  document.getElementById('cf-msg').textContent='';
  const sqnSel=document.getElementById('cf-sqn');
  sqnSel.innerHTML='<option value="">— select squadron —</option>';
  (S.squadrons||[]).forEach(s=>sqnSel.appendChild(new Option(s.code||s.short_name||s.name, s.squadron_id)));
  if(S.role==='sqn_admin' && S.sqn){
    const own=(S.squadrons||[]).find(x=>x.code===S.sqn||x.short_name===S.sqn);
    if(own){ sqnSel.value=own.squadron_id; sqnSel.disabled=true; }
  } else { sqnSel.disabled=false; }
  openModal('m-create-flight');
}
async function doCreateFlight(){
  const msg=document.getElementById('cf-msg');
  const name=(document.getElementById('cf-name').value||'').trim();
  const sqnId=document.getElementById('cf-sqn').value;
  if(!name){ msg.textContent='Flight name is required.'; return; }
  if(!sqnId){ msg.textContent='Select a squadron.'; return; }
  msg.textContent='Creating…'; msg.style.color='var(--muted)';
  try{
    await api('/api/flights',{method:'POST',body:JSON.stringify({name,squadron_id:sqnId})});
    closeModal('m-create-flight');
    S.flightList=null; renderAccounts();
  }catch(e){ msg.textContent=apiErr(e); msg.style.color='var(--red)'; }
}
async function doArchiveFlight(flightId, name){
  confirmAction('Archive flight "'+name+'"? Users assigned to it lose this assignment, but this can be undone from "Show archived".',async()=>{
    try{
      await api('/api/flights/'+flightId+'/archive',{method:'POST'});
      S.flightList=null; renderAccounts();
    }catch(e){ showToast(apiErr(e),true); }
  });
}

// ── Edit Account ──────────────────────────────────────────
let _editAccountId=null;
let _editAccountOrigRole=null;
let _changeScopeAccountId=null;
function openEditAccountModal(uid){
  const u=(S.accountList||[]).find(x=>x.user_id===uid);
  if(!u)return;
  _editAccountId=uid;
  _editAccountOrigRole=u.role;
  document.getElementById('ea-name').value=u.display_name||'';
  document.getElementById('ea-msg').textContent='';
  // Show flight selector only for squadron-scoped accounts
  const flightRow=document.getElementById('ea-flight-row');
  const sel=document.getElementById('ea-flight');
  if(u.scope_type==='squadron' && u.squadron_id){
    flightRow.style.display='';
    sel.innerHTML='<option value="">— no flight —</option>';
    (S.flightList||[]).filter(f=>f.squadron_id===u.squadron_id).forEach(f=>{
      const o=new Option(f.name,f.flight_id); if(f.flight_id===u.flight_id) o.selected=true; sel.appendChild(o);
    });
  } else { flightRow.style.display='none'; }

  // Role selector: only same-scope-level roles the actor has authority to
  // assign, and only for accounts other than the actor's own (self-role-change
  // is blocked server-side, so don't offer it here).
  const roleRow=document.getElementById('ea-role-row');
  const roleSel=document.getElementById('ea-role');
  const myUid=S.session&&S.session.user_id;
  const assignable=(_ROLE_ASSIGN_AUTHORITY[S.role]||[]).filter(r=>_roleScopeType(r)===u.scope_type);
  if(uid!==myUid && assignable.length){
    roleRow.style.display='';
    roleSel.innerHTML='';
    // Always include the account's current role even if the actor's authority
    // list wouldn't otherwise offer it, so the select reflects reality.
    const opts=new Set([u.role, ...assignable]);
    [...opts].forEach(r=>{
      const o=new Option(_ROLE_LABELS[r]||r, r); if(r===u.role) o.selected=true; roleSel.appendChild(o);
    });
  } else { roleRow.style.display='none'; }

  openModal('m-edit-account');
}
async function doEditAccount(){
  const msg=document.getElementById('ea-msg');
  const name=(document.getElementById('ea-name').value||'').trim();
  const flightId=document.getElementById('ea-flight').value;
  if(!name){msg.textContent='Display name is required.';return;}
  if(!_editAccountId){msg.textContent='No account selected.';return;}
  msg.textContent='Saving…'; msg.style.color='var(--muted)';
  try{
    const body={display_name:name};
    // Include flight_id: empty string clears it, non-empty sets it
    const flightRow=document.getElementById('ea-flight-row');
    if(flightRow.style.display!=='none') body.flight_id=flightId||'';
    await api('/api/accounts/'+_editAccountId,{method:'PATCH',body:JSON.stringify(body)});

    const roleRow=document.getElementById('ea-role-row');
    if(roleRow.style.display!=='none'){
      const newRole=document.getElementById('ea-role').value;
      if(newRole && newRole!==_editAccountOrigRole){
        await api('/api/accounts/'+_editAccountId+'/change-role',{method:'POST',body:JSON.stringify({new_role:newRole})});
      }
    }

    closeModal('m-edit-account');
    S.accountList=null; renderAccounts();
  }catch(e){ msg.textContent=apiErr(e); msg.style.color='var(--red)'; }
}

// REM-05: move an account to a different Squadron (squadron-scoped roles) or
// a different Wing (wing-scoped roles). Deliberately separate from
// openEditAccountModal/doEditAccount above -- a materially different, riskier
// operation than a display-name or role change, per the backend's own
// change-scope docstring.
function openChangeScopeModal(uid){
  const u=(S.accountList||[]).find(x=>x.user_id===uid);
  if(!u)return;
  _changeScopeAccountId=uid;
  document.getElementById('cs-title').textContent='Change Scope — '+(u.display_name||'');
  document.getElementById('cs-msg').textContent='';

  const sqnRow=document.getElementById('cs-sqn-row');
  const wingRow=document.getElementById('cs-wing-row');
  const sqnSel=document.getElementById('cs-sqn');
  const wingSel=document.getElementById('cs-wing');

  if(u.scope_type==='squadron'){
    document.getElementById('cs-current').textContent=
      (u.squadron_name||u.squadron_code||'—')+(u.wing_code?' ('+u.wing_code+')':'');
    sqnRow.style.display=''; wingRow.style.display='none';
    sqnSel.innerHTML='<option value="">— select squadron —</option>';
    // Wing Admin can only move accounts within their own Wing (server-
    // enforced too) -- filter the picker to match, same "UI convenience
    // only" framing as the role picker's own authority map.
    const src=(S.squadrons||[]).filter(s=>
      s.squadron_id!==u.squadron_id && (S.role!=='wing_admin' || s.wing_id===S.session.wing_id));
    src.forEach(s=>sqnSel.appendChild(new Option(s.code||s.short_name||s.name, s.squadron_id)));
  } else if(u.scope_type==='wing'){
    document.getElementById('cs-current').textContent=u.wing_name||u.wing_code||'—';
    sqnRow.style.display='none'; wingRow.style.display='';
    wingSel.innerHTML='<option value="">— select wing —</option>';
    (S.wings||[]).filter(w=>w.wing_id!==u.wing_id).forEach(w=>wingSel.appendChild(new Option(w.code||w.name, w.wing_id)));
  } else {
    // National-scope accounts have nothing to move -- the Change Scope
    // button is already hidden for these in _renderAccountTable(), this is
    // a defensive fallback only.
    document.getElementById('cs-msg').textContent='This account has no Squadron/Wing scope to change.';
    sqnRow.style.display='none'; wingRow.style.display='none';
  }

  openModal('m-change-scope');
}
async function doChangeScope(){
  const msg=document.getElementById('cs-msg');
  if(!_changeScopeAccountId){msg.textContent='No account selected.';return;}
  const u=(S.accountList||[]).find(x=>x.user_id===_changeScopeAccountId);
  if(!u){msg.textContent='Account not found.';return;}

  let body;
  if(u.scope_type==='squadron'){
    const val=document.getElementById('cs-sqn').value;
    if(!val){msg.textContent='Select a destination Squadron.';return;}
    body={new_squadron_id:val};
  } else if(u.scope_type==='wing'){
    const val=document.getElementById('cs-wing').value;
    if(!val){msg.textContent='Select a destination Wing.';return;}
    body={new_wing_id:val};
  } else {
    msg.textContent='This account has no Squadron/Wing scope to change.';
    return;
  }

  msg.textContent='Saving…'; msg.style.color='var(--muted)';
  try{
    await api('/api/accounts/'+_changeScopeAccountId+'/change-scope',{method:'POST',body:JSON.stringify(body)});
    closeModal('m-change-scope');
    S.accountList=null; renderAccounts();
  }catch(e){ msg.textContent=apiErr(e); msg.style.color='var(--red)'; }
}

// ── Rename Flight ──────────────────────────────────────────
let _renameFlightId=null;
function openRenameFlightModal(fid, currentName){
  _renameFlightId=fid;
  document.getElementById('rf-name').value=currentName||'';
  document.getElementById('rf-msg').textContent='';
  openModal('m-rename-flight');
}
async function doRenameFlight(){
  const msg=document.getElementById('rf-msg');
  const name=(document.getElementById('rf-name').value||'').trim();
  if(!name){msg.textContent='Flight name is required.';return;}
  if(!_renameFlightId){msg.textContent='No flight selected.';return;}
  msg.textContent='Saving…'; msg.style.color='var(--muted)';
  try{
    await api('/api/flights/'+_renameFlightId,{method:'PATCH',body:JSON.stringify({name})});
    closeModal('m-rename-flight');
    S.flightList=null; renderAccounts();
  }catch(e){ msg.textContent=apiErr(e); msg.style.color='var(--red)'; }
}
