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

## §2 — Create Wing Structure

All steps below use the target environment URL. Replace `<url>` with the staging
or production backend Railway URL as appropriate.

### Step 2.0 — Recommended: One-call Wing Provisioning (staging and production)

The `POST /api/system/provision-wing` endpoint creates a Wing, its Squadrons, and
initial accounts in a single idempotent call. This is the recommended path for both
staging validation and production activation — it does not require SSH, CLI access,
or a separate bootstrap step, and works in any environment.

```bash
TOKEN="<system-admin-bearer-token>"
curl -X POST "<url>/api/system/provision-wing" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "wing_code": "1WG",
    "wing_name": "1 Wing HQ",
    "wing_short": "1WG",
    "squadrons": [
      {
        "code": "101",
        "name": "101 Squadron AAFC",
        "short_name": "101 SQN",
        "parade_day": "Wednesday",
        "start_time": "18:00",
        "end_time": "21:30"
      },
      {
        "code": "102",
        "name": "102 Squadron AAFC",
        "short_name": "102 SQN",
        "parade_day": "Thursday",
        "start_time": "18:00",
        "end_time": "21:30"
      }
    ],
    "create_accounts": true
  }'
```

**Important:** The response includes generated access codes for `wing_admin`,
`sqn_admin`, and `sqn_general` per squadron.
**Record these codes immediately — they are shown once and not retrievable.**

The endpoint is idempotent: calling it again with the same Wing and Squadron codes
returns the existing records without creating duplicates or revealing codes again.
If you need to issue new codes, use Account Management → Reset Code instead.

Expected response shape:
```json
{
  "wing": {"id": "...", "code": "1WG", "name": "1 Wing HQ"},
  "results": [
    {"type": "wing", "code": "1WG", "created": true},
    {"type": "squadron", "code": "101", "created": true},
    {"type": "account", "code": "101", "role": "wing_admin", "created": true},
    ...
  ],
  "accounts_created": [
    {"role": "wing_admin", "display_name": "1WG Wing Admin", "new_code": "..."},
    {"role": "sqn_admin", "display_name": "101 SQN Admin", "new_code": "..."},
    ...
  ],
  "notice": "Codes shown here will NOT be retrievable again. Record each code now."
}
```

To provision without creating accounts (when accounts already exist or will be
created separately): set `"create_accounts": false`.

> **Alternative: Manual steps (Steps 2.1–2.3 below)**
> Use the manual steps only if you need to create a Wing with no initial squadrons,
> or if you need finer control over each operation. The provision-wing endpoint
> covers the common onboarding case.

---

### Step 2.1 — Create the Wing (manual alternative)

Via System Console (UI):
1. Log into staging frontend as system_admin.
2. System Console → Scope Map → **Create Wing**.
3. Enter: Wing Code (e.g. `1WG`), Wing Name (e.g. `1 Wing HQ`), short name.
4. Click Create.

Via API (curl):
```bash
TOKEN="<system-admin-bearer-token>"
curl -X POST "<url>/api/system/create-wing" \
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

### Step 2.2 — Create Squadrons (manual alternative)

For each squadron in the new Wing, via System Console → Scope Map → Create Squadron.

Or via API:
```bash
curl -X POST "<url>/api/system/create-squadron" \
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

### Step 2.3 — Bootstrap initial accounts (staging only — manual alternative)

Use the generic bootstrap endpoint to create initial accounts for the new Wing.
This endpoint is rejected in production — use `provision-wing` (Step 2.0) for
production account creation.

```bash
curl -X POST "<url>/api/system/bootstrap-staging" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"wing_code": "1WG", "sqn_code": "101"}'
```

Expected response includes generated access codes for `wing_admin` and `sqn_admin`.
**Record these codes immediately — they are shown once and not retrievable.**

### Step 2.4 — Run the second-wing synthetic seed (Staging only)

For a more complete staging pilot with two squadrons and multiple role accounts:

**Step 2.4a — Dry-run preview (recommended first)**

```bash
cd backend
source .venv/bin/activate
ENVIRONMENT=staging DATABASE_URL=<staging-db-url> \
  WING2_CODE=1WG WING2_NAME="1 Wing HQ" \
  SQN2A_CODE=101 SQN2A_NAME="101 Squadron AAFC" \
  SQN2B_CODE=102 SQN2B_NAME="102 Squadron AAFC" \
  DRY_RUN=1 \
  python -m app.seeds.second_wing_seed
```

