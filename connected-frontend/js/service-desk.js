// Main TMS module: Service Desk -- request modal with unit typeahead, and the
// Service Desk page.
// Extracted verbatim from connected-frontend/index.html (stabilisation Phase 4,
// C6). Top-level function declarations and side-effect-free let/const only;
// loaded as a classic script BEFORE the inline bootstrap, so everything here
// is defined before any page-load code runs. Statements with load-time
// effects stay in index.html in their original order. Parity is proven by
// tools/architecture/frontend_parity.mjs.

// ── Unit typeahead state ─────────────────────────────────────────────────────
let _sdUnits = null;
let _sdUnitSelected = null; // {unit_id, name, type}
let _sdUnitFocusIdx = -1;

async function sdLoadUnits() {
  if (_sdUnits) return _sdUnits;
  try {
    const r = await fetch(API_BASE + '/api/public/units');
    if (!r.ok) throw new Error('Failed to load units');
    _sdUnits = await r.json();
  } catch (e) {
    _sdUnits = [];
  }
  return _sdUnits;
}

function sdUnitOpen() {
  sdUnitFilter();
}

function sdUnitFilter() {
  const input = document.getElementById('sd-unit-input');
  const dd = document.getElementById('sd-unit-dropdown');
  const q = (input.value || '').trim().toLowerCase();
  if (!_sdUnits) { sdLoadUnits().then(() => sdUnitFilter()); return; }
  const filtered = q
    ? _sdUnits.filter(u => u.name.toLowerCase().includes(q))
    : _sdUnits;
  if (!filtered.length) { dd.classList.remove('open'); return; }
  _sdUnitFocusIdx = -1;
  dd.innerHTML = filtered.slice(0, 40).map((u, i) =>
    `<div class="sd-unit-opt" data-uid="${esc(u.unit_id)}" data-uname="${esc(u.name)}" data-utype="${esc(u.type)}"
      onmousedown="sdUnitSelect('${esc(u.unit_id)}','${esc(u.name.replace(/'/g,"&#39;"))}','${esc(u.type)}')">
      <span class="sd-unit-type sd-unit-type-${esc(u.type)}">${esc(u.type === 'wing' ? 'Wing' : 'Sqn')}</span>
      ${esc(u.name)}
    </div>`
  ).join('');
  dd.classList.add('open');
}

function sdUnitSelect(uid, name, type) {
  _sdUnitSelected = {unit_id: uid, name, type};
  document.getElementById('sd-unit-input').value = name;
  document.getElementById('sd-unit-id').value = uid;
  document.getElementById('sd-unit-type').value = type;
  document.getElementById('sd-unit-dropdown').classList.remove('open');
}

function sdUnitKey(e) {
  const dd = document.getElementById('sd-unit-dropdown');
  const opts = dd.querySelectorAll('.sd-unit-opt');
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    _sdUnitFocusIdx = Math.min(_sdUnitFocusIdx + 1, opts.length - 1);
    opts.forEach((o, i) => o.classList.toggle('focused', i === _sdUnitFocusIdx));
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    _sdUnitFocusIdx = Math.max(_sdUnitFocusIdx - 1, 0);
    opts.forEach((o, i) => o.classList.toggle('focused', i === _sdUnitFocusIdx));
  } else if (e.key === 'Enter' && _sdUnitFocusIdx >= 0) {
    e.preventDefault();
    const opt = opts[_sdUnitFocusIdx];
    if (opt) sdUnitSelect(opt.dataset.uid, opt.dataset.uname, opt.dataset.utype);
  } else if (e.key === 'Escape') {
    dd.classList.remove('open');
  }
}

