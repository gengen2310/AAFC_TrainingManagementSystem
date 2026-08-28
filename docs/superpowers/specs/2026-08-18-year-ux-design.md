> ## ⚠️ SUPERSEDED IN PART — 2026-08-28
>
> See `docs/superpowers/specs/2026-08-28-training-year-context-model.md`.
>
> Any create-year, manage-years, rename-year, archive or restore user experience
> described below no longer stands. A Training Year is calendar context: the user
> selects a year, and the canonical row is materialised on first write.
>
> Kept unedited below as decision history.

# Year UX — Design Spec
**Sub-project 1 of POST-GAP TRAINING CELL PRODUCT REVIEW**
Date: 2026-08-18 | Status: Approved for implementation

> **LOCKED — 2026-08-18 | Implemented at commit `5ab3b19` on branch `main`.**
> This spec is the authoritative record of approved design decisions for Sub-project 1.
> Do not modify the requirements, API contracts, or UI behaviour described below without
> explicit written authorisation from the project owner. Clarifications and errata must be
> appended in a clearly dated addendum section, never edited inline.

---

## Problem

The TMS currently labels the planning year as "Planning Year" or "Training Year" throughout the UI, supplemented by a full string like "2026–2027 Training Year". This is wordy, inconsistent, and clutters the interface. More critically, there is no year selector on the Activities page — the page silently uses the globally active year with no visible indicator and no way to navigate to a different year without going elsewhere. As the system accumulates years over time, users need a scalable, direct way to move between them. CEA activity import also belongs in this year-contextual view since it is always year-scoped.

---

## Design decisions (from Grill Me)

| Question | Decision |
|---|---|
| How should year be labelled? | The integer year only — `2026`. No "Planning Year", "Training Year", or date-range suffixes. |
| How many years will exist? | Indefinite — no cap. The control must scale without a fixed list. |
| Who can create/manage years? | system_admin, wing_admin, national_admin — all three management roles. The ⚙ gear is role-gated to these three. |
| Can multiple years be active simultaneously? | Yes. `active_status` on `PlanningYear` means "in current planning cycle", not "the one selected year". Wing may plan 2027 while 2026 is still running. |
| What happens when user types a non-existent year? | Error toast — "No year YYYY — create one in Manage years ⚙". Never silently create. |
| Does year selection affect Planning Workspace? | Yes — the nav-pw-link badge shows current year and passes it in the URL fragment. |

---

## Section 1 — Label changes

Replace every instance of "Planning Year", "Training Year", and "YYYY–YYYY Training Year" in `connected-frontend/index.html` with the bare year integer wherever a year value is displayed.

Specific replacements:
- Page headings and section titles: `Planning Year 2026–2027` → `2026`
- Dropdown option text: `2026–2027 Training Year` → `2026`
- Toast / confirmation messages: `Training Year` → `year` (lowercase, no capitalisation)
- `<select>` option text for any year selector already in the page: render as the integer year only
- `tc-year-sel` dropdown (Training Classes sub-section): options change from long strings to `2026`, `2025`, etc.

`PlanningYear.name` (string field on the model) becomes internal/optional — it is no longer displayed in the frontend. The display value is always `PlanningYear.year` (the integer).

---

## Section 2 — Year navigation control on the Activities page

### Visual design

A single connected navy pill (`--dark: #002f65`) in the Activities page header, right-aligned, separated from action buttons:

```
[ ‹ ]  [ 2026 ]  [ › ]  [ ⚙ ]
```

- **‹ / ›** — arrow buttons, step through existing years in chronological order
- **2026** — year display, click to enter direct-input mode
- **⚙** — gear icon, opens the Manage years panel (admin roles only; hidden for sqn_general, sqn_admin, auditor)

### Interaction

**Arrow navigation:**
- ‹ and › step through the ordered list of existing `PlanningYear` records only.
- ‹ is `disabled` (and visually faded) when the user is on the earliest year.
- › is `disabled` when the user is on the latest year.
- Clicking a non-disabled arrow sets `P.currentYearId` to the adjacent year's id and re-triggers the Activities data load.

**Direct input:**
- Clicking the year number converts it to an inline `<input type="text" maxlength="4">` with an underline cursor in `--blue`.
- Arrows and gear dim (pointer-events: none) while editing.
- `Enter`: validate the typed value. If a `PlanningYear` with that `year` integer exists → navigate there. If not → show error toast (see below) and restore previous value.
- `Escape` or blur (with a 120ms delay to allow gear/arrow clicks to register) → cancel and restore.

