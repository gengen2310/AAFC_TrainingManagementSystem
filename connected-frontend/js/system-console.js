// Main TMS module: System Console -- overview, health, scope map, maintenance
// mode, backups, audit, service-desk email, curriculum workbook import, staging
// bootstrap.
// Extracted verbatim from connected-frontend/index.html (stabilisation Phase 4,
// C6). Top-level function declarations and side-effect-free let/const only;
// loaded as a classic script BEFORE the inline bootstrap, so everything here
// is defined before any page-load code runs. Statements with load-time
// effects stay in index.html in their original order. Parity is proven by
// tools/architecture/frontend_parity.mjs.

// ═══════════════════════════════════════════════════════════
//  SYSTEM CONSOLE
// ═══════════════════════════════════════════════════════════

function loadSystemConsole(){
  if(S.role!=='system_admin') return;
  // Populate build fingerprint from meta tag injected by docker-entrypoint.sh.
  // REM-91: local dev (python3 -m http.server) has no build/entrypoint step at
  // all, so this meta tag's content is always the raw, unresolved
  // "__APP_BUILD__" placeholder there -- a real, non-empty string, so the old
  // `sha||'(local build)'` fallback never triggered (it only catches an empty
  // string, not a truthy placeholder). Deployed environments (staging,
  // production) are unaffected -- confirmed via direct inspection of
  // docker-entrypoint.sh, which always substitutes this tag on container
  // start regardless of environment.
  const buildMeta=(document.querySelector('meta[name="app-build"]')||{}).content||'';
  const isUnresolved=!buildMeta||buildMeta.includes('__APP_BUILD__');
  const [sha,built]=isUnresolved?['','']:buildMeta.split('|');
  const commitEl=document.getElementById('sc-build-commit');
  const builtEl=document.getElementById('sc-build-time');
  if(commitEl) commitEl.textContent=sha||'(local build)';
  if(builtEl) builtEl.textContent=built||'unknown';
  scLoadOverview();
  scLoadHealth();
  scLoadScopeMap();
  scLoadMaintenance();
  scLoadBackups();
  scLoadAudit();
  scLoadSdEmailConfig();
}

async function scLoadOverview(){
  const el=document.getElementById('sc-overview-body'); if(!el) return;
  el.innerHTML='<div class="muted">Loading…</div>';
  const warn=document.getElementById('sc-coldstart-warn');
  if(warn) warn.style.display='none';
  const coldTimer=setTimeout(()=>{if(warn)warn.style.display='block';},8000);
  try {
    const d=await api('/api/system/overview');
    clearTimeout(coldTimer);
    if(warn) warn.style.display='none';
    el.innerHTML=`<dl class="sc-kv">
      <dt>App version</dt><dd>${esc(d.app_version)}</dd>
      <dt>Package</dt><dd>${esc(d.package_version)}</dd>
      <dt>Environment</dt><dd><span class="badge-${d.environment==='production'?'red':'green'}">${esc(d.environment)}</span></dd>
      <dt>Database</dt><dd>${esc(d.db_type)}</dd>
      <dt>Wings</dt><dd>${d.wings}</dd>
      <dt>Squadrons / Units</dt><dd>${d.squadrons}</dd>
      <dt>Users (total)</dt><dd>${d.users_total}</dd>
      <dt>Users (active)</dt><dd>${d.users_active}</dd>
      <dt>Maintenance mode</dt><dd>${d.maintenance_mode?'<span class="sc-status-warn">ENABLED</span>':'<span class="sc-status-ok">Off</span>'}</dd>
      <dt>Last manual app backup</dt><dd>${d.last_backup_at?esc(d.last_backup_at):'<span class="muted">No manual app backup recorded</span>'}</dd>
      <dt>Backup source</dt><dd>${d.last_backup_source?esc(d.last_backup_source):'<span class="muted">Scheduled GitHub backups are tracked separately</span>'}</dd>
    </dl>`;
  } catch(e){ clearTimeout(coldTimer); if(warn) warn.style.display='none'; el.innerHTML=`<div class="sc-status-err">Could not load System Overview: ${esc(apiErr(e))}</div>`; }
}

