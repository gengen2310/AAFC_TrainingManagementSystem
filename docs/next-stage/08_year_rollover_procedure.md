# AAFC TMS — Year Rollover Procedure

**Audience:** Squadron Administrators, Wing Administrators
**Last updated:** 2026-08-12

---

## Timing Recommendation

Run the rollover **4–6 weeks before the first parade night of the new training year** (typically
late July or early August for a September start). Running early is safe — the old year remains
fully active and accessible until you deactivate it.

---

## 1. Pre-Rollover Checklist

Complete these checks in the **source year** before triggering the rollover.

| # | Check | How to verify |
|---|---|---|
| 1 | All parade nights are at `Published` or `Closed` status | Activities page → Parade Nights — no nights in `Draft` |
| 2 | All sessions have a final status (`delivered`, `not_delivered`, or `cancelled`) | Planning Workspace → Year view — no sessions in `planned` |
| 3 | Holidays and term dates are accurate in the source year | Planning Workspace → Left panel → Holidays |
| 4 | Parade dates are complete and correct for the source year | Planning Workspace → Year view → date list |
| 5 | No planning year already exists for the target year | Planning Workspace → year selector — target year must not appear |
| 6 | Database backup is current | GitHub Actions → `backup-postgresql.yml` — last run successful |

**Note on incomplete sessions:** If step 2 finds sessions still in `planned` status, they will be
flagged in the rollover response (`incomplete_sessions_noted`). The rollover will still proceed —
these sessions are noted for your review, not blocked.

---

## 2. Performing the Rollover

### Option A — Planning Workspace (recommended for squadron and wing admins)

1. Open the Planning Workspace (`/planning`).
2. Click the **Settings / Configuration** area (gear icon or year selector menu).
3. Select **Guided Year Setup** (or "New Planning Year").
4. Choose **"Roll over from \<current year\>"**.
5. Confirm the options shown (copy holidays, carry incomplete session notes, copy training classes).
6. Click **Create** — the modal calls the rollover API and returns a summary on success.
7. The new planning year opens automatically.

### Option B — API (for system admins or scripted deployments)

Replace `<YEAR_ID>` with the `planning_year_id` of the source year and `<TOKEN>` with a valid
bearer token for a `sqn_admin` or `wing_admin` account.

```bash
curl -X POST "https://<backend-host>/api/planning/years/<YEAR_ID>/rollover" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "copy_holidays": true,
    "carry_incomplete_sessions": true,
    "copy_training_classes": true
  }'
```

**Successful response:**

```json
{
  "ok": true,
  "new_planning_year_id": "...",
  "year": 2027,
  "name": "2026 Training Year → 2027",
  "holidays_copied": 8,
  "parade_dates_copied": 30,
  "incomplete_sessions_noted": 3,
  "training_classes_copied": 5
}
```

#### Rollover parameters

| Parameter | Default | Description |
|---|---|---|
| `target_year` | source + 1 | Override the target year number. Must not already exist for this unit. |
| `name` | `"<source> → <target>"` | Override the name of the new planning year. |
| `copy_holidays` | `true` | Copy all holiday periods, date-shifted one year forward. |
| `carry_incomplete_sessions` | `true` | Count and note sessions in `planned`/`not_delivered` status. Sessions are noted only — not auto-assigned to the new year. |
| `copy_training_classes` | `true` | Copy active Training Class definitions (not session data) to the new year. |

---

## 3. Post-Rollover Checklist

| # | Task | Where |
|---|---|---|
| 1 | Verify all expected parade dates appear in the new year, shifted one year | Planning Workspace → Year view |
| 2 | Check for any parade dates that overlap new-year holidays | Planning Workspace → holiday overlap indicator |
| 3 | Confirm each new parade date has a corresponding Parade Night record | Activities page → Parade Nights |
| 4 | Review and adjust holiday periods for accuracy (federal/provincial dates shift year-to-year) | Planning Workspace → Holidays |
| 5 | Enter anchor events for the new year (these are NOT carried over) | Planning Workspace → Anchor Events |
| 6 | Review `incomplete_sessions_noted` count; re-schedule those sessions if required | Planning Workspace → session builder |
| 7 | Verify training classes are correct for the new year; update as needed | Planning Workspace → Training Classes |
| 8 | Deactivate the source year when you are confident the new year is correct | API `PATCH /api/planning/years/<id>` → `{"active_status": false}` |

---

## 4. What Is NOT Carried Over

| Item | Reason |
|---|---|
| **Anchor events** | Year-specific; must be re-entered each year |
| **Session curriculum assignments** | Planners choose what to teach each parade night in the new year |
| **Session delivery data** | Historical only; belongs to the source year's record |
| **Cadet attendance records** | Tied to specific sessions in the source year |
| **Wing calendar events** | Wing admins re-enter wing-level events for the new year |
| **Incomplete session → new year auto-assignment** | Advisory only; planner decides what carries forward |

---

## 5. Data Integrity Notes

- The rollover is **non-destructive**. The source year and all its data remain fully readable and
  accessible after rollover.
- The source year is not archived or deactivated automatically — that is a manual step (checklist
  item 8 above) you take only after reviewing the new year.
- Parade dates are advanced by exactly one calendar year. A date of `2026-09-05` becomes
  `2027-09-05`. The same-weekday approximation is accurate for most years; verify and adjust the
  few dates that fall on different weeks due to calendar shift.
- Each copied parade date automatically creates a new `ParadeNight` record linked via
  `parade_night_id`. No manual linking is required.

---

## 6. Troubleshooting

**409 — planning year already exists**
A planning year for the target year already exists for this unit. Do not re-run the rollover.
Find the existing year in the Planning Workspace year selector and edit it directly.

**Missing parade nights after rollover**
Check the Activities page → Parade Nights and filter by the new year. If dates appear in the
Planning Workspace but not as Parade Nights, the `ParadeNight` creation step may have partially
failed. Raise a support request with the `new_planning_year_id` and the affected dates.

**Leap-year date handling (Feb 29)**
If the source year contains a Feb 29 date (leap year), the backend shifts it to Feb 28 in the
target year when the target is not a leap year. Review the February dates after rollover.

**403 — permission denied**
The API token belongs to a `sqn_general` or other role that cannot trigger a rollover.
Log in as `sqn_admin` or `wing_admin`.

**Wing admin rolling over multiple squadrons**
Roll over each squadron's planning year individually. There is no bulk Wing-level rollover.

---

## Support

If the rollover produces unexpected results, raise a support request with:
- The source `planning_year_id`
- The full API response body (or the Planning Workspace error message)
- The target year number and your unit's Wing/Squadron IDs
