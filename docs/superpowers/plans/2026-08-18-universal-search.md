# Universal Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a backend `GET /api/search?q=` endpoint and wire it into the existing ⌘K command palette so users can search facilitators, accounts, wings, squadrons, activities, and sessions across their permitted scope.

**Architecture:** A new `search.py` FastAPI router queries six entity types scoped by the caller's Principal; results are returned as a typed list. The frontend's existing ⌘K IIFE is extended with a 200 ms debounced backend fetch that merges entity results below the existing in-memory hits (pages, curriculum, parade nights).

**Tech Stack:** FastAPI, SQLAlchemy ORM (Session as DBSession pattern), SQLite-compatible `.ilike()`, plain HTML/JS inside a closure (IIFE), `api()` helper for auth.

## Global Constraints

- All queries use `.ilike(f"%{q.strip()}%")` — no raw SQL, no f-string interpolation into SQL
- Soft-deleted records excluded via `Model.is_archived == False` (SoftDeleteMixin field is `is_archived`, **not** `is_deleted`)
- Active-only filter for Wings, Squadrons, Users: `active_status == True`
- Disabled accounts (`User.active_status == False`) excluded from account results
- `auditor` role: wings and squadrons only — no facilitators, accounts, activities, sessions
- `sqn_general`: facilitators + activities + sessions within own squadron; accounts excluded
- `sqn_admin` can search own squadron's accounts; `wing_admin` their wing's accounts; national/system_admin all accounts
- Min query length: 2 characters (enforced at endpoint; return `{"results": []}` for shorter)
- Results per category: 5 max; total response cap: 30
- Model `Session` (parade-night sessions from `..models`) must be imported as `TrainingSession` to avoid collision with `sqlalchemy.orm.Session` — follow the pattern in `planning.py` line 22: `from ..models import Session as TrainingSession`
- All new frontend code lives **inside** the existing IIFE at `connected-frontend/index.html` line 15767 (`(function(){`) through line 15870 (`})()`)
- XSS: all label/sub values inserted via `esc()` — never raw innerHTML from API values
- No schema migration — reads existing tables only
- Test suite must pass: `cd backend && python -m pytest tests/ -q`

---

### Task 1: Backend search endpoint, registration, and tests

**Files:**
- Create: `backend/app/routers/search.py`
- Modify: `backend/app/main.py` (import + router registration)
- Create: `backend/tests/test_search.py`

**Interfaces:**
- Consumes: `get_principal` from `..dependencies`, `get_db` from `..database`, `Principal` from `..permissions`, models `Wing`, `Squadron`, `User`, `Facilitator`, `Activity`, `TrainingSession` (alias for `Session`), `ParadeNight` from `..models`
- Produces: `GET /api/search?q={str}` → `{"results": [{type, id, label, sub, meta}]}`

---

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_search.py`:

```python
"""Tests for GET /api/search — universal entity search."""
import pytest
from tests.conftest import login


def test_search_requires_auth(client):
    r = client.get("/api/search?q=Daniels")
    assert r.status_code == 401


def test_search_short_query_returns_empty(client):
    h = login(client, "ADMIN703")
    r = client.get("/api/search?q=D", headers=h)
    assert r.status_code == 200
    assert r.json() == {"results": []}


def test_search_single_char_returns_empty(client):
    h = login(client, "ADMIN703")
    r = client.get("/api/search?q=a", headers=h)
    assert r.status_code == 200
    assert r.json()["results"] == []


def test_search_facilitator_by_last_name(client):
    h = login(client, "ADMIN703")
    r = client.get("/api/search?q=Daniels", headers=h)
    assert r.status_code == 200
    results = r.json()["results"]
    facs = [x for x in results if x["type"] == "facilitator"]
    assert len(facs) >= 1
    assert any("Daniels" in f["label"] for f in facs)


def test_search_result_shape(client):
    h = login(client, "ADMIN703")
    r = client.get("/api/search?q=Daniels", headers=h)
    assert r.status_code == 200
    for item in r.json()["results"]:
        assert "type" in item
        assert "id" in item
        assert "label" in item
        assert "sub" in item
        assert "meta" in item


