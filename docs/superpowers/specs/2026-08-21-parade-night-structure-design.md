# Parade Night Structure Redesign — Design Spec

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current session/IP/timing-template language with a unified "Training Period" model; redesign the print program to show the full parade night structure with dynamic training-class columns; add custom training phases with scope-based inheritance; surface year management in Settings; and align Planning Workspace terminology and template-switching with TMS.

**Architecture:** Single-file SPA frontend (`connected-frontend/index.html`) + FastAPI backend + SQLAlchemy/Alembic + separate React Planning Workspace (`frontend/`). All changes share the same backend. Frontend changes touch both apps. Login layout bug fixed in the same pass (bounded: `flex-direction:column` on `#auth-screen`).

**Tech Stack:** Python 3.13 / FastAPI / SQLAlchemy 2.0 / Alembic / SQLite (dev) / PostgreSQL (prod) · Plain HTML/CSS/JS SPA · React + Vite (Planning Workspace)

**Spec authored:** 2026-08-21

---

## Global Constraints

- `connected-frontend/index.html` is a single-file SPA — no build step. All CSS/JS inlined.
- Never replace it with the React app; never merge the two frontends.
- All XSS-risk strings use `esc()` before `innerHTML` insertion.
- Every new backend endpoint follows `permissions.py` RBAC helpers — no ad-hoc role checks.
- New migrations use `batch_alter_table` for SQLite compatibility; `alembic heads` checked before each.
- No plaintext credentials, access codes, or hashes in source, logs, or API responses.
- Do not deploy production without separate explicit authorisation.
- Training class and custom phase deletions must be dependency-gated (check sessions, then block or cascade per entity rules below).

---

## 1. Terminology / Language Unification

Retire all occurrences of "Session", "Instructional Period", and "IP" in user-visible text. Adopt a single vocabulary everywhere (TMS + PW):

| Old term | New term |
|---|---|
| Instructional Period / IP | Training Period |
| Session (when referring to a scheduled slot) | Training Period |
| Default Sessions Per Night (fallback) | Default Training Periods (fallback) |
| Sessions This Night | Training Periods This Night |
| IP (block type in timing template) | Training Period |

Code-level names (function names, API field names, DB columns) are **not** renamed in this spec to avoid unnecessary migration churn — only user-visible labels change.

---

## 2. Block Type Taxonomy

Replace the current timing template block type set with:

| Stored value | Display label | Generates schedulable Training Period? |
|---|---|---|
| `arrival` | Arrival | No |
| `admin` | Admin | No |
| `parade` | Parade | No |
| `briefing` | Briefing | No |
| `training_period` | Training Period *(custom name — see §3)* | **Yes** |
| `drinks_break` | Drinks Break | No |
| `fatigue` | Fatigue | No |
| `dismissal` | Dismissal | No |
| `other` | *(admin-entered free text)* | No |

Existing DB rows with type `ip` are migrated to `training_period`. Existing `admin`, `parade`, `break` rows map to `admin`, `parade`, `drinks_break` respectively. Any unrecognised legacy type maps to `other`.

Only `training_period` blocks appear in TMS session scheduling, the PW lesson-allocation view, and the "Training Periods This Night" section of a parade night. All blocks appear in the print program.

---

## 3. Timing Template Enhancements

### 3a. Custom name for Training Period blocks

When creating or editing a timing template block with type `training_period`, a **Name** text field is required (not optional). Examples: "Flight Period", "Section Period", "Training Period". This name is cosmetic — it affects display and print only, not scheduling logic.

For all other block types, the name field is pre-filled with the type display label and is editable (admins can rename "Drinks Break" to "Canteen Break" if they wish).

### 3b. Updated type dropdown

The block-editor row (in the timing template modal, `#tt-blocks-body`) shows the updated type list. When `other` is selected, the Name field is cleared and becomes required. When `training_period` is selected, the Name field defaults to "Training Period" and remains required.

### 3c. Quick-setup auto-populate

The "Auto-populate" button (`ttQuickSetup()`) generates a standard block sequence for N Training Periods:

`Arrival → Admin → Parade → Briefing → [Training Period × N with Drinks Break between periods 1 and 2 if N > 1] → Fatigue → Parade → Dismissal`

Start times default to blank (admin fills them in). This replaces the current bare IP-count populate.

### 3d. Who can manage timing templates

Squadron, wing, national, and system admins can create, edit, and delete timing templates. Templates are scoped to the unit creating them (a wing template is visible to the wing only; squadron templates to that squadron only). This matches the existing `admin-el` guard.

---

## 4. Training Class Enhancements

### 4a. Stage field (new)

`TrainingClass` gains a required `stage_code` field. Allowed values:

| Code | Stage name | Print column group |
|---|---|---|
| `ORI` | Orientation | Orientation / Initial |
| `INI` | Initial | Orientation / Initial |
| `JNR` | Junior | Junior / Bronze |
| `INT` | Intermediate | Intermediate / Silver |
| `SNR` | Senior | Senior / Gold |

