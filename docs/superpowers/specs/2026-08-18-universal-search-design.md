# Universal Search — Design Spec

**Date:** 2026-08-18  
**Sub-project:** C — Universal Search  
**Fixes:** Staging audit finding B-3 (global search returns zero results for facilitators, units, users)

---

## Goal

Extend the existing ⌘K command palette so a user can type any name, code, date, or keyword and find facilitators, wings, squadrons, user accounts, activities, and sessions — in addition to the existing pages, curriculum items, and parade nights. All results are scoped to what the caller is permitted to see.

---

## Architecture

Two layers compose the final result list:

**Layer 1 — client-side (unchanged):** Pages, curriculum items, and parade nights stay in the existing `_searchLocal(q)` function (renamed from `_search`). These render immediately on every keystroke with zero latency.

**Layer 2 — backend entity search:** A new `GET /api/search?q={query}` endpoint returns facilitators, accounts, wings, squadrons, activities, and sessions, scoped by the caller's principal. The frontend fires this debounced (200 ms) for queries ≥ 2 characters and merges the results below the local hits.

**Two-phase rendering:**  
1. On each keystroke → render local results immediately  
2. On backend response → append entity results below local results  
3. While backend call is in flight → show a subtle "Searching…" line below local results  
4. If the query changes before the response arrives → discard the stale response

---

## Backend

### New file: `backend/app/routers/search.py`

```python
router = APIRouter(prefix="/api", tags=["search"])
```

### Endpoint

```
GET /api/search?q={query}
```

- **Auth:** Bearer token required (same `get_principal` dependency as all other routers)
- **Min query length:** 2 characters. Return `{"results": []}` for shorter queries.
- **Results per category:** 5 max. Total response cap: 30 results.
- **Soft-deleted records excluded:** all queries add `Model.is_deleted.is_(False)` (or `== False` for non-nullable columns).

### Scope rules

| Entity | sqn_admin / sqn_general | wing_admin | national_admin | system_admin |
|--------|------------------------|------------|----------------|--------------|
| Facilitators | `squadron_id == p.squadron_id` | `wing_id == p.wing_id` | all | all |
| Accounts (Users) | `squadron_id == p.squadron_id` | `wing_id == p.wing_id` | all | all |
| Wings | `wing_id == p.wing_id` (own wing only) | `wing_id == p.wing_id` | all | all |
| Squadrons | `squadron_id == p.squadron_id` (own sqn only) | `wing_id == p.wing_id` | all | all |
| Activities | `squadron_id == p.squadron_id` OR `wing_id == p.wing_id` (see note) | `wing_id == p.wing_id` | all | all |
| Sessions | `squadron_id == p.squadron_id` | `wing_id == p.wing_id` (via join to ParadeNight) | all | all |

**Activity scope note:** For sqn_admin/sqn_general, return activities where `squadron_id == p.squadron_id` OR (`owning_level == 'wing'` AND `wing_id == p.wing_id`). This matches the existing Activities page behaviour.

**Archived/inactive accounts:** Include `active_status == True` users only (i.e., exclude disabled accounts).

### Search matching

All text matching is case-insensitive using SQLAlchemy `.ilike(f"%{q}%")`. For SQLite compatibility do **not** use PostgreSQL-specific `func.lower()` — `.ilike()` works on both.

| Entity | Fields searched |
|--------|----------------|
| Facilitator | `first_name`, `last_name`, `(first_name + ' ' + last_name)` effectively via OR |
| User (account) | `display_name`, `role` |
| Wing | `name`, `code` |
| Squadron | `name`, `short_name`, `code` |
| Activity | `activity_name`, `activity_type`, `date_start`, `location` |
| Session | `curriculum_title_at_time`, `curriculum_code_at_time`, `session_title`, `custom_title` |

### Response shape

```json
{
  "results": [
    {
      "type": "facilitator",
      "id": "<facilitator_id>",
      "label": "Sgt Jane Smith",
      "sub": "701 SQN · 7 Wing",
      "meta": {
        "first_name": "Jane",
        "last_name": "Smith",
        "squadron_id": "<uuid>"
      }
    },
    {
      "type": "account",
      "id": "<user_id>",
      "label": "Capt John Doe",
      "sub": "sqn_admin · 701 SQN",
      "meta": {}
    },
    {
      "type": "wing",
      "id": "<wing_id>",
      "label": "7 Wing",
      "sub": "7WG",
      "meta": { "code": "7WG" }
    },
    {
      "type": "squadron",
      "id": "<squadron_id>",
      "label": "701 Squadron — Bullsbrook",
      "sub": "7 Wing",
      "meta": { "code": "701", "wing_id": "<uuid>" }
    },
    {
      "type": "activity",
      "id": "<activity_id>",
      "label": "RCAF Day Parade",
      "sub": "Wing Activity · 2026-06-15",
      "meta": {}
    },
    {
      "type": "session",
      "id": "<session_id>",
      "label": "Air & Space — Introduction",
      "sub": "701 SQN · 2026-03-15",
      "meta": { "pn_date": "2026-03-15" }
    }
  ]
}
```