async function scLoadHealth(){
  const el=document.getElementById('sc-health-body'); if(!el) return;
  try {
    const d=await api('/api/system/health');
    const dbCls=d.db==='ok'?'sc-status-ok':'sc-status-err';
    el.innerHTML=`<dl class="sc-kv">
      <dt>Backend</dt><dd class="sc-status-ok">${esc(d.backend)}</dd>
      <dt>Database</dt><dd class="${dbCls}">${esc(d.db)}</dd>
      <dt>DB type</dt><dd>${esc(d.db_type)}</dd>
      <dt>Cookie secure</dt><dd>${d.cookie_secure?'<span class="sc-status-ok">Yes</span>':'<span class="sc-status-warn">No (dev/staging only)</span>'}</dd>
      <dt>CORS origins</dt><dd style="font-family:monospace;font-size:var(--fs-xs)">${(d.cors_origins||[]).map(o=>esc(o)).join('<br>')}</dd>
    </dl>`;
  } catch(e){ el.innerHTML=`<div class="sc-status-err">Could not load Health status: ${esc(apiErr(e))}</div>`; }
}

async function _refreshOrgCache(){
  // Shared by every Wing/Squadron create+archive+restore flow (System Console
  // and Account Management) so S.wings/S.squadrons never go stale — see
  // qualification_gap_register.md defect on System-Console-created units not
  // appearing in Account Management until a full reload.
  try{S.wings=await api('/api/wings');}catch(_){}
  try{S.squadrons=await api('/api/squadrons');}catch(_){}
  // The System Administrator scope-selector bar builds its Wing/Squadron
  // dropdowns from this same cache — without this call it stays stale until
  // the next full bootApp() (login, scope switch, or Proxy/Intervention entry),
  // which is the same class of bug as the one this helper exists to fix.
  if(typeof saRenderScopeBar==='function')saRenderScopeBar();
}

async function scLoadScopeMap(){
  const el=document.getElementById('sc-scope-body'); if(!el) return;
  const showArchived=!!document.getElementById('sc-scope-show-archived')?.checked;
  try {
    const d=await api('/api/system/scope-map'+(showArchived?'?include_archived=true':''));
    if(!d.wings||!d.wings.length){ el.innerHTML='<div class="muted">No wings found.</div>'; return; }
    let h='';
    for(const w of d.wings){
      const wingArchived=w.wing_is_archived===true;
      const chips=(w.squadrons||[]).map(s=>{
        const sArchived=s.is_archived===true;
        const archiveOrRestoreBtn=sArchived
          ?`<button class="btn-icon" style="font-size:var(--fs-3xs);padding:2px 8px;margin-left:4px;background:transparent;border:1px solid #bbb;cursor:pointer;border-radius:3px;line-height:1" onclick="scRestoreSquadron('${s.id}','${_jsAttr(s.name||s.id)}')">Restore</button>`
          :`<button style="font-size:var(--fs-3xs);padding:1px 4px;margin-left:4px;background:transparent;border:1px solid #bbb;cursor:pointer;border-radius:3px;line-height:1" onclick="scArchiveSquadron('${s.id}','${_jsAttr(s.name||s.id)}')">Archive</button>`;
        return `<span class="sc-sqn-chip${sArchived?' inactive':''}" title="${esc(s.unit_type||'')}">
          ${esc(s.name||s.id)}${sArchived?' <span class="muted" style="font-size:var(--fs-3xs)">(archived)</span>':''}
          ${archiveOrRestoreBtn}
        </span>`;
      }).join('');
      const archiveWingBtn=wingArchived
        ?`<button class="btn btn-sm" style="font-size:var(--fs-2xs);padding:2px 7px;margin-left:8px;background:#fff;border:1px solid #ccc;color:var(--dark);cursor:pointer" onclick="scRestoreWing('${w.wing_id}','${_jsAttr(w.wing_code||w.wing_id)}')">Restore</button>`
        :`<button class="btn btn-sm" style="font-size:var(--fs-2xs);padding:2px 7px;margin-left:8px;background:#fff;border:1px solid #ccc;color:var(--dark);cursor:pointer" onclick="scArchiveWing('${w.wing_id}','${_jsAttr(w.wing_code||w.wing_id)}')">Archive…</button>`;
      h+=`<div class="sc-wing-row"${wingArchived?' style="opacity:.5"':''}>
        <div class="sc-wing-name">${esc(w.wing_name||w.wing_id)} <span class="muted" style="font-size:var(--fs-xs);font-weight:400">${esc(w.wing_code||'')}</span>${wingArchived?' <span class="muted" style="font-size:var(--fs-2xs)">(archived)</span>':''}${archiveWingBtn}</div>
        <div class="sc-sqn-chips">${chips||'<span class="muted" style="font-size:var(--fs-xs)">No units</span>'}</div>
      </div>`;
    }
    el.innerHTML=h;
  } catch(e){ el.innerHTML=`<div class="sc-status-err">Could not load the Scope Map: ${esc(apiErr(e))}</div>`; }
}

