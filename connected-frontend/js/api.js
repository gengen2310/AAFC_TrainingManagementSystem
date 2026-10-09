// Main TMS module: backend API client -- session token storage, sliding
// refresh, expiry recovery, api()/apiErr()/gate(), and the toast/job-poll error
// surfaces.
// Extracted verbatim from connected-frontend/index.html (stabilisation Phase 4,
// C6). Top-level function declarations and side-effect-free let/const only;
// loaded as a classic script BEFORE the inline bootstrap, so everything here
// is defined before any page-load code runs. Statements with load-time
// effects stay in index.html in their original order. Parity is proven by
// tools/architecture/frontend_parity.mjs.

function tokenGet(){return sessionStorage.getItem('aafc_token')||'';}   // JWT only; never codes/data
function tokenSet(t){if(t){sessionStorage.setItem('aafc_token',t);_scheduleRefresh();}}
function tokenClear(){sessionStorage.removeItem('aafc_token');_cancelRefresh();}

// ── SESSION-01: sliding refresh ──────────────────────────────────────────────
// /api/auth/refresh has existed since the auth router was written and its own
// docstring says "the frontend calls this endpoint while the current token is
// still valid, so active users are not logged out mid-session". Nothing called
// it, so every session died at ACCESS_TOKEN_TTL_MIN (30) regardless of activity.
//
// The endpoint deliberately REJECTS an expired token (it exists so there is no
// second long-lived credential), which is why this is a proactive timer and not
// a retry-on-401 interceptor -- by the time a 401 arrives it is already too late.
//
// The schedule reads the exp claim from the token itself rather than assuming 30,
// so it stays correct if the server's TTL changes. Reading an unverified claim is
// safe here: it only decides when to ask: the server still verifies every request.
let _refreshTimer=null;
function _jwtExpMs(t){
  try{
    const b=t.split('.')[1].replace(/-/g,'+').replace(/_/g,'/');
    const p=JSON.parse(atob(b.padEnd(b.length+(4-b.length%4)%4,'=')));
    return p&&p.exp ? p.exp*1000 : 0;
  }catch(_){ return 0; }
}
function _cancelRefresh(){ if(_refreshTimer){clearTimeout(_refreshTimer);_refreshTimer=null;} }
function _scheduleRefresh(){
  _cancelRefresh();
  const t=tokenGet(); if(!t) return;
  const exp=_jwtExpMs(t); if(!exp) return;
  const remaining=exp-Date.now();
  if(remaining<=0) return;                       // already dead; the next call surfaces it
  const at=Math.max(30000, Math.floor(remaining*0.6));   // 60% of what is left, never under 30s
  _refreshTimer=setTimeout(async()=>{
    try{
      const out=await api('/api/auth/refresh',{method:'POST'});
      if(out&&out.token) tokenSet(out.token);    // reschedules itself via tokenSet
    }catch(_){
      // A failed refresh needs no handling here: api() routes a 401 through
      // handleSessionExpired(), and a transient network failure simply means the
      // next user action re-surfaces the problem with better context than a toast.
    }
  }, at);
}

