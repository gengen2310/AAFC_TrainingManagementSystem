// Main TMS module: planning spreadsheet export and schedule XLSX import.
// Extracted verbatim from connected-frontend/index.html (stabilisation Phase 4,
// C6). Top-level function declarations and side-effect-free let/const only;
// loaded as a classic script BEFORE the inline bootstrap, so everything here
// is defined before any page-load code runs. Statements with load-time
// effects stay in index.html in their original order. Parity is proven by
// tools/architecture/frontend_parity.mjs.

// ── Spreadsheet Export ──────────────────────────────────────
function _downloadExport(url, filename){
  const tok=tokenGet();
  fetch(API_BASE+url,{headers:{'Authorization':'Bearer '+tok}})
    .then(r=>{
      if(!r.ok) return r.json().then(d=>{ throw new Error(d.detail?.message||d.detail?.error||r.statusText); });
      return r.blob();
    })
    .then(blob=>{
      const a=document.createElement('a');
      a.href=URL.createObjectURL(blob);
      a.download=filename;
      document.body.appendChild(a); a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(a.href);
    })
    .catch(e=>showToast('Export failed: '+apiErr(e),true));
}

function exportAnnualProgram(){
  if(!P.currentYearId){ showToast('Select a year from the dropdown above before continuing.',true); return; }
  _downloadExport(`/api/planning/years/${P.currentYearId}/export.xlsx`,`annual-program.xlsx`);
}

function exportCurriculum(){
  _downloadExport('/api/curriculum/export.xlsx','curriculum.xlsx');
}

function exportSchedule(){
  if(!P.currentYearId){ showToast('Select a year from the dropdown above before continuing.',true); return; }
  _downloadExport(`/api/planning/years/${P.currentYearId}/schedule/export.xlsx`,`schedule.xlsx`);
}

// ── Schedule XLSX Import ────────────────────────────────────
function openSchedImport(){
  if(!P.currentYearId){ showToast('Select a year from the dropdown above before continuing.',true); return; }
  document.getElementById('sched-import-file').value='';
  document.getElementById('sched-import-msg').textContent='';
  document.getElementById('sched-import-preview').style.display='none';
  document.getElementById('sched-import-commit-btn').style.display='none';
  document.getElementById('sched-import-preview-btn').style.display='inline-flex';
  openModal('m-sched-import');
}

async function previewSchedImport(){
  const msg=document.getElementById('sched-import-msg');
  const fileEl=document.getElementById('sched-import-file');
  if(!fileEl.files||!fileEl.files[0]){ msg.textContent='Select an XLSX file first.'; return; }
  if(!P.currentYearId){ msg.textContent='Select a year from the dropdown above to continue.'; return; }
  msg.textContent='Parsing…';
  const form=new FormData();
  form.append('file',fileEl.files[0]);
  try{
    const res=await fetch(API_BASE+`/api/planning/years/${P.currentYearId}/schedule/import?preview=true`,{
      method:'POST',
      headers:{'Authorization':'Bearer '+tokenGet()},
      body:form,
    });
    const d=await res.json();
    if(!res.ok){ msg.textContent=d.detail?.message||d.detail?.error||'Request failed.'; return; }
    msg.textContent='';
    const updateRows=d.rows.filter(r=>r.action==='update');
    const summary=`${updateRows.length} change(s) to apply · ${d.rows.filter(r=>r.action==='unchanged').length} unchanged · ${d.not_found} not found`;
    document.getElementById('sched-import-summary').textContent=summary;
    const tbody=document.getElementById('sched-import-rows');
    const ACTION_CLR={update:'color:var(--royal);font-weight:600',unchanged:'color:var(--muted)',not_found:'color:var(--error)'};
    tbody.innerHTML=d.rows.map(r=>`<tr>
      <td style="padding:3px 8px;border-bottom:1px solid var(--border)">${esc(r.date||'')}</td>
      <td style="padding:3px 8px;border-bottom:1px solid var(--border)">${esc(String(r.session||''))}</td>
      <td style="padding:3px 8px;border-bottom:1px solid var(--border)">${esc(r.group||'')}</td>
      <td style="padding:3px 8px;border-bottom:1px solid var(--border);${ACTION_CLR[r.action]||''}">${esc(r.action||'')}</td>
      <td style="padding:3px 8px;border-bottom:1px solid var(--border);color:var(--muted)">${esc(r.current_code||'')}</td>
      <td style="padding:3px 8px;border-bottom:1px solid var(--border)">${esc(r.code||'')}</td>
      <td style="padding:3px 8px;border-bottom:1px solid var(--border)">${esc(r.title||'')}</td>
    </tr>`).join('');
    document.getElementById('sched-import-preview').style.display='';
    document.getElementById('sched-import-commit-btn').style.display=updateRows.length?'inline-flex':'none';
  }catch(e){ msg.textContent=apiErr(e); }
}

async function commitSchedImport(){
  const msg=document.getElementById('sched-import-msg');
  const fileEl=document.getElementById('sched-import-file');
  if(!fileEl.files||!fileEl.files[0]||!P.currentYearId){ return; }
  msg.textContent='Applying changes…';
  const form=new FormData();
  form.append('file',fileEl.files[0]);
  try{
    const res=await fetch(API_BASE+`/api/planning/years/${P.currentYearId}/schedule/import?preview=false`,{
      method:'POST',
      headers:{'Authorization':'Bearer '+tokenGet()},
      body:form,
    });
    const d=await res.json();
    if(!res.ok){ msg.textContent=d.detail?.message||d.detail?.error||'Request failed.'; return; }
    msg.textContent=`Done: ${d.updated} session(s) updated, ${d.skipped} unchanged, ${d.not_found} not found.`;
    document.getElementById('sched-import-commit-btn').style.display='none';
  }catch(e){ msg.textContent=apiErr(e); }
}
