// Main TMS module: planning-year navigation control and the Manage Years panel.
// Extracted verbatim from connected-frontend/index.html (stabilisation Phase 4,
// C6). Top-level function declarations and side-effect-free let/const only;
// loaded as a classic script BEFORE the inline bootstrap, so everything here
// is defined before any page-load code runs. Statements with load-time
// effects stay in index.html in their original order. Parity is proven by
// tools/architecture/frontend_parity.mjs.

// ── Year nav control ──────────────────────────────────────────────────────────

function ynInit() {
  if (!P.years || !P.years.length) return;
  _ynPopulateYearSelects();
  // Set currentYearInt from the already-selected currentYearId
  if (P.currentYearId && !P.currentYearInt) {
    const cur = P.years.find(y => y.planning_year_id === P.currentYearId);
    if (cur) P.currentYearInt = cur.year;
  }
  _ynUpdateDisplay();
  _ynUpdateArrows();
  const ceaBtn = document.getElementById('actImportCeaBtn');
  if (ceaBtn) {
    ceaBtn.style.display = ['system_admin','wing_admin','national_admin'].includes(S.role||'') ? '' : 'none';
  }
}

// A year the user can select may have no row yet. Anything that needs a row --
// an import target, a sub-resource URL -- must say so plainly rather than
// building /api/planning/years/null/... and failing with a 404.
function _ynNeedsSetup(what) {
  if (P && P.currentYearId) return false;
  showToast('Set up ' + (P && P.currentYearInt ? P.currentYearInt : 'this year') +
            ' before you can ' + what + '.', true);
  return true;
}

function setCurrentYear(yearObj, reload) {
  if (!yearObj) return;
  // May be null: a selectable year that nobody has written to yet has no row.
  // Downstream `if (P.currentYearId)` guards then correctly render the empty
  // state for that year rather than "no year".
  P.currentYearId = yearObj.planning_year_id || null;
  P.currentYearInt = yearObj.year;
  // Which year was current AT THE TIME of selection. Without it, any past year
  // the user deliberately opened would claim the year had just rolled over.
  if (yearObj.state === 'current') P._ynWasCurrentYear = yearObj.year;
  // CAL-2: the Training Calendar follows the training year. Without this,
  // creating or switching a year left the calendar sitting on whatever year it
  // booted with, which is what "the calendar doesn't update" looked like.
  const _cy = parseInt(yearObj.year, 10);
  if (_cy >= 1990 && _cy <= 2999) {
    calYear = _cy;
    if (typeof _syncCalYearOptions === 'function') _syncCalYearOptions();
    const _calPage = document.getElementById('page-calendar');
    if (_calPage && _calPage.classList.contains('active')) {
      renderCal();
      _loadCalendarHolidayPeriods();
    }
  }
  _ynUpdateDisplay();
  _ynUpdateArrows();
  if (typeof ynSyncPwBadge === 'function') ynSyncPwBadge();
  if (reload !== false) return _loadActivitiesPage();
  return Promise.resolve();
}

// The year bar steps through YEAR INTEGERS, not planning_year_id. A year the
// user can select may have no row at all -- that is the normal state of a year
// nobody has written to -- and a UUID cannot express it. Keying navigation off
// the id is what made an unconfigured year unreachable.
function _ynYears() {
  const rows = (P.years || []).filter(y =>
    y && y.year != null && y.active_status !== false);
  const byYear = new Map();
  for (const r of rows) {
    // Prefer the materialised row when both are present for one year.
    const prior = byYear.get(r.year);
    if (!prior || (r.planning_year_id && !prior.planning_year_id)) byYear.set(r.year, r);
  }
  return [...byYear.values()].sort((a, b) => a.year - b.year);
}

// One quiet line, no chips. The current year deliberately has no arrow: the
// arrows mean "away from now", so their absence is what says you are in it.
const _YN_STATE_TEXT = {
  past:    '\u2190 Previous year \u00b7 training record',
  current: 'Current year',
  future:  '\u2192 Future year \u00b7 planning ahead',
};

function _ynUpdateDisplay() {
  const lbl = document.getElementById('ynLabel');
  // Render nothing until a year resolves. The old placeholder made the control
  // read as broken -- the reported screenshot showed the capsule containing an
  // em-dash where the year should be.
  const wrap = document.getElementById('actYnWrap');
  if (wrap) wrap.style.visibility = P.currentYearInt ? '' : 'hidden';
  if (lbl) lbl.textContent = P.currentYearInt || '';
  const st = document.getElementById('ynState');
  if (st) {
    const row = _ynYears().find(y => y.year === P.currentYearInt);
    const state = row && row.state
      ? row.state
      : P.currentYearInt < new Date().getFullYear()
        ? 'past'
        : P.currentYearInt > new Date().getFullYear()
          ? 'future'
          : 'current';
    st.textContent = _YN_STATE_TEXT[state] || '';
  }
  _ynRenderYearNotice();
  _ynRenderRolloverNotice();
}

