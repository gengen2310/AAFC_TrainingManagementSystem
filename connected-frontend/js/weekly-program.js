// Main TMS module: Weekly Program page -- term/night navigation, schedule
// rendering, print and publish.
// Extracted verbatim from connected-frontend/index.html (stabilisation Phase 4,
// C6). Top-level function declarations and side-effect-free let/const only;
// loaded as a classic script BEFORE the inline bootstrap, so everything here
// is defined before any page-load code runs. Statements with load-time
// effects stay in index.html in their original order. Parity is proven by
// tools/architecture/frontend_parity.mjs.

// ═══════════════════════════════════════════════════════════
//  WEEKLY PROGRAM
// ═══════════════════════════════════════════════════════════
// WP-6: renderWP() used to overwrite #page-weekly-program -- the entire page,
// toolbar included -- so the search box, night selector and status filter were
// destroyed on first render. It paints into #wp-content, which had been sitting
// in the markup all along and was never written to.
//
// Fetched once per page visit; the filters re-paint from this and never refetch.
let _wpData = null;   // {pns, classes, schedByPn}

// Fixed column groups -- always 4, always rendered
const WP_STAGE_GROUPS = [
    {label:'Orientation / Initial', codes:['ORI','INI']},
    {label:'Junior / Bronze',       codes:['JNR']},
    {label:'Intermediate / Silver', codes:['INT']},
    {label:'Senior / Gold',         codes:['SNR']},
];

// The night selector is rebuilt from whichever term is chosen, so this is now
// just the entry point nav() already calls. It used to write its own flat list
// of every night, which would overwrite the term-filtered one.
function populateWPDD(){
  _wpPopulateYearSel();
  if(typeof _wpSyncNightOptions==='function') _wpSyncNightOptions();
}

// WP-9: populate the year selector from P.years, defaulting to P.currentYearId.
// The selector drives renderWP()'s planning_year_id query param.
function _wpPopulateYearSel(){
  const sel=document.getElementById('wp-f-year');
  if(!sel) return;
  const years=((typeof P!=='undefined')&&P.years)||[];
  const curId=((typeof P!=='undefined')&&P.currentYearId)||'';
  const opts=years
    .filter(y=>y&&y.planning_year_id)
    .sort((a,b)=>(b.year||0)-(a.year||0))
    .map(y=>'<option value="'+esc(y.planning_year_id)+'"'+(y.planning_year_id===curId?' selected':'')+'>'+esc(String(y.year||'—'))+'</option>')
    .join('');
  sel.innerHTML='<option value="">All years</option>'+opts;
}
async function renderWP() {
    const wrap = document.getElementById('wp-content');
    if (!wrap) return;
    wrap.innerHTML = '<p class="muted p-4">Loading\u2026</p>';
    try {
        // WP-9: use the year selector value; fall back to P.currentYearId on first
        // load (before the selector is populated by _wpPopulateYearSel).
        const wpYearSel = document.getElementById('wp-f-year');
        const wpYear = (wpYearSel && wpYearSel.value) ||
                       ((typeof P !== 'undefined' && P.currentYearId) ? P.currentYearId : '');
        const yearQ = wpYear ? `?planning_year_id=${encodeURIComponent(wpYear)}` : '';

        // WP-1/WP-2: three requests for the whole page. This was previously two
        // plus one /schedule per parade night -- 244 locally -- issued serially
        // inside an awaited for-loop, against an API_RATE_LIMIT of 300/window.
        const [pns, bulk] = await Promise.all([
            api(`/api/parade-nights${yearQ}`),
            api(`/api/parade-night-schedules${yearQ}`),
        ]);

        const yearId = wpYear;
        const classes = yearId
            ? (await api(`/api/training-classes?training_year_id=${encodeURIComponent(yearId)}`))
              .filter(c => !c.is_archived)
            : [];

        const schedByPn = {};
        for (const sc of ((bulk && bulk.schedules) || [])) schedByPn[sc.parade_night_id] = sc;
        _wpData = {pns: pns || [], classes, schedByPn};
        // WP-7: open on the term containing today rather than the whole year.
        // Only on first load -- a choice the user makes afterwards stands.
        const termSel = document.getElementById('wp-f-term');
        if (termSel && !termSel.dataset.userSet) {
            const t = _wpCurrentTerm();
            if (t && [...termSel.options].some(o => o.value === t)) termSel.value = t;
        }
        _wpSyncNightOptions();
        _wpPaint();
    } catch(e) {
        _wpData = null;
        wrap.innerHTML = `<p class="text-danger p-4">Failed to load: ${esc(apiErr(e))}</p>`;
    }
}