The `sub` field for sessions is built by joining `Session` → `ParadeNight` (on `session.parade_night_id = parade_night.id`) to get the `date`. The session label uses `curriculum_title_at_time or custom_title or session_title` (first non-null).

### Router registration

In `backend/app/main.py`:
1. Add `from .routers import ... search` to the existing import line
2. Add `search.router` to the `for r in (...)` list

### Tests

New file: `backend/tests/test_search.py`

Required test cases:
- `test_search_requires_auth` — unauthenticated call returns 401
- `test_search_short_query_returns_empty` — `q=a` (1 char) returns `{"results": []}`
- `test_search_facilitator_by_name` — sqn_admin finds their facilitator by last name
- `test_search_wing_admin_scope` — wing_admin finds facilitators in their wing only (not other wings)
- `test_search_system_admin_cross_org` — system_admin finds a facilitator from a different squadron
- `test_search_accounts_by_name` — sqn_admin finds their own account by display_name
- `test_search_activity_by_name` — finds activity by `activity_name`
- `test_search_session_by_curriculum` — finds session by `curriculum_title_at_time`
- `test_search_excludes_deleted` — soft-deleted facilitator does not appear in results

---

## Frontend (`connected-frontend/index.html`)

### Rename existing function

`_search(q)` → `_searchLocal(q)` (returns HTML string for pages + curriculum + parade nights — logic unchanged).

### IIFE scope requirement

**All new variables and functions below must be declared INSIDE the existing IIFE** (`(function(){ … })()`), not at top-level. The IIFE already owns `_open`, `_idx`, `_results`, `openPalette`, `closePalette`, `_run`, `_score`, `_search` — these must remain accessible to the new code via shared closure.

### New variables (inside the IIFE, near the top with `_open`, `_idx`, `_results`)

```javascript
let _searchTimer = null;
let _backendResults = [];
let _backendQueryRef = '';  // tracks which query the in-flight request belongs to
```

### Modified input handler

Replace the existing `inp.addEventListener('input', ...)` inside the `DOMContentLoaded` listener:

```javascript
inp.addEventListener('input', function () {
  const q = this.value;
  _idx = 0;
  _backendResults = [];
  // Render local results immediately
  document.getElementById('cmd-palette-results').innerHTML =
    _searchLocal(q) + (q.length >= 2 ? '<div class="cp-hint cp-searching">Searching…</div>' : '');
  // Debounced backend fetch
  clearTimeout(_searchTimer);
  if (q.length >= 2) {
    _backendQueryRef = q;
    _searchTimer = setTimeout(() => _fetchEntityResults(q), 200);
  }
});
```

### New function: `_fetchEntityResults(q)`

```javascript
function _fetchEntityResults(q) {
  api('/api/search?q=' + encodeURIComponent(q))
    .then(function (data) {
      if (q !== _backendQueryRef) return; // stale response — discard
      _backendResults = (data.results || []);
      // Re-render: local results + entity results
      const localHtml = _searchLocal(q);
      const entityHtml = _renderEntityResults(_backendResults);
      document.getElementById('cmd-palette-results').innerHTML = localHtml + entityHtml;
      // Rebuild _results array used by keyboard nav — append entity results
      _backendResults.forEach(r => _results.push({
        score: 1,
        cat: _entityCat(r.type),
        label: r.label,
        sub: r.sub || '',
        action: r.type,
        target: r.id,
        meta: r.meta || {}
      }));
    })
    .catch(function () {
      // Silently remove "Searching…" on error; local results stay visible
      document.querySelectorAll('.cp-searching').forEach(el => el.remove());
    });
}
```

### New function: `_renderEntityResults(results)`