function scArchiveWing(wingId, wingCode){
  confirmAction(`Archive Wing '${wingCode}'?\n\nAll squadrons in this Wing must already be archived. The Wing can be restored later from the Scope Map.`, async()=>{
    try {
      await api(`/api/wings/${wingId}/archive`,{method:'POST'});
      showToast(`Wing '${wingCode}' archived.`);
      await _refreshOrgCache();
      scLoadScopeMap();
    } catch(e){ showToast('Archive failed: '+(apiErr(e)),true); }
  }, true);
}

async function scRestoreWing(wingId, wingCode){
  try {
    await api(`/api/wings/${wingId}/restore`,{method:'POST'});
    showToast(`Wing '${wingCode}' restored.`);
    await _refreshOrgCache();
    scLoadScopeMap();
  } catch(e){ showToast('Restore failed: '+(apiErr(e)),true); }
}

function scArchiveSquadron(sqnId, sqnName){
  confirmAction(`Archive unit '${sqnName}'?\n\nThis will remove the unit from all active views. It can be restored later from the Scope Map.`, async()=>{
    try {
      await api(`/api/squadrons/${sqnId}/archive`,{method:'POST'});
      showToast(`Unit '${sqnName}' archived.`);
      await _refreshOrgCache();
      scLoadScopeMap();
    } catch(e){ showToast('Archive failed: '+(apiErr(e)),true); }
  }, true);
}

async function scRestoreSquadron(sqnId, sqnName){
  try {
    await api(`/api/squadrons/${sqnId}/restore`,{method:'POST'});
    showToast(`Unit '${sqnName}' restored.`);
    await _refreshOrgCache();
    scLoadScopeMap();
  } catch(e){ showToast('Restore failed: '+(apiErr(e)),true); }
}

async function scPopulateWingSelect(){
  const sel=document.getElementById('sc-sqn-wing'); if(!sel) return;
  try {
    const wings=await api('/api/wings');
    sel.innerHTML='<option value="">Select wing…</option>';
    for(const w of (wings||[])){
      const o=document.createElement('option');
      o.value=w.wing_id; o.textContent=`${w.code||''} — ${w.name||w.wing_id}`;
      sel.appendChild(o);
    }
  } catch(e){ sel.innerHTML='<option value="">Could not load wings — refresh the page</option>'; }
}

async function scCreateWing(){
  const code=(document.getElementById('sc-wing-code').value||'').trim();
  const name=(document.getElementById('sc-wing-name').value||'').trim();
  const short=(document.getElementById('sc-wing-short').value||'').trim();
  const msg=document.getElementById('sc-wing-msg');
  if(!code||!name){ msg.textContent='Wing Code and Full Name are required.'; msg.style.color='var(--danger)'; return; }
  msg.style.color='var(--muted)'; msg.textContent='Creating…';
  try {
    const d=await api('/api/wings',{method:'POST',body:JSON.stringify({code,name,short_name:short||null})});
    msg.style.color='var(--ok)'; msg.textContent=`Wing '${d.code}' created.`;
    document.getElementById('sc-wing-code').value='';
    document.getElementById('sc-wing-name').value='';
    document.getElementById('sc-wing-short').value='';
    await _refreshOrgCache();
    scLoadScopeMap();
  } catch(e){ msg.style.color='var(--danger)'; msg.textContent='Error: '+(apiErr(e)); }
}