// ── SESSION-02: make expiry recoverable ──────────────────────────────────────
// api() threw {kind:'auth'} on a mid-session 401 and nothing handled it, so the
// error landed on whichever of 215 inline apiErr() call sites happened to be
// running -- text on a dead page with no way back. doLogout() already had the
// correct recovery; expiry just never reached it.
function handleSessionExpired(msg){
  _cancelRefresh();
  S={sqn:null,isAdmin:false,isWing:false,session:null,pns:[],facs:[],acts:[],rooms:[],equip:[],cfg:{},curr:[],reports:{}};
  try{ showAuthStep1(); }catch(_){}
  const scr=document.getElementById('auth-screen');
  if(scr) scr.style.display='flex';
  const err=document.querySelector('#auth-screen .auth-err');
  if(err){ err.textContent=msg; err.style.display=''; }
}
async function api(path, opts={}){
  const headers=Object.assign({'Content-Type':'application/json'}, opts.headers||{});
  const t=tokenGet(); if(t)headers['Authorization']='Bearer '+t;
  // Auto-serialize plain JS objects so callers don't need to JSON.stringify manually.
  // Strings (already serialised), FormData, Blob, URLSearchParams pass through unchanged.
  let fetchOpts={...opts,headers,credentials:'include'};
  if(fetchOpts.body!==undefined&&fetchOpts.body!==null
     &&typeof fetchOpts.body==='object'
     &&!(fetchOpts.body instanceof FormData)
     &&!(fetchOpts.body instanceof Blob)
     &&!(fetchOpts.body instanceof URLSearchParams)){
    fetchOpts.body=JSON.stringify(fetchOpts.body);
  }
  let res;
  // Single-replica deployments (see .claude/rules/deployment.md) have no overlap
  // between the old and new container during a redeploy -- a real, brief
  // (typically well under a second) connectivity gap, not a stuck backend.
  // Retry transient network failures with backoff before surfacing an error,
  // but only for GET (safe/idempotent) -- fetch() can throw after a request
  // already reached the server, so retrying a write here risks a duplicate.
  // 502/503/504 are the same class of transient gap seen as an HTTP response
  // instead of a raw connection failure (e.g. a proxy/edge in front of the
  // backend) -- retried the same way, still GET-only.
  const method=(fetchOpts.method||'GET').toUpperCase();
  const maxAttempts=method==='GET'?3:1;
  const RETRYABLE_STATUS=new Set([502,503,504]);
  for(let attempt=1;;attempt++){
    try{
      res=await fetch(API_BASE+path,fetchOpts);
      if(RETRYABLE_STATUS.has(res.status)&&attempt<maxAttempts){
        // MM-01: 503 with maintenance_mode error code is not transient -- skip retry
        // and show a persistent banner immediately so the user understands why actions fail.
        if(res.status===503){
          let pb=null;try{pb=await res.clone().json();}catch(_){}
          if(pb&&pb.error==='maintenance_mode'){
            _showMaintenanceBanner(pb.message||'System under maintenance.');
            break;
          }
        }
        await new Promise(r=>setTimeout(r,attempt*400));
        continue;
      }
      break;
    }catch(e){
      // A caller-supplied AbortSignal firing (page/scope/year change cancelling
      // a stale in-flight request) throws a DOMException named 'AbortError' --
      // this is an intentional cancellation, not a connectivity failure, and
      // must never be retried or reported as "cannot reach the backend".
      if(e&&e.name==='AbortError'){
        throw {kind:'cancelled', msg:'Request cancelled.'};
      }
      // Any other fetch() throw is a true network failure or CORS preflight block.
      if(attempt>=maxAttempts){
        throw {kind:'network', msg:'Cannot reach the training system. Check your internet connection and try again.'};
      }
      await new Promise(r=>setTimeout(r,attempt*400));
    }
  }
  if(res.status===401){
    const hadSession=!!t;   // t is the token this request was sent with
    tokenClear();
    let b401=null; try{b401=await res.json();}catch(_){}
    const c401=(b401&&b401.detail&&typeof b401.detail==='object'&&b401.detail.error)||'';
    const msg401=c401==='invalid_user'?'Your account has been deactivated. Contact your Wing HQ.':'Your session ended after a period of inactivity. Sign in to continue.';
    // SESSION-02: only a request that CARRIED a token is an expired session. A 401
    // from /auth/login or /auth/lookup means a wrong access code and must stay on
    // the form -- bouncing the user to step 1 on a typo would lose their selection.
    if(hadSession) handleSessionExpired(msg401);
    throw {kind:'auth', status:401, code:c401, msg:msg401};
  }
  let body=null, bodyParseFailed=false;
  try{ body=await res.json(); }catch(_){ bodyParseFailed=true; }
  if(res.ok&&bodyParseFailed){
    // A 2xx with a body that isn't valid JSON is a distinct failure mode from
    // both a network error and an application-level error response -- the
    // request reached the server and "succeeded" by HTTP status, but the
    // payload can't be used. Surfacing it as a generic network failure would
    // be misleading (the backend IS reachable).
    throw {kind:'invalid_response', status:res.status, msg:'The server returned an unreadable response. Try again.'};
  }
  if(!res.ok){
    // Extract structured error code (custom responses only — not present on standard FastAPI errors)
    const code=(body&&body.detail&&typeof body.detail==='object'&&!Array.isArray(body.detail)&&body.detail.error)||(body&&body.error)||'';
    // FastAPI returns detail as: plain string (most 4xx), object with .message (custom), array (422 validation)
    let msg=(body&&body.detail&&typeof body.detail==='object'&&!Array.isArray(body.detail)&&body.detail.message)
      ||(body&&typeof body.detail==='string'&&body.detail)
      ||(body&&body.message)
      ||'';
    // 422 validation array → readable field-error list
    if(res.status===422&&body&&body.detail&&Array.isArray(body.detail)){
      msg='Validation failed: '+body.detail.map(d=>d.msg||d.message||'Field error').join('; ');
    }
    // Status-specific fallbacks when the backend provides no message
    if(!msg){
      if(res.status===400)      msg='Bad request — check the submitted values.';
      else if(res.status===403) msg='Access not permitted.';
      else if(res.status===404) msg='Not found.';
      else if(res.status===422) msg='Some fields are invalid.';
      else if(res.status===429) msg='Too many attempts. Wait a moment and try again.';
      else if(res.status>=500)  msg='Server error. Try again or contact support.';
      else                       msg='Request failed. Try again, or contact your administrator.';
    }
    // Named error codes — human-readable overrides.
    // 'forbidden'/'access_denied' fall back to a generic message only when the
    // backend didn't already supply a specific one (REM-04: permissions.py's
    // require_* helpers now return an actionable message for many forbidden
    // cases -- unconditionally overwriting msg here was discarding it).
    if(code==='maintenance_mode'){
      const maintMsg=msg||'System under maintenance. Try again later.';
      _showMaintenanceBanner(maintMsg); msg=maintMsg;
    }
    if(!msg&&(code==='forbidden'||code==='access_denied')) msg='Access not permitted.';
    if(code==='no_squadron_scope')                       msg='Squadron / Specialist Unit is required for this action.';
    if(code==='out_of_scope')                            msg='This record is outside your authorised scope.';
    if(code==='invalid_status')                          msg='The status value provided is not valid.';
    if(code==='reason_required_not_delivered')           msg='A reason must be provided when setting status to Not Delivered.';
    if(code==='invalid_date_format')                     msg='Date must be in YYYY-MM-DD format.';
    if(code==='invalid_cadet_group')                     msg='Cadet group value is not recognised.';
    if(code==='no_parade_night_linked')                  msg='No parade night is linked to this planning date. Ensure the year is set up correctly.';
    if(code==='parade_night_not_found')                  msg='Parade night not found.';
    if(code==='planning_year_not_found')                 msg='Year not found.';
    if(code==='override_requires_reason')                msg='A reason is required to override an identified conflict.';
    if(res.status===403&&code==='proxy_required')        msg='Proxy Mode required. Enter a reason before making changes to this squadron.';
    if(res.status===403&&code==='intervention_required') msg='Delegated Intervention Mode required. Enter a reason before making changes.';
    if(res.status===422&&code==='squadron_id_required')  msg='Squadron / Specialist Unit is required.';
    if(res.status===422&&code==='wing_id_required')      msg='Wing is required.';
    if(res.status===409&&code==='code_exists'&&body&&body.detail&&body.detail.message) msg=body.detail.message;
    if(res.status===409&&code==='tag_already_exists') msg='A tag with that name already exists.';
    if(res.status===429 && !msg) msg='Too many attempts. Wait a moment and try again.';
    if(res.status===409&&code==='resource_conflict') msg='This facilitator or room is already booked for that period.';
    if(code==='duplicate_date')                         msg='A Parade Night already exists on that date.';
    if(code==='parade_night_closed')                    msg='This Parade Night is closed and cannot be modified.';
    if(code==='already_archived')                       msg='This record has already been archived.';
    if(code==='not_archived')                           msg='This record is not archived.';
    if(code==='planning_year_already_exists')           msg='A year for this period already exists.';
    if(code==='cross_squadron'||code==='cross_squadron_copy_not_permitted'||code==='cross_squadron_move_forbidden') msg='This record belongs to a different Squadron.';
    if(code==='publish_blocked')                        msg='Cannot publish — some sessions are missing required information. Check facilitators and rooms before publishing.';
    if(code==='close_blocked')                          msg='Cannot close this Parade Night — some sessions are still Planned. Record outcomes first.';
    if(code==='invalid_training_class')                 msg='Training Class not found or does not belong to this Squadron.';
    if(code==='training_class_wrong_squadron')          msg='That Training Class belongs to a different Squadron.';
    if(code==='training_stage_not_found')               msg='Training Stage not found — it may have been archived.';
    if(code==='training_year_not_found_for_squadron')   msg='No year found for this Squadron. Create one in Getting Started.';
    if(code==='reason_required')                        msg='A reason is required for this action.';
    if(code==='name_required')                          msg='A name is required.';
    if(code==='name_exists')                            msg='A record with that name already exists.';
    if(code==='source_not_found')                       msg='Source Parade Night not found.';
    if(code==='target_not_found'||code==='target_parade_night_not_found') msg='Target Parade Night not found.';
    // body is included (not just code/msg) so callers that need structured detail --
    // e.g. the scheduling conflict prompt's list of which facilitator/room clashed --
    // don't have to re-fetch or re-parse; existing callers only ever destructured
    // kind/status/code/msg and are unaffected by this additive field.
    throw {kind:'http', status:res.status, code, msg, body};
  }
  // Successful response — maintenance mode has ended; hide the banner.
  _hideMaintenanceBanner();
  return body;
}
function apiErr(e){
  if(!e) return 'Something went wrong.';
  if(e.msg) return e.msg;
  // WRITE-04: fetch() rejects with a TypeError for network-level failures
  // (offline, backend unreachable, CORS) -- its raw message ("Failed to
  // fetch" / "NetworkError when attempting to fetch resource.", wording
  // varies by browser) is a technical detail, not something a non-technical
  // operational user should see verbatim. Every other Error thrown in this
  // file is a deliberate, already-human-readable message (e.g.
  // _downloadExport's own curated Error) and is left untouched below --
  // matches the friendly text already used for the equivalent case in the
  // Planning Workspace (ApiError.friendly's isNetwork branch).
  if(e instanceof TypeError && /fetch|network/i.test(e.message||'')) return 'Cannot reach the training system. Check your internet connection and try again.';
  if(e instanceof Error) return e.message||'Unexpected error.';
  return 'Something went wrong.';
}
// gate() is retained for any residual call sites; normal SQN admin work should not reach this.
function gate(n){ showToast((n||'This action')+' is not available in this build. If you see this message, please report which action triggered it.', true); }