// WP-7: each night's header already printed its term, but there was no way to
// filter by it, so finding "this term" meant scrolling the whole year.
function _wpCurrentTerm(){
  const pns=((_wpData&&_wpData.pns)||[]).filter(p=>p.term);
  if(!pns.length) return 'all';
  const today=new Date().toISOString().slice(0,10);
  const ahead=pns.filter(p=>p.date>=today).sort((a,b)=>a.date.localeCompare(b.date));
  if(ahead.length) return ahead[0].term;
  return pns.slice().sort((a,b)=>b.date.localeCompare(a.date))[0].term;
}
function _wpNightsInTerm(){
  const term=(document.getElementById('wp-f-term')||{}).value||'all';
  return ((_wpData&&_wpData.pns)||[])
    .filter(p=>term==='all'||p.term===term)
    .slice().sort((a,b)=>a.date.localeCompare(b.date));
}
function _wpSyncNightOptions(){
  const sel=document.getElementById('wp-sel');
  if(!sel) return;
  const prev=sel.value;
  const nights=_wpNightsInTerm();
  // REM-92: prepend a placeholder so the user sees "choose a parade night"
  // guidance before making a selection, rather than a blank area.
  sel.innerHTML='<option value="">— Choose a parade night —</option>'+(nights.length
    ? nights.map(function(pn){
        return '<option value="'+esc(pn.date)+'">'+esc(fmtD(pn.date,{weekday:'short',day:'numeric',month:'short',year:'numeric'}))+'</option>';
      }).join('')
    : '');
  // Restore the previous selection if the night is still in this term.
  if(prev && nights.some(function(n){return n.date===prev;})){
    sel.value=prev;
  }
  _wpUpdateNavBtns();
}
function _wpUpdateNavBtns(){
  const sel=document.getElementById('wp-sel');
  const prevBtn=document.getElementById('wp-prev');
  const nextBtn=document.getElementById('wp-next');
  if(!sel) return;
  const n=sel.options.length;
  const i=sel.selectedIndex;
  if(prevBtn) prevBtn.disabled=(i<=1||n<=1);
  if(nextBtn) nextBtn.disabled=(i<0||i>=n-1||n===0);
}
function _wpPrev(){
  const sel=document.getElementById('wp-sel');
  if(!sel||sel.selectedIndex<=1) return;
  sel.selectedIndex--;
  _wpPaint();
}
function _wpNext(){
  const sel=document.getElementById('wp-sel');
  if(!sel||sel.selectedIndex>=sel.options.length-1) return;
  sel.selectedIndex++;
  _wpPaint();
}
function wpTermChanged(){
  const t=document.getElementById('wp-f-term');
  if(t) t.dataset.userSet='1';
  _wpSyncNightOptions(); _wpPaint();
}
// WP-9: changing year resets the term auto-selection (the new year may have
// different terms) and re-fetches all data.
function wpYearChanged(){
  const t=document.getElementById('wp-f-term');
  if(t) delete t.dataset.userSet;
  renderWP();
}

// WP-8: printReport() has existed all along and nothing ever called it, and this
// page had no print control. window.print() prints the active page; the print
// stylesheet already hides every other page and all chrome.
function wpPrint(){
  if(typeof _wpData==='undefined'||!_wpData){ showToast('Nothing to print yet.',true); return; }
  window.print();
}

