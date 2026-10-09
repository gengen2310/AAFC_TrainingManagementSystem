// Main TMS module: Unit Settings -- user directory, display density, crest
// preview, parade-day propagation, recovery email and access-code change.
// Extracted verbatim from connected-frontend/index.html (stabilisation Phase 4,
// C6). Top-level function declarations and side-effect-free let/const only;
// loaded as a classic script BEFORE the inline bootstrap, so everything here
// is defined before any page-load code runs. Statements with load-time
// effects stay in index.html in their original order. Parity is proven by
// tools/architecture/frontend_parity.mjs.

// ── Settings page: load user directory for admins ──────────────────────────
// DENS-01: display density

// Apply stored preference early (runs when script parses, before any page render)

async function renderSettings(){
  await _loadSettingsTrainingClasses();
  const card=document.getElementById('user-dir-card');
  if(!card)return;
  // Sync display size radio buttons with current preference
  // Only show for admin roles
  const adminRoles=['sqn_admin','wing_admin','national_admin','system_admin'];
  // The User Directory (admin code reset) is admin-only. Other roles -- notably
  // read-only sqn_general -- still get the rest of Settings, so do not return
  // early here: the phases and year cards below must load for them too.
  if(!adminRoles.includes(S.role)){ card.style.display='none'; }
  else {
    card.style.display='';
    if(!S.users){
      try{ S.users=await api('/api/users'); }
      catch(_){ S.users=[]; }
    }
    renderUserDir();
  }
  loadCustomPhases();
  _applySettingsReadOnly();
  // Load year list into the Training Years settings card. Uses the same
  // renderer as the Manage Training Years modal -- this block used to draw its
  // own 2-column read-only table, which is why the two surfaces looked like
  // different features.
  (async () => {
    const wrap = document.getElementById('settings-yn-table-wrap');
    if (!wrap) return;
    try {
      await ynRefreshAllYearViews();
    } catch(e) { wrap.innerHTML = '<p style="color:var(--red);font-size:var(--fs-xs)">Failed to load years.</p>'; }
  })();
}
// Read-only roles see Settings but cannot edit it: disable form fields so the
// page does not look editable (Save buttons are already hidden via .admin-el).
// View controls that only change what is displayed stay usable.
function _applySettingsReadOnly(){
  const ro=isReadOnly();
  const keep=new Set(['tc-year-sel','tc-show-archived']);
  document.querySelectorAll('#page-settings input, #page-settings select, #page-settings textarea').forEach(el=>{
    if(keep.has(el.id)||el.type==='hidden')return;
    if(ro&&!el.disabled){ el.disabled=true; el.dataset.roDisabled='1'; }
    // Same-page sign-out/sign-in: re-enable only what read-only mode disabled.
    else if(!ro&&el.dataset.roDisabled){ el.disabled=false; delete el.dataset.roDisabled; }
  });
}
function renderUserDir(){
  const el=document.getElementById('user-dir-table'); if(!el)return;
  const flt=(document.getElementById('user-dir-filter')||{value:''}).value.toLowerCase();
  const ROLE_L={sqn_general:'SQN General',sqn_admin:'SQN Admin',wing_viewer:'Wing Viewer',wing_admin:'Wing Admin',
    national_viewer:'NAT Viewer',national_admin:'NAT Admin',system_admin:'System',auditor:'Auditor'};
  const ROLE_CLS={sqn_general:'b-blue',sqn_admin:'b-blue',wing_viewer:'b-ok',wing_admin:'b-ok',
    national_viewer:'b-amber',national_admin:'b-amber',system_admin:'b-amber',auditor:'b-grey'};
  const myUid=S.session&&S.session.user_id;
  const rows=(S.users||[]).filter(u=>u.user_id!==myUid && (!flt||
    (u.display_name||'').toLowerCase().includes(flt)||
    (u.role||'').includes(flt)||
    (u.squadron_code||'').toLowerCase().includes(flt)||
    (u.wing_code||'').toLowerCase().includes(flt)));
  if(!rows.length){ el.innerHTML='<div style="color:var(--muted);font-size:var(--fs-xs);padding:8px 0">'+(!(S.users||[]).length?'No users in scope.':'No users match the filter.')+'</div>'; return; }
  const unit=u=>u.squadron_code?'SQN '+u.squadron_code:u.wing_code?'Wing '+u.wing_code:u.national_id?'NAT HQ':'—';
  el.innerHTML='<div class="tw"><table><thead><tr><th>Name</th><th>Role</th><th>Unit</th><th></th></tr></thead><tbody>'+
    rows.map(u=>`<tr><td style="font-weight:700">${esc(u.display_name)}</td>
      <td><span class="badge ${ROLE_CLS[u.role]||'b-grey'}">${ROLE_L[u.role]||u.role}</span></td>
      <td style="font-size:var(--fs-xs);color:var(--muted)">${esc(unit(u))}</td>
      <td><button class="btn btn-xs btn-sky" onclick="openResetCodeModal('${u.user_id}','${_jsAttr(u.display_name||'')}','${u.role}','${_jsAttr(unit(u))}')">Reset code</button></td>
    </tr>`).join('')+
    '</tbody></table></div>';
}
let _resetUserId=null, _resetUserName=null;
function openResetCodeModal(userId,name,role,unit){
  _resetUserId=userId; _resetUserName=name;
  const ROLE_L={sqn_general:'SQN General',sqn_admin:'SQN Admin',wing_viewer:'Wing Viewer',wing_admin:'Wing Admin',
    national_viewer:'NAT Viewer',national_admin:'NAT Admin',system_admin:'System',auditor:'Auditor'};
  document.getElementById('m-reset-title').textContent='Reset Code — '+name;
  document.getElementById('m-reset-new').value='';
  document.getElementById('m-reset-confirm').value='';
  document.getElementById('m-reset-msg').textContent='';
  document.getElementById('m-reset-msg').style.color='var(--red)';
  openModal('m-reset-code');
}
async function doResetCode(){
  const msg=document.getElementById('m-reset-msg');
  const nw=(document.getElementById('m-reset-new').value||'').trim();
  const cf=(document.getElementById('m-reset-confirm').value||'').trim();
  if(!nw||!cf){msg.textContent='Enter and confirm the new code.';return;}
  if(nw!==cf){msg.textContent='Codes do not match.';return;}
  if(nw.length<6){msg.textContent='Code must be at least 6 characters.';return;}
  msg.textContent='Saving…'; msg.style.color='var(--muted)';
  try{
    const r=await api('/api/accounts/'+_resetUserId+'/reset-code',{method:'POST',body:JSON.stringify({new_code:nw})});
    closeModal('m-reset-code');
    document.getElementById('m-reset-new').value=''; document.getElementById('m-reset-confirm').value='';
    _showNewCodeModal(r.new_code, _resetUserName);
  }catch(e){ msg.textContent='Could not reset: '+apiErr(e); msg.style.color='var(--red)'; }
}

