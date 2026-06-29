# AAFC TMS — Access and Scope Model

## 1. Purpose

This document states the access model enforced in the AAFC Training Management System (TMS)
pilot package. The backend is the Backend Source of Truth and the security authority. The
frontend hides controls a role cannot use; it does not enforce security.

## 2. Scope determination

On login the backend returns a session: role, squadron_id, wing_id, national_id, is_wing,
is_national, display_name. All identifiers are UUIDs. The client derives one scope.

| Scope | Condition | Display label / chip |
|---|---|---|
| SQN | squadron_id set; not Wing/NAT HQ | SQN |
| Wing | is_wing true | WING |
| NAT HQ | is_national true; role not auditor | NAT HQ |
| Auditor | role auditor | AUDIT |

NAT HQ is a separate national scope. It is not rendered as a SQN and not as 7WG.

## 3. UUID safety

The client must not assume a backend identifier is a short SQN code. `getCurrentUnitInfo()`
never throws and returns a safe fallback object (name, short, addr, day, start, end, sess)
derived from the session when no local SQN record exists. All legacy `SQN_DATA[S.sqn]` reads
were removed or routed through this helper.

Helper functions (UI gating only): `getScopeType`, `getCurrentUnitInfo`, `canRead`,
`canWriteSquadron`, `canWriteWing`, `canWriteNational`, `isReadOnly`, `isProxyActive`,
`isInterventionActive`, `isProxyRequired`, `isInterventionRequired`.

## 4. SQN users

4.1 SQN users see their own SQN only: dashboard, calendar, parade nights, sessions, weekly
program, curriculum coverage, facilitators, resources, action items, reports.

4.2 SQN general users are read-mostly. SQN admin may create or update local SQN records only
where the backend permits.

4.3 SQN users do not see other SQN data, Wing controls, or NAT HQ controls.

## 5. Wing users

5.1 Wing users see all SQNs in their Wing through a visual Wing dashboard and comparison table.

5.2 Wing users drill into SQN data for oversight, assurance, support and comparison.

5.3 Wing users do not edit SQN data directly. A Wing admin write into a SQN requires Proxy Mode
with a reason. Proxy Mode shows a banner and provides an Exit action.

5.4 Wing viewer is Read Only.

## 6. NAT HQ users

6.1 NAT HQ users see all Wings and all SQNs: NAT HQ dashboard, Wing comparison, SQN comparison,
readiness summary, curriculum assurance, not-delivered summary, needs-action summary, audit
where the backend permits.

6.2 Drill path: NAT HQ to Wing to SQN.

6.3 NAT HQ users do not edit Wing or SQN data unless Delegated Intervention Mode is active and
the backend permits the write. Delegated Intervention Mode requires a reason and shows a banner.

6.4 NAT HQ viewer is Read Only. NAT HQ admin and system admin perform privileged functions only
where the backend permits.

## 7. Auditor

7.1 Auditor is Read Only. No add, edit, delete, publish, close, status change, proxy,
intervention or administration controls are shown.

7.2 Audit views are visible where the backend permits.

## 8. Proxy Mode and Delegated Intervention Mode

8.1 Backend behaviour confirmed by test: a Wing write without proxy returns 403 proxy_required;
a NAT HQ write without intervention returns 403.

8.2 Enter: `POST /api/proxy/enter/{squadron_id}` with a reason returns
`{ proxy: { mode, acting_squadron_id, proxy_session_id } }`. Current state:
`GET /api/proxy/current` returns `{ active, mode, acting_squadron_id }`. Exit:
`POST /api/proxy/exit`.

8.3 The client loads proxy state on every data refresh and drives the mode banner and write
gating from it.

## 9. Write controls

9.1 Controls are hidden or disabled unless the backend role and scope allow the write.

9.2 Wired writes: session status (incl. not-delivered with reason), create parade night, add
facilitator, proxy/intervention enter and exit.

9.3 The backend remains the authority. Test confirmed: auditor write 403; SQN admin write 200;
Wing write without proxy 403.

## 10. Limitation — access code handling (stated plainly)

10.1 Tasking line 9.2 ("Wing viewer must be able to access all the SQN access code and change
it") is NOT implemented, by deliberate decision.

10.2 Reason: access codes must never be exposed in frontend code or to a Read Only role, and
viewers are Read Only. Surfacing or editing access codes in the browser would breach the
Backend Source of Truth and Read Only principles in this same document.

10.3 Correct mechanism: access code rotation is a backend or administrator function
(`POST /api/auth/change-code` and the backend `rotate_access_codes.py` utility), performed
server-side by an authorised account. This item is referred for confirmation before any client
exposure of codes is considered.

---

## 11. v2 — operating-level navigation

11.1 SQN, Wing and NAT HQ are different operating levels. Wing and NAT HQ do not use SQN delivery
navigation by default.

11.2 Default Wing navigation: Wing Dashboard, Curriculum Coverage, Training Balance, Risk and
Bottlenecks, Reports, Audit, Proxy Mode.

11.3 Default NAT HQ navigation: NAT HQ Dashboard, Curriculum Coverage, Training Balance, Risk and
Bottlenecks, Reports, Audit, Delegated Intervention Mode.

11.4 Auditor navigation: Reports and Audit only. No write controls.

## 12. v2 — Proxy Mode and Delegated Intervention as exact SQN view

12.1 When Proxy Mode (Wing) or Delegated Intervention (NAT HQ) is active, the UI shows the exact
SQN workspace for the acting squadron: dashboard, calendar, parade nights, weekly program,
curriculum, facilitators, resources and reports.

12.2 The backend returns the acting squadron's data while proxy is active (verified: Wing parade
nights 0 normally, 4 when acting on 703).