async function sdOpenModal(preselectedSquadronId) {
  const modal = document.getElementById('sd-modal');
  const form = document.getElementById('sd-form');
  const errEl = document.getElementById('sd-err');
  form.reset();
  errEl.style.display = 'none';
  document.getElementById('sd-submit-btn').disabled = false;
  _sdUnitSelected = null;
  document.getElementById('sd-unit-id').value = '';
  document.getElementById('sd-unit-type').value = '';
  document.getElementById('sd-unit-dropdown').classList.remove('open');

  // Pre-load units in background
  sdLoadUnits();

  // If sqn pre-selected (logged-in sqn_admin/sqn_general), pre-fill the typeahead
  if (preselectedSquadronId) {
    const units = await sdLoadUnits();
    const sqn = units.find(u => u.unit_id === preselectedSquadronId);
    if (sqn) {
      sdUnitSelect(sqn.unit_id, sqn.name, sqn.type);
      document.getElementById('sd-unit-input').disabled = true;
    }
  } else {
    document.getElementById('sd-unit-input').disabled = false;
  }

  modal.style.display = 'flex';
  document.getElementById('sd-category').focus();

  modal._escHandler = (e) => { if (e.key === 'Escape') sdCloseModal(); };
  document.addEventListener('keydown', modal._escHandler);
}

function sdCloseModal() {
  const modal = document.getElementById('sd-modal');
  modal.style.display = 'none';
  if (modal._escHandler) {
    document.removeEventListener('keydown', modal._escHandler);
    modal._escHandler = null;
  }
}

// SD-5: turn whatever the API returned into something the person filling in the
// form can act on. FastAPI sends 422 validation errors as a list of
// {loc:[...], msg}, which the previous handler could not read at all.
const _SD_FIELD_LABELS = {
  rank:'Rank', first_name:'First name', last_name:'Last name', email:'Email',
  category:'Category', description:'Description', squadron_id:'Unit', unit_name:'Unit',
};
function _sdErrorMessage(data, status){
  const d = data && data.detail;
  if (Array.isArray(d) && d.length) {
    const parts = d.slice(0, 3).map(e => {
      const field = Array.isArray(e.loc) ? e.loc[e.loc.length - 1] : '';
      const label = _SD_FIELD_LABELS[field] || field || 'This form';
      let why = String(e.msg || '').replace(/^Value error,\s*/i, '').trim();
      if (/valid email/i.test(why)) why = 'is not a valid email address';
      else if (/^field required$|^missing$/i.test(why)) why = 'is required';
      else if (/field is required and must not be blank/i.test(why)) why = 'is required';
      // The validator often names the field itself ("description must be at
      // least 10 characters"). Do not print the name twice.
      const bare = String(field).replace(/_/g, ' ');
      const rx = new RegExp('^' + bare.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\s+', 'i');
      if (rx.test(why)) why = why.replace(rx, '');
      why = why.charAt(0).toLowerCase() + why.slice(1);
      return `${label} ${why}`;
    });
    return parts.join('. ') + '.';
  }
  if (d && typeof d === 'object' && d.message) return d.message;
  if (typeof d === 'string' && d) return d;
  if (status === 403) return 'You do not have permission to submit this ticket.';
  return `Submission failed (${status}). Please check the form and try again.`;
}

async function sdSubmit(event) {
  event.preventDefault();
  const errEl = document.getElementById('sd-err');
  const submitBtn = document.getElementById('sd-submit-btn');
  errEl.style.display = 'none';
  submitBtn.disabled = true;

  // Validate unit selection
  if (!_sdUnitSelected) {
    errEl.textContent = 'Please select a unit from the list.';
    errEl.style.display = 'block';
    submitBtn.disabled = false;
    document.getElementById('sd-unit-input').focus();
    return;
  }

  const body = {
    rank: document.getElementById('sd-rank').value.trim(),
    first_name: document.getElementById('sd-first').value.trim(),
    last_name: document.getElementById('sd-last').value.trim(),
    email: document.getElementById('sd-email').value.trim(),
    category: document.getElementById('sd-category').value,
    description: document.getElementById('sd-desc').value.trim(),
  };

  // Set unit fields based on selection type
  if (_sdUnitSelected.type === 'squadron') {
    body.squadron_id = _sdUnitSelected.unit_id;
    body.unit_name = _sdUnitSelected.name;
  } else {
    body.wing_id = _sdUnitSelected.unit_id;
    body.unit_name = _sdUnitSelected.name;
  }

  try {
    const r = await fetch(API_BASE + '/api/service-desk/tickets', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });

    if (r.status === 201) {
      sdCloseModal();
      showToast('Ticket submitted.');
      return;
    }

    if (r.status === 429) {
      errEl.textContent = 'Too many requests — please wait before submitting again.';
      errEl.style.display = 'block';
    } else {
      const data = await r.json().catch(() => ({}));
      errEl.textContent = _sdErrorMessage(data, r.status);
      errEl.style.display = 'block';
    }
  } catch (e) {
    errEl.textContent = 'Network error — please try again.';
    errEl.style.display = 'block';
  }
  submitBtn.disabled = false;
}