The four print column groups (ORI/INI combined, JNR, INT, SNR) are always rendered in the print output regardless of whether a squadron has classes for that group.

### 4b. Date range fields (new)

`TrainingClass` gains:
- `applies_from` (Date, required) — first parade night date this class is active
- `applies_to` (Date, nullable) — last active date; null means open-ended

A class whose date range does not cover a specific parade night shows `—` in its sub-column for that night.

### 4c. Auto-creation on year setup

When a planning year is created (`POST /api/planning/years`), the backend auto-creates five training classes for that year with defaults:

| stage_code | Default name | applies_from | applies_to |
|---|---|---|---|
| ORI | Orientation | Year start date | null |
| INI | Initial | Year start date | null |
| JNR | Junior | Year start date | null |
| INT | Intermediate | Year start date | null |
| SNR | Senior | Year start date | null |

"Year start date" = first parade night of the planning year, or 1 January of the year number if no parade nights exist yet.

### 4d. CRUD permissions

Squadron, wing, national, and system admins can create, edit, archive, and delete training classes within their scope. Deletion is dependency-gated: if any session references the class, deletion is blocked and a message explains that the class must be unassigned from all sessions before deletion. Archive (set `applies_to` to today) is always available.

### 4e. Stage selector in Settings UI

The Training Classes card in Unit Settings (`settings-training-classes-wrap`) adds a **Stage** selector when creating or editing a class. Order in the UI matches the print column order: ORI → INI → JNR → INT → SNR. The year selector already present is retained.

---

## 5. Custom Training Phases

A new model (`CustomTrainingPhase`) for ad-hoc training groups beyond the five standard stages.

### 5a. Data model

| Field | Type | Notes |
|---|---|---|
| `custom_phase_id` | UUID PK | |
| `name` | string | e.g. "Wing Band", "Biathlon Team" |
| `scope_type` | enum | squadron / wing / national / system |
| `scope_id` | UUID nullable | squadron_id or wing_id; null for national/system |
| `applies_from` | Date | required |
| `applies_to` | Date nullable | open-ended if null |
| `created_by` | UUID FK → User | |
| `created_at` | timestamp | |

### 5b. Scope inheritance (downward)

A phase is visible and usable at its own scope and all scopes below it:
- `system` → all scopes
- `national` → all wings and squadrons
- `wing` (scope_id = wing_id) → all squadrons in that wing
- `squadron` (scope_id = squadron_id) → that squadron only

When assigning a custom phase to a Training Period session, the UI shows all phases whose scope covers the current unit.

### 5c. Print behaviour

A custom phase appears as an **additional column** in the print program, after the four standard column groups, **only when** at least one session on that parade night is assigned to it. Columns for phases with no sessions that night are omitted. Multiple custom phases sort alphabetically.

### 5d. CRUD permissions

Each scope's admin can create, edit, and delete custom phases within their scope. Deletion is dependency-gated (same rule as training classes: block if sessions reference it).

### 5e. UI location

Custom training phases are managed in a new card in Unit Settings, visible to admins of the appropriate scope. The card lists phases applicable to the current scope, with create/edit/delete actions. Wing and national admins see phases from their own scope and can create new ones; they cannot edit squadron-created phases.

---

## 6. Print Program Redesign

### 6a. Data requirements

`renderWP()` currently renders only `pn.sessions` (IP/Training Period slots). The print redesign requires two data sources per parade night:

1. **All timing template blocks** for the night (the full ordered list from the applied template, not just the schedulable ones) — supplied by `GET /api/parade-nights/{id}/schedule` (new endpoint, see §9).
2. **All sessions** for the night (existing `pn.sessions`), each now carrying a `timing_block_id` foreign key so they can be grouped by period.

### 6b. Column structure

Fixed column groups (always rendered, in this order):

1. **Orientation / Initial** — sub-columns: all ORI-stage classes, then all INI-stage classes, ordered by `applies_from`
2. **Junior / Bronze** — sub-columns: all JNR-stage classes
3. **Intermediate / Silver** — sub-columns: all INT-stage classes
4. **Senior / Gold** — sub-columns: all SNR-stage classes

Dynamic column groups (rendered after fixed groups, only when sessions assigned):
5+ **Custom phases** active on that parade night, sorted alphabetically

If a stage group has no training classes defined for the year, one column still renders under that group header, showing `—` for all rows.

### 6c. Row structure

| Row type | Time col | Block name col | Class sub-columns |
|---|---|---|---|
| Non-Training-Period block | start time | block name (e.g. "Parade", "Drinks Break") | `—` for all |
| Training Period block | start–end time | custom name (e.g. "Flight Period") | per-class cell: lesson title, facilitator(s), room |

Training Period cell content:
- Line 1: curriculum item title (or *Unassigned* in muted style)
- Line 2: facilitator name(s), comma-separated
- Line 3: room/location
- If no session assigned for this class/period: `—`

### 6d. Print layout

