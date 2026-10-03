// Main TMS module: Curriculum > Import CSV.
// Extracted verbatim from connected-frontend/index.html (stabilisation step 4:
// modularise the monolith by extraction, never by addition). Loaded as a
// classic script after the main inline script, so its top-level functions and
// constants share the page's global scope exactly as before: the modal's
// onclick handlers and its dependencies (openModal, API_BASE, tokenGet, esc,
// reloadAndRender) resolve unchanged.

// ════════════════════════════
//  CSV CURRICULUM IMPORT
// ════════════════════════════

function openCsvCurrImport(){
  document.getElementById('csv-curr-file').value='';
  document.getElementById('csv-curr-msg').textContent='';
  document.getElementById('csv-curr-preview').style.display='none';
  document.getElementById('csv-curr-result').style.display='none';
  document.getElementById('csv-curr-commit-btn').style.display='none';
  document.getElementById('csv-curr-preview-btn').style.display='inline-flex';
  openModal('m-csv-curr-import');
}
const _CSV_CURR_ACTION_CLR={created:'color:var(--ok);font-weight:600',updated:'color:var(--royal);font-weight:600',skipped:'color:var(--muted)',failed:'color:var(--error);font-weight:600'};
async function _csvCurrRequest(preview){
  const msg=document.getElementById('csv-curr-msg');
  const fileEl=document.getElementById('csv-curr-file');
  const level=document.getElementById('csv-curr-level').value;
  if(!fileEl.files||!fileEl.files[0]){ msg.textContent='Select a CSV file first.'; return null; }
  msg.textContent=preview?'Parsing…':'Importing…';
  const form=new FormData();
  form.append('file',fileEl.files[0]);
  const res=await fetch(API_BASE+`/api/curriculum/import-csv?owning_level=${encodeURIComponent(level)}&preview=${preview}`,{
    method:'POST',
    headers:{'Authorization':'Bearer '+tokenGet()},
    body:form,
  });
  const d=await res.json();
  if(!res.ok){ msg.textContent=d.detail?.message||d.detail?.error||'Request failed.'; return null; }
  msg.textContent='';
  return d;
}
async function previewCsvCurr(){
  const d=await _csvCurrRequest(true);
  if(!d)return;
  const summary=`${d.created} to create · ${d.updated} to update · ${d.skipped} unchanged${d.failed?' · '+d.failed+' failed':''}`;
  document.getElementById('csv-curr-summary').textContent=summary;
  document.getElementById('csv-curr-rows').innerHTML=(d.results||[]).map(r=>`<tr>
    <td style="padding:3px 8px;border-bottom:1px solid var(--border)">${esc(r.code||'')}</td>
    <td style="padding:3px 8px;border-bottom:1px solid var(--border)">${esc(r.title||'')}</td>
    <td style="padding:3px 8px;border-bottom:1px solid var(--border)">${esc(r.phase||'')}</td>
    <td style="padding:3px 8px;border-bottom:1px solid var(--border);${_CSV_CURR_ACTION_CLR[r.status]||''}">${esc(r.status||'')}${r.error?' — '+esc(r.error):''}</td>
  </tr>`).join('')||'<tr><td colspan="4" style="padding:8px;color:var(--muted)">No rows parsed.</td></tr>';
  document.getElementById('csv-curr-preview').style.display='';
  document.getElementById('csv-curr-commit-btn').style.display=(d.created+d.updated)>0?'inline-flex':'none';
  if(d.parse_errors&&d.parse_errors.length){
    document.getElementById('csv-curr-msg').innerHTML=`<span style="color:var(--warn-text)">${d.parse_errors.slice(0,5).map(e=>esc(e)).join('<br>')}</span>`;
  }
}
async function commitCsvCurr(){
  const d=await _csvCurrRequest(false);
  if(!d)return;
  const result=document.getElementById('csv-curr-result');
  result.innerHTML=`<div class="alert a-ok">Import complete: ${d.created} created, ${d.updated} updated, ${d.skipped} unchanged.${d.failed?' '+d.failed+' failed.':''}</div>`;
  result.style.display='block';
  document.getElementById('csv-curr-commit-btn').style.display='none';
  await reloadAndRender();
}
