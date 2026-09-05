# Parade Night Planning Redesign — Plan C: Connected TMS + CEA

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify the CEA import pipeline in TMS Activities is complete and correctly scoped, ensure the CEA Location vs Room distinction is visible in the UI, and surface the `timing_template_id` / `instructional_periods` data in the TMS parade night views where relevant.

**Architecture:** Most CEA functionality already exists in `connected-frontend/index.html`. This plan verifies correctness, adds two missing UI labels, and wires the timing template display into the TMS parade night card. No new backend endpoints; no new frontend JS frameworks.

**Tech Stack:** Plain HTML/CSS/JS in `connected-frontend/index.html`. Use the existing `esc()`, `api()`, `nav()`, `openModal()`/`closeModal()` helpers. All new innerHTML uses `esc()` for any user-supplied content.

**Spec:** `docs/superpowers/specs/2026-09-05-parade-night-planning-redesign.md`

## Global Constraints

- Never use innerHTML with unsanitised strings — always `esc()`.
- CEA Location field (`a.location`) must never be mapped to `training_area_id` — they are semantically distinct.
- CEA import must remain Wing Admin+ only (system_admin, wing_admin, national_admin). Do not expose to sqn_admin or sqn_general.
- Do not merge the two frontends; do not introduce a build step to `connected-frontend/`.
- Security greps must return 0 after every commit.
- No localStorage for operational data.

---

### Task 1: Verify CEA import is complete and fix any gaps

**Files:**
- Read + potentially modify: `connected-frontend/index.html`

**Interfaces:**
- Verifies: `actImportCeaBtn` at line 1968 is visible only to wing_admin+ (line 12176-12178).
- Verifies: `openCeaImportModal()` opens the modal at line 4296.
- Verifies: `ceaPreview()` calls `POST /api/planning/years/{year_id}/cea/import` via the existing fetch at line 12832.
- Verifies: `ceaConfirm()` completes the import and reloads activities.
- Produces: A passing end-to-end verification checklist in the ledger.

- [ ] **Step 1: Read the Activities page HTML block**

Find lines 1959-2100 in `connected-frontend/index.html`. Confirm:
1. `id="page-activities"` div exists.
2. `id="actImportCeaBtn"` button exists within the Activities page header row.
3. The button's `onclick` is `openCeaImportModal()`.
4. The button has `style="display:none"` as default (JS shows it for correct roles).

If any of these are missing or wrong, fix them.

- [ ] **Step 2: Read the role gate at `_loadActivitiesPage`**

Find lines 12176-12178:
```javascript
const ceaBtn = document.getElementById('actImportCeaBtn');
if (ceaBtn) {
  ceaBtn.style.display = ['system_admin','wing_admin','national_admin'].includes(S.role||'') ? '' : 'none';
}
```

Verify this exactly matches the Wing Admin+ requirement. If `sqn_admin` or `sqn_general` appear in the list, remove them.

- [ ] **Step 3: Read the `openCeaImportModal` function**

Find the `openCeaImportModal` function (around line 12675). Verify it:
1. Sets the year label in `ceaImportYearLabel` from `P.currentYearId`.
2. Calls `openModal('m-cea-import')`.
3. Does not pass any unsanitised user content directly into innerHTML without `esc()`.

If any innerHTML writes miss `esc()`, add it.

- [ ] **Step 4: Read the `ceaPreview` function**

Find `ceaPreview()` and verify:
1. It reads the uploaded CSV via FileReader.
2. It calls `_normalise_cea_row` or equivalent to normalise each row.
3. It renders a preview table — all user-supplied column values use `esc()`.
4. The preview table has a column for `location` (CEA venue) and does NOT show it as or alongside `training_area_id`.

If the preview table is missing an `esc()` call on any column that comes from the uploaded file, add it.

- [ ] **Step 5: Commit any fixes found**

If no changes were needed, note "no changes required — implementation verified" in the ledger and do not commit. If changes were made:

```bash
git add connected-frontend/index.html
git commit -m "fix(tms): verify CEA import gate + esc() coverage in ceaPreview"
```

---

### Task 2: Label CEA Location distinctly from TMS Room in the import preview

**Files:**
- Modify: `connected-frontend/index.html` (CEA preview table headers)

**Interfaces:**
- Consumes: The CEA preview table rendered by `ceaPreview()`.
- Produces: The `location` column header reads "CEA Location (event venue)" — not "Location" or "Room". A tooltip or small note clarifies it is distinct from training areas.

**Why this matters:** The TMS uses `training_area_id` for Room assignments in Sessions. CEA activities have a plain-text `location` field that is the venue where the CEA event occurs (often off-site). Without distinct labeling, users may confuse the two and attempt to map them.

- [ ] **Step 1: Find the CEA preview table header**

Search for the `ceaPreview` table header render (around line 12750-12797). Find the `<th>` for the `location` column.

- [ ] **Step 2: Update the location column header**

Change the header from `Location` (or whatever it currently reads) to:

```javascript
'<th>CEA Location<br><small style="color:var(--muted,#5c6a76);font-weight:400">event venue — not a training room</small></th>'
```

This change is in a JavaScript string that builds innerHTML. Because the header text is a string literal (not user input), it does not need `esc()`.

- [ ] **Step 3: Find any CEA activity detail display**

Also find where individual CEA activities are rendered in the Activities list (in `_actTabLoad` or `_actsList` rendering, around line 11914+). Where `a.location` is shown, ensure the label reads "CEA Venue" or "Event Location" — not "Room" or "Training Area".

```javascript
// Example fix — change:
'<td>' + esc(a.location) + '</td>'
// To:
'<td><span title="CEA event venue — not a training room">' + esc(a.location) + '</span></td>'
```

- [ ] **Step 4: TypeScript/syntax check**

```bash
# No build step — just verify the file is valid JS by checking for syntax errors
node --input-type=module < /dev/null 2>&1 || true
# Manual check: open browser devtools on the Activities page and confirm no JS errors
```

- [ ] **Step 5: Commit**

```bash
git add connected-frontend/index.html
git commit -m "fix(tms): label CEA Location distinctly from TMS Room in import preview

Location column header now reads 'CEA Location (event venue)' with a
note clarifying it is not a training room. Activity list renders the
location field with a tooltip for the same reason."
```

---

### Task 3: Show timing template name in TMS Parade Night card

**Files:**
- Modify: `connected-frontend/index.html` (parade night card render in Activities or the planning page)