// The year is real; only its configuration is empty. Never say the year does
// not exist, and never offer more than the two things that can usefully be
// done from here.
// Past years appear because they hold records; the current year and two ahead
// appear because those can be planned. RECORD rather than PAST: it says what
// the year is FOR, and it is the word the read-only notice uses.
const _YN_TAG = { past: 'RECORD', current: 'CURRENT', future: 'FUTURE' };

// 1 January performs no database write: it changes a derived value. So a
// session left open across midnight is quietly looking at last year. Say so,
// offer the switch, and do not take it -- swapping the data underneath someone
// mid-task is the thing this notice exists to avoid.
function _ynRenderRolloverNotice() {
  const el = document.getElementById('yn-rollover');
  if (!el) return;
  const rows = _ynYears();
  const current = rows.find(function (y) { return y.state === 'current'; });
  const mine = rows.find(function (y) { return y.year === P.currentYearInt; });

  // Only when the year the user is on has JUST stopped being the current one.
  const rolled = !!current && !!mine && mine.state === 'past' &&
                 P._ynWasCurrentYear === mine.year;
  if (!rolled) { el.setAttribute('hidden', ''); el.textContent = ''; return; }

  el.textContent = '';
  const box = document.createElement('div');
  box.className = 'yn-rollover';
  const para = document.createElement('p');
  para.textContent = current.year + ' is now the current training year.';
  const btn = document.createElement('button');
  btn.className = 'btn btn-dk';
  btn.type = 'button';
  btn.textContent = 'Switch to ' + current.year;
  btn.addEventListener('click', function () {
    P._ynWasCurrentYear = current.year;
    setCurrentYear(current);
    _ynRenderRolloverNotice();
  });
  box.appendChild(para);
  box.appendChild(btn);
  el.appendChild(box);
  el.removeAttribute('hidden');
}

let _ynLastRolloverCheck = 0;
async function ynCheckYearRollover(force) {
  const now = Date.now();
  if (!force && now - _ynLastRolloverCheck < 60000) return;   // never hammer the API
  _ynLastRolloverCheck = now;
  try { await _ynFetchYears(); } catch (_) { return; }
  _ynUpdateArrows();
  _ynRenderRolloverNotice();
}

function ynToggleMenu(force) {
  const menu = document.getElementById('ynMenu');
  const btn = document.getElementById('ynDisplay');
  if (!menu || !btn) return;
  const open = (force === undefined) ? menu.hasAttribute('hidden') : !!force;
  if (!open) {
    menu.setAttribute('hidden', '');
    btn.setAttribute('aria-expanded', 'false');
    return;
  }
  _ynRenderMenu();
  menu.removeAttribute('hidden');
  btn.setAttribute('aria-expanded', 'true');
  const first = menu.querySelector('button[aria-current="true"]') || menu.querySelector('button');
  if (first) first.focus();
}

function _ynRenderMenu() {
  const menu = document.getElementById('ynMenu');
  if (!menu) return;
  menu.textContent = '';
  const rows = _ynYears().slice().sort((a, b) => b.year - a.year);
  rows.forEach(function (row) {
    const li = document.createElement('li');
    li.setAttribute('role', 'none');
    const b = document.createElement('button');
    b.type = 'button';
    b.setAttribute('role', 'menuitem');
    if (row.year === P.currentYearInt) b.setAttribute('aria-current', 'true');
    const num = document.createElement('span');
    num.textContent = String(row.year);
    const tag = document.createElement('span');
    tag.className = 'yn-tag';
    tag.textContent = _YN_TAG[row.state] || '';
    b.appendChild(num);
    b.appendChild(tag);
    b.addEventListener('click', function () {
      setCurrentYear(row);
      ynToggleMenu(false);
      const d = document.getElementById('ynDisplay');
      if (d) d.focus();
    });
    li.appendChild(b);
    menu.appendChild(li);
  });
}