The dry-run prints what would be created (Wing, squadrons, accounts, planning year, holidays)
without writing anything to the database. Verify the planned output before continuing.

**Step 2.4b — Actual creation**

Remove `DRY_RUN=1` and re-run the same command. The script is idempotent — if the Wing or
squadrons already exist, it skips creation and only adds missing records:

```bash
ENVIRONMENT=staging DATABASE_URL=<staging-db-url> \
  WING2_CODE=1WG WING2_NAME="1 Wing HQ" \
  SQN2A_CODE=101 SQN2A_NAME="101 Squadron AAFC" \
  SQN2B_CODE=102 SQN2B_NAME="102 Squadron AAFC" \
  python -m app.seeds.second_wing_seed
```

The script prints a structured JSON onboarding report on completion, including generated
access codes. **Record the access codes immediately — they are shown once and not retrievable.**

Additional env vars (all optional):
- `WING2_SHORT` — wing short name (default: `WING2_CODE`)
- `SQN2A_PARADE_DAY` / `SQN2B_PARADE_DAY` — `monday`…`sunday` (default: `wednesday` / `thursday`)
- `SQN2A_START_TIME` / `SQN2B_START_TIME` — parade start time HH:MM (default: `18:00`)
- `SQN2A_END_TIME` / `SQN2B_END_TIME` — parade end time HH:MM (default: `21:30`)
- `PLANNING_YEAR` — training year start (YYYY, default: current year)

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

After §2 (provision-wing or manual steps) and §3, the audit log must contain entries for:
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

Production activation uses `POST /api/system/provision-wing` (Step 2.0) against the
production backend URL. The bootstrap-staging endpoint is rejected in production.

Production activation checklist:

1. Take a DR backup of production before starting.
2. Run `POST /api/system/provision-wing` against the production backend with the Wing's
   final codes, names, and squadrons. Record all generated access codes immediately.
3. Confirm the response shows `"created": true` for wing and each squadron.
4. Provide wing_admin code to the incoming Wing Admin — see §6 for the full package.
5. Wing Admin resets their code on first login (Settings → Access Codes → Generate New Code).
6. National Admin confirms tenancy isolation in production using checks from §4.
7. Wing Admin completes §3.4 (squadron initialisation) for real: create planning year,
   generate parade dates, add holidays.
8. National Admin signs off production activation in the governance record.

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

## §7 — Wing Rollback Procedure

Rollback is required if staging onboarding fails acceptance criteria (§4) or if a
production activation must be reversed.

**Important constraint:** Audit log records are immutable. Wing, Squadron, and Account
records that triggered audit entries cannot be deleted — only deactivated.
The rollback procedure below archives records; it does not purge them.

---

### 7.1 When to use rollback

Use rollback when:
- §4 acceptance criteria fail and the Wing data cannot be salvaged
- An incorrect Wing code was used and cannot be corrected in place
- A production activation is reversed by governance authority

Do NOT use rollback to address a configuration error (wrong parade day, wrong Squadron
name) — those are editable in place via System Console. Rollback is for structural
failures only.

---

### 7.2 Staging rollback — full reset

For staging, the cleanest rollback is to restore from the pre-onboarding staging DB
backup (or re-run the base staging seed). Only do this if NO existing 7WG data has
been entered since the new Wing was created — otherwise treat staging rollback the
same as production rollback (§7.3).

```bash
# Option A — re-bootstrap staging from scratch (loses all staging data)
curl -X POST "<staging-url>/api/system/bootstrap-staging" \
  -H "Authorization: Bearer $SYSADMIN_TOKEN" \
  -H "Content-Type: application/json"

# Option B — archive the Wing only (preserves existing staging data)
# Proceed to §7.3 steps using the staging URL
```

---

### 7.3 Production (and surgical staging) rollback

Step-by-step via System Console or API:

**Step 7.3.1 — Block Wing access immediately**

Disable all accounts for the Wing being rolled back:

1. System Console → Account Management → filter by Wing Code → **Archive** each account.
2. This invalidates their JWTs via `token_version` increment on next login attempt.
   Active sessions will expire within the JWT lifetime (default 8 hours).