// ═══════════════════════════════════════════════════════════
//  SETTINGS
// ═══════════════════════════════════════════════════════════
// Shows the crest image live as the URL is typed, or a plain placeholder
// when empty -- never renders anything before the field is actually saved,
// since <img src> failures (bad URL, blocked host) just show the browser's
// own broken-image icon rather than crashing anything.
function _renderCrestPreview(){
  const el=document.getElementById('s-crest-preview'); if(!el)return;
  const url=(document.getElementById('s-crest')||{}).value||'';
  el.innerHTML=url
    ? `<img src="${esc(url)}" alt="Squadron crest" style="max-height:36px;max-width:120px;object-fit:contain">`
    : '<span class="muted" style="font-size:var(--fs-xs)">No crest set — default will be used</span>';
}
async function saveSettings(){
  const sqnId=S.currentSqnId||(S.session&&S.session.squadron_id);
  if(!sqnId){showToast('Select a squadron before saving settings.',true);return;}
  const msg=document.getElementById('settings-msg');
  if(msg){msg.textContent='Saving…';msg.style.color='var(--muted)';}
  const oldDay=(S.cfg&&S.cfg.day)||'';
  const newDay=document.getElementById('s-pday').value||null;
  const payload={
    address:document.getElementById('s-addr').value||null,
    default_parade_day:newDay,
    default_start_time:document.getElementById('s-start').value||null,
    default_end_time:document.getElementById('s-end').value||null,
    crest_url:document.getElementById('s-crest').value||'',
    unit_type:document.getElementById('s-unit-type').value||null
  };
  try{
    await api('/api/squadrons/'+sqnId,{method:'PATCH',body:JSON.stringify(payload)});
    if(msg){msg.textContent='✅ Settings saved.';msg.style.color='var(--ok)';}
    await reloadAndRender();
    // Only newly-created Parade Nights use the new default automatically --
    // already-generated nights keep their original day/time until explicitly
    // moved (see update-future-parade-day). Offer that as a separate, explicit,
    // always-previewed action rather than silently applying it.
    if(newDay && oldDay && newDay!==oldDay){ await _offerPdayPropagation(oldDay,newDay); }
  }catch(e){
    if(msg){msg.textContent=apiErr(e);msg.style.color='var(--red)';}else showToast(apiErr(e),true);
  }
}