// Render from _wpData applying the current filters. No network access -- this is
// what the search box calls on every keystroke (WP-3: `oninput` used to call
// renderWP(), which would now be 3 requests per character).
function _wpPaint() {
    const wrap = document.getElementById('wp-content');
    if (!wrap || !_wpData) return;
    const qEl = document.getElementById('wp-search');
    const stEl = document.getElementById('wp-f-status');
    const q = ((qEl && qEl.value) || '').trim().toLowerCase();
    const status = (stEl && stEl.value) || 'all';
    const term = (document.getElementById('wp-f-term')||{}).value || 'all';
    const oneNight = (document.getElementById('wp-sel')||{}).value || '';

    // Always show exactly one night — no multi-night view.
    if (!oneNight) {
        // REM-92: distinguish "nights exist but none chosen" from "no nights at all"
        if (_wpNightsInTerm().length) {
            wrap.innerHTML = '<p class="muted p-4">Choose a parade night from the dropdown above to view its programme.</p>';
        } else {
            wrap.innerHTML = '<p class="muted p-4">No parade nights for this term. Choose a different term above.</p>';
        }
        _wpUpdateNavBtns();
        return;
    }

    // Publish acts on the night being shown, so it only makes sense for one.
    const pubBtn = document.getElementById('wp-publish-btn');
    if (pubBtn) {
        pubBtn.disabled = !oneNight;
        pubBtn.title = oneNight ? 'Publish the night shown' : 'Choose a single night to publish it';
    }

    let html = '', shown = 0;
    for (const pn of _wpData.pns) {
        if (term !== 'all' && pn.term !== term) continue;
        if (pn.date !== oneNight) continue;
        const sched = _wpFilterSchedule(_wpData.schedByPn[pn.parade_night_id], q, status);
        if (!sched) continue;
        shown++;
        html += _renderPNSchedule(pn, sched, _wpData.classes, WP_STAGE_GROUPS);
    }

    if (!_wpData.pns.length) {
        wrap.innerHTML = '<p class="muted p-4">No parade nights for this training year.</p>';
        return;
    }
    const countEl = document.getElementById('wp-count');
    if (countEl) countEl.textContent = shown ? (shown + ' night' + (shown===1?'':'s') + ' shown') : '';

    if (!shown) {
        const bits = [];
        if (q) bits.push(`matching \u201c${esc(q)}\u201d`);
        if (status !== 'all') bits.push(`with status \u201c${esc(status.replace(/_/g,' '))}\u201d`);
        wrap.innerHTML = `<p class="muted p-4">No sessions ${esc(bits.join(' '))}. `
            + `Clear the search and status filter to see all ${_wpData.pns.length} parade nights.</p>`;
        return;
    }
    const today = new Date().toLocaleDateString('en-AU', {day:'2-digit',month:'long',year:'numeric'});
    wrap.innerHTML = `<div class="wp-schedule-scroll" tabindex="0" role="region" aria-label="Weekly Program schedule">${html}</div><div class="print-footer">Generated ${esc(today)}</div>`;
    _wpUpdateNavBtns();
}

// WP-4: the search box and status filter were wired to renderWP(), which never
// read either one -- they refetched the entire page and changed nothing. These
// two functions are the filter they always implied.

// Does one session match the typed query? The placeholder promises "facilitator,
// room, curriculum item", so those are the fields searched, plus the cadet group
// and any custom title. Change this one function to change what search means.
function _wpMatch(sess, q) {
    return [
        sess.curriculum_title_at_time,
        sess.custom_title,
        sess.facilitator_display_name_at_time,
        sess.training_area_name_at_time,
        sess.cadet_group,
    ].some(v => String(v || '').toLowerCase().includes(q));
}

// Returns a copy of `sched` carrying only sessions that pass both filters, or
// null when the night has none left -- a night with nothing matching is dropped
// from the program rather than printed as an empty shell.
function _wpFilterSchedule(sched, q, status) {
    if (!sched) return null;
    if (!q && status === 'all') return sched;
    const keep = s => (status === 'all' || String(s.status || '') === status)
                   && (!q || _wpMatch(s, q));
    const byBlock = {};
    let kept = 0;
    for (const bid of Object.keys(sched.sessions_by_block || {})) {
        const f = (sched.sessions_by_block[bid] || []).filter(keep);
        if (f.length) { byBlock[bid] = f; kept += f.length; }
    }
    const unlinked = (sched.unlinked_sessions || []).filter(keep);
    kept += unlinked.length;
    if (!kept) return null;
    return Object.assign({}, sched, {sessions_by_block: byBlock, unlinked_sessions: unlinked});
}