function _ynRenderYearNotice() {
  const el = document.getElementById('yn-year-notice');
  if (!el) return;
  const rows = _ynYears();
  const row = rows.find(y => y.year === P.currentYearInt);
  el.textContent = '';
  if (!row) return;
  const yr = Number(row.year);

  if (row.state === 'past') {
    // Read-only stated in words, first, and the notice names the way out --
    // blocking someone without saying what to do instead is just a wall.
    const box = document.createElement('div');
    box.className = 'yn-notice yn-notice-locked';
    const para = document.createElement('p');
    const lead = document.createElement('strong');
    lead.textContent = 'Read-only.';
    para.appendChild(lead);
    para.appendChild(document.createTextNode(
      ` ${yr} is complete. Its records stay available to review. To correct ` +
      `something, a Wing administrator can open Delegated Intervention.`));
    box.appendChild(para);
    el.appendChild(box);
    return;
  }

  if (row.materialised === false) {
    const prev = rows.filter(y => y.year < yr && y.materialised)
                     .sort((a, b) => b.year - a.year)[0];
    const box = document.createElement('div');
    box.className = 'yn-notice';
    const para = document.createElement('p');
    para.textContent = prev
      ? `Nothing has been set up for ${yr} yet. You can start from scratch, or ` +
        `bring across the class structure you used in ${prev.year}.`
      : `Nothing has been set up for ${yr} yet.`;
    box.appendChild(para);

    const actions = document.createElement('div');
    actions.className = 'yn-notice-actions';
    const setUp = document.createElement('button');
    setUp.className = 'btn btn-dk';
    setUp.textContent = `Set up ${yr}`;
    setUp.addEventListener('click', () => ynSetUpYear(yr));
    actions.appendChild(setUp);
    if (prev) {
      // Names the source year rather than "copy previous", so the sentence is
      // true without the reader reconstructing context.
      const copy = document.createElement('button');
      copy.className = 'btn btn-secondary';
      copy.textContent = `Copy setup from ${prev.year}`;
      copy.addEventListener('click', () => ynCopySetupFrom(Number(prev.year), yr));
      actions.appendChild(copy);
    }
    box.appendChild(actions);
    el.appendChild(box);
  }
}

async function ynSetUpYear(year) {
  try {
    await api('/api/planning/years', {
      method: 'POST', body: { year: year, name: year + ' Training Year' } });
    await _ynFetchYears();
    const row = _ynYears().find(y => y.year === year);
    if (row) setCurrentYear(row);
    showToast(`Set up ${year}.`);
  } catch (e) { showToast(`Could not set up ${year}: ` + apiErr(e), true); }
}

async function ynCopySetupFrom(src, tgt) {
  try {
    const r = await api('/api/planning/years/copy-setup', { method: 'POST', body: {
      source_year: src, target_year: tgt,
      copy_classes: true, copy_parade_pattern: false } });
    await _ynFetchYears();
    const row = _ynYears().find(y => y.year === tgt);
    if (row) setCurrentYear(row);
    const n = (r && r.classes_copied != null) ? r.classes_copied : 0;
    showToast(`Copied ${n} training ${n === 1 ? 'class' : 'classes'} from ${src} into ${tgt}.`);
  } catch (e) { showToast('Could not copy setup: ' + apiErr(e), true); }
}

function _ynUpdateArrows() {
  const prev = document.getElementById('ynPrev');
  const next = document.getElementById('ynNext');
  const year = Number(P.currentYearInt);
  if (prev) prev.disabled = !Number.isFinite(year) || year <= 1990;
  if (next) next.disabled = !Number.isFinite(year) || year >= 2999;
}

function ynNav(dir) {
  const year = Number(P.currentYearInt);
  if (!Number.isFinite(year)) return;
  const targetYear = year + dir;
  if (targetYear < 1990 || targetYear > 2999) return;
  const target = _ynYears().find(y => Number(y.year) === targetYear) || {
    year: targetYear,
    planning_year_id: null,
    materialised: false,
    state: targetYear < new Date().getFullYear()
      ? 'past'
      : targetYear > new Date().getFullYear() ? 'future' : 'current',
  };
  if (!target.planning_year_id && !_ynYears().some(y => Number(y.year) === targetYear)) {
    P.years = [...(P.years || []), target];
  }
  setCurrentYear(target);
}

// The year is chosen from the menu (ynToggleMenu). The old click-to-type
// editor is gone: it let you type any year at all, including ones outside
// what can be planned, and its cancel path rebuilt #ynDisplay's innerHTML,
// which would now destroy the caret and the menu's aria wiring.

let _ynToastTimer = null;
function ynToast(msg) {
  const el = document.getElementById('ynToast');
  if (!el) return;
  el.textContent = msg;
  clearTimeout(_ynToastTimer);
  _ynToastTimer = setTimeout(() => { el.textContent = ''; }, 3200);
}