**Step 7.3.2 — Archive all Squadrons under the Wing**

1. System Console → Scope Map → find the Wing → expand squadrons.
2. Archive each squadron.

Via API (repeat for each squadron ID):
```bash
curl -X PATCH "<url>/api/system/squadron/<sqn-id>/archive" \
  -H "Authorization: Bearer $SYSADMIN_TOKEN"
```

**Step 7.3.3 — Archive the Wing**

1. System Console → Scope Map → find the Wing → **Archive Wing**.
2. The Wing remains in the database but `active_status = false`; it is invisible to
   all operational endpoints.

Via API:
```bash
curl -X PATCH "<url>/api/system/wing/<wing-id>/archive" \
  -H "Authorization: Bearer $SYSADMIN_TOKEN"
```

**Step 7.3.4 — Verify rollback**

```bash
# Confirm Wing is no longer in scope-map
curl "<url>/api/system/scope-map" -H "Authorization: Bearer $SYSADMIN_TOKEN" \
  | python3 -m json.tool | grep -i "<wing-code>"
# Must return no matches.

# Confirm no active accounts for the Wing
curl "<url>/api/system/accounts?wing_code=<wing-code>" \
  -H "Authorization: Bearer $SYSADMIN_TOKEN"
# Must return empty list or 404.
```

**Step 7.3.5 — Record audit entry**

Rollback must be recorded in the program's decision log and in the support runbook
incident record. Include:

| Field | Value |
|---|---|
| Date | — |
| Reason for rollback | — |
| Wing code affected | — |
| Steps taken | §7.3.1–7.3.4 |
| Data impact | Records archived; audit log entries preserved |
| Authorised by | — |

---

### 7.4 Re-onboarding after rollback

If the Wing is re-onboarded with the same Wing code, the idempotent
`POST /api/system/provision-wing` endpoint checks for an existing Wing by code regardless
of `active_status`. If the Wing is archived, the endpoint returns it as existing (not
created) and does not create accounts. Restore the Wing first via System Console →
Scope Map → Restore Wing, then call provision-wing again with `"create_accounts": true`.

For `second_wing_seed.py` (CLI alternative): it queries `active_status=true` only, so
it will fail to find the archived Wing and attempt to create a new one with the same code,
which will fail on a UNIQUE constraint.

**Resolution for re-onboarding with the same Wing code:**
1. System Admin permanently deletes the archived Wing record (only permissible because
   the Wing was never used in production and has no operational data).
2. OR use a new Wing code and update all references.

If the Wing had operational data (parade nights, planning records), permanent deletion
is NOT permitted. The Wing must use a new code, or the archived record must be
restored to active.

---

## §8 — Troubleshooting Common Onboarding Issues

| Symptom | Likely cause | Resolution |
|---|---|---|
| `provision-wing` returns 403 | Token is not for a system_admin account | Re-authenticate as system_admin |
| `provision-wing` returns existing Wing but `created: false` | Wing with that code already exists (possibly archived) | Restore Wing via System Console → Scope Map first, then re-call with `create_accounts: true` |
| Bootstrap endpoint returns 409 on Wing creation | Wing code already exists | Check scope-map; use a different code or archive the existing Wing first |
| Wing Admin cannot see their squadrons | Account `wing_id` FK not set correctly | Check Account Management → verify `wing_id` matches the new Wing |
| 1WG wing_admin can see 7WG data | RBAC query missing wing_id filter | Raise as a bug — do not proceed to production |
| `second_wing_seed.py` exits: "No NationalEntity found" | DB not migrated | `alembic upgrade head` then re-run |
| `second_wing_seed.py` `crest_url column` error | DB schema is behind migrations | `alembic upgrade head` from the `backend/` directory |

---

## Revision History

| Date | Change | Author |
|---|---|---|
| 2026-07-17 | Initial version (Phase 10) | Next-Stage Program |
| 2026-08-12 | §2.4 updated for dry-run mode; §7 rollback procedure added; §8 troubleshooting added | Next-Stage Program |
| 2026-08-13 | §2.0 added: `POST /api/system/provision-wing` one-call endpoint (replaces separate create-wing/create-squadron/bootstrap-staging calls for both staging and production); §5 updated to use provision-wing for production; §7.4 and §8 updated to reflect new endpoint's idempotency behaviour | Next-Stage Program |