// ── Toast: non-blocking, accessible replacement for alert() in the outcome workflow ──
function showToast(msg, isErr){
  const region=document.getElementById('toast-region');
  const t=document.createElement('div');
  t.className='toast '+(isErr?'err':'ok');
  t.setAttribute('role',isErr?'alert':'status');
  t.textContent=msg;
  region.appendChild(t);
  setTimeout(()=>t.remove(),isErr?7000:4000);
}

// ── Background-job polling toast (DEF-09) ─────────────────────────────
// Shows a persistent progress toast while a background job runs.
// Polls GET /api/jobs/{jobId} every 2 s until the job reaches a terminal
// state (succeeded / failed), then auto-dismisses.
function _jobPollToast(label, jobId) {
  const region = document.getElementById('toast-region');
  const t = document.createElement('div');
  t.className = 'toast job';
  t.setAttribute('role', 'status');
  t.setAttribute('aria-live', 'polite');
  function _setText(spin, text) {
    t.innerHTML = (spin ? '<span class="job-spin" aria-hidden="true"></span>' : '') + esc(text);
  }
  _setText(true, label);
  region.appendChild(t);
  let done = false;
  function _poll() {
    if (done) return;
    api('/api/jobs/' + encodeURIComponent(jobId))
      .then(j => {
        if (j.status === 'succeeded') {
          done = true;
          t.className = 'toast ok'; t.setAttribute('role', 'alert');
          _setText(false, 'Export complete.');
          setTimeout(() => t.remove(), 5000);
        } else if (j.status === 'failed') {
          done = true;
          t.className = 'toast err'; t.setAttribute('role', 'alert');
          _setText(false, 'Export failed: ' + (j.error_message || 'Unexpected error — check your connection and try again.'));
          setTimeout(() => t.remove(), 9000);
        } else {
          const pct = j.progress_percentage || 0;
          _setText(true, label + (pct > 0 ? ' — ' + pct + '%' : ''));
          setTimeout(_poll, 2000);
        }
      })
      .catch(() => { if (!done) setTimeout(_poll, 3000); });
  }
  // Poll immediately — sync fallback is already terminal on first call.
  _poll();
}

function exportProgramItemsCSV() {
  _downloadExport('/api/export/program-items.csv','program-items.csv');
}

// Shared manual-refresh pattern for primary pages (Training Dashboard,
// Activities, Calendar, Account Management) -- matches the one precedent
// already in this app (System Console's own Refresh button), just factored
// out so each page doesn't hand-roll the same "Refreshing… / Updated at /
// failed, Retry" states. Filters/scope/selected date are untouched since
// this only re-runs the page's own loader, never a full reload.
async function _pageRefresh(statusElId, loaderFn){
  const el=document.getElementById(statusElId);
  if(el){ el.textContent='Refreshing…'; el.style.color='var(--muted)'; }
  try{
    await loaderFn();
    if(el){ el.textContent='Updated at '+new Date().toLocaleTimeString('en-AU',{hour:'2-digit',minute:'2-digit',hour12:false}); el.style.color='var(--muted)'; }
  }catch(e){
    if(el){ el.textContent='Refresh failed — try again'; el.style.color='var(--red)'; }
    showToast('Refresh failed: '+apiErr(e), true);
  }
}