12.3 A banner shows "Proxy Mode — Wing viewing [SQN]" (or "Delegated Intervention Mode — NAT HQ
viewing [unit]"), the reason, and Exit. Wing/NAT dashboards are hidden until the user exits.

## 13. v2 — subject areas

13.1 Six subject areas are derived from the backend `element` field: Service Knowledge,
Drill/Discipline, Field/Survival, Leadership/Teamwork, Community/SFA, STEM/Air and Space. They are
shown as coloured chips and drive the Training Balance view.

## 14. v2 — access code change

14.1 A user may change their own sign-in code from Settings: new plus confirm, server-hashed,
success or failure only. Existing codes are never shown. Verified end-to-end (old code rejected
after change).

14.2 Scoped reset of another unit's code is an audited backend/administrator function and is not
exposed in this client (no client endpoint wired).

---

## 15. v3 — facilitator subject-area tags and capability data

15.1 Facilitators carry subject-area tags (backend `subject_areas`). The six reporting categories
are Service Knowledge, Drill/Discipline, Field/Survival, Leadership/Teamwork, Community/SFA, and
STEM/Air and Space; the facilitator tag vocabulary (Service Knowledge, Drill and Ceremonial, Field
Skills, PDL, Community Engagement, Air & Space, Aviation, Space, Cyber, RPAS) maps onto these.

15.2 Tag write authority is backend-enforced via `PATCH /api/facilitators/{id}` with the standard
squadron write check; changes are audited. The connected client exposes own-squadron tagging to
SQN admins (and to Wing/NAT HQ via Proxy/Intervention where the backend permits). Wing- and
national-scope tag ownership across units is not exposed in this client build.

15.3 Wing and national capability/balance views read `GET /api/reports/wing-capability` and
`GET /api/reports/national-capability`. These are read-only roll-ups; access codes are never
included.

---

## 16. v6 — Account Management, Access-Code Administration and Flight Assignment

### 16.1 Account hierarchy and scope

Accounts belong to one scope tier: National, Wing, or Squadron. Scope is derived from the account
role; it is not stored separately. A Flight is a local squadron display grouping only. Flight
assignment does NOT create separate tenancy, does NOT change permissions, and does NOT change the
account's scope tier.

| Role | Scope tier |
|---|---|
| system_admin, national_admin, national_viewer, auditor | National |
| wing_admin, wing_viewer | Wing |
| sqn_admin, sqn_general | Squadron |

### 16.2 Account creation authority

| Creator role | May create roles |
|---|---|
| system_admin | All 8 roles |
| national_admin | All except system_admin |
| wing_admin | wing_viewer, sqn_admin, sqn_general (own Wing only) |
| sqn_admin | sqn_general (own Squadron only) |
| All viewers, sqn_general, auditor | Cannot create accounts |

Wing admin scope enforcement: may only create accounts for their own Wing (wing-scope accounts) or
for Squadrons within their Wing (sqn-scope accounts). Backend returns 403 out_of_scope otherwise.

SQN admin scope enforcement: may only create sqn_general accounts for their own Squadron. Backend
returns 403 out_of_scope otherwise.

### 16.3 Access-code security invariants

- Access-code hashes are **never returned** by any API endpoint.
- Existing plaintext codes are **never returned** by any API endpoint.
- A new plaintext code is returned **exactly once**: in the create or reset-code response.
  It is not retrievable after that point.
- Codes are stored as PBKDF2-SHA256 hashes (passlib) only.
- Codes are **never stored in frontend JavaScript, localStorage, or sessionStorage**.
- The `new_code_notice` field accompanies every one-time code: "This code will not be shown again. Copy it now."

UI wording requirements (enforced in frontend):
- Use: "Generate new access code", "Reset access code", "Set new access code", "Last changed", "Changed by", "Active / Disabled", "New code shown once"
- Must not use: "View current code", "Show access code", "Reveal code", "Display existing code"

### 16.4 Flight rules

- A Flight is a local Squadron grouping only (display / reporting).
- Flight assignment requires the user to be squadron-scoped.
- Flight must belong to the same Squadron as the account being created or updated.
- Assigning a Flight does not grant any additional scope or permissions.
- Archiving a Flight clears `flight_id` from all users assigned to it before soft-deleting.
- There are no standalone Flight accounts and no Flight tenancy.

### 16.5 API endpoints (v6)

```
GET    /api/accounts                        — list accounts (scoped to actor's authority)
POST   /api/accounts                        — create account; returns new_code once only
GET    /api/accounts/{id}                   — single account detail (no code_hash, no plaintext)
PATCH  /api/accounts/{id}                   — update display_name / flight_id
POST   /api/accounts/{id}/reset-code        — generate or set new code; returned once only
POST   /api/accounts/{id}/disable           — deactivate; code also deactivated immediately
POST   /api/accounts/{id}/reactivate        — reactivate user

GET    /api/flights                         — list flights (scoped)
POST   /api/flights                         — create flight (sqn_admin / wing_admin / nat_admin)
PATCH  /api/flights/{fid}                   — rename / toggle active
POST   /api/flights/{fid}/archive           — soft-delete; clears flight_id from users first
```

All account and flight mutations are recorded in the audit log with the actor's user_id, role,
action, and affected object.