**Error toast:**
- Appears directly below the control, error-background with error-red text.
- Message: `No year {YYYY} — create one in Manage years ⚙`
- Auto-dismisses after 3.2 seconds. Does not block interaction.

### Data

Year list is fetched once on page load from `GET /api/planning/years` (existing endpoint). Response includes `id`, `year` (int), `active_status`. Sorted ascending by `year`. Cached in a module-level `P.years` array — no repeated fetches on arrow clicks.

On year change, all mutations go through a single `setCurrentYear(yearObj)` setter:
1. Set `P.currentYearId = yearObj.id` and `P.currentYearInt = yearObj.year`
2. Call `_actTabLoad(activeTab, scope, ...)` with the updated year — same function already called on initial Activities page load.
3. Update year nav display label (inner text of the year number span).
4. Update nav-pw-link badge and hint line (see Section 3).
5. Update ‹ / › disabled states based on position in `P.years` array.

All three UI surfaces (nav control, page header label, PW badge) are updated from this one function. No scattered DOM updates.

### Initial state

On Activities page load:
- If `P.currentYearId` is already set (user navigated from another page mid-session) → display that year.
- If not set → use the most recent `PlanningYear` where `active_status = true`. If multiple years are active, pick the one with the highest `year` integer.

---

## Section 3 — Planning Workspace year sync

### Nav badge

The `nav-pw-link` element in the sidebar gets a year badge:

```html
<a class="nav-pw-link" ...>
  Planning Workspace ↗
  <span class="nav-pw-year" id="navPwYear">2026</span>
</a>
<div class="nav-pw-hint">Opens with 2026 context</div>
```

- The badge displays `P.currentYearInt`.
- Updates reactively whenever `P.currentYearId` changes (via the `setCurrentYear` setter in Section 2).
- The hint line also updates: `Opens with {YYYY} context`.

### URL fragment extension

Current click handler builds: `#t={token}`
Extended handler builds: `#t={token}&y={year integer}` — e.g. `#t=abc123&y=2026`

The year integer (not the UUID) is passed because Planning Workspace has its own independent year records and does not share the TMS UUID namespace.

Planning Workspace startup reads `location.hash`, already extracts `t`. Add extraction for `y`:
- If `y` is present and matches a `PlanningYear.year` integer in PW's own year list → pre-select it on load.
- If `y` is absent or unrecognised → fall back to the most recent active year (existing behaviour, no regression).

This is a one-way push: TMS tells PW what year to open with. PW does not push year changes back to TMS (the two apps are separate deployments).

---

## Section 4 — Year management panel (progressive disclosure)

### Access

⚙ gear icon on the year nav control. Visible only when `S.role` is one of: `system_admin`, `wing_admin`, `national_admin`. Hidden (not disabled) for `sqn_general`, `sqn_admin`, `auditor`.

### Panel design

Modal overlay, width 580px. Header: navy (`--dark`), title "Manage Training Years", × close button.

**Body:**
1. `+ Create {next year}` button (green) — the label pre-fills with `current latest year + 1`. POST to `POST /api/planning/years`.
2. Table of all years, newest first:

| Year | Status | Actions |
|---|---|---|
| 2027 | Active (green chip) | Export · Rename · Archive |
| 2026 | Active (green chip) | Export · Rename · Archive |
| 2025 | Archived (grey chip) | Export · Rename · Restore · Delete |

**Actions:**

- **Export** — downloads a CSV of the year's full training program. See Export spec below.
- **Rename** — edits `PlanningYear.name` (internal label only, not displayed in frontend) via PATCH.
- **Archive** — sets `active_status = false`. Simple toggle — no constraint on how many active years remain. An archived year is still navigable via ‹ ›.
- **Restore** — sets `active_status = true`. Simple toggle — no deactivation of other years. Multiple years may be active simultaneously (e.g., planning 2027 while 2026 is in progress).
- **Delete** — dependency-gated via existing `fk_dependents` pattern (`app/services.py`). If the year has attached `ParadeDate`, `Activity`, or `Session` records, refuse with an explanation. Red colour, rightmost position. Requires confirmation.

### Export spec

Export generates a CSV download of the year's complete training program.

**Endpoint:** `GET /api/planning/years/{id}/export` (new)
**Response headers:** `Content-Disposition: attachment; filename="AAFC_TMS_{year}_{scope}_{YYYY-MM-DD}.csv"`
**Permissions:** same as `GET /api/planning/years/{id}` — scoped to the caller's squadron/wing.