function _renderPNSchedule(pn, schedule, classes, stageGroups) {
    const blocks = (schedule && schedule.blocks) || [];
    const byBlock = (schedule && schedule.sessions_by_block) || {};
    const unlinked = (schedule && schedule.unlinked_sessions) || [];

    // Determine sub-columns: classes per group (or one placeholder if none)
    const groupCols = stageGroups.map(g => {
        const cls = classes.filter(c => g.codes.includes(c.stage_code))
                           .sort((a,b) => (a.sequence||0)-(b.sequence||0));
        return {group: g, cols: cls.length ? cls : [{display_name:'—', training_class_id:null}]};
    });
    const totalCols = groupCols.reduce((s,g) => s + g.cols.length, 0);

    // Build header
    const dateStr = pn.date
        ? (() => { try { return new Date(pn.date).toLocaleDateString('en-AU',{weekday:'long',day:'numeric',month:'long',year:'numeric'}); } catch(_){ return esc(pn.date); }})()
        : '';
    const sqnName = esc(S.scopeName || (S.session && S.session.display_name) || '');
    const weeklySquadronId = saBrowseSquadronId() || S.currentSqnId || (S.session && S.session.squadron_id);
    const weeklySquadron = (S.squadrons || []).find(s => s.squadron_id === weeklySquadronId);
    const weeklyWingId = (weeklySquadron && weeklySquadron.wing_id)
        || (S.session && S.session.wing_id)
        || saBrowseWingId();
    const weeklyWing = (S.wings || []).find(w => w.wing_id === weeklyWingId);
    const wingName = esc(
        (weeklySquadron && weeklySquadron.wing_name)
        || (weeklyWing && (weeklyWing.name || weeklyWing.wing_name))
        || (S.session && (S.session.wing_name || S.session.wing_code))
        || ''
    );
    // Three spans rather than one string, so the two media can order the same
    // facts differently. On paper they sit inline and read exactly as before --
    // squadron, date, term, time -- because the separators are supplied by CSS
    // in the print block. On screen the date is promoted to its own line: it is
    // the only part that differs between nights, and it used to be the third
    // thing in a 12px row led by a squadron name identical on all of them.
    // The flex container is the inner span, NOT the td. Setting display:flex on
    // a cell takes it out of the table layout algorithm, and colspan stops
    // applying with it -- the banner rendered across two columns instead of the
    // full width. The cell stays a table-cell; the span inside it does the work.
    const nightHeaderRow = `<tr><td colspan="${totalCols+2}" class="night-header">`
        + `<span class="night-inner">`
        + `<span class="night-sqn">${sqnName}${wingName ? ` — ${wingName}` : ''}</span>`
        + `<span class="night-date">${esc(dateStr)}</span>`
        + `<span class="night-rest">Term ${esc(String(pn.term||'—'))} · ${esc(pn.start_time||'')}–${esc(pn.end_time||'')}</span>`
        + `</span></td></tr>`;
    let thead = '<thead>';
    thead += nightHeaderRow;
    thead += '<tr><th class="col-time">Time</th><th class="col-block">Block</th>';
    groupCols.forEach(gc => { thead += `<th colspan="${gc.cols.length}" class="group-header">${esc(gc.group.label)}</th>`; });
    thead += '</tr><tr><th></th><th></th>';
    groupCols.forEach(gc => { gc.cols.forEach(cl => { thead += `<th class="class-header">${esc(cl.display_name)}</th>`; }); });
    thead += '</tr></thead>';

    // Build body
    const dash = '<td style="text-align:center;color:#aaa">—</td>';
    let tbody = '<tbody>';
    for (const b of blocks) {
        // TB-2: this tested block_type === 'training_period' only. The backend's
        // own period count uses is_instructional_period (see training.py's
        // ip_count), and that flag is the semantic one -- block_type is a
        // category label. Any block flagged as an instructional period gets
        // class columns; the string is kept as a fallback.
        const isTP = !!b.is_instructional_period || b.block_type === 'training_period';
        const timeStr = b.start_time ? `${esc(b.start_time)}${b.end_time ? '–'+esc(b.end_time) : ''}` : '';
        if (!isTP) {
            tbody += `<tr class="non-period-row"><td>${timeStr}</td><td>${esc(b.block_name)}</td>${dash.repeat(totalCols)}</tr>`;
        } else {
            const blockSessions = byBlock[b.block_id] || [];
            tbody += `<tr><td>${timeStr}</td><td><strong>${esc(b.block_name)}</strong></td>`;
            groupCols.forEach(gc => {
                gc.cols.forEach(cl => {
                    if (!cl.training_class_id) { tbody += dash; return; }
                    const inactive = (cl.start_date && pn.date < cl.start_date) || (cl.end_date && pn.date > cl.end_date);
                    if (inactive) { tbody += dash; return; }
                    const sess = blockSessions.find(s =>
                        Array.isArray(s.training_classes) &&
                        s.training_classes.some(tc => tc.training_class_id === cl.training_class_id)
                    ) || blockSessions.find(s =>
                        (!Array.isArray(s.training_classes) || s.training_classes.length === 0) &&
                        _stageCodeMatchesCadetGroup(cl.stage_code, s.cadet_group)
                    );
                    if (!sess) {
                        tbody += `<td><em style="color:#aaa">Unassigned</em></td>`;
                    } else {
                        const title = esc(sess.custom_title || sess.curriculum_title_at_time || 'Unassigned');
                        const fac   = sess.facilitator_display_name_at_time ? `<br><small>${esc(sess.facilitator_display_name_at_time)}</small>` : '';
                        // #888 measured 3.54:1 on white against the 4.5:1 small-text floor. #5f6b7a
        // is 5.43:1 and carries a blue bias that sits with the AAFC navy rather
        // than reading as a neutral grey. Pre-existing; surfaced only once
        // weekly-program was added to the contrast gate.
        const room  = sess.training_area_name_at_time ? `<br><small style="color:#5f6b7a">${esc(sess.training_area_name_at_time)}</small>` : '';
                        tbody += `<td>${title}${fac}${room}</td>`;
                    }
                });
            });
            tbody += '</tr>';
        }
    }
    if (unlinked.length) {
        tbody += `<tr><td colspan="${totalCols+2}" style="background:#fff8e1;padding:4px 6px;font-style:italic;font-size:7.5pt;">`;
        tbody += `Unlinked periods: ${unlinked.map(s=>esc(s.curriculum_title_at_time||'—')).join(', ')}</td></tr>`;
    }
    tbody += '</tbody>';

    // A night with nothing on it used to render the full block skeleton -- every
    // row a dash -- which at a glance is indistinguishable from a night whose
    // grid simply has not loaded. Say which it is.
    const sessionCount = Object.keys(byBlock).reduce((n,k) => n + ((byBlock[k]||[]).length), 0)
                       + unlinked.length;
    if (!sessionCount) {
        return `<div class="print-pn-block"><div class="wp-table-scroll" tabindex="0" role="region" aria-label="Weekly Program schedule"><table class="print-schedule-table"><thead>${nightHeaderRow}</thead></table></div>`
             + `<div class="wp-empty-night">No sessions planned</div></div>`;
    }
    // margin-bottom moved to the stylesheet: it was the only separation between
    // nights on screen, and an inline style cannot be overridden per medium.
    return `<div class="print-pn-block"><div class="wp-table-scroll" tabindex="0" role="region" aria-label="Weekly Program schedule"><table class="print-schedule-table">${thead}${tbody}</table></div></div>`;
}

