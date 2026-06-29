# API reference

Full interactive docs at `/docs` (Swagger) and `/redoc`; machine schema at `/openapi.json`
(77 routes — 32 new in V11 TRGO Planning). Highlights:

- Auth: `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`, `POST /api/auth/change-code`
- Orgs: `GET /api/national/overview`, `GET|POST /api/wings`, `GET|POST /api/squadrons`, `PATCH /api/squadrons/{id}`
- Proxy: `POST /api/proxy/enter/{squadron_id}` (reason required), `POST /api/proxy/exit`, `GET /api/proxy/current`
- Curriculum: `GET /api/curriculum`, `POST /api/curriculum` (squadron), `POST /api/curriculum/wing`, `POST /api/curriculum/national`, `PATCH /api/curriculum/{id}`, `DELETE /api/curriculum/{id}`, `GET /api/curriculum/{id}/sessions`
- Parade/sessions: `GET|POST /api/parade-nights`, `GET /api/parade-nights/{id}` (incl. readiness + publish_blockers),
  `POST /api/parade-nights/{id}/publish|close`, `POST /api/sessions`, `PUT /api/sessions/{id}`, `POST /api/sessions/{id}/status`
- Facilitators: `GET|POST /api/facilitators`, `GET /api/facilitators/{id}/stats`
- Resources: `GET /api/training-areas`, `/api/equipment`, `/api/resources/clashes`
- Cadets: `GET /api/cadets` (gated), `GET /api/cadets/risk`
- Reports: `/api/reports/summary|readiness|curriculum-coverage|facilitator-load|not-delivered|wing-overview|national-overview`
- Actions/automation: `GET|POST /api/action-items`, `POST /api/action-items/{id}/close`, `POST /api/exceptions/run-checks`
- Import: `POST /api/import/preview|commit|rollback`
- Audit: `GET /api/audit`
- Health: `GET /api/health`, `/api/health/db`, `/api/health/ready`
- **TRGO Planning (V11):**
  - Years: `GET|POST /api/planning/years`, `GET|PATCH /api/planning/years/{id}`
  - Parade dates: `GET|POST /api/planning/years/{id}/parade-dates`, `POST /api/planning/years/{id}/generate-parade-dates`, `DELETE /api/planning/parade-dates/{id}`
  - Holidays: `GET|POST /api/planning/years/{id}/holidays`, `DELETE /api/planning/holidays/{id}`
  - Anchors: `GET|POST /api/planning/years/{id}/anchors`, `PATCH|DELETE /api/planning/anchors/{id}`, `GET /api/planning/anchors/{id}/prep-suggestions`
  - Planner views: `GET /api/planning/years/{id}/term-planner`, `GET /api/planning/years/{id}/long-range`, `GET /api/planning/years/{id}/decision-guide`
  - Builder: `GET /api/planning/parade-dates/{id}/builder`, `POST /api/planning/parade-dates/{id}/sessions`, `PATCH|DELETE /api/planning/sessions/{id}`
  - Program: `GET /api/planning/parade-dates/{id}/weekly-program`
  - Locations: `GET|POST /api/planning/locations`, `PATCH /api/planning/locations/{id}`
  - Facilitators: `GET /api/planning/facilitators`
  - Conflicts: `GET /api/planning/years/{id}/conflicts`, `POST /api/planning/years/{id}/run-checks`, `POST /api/planning/conflicts/{id}/override`
  - Prep rules: `GET /api/planning/prep-rules`

Auth errors use structured detail, e.g. `{"error":"proxy_required"}` /
`{"error":"intervention_required"}` for privileged edits without an active session.

## V6 Account Management and Flight routes

### Accounts
- `GET /api/accounts` — list accounts scoped to caller's authority; supports `?wing_id=`, `?squadron_id=`, `?flight_id=` filters. Never returns `code_hash` or `new_code`.
- `POST /api/accounts` — create account; returns `new_code` **once only**. Body: `display_name`, `role`, `wing_id`, `squadron_id`, `national_id` (optional), `flight_id` (optional), `new_code` (optional manual code).
- `GET /api/accounts/{id}` — single account detail. Never returns `code_hash` or `new_code`.
- `PATCH /api/accounts/{id}` — update `display_name` and/or `flight_id`. Audited.
- `POST /api/accounts/{id}/reset-code` — generate or set new code; returns `new_code` once only. Body: `new_code` (optional; omit to auto-generate).
- `POST /api/accounts/{id}/disable` — deactivate account and access code. Cannot disable self (400).
- `POST /api/accounts/{id}/reactivate` — reactivate account and access code.