- **Orientation: landscape** (`@media print { @page { size: landscape; } }`)
- The existing `@media print` block hides nav, topbar, filters
- The header block shows: squadron name, date (long format), wing name, term, time range
- **Footer:** `Generated [date in en-AU format]` — no wing code, no "planning document only"
- Table uses `table-layout: fixed` with percentage widths; Time and Block columns are narrow; class sub-columns share remaining width equally

### 6e. Session ↔ block linkage (new DB field)

`Session` (or the existing sessions table) gains `timing_block_id` (UUID FK → `TimingTemplateBlock`, nullable). When a timing template is applied to a parade night, sessions auto-created for Training Period blocks are stamped with the corresponding `timing_block_id`. Existing sessions without this field default to null and are treated as unlinked (shown in a separate "Unlinked Periods" row at the bottom of the print table).

---

## 7. Per-Night Template Switching (TMS + PW)

### 7a. TMS discoverability

Each parade night card/row gains a small chip showing the applied template name: `Template: Standard Wed Night ▾`. Clicking it opens the existing "Override Parade Night Timing" modal (already implemented as `#m-pn-timing-override`). The modal is relabelled to match the new block-type vocabulary.

### 7b. API change

`PATCH /api/parade-nights/{id}` (or the existing override endpoint) accepts `timing_template_id` to change the applied template. When changed, the backend re-generates sessions for Training Period blocks (preserving any existing lesson/facilitator/room assignments on matching block positions). Requires `sqn_admin` or higher.

### 7c. Planning Workspace

The PW parade night detail view (`frontend/`) adds a "Change Template" dropdown/button that calls the same `PATCH` endpoint. Available templates fetched from `GET /api/timing-templates`. Terminology in PW updated: "Session" → "Training Period" in all user-visible labels.

---

## 8. Year Creation UX (Item 1)

### 8a. Problem

The "Manage Training Years" entry point is a hidden `⚙` gear icon in the Activities page header, visible only to admins, with no label. New users cannot find it.

### 8b. Solution

Add a **Training Years** card to the Unit Settings page (`page-settings`), between the Access Code card and the Timing Templates card. The card shows the existing `ynManageTable` list (year / status / actions) and the "+ Create Year" button — the same content currently in the `m-manage-years` modal, promoted to an always-visible settings card.

The gear icon in Activities remains as a shortcut but gains a visible label: `Manage Years` (instead of the bare ⚙ symbol).

### 8c. Post-creation prompt

After `ynCreateYear()` succeeds, show an inline prompt within the Training Years card:

> "Year [N] created. 5 default training classes have been added. Go to Training Classes to customise them, or continue to set up Timing Templates."

Two links: **Training Classes ↓** (scrolls to the classes card) and **Timing Templates ↓** (scrolls to the templates card). This replaces the existing silent create behaviour.

---

## 9. Backend API Changes

| Method | Endpoint | Change |
|---|---|---|
| POST | `/api/planning/years` | Auto-create 5 training classes (ORI/INI/JNR/INT/SNR) after year creation |
| GET | `/api/parade-nights/{id}/schedule` | **New.** Returns all timing template blocks for the night + sessions keyed by `timing_block_id` and `training_class_id` |
| PATCH | `/api/parade-nights/{id}` | Add `timing_template_id` field; re-generate sessions on template change |
| GET | `/api/training-classes` | Add `stage_code`, `applies_from`, `applies_to` to response |
| POST/PATCH | `/api/training-classes` | Accept `stage_code`, `applies_from`, `applies_to` |
| GET/POST/PATCH/DELETE | `/api/custom-training-phases` | **New CRUD.** Scope-filtered; respects scope hierarchy on GET |
| GET/POST/PATCH/DELETE | `/api/timing-templates` (blocks) | Accept new block type values; `training_period` blocks require `name` field |

---

## 10. Database Migrations (Alembic)

In order:

1. **`timing_template_blocks` table** — add `name` column (string, nullable initially; backfill `ip` → `Training Period` then `NOT NULL`); migrate `type` values: `ip` → `training_period`, `break` → `drinks_break`.
2. **`training_classes` table** — add `stage_code` (enum string, nullable initially for existing rows; set default `SNR` for existing then make required); add `applies_from` (Date, nullable); add `applies_to` (Date, nullable).
3. **`sessions` table** — add `timing_block_id` (UUID FK → `timing_template_blocks.id`, nullable, ON DELETE SET NULL).
4. **`custom_training_phases` table** — new table with all fields from §5a.

Each migration is a separate Alembic version file. All use `batch_alter_table` for SQLite compatibility.

---

## 11. Out of Scope

- Cadet-level tracking within training classes (which individual cadets are in which class)
- Attendance recording per Training Period
- The PW's internal session planning drag-and-drop UI
- Any new parade night creation flow (existing create flow unchanged)
- Timetable conflicts detection across custom phases

---

## What Is NOT Changing

- `connected-frontend/index.html` is not replaced or split.
- Existing timing template `effective_from` / `effective_to` date range logic is unchanged.
- Existing session scheduling, lesson assignment, facilitator and room allocation flows are unchanged — only labels and column structure change.
- The `NAV_BY_SCOPE` routing table is unchanged.
- Existing training class conflict detection logic is unchanged.
