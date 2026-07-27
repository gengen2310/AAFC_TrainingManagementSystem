# AAFC TMS — Wing Onboarding Runbook

Phase 10 — Next-Stage Development Program.
Written 2026-07-17. Audience: National Admin, System Admin, incoming Wing Admin.

This document defines the complete procedure for onboarding a new Wing into the AAFC TMS.
It covers staging validation (which can be done any time) and production activation
(which requires explicit governance approval — see §0).

**Rule 8 of the non-negotiable rules:**
> Do not activate other Wings in production.

Production activation of a new Wing requires explicit organisational approval and is a
**HARD STOP** in this program. This runbook is the procedure to follow once that approval
is granted. Nothing in this document authorises activating a Wing in production.

---

## §0 — Governance Gate (HARD STOP before production)

Before activating any Wing in production, confirm:

| Gate | Required approver | Status |
|---|---|---|
| Wing Commander or SOCAD has accepted TMS responsibility | Wing Commander / SOCAD | _pending_ |
| Wing data governance decisions made (9 items from Gap #23) | AAFC Governance Authority | _pending_ |
| Wing Admin named and access code issued | National Admin | _pending_ |
| Wing operational profile entered (parade night day, time, term dates) | Wing Admin | _pending_ |
| Squadron list and squadron admin accounts prepared | Wing Admin | _pending_ |
| Backup plan confirmed for new Wing's data | System Admin | _pending_ |
| Staging pilot completed (this document §1–§4) | System Admin | _pending_ |
| Production deployment window approved | AAFC IT / National Admin | _pending_ |

Until all gates are checked, stop here. This runbook's §1–§4 are for staging only.

---

## §1 — Pre-Onboarding Checklist

Confirm before starting:

| Check | How to verify |
|---|---|
| Staging environment is current | `/api/health/ready` on staging URL returns `{"status":"ready"}` |
| Latest next-stage branch deployed to staging | Railway staging → last deploy is current |
| National entity exists in staging DB | `GET /api/system/scope-map` returns a national entity |
| No existing Wing with the incoming Wing's code | `GET /api/system/scope-map` — scan Wings list |
| System Admin token available | Log in as system_admin on staging |

---

## §2 — Create Wing Structure (Staging)

All steps below use the staging backend URL. Replace `<staging-url>` with the
staging backend Railway URL.

### Step 2.1 — Create the Wing

Via System Console (UI):
1. Log into staging frontend as system_admin.
2. System Console → Scope Map → **Create Wing**.
3. Enter: Wing Code (e.g. `1WG`), Wing Name (e.g. `1 Wing HQ`), short name.
4. Click Create.

Via API (curl):
```bash
TOKEN="<system-admin-bearer-token>"
curl -X POST "<staging-url>/api/system/create-wing" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "1WG",
    "name": "1 Wing HQ",
    "short_name": "1WG",
    "national_id": "<national-entity-id>"
  }'
```

Expected: `{"ok": true, "wing_id": "..."}`.

### Step 2.2 — Create Squadrons

For each squadron in the new Wing, via System Console → Scope Map → Create Squadron.

Or via API:
```bash
curl -X POST "<staging-url>/api/system/create-squadron" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "wing_id": "<new-wing-id>",
    "code": "101",
    "name": "101 Squadron AAFC",
    "short_name": "101 SQN",
    "unit_type": "standard_squadron"
  }'
```

Repeat for each squadron.

### Step 2.3 — Bootstrap initial accounts (Staging only)

Use the generic bootstrap endpoint to create initial accounts for the new Wing:

```bash
curl -X POST "<staging-url>/api/system/bootstrap-staging" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"wing_code": "1WG", "sqn_code": "101"}'
```

Expected response includes generated access codes for `wing_admin` and `sqn_admin`.
**Record these codes immediately — they are shown once and not retrievable.**

For production, accounts are created via System Console → Account Management, not
the bootstrap endpoint (which is rejected in production).

### Step 2.4 — Run the second-wing synthetic seed (Staging only)

For a more complete staging pilot with two squadrons and multiple role accounts:

```bash
cd backend
source .venv/bin/activate
ENVIRONMENT=staging DATABASE_URL=<staging-db-url> \
  WING2_CODE=1WG WING2_NAME="1 Wing HQ" \
  SQN2A_CODE=101 SQN2A_NAME="101 Squadron AAFC" \
  SQN2B_CODE=102 SQN2B_NAME="102 Squadron AAFC" \
  python -m app.seeds.second_wing_seed
```

---

## §3 — Wing Configuration

After the Wing structure exists, the Wing Admin configures the Wing's operational profile.

### Step 3.1 — Wing Admin first login

1. Provide the wing_admin access code from §2.3 to the incoming Wing Admin.
2. Wing Admin logs in at the staging frontend.
3. Wing Admin resets their access code via Settings → Access Codes → Generate New Code.
4. Wing Admin records the new code securely. The system never shows it again.

### Step 3.2 — Configure Wing Calendar (optional for staging pilot)

Wing Admin or National Admin:
1. Log in as wing_admin.
2. Wing Calendar → add any known annual Wing events (Wing exercises, Wing Training Weekends, etc.).
3. Mark each event with Planning Importance (Must Attend / Key Event / Informational).

### Step 3.3 — Squadron Admin setup

For each squadron:
1. National Admin or Wing Admin creates a sqn_admin account via Account Management.
2. Provide the sqn_admin code to the squadron's Training Officer.
3. Squadron Training Officer logs in, resets the code, and begins setup.

### Step 3.4 — Squadron initialisation

Each squadron's sqn_admin:
1. Planning Workspace → Setup → create a Planning Year for the current training year.
2. Generate parade dates (weekday, start/end dates for each term).
3. Add holidays (federal public + provincial/territorial + local).
4. Verify the parade night count matches the Wing's expected training schedule.

---

## §4 — Staging Pilot Acceptance Criteria

Run the following checks before declaring the staging onboarding complete.

### 4.1 Tenancy isolation

- Log in as `1WG wing_admin` → can see 101 SQN and 102 SQN data.
- Log in as `7WG wing_admin` → cannot see 1WG data, cannot list 1WG squadrons.
- Log in as `101 sqn_admin` → cannot see 102 SQN data.
- Log in as `7WG sqn_admin` → cannot see 1WG data.

Verify via API:
```bash
# As 1WG wing_admin
curl "<staging-url>/api/planning/years" -H "Authorization: Bearer $WING1_TOKEN"
# Must only return planning years for 1WG squadrons.

# As 7WG sqn_admin
curl "<staging-url>/api/planning/years" -H "Authorization: Bearer $7WG_TOKEN"
# Must NOT include any 1WG planning years.
```

### 4.2 Wing Calendar isolation

```bash
# As 1WG wing_admin — creates a 1WG event
curl -X POST "<staging-url>/api/wing-calendar/events" \
  -H "Authorization: Bearer $WING1_TOKEN" \
  -d '{"wing_id":"<1wg-id>","title":"1WG Pilot Test Event","start_date":"2099-01-15","event_type":"wing_exercise"}'

# As 7WG sqn_admin — must NOT see the 1WG event
curl "<staging-url>/api/wing-calendar/events?wing_id=<7wg-id>" \
  -H "Authorization: Bearer $7WG_TOKEN"
```

### 4.3 Report isolation

```bash
# As 1WG wing_admin — reports must only include 1WG squadrons
curl "<staging-url>/api/reports/curriculum-coverage" \
  -H "Authorization: Bearer $WING1_TOKEN"
```

### 4.4 Audit log entries present

After §2.1–3.3, the audit log must contain entries for:
- `squadron.create` for both new squadrons
- `account_created` for wing_admin and sqn_admin accounts

```bash
curl "<staging-url>/api/system/audit-summary?limit=100" \
  -H "Authorization: Bearer $SYSADMIN_TOKEN" | python3 -m json.tool
```

### 4.5 Planning year flows end-to-end

- 101 SQN sqn_admin creates a planning year, generates parade dates, publishes a parade night.
- Verify the parade night appears in the 101 SQN Parade Nights list.
- Verify it does NOT appear in a 7WG squadron's Parade Nights list.

---

## §5 — Production Activation (HARD STOP — governance required)

**Do not proceed with §5 until all §0 gates are signed off.**

Production activation follows the same steps as §2–§3, but:

1. Wing and Squadron are created via System Console in production (not bootstrap-staging).
2. Account codes are issued via Account Management → Generate Code (one-time display, operator records).
3. The new Wing Admin resets their code on first login.
4. The new Wing receives a Wing Onboarding Information Package (see §6).
5. A DR backup of production is taken before activation begins.
6. After activation, the Wing Admin completes §3.4 (squadron initialisation) for real.
7. National Admin confirms tenancy isolation in production using checks from §4.

---

## §6 — Wing Onboarding Information Package (for the incoming Wing)

Provide the following to the incoming Wing Admin before production go-live:

| Document | Location |
|---|---|
| Squadron Admin Guide | `docs/beta/beta_user_guide.md` |
| Planning Workspace Guide | `docs/AAFC_TMS_TRGO_Planning_Module.md` |
| Year Rollover Procedure | `docs/next-stage/08_year_rollover_procedure.md` |
| Access code security rules | `docs/security_model.md` |
| Support contact | `docs/next-stage/25_support_runbook.md` §Part 1 |

The Wing Admin must acknowledge receipt of the onboarding package before production activation.

---

## Revision History

| Date | Change | Author |
|---|---|---|
| 2026-07-17 | Initial version (Phase 10) | Next-Stage Program |
