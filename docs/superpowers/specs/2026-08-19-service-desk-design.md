# Service Desk — Design Spec

**Sub-project E, Phase 1 of 1**
Issue reporting and tracking for AAFC TMS. Authenticated and unauthenticated submission, role-scoped visibility, system_admin actioning.

---

## 1. Goal

Provide a lightweight internal service desk so Training Officers and admins can report problems with the TMS. System administrators can view, annotate, and resolve tickets. Wing and national admins can monitor tickets from their scope. No external tool required — the form is accessible before login and from inside the app.

---

## 2. Scope and constraints

- Backend: new `service_tickets` table + 3 endpoints. One Alembic migration. No changes to existing tables.
- Frontend: `connected-frontend/index.html` only — new modal form, new `page-service-desk`, nav entry, pre-login link. No backend or schema changes outside this feature.
- No email notifications — system has no SMTP config. Submission confirmed by toast only.
- No ticket reference numbers — not required.
- Rate limiting: public POST endpoint uses the existing per-IP rate limiter.
- Audit log: status and notes changes by system_admin are written to `AuditLog`.
- B-DS tokens apply throughout (`--dark`, `--blue`, `--surface`, `--border`, spacing tokens, `.tbl`, `.badge`, `.btn-*`).

---

## 3. Data model

### Table: `service_tickets`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUID | PK, default uuid4 | |
| `rank` | VARCHAR(40) | NOT NULL | Free text, e.g. "Fg Off", "WO2" |
| `first_name` | VARCHAR(80) | NOT NULL | |
| `last_name` | VARCHAR(80) | NOT NULL | |
| `email` | VARCHAR(200) | NOT NULL | Validated as email format |
| `squadron_id` | UUID | NOT NULL, FK → `squadrons.id` | Selected from dropdown |
| `description` | TEXT | NOT NULL | Minimum 10 characters |
| `status` | VARCHAR(20) | NOT NULL, default `'open'` | `open` / `in_progress` / `resolved` |
| `admin_notes` | TEXT | nullable | Written by system_admin only |
| `created_at` | TIMESTAMP | NOT NULL, default now | |
| `resolved_at` | TIMESTAMP | nullable | Stamped when status → `resolved` |

No soft-delete. Tickets are permanent records — archiving is not supported.

### Alembic migration

One new migration from current head. Uses `batch_alter_table` for SQLite compatibility. Foreign key to `squadrons.id` with `ondelete='SET NULL'` so archiving a squadron does not destroy ticket history (set `squadron_id` nullable in migration, `NOT NULL` enforced at application layer for new submissions only).

---

## 4. API

### 4.0 `GET /api/public/squadrons` — public, no auth

Returns a minimal list of active squadrons for the pre-login ticket form's unit dropdown.

**Response 200**
```json
[
  { "squadron_id": "<uuid>", "name": "703 SQN AAFC" },
  { "squadron_id": "<uuid>", "name": "704 SQN AAFC" }
]
```

Ordered alphabetically by name. Archived squadrons excluded. No other fields returned — this endpoint is intentionally minimal to avoid exposing operational data without authentication.

---

### 4.1 `POST /api/service-desk/tickets` — public, no auth

Creates a new ticket. Available to unauthenticated callers (pre-login form) and authenticated callers (in-app form).

**Request body**
```json
{
  "rank": "Fg Off",
  "first_name": "Jane",
  "last_name": "Smith",
  "email": "jane.smith@example.com",
  "squadron_id": "<uuid>",
  "description": "The cadet roster is not loading for our squadron."
}
```

**Validation**
- All fields required and non-empty after strip.
- `email` must match basic RFC 5322 pattern (Pydantic `EmailStr`).
- `description` minimum 10 characters.
- `squadron_id` must reference an active (non-archived) squadron.
- Rate limited by existing per-IP limiter.

**Response 201**
```json
{ "ok": true, "ticket_id": "<uuid>" }
```

