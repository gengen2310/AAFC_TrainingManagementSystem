# Unit Type Lock Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent `sqn_admin` from changing a squadron's `unit_type`; wing/national/system admins retain full edit rights.

**Architecture:** Backend guard in the existing PATCH handler rejects changed `unit_type` values from `sqn_admin` callers with HTTP 403. Frontend disables the `s-unit-type` select and adds a note for `sqn_admin` users. No schema migration; no new endpoints.

**Tech Stack:** FastAPI, SQLAlchemy, Python 3.13; plain HTML/CSS/JS single-file SPA.

## Global Constraints

- No migration required — `unit_type` column already exists on `Squadron`
- 403 error message must use human-readable role names: `"wing or national admin"` not `"wing_admin or national_admin"`
- Sending the current `unit_type` value unchanged must succeed with 200 (no-op update allowed for `sqn_admin`)
- `sqn_general` and `auditor` are already blocked before this guard by `require_can_write_squadron` — no additional check needed for them
- All JS changes must remain outside the command palette IIFE (this is a separate settings form)
- Do not remove the `unit_type` field from `SquadronUpdateIn` — the guard lives in the handler, not the schema

---

### Task 1: Backend guard + tests

**Files:**
- Modify: `backend/app/routers/organisations.py:532-576` (`update_squadron` handler)
- Modify: `backend/tests/test_organisations.py:231-241` (update broken existing test + add new tests)

**Interfaces:**
- Consumes: existing `update_squadron(squadron_id, body, db, p)` at line 532; `require_can_write_squadron` at line 538; `Squadron` model with `unit_type: str` field
- Produces: HTTP 403 `{"error": "unit_type_locked", "message": "Unit type can only be changed by wing or national admin."}` when `sqn_admin` tries to change `unit_type`

- [ ] **Step 1: Write the failing tests**

Open `backend/tests/test_organisations.py`. The existing `test_patch_squadron_unit_type` (line 231) currently tests that `sqn_admin` CAN change unit_type — after the guard it will return 403. Update it and add three new tests:

```python
def test_sqn_admin_cannot_change_unit_type(client):
    """sqn_admin must get 403 when trying to change unit_type."""
    h = login(client, "ADMIN703")
    sqn_id = _get_sqn_id(client, h)
    r = client.patch(f"/api/squadrons/{sqn_id}", headers=h,
                     json={"unit_type": "specialist_squadron"})
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "unit_type_locked"


def test_sqn_admin_can_send_same_unit_type(client):
    """sqn_admin sending the current unit_type unchanged must succeed (no-op)."""
    h = login(client, "ADMIN703")
    sqn_id = _get_sqn_id(client, h)
    # Get current unit_type
    sqns = client.get("/api/squadrons", headers=h).json()
    current = next(s["unit_type"] for s in sqns if s["squadron_id"] == sqn_id)
    r = client.patch(f"/api/squadrons/{sqn_id}", headers=h,
                     json={"unit_type": current})
    assert r.status_code == 200


def test_sqn_admin_can_edit_other_settings(client):
    """sqn_admin can still PATCH other fields (regression guard)."""
    h = login(client, "ADMIN703")
    sqn_id = _get_sqn_id(client, h)
    r = client.patch(f"/api/squadrons/{sqn_id}", headers=h,
                     json={"address": "999 Test St"})
    assert r.status_code == 200
    # Restore
    client.patch(f"/api/squadrons/{sqn_id}", headers=h, json={"address": ""})


def test_wing_admin_can_change_unit_type(client):
    """wing_admin must be able to change unit_type of a squadron in their wing."""
    h = login(client, "ADMIN7WG")
    sqn_id = _get_sqn_id(client, h)
    # Change to specialist_squadron
    r = client.patch(f"/api/squadrons/{sqn_id}", headers=h,
                     json={"unit_type": "specialist_squadron"})
    assert r.status_code == 200, r.text
    sqns = client.get("/api/squadrons", headers=h).json()
    s = next(x for x in sqns if x["squadron_id"] == sqn_id)
    assert s["unit_type"] == "specialist_squadron"
    # Restore
    client.patch(f"/api/squadrons/{sqn_id}", headers=h,
                 json={"unit_type": "standard_squadron"})
```

Also **replace** the old `test_patch_squadron_unit_type` (lines 231–241) with `test_wing_admin_can_change_unit_type` above — they test the same endpoint but the old one used sqn_admin which is now forbidden. Delete the old function entirely.

- [ ] **Step 2: Run the new tests to verify they fail (before implementation)**

```bash
cd backend && source .venv/bin/activate
python -m pytest tests/test_organisations.py::test_sqn_admin_cannot_change_unit_type \
                  tests/test_organisations.py::test_sqn_admin_can_send_same_unit_type \
                  tests/test_organisations.py::test_sqn_admin_can_edit_other_settings \
                  tests/test_organisations.py::test_wing_admin_can_change_unit_type -v
```

Expected: `test_sqn_admin_cannot_change_unit_type` FAILS (gets 200, expects 403). The others may pass already — that's fine.