function _stageCodeMatchesCadetGroup(stageCode, cadetGroup) {
    if (!cadetGroup) return false;
    const MAP = {ORI:'orientation', INI:'initial', JNR:'junior', INT:'intermediate', SNR:'senior'};
    const mapped = MAP[stageCode];
    if (!mapped) return false;
    return cadetGroup.toLowerCase().includes(mapped);
}

function printReport(){
  // Hide all pages, show only active
  window.print();
}
async function publishWP(){
  const ds=document.getElementById('wp-sel').value;
  const pn=S.pns.find(p=>p.date===ds);
  if(!pn||!pn.id){showToast('Select a parade night first.',true);return;}
  if(pn.published){showToast('This program has already been published.');return;}
  try{
    await apiPublishPN(pn.id);
    pn.published=true;
    renderWP();
    showToast('Weekly Program published. Planned sessions are now marked Published.');
    reloadAndRender();
  }catch(e){
    const d=e&&e.body?.detail;
    if(d&&d.error==='publish_blocked'&&Array.isArray(d.blockers)&&d.blockers.length){
      const first=d.blockers[0];
      const more=d.blockers.length>1?' Plus '+(d.blockers.length-1)+' more issue'+(d.blockers.length>2?'s':'')+'.':'';
      showToast('Cannot publish — '+first.reason+'.'+more,true);
    }else{
      showToast(apiErr(e)||'Publish failed. Try again.',true);
    }
  }
}