**Errors**
- `422` — validation failure, field-level detail.
- `404` — squadron not found or archived.
- `429` — rate limit exceeded.

### 4.2 `GET /api/service-desk/tickets` — authenticated

Returns tickets scoped to the caller's role. Query params:
- `status` — optional filter: `open` / `in_progress` / `resolved` / omit for all.

**Scoping**
| Role | Tickets returned |
|------|-----------------|
| `system_admin` | All |
| `national_admin` | All (read-only) |
| `wing_admin` | Tickets where `squadron.wing_id = caller.wing_id` |
| `sqn_admin` | Tickets where `squadron_id = caller.squadron_id` |
| `auditor` | 403 |
| `sqn_general` | 403 |

**Response 200**
```json
[
  {
    "ticket_id": "<uuid>",
    "rank": "Fg Off",
    "first_name": "Jane",
    "last_name": "Smith",
    "email": "jane.smith@example.com",
    "squadron_id": "<uuid>",
    "squadron_name": "703 SQN AAFC",
    "description": "The cadet roster is not loading…",
    "status": "open",
    "admin_notes": null,
    "created_at": "2026-08-19T10:00:00Z",
    "resolved_at": null
  }
]
```

Ordered newest first (`created_at DESC`).

### 4.3 `PATCH /api/service-desk/tickets/{ticket_id}` — system_admin only

Updates status and/or admin notes. Partial update — omitted fields unchanged.

**Request body**
```json
{
  "status": "in_progress",
  "admin_notes": "Reproduced — investigating with Railway logs."
}
```

**Business rules**
- Only `system_admin` may call this endpoint. All other roles receive 403.
- `status` must be one of `open`, `in_progress`, `resolved`.
- When `status` changes to `resolved`, server stamps `resolved_at = now()`.
- When `status` changes away from `resolved`, server clears `resolved_at`.
- `admin_notes` replaces the existing value (caller appends manually if desired).

**Audit log** — written on every successful PATCH:
- `object_type = "service_ticket"`
- `object_id = ticket_id`
- `action = "updated"` with `old` / `new` values for `status` and presence of notes change.

**Response 200**
```json
{ "ok": true }
```

---

## 5. Frontend

### 5.1 Pre-login entry point

A `"Report an Issue"` link is rendered below the login card on the login screen. Styling:

```css
/* Below the login card, centered */
.login-report-link {
  display: block;
  text-align: center;
  margin-top: var(--sp-md);        /* 16px below card */
  font-size: 11px;
  font-weight: 600;
  color: rgba(255,255,255,.45);
  cursor: pointer;
  text-decoration: none;
  background: none;
  border: none;
}
.login-report-link:hover {
  color: rgba(255,255,255,.72);
}
/* Text: Report an Issue */
```

Clicking opens the ticket submission modal (see §5.3). The link is always visible regardless of login step.

### 5.2 In-app entry point

- `Service Desk` is added to `NAV_BY_SCOPE` for scopes: `squadron`, `wing`, `national`, `system_admin`.
- Nav icon: a speech-bubble or flag glyph (SVG inline, consistent with existing nav icons).
- Activating the nav item loads `page-service-desk` via `nav('service-desk')`.
- At the top of the page a `"Submit a Ticket"` button (`btn-primary`) opens the same ticket submission modal.

### 5.3 Ticket submission modal

Used from both pre-login and in-app. Rendered as a centred overlay modal.