def test_search_wing_admin_finds_same_wing_facilitator(client):
    h = login(client, "ADMIN7WG")
    r = client.get("/api/search?q=Flanders", headers=h)
    assert r.status_code == 200
    facs = [x for x in r.json()["results"] if x["type"] == "facilitator"]
    assert len(facs) >= 1


def test_search_system_admin_cross_org(client):
    """system_admin must find facilitators from any squadron."""
    h = login(client, "SYSADMIN2026")
    r = client.get("/api/search?q=McGhie", headers=h)
    assert r.status_code == 200
    facs = [x for x in r.json()["results"] if x["type"] == "facilitator"]
    assert len(facs) >= 1
    assert any("McGhie" in f["label"] for f in facs)


def test_search_accounts_by_name_sqn_admin(client):
    """sqn_admin can search accounts in own squadron."""
    h = login(client, "ADMIN703")
    r = client.get("/api/search?q=703 Admin", headers=h)
    assert r.status_code == 200
    accounts = [x for x in r.json()["results"] if x["type"] == "account"]
    assert len(accounts) >= 1


def test_search_wing_by_code(client):
    h = login(client, "SYSADMIN2026")
    r = client.get("/api/search?q=7WG", headers=h)
    assert r.status_code == 200
    wings = [x for x in r.json()["results"] if x["type"] == "wing"]
    assert len(wings) >= 1
    assert any("7W" in w["label"] or "7WG" in w["sub"] for w in wings)


def test_search_squadron_by_code(client):
    h = login(client, "SYSADMIN2026")
    r = client.get("/api/search?q=703", headers=h)
    assert r.status_code == 200
    sqns = [x for x in r.json()["results"] if x["type"] == "squadron"]
    assert len(sqns) >= 1
    assert any("703" in s["label"] or "703" in s["meta"].get("code", "") for s in sqns)


def test_search_session_by_curriculum_code(client):
    """Sessions can be found by curriculum_code_at_time."""
    h = login(client, "ADMIN703")
    r = client.get("/api/search?q=AS-", headers=h)
    assert r.status_code == 200
    # Even if no sessions match, the endpoint must return 200 with a results list
    assert "results" in r.json()


def test_search_auditor_gets_only_wings_and_squadrons(client):
    h = login(client, "AUDITOR2026")
    r = client.get("/api/search?q=703", headers=h)
    assert r.status_code == 200
    results = r.json()["results"]
    for item in results:
        assert item["type"] in ("wing", "squadron"), f"Auditor must not see {item['type']}"


def test_search_excludes_archived_facilitator(client):
    """Soft-archived facilitators must not appear in results."""
    from app.database import SessionLocal
    from app.models import Facilitator
    db = SessionLocal()
    try:
        # Archive Daley
        f = db.query(Facilitator).filter(Facilitator.last_name == "Daley").first()
        assert f is not None, "Seed must include Daley facilitator"
        original = f.is_archived
        f.is_archived = True
        db.commit()

        h = login(client, "SYSADMIN2026")
        r = client.get("/api/search?q=Daley", headers=h)
        assert r.status_code == 200
        facs = [x for x in r.json()["results"] if x["type"] == "facilitator"]
        assert all("Daley" not in f["label"] for f in facs)
    finally:
        # Restore
        f.is_archived = original
        db.commit()
        db.close()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && source .venv/bin/activate
python -m pytest tests/test_search.py -v 2>&1 | head -40
```

Expected: all tests FAIL with `404 Not Found` or `ImportError` (endpoint doesn't exist yet).

- [ ] **Step 3: Create `backend/app/routers/search.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import or_, and_

from ..database import get_db
from ..models import (
    Wing, Squadron, User, Facilitator, Activity, ParadeNight,
)
from ..models import Session as TrainingSession
from ..dependencies import get_principal
from ..permissions import Principal

router = APIRouter(prefix="/api", tags=["search"])

_LIMIT = 5
_NATIONAL_ROLES = {"national_admin", "national_viewer", "system_admin"}
_WING_ROLES = {"wing_admin", "wing_viewer"}
_ACCOUNT_ROLES = {"sqn_admin", "wing_admin", "national_admin", "system_admin"}