- [ ] **Step 3: Add the backend guard**

Open `backend/app/routers/organisations.py`. Find `update_squadron` (line 532). After line 538 (`require_can_write_squadron(p, s.id, s.wing_id)`), insert the guard:

```python
    if (
        body.unit_type is not None
        and body.unit_type != s.unit_type
        and p.role == "sqn_admin"
    ):
        raise HTTPException(403, detail={"error": "unit_type_locked",
                                         "message": "Unit type can only be changed by wing or national admin."})
```

The file at that location currently looks like:

```python
    require_can_write_squadron(p, s.id, s.wing_id)
    if body.name is not None:
```

Insert the guard between those two lines.

- [ ] **Step 4: Run the tests to verify they all pass**

```bash
python -m pytest tests/test_organisations.py::test_sqn_admin_cannot_change_unit_type \
                  tests/test_organisations.py::test_sqn_admin_can_send_same_unit_type \
                  tests/test_organisations.py::test_sqn_admin_can_edit_other_settings \
                  tests/test_organisations.py::test_wing_admin_can_change_unit_type -v
```

Expected: all 4 PASS.

- [ ] **Step 5: Run the full test suite to check for regressions**

```bash
python -m pytest tests/ -q --tb=short
```

Expected: same pass/skip/fail counts as before (baseline: 1777+ passed, ≤7 skipped, 2 pre-existing failures).

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/organisations.py backend/tests/test_organisations.py
git commit -m "feat: lock unit_type to wing/national/system_admin only"
```

---

### Task 2: Frontend — disable unit_type select for sqn_admin

**Files:**
- Modify: `connected-frontend/index.html:1535-1544` (Unit Type form row HTML)
- Modify: `connected-frontend/index.html:4943` (`renderSettings()` population block)

**Interfaces:**
- Consumes: `S.role` (session role string); `document.getElementById('s-unit-type')` (the select); `renderSettings()` function (already exists, called when settings page loads)
- Produces: `s-unit-type` select is `disabled` and `s-unit-type-note` span shows "Set by wing or national admin" when `S.role === 'sqn_admin'`; both are reset for other roles

- [ ] **Step 1: Add the note span to the HTML**

Find the Unit Type form row in `connected-frontend/index.html` (around line 1535):

```html
<div class="ff"><label for="s-unit-type">Unit Type</label>
  <select id="s-unit-type" aria-label="Unit type">
```

After the closing `</select>` tag of the `s-unit-type` select, add:

```html
<span id="s-unit-type-note" class="muted" style="font-size:11px;margin-left:6px"></span>
```

The full block should look like:

```html
<div class="ff"><label for="s-unit-type">Unit Type</label>
  <select id="s-unit-type" aria-label="Unit type">
    <option value="standard_squadron">Standard Squadron</option>
    <option value="specialist_squadron">Specialist Squadron</option>
    <option value="specialist_flight">Specialist Flight</option>
    <option value="support_unit">Support Unit</option>
  </select>
  <span id="s-unit-type-note" class="muted" style="font-size:11px;margin-left:6px"></span>
</div>
```

Read the actual current HTML at lines 1535–1545 before editing to get the exact existing option values and whitespace.

- [ ] **Step 2: Add the disable/enable logic to renderSettings()**

Find the block in `renderSettings()` (around line 4943) that sets `s-unit-type`:

```javascript
setVal('s-crest',S.cfg.crestUrl||''); setVal('s-unit-type',S.cfg.unitType||'standard_squadron'); _renderCrestPreview();
```

After that line, add:

```javascript
const _utSel = document.getElementById('s-unit-type');
const _utNote = document.getElementById('s-unit-type-note');
if (_utSel) _utSel.disabled = (S.role === 'sqn_admin');
if (_utNote) _utNote.textContent = (S.role === 'sqn_admin') ? 'Set by wing or national admin' : '';
```

- [ ] **Step 3: Verify JS syntax is clean**

```bash
node --check connected-frontend/index.html 2>&1 | head -5
```

Expected: no output (no errors).

- [ ] **Step 4: Manual smoke test**

Start the backend and frontend:

```bash
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000 &
cd connected-frontend && python3 -m http.server 8080 &
```

1. Open `http://localhost:8080`, log in as `ADMIN703` (sqn_admin)
2. Navigate to Unit Settings
3. Confirm the Unit Type select is **disabled** and the note "Set by wing or national admin" is visible
4. Confirm all other fields (address, parade day, etc.) are still editable
5. Confirm Save Settings succeeds (check network tab — 200 from PATCH)
6. Log out, log in as `ADMIN7WG` (wing_admin for 703's wing) — navigate to a squadron's settings if reachable
7. Confirm Unit Type select is **enabled** for wing_admin

If you cannot run the servers, note it in your report and rely on the backend tests for correctness verification.

- [ ] **Step 5: Commit**

```bash
git add connected-frontend/index.html
git commit -m "feat: disable unit_type select for sqn_admin in Unit Settings"
```
