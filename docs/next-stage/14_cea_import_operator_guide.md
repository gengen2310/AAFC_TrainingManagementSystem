# CEA Import — Operator Guide

**Audience:** Wing Administrators, System Administrators  
**TMS component:** Planning Workspace → Import CEA  
**Updated:** 2026-08-13

---

## What is a CEA activity?

CEA (Cadet Enterprise Application) is the national cadet activity management system maintained by National Headquarters. It records approved external activities that squadrons can nominate cadets to attend — camps, courses, competitions, exchanges, and similar events.

TMS does not replace CEA. It imports a snapshot of approved activities so that Wing and Squadron administrators can see upcoming events alongside their local training schedule, assign relevant activities to training nights, and plan cadet participation.

---

## Why import CEA activities into TMS?

Importing CEA data lets you:

- See national and Wing activities on the same planning calendar as local Parade Nights
- Link a CEA activity to a Session so it appears in the curriculum record and Mission Backlog
- Classify each activity as relevant or not relevant to your Wing's squadrons
- Flag activities that affect specific Training Classes (for example, a camp that takes Senior 2 cadets out for a weekend)

---

## How the import works

### Step 1 — Export from CEA

Log in to CEA and export the current activity list for your Wing as a CSV file. The export function is normally under **Reports → Activity Report**. Save the file in UTF-8 format.

The import accepts two column-name conventions:

| TMS field | CEA column (v1) | CEA column (v2 / legacy) |
|---|---|---|
| Activity ID | `ActivityID` | `SeqNr` |
| Activity name | `ActivityName` | `Name` |
| Start date | `StartDate` | `ActivityStartDate` |
| End date | `EndDate` | `ActivityEndDate` |
| Host unit | `HostUnit` | `OwnerUnit` |
| Parent unit | `ParentUnit` | `Region` |
| Location | `Location` | `Venue` |
| Status | `Status` | `StatusName` |
| Activity type | `ActivityType` | `Type` |

If your export uses different column names, contact your System Administrator.

### Step 2 — Import in Planning Workspace

1. Open Planning Workspace and select the correct Planning Year.
2. Go to **CEA Activities** → **Import CEA CSV**.
3. Upload your exported CSV file.
4. Review the preview — each row is classified as one of:
   - **Create** — new activity not already in TMS
   - **Update** — activity already imported; this import contains newer data
   - **Duplicate** — same name and date already exists; the earlier record is kept
   - **Skipped** — row has no activity name; ignored
5. Confirm to complete the import.

### What the import records

Each import run creates a **CEA Import Batch** record (visible to System Administrators in the audit log). The batch records:

- The source filename
- Who ran the import and when
- How many rows were created, updated, duplicated, skipped, or rejected due to errors

Activities removed from CEA since the previous import are flagged `removed_from_cea = true` but not deleted. This preserves the planning record if a session was already linked to the activity.

---

## Classifying imported activities

After import, each activity has the status **Needs Review**. Wing Admins must classify each activity before it becomes active in squadron planning views.

**To classify an activity:**

1. Go to **CEA Activities** in Planning Workspace.
2. Select an activity marked **Needs Review**.
3. Set:
   - **Importance** — High, Medium, or Low
   - **Audience flags** — which groups may attend (Staff, Seniors, Proficient, First Year)
4. Save. The activity status changes to **Classified**.

Only classified activities appear as overlay events in the planning calendar and in Squadron-level views.

**Who can classify:** Wing Admins and above. Squadron Admins see classified activities but cannot change the classification.

---

## How CEA activities relate to Training Classes

CEA activities do not automatically link to Training Classes. The link is made when a **Session** references the CEA activity.

The path is:

```
CeaActivity
    ↓ (linked via session.cea_activity_id)
Session
    ↓ (linked via SessionAudience)
TrainingClass
```

**To link a CEA activity to a Training Class:**

1. In Planning Workspace, open the Parade Night where the activity will be acknowledged.
2. Create or edit a Session.
3. Set the **Activity** field to the CEA activity.
4. In the **Audience** section, select the Training Class (or classes) that will be affected.

The Session now appears in the Mission Backlog for each linked Training Class with the activity as context.

**Example:** Camp Jungwirth is a Senior camp. Import it from CEA, classify it as High importance / Seniors audience. On the Parade Night before the camp, create a Session referencing Camp Jungwirth and add Senior 1 and Senior 2 as audience. Senior 3 through 5 are not attending, so leave them out. The Mission Backlog will show the activity under Senior 1 and Senior 2 only.

---

## What appears in Squadron views

Once an activity is classified, it appears in:

- **Planning calendar** — as an overlay event on the relevant dates
- **Needs Attention** — if the activity is high importance and within 30 days without a corresponding Session
- **What Changed** — when classification status changes (visible to Wing/National roles)

Activities classified as **Staff Only** are visible to administrators but not in cadet-facing or parent-facing outputs.

---

## Repeated imports

You can import an updated CEA CSV as many times as needed throughout the year. Each import:

- Updates existing activities if the CEA Activity ID matches
- Marks removed activities with a flag (does not delete)
- Does not duplicate activities with the same name and start date

Re-importing after a CEA update is recommended before the start of each Term.

---

## Troubleshooting

| Problem | Cause | Resolution |
|---|---|---|
| "File too large" error | CSV exceeds the upload limit (default 10 MB) | Split the export into smaller date ranges |
| Activities not appearing in Squadron views | Activity not yet classified | Wing Admin classifies the activity in CEA Activities |
| Duplicate activities appearing | Multiple imports with different column formats | System Admin merges duplicates via the admin console |
| Activity dates wrong | CEA exported in a different date format | Verify the export settings; TMS expects ISO 8601 (YYYY-MM-DD) |
| Import shows 0 rows created, 100% skipped | CSV has no activity name column recognised | Check column names match the table above; contact System Admin if unsure |

---

## Role summary

| Role | Can import CSV | Can classify | Can create Sessions linking CEA | Can see classified activities |
|---|---|---|---|---|
| System Admin | Yes | Yes | Yes | Yes |
| National Admin | Yes | Yes | Yes | Yes |
| Wing Admin | Yes | Yes | Yes | Yes |
| Squadron Admin | No | No | Yes (for their squadron) | Yes |
| Squadron Viewer | No | No | No | Yes |