async function scCreateSquadron(){
  const wing_id=document.getElementById('sc-sqn-wing').value;
  const code=(document.getElementById('sc-sqn-code').value||'').trim();
  const name=(document.getElementById('sc-sqn-name').value||'').trim();
  const unit_type=document.getElementById('sc-sqn-type').value;
  const msg=document.getElementById('sc-sqn-msg');
  if(!wing_id||!code||!name){ msg.textContent='Wing, Unit Code and Full Name are required.'; msg.style.color='var(--danger)'; return; }
  msg.style.color='var(--muted)'; msg.textContent='Creating…';
  try {
    const d=await api('/api/squadrons',{method:'POST',body:JSON.stringify({wing_id,code,name,unit_type})});
    msg.style.color='var(--ok)'; msg.textContent=`Unit '${d.code}' created.`;
    document.getElementById('sc-sqn-code').value='';
    document.getElementById('sc-sqn-name').value='';
    await _refreshOrgCache();
    scLoadScopeMap();
  } catch(e){ msg.style.color='var(--danger)'; msg.textContent='Error: '+(apiErr(e)); }
}

async function scLoadMaintenance(){
  const el=document.getElementById('sc-maint-body'); if(!el) return;
  try {
    const d=await api('/api/system/maintenance');
    let h='';
    if(d.enabled){
      const phase=d.phase||'locked';
      const isPending=phase==='pending';
      const phaseLabel=isPending
        ?'<span class="sc-status-warn">PENDING (drain window active — writes not yet blocked)</span>'
        :'<span class="sc-status-err">LOCKED (write-block active)</span>';
      h+=`<div class="sc-maint-on">Maintenance mode is ON — Phase: ${phaseLabel}</div>`;
      if(isPending&&d.pending_until)h+=`<div class="muted" style="font-size:var(--fs-sm);margin-bottom:4px">Write-block starts: ${esc(d.pending_until)}</div>`;
      if(d.message) h+=`<div class="muted" style="font-size:var(--fs-sm);margin-bottom:4px">Message: ${esc(d.message)}</div>`;
      if(d.until) h+=`<div class="muted" style="font-size:var(--fs-sm);margin-bottom:4px">Expected return: ${esc(d.until)}</div>`;
      h+=`<div style="font-size:var(--fs-xs);margin:6px 0 10px;display:flex;gap:10px;flex-wrap:wrap">`;
      h+=`<span class="${d.block_logins?'sc-status-warn':'sc-status-ok'}">Logins: ${d.block_logins?'Blocked':'Allowed'}</span>`;
      h+=`<span class="${d.block_reads?'sc-status-warn':'sc-status-ok'}">Reads: ${d.block_reads?'Blocked':'Allowed'}</span>`;
      h+=`<span class="${isPending?'sc-status-ok':'sc-status-warn'}">Writes: ${isPending?'Allowed (pending)':'Blocked'}</span>`;
      h+=`</div>`;
      h+=`<button class="btn btn-secondary" onclick="scDisableMaint()">Disable Maintenance Mode</button>`;
    } else {
      h+=`<div style="font-size:var(--fs-sm);color:var(--ok);margin-bottom:10px">Maintenance mode is off. System is operating normally.</div>`;
      h+=`<button class="btn btn-secondary" onclick="document.getElementById('sc-maint-title').value='';document.getElementById('sc-maint-block-logins').checked=false;document.getElementById('sc-maint-block-reads').checked=false;document.getElementById('sc-maint-drain').value='20';document.getElementById('sc-maint-form').style.display='block';this.style.display='none'">Enable Maintenance Mode…</button>`;
    }
    el.innerHTML=h;
  } catch(e){ el.innerHTML=`<div class="sc-status-err">Could not load Maintenance status: ${esc(apiErr(e))}</div>`; }
}