**CSV structure** — three sections in one file, separated by a blank row and a section header:

```
TRAINING PROGRAM — 704 SQUADRON — 2026
Exported: 2026-08-18

ACTIVITIES
cea_seq_nr,name,type,owning_level,importance,description
CEA-001,First Aid,Required,...
...

PARADE SCHEDULE
date,theme,notes
2026-09-12,Leadership,...
...

SESSIONS
date,period,activity_name,facilitator,training_classes
2026-09-12,1,First Aid,Capt Smith,"301 Class; 302 Class"
...
```

**Backend implementation:** Python `csv` module (stdlib, no new dependency). Query joins `PlanningYear → ParadeDate → Session → Activity → Facilitator → SessionAudience → TrainingClass` for the sessions section. Activities section queries all `Activity` records for the year scoped to the caller.

### Closing

- × button, Escape key, or clicking the overlay backdrop.
- After any create/archive/restore/delete: refresh the year list in both the panel and `P.years`, update the nav control.

---

## Section 5 — CEA Activity Import

CEA import is year-scoped and belongs in the Activities page view. The import button lives in the Activities page header alongside the existing action buttons, visible to wing_admin and above.

### Entry point

```
[Refresh] [+ Add Activity] [Generate Activities] [+ Add Holiday] [Import CEA ↑]    [‹ 2026 › ⚙]
```

"Import CEA ↑" button (secondary style, wing_admin / national_admin / system_admin only). Clicking opens the Import modal.

### Import modal

**Step 1 — File selection**

Modal header: "Import CEA Activities — 2026"

Body:
- File input: "Upload CEA export file" — accepts `.csv` and `.xls`/`.xlsx`
- Or: paste CEA activity IDs manually (one per line) in a textarea
- "Preview import" button (disabled until file/text is provided)

**Step 2 — Preview with conflict detection**

After the file is parsed (client-side for CSV, or submitted to a preview endpoint), the modal shows three categorised lists:

| Category | Colour | Meaning |
|---|---|---|
| New activities | Green row | CEA ID not yet in TMS for this year |
| Updates | Blue row | CEA ID exists in TMS; some fields differ — new data will overwrite |
| Conflicts | Amber row | CEA ID was previously imported at squadron level; wing import will replace it |

For conflicts, each row shows:
- Activity name (CEA version vs existing TMS version)
- Who imported the existing version and when
- Per-row toggle: "Replace" (default) / "Keep existing"

**Resolution options (bottom of preview):**
- "Import all (N activities)" — proceeds with defaults (Replace for all conflicts)
- "Review conflicts individually" — expands conflict rows for per-item decision
- "Cancel"

**Step 3 — Confirmation and result**

On confirm: POST to `POST /api/planning/years/{id}/cea/import` (existing endpoint, wing_admin+).

Request body includes the parsed activity list plus per-conflict resolution decisions (`override: true/false` per conflicting CEA ID).

Response: summary of what was created / updated / skipped.

Post-import toast: "Import complete — 42 added, 3 updated, 1 kept existing."

Activities page auto-refreshes after modal closes.

### Deduplication and override rules (from Grill Me Q8)

- **Wing imports same CEA ID as squadron**: wing version replaces squadron version for all users at that squadron. The warning in Step 2 surfaces this before it happens.
- **Same CEA ID already exists at wing level**: treated as an update — new CEA data overwrites existing TMS data (name, type, description, etc.). Notes that were added at the TMS level are preserved.
- **CEA ID collision across two squadrons**: each squadron's import is independent; no cross-squadron conflict.
- **Squadron imports CEA ID that already exists at wing level**: shows a warning — "This activity is already imported at Wing level (Wing: CEA-042, First Aid). Import it as a squadron-specific copy, or skip it?" Skipping is the recommended default.

### Unit filter (display, post-import)

When wing imports activities, some belong to other units (cadets from 701 Sqn parading with 704 Sqn for a specific event). After import, each squadron can:
- Filter the activity list by unit (a unit filter dropdown appears on the Activities page when wing-level activities are present)
- Hide individual wing-level activities from their own view (affects Activities page and Calendar)

The unit filter and per-activity hide are display preferences scoped to the squadron; they do not delete or modify the underlying activity record. Spec for unit filter UI is in Sub-project 2.

### Backend import endpoint