```javascript
function _renderEntityResults(results) {
  if (!results.length) return '';
  const startIdx = _results.length; // local results already in _results
  return results.map((r, i) => {
    const idx = startIdx + i;
    return `<div class="cp-result" onclick="_cpRun(${idx})" onmouseover="_cpHover(${idx})" role="option" aria-selected="false">
      <span class="badge ${_entityBadgeClass(r.type)}" style="font-size:10px;margin-right:6px">${esc(_entityCat(r.type))}</span>
      <span style="font-weight:700;font-size:12.5px">${esc(r.label)}</span>
      ${r.sub ? `<span style="font-size:11px;color:var(--muted);margin-left:6px">${esc(r.sub)}</span>` : ''}
    </div>`;
  }).join('');
}
```

### Helper functions

```javascript
function _entityCat(type) {
  return { facilitator:'Facilitator', account:'Account', wing:'Wing',
           squadron:'Squadron', activity:'Activity', session:'Session' }[type] || type;
}

function _entityBadgeClass(type) {
  return { wing:'b-dark', squadron:'b-royal', activity:'b-steel',
           session:'b-grey', facilitator:'b-grey', account:'b-grey' }[type] || 'b-grey';
}
```

### Extended `_run(r)` function

Add handlers for the new action types:

```javascript
// existing:
if (r.action === 'nav')  nav(r.target);
else if (r.action === 'curr') showCurrDetail(r.target);
else if (r.action === 'pn')  navToScheduledPN(r.target);
else if (r.action === 'fac') nav('facilitators');  // ← existing (current scope only)

// new:
else if (r.action === 'facilitator') {
  nav('facilitators');
  const nameVal = r.label; // full display name from label
  const el = document.getElementById('fac-search');
  if (el) { el.value = nameVal; if (typeof renderFacs === 'function') renderFacs(); }
}
else if (r.action === 'account') {
  nav('accounts');
  const el = document.getElementById('acct-search');
  if (el) { el.value = r.label; if (typeof renderAccounts === 'function') renderAccounts(); }
}
else if (r.action === 'wing') {
  if (S.role === 'system_admin' && typeof saSelectWing === 'function') {
    saSelectWing(r.target);
  } else {
    nav('wing-overview');
  }
}
else if (r.action === 'squadron') {
  if (S.role === 'system_admin' && typeof saSelectSquadron === 'function') {
    saSelectSquadron(r.target);
  } else {
    nav('dashboard');
  }
}
else if (r.action === 'activity') {
  nav('activities');
  const el = document.getElementById('act-search');
  if (el) { el.value = r.label; if (typeof renderActs === 'function') renderActs(); }
}
else if (r.action === 'session') {
  if (r.meta && r.meta.pn_date) navToScheduledPN(r.meta.pn_date);
  else nav('parade-nights');
}
```

### CSS — new badge classes

Add to the existing `<style>` block near `.cp-hint` and `.cp-result`:

```css
.b-dark  { background: var(--dark);  color: #fff; }
.b-royal { background: var(--royal); color: #fff; }
.b-steel { background: var(--steel); color: #fff; }
.b-grey  { background: var(--lgrey); color: var(--text-2); }  /* already exists as .badge.b-grey if so, skip */
.cp-searching { font-style: italic; }
```

### Placeholder text

Change both occurrences of the `cmd-palette-input` placeholder and the initial hint `div` to a single space `" "`.

```html
<input id="cmd-palette-input" ... placeholder=" " ...>
```

```html
<div class="cp-hint"> </div>
```

---

## Global Constraints

- No schema migration required — search queries only read existing tables
- SQLite-compatible queries only (`.ilike()` not raw `ILIKE` SQL; no `func.lower()` on indexed columns)
- All user-supplied `q` values must be parameterised (never string-interpolated into SQL)
- XSS: all label/sub values inserted via `esc()` or as `textContent` in frontend — never raw innerHTML from API response
- No access-code hashes, no plaintext codes returned in search results
- Soft-deleted records excluded from all result sets
- Disabled accounts (`active_status == False`) excluded from account results
- `auditor` role: wings and squadrons only; facilitators, accounts, activities, sessions excluded (no tenancy — auditor has national read access to org structure only)
- `sqn_general` role: facilitators and activities within own squadron only; accounts excluded; sessions within own squadron included
- The scope table in the Backend section covers `system_admin`, `national_admin`, `wing_admin`, `sqn_admin` explicitly. For `sqn_general`, apply same rules as `sqn_admin`. For `auditor`, query wings and squadrons only (all wings/all squadrons, no other entity types).
- `b-grey` badge class: the existing `<style>` block already has `.badge { … }` but may not have `.b-grey` as a named class — check before adding. The existing palette-result badge is rendered inline with `class="badge b-grey"` in the existing `_search` function; if the class resolves correctly in staging, do not redefine it.