async function scEnableMaint(){
  const title=document.getElementById('sc-maint-title').value.trim();
  const msg=document.getElementById('sc-maint-msg').value.trim();
  const until=document.getElementById('sc-maint-until').value.trim();
  const confirm=document.getElementById('sc-maint-confirm').value.trim();
  const blockLogins=document.getElementById('sc-maint-block-logins').checked;
  const blockReads=document.getElementById('sc-maint-block-reads').checked;
  const drainRaw=parseInt(document.getElementById('sc-maint-drain').value,10);
  const drainSecs=isNaN(drainRaw)?20:Math.max(0,Math.min(drainRaw,300));
  try {
    await api('/api/system/maintenance/enable',{method:'POST',body:JSON.stringify({
      title:title||null,message:msg||null,until:until||null,confirm,
      block_logins:blockLogins,block_reads:blockReads,drain_seconds:drainSecs
    })});
    document.getElementById('sc-maint-form').style.display='none';
    scLoadMaintenance();
    scLoadOverview();
    _pollMaintenanceStatus();
  } catch(e){ showToast('Could not enable maintenance mode: '+(apiErr(e)),true); }
}

function scDisableMaint(){
  confirmAction('Disable maintenance mode and restore normal access?', async()=>{
    try {
      await api('/api/system/maintenance/disable',{method:'POST'});
      scLoadMaintenance();
      scLoadOverview();
    } catch(e){ showToast('Could not disable maintenance mode: '+(apiErr(e)),true); }
  });
}

async function scLoadBackups(){
  const el=document.getElementById('sc-backup-body'); if(!el) return;
  const acts=document.getElementById('sc-backup-actions');
  try {
    const d=await api('/api/system/backups');
    const isPg=(d.db_type||'').toLowerCase().includes('postgres');
    if(isPg){
      el.innerHTML=`<div class="muted" style="font-size:var(--fs-sm)">Database: ${esc(d.db_type)}</div>
        <div style="margin-top:8px;font-size:var(--fs-sm)">Use the button below to download a pg_dump of the live database directly to your browser. No data is written to the server filesystem.</div>
        <div style="margin-top:6px;font-size:var(--fs-xs);color:var(--muted)">To restore: <code>pg_restore --clean --if-exists -d &quot;DATABASE_URL&quot; filename.dump</code><br>
        This is a controlled CLI operation. Do not share the dump file outside authorised personnel.</div>`;
      if(acts) acts.innerHTML='<button id="sc-pgdump-btn" class="btn btn-secondary" onclick="scDownloadPgDump()">Download PostgreSQL Backup (pg_dump)</button>';
    } else {
      if(!d.backups||!d.backups.length){
        el.innerHTML='<div class="muted">No backups found in <code>'+esc(d.backup_dir||'./backups')+'</code>.</div>';
      } else {
        let h=`<div class="muted" style="font-size:var(--fs-xs);margin-bottom:8px">Backup directory: <code>${esc(d.backup_dir)}</code></div>`;
        for(const b of d.backups){
          const kb=b.size_bytes?Math.round(b.size_bytes/1024)+'KB':'';
          h+=`<div class="sc-backup-item"><span class="sc-filename">${esc(b.filename)}</span><span class="sc-bsize">${kb}</span><span class="muted">${b.created_at?esc(b.created_at.slice(0,19).replace('T',' '))+'Z':''}</span></div>`;
        }
        el.innerHTML=h;
      }
      if(acts) acts.innerHTML='<button class="btn btn-secondary" onclick="scCreateBackup()">Create Backup Now</button>';
    }
  } catch(e){ el.innerHTML=`<div class="sc-status-err">Could not load Backups: ${esc(apiErr(e))}</div>`; }
}

async function scCreateBackup(){
  try {
    const d=await api('/api/system/backups',{method:'POST'});
    showToast('Backup created: '+d.filename+' ('+Math.round((d.size_bytes||0)/1024)+'KB)');
    scLoadBackups(); scLoadOverview();
  } catch(e){ showToast('Backup failed: '+apiErr(e),true); }
}