**HTML structure (skeleton)**
```html
<div id="sd-modal" class="modal-overlay" style="display:none">
  <div class="modal card" style="width:480px;max-width:96vw">
    <div class="modal-hdr">
      <span class="modal-title">Report an Issue</span>
      <button class="modal-close" onclick="sdCloseModal()">✕</button>
    </div>
    <form id="sd-form" onsubmit="sdSubmit(event)">
      <div class="form-group">
        <label class="ff-label">Rank</label>
        <input id="sd-rank" type="text" class="ff-input" placeholder="e.g. Fg Off" required>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:var(--sp-sm)">
        <div class="form-group">
          <label class="ff-label">First Name</label>
          <input id="sd-first" type="text" class="ff-input" required>
        </div>
        <div class="form-group">
          <label class="ff-label">Last Name</label>
          <input id="sd-last" type="text" class="ff-input" required>
        </div>
      </div>
      <div class="form-group">
        <label class="ff-label">Email</label>
        <input id="sd-email" type="email" class="ff-input" required>
      </div>
      <div class="form-group">
        <label class="ff-label">Unit</label>
        <select id="sd-sqn" class="ff-select" required></select>
      </div>
      <div class="form-group">
        <label class="ff-label">Description of Issue</label>
        <textarea id="sd-desc" class="ff-input" rows="4"
          placeholder="Describe the issue…" required></textarea>
      </div>
      <div id="sd-err" style="display:none" class="form-err"></div>
      <div class="modal-footer">
        <button type="button" class="btn btn-secondary" onclick="sdCloseModal()">Cancel</button>
        <button type="submit" class="btn btn-primary">Submit</button>
      </div>
    </form>
  </div>
</div>
```

**JS behaviour**

`sdOpenModal(preselectedSquadronId)` — opens the modal. If `preselectedSquadronId` is provided (logged-in sqn_admin), the unit select is set to that value and disabled. Wing/national/system_admin callers leave the select enabled. Pre-login callers leave it enabled.

Squadron list is populated from `GET /api/public/squadrons` — a new lightweight public endpoint (no auth) that returns only `[{squadron_id, name}]` for active squadrons, ordered alphabetically. This avoids exposing the authenticated `/api/squadrons` endpoint without auth. Cached in `window._sdSquadrons` after first fetch.

On submit: POST to `/api/service-desk/tickets`. On 201: close modal, show toast "Ticket submitted — a system administrator will follow up." On 422: display field errors inline below offending inputs. On 429: display "Too many requests — please wait before submitting again."

### 5.4 Service Desk page (`page-service-desk`)

**Page structure**
```
┌─────────────────────────────────────────────────────────┐
│  Service Desk                    [Submit a Ticket ▶]    │  ← page heading row
├─────────────────────────────────────────────────────────┤
│  [All]  [Open]  [In Progress]  [Resolved]               │  ← filter bar (seg buttons)
├─────────────────────────────────────────────────────────┤
│  Ticket list (.tbl)             │  Detail panel         │
│  Date · Name · Unit · Desc · ● │  (hidden until click) │
│  ...                            │                       │
└─────────────────────────────────────────────────────────┘
```

**Ticket list columns**

| Column | Detail |
|--------|--------|
| Date | `dd MMM YYYY` — `created_at` |
| Submitted By | `Rank First Last` |
| Unit | Squadron name |
| Issue | Description truncated to 60 chars, ellipsis |
| Status | `.badge` — `open`→blue, `in_progress`→amber, `resolved`→green |

Rows are clickable. Active row highlighted with `background: var(--accent-light)`.

**Detail panel**

Slides in from the right (CSS `transform: translateX(100%)` → `translateX(0)`, `transition: transform .18s`). Width 360px. Ticket list shrinks to fill remaining width via flex. Panel closes via `[×]` button or pressing Escape.

Panel contents:
```
[×]

Submitted: 19 Aug 2026
703 SQN AAFC

Fg Off Jane Smith
jane.smith@example.com

DESCRIPTION
──────────────────────────────────
The cadet roster is not loading for our squadron.

ADMIN NOTES                          ← textarea (system_admin) / plain text (others)
──────────────────────────────────
[textarea placeholder "Add notes…"]

STATUS
──────────────────────────────────
[Open]  [In Progress]  [Resolved]   ← seg buttons (system_admin only)

                        [Save Changes]  ← system_admin only
```

For wing/national admins: admin notes shown as plain text (or "No notes yet" if empty). Status shown as a static badge. No Save button.

