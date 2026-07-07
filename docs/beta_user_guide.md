# AAFC TMS — Beta User Guide
**7 Wing Pilot · 2026**  
**Applies to:** Squadron Admins and Squadron General users across 7 Wing (701–723 SQN)

---

## What is TMS?

The Training Management System (TMS) is the AAFC's central platform for planning, recording, and reporting on squadron training nights. It replaces manual spreadsheets and ad-hoc records with a structured, role-controlled system that feeds into Wing and National reporting.

During the beta, 7 Wing squadrons use TMS to:
- Plan and publish parade nights with session-by-session detail
- Track curriculum delivery against AAFC training areas
- Record attendance, facilitators, and training resources
- Generate squadron and Wing readiness reports

---

## Accessing TMS

Open a web browser and go to:

**https://aafc-tms-frontend-production.up.railway.app**

No installation is required. TMS works on desktop and tablet browsers. Chrome and Firefox are recommended.

---

## Logging In

TMS uses a two-step login.

**Step 1 — Identify your unit**

1. Under *Account Type*, select **Squadron**.
2. Under *Wing*, select **7 Wing — Western Australia**.
3. Under *Squadron / Unit*, select your squadron (e.g. 703 Squadron — City of Fremantle).
4. Under *Role*, select your role (**Squadron Admin** or **Squadron General**).
5. Click **Continue**.

If your squadron does not yet have an account, you will see: *"No account has been created for [Squadron] yet. Contact the system administrator to create one."* Contact your Wing Admin to have the account set up.

**Step 2 — Enter your access code**

Enter the access code for your role and click **Sign In**.

- Access codes are provided by your Squadron Admin (for sqn_general) or Wing Admin (for sqn_admin).
- Codes are case-sensitive. Use the exact code as issued — no spaces.
- After 5 incorrect attempts, the account locks for 15 minutes. Contact your Wing Admin if you are locked out.

**Logging out**

Click your name or the logout button in the top navigation bar. You will be returned to the login screen.

> **Important — shared devices:** Your session token expires after 30 minutes of inactivity, but a token captured before logout remains technically valid until it expires. On any shared device (squadron tablet, duty staff computer), always click **Log Out** before leaving the screen. Do not simply close the browser tab.

---

## Roles

Two roles are active during the 7 Wing beta.

### Squadron Admin (`sqn_admin`)

Full read and write access for your own squadron. This role is for the Training Officer or designated staff member responsible for managing the squadron's TMS records.

Can:
- Create, edit, publish, and close parade nights
- Add and manage training sessions
- Record session status (delivered, not delivered, cancelled, etc.)
- Manage facilitators and training resources
- View curriculum and track progress
- Run squadron training reports
- Create `sqn_general` accounts for their squadron
- Reset access codes for their squadron

Cannot:
- Access another squadron's data
- View Wing or National reports

### Squadron General (`sqn_general`)

Read-only access for your squadron. Intended for staff who need visibility into the training programme without edit access.

Can:
- View parade nights and session plans
- View curriculum
- View training reports

Cannot:
- Create or edit any records

---

## Core Features

### Parade Nights

The central object in TMS. Each parade night represents one training night for your squadron.

**Creating a parade night**
1. Go to **Parade Nights** in the navigation.
2. Click **New Parade Night**.
3. Select the date and term. Session count and timing will pre-fill from your squadron's default template.
4. Click **Save**.

**Sessions**
Each parade night has one or more sessions (typically 3). For each session you can set:
- Curriculum item (links to the AAFC Curriculum)
- Facilitator
- Training area
- Cadet group (Alpha, Bravo, whole squadron, etc.)

**Status flow**
A parade night moves through these statuses:

| Status | Meaning |
|--------|---------|
| Draft | Being planned, not visible to general users |
| Planned | Ready for the night |
| Published | Finalised plan distributed to staff |
| Delivered | Night ran as planned |
| Delivered with issue | Night ran with noted problems |
| Not delivered | Night did not proceed |
| Cancelled | Cancelled in advance |

**Publishing**
Publishing locks the plan. You can still make changes after publishing — all edits are audited and require confirmation.

**Closing**
Close a parade night once you have recorded actual outcomes (attendance, delivery status). A night must be closed before it contributes to readiness reports.

### Curriculum

The **Curriculum** view shows all training items available to your squadron, grouped by phase and training area. Each item shows:
- Delivery progress (how many times it has been delivered this year)
- Link to the AAFC Learning Hub resource

Curriculum items are read-only for squadron users — content is managed at Wing and National level.

### Facilitators

Manage the list of staff and instructors who deliver sessions at your squadron. Each facilitator has a name, rank, and optional subject area tags. Facilitator records are used to populate session plans and track facilitator load in reports.

### Training Areas

Record the physical spaces available at your squadron (training rooms, ranges, outdoor areas). These are used in session planning and resource clash detection.

### Reports

The **Reports** section provides:
- **Training Summary** — overall delivery rate and readiness score for your squadron
- **Not Delivered** — sessions that did not proceed, with reasons
- **Curriculum Coverage** — which curriculum items have been delivered and how often

Wing Admins have access to Wing-wide overview reports across all 16 squadrons.

---

## Access Codes and Shared Accounts

TMS uses a **shared access code model**. Each role at your squadron (sqn_admin, sqn_general) has one access code that all staff holding that role use. This is by design for the beta — it keeps setup simple and avoids the need for individual user accounts.

**What this means in practice:**
- All staff using the sqn_admin code appear under the same account in the audit log. If a change needs to be traced to a specific person, you will need to refer to your own records (e.g. who was on duty that night).
- If you suspect your access code has been compromised, the Squadron Admin can reset the sqn_general code. The Wing Admin can reset the sqn_admin code.
- Do not share your access code outside your squadron staff.
- Do not write access codes in publicly visible locations (whiteboards, shared documents with broad access).

---

## Beta Scope and Known Limitations

The beta covers all 16 squadrons in 7 Wing. The following limitations apply during this phase:

| Limitation | Detail |
|------------|--------|
| 7 Wing only | Other wings are not yet active. Wing and National reports reflect 7 Wing data only. |
| Audit log is per-account, not per-person | Changes are attributed to the shared account (sqn_admin / sqn_general), not individual users. This is expected behaviour for the beta. |
| Session token expires after 30 minutes | You will be logged out after 30 minutes of inactivity. Save your work before stepping away. |
| No offline mode | TMS requires an internet connection. |
| Concurrent edits | If two people edit the same parade night at the same time, the last save wins silently. Co-ordinate with your co-admin if multiple people will be entering data simultaneously. |

---

## Reporting Issues and Feedback

TMS is in beta. Your feedback is essential.

**For access problems** (locked out, wrong code, missing account): contact your Wing Admin.

**For bugs or unexpected behaviour**: note the steps that led to the problem, any error message shown, and your browser/device, then pass this to your Wing Admin or directly to the TMS administrator.

**For feedback on features or workflow**: your Wing Admin is collecting structured feedback throughout the beta period. Written notes after each parade night are the most useful format.

---

## Quick Reference

| Task | Where |
|------|-------|
| Create a parade night | Parade Nights → New Parade Night |
| Add a session to a parade night | Open the parade night → Add Session |
| Record session outcome | Open the session → Set Status |
| Publish a parade night | Open the parade night → Publish |
| Close a parade night | Open the parade night → Close |
| Add a facilitator | Facilitators → Add Facilitator |
| View training reports | Reports |
| Log out | Top navigation → Log Out |

---

*TMS v17.1 · 7 Wing Beta · 2026*