### Flights (local squadron groupings — no tenancy or permission expansion)
- `GET /api/flights` — list flights scoped to caller; supports `?squadron_id=` filter.
- `POST /api/flights` — create flight. Body: `name`, `squadron_id`.
- `PATCH /api/flights/{id}` — rename flight or toggle `active_status`. Body: `name` (optional), `active_status` (optional).
- `POST /api/flights/{id}/archive` — soft-delete; clears `flight_id` from all assigned users first.

### Account creation authority
| Creator role | May create roles |
|---|---|
| `system_admin` | All 8 roles |
| `national_admin` | All except `system_admin` |
| `wing_admin` | `wing_viewer`, `sqn_admin`, `sqn_general` (own Wing only) |
| `sqn_admin` | `sqn_general` (own Squadron only) |
| Viewers, `sqn_general`, `auditor` | Cannot create accounts — 403 `forbidden` |

### Access-code security invariants
- `code_hash` is **never** returned by any endpoint.
- Existing plaintext codes are **never** returned by any endpoint.
- `new_code` is returned **exactly once** (create or reset-code response only); it cannot be retrieved later.
- `new_code_notice` always accompanies a one-time code: `"This code will not be shown again. Copy it now."`

## V9.1 Cadet Program routes
- Phases: `GET /api/phases`
- Packages: `GET|POST /api/program-packages`, `POST /api/program-packages/{id}/submit-review|approve|publish|retire|archive`
- Items: `GET /api/program-items?schedulable=…`, `GET /api/program-items/{id}`, `POST /api/program-items`, `POST /api/program-items/{id}/retire`
- Learning Hub: `GET /api/learning-hub-resources`, `GET /api/learning-hub-resources/missing`
- Coverage: `GET /api/program-coverage/squadron`, `GET /api/program-coverage/wing`
- Promotion: `POST /api/program-promotion/squadron-to-wing`, `GET /api/program-promotion/requests`, `POST /api/program-promotion/{id}/approve`
- Export: `GET /api/export/{type}.csv|.xlsx|.pdf`
- Program import: `POST /api/program-imports/preview`

## V8 Timing Templates

### Timing Templates

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/api/timing-templates` | Any authenticated | List active templates for acting squadron |
| `POST` | `/api/timing-templates` | SQN admin (or proxied) | Create template with blocks |
| `GET`  | `/api/timing-templates/effective?date=YYYY-MM-DD` | Any authenticated | Effective template for acting squadron on date |
| `GET`  | `/api/timing-templates/{tid}` | Any authenticated | Get template by ID with blocks |
| `PATCH`| `/api/timing-templates/{tid}` | SQN admin (or proxied) | Update name/dates/notes/blocks |
| `POST` | `/api/timing-templates/{tid}/archive` | SQN admin (or proxied) | Soft-archive template |
| `POST` | `/api/timing-templates/{tid}/apply-from-date` | SQN admin (or proxied) | Set effective_from; closes overlapping open templates |

**Template request body (POST/PATCH):**
```json
{
  "name": "Standard 3-Period Night",
  "effective_from": "2026-09-01",
  "effective_to": null,
  "notes": "Term 3 template",
  "blocks": [
    {"display_order": 0, "block_name": "Arrival", "block_type": "arrival",
     "is_instructional_period": false, "start_time": "18:00", "end_time": "18:15"},
    {"display_order": 1, "block_name": "Period 1", "block_type": "instructional_period",
     "is_instructional_period": true, "start_time": "18:50", "end_time": "19:25"}
  ]
}
```

**Block types:** `arrival`, `administration`, `roll_call`, `parade`, `flight_period`, `instructional_period`, `break`, `fatigues`, `debrief`, `dismissal`, `custom`

**Note:** `flight_period` is a timing slot before Period 1. It is NOT the same as a Flight (squadron sub-group account scope).

## V9 Wing/Squadron CRUD and Multi-Level Curriculum

### Wings

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/api/wings` | Any authenticated | List Wings; scoped (non-national sees own wing only) |
| `POST` | `/api/wings` | `national_admin`, `system_admin` | Create Wing. Body: `code`, `name`, `short_name`. 409 on duplicate code. Audited. |