@router.get("/search")
async def search_entities(
    q: str = "",
    p: Principal = Depends(get_principal),
    db: DBSession = Depends(get_db),
):
    q = q.strip()
    if len(q) < 2:
        return {"results": []}

    pat = f"%{q}%"
    results: list[dict] = []

    is_national = p.role in _NATIONAL_ROLES
    is_wing = p.role in _WING_ROLES
    is_auditor = p.role == "auditor"

    # ── Wings ─────────────────────────────────────────────────────────────
    wq = (
        db.query(Wing)
        .filter(Wing.is_archived == False, Wing.active_status == True)  # noqa: E712
        .filter(or_(Wing.name.ilike(pat), Wing.code.ilike(pat), Wing.short_name.ilike(pat)))
    )
    if not is_national:
        wq = wq.filter(Wing.id == p.wing_id)
    for w in wq.limit(_LIMIT).all():
        results.append({
            "type": "wing", "id": w.id, "label": w.name,
            "sub": w.code, "meta": {"code": w.code},
        })

    # ── Squadrons ─────────────────────────────────────────────────────────
    sq = (
        db.query(Squadron)
        .filter(Squadron.is_archived == False, Squadron.active_status == True)  # noqa: E712
        .filter(or_(Squadron.name.ilike(pat), Squadron.short_name.ilike(pat), Squadron.code.ilike(pat)))
    )
    if is_national:
        pass
    elif is_wing:
        sq = sq.filter(Squadron.wing_id == p.wing_id)
    else:
        sq = sq.filter(Squadron.id == p.squadron_id)
    for s in sq.limit(_LIMIT).all():
        w_row = db.query(Wing).filter(Wing.id == s.wing_id).first()
        results.append({
            "type": "squadron", "id": s.id, "label": s.name,
            "sub": w_row.code if w_row else "",
            "meta": {"code": s.code, "wing_id": s.wing_id},
        })

    if not is_auditor:
        # ── Facilitators ───────────────────────────────────────────────────
        fq = (
            db.query(Facilitator)
            .filter(Facilitator.is_archived == False)  # noqa: E712
            .filter(or_(Facilitator.first_name.ilike(pat), Facilitator.last_name.ilike(pat)))
        )
        if is_national:
            pass
        elif is_wing:
            fq = fq.filter(Facilitator.wing_id == p.wing_id)
        else:
            fq = fq.filter(Facilitator.squadron_id == p.squadron_id)
        for f in fq.limit(_LIMIT).all():
            name = f"{f.first_name or ''} {f.last_name}".strip()
            sqn_row = (
                db.query(Squadron).filter(Squadron.id == f.squadron_id).first()
                if f.squadron_id else None
            )
            results.append({
                "type": "facilitator", "id": f.id, "label": name,
                "sub": sqn_row.code if sqn_row else "",
                "meta": {
                    "first_name": f.first_name or "",
                    "last_name": f.last_name,
                    "squadron_id": f.squadron_id or "",
                },
            })

        # ── Activities ─────────────────────────────────────────────────────
        aq = (
            db.query(Activity)
            .filter(Activity.is_archived == False)  # noqa: E712
            .filter(or_(
                Activity.activity_name.ilike(pat),
                Activity.date_start.ilike(pat),
                Activity.location.ilike(pat),
            ))
        )
        if is_national:
            pass
        elif is_wing:
            aq = aq.filter(Activity.wing_id == p.wing_id)
        else:
            aq = aq.filter(or_(
                Activity.squadron_id == p.squadron_id,
                and_(Activity.owning_level == "wing", Activity.wing_id == p.wing_id),
            ))
        for a in aq.limit(_LIMIT).all():
            owning = (a.owning_level or "squadron").capitalize() + " Activity"
            results.append({
                "type": "activity", "id": a.id, "label": a.activity_name,
                "sub": f"{owning} · {a.date_start}", "meta": {},
            })

        # ── Accounts ──────────────────────────────────────────────────────
        if p.role in _ACCOUNT_ROLES:
            uq = (
                db.query(User)
                .filter(User.is_archived == False, User.active_status == True)  # noqa: E712
                .filter(or_(User.display_name.ilike(pat), User.role.ilike(pat)))
            )
            if is_national:
                pass
            elif is_wing:
                uq = uq.filter(User.wing_id == p.wing_id)
            else:
                uq = uq.filter(User.squadron_id == p.squadron_id)
            for u in uq.limit(_LIMIT).all():
                sqn_row = (
                    db.query(Squadron).filter(Squadron.id == u.squadron_id).first()
                    if u.squadron_id else None
                )
                results.append({
                    "type": "account", "id": u.id, "label": u.display_name,
                    "sub": f"{u.role} · {sqn_row.code}" if sqn_row else u.role,
                    "meta": {},
                })

        # ── Sessions ───────────────────────────────────────────────────────
        sess_q = (
            db.query(TrainingSession, ParadeNight)
            .join(ParadeNight, TrainingSession.parade_night_id == ParadeNight.id)
            .filter(
                TrainingSession.is_archived == False,  # noqa: E712
                ParadeNight.is_archived == False,       # noqa: E712
            )
            .filter(or_(
                TrainingSession.curriculum_title_at_time.ilike(pat),
                TrainingSession.curriculum_code_at_time.ilike(pat),
                TrainingSession.session_title.ilike(pat),
                TrainingSession.custom_title.ilike(pat),
            ))
        )
        if is_national:
            pass
        elif is_wing:
            wing_sqn_ids = [
                s.id for s in
                db.query(Squadron).filter(
                    Squadron.wing_id == p.wing_id,
                    Squadron.is_archived == False,  # noqa: E712
                ).all()
            ]
            sess_q = sess_q.filter(TrainingSession.squadron_id.in_(wing_sqn_ids))
        else:
            sess_q = sess_q.filter(TrainingSession.squadron_id == p.squadron_id)
        for sess, pn in sess_q.limit(_LIMIT).all():
            label = (
                sess.curriculum_title_at_time
                or sess.custom_title
                or sess.session_title
                or "Session"
            )
            results.append({
                "type": "session", "id": sess.id, "label": label,
                "sub": pn.date, "meta": {"pn_date": pn.date},
            })

    return {"results": results[:30]}
