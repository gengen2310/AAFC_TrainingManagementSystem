# Planning Workspace — User Test Guide (RC1)

## How to Access Planning Workspace

1. Log in to the main AAFC TMS at the usual URL.
2. From the main dashboard navigation, click **Planning Workspace**.
3. You do not need to log in again — your TMS session carries over automatically.
4. Planning Workspace opens in the same tab.
5. To return to the main TMS, click **← Back to TMS** (top-right corner).

---

## What Testers Should Test

You are testing the Planning Workspace as a realistic squadron user. Treat it as you would in a real planning cycle.

Work through these areas in order:

### 1. Open and Navigate

- Confirm the workspace loads without a blank screen.
- Check that your squadron's planning year is shown.
- Try the view buttons: **Year**, **Term**, **8-week**, **2-week**, **Parade Night**, **Custom**.
- Try switching between Calendar and List display.
- Confirm parade dates appear correctly.

### 2. Schedule a Lesson

- Click on a parade night cell in Year or 8-week view.
- In the drawer that opens on the right, assign a curriculum item, period, cadet group, facilitator, and room.
- Watch for the **Saved** indicator — do not click Save; it saves automatically.
- Re-open the same session and confirm your changes persisted.
- Try editing notes on an existing session.

### 3. Activities Tab

- Click **Activities ▲** at the bottom of the screen.
- The Activities tab opens with a unified table.
- Confirm you can see CEA activities, anchor events, and holidays in the same table.
- Try filtering by source (CEA / Anchor / Holiday) and by date range.
- Try importing a CEA CSV file using the **Import CEA** button in the toolbar.
- After import, confirm new activities appear and duplicates are skipped.
- Click **Classify** on a CEA activity and assign an importance and audience.

### 4. Notices

- In the bottom drawer, open the **Notices** tab.
- Check that upcoming notices are listed.

### 5. Facilitators

- Open the **Facilitators** tab.
- View a facilitator's profile and workload.
- Add a leave period.
- Confirm the leave appears.

### 6. Rooms

- Open the **Rooms** tab.
- Confirm your rooms are listed.

---

## How to Report Issues

For each issue found, please record:

1. **What you were doing** — step by step
2. **What you expected to happen**
3. **What actually happened** — exact error message or behaviour
4. **Which view/tab you were in**
5. **Your role** (sqn_admin, sqn_general, etc.)
6. **Approximate time** so logs can be checked

Report to your squadron administrator or system contact.

---

## Known Limitations (RC1)

- **CEA History tab** may show an error. This is a known issue and is being fixed. The main **Activities** tab works normally.
- **Annual-program load time** is approximately 2 seconds — this is normal for the current database size.
- HQ/NATHQ overlays are read-only. You can add a local note or hide them, but cannot edit the source record.
- Custom date range requires both From and To dates to be set before content appears.

---

## CEA Import — Step by Step

1. Open the **Activities** tab (bottom drawer).
2. Click **Import CEA** in the toolbar.
3. Select your CEA export CSV file.
4. Wait for the import to complete (usually a few seconds).
5. A result banner appears: count of new, updated, duplicates, and skipped.
6. The table updates immediately to show the imported activities.
7. Activities with the same Activity ID as an existing record are updated, not duplicated.
8. Activities that were in a previous import but not in the new file are marked **[Not in latest import]**.

---

## Activity Review — Step by Step

1. In the Activities tab, filter by **Needs review** to see unclassified CEA activities.
2. Click **Classify** on any activity.
3. Select an **Importance** level (Must Attend, Key Event, Optional, etc.).
4. Select the **Audience** groups that apply.
5. Click **Save classification**.
6. The activity status changes to **Classified** and becomes visible as an overlay in Year/Term/8-week views.

---

## Lesson Scheduling — Step by Step

1. Open Year, Term, or 8-week view.
2. Click on an empty cell in a parade night block.
3. The scheduling drawer opens on the right.
4. Select or search for a curriculum item.
5. Set the period number, cadet group, facilitator, and room.
6. Add any notes.
7. The session saves automatically within a few seconds.
8. Close the drawer and confirm the cell shows the lesson.

---

## Autosave Behaviour

Planning Workspace saves automatically — there is no Save button for most fields.

- When a change is made, a **Saving…** indicator appears briefly.
- After saving, it shows **Saved**.
- If saving fails (e.g., temporary network issue), it shows **Could not save** with a Retry option.
- If you close the drawer before save completes, the save still continues in the background.
- Do not create a second session for the same period on the same parade night — the system does not currently prevent this.

---

## Permission Expectations

| Role | Can do |
|------|--------|
| sqn_admin | Full access to own squadron planning |
| sqn_general | Read-only (cannot edit sessions, activities, or notices) |
| wing_admin | Manage wing-owned activities and overlays |
| national_admin | Manage national overlays only |

HQ and National activity records are **read-only** for squadron users. You can add a local note or hide them locally, but the source record is unchanged.

---

*RC1 — Testing period. Do not use for live programme planning until GO is issued.*