`POST /api/planning/years/{id}/cea/import` — already exists (`planning.py` line ~4913).

Required change: accept per-conflict `override` flags in the request body so the frontend's per-item resolution choices are respected. Currently the endpoint may overwrite unconditionally — confirm behaviour and add override support if missing.

---

## API contracts

| Method | Path | Status |
|---|---|---|
| GET | `/api/planning/years` | Exists |
| POST | `/api/planning/years` | Exists |
| PATCH | `/api/planning/years/{id}` | Exists or trivial addition |
| PATCH | `/api/planning/years/{id}/archive` | Exists |
| PATCH | `/api/planning/years/{id}/restore` | Exists |
| DELETE | `/api/planning/years/{id}` | Exists (`fk_dependents` gated) |
| GET | `/api/planning/years/{id}/export` | **New** — CSV download |
| POST | `/api/planning/years/{id}/cea/import` | Exists — confirm override flag support |

---

## Permissions

| Role | Navigate ‹› | Direct input | See ⚙ | Create/Archive/Delete | Import CEA |
|---|---|---|---|---|---|
| system_admin | ✓ | ✓ | ✓ | ✓ | ✓ |
| national_admin | ✓ | ✓ | ✓ | ✓ | ✓ |
| wing_admin | ✓ | ✓ | ✓ | ✓ | ✓ |
| sqn_admin | ✓ | ✓ | ✗ | ✗ | ✗ |
| sqn_general | ✓ | ✓ | ✗ | ✗ | ✗ |
| auditor | ✓ | ✓ | ✗ | ✗ | ✗ |

Navigation (‹›) and direct input are available to all authenticated roles — viewing a past year's activities is a read operation, not a management action.

---

## Error handling

| Scenario | Handling |
|---|---|
| Typed year doesn't exist | Toast: "No year {YYYY} — create one in Manage years ⚙". Restore previous year. |
| Typed value not a valid 4-digit year | Toast: "Enter a valid year (e.g. 2026)". Restore. |
| Delete year with dependencies | API returns 400. Panel shows: "Cannot delete 2024 — it has 42 parade nights and 108 activities." |
| GET /api/planning/years fails on load | Show static "—" in year nav; log to console. Do not crash the page. |
| CEA import file parse error | Inline error in modal: "Could not read file — check it is a valid CSV or Excel file." |
| CEA import API error | Toast on modal: "Import failed — {error message}". Modal stays open. |
| Export API error | Toast: "Export failed. Try again or contact support." |

---

## Testing

- All existing backend tests for planning year CRUD must continue to pass.
- New backend tests:
  - `GET /api/planning/years/{id}/export` returns valid CSV with correct sections and scope
  - Export is scoped — squadron cannot export another squadron's year
  - Multiple years can have `active_status = true` simultaneously (no constraint violated)
  - `POST /api/planning/years/{id}/cea/import` with `override: false` on a conflict keeps existing record
- New frontend interaction tests (Playwright):
  - ‹ navigation from 2026 → 2025, verify Activities reload with new year's data
  - › navigation from 2025 → 2026, verify Activities reload
  - ‹ disabled on earliest year (verify `disabled` attribute)
  - Direct input to existing year → navigates
  - Direct input to non-existent year → toast appears, year unchanged
  - Direct input Escape → cancels, year unchanged
  - ⚙ hidden for sqn_general role
  - ⚙ visible for national_admin role
  - Manage panel: create year → appears in nav list
  - Manage panel: archive year → chip changes to Archived
  - Manage panel: two years simultaneously active → both show green chip
  - Manage panel: delete with dependencies → blocked with message
  - Manage panel: export → file download triggered
  - nav-pw-link badge matches current year after arrow navigation
  - Import CEA button hidden for sqn_general
  - Import CEA: upload valid file → preview shows categorised rows
  - Import CEA: conflict with "Keep existing" → original record preserved after import
  - Import CEA: successful import → activities page refreshes, toast confirms count

---

## Out of scope for this sub-project

- Backend model changes to `PlanningYear` — no schema migration required.
- `PlanningYear.name` removal from the database — field stays, just stops being displayed.
- Planning Workspace internal year selector redesign — PW only receives the year via URL fragment; its internal selector is unchanged.
- Unit filter UI and per-activity hide control — display preferences post-import, specified in Sub-project 2.
- Layered importance model, notes at level, `ActivityLocalDecision` — Sub-project 2.
- Combined Training, Help & Reference — Sub-projects 3 and 4.