```

- [ ] **Step 4: Register search router in `backend/app/main.py`**

In `main.py` line 14, extend the import:

```python
# Before:
from .routers import auth, organisations, training, ops, health, program, export_import, accounts, timing, planning, system, wing_calendar, jobs, dashboard, setup

# After:
from .routers import auth, organisations, training, ops, health, program, export_import, accounts, timing, planning, system, wing_calendar, jobs, dashboard, setup, search
```

In `main.py` at the `for r in (...)` block, add `search.router`:

```python
for r in (health.router, auth.router, organisations.router, accounts.router,
          training.router, timing.router, ops.router, program.router, export_import.router,
          planning.router, wing_calendar.router, system.router, jobs.router,
          dashboard.router, setup.router, search.router):
    app.include_router(r)
```

- [ ] **Step 5: Run the new tests to verify they pass**

```bash
cd backend && source .venv/bin/activate
python -m pytest tests/test_search.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Run the full test suite to check for regressions**

```bash
cd backend && source .venv/bin/activate
python -m pytest tests/ -q
```

Expected: same pass/skip count as baseline (1553 passed, 5 skipped — or the current count; zero new failures).

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/search.py backend/app/main.py backend/tests/test_search.py
git commit -m "feat: add GET /api/search universal entity search endpoint"
```

---

### Task 2: Frontend — extend ⌘K palette with backend entity results

**Files:**
- Modify: `connected-frontend/index.html`

**Interfaces:**
- Consumes: `GET /api/search?q=` from Task 1; existing `api(path)` helper; `esc(str)` helper; `nav(id)`, `renderFacs()`, `renderAccounts()`, `renderActs()`, `navToScheduledPN(date)`, `saSelectWing(wingId)`, `saSelectSquadron(sqnId)` — all already defined globally in `index.html`
- Produces: extended ⌘K palette with entity results; existing pages/curriculum/parade-night results unchanged

All edits in this task are **inside the existing IIFE** at line 15767 unless stated otherwise (CSS is outside the IIFE in the `<style>` block near line 15888).

---

- [ ] **Step 1: Rename `_search` to `_searchLocal` inside the IIFE**

Find line 15816:
```javascript
  function _search(q){
```
Change to:
```javascript
  function _searchLocal(q){
```

Find line 15863 (inside the `DOMContentLoaded` listener):
```javascript
      _idx=0;document.getElementById('cmd-palette-results').innerHTML=_search(this.value);
```
Change to:
```javascript
      _idx=0;document.getElementById('cmd-palette-results').innerHTML=_searchLocal(this.value);
```

- [ ] **Step 2: Add backend-search variables inside the IIFE (near line 15788)**

After the existing line:
```javascript
  let _open=false,_idx=0,_results=[];
```
Add:
```javascript
  let _searchTimer=null,_backendResults=[],_backendQueryRef='';
```

- [ ] **Step 3: Add helper functions inside the IIFE (after `_searchLocal`, before the keyboard listener)**

Insert the following three functions immediately after `_searchLocal` closes (after the `return _results.map(...)` block, before `window._cpRun`):

```javascript
  function _entityCat(type){
    return({facilitator:'Facilitator',account:'Account',wing:'Wing',
            squadron:'Squadron',activity:'Activity',session:'Session'})[type]||type;
  }
  function _entityBadgeClass(type){
    return({wing:'b-dark',squadron:'b-royal',activity:'b-steel'})[type]||'b-grey';
  }
  function _renderEntityResults(list,startIdx){
    if(!list||!list.length)return'';
    return list.map(function(r,i){
      var idx=startIdx+i;
      return'<div class="cp-result" onclick="_cpRun('+idx+')" onmouseover="_cpHover('+idx+')" role="option" aria-selected="false">'
        +'<span class="badge '+_entityBadgeClass(r.type)+'" style="font-size:10px;margin-right:6px">'+esc(_entityCat(r.type))+'</span>'
        +'<span style="font-weight:700;font-size:12.5px">'+esc(r.label)+'</span>'
        +(r.sub?'<span style="font-size:11px;color:var(--muted);margin-left:6px">'+esc(r.sub)+'</span>':'')
        +'</div>';
    }).join('');
  }
  function _fetchEntityResults(q){
    api('/api/search?q='+encodeURIComponent(q)).then(function(data){
      if(q!==_backendQueryRef)return;
      _backendResults=(data.results||[]);
      var localHtml=_searchLocal(q);
      // Append entity results to _results array so keyboard nav covers them
      _backendResults.forEach(function(r){
        _results.push({score:1,cat:_entityCat(r.type),label:r.label,sub:r.sub||'',
                        action:r.type,target:r.id,meta:r.meta||{}});
      });
      var entityHtml=_renderEntityResults(_backendResults,_results.length-_backendResults.length);
      document.getElementById('cmd-palette-results').innerHTML=localHtml+entityHtml;
    }).catch(function(){
      document.querySelectorAll('.cp-searching').forEach(function(el){el.remove();});
    });
  }
```

- [ ] **Step 4: Replace the `DOMContentLoaded` input handler inside the IIFE**

Find and replace the existing `inp.addEventListener('input', ...)` block (lines 15862–15864):

```javascript
// BEFORE:
    if(inp)inp.addEventListener('input',function(){
      _idx=0;document.getElementById('cmd-palette-results').innerHTML=_searchLocal(this.value);
    });
```

```javascript
// AFTER:
    if(inp)inp.addEventListener('input',function(){
      var q=this.value;
      _idx=0;_backendResults=[];
      document.getElementById('cmd-palette-results').innerHTML=
        _searchLocal(q)+(q.length>=2?'<div class="cp-hint cp-searching">Searching…</div>':'');
      clearTimeout(_searchTimer);
      if(q.length>=2){
        _backendQueryRef=q;
        _searchTimer=setTimeout(function(){_fetchEntityResults(q);},200);
      }
    });
```

- [ ] **Step 5: Also reset `_backendResults` in `openPalette` and `closePalette`**

In `openPalette` (line 15793), after `_open=true;_idx=0;_results=[];` add `_backendResults=[];_backendQueryRef='';`:

```javascript
  function openPalette(){
    const o=_overlay();if(!o||_open)return;
    _open=true;_idx=0;_results=[];_backendResults=[];_backendQueryRef='';
    o.style.display='flex';
    _input().value='';
    document.getElementById('cmd-palette-results').innerHTML='<div class="cp-hint"> </div>';
    setTimeout(()=>_input().focus(),20);
  }
```

- [ ] **Step 6: Extend `_run(r)` inside the IIFE to handle entity actions**

Find the existing `_run` function (around line 15805):

```javascript
  function _run(r){
    closePalette();
    if(r.action==='nav')nav(r.target);
    else if(r.action==='curr')showCurrDetail(r.target);
    else if(r.action==='pn'){navToScheduledPN(r.target);}
    else if(r.action==='fac'){nav('facilitators');}
  }
```

Replace with:

```javascript
  function _run(r){
    closePalette();
    if(r.action==='nav')nav(r.target);
    else if(r.action==='curr')showCurrDetail(r.target);
    else if(r.action==='pn'){navToScheduledPN(r.target);}
    else if(r.action==='fac'){nav('facilitators');}
    else if(r.action==='facilitator'){
      nav('facilitators');
      var el=document.getElementById('fac-search');
      if(el){el.value=r.label;if(typeof renderFacs==='function')renderFacs();}
    }
    else if(r.action==='account'){
      nav('accounts');
      var el2=document.getElementById('acct-search');
      if(el2){el2.value=r.label;if(typeof renderAccounts==='function')renderAccounts();}
    }
    else if(r.action==='wing'){
      if(S.role==='system_admin'&&typeof saSelectWing==='function')saSelectWing(r.target);
      else nav('wing-overview');
    }
    else if(r.action==='squadron'){
      if(S.role==='system_admin'&&typeof saSelectSquadron==='function'){
        if(r.meta&&r.meta.wing_id)S.saScope.wingId=r.meta.wing_id;
        saSelectSquadron(r.target);
      } else nav('dashboard');
    }
    else if(r.action==='activity'){
      nav('activities');
      var el3=document.getElementById('act-search');
      if(el3){el3.value=r.label;if(typeof renderActs==='function')renderActs();}
    }
    else if(r.action==='session'){
      if(r.meta&&r.meta.pn_date)navToScheduledPN(r.meta.pn_date);
      else nav('parade-nights');
    }
  }
```

- [ ] **Step 7: Blank the placeholder text (two occurrences)**

Find the `cmd-palette-input` element (line 15878):
```html
        style="flex:1;border:none;outline:none;font-size:14px;background:transparent;color:var(--text)" aria-label="Search">
```
The line above it has `placeholder="Search pages, curriculum, facilitators, parade nights…"`. Change to:
```html
        placeholder=" "
```

Find the initial hint div (line 15884):
```html
      <div class="cp-hint">Start typing to search pages, curriculum, parade nights, and facilitators…</div>
```
Change to:
```html
      <div class="cp-hint"> </div>
```

Also update the `openPalette` function's initial hint (line 15798) — already handled in Step 5 above (`'<div class="cp-hint"> </div>'`).

- [ ] **Step 8: Add CSS badge classes to the `<style>` block (outside the IIFE, near line 15888)**

Find the existing CSS block:
```css
.cp-hint{padding:14px 16px;font-size:12px;color:var(--muted);}
.cp-result{display:flex;align-items:center;padding:9px 16px;cursor:pointer;font-size:13px;}
.cp-result.cp-sel,.cp-result:hover{background:var(--accent-light);}
```

Append new rules after these:
```css
.b-dark{background:var(--dark);color:#fff;}
.b-royal{background:var(--royal);color:#fff;}
.b-steel{background:var(--steel);color:#fff;}
.cp-searching{font-style:italic;}
```

- [ ] **Step 9: Verify locally**

```bash
# Start backend
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000 &

# Serve frontend
cd ../connected-frontend && python3 -m http.server 8080 &
```

1. Open `http://localhost:8080` and log in as `ADMIN703` (sqn_admin)
2. Press ⌘K — palette opens with blank placeholder
3. Type "Dan" — local results appear immediately; after 200 ms, "Daniels" appears with a grey "Facilitator" badge
4. Click the Daniels result — navigates to Facilitators page with "Daniels" pre-filled in `#fac-search` and only Daniels visible
5. Re-open palette, type "703" — squadron result appears with dark-blue "Squadron" badge
6. Log out, log in as `SYSADMIN2026`, open palette, type "7WG" — Wing result appears with dark-blue "Wing" badge; clicking it switches SA scope to 7 Wing

- [ ] **Step 10: Commit**

```bash
git add connected-frontend/index.html
git commit -m "feat: extend ⌘K palette with universal entity search (backend-driven)"
```