async function scDownloadPgDump(){
  const btn=document.getElementById('sc-pgdump-btn');
  if(btn){btn.disabled=true;btn.textContent='Preparing download…';}
  try{
    const t=tokenGet();
    const headers=t?{'Authorization':'Bearer '+t}:{};
    const res=await fetch(API_BASE+'/api/system/backups/pg-dump',{headers,credentials:'include'});
    if(!res.ok){
      const body=await res.json().catch(()=>({}));
      const msg=(body&&body.detail&&body.detail.message)||(typeof body.detail==='string'&&body.detail)||'Backup failed. Check the server status and try again.';
      showToast('Backup download failed: '+msg,true);
      return;
    }
    const blob=await res.blob();
    const url=URL.createObjectURL(blob);
    const a=document.createElement('a');
    const cd=res.headers.get('Content-Disposition')||'';
    const m=cd.match(/filename="([^"]+)"/);
    a.href=url; a.download=m?m[1]:'aafc_tms_backup.dump';
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    URL.revokeObjectURL(url);
    scLoadOverview();
  }catch(e){showToast('Backup download failed: '+apiErr(e),true);}
  finally{if(btn){btn.disabled=false;btn.textContent='Download PostgreSQL Backup (pg_dump)';}}
}

async function scLoadAudit(){
  const el=document.getElementById('sc-audit-body'); if(!el) return;
  const action=document.getElementById('sc-audit-action');
  const q=action&&action.value?'?action='+encodeURIComponent(action.value)+'&limit=50':'?limit=50';
  try {
    const d=await api('/api/system/audit-summary'+q);
    if(!d.logs||!d.logs.length){ el.innerHTML='<div class="muted">No audit entries found.</div>'; return; }
    let h='<div style="font-family:monospace;font-size:var(--fs-xs)">';
    for(const e of d.logs){
      const ts=(e.timestamp||'').slice(0,19).replace('T',' ');
      const role=e.role||'—'; const act=e.action||'—'; const obj=e.object_type||''; const oid=(e.object_id||'').slice(0,12);
      h+=`<div class="sc-audit-row">
        <span style="color:var(--muted)">${esc(ts)}</span>
        <span style="color:var(--steel)">${esc(role)}</span>
        <span style="color:var(--dark)">${esc(act)}</span>
        <span style="color:var(--muted)">${esc(obj)} ${esc(oid)}</span>
      </div>`;
    }
    h+='</div>';
    el.innerHTML=h;
  } catch(e){ el.innerHTML=`<div class="sc-status-err">Could not load the Audit summary: ${esc(apiErr(e))}</div>`; }
}

async function scLoadSdEmailConfig(){
  const el=document.getElementById('sc-sd-email-body'); if(!el) return;
  el.innerHTML='<div class="muted">Loading…</div>';
  try {
    const configs=await api('/api/service-desk/email-config');
    const byScope={};
    for(const c of configs) byScope[c.scope+(c.wing_id||'')]=c;

    // Fetch wings for the wing section (SA only)
    let wings=[];
    if(S&&S.role==='system_admin'){
      try{ wings=S.wings||[]; } catch(e){}
    }

    let h='';
    const row=(label,scope,wingId)=>{
      const key=scope+(wingId||'');
      const cur=byScope[key];
      const val=cur?esc(cur.notification_email):'';
      const wParam=wingId?`,'${esc(wingId)}'`:'';
      return `<div style="display:grid;grid-template-columns:160px 1fr auto;gap:var(--sp-sm);align-items:center;margin-bottom:var(--sp-xs)">
        <label for="sd-email-cfg-${esc(key)}" style="font-size:var(--fs-xs);font-weight:600">${esc(label)}</label>
        <input type="email" class="ff-input" style="font-size:var(--fs-sm);padding:5px 8px" value="${val}"
          placeholder="not configured" id="sd-email-cfg-${esc(key)}" autocomplete="off">
        <button class="btn btn-secondary" style="font-size:var(--fs-xs);padding:4px 10px;white-space:nowrap"
          onclick="scSaveSdEmail('${esc(scope)}',document.getElementById('sd-email-cfg-${esc(key)}').value${wParam})">Save</button>
      </div>`;
    };

    h+=`<div style="font-size:var(--fs-2xs);font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--steel);margin-bottom:4px">System Admin</div>`;
    h+=row('System Admin','system',null);
    h+=`<div style="font-size:var(--fs-2xs);font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--steel);margin:var(--sp-sm) 0 4px">National HQ</div>`;
    h+=row('National HQ','national',null);
    if(wings.length){
      h+=`<div style="font-size:var(--fs-2xs);font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--steel);margin:var(--sp-sm) 0 4px">Wing Notifications</div>`;
      for(const w of wings) h+=row(esc(w.short_name||w.name),'wing',w.wing_id);
    }
    el.innerHTML=h;
  } catch(e){ el.innerHTML=`<div style="color:var(--red);font-size:var(--fs-sm)">${esc(apiErr(e))}</div>`; }
}