**`loadServiceDesk()`** — called by `nav()` when `page-service-desk` activates. Fetches `GET /api/service-desk/tickets`, renders the table. Filter buttons re-render client-side from the cached response (no re-fetch on filter change).

**`sdSave(ticketId)`** — called by Save Changes button. PATCHes `{ status, admin_notes }`. On 200: updates the row badge in the list and refreshes the panel. On error: inline error below the Save button.

**Empty state:** When filtered list is empty — centred `"No tickets"` in `--muted`, 13px. No illustration.

---

## 6. Role access summary

| Role | Pre-login submit | In-app submit | View Service Desk page | Update tickets |
|------|-----------------|---------------|----------------------|----------------|
| Unauthenticated | ✓ | — | — | — |
| `sqn_admin` | ✓ | ✓ (own sqn pre-filled) | ✓ (own sqn tickets) | — |
| `wing_admin` | ✓ | ✓ | ✓ (wing scope) | — |
| `national_admin` | ✓ | ✓ | ✓ (all) | — |
| `system_admin` | ✓ | ✓ | ✓ (all) | ✓ |
| `auditor` | ✓ (pre-login) | — | — | — |
| `sqn_general` | ✓ (pre-login) | — | — | — |

---

## 7. Testing

### Backend tests (`tests/test_service_desk.py`)

- `test_public_squadrons_returns_active_only` — GET /api/public/squadrons returns active squadrons, excludes archived, no auth required.
- `test_create_ticket_unauthenticated` — public POST succeeds with valid body, returns 201.
- `test_create_ticket_validates_required_fields` — missing fields return 422.
- `test_create_ticket_validates_email_format` — invalid email returns 422.
- `test_create_ticket_validates_description_length` — < 10 chars returns 422.
- `test_create_ticket_archived_squadron_rejected` — archived squadron_id returns 404.
- `test_sqn_admin_sees_own_squadron_tickets_only` — GET returns only own squadron.
- `test_wing_admin_sees_wing_scope_tickets` — GET returns only wing's squadrons.
- `test_national_admin_sees_all_tickets` — GET returns all.
- `test_system_admin_sees_all_tickets` — GET returns all.
- `test_auditor_cannot_list_tickets` — GET returns 403.
- `test_system_admin_can_update_status` — PATCH changes status, resolved_at stamped on resolve.
- `test_system_admin_can_add_notes` — PATCH updates admin_notes.
- `test_non_system_admin_cannot_patch` — wing_admin PATCH returns 403.
- `test_audit_log_entry_created_on_patch` — AuditLog entry exists after PATCH.
- `test_status_filter_param` — GET with `?status=open` returns only open tickets.

### Frontend verification (manual)

1. Pre-login form visible and submits without auth — toast confirms.
2. In-app: Service Desk nav item visible for sqn_admin, wing, national, system_admin; hidden for auditor.
3. sqn_admin: only own squadron's tickets listed; unit select pre-filled and locked on form.
4. system_admin: all tickets visible; Save Changes updates status and notes; badge updates in list.
5. wing/national: tickets visible (scoped); panel shows read-only notes and static badge.
6. Filter bar correctly hides/shows rows by status client-side.
7. Detail panel slides in on row click, closes on × and Escape.

---

## 8. File map

**Create:**
- `backend/app/routers/service_desk.py` — all four endpoints (including public squadrons list)
- `backend/app/models/service_ticket.py` — `ServiceTicket` model
- `backend/alembic/versions/<hash>_add_service_tickets.py` — migration
- `backend/tests/test_service_desk.py` — full test suite

**Modify:**
- `backend/app/models/__init__.py` — import `ServiceTicket`
- `backend/app/main.py` — register `service_desk` router (prefix `/api/service-desk`)
- `connected-frontend/index.html` — modal HTML, `page-service-desk` HTML, `sdOpenModal` / `sdCloseModal` / `sdSubmit` / `loadServiceDesk` / `sdSave` JS, nav entry in `NAV_BY_SCOPE`, pre-login link below login card