// ═══ PARADE DAY PROPAGATION WIZARD (Settings → already-generated nights) ═══
const _DAY_NAME_TO_INT={Monday:0,Tuesday:1,Wednesday:2,Thursday:3,Friday:4,Saturday:5,Sunday:6};
let _pdayPropYearId=null, _pdayPropNewWeekday=null;

async function _offerPdayPropagation(oldDay,newDay){
  const body=document.getElementById('pday-prop-body');
  _pdayPropYearId=await _loadPlanningYears();
  _pdayPropNewWeekday=_DAY_NAME_TO_INT[newDay];
  if(!_pdayPropYearId || _pdayPropNewWeekday==null){ return; } // no planning year in scope -- nothing to propagate
  body.innerHTML=`
    <p>The default parade day changed from <b>${esc(oldDay)}</b> to <b>${esc(newDay)}</b>. This only applies automatically to <b>new</b> Parade Nights from now on.</p>
    <p style="font-size:var(--fs-sm);color:var(--muted)">Already-generated Parade Nights keep their original day until you explicitly move them. Delivered, cancelled and manually-protected nights are never moved.</p>
    <div class="modal-actions" style="flex-wrap:wrap;gap:8px;justify-content:flex-start">
      <button class="btn btn-secondary" onclick="closeModal('m-pday-propagate')">No — new nights only</button>
      <button class="btn btn-out" onclick="_pdayPropPreview('draft_only')">Preview: draft nights only</button>
      <button class="btn btn-out" onclick="_pdayPropPreview('draft_and_planned')">Preview: draft + planned nights</button>
    </div>`;
  openModal('m-pday-propagate');
}

async function _pdayPropPreview(sessionScope){
  const body=document.getElementById('pday-prop-body');
  body.innerHTML='<p style="color:var(--muted)">Loading preview…</p>';
  try{
    const r=await api(`/api/planning/years/${_pdayPropYearId}/update-future-parade-day`,{method:'POST',body:JSON.stringify({
      new_weekday:_pdayPropNewWeekday, preview:true, session_status_scope:sessionScope
    })});
    const rows=r.changes||[];
    const dayName=n=>Object.keys(_DAY_NAME_TO_INT).find(k=>_DAY_NAME_TO_INT[k]===n);
    let html=`<p style="font-size:var(--fs-sm)">${r.to_update} night(s) will move. ${r.blocked} blocked by a conflict. ${r.session_status_excluded} excluded (outside the selected scope). ${r.exceptions_preserved} manually-protected exception(s) left untouched.</p>`;
    if(rows.length){
      html+=`<div class="tw" style="max-height:280px;overflow-y:auto"><table><thead><tr><th>Old date</th><th>New date</th><th>Status</th></tr></thead><tbody>`+
        rows.map(c=>`<tr${c.blocked?' style="opacity:.55"':''}><td>${esc(c.old_date)}</td><td>${esc(c.new_date)}</td><td>${c.blocked?`<span class="badge b-red">Blocked: ${esc((c.conflicts||[]).join(', '))}</span>`:'<span class="badge b-ok">Will move</span>'}</td></tr>`).join('')+
        `</tbody></table></div>`;
    } else {
      html+=`<p style="color:var(--muted)">No eligible Parade Nights found in this scope.</p>`;
    }
    html+=`<div class="form-group" style="margin-top:12px"><label for="pday-prop-reason">Reason (required, audited)</label><input id="pday-prop-reason" placeholder="e.g. Squadron changed parade night to ${esc(dayName(_pdayPropNewWeekday)||'')}"></div>
    <div class="modal-actions">
      <button class="btn btn-secondary" onclick="closeModal('m-pday-propagate')">Cancel</button>
      <button class="btn btn-primary" ${r.to_update?'':'disabled'} onclick="_pdayPropApply('${sessionScope}')">Apply changes</button>
    </div>`;
    body.innerHTML=html;
  }catch(e){ body.innerHTML=`<p style="color:var(--red)">${esc(apiErr(e))}</p>`; }
}