function ynOpenManage() {
  if (typeof _ynOpenManagePanel === 'function') { _ynOpenManagePanel(); return; }
  ynToast('Year management coming soon');
}

// ── Manage Years Panel ──────────────────────────────────────────────────────

// YR-1: the next training year follows the year currently being planned (or the
// real calendar year), not the largest year that has ever existed -- a single
// stray year would otherwise push every subsequent Create Year along with it.
function _ynNextYearNumber(){
  const existing=new Set(((typeof P!=='undefined'&&P.years)||[]).map(y=>parseInt(y&&y.year,10)));
  const cur=parseInt((typeof P!=='undefined'&&P.currentYearInt)||0,10);
  const base=(cur>=1990&&cur<=2998)?cur:new Date().getFullYear();
  let n=base+1;
  while(existing.has(n)&&n<=2999) n++;
  return n;
}

// One renderer for every surface that lists training years, so the Unit Setup
// card and the Manage Training Years modal cannot drift apart again.
// `canWrite` gates the destructive actions; `compact` drops the description.
function _ynRenderYearList(el, years, opts){
  opts = opts || {};
  const canWrite = opts.canWrite !== false;
  years = (years||[]).slice().sort((a,b)=> b.year - a.year);
  if(!years.length){
    el.innerHTML = '<div class="yn-empty">No training years yet. Create one to start planning.</div>';
    return;
  }
  const curId = (typeof P!=='undefined') ? P.currentYearId : null;
  const logical = years.filter(function(y){ return !y.planning_year_id; });
  const materialised = years.filter(function(y){ return !!y.planning_year_id; });
  const showArch = !!opts.showArchived;
  const active = materialised.filter(function(y){return y.active_status;});
  const archived = materialised.filter(function(y){return !y.active_status;});
  const visible = logical.concat(showArch ? materialised : active)
    .sort((a,b)=> b.year - a.year);
  const archNote = archived.length
    ? '<button class="btn btn-xs btn-out" style="align-self:flex-start;margin-top:4px" '
      + 'onclick="ynToggleArchived(this)" aria-expanded="'+(showArch?'true':'false')+'">'
      + (showArch ? 'Hide archived years' : ('Show '+archived.length+' archived year'+(archived.length===1?'':'s')))
      + '</button>'
    : '';
  if(!visible.length && !showArch && archived.length){
    el.innerHTML = '<div class="yn-empty">No active training years. '
      + archived.length + ' archived.</div><div class="yn-year-list">'+archNote+'</div>';
    return;
  }
  el.innerHTML = '<div class="yn-year-list">' + visible.map(function(y){
    const id = y.planning_year_id;
    const isLogical = !id;
    const isCur = isLogical
      ? Number(y.year) === Number((typeof P!=='undefined') ? P.currentYearInt : null)
      : id === curId;
    const activeRow = isLogical ? true : !!y.active_status;
    const cls = 'yn-year-row' + (isCur?' is-current':'') + (activeRow?'':' is-arch');
    const nameLine = (y.name && String(y.name) !== String(y.year))
      ? '<div class="yn-year-name">'+esc(String(y.name))+'</div>' : '';
    const created = y.created_at ? fmtD(String(y.created_at).slice(0,10),{day:'numeric',month:'short',year:'numeric'}) : '';
    const stateLabel = isLogical ? 'Not set up'
      : y.state==='current'?'Current':y.state==='past'?'Record':'Upcoming';
    const meta = [stateLabel, created?('Created '+created):''].filter(Boolean).join(' \u00b7 ');
    let acts = '';
    if(isLogical){
      if(canWrite){
        acts += '<button class="btn btn-xs btn-dk" onclick="ynSetUpYear('+(+y.year)+')">Set up '+esc(String(y.year))+'</button>';
      }
    }else{
      acts += '<button class="btn btn-xs btn-out" onclick="ynExportYear(\''+esc(id)+'\','+(+y.year)+')">Export</button>';
      const canRemediate=['wing_admin','system_admin'].includes(S.role||'');
      if(canRemediate){
        acts += activeRow
          ? '<button class="btn btn-xs btn-out" onclick="ynArchiveYear(\''+esc(id)+'\')">Archive</button>'
          : '<button class="btn btn-xs btn-out" onclick="ynRestoreYear(\''+esc(id)+'\')">Restore</button>';
        if(!activeRow){
          acts += '<button class="btn btn-xs btn-red" onclick="ynDeleteYear(\''+esc(id)+'\','+(+y.year)+')">Delete</button>';
        }
      }
    }
    return '<div class="'+cls+'">'
      + '<div class="yn-year-id"><span class="yn-year-num">'+esc(String(y.year))+'</span>'
      + (isCur?'<span class="yn-current-tag">Planning now</span>':'')
      + '</div>'
      + '<div class="yn-year-body">'+nameLine+'<div class="yn-year-meta">'+esc(meta)+'</div></div>'
      + '<div class="yn-year-acts">'+acts+'</div>'
      + '</div>';
  }).join('') + archNote + '</div>';
}

