// Main TMS module: dialog core -- openModal/closeModal (per-dialog return
// focus), confirmAction() and promptText(). Extracted verbatim from
// connected-frontend/index.html (stabilisation step 4). Declarations only, no
// load-time side effects, and loaded BEFORE the main inline script so any
// caller -- including code that runs while the page loads -- finds these
// functions defined. Classic-script globals: the main script's Escape handler
// still reads _modalReturnFocusById directly. Document-level listeners (Enter
// in #m-text-input, backdrop clicks) stay in index.html where they were wired.

// ═══════════════════════════════════════════════════════════
//  MODALS
// ═══════════════════════════════════════════════════════════
let _modalReturnFocus=null;
const _modalReturnFocusById=new Map();
function openModal(id){
  const bg=document.getElementById(id);
  if(!bg)return;
  const returnTarget=document.activeElement;
  _modalReturnFocus=returnTarget;
  _modalReturnFocusById.set(id,returnTarget);
  bg.classList.add('active');
  const first=bg.querySelector('input:not([type="hidden"]):not(:disabled),select:not(:disabled),textarea:not(:disabled)')||bg.querySelector('button:not(:disabled),[tabindex]:not([tabindex="-1"]),[href]');
  // Deferred, but never steal focus: if focus is already inside this dialog
  // when the timer fires (the user started typing, or autofill), leave it.
  // An unconditional focus() redirected keystrokes mid-word into the first
  // field (CI REM-111: "Regression" landed in Rank, Family Name stayed empty).
  if(first)setTimeout(()=>{ if(bg.classList.contains('active')&&!bg.contains(document.activeElement))first.focus(); },200);
}
function closeModal(id){
  const bg=document.getElementById(id);
  if(!bg)return;
  bg.classList.remove('active');
  const el=_modalReturnFocusById.get(id)||_modalReturnFocus;
  _modalReturnFocusById.delete(id);
  _modalReturnFocus=null;
  if(!el||!el.focus)return;
  const parentBg=el.closest&&el.closest('.modal-bg');
  if(parentBg&&parentBg.classList.contains('active')){
    const parentDialog=parentBg.querySelector('.modal')||parentBg;
    if(!parentDialog.hasAttribute('tabindex'))parentDialog.setAttribute('tabindex','-1');
    setTimeout(()=>{try{parentDialog.focus();}catch(_){}},0);
    return;
  }
  setTimeout(()=>{try{el.focus();}catch(_){}},0);
}

// REM-106: confirmAction() replaces native confirm() for critical SA/org-
// management operations (archive Wing/Squadron, maintenance mode, account
// disable/reactivate/delete/restore/unlock) -- native confirm() blocks the
// page entirely under browser automation (see .claude/rules/frontend.md).
// Usage: confirmAction('message', () => { ...the code that used to run after
// `if(!confirm(...))return;` ... }). Cancelling simply never calls onConfirm,
// matching confirm()'s own early-return-on-Cancel behaviour exactly.
let _confirmCb=null;
function confirmAction(message, onConfirm, danger){
  document.getElementById('confirm-msg').textContent=message;
  const yesBtn=document.getElementById('confirm-yes-btn');
  yesBtn.className='btn '+(danger?'btn-red':'btn-dk');
  _confirmCb=onConfirm;
  openModal('m-confirm');
}
function _confirmYes(){
  closeModal('m-confirm');
  const cb=_confirmCb; _confirmCb=null;
  if(cb)cb();
}
function _confirmNo(){
  closeModal('m-confirm');
  _confirmCb=null;
}

// ── promptText() — non-blocking replacement for native prompt() ──────────────
// Returns a Promise<string|null>: resolves to the trimmed input string, or null if
// the user cancels. Accepts an options object: { context, defaultValue, okLabel,
// validate(val)->errorString|null, danger }. danger=true renders the confirm button red.
let _tiResolve=null, _tiValidate=null;
function promptText(title,label,{context='',defaultValue='',okLabel='OK',validate=null,danger=false}={}){
  return new Promise(resolve=>{
    _tiResolve=resolve; _tiValidate=validate;
    document.getElementById('ti-title').textContent=title;
    document.getElementById('ti-label').textContent=label;
    const ctx=document.getElementById('ti-context');
    ctx.textContent=context; ctx.style.display=context?'':'none';
    const inp=document.getElementById('ti-input');
    inp.value=defaultValue; inp.setAttribute('aria-label',label);
    document.getElementById('ti-err').textContent='';
    const okBtn=document.getElementById('ti-ok-btn');
    okBtn.textContent=okLabel; okBtn.className='btn '+(danger?'btn-red':'btn-dk');
    openModal('m-text-input');
    setTimeout(()=>{inp.focus();inp.select();},40);
  });
}
function _tiSave(){
  const val=document.getElementById('ti-input').value.trim();
  if(!val){document.getElementById('ti-err').textContent='This field is required.';return;}
  if(_tiValidate){const err=_tiValidate(val);if(err){document.getElementById('ti-err').textContent=err;return;}}
  closeModal('m-text-input');
  const cb=_tiResolve; _tiResolve=null; _tiValidate=null;
  if(cb)cb(val);
}
function _tiCancel(){
  closeModal('m-text-input');
  const cb=_tiResolve; _tiResolve=null; _tiValidate=null;
  if(cb)cb(null);
}