async function _pdayPropApply(sessionScope){
  const body=document.getElementById('pday-prop-body');
  const reason=(document.getElementById('pday-prop-reason').value||'').trim();
  if(!reason){ showToast('A reason is required.',true); return; }
  body.innerHTML='<p style="color:var(--muted)">Applying…</p>';
  try{
    const r=await api(`/api/planning/years/${_pdayPropYearId}/update-future-parade-day`,{method:'POST',body:JSON.stringify({
      new_weekday:_pdayPropNewWeekday, preview:false, session_status_scope:sessionScope, reason
    })});
    body.innerHTML=`<p>✅ Moved <b>${r.updated}</b> Parade Night(s). ${r.skipped} skipped due to a conflict. ${r.session_status_excluded} left untouched (outside the selected scope). ${r.exceptions_preserved} manually-protected exception(s) preserved.</p>
      <div class="modal-actions"><button class="btn btn-primary" onclick="closeModal('m-pday-propagate')">Done</button></div>`;
    await reloadAndRender();
  }catch(e){ body.innerHTML=`<p style="color:var(--red)">${esc(apiErr(e))}</p><div class="modal-actions"><button class="btn btn-secondary" onclick="closeModal('m-pday-propagate')">Close</button></div>`; }
}
async function saveMyRecoveryEmail(){
  const msg=document.getElementById('recovery-msg');
  const email=(document.getElementById('recovery-email-new').value||'').trim();
  const current=(document.getElementById('recovery-current-code').value||'').trim();
  const show=(text,ok)=>{msg.textContent=text;msg.style.color=ok?'var(--ok)':'var(--red)';};
  if(!email){show('Enter a recovery email.',false);return;}
  if(!current){show('Enter your current access code.',false);return;}
  const uid=S.session&&S.session.user_id;
  if(!uid){show('No active session.',false);return;}
  try{
    const r=await api('/api/accounts/'+uid+'/recovery-email',{
      method:'POST',body:JSON.stringify({email,current_code:current})
    });
    document.getElementById('recovery-current-code').value='';
    show(r.verification_sent
      ? 'Verification code sent. Enter it below to activate recovery.'
      : 'Email saved, but delivery could not be confirmed. Check SMTP configuration before relying on recovery.',
      !!r.verification_sent);
  }catch(e){show('Could not update recovery email: '+apiErr(e),false);}
}

async function verifyMyRecoveryEmail(){
  const msg=document.getElementById('recovery-msg');
  const token=(document.getElementById('recovery-verify-token').value||'').trim();
  if(!token){msg.textContent='Enter the verification code from the email.';msg.style.color='var(--red)';return;}
  try{
    await api('/api/auth/verify-recovery-email',{
      method:'POST',body:JSON.stringify({token})
    });
    document.getElementById('recovery-verify-token').value='';
    msg.textContent='Recovery email verified.';
    msg.style.color='var(--ok)';
  }catch(e){
    msg.textContent='That verification code is invalid or expired.';
    msg.style.color='var(--red)';
  }
}

async function changeMyCode(){
  const msg=document.getElementById('cc-msg');
  const current=(document.getElementById('cc-current').value||'').trim();
  const nw=(document.getElementById('cc-new').value||'').trim();
  const cf=(document.getElementById('cc-confirm').value||'').trim();
  const show=(t,ok)=>{ if(msg){ msg.textContent=t; msg.style.color=ok?'var(--ok)':'var(--red)'; } };
  if(!current){ show('Enter your current access code.',false); return; }
  if(!nw||!cf){ show('Enter and confirm the new code.',false); return; }
  if(nw!==cf){ show('Codes do not match.',false); return; }
  if(nw.length<6){ show('Use at least 6 characters.',false); return; }
  const uid=S.session&&S.session.user_id;
  if(!uid){ show('No active session.',false); return; }
  try{
    await api('/api/auth/change-code',{method:'POST',body:JSON.stringify({user_id:uid,new_code:nw,current_code:current})});
    document.getElementById('cc-current').value=''; document.getElementById('cc-new').value=''; document.getElementById('cc-confirm').value='';
    show('Access code changed. Signing you out so you can use the new code.',true);
    setTimeout(()=>doLogout(),900);
  }catch(e){ show('Could not change code: '+apiErr(e),false); }
}
