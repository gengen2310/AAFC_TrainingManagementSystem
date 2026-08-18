# Unit Type Lock — Design Spec

**Date:** 2026-08-18
**Sub-project:** D — Unit Type lock for squadrons + Unit Settings editing restriction
**Fixes:** Prevents squadron-level admins from changing the unit type assigned to their squadron

---

## Goal

Lock the `unit_type` field on a squadron so that only wing admins, national admins, and system admins can change it. Squadron admins can still view the current unit type in their settings page, and can still edit all other Unit Settings fields (address, parade day/time, session count, crest URL, name).

---

## Architecture

A single enforcement layer in the existing PATCH endpoint, plus a disabled control in the frontend settings form. No schema migration, no new endpoint.

---

## Backend

### File: `backend/app/routers/organisations.py`

**Where:** In `update_squadron()`, after `require_can_write_squadron(p, s.id, s.wing_id)` (line 538) and before the `unit_type` assignment block (line 561).

**Guard to insert:**

```python
if (
    body.unit_type is not None
    and body.unit_type != s.unit_type
    and p.role == "sqn_admin"
):
    raise HTTPException(403, detail={"error": "unit_type_locked",
                                     "message": "Unit type can only be changed by wing or national admin."})
```

Note: `require_can_write_squadron` already blocks `sqn_general` and `auditor` from writing, so only `sqn_admin`, `wing_admin`, `national_admin`, and `system_admin` reach this point. The guard blocks only `sqn_admin` — the other three are permitted to change unit_type. The check is: payload contains `unit_type` **and** it differs from the current value **and** caller is `sqn_admin`. Sending the same `unit_type` value (no actual change) is allowed and does not trigger the 403 — the frontend's disabled select ensures this is the normal case.

**No changes to `SquadronUpdateIn` schema** — `unit_type` remains optional in the schema. The restriction is enforced in the handler, not the Pydantic model.

---

## Frontend (`connected-frontend/index.html`)

### 1. Disable the select for sqn_admin

In `renderSettings()` (near line 4943), after `setVal('s-unit-type', S.cfg.unitType || 'standard_squadron')`, add:

```javascript
const utSel = document.getElementById('s-unit-type');
const utNote = document.getElementById('s-unit-type-note');
if (S.role === 'sqn_admin') {
  utSel.disabled = true;
  if (utNote) utNote.textContent = 'Set by wing or national admin';
} else {
  utSel.disabled = false;
  if (utNote) utNote.textContent = '';
}
```

### 2. Add the note element to the HTML

In the HTML near the `s-unit-type` select (around line 1536), add a note span after the closing `</select>`:

```html
<span id="s-unit-type-note" class="muted" style="font-size:11px;margin-left:6px"></span>
```

### 3. No change to `saveSettings()`

`saveSettings()` reads the current value of `s-unit-type` (which is correct and unchanged when disabled) and includes it in the PATCH payload. The backend guard allows unchanged values — no change required to `saveSettings()`. If somehow a sqn_admin's payload does contain a changed value (e.g., via devtools), the 403 from the backend is caught by `apiErr()` and shown as a toast.

---

## Tests

**File:** `backend/tests/test_organisations.py` (or wherever squadron PATCH tests live — check first)

### Required test cases

- `test_sqn_admin_cannot_change_unit_type`
  - Login as sqn_admin (`ADMIN703`)
  - PATCH `/api/squadrons/{sqn_id}` with `{"unit_type": "<different_value>"}`
  - Assert 403 with `error == "unit_type_locked"`

- `test_sqn_admin_can_set_same_unit_type`
  - Login as sqn_admin
  - PATCH with `{"unit_type": "<current_value>"}` (no actual change)
  - Assert 200 (no-op update is allowed)

- `test_sqn_admin_can_edit_other_settings`
  - Login as sqn_admin
  - PATCH with `{"address": "123 New St"}` (no `unit_type` key)
  - Assert 200 and address updated

- `test_wing_admin_can_change_unit_type`
  - Login as wing_admin (`ADMIN7WG`) in proxy/delegated mode for 703 SQN
  - PATCH with `{"unit_type": "specialist_squadron"}`
  - Assert 200 and `unit_type` updated
  - Restore original value after test

---

## Global Constraints

- No migration required — `unit_type` column already exists
- The 403 message must not reveal internal role names: use "wing or national admin" not "wing_admin or national_admin"
- `sqn_general` is already blocked from PATCH by `require_can_write_squadron` — no additional check needed
- Disabled HTML `<select>` still submits its current value in the form — `saveSettings()` remains unchanged
- Do not add the note span inside the `<select>` element — place it after the closing `</select>` tag