async function scSaveSdEmail(scope, email, wingId){
  try {
    const body={scope, notification_email:email};
    if(wingId) body.wing_id=wingId;
    await api('/api/service-desk/email-config',{method:'PUT',body});
    showToast('Notification email saved.');
    scLoadSdEmailConfig();
  } catch(e){ showToast(apiErr(e),true); }
}

let _scCurriculumPreviewReady=false;

async function _scCurriculumXlsmRequest(preview){
  const input=document.getElementById('sc-curr-import-file');
  if(!input||!input.files||!input.files[0]) throw new Error('Select a workbook first.');
  const file=input.files[0];
  const form=new FormData();
  form.append('file',file);
  const base=document.querySelector('meta[name="aafc-api-base"]')?.content||'';
  const token=tokenGet();
  const suffix=preview?'?preview=true':'';
  const r=await fetch(base+'/api/curriculum/import-xlsm'+suffix,{
    method:'POST',
    headers:{'Authorization':'Bearer '+token},
    body:form,
  });
  let d={};
  try{ d=await r.json(); }catch(_){}
  if(!r.ok){
    const msg=d.detail?.message||d.detail?.error||'An error occurred. Check the file format.';
    throw new Error(msg);
  }
  return d;
}

function _scRenderCurriculumSummary(d, preview){
  const results=document.getElementById('sc-curr-import-results');
  const failed=(d.results||[]).filter(x=>x.status==='failed');
  let html='<div style="margin-top:4px">';
  html+=`<strong>${preview?'Preview':'Committed'}:</strong> created ${Number(d.created||0)}, updated ${Number(d.updated||0)}, skipped ${Number(d.skipped||0)}, failed ${Number(d.failed||0)} of ${Number(d.total||0)}.`;
  if(failed.length){
    html+='<div style="color:var(--red);margin-top:6px">Failures:<br>'+
      failed.map(x=>`${esc(x.identifier||x.code||'row')}: ${esc(x.error||'Import failed')}`).join('<br>')+'</div>';
  }
  if(preview){
    html+='<div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap">'+
      '<button type="button" class="btn btn-primary" id="sc-curr-import-commit" onclick="scCommitCurriculum()">Commit import</button>'+
      '<button type="button" class="btn btn-secondary" onclick="scCancelCurriculumPreview()">Cancel</button>'+
      '</div>';
  }
  html+='</div>';
  results.innerHTML=html;
}

async function scPreviewCurriculum(){
  const input=document.getElementById('sc-curr-import-file');
  const msg=document.getElementById('sc-curr-import-msg');
  const results=document.getElementById('sc-curr-import-results');
  const fname=document.getElementById('sc-curr-import-filename');
  if(!input||!input.files||!input.files[0]) return;
  _scCurriculumPreviewReady=false;
  fname.textContent=input.files[0].name;
  msg.textContent='Parsing and previewing — no changes will be written…';
  msg.style.color='var(--muted)';
  results.innerHTML='';
  try{
    const d=await _scCurriculumXlsmRequest(true);
    _scCurriculumPreviewReady=true;
    msg.textContent='Preview ready. Review the counts below before committing.';
    msg.style.color=Number(d.failed||0)>0?'var(--amber)':'var(--ok)';
    _scRenderCurriculumSummary(d,true);
  }catch(e){
    msg.textContent='Preview failed: '+apiErr(e);
    msg.style.color='var(--red)';
    input.value='';
    fname.textContent='';
  }
}

// Backward-compatible name retained for any automation/bookmark that called the
// old function directly. It now performs the safe preview stage only.
async function scImportCurriculum(){
  return scPreviewCurriculum();
}

