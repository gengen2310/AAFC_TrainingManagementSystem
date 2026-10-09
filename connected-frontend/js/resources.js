// Main TMS module: Locations and Resources -- rooms and equipment.
// Extracted verbatim from connected-frontend/index.html (stabilisation Phase 4,
// C6). Top-level function declarations and side-effect-free let/const only;
// loaded as a classic script BEFORE the inline bootstrap, so everything here
// is defined before any page-load code runs. Statements with load-time
// effects stay in index.html in their original order. Parity is proven by
// tools/architecture/frontend_parity.mjs.

// ═══════════════════════════════════════════════════════════
//  RESOURCES
// ═══════════════════════════════════════════════════════════
let _archivedRoomList=null, _archivedEquipList=null;
async function _resToggleShowArchived(type){
  const elId=type==='room'?'room-show-archived':'equip-show-archived';
  const checked=(document.getElementById(elId)||{}).checked;
  if(!checked){ renderRooms(); return; }
  try{
    if(type==='room'){
      const rows=await api('/api/training-areas?include_archived=true');
      _archivedRoomList=(rows||[]).filter(r=>r.is_archived).map(r=>({id:r.training_area_id,name:r.name,capacity:r.capacity,type:r.type,notes:r.notes||''}));
    } else {
      const rows=await api('/api/equipment?include_archived=true');
      _archivedEquipList=(rows||[]).filter(e=>e.is_archived).map(e=>({id:e.equipment_id,name:e.name,qty:e.quantity,notes:e.notes||''}));
    }
  }catch(ex){ showToast('Could not load archived items: '+apiErr(ex), true); }
  renderRooms();
}
async function doRestoreRoom(id, name){
  try{
    await api(`/api/training-areas/${id}/restore`,{method:'POST'});
    showToast(`'${name}' restored.`);
    await loadData();
    const rows=await api('/api/training-areas?include_archived=true');
    _archivedRoomList=(rows||[]).filter(r=>r.is_archived).map(r=>({id:r.training_area_id,name:r.name,capacity:r.capacity,type:r.type,notes:r.notes||''}));
    renderRooms();
  }catch(ex){ showToast('Could not restore: '+apiErr(ex), true); }
}
async function doRestoreEquip(id, name){
  try{
    await api(`/api/equipment/${id}/restore`,{method:'POST'});
    showToast(`'${name}' restored.`);
    await loadData();
    const rows=await api('/api/equipment?include_archived=true');
    _archivedEquipList=(rows||[]).filter(e=>e.is_archived).map(e=>({id:e.equipment_id,name:e.name,qty:e.quantity,notes:e.notes||''}));
    renderRooms();
  }catch(ex){ showToast('Could not restore: '+apiErr(ex), true); }
}
function renderRooms(){
  const showRooms=(document.getElementById('room-show-archived')||{}).checked;
  const roomSrc=showRooms?(_archivedRoomList||[]):S.rooms;
  document.getElementById('room-tbody').innerHTML=roomSrc.map((r,i)=>`<tr${showRooms?' style="opacity:.6"':''}>
    <td style="font-weight:700">${esc(r.name)}${showRooms?' <span class="badge b-grey">Archived</span>':''}</td>
    <td style="text-align:center">${r.capacity||'—'}</td>
    <td>${r.type?`<span class="badge b-blue" style="font-size:var(--fs-2xs)">${esc(r.type)}</span>`:'—'}</td>
    <td class="no-print">${showRooms
      ?(canWriteSquadron()?`<button class="btn btn-xs btn-ok" onclick="doRestoreRoom('${r.id}','${_jsAttr(r.name)}')">Restore</button>`:'')
      :(canWriteSquadron()?`<button class="btn btn-xs btn-sky" onclick="editRoom('${r.id}')">Edit</button> <button class="btn btn-xs btn-red" aria-label="Archive training area" onclick="delRoom('${r.id}')">×</button>`:'—')}</td>
  </tr>`).join('')||`<tr><td colspan="4" style="color:var(--muted);text-align:center;padding:14px">No ${showRooms?'archived ':''}training areas.</td></tr>`;
  const showEquip=(document.getElementById('equip-show-archived')||{}).checked;
  const equipSrc=showEquip?(_archivedEquipList||[]):S.equip;
  document.getElementById('equip-tbody').innerHTML=equipSrc.map((eq,i)=>`<tr${showEquip?' style="opacity:.6"':''}>
    <td style="font-weight:700">${esc(eq.name)}${showEquip?' <span class="badge b-grey">Archived</span>':''}</td>
    <td style="text-align:center">${eq.qty||'—'}</td>
    <td style="font-size:var(--fs-xs);color:var(--muted)">${esc(eq.notes||'')}</td>
    <td class="no-print">${showEquip
      ?(canWriteSquadron()?`<button class="btn btn-xs btn-ok" onclick="doRestoreEquip('${eq.id}','${_jsAttr(eq.name)}')">Restore</button>`:'')
      :(canWriteSquadron()?`<button class="btn btn-xs btn-sky" onclick="editEquip('${eq.id}')">Edit</button> <button class="btn btn-xs btn-red" aria-label="Archive equipment" onclick="delEquip('${eq.id}')">×</button>`:'—')}</td>
  </tr>`).join('')||`<tr><td colspan="4" style="color:var(--muted);text-align:center;padding:14px">No ${showEquip?'archived ':''}equipment.</td></tr>`;
}
function openAddRoomModal(){
  editRoomId=null;
  document.getElementById('room-modal-title').textContent='+ Add Room / Training Area';
  document.getElementById('room-name').value='';
  document.getElementById('room-cap').value='20';
  document.getElementById('room-type').value='Indoor';
  document.getElementById('room-notes').value='';
  _renderRoomCapabilities([]);
  openModal('m-add-room');
}
function _renderRoomCapabilities(selected){
  // Render capability checkboxes from S.trainingAreaCapabilityTags.
  const caps=S.trainingAreaCapabilityTags||[];
  const sel=new Set(Array.isArray(selected)?selected:[]);
  const wrap=document.getElementById('room-capabilities'); if(!wrap)return;
  if(!caps.length){ wrap.innerHTML='<span style="font-size:var(--fs-xs);color:var(--muted)">No capabilities defined yet.</span>'; return; }
  wrap.innerHTML=caps.map(c=>{
    const checked=sel.has(c.display_name)?'checked':'';
    return `<label style="display:inline-flex;align-items:center;gap:4px;font-size:var(--fs-xs);cursor:pointer;background:var(--surface-2);border:1px solid var(--border);border-radius:6px;padding:3px 8px"><input type="checkbox" value="${esc(c.display_name)}" ${checked} style="margin:0"> ${esc(c.display_name)}</label>`;
  }).join('');
}
function _collectRoomCapabilities(){
  const wrap=document.getElementById('room-capabilities'); if(!wrap)return[];
  return [...wrap.querySelectorAll('input[type=checkbox]:checked')].map(cb=>cb.value);
}
async function saveRoom(){
  const name=document.getElementById('room-name').value.trim();
  if(!name){showToast('Room name required.',true);return;}
  const capabilities=_collectRoomCapabilities();
  const payload={name,capacity:+document.getElementById('room-cap').value||null,type:document.getElementById('room-type').value||null,notes:document.getElementById('room-notes').value||null,capabilities};
  try{
    const isEditRoom=!!editRoomId;
    if(editRoomId){ await api('/api/training-areas/'+editRoomId,{method:'PATCH',body:JSON.stringify(payload)}); editRoomId=null; }
    else { await api('/api/training-areas',{method:'POST',body:JSON.stringify(payload)}); }
    await reloadAndRender(); showToast(isEditRoom?'Room updated.':'Room added.'); closeModal('m-add-room');
    document.getElementById('room-modal-title').textContent='+ Add Room / Training Area';
  }catch(e){ showToast(apiErr(e),true); }
}
function editRoom(id){
  const r=S.rooms.find(x=>x.id===id);if(!r)return;editRoomId=id;
  document.getElementById('room-modal-title').textContent='Edit Room';
  document.getElementById('room-name').value=r.name;document.getElementById('room-cap').value=r.capacity;
  document.getElementById('room-type').value=r.type;document.getElementById('room-notes').value=r.notes||'';
  _renderRoomCapabilities(r.capabilities||[]);
  openModal('m-add-room');
}
async function delRoom(id){
  confirmAction('Archive this training area? It will no longer appear in active lists, but existing records are unaffected.',async()=>{
    try{ await api('/api/training-areas/'+id,{method:'DELETE'}); await reloadAndRender(); }
    catch(e){ showToast(apiErr(e),true); }
  });
}
async function saveEquip(){
  const name=document.getElementById('equip-name').value.trim();
  if(!name){showToast('Equipment name required.',true);return;}
  const payload={name,quantity:+document.getElementById('equip-qty').value||1,notes:document.getElementById('equip-notes').value||null};
  try{
    const isEditEquip=!!editEquipId;
    if(editEquipId){ await api('/api/equipment/'+editEquipId,{method:'PATCH',body:JSON.stringify(payload)}); editEquipId=null; }
    else { await api('/api/equipment',{method:'POST',body:JSON.stringify(payload)}); }
    await reloadAndRender(); showToast(isEditEquip?'Equipment updated.':'Equipment added.'); closeModal('m-add-equip');
    document.getElementById('equip-modal-title').textContent='+ Add Equipment';
  }catch(e){ showToast(apiErr(e),true); }
}
// Mirrors openAddRoomModal() directly above. Without it, "+ Add Equipment"
// opened the modal still holding the item editEquip() last loaded, with
// editEquipId still set -- so Save issued a PATCH and renamed that item instead
// of adding a new one. Rooms already had this; equipment did not. Same defect
// as REM-147 on activities.
function openAddEquipModal(){
  editEquipId=null;
  document.getElementById('equip-modal-title').textContent='+ Add Equipment';
  document.getElementById('equip-name').value='';
  document.getElementById('equip-qty').value='1';
  document.getElementById('equip-notes').value='';
  openModal('m-add-equip');
}
function editEquip(id){
  const eq=S.equip.find(x=>x.id===id);if(!eq)return;editEquipId=id;
  document.getElementById('equip-modal-title').textContent='Edit Equipment';
  document.getElementById('equip-name').value=eq.name;document.getElementById('equip-qty').value=eq.qty;
  document.getElementById('equip-notes').value=eq.notes||'';openModal('m-add-equip');
}
async function delEquip(id){
  confirmAction('Archive this equipment item? It will no longer appear in active lists, but existing records are unaffected.',async()=>{
    try{ await api('/api/equipment/'+id,{method:'DELETE'}); await reloadAndRender(); }
    catch(e){ showToast(apiErr(e),true); }
  });
}
