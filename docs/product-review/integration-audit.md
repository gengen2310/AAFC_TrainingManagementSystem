# AAFC TMS — Integration Audit

**Review:** Post-Gap Human Workflow, Architecture and Design Review — Stage 2 (Superpowers)  
**Date:** 2026-08-16  
**Scope:** All integration points between Main TMS and Planning Workspace, plus external integrations  
**Method:** Analysis only — no changes

---

## 1. Integration map

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Integration Points                          │
│                                                                      │
│  Main TMS (connected-frontend)          Planning Workspace (PW)     │
│  ─────────────────────────────          ──────────────────────────  │
│                                                                      │
│  1. Auth handoff ──────────────────────► Cookie → PW authenticates  │
│     (aafc_session cookie)                                            │
│                                                                      │
│  2. Session entity bridge ─────────────► Sessions in PW appear      │
│     (shared /api/sessions table)         in Main TMS Parade Nights  │
│                                                                      │
│  3. "Open PW" link ────────────────────► PW opens at /planning      │
│     (nav → Planning Workspace ↗)         in new tab                 │
│                                                                      │
│  4. Shared API (read) ─────────────────► Both read same backend     │
│     (GET /api/*)                          All data consistent        │
│                                                                      │
│  5. Back link ◄────────────────────────── ← Main TMS link in PW nav │
│     (closes PW, returns to Main TMS)                                 │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

External integrations:
  A. Learning Hub (airforcecadets.net.au)  — outbound link only
  B. CEA Activity Import                   — file-based import
  C. Curriculum XLSM Import               — file-based import
  D. GitHub Actions (backup/restore)      — Supabase direct
  E. Google Fonts CDN                     — stylesheet link (optional)
```

---

## 2. Integration 1: Auth handoff (Main TMS → PW)

### Mechanism

When the user clicks "Planning Workspace ↗" in Main TMS:
1. Main TMS opens `/planning` in a new browser tab
2. The `aafc_session` cookie (set at login, `SameSite=None; Secure`, `HttpOnly`) is sent by the browser with the new-tab request
3. PW on load calls `GET /api/auth/me` with the cookie
4. Backend returns the user's role/scope/session from the cookie
5. PW stores the JWT token in `sessionStorage` for subsequent API calls

### Risks

**IA-R01: Browser privacy settings block SameSite=None cookies**

Safari's Intelligent Tracking Prevention (ITP) and Firefox's Enhanced Tracking Protection can block third-party cookies — including `SameSite=None` cookies sent to a different origin. In these browsers, the handoff fails silently: PW opens but shows a login screen, not the expected view. The user is not told why.

*Affected users:* Any Training Officer using Safari (common on Mac/iPad) or Firefox with Enhanced Tracking Protection. This is a significant proportion of the target user population.

*Current mitigation:* None observed.

*Detection:* A user opening PW from Main TMS in Safari will see the PW login page with their unit pre-populated from the URL hash (if hash-fragment auth is implemented) or a blank login form.

**IA-R02: Token TTL mismatch between Main TMS and PW**

If the Main TMS session is near-expiry (cookie TTL close to 0), the cookie may still be valid enough to authenticate the PW session but expire shortly after. The user would then be in an authenticated state in Main TMS but unauthenticated in the PW tab.

*Severity:* LOW — users would simply re-authenticate. No data loss.

**IA-R03: Hash-fragment token handoff**

The architecture notes mention "hash-fragment token handoff" as a mechanism. This passes the JWT token as a URL fragment (e.g., `/planning#token=...`). Hash fragments are:
- Never sent to the server (client-only)
- Not stored in browser history on navigation (if handled correctly)
- Accessible to JavaScript on the destination page

This mechanism would allow the handoff without relying on cookies. However:
- The token is briefly visible in the address bar
- If the user copies the URL and sends it to someone, the token is exposed until it expires
- The PW must clear the hash immediately after consuming the token

*Assessment:* If hash-fragment handoff is implemented, verify that the PW clears the URL fragment immediately after consuming the token and that the token cannot be cached or shared.

**IA-R04: PW opened without Main TMS context (direct navigation)**

If a user bookmarks the PW URL and returns to it directly (without first logging into Main TMS), there is no cookie and no token. The PW must fall back to showing its own login screen. This login screen must:
- Know which unit/wing the user belongs to (required for the lookup step)
- Not assume the user is logged into Main TMS first

*Current state:* PW login screen should function independently. Verify that `POST /api/auth/lookup` and `POST /api/auth/login` work when called from the PW origin.

---

## 3. Integration 2: Session entity bridge

### Mechanism

The `Session` entity is the primary data bridge between PW and Main TMS:

```
PW (planning)                              Main TMS (operational)
─────────────────                          ──────────────────────────
Create session plan                        Create session (quick entry)
  POST /api/planning/                        POST /api/sessions
  parade-dates/{id}/sessions                 
                                           
Both write to the same `sessions` table    

PW reads sessions from:                    Main TMS reads sessions from:
  GET /api/planning/                         GET /api/parade-nights/{id}
  parade-dates/{id}/builder                  (includes sessions array)
  GET /api/planning/sessions/{id}            GET /api/sessions/{id}
```

### Session lifecycle across systems

```
Planning (PW)                    Operational (Main TMS)
─────────────────────────────    ─────────────────────────────────────
Create session (draft)           
Assign curriculum, class,        
  facilitator, room              
Publish parade night         ─►  Session appears in Parade Night view
                                  Status: planned → published
                                 Record outcome:
                                   delivered / not_delivered / cancelled
                             ◄─  Closed parade night
Session visible in PW as         
  delivered/cancelled (if       
  PW re-fetches status)         
```

### Risks

**IA-R05: Outcome recording in Main TMS not reflected in PW real-time**

When a Training Officer records that a session was "delivered" in Main TMS, the PW calendar still shows the session in its planned state until the PW re-fetches data. If the Training Officer has both tabs open, they may see inconsistent views of the same session.

*Severity:* LOW — data is consistent in the database; the display lag is a UI refresh issue.

**IA-R06: PW session archive vs Main TMS cancel divergence**

As noted in the data-model-audit:
- `DELETE /api/planning/sessions/{id}` in PW archives a session (removes from plan)
- `POST /api/sessions/{id}/status` with `cancelled` in Main TMS records a cancellation

These are different operations. A session that is "cancelled" in Main TMS still appears in PW as planned (it has not been archived). A session that is "archived" in PW may still appear in Main TMS as a visible session (depending on whether archived sessions are filtered).

*Verification needed:* Does the Main TMS parade night view filter out PW-archived sessions?

**IA-R07: Session created in Main TMS without PW context**

If a Training Officer creates a session in Main TMS (Quick Entry or Guided mode), the session is created without a `parade_date_id` link (it has a `parade_night_id` only). Does this session appear in the PW planning view? And if so, does it appear correctly?

*This depends on:* Whether the PW reads sessions via the planning endpoint (which requires `parade_date_id`) or directly from the sessions table. If PW uses the planning endpoint, Main-TMS-only sessions would not appear in PW.

*Severity:* MEDIUM — if a Training Officer uses Main TMS to create sessions and then opens PW, they may find PW does not show those sessions.

---

## 4. Integration 3: Navigation link from Main TMS to PW

### Current behaviour

The "Planning Workspace ↗" link in Main TMS navigation:
- Opens `/planning` in a new tab
- Is listed in `NAV_BY_SCOPE._PLANNING_PAGES` as always empty `[]` in the current pilot configuration
- May not be visible in all role/environment configurations

### Risks

**IA-R08: PW link conditionally visible**

The `_PLANNING_PAGES` array being empty in the pilot configuration means the Planning Workspace nav item may not appear or may appear as "(unavailable)". A Training Officer who has never been shown the link will not know PW exists.

*This is one of the highest-impact discoverability issues in the system.* See findability-audit.md CF-08.

**IA-R09: No context passed to PW on open**

When the user clicks "Planning Workspace," the new tab opens at `/planning` with no context:
- No pre-selected squadron (wing/national users would need to re-select)
- No pre-selected planning year (user must select on arrival)
- No indication of which operation in Main TMS prompted the navigation (e.g., "I opened PW from Parade Nights because I wanted to plan next Thursday")

*Consequence:* Every PW session starts at the top — year/squadron selection required before any work can be done. For a daily user this is acceptable; for occasional users this is friction.

*Potential improvement:* Pass `?year_id=X&squadron_id=Y` in the URL so PW can pre-select the relevant context.

---

## 5. Integration 4: Back navigation from PW to Main TMS

### Current behaviour

PW has a "← Main TMS" link in the nav that closes or redirects back to the Main TMS. This is present in all scope groups in AppShell.tsx.

**Assessment:** Correct and necessary. A user who navigated from Main TMS to PW has an easy way back. The current implementation closes the PW tab or navigates away — verify which.

**Risk:** If the link navigates away (not closes), the user loses the PW tab state. If it closes the tab, the user returns to Main TMS in whatever state they left it. The close-tab behaviour is preferable.

---

## 6. Integration 5: Shared backend API

Both frontends call the same FastAPI backend. This is the most fundamental integration and the most reliable:
- Data is always consistent (both read the same DB)
- Auth is handled identically (same JWT validation)
- Audit log captures actions from both frontends (both send the same auth token)

**Strength:** This is the correct architecture. No data sync required between frontends.

**Risk:** CORS configuration must allow both frontend origins. If only Main TMS origin is in `CORS_ALLOWED_ORIGINS` and PW is deployed at a different Railway subdomain, PW API calls will be blocked. Verify that both origins are included.

---

## 7. External integrations

### EA-01: Learning Hub (airforcecadets.net.au)

**Type:** Outbound link  
**Integration depth:** URL storage in `CurriculumItem.learning_hub_url`  
**Risk:** Link rot — if the Learning Hub URL changes, stored links become dead. There is a "Missing Learning Hub link" filter in the curriculum view for data quality, but no automated check for broken links.  
**Severity:** LOW.

### EA-02: CEA Activity Import

**Type:** File-based import (uploaded via `/api/planning/years/{year_id}/cea/import` or `/api/activities/import-cea`)  
**Integration depth:** One-way import from CEA data file to local `CeaActivity` records  
**Risk:** No live sync — CEA data must be manually re-imported when it changes. If the CEA updates an event date after it has been imported, the local record is stale.  
**Severity:** LOW — file-based import is the intended mechanism.

### EA-03: Curriculum XLSM/CSV Import

**Type:** File-based import  
**Risk:** Same as EA-02 — one-directional, manual.  
**Severity:** LOW.

### EA-04: GitHub Actions — Backup/Restore

**Type:** Scheduled workflow (daily backup, weekly restore test)  
**Risk:** The backup uses `SUPABASE_DB_URL` stored as a GitHub Secret. If the key is rotated or the Supabase URL changes, the backup silently fails until someone checks the Actions log.  
**Monitoring:** `test-restore-postgresql.yml` (weekly) should catch this.  
**Severity:** LOW — standard CI/CD risk.

### EA-05: Google Fonts CDN

**Type:** External stylesheet link (Montserrat)  
**Risk:** If Google Fonts CDN is unavailable, the application falls back to Arial. This is a cosmetic fallback, not a functional failure. The playwright staging suite now correctly excludes Google Fonts 404s from network error checks.  
**Severity:** VERY LOW.

---

## 8. Summary findings

| ID | Finding | Severity | Domain |
|---|---|---|---|
| IA-R01 | Safari/Firefox ITP blocks SameSite=None cookie handoff | HIGH | Auth |
| IA-R02 | Token TTL mismatch | LOW | Auth |
| IA-R03 | Hash-fragment token handoff must clear URL immediately | LOW | Auth |
| IA-R04 | PW direct navigation must work without Main TMS session | LOW | Auth |
| IA-R05 | Outcome recording lag — PW not updated until re-fetch | LOW | Data sync |
| IA-R06 | PW archive vs Main TMS cancel — divergent session visibility | MEDIUM | Data integrity |
| IA-R07 | Main-TMS-only sessions may not appear in PW | MEDIUM | Data integrity |
| IA-R08 | PW link conditionally visible — discoverability failure | HIGH | Navigation |
| IA-R09 | No context passed to PW on open | LOW | UX |
| EA-01 | Learning Hub link rot (no automated validation) | LOW | External |
| EA-02–03 | CEA/Curriculum import is manual, stale data risk | LOW | External |
| EA-04 | Backup key rotation risk | LOW | Infrastructure |

### Priority focus

The two HIGH findings (IA-R01 and IA-R08) are the most significant:

**IA-R01 (Safari/Firefox cookie block):** This affects the authentication handoff for a substantial proportion of users. If a Training Officer's school-issued MacBook uses Safari with default privacy settings, the PW will always show a login screen when opened from Main TMS. This is a reliability issue for the core cross-app navigation path.

**IA-R08 (PW link conditional visibility):** If the Planning Workspace link is not shown in the nav, users cannot discover or access PW at all. This is an architecture-level discoverability failure that cannot be resolved by UI improvements alone.