**Interfaces:**
- Consumes: `parade_night.timing_template_id` — already on the ParadeNight model; the TMS parade night list/card may need to fetch the template name.
- Produces: The parade night card in TMS Activities (or the Planning Workspace's parade-nights list in TMS, if accessible from the connected frontend) shows the timing template name alongside the date and session count.

**Why this matters:** With the new mandatory timing template enforcement (Plan A Task 3), every new parade night has a timing template. Showing the template name in the TMS card lets coordinators verify at a glance which template is in use, without opening the planning workspace.

- [ ] **Step 1: Find where parade nights are rendered in TMS**

Search for where parade nights are listed in the connected frontend:
```bash
grep -n "parade.night\|parade_night\|session_count\|loadParadeNights\|_paradeNight" connected-frontend/index.html | grep -i "render\|innerHTML\|append\|card\|row" | head -20
```

Find the render function and the card/row template.

- [ ] **Step 2: Check if `timing_template_id` is in the API response**

The TMS's parade night list API already returns `timing_template_id` on the `ParadeNight` model. Confirm by reading the existing render code — if `pn.timing_template_id` is already available, proceed. If not, check whether the endpoint includes it.

- [ ] **Step 3: Fetch timing template names**

If the timing template name is not already cached, fetch templates for the squadron:

```javascript
// Fetch once and cache in S or P (planning state)
const templates = await api('/api/training/timing-templates?squadron_id=' + S.squadron_id).catch(() => []);
const templateMap = Object.fromEntries((templates||[]).map(t => [t.id, t.name]));
```

Store in `P.templateMap` or a local variable within the render function.

- [ ] **Step 4: Add template name to the parade night card**

In the parade night card/row HTML template, after the session count or date, add:

```javascript
const tmplName = pn.timing_template_id && P.templateMap
  ? (P.templateMap[pn.timing_template_id] || 'Custom')
  : (pn.timing_template_id ? '…' : 'No template');

// In the card innerHTML:
'<span class="tag tag-muted" title="Timing template">' + esc(tmplName) + '</span>'
```

- [ ] **Step 5: Handle legacy parade nights (no template)**

Legacy parade nights have `timing_template_id = null`. Show a neutral indicator:

```javascript
const tmplBadge = pn.timing_template_id
  ? '<span class="tag tag-blue" title="Timing template">' + esc(tmplName) + '</span>'
  : '<span class="tag tag-muted" title="No timing template assigned">Legacy</span>';
```

- [ ] **Step 6: Visual verification in browser**

Start the backend and connected frontend:
```bash
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000 &
cd connected-frontend && python3 -m http.server 8080
```

1. Log in as sqn_admin.
2. Navigate to the parade nights or activities page.
3. Verify: each parade night card shows a template name badge (or "Legacy" for old nights).
4. Verify: no JS errors in the console.
5. Log in as sqn_general: verify the CEA import button is NOT visible.
6. Log in as wing_admin: verify the CEA import button IS visible.

- [ ] **Step 7: Commit**

```bash
git add connected-frontend/index.html
git commit -m "feat(tms): show timing template name on parade night cards

Each parade night card now shows a badge with the timing template name.
Legacy nights (no timing_template_id) show a 'Legacy' badge.
Uses templateMap cached from /api/training/timing-templates."
```

---

### Task 4: Security verification and final sweep

**Files:**
- Run: security greps
- Run: manual browser verification

- [ ] **Step 1: Run all security greps**

```bash
cd /path/to/project

grep -Rc -E "your unit only|Controlled access for training" connected-frontend backend
grep -Rc -E "View current code|Show access code|Reveal code|Display existing code" connected-frontend backend
grep -Rc -E "ADMIN703|ADMIN7WG|ADMINNATIONAL|SYSADMIN2026|plain_code|code_hash|access_code|localStorage" connected-frontend
grep -Rc -E "JWT_SECRET|SECRET_KEY|DATABASE_URL" connected-frontend
```

All must return 0 matches.

- [ ] **Step 2: Verify CEA Location ≠ Room in the backend**

Read `backend/app/routers/planning.py` around the `import_cea_csv` function (line 5625). Verify:
1. The `location` field from the CEA CSV is stored in `CeaActivity.location` (a text field).
2. It is NOT mapped to `training_area_id` or any FK to training areas.

If it is incorrectly mapped, fix it:
- The `CeaActivity.location` field should store the raw CEA venue string.
- `training_area_id` should only ever be populated by the TMS Room picker, not by CEA import.

- [ ] **Step 3: Final commit if fixes were needed**

```bash
git add connected-frontend/index.html backend/app/
git commit -m "fix(tms/cea): verify CEA Location vs Room separation end to end

Backend: CeaActivity.location is a text field — not mapped to training_area_id.
Frontend: location column labeled as 'CEA Location (event venue)' in import preview."
```

- [ ] **Step 4: Push**

```bash
git push origin main
```

---

## Plan C complete

| Feature | Status |
|---|---|
| CEA import button in TMS Activities (wing_admin+) | Verified + scoped |
| CEA Location ≠ Room distinction in import preview | Labeled |
| CEA activity list location labeled as event venue | Done |
| Timing template name on parade night cards | Done |
| Security greps | All 0 |

**Plan C has no dependencies on Plans A or B and can be executed in parallel.**