// Toggle archived years in whichever year list the button belongs to.
function ynToggleArchived(btn){
  const host = btn.closest('#settings-yn-table-wrap, #ynManageTable');
  if(!host) return;
  const nowShow = btn.getAttribute('aria-expanded') !== 'true';
  _ynRenderYearList(host, (typeof P!=='undefined'&&P.years)||[], {
    canWrite: canWriteSquadron(), showArchived: nowShow
  });
}

// Both year surfaces load through here.
async function _ynFetchYears(){
  // include_unmaterialised: the bar steps through selectable years, and a year
  // nobody has written to has no row. Every P.years assignment goes through
  // here -- six call sites used to refetch without the flag, and the first one
  // to run after a step silently dropped the future years back out of the bar.
  let all = await api('/api/planning/years?include_unmaterialised=true') || [];
  // Keep a year handed off from Planning Workspace selectable until it exists.
  if(typeof P!=='undefined' && P._handoffYear){
    const hy = P._handoffYear;
    if(all.some(y => Number(y.year) === hy && y.active_status !== false && y.planning_year_id)) P._handoffYear = null;
    else if(!all.some(y => Number(y.year) === hy && y.active_status !== false)) all = [...all, _ynLogicalYear(hy)];
  }
  if(typeof P!=='undefined') P.years = all;
  return all;
}

// Repaint every year surface that is currently in the DOM.
async function ynRefreshAllYearViews(){
  let years;
  try{ years = await _ynFetchYears(); }catch(e){ return; }
  const modalEl = document.getElementById('ynManageTable');
  if(modalEl) _ynRenderYearList(modalEl, years, {canWrite:canWriteSquadron()});
  const cardEl = document.getElementById('settings-yn-table-wrap');
  if(cardEl) _ynRenderYearList(cardEl, years, {canWrite:canWriteSquadron()});
  if(typeof _syncCalYearOptions==='function') _syncCalYearOptions();
}

async function ynLoadManagePanel(){
  const tbl=document.getElementById('ynManageTable');
  if(!tbl) return;
  tbl.innerHTML='<div class="yn-empty">Loading\u2026</div>';
  try{ await ynRefreshAllYearViews(); }
  catch(e){ tbl.innerHTML='<div class="sc-status-err">Could not load years: '+esc(apiErr(e))+'</div>'; }
}

async function ynArchiveYear(id){
  try{
    await api('/api/planning/years/'+id,{method:'PATCH',body:{active_status:false}});
    const all=await _ynFetchYears();
    await ynRefreshAllYearViews();
  } catch(e){ showToast('Archive failed: '+apiErr(e),true); }
}

async function ynRestoreYear(id){
  try{
    await api('/api/planning/years/'+id,{method:'PATCH',body:{active_status:true}});
    const all=await _ynFetchYears();
    await ynRefreshAllYearViews();
  } catch(e){ showToast('Restore failed: '+apiErr(e),true); }
}

function ynDeleteYear(id,yearNum){
  confirmAction('Permanently delete '+yearNum+'? This fails if the year has any attached data.',async()=>{
    try{
      await api('/api/planning/years/'+id,{method:'DELETE'});
      const all=await _ynFetchYears();
      await ynRefreshAllYearViews();
    } catch(e){ showToast('Delete failed: '+apiErr(e),true); }
  },true);
}

function ynExportYear(id,yearNum){
  _downloadExport('/api/planning/years/'+id+'/export','AAFC_TMS_'+yearNum+'.csv');
}

// Override the ynOpenManage stub — this definition wins (last in file order)
function ynOpenManage(){
  openModal('m-manage-years');
  ynLoadManagePanel();
}

function ynSyncPwBadge() {
  const badge = document.getElementById('navPwYrBadge');
  const hint = document.getElementById('navPwYrHint');
  const yr = P && P.currentYearInt;
  if (badge) {
    badge.textContent = yr ? String(yr) : '';
    badge.style.display = yr ? '' : 'none';
  }
  if (hint) {
    hint.textContent = yr ? `Opens with ${yr} context` : '';
    hint.style.display = yr ? '' : 'none';
  }
}