async function scCommitCurriculum(){
  const input=document.getElementById('sc-curr-import-file');
  const msg=document.getElementById('sc-curr-import-msg');
  const results=document.getElementById('sc-curr-import-results');
  const fname=document.getElementById('sc-curr-import-filename');
  if(!_scCurriculumPreviewReady||!input||!input.files||!input.files[0]){
    msg.textContent='Preview the workbook before committing.';
    msg.style.color='var(--red)';
    return;
  }
  const btn=document.getElementById('sc-curr-import-commit');
  if(btn){btn.disabled=true;btn.textContent='Committing…';}
  msg.textContent='Committing reviewed curriculum changes…';
  msg.style.color='var(--muted)';
  try{
    const d=await _scCurriculumXlsmRequest(false);
    _scCurriculumPreviewReady=false;
    msg.textContent=`Import complete — created: ${d.created}, updated: ${d.updated}, skipped: ${d.skipped}, failed: ${d.failed} of ${d.total}`;
    msg.style.color=Number(d.failed||0)>0?'var(--amber)':'var(--ok)';
    _scRenderCurriculumSummary(d,false);
    try{const cur=await api('/api/curriculum');S.curr=((cur&&cur.items)||[]).map(_mapCurrItem);}catch(_){}
    input.value='';
    fname.textContent='';
  }catch(e){
    msg.textContent='Import failed: '+apiErr(e);
    msg.style.color='var(--red)';
    if(btn){btn.disabled=false;btn.textContent='Commit import';}
  }
}

function scCancelCurriculumPreview(){
  const input=document.getElementById('sc-curr-import-file');
  _scCurriculumPreviewReady=false;
  if(input) input.value='';
  const fname=document.getElementById('sc-curr-import-filename');
  const msg=document.getElementById('sc-curr-import-msg');
  const results=document.getElementById('sc-curr-import-results');
  if(fname) fname.textContent='';
  if(msg) msg.textContent='Preview cancelled. No curriculum changes were written.';
  if(results) results.innerHTML='';
}

async function scBootstrapStaging(){
  const msg=document.getElementById('sc-bootstrap-msg');
  msg.textContent='Creating accounts…'; msg.style.color='var(--muted)';
  try{
    const r=await api('/api/system/bootstrap-staging',{method:'POST'});
    msg.textContent='';
    const all=r.results||[];
    const codes=r.accounts_created||[];
    let html='<table style="width:100%;border-collapse:collapse;font-size:var(--fs-sm);margin-bottom:14px"><thead>';
    html+='<tr style="border-bottom:1px solid var(--border)"><th style="text-align:left;padding:4px 8px">Type</th><th style="text-align:left;padding:4px 8px">Name / Code</th><th style="text-align:left;padding:4px 8px">Result</th></tr></thead><tbody>';
    for(const x of all){
      const created=x.created?'<span style="color:var(--ok);font-weight:700">Created</span>':'<span style="color:var(--muted)">Already existed</span>';
      const label=x.display_name||x.name||x.code||'';
      html+=`<tr><td style="padding:4px 8px;text-transform:capitalize">${esc(x.type)}</td><td style="padding:4px 8px">${esc(label)}</td><td style="padding:4px 8px">${created}</td></tr>`;
    }
    html+='</tbody></table>';
    if(codes.length){
      html+='<div style="font-size:var(--fs-sm);font-weight:700;margin-bottom:10px">Access codes — copy all now, they will not appear again:</div>';
      for(const a of codes){
        html+=`<div style="margin-bottom:12px">
          <div style="font-size:var(--fs-xs);color:var(--muted);margin-bottom:4px">${esc(_ROLE_LABELS[a.role]||a.role)} — ${esc(a.display_name)}</div>
          <div style="background:#1a1a2e;color:#7efff5;font-family:monospace;font-size:var(--fs-2xl);font-weight:900;letter-spacing:3px;text-align:center;padding:12px;border-radius:6px;user-select:all">${esc(a.new_code)}</div>
        </div>`;
      }
    } else {
      html+='<div class="alert a-info" style="font-size:var(--fs-sm)">All accounts already existed — no new codes generated.</div>';
    }
    document.getElementById('m-bootstrap-results').innerHTML=html;
    openModal('m-bootstrap-codes');
    scLoadOverview();
  }catch(e){ msg.textContent=apiErr(e); msg.style.color='var(--red)'; }
}