### Squadrons / Specialist Units

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/api/squadrons` | Any authenticated | List units; supports `?wing_id=`, `?unit_type=`. Returns `unit_type`, `active_status`. |
| `POST` | `/api/squadrons` | `wing_admin` (own wing), `national_admin`, `system_admin` | Create unit. Body: `wing_id`, `code`, `name`, `short_name`, `unit_type`. 409 on duplicate code; 403 cross-wing. Audited. |
| `PATCH`| `/api/squadrons/{id}` | SQN admin (own) or proxied | Update settings inc. `unit_type`. |

**`unit_type` values:** `standard_squadron` (default) | `specialist_squadron` | `specialist_flight` | `support_unit`

All unit types use the same account/tenancy model as a standard squadron. A `specialist_flight` is a Squadron-equivalent training unit — it is NOT the same as a local sub-squadron `Flight` grouping.

### Curriculum (multi-level publication)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/api/curriculum` | Any authenticated | List items visible to actor: national + wing (actor's wing) + squadron (own). Returns `owning_level`, `wing_id`, `squadron_id` on each item. |
| `POST` | `/api/curriculum` | SQN admin (or proxied) | Create `owning_level=squadron` item. |
| `POST` | `/api/curriculum/wing` | `wing_admin`, `national_admin`, `system_admin` | Create `owning_level=wing` item; visible to all SQNs under that Wing. |
| `POST` | `/api/curriculum/national` | `national_admin`, `system_admin` | Create `owning_level=national` item; visible to all Wings and SQNs. |
| `PATCH`| `/api/curriculum/{id}` | By owning_level: national → nat_admin; wing → wing_admin/nat_admin; squadron → sqn_admin | Update title/phase/element/term/duration/lh_url. |
| `DELETE`| `/api/curriculum/{id}` | Same ownership rules as PATCH | Soft-archive. 403 if out of scope. |

**Ownership enforcement:** Squadron admins cannot edit or delete national or wing curriculum (403). Wing admins cannot edit national curriculum (403).

**Response includes:**
- `instructional_period_count` — count of `is_instructional_period=true` blocks
- `warnings` — list of non-blocking warnings (e.g. overlapping block times)

### Parade Night Builder (V12)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/api/parade-nights/{id}/builder` | SQN admin (or proxied) | Returns the Night Builder grid: timing blocks, cadet groups, real Session records |

**`GET /api/parade-nights/{id}/builder` response:**
```json
{
  "parade_night_id": "<uuid>",
  "parade_date": "2026-10-16",
  "parade_type": "normal",
  "squadron_id": "<uuid>",
  "session_count": 3,
  "timing_template_id": "<uuid>|null",
  "timing_blocks": [
    {"block_name": "Period 1", "start_time": "19:15", "end_time": "20:00", "is_instructional_period": true, "period_number": 1}
  ],
  "cadet_groups": ["orientation", "initial", "junior", "intermediate", "senior"],
  "sessions": [
    {
      "session_id": "<uuid>",
      "parade_night_id": "<uuid>",
      "squadron_id": "<uuid>",
      "cadet_group": "junior",
      "session_number": 1,
      "curriculum_id": "<uuid>|null",
      "curriculum_code": "ORI-M01",
      "curriculum_title": "Orientation Module 1",
      "activity_title": "Orientation Module 1",
      "facilitator_id": "<uuid>|null",
      "facilitator_name": "Sgt Smith",
      "location_id": "<uuid>|null",
      "location_name": "Classroom A",
      "status": "planned",
      "notes": null
    }
  ]
}
```

### Parade Night Timing

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/api/parade-nights/{id}/timing` | Any authenticated | Effective timing for this parade night (override or default) |
| `POST` | `/api/parade-nights/{id}/timing-override` | SQN admin (or proxied) | Set one-night override; archives existing override |
| `DELETE` | `/api/parade-nights/{id}/timing-override` | SQN admin (or proxied) | Remove override (soft-archives it) |

**Override request body:**
```json
{"timing_template_id": "<uuid>", "reason": "Shortened ANZAC night"}
```

**`GET /api/parade-nights/{id}/timing` response:**
```json
{
  "source": "override",      // "override" | "default" | "none"
  "override_reason": "...",  // present when source = "override"
  "template": { ...full template dict... },
  "instructional_period_count": 1
}
```

### RBAC
- Viewers and auditors: GET only — POST/PATCH/DELETE return `403`
- `sqn_admin`: own squadron templates only
- `wing_admin` / `national_admin`: must enter Proxy / Delegated Intervention Mode to write
- SQN admin of squadron A cannot modify templates owned by squadron B