// ── Service Desk page ────────────────────────────────────────────────────────
let _sdAllTickets = [];
let _sdActiveFilter = 'all';
let _sdActiveCategoryFilter = '';
let _sdActiveUnitFilter = '';
let _sdEditStatus = null;
let _sdSelectedTicketId = null;
let _sdAssignableAccounts = [];

function sdFmtDate(iso) {
  // Was: new Date(iso) then getUTCDate(). That parsed a naive UTC string as
  // local time and then read it back as UTC -- two errors that happened to
  // cancel into the UTC date, which is not the date the reader is living in.
  const d = parseServerTime(iso);
  if (!d) return '';
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return `${String(d.getDate()).padStart(2,'0')} ${months[d.getMonth()]} ${d.getFullYear()}`;
}

function sdStatusBadge(status) {
  const labels = {open: 'Open', in_progress: 'In Progress', resolved: 'Resolved'};
  const cls = {open: 'badge-open', in_progress: 'badge-in_progress', resolved: 'badge-resolved'}[status] || 'b-grey';
  return `<span class="badge ${cls}" style="font-size:var(--fs-3xs);padding:2px 6px;border-radius:4px;font-weight:700">${esc(labels[status] || status)}</span>`;
}

async function loadServiceDesk() {
  const tbody = document.getElementById('sd-tbody');
  const empty = document.getElementById('sd-empty');
  const filterBar = document.getElementById('sd-filter-bar');
  const table = document.getElementById('sd-table');
  tbody.innerHTML = '';
  empty.style.display = 'none';
  sdCloseDetail();

  if (S && S.role === 'sqn_general') {
    filterBar.style.display = 'none';
    table.style.display = 'none';
    empty.textContent = 'Use the Submit a Ticket button above to report an issue to your Wing.';
    empty.style.display = 'block';
    return;
  }

  filterBar.style.display = '';
  table.style.display = '';
  // sdRenderList() owns the empty-state wording from here on, since it is the
  // only thing that knows whether the list is empty or merely filtered.
  empty.textContent = 'No tickets yet.';
  // 7 columns since the colour-only status stripe column was removed.
  tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--muted);font-size:var(--fs-sm)">Loading…</td></tr>';

  try {
    const canAssign = S && ['system_admin','wing_admin','national_admin'].includes(S.role);
    const [r, accounts] = await Promise.all([
      api('/api/service-desk/tickets'),
      canAssign ? api('/api/accounts') : Promise.resolve([]),
    ]);
    _sdAllTickets = r;
    _sdAssignableAccounts = (accounts||[]).filter(a =>
      a.active_status && !a.is_archived &&
      ['system_admin','national_admin','wing_admin'].includes(a.role)
    );
    sdRenderList();
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="7" style="color:var(--red);font-size:var(--fs-sm)">${esc(apiErr(e))}</td></tr>`;
  }
}

function sdSetFilter(filter, btn) {
  _sdActiveFilter = filter;
  document.querySelectorAll('#sd-filter-bar button').forEach(b => {
    b.classList.remove('active');
    b.setAttribute('aria-pressed', 'false');
  });
  btn.classList.add('active');
  btn.setAttribute('aria-pressed', 'true');
  sdRenderList();
}

function sdSetCategoryFilter(val) {
  _sdActiveCategoryFilter = val;
  sdRenderList();
}

function sdSetUnitFilter(val) {
  _sdActiveUnitFilter = val;
  sdRenderList();
}

const _SD_CAT_LABELS = {
  account_access: 'Account Access', training_data: 'Training Data',
  technical_error: 'Technical Error', feature_request: 'Feature Request', other: 'Other',
};

function sdRenderList() {
  const tbody = document.getElementById('sd-tbody');
  const empty = document.getElementById('sd-empty');
  let filtered = _sdActiveFilter === 'all'
    ? _sdAllTickets
    : _sdAllTickets.filter(t => t.status === _sdActiveFilter);
  if (_sdActiveCategoryFilter) {
    filtered = filtered.filter(t => (t.category || 'other') === _sdActiveCategoryFilter);
  }
  if (_sdActiveUnitFilter) {
    filtered = filtered.filter(t => (t.unit_name || t.squadron_name || '') === _sdActiveUnitFilter);
  }

  sdRenderUnitFilter();
  const openCount = _sdAllTickets.filter(t => t.status === 'open').length;
  const countEl = document.getElementById('sd-count');
  if (countEl) {
    countEl.textContent = filtered.length === _sdAllTickets.length
      ? `${_sdAllTickets.length} ticket${_sdAllTickets.length === 1 ? '' : 's'} · ${openCount} open`
      : `${filtered.length} of ${_sdAllTickets.length} tickets · ${openCount} open`;
  }

  if (filtered.length === 0) {
    tbody.innerHTML = '';
    // "No tickets" and "nothing matches your filters" are different situations
    // and need different wording -- the second one tells you what to do next.
    empty.textContent = _sdAllTickets.length === 0
      ? 'No tickets yet.'
      : 'No tickets match these filters. Clear a filter to see the rest.';
    empty.style.display = 'block';
    document.getElementById('sd-table').style.display = 'none';
    return;
  }
  document.getElementById('sd-table').style.display = '';
  empty.style.display = 'none';

  tbody.innerHTML = filtered.map(t => {
    const desc = t.description.length > 60
      ? esc(t.description.slice(0, 60)) + '…'
      : esc(t.description);
    const active = t.ticket_id === _sdSelectedTicketId ? ' class="sd-row-active"' : '';
    const unitDisplay = esc(t.unit_name || t.squadron_name || '');
    const catLabel = esc(_SD_CAT_LABELS[t.category || 'other'] || 'Other');
    const assignee = t.assigned_to_name ? esc(t.assigned_to_name) : '<span style="color:var(--muted)">Unassigned</span>';
    // The row is a real activation target: Enter and Space open the ticket, so
    // the list is workable without a pointer.
    return `<tr${active} data-tid="${esc(t.ticket_id)}" tabindex="0" role="button"
      aria-label="Open ticket from ${esc(t.rank)} ${esc(t.first_name)} ${esc(t.last_name)}"
      onclick="sdOpenDetail(this.dataset.tid)"
      onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();sdOpenDetail(this.dataset.tid);}">
      <td style="font-size:var(--fs-sm);white-space:nowrap">${sdFmtDate(t.created_at)}</td>
      <td style="font-size:var(--fs-sm)">${esc(t.rank)} ${esc(t.first_name)} ${esc(t.last_name)}</td>
      <td style="font-size:var(--fs-sm)">${unitDisplay}</td>
      <td style="font-size:var(--fs-xs);color:var(--muted)">${catLabel}</td>
      <td style="font-size:var(--fs-sm)">${desc}</td>
      <td style="font-size:var(--fs-xs)">${assignee}</td>
      <td>${sdStatusBadge(t.status)}</td>
    </tr>`;
  }).join('');
}

function sdRenderUnitFilter() {
  const sel = document.getElementById('sd-unit-filter');
  if (!sel) return;
  const units = [...new Set(_sdAllTickets.map(t => t.unit_name || t.squadron_name || '').filter(Boolean))].sort();
  // A unit filter with one option filters nothing -- hide it rather than show a
  // control that cannot change the result.
  sel.style.display = units.length > 1 ? '' : 'none';
  const current = _sdActiveUnitFilter;
  if (sel.dataset.units === units.join('|')) { sel.value = current; return; }
  sel.dataset.units = units.join('|');
  sel.innerHTML = '<option value="">All units</option>' +
    units.map(u => `<option value="${esc(u)}">${esc(u)}</option>`).join('');
  sel.value = current;
}

let _sdModalWatched = false;
function sdWatchModal() {
  // The app's global Escape handler closes the topmost modal directly, without
  // going through sdCloseDetail(), which left the row highlight stuck on.
  // Watching the modal's own class means the highlight follows it however it
  // closes -- Close button, Escape, or a future path that does not exist yet.
  if (_sdModalWatched) return;
  const modal = document.getElementById('m-sd-ticket');
  if (!modal) return;
  _sdModalWatched = true;
  new MutationObserver(() => {
    if (!modal.classList.contains('active') && _sdSelectedTicketId) {
      _sdSelectedTicketId = null;
      sdRenderList();
    }
  }).observe(modal, {attributes: true, attributeFilter: ['class']});
}

function sdShortTitle(text, limit) {
  // Cut on a word boundary. Slicing at a fixed count produced titles that ended
  // mid-word ("... against Senior 2, only..."), which reads as broken rather
  // than abbreviated.
  const t = String(text || '').trim();
  const max = limit || 62;
  if (t.length <= max) return t;
  const cut = t.slice(0, max);
  const sp = cut.lastIndexOf(' ');
  return (sp > max * 0.6 ? cut.slice(0, sp) : cut).replace(/[,;:.\s]+$/, '') + '…';
}

function sdOpenDetail(ticketId) {
  const t = _sdAllTickets.find(x => x.ticket_id === ticketId);
  if (!t) return;
  _sdSelectedTicketId = ticketId;
  sdRenderList(); // keep the row highlighted behind the modal

  const canEdit = S && ['system_admin','wing_admin','national_admin'].includes(S.role);
  const catLabel = _SD_CAT_LABELS[t.category || 'other'] || 'Other';
  const unitDisplay = t.unit_name || t.squadron_name || '';

  document.getElementById('m-sd-ticket-title').textContent = sdShortTitle(t.description);
  document.getElementById('sd-t-meta').textContent =
    `Raised ${sdFmtDate(t.created_at)} · ${t.rank} ${t.first_name} ${t.last_name} · ${unitDisplay}`;
  document.getElementById('sd-t-status-badge').innerHTML = sdStatusBadge(t.status);

  const notesHtml = canEdit
    ? `<textarea id="sd-notes-input" rows="3" aria-label="Internal notes" style="width:100%;box-sizing:border-box;font-size:var(--fs-sm);font-family:inherit;padding:6px 8px;border:1px solid var(--border);border-radius:var(--radius)">${esc(t.admin_notes || '')}</textarea>`
    : `<div style="font-size:var(--fs-sm);color:var(--text)">${t.admin_notes ? esc(t.admin_notes) : '<span style="color:var(--muted)">No notes yet</span>'}</div>`;

  const assigneeHtml = canEdit
    ? (() => {
        const legacy = t.assigned_to_name && !t.assigned_to_user_id
          ? `<option value="__legacy__" selected>${esc(t.assigned_to_name)} (legacy assignment)</option>`
          : '';
        const options = _sdAssignableAccounts.map(a =>
          `<option value="${esc(a.user_id)}" ${a.user_id===t.assigned_to_user_id?'selected':''}>${esc(a.display_name)} — ${esc(a.role.replaceAll('_',' '))}</option>`
        ).join('');
        return `<select id="sd-assignee-input" aria-label="Assigned to" style="width:100%;box-sizing:border-box;font-size:var(--fs-sm);padding:6px 8px;border:1px solid var(--border);border-radius:var(--radius);min-height:32px">
          <option value="">Unassigned</option>${legacy}${options}
        </select>`;
      })()
    : `<div style="font-size:var(--fs-sm)">${t.assigned_to_name ? esc(t.assigned_to_name) : '<span style="color:var(--muted)">Unassigned</span>'}</div>`;

  const statusHtml = canEdit
    ? `<div role="group" aria-label="Ticket status" style="display:flex;gap:var(--sp-xs);flex-wrap:wrap">
        ${['open','in_progress','resolved'].map(st => {
          const labels = {open:'Open', in_progress:'In progress', resolved:'Resolved'};
          const on = t.status === st;
          return `<button type="button" class="btn ${on ? 'btn-primary' : 'btn-secondary'}" id="sd-status-${st}"
            aria-pressed="${on}" style="font-size:var(--fs-xs);padding:5px 12px;min-height:var(--ctl-min)"
            onclick="sdSelectStatus('${st}')">${labels[st]}</button>`;
        }).join('')}
      </div>`
    : sdStatusBadge(t.status);

  document.getElementById('sd-t-body').innerHTML = `
    <div class="sd-field">
      <div class="sd-field-label">Description</div>
      <div style="font-size:var(--fs-sm);line-height:1.55">${esc(t.description)}</div>
    </div>
    <div class="sd-field">
      <div class="sd-field-label">Category</div>
      <div style="font-size:var(--fs-sm)">${esc(catLabel)}</div>
    </div>
    <div class="sd-field">
      <div class="sd-field-label">Contact</div>
      <div style="font-size:var(--fs-sm)">${esc(t.email)}</div>
    </div>
    <div class="sd-field">
      <div class="sd-field-label">Assigned to</div>
      ${assigneeHtml}
    </div>
    <div class="sd-field">
      <div class="sd-field-label">Internal notes</div>
      ${notesHtml}
    </div>
    <div class="sd-field">
      <div class="sd-field-label">Status</div>
      ${statusHtml}
    </div>`;

  const saveBtn = document.getElementById('sd-save-btn');
  saveBtn.style.display = canEdit ? 'inline-flex' : 'none';
  saveBtn.dataset.tid = ticketId;
  const err = document.getElementById('sd-save-err');
  if (err) err.style.display = 'none';

  _sdEditStatus = t.status;
  sdWatchModal();
  openModal('m-sd-ticket');
}

function sdSelectStatus(status) {
  _sdEditStatus = status;
  ['open','in_progress','resolved'].forEach(st => {
    const btn = document.getElementById('sd-status-' + st);
    if (!btn) return;
    const on = st === status;
    btn.className = 'btn ' + (on ? 'btn-primary' : 'btn-secondary');
    btn.style.cssText = 'font-size:var(--fs-xs);padding:5px 12px;min-height:var(--ctl-min)';
    btn.setAttribute('aria-pressed', on ? 'true' : 'false');
  });
}

async function sdSave(ticketId) {
  const errEl = document.getElementById('sd-save-err');
  if (errEl) errEl.style.display = 'none';

  const notesInput = document.getElementById('sd-notes-input');
  const assigneeInput = document.getElementById('sd-assignee-input');
  const body = {
    status: _sdEditStatus,
    admin_notes: notesInput ? notesInput.value : undefined,
  };
  if(assigneeInput && assigneeInput.value !== '__legacy__'){
    body.assigned_to_user_id = assigneeInput.value;
  }

  try {
    await api(`/api/service-desk/tickets/${ticketId}`, {method:'PATCH', body});
    const t = _sdAllTickets.find(x => x.ticket_id === ticketId);
    if (t) {
      if (body.status) t.status = body.status;
      if (body.admin_notes !== undefined) t.admin_notes = body.admin_notes;
      if (body.assigned_to_user_id !== undefined) {
        t.assigned_to_user_id = body.assigned_to_user_id || null;
        const assignee = _sdAssignableAccounts.find(a => a.user_id === body.assigned_to_user_id);
        t.assigned_to_name = assignee ? assignee.display_name : null;
      }
      if (body.status === 'resolved') t.resolved_at = new Date().toISOString();
      else if (body.status) t.resolved_at = null;
    }
    sdRenderList();
    closeModal('m-sd-ticket');
    _sdSelectedTicketId = null;
    sdRenderList();
    showToast('Ticket updated.');
  } catch (e) {
    if (errEl) {
      errEl.textContent = apiErr(e);
      errEl.style.display = 'block';
    }
  }
}

function sdCloseDetail() {
  closeModal('m-sd-ticket');
  _sdSelectedTicketId = null;
  sdRenderList(); // clear the row highlight
}
